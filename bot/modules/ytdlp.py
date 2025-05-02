from asyncio import Event, create_task, wait_for
from functools import partial
from os import path as ospath
from time import time

from httpx import AsyncClient
from pyrogram.filters import regex, user
from pyrogram.handlers import CallbackQueryHandler
from yt_dlp import YoutubeDL

from bot import DOWNLOAD_DIR, LOGGER, bot_loop, task_dict_lock
from bot.core.config_manager import Config
from bot.helper.aeon_utils.access_check import error_check
from bot.helper.ext_utils.bot_utils import (
    COMMAND_USAGE,
    arg_parser,
    new_task,
    sync_to_async,
)
from bot.helper.ext_utils.links_utils import is_url
from bot.helper.ext_utils.status_utils import (
    get_readable_file_size,
    get_readable_time,
)
from bot.helper.listeners.task_listener import TaskListener
from bot.helper.mirror_leech_utils.download_utils.yt_dlp_download import (
    YoutubeDLHelper,
)
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_links,
    delete_message,
    edit_message,
    send_message,
)


@new_task
async def select_format(_, query, obj):
    data = query.data.split()
    await query.answer()

    if data[1] == "dict":
        b_name = data[2]
        await obj.qual_subbuttons(b_name)
    elif data[1] == "mp3":
        await obj.mp3_subbuttons()
    elif data[1] == "audio":
        await obj.audio_format()
    elif data[1] == "info":
        # For section headers, show a helpful message
        await query.answer(
            "This is a section header. Please select a format below.",
            show_alert=True,
        )
    elif data[1] == "section":
        # Handle section selection
        try:
            section = data[2]
            await obj.show_section(section)
        except Exception as e:
            LOGGER.error(f"Error in section selection: {e}")
            await query.answer(f"Error: {e!s}", show_alert=True)
    elif data[1] == "aq":
        if data[2] == "back":
            await obj.audio_format()
        else:
            await obj.audio_quality(data[2])
    elif data[1] == "back":
        await obj.back_to_main()
    elif data[1] == "cancel":
        # First send cancellation message
        cancel_msg = await send_message(
            obj.listener.message,
            f"{obj.listener.tag} Task has been cancelled!",
        )

        # Delete the selection menu
        await delete_message(obj._reply_to)

        # Delete the original command
        await delete_message(obj.listener.message)

        # Create background task for auto-deletion
        create_task(  # noqa: RUF006
            auto_delete_message(cancel_msg, time=300),
        )  # 5 minutes auto-delete

        obj.qual = None
        obj.listener.is_cancelled = True
        obj.event.set()
    else:
        if data[1] == "sub":
            obj.qual = obj.formats[data[2]][data[3]][1]
        elif "|" in data[1]:
            obj.qual = obj.formats[data[1]]
        else:
            obj.qual = data[1]
        obj.event.set()


