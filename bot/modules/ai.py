import json
from asyncio import create_task

from httpx import AsyncClient, Timeout

from bot import LOGGER, user_data
from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_message,
    send_message,
)


async def send_long_message(message, text, time=300):
    """
    Split and send long messages that exceed Telegram's 4096 character limit

    Args:
        message: Message to reply to
        text: Text content to send
        time: Time in seconds after which to auto-delete the messages

    Returns:
        List of sent message objects
    """
    # Maximum length for a single Telegram message
    MAX_LENGTH = 4000  # Using 4000 instead of 4096 to be safe

    # If the message is short enough, send it as is
    if len(text) <= MAX_LENGTH:
        msg = await send_message(message, text)
        create_task(auto_delete_message(msg, time=time))  # noqa: RUF006
        return [msg]

    # Split the message into chunks
    chunks = []
    current_chunk = ""

    # Split by paragraphs first (double newlines)
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        # If adding this paragraph would exceed the limit, start a new chunk
        if len(current_chunk) + len(paragraph) + 2 > MAX_LENGTH:
            # If the current chunk is not empty, add it to chunks
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # If the paragraph itself is too long, split it by sentences
            if len(paragraph) > MAX_LENGTH:
                sentences = paragraph.replace(". ", ".\n").split("\n")
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 > MAX_LENGTH:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = ""

                        # If the sentence is still too long, split it by words
                        if len(sentence) > MAX_LENGTH:
                            words = sentence.split(" ")
                            for word in words:
                                if len(current_chunk) + len(word) + 1 > MAX_LENGTH:
                                    chunks.append(current_chunk)
                                    current_chunk = word + " "
                                else:
                                    current_chunk += word + " "
                        else:
                            current_chunk = sentence + "\n\n"
                    else:
                        current_chunk += sentence + "\n\n"
            else:
                current_chunk = paragraph + "\n\n"
        else:
            current_chunk += paragraph + "\n\n"

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)

    # Send each chunk as a separate message
    sent_messages = []
    for i, chunk in enumerate(chunks):
        # Add part number if there are multiple chunks
        if len(chunks) > 1:
            prefix = f"<b>Part {i + 1}/{len(chunks)}</b>\n\n"
            chunk = prefix + chunk

        msg = await send_message(message, chunk)
        create_task(auto_delete_message(msg, time=time))  # noqa: RUF006
        sent_messages.append(msg)

    return sent_messages


