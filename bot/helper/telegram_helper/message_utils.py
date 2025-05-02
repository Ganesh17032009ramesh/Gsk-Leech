import contextlib
from asyncio import gather, sleep
from re import match as re_match
from time import time as get_time

from cachetools import TTLCache
from pyrogram import Client, enums
from pyrogram.errors import (
    FloodPremiumWait,
    FloodWait,
    MessageEmpty,
    MessageNotModified,
)
from pyrogram.types import InputMediaPhoto

from bot import (
    LOGGER,
    intervals,
    status_dict,
    task_dict_lock,
    user_data,
)
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import SetInterval
from bot.helper.ext_utils.db_handler import database
from bot.helper.ext_utils.exceptions import TgLinkException
from bot.helper.ext_utils.status_utils import get_readable_message

session_cache = TTLCache(
    maxsize=100,
    ttl=3600,
)  # Reduced from 1000 to 100, and 36000 to 3600


async def send_message(
    message,
    text,
    buttons=None,
    photo=None,
    markdown=False,
    block=True,
    bot_client=None,
):
    """Send a message using the specified bot client

    Args:
        message: Message to reply to or chat ID to send to
        text: Text content of the message
        buttons: Reply markup buttons
        photo: Photo to include with the message
        markdown: Whether to use Markdown formatting
        block: Whether to block until the message is sent
        bot_client: Bot client to use for sending (default: main bot)
    """
    parse_mode = enums.ParseMode.MARKDOWN if markdown else enums.ParseMode.HTML

    # Use the specified bot client or default to the main bot
    client = bot_client or TgClient.bot

    # Handle None message object
    if message is None:
        return "Cannot send message: message object is None"

    try:
        # Handle case where message is a chat_id (int or string)
        if isinstance(message, int | str):
            # If it's a string, try to convert to int if it's numeric
            if isinstance(message, str) and message.isdigit():
                message = int(message)

            return await client.send_message(
                chat_id=message,
                text=text,
                disable_web_page_preview=True,
                disable_notification=True,
                reply_markup=buttons,
                parse_mode=parse_mode,
            )

        # Check if message has required attributes
        if not hasattr(message, "chat") or not hasattr(message.chat, "id"):
            # Try to send to chat directly if message has an id attribute
            if hasattr(message, "id"):
                return await client.send_message(
                    chat_id=message.id,
                    text=text,
                    disable_web_page_preview=True,
                    disable_notification=True,
                    reply_markup=buttons,
                    parse_mode=parse_mode,
                )

            return f"Invalid message object: {type(message)}"

        if photo:
            return await message.reply_photo(
                photo=photo,
                reply_to_message_id=message.id,
                caption=text,
                reply_markup=buttons,
                disable_notification=True,
                parse_mode=parse_mode,
            )

        return await message.reply(
            text=text,
            quote=True,
            disable_web_page_preview=True,
            disable_notification=True,
            reply_markup=buttons,
            parse_mode=parse_mode,
        )

    except FloodWait as f:
        if not block:
            return message
        await sleep(f.value * 1.2)
        return await send_message(
            message,
            text,
            buttons,
            photo,
            markdown,
            block,
            bot_client,
        )
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def edit_message(
    message,
    text,
    buttons=None,
    photo=None,
    markdown=False,
    block=True,
):
    # Check if message is valid
    if not message or not hasattr(message, "chat") or not hasattr(message, "id"):
        return "Invalid message object"

    parse_mode = enums.ParseMode.MARKDOWN if markdown else enums.ParseMode.HTML
    try:
        # Check if message still exists by trying to get its chat and message ID
        chat_id = getattr(message.chat, "id", None)
        message_id = getattr(message, "id", None)

        if not chat_id or not message_id:
            return "Message has invalid chat_id or message_id"

        # Check message length but don't truncate if it contains expandable blockquotes
        max_length = 4096  # Telegram's message length limit
        if len(text) > max_length and "<blockquote expandable=" not in text:
            # Don't truncate automatically - let Telegram API handle the error
            # This will encourage proper use of expandable blockquotes
            pass

        if message.media:
            if photo:
                # Create InputMediaPhoto with the correct parse_mode
                media = InputMediaPhoto(photo, caption=text, parse_mode=parse_mode)
                return await message.edit_media(media=media, reply_markup=buttons)
            return await message.edit_caption(
                caption=text,
                reply_markup=buttons,
                parse_mode=parse_mode,
            )
        await message.edit(
            text=text,
            disable_web_page_preview=True,
            reply_markup=buttons,
            parse_mode=parse_mode,
        )
    except FloodWait as f:
        if not block:
            return message
        await sleep(f.value * 1.2)
        return await edit_message(message, text, buttons, photo, markdown)
    except (MessageNotModified, MessageEmpty):
        # Message content hasn't changed or is empty, not an error
        return message
    except Exception as e:
        error_str = str(e)
        # Check for MESSAGE_TOO_LONG error and suggest using expandable blockquotes
        if "MESSAGE_TOO_LONG" in error_str:
            LOGGER.error(
                f"Message too long: {error_str}. Consider using expandable blockquotes for long content."
            )
            # Try to send a notification about using expandable blockquotes
            with contextlib.suppress(Exception):
                await message.reply(
                    "The message is too long for Telegram. Please use expandable blockquotes for long content sections.",
                    quote=True,
                )
        # Only log at debug level for common Telegram API errors
        elif (
            "MESSAGE_ID_INVALID" in error_str
            or "message to edit not found" in error_str.lower()
        ):
            pass
        else:
            LOGGER.error(error_str)
        return error_str


