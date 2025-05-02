import gc
import hashlib
import time
from asyncio import CancelledError, create_task, gather, sleep

from pyrogram.errors import PeerIdInvalid
from pyrogram.types import Message

from bot import LOGGER
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import new_task

try:
    from bot.helper.ext_utils.gc_utils import smart_garbage_collection
except ImportError:
    smart_garbage_collection = None
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    edit_message,
    send_message,
)

# Create a module-specific logger
MUSIC_LOGGER = LOGGER.getChild("music_search")
MUSIC_LOGGER.setLevel("ERROR")  # Only show errors


# Cache for valid chat IDs to avoid repeated errors
# Using LRU cache pattern with size limits to prevent memory leaks
class LRUCache:
    """LRU Cache implementation with size limit and expiration to prevent memory leaks."""

    def __init__(self, max_size=100, expiry_seconds=3600):
        self.cache = {}  # {key: (value, timestamp)}
        self.max_size = max_size
        self.access_order = []
        self.expiry_seconds = expiry_seconds

    def _is_expired(self, timestamp):
        """Check if a cache entry has expired."""
        if self.expiry_seconds <= 0:  # No expiration
            return False
        return (time.time() - timestamp) > self.expiry_seconds

    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        if self.expiry_seconds <= 0:  # No expiration
            return

        current_time = time.time()
        expired_keys = []

        for key in list(self.cache.keys()):
            _, timestamp = self.cache[key]
            if (current_time - timestamp) > self.expiry_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            self.access_order.remove(key)
            del self.cache[key]

    def get(self, key):
        """Get item from cache and update access order."""
        self._cleanup_expired()

        if key in self.cache:
            value, timestamp = self.cache[key]

            # Check if expired
            if self._is_expired(timestamp):
                self.access_order.remove(key)
                del self.cache[key]
                return None

            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            # Update timestamp
            self.cache[key] = (value, time.time())
            return value
        return None

    def put(self, key, value):
        """Add item to cache with LRU eviction policy."""
        self._cleanup_expired()

        current_time = time.time()
        if key in self.cache:
            # Update existing item
            self.cache[key] = (value, current_time)
            self.access_order.remove(key)
            self.access_order.append(key)
        else:
            # Add new item, evict if necessary
            if len(self.cache) >= self.max_size:
                # Remove least recently used item
                lru_key = self.access_order.pop(0)
                del self.cache[lru_key]
            self.cache[key] = (value, current_time)
            self.access_order.append(key)

    def contains(self, key):
        """Check if key exists in cache and not expired."""
        if key not in self.cache:
            return False

        _, timestamp = self.cache[key]
        if self._is_expired(timestamp):
            # Clean up expired entry
            self.access_order.remove(key)
            del self.cache[key]
            return False

        return True

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.access_order.clear()


# Initialize caches with reasonable size limits and expiration times
VALID_CHAT_IDS = {
    "bot": LRUCache(
        max_size=50, expiry_seconds=3600
    ),  # 1 hour expiry for chat validation
    "user": LRUCache(max_size=50, expiry_seconds=3600),
}

# Cache for search results to avoid redundant searches
SEARCH_RESULTS_CACHE = LRUCache(
    max_size=20, expiry_seconds=300
)  # 5 minutes expiry for search results


# Background task to periodically clean up caches
async def cache_cleanup_task():
    """Background task to periodically clean up all caches to prevent memory leaks."""
    while True:
        try:
            # Sleep for 5 minutes between cleanups
            await sleep(300)

            # Get current timestamp for logging
            time.strftime("%Y-%m-%d %H:%M:%S")
            MUSIC_  # Clean up all caches
            for client_type in VALID_CHAT_IDS:
                cache = VALID_CHAT_IDS[client_type]
                before_size = len(cache.cache)
                cache._cleanup_expired()
                after_size = len(cache.cache)
                if before_size > after_size:
                    MUSIC_  # Force garbage collection after cache cleanup
            if smart_garbage_collection:
                smart_garbage_collection(aggressive=False)
            else:
                gc.collect()

            # Clean up search results cache
            before_size = len(SEARCH_RESULTS_CACHE.cache)
            SEARCH_RESULTS_CACHE._cleanup_expired()
            after_size = len(SEARCH_RESULTS_CACHE.cache)
            if before_size > after_size:
                MUSIC_LOGGER.info(
                    f"Cleaned up {before_size - after_size} expired search results"
                )
        except Exception as e:
            MUSIC_LOGGER.error(f"Error in cache cleanup task: {e}")


# Start the cache cleanup task
create_task(cache_cleanup_task())


# Function to generate a cache key for search results
def generate_search_key(chat_id: int, query: str, client_type: str) -> str:
    """Generate a unique cache key for search results.

    Args:
        chat_id: The chat ID being searched
        query: The search query
        client_type: The client type (bot or user)

    Returns:
        A unique string key for caching
    """
    # Normalize the query to ensure consistent keys
    normalized_query = query.lower().strip()
    # Create a unique key combining all parameters
    key = f"{chat_id}:{normalized_query}:{client_type}"
    # Use hash for shorter keys and to avoid any special character issues
    return hashlib.md5(key.encode()).hexdigest()