@new_task
async def ask_ai(_, message):
    """
    Command handler for /ask
    Sends user's question to the configured AI provider and displays the response
    """
    # Check if message is valid
    if not message or not hasattr(message, "from_user") or not message.from_user:
        LOGGER.error("Invalid message object received in ask_ai")
        return

    # Check if message has text
    if not hasattr(message, "text") or not message.text:
        LOGGER.error("Message without text received in ask_ai")
        return

    # Check if Extra Modules are enabled
    if not Config.ENABLE_EXTRA_MODULES:
        error_msg = await send_message(
            message,
            "❌ <b>AI module is currently disabled.</b>\n\nPlease contact the bot owner to enable it.",
        )
        # Auto-delete error message after 5 minutes
        create_task(auto_delete_message(error_msg, message, time=300))  # noqa: RUF006
        return

    user_id = message.from_user.id

    # Get user-specific settings if available
    user_dict = user_data.get(user_id, {})

    # Determine which AI provider to use (user settings take priority)
    ai_provider = user_dict.get(
        "DEFAULT_AI_PROVIDER", Config.DEFAULT_AI_PROVIDER
    ).lower()

    # Check if this is a direct command without arguments (e.g., just "/ask")
    # In this case, we should show the help message
    if (
        not hasattr(message, "text")
        or not message.text
        or message.text.strip() == f"/{message.command[0]}"
        if (hasattr(message, "command") and message.command)
        else False
    ):
        provider_name = ai_provider.capitalize()
        help_msg = await send_message(
            message,
            f"🧠 <b>{provider_name} AI Chatbot</b>\n\n"
            "💓 <b>Command:</b> /ask <i>your question</i>\n\n"
            "👼 <b>Answer:</b> Send me your question to chat with AI.\n\n"
            f"🤖 <b>Current AI Provider:</b> {provider_name}\n\n"
            "⏳ <b>Wait for Answer:</b> On✅",
        )
        # Auto-delete help message after 5 minutes
        create_task(auto_delete_message(help_msg, time=300))  # noqa: RUF006
        # Auto-delete command message after 5 minutes
        create_task(auto_delete_message(message, time=300))  # noqa: RUF006
        return

    # Extract the question from the message
    try:
        # Simple approach: if the message starts with a command (like /ask), extract everything after it
        if hasattr(message, "text") and message.text:
            # Check if the message starts with a command
            if message.text.startswith("/"):
                # Find the first space after the command
                space_index = message.text.find(" ")
                if space_index != -1:
                    # Extract everything after the first space
                    question = message.text[space_index + 1 :].strip()
                else:
                    # No space found, so no question
                    error_msg = await send_message(
                        message,
                        "❌ <b>Error:</b> Could not extract your question. Please use the format: /ask your question here",
                    )
                    # Auto-delete error message after 5 minutes
                    create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                    # Auto-delete command message after 5 minutes
                    create_task(auto_delete_message(message, time=300))  # noqa: RUF006
                    return
            else:
                # Not a command, use the entire message as the question
                question = message.text.strip()
        else:
            # If we can't extract a question, show an error
            error_msg = await send_message(
                message,
                "❌ <b>Error:</b> Could not extract your question. Please use the format: /ask your question here",
            )
            # Auto-delete error message after 5 minutes
            create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
            # Auto-delete command message after 5 minutes
            create_task(auto_delete_message(message, time=300))  # noqa: RUF006
            return
    except Exception as e:
        # Handle any exceptions that might occur
        LOGGER.error(f"Error extracting question: {e!s}")
        error_msg = await send_message(
            message,
            "❌ <b>Error:</b> Could not extract your question. Please use the format: /ask your question here",
        )
        # Auto-delete error message after 5 minutes
        create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
        # Auto-delete command message after 5 minutes
        create_task(auto_delete_message(message, time=300))  # noqa: RUF006
        return

    # Send a waiting message
    wait_msg = await send_message(message, "⏳ <b>Processing your request...</b>")

    try:
        # Process the request based on the AI provider
        if ai_provider == "mistral":
            # Get Mistral API settings
            api_key = user_dict.get("MISTRAL_API_KEY", Config.MISTRAL_API_KEY)
            api_url = user_dict.get("MISTRAL_API_URL", Config.MISTRAL_API_URL)

            # Check if we have either an API key or URL
            if not api_key and not api_url:
                error_msg = await send_message(
                    message,
                    "❌ <b>Error:</b> No API key or URL configured for Mistral AI. Please set up Mistral AI in settings.",
                )
                # Auto-delete error message after 5 minutes
                create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                # Auto-delete command message after 5 minutes
                create_task(auto_delete_message(message, time=300))  # noqa: RUF006
                await delete_message(wait_msg)
                return

            # Get response from Mistral AI
            response = await get_ai_response(question, api_key, api_url, user_id)
            provider_display = "Mistral AI"

        elif ai_provider == "deepseek":
            # Get DeepSeek API settings
            api_key = user_dict.get("DEEPSEEK_API_KEY", Config.DEEPSEEK_API_KEY)
            api_url = user_dict.get("DEEPSEEK_API_URL", Config.DEEPSEEK_API_URL)

            # Check if we have either an API key or URL
            if not api_key and not api_url:
                error_msg = await send_message(
                    message,
                    "❌ <b>Error:</b> No API key or URL configured for DeepSeek AI. Please set up DeepSeek AI in settings.",
                )
                # Auto-delete error message after 5 minutes
                create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                # Auto-delete command message after 5 minutes
                create_task(auto_delete_message(message, time=300))  # noqa: RUF006
                await delete_message(wait_msg)
                return

            # Get response from DeepSeek AI
            response = await get_deepseek_response(
                question, api_key, api_url, user_id
            )
            provider_display = "DeepSeek AI"

        elif ai_provider == "chatgpt":
            # Get ChatGPT API settings
            api_key = user_dict.get("CHATGPT_API_KEY", Config.CHATGPT_API_KEY)
            api_url = user_dict.get("CHATGPT_API_URL", Config.CHATGPT_API_URL)

            # Check if we have either an API key or URL
            if not api_key and not api_url:
                error_msg = await send_message(
                    message,
                    "❌ <b>Error:</b> No API key or URL configured for ChatGPT. Please set up ChatGPT in settings.",
                )
                # Auto-delete error message after 5 minutes
                create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                # Auto-delete command message after 5 minutes
                create_task(auto_delete_message(message, time=300))  # noqa: RUF006
                await delete_message(wait_msg)
                return

            # Get response from ChatGPT
            response = await get_chatgpt_response(
                question, api_key, api_url, user_id
            )
            provider_display = "ChatGPT"

        elif ai_provider == "gemini":
            # Get Gemini API settings
            api_key = user_dict.get("GEMINI_API_KEY", Config.GEMINI_API_KEY)
            api_url = user_dict.get("GEMINI_API_URL", Config.GEMINI_API_URL)

            # Check if we have either an API key or URL
            if not api_key and not api_url:
                error_msg = await send_message(
                    message,
                    "❌ <b>Error:</b> No API key or URL configured for Gemini AI. Please set up Gemini AI in settings.",
                )
                # Auto-delete error message after 5 minutes
                create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                # Auto-delete command message after 5 minutes
                create_task(auto_delete_message(message, time=300))  # noqa: RUF006
                await delete_message(wait_msg)
                return

            # Get response from Gemini AI
            response = await get_gemini_response(question, api_key, api_url, user_id)
            provider_display = "Gemini AI"

        else:
            # Default to Mistral if the provider is not recognized
            api_key = user_dict.get("MISTRAL_API_KEY", Config.MISTRAL_API_KEY)
            api_url = user_dict.get("MISTRAL_API_URL", Config.MISTRAL_API_URL)

            # Check if we have either an API key or URL
            if not api_key and not api_url:
                error_msg = await send_message(
                    message,
                    "❌ <b>Error:</b> No API key or URL configured for Mistral AI. Please set up Mistral AI in settings.",
                )
                # Auto-delete error message after 5 minutes
                create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                # Auto-delete command message after 5 minutes
                create_task(auto_delete_message(message, time=300))  # noqa: RUF006
                await delete_message(wait_msg)
                return

            # Get response from Mistral AI
            response = await get_ai_response(question, api_key, api_url, user_id)
            provider_display = "Mistral AI"

        # Format the response
        formatted_response = f"🤖 <b>{provider_display}:</b>\n\n{response}"

        # Send the response using the long message handler to handle message length limits
        # This will automatically handle messages that are too long for Telegram
        await send_long_message(message, formatted_response, time=300)

    except Exception as e:
        LOGGER.error(f"Error in AI response: {e!s}")
        error_msg = await send_message(message, f"❌ <b>Error:</b> {e!s}")
        # Auto-delete error message after 5 minutes
        create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006

    # Delete the waiting message
    await delete_message(wait_msg)

    # Auto-delete the command message after 5 minutes
    create_task(auto_delete_message(message, time=300))  # noqa: RUF006