class YtSelection:
    def __init__(self, listener):
        self.listener = listener
        self._is_m4a = False
        self._reply_to = None
        self._time = time()
        self._timeout = 120
        self._is_playlist = False
        self._main_buttons = None
        self.event = Event()
        self.formats = {}
        self.qual = None

    async def _event_handler(self):
        pfunc = partial(select_format, obj=self)
        handler = self.listener.client.add_handler(
            CallbackQueryHandler(
                pfunc,
                filters=regex("^ytq") & user(self.listener.user_id),
            ),
            group=-1,
        )
        try:
            await wait_for(self.event.wait(), timeout=self._timeout)
        except Exception:
            # Delete both original command and its replied message
            await delete_links(self.listener.message)

            # Send new timeout message instead of editing
            timeout_msg = await send_message(
                self.listener.message,
                f"{self.listener.tag} Timed Out. Task has been cancelled!",
            )

            # Delete the selection menu
            await delete_message(self._reply_to)

            # Create background task to delete timeout message after 5 minutes
            create_task(  # noqa: RUF006
                auto_delete_message(timeout_msg, time=300),
            )  # 5 minutes auto-delete

            self.qual = None
            self.listener.is_cancelled = True
            self.event.set()
        finally:
            self.listener.client.remove_handler(*handler)

    async def show_section(self, section):
        buttons = ButtonMaker()

        if self._is_playlist:
            # For playlists, show predefined formats
            if section == "sd":
                # SD formats (144p, 240p, 360p, 480p) in ascending order
                for i in ["144", "240", "360", "480"]:
                    # MP4 format with audio
                    b_data = f"{i}|mp4"
                    buttons.data_button(f"{i}p MP4", f"ytq {b_data}")

                    # WebM format with audio
                    b_data = f"{i}|webm"
                    buttons.data_button(f"{i}p WebM", f"ytq {b_data}")

            elif section == "hd":
                # HD formats (720p, 1080p) in ascending order
                for i in ["720", "1080"]:
                    # MP4 format with audio
                    b_data = f"{i}|mp4"
                    buttons.data_button(f"{i}p MP4", f"ytq {b_data}")

                    # WebM format with audio
                    b_data = f"{i}|webm"
                    buttons.data_button(f"{i}p WebM", f"ytq {b_data}")

                    # AV1 format with audio
                    b_data = f"{i}|av1"
                    buttons.data_button(f"{i}p AV1", f"ytq {b_data}")

            elif section == "4k":
                # 4K formats (1440p, 2160p) in ascending order
                for i in ["1440", "2160"]:
                    # MP4 format with audio
                    b_data = f"{i}|mp4"
                    buttons.data_button(f"{i}p MP4", f"ytq {b_data}")

                    # WebM format with audio
                    b_data = f"{i}|webm"
                    buttons.data_button(f"{i}p WebM", f"ytq {b_data}")

                    # AV1 format with audio
                    b_data = f"{i}|av1"
                    buttons.data_button(f"{i}p AV1", f"ytq {b_data}")

        # For single videos, show available formats from the extracted info
        elif section in ["sd", "hd", "4k"]:
            # Define resolution ranges for each section
            if section == "sd":
                # SD: below 720p
                def res_range(r):
                    return r < 720
            elif section == "hd":
                # HD: 720p to 1440p (exclusive)
                def res_range(r):
                    return 720 <= r < 1440
            else:  # 4k
                # 4K: 1440p and above
                def res_range(r):
                    return r >= 1440

            # Get all resolutions in this range
            matching_resolutions = []
            for r in self.formats:
                # Check if the format name contains 'p' and has a number before it
                if "p" in r:
                    try:
                        # Try to extract the resolution number
                        res_num = int(r.split("p")[0])
                        # Check if it's in the desired range
                        if res_range(res_num):
                            matching_resolutions.append(r)
                    except (ValueError, IndexError):
                        # Skip formats that don't have a valid resolution number
                        continue

            # Sort resolutions in ascending order
            def get_resolution(format_name):
                try:
                    if "p" in format_name:
                        return int(format_name.split("p")[0])
                    return 0
                except (ValueError, IndexError):
                    return 0

            # Check if we found any matching resolutions
            if not matching_resolutions:
                # No formats in this resolution range
                buttons.data_button(
                    f"No {section.upper()} formats available", "ytq info"
                )
            else:
                # Add formats in ascending order
                for b_name in sorted(matching_resolutions, key=get_resolution):
                    try:
                        tbr_dict = self.formats[b_name]
                        if len(tbr_dict) == 1:
                            tbr, v_list = next(iter(tbr_dict.items()))
                            size_str = get_readable_file_size(v_list[0])
                            # Highlight AV1 formats
                            if "av1" in b_name.lower():
                                buttonName = f"🔸 {b_name} ({size_str})"
                            else:
                                buttonName = f"{b_name} ({size_str})"
                            buttons.data_button(
                                buttonName, f"ytq sub {b_name} {tbr}"
                            )
                        else:
                            buttons.data_button(b_name, f"ytq dict {b_name}")
                    except Exception as e:
                        LOGGER.error(f"Error adding format button {b_name}: {e}")
                        continue

        # Audio options section is the same for both playlist and single videos
        if section == "audio":
            # Audio options
            buttons.data_button("MP3 Audio", "ytq mp3")
            buttons.data_button("Other Audio Formats", "ytq audio")
            buttons.data_button("Best Audio", "ytq ba/b")

        # Quick options section is the same for both playlist and single videos
        elif section == "quick":
            # Quick options
            buttons.data_button("Best Video", "ytq bv*+ba/b")
            buttons.data_button("Best Audio", "ytq ba/b")

        # Add back button
        buttons.data_button("Back", "ytq back", "footer")
        buttons.data_button("Cancel", "ytq cancel", "footer")

        subbuttons = buttons.build_menu(2)
        msg = f"Choose {section.upper()} Format:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await edit_message(self._reply_to, msg, subbuttons)

    async def get_quality(self, result):
        buttons = ButtonMaker()
        if "entries" in result:
            self._is_playlist = True

            # Store all formats for later use
            # SD formats
            for i in ["144", "240", "360", "480"]:
                # MP4 format with audio
                video_format = (
                    f"bv*[height<=?{i}][ext=mp4]+ba[ext=m4a]/b[height<=?{i}]"
                )
                b_data = f"{i}|mp4"
                self.formats[b_data] = video_format

                # WebM format with audio
                video_format = f"bv*[height<=?{i}][ext=webm]+ba/b[height<=?{i}]"
                b_data = f"{i}|webm"
                self.formats[b_data] = video_format

            # HD formats
            for i in ["720", "1080"]:
                # MP4 format with audio
                video_format = (
                    f"bv*[height<=?{i}][ext=mp4]+ba[ext=m4a]/b[height<=?{i}]"
                )
                b_data = f"{i}|mp4"
                self.formats[b_data] = video_format

                # WebM format with audio
                video_format = f"bv*[height<=?{i}][ext=webm]+ba/b[height<=?{i}]"
                b_data = f"{i}|webm"
                self.formats[b_data] = video_format

                # AV1 format with audio
                video_format = f"bv*[height<=?{i}][vcodec*=av01]+ba/b[height<=?{i}]"
                b_data = f"{i}|av1"
                self.formats[b_data] = video_format

            # 4K formats
            for i in ["1440", "2160"]:
                # MP4 format with audio
                video_format = (
                    f"bv*[height<=?{i}][ext=mp4]+ba[ext=m4a]/b[height<=?{i}]"
                )
                b_data = f"{i}|mp4"
                self.formats[b_data] = video_format

                # WebM format with audio
                video_format = f"bv*[height<=?{i}][ext=webm]+ba/b[height<=?{i}]"
                b_data = f"{i}|webm"
                self.formats[b_data] = video_format

                # AV1 format with audio
                video_format = f"bv*[height<=?{i}][vcodec*=av01]+ba/b[height<=?{i}]"
                b_data = f"{i}|av1"
                self.formats[b_data] = video_format

            # Create main menu with sections
            # Resolution sections in ascending order
            buttons.data_button("🔹 SD FORMATS (144p-480p) 🔹", "ytq section sd")
            buttons.data_button("🔹 HD FORMATS (720p-1080p) 🔹", "ytq section hd")
            buttons.data_button("🔹 4K FORMATS (1440p-2160p) 🔹", "ytq section 4k")
            buttons.data_button("🔹 AUDIO OPTIONS 🔹", "ytq section audio")
            buttons.data_button("🔹 QUICK OPTIONS 🔹", "ytq section quick")
            buttons.data_button("Cancel", "ytq cancel", "footer")

            self._main_buttons = buttons.build_menu(1)
            msg = f"Choose Playlist Videos Quality Category:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        else:
            format_dict = result.get("formats")
            if format_dict is not None:
                # Group formats by codec for better organization
                codec_groups = {}

                for item in format_dict:
                    if item.get("tbr"):
                        format_id = item["format_id"]

                        if item.get("filesize"):
                            size = item["filesize"]
                        elif item.get("filesize_approx"):
                            size = item["filesize_approx"]
                        else:
                            size = 0

                        # Handle audio formats
                        if item.get("video_ext") == "none" and (
                            item.get("resolution") == "audio only"
                            or item.get("acodec") != "none"
                        ):
                            if item.get("audio_ext") == "m4a":
                                self._is_m4a = True
                            b_name = (
                                f"{item.get('acodec') or format_id}-{item['ext']}"
                            )
                            v_format = format_id

                            # Add to audio group
                            codec_group = "audio"

                        # Handle video formats
                        elif item.get("height"):
                            height = item["height"]
                            ext = item["ext"]
                            fps = item["fps"] if item.get("fps") else ""

                            # Identify codec for grouping
                            vcodec = item.get("vcodec", "")
                            if "av01" in vcodec:
                                codec_group = "av1"
                            elif "avc" in vcodec or "h264" in vcodec:
                                codec_group = "h264"
                            elif "vp9" in vcodec:
                                codec_group = "vp9"
                            else:
                                codec_group = ext

                            b_name = f"{height}p{fps}-{codec_group}"
                            ba_ext = (
                                "[ext=m4a]" if self._is_m4a and ext == "mp4" else ""
                            )
                            v_format = f"{format_id}+ba{ba_ext}/b[height=?{height}]"
                        else:
                            continue

                        # Store format info
                        self.formats.setdefault(b_name, {})[f"{item['tbr']}"] = [
                            size,
                            v_format,
                        ]

                        # Group by codec for better UI organization
                        codec_groups.setdefault(codec_group, []).append(b_name)

                # Group formats by resolution for better organization
                resolutions = {}

                # Collect all formats by resolution
                for codec_group, b_names in codec_groups.items():
                    if codec_group != "audio":
                        for b_name in b_names:
                            if "p" in b_name:
                                resolution = int(b_name.split("p")[0])
                                resolutions.setdefault(resolution, []).append(
                                    (b_name, codec_group)
                                )

                # Store formats for section-based display
                # We'll use the show_section method to display them when needed

            # Create main menu with sections for non-playlist videos
            # Resolution sections in ascending order
            buttons.data_button("🔹 SD FORMATS (144p-480p) 🔹", "ytq section sd")
            buttons.data_button("🔹 HD FORMATS (720p-1080p) 🔹", "ytq section hd")
            buttons.data_button("🔹 4K FORMATS (1440p-2160p) 🔹", "ytq section 4k")
            buttons.data_button("🔹 AUDIO OPTIONS 🔹", "ytq section audio")
            buttons.data_button("🔹 QUICK OPTIONS 🔹", "ytq section quick")
            buttons.data_button("Cancel", "ytq cancel", "footer")

            self._main_buttons = buttons.build_menu(1)
            msg = f"Choose Video Quality Category:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        self._reply_to = await send_message(
            self.listener.message,
            msg,
            self._main_buttons,
        )
        await self._event_handler()
        if not self.listener.is_cancelled:
            await delete_message(self._reply_to)
        return self.qual

    async def back_to_main(self):
        if self._is_playlist:
            msg = f"Choose Playlist Videos Quality Category:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        else:
            msg = f"Choose Video Quality Category:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await edit_message(self._reply_to, msg, self._main_buttons)

    async def qual_subbuttons(self, b_name):
        buttons = ButtonMaker()
        tbr_dict = self.formats[b_name]
        for tbr, d_data in tbr_dict.items():
            button_name = f"{tbr}K ({get_readable_file_size(d_data[0])})"
            buttons.data_button(button_name, f"ytq sub {b_name} {tbr}")
        buttons.data_button("Back", "ytq back", "footer")
        buttons.data_button("Cancel", "ytq cancel", "footer")
        subbuttons = buttons.build_menu(2)
        msg = f"Choose Bit rate for <b>{b_name}</b>:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await edit_message(self._reply_to, msg, subbuttons)

    async def mp3_subbuttons(self):
        i = "s" if self._is_playlist else ""
        buttons = ButtonMaker()
        audio_qualities = [64, 128, 192, 256, 320]
        for q in audio_qualities:
            audio_format = f"ba/b-mp3-{q}"
            buttons.data_button(f"{q}K-mp3", f"ytq {audio_format}")
        buttons.data_button("Back", "ytq back")
        buttons.data_button("Cancel", "ytq cancel")
        subbuttons = buttons.build_menu(3)
        msg = f"Choose mp3 Audio{i} Bitrate:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await edit_message(self._reply_to, msg, subbuttons)

    async def audio_format(self):
        i = "s" if self._is_playlist else ""
        buttons = ButtonMaker()
        # Add more audio formats and organize them
        for frmt in ["aac", "alac", "flac", "m4a", "mp3", "opus", "vorbis", "wav"]:
            audio_format = f"ba/b-{frmt}-"
            # Add format description
            if frmt == "flac":
                desc = "(Lossless)"
            elif frmt == "alac":
                desc = "(Apple Lossless)"
            elif frmt == "opus":
                desc = "(Best Compressed)"
            elif frmt == "mp3":
                desc = "(Common)"
            elif frmt == "aac":
                desc = "(AAC)"
            elif frmt == "m4a":
                desc = "(AAC in M4A)"
            elif frmt == "vorbis":
                desc = "(OGG)"
            elif frmt == "wav":
                desc = "(Uncompressed)"
            else:
                desc = ""
            buttons.data_button(f"{frmt.upper()} {desc}", f"ytq aq {audio_format}")
        buttons.data_button("Back", "ytq back", "footer")
        buttons.data_button("Cancel", "ytq cancel", "footer")
        subbuttons = buttons.build_menu(2)
        msg = f"Choose Audio{i} Format:\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await edit_message(self._reply_to, msg, subbuttons)

    async def audio_quality(self, format):
        i = "s" if self._is_playlist else ""
        buttons = ButtonMaker()
        for qual in range(11):
            audio_format = f"{format}{qual}"
            buttons.data_button(str(qual), f"ytq {audio_format}")
        buttons.data_button("Back", "ytq aq back")
        buttons.data_button("Cancel", "ytq aq cancel")
        subbuttons = buttons.build_menu(5)
        msg = f"Choose Audio{i} Quality:\n0 is best and 10 is worst\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await edit_message(self._reply_to, msg, subbuttons)