async def send_file(message, file, caption="", buttons=None):
    try:
        return await message.reply_document(
            document=file,
            quote=True,
            caption=caption,
            disable_notification=True,
            reply_markup=buttons,
        )

    except FloodWait as f:
        await sleep(f.value * 1.2)
        return await send_file(message, file, caption, buttons)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def send_rss(text, chat_id, thread_id):
    # Validate input parameters
    if not text or not text.strip():
        LOGGER.error("Attempted to send empty RSS message")
        return "Message is empty"

    # Ensure text is not too long
    if len(text) > 4096:
        text = text[:4093] + "..."

    # Remove zero-width and control characters that might cause issues
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = "".join(c if ord(c) >= 32 or c == "\n" else " " for c in text)

    try:
        app = TgClient.user or TgClient.bot
        return await app.send_message(
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=True,
            message_thread_id=thread_id,
            disable_notification=True,
        )

    except MessageEmpty:
        LOGGER.error("Telegram says: Message is empty")
        # Try with a simplified message as a fallback
        try:
            simplified_text = "RSS Update: Unable to display full content due to formatting issues."
            return await app.send_message(
                chat_id=chat_id,
                text=simplified_text,
                disable_web_page_preview=True,
                message_thread_id=thread_id,
                disable_notification=True,
            )

        except Exception as e2:
            LOGGER.error(f"Failed to send simplified message too: {e2}")
            return str(e2)
    except (FloodWait, FloodPremiumWait) as f:
        await sleep(f.value * 1.2)
        return await send_rss(text, chat_id, thread_id)
    except Exception as e:
        LOGGER.error(f"Error sending RSS message: {e!s}")
        # Try with a simplified message as a fallback if it seems to be a formatting issue
        if "MESSAGE_EMPTY" in str(e) or "400" in str(e):
            try:
                simplified_text = "RSS Update: Unable to display full content due to formatting issues."
                return await app.send_message(
                    chat_id=chat_id,
                    text=simplified_text,
                    disable_web_page_preview=True,
                    message_thread_id=thread_id,
                    disable_notification=True,
                )

            except Exception as e2:
                LOGGER.error(f"Failed to send simplified message too: {e2}")
        return str(e)


async def delete_message(*args):
    msgs = []
    for msg in args:
        if msg:
            msgs.append(msg.delete())
            # Remove from database if it exists
            if hasattr(msg, "id") and hasattr(msg, "chat"):
                await database.remove_scheduled_deletion(msg.chat.id, msg.id)

    results = await gather(*msgs, return_exceptions=True)

    for msg, result in zip(args, results, strict=False):
        if isinstance(result, Exception):
            LOGGER.error(f"Failed to delete message {msg}: {result}", exc_info=True)


async def delete_links(message):
    if not Config.DELETE_LINKS:
        return

    msgs = []
    if reply_to := message.reply_to_message:
        msgs.append(reply_to)
    msgs.append(message)

    await delete_message(*msgs)