async def get_ai_response(question, api_key, api_url, user_id):
    """
    Get a response from the AI using either direct API key or external API URL
    Falls back to the other method if one fails
    """
    # Try with API key first if available
    if api_key:
        try:
            return await get_response_with_api_key(question, api_key)
        except Exception as e:
            # If API URL is available, try that as fallback
            if api_url:
                LOGGER.info("Falling back to external API URL")
                return await get_response_with_api_url(question, api_url, user_id)
            raise e

    # If no API key but URL is available
    elif api_url:
        try:
            return await get_response_with_api_url(question, api_url, user_id)
        except Exception as e:
            raise Exception(
                f"Failed to get response from external API: {e!s}"
            ) from e

    # This should never happen due to earlier checks
    raise Exception("No API key or URL configured")


async def get_response_with_api_key(question, api_key):
    """
    Get a response from Mistral AI using the official API
    """
    url = "https://api.mistral.ai/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": question}],
    }

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]


async def get_response_with_api_url(question, api_url, user_id):
    """
    Get a response from Mistral AI using an external API URL
    """
    # Ensure the URL doesn't end with a slash
    api_url = api_url.rstrip("/")

    data = {
        "id": user_id,  # Using user's ID for history
        "question": question,
    }

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(api_url, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        try:
            response_data = response.json()

            if response_data.get("status") == "success":
                return response_data.get("answer", "No answer provided")
            raise Exception(
                f"API returned error: {response_data.get('error', 'Unknown error')}"
            )
        except json.JSONDecodeError as e:
            raise Exception("Invalid JSON response from API") from e


async def get_deepseek_response(question, api_key, api_url, user_id):
    """
    Get a response from the DeepSeek AI using either direct API key or external API URL
    Falls back to the other method if one fails
    """
    # Try with API key first if available
    if api_key:
        try:
            return await get_deepseek_response_with_api_key(question, api_key)
        except Exception as e:
            # If API URL is available, try that as fallback
            if api_url:
                LOGGER.info("Falling back to external API URL")
                return await get_deepseek_response_with_api_url(
                    question, api_url, user_id
                )
            raise e

    # If no API key but URL is available
    elif api_url:
        try:
            return await get_deepseek_response_with_api_url(
                question, api_url, user_id
            )
        except Exception as e:
            raise Exception(
                f"Failed to get response from external API: {e!s}"
            ) from e

    # This should never happen due to earlier checks
    raise Exception("No API key or URL configured")


async def get_deepseek_response_with_api_key(question, api_key):
    """
    Get a response from DeepSeek AI using the official API
    """
    url = "https://api.deepseek.com/v1/chat/completions"  # This is a placeholder URL

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    data = {
        "model": "deepseek-chat",  # This is a placeholder model name
        "messages": [{"role": "user", "content": question}],
    }

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]