# Function to update search status with animation
async def update_search_status(message, query, total_channels):
    """Update the search status message with an animation to show progress.

    Args:
        message: The message to update
        query: The search query
        total_channels: Total number of channels being searched
    """
    search_animations = [
        "🔍 Searching",
        "🔍 Searching.",
        "🔍 Searching..",
        "🔍 Searching...",
    ]
    i = 0

    try:
        while True:
            status_text = f"<b>{search_animations[i]}</b>\n\n"
            status_text += f"<b>Query:</b> <code>{query}</code>\n"
            status_text += f"<b>Searching in:</b> {total_channels} channels\n"
            status_text += "\n<i>Please wait, this may take a moment...</i>"

            await edit_message(message, status_text)
            i = (i + 1) % len(search_animations)
            await sleep(0.5)  # Update every 0.5 seconds
    except CancelledError:
        # Task was cancelled, which is expected
        pass
    except Exception as e:
        MUSIC_LOGGER.error(f"Error in search status update: {e}")


async def format_duration(seconds: int) -> str:
    """Convert seconds to a formatted duration string."""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


async def format_size(bytes_size: int) -> str:
    """Convert bytes to a formatted size string."""
    size_mb = bytes_size / (1024 * 1024)
    return f"{size_mb:.2f} MB"


async def validate_chat_id(client, chat_id: int, client_type: str) -> bool:
    """Validate if a chat ID is accessible by the client.

    Args:
        client: The Telegram client (bot or user)
        chat_id: The chat ID to validate
        client_type: Either 'bot' or 'user'

    Returns:
        bool: True if the chat is valid and accessible, False otherwise
    """
    # If already validated, return cached result (using LRU cache)
    if VALID_CHAT_IDS[client_type].contains(chat_id):
        return VALID_CHAT_IDS[client_type].get(chat_id)

    # Try to get basic chat info to validate access
    try:
        # Use get_chat which is more likely to be available in all Pyrogram versions
        chat = await client.get_chat(chat_id)
        if chat:
            # Add to valid chats cache with positive result
            VALID_CHAT_IDS[client_type].put(chat_id, True)

            # For user client, log the chat name for debugging
            if client_type == "user":
                chat_title = getattr(chat, "title", str(chat_id))
                MUSIC_LOGGER.info(f"Using user client in chat: {chat_title}")
            return True
    except Exception as e:
        error_msg = str(e)
        # Cache the negative result to avoid repeated attempts
        VALID_CHAT_IDS[client_type].put(chat_id, False)

        if "PEER_ID_INVALID" in error_msg and client_type == "user":
            MUSIC_LOGGER.error(f"Invalid peer ID for chat {chat_id}")
        else:
            MUSIC_LOGGER.error(f"Error checking chat: {error_msg}")
        return False


