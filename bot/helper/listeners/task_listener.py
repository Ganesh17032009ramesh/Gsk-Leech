# ruff: noqa: RUF006
from asyncio import create_task, gather, sleep
from html import escape

from aiofiles.os import listdir, makedirs, remove
from aiofiles.os import path as aiopath
from aioshutil import move
from requests import utils as rutils

from bot import (
    DOWNLOAD_DIR,
    LOGGER,
    intervals,
    non_queued_dl,
    non_queued_up,
    queue_dict_lock,
    queued_dl,
    queued_up,
    same_directory_lock,
    task_dict,
    task_dict_lock,
)
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.core.torrent_manager import TorrentManager
from bot.helper.common import TaskConfig
from bot.helper.ext_utils.bot_utils import encode_slink, sync_to_async
from bot.helper.ext_utils.db_handler import database
from bot.helper.ext_utils.files_utils import (
    clean_download,
    clean_target,
    create_recursive_symlink,
    get_path_size,
    join_files,
    remove_excluded_files,
)
from bot.helper.ext_utils.links_utils import is_gdrive_id, is_rclone_path
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.ext_utils.task_manager import check_running_tasks, start_from_queued
from bot.helper.mirror_leech_utils.gdrive_utils.upload import GoogleDriveUpload
from bot.helper.mirror_leech_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.mirror_leech_utils.status_utils.gdrive_status import (
    GoogleDriveStatus,
)
from bot.helper.mirror_leech_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_leech_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_leech_utils.status_utils.telegram_status import TelegramStatus
from bot.helper.mirror_leech_utils.telegram_uploader import TelegramUploader
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_links,
    delete_message,
    delete_status,
    send_message,
    update_status_message,
)