async def get_deepseek_response_with_api_url(question, api_url, user_id):
    """
    Get a response from DeepSeek AI using an external API URL
    """
    # Ensure the URL doesn't end with a slash
    api_url = api_url.rstrip("/")

    # Check if this is a specific API URL format
    if "deepseek" in api_url and "workers.dev" in api_url:
        # Use a GET request format with query parameter
        full_url = f"{api_url}/?question={question}"

        timeout = Timeout(30.0, connect=10.0)

        async with AsyncClient(timeout=timeout) as client:
            response = await client.get(full_url)

            if response.status_code != 200:
                raise Exception(
                    f"API returned status code {response.status_code}: {response.text}"
                )

            try:
                response_data = response.json()

                if response_data.get("status") == "success":
                    return response_data.get("message", "No message provided")
                raise Exception(
                    f"API returned error: {response_data.get('error', 'Unknown error')}"
                )
            except json.JSONDecodeError as e:
                raise Exception("Invalid JSON response from API") from e
    else:
        # Use a more standard POST request format for custom endpoints
        data = {
            "id": user_id,  # Using user's ID for history
            "question": question,
        }

        timeout = Timeout(30.0, connect=10.0)

        async with AsyncClient(timeout=timeout) as client:
            response = await client.post(api_url, json=data)

            if response.status_code != 200:
                raise Exception(
                    f"API returned status code {response.status_code}: {response.text}"
                )

            try:
                response_data = response.json()

                if response_data.get("status") == "success":
                    return response_data.get(
                        "message", response_data.get("answer", "No answer provided")
                    )
                raise Exception(
                    f"API returned error: {response_data.get('error', 'Unknown error')}"
                )
            except json.JSONDecodeError as e:
                raise Exception("Invalid JSON response from API") from e