async def auto_delete_message(*args, time=300, bot_id=None):
    """Schedule messages for automatic deletion after a specified time

    Args:
        *args: Messages to delete
        time: Time in seconds after which to delete the messages
        bot_id: ID of the bot that sent the message (default: main bot ID)
    """
    if time and time > 0:
        # Store messages for deletion in database
        message_ids = []
        chat_ids = []
        for msg in args:
            if msg and hasattr(msg, "id") and hasattr(msg, "chat"):
                message_ids.append(msg.id)
                chat_ids.append(msg.chat.id)
                # Message scheduled for deletion

        if message_ids and chat_ids:
            delete_time = int(get_time() + time)

            # Determine which bot sent the message
            if bot_id is None:
                # Try to determine the bot ID from the message's _client attribute if available
                if (
                    args
                    and hasattr(args[0], "_client")
                    and hasattr(args[0]._client, "me")
                ):
                    client = args[0]._client
                    if hasattr(client.me, "id"):
                        bot_id = str(client.me.id)
                        # Bot ID determined from message client
                    else:
                        bot_id = TgClient.ID
                        # Using default bot ID
                else:
                    bot_id = TgClient.ID
                    # Using default bot ID

            await database.store_scheduled_deletion(
                chat_ids,
                message_ids,
                delete_time,
                bot_id,
            )
            # Messages stored for deletion

        # Instead of blocking with sleep, let the scheduled deletion system handle it
        # The process_pending_deletions function will handle this on next run


async def delete_status():
    async with task_dict_lock:
        for key, data in list(status_dict.items()):
            try:
                await delete_message(data["message"])
                del status_dict[key]
            except Exception as e:
                LOGGER.error(str(e))


async def get_tg_link_message(link, user_id=""):
    message = None
    links = []
    user_session = None

    if user_id:
        if user_id in session_cache:
            user_session = session_cache[user_id]
        else:
            user_dict = user_data.get(user_id, {})
            session_string = user_dict.get("session_string")
            if session_string:
                user_session = Client(
                    f"session_{user_id}",
                    Config.TELEGRAM_API,
                    Config.TELEGRAM_HASH,
                    session_string=session_string,
                    no_updates=True,
                )
                await user_session.start()
                session_cache[user_id] = user_session
            else:
                user_session = TgClient.user

    if link.startswith("https://t.me/"):
        private = False
        msg = re_match(
            r"https:\/\/t\.me\/(?:c\/)?([^\/]+)(?:\/[^\/]+)?\/([0-9-]+)",
            link,
        )
    else:
        private = True
        msg = re_match(
            r"tg:\/\/openmessage\?user_id=([0-9]+)&message_id=([0-9-]+)",
            link,
        )
        if not user_session:
            raise TgLinkException(
                "USER_SESSION_STRING required for this private link!",
            )

    chat = msg[1]
    msg_id = msg[2]
    if "-" in msg_id:
        start_id, end_id = map(int, msg_id.split("-"))
        msg_id = start_id
        btw = end_id - start_id
        if private:
            link = link.split("&message_id=")[0]
            links.append(f"{link}&message_id={start_id}")
            for _ in range(btw):
                start_id += 1
                links.append(f"{link}&message_id={start_id}")
        else:
            link = link.rsplit("/", 1)[0]
            links.append(f"{link}/{start_id}")
            for _ in range(btw):
                start_id += 1
                links.append(f"{link}/{start_id}")
    else:
        msg_id = int(msg_id)

    if chat.isdigit():
        chat = int(chat) if private else int(f"-100{chat}")

    if not private:
        try:
            # Get the message by its ID with Electrogram compatibility
            try:
                message = await TgClient.bot.get_messages(
                    chat_id=chat,
                    message_ids=msg_id,
                )
            except TypeError as e:
                # Handle case where get_messages has different parameters in Electrogram
                if "unexpected keyword argument" in str(
                    e
                ):  # Try alternative approach for Electrogram
                    message = await TgClient.bot.get_messages(
                        chat,  # chat_id as positional argument
                        msg_id,  # message_ids as positional argument
                    )
                else:
                    raise
            if message.empty:
                private = True
        except Exception as e:
            private = True
            if not user_session:
                raise e

    if not private:
        return (links, TgClient.bot) if links else (message, TgClient.bot)
    if user_session:
        try:
            # Get the message by its ID with Electrogram compatibility
            try:
                user_message = await user_session.get_messages(
                    chat_id=chat,
                    message_ids=msg_id,
                )
            except TypeError as e:
                # Handle case where get_messages has different parameters in Electrogram
                if "unexpected keyword argument" in str(
                    e
                ):  # Try alternative approach for Electrogram
                    user_message = await user_session.get_messages(
                        chat,  # chat_id as positional argument
                        msg_id,  # message_ids as positional argument
                    )
                else:
                    raise
        except Exception as e:
            raise TgLinkException("We don't have access to this chat!") from e
        if not user_message.empty:
            return (links, user_session) if links else (user_message, user_session)
        return None, None
    raise TgLinkException("Private: Please report!")