class TaskListener(TaskConfig):
    def __init__(self):
        super().__init__()

    async def clean(self):
        try:
            if st := intervals["status"]:
                for intvl in list(st.values()):
                    intvl.cancel()
            intervals["status"].clear()
            await gather(TorrentManager.aria2.purgeDownloadResult(), delete_status())
        except Exception as e:
            LOGGER.error(e)

    def clear(self):
        self.subname = ""
        self.subsize = 0
        self.files_to_proceed = []
        self.proceed_count = 0
        self.progress = True

    async def remove_from_same_dir(self):
        async with task_dict_lock:
            if (
                self.folder_name
                and self.same_dir
                and self.mid in self.same_dir[self.folder_name]["tasks"]
            ):
                self.same_dir[self.folder_name]["tasks"].remove(self.mid)
                self.same_dir[self.folder_name]["total"] -= 1

    async def on_download_start(self):
        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.add_incomplete_task(
                self.message.chat.id,
                self.message.link,
                self.tag,
            )

    async def on_download_complete(self):
        await sleep(2)
        if self.is_cancelled:
            return
        multi_links = False
        if (
            self.folder_name
            and self.same_dir
            and self.mid in self.same_dir[self.folder_name]["tasks"]
        ):
            async with same_directory_lock:
                while True:
                    async with task_dict_lock:
                        if self.mid not in self.same_dir[self.folder_name]["tasks"]:
                            return
                        if self.mid in self.same_dir[self.folder_name]["tasks"] and (
                            self.same_dir[self.folder_name]["total"] <= 1
                            or len(self.same_dir[self.folder_name]["tasks"]) > 1
                        ):
                            if self.same_dir[self.folder_name]["total"] > 1:
                                self.same_dir[self.folder_name]["tasks"].remove(
                                    self.mid,
                                )
                                self.same_dir[self.folder_name]["total"] -= 1
                                spath = f"{self.dir}{self.folder_name}"
                                des_id = next(
                                    iter(self.same_dir[self.folder_name]["tasks"]),
                                )
                                des_path = (
                                    f"{DOWNLOAD_DIR}{des_id}{self.folder_name}"
                                )
                                await makedirs(des_path, exist_ok=True)
                                LOGGER.info(
                                    f"Moving files from {self.mid} to {des_id}",
                                )
                                for item in await listdir(spath):
                                    if item.strip().endswith((".aria2", ".!qB")):
                                        continue
                                    item_path = (
                                        f"{self.dir}{self.folder_name}/{item}"
                                    )
                                    if item in await listdir(des_path):
                                        await move(
                                            item_path,
                                            f"{des_path}/{self.mid}-{item}",
                                        )
                                    else:
                                        await move(item_path, f"{des_path}/{item}")
                                multi_links = True
                            break
                    await sleep(1)
        async with task_dict_lock:
            if self.is_cancelled:
                return
            if self.mid in task_dict:
                download = task_dict[self.mid]
                self.name = download.name()
                gid = download.gid()
            else:
                return
        LOGGER.info(f"Download completed: {self.name}")

        if not (self.is_torrent or self.is_qbit):
            self.seed = False

        if multi_links:
            self.seed = False
            await self.on_upload_error(
                f"{self.name} Downloaded!\n\nWaiting for other tasks to finish...",
            )
            return

        if self.folder_name:
            self.name = self.folder_name.strip("/").split("/", 1)[0]

        if not await aiopath.exists(f"{self.dir}/{self.name}"):
            try:
                files = await listdir(self.dir)
                self.name = files[-1]
                if self.name == "yt-dlp-thumb":
                    self.name = files[0]
            except Exception as e:
                await self.on_upload_error(str(e))
                return

        dl_path = f"{self.dir}/{self.name}"
        self.size = await get_path_size(dl_path)
        self.is_file = await aiopath.isfile(dl_path)
        if self.seed:
            up_dir = self.up_dir = f"{self.dir}10000"
            up_path = f"{self.up_dir}/{self.name}"
            await create_recursive_symlink(self.dir, self.up_dir)
            LOGGER.info(f"Shortcut created: {dl_path} -> {up_path}")
        else:
            up_dir = self.dir
            up_path = dl_path
        await remove_excluded_files(
            self.up_dir or self.dir,
            self.excluded_extensions,
        )
        if not Config.QUEUE_ALL:
            async with queue_dict_lock:
                if self.mid in non_queued_dl:
                    non_queued_dl.remove(self.mid)
            await start_from_queued()

        if self.join and not self.is_file:
            await join_files(up_path)

        if self.extract and not self.is_nzb:
            up_path = await self.proceed_extract(up_path, gid)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()
            await remove_excluded_files(up_dir, self.excluded_extensions)

        # Determine which media tool to run first based on priority
        media_tools = []

        if self.merge_enabled:
            media_tools.append((self.merge_priority, "merge", self.proceed_merge))

        # Check if watermark is enabled or watermark text is available
        if self.watermark_enabled or self.watermark:
            media_tools.append(
                (self.watermark_priority, "watermark", self.proceed_watermark)
            )

        # Check if trim is enabled or trim parameters are provided
        if self.trim_enabled or self.trim:
            media_tools.append((self.trim_priority, "trim", self.proceed_trim))

        # Check if compression is enabled
        if self.compression_enabled:
            media_tools.append(
                (self.compression_priority, "compression", self.proceed_compress)
            )

        # Check if extract is enabled
        if self.extract_enabled:
            media_tools.append(
                (self.extract_priority, "extract", self.proceed_extract_tracks)
            )

        # Sort media tools by priority (lower number = higher priority)
        media_tools.sort(key=lambda x: x[0])

        # Run media tools in priority order
        for _, tool_name, tool_func in media_tools:
            LOGGER.info(f"Running {tool_name} with priority {_}")
            up_path = await tool_func(up_path, gid)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        # Check if any metadata settings are provided (legacy or new)
        if (
            self.metadata
            or self.metadata_title
            or self.metadata_author
            or self.metadata_comment
            or self.metadata_all
            or self.metadata_video_title
            or self.metadata_video_author
            or self.metadata_video_comment
            or self.metadata_audio_title
            or self.metadata_audio_author
            or self.metadata_audio_comment
            or self.metadata_subtitle_title
            or self.metadata_subtitle_author
            or self.metadata_subtitle_comment
        ):
            up_path = await self.proceed_metadata(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        if self.ffmpeg_cmds:
            up_path = await self.proceed_ffmpeg(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        if self.name_sub:
            up_path = await self.substitute(up_path)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]

        up_path = await self.remove_www_prefix(up_path)
        self.is_file = await aiopath.isfile(up_path)
        self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]

        if self.screen_shots:
            up_path = await self.generate_screenshots(up_path)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)

        if self.convert_audio or self.convert_video:
            up_path = await self.convert_media(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        if self.sample_video:
            up_path = await self.generate_sample_video(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        # Compression is already handled in the media tools priority system above

        self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
        self.size = await get_path_size(up_dir)

        if self.is_leech:
            await self.proceed_split(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.clear()

        self.subproc = None

        # Store MediaInfo link for later use in task completion message
        self.mediainfo_link = None

        add_to_queue, event = await check_running_tasks(self, "up")
        await start_from_queued()
        if add_to_queue:
            LOGGER.info(f"Added to Queue/Upload: {self.name}")
            async with task_dict_lock:
                task_dict[self.mid] = QueueStatus(self, gid, "Up")
            await event.wait()
            if self.is_cancelled:
                return
            LOGGER.info(f"Start from Queued/Upload: {self.name}")

        self.size = await get_path_size(up_dir)

        # For mirror tasks, send the command message to owner's log chat ID if configured
        self.log_msg = None
        if not self.is_leech and Config.LOG_CHAT_ID:
            try:
                msg = self.message.text.lstrip("/")
                # Send command message to owner's log chat ID
                self.log_msg = await self.client.send_message(
                    chat_id=int(Config.LOG_CHAT_ID),
                    text=msg,
                    disable_web_page_preview=True,
                    disable_notification=True,
                )

            except Exception as e:
                LOGGER.error(
                    f"Failed to send mirror command message to owner's log chat ID: {e}"
                )

        if self.is_leech:
            LOGGER.info(f"Leech Name: {self.name}")
            tg = TelegramUploader(self, up_dir)
            async with task_dict_lock:
                task_dict[self.mid] = TelegramStatus(self, tg, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                tg.upload(),
            )
            # Delete the command message in owner's dump after task completion
            if hasattr(tg, "log_msg") and tg.log_msg:
                try:
                    await delete_message(tg.log_msg)

                except Exception as e:
                    LOGGER.error(
                        f"Failed to delete leech command message in owner's dump: {e}"
                    )
            del tg
        elif is_gdrive_id(self.up_dest):
            LOGGER.info(f"Gdrive Upload Name: {self.name}")
            drive = GoogleDriveUpload(self, up_path)
            async with task_dict_lock:
                task_dict[self.mid] = GoogleDriveStatus(self, drive, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                sync_to_async(drive.upload),
            )
            del drive
        else:
            LOGGER.info(f"Rclone Upload Name: {self.name}")
            RCTransfer = RcloneTransferHelper(self)
            async with task_dict_lock:
                task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                RCTransfer.upload(up_path),
            )
            del RCTransfer
        return

    async def on_upload_complete(
        self,
        link,
        files,
        folders,
        mime_type,
        rclone_path="",
        dir_id="",
    ):
        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

        # Use the most up-to-date name (which may have been modified by leech filename template)
        current_name = self.name

        # Check if MediaInfo is enabled
        mediainfo_enabled = self.user_dict.get("MEDIAINFO_ENABLED", None)
        if mediainfo_enabled is None:
            mediainfo_enabled = Config.MEDIAINFO_ENABLED

        # If this is a leech task and files is a dictionary (from TelegramUploader)
        if self.is_leech and isinstance(files, dict) and files:
            # Get the first file's name from the dictionary values
            first_file = next(iter(files.values()), None)
            if first_file:
                # Use the actual filename that was uploaded
                current_name = first_file
                # Remove part numbers from the filename if present
                import re

                if re.search(r"\.part\d+(\..*)?$", current_name):
                    base_name = re.sub(r"\.part\d+(\..*)?$", "", current_name)
                    ext = current_name.split(".")[-1] if "." in current_name else ""
                    current_name = f"{base_name}.{ext}" if ext else base_name

        msg = f"<b>Name: </b><code>{escape(current_name)}</code>\n\n<blockquote><b>Size: </b>{get_readable_file_size(self.size)}"
        done_msg = f"<b><blockquote>Hey, {self.tag}</blockquote>\nYour task is complete\nPlease check your inbox.</b>"
        LOGGER.info(f"Task Done: {current_name}")
        if self.is_leech:
            msg += f"\n<b>Total Files: </b>{folders}"
            if mime_type != 0:
                msg += f"\n<b>Corrupted Files: </b>{mime_type}"
            msg += f"\n<b>cc: </b>{self.tag}"

            # Add media store links inside blockquote if enabled and there's only one file
            if Config.MEDIA_STORE and files and len(files) == 1:
                url = next(iter(files.keys()))
                chat_id, msg_id = url.split("/")[-2:]
                if chat_id.isdigit():
                    chat_id = f"-100{chat_id}"
                store_link = f"https://t.me/{TgClient.NAME}?start={encode_slink('file' + chat_id + '&&' + msg_id)}"
                msg += f"\n\n<b>Media Links:</b>\n┖ <a href='{store_link}'>Store Link</a> | <a href='https://t.me/share/url?url={store_link}'>Share Link</a>"

                # Add MediaInfo link if it was generated before upload
                user_mediainfo_enabled = self.user_dict.get(
                    "MEDIAINFO_ENABLED", None
                )
                if user_mediainfo_enabled is None:
                    user_mediainfo_enabled = (
                        Config.MEDIAINFO_ENABLED
                    )  # Use the pre-generated MediaInfo link if available
                if (
                    user_mediainfo_enabled
                    and hasattr(self, "mediainfo_link")
                    and self.mediainfo_link
                ):
                    msg += f"\n┖ <b>MediaInfo</b> → <a href='https://graph.org/{self.mediainfo_link}'>View</a>"

            msg += "</blockquote>\n\n"

            if not files:
                await send_message(self.message, msg)
            else:
                fmsg = ""
                for index, (url, name) in enumerate(files.items(), start=1):
                    fmsg += f"{index}. <a href='{url}'>{name}</a>"

                    # Add store link if enabled
                    if Config.MEDIA_STORE:
                        chat_id, msg_id = url.split("/")[-2:]
                        if chat_id.isdigit():
                            chat_id = f"-100{chat_id}"
                        store_link = f"https://t.me/{TgClient.NAME}?start={encode_slink('file' + chat_id + '&&' + msg_id)}"
                        fmsg += f"\n┖ <b>Get Media</b> → <a href='{store_link}'>Store Link</a> | <a href='https://t.me/share/url?url={store_link}'>Share Link</a>"

                    # Add MediaInfo link for media files if enabled
                    # Check if MediaInfo is enabled for this user
                    user_mediainfo_enabled = self.user_dict.get(
                        "MEDIAINFO_ENABLED", None
                    )
                    if user_mediainfo_enabled is None:
                        user_mediainfo_enabled = Config.MEDIAINFO_ENABLED  # Use the pre-generated MediaInfo link if available and valid
                    if (
                        user_mediainfo_enabled
                        and hasattr(self, "mediainfo_link")
                        and self.mediainfo_link
                        and self.mediainfo_link.strip()
                    ):
                        # Support all media types including archives, documents, images, etc.
                        fmsg += f"\n┖ <b>MediaInfo</b> → <a href='https://graph.org/{self.mediainfo_link}'>View</a>"
                        # Log that MediaInfo link was successfully added to the message
                    elif user_mediainfo_enabled and hasattr(self, "mediainfo_link"):
                        # MediaInfo was attempted but failed or returned empty
                        pass

                    fmsg += "\n"
                    if len(fmsg.encode() + msg.encode()) > 4000:
                        # Check if user specified a destination with -up flag
                        if (
                            self.up_dest
                            and not is_gdrive_id(self.up_dest)
                            and not is_rclone_path(self.up_dest)
                        ):
                            # If user specified a destination with -up flag, it takes precedence
                            try:
                                # Send to the specified destination
                                await send_message(
                                    int(self.up_dest),
                                    f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                                )
                                # Also send to user's PM if it's not the same as the specified destination
                                if int(self.up_dest) != self.user_id:
                                    await send_message(
                                        self.user_id,
                                        f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                                    )
                            except Exception as e:
                                LOGGER.error(
                                    f"Failed to send leech log to specified destination {self.up_dest}: {e}"
                                )
                                # Fallback to user's PM
                                await send_message(
                                    self.user_id,
                                    f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                                )
                        else:
                            # No specific destination was specified or it's a cloud destination
                            # Determine leech destinations based on requirements
                            leech_destinations = []

                            # Always add user's PM
                            leech_destinations.append(self.user_id)

                            # Check if user has set their own dump and owner's premium status
                            user_dump = self.user_dict.get("USER_DUMP")
                            owner_has_premium = TgClient.IS_PREMIUM_USER

                            # Case 1: If user didn't set any dump
                            if not user_dump:
                                # Send to owner leech dump and bot PM
                                if Config.LEECH_DUMP_CHAT:
                                    leech_destinations.append(
                                        int(Config.LEECH_DUMP_CHAT)
                                    )

                            # Case 2: If user set their own dump and owner has no premium string
                            elif user_dump and not owner_has_premium:
                                # Send to user's own dump, owner leech dump, and bot PM
                                leech_destinations.append(int(user_dump))
                                if Config.LEECH_DUMP_CHAT:
                                    leech_destinations.append(
                                        int(Config.LEECH_DUMP_CHAT)
                                    )

                            # Case 3: If user set their own dump and owner has premium string
                            elif user_dump and owner_has_premium:
                                # By default, send to owner leech dump and bot PM
                                if Config.LEECH_DUMP_CHAT:
                                    leech_destinations.append(
                                        int(Config.LEECH_DUMP_CHAT)
                                    )

                                # TODO: Add logic to check if owner has permission to user's dump
                                # For now, we'll assume owner doesn't have permission to user's dump

                            # Remove duplicates while preserving order
                            seen = set()
                            leech_destinations = [
                                x
                                for x in leech_destinations
                                if not (x in seen or seen.add(x))
                            ]

                            # Send to all destinations
                            for dest in leech_destinations:
                                try:
                                    await send_message(
                                        dest,
                                        f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                                    )
                                except Exception as e:
                                    LOGGER.error(
                                        f"Failed to send leech log to destination {dest}: {e}"
                                    )

                        await sleep(1)
                        fmsg = ""
                if fmsg != "":
                    # Check if user specified a destination with -up flag
                    if (
                        self.up_dest
                        and not is_gdrive_id(self.up_dest)
                        and not is_rclone_path(self.up_dest)
                    ):
                        # If user specified a destination with -up flag, it takes precedence
                        try:
                            # Send to the specified destination
                            await send_message(
                                int(self.up_dest),
                                f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                            )
                            # Also send to user's PM if it's not the same as the specified destination
                            if int(self.up_dest) != self.user_id:
                                await send_message(
                                    self.user_id,
                                    f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                                )
                        except Exception as e:
                            LOGGER.error(
                                f"Failed to send leech log to specified destination {self.up_dest}: {e}"
                            )
                            # Fallback to user's PM
                            await send_message(
                                self.user_id,
                                f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                            )
                    else:
                        # No specific destination was specified or it's a cloud destination
                        # Determine leech destinations based on requirements
                        leech_destinations = []

                        # Always add user's PM
                        leech_destinations.append(self.user_id)

                        # Check if user has set their own dump and owner's premium status
                        user_dump = self.user_dict.get("USER_DUMP")
                        owner_has_premium = TgClient.IS_PREMIUM_USER

                        # Case 1: If user didn't set any dump
                        if not user_dump:
                            # Send to owner leech dump and bot PM
                            if Config.LEECH_DUMP_CHAT:
                                leech_destinations.append(
                                    int(Config.LEECH_DUMP_CHAT)
                                )

                        # Case 2: If user set their own dump and owner has no premium string
                        elif user_dump and not owner_has_premium:
                            # Send to user's own dump, owner leech dump, and bot PM
                            leech_destinations.append(int(user_dump))
                            if Config.LEECH_DUMP_CHAT:
                                leech_destinations.append(
                                    int(Config.LEECH_DUMP_CHAT)
                                )

                        # Case 3: If user set their own dump and owner has premium string
                        elif user_dump and owner_has_premium:
                            # By default, send to owner leech dump and bot PM
                            if Config.LEECH_DUMP_CHAT:
                                leech_destinations.append(
                                    int(Config.LEECH_DUMP_CHAT)
                                )

                            # TODO: Add logic to check if owner has permission to user's dump
                            # For now, we'll assume owner doesn't have permission to user's dump

                        # Remove duplicates while preserving order
                        seen = set()
                        leech_destinations = [
                            x
                            for x in leech_destinations
                            if not (x in seen or seen.add(x))
                        ]

                        # Send to all destinations
                        for dest in leech_destinations:
                            try:
                                await send_message(
                                    dest,
                                    f"{msg}<blockquote expandable>{fmsg}</blockquote>",
                                )
                            except Exception as e:
                                LOGGER.error(
                                    f"Failed to send leech log to destination {dest}: {e}"
                                )

                # Send completion message to original chat
                await send_message(self.message, done_msg)
        else:
            msg += f"\n\n<b>Type: </b>{mime_type}"
            if mime_type == "Folder":
                msg += f"\n<b>SubFolders: </b>{folders}"
                msg += f"\n<b>Files: </b>{files}"

            # Add MediaInfo link for mirror tasks if enabled
            # Check if MediaInfo is enabled for this user
            user_mediainfo_enabled = self.user_dict.get("MEDIAINFO_ENABLED", None)
            if user_mediainfo_enabled is None:
                user_mediainfo_enabled = (
                    Config.MEDIAINFO_ENABLED
                )  # Use the pre-generated MediaInfo link if available and valid
            if (
                user_mediainfo_enabled
                and hasattr(self, "mediainfo_link")
                and self.mediainfo_link
                and self.mediainfo_link.strip()
            ):
                # Support all media types including archives, documents, images, etc.
                msg += f"\n<b>MediaInfo</b> → <a href='https://graph.org/{self.mediainfo_link}'>View</a>"
                # Log that MediaInfo link was successfully added to the message
            elif user_mediainfo_enabled and hasattr(self, "mediainfo_link"):
                # MediaInfo was attempted but failed or returned empty
                pass
            if link or (
                rclone_path and Config.RCLONE_SERVE_URL and not self.private_link
            ):
                buttons = ButtonMaker()
                if link:
                    buttons.url_button("☁️ Cloud Link", link)
                else:
                    msg += f"\n\nPath: <code>{rclone_path}</code>"
                if rclone_path and Config.RCLONE_SERVE_URL and not self.private_link:
                    remote, rpath = rclone_path.split(":", 1)
                    url_path = rutils.quote(f"{rpath}")
                    share_url = f"{Config.RCLONE_SERVE_URL}/{remote}/{url_path}"
                    if mime_type == "Folder":
                        share_url += "/"
                    buttons.url_button("🔗 Rclone Link", share_url)
                if not rclone_path and dir_id:
                    INDEX_URL = ""
                    if self.private_link:
                        INDEX_URL = self.user_dict.get("INDEX_URL", "") or ""
                    elif Config.INDEX_URL:
                        INDEX_URL = Config.INDEX_URL
                    if INDEX_URL:
                        share_url = f"{INDEX_URL}findpath?id={dir_id}"
                        buttons.url_button("⚡ Index Link", share_url)
                        if mime_type.startswith(("image", "video", "audio")):
                            share_urls = f"{INDEX_URL}findpath?id={dir_id}&view=true"
                            buttons.url_button("🌐 View Link", share_urls)
                button = buttons.build_menu(2)
            else:
                msg += f"\n\nPath: <code>{rclone_path}</code>"
                button = None
            msg += f"\n\n<b>cc: </b>{self.tag}</blockquote>"

            # Check if user specified a destination with -up flag
            if (
                self.up_dest
                and not is_gdrive_id(self.up_dest)
                and not is_rclone_path(self.up_dest)
            ):
                # If user specified a destination with -up flag, it takes precedence
                try:
                    # Send to the specified destination
                    await send_message(int(self.up_dest), msg, button)
                    # Also send to user's PM if it's not the same as the specified destination
                    if int(self.up_dest) != self.user_id:
                        await send_message(self.user_id, msg, button)
                except Exception as e:
                    LOGGER.error(
                        f"Failed to send mirror log to specified destination {self.up_dest}: {e}"
                    )
                    # Fallback to user's PM
                    await send_message(self.user_id, msg, button)
            else:
                # No specific destination was specified or it's a cloud destination
                # Determine mirror log destinations based on requirements
                mirror_destinations = []

                # Always add user's PM
                mirror_destinations.append(self.user_id)

                # Check if user has set their own dump
                user_dump = self.user_dict.get("USER_DUMP")

                # Case 1: If user set their own dump and owner has set log chat id
                if user_dump and Config.LOG_CHAT_ID:
                    # Send to user dump, owner log chat id, and bot PM
                    mirror_destinations.append(int(user_dump))
                    mirror_destinations.append(int(Config.LOG_CHAT_ID))

                # Case 2: If user set their own dump and owner didn't set log chat id
                elif user_dump and not Config.LOG_CHAT_ID:
                    # Send to user dump and bot PM
                    mirror_destinations.append(int(user_dump))

                # Case 3: If user didn't set their own dump and owner set log chat id
                elif not user_dump and Config.LOG_CHAT_ID:
                    # Send to owner log chat id and bot PM
                    mirror_destinations.append(int(Config.LOG_CHAT_ID))

                # Remove duplicates while preserving order
                seen = set()
                mirror_destinations = [
                    x for x in mirror_destinations if not (x in seen or seen.add(x))
                ]

                # Send to all destinations
                for dest in mirror_destinations:
                    try:
                        await send_message(dest, msg, button)
                    except Exception as e:
                        LOGGER.error(
                            f"Failed to send mirror log to destination {dest}: {e}"
                        )

            # Send completion message to original chat
            await send_message(self.message, done_msg)
        # Delete the command message (with link or replied) after task completion
        try:
            # Only delete the command message if it's not in a private chat
            if (
                self.message
                and self.message.chat
                and self.message.chat.type != "private"
            ):
                await delete_message(self.message)
            # Delete the mirror command message in the owner's log chat ID if it exists
            if hasattr(self, "log_msg") and self.log_msg:
                await delete_message(self.log_msg)
        except Exception as e:
            LOGGER.error(f"Failed to delete command message: {e}")

        if self.seed:
            await clean_target(self.up_dir)
            async with queue_dict_lock:
                if self.mid in non_queued_up:
                    non_queued_up.remove(self.mid)
            await start_from_queued()
            return

        # Add a delay before cleaning up to ensure all processes are complete
        await sleep(3)

        # Now clean up the download directory
        await clean_download(self.dir)
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        async with queue_dict_lock:
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()

    async def on_download_error(self, error, button=None):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await self.remove_from_same_dir()

        # Delete command message and any replied message for all tasks
        await delete_links(self.message)

        # Send and auto-delete error message
        msg = f"{self.tag} Download: {escape(str(error))}"
        error_msg = await send_message(self.message, msg, button)
        create_task(
            auto_delete_message(error_msg, time=300),
        )  # noqa: RUF006, RUF100

        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()

        # Add a delay before cleaning up to ensure all processes are complete
        await sleep(5)

        # Now clean up the download directory
        await clean_download(self.dir)
        if self.up_dir:
            await clean_download(self.up_dir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)

    async def on_upload_error(self, error):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        x = await send_message(self.message, f"{self.tag} {escape(str(error))}")
        create_task(auto_delete_message(x, time=300))  # noqa: RUF006, RUF100
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()

        # Add a delay before cleaning up to ensure all processes are complete
        await sleep(5)

        # Now clean up the download directory
        await clean_download(self.dir)
        if self.up_dir:
            await clean_download(self.up_dir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)