async def get_chatgpt_response(question, api_key, api_url, user_id):
    """
    Get a response from ChatGPT using either direct API key or external API URL
    Falls back to the other method if one fails
    """
    # Try with API key first if available
    if api_key:
        try:
            return await get_chatgpt_response_with_api_key(question, api_key)
        except Exception as e:
            # If API URL is available, try that as fallback
            if api_url:
                LOGGER.info("Falling back to external API URL")
                return await get_chatgpt_response_with_api_url(
                    question, api_url, user_id
                )
            raise e

    # If no API key but URL is available
    elif api_url:
        try:
            return await get_chatgpt_response_with_api_url(
                question, api_url, user_id
            )
        except Exception as e:
            raise Exception(
                f"Failed to get response from external API: {e!s}"
            ) from e

    # This should never happen due to earlier checks
    raise Exception("No API key or URL configured")


async def get_chatgpt_response_with_api_key(question, api_key):
    """
    Get a response from ChatGPT using the official OpenAI API
    """
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": question}],
    }

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]


async def get_chatgpt_response_with_api_url(question, api_url, user_id):
    """
    Get a response from ChatGPT using an external API URL
    """
    # Ensure the URL doesn't end with a slash
    api_url = api_url.rstrip("/")

    data = {
        "id": user_id,  # Using user's ID for history
        "question": question,
    }

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(api_url, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        try:
            response_data = response.json()

            if response_data.get("status") == "success":
                return response_data.get(
                    "message", response_data.get("answer", "No answer provided")
                )
            raise Exception(
                f"API returned error: {response_data.get('error', 'Unknown error')}"
            )
        except json.JSONDecodeError as e:
            raise Exception("Invalid JSON response from API") from e


async def get_gemini_response(question, api_key, api_url, user_id):
    """
    Get a response from the Gemini AI using either direct API key or external API URL
    Falls back to the other method if one fails
    """
    # Try with API key first if available
    if api_key:
        try:
            return await get_gemini_response_with_api_key(question, api_key)
        except Exception as e:
            # If API URL is available, try that as fallback
            if api_url:
                LOGGER.info("Falling back to external API URL")
                return await get_gemini_response_with_api_url(
                    question, api_url, user_id
                )
            raise e

    # If no API key but URL is available
    elif api_url:
        try:
            return await get_gemini_response_with_api_url(question, api_url, user_id)
        except Exception as e:
            raise Exception(
                f"Failed to get response from external API: {e!s}"
            ) from e

    # This should never happen due to earlier checks
    raise Exception("No API key or URL configured")


async def get_gemini_response_with_api_key(question, api_key):
    """
    Get a response from Gemini AI using the official Google AI API
    """
    # Format the URL with the API key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json",
    }

    data = {"contents": [{"parts": [{"text": question}]}]}

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        response_data = response.json()

        # Extract the response text from the Gemini API response format
        try:
            return response_data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise Exception(f"Unexpected response format: {e}") from e


async def get_gemini_response_with_api_url(question, api_url, user_id):
    """
    Get a response from Gemini AI using an external API URL
    """
    # Ensure the URL doesn't end with a slash
    api_url = api_url.rstrip("/")

    data = {
        "id": user_id,  # Using user's ID for history
        "question": question,
    }

    timeout = Timeout(30.0, connect=10.0)

    async with AsyncClient(timeout=timeout) as client:
        response = await client.post(api_url, json=data)

        if response.status_code != 200:
            raise Exception(
                f"API returned status code {response.status_code}: {response.text}"
            )

        try:
            response_data = response.json()

            if response_data.get("status") == "success":
                return response_data.get(
                    "message", response_data.get("answer", "No answer provided")
                )
            raise Exception(
                f"API returned error: {response_data.get('error', 'Unknown error')}"
            )
        except json.JSONDecodeError as e:
            raise Exception("Invalid JSON response from API") from e
