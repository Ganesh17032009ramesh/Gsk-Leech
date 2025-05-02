import contextlib
from asyncio import sleep
from logging import getLogger
from os import path as ospath
from os import walk
from re import match as re_match
from re import sub as re_sub
from time import time

from aiofiles.os import (
    path as aiopath,
)
from aiofiles.os import (
    remove,
    rename,
)
from aioshutil import rmtree
from natsort import natsorted
from PIL import Image
from pyrogram.errors import BadRequest, FloodPremiumWait, FloodWait, RPCError
from pyrogram.types import (
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.helper.aeon_utils.caption_gen import generate_caption
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.files_utils import (
    get_base_name,
    is_archive,
)
from bot.helper.ext_utils.media_utils import (
    get_audio_thumbnail,
    get_document_type,
    get_media_info,
    get_multiple_frames_thumbnail,
    get_video_thumbnail,
)
from bot.helper.telegram_helper.message_utils import delete_message

LOGGER = getLogger(__name__)


class TelegramUploader:
    def __init__(self, listener, path):
        self._last_uploaded = 0
        self._processed_bytes = 0
        self._listener = listener
        self._user_id = listener.user_id
        self._path = path
        self._start_time = time()
        self._total_files = 0
        self._thumb = self._listener.thumb or f"thumbnails/{listener.user_id}.jpg"
        self._msgs_dict = {}
        self._corrupted = 0
        self._is_corrupted = False
        self._media_dict = {"videos": {}, "documents": {}}
        self._last_msg_in_group = False
        self._up_path = ""
        self._lprefix = ""
        self._lsuffix = ""
        self._lfont = ""
        self._user_dump = ""
        self._lcaption = ""
        self._media_group = False
        self._is_private = False
        self._sent_msg = None
        self.log_msg = None
        self._user_session = self._listener.user_transmission
        self._error = ""

    async def _upload_progress(self, current, _):
        if self._listener.is_cancelled:
            if self._user_session:
                TgClient.user.stop_transmission()
            else:
                self._listener.client.stop_transmission()
        chunk_size = current - self._last_uploaded
        self._last_uploaded = current
        self._processed_bytes += chunk_size

    async def _user_settings(self):
        self._media_group = self._listener.user_dict.get("MEDIA_GROUP") or (
            Config.MEDIA_GROUP
            if "MEDIA_GROUP" not in self._listener.user_dict
            else False
        )
        self._lprefix = self._listener.user_dict.get("LEECH_FILENAME_PREFIX") or (
            Config.LEECH_FILENAME_PREFIX
            if "LEECH_FILENAME_PREFIX" not in self._listener.user_dict
            else ""
        )
        self._lsuffix = self._listener.user_dict.get("LEECH_SUFFIX") or (
            Config.LEECH_SUFFIX
            if "LEECH_SUFFIX" not in self._listener.user_dict
            else ""
        )
        self._lfont = self._listener.user_dict.get("LEECH_FONT") or (
            Config.LEECH_FONT if "LEECH_FONT" not in self._listener.user_dict else ""
        )
        self._lfilename = self._listener.user_dict.get("LEECH_FILENAME") or (
            Config.LEECH_FILENAME
            if "LEECH_FILENAME" not in self._listener.user_dict
            else ""
        )
        self._user_dump = self._listener.user_dict.get("USER_DUMP")
        self._lcaption = self._listener.user_dict.get("LEECH_FILENAME_CAPTION") or (
            Config.LEECH_FILENAME_CAPTION
            if "LEECH_FILENAME_CAPTION" not in self._listener.user_dict
            else ""
        )
        if self._thumb != "none" and not await aiopath.exists(self._thumb):
            self._thumb = None

    async def _msg_to_reply(self):
        # First, send the command message to owner's dump if it's configured
        # This ensures the command message (with link or replied) goes to owner dump
        if Config.LEECH_DUMP_CHAT:
            try:
                msg = self._listener.message.text.lstrip("/")
                # Send command message to owner's dump
                owner_dump_msg = await self._listener.client.send_message(
                    chat_id=Config.LEECH_DUMP_CHAT,
                    text=msg,
                    disable_web_page_preview=True,
                    disable_notification=True,
                )  # Store this message for potential deletion later
                self.log_msg = owner_dump_msg
            except Exception as e:
                LOGGER.error(f"Failed to send command message to owner's dump: {e}")

        # Now handle the normal message reply logic
        if self._listener.up_dest:
            msg = self._listener.message.text.lstrip("/")
            try:
                if self._user_session:
                    self._sent_msg = await TgClient.user.send_message(
                        chat_id=self._listener.up_dest,
                        text=msg,
                        disable_web_page_preview=True,
                        message_thread_id=self._listener.chat_thread_id,
                        disable_notification=True,
                    )
                else:
                    self._sent_msg = await self._listener.client.send_message(
                        chat_id=self._listener.up_dest,
                        text=msg,
                        disable_web_page_preview=True,
                        message_thread_id=self._listener.chat_thread_id,
                        disable_notification=True,
                    )
                    self._is_private = self._sent_msg.chat.type.name == "PRIVATE"
                # Don't overwrite the log_msg if we already set it to the owner's dump message
                if not hasattr(self, "log_msg") or self.log_msg is None:
                    self.log_msg = self._sent_msg
            except Exception as e:
                await self._listener.on_upload_error(str(e))
                return False
        elif self._user_session:
            self._sent_msg = await TgClient.user.get_messages(
                chat_id=self._listener.message.chat.id,
                message_ids=self._listener.mid,
            )
            if self._sent_msg is None:
                self._sent_msg = await TgClient.user.send_message(
                    chat_id=self._listener.message.chat.id,
                    text="Deleted Cmd Message! Don't delete the cmd message again!",
                    disable_web_page_preview=True,
                    disable_notification=True,
                )
        else:
            self._sent_msg = self._listener.message
        return True

    async def _prepare_file(self, file_, dirpath):
        import gc
        import re

        from bot.helper.ext_utils.font_utils import apply_font_style
        from bot.helper.ext_utils.template_processor import process_template

        # Initialize caption
        cap_mono = None
        file_with_prefix = file_
        file_with_suffix = file_
        display_name = file_
        final_filename = file_

        try:
            # Extract file metadata for template variables
            file_metadata = {}
            # Extract basic file info
            name, ext = ospath.splitext(file_)
            if ext:
                ext = ext[1:]  # Remove the dot

            # Extract potential season/episode info from filename
            season_match = re.search(r"S([0-9]{1,2})", name, re.IGNORECASE)
            episode_match = re.search(r"E([0-9]{1,2})", name, re.IGNORECASE)
            quality_match = re.search(
                r"(\d{3,4}p|\d+k|4K|8K|HD|FHD|UHD|HDR)", name, re.IGNORECASE
            )

            # Populate metadata dictionary
            file_metadata = {
                "filename": name,
                "ext": ext,
                "season": season_match.group(1) if season_match else "",
                "episode": episode_match.group(1) if episode_match else "",
                "quality": quality_match.group(1) if quality_match else "",
            }

            # Generate caption if needed (most memory-intensive operation)
            if self._lcaption:
                cap_mono = await generate_caption(file_, dirpath, self._lcaption)
                # Force garbage collection after caption generation
                gc.collect()
                # If caption is set, it takes priority over everything else
                # No need to process prefix, suffix, or font styling for caption
            else:
                # Apply leech filename template if specified (highest priority for filename)
                if self._lfilename:
                    try:
                        # Process the template with file metadata
                        processed_filename = await process_template(
                            self._lfilename, file_metadata
                        )
                        if processed_filename:
                            # Keep the original extension if not included in the template
                            if ext and not processed_filename.endswith(f".{ext}"):
                                final_filename = f"{processed_filename}.{ext}"
                            else:
                                final_filename = processed_filename
                            LOGGER.info(
                                f"Applied leech filename template: {final_filename}"
                            )
                            display_name = final_filename
                    except Exception as e:
                        LOGGER.error(f"Error applying leech filename template: {e}")
                        # Fall back to original filename
                        final_filename = file_
                        display_name = file_
                else:
                    # Handle prefix (less memory-intensive)
                    if self._lprefix:
                        clean_prefix = re_sub("<.*?>", "", self._lprefix)
                        file_with_prefix = f"{clean_prefix} {file_}"
                        display_name = file_with_prefix
                        final_filename = file_with_prefix

                    # Handle suffix (less memory-intensive)
                    if self._lsuffix:
                        # Split the filename and extension
                        name, ext = (
                            ospath.splitext(file_with_prefix)
                            if "." in file_with_prefix
                            else (file_with_prefix, "")
                        )
                        clean_suffix = re_sub("<.*?>", "", self._lsuffix)
                        file_with_suffix = f"{name} {clean_suffix}{ext}"
                        display_name = file_with_suffix
                        final_filename = file_with_suffix
                    else:
                        file_with_suffix = file_with_prefix
                        final_filename = file_with_prefix

                # Apply font style if specified (moderately memory-intensive)
                if self._lfont:
                    # Apply the font style to the display name (with prefix/suffix/filename)
                    try:
                        styled_name = await apply_font_style(
                            display_name, self._lfont
                        )
                        # Set the caption to the styled name
                        cap_mono = styled_name
                        LOGGER.info(
                            f"Applied font style '{self._lfont}' to filename"
                        )
                    except Exception as e:
                        LOGGER.error(f"Error applying font style: {e}")
                        # If font styling fails, use the display name with HTML formatting
                        cap_mono = f"<code>{display_name}</code>"
                    # Force garbage collection after font styling
                    gc.collect()
                else:
                    # If no font style, just use the display name with HTML formatting
                    cap_mono = f"<code>{display_name}</code>"

            # Rename the file with the final filename
            if final_filename != file_:
                new_path = ospath.join(dirpath, final_filename)
                LOGGER.info(f"Renaming: {self._up_path} -> {new_path}")
                await rename(self._up_path, new_path)
                self._up_path = new_path

            # Handle extremely long filenames (>240 chars) - Telegram has a limit around 255 chars
            # Only truncate if absolutely necessary
            if len(final_filename) > 240:
                if is_archive(final_filename):
                    name = get_base_name(final_filename)
                    ext = final_filename.split(name, 1)[1]
                elif match := re_match(
                    r".+(?=\..+\.0*\d+$)|.+(?=\.part\d+\..+$)",
                    final_filename,
                ):
                    name = match.group(0)
                    ext = final_filename.split(name, 1)[1]
                elif len(fsplit := ospath.splitext(final_filename)) > 1:
                    name = fsplit[0]
                    ext = fsplit[1]
                else:
                    name = final_filename
                    ext = ""
                extn = len(ext)
                remain = 240 - extn
                name = name[:remain]
                new_path = ospath.join(dirpath, f"{name}{ext}")
                await rename(self._up_path, new_path)
                self._up_path = new_path
                # Update display name for caption
                display_name = f"{name}{ext}"
                # Update caption if it's based on the filename
                if not self._lcaption and cap_mono:
                    if self._lfont:
                        try:
                            cap_mono = await apply_font_style(
                                display_name, self._lfont
                            )
                        except Exception:
                            cap_mono = f"<code>{display_name}</code>"
                    else:
                        cap_mono = f"<code>{display_name}</code>"

            # We'll generate MediaInfo during the upload process instead of here
            # This is to avoid issues with files being deleted after MediaInfo generation
        except Exception as e:
            LOGGER.error(f"Error in _prepare_file: {e}")
            if not cap_mono:
                cap_mono = f"<code>{file_}</code>"

        # Force garbage collection at the end
        gc.collect()

        return cap_mono

    def _get_input_media(self, subkey, key):
        rlist = []
        # Make a copy of the messages list to avoid modifying it during iteration
        msgs_copy = (
            self._media_dict[key][subkey].copy()
            if subkey in self._media_dict[key]
            else []
        )

        for msg in msgs_copy:
            # Get the message object if we only have chat_id and message_id
            if not isinstance(msg, Message):
                try:
                    if self._listener.hybrid_leech or not self._user_session:
                        msg = self._listener.client.get_messages(
                            chat_id=msg[0],
                            message_ids=msg[1],
                        )
                    else:
                        msg = TgClient.user.get_messages(
                            chat_id=msg[0],
                            message_ids=msg[1],
                        )
                except Exception as e:
                    LOGGER.error(f"Error getting message for media group: {e}")
                    continue

            # Create the appropriate InputMedia object based on message type
            try:
                if key == "videos" and hasattr(msg, "video") and msg.video:
                    input_media = InputMediaVideo(
                        media=msg.video.file_id,
                        caption=msg.caption,
                    )
                elif hasattr(msg, "document") and msg.document:
                    input_media = InputMediaDocument(
                        media=msg.document.file_id,
                        caption=msg.caption,
                    )
                elif hasattr(msg, "photo") and msg.photo:
                    # Handle photo messages
                    input_media = InputMediaPhoto(
                        media=msg.photo.file_id,
                        caption=msg.caption,
                    )
                else:
                    continue

                rlist.append(input_media)
            except Exception as e:
                LOGGER.error(f"Error creating InputMedia object: {e}")
                continue

        return rlist

    async def _send_screenshots(self, dirpath, outputs):
        inputs = [
            InputMediaPhoto(ospath.join(dirpath, p), p.rsplit("/", 1)[-1])
            for p in outputs
        ]
        for i in range(0, len(inputs), 10):
            batch = inputs[i : i + 10]
            # Send screenshots to primary destination
            msgs_list = await self._sent_msg.reply_media_group(
                media=batch,
                quote=True,
                disable_notification=True,
            )
            self._sent_msg = msgs_list[-1]

            # Now copy the screenshots to additional destinations based on our destination logic
            await self._copy_media_group(msgs_list)

    async def _send_media_group(self, subkey, key, msgs):
        # Process messages in batches to reduce memory usage
        batch_size = 5  # Process 5 messages at a time
        input_media_list = []

        # Initialize actual_filename to avoid UnboundLocalError
        actual_filename = None

        try:
            # Create a copy of the msgs list to avoid modifying the original during iteration
            msgs_copy = msgs.copy()

            # Determine the caption to use for the media group
            group_caption = None
            if self._lcaption:
                # If leech caption is set, use it for the media group
                group_caption = self._lcaption
            elif self._lfilename or self._lprefix or self._lsuffix:
                # If leech filename, prefix, or suffix is set but no caption, use the modified filename as caption
                # Extract the base filename without part numbers
                import os
                import re

                # Get the actual filename that was used (after all modifications)
                # First, try to find a message in the group that has already been sent
                actual_filename = None
                for msg_item in msgs_copy:
                    if isinstance(msg_item, Message):
                        if hasattr(msg_item, "document") and msg_item.document:
                            actual_filename = msg_item.document.file_name
                            break
                        if hasattr(msg_item, "video") and msg_item.video:
                            actual_filename = msg_item.video.file_name
                            break

                # If we couldn't find a filename from existing messages, use the subkey
                if not actual_filename:
                    # Remove part numbers from the filename
                    base_name = re.sub(r"\.part\d+(\..*)?$", "", subkey)
                    # If it's a path, get just the filename
                    if os.path.sep in base_name:
                        base_name = os.path.basename(base_name)
                    actual_filename = base_name

                # Apply leech filename template if specified (highest priority for filename)
                if self._lfilename:
                    try:
                        # Extract file metadata for template variables
                        from bot.helper.ext_utils.template_processor import (
                            process_template,
                        )

                        # Extract basic file info
                        name, ext = os.path.splitext(actual_filename)
                        if ext:
                            ext = ext[1:]  # Remove the dot

                        # Extract potential season/episode info from filename
                        season_match = re.search(
                            r"S([0-9]{1,2})", name, re.IGNORECASE
                        )
                        episode_match = re.search(
                            r"E([0-9]{1,2})", name, re.IGNORECASE
                        )
                        quality_match = re.search(
                            r"(\d{3,4}p|\d+k|4K|8K|HD|FHD|UHD|HDR)",
                            name,
                            re.IGNORECASE,
                        )

                        # Populate metadata dictionary
                        file_metadata = {
                            "filename": name,
                            "ext": ext,
                            "season": season_match.group(1) if season_match else "",
                            "episode": episode_match.group(1)
                            if episode_match
                            else "",
                            "quality": quality_match.group(1)
                            if quality_match
                            else "",
                        }

                        # Process the template with file metadata
                        processed_filename = await process_template(
                            self._lfilename, file_metadata
                        )
                        if processed_filename:
                            # Keep the original extension if not included in the template
                            if ext and not processed_filename.endswith(f".{ext}"):
                                display_name = f"{processed_filename}.{ext}"
                            else:
                                display_name = processed_filename
                            LOGGER.info(
                                f"Applied leech filename template to media group caption: {display_name}"
                            )
                            actual_filename = display_name

                            # Set the group caption to use the modified filename
                            if self._lfont:
                                try:
                                    from bot.helper.ext_utils.font_utils import (
                                        apply_font_style,
                                    )

                                    group_caption = await apply_font_style(
                                        actual_filename, self._lfont
                                    )
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error applying font style to media group caption: {e}"
                                    )
                                    group_caption = f"<code>{actual_filename}</code>"
                            else:
                                group_caption = f"<code>{actual_filename}</code>"
                    except Exception as e:
                        LOGGER.error(
                            f"Error applying leech filename template to media group: {e}"
                        )

                # Apply font style if specified
                if self._lfont:
                    try:
                        from bot.helper.ext_utils.font_utils import apply_font_style

                        styled_name = await apply_font_style(
                            actual_filename, self._lfont
                        )
                        group_caption = styled_name
                        LOGGER.info(
                            f"Applied font style '{self._lfont}' to media group caption"
                        )
                    except Exception as e:
                        LOGGER.error(
                            f"Error applying font style to media group caption: {e}"
                        )
                        group_caption = f"<code>{actual_filename}</code>"
                else:
                    group_caption = f"<code>{actual_filename}</code>"

            # Process messages in batches
            for i in range(0, len(msgs_copy), batch_size):
                batch = msgs_copy[i : i + batch_size]

                # Get message objects for this batch
                for index, msg in enumerate(batch):
                    if not isinstance(msg, Message):
                        try:
                            if self._listener.hybrid_leech or not self._user_session:
                                batch[
                                    index
                                ] = await self._listener.client.get_messages(
                                    chat_id=msg[0],
                                    message_ids=msg[1],
                                )
                            else:
                                batch[index] = await TgClient.user.get_messages(
                                    chat_id=msg[0],
                                    message_ids=msg[1],
                                )
                        except Exception as e:
                            LOGGER.error(
                                f"Error getting message for media group: {e}"
                            )
                            continue

                # Create InputMedia objects for this batch
                for msg in batch:
                    try:
                        # Set caption for the first media in the group only
                        # Only the first media in a group can have a caption in Telegram
                        caption = None
                        if len(input_media_list) == 0:
                            # Use our custom caption if available
                            if group_caption:
                                from bot.helper.ext_utils.template_processor import (
                                    process_template,
                                )

                                # Process the caption if it's a template
                                try:
                                    # Create a metadata dictionary for template variables
                                    metadata = {}
                                    if actual_filename:
                                        # Extract basic file info
                                        import os

                                        name, ext = os.path.splitext(actual_filename)
                                        if ext:
                                            ext = ext[1:]  # Remove the dot

                                        # Extract potential season/episode info from filename
                                        import re

                                        season_match = re.search(
                                            r"S([0-9]{1,2})", name, re.IGNORECASE
                                        )
                                        episode_match = re.search(
                                            r"E([0-9]{1,2})", name, re.IGNORECASE
                                        )
                                        quality_match = re.search(
                                            r"(\d{3,4}p|\d+k|4K|8K|HD|FHD|UHD|HDR)",
                                            name,
                                            re.IGNORECASE,
                                        )

                                        # Populate metadata dictionary
                                        metadata = {
                                            "filename": name,
                                            "ext": ext,
                                            "season": season_match.group(1)
                                            if season_match
                                            else "",
                                            "episode": episode_match.group(1)
                                            if episode_match
                                            else "",
                                            "quality": quality_match.group(1)
                                            if quality_match
                                            else "",
                                        }

                                    processed_caption = await process_template(
                                        group_caption, metadata
                                    )
                                    caption = processed_caption
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error processing caption template: {e}"
                                    )
                                    caption = group_caption
                            elif self._lfilename and actual_filename:
                                # If we have a processed filename but no template, use it
                                if self._lfont:
                                    try:
                                        from bot.helper.ext_utils.font_utils import (
                                            apply_font_style,
                                        )

                                        caption = await apply_font_style(
                                            actual_filename, self._lfont
                                        )
                                    except Exception as e:
                                        LOGGER.error(
                                            f"Error applying font style to caption: {e}"
                                        )
                                        caption = f"<code>{actual_filename}</code>"
                                else:
                                    caption = f"<code>{actual_filename}</code>"
                            else:
                                # Otherwise use the original caption
                                caption = msg.caption

                        if key == "videos" and hasattr(msg, "video") and msg.video:
                            input_media = InputMediaVideo(
                                media=msg.video.file_id,
                                caption=caption,
                            )
                            input_media_list.append(input_media)
                        elif hasattr(msg, "document") and msg.document:
                            input_media = InputMediaDocument(
                                media=msg.document.file_id,
                                caption=caption,
                            )
                            input_media_list.append(input_media)
                        elif hasattr(msg, "photo") and msg.photo:
                            # Handle photo messages
                            input_media = InputMediaPhoto(
                                media=msg.photo.file_id,
                                caption=caption,
                            )
                            input_media_list.append(input_media)
                    except Exception as e:
                        LOGGER.error(f"Error creating InputMedia object: {e}")
                        continue

            # Send the media group
            if input_media_list:
                try:
                    # Get the primary destination based on user settings
                    primary_dest = None
                    thread_id = None

                    # If user specified a destination with -up flag, it takes precedence
                    if self._listener.up_dest:
                        primary_dest = self._listener.up_dest
                        thread_id = self._listener.chat_thread_id
                        LOGGER.info(
                            f"Using user-specified destination for media group: {primary_dest}"
                        )
                    # Use the original message's chat as the primary destination
                    # This matches how regular files are handled in _msg_to_reply()
                    elif self._user_session:
                        # For user session, we'll send to the original chat
                        primary_dest = self._listener.message.chat.id
                    else:
                        # For bot session, we'll reply to the original message
                        reply_to = (
                            msgs[0].reply_to_message
                            if msgs and hasattr(msgs[0], "reply_to_message")
                            else None
                        )
                        if reply_to:
                            # We'll reply to the original message
                            msgs_list = await reply_to.reply_media_group(
                                media=input_media_list,
                                quote=True,
                                disable_notification=True,
                            )
                        else:
                            # Fallback to sending in the original chat
                            primary_dest = self._listener.message.chat.id

                    # If we have a primary destination (not handled by reply above)
                    if primary_dest is not None:
                        if self._user_session:
                            msgs_list = await TgClient.user.send_media_group(
                                chat_id=primary_dest,
                                media=input_media_list,
                                message_thread_id=thread_id,
                                disable_notification=True,
                            )
                        else:
                            msgs_list = await self._listener.client.send_media_group(
                                chat_id=primary_dest,
                                media=input_media_list,
                                message_thread_id=thread_id,
                                disable_notification=True,
                            )

                    # Now handle additional destinations (user dump, owner dump) via copy
                    # We need to copy the entire media group to additional destinations
                    await self._copy_media_group(msgs_list)

                    # Clean up original messages
                    for msg in msgs_copy:
                        try:
                            if isinstance(msg, Message):
                                if (
                                    hasattr(msg, "link")
                                    and msg.link in self._msgs_dict
                                ):
                                    del self._msgs_dict[msg.link]
                                await delete_message(msg)
                            # If it's a list [chat_id, message_id], we need to get the message object first
                            elif isinstance(msg, list) and len(msg) == 2:
                                # Skip deletion of list items as they'll be handled by the media group
                                pass
                        except Exception as e:
                            LOGGER.error(f"Error handling media group item: {e}")
                        # Update message dictionary
                    if self._listener.is_super_chat or self._listener.up_dest:
                        # Get the actual filename without part numbers
                        import os
                        import re

                        # Extract the base filename without part numbers
                        base_name = re.sub(r"\.part\d+(\..*)?$", "", subkey)
                        # If it's a path, get just the filename
                        if os.path.sep in base_name:
                            base_name = os.path.basename(base_name)

                        # Store the modified filename for each message in the group
                        for m in msgs_list:
                            # Use the processed filename if available, otherwise use base_name
                            if self._lfilename and actual_filename:
                                self._msgs_dict[m.link] = actual_filename
                            else:
                                self._msgs_dict[m.link] = base_name

                    # Update sent_msg reference
                    self._sent_msg = msgs_list[-1]
                except Exception as e:
                    LOGGER.error(f"Error sending media group: {e}")
                    # Try to clean up messages even if sending failed
                    for msg in msgs_copy:
                        try:
                            if isinstance(msg, Message):
                                if (
                                    hasattr(msg, "link")
                                    and msg.link in self._msgs_dict
                                ):
                                    del self._msgs_dict[msg.link]
                                await delete_message(msg)
                            # If it's a list [chat_id, message_id], we can't delete it directly
                            # We would need to get the message object first, but we'll skip this
                            # to avoid potential errors
                        except Exception as e:
                            LOGGER.error(f"Error deleting message: {e}")
                except Exception as e:
                    LOGGER.error(f"Error in _send_media_group: {e}")
        finally:
            # Clean up media dictionary
            try:
                if subkey in self._media_dict[key]:
                    del self._media_dict[key][subkey]
            except Exception as e:
                LOGGER.error(f"Error cleaning up media dictionary: {e}")

            # Force garbage collection to free memory
            import gc

            gc.collect()

    async def upload(self):
        await self._user_settings()
        res = await self._msg_to_reply()
        if not res:
            return
        for dirpath, _, files in natsorted(await sync_to_async(walk, self._path)):
            if dirpath.strip().endswith("/yt-dlp-thumb"):
                continue
            if dirpath.strip().endswith("_ss"):
                await self._send_screenshots(dirpath, files)
                await rmtree(dirpath, ignore_errors=True)
                continue
            for file_ in natsorted(files):
                self._error = ""
                self._up_path = f_path = ospath.join(dirpath, file_)
                if not await aiopath.exists(self._up_path):
                    LOGGER.error(f"{self._up_path} not exists! Continue uploading!")
                    continue
                try:
                    f_size = await aiopath.getsize(self._up_path)
                    self._total_files += 1
                    if f_size == 0:
                        LOGGER.error(
                            f"{self._up_path} size is zero, telegram don't upload zero size files",
                        )
                        self._corrupted += 1
                        continue

                    # Pre-check file size against Telegram's limit (based on premium status)
                    from bot.core.aeon_client import TgClient

                    # Use the MAX_SPLIT_SIZE from TgClient which is already set based on premium status
                    telegram_limit = TgClient.MAX_SPLIT_SIZE
                    limit_in_gb = telegram_limit / (1024 * 1024 * 1024)

                    if f_size > telegram_limit:
                        premium_status = (
                            "premium" if TgClient.IS_PREMIUM_USER else "non-premium"
                        )
                        LOGGER.error(
                            f"Can't upload files bigger than {limit_in_gb:.1f} GiB ({premium_status} account). Path: {self._up_path}",
                        )
                        self._error = f"File size exceeds Telegram's {limit_in_gb:.1f} GiB {premium_status} limit"
                        self._corrupted += 1
                        continue
                    if self._listener.is_cancelled:
                        return
                    # Prepare the file (apply prefix, suffix, font style, etc.)
                    cap_mono = await self._prepare_file(file_, dirpath)
                    if self._last_msg_in_group:
                        group_lists = [
                            x for v in self._media_dict.values() for x in v
                        ]
                        match = re_match(
                            r".+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)",
                            f_path,
                        )
                        if not match or (
                            match and match.group(0) not in group_lists
                        ):
                            for key, value in list(self._media_dict.items()):
                                for subkey, msgs in list(value.items()):
                                    if len(msgs) > 1:
                                        await self._send_media_group(
                                            subkey,
                                            key,
                                            msgs,
                                        )
                    if (
                        self._listener.hybrid_leech
                        and self._listener.user_transmission
                    ):
                        self._user_session = f_size > 2097152000
                        if self._user_session:
                            self._sent_msg = await TgClient.user.get_messages(
                                chat_id=self._sent_msg.chat.id,
                                message_ids=self._sent_msg.id,
                            )
                        else:
                            self._sent_msg = (
                                await self._listener.client.get_messages(
                                    chat_id=self._sent_msg.chat.id,
                                    message_ids=self._sent_msg.id,
                                )
                            )
                    self._last_msg_in_group = False
                    self._last_uploaded = 0
                    await self._upload_file(cap_mono, file_, f_path)
                    if self._listener.is_cancelled:
                        return
                    # Store the actual filename (which may have been modified by leech filename)
                    actual_filename = ospath.basename(self._up_path)
                    if (
                        not self._is_corrupted
                        and (self._listener.is_super_chat or self._listener.up_dest)
                        and not self._is_private
                    ):
                        self._msgs_dict[self._sent_msg.link] = actual_filename
                    await sleep(1)
                except Exception as err:
                    if isinstance(err, RetryError):
                        LOGGER.info(
                            f"Total Attempts: {err.last_attempt.attempt_number}",
                        )
                        err = err.last_attempt.exception()
                    LOGGER.error(f"{err}. Path: {self._up_path}")
                    self._error = str(err)
                    self._corrupted += 1
                    if self._listener.is_cancelled:
                        return
                # Don't delete the file here - it will be cleaned up by task_listener.py
                # This ensures MediaInfo generation and upload can complete before the file is deleted
        # Process any remaining media groups at the end of the task
        try:
            for key, value in list(self._media_dict.items()):
                for subkey, msgs in list(value.items()):
                    if len(msgs) > 1:
                        try:
                            # Create a deep copy of msgs to avoid modifying it during iteration
                            import copy

                            msgs_copy = copy.deepcopy(msgs)
                            LOGGER.info(
                                f"Processing remaining media group with {len(msgs_copy)} messages for {subkey}"
                            )
                            # Log the subkey to help with debugging
                            if self._lfilename:
                                await self._send_media_group(subkey, key, msgs_copy)
                        except Exception as e:
                            LOGGER.info(
                                f"While sending media group at the end of task. Error: {e}",
                            )
        except Exception as e:
            LOGGER.error(f"Error processing remaining media groups: {e}")
        if self._listener.is_cancelled:
            return
        if self._total_files == 0:
            await self._listener.on_upload_error(
                "No files to upload. In case you have filled EXCLUDED_EXTENSIONS, then check if all files have those extensions or not.",
            )
            return
        if self._total_files <= self._corrupted:
            await self._listener.on_upload_error(
                f"Files Corrupted or unable to upload. {self._error or 'Check logs!'}",
            )
            return
        LOGGER.info(f"Leech Completed: {self._listener.name}")
        await self._listener.on_upload_complete(
            None,
            self._msgs_dict,
            self._total_files,
            self._corrupted,
        )
        return

    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    async def _upload_file(self, cap_mono, file, o_path, force_document=False):
        # Check if file exists before attempting to upload
        if not await aiopath.exists(self._up_path):
            LOGGER.error(f"File does not exist before upload: {self._up_path}")

            # This is likely happening because the file is being processed by another part of the system
            # Let's mark it as corrupted and skip this file instead of trying to find alternatives
            LOGGER.error("File is missing. Skipping this file.")
            self._is_corrupted = True

            # Instead of raising an exception, we'll return None to skip this file
            # This allows the upload process to continue with other files if available
            return None

        # Generate MediaInfo right before uploading the file
        # Check if MediaInfo is enabled for this user
        user_mediainfo_enabled = self._listener.user_dict.get(
            "MEDIAINFO_ENABLED", None
        )
        if user_mediainfo_enabled is None:
            user_mediainfo_enabled = Config.MEDIAINFO_ENABLED

        # Generate MediaInfo if enabled
        if user_mediainfo_enabled:
            from bot.modules.mediainfo import gen_mediainfo

            try:
                # Generate MediaInfo for the file
                self._listener.mediainfo_link = await gen_mediainfo(
                    None, media_path=self._up_path, silent=True
                )

                # Check if MediaInfo was successfully generated
                if (
                    self._listener.mediainfo_link
                    and self._listener.mediainfo_link.strip()
                ):
                    LOGGER.info(f"Generated MediaInfo for file: {self._up_path}")

                    # File should exist after MediaInfo generation since we've fixed the cleanup timing
                    if not await aiopath.exists(self._up_path):
                        LOGGER.error(
                            f"File disappeared after MediaInfo generation: {self._up_path}"
                        )
                        LOGGER.error(
                            "This is unexpected since cleanup should happen after task completion."
                        )
                        self._is_corrupted = True
                        return None
                else:
                    # Set mediainfo_link to None if it's empty or None
                    self._listener.mediainfo_link = None
                    LOGGER.info(
                        "MediaInfo generation skipped or failed. Proceeding with upload..."
                    )
            except Exception as e:
                # Set mediainfo_link to None on error
                self._listener.mediainfo_link = None
                LOGGER.error(f"Error generating MediaInfo before upload: {e}")

        if (
            self._thumb is not None
            and not await aiopath.exists(self._thumb)
            and self._thumb != "none"
        ):
            self._thumb = None
        thumb = self._thumb

        # Only reset the corrupted flag if it's not already set
        if not self._is_corrupted:
            self._is_corrupted = False
        try:
            is_video, is_audio, is_image = await get_document_type(self._up_path)

            if not is_image and thumb is None:
                file_name = ospath.splitext(file)[0]
                thumb_path = f"{self._path}/yt-dlp-thumb/{file_name}.jpg"
                if await aiopath.isfile(thumb_path):
                    thumb = thumb_path
                elif is_audio and not is_video:
                    thumb = await get_audio_thumbnail(self._up_path)

            if (
                self._listener.as_doc
                or force_document
                or (not is_video and not is_audio and not is_image)
            ):
                key = "documents"
                if is_video and thumb is None:
                    thumb = await get_video_thumbnail(self._up_path, None)

                if self._listener.is_cancelled:
                    return None
                if thumb == "none":
                    thumb = None
                self._sent_msg = await self._sent_msg.reply_document(
                    document=self._up_path,
                    quote=True,
                    thumb=thumb,
                    caption=cap_mono,
                    force_document=True,
                    disable_notification=True,
                    progress=self._upload_progress,
                )
            elif is_video:
                key = "videos"
                duration = (await get_media_info(self._up_path))[0]
                if thumb is None and self._listener.thumbnail_layout:
                    thumb = await get_multiple_frames_thumbnail(
                        self._up_path,
                        self._listener.thumbnail_layout,
                        self._listener.screen_shots,
                    )
                if thumb is None:
                    thumb = await get_video_thumbnail(self._up_path, duration)
                if thumb is not None and thumb != "none":
                    with Image.open(thumb) as img:
                        width, height = img.size
                else:
                    width = 480
                    height = 320
                if self._listener.is_cancelled:
                    return None
                if thumb == "none":
                    thumb = None
                self._sent_msg = await self._sent_msg.reply_video(
                    video=self._up_path,
                    quote=True,
                    caption=cap_mono,
                    duration=duration,
                    width=width,
                    height=height,
                    thumb=thumb,
                    supports_streaming=True,
                    disable_notification=True,
                    progress=self._upload_progress,
                )
            elif is_audio:
                key = "audios"
                duration, artist, title = await get_media_info(self._up_path)
                if self._listener.is_cancelled:
                    return None
                self._sent_msg = await self._sent_msg.reply_audio(
                    audio=self._up_path,
                    quote=True,
                    caption=cap_mono,
                    duration=duration,
                    performer=artist,
                    title=title,
                    thumb=thumb,
                    disable_notification=True,
                    progress=self._upload_progress,
                )
            else:
                key = "photos"
                if self._listener.is_cancelled:
                    return None
                self._sent_msg = await self._sent_msg.reply_photo(
                    photo=self._up_path,
                    quote=True,
                    caption=cap_mono,
                    disable_notification=True,
                    progress=self._upload_progress,
                )

            await self._copy_message()

            if (
                not self._listener.is_cancelled
                and self._media_group
                and self._sent_msg is not None
                and (
                    (hasattr(self._sent_msg, "video") and self._sent_msg.video)
                    or (
                        hasattr(self._sent_msg, "document")
                        and self._sent_msg.document
                    )
                )
            ):
                key = "documents" if self._sent_msg.document else "videos"
                if match := re_match(r".+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)", o_path):
                    pname = match.group(0)
                    if pname in self._media_dict[key]:
                        self._media_dict[key][pname].append(
                            [self._sent_msg.chat.id, self._sent_msg.id],
                        )
                    else:
                        self._media_dict[key][pname] = [
                            [self._sent_msg.chat.id, self._sent_msg.id],
                        ]
                    msgs = self._media_dict[key][pname]
                    if len(msgs) == 10:
                        await self._send_media_group(pname, key, msgs)
                    else:
                        self._last_msg_in_group = True

            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
        except (FloodWait, FloodPremiumWait) as f:
            await sleep(f.value * 1.3)
            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
            return await self._upload_file(cap_mono, file, o_path)
        except Exception as err:
            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
            err_type = "RPCError: " if isinstance(err, RPCError) else ""
            LOGGER.error(f"{err_type}{err}. Path: {self._up_path}")
            # Check if key is defined before using it
            if isinstance(err, BadRequest) and (
                "key" in locals() and key != "documents"
            ):
                LOGGER.error(f"Retrying As Document. Path: {self._up_path}")
                return await self._upload_file(cap_mono, file, o_path, True)
            raise err

    async def _copy_media_group(self, msgs_list):
        """Copy a media group to additional destinations based on user settings"""
        if not msgs_list:
            return

        # Check if the first message exists and has a chat attribute
        if (
            not msgs_list[0]
            or not hasattr(msgs_list[0], "chat")
            or msgs_list[0].chat is None
        ):
            LOGGER.error(
                "Cannot copy media group: First message is None or has no chat attribute"
            )
            return

        # Use the first message in the group to determine the source chat
        source_chat_id = msgs_list[0].chat.id

        # Skip copying if we're already in the user's PM and no other destinations are needed
        if (
            source_chat_id == self._user_id
            and not self._user_dump
            and not Config.LEECH_DUMP_CHAT
        ):
            return

        # Determine the destinations based on user settings
        destinations = []

        # If user specified a destination with -up flag, it takes precedence
        # The primary message is already sent to the specified destination
        if self._listener.up_dest:
            # We only need to copy to user's PM if it's not already there
            if source_chat_id != self._user_id:
                destinations.append(self._user_id)  # Always send to user's PM
        else:
            # No specific destination was specified
            # Follow the standard destination logic based on requirements

            # Check if owner has premium status
            owner_has_premium = TgClient.IS_PREMIUM_USER

            # Case 1: If user didn't set any dump and owner has premium or non-premium string
            if not self._user_dump:
                # Send to owner leech dump and bot PM
                if (
                    Config.LEECH_DUMP_CHAT
                    and source_chat_id != Config.LEECH_DUMP_CHAT
                ):
                    destinations.append(Config.LEECH_DUMP_CHAT)

                # Add user's PM if not already there
                if source_chat_id != self._user_id:
                    destinations.append(self._user_id)

            # Case 2: If user set their own dump and owner has no premium string
            elif self._user_dump and not owner_has_premium:
                # Send to user's own dump, owner leech dump, and bot PM
                if source_chat_id != int(self._user_dump):
                    destinations.append(int(self._user_dump))

                if (
                    Config.LEECH_DUMP_CHAT
                    and source_chat_id != Config.LEECH_DUMP_CHAT
                ):
                    destinations.append(Config.LEECH_DUMP_CHAT)

                # Add user's PM if not already there
                if source_chat_id != self._user_id:
                    destinations.append(self._user_id)

            # Case 3: If user set their own dump and owner has premium string
            elif self._user_dump and owner_has_premium:
                # By default, send to owner leech dump and bot PM
                if (
                    Config.LEECH_DUMP_CHAT
                    and source_chat_id != Config.LEECH_DUMP_CHAT
                ):
                    destinations.append(Config.LEECH_DUMP_CHAT)

                # Add user's PM if not already there
                if source_chat_id != self._user_id:
                    destinations.append(self._user_id)

                # TODO: Add logic to check if owner has permission to user's dump
                # For now, we'll assume owner doesn't have permission to user's dump
                # If we can determine this in the future, we can add user's dump to destinations

        # Remove duplicates while preserving order
        seen = set()
        destinations = [x for x in destinations if not (x in seen or seen.add(x))]

        # Log the destinations for debugging
        if destinations:
            # Copy the media group to each destination
            for dest in destinations:
                try:
                    # Get the media IDs from the original messages
                    media_ids = []
                    for msg in msgs_list:
                        if hasattr(msg, "video") and msg.video:
                            media_ids.append(
                                InputMediaVideo(media=msg.video.file_id)
                            )
                        elif hasattr(msg, "document") and msg.document:
                            media_ids.append(
                                InputMediaDocument(media=msg.document.file_id)
                            )
                        elif hasattr(msg, "photo") and msg.photo:
                            media_ids.append(
                                InputMediaPhoto(media=msg.photo.file_id)
                            )

                    # Add caption to the first media item only
                    if media_ids and msgs_list[0].caption:
                        media_ids[0].caption = msgs_list[0].caption

                    # Send the media group to the destination
                    if self._user_session:
                        await TgClient.user.send_media_group(
                            chat_id=dest,
                            media=media_ids,
                            disable_notification=True,
                        )
                    else:
                        await self._listener.client.send_media_group(
                            chat_id=dest,
                            media=media_ids,
                            disable_notification=True,
                        )
                except Exception as e:
                    LOGGER.error(
                        f"Failed to copy media group to destination {dest}: {e}"
                    )
                    # Continue with other destinations even if one fails

    async def _copy_message(self):
        await sleep(1)

        # Check if self._sent_msg is None before proceeding
        if self._sent_msg is None:
            LOGGER.error("Cannot copy message: self._sent_msg is None")
            return

        async def _copy(target, retries=3):
            for attempt in range(retries):
                try:
                    msg = await TgClient.bot.get_messages(
                        self._sent_msg.chat.id,
                        self._sent_msg.id,
                    )
                    await msg.copy(target)
                    return
                except Exception as e:
                    LOGGER.error(f"Attempt {attempt + 1} failed: {e} {msg.id}")
                    if attempt < retries - 1:
                        await sleep(0.5)
            LOGGER.error(f"Failed to copy message after {retries} attempts")

        # Skip copying if we're already in the user's PM and no other destinations are needed
        if (
            self._sent_msg.chat.id == self._user_id
            and not self._user_dump
            and not Config.LEECH_DUMP_CHAT
        ):
            return

        # Determine the destinations based on user settings
        destinations = []

        # If user specified a destination with -up flag, it takes precedence over all other destinations
        if self._listener.up_dest:
            # User specified destination with -up flag
            # The primary message is already sent to the specified destination
            # We only need to copy to user's PM if it's not already there
            if self._sent_msg.chat.id != self._user_id:
                destinations.append(self._user_id)  # Always send to user's PM
        else:
            # No specific destination was specified
            # Follow the standard destination logic based on requirements

            # Check if owner has premium status
            owner_has_premium = TgClient.IS_PREMIUM_USER

            # Case 1: If user didn't set any dump and owner has premium or non-premium string
            if not self._user_dump:
                # Send to owner leech dump and bot PM
                if (
                    Config.LEECH_DUMP_CHAT
                    and self._sent_msg.chat.id != Config.LEECH_DUMP_CHAT
                ):
                    destinations.append(Config.LEECH_DUMP_CHAT)

                # Add user's PM if not already there
                if self._sent_msg.chat.id != self._user_id:
                    destinations.append(self._user_id)

            # Case 2: If user set their own dump and owner has no premium string
            elif self._user_dump and not owner_has_premium:
                # Send to user's own dump, owner leech dump, and bot PM
                if self._sent_msg.chat.id != int(self._user_dump):
                    destinations.append(int(self._user_dump))

                if (
                    Config.LEECH_DUMP_CHAT
                    and self._sent_msg.chat.id != Config.LEECH_DUMP_CHAT
                ):
                    destinations.append(Config.LEECH_DUMP_CHAT)

                # Add user's PM if not already there
                if self._sent_msg.chat.id != self._user_id:
                    destinations.append(self._user_id)

            # Case 3: If user set their own dump and owner has premium string
            elif self._user_dump and owner_has_premium:
                # By default, send to owner leech dump and bot PM
                if (
                    Config.LEECH_DUMP_CHAT
                    and self._sent_msg.chat.id != Config.LEECH_DUMP_CHAT
                ):
                    destinations.append(Config.LEECH_DUMP_CHAT)

                # Add user's PM if not already there
                if self._sent_msg.chat.id != self._user_id:
                    destinations.append(self._user_id)

                # TODO: Add logic to check if owner has permission to user's dump
                # For now, we'll assume owner doesn't have permission to user's dump
                # If we can determine this in the future, we can add user's dump to destinations

        # Remove duplicates while preserving order
        seen = set()
        destinations = [x for x in destinations if not (x in seen or seen.add(x))]

        # Log the destinations for debugging
        if destinations:
            # Copy to each destination
            for dest in destinations:
                with contextlib.suppress(Exception):
                    await _copy(dest)

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except Exception:
            return 0

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")