async def update_status_message(sid, force=False):
    if intervals["stopAll"]:
        return
    async with task_dict_lock:
        if not status_dict.get(sid):
            if obj := intervals["status"].get(sid):
                obj.cancel()
                del intervals["status"][sid]
            return
        if not force and get_time() - status_dict[sid]["time"] < 3:
            return
        status_dict[sid]["time"] = get_time()
        page_no = status_dict[sid]["page_no"]
        status = status_dict[sid]["status"]
        is_user = status_dict[sid]["is_user"]
        page_step = status_dict[sid]["page_step"]
        text, buttons = await get_readable_message(
            sid,
            is_user,
            page_no,
            status,
            page_step,
        )
        if text is None:
            del status_dict[sid]
            if obj := intervals["status"].get(sid):
                obj.cancel()
                del intervals["status"][sid]
            return
        if text != status_dict[sid]["message"].text:
            message = await edit_message(
                status_dict[sid]["message"],
                text,
                buttons,
                block=False,
            )
            if isinstance(message, str):
                # Check for common Telegram API errors that indicate the message is no longer valid
                if (
                    message.startswith("Telegram says: [40")
                    or "MESSAGE_ID_INVALID" in message
                    or "message to edit not found" in message.lower()
                ):
                    del status_dict[sid]
                    if obj := intervals["status"].get(sid):
                        obj.cancel()
                        del intervals["status"][sid]
                else:
                    # Only log as error for non-standard issues
                    LOGGER.error(
                        f"Status with id: {sid} haven't been updated. Error: {message}",
                    )
                return
            status_dict[sid]["message"].text = text
            status_dict[sid]["time"] = get_time()


async def send_status_message(msg, user_id=0):
    if intervals["stopAll"]:
        return
    sid = user_id or msg.chat.id
    is_user = bool(user_id)
    async with task_dict_lock:
        if sid in status_dict:
            page_no = status_dict[sid]["page_no"]
            status = status_dict[sid]["status"]
            page_step = status_dict[sid]["page_step"]
            text, buttons = await get_readable_message(
                sid,
                is_user,
                page_no,
                status,
                page_step,
            )
            if text is None:
                del status_dict[sid]
                if obj := intervals["status"].get(sid):
                    obj.cancel()
                    del intervals["status"][sid]
                return
            old_message = status_dict[sid]["message"]
            message = await send_message(msg, text, buttons, block=False)
            if isinstance(message, str):
                LOGGER.error(
                    f"Status with id: {sid} haven't been sent. Error: {message}",
                )
                return
            await delete_message(old_message)
            message.text = text
            status_dict[sid].update({"message": message, "time": get_time()})
        else:
            text, buttons = await get_readable_message(sid, is_user)
            if text is None:
                return
            message = await send_message(msg, text, buttons, block=False)
            if isinstance(message, str):
                LOGGER.error(
                    f"Status with id: {sid} haven't been sent. Error: {message}",
                )
                return
            message.text = text
            status_dict[sid] = {
                "message": message,
                "time": get_time(),
                "page_no": 1,
                "page_step": 1,
                "status": "All",
                "is_user": is_user,
            }
        if not intervals["status"].get(sid) and not is_user:
            intervals["status"][sid] = SetInterval(
                1,
                update_status_message,
                sid,
            )