async def search_music_in_chat(
    client,
    chat_id: int,
    query: str,
    offset: int = 0,
    limit: int = 20,
    client_type: str = "user",
) -> tuple[list[Message], bool, Exception | None]:
    """Search for music in a specific chat using the provided client.

    Note: This function should primarily be used with the user client, as bots cannot search messages.
    The bot client can only be used for direct message retrieval, not for searching.
    """
    # Check if this is a bot client - bots cannot search messages
    if client_type == "bot":
        MUSIC_return(
            [],
            False,
            Exception("BOT_METHOD_INVALID: Bots cannot search messages"),
        )

    # Validate if the chat is accessible
    if not await validate_chat_id(client, chat_id, client_type):
        return (
            [],
            False,
            PeerIdInvalid(
                f"Chat {chat_id} is not accessible by {client_type} client"
            ),
        )

    # Check cache for existing results
    cache_key = generate_search_key(chat_id, query, client_type)
    cached_result = SEARCH_RESULTS_CACHE.get(cache_key)
    if cached_result is not None:
        MUSIC_LOGGER.info(f"Using cached search results for {query} in {chat_id}")
        return cached_result

    try:
        # Try to use search_messages if available
        try:
            from pyrogram.enums import MessagesFilter

            # Use search_messages with AUDIO filter
            messages = []
            # Try to use offset if supported
            try:
                async for msg in client.search_messages(
                    chat_id=chat_id,
                    query=query,  # Search query in captions/titles
                    filter=MessagesFilter.AUDIO,
                    offset=offset,  # Use offset parameter
                    limit=limit,
                ):
                    messages.append(msg)
                    if len(messages) >= limit:
                        break

                has_more = len(messages) == limit  # Might have more
                result = (messages, has_more, None)
                # Cache the result
                SEARCH_RESULTS_CACHE.put(cache_key, result)
                return result
            except Exception:
                MUSIC_  # Try without offset
                messages = []
                async for msg in client.search_messages(
                    chat_id=chat_id,
                    query=query,  # Search query in captions/titles
                    filter=MessagesFilter.AUDIO,
                    limit=limit,
                ):
                    messages.append(msg)
                    if len(messages) >= limit:
                        break

                has_more = len(messages) == limit  # Might have more
                result = (messages, has_more, None)
                # Cache the result
                SEARCH_RESULTS_CACHE.put(cache_key, result)
                return result

        except (ImportError, AttributeError):
            # If search_messages or MessagesFilter is not available, fall back to get_messages
            MUSIC_  # Get recent messages without any filter
            messages = []
            try:
                # Try with get_chat_history which is more likely to be available
                async for msg in client.get_chat_history(chat_id, limit=limit * 5):
                    if hasattr(msg, "audio") and msg.audio:
                        # Get audio metadata
                        audio = msg.audio
                        title = (getattr(audio, "title", "") or "").lower()
                        performer = (getattr(audio, "performer", "") or "").lower()
                        file_name = (getattr(audio, "file_name", "") or "").lower()

                        # Check if query is in title, performer or filename with improved partial matching
                        query_lower = query.lower()
                        query_words = query_lower.split()

                        # Check for exact matches
                        exact_match = (
                            query_lower in title
                            or query_lower in performer
                            or query_lower in file_name
                        )

                        # Check for word boundary matches
                        word_match = False
                        for word in (
                            title.split() + performer.split() + file_name.split()
                        ):
                            word = word.lower()
                            if query_lower in word or any(
                                q in word for q in query_words
                            ):
                                word_match = True
                                break

                        # Check for substring matches
                        substring_match = (
                            any(q in title for q in query_words)
                            or any(q in performer for q in query_words)
                            or any(q in file_name for q in query_words)
                        )

                        if exact_match or word_match or substring_match:
                            messages.append(msg)

                        # Limit results
                        if len(messages) >= limit:
                            break
            except Exception as e2:
                LOGGER.error(f"Error using get_chat_history: {e2}")
                # Last resort: try to get messages one by one
                for i in range(1, 100):  # Get up to 100 recent messages
                    try:
                        msg = await client.get_messages(chat_id, i)
                        if msg and hasattr(msg, "audio") and msg.audio:
                            # Get audio metadata
                            audio = msg.audio
                            title = (getattr(audio, "title", "") or "").lower()
                            performer = (
                                getattr(audio, "performer", "") or ""
                            ).lower()
                            file_name = (
                                getattr(audio, "file_name", "") or ""
                            ).lower()

                            # Check if query is in title, performer or filename with improved partial matching
                            query_lower = query.lower()
                            query_words = query_lower.split()

                            # Check for exact matches
                            exact_match = (
                                query_lower in title
                                or query_lower in performer
                                or query_lower in file_name
                            )

                            # Check for word boundary matches
                            word_match = False
                            for word in (
                                title.split() + performer.split() + file_name.split()
                            ):
                                word = word.lower()
                                if query_lower in word or any(
                                    q in word for q in query_words
                                ):
                                    word_match = True
                                    break

                            # Check for substring matches
                            substring_match = (
                                any(q in title for q in query_words)
                                or any(q in performer for q in query_words)
                                or any(q in file_name for q in query_words)
                            )

                            if exact_match or word_match or substring_match:
                                messages.append(msg)

                            # Limit results
                            if len(messages) >= limit:
                                break
                    except Exception:
                        # Skip any errors for individual messages
                        pass

            has_more = False  # Can't determine if there are more
            result = (messages, has_more, None)
            # Cache the result
            SEARCH_RESULTS_CACHE.put(cache_key, result)
            return result
    except Exception as e:
        # Get client name safely
        try:
            if hasattr(client, "me"):
                if hasattr(client.me, "username"):
                    client_name = client.me.username
                else:
                    client_name = "Unknown"
            else:
                client_name = "Unknown"
        except Exception:
            client_name = "Unknown"

        MUSIC_LOGGER.error(
            f"Error searching in chat {chat_id} with client {client_name}: {e}"
        )
        return [], False, e