def extract_info(link, options):
    with YoutubeDL(options) as ydl:
        result = ydl.extract_info(link, download=False)
        if result is None:
            raise ValueError("Info result is None")
        return result


async def _mdisk(link, name):
    key = link.split("/")[-1]
    async with AsyncClient(verify=False) as client:
        resp = await client.get(
            f"https://diskuploader.entertainvideo.com/v1/file/cdnurl?param={key}",
        )
    if resp.status_code == 200:
        resp_json = resp.json()
        link = resp_json["source"]
        if not name:
            name = resp_json["filename"]
    return name, link


class YtDlp(TaskListener):
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        client,
        message,
        _=None,  # Placeholder for compatibility with Mirror class
        is_leech=False,
        # These parameters are unused but required for compatibility with Mirror class
        **kwargs,
    ):
        # Extract parameters from kwargs with defaults
        same_dir = kwargs.get("same_dir", {})
        bulk = kwargs.get("bulk", [])
        multi_tag = kwargs.get("multi_tag")
        options = kwargs.get("options", "")
        if same_dir is None:
            same_dir = {}
        if bulk is None:
            bulk = []
        self.message = message
        self.client = client
        self.multi_tag = multi_tag
        self.options = options
        self.same_dir = same_dir
        self.bulk = bulk
        super().__init__()
        self.is_ytdlp = True
        self.is_leech = is_leech

    async def new_event(self):
        text = self.message.text.split("\n")
        input_list = text[0].split(" ")
        qual = ""
        error_msg, error_button = await error_check(self.message)
        if error_msg:
            await delete_links(self.message)
            error = await send_message(self.message, error_msg, error_button)
            create_task(auto_delete_message(error, time=300))  # noqa: RUF006
            return

        args = {
            "-doc": False,
            "-med": False,
            "-s": False,
            "-b": False,
            "-z": False,
            "-sv": False,
            "-ss": False,
            "-f": False,
            "-fd": False,
            "-fu": False,
            "-hl": False,
            "-bt": False,
            "-ut": False,
            "-merge-video": False,
            "-merge-audio": False,
            "-merge-subtitle": False,
            "-merge-all": False,
            "-i": 0,
            "-sp": 0,
            "link": "",
            "-m": "",
            "-opt": {},
            "-n": "",
            "-up": "",
            "-rcf": "",
            "-t": "",
            "-ca": "",
            "-cv": "",
            "-ns": "",
            "-md": "",
            "-metadata-title": "",
            "-metadata-author": "",
            "-metadata-comment": "",
            "-metadata-all": "",
            "-metadata-video-title": "",
            "-metadata-video-author": "",
            "-metadata-video-comment": "",
            "-metadata-audio-title": "",
            "-metadata-audio-author": "",
            "-metadata-audio-comment": "",
            "-metadata-subtitle-title": "",
            "-metadata-subtitle-author": "",
            "-metadata-subtitle-comment": "",
            "-tl": "",
            "-ff": set(),
        }

        # Parse arguments from the command
        arg_parser(input_list[1:], args)

        # Check if media tools flags are enabled
        from bot.helper.ext_utils.bot_utils import is_flag_enabled

        # Disable flags that depend on disabled media tools
        for flag in list(args.keys()):
            if flag.startswith("-") and not is_flag_enabled(flag):
                if isinstance(args[flag], bool):
                    args[flag] = False
                elif isinstance(args[flag], set):
                    args[flag] = set()
                elif isinstance(args[flag], str):
                    args[flag] = ""
                elif isinstance(args[flag], int):
                    args[flag] = 0

        try:
            self.multi = int(args["-i"])
        except Exception:
            self.multi = 0

        try:
            if args["-ff"]:
                if isinstance(args["-ff"], set):
                    self.ffmpeg_cmds = args["-ff"]
                else:
                    self.ffmpeg_cmds = eval(args["-ff"])
        except Exception as e:
            self.ffmpeg_cmds = None
            LOGGER.error(e)

        try:
            opt = eval(args["-opt"]) if args["-opt"] else {}
        except Exception as e:
            LOGGER.error(e)
            opt = {}

        self.select = args["-s"]
        self.name = args["-n"]
        self.up_dest = args["-up"]
        self.rc_flags = args["-rcf"]
        self.link = args["link"]
        self.compress = args["-z"]
        self.thumb = args["-t"]
        self.split_size = args["-sp"]
        self.sample_video = args["-sv"]
        self.screen_shots = args["-ss"]
        self.force_run = args["-f"]
        self.force_download = args["-fd"]
        self.force_upload = args["-fu"]
        self.convert_audio = args["-ca"]
        self.convert_video = args["-cv"]
        self.name_sub = args["-ns"]
        self.hybrid_leech = args["-hl"]
        self.thumbnail_layout = args["-tl"]
        self.as_doc = args["-doc"]
        self.as_med = args["-med"]
        self.metadata = args["-md"]
        self.metadata_title = args["-metadata-title"]
        self.metadata_author = args["-metadata-author"]
        self.metadata_comment = args["-metadata-comment"]
        self.metadata_all = args["-metadata-all"]
        self.metadata_video_title = args["-metadata-video-title"]
        self.metadata_video_author = args["-metadata-video-author"]
        self.metadata_video_comment = args["-metadata-video-comment"]
        self.metadata_audio_title = args["-metadata-audio-title"]
        self.metadata_audio_author = args["-metadata-audio-author"]
        self.metadata_audio_comment = args["-metadata-audio-comment"]
        self.metadata_subtitle_title = args["-metadata-subtitle-title"]
        self.metadata_subtitle_author = args["-metadata-subtitle-author"]
        self.metadata_subtitle_comment = args["-metadata-subtitle-comment"]
        self.folder_name = (
            f"/{args['-m']}".rstrip("/") if len(args["-m"]) > 0 else ""
        )
        self.bot_trans = args["-bt"]
        self.user_trans = args["-ut"]
        self.merge_video = args["-merge-video"]
        self.merge_audio = args["-merge-audio"]
        self.merge_subtitle = args["-merge-subtitle"]
        self.merge_all = args["-merge-all"]

        is_bulk = args["-b"]

        bulk_start = 0
        bulk_end = 0
        reply_to = None

        if not isinstance(is_bulk, bool):
            dargs = is_bulk.split(":")
            bulk_start = dargs[0] or None
            if len(dargs) == 2:
                bulk_end = dargs[1] or None
            is_bulk = True

        if not is_bulk:
            if self.multi > 0:
                if self.folder_name:
                    async with task_dict_lock:
                        if self.folder_name in self.same_dir:
                            self.same_dir[self.folder_name]["tasks"].add(self.mid)
                            for fd_name in self.same_dir:
                                if fd_name != self.folder_name:
                                    self.same_dir[fd_name]["total"] -= 1
                        elif self.same_dir:
                            self.same_dir[self.folder_name] = {
                                "total": self.multi,
                                "tasks": {self.mid},
                            }
                            for fd_name in self.same_dir:
                                if fd_name != self.folder_name:
                                    self.same_dir[fd_name]["total"] -= 1
                        else:
                            self.same_dir = {
                                self.folder_name: {
                                    "total": self.multi,
                                    "tasks": {self.mid},
                                },
                            }
                elif self.same_dir:
                    async with task_dict_lock:
                        for fd_name in self.same_dir:
                            self.same_dir[fd_name]["total"] -= 1
        else:
            await self.init_bulk(input_list, bulk_start, bulk_end, YtDlp)
            return

        if len(self.bulk) != 0:
            del self.bulk[0]

        path = f"{DOWNLOAD_DIR}{self.mid}{self.folder_name}"

        await self.get_tag(text)

        opt = opt or self.user_dict.get("YT_DLP_OPTIONS") or Config.YT_DLP_OPTIONS

        if not self.link and (reply_to := self.message.reply_to_message):
            self.link = reply_to.text.split("\n", 1)[0].strip()

        if not is_url(self.link):
            await delete_links(self.message)
            usage_msg = await send_message(
                self.message,
                COMMAND_USAGE["yt"][0],
                COMMAND_USAGE["yt"][1],
            )
            create_task(auto_delete_message(usage_msg, time=300))  # noqa: RUF006
            await self.remove_from_same_dir()
            return

        if "mdisk.me" in self.link:
            self.name, self.link = await _mdisk(self.link, self.name)

        try:
            await self.before_start()
        except Exception as e:
            await delete_links(self.message)
            error_msg = await send_message(self.message, str(e))
            create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
            await self.remove_from_same_dir()
            return

        # Check for user-specific cookies
        user_id = self.user_id
        user_cookies_path = f"cookies/{user_id}.txt"

        # Security check: Only use user's own cookies or the default cookies
        if ospath.exists(user_cookies_path):
            cookies_file = user_cookies_path
        else:
            cookies_file = "cookies.txt"

        options = {"usenetrc": True, "cookiefile": cookies_file}
        if opt:
            for key, value in opt.items():
                if key in ["postprocessors", "download_ranges"]:
                    continue
                if key == "format" and not self.select:
                    if value.startswith("ba/b-"):
                        qual = value
                        continue
                    qual = value

                options[key] = value
        options["playlist_items"] = "0"

        # Log which cookies file is being used
        if cookies_file == user_cookies_path:
            LOGGER.info(f"Using user-specific cookies for user ID: {user_id}")
        else:
            LOGGER.info("Using default cookies.txt file")

        try:
            # Log which client is being used for YouTube
            if "youtube.com" in self.link or "youtu.be" in self.link:
                LOGGER.info("Extracting YouTube video info with TV client")
                # Add YouTube TV client settings to help with SSAP experiment issues
                if "extractor_args" not in options:
                    options["extractor_args"] = {
                        "youtube": {
                            "player_client": ["tv"],
                            "player_skip": ["webpage"],
                            "max_comments": [0],
                            "skip_webpage": [True],
                        }
                    }
                elif "youtube" not in options["extractor_args"]:
                    options["extractor_args"]["youtube"] = {
                        "player_client": ["tv"],
                        "player_skip": ["webpage"],
                        "max_comments": [0],
                        "skip_webpage": [True],
                    }

            result = await sync_to_async(extract_info, self.link, options)
        except Exception as e:
            msg = str(e).replace("<", " ").replace(">", " ")

            # Handle YouTube SSAP experiment issues
            if "youtube" in self.link.lower() and (
                "Unable to extract video data" in msg
                or "This video is unavailable" in msg
                or "Sign in to confirm" in msg
            ):
                try:
                    # Try with Android client
                    if (
                        "extractor_args" in options
                        and "youtube" in options["extractor_args"]
                    ):
                        options["extractor_args"]["youtube"]["player_client"] = [
                            "android"
                        ]

                    result = await sync_to_async(extract_info, self.link, options)
                except Exception:
                    try:
                        # Last resort: try with web client
                        if (
                            "extractor_args" in options
                            and "youtube" in options["extractor_args"]
                        ):
                            options["extractor_args"]["youtube"]["player_client"] = [
                                "web"
                            ]

                        result = await sync_to_async(
                            extract_info, self.link, options
                        )
                    except Exception:
                        # All clients failed, report the original error
                        msg = f"{msg}\n\nTried multiple YouTube clients but all failed. This might be due to the YouTube SSAP experiment or region restrictions."
                        try:
                            await self.on_download_error(msg)
                        except Exception as err:
                            LOGGER.error(f"Error in error handling: {err}")
                            await delete_links(self.message)
                            error_msg = await send_message(
                                self.message, f"{self.tag} {msg}"
                            )
                            create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                        finally:
                            await self.remove_from_same_dir()
                        return
            else:
                # Not a YouTube SSAP issue, handle normally
                try:
                    # Use self directly since YtDlp inherits from TaskListener
                    # Don't add tag here as it will be added in on_download_error
                    await self.on_download_error(msg)
                except Exception as err:
                    LOGGER.error(f"Error in error handling: {err}")
                    # Fallback error handling
                    await delete_links(self.message)
                    error_msg = await send_message(self.message, f"{self.tag} {msg}")
                    create_task(auto_delete_message(error_msg, time=300))  # noqa: RUF006
                finally:
                    await self.remove_from_same_dir()
                return
        finally:
            await self.run_multi(input_list, YtDlp)

        if not qual:
            qual = await YtSelection(self).get_quality(result)
            if qual is None:
                await self.remove_from_same_dir()
                return

        LOGGER.info(f"Downloading with YT-DLP: {self.link}")
        playlist = "entries" in result
        ydl = YoutubeDLHelper(self)
        create_task(ydl.add_download(path, qual, playlist, opt))  # noqa: RUF006
        await delete_links(self.message)
        return


async def ytdl(client, message):
    bot_loop.create_task(YtDlp(client, message).new_event())


async def ytdl_leech(client, message):
    bot_loop.create_task(YtDlp(client, message, is_leech=True).new_event())