@new_task
async def music_search(_, message: Message):
    """Handle the music search command.

    This function allows users to search for music in configured channels.
    Users can either provide the search query directly with the command or
    reply to a message containing the search query.
    """
    user_id = message.from_user.id

    # Store original command message for later deletion
    cmd_message = message

    # Check if replying to a message
    reply_to = message.reply_to_message

    # Get query from command or reply
    query = ""
    if reply_to and reply_to.text:
        # Get query from replied message
        query = reply_to.text.strip()
    else:
        # Parse command arguments
        args = message.text.split(" ", 1)
        if len(args) > 1:
            query = args[1].strip()

    # If no query found, show help message
    if not query:
        help_msg = (
            f"<b>Usage:</b>\n"
            f"1. <code>/{BotCommands.MusicSearchCommand[0]} query</code> or <code>/{BotCommands.MusicSearchCommand[1]} query</code>\n"
            f"2. Reply to any message containing the search query with <code>/{BotCommands.MusicSearchCommand[0]}</code> or <code>/{BotCommands.MusicSearchCommand[1]}</code>"
        )
        help_message = await send_message(message, help_msg)
        # Delete help message after 5 minutes
        create_task(auto_delete_message(help_message, time=300))
        # Delete command message after 5 minutes
        create_task(auto_delete_message(cmd_message, time=300))
        # Delete reply message after 5 minutes if it exists
        if reply_to:
            create_task(auto_delete_message(reply_to, time=300))
        return

    # Send initial processing message
    status_msg = await send_message(
        message, f"<b>Searching for:</b> <code>{query}</code>"
    )

    # Get music search channels from config
    music_channels = Config.MUSIC_SEARCH_CHATS
    if not music_channels:
        await edit_message(
            status_msg,
            "No music search channels configured. Please add channels to MUSIC_SEARCH_CHATS in config.",
        )
        # Delete error message after 5 minutes
        create_task(auto_delete_message(status_msg, time=300))
        # Delete command message after 5 minutes
        create_task(auto_delete_message(cmd_message, time=300))
        # Delete reply message after 5 minutes if it exists
        if reply_to:
            create_task(auto_delete_message(reply_to, time=300))
        return

    # Prepare for parallel searches
    bot_results = []
    user_results = []
    bot_errors = []
    search_tasks = []

    # Update status message
    await edit_message(status_msg, f"<b>Searching for:</b> <code>{query}</code>")

    # Normalize query for case-insensitive and partial matching
    normalized_query = query.lower()

    # Function to process search results with caching and optimized processing
    async def process_search_results(client, chat_id, client_type):
        results = []
        try:
            # Generate a cache key for this specific search task
            task_cache_key = (
                f"task_{generate_search_key(chat_id, query, client_type)}"
            )
            cached_results = SEARCH_RESULTS_CACHE.get(task_cache_key)
            if cached_results is not None:
                MUSIC_LOGGER.info(f"Using cached search results for task {task_id}")
                return cached_results

            # Validate chat ID first
            if not await validate_chat_id(client, chat_id, client_type):
                if client_type == "bot":
                    bot_errors.append(f"Chat {chat_id}: Not accessible")
                # Cache negative result to avoid repeated validation
                SEARCH_RESULTS_CACHE.put(task_cache_key, results)
                return results

            # For bot clients, we know search will fail, so add a specific error
            if client_type == "bot":
                bot_errors.append(
                    f"Chat {chat_id}: BOT_METHOD_INVALID - Bots cannot search messages"
                )
                # Cache negative result
                SEARCH_RESULTS_CACHE.put(task_cache_key, results)
                return results

            # For user clients, attempt the search
            messages, _, error = await search_music_in_chat(
                client, chat_id, query, client_type=client_type
            )
            if error:
                # Log the error for debugging
                MUSIC_LOGGER.error(f"Error searching in chat {chat_id}: {error}")
                if client_type == "bot":
                    bot_errors.append(f"Chat {chat_id}: {error!s}")
                # Cache negative result
                SEARCH_RESULTS_CACHE.put(task_cache_key, results)
                return results

            # Messages are already filtered by the search function
            for msg in messages:
                if not hasattr(msg, "audio") or not msg.audio:
                    continue

                audio = msg.audio
                title = getattr(audio, "title", None) or "Untitled"
                performer = getattr(audio, "performer", None) or "Unknown Artist"

                try:
                    duration = await format_duration(getattr(audio, "duration", 0))
                    file_size = await format_size(getattr(audio, "file_size", 0))
                except Exception as e:
                    MUSIC_LOGGER.error(f"Error formatting audio metadata: {e}")
                    duration = "0:00"
                    file_size = "0.00 MB"

                # Calculate relevance score with improved partial matching
                title_lower = title.lower()
                performer_lower = performer.lower()
                file_name_lower = (getattr(audio, "file_name", "") or "").lower()

                # Split query into words for better partial matching
                query_words = normalized_query.split()

                relevance = 0

                # Check for exact matches first (highest priority)
                if normalized_query in title_lower:
                    relevance += 10  # Exact title match
                if normalized_query in performer_lower:
                    relevance += 8  # Exact performer match
                if normalized_query in file_name_lower:
                    relevance += 6  # Exact filename match

                # Check for word boundary matches (medium priority)
                # This helps find "King of Contradiction" when searching for "contradiction"
                for word in title_lower.split():
                    if normalized_query in word or any(
                        q in word for q in query_words
                    ):
                        relevance += 5

                for word in performer_lower.split():
                    if normalized_query in word or any(
                        q in word for q in query_words
                    ):
                        relevance += 4

                # Check for substring matches (lower priority)
                if any(q in title_lower for q in query_words):
                    relevance += 3
                if any(q in performer_lower for q in query_words):
                    relevance += 2
                if any(q in file_name_lower for q in query_words):
                    relevance += 1

                # Skip items with zero relevance
                if relevance == 0:
                    continue

                results.append(
                    {
                        "chat_id": chat_id,
                        "message_id": msg.id,
                        "title": title,
                        "performer": performer,
                        "duration": duration,
                        "file_size": file_size,
                        "file_id": getattr(audio, "file_id", ""),
                        "client": client_type,
                        "relevance": relevance,
                    }
                )

                # Limit results per chat
                if len(results) >= 5:  # Reduced from 10 to 5 for faster response
                    break

            # Cache the results for this task
            SEARCH_RESULTS_CACHE.put(task_cache_key, results)
            return results
        except Exception as e:
            MUSIC_LOGGER.error(
                f"Error in process_search_results for {client_type} client: {e}"
            )
            # Cache the error result to avoid repeated failures
            SEARCH_RESULTS_CACHE.put(task_cache_key, [])
            return []

    # Create search tasks - always use user client for searching since bots cannot search messages
    if TgClient.user:
        # User client can search messages
        # Searching channels using user client
        for chat_id in music_channels:
            search_tasks.append(
                process_search_results(TgClient.user, chat_id, "user")
            )
    elif TgClient.bot:
        # Only use bot client if user client is not available (will likely fail for searching)
        MUSIC_  # Add warning to status message
        await edit_message(
            status_msg,
            f"<b>Searching for:</b> <code>{query}</code>\n\n"
            "⚠️ <b>Warning:</b> User client not available. Bots cannot search messages in channels.\n"
            "Music search may not work properly. Please add a user session for better results.",
        )

        # Even though bot client will likely fail for searching, try it as a last resort
        for chat_id in music_channels:
            search_tasks.append(process_search_results(TgClient.bot, chat_id, "bot"))

    # Record start time for performance measurement
    search_start_time = time.time()

    # Update status message to show searching animation
    search_status_task = create_task(
        update_search_status(status_msg, query, len(music_channels))
    )

    # Run all search tasks in parallel
    all_results = await gather(*search_tasks)

    # Cancel the status update task
    search_status_task.cancel()

    # Calculate search time
    search_time = time.time() - search_start_time

    # Collect statistics
    total_messages_searched = 0
    channels_searched = 0

    # Combine results
    for result_list in all_results:
        if not result_list:
            continue

        # Count valid channels searched
        channels_searched += 1

        # Add to appropriate result list
        client_type = result_list[0]["client"]
        if client_type == "bot":
            bot_results.extend(result_list)
        else:
            user_results.extend(result_list)

        # Count total messages in this result
        total_messages_searched += len(result_list)

    # Sort results by relevance (higher score first)
    bot_results.sort(key=lambda x: x["relevance"], reverse=True)
    user_results.sort(key=lambda x: x["relevance"], reverse=True)

    # Limit total results
    bot_results = bot_results[:10]
    user_results = user_results[:10]

    # Combine results, prioritizing user results since they're more reliable for music search
    results = user_results + bot_results

    # Check if we have any results
    if not results:
        # Calculate search time string
        search_time_str = f"{search_time:.2f}"

        error_msg = f"<b>No results found for:</b> <code>{query}</code>\n"
        error_msg += (
            f"<i>Searched {channels_searched} channels in {search_time_str}s</i>\n\n"
        )

        # Add more specific error information
        if not TgClient.user:
            error_msg += "⚠️ <b>User client is not available.</b> Bots cannot search messages in channels.\n"
            error_msg += "Please add a user session to enable music search.\n\n"
        elif TgClient.user and len(music_channels) > 0:
            # Check if any channels were successfully validated
            user_valid_channels = [
                ch
                for ch in music_channels
                if VALID_CHAT_IDS["user"].contains(ch)
                and VALID_CHAT_IDS["user"].get(ch)
            ]

            if not user_valid_channels:
                error_msg += (
                    "⚠️ <b>User client cannot access any configured channels.</b>\n"
                )
                error_msg += "The user account needs to <b>join all channels</b> configured in MUSIC_SEARCH_CHATS.\n"
                error_msg += "Please make sure the user account has joined these channels/groups.\n\n"
            else:
                error_msg += f"Searched {len(user_valid_channels)} accessible channels but couldn't find matching audio files.\n"
                error_msg += "Try a different search term or check if the audio exists in the channels.\n\n"

        if bot_errors and len(bot_errors) > 0:
            error_msg += "<b>Errors encountered:</b>\n"
            # Show up to 3 errors to avoid too long message
            for error in bot_errors[:3]:
                error_msg += f"• {error}\n"
            if len(bot_errors) > 3:
                error_msg += f"• ...and {len(bot_errors) - 3} more errors\n"

        await edit_message(status_msg, error_msg)
        # Delete error message after 5 minutes
        create_task(auto_delete_message(status_msg, time=300))
        # Delete command message after 5 minutes
        create_task(auto_delete_message(cmd_message, time=300))
        # Delete reply message after 5 minutes if it exists
        if reply_to:
            create_task(auto_delete_message(reply_to, time=300))
        return

    # Create result message with buttons and statistics
    result_text = f"<b>Found {len(results)} results for:</b> <code>{query}</code>\n"

    # Add search statistics
    search_time_str = f"{search_time:.2f}"
    result_text += f"<i>Searched {channels_searched} channels, {total_messages_searched} messages in {search_time_str}s</i>\n\n"

    buttons = ButtonMaker()

    for i, result in enumerate(results, 1):
        # Highlight the matching parts in the title and performer
        title = result["title"]
        performer = result["performer"]

        # Add match indicators
        match_indicators = []
        if normalized_query in title.lower():
            match_indicators.append("title")
        if normalized_query in performer.lower():
            match_indicators.append("artist")

        # Add match indicator if it's a partial match
        if not match_indicators:
            for word in query.lower().split():
                if word in title.lower() or word in performer.lower():
                    match_indicators.append("partial")
                    break

        # Add match indicator text
        match_text = ""
        if match_indicators:
            match_text = f" <i>({', '.join(match_indicators)} match)</i>"

        result_text += (
            f"<b>{i}. {result['title']}</b>{match_text}\n"
            f"<b>Artist:</b> {result['performer']}\n"
            f"<b>Duration:</b> {result['duration']} | <b>Size:</b> {result['file_size']}\n\n"
        )

        # Truncate button text if too long
        button_text = f"{i}. {result['title']} - {result['performer']}"
        if len(button_text) > 60:  # Telegram has a limit on button text length
            button_text = button_text[:57] + "..."

        buttons.data_button(
            button_text,
            f"musget_{user_id}_{result['chat_id']}_{result['message_id']}_{cmd_message.id}_{reply_to.id if reply_to else 0}_{result['client']}",
        )

    buttons.data_button(
        "Cancel",
        f"muscancel_{user_id}_{cmd_message.id}_{reply_to.id if reply_to else 0}",
    )

    await edit_message(status_msg, result_text, buttons.build_menu(1))

    # When search results are found, delete command and reply messages immediately
    try:
        await cmd_message.delete()
    except Exception as e:
        MUSIC_LOGGER.error(f"Error deleting command message: {e}")
        # Fallback: Auto-delete after 5 minutes if immediate deletion fails
        create_task(auto_delete_message(cmd_message, time=300))

    # Delete reply message immediately if it exists
    if reply_to:
        try:
            await reply_to.delete()
        except Exception as e:
            MUSIC_LOGGER.error(f"Error deleting reply message: {e}")
            # Fallback: Auto-delete after 5 minutes if immediate deletion fails
            create_task(auto_delete_message(reply_to, time=300))

    # Auto-delete the results menu after 5 minutes if no selection is made
    create_task(auto_delete_message(status_msg, time=300))


async def music_get_callback(_, query):
    """Handle the music get callback.

    This function retrieves music files using the following strategy:
    1. Always use the bot client for message retrieval when available
    2. Only fall back to the user client if the bot client fails
    3. The client_type in the callback data only indicates which client found the message during search

    This approach ensures optimal performance and reliability, as bot clients are better suited
    for message retrieval, while user clients are necessary for searching functionality.
    """
    data = query.data.split("_")
    user_id = int(data[1])

    # Check if the callback is for the user who initiated the search
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return None

    # Silently acknowledge the callback without showing a notification
    await query.answer()

    # Try to delete the selection menu immediately after user makes a selection
    try:
        # We'll try to delete the message first, then proceed with downloading
        # This ensures the menu disappears immediately when user makes a selection
        await (
            query.message.delete()
        )  # No need to send a status message - we'll just forward the audio directly
    except Exception as e:
        LOGGER.error(f"Error deleting selection menu: {e}")
        # If deletion fails, we'll just update the existing message to show it's processing
        # Use a simple loading indicator instead of text
        await query.edit_message_text("⏳ <i>Processing...</i>")

    chat_id = int(data[2])
    message_id = int(data[3])
    cmd_message_id = int(data[4])
    reply_message_id = int(data[5])

    # Get client type from callback data (this indicates which client found the message)
    client_type = (
        data[6] if len(data) > 6 else "user"
    )  # This is just for tracking which client found the message

    # IMPORTANT: Always use bot client for message retrieval when possible
    # Only fall back to user client if bot client fails
    client = TgClient.bot if TgClient.bot else TgClient.user
    client_type = "bot" if TgClient.bot else "user"

    # Check if the selected client is available
    if (client_type == "bot" and not TgClient.bot) or (
        client_type == "user" and not TgClient.user
    ):
        await query.edit_message_text(
            f"The {client_type} client is not available. Please try again."
        )
        # Auto-delete error message after 5 minutes
        create_task(auto_delete_message(query.message, time=300))
        return None

    # Only log at debug level to avoid cluttering logs
    MUSIC_  # Try to validate the chat with both clients to find one that works
    user_client_valid = False
    bot_client_valid = False

    # Check if bot client can access this chat (prioritize bot client validation)
    if TgClient.bot:
        bot_client_valid = await validate_chat_id(TgClient.bot, chat_id, "bot")
        # No need to log successful validation

    # Check if user client can access this chat (as fallback)
    if TgClient.user:
        user_client_valid = await validate_chat_id(TgClient.user, chat_id, "user")
        # No need to log successful validation

    # Choose the best client based on validation results
    if not user_client_valid and not bot_client_valid:
        await query.edit_message_text(
            "Chat is not accessible by either bot or user client.\n"
            "Please make sure at least one client has access to this channel."
        )
        create_task(auto_delete_message(query.message, time=300))
        return None

    # For message retrieval, always try to use the client specified in the callback data first
    # This preserves the original intent of which client found the message
    # But we'll ensure we have a proper fallback mechanism later

    # If the specified client is not valid, switch to the other one if available
    if client_type == "user" and not user_client_valid and bot_client_valid:
        client_type = "bot"
    elif client_type == "bot" and not bot_client_valid and user_client_valid:
        client_type = "user"

    # No need to log which client we're using

    # Get the original message
    try:
        # Try with the selected client first
        message = None
        try:
            # No need to log message retrieval attempt

            # First try to resolve the peer to ensure it's valid
            try:
                # This will validate if the peer is accessible
                # We don't need to use the returned peer object, just checking if it resolves
                _ = await client.resolve_peer(chat_id)
            except Exception as peer_error:
                MUSIC_LOGGER.error(f"Error resolving peer {chat_id}: {peer_error}")
                # If we can't resolve the peer, we can't get the message
                raise

            # Now try to get the message
            try:
                # Use message_ids parameter as a list to match PyroFork's expected format
                messages = await client.get_messages(
                    chat_id=chat_id, message_ids=[message_id]
                )
                # get_messages returns a list when message_ids is a list
                if isinstance(messages, list) and len(messages) > 0:
                    message = messages[0]  # Get the first message from the list
                else:
                    message = messages

                if message and getattr(message, "audio", None):
                    MUSIC_LOGGER.info(
                        f"Found audio message {message_id} in chat {chat_id}"
                    )
                    return message
                if message:
                    MUSIC_LOGGER.info(
                        f"Found non-audio message {message_id} in chat {chat_id}"
                    )
                    return None
                MUSIC_LOGGER.warning(
                    f"No message found with ID {message_id} in chat {chat_id}"
                )
            except Exception:
                raise

        except Exception:
            message = None

        # If message not found with the selected client, try the other client as fallback
        if not message or not getattr(message, "audio", None):
            # Try the other client
            fallback_client = None
            fallback_client_type = None

            # Since we're now using bot client as primary, only fall back to user client if bot client fails
            if client_type == "bot" and TgClient.user and user_client_valid:
                fallback_client = TgClient.user
                fallback_client_type = "user"  # This case should rarely happen now, but keep it for completeness
            elif client_type == "user" and TgClient.bot and bot_client_valid:
                fallback_client = TgClient.bot
                fallback_client_type = "bot"

            if fallback_client:
                try:
                    # First try to resolve the peer with fallback client
                    try:
                        # We don't need to use the returned peer object, just checking if it resolves
                        _ = await fallback_client.resolve_peer(chat_id)
                    except Exception as peer_error:
                        MUSIC_LOGGER.error(
                            f"Fallback client error resolving peer {chat_id}: {peer_error}"
                        )
                        raise

                    # Now try to get the message with fallback client
                    try:
                        # Use message_ids parameter as a list to match PyroFork's expected format
                        fallback_messages = await fallback_client.get_messages(
                            chat_id=chat_id, message_ids=[message_id]
                        )
                        # get_messages returns a list when message_ids is a list
                        if (
                            isinstance(fallback_messages, list)
                            and len(fallback_messages) > 0
                        ):
                            message = fallback_messages[
                                0
                            ]  # Get the first message from the list
                        else:
                            message = fallback_messages

                        if message and getattr(message, "audio", None):
                            client_type = fallback_client_type
                        elif message:
                            MUSIC_LOGGER.info(
                                "Found non-audio message with fallback client"
                            )
                            return None
                        else:
                            MUSIC_LOGGER.warning(
                                "No message found with fallback client"
                            )
                    except Exception:
                        raise

                except Exception as e2:
                    MUSIC_LOGGER.error(f"Error with fallback client: {e2}")

        # If still no message found
        if not message or not getattr(message, "audio", None):
            await query.edit_message_text(
                "Music file not found or no longer available.\n\n"
                "The message might have been deleted or the audio file removed."
            )
            # Auto-delete error message after 5 minutes
            create_task(auto_delete_message(query.message, time=300))
            return None

        # Forward the audio to the user
        await message.forward(query.message.chat.id, disable_notification=True)

        # Delete the search results message immediately
        await query.message.delete()

        # Delete the command message immediately
        try:
            await TgClient.bot.delete_messages(query.message.chat.id, cmd_message_id)
        except Exception as e:
            MUSIC_LOGGER.error(f"Error deleting command message: {e}")

        # Delete the reply message immediately if it exists
        if reply_message_id != 0:
            try:
                await TgClient.bot.delete_messages(
                    query.message.chat.id, reply_message_id
                )
            except Exception as e:
                MUSIC_LOGGER.error(f"Error deleting reply message: {e}")

    except Exception as e:
        error_msg = str(e)
        MUSIC_LOGGER.error(f"Error getting music with {client_type} client: {e}")

        # Check for PEER_ID_INVALID error which indicates the client can't access the chat
        if "PEER_ID_INVALID" in error_msg:
            # This is a more specific error message for PEER_ID_INVALID
            error_text = (
                "⚠️ <b>Cannot access this channel or message.</b>\n\n"
                "This could be due to one of the following reasons:\n"
                "• The channel no longer exists\n"
                "• The message has been deleted\n"
                "• The user account needs to join the channel\n"
                "• The message ID might be invalid\n\n"
            )

            # Add specific guidance based on which client failed
            if client_type == "user":
                error_text += (
                    "<b>Recommendation:</b> Please make sure the user account has joined "
                    "this channel and has permission to access messages.\n\n"
                )
            elif client_type == "bot":
                error_text += (
                    "<b>Recommendation:</b> Please make sure the bot has been added "
                    "to this channel as an admin with permission to access messages.\n\n"
                )

            error_text += f"<i>Technical details: {error_msg[:100]}</i>"

            await query.edit_message_text(error_text)
            # Auto-delete error message after 5 minutes
            create_task(auto_delete_message(query.message, time=300))
            return None

        # Try the other client as fallback if the first one fails
        try:
            fallback_client = None
            fallback_client_type = None

            # Since we're now using bot client as primary, only fall back to user client if bot client fails
            if client_type == "bot" and TgClient.user and user_client_valid:
                fallback_client = TgClient.user
                fallback_client_type = "user"  # This case should rarely happen now, but keep it for completeness
            elif client_type == "user" and TgClient.bot and bot_client_valid:
                fallback_client = TgClient.bot
                fallback_client_type = "bot"
            if fallback_client:
                try:
                    # First try to resolve the peer with fallback client
                    try:
                        # We don't need to use the returned peer object, just checking if it resolves
                        _ = await fallback_client.resolve_peer(chat_id)
                    except Exception:
                        raise

                    # Now try to get the message with fallback client
                    try:
                        # Use message_ids parameter as a list to match PyroFork's expected format
                        messages = await fallback_client.get_messages(
                            chat_id=chat_id, message_ids=[message_id]
                        )
                        # get_messages returns a list when message_ids is a list
                        if isinstance(messages, list) and len(messages) > 0:
                            message = messages[
                                0
                            ]  # Get the first message from the list
                        else:
                            message = messages

                        if message and getattr(message, "audio", None):
                            await message.forward(
                                query.message.chat.id, disable_notification=True
                            )
                            await query.message.delete()

                            # Delete the command and reply messages
                            try:
                                await TgClient.bot.delete_messages(
                                    query.message.chat.id, cmd_message_id
                                )
                                if reply_message_id != 0:
                                    await TgClient.bot.delete_messages(
                                        query.message.chat.id, reply_message_id
                                    )
                            except Exception as e2:
                                LOGGER.error(f"Error deleting messages: {e2}")
                            return None
                        if message:
                            MUSIC_LOGGER.info(
                                "Found non-audio message with fallback client"
                            )
                            return None
                        MUSIC_LOGGER.warning("No message found with fallback client")
                    except Exception:
                        raise
                except Exception as e3:
                    MUSIC_LOGGER.error(f"Error in fallback client attempt: {e3}")
            else:
                MUSIC_LOGGER.warning("No fallback client available")
        except Exception as e2:
            MUSIC_LOGGER.error(f"Error in fallback handling: {e2}")

        # If all fallbacks fail, show error message
        error_text = (
            "⚠️ <b>Error retrieving music</b>\n\n"
            "The music file could not be retrieved after trying both user and bot clients.\n\n"
            "<b>Possible reasons:</b>\n"
            "• The file no longer exists\n"
            "• Neither the bot nor user account has access to the channel\n"
            "• The message ID is invalid or the message was deleted\n"
            "• The audio file format is not supported\n\n"
        )

        # Add specific guidance based on the error
        if "PEER_ID_INVALID" in str(e):
            error_text += (
                "<b>Recommendation:</b> Please make sure both the bot and user account "
                "have joined the channel and have permission to access messages.\n\n"
            )
        elif "FILE_REFERENCE" in str(e):
            error_text += (
                "<b>Recommendation:</b> The file reference has expired. Try searching again "
                "to get a fresh reference to the file.\n\n"
            )

        # Add technical details
        error_text += f"<i>Technical details: {str(e)[:100]}</i>"

        await query.edit_message_text(error_text)

        # Auto-delete error message after 5 minutes
        create_task(auto_delete_message(query.message, time=300))


async def music_cancel_callback(_, query):
    """Handle the music cancel callback."""
    data = query.data.split("_")
    user_id = int(data[1])
    cmd_message_id = int(data[2])
    reply_message_id = int(data[3])

    # Check if the callback is for the user who initiated the search
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return

    # Silently acknowledge the callback without showing a notification
    await query.answer()

    # Delete the search results message immediately
    await query.message.delete()

    # Delete the command message immediately
    try:
        await TgClient.bot.delete_messages(query.message.chat.id, cmd_message_id)
    except Exception as e:
        MUSIC_LOGGER.error(f"Error deleting command message: {e}")

    # Delete the reply message immediately if it exists
    if reply_message_id != 0:
        try:
            await TgClient.bot.delete_messages(
                query.message.chat.id, reply_message_id
            )
        except Exception as e:
            MUSIC_LOGGER.error(f"Error deleting reply message: {e}")
