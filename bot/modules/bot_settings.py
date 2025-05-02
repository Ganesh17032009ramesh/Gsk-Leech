from asyncio import (
    create_subprocess_exec,
    create_subprocess_shell,
    create_task,
    gather,
    sleep,
)
from functools import partial
from io import BytesIO
from os import getcwd
from time import time

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from aiofiles.os import remove, rename
from aioshutil import rmtree
from pyrogram.filters import create
from pyrogram.handlers import MessageHandler

from bot import (
    LOGGER,
    aria2_options,
    auth_chats,
    drives_ids,
    drives_names,
    excluded_extensions,
    index_urls,
    intervals,
    jd_listener_lock,
    nzb_options,
    qbit_options,
    sabnzbd_client,
    sudo_users,
    task_dict,
)
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.core.jdownloader_booter import jdownloader
from bot.core.startup import (
    update_aria2_options,
    update_nzb_options,
    update_qb_options,
    update_variables,
)
from bot.core.torrent_manager import TorrentManager
from bot.helper.ext_utils.bot_utils import SetInterval, new_task
from bot.helper.ext_utils.db_handler import database
from bot.helper.ext_utils.task_manager import start_from_queued
from bot.helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_message,
    edit_message,
    send_file,
    send_message,
    update_status_message,
)

from .rss import add_job

start = 0
state = "view"
merge_page = 0  # Track current page for merge menu
handler_dict = {}
DEFAULT_VALUES = {
    # Set default leech split size to max split size based on owner session premium status
    "LEECH_SPLIT_SIZE": TgClient.MAX_SPLIT_SIZE
    if hasattr(Config, "USER_SESSION_STRING") and Config.USER_SESSION_STRING
    else 2097152000,
    "RSS_DELAY": 600,
    "UPSTREAM_BRANCH": "main",
    "DEFAULT_UPLOAD": "rc",
    "PIL_MEMORY_LIMIT": 2048,
    "AUTO_RESTART_ENABLED": False,
    "AUTO_RESTART_INTERVAL": 24,
    "EQUAL_SPLITS": False,
    "ENABLE_EXTRA_MODULES": True,
    "MEDIA_TOOLS_ENABLED": True,
    # Watermark Settings
    "WATERMARK_ENABLED": False,
    "WATERMARK_KEY": "",
    "WATERMARK_POSITION": "top_left",
    "WATERMARK_SIZE": 20,
    "WATERMARK_COLOR": "white",
    "WATERMARK_FONT": "default.otf",
    "WATERMARK_PRIORITY": 2,
    "WATERMARK_THREADING": True,
    "WATERMARK_THREAD_NUMBER": 4,
    "WATERMARK_FAST_MODE": True,
    "WATERMARK_MAINTAIN_QUALITY": True,
    "WATERMARK_OPACITY": 1.0,
    # Audio Watermark Settings
    "AUDIO_WATERMARK_ENABLED": False,
    "AUDIO_WATERMARK_TEXT": "",
    "AUDIO_WATERMARK_VOLUME": 0.3,
    # Subtitle Watermark Settings
    "SUBTITLE_WATERMARK_ENABLED": False,
    "SUBTITLE_WATERMARK_TEXT": "",
    "SUBTITLE_WATERMARK_STYLE": "normal",
    # Compression Settings
    "COMPRESSION_ENABLED": False,
    "COMPRESSION_PRIORITY": 4,
    # Video Compression Settings
    "COMPRESSION_VIDEO_ENABLED": False,
    "COMPRESSION_VIDEO_PRESET": "none",
    "COMPRESSION_VIDEO_CRF": 0,
    "COMPRESSION_VIDEO_CODEC": "none",
    "COMPRESSION_VIDEO_TUNE": "none",
    "COMPRESSION_VIDEO_PIXEL_FORMAT": "none",
    # Audio Compression Settings
    "COMPRESSION_AUDIO_ENABLED": False,
    "COMPRESSION_AUDIO_PRESET": "none",
    "COMPRESSION_AUDIO_CODEC": "none",
    "COMPRESSION_AUDIO_BITRATE": "none",
    "COMPRESSION_AUDIO_CHANNELS": 0,
    # Image Compression Settings
    "COMPRESSION_IMAGE_ENABLED": False,
    "COMPRESSION_IMAGE_PRESET": "none",
    "COMPRESSION_IMAGE_QUALITY": 0,
    "COMPRESSION_IMAGE_RESIZE": "none",
    # Document Compression Settings
    "COMPRESSION_DOCUMENT_ENABLED": False,
    "COMPRESSION_DOCUMENT_PRESET": "none",
    "COMPRESSION_DOCUMENT_DPI": 0,
    # Subtitle Compression Settings
    "COMPRESSION_SUBTITLE_ENABLED": False,
    "COMPRESSION_SUBTITLE_PRESET": "none",
    "COMPRESSION_SUBTITLE_ENCODING": "none",
    # Archive Compression Settings
    "COMPRESSION_ARCHIVE_ENABLED": False,
    "COMPRESSION_ARCHIVE_PRESET": "none",
    "COMPRESSION_ARCHIVE_LEVEL": 0,
    "COMPRESSION_ARCHIVE_METHOD": "none",
    # Trim Settings
    "TRIM_ENABLED": False,
    "TRIM_PRIORITY": 5,
    "TRIM_START_TIME": "00:00:00",
    "TRIM_END_TIME": "",
    "TRIM_DELETE_ORIGINAL": False,
    # Video Trim Settings
    "TRIM_VIDEO_ENABLED": False,
    "TRIM_VIDEO_CODEC": "none",
    "TRIM_VIDEO_PRESET": "none",
    "TRIM_VIDEO_FORMAT": "none",
    # Audio Trim Settings
    "TRIM_AUDIO_ENABLED": False,
    "TRIM_AUDIO_CODEC": "none",
    "TRIM_AUDIO_PRESET": "none",
    "TRIM_AUDIO_FORMAT": "none",
    # Image Trim Settings
    "TRIM_IMAGE_ENABLED": False,
    "TRIM_IMAGE_QUALITY": 90,
    "TRIM_IMAGE_FORMAT": "none",
    # Document Trim Settings
    "TRIM_DOCUMENT_ENABLED": False,
    "TRIM_DOCUMENT_QUALITY": 90,
    "TRIM_DOCUMENT_FORMAT": "none",
    # Subtitle Trim Settings
    "TRIM_SUBTITLE_ENABLED": False,
    "TRIM_SUBTITLE_ENCODING": "none",
    "TRIM_SUBTITLE_FORMAT": "none",
    # Archive Trim Settings
    "TRIM_ARCHIVE_ENABLED": False,
    "TRIM_ARCHIVE_FORMAT": "none",
    # Extract Settings
    "EXTRACT_ENABLED": False,
    "EXTRACT_PRIORITY": 6,
    "EXTRACT_DELETE_ORIGINAL": True,
    # Video Extract Settings
    "EXTRACT_VIDEO_ENABLED": False,
    "EXTRACT_VIDEO_CODEC": "none",
    "EXTRACT_VIDEO_FORMAT": "none",
    "EXTRACT_VIDEO_INDEX": None,
    "EXTRACT_VIDEO_QUALITY": "none",
    "EXTRACT_VIDEO_PRESET": "none",
    "EXTRACT_VIDEO_BITRATE": "none",
    "EXTRACT_VIDEO_RESOLUTION": "none",
    "EXTRACT_VIDEO_FPS": "none",
    # Audio Extract Settings
    "EXTRACT_AUDIO_ENABLED": False,
    "EXTRACT_AUDIO_CODEC": "none",
    "EXTRACT_AUDIO_FORMAT": "none",
    "EXTRACT_AUDIO_INDEX": None,
    "EXTRACT_AUDIO_BITRATE": "none",
    "EXTRACT_AUDIO_CHANNELS": "none",
    "EXTRACT_AUDIO_SAMPLING": "none",
    "EXTRACT_AUDIO_VOLUME": "none",
    # Subtitle Extract Settings
    "EXTRACT_SUBTITLE_ENABLED": False,
    "EXTRACT_SUBTITLE_CODEC": "none",
    "EXTRACT_SUBTITLE_FORMAT": "none",
    "EXTRACT_SUBTITLE_INDEX": None,
    "EXTRACT_SUBTITLE_LANGUAGE": "none",
    "EXTRACT_SUBTITLE_ENCODING": "none",
    "EXTRACT_SUBTITLE_FONT": "none",
    "EXTRACT_SUBTITLE_FONT_SIZE": "none",
    # Attachment Extract Settings
    "EXTRACT_ATTACHMENT_ENABLED": False,
    "EXTRACT_ATTACHMENT_FORMAT": "none",
    "EXTRACT_ATTACHMENT_INDEX": None,
    "EXTRACT_ATTACHMENT_FILTER": "none",
    "EXTRACT_MAINTAIN_QUALITY": True,
    # Convert Settings
    "CONVERT_ENABLED": False,
    "CONVERT_PRIORITY": 3,
    "CONVERT_DELETE_ORIGINAL": False,
    # Video Convert Settings
    "CONVERT_VIDEO_ENABLED": False,
    "CONVERT_VIDEO_FORMAT": "none",
    "CONVERT_VIDEO_CODEC": "none",
    "CONVERT_VIDEO_QUALITY": "none",
    "CONVERT_VIDEO_CRF": 0,
    "CONVERT_VIDEO_PRESET": "none",
    "CONVERT_VIDEO_MAINTAIN_QUALITY": True,
    "CONVERT_VIDEO_RESOLUTION": "none",
    "CONVERT_VIDEO_FPS": "none",
    # Audio Convert Settings
    "CONVERT_AUDIO_ENABLED": False,
    "CONVERT_AUDIO_FORMAT": "none",
    "CONVERT_AUDIO_CODEC": "none",
    "CONVERT_AUDIO_BITRATE": "none",
    "CONVERT_AUDIO_CHANNELS": 0,
    "CONVERT_AUDIO_SAMPLING": 0,
    "CONVERT_AUDIO_VOLUME": 0.0,
    # Subtitle Convert Settings
    "CONVERT_SUBTITLE_ENABLED": False,
    "CONVERT_SUBTITLE_FORMAT": "none",
    "CONVERT_SUBTITLE_ENCODING": "none",
    "CONVERT_SUBTITLE_LANGUAGE": "none",
    # Document Convert Settings
    "CONVERT_DOCUMENT_ENABLED": False,
    "CONVERT_DOCUMENT_FORMAT": "none",
    "CONVERT_DOCUMENT_QUALITY": 0,
    "CONVERT_DOCUMENT_DPI": 0,
    # Archive Convert Settings
    "CONVERT_ARCHIVE_ENABLED": False,
    "CONVERT_ARCHIVE_FORMAT": "none",
    "CONVERT_ARCHIVE_LEVEL": 0,
    "CONVERT_ARCHIVE_METHOD": "none",
    # Media Tools Settings
    "MEDIAINFO_ENABLED": False,
    # Task Monitoring Settings
    "TASK_MONITOR_ENABLED": True,
    "TASK_MONITOR_INTERVAL": 60,
    "TASK_MONITOR_CONSECUTIVE_CHECKS": 3,
    "TASK_MONITOR_SPEED_THRESHOLD": 50,
    "TASK_MONITOR_ELAPSED_THRESHOLD": 3600,
    "TASK_MONITOR_ETA_THRESHOLD": 86400,
    "TASK_MONITOR_WAIT_TIME": 600,
    "TASK_MONITOR_COMPLETION_THRESHOLD": 14400,
    "TASK_MONITOR_CPU_HIGH": 90,
    "TASK_MONITOR_CPU_LOW": 40,
    "TASK_MONITOR_MEMORY_HIGH": 75,
    "TASK_MONITOR_MEMORY_LOW": 60,
}


async def get_buttons(key=None, edit_type=None, page=0, user_id=None):
    buttons = ButtonMaker()
    msg = ""  # Initialize msg with a default value
    if key is None:
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        buttons.data_button("Config", "botset var")
        buttons.data_button("Pvt Files", "botset private")

        # Only show Media Tools button if media tools are enabled
        if is_media_tool_enabled("mediatools"):
            buttons.data_button("Media Tools", "botset mediatools")

        # Only show AI Settings button if Extra Modules are enabled
        if Config.ENABLE_EXTRA_MODULES:
            buttons.data_button("AI Settings", "botset ai")

        buttons.data_button("Task Monitor", "botset taskmonitor")
        buttons.data_button("Qbit Settings", "botset qbit")
        buttons.data_button("Aria2c Settings", "botset aria")
        buttons.data_button("Sabnzbd", "botset nzb")
        buttons.data_button("JD Sync", "botset syncjd")
        buttons.data_button("Close", "botset close")
        msg = "Bot Settings:"
    elif edit_type is not None:
        if edit_type == "editvar" and (
            key.startswith(
                (
                    "WATERMARK_",
                    "AUDIO_WATERMARK_",
                    "SUBTITLE_WATERMARK_",
                    "MERGE_",
                    "METADATA_",
                    "TASK_MONITOR_",
                )
            )
            or key in ["CONCAT_DEMUXER_ENABLED", "FILTER_COMPLEX_ENABLED"]
        ):
            msg = ""
            if key.startswith(
                ("WATERMARK_", "AUDIO_WATERMARK_", "SUBTITLE_WATERMARK_")
            ):
                buttons.data_button("Back", "botset mediatools_watermark")
            elif key.startswith("METADATA_"):
                buttons.data_button("Back", "botset mediatools_metadata")
            elif key.startswith("TRIM_"):
                buttons.data_button("Back", "botset mediatools_trim")
            elif key.startswith("COMPRESSION_"):
                buttons.data_button("Back", "botset mediatools_compression")
            elif key.startswith("CONVERT_"):
                buttons.data_button("Back", "botset mediatools_convert")
            elif key.startswith("TASK_MONITOR_"):
                buttons.data_button("Back", "botset taskmonitor")
            elif key.startswith("MISTRAL_"):
                buttons.data_button("Back", "botset ai")
            elif key.startswith("MERGE_") and "MERGE_OUTPUT_FORMAT" in key:
                # If it's a format setting, it's likely from the merge_config menu
                buttons.data_button("Back", "botset mediatools_merge_config")
            else:
                buttons.data_button("Back", "botset mediatools_merge")
            buttons.data_button("Close", "botset close")

            # Get help text for settings
            if key in {
                "WATERMARK_ENABLED",
                "WATERMARK_FAST_MODE",
                "WATERMARK_MAINTAIN_QUALITY",
                "WATERMARK_THREADING",
                "AUDIO_WATERMARK_ENABLED",
                "SUBTITLE_WATERMARK_ENABLED",
                "MERGE_ENABLED",
                "CONCAT_DEMUXER_ENABLED",
                "FILTER_COMPLEX_ENABLED",
                "MERGE_THREADING",
                "MERGE_REMOVE_ORIGINAL",
                "MERGE_VIDEO_FASTSTART",
                "CONVERT_ENABLED",
                "CONVERT_VIDEO_ENABLED",
                "CONVERT_AUDIO_ENABLED",
                "CONVERT_SUBTITLE_ENABLED",
                "CONVERT_DOCUMENT_ENABLED",
                "CONVERT_ARCHIVE_ENABLED",
                "CONVERT_VIDEO_MAINTAIN_QUALITY",
                "CONVERT_DELETE_ORIGINAL",
                "COMPRESSION_ENABLED",
                "COMPRESSION_VIDEO_ENABLED",
                "COMPRESSION_AUDIO_ENABLED",
                "COMPRESSION_IMAGE_ENABLED",
                "COMPRESSION_DOCUMENT_ENABLED",
                "COMPRESSION_SUBTITLE_ENABLED",
                "COMPRESSION_ARCHIVE_ENABLED",
                "TASK_MONITOR_ENABLED",
            }:
                help_text = (
                    "Send 'true' to enable or 'false' to disable this feature."
                )
            elif key == "WATERMARK_KEY":
                help_text = "Send your text which will be added as watermark in all media files."
            elif key == "AUDIO_WATERMARK_TEXT":
                help_text = "Send your text which will be used for audio watermarks. If empty, the visual watermark text will be used."
            elif key == "SUBTITLE_WATERMARK_TEXT":
                help_text = "Send your text which will be used for subtitle watermarks. If empty, the visual watermark text will be used."
            elif key == "WATERMARK_POSITION":
                help_text = "Send watermark position. Valid options: top_left, top_right, bottom_left, bottom_right, center."
            elif key in {
                "WATERMARK_SIZE",
                "WATERMARK_THREAD_NUMBER",
                "MERGE_THREAD_NUMBER",
                "MERGE_PRIORITY",
                "MERGE_VIDEO_CRF",
                "MERGE_IMAGE_COLUMNS",
                "MERGE_IMAGE_QUALITY",
                "MERGE_IMAGE_DPI",
                "MERGE_SUBTITLE_FONT_SIZE",
                "MERGE_DOCUMENT_MARGIN",
                "MERGE_AUDIO_CHANNELS",
                "CONVERT_PRIORITY",
                "CONVERT_VIDEO_CRF",
                "CONVERT_AUDIO_CHANNELS",
                "CONVERT_AUDIO_SAMPLING",
                "CONVERT_DOCUMENT_QUALITY",
                "CONVERT_DOCUMENT_DPI",
                "CONVERT_ARCHIVE_LEVEL",
                "COMPRESSION_PRIORITY",
                "COMPRESSION_VIDEO_CRF",
                "COMPRESSION_AUDIO_CHANNELS",
                "COMPRESSION_IMAGE_QUALITY",
                "COMPRESSION_DOCUMENT_DPI",
                "COMPRESSION_ARCHIVE_LEVEL",
            }:
                help_text = "Send an integer value. Example: 4."
            elif key in {
                "WATERMARK_COLOR",
                "MERGE_VIDEO_PIXEL_FORMAT",
                "MERGE_VIDEO_TUNE",
                "MERGE_IMAGE_BACKGROUND",
                "MERGE_SUBTITLE_FONT_COLOR",
                "MERGE_SUBTITLE_BACKGROUND",
            }:
                help_text = "Send a color name. Example: white, black, red, green, blue, yellow."
            elif key == "COMPRESSION_VIDEO_PIXEL_FORMAT":
                help_text = (
                    "Send a pixel format. Example: yuv420p, yuv444p, rgb24, etc."
                )
            elif key == "COMPRESSION_VIDEO_TUNE":
                help_text = "Send a tune option. Example: film, animation, grain, stillimage, fastdecode, zerolatency, etc."
            elif key in {"COMPRESSION_ARCHIVE_METHOD", "CONVERT_ARCHIVE_METHOD"}:
                help_text = "Send a compression method. Example: deflate, store, bzip2, lzma, etc."
            elif key == "CONVERT_ARCHIVE_LEVEL":
                help_text = "Send the compression level (0-9). Higher values mean better compression but slower speed. Example: 6, 9, etc."
            elif key in {"WATERMARK_FONT", "MERGE_SUBTITLE_FONT"}:
                help_text = "Send font file name. The font file should be available in the bot's directory. Example: Arial.ttf."
            elif key in {
                "MERGE_OUTPUT_FORMAT_VIDEO",
                "CONVERT_VIDEO_FORMAT",
                "EXTRACT_VIDEO_FORMAT",
            }:
                help_text = "Send video output format. Example: mp4, mkv, avi, etc."
            elif key in {
                "MERGE_OUTPUT_FORMAT_AUDIO",
                "CONVERT_AUDIO_FORMAT",
                "EXTRACT_AUDIO_FORMAT",
            }:
                help_text = "Send audio output format. Example: mp3, aac, flac, etc."
            elif key in {"EXTRACT_SUBTITLE_FORMAT", "CONVERT_SUBTITLE_FORMAT"}:
                help_text = (
                    "Send subtitle output format. Example: srt, ass, vtt, etc."
                )
            elif key == "CONVERT_DOCUMENT_FORMAT":
                help_text = (
                    "Send document output format. Example: pdf, docx, txt, etc."
                )
            elif key == "CONVERT_ARCHIVE_FORMAT":
                help_text = (
                    "Send archive output format. Example: zip, rar, 7z, tar, etc."
                )
            elif key == "EXTRACT_ATTACHMENT_FORMAT":
                help_text = (
                    "Send attachment output format. Example: png, jpg, pdf, etc."
                )
            elif key == "EXTRACT_PRIORITY":
                help_text = "Send an integer value for extract priority. Lower values mean higher priority. Example: 6."
            elif key in {"EXTRACT_DELETE_ORIGINAL", "CONVERT_DELETE_ORIGINAL"}:
                help_text = "Send 'true' to delete original files after processing or 'false' to keep them."
            elif key == "EXTRACT_VIDEO_INDEX":
                help_text = "Send the video track index to extract. Use comma-separated values for multiple tracks (e.g., '0,1,2') or 'all' for all tracks."
            elif key == "EXTRACT_AUDIO_INDEX":
                help_text = "Send the audio track index to extract. Use comma-separated values for multiple tracks (e.g., '0,1,2') or 'all' for all tracks."
            elif key == "EXTRACT_SUBTITLE_INDEX":
                help_text = "Send the subtitle track index to extract. Use comma-separated values for multiple tracks (e.g., '0,1,2') or 'all' for all tracks."
            elif key == "EXTRACT_ATTACHMENT_INDEX":
                help_text = "Send the attachment index to extract. Use comma-separated values for multiple indices (e.g., '0,1,2') or 'all' for all attachments."
            elif key == "EXTRACT_VIDEO_CODEC":
                help_text = "Send the video codec to use for extraction. Example: copy, h264, libx264, etc."
            elif key == "EXTRACT_AUDIO_CODEC":
                help_text = "Send the audio codec to use for extraction. Example: copy, aac, mp3, etc."
            elif key == "EXTRACT_SUBTITLE_CODEC":
                help_text = "Send the subtitle codec to use for extraction. Example: copy, srt, ass, etc."
            elif key == "EXTRACT_VIDEO_QUALITY":
                help_text = "Send the video quality setting for extraction. Example: high, medium, low, etc."
            elif key == "EXTRACT_VIDEO_PRESET":
                help_text = "Send the video preset for extraction. Example: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow."
            elif key == "EXTRACT_VIDEO_BITRATE":
                help_text = (
                    "Send the video bitrate for extraction. Example: 5M, 10M, etc."
                )
            elif key in {"EXTRACT_VIDEO_RESOLUTION", "CONVERT_VIDEO_RESOLUTION"}:
                help_text = "Send the video resolution for processing. Example: 1920x1080, 1280x720, etc."
            elif key in {"EXTRACT_VIDEO_FPS", "CONVERT_VIDEO_FPS"}:
                help_text = (
                    "Send the video frame rate for processing. Example: 30, 60, etc."
                )
            elif key == "CONVERT_DOCUMENT_QUALITY":
                help_text = "Send the document quality for conversion (1-100). Higher values mean better quality. Example: 90, 75, etc."
            elif key in {"COMPRESSION_DOCUMENT_DPI", "CONVERT_DOCUMENT_DPI"}:
                help_text = "Send the document DPI (dots per inch) for processing. Higher values mean better quality. Example: 300, 600, etc."
            elif key == "EXTRACT_AUDIO_BITRATE":
                help_text = "Send the audio bitrate for extraction. Example: 128k, 192k, 320k, etc."
            elif key == "EXTRACT_AUDIO_CHANNELS":
                help_text = "Send the number of audio channels for extraction. Example: 2, 6, etc."
            elif key == "EXTRACT_AUDIO_SAMPLING":
                help_text = "Send the audio sampling rate for extraction. Example: 44100, 48000, etc."
            elif key == "EXTRACT_AUDIO_VOLUME":
                help_text = "Send the audio volume adjustment for extraction. Example: 1.0, 1.5, 0.5, etc."
            elif key == "EXTRACT_SUBTITLE_LANGUAGE":
                help_text = "Send the subtitle language code for extraction. Example: eng, spa, fre, etc."
            elif key == "EXTRACT_SUBTITLE_ENCODING":
                help_text = "Send the subtitle character encoding for extraction. Example: utf-8, ascii, etc."
            elif key == "EXTRACT_SUBTITLE_FONT":
                help_text = "Send the subtitle font for extraction (for formats that support it). Example: Arial, Times New Roman, etc."
            elif key == "EXTRACT_SUBTITLE_FONT_SIZE":
                help_text = "Send the subtitle font size for extraction. Example: 24, 32, etc."
            elif key == "EXTRACT_ATTACHMENT_FILTER":
                help_text = "Send a filter pattern for attachment extraction. Example: *.jpg, *.pdf, etc."
            elif key == "EXTRACT_MAINTAIN_QUALITY":
                help_text = "Send 'true' to maintain high quality during extraction or 'false' to optimize for size."
            elif key == "MERGE_OUTPUT_FORMAT_IMAGE":
                help_text = "Send image output format. Example: jpg, png, webp, etc."
            elif key == "MERGE_OUTPUT_FORMAT_DOCUMENT":
                help_text = "Send document output format. Example: pdf, docx, etc."
            elif key == "MERGE_OUTPUT_FORMAT_SUBTITLE":
                help_text = "Send subtitle output format. Example: srt, ass, etc."
            elif key in {
                "MERGE_VIDEO_CODEC",
                "CONVERT_VIDEO_CODEC",
                "COMPRESSION_VIDEO_CODEC",
            }:
                help_text = "Send video codec. Example: h264, h265, libx264, libx265, copy, etc."
            elif key in {"MERGE_VIDEO_QUALITY", "CONVERT_VIDEO_QUALITY"}:
                help_text = "Send video quality. Example: high, medium, low, etc."
            elif key in {
                "MERGE_VIDEO_PRESET",
                "CONVERT_VIDEO_PRESET",
                "COMPRESSION_VIDEO_PRESET",
                "COMPRESSION_AUDIO_PRESET",
                "COMPRESSION_IMAGE_PRESET",
                "COMPRESSION_DOCUMENT_PRESET",
                "COMPRESSION_SUBTITLE_PRESET",
                "COMPRESSION_ARCHIVE_PRESET",
            }:
                help_text = "Send preset. Example: fast, medium, slow. For video: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow, etc."
            elif key in {
                "MERGE_AUDIO_CODEC",
                "CONVERT_AUDIO_CODEC",
                "COMPRESSION_AUDIO_CODEC",
            }:
                help_text = "Send audio codec. Example: aac, mp3, libmp3lame, libvorbis, copy, etc."
            elif key in {
                "MERGE_AUDIO_BITRATE",
                "CONVERT_AUDIO_BITRATE",
                "COMPRESSION_AUDIO_BITRATE",
            }:
                help_text = "Send audio bitrate. Example: 128k, 192k, 320k, etc."
            elif key in {"MERGE_AUDIO_SAMPLING", "CONVERT_AUDIO_SAMPLING"}:
                help_text = "Send audio sampling rate. Example: 44100, 48000, etc."
            elif key == "WATERMARK_OPACITY":
                help_text = "Send opacity value between 0.0 and 1.0. Lower values make the watermark more transparent. Example: 0.5 for 50% opacity."
            elif key == "AUDIO_WATERMARK_VOLUME":
                help_text = "Send volume value between 0.0 and 1.0. Higher values make the audio watermark louder. Example: 0.3 for 30% volume."
            elif key == "SUBTITLE_WATERMARK_STYLE":
                help_text = "Send subtitle style. Valid options: normal, bold, italic, underline. Example: bold."
            elif key in {"MERGE_AUDIO_VOLUME", "CONVERT_AUDIO_VOLUME"}:
                help_text = (
                    "Send audio volume multiplier. Example: 1.0, 1.5, 0.5, etc."
                )
            elif key == "MERGE_IMAGE_MODE":
                help_text = "Send image mode. Example: auto, grid, horizontal, vertical, etc."
            elif key in {"MERGE_IMAGE_RESIZE", "COMPRESSION_IMAGE_RESIZE"}:
                help_text = (
                    "Send image resize option. Example: none, 1080p, 720p, etc."
                )
            elif key in {
                "MERGE_SUBTITLE_ENCODING",
                "COMPRESSION_SUBTITLE_ENCODING",
                "CONVERT_SUBTITLE_ENCODING",
            }:
                help_text = "Send subtitle encoding. Example: utf-8, ascii, etc."
            elif key == "CONVERT_SUBTITLE_LANGUAGE":
                help_text = (
                    "Send subtitle language code. Example: eng, spa, fre, etc."
                )
            elif key == "MERGE_DOCUMENT_PAPER_SIZE":
                help_text = "Send document paper size. Example: a4, letter, etc."
            elif key == "MERGE_DOCUMENT_ORIENTATION":
                help_text = (
                    "Send document orientation. Example: portrait, landscape, etc."
                )
            elif key in {
                "MERGE_METADATA_TITLE",
                "MERGE_METADATA_AUTHOR",
                "MERGE_METADATA_COMMENT",
                "METADATA_TITLE",
                "METADATA_AUTHOR",
                "METADATA_COMMENT",
            }:
                help_text = "Send metadata text. Example: My Video, John Doe, etc."
            elif key == "METADATA_KEY":
                help_text = "Send legacy metadata key for backward compatibility."
            elif key == "METADATA_ALL":
                help_text = "Send metadata text to apply to all metadata fields."
            elif key == "TASK_MONITOR_INTERVAL":
                help_text = "Send the interval in seconds between task monitoring checks. Default: 60"
            elif key == "TASK_MONITOR_CONSECUTIVE_CHECKS":
                help_text = "Send the number of consecutive checks required to confirm an issue. Default: 3"
            elif key == "TASK_MONITOR_SPEED_THRESHOLD":
                help_text = "Send the download speed threshold in KB/s. Downloads below this speed are considered slow. Default: 50"
            elif key == "TASK_MONITOR_ELAPSED_THRESHOLD":
                help_text = "Send the elapsed time threshold in seconds. Default: 3600 (1 hour)"
            elif key == "TASK_MONITOR_ETA_THRESHOLD":
                help_text = (
                    "Send the ETA threshold in seconds. Default: 86400 (24 hours)"
                )
            elif key == "TASK_MONITOR_WAIT_TIME":
                help_text = "Send the wait time in seconds before cancelling a task after warning. Default: 600 (10 minutes)"
            elif key == "TASK_MONITOR_COMPLETION_THRESHOLD":
                help_text = "Send the completion time threshold in seconds. Default: 14400 (4 hours)"
            elif key == "TASK_MONITOR_CPU_HIGH":
                help_text = "Send the high CPU threshold percentage. Default: 90"
            elif key == "TASK_MONITOR_CPU_LOW":
                help_text = "Send the low CPU threshold percentage. Default: 40"
            elif key == "TASK_MONITOR_MEMORY_HIGH":
                help_text = "Send the high memory threshold percentage. Default: 75"
            elif key == "TASK_MONITOR_MEMORY_LOW":
                help_text = "Send the low memory threshold percentage. Default: 60"
            elif key == "TRIM_START_TIME":
                help_text = "Send the start time for trimming in HH:MM:SS format. Default: 00:00:00 (beginning of file)"
            elif key == "TRIM_END_TIME":
                help_text = "Send the end time for trimming in HH:MM:SS format. Leave empty for end of file. Default: (empty)"
            else:
                help_text = f"Send a valid value for {key}."

            msg += f"{help_text}\n\nCurrent value is '{Config.get(key)}'. Timeout: 60 sec"
        elif edit_type == "botvar":
            msg = ""
            buttons.data_button("Back", "botset var")
            if key not in ["TELEGRAM_HASH", "TELEGRAM_API", "OWNER_ID", "BOT_TOKEN"]:
                buttons.data_button("Default", f"botset resetvar {key}")
            buttons.data_button("Close", "botset close")
            if key in [
                "CMD_SUFFIX",
                "OWNER_ID",
                "USER_SESSION_STRING",
                "TELEGRAM_HASH",
                "TELEGRAM_API",
                "BOT_TOKEN",
                "TG_PROXY",
            ]:
                msg += "Restart required for this edit to take effect! You will not see the changes in bot vars, the edit will be in database only!\n\n"

            # Add help text for resource management settings
            if key == "PIL_MEMORY_LIMIT":
                msg += "Set the memory limit for PIL operations in MB. Use 0 for no limit.\n\n"
                msg += "Example: 2048 (for 2GB limit)\n\n"
            elif key == "AUTO_RESTART_ENABLED":
                msg += "Enable or disable automatic bot restart at specified intervals.\n\n"
                msg += "Send 'true' to enable or 'false' to disable.\n\n"
                msg += "Note: Changes will take effect after saving.\n\n"
            elif key == "AUTO_RESTART_INTERVAL":
                msg += (
                    "Set the interval in hours between automatic bot restarts.\n\n"
                )
                msg += "Example: 24 (for daily restart)\n\n"
                msg += "Minimum value is 1 hour.\n\n"
            elif key == "TRUECALLER_API_URL":
                msg += "Set the API URL for Truecaller phone number lookup.\n\n"
                msg += "No default URL is provided. You must set your own API endpoint.\n\n"
                msg += "The Truecaller module will not work until this is configured.\n\n"

            msg += f"Send a valid value for {key}. Current value is '{Config.get(key)}'. Timeout: 60 sec"
        elif edit_type == "ariavar":
            buttons.data_button("Back", "botset aria")
            if key != "newkey":
                buttons.data_button("Empty String", f"botset emptyaria {key}")
            buttons.data_button("Close", "botset close")
            msg = (
                "Send a key with value. Example: https-proxy-user:value. Timeout: 60 sec"
                if key == "newkey"
                else f"Send a valid value for {key}. Current value is '{aria2_options[key]}'. Timeout: 60 sec"
            )
        elif edit_type == "qbitvar":
            buttons.data_button("Back", "botset qbit")
            buttons.data_button("Empty", f"botset emptyqbit {key}")
            buttons.data_button("Close", "botset close")
            msg = f"Send a valid value for {key}. Current value is '{qbit_options[key]}'. Timeout: 60 sec"
        elif edit_type == "nzbvar":
            buttons.data_button("Back", "botset nzb")
            buttons.data_button("Default", f"botset resetnzb {key}")
            buttons.data_button("Empty String", f"botset emptynzb {key}")
            buttons.data_button("Close", "botset close")
            msg = f"Send a valid value for {key}. Current value is '{nzb_options[key]}'.\nIf the value is list then separate them by space or ,\nExample: .exe,info or .exe .info\nTimeout: 60 sec"
        elif edit_type.startswith("nzbsevar"):
            index = 0 if key == "newser" else int(edit_type.replace("nzbsevar", ""))
            buttons.data_button("Back", f"botset nzbser{index}")
            if key != "newser":
                buttons.data_button("Empty", f"botset emptyserkey {index} {key}")
            buttons.data_button("Close", "botset close")
            if key == "newser":
                msg = "Send one server as dictionary {}, like in config.py without []. Timeout: 60 sec"
            else:
                msg = f"Send a valid value for {key} in server {Config.USENET_SERVERS[index]['name']}. Current value is {Config.USENET_SERVERS[index][key]}. Timeout: 60 sec"
    elif key == "var":
        conf_dict = Config.get_all()
        # Filter out watermark, merge configs, metadata, convert, task monitor, and AI settings
        filtered_keys = [
            k
            for k in list(conf_dict.keys())
            if not (
                k.startswith(
                    (
                        "WATERMARK_",
                        "AUDIO_WATERMARK_",
                        "SUBTITLE_WATERMARK_",
                        "MERGE_",
                        "METADATA_",
                        "CONVERT_",
                        "COMPRESSION_",
                        "TRIM_",
                        "EXTRACT_",
                        "TASK_MONITOR_",
                        "MISTRAL_",
                        "DEEPSEEK_",
                        "CHATGPT_",
                        "GEMINI_",
                    )
                )
                or k
                in [
                    "CONCAT_DEMUXER_ENABLED",
                    "FILTER_COMPLEX_ENABLED",
                    "DEFAULT_AI_PROVIDER",
                ]
            )
        ]

        # Add resource management settings to the config menu
        resource_keys = [
            "PIL_MEMORY_LIMIT",
            "AUTO_RESTART_ENABLED",
            "AUTO_RESTART_INTERVAL",
        ]

        # Add API settings to the config menu
        api_keys = [
            "TRUECALLER_API_URL",
        ]

        # Add module control settings to the config menu
        module_keys = [
            "ENABLE_EXTRA_MODULES",
            "MEDIA_TOOLS_ENABLED",
        ]

        # Add descriptions for module settings
        module_descriptions = {
            "ENABLE_EXTRA_MODULES": "Enable Extra Modules (AI, Truecaller, IMDB)",
            "MEDIA_TOOLS_ENABLED": "Enable Media Tools",
        }

        # Ensure resource keys are in the filtered keys list
        for rk in resource_keys:
            if rk not in filtered_keys:
                filtered_keys.append(rk)

        # Ensure API keys are in the filtered keys list
        for ak in api_keys:
            if ak not in filtered_keys:
                filtered_keys.append(ak)

        # Ensure module keys are in the filtered keys list
        for mk in module_keys:
            if mk not in filtered_keys:
                filtered_keys.append(mk)

        # Sort the keys alphabetically
        filtered_keys.sort()

        for k in filtered_keys[start : 10 + start]:
            if k == "DATABASE_URL" and state != "view":
                continue
            # Highlight resource management settings
            if k in resource_keys:
                buttons.data_button(f"⚙️ {k}", f"botset botvar {k}")
            # Highlight API settings
            elif k in api_keys:
                buttons.data_button(f"🔌 {k}", f"botset botvar {k}")
            # Highlight module control settings
            elif k in module_keys:
                # Use the module descriptions for better display
                description = module_descriptions.get(k, k)
                value = Config.get(k)

                # For MEDIA_TOOLS_ENABLED, handle special case for comma-separated values
                if k == "MEDIA_TOOLS_ENABLED":
                    if isinstance(value, str) and "," in value:
                        # Show the number of enabled tools
                        enabled_tools = [
                            t.strip() for t in value.split(",") if t.strip()
                        ]
                        # Get the list of all available tools
                        all_tools = [
                            "watermark",
                            "merge",
                            "convert",
                            "compression",
                            "trim",
                            "extract",
                            "metadata",
                            "ffmpeg",
                            "sample",
                        ]
                        status = (
                            f"✅ ({len(enabled_tools)}/{len(all_tools)})"
                            if enabled_tools
                            else "❌"
                        )
                    else:
                        status = "✅" if value else "❌"
                    buttons.data_button(
                        f"🧩 {description}: {status}", f"botset botvar {k}"
                    )
                # For ENABLE_EXTRA_MODULES, show status
                elif k == "ENABLE_EXTRA_MODULES":
                    if isinstance(value, str) and "," in value:
                        # Show the number of disabled modules
                        disabled_modules = [
                            t.strip() for t in value.split(",") if t.strip()
                        ]
                        status = (
                            f"✅ ({len(disabled_modules)} disabled)"
                            if disabled_modules
                            else "✅"
                        )
                    else:
                        status = "✅" if value else "❌"
                    buttons.data_button(
                        f"🧩 {description}: {status}", f"botset botvar {k}"
                    )
                else:
                    buttons.data_button(f"🧩 {k}", f"botset botvar {k}")
            else:
                buttons.data_button(k, f"botset botvar {k}")
        if state == "view":
            buttons.data_button("Edit", "botset edit var")
        else:
            buttons.data_button("View", "botset view var")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(filtered_keys), 10):
            buttons.data_button(
                f"{int(x / 10)}",
                f"botset start var {x}",
                position="footer",
            )

        msg = f"Config Variables | Page: {int(start / 10)} | State: {state}"
    elif key == "private":
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        msg = """Send private file: config.py, token.pickle, rclone.conf, accounts.zip, list_drives.txt, cookies.txt, .netrc or any other private file!
To delete private file send only the file name as text message.
Note: Changing .netrc will not take effect for aria2c until restart.
Timeout: 60 sec"""
    elif key == "aria":
        for k in list(aria2_options.keys())[start : 10 + start]:
            buttons.data_button(k, f"botset ariavar {k}")
        if state == "view":
            buttons.data_button("Edit", "botset edit aria")
        else:
            buttons.data_button("View", "botset view aria")
        buttons.data_button("Add Option", "botset ariavar newkey")
        buttons.data_button("Sync Aria2c", "botset syncaria")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(aria2_options), 10):
            buttons.data_button(
                f"{int(x / 10)}",
                f"botset start aria {x}",
                position="footer",
            )
        msg = f"Aria2c Options | Page: {int(start / 10)} | State: {state}"
    elif key == "qbit":
        for k in list(qbit_options.keys())[start : 10 + start]:
            buttons.data_button(k, f"botset qbitvar {k}")
        if state == "view":
            buttons.data_button("Edit", "botset edit qbit")
        else:
            buttons.data_button("View", "botset view qbit")
        buttons.data_button("Sync Qbittorrent", "botset syncqbit")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(qbit_options), 10):
            buttons.data_button(
                f"{int(x / 10)}",
                f"botset start qbit {x}",
                position="footer",
            )
        msg = f"Qbittorrent Options | Page: {int(start / 10)} | State: {state}"
    elif key == "nzb":
        for k in list(nzb_options.keys())[start : 10 + start]:
            buttons.data_button(k, f"botset nzbvar {k}")
        if state == "view":
            buttons.data_button("Edit", "botset edit nzb")
        else:
            buttons.data_button("View", "botset view nzb")
        buttons.data_button("Servers", "botset nzbserver")
        buttons.data_button("Sync Sabnzbd", "botset syncnzb")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(nzb_options), 10):
            buttons.data_button(
                f"{int(x / 10)}",
                f"botset start nzb {x}",
                position="footer",
            )
        msg = f"Sabnzbd Options | Page: {int(start / 10)} | State: {state}"

    elif key == "nzbserver":
        if len(Config.USENET_SERVERS) > 0:
            for index, k in enumerate(Config.USENET_SERVERS[start : 10 + start]):
                buttons.data_button(k["name"], f"botset nzbser{index}")
        buttons.data_button("Add New", "botset nzbsevar newser")
        buttons.data_button("Back", "botset nzb")
        buttons.data_button("Close", "botset close")
        if len(Config.USENET_SERVERS) > 10:
            for x in range(0, len(Config.USENET_SERVERS), 10):
                buttons.data_button(
                    f"{int(x / 10)}",
                    f"botset start nzbser {x}",
                    position="footer",
                )
        msg = f"Usenet Servers | Page: {int(start / 10)} | State: {state}"
    elif key.startswith("nzbser"):
        index = int(key.replace("nzbser", ""))
        for k in list(Config.USENET_SERVERS[index].keys())[start : 10 + start]:
            buttons.data_button(k, f"botset nzbsevar{index} {k}")
        if state == "view":
            buttons.data_button("Edit", f"botset edit {key}")
        else:
            buttons.data_button("View", f"botset view {key}")
        buttons.data_button("Remove Server", f"botset remser {index}")
        buttons.data_button("Back", "botset nzbserver")
        buttons.data_button("Close", "botset close")
        if len(Config.USENET_SERVERS[index].keys()) > 10:
            for x in range(0, len(Config.USENET_SERVERS[index]), 10):
                buttons.data_button(
                    f"{int(x / 10)}",
                    f"botset start {key} {x}",
                    position="footer",
                )
        msg = f"Server Keys | Page: {int(start / 10)} | State: {state}"
    elif key == "mediatools":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        # Only show enabled tools
        if is_media_tool_enabled("watermark"):
            buttons.data_button("Watermark Settings", "botset mediatools_watermark")

        if is_media_tool_enabled("merge"):
            buttons.data_button("Merge Settings", "botset mediatools_merge")

        if is_media_tool_enabled("convert"):
            buttons.data_button("Convert Settings", "botset mediatools_convert")

        if is_media_tool_enabled("compression"):
            buttons.data_button(
                "Compression Settings", "botset mediatools_compression"
            )

        if is_media_tool_enabled("trim"):
            buttons.data_button("Trim Settings", "botset mediatools_trim")

        if is_media_tool_enabled("extract"):
            buttons.data_button("Extract Settings", "botset mediatools_extract")

        # Only show metadata settings if metadata tool is enabled
        if is_media_tool_enabled("metadata"):
            buttons.data_button("Metadata Settings", "botset mediatools_metadata")

        buttons.data_button("Back", "botset back", "footer")
        buttons.data_button("Close", "botset close", "footer")
        msg = "<b>Media Tools Settings</b>\n\nConfigure global settings for media tools."
    elif key == "ai":
        # Add buttons for each AI setting
        ai_settings = [
            "DEFAULT_AI_PROVIDER",
            "MISTRAL_API_KEY",
            "MISTRAL_API_URL",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_API_URL",
            "CHATGPT_API_KEY",
            "CHATGPT_API_URL",
            "GEMINI_API_KEY",
            "GEMINI_API_URL",
        ]

        for setting in ai_settings:
            display_name = setting.replace("_", " ").title()
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit ai")
        else:
            buttons.data_button("View", "botset view ai")

        buttons.data_button("Default", "botset default_ai")
        buttons.data_button("Back", "botset back", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current AI settings
        default_ai = Config.DEFAULT_AI_PROVIDER.capitalize()
        mistral_api_key = "✅ Set" if Config.MISTRAL_API_KEY else "❌ Not Set"
        mistral_api_url = Config.MISTRAL_API_URL or "Not Set"
        deepseek_api_key = "✅ Set" if Config.DEEPSEEK_API_KEY else "❌ Not Set"
        deepseek_api_url = Config.DEEPSEEK_API_URL or "Not Set"
        chatgpt_api_key = "✅ Set" if Config.CHATGPT_API_KEY else "❌ Not Set"
        chatgpt_api_url = Config.CHATGPT_API_URL or "Not Set"
        gemini_api_key = "✅ Set" if Config.GEMINI_API_KEY else "❌ Not Set"
        gemini_api_url = Config.GEMINI_API_URL or "Not Set"

        msg = f"""<b>AI Settings</b> | State: {state}

<b>Default AI Provider:</b> <code>{default_ai}</code>

<b>Mistral AI:</b>
• <b>API Key:</b> {mistral_api_key}
• <b>API URL:</b> <code>{mistral_api_url}</code>

<b>DeepSeek AI:</b>
• <b>API Key:</b> {deepseek_api_key}
• <b>API URL:</b> <code>{deepseek_api_url}</code>

<b>ChatGPT:</b>
• <b>API Key:</b> {chatgpt_api_key}
• <b>API URL:</b> <code>{chatgpt_api_url}</code>

<b>Gemini AI:</b>
• <b>API Key:</b> {gemini_api_key}
• <b>API URL:</b> <code>{gemini_api_url}</code>

<i>Note: For each AI provider, configure either API Key or API URL. If both are set, API Key will be used first with fallback to API URL.</i>
<i>Users can override these settings in their user settings.</i>
<i>Use /ask command to chat with the default AI provider.</i>"""

    elif key == "taskmonitor":
        # Add buttons for each task monitoring setting
        task_monitor_settings = [
            "TASK_MONITOR_ENABLED",
            "TASK_MONITOR_INTERVAL",
            "TASK_MONITOR_CONSECUTIVE_CHECKS",
            "TASK_MONITOR_SPEED_THRESHOLD",
            "TASK_MONITOR_ELAPSED_THRESHOLD",
            "TASK_MONITOR_ETA_THRESHOLD",
            "TASK_MONITOR_WAIT_TIME",
            "TASK_MONITOR_COMPLETION_THRESHOLD",
            "TASK_MONITOR_CPU_HIGH",
            "TASK_MONITOR_CPU_LOW",
            "TASK_MONITOR_MEMORY_HIGH",
            "TASK_MONITOR_MEMORY_LOW",
        ]

        for setting in task_monitor_settings:
            display_name = (
                setting.replace("TASK_MONITOR_", "").replace("_", " ").title()
            )
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit taskmonitor")
        else:
            buttons.data_button("View", "botset view taskmonitor")

        buttons.data_button("Default", "botset default_taskmonitor")
        buttons.data_button("Back", "botset back", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current task monitoring settings
        monitor_enabled = (
            "✅ Enabled" if Config.TASK_MONITOR_ENABLED else "❌ Disabled"
        )
        monitor_interval = f"{Config.TASK_MONITOR_INTERVAL} seconds"
        monitor_checks = str(Config.TASK_MONITOR_CONSECUTIVE_CHECKS)
        monitor_speed = f"{Config.TASK_MONITOR_SPEED_THRESHOLD} KB/s"
        monitor_elapsed = f"{Config.TASK_MONITOR_ELAPSED_THRESHOLD // 60} minutes"
        monitor_eta = f"{Config.TASK_MONITOR_ETA_THRESHOLD // 3600} hours"
        monitor_wait = f"{Config.TASK_MONITOR_WAIT_TIME // 60} minutes"
        monitor_completion = (
            f"{Config.TASK_MONITOR_COMPLETION_THRESHOLD // 3600} hours"
        )
        monitor_cpu_high = f"{Config.TASK_MONITOR_CPU_HIGH}%"
        monitor_cpu_low = f"{Config.TASK_MONITOR_CPU_LOW}%"
        monitor_memory_high = f"{Config.TASK_MONITOR_MEMORY_HIGH}%"
        monitor_memory_low = f"{Config.TASK_MONITOR_MEMORY_LOW}%"

        msg = f"""<b>Task Monitoring Settings</b> | State: {state}

<b>Status:</b> {monitor_enabled}
<b>Check Interval:</b> {monitor_interval}
<b>Consecutive Checks:</b> {monitor_checks}
<b>Speed Threshold:</b> {monitor_speed}
<b>Elapsed Time Threshold:</b> {monitor_elapsed}
<b>ETA Threshold:</b> {monitor_eta}
<b>Wait Time Before Cancel:</b> {monitor_wait}
<b>Completion Time Threshold:</b> {monitor_completion}
<b>CPU High Threshold:</b> {monitor_cpu_high}
<b>CPU Low Threshold:</b> {monitor_cpu_low}
<b>Memory High Threshold:</b> {monitor_memory_high}
<b>Memory Low Threshold:</b> {monitor_memory_low}

Configure task monitoring settings to automatically manage downloads based on performance metrics."""
    elif key == "mediatools_watermark":
        # Add buttons for each watermark setting in a 2-column layout
        # Visual watermark settings
        visual_settings = [
            "WATERMARK_ENABLED",
            "WATERMARK_KEY",
            "WATERMARK_POSITION",
            "WATERMARK_SIZE",
            "WATERMARK_COLOR",
            "WATERMARK_FONT",
            "WATERMARK_PRIORITY",
            "WATERMARK_THREADING",
            "WATERMARK_THREAD_NUMBER",
            "WATERMARK_FAST_MODE",
            "WATERMARK_MAINTAIN_QUALITY",
            "WATERMARK_OPACITY",
        ]

        # Audio watermark settings
        audio_settings = [
            "AUDIO_WATERMARK_ENABLED",
            "AUDIO_WATERMARK_TEXT",
            "AUDIO_WATERMARK_VOLUME",
        ]

        # Subtitle watermark settings
        subtitle_settings = [
            "SUBTITLE_WATERMARK_ENABLED",
            "SUBTITLE_WATERMARK_TEXT",
            "SUBTITLE_WATERMARK_STYLE",
        ]

        # Combine all settings
        watermark_settings = visual_settings + audio_settings + subtitle_settings
        for setting in watermark_settings:
            if setting.startswith("AUDIO_"):
                display_name = (
                    "Audio "
                    + setting.replace("AUDIO_WATERMARK_", "")
                    .replace("_", " ")
                    .title()
                )
                # For boolean settings, add toggle buttons
                if setting == "AUDIO_WATERMARK_ENABLED":
                    status = "✅ ON" if Config.AUDIO_WATERMARK_ENABLED else "❌ OFF"
                    display_name = f"Audio Enabled: {status}"
                    buttons.data_button(
                        display_name,
                        f"botset toggle {setting} {not Config.AUDIO_WATERMARK_ENABLED}",
                    )
                    continue
            elif setting.startswith("SUBTITLE_"):
                display_name = (
                    "Subtitle "
                    + setting.replace("SUBTITLE_WATERMARK_", "")
                    .replace("_", " ")
                    .title()
                )
                # For boolean settings, add toggle buttons
                if setting == "SUBTITLE_WATERMARK_ENABLED":
                    status = (
                        "✅ ON" if Config.SUBTITLE_WATERMARK_ENABLED else "❌ OFF"
                    )
                    display_name = f"Subtitle Enabled: {status}"
                    buttons.data_button(
                        display_name,
                        f"botset toggle {setting} {not Config.SUBTITLE_WATERMARK_ENABLED}",
                    )
                    continue
            else:
                display_name = (
                    setting.replace("WATERMARK_", "").replace("_", " ").title()
                )
                # For boolean settings, add toggle buttons
                if setting == "WATERMARK_ENABLED":
                    status = "✅ ON" if Config.WATERMARK_ENABLED else "❌ OFF"
                    display_name = f"Enabled: {status}"
                    buttons.data_button(
                        display_name,
                        f"botset toggle {setting} {not Config.WATERMARK_ENABLED}",
                    )
                    continue
                if setting in [
                    "WATERMARK_THREADING",
                    "WATERMARK_FAST_MODE",
                    "WATERMARK_MAINTAIN_QUALITY",
                ]:
                    status = "✅ ON" if getattr(Config, setting) else "❌ OFF"
                    display_name = f"{display_name}: {status}"
                    buttons.data_button(
                        display_name,
                        f"botset toggle {setting} {not getattr(Config, setting)}",
                    )
                    continue

            # For non-boolean settings, use editvar
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_watermark")
        else:
            buttons.data_button("View", "botset view mediatools_watermark")

        buttons.data_button("Default", "botset default_watermark")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current visual watermark settings
        watermark_enabled = (
            "✅ Enabled" if Config.WATERMARK_ENABLED else "❌ Disabled"
        )
        watermark_text = Config.WATERMARK_KEY or "None"
        watermark_position = Config.WATERMARK_POSITION or "top_left (Default)"
        watermark_size = Config.WATERMARK_SIZE or "20 (Default)"
        watermark_color = Config.WATERMARK_COLOR or "white (Default)"
        watermark_font = Config.WATERMARK_FONT or "default.otf (Default)"
        watermark_priority = Config.WATERMARK_PRIORITY or "2 (Default)"
        watermark_threading = (
            "✅ Enabled" if Config.WATERMARK_THREADING else "❌ Disabled"
        )
        watermark_thread_number = Config.WATERMARK_THREAD_NUMBER or "4 (Default)"
        watermark_fast_mode = (
            "✅ Enabled" if Config.WATERMARK_FAST_MODE else "❌ Disabled"
        )
        watermark_maintain_quality = (
            "✅ Enabled" if Config.WATERMARK_MAINTAIN_QUALITY else "❌ Disabled"
        )
        watermark_opacity = Config.WATERMARK_OPACITY or "1.0 (Default)"

        # Get current audio watermark settings
        audio_watermark_enabled = (
            "✅ Enabled" if Config.AUDIO_WATERMARK_ENABLED else "❌ Disabled"
        )
        audio_watermark_text = (
            Config.AUDIO_WATERMARK_TEXT or "None (Uses visual watermark text)"
        )
        audio_watermark_volume = Config.AUDIO_WATERMARK_VOLUME or "0.3 (Default)"

        # Get current subtitle watermark settings
        subtitle_watermark_enabled = (
            "✅ Enabled" if Config.SUBTITLE_WATERMARK_ENABLED else "❌ Disabled"
        )
        subtitle_watermark_text = (
            Config.SUBTITLE_WATERMARK_TEXT or "None (Uses visual watermark text)"
        )
        subtitle_watermark_style = (
            Config.SUBTITLE_WATERMARK_STYLE or "normal (Default)"
        )

        msg = f"""<b>Watermark Settings</b> | State: {state}

<b>Visual Watermark Settings:</b>
<b>Status:</b> {watermark_enabled}
<b>Text:</b> <code>{watermark_text}</code>
<b>Position:</b> <code>{watermark_position}</code>
<b>Size:</b> <code>{watermark_size}</code>
<b>Color:</b> <code>{watermark_color}</code>
<b>Font:</b> <code>{watermark_font}</code>
<b>Priority:</b> <code>{watermark_priority}</code>
<b>Threading:</b> {watermark_threading}
<b>Thread Number:</b> <code>{watermark_thread_number}</code>
<b>Fast Mode:</b> {watermark_fast_mode}
<b>Maintain Quality:</b> {watermark_maintain_quality}
<b>Opacity:</b> <code>{watermark_opacity}</code>

<b>Audio Watermark Settings:</b>
<b>Status:</b> {audio_watermark_enabled}
<b>Text:</b> <code>{audio_watermark_text}</code>
<b>Volume:</b> <code>{audio_watermark_volume}</code>

<b>Subtitle Watermark Settings:</b>
<b>Status:</b> {subtitle_watermark_enabled}
<b>Text:</b> <code>{subtitle_watermark_text}</code>
<b>Style:</b> <code>{subtitle_watermark_style}</code>

Configure global watermark settings that will be used when user settings are not available."""

    elif key == "mediatools_merge":
        # Get all merge settings and organize them by category
        general_settings = [
            "MERGE_ENABLED",
            "CONCAT_DEMUXER_ENABLED",
            "FILTER_COMPLEX_ENABLED",
            "MERGE_PRIORITY",
            "MERGE_THREADING",
            "MERGE_THREAD_NUMBER",
            "MERGE_REMOVE_ORIGINAL",
        ]

        # Output formats
        formats = [
            "MERGE_OUTPUT_FORMAT_VIDEO",
            "MERGE_OUTPUT_FORMAT_AUDIO",
            "MERGE_OUTPUT_FORMAT_IMAGE",
            "MERGE_OUTPUT_FORMAT_DOCUMENT",
            "MERGE_OUTPUT_FORMAT_SUBTITLE",
        ]

        # Video settings
        video_settings = [
            "MERGE_VIDEO_CODEC",
            "MERGE_VIDEO_QUALITY",
            "MERGE_VIDEO_PRESET",
            "MERGE_VIDEO_CRF",
            "MERGE_VIDEO_PIXEL_FORMAT",
            "MERGE_VIDEO_TUNE",
            "MERGE_VIDEO_FASTSTART",
        ]

        # Audio settings
        audio_settings = [
            "MERGE_AUDIO_CODEC",
            "MERGE_AUDIO_BITRATE",
            "MERGE_AUDIO_CHANNELS",
            "MERGE_AUDIO_SAMPLING",
            "MERGE_AUDIO_VOLUME",
        ]

        # Image settings
        image_settings = [
            "MERGE_IMAGE_MODE",
            "MERGE_IMAGE_COLUMNS",
            "MERGE_IMAGE_QUALITY",
            "MERGE_IMAGE_DPI",
            "MERGE_IMAGE_RESIZE",
            "MERGE_IMAGE_BACKGROUND",
        ]

        # Subtitle settings
        subtitle_settings = [
            "MERGE_SUBTITLE_ENCODING",
            "MERGE_SUBTITLE_FONT",
            "MERGE_SUBTITLE_FONT_SIZE",
            "MERGE_SUBTITLE_FONT_COLOR",
            "MERGE_SUBTITLE_BACKGROUND",
        ]

        # Document settings
        document_settings = [
            "MERGE_DOCUMENT_PAPER_SIZE",
            "MERGE_DOCUMENT_ORIENTATION",
            "MERGE_DOCUMENT_MARGIN",
        ]

        # Metadata settings
        metadata_settings = [
            "MERGE_METADATA_TITLE",
            "MERGE_METADATA_AUTHOR",
            "MERGE_METADATA_COMMENT",
        ]

        # Combine all settings in a logical order
        merge_settings = (
            general_settings
            + formats
            + video_settings
            + audio_settings
            + image_settings
            + subtitle_settings
            + document_settings
            + metadata_settings
        )

        # 5 rows per page, 2 columns = 10 items per page
        items_per_page = 10  # 5 rows * 2 columns
        total_pages = (len(merge_settings) + items_per_page - 1) // items_per_page

        # Ensure page is valid
        # Use the global merge_page variable if page is not provided
        if page == 0 and globals()["merge_page"] != 0:
            current_page = globals()["merge_page"]
        else:
            current_page = page
            # Update the global merge_page variable
            globals()["merge_page"] = current_page

        # Validate page number
        if current_page >= total_pages:
            current_page = 0
            globals()["merge_page"] = 0
        elif current_page < 0:
            current_page = total_pages - 1
            globals()["merge_page"] = total_pages - 1
            LOGGER.debug(f"Updated merge_page to {globals()['merge_page']}")

        # Get settings for current page
        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, len(merge_settings))
        current_page_settings = merge_settings[start_idx:end_idx]

        # Add buttons for each setting on current page
        for setting in current_page_settings:
            display_name = setting.replace("MERGE_", "").replace("_", " ").title()
            if setting.startswith(("CONCAT", "FILTER")):
                display_name = setting.replace("_ENABLED", "").title()
            buttons.data_button(display_name, f"botset editvar {setting}")

        # Add action buttons in a separate row
        # Add Edit/View button
        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_merge", "footer")
        else:
            buttons.data_button("View", "botset view mediatools_merge", "footer")

        # Add Default button
        buttons.data_button("Default", "botset default_merge", "footer")

        # Add navigation buttons
        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Add pagination buttons in a separate row below action buttons
        if total_pages > 1:
            for i in range(total_pages):
                # Make the current page button different
                if i == current_page:
                    buttons.data_button(
                        f"[{i + 1}]", f"botset start_merge {i}", "page"
                    )
                else:
                    buttons.data_button(
                        str(i + 1), f"botset start_merge {i}", "page"
                    )

            # Add a debug log message# Get current merge settings
        merge_enabled = "✅ Enabled" if Config.MERGE_ENABLED else "❌ Disabled"
        concat_demuxer = (
            "✅ Enabled" if Config.CONCAT_DEMUXER_ENABLED else "❌ Disabled"
        )
        filter_complex = (
            "✅ Enabled" if Config.FILTER_COMPLEX_ENABLED else "❌ Disabled"
        )
        video_format = Config.MERGE_OUTPUT_FORMAT_VIDEO or "mkv (Default)"
        audio_format = Config.MERGE_OUTPUT_FORMAT_AUDIO or "mp3 (Default)"
        merge_priority = Config.MERGE_PRIORITY or "1 (Default)"
        merge_threading = "✅ Enabled" if Config.MERGE_THREADING else "❌ Disabled"
        merge_thread_number = Config.MERGE_THREAD_NUMBER or "4 (Default)"
        merge_remove_original = (
            "✅ Enabled" if Config.MERGE_REMOVE_ORIGINAL else "❌ Disabled"
        )

        # Determine which category is shown on the current page
        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, len(merge_settings))

        # Get the categories shown on the current page
        categories = []
        if any(
            setting in general_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("General")
        if any(setting in formats for setting in merge_settings[start_idx:end_idx]):
            categories.append("Formats")
        if any(
            setting in video_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("Video")
        if any(
            setting in audio_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("Audio")
        if any(
            setting in image_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("Image")
        if any(
            setting in subtitle_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("Subtitle")
        if any(
            setting in document_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("Document")
        if any(
            setting in metadata_settings
            for setting in merge_settings[start_idx:end_idx]
        ):
            categories.append("Metadata")

        category_text = ", ".join(categories)

        msg = f"""<b>Merge Settings</b> | State: {state}

<b>Status:</b> {merge_enabled}
<b>Concat Demuxer:</b> {concat_demuxer}
<b>Filter Complex:</b> {filter_complex}
<b>Video Format:</b> <code>{video_format}</code>
<b>Audio Format:</b> <code>{audio_format}</code>
<b>Priority:</b> <code>{merge_priority}</code>
<b>Threading:</b> {merge_threading}
<b>Thread Number:</b> <code>{merge_thread_number}</code>
<b>Remove Original:</b> {merge_remove_original}

Configure global merge settings that will be used when user settings are not available.
Current page shows: {category_text} settings."""

        # Add page info to message
        if total_pages > 1:
            msg += f"\n\n<b>Page:</b> {current_page + 1}/{total_pages}"

        # Build the menu with 2 columns for settings, 4 columns for action buttons, and 8 columns for pagination
        btns = buttons.build_menu(2, 8, 4, 8)
        return msg, btns

    elif key == "mediatools_extract":
        # Add buttons for extract settings
        # General extract settings
        general_settings = [
            "EXTRACT_ENABLED",
            "EXTRACT_PRIORITY",
            "EXTRACT_DELETE_ORIGINAL",
        ]

        # Video extract settings
        video_settings = [
            "EXTRACT_VIDEO_ENABLED",
            "EXTRACT_VIDEO_CODEC",
            "EXTRACT_VIDEO_FORMAT",
            "EXTRACT_VIDEO_INDEX",
            "EXTRACT_VIDEO_QUALITY",
            "EXTRACT_VIDEO_PRESET",
            "EXTRACT_VIDEO_BITRATE",
            "EXTRACT_VIDEO_RESOLUTION",
            "EXTRACT_VIDEO_FPS",
        ]

        # Audio extract settings
        audio_settings = [
            "EXTRACT_AUDIO_ENABLED",
            "EXTRACT_AUDIO_CODEC",
            "EXTRACT_AUDIO_FORMAT",
            "EXTRACT_AUDIO_INDEX",
            "EXTRACT_AUDIO_BITRATE",
            "EXTRACT_AUDIO_CHANNELS",
            "EXTRACT_AUDIO_SAMPLING",
            "EXTRACT_AUDIO_VOLUME",
        ]

        # Subtitle extract settings
        subtitle_settings = [
            "EXTRACT_SUBTITLE_ENABLED",
            "EXTRACT_SUBTITLE_CODEC",
            "EXTRACT_SUBTITLE_FORMAT",
            "EXTRACT_SUBTITLE_INDEX",
            "EXTRACT_SUBTITLE_LANGUAGE",
            "EXTRACT_SUBTITLE_ENCODING",
            "EXTRACT_SUBTITLE_FONT",
            "EXTRACT_SUBTITLE_FONT_SIZE",
        ]

        # Attachment extract settings
        attachment_settings = [
            "EXTRACT_ATTACHMENT_ENABLED",
            "EXTRACT_ATTACHMENT_FORMAT",
            "EXTRACT_ATTACHMENT_INDEX",
            "EXTRACT_ATTACHMENT_FILTER",
        ]

        # Quality settings
        quality_settings = [
            "EXTRACT_MAINTAIN_QUALITY",
        ]

        # Combine all settings
        extract_settings = (
            general_settings
            + video_settings
            + audio_settings
            + subtitle_settings
            + attachment_settings
            + quality_settings
        )

        for setting in extract_settings:
            # Create display name based on setting type
            if setting.startswith("EXTRACT_VIDEO_"):
                display_name = (
                    "Video "
                    + setting.replace("EXTRACT_VIDEO_", "").replace("_", " ").title()
                )
            elif setting.startswith("EXTRACT_AUDIO_"):
                display_name = (
                    "Audio "
                    + setting.replace("EXTRACT_AUDIO_", "").replace("_", " ").title()
                )
            elif setting.startswith("EXTRACT_SUBTITLE_"):
                display_name = (
                    "Subtitle "
                    + setting.replace("EXTRACT_SUBTITLE_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("EXTRACT_ATTACHMENT_"):
                display_name = (
                    "Attachment "
                    + setting.replace("EXTRACT_ATTACHMENT_", "")
                    .replace("_", " ")
                    .title()
                )
            else:
                display_name = (
                    setting.replace("EXTRACT_", "").replace("_", " ").title()
                )

            # For boolean settings, add toggle buttons
            if setting in [
                "EXTRACT_ENABLED",
                "EXTRACT_VIDEO_ENABLED",
                "EXTRACT_AUDIO_ENABLED",
                "EXTRACT_SUBTITLE_ENABLED",
                "EXTRACT_ATTACHMENT_ENABLED",
                "EXTRACT_MAINTAIN_QUALITY",
            ]:
                setting_value = getattr(Config, setting, False)
                status = "✅ ON" if setting_value else "❌ OFF"

                # Format display name with status
                if setting == "EXTRACT_ENABLED":
                    display_name = f"Enabled: {status}"
                elif setting == "EXTRACT_VIDEO_ENABLED":
                    display_name = f"Video Enabled: {status}"
                elif setting == "EXTRACT_AUDIO_ENABLED":
                    display_name = f"Audio Enabled: {status}"
                elif setting == "EXTRACT_SUBTITLE_ENABLED":
                    display_name = f"Subtitle Enabled: {status}"
                elif setting == "EXTRACT_ATTACHMENT_ENABLED":
                    display_name = f"Attachment Enabled: {status}"
                elif setting == "EXTRACT_MAINTAIN_QUALITY":
                    display_name = f"Maintain Quality: {status}"
                else:
                    display_name = f"{display_name}: {status}"

                # Create toggle button
                buttons.data_button(
                    display_name,
                    f"botset toggle {setting} {not setting_value}",
                )
                continue

            # For non-boolean settings, use editvar
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_extract")
        else:
            buttons.data_button("View", "botset view mediatools_extract")

        buttons.data_button("Default", "botset default_extract")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current extract settings
        extract_enabled = "✅ Enabled" if Config.EXTRACT_ENABLED else "❌ Disabled"
        extract_priority = f"{Config.EXTRACT_PRIORITY}"
        extract_delete_original = (
            "✅ Enabled" if Config.EXTRACT_DELETE_ORIGINAL else "❌ Disabled"
        )

        # Video settings
        video_enabled = (
            "✅ Enabled" if Config.EXTRACT_VIDEO_ENABLED else "❌ Disabled"
        )
        video_codec = Config.EXTRACT_VIDEO_CODEC or "None"
        video_format = Config.EXTRACT_VIDEO_FORMAT or "None"
        video_index = Config.EXTRACT_VIDEO_INDEX or "All"
        video_quality = Config.EXTRACT_VIDEO_QUALITY or "None"
        video_preset = Config.EXTRACT_VIDEO_PRESET or "None"
        video_bitrate = Config.EXTRACT_VIDEO_BITRATE or "None"
        video_resolution = Config.EXTRACT_VIDEO_RESOLUTION or "None"
        video_fps = Config.EXTRACT_VIDEO_FPS or "None"

        # Audio settings
        audio_enabled = (
            "✅ Enabled" if Config.EXTRACT_AUDIO_ENABLED else "❌ Disabled"
        )
        audio_codec = Config.EXTRACT_AUDIO_CODEC or "None"
        audio_format = Config.EXTRACT_AUDIO_FORMAT or "None"
        audio_index = Config.EXTRACT_AUDIO_INDEX or "All"
        audio_bitrate = Config.EXTRACT_AUDIO_BITRATE or "None"
        audio_channels = Config.EXTRACT_AUDIO_CHANNELS or "None"
        audio_sampling = Config.EXTRACT_AUDIO_SAMPLING or "None"
        audio_volume = Config.EXTRACT_AUDIO_VOLUME or "None"

        # Subtitle settings
        subtitle_enabled = (
            "✅ Enabled" if Config.EXTRACT_SUBTITLE_ENABLED else "❌ Disabled"
        )
        subtitle_codec = Config.EXTRACT_SUBTITLE_CODEC or "None"
        subtitle_format = Config.EXTRACT_SUBTITLE_FORMAT or "None"
        subtitle_index = Config.EXTRACT_SUBTITLE_INDEX or "All"
        subtitle_language = Config.EXTRACT_SUBTITLE_LANGUAGE or "None"
        subtitle_encoding = Config.EXTRACT_SUBTITLE_ENCODING or "None"
        subtitle_font = Config.EXTRACT_SUBTITLE_FONT or "None"
        subtitle_font_size = Config.EXTRACT_SUBTITLE_FONT_SIZE or "None"

        # Attachment settings
        attachment_enabled = (
            "✅ Enabled" if Config.EXTRACT_ATTACHMENT_ENABLED else "❌ Disabled"
        )
        attachment_format = Config.EXTRACT_ATTACHMENT_FORMAT or "None"
        attachment_index = Config.EXTRACT_ATTACHMENT_INDEX or "All"
        attachment_filter = Config.EXTRACT_ATTACHMENT_FILTER or "None"

        # Quality settings
        maintain_quality = (
            "✅ Enabled" if Config.EXTRACT_MAINTAIN_QUALITY else "❌ Disabled"
        )

        msg = f"""<b>Extract Settings</b> | State: {state}

<b>General Settings:</b>
• <b>Status:</b> {extract_enabled}
• <b>Priority:</b> <code>{extract_priority}</code>
• <b>Delete Original:</b> {extract_delete_original}

<b>Video Extract Settings:</b>
• <b>Status:</b> {video_enabled}
• <b>Codec:</b> <code>{video_codec}</code>
• <b>Format:</b> <code>{video_format}</code>
• <b>Index:</b> <code>{video_index}</code>
• <b>Quality:</b> <code>{video_quality}</code>
• <b>Preset:</b> <code>{video_preset}</code>
• <b>Bitrate:</b> <code>{video_bitrate}</code>
• <b>Resolution:</b> <code>{video_resolution}</code>
• <b>FPS:</b> <code>{video_fps}</code>

<b>Audio Extract Settings:</b>
• <b>Status:</b> {audio_enabled}
• <b>Codec:</b> <code>{audio_codec}</code>
• <b>Format:</b> <code>{audio_format}</code>
• <b>Index:</b> <code>{audio_index}</code>
• <b>Bitrate:</b> <code>{audio_bitrate}</code>
• <b>Channels:</b> <code>{audio_channels}</code>
• <b>Sampling:</b> <code>{audio_sampling}</code>
• <b>Volume:</b> <code>{audio_volume}</code>

<b>Subtitle Extract Settings:</b>
• <b>Status:</b> {subtitle_enabled}
• <b>Codec:</b> <code>{subtitle_codec}</code>
• <b>Format:</b> <code>{subtitle_format}</code>
• <b>Index:</b> <code>{subtitle_index}</code>
• <b>Language:</b> <code>{subtitle_language}</code>
• <b>Encoding:</b> <code>{subtitle_encoding}</code>
• <b>Font:</b> <code>{subtitle_font}</code>
• <b>Font Size:</b> <code>{subtitle_font_size}</code>

<b>Attachment Extract Settings:</b>
• <b>Status:</b> {attachment_enabled}
• <b>Format:</b> <code>{attachment_format}</code>
• <b>Index:</b> <code>{attachment_index}</code>
• <b>Filter:</b> <code>{attachment_filter}</code>

<b>Quality Settings:</b>
• <b>Maintain Quality:</b> {maintain_quality}

<b>Usage:</b>
• Main Extract toggle must be enabled
• Media type specific toggles must be enabled for respective extractions
• Use <code>-extract</code> to enable extraction
• Use <code>-extract-video</code>, <code>-extract-audio</code>, etc. for specific track types
• Use <code>-extract-video-index 0</code> to extract specific track by index
• Add <code>-del</code> to delete original files after extraction
• Settings with value 'None' will not be used in command generation

Configure global extract settings that will be used when user settings are not available."""

    elif key == "mediatools_trim":
        # Add buttons for trim settings
        # General trim settings
        general_settings = [
            "TRIM_ENABLED",
            "TRIM_PRIORITY",
            "TRIM_START_TIME",
            "TRIM_END_TIME",
            "TRIM_DELETE_ORIGINAL",
        ]

        # Video trim settings
        video_settings = [
            "TRIM_VIDEO_ENABLED",
            "TRIM_VIDEO_CODEC",
            "TRIM_VIDEO_PRESET",
            "TRIM_VIDEO_FORMAT",
        ]

        # Audio trim settings
        audio_settings = [
            "TRIM_AUDIO_ENABLED",
            "TRIM_AUDIO_CODEC",
            "TRIM_AUDIO_PRESET",
            "TRIM_AUDIO_FORMAT",
        ]

        # Image trim settings
        image_settings = [
            "TRIM_IMAGE_ENABLED",
            "TRIM_IMAGE_QUALITY",
            "TRIM_IMAGE_FORMAT",
        ]

        # Document trim settings
        document_settings = [
            "TRIM_DOCUMENT_ENABLED",
            "TRIM_DOCUMENT_QUALITY",
            "TRIM_DOCUMENT_FORMAT",
        ]

        # Subtitle trim settings
        subtitle_settings = [
            "TRIM_SUBTITLE_ENABLED",
            "TRIM_SUBTITLE_ENCODING",
            "TRIM_SUBTITLE_FORMAT",
        ]

        # Archive trim settings
        archive_settings = [
            "TRIM_ARCHIVE_ENABLED",
            "TRIM_ARCHIVE_FORMAT",
        ]

        # Combine all settings
        trim_settings = (
            general_settings
            + video_settings
            + audio_settings
            + image_settings
            + document_settings
            + subtitle_settings
            + archive_settings
        )

        for setting in trim_settings:
            # Create display name based on setting type
            if setting.startswith("TRIM_VIDEO_"):
                display_name = (
                    "Video "
                    + setting.replace("TRIM_VIDEO_", "").replace("_", " ").title()
                )
            elif setting.startswith("TRIM_AUDIO_"):
                display_name = (
                    "Audio "
                    + setting.replace("TRIM_AUDIO_", "").replace("_", " ").title()
                )
            elif setting.startswith("TRIM_IMAGE_"):
                display_name = (
                    "Image "
                    + setting.replace("TRIM_IMAGE_", "").replace("_", " ").title()
                )
            elif setting.startswith("TRIM_DOCUMENT_"):
                display_name = (
                    "Document "
                    + setting.replace("TRIM_DOCUMENT_", "").replace("_", " ").title()
                )
            elif setting.startswith("TRIM_SUBTITLE_"):
                display_name = (
                    "Subtitle "
                    + setting.replace("TRIM_SUBTITLE_", "").replace("_", " ").title()
                )
            elif setting.startswith("TRIM_ARCHIVE_"):
                display_name = (
                    "Archive "
                    + setting.replace("TRIM_ARCHIVE_", "").replace("_", " ").title()
                )
            else:
                display_name = setting.replace("TRIM_", "").replace("_", " ").title()

            # For boolean settings, add toggle buttons
            if setting in [
                "TRIM_ENABLED",
                "TRIM_VIDEO_ENABLED",
                "TRIM_AUDIO_ENABLED",
                "TRIM_IMAGE_ENABLED",
                "TRIM_DOCUMENT_ENABLED",
                "TRIM_SUBTITLE_ENABLED",
                "TRIM_ARCHIVE_ENABLED",
            ]:
                setting_value = getattr(Config, setting, False)
                status = "✅ ON" if setting_value else "❌ OFF"

                # Format display name with status
                if setting == "TRIM_ENABLED":
                    display_name = f"Enabled: {status}"
                elif setting == "TRIM_VIDEO_ENABLED":
                    display_name = f"Video Enabled: {status}"
                elif setting == "TRIM_AUDIO_ENABLED":
                    display_name = f"Audio Enabled: {status}"
                elif setting == "TRIM_IMAGE_ENABLED":
                    display_name = f"Image Enabled: {status}"
                elif setting == "TRIM_DOCUMENT_ENABLED":
                    display_name = f"Document Enabled: {status}"
                elif setting == "TRIM_SUBTITLE_ENABLED":
                    display_name = f"Subtitle Enabled: {status}"
                elif setting == "TRIM_ARCHIVE_ENABLED":
                    display_name = f"Archive Enabled: {status}"
                else:
                    display_name = f"{display_name}: {status}"

                # Create toggle button
                buttons.data_button(
                    display_name,
                    f"botset toggle {setting} {not setting_value}",
                )
                continue

            # For non-boolean settings, use editvar
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_trim")
        else:
            buttons.data_button("View", "botset view mediatools_trim")

        buttons.data_button("Default", "botset default_trim")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current trim settings
        trim_enabled = "✅ Enabled" if Config.TRIM_ENABLED else "❌ Disabled"
        trim_priority = Config.TRIM_PRIORITY or "5 (Default)"
        trim_start_time = Config.TRIM_START_TIME or "00:00:00 (Default)"
        trim_end_time = Config.TRIM_END_TIME or "None (End of file)"

        # Video settings
        video_enabled = "✅ Enabled" if Config.TRIM_VIDEO_ENABLED else "❌ Disabled"
        video_codec = Config.TRIM_VIDEO_CODEC or "None"
        video_preset = Config.TRIM_VIDEO_PRESET or "None"
        video_format = Config.TRIM_VIDEO_FORMAT or "None"

        # Audio settings
        audio_enabled = "✅ Enabled" if Config.TRIM_AUDIO_ENABLED else "❌ Disabled"
        audio_codec = Config.TRIM_AUDIO_CODEC or "None"
        audio_preset = Config.TRIM_AUDIO_PRESET or "None"
        audio_format = Config.TRIM_AUDIO_FORMAT or "None"

        # Image settings
        image_enabled = "✅ Enabled" if Config.TRIM_IMAGE_ENABLED else "❌ Disabled"
        image_quality = Config.TRIM_IMAGE_QUALITY or "90 (Default)"
        image_format = Config.TRIM_IMAGE_FORMAT or "None"

        # Document settings
        document_enabled = (
            "✅ Enabled" if Config.TRIM_DOCUMENT_ENABLED else "❌ Disabled"
        )
        document_quality = Config.TRIM_DOCUMENT_QUALITY or "90 (Default)"
        document_format = Config.TRIM_DOCUMENT_FORMAT or "None"

        # Subtitle settings
        subtitle_enabled = (
            "✅ Enabled" if Config.TRIM_SUBTITLE_ENABLED else "❌ Disabled"
        )
        subtitle_encoding = Config.TRIM_SUBTITLE_ENCODING or "None"
        subtitle_format = Config.TRIM_SUBTITLE_FORMAT or "None"

        # Archive settings
        archive_enabled = (
            "✅ Enabled" if Config.TRIM_ARCHIVE_ENABLED else "❌ Disabled"
        )
        archive_format = Config.TRIM_ARCHIVE_FORMAT or "None"

        msg = f"""<b>Trim Settings</b> | State: {state}

<b>General Settings:</b>
• <b>Status:</b> {trim_enabled}
• <b>Priority:</b> <code>{trim_priority}</code>
• <b>Start Time:</b> <code>{trim_start_time}</code>
• <b>End Time:</b> <code>{trim_end_time}</code>

<b>Video Trim Settings:</b>
• <b>Status:</b> {video_enabled}
• <b>Codec:</b> <code>{video_codec}</code>
• <b>Preset:</b> <code>{video_preset}</code>
• <b>Format:</b> <code>{video_format}</code>

<b>Audio Trim Settings:</b>
• <b>Status:</b> {audio_enabled}
• <b>Codec:</b> <code>{audio_codec}</code>
• <b>Preset:</b> <code>{audio_preset}</code>
• <b>Format:</b> <code>{audio_format}</code>

<b>Image Trim Settings:</b>
• <b>Status:</b> {image_enabled}
• <b>Quality:</b> <code>{image_quality}</code>
• <b>Format:</b> <code>{image_format}</code>

<b>Document Trim Settings:</b>
• <b>Status:</b> {document_enabled}
• <b>Quality:</b> <code>{document_quality}</code>
• <b>Format:</b> <code>{document_format}</code>

<b>Subtitle Trim Settings:</b>
• <b>Status:</b> {subtitle_enabled}
• <b>Encoding:</b> <code>{subtitle_encoding}</code>
• <b>Format:</b> <code>{subtitle_format}</code>

<b>Archive Trim Settings:</b>
• <b>Status:</b> {archive_enabled}
• <b>Format:</b> <code>{archive_format}</code>

<b>Usage:</b>
• Main Trim toggle must be enabled
• Media type specific toggles must be enabled for respective trims
• Use <code>-trim</code> to enable trimming
• Use <code>-trim-start HH:MM:SS</code> to set start time
• Use <code>-trim-end HH:MM:SS</code> to set end time
• Add <code>-del</code> to delete original files after trimming

Configure global trim settings that will be used when user settings are not available."""

    elif key == "mediatools_extract":
        # Add buttons for extract settings
        # General extract settings
        general_settings = [
            "EXTRACT_ENABLED",
            "EXTRACT_PRIORITY",
            "EXTRACT_DELETE_ORIGINAL",
        ]

        # Video extract settings
        video_settings = [
            "EXTRACT_VIDEO_ENABLED",
            "EXTRACT_VIDEO_CODEC",
            "EXTRACT_VIDEO_INDEX",
            "EXTRACT_VIDEO_QUALITY",
            "EXTRACT_VIDEO_PRESET",
            "EXTRACT_VIDEO_BITRATE",
            "EXTRACT_VIDEO_RESOLUTION",
            "EXTRACT_VIDEO_FPS",
            "EXTRACT_VIDEO_FORMAT",
        ]

        # Audio extract settings
        audio_settings = [
            "EXTRACT_AUDIO_ENABLED",
            "EXTRACT_AUDIO_CODEC",
            "EXTRACT_AUDIO_INDEX",
            "EXTRACT_AUDIO_BITRATE",
            "EXTRACT_AUDIO_CHANNELS",
            "EXTRACT_AUDIO_SAMPLING",
            "EXTRACT_AUDIO_VOLUME",
            "EXTRACT_AUDIO_FORMAT",
        ]

        # Subtitle extract settings
        subtitle_settings = [
            "EXTRACT_SUBTITLE_ENABLED",
            "EXTRACT_SUBTITLE_CODEC",
            "EXTRACT_SUBTITLE_INDEX",
            "EXTRACT_SUBTITLE_LANGUAGE",
            "EXTRACT_SUBTITLE_ENCODING",
            "EXTRACT_SUBTITLE_FONT",
            "EXTRACT_SUBTITLE_FONT_SIZE",
            "EXTRACT_SUBTITLE_FORMAT",
        ]

        # Attachment extract settings
        attachment_settings = [
            "EXTRACT_ATTACHMENT_ENABLED",
            "EXTRACT_ATTACHMENT_INDEX",
            "EXTRACT_ATTACHMENT_FILTER",
            "EXTRACT_ATTACHMENT_FORMAT",
        ]

        # Quality settings
        quality_settings = [
            "EXTRACT_MAINTAIN_QUALITY",
        ]

        # Combine all settings
        extract_settings = (
            general_settings
            + video_settings
            + audio_settings
            + subtitle_settings
            + attachment_settings
            + quality_settings
        )

        for setting in extract_settings:
            # Create display name based on setting type
            if setting.startswith("EXTRACT_VIDEO_"):
                display_name = (
                    "Video "
                    + setting.replace("EXTRACT_VIDEO_", "").replace("_", " ").title()
                )
            elif setting.startswith("EXTRACT_AUDIO_"):
                display_name = (
                    "Audio "
                    + setting.replace("EXTRACT_AUDIO_", "").replace("_", " ").title()
                )
            elif setting.startswith("EXTRACT_SUBTITLE_"):
                display_name = (
                    "Subtitle "
                    + setting.replace("EXTRACT_SUBTITLE_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("EXTRACT_ATTACHMENT_"):
                display_name = (
                    "Attachment "
                    + setting.replace("EXTRACT_ATTACHMENT_", "")
                    .replace("_", " ")
                    .title()
                )
            else:
                display_name = (
                    setting.replace("EXTRACT_", "").replace("_", " ").title()
                )

            # For boolean settings, add toggle buttons
            if setting in [
                "EXTRACT_ENABLED",
                "EXTRACT_VIDEO_ENABLED",
                "EXTRACT_AUDIO_ENABLED",
                "EXTRACT_SUBTITLE_ENABLED",
                "EXTRACT_ATTACHMENT_ENABLED",
                "EXTRACT_MAINTAIN_QUALITY",
                "EXTRACT_DELETE_ORIGINAL",
            ]:
                setting_value = getattr(Config, setting, False)
                status = "✅ ON" if setting_value else "❌ OFF"

                # Format display name with status
                if setting == "EXTRACT_ENABLED":
                    display_name = f"Enabled: {status}"
                elif setting == "EXTRACT_VIDEO_ENABLED":
                    display_name = f"Video Enabled: {status}"
                elif setting == "EXTRACT_AUDIO_ENABLED":
                    display_name = f"Audio Enabled: {status}"
                elif setting == "EXTRACT_SUBTITLE_ENABLED":
                    display_name = f"Subtitle Enabled: {status}"
                elif setting == "EXTRACT_ATTACHMENT_ENABLED":
                    display_name = f"Attachment Enabled: {status}"
                elif setting == "EXTRACT_MAINTAIN_QUALITY":
                    display_name = f"Maintain Quality: {status}"
                elif setting == "EXTRACT_DELETE_ORIGINAL":
                    display_name = f"Delete Original: {status}"
                else:
                    display_name = f"{display_name}: {status}"

                # Create toggle button
                buttons.data_button(
                    display_name,
                    f"botset toggle {setting} {not setting_value}",
                )
                continue

            # For non-boolean settings, use editvar
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_extract")
        else:
            buttons.data_button("View", "botset view mediatools_extract")

        buttons.data_button("Default", "botset default_extract")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current extract settings
        extract_enabled = "✅ Enabled" if Config.EXTRACT_ENABLED else "❌ Disabled"
        extract_priority = f"{Config.EXTRACT_PRIORITY}"
        delete_original = (
            "✅ Enabled" if Config.EXTRACT_DELETE_ORIGINAL else "❌ Disabled"
        )

        # Video settings
        video_enabled = (
            "✅ Enabled" if Config.EXTRACT_VIDEO_ENABLED else "❌ Disabled"
        )
        video_codec = Config.EXTRACT_VIDEO_CODEC or "None"
        video_format = Config.EXTRACT_VIDEO_FORMAT or "None"
        video_index = Config.EXTRACT_VIDEO_INDEX or "All"
        video_quality = Config.EXTRACT_VIDEO_QUALITY or "None"
        video_preset = Config.EXTRACT_VIDEO_PRESET or "None"
        video_bitrate = Config.EXTRACT_VIDEO_BITRATE or "None"
        video_resolution = Config.EXTRACT_VIDEO_RESOLUTION or "None"
        video_fps = Config.EXTRACT_VIDEO_FPS or "None"

        # Audio settings
        audio_enabled = (
            "✅ Enabled" if Config.EXTRACT_AUDIO_ENABLED else "❌ Disabled"
        )
        audio_codec = Config.EXTRACT_AUDIO_CODEC or "None"
        audio_format = Config.EXTRACT_AUDIO_FORMAT or "None"
        audio_index = Config.EXTRACT_AUDIO_INDEX or "All"
        audio_bitrate = Config.EXTRACT_AUDIO_BITRATE or "None"
        audio_channels = Config.EXTRACT_AUDIO_CHANNELS or "None"
        audio_sampling = Config.EXTRACT_AUDIO_SAMPLING or "None"
        audio_volume = Config.EXTRACT_AUDIO_VOLUME or "None"

        # Subtitle settings
        subtitle_enabled = (
            "✅ Enabled" if Config.EXTRACT_SUBTITLE_ENABLED else "❌ Disabled"
        )
        subtitle_codec = Config.EXTRACT_SUBTITLE_CODEC or "None"
        subtitle_format = Config.EXTRACT_SUBTITLE_FORMAT or "None"
        subtitle_index = Config.EXTRACT_SUBTITLE_INDEX or "All"
        subtitle_language = Config.EXTRACT_SUBTITLE_LANGUAGE or "None"
        subtitle_encoding = Config.EXTRACT_SUBTITLE_ENCODING or "None"
        subtitle_font = Config.EXTRACT_SUBTITLE_FONT or "None"
        subtitle_font_size = Config.EXTRACT_SUBTITLE_FONT_SIZE or "None"

        # Attachment settings
        attachment_enabled = (
            "✅ Enabled" if Config.EXTRACT_ATTACHMENT_ENABLED else "❌ Disabled"
        )
        attachment_format = Config.EXTRACT_ATTACHMENT_FORMAT or "None"
        attachment_index = Config.EXTRACT_ATTACHMENT_INDEX or "All"
        attachment_filter = Config.EXTRACT_ATTACHMENT_FILTER or "None"

        # Quality settings
        maintain_quality = (
            "✅ Enabled" if Config.EXTRACT_MAINTAIN_QUALITY else "❌ Disabled"
        )

        msg = f"""<b>Extract Settings</b> | State: {state}

<b>General Settings:</b>
• <b>Status:</b> {extract_enabled}
• <b>Priority:</b> <code>{extract_priority}</code>
• <b>Delete Original:</b> {delete_original}

<b>Video Extract Settings:</b>
• <b>Status:</b> {video_enabled}
• <b>Codec:</b> <code>{video_codec}</code>
• <b>Format:</b> <code>{video_format}</code>
• <b>Index:</b> <code>{video_index}</code>
• <b>Quality:</b> <code>{video_quality}</code>
• <b>Preset:</b> <code>{video_preset}</code>
• <b>Bitrate:</b> <code>{video_bitrate}</code>
• <b>Resolution:</b> <code>{video_resolution}</code>
• <b>FPS:</b> <code>{video_fps}</code>

<b>Audio Extract Settings:</b>
• <b>Status:</b> {audio_enabled}
• <b>Codec:</b> <code>{audio_codec}</code>
• <b>Format:</b> <code>{audio_format}</code>
• <b>Index:</b> <code>{audio_index}</code>
• <b>Bitrate:</b> <code>{audio_bitrate}</code>
• <b>Channels:</b> <code>{audio_channels}</code>
• <b>Sampling:</b> <code>{audio_sampling}</code>
• <b>Volume:</b> <code>{audio_volume}</code>

<b>Subtitle Extract Settings:</b>
• <b>Status:</b> {subtitle_enabled}
• <b>Codec:</b> <code>{subtitle_codec}</code>
• <b>Format:</b> <code>{subtitle_format}</code>
• <b>Index:</b> <code>{subtitle_index}</code>
• <b>Language:</b> <code>{subtitle_language}</code>
• <b>Encoding:</b> <code>{subtitle_encoding}</code>
• <b>Font:</b> <code>{subtitle_font}</code>
• <b>Font Size:</b> <code>{subtitle_font_size}</code>

<b>Attachment Extract Settings:</b>
• <b>Status:</b> {attachment_enabled}
• <b>Format:</b> <code>{attachment_format}</code>
• <b>Index:</b> <code>{attachment_index}</code>
• <b>Filter:</b> <code>{attachment_filter}</code>

<b>Quality Settings:</b>
• <b>Maintain Quality:</b> {maintain_quality}

<b>Usage:</b>
• Main Extract toggle must be enabled
• Media type specific toggles must be enabled for respective extractions
• Use <code>-extract</code> to enable extraction
• Use <code>-extract-video</code>, <code>-extract-audio</code>, etc. for specific track types
• Use <code>-extract-video-index 0</code> to extract specific track by index
• Add <code>-del</code> to delete original files after extraction

Configure global extract settings that will be used when user settings are not available."""

    elif key == "mediatools_compression":
        # Add buttons for compression settings
        # General compression settings
        general_settings = [
            "COMPRESSION_ENABLED",
            "COMPRESSION_PRIORITY",
            "COMPRESSION_DELETE_ORIGINAL",
        ]

        # Video compression settings
        video_settings = [
            "COMPRESSION_VIDEO_ENABLED",
            "COMPRESSION_VIDEO_PRESET",
            "COMPRESSION_VIDEO_CRF",
            "COMPRESSION_VIDEO_CODEC",
            "COMPRESSION_VIDEO_TUNE",
            "COMPRESSION_VIDEO_PIXEL_FORMAT",
            "COMPRESSION_VIDEO_FORMAT",
        ]

        # Audio compression settings
        audio_settings = [
            "COMPRESSION_AUDIO_ENABLED",
            "COMPRESSION_AUDIO_PRESET",
            "COMPRESSION_AUDIO_CODEC",
            "COMPRESSION_AUDIO_BITRATE",
            "COMPRESSION_AUDIO_CHANNELS",
            "COMPRESSION_AUDIO_FORMAT",
        ]

        # Image compression settings
        image_settings = [
            "COMPRESSION_IMAGE_ENABLED",
            "COMPRESSION_IMAGE_PRESET",
            "COMPRESSION_IMAGE_QUALITY",
            "COMPRESSION_IMAGE_RESIZE",
            "COMPRESSION_IMAGE_FORMAT",
        ]

        # Document compression settings
        document_settings = [
            "COMPRESSION_DOCUMENT_ENABLED",
            "COMPRESSION_DOCUMENT_PRESET",
            "COMPRESSION_DOCUMENT_DPI",
            "COMPRESSION_DOCUMENT_FORMAT",
        ]

        # Subtitle compression settings
        subtitle_settings = [
            "COMPRESSION_SUBTITLE_ENABLED",
            "COMPRESSION_SUBTITLE_PRESET",
            "COMPRESSION_SUBTITLE_ENCODING",
            "COMPRESSION_SUBTITLE_FORMAT",
        ]

        # Archive compression settings
        archive_settings = [
            "COMPRESSION_ARCHIVE_ENABLED",
            "COMPRESSION_ARCHIVE_PRESET",
            "COMPRESSION_ARCHIVE_LEVEL",
            "COMPRESSION_ARCHIVE_METHOD",
            "COMPRESSION_ARCHIVE_FORMAT",
        ]

        # Combine all settings
        compression_settings = (
            general_settings
            + video_settings
            + audio_settings
            + image_settings
            + document_settings
            + subtitle_settings
            + archive_settings
        )

        for setting in compression_settings:
            # Create display name based on setting type
            if setting.startswith("COMPRESSION_VIDEO_"):
                display_name = (
                    "Video "
                    + setting.replace("COMPRESSION_VIDEO_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("COMPRESSION_AUDIO_"):
                display_name = (
                    "Audio "
                    + setting.replace("COMPRESSION_AUDIO_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("COMPRESSION_IMAGE_"):
                display_name = (
                    "Image "
                    + setting.replace("COMPRESSION_IMAGE_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("COMPRESSION_DOCUMENT_"):
                display_name = (
                    "Document "
                    + setting.replace("COMPRESSION_DOCUMENT_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("COMPRESSION_SUBTITLE_"):
                display_name = (
                    "Subtitle "
                    + setting.replace("COMPRESSION_SUBTITLE_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("COMPRESSION_ARCHIVE_"):
                display_name = (
                    "Archive "
                    + setting.replace("COMPRESSION_ARCHIVE_", "")
                    .replace("_", " ")
                    .title()
                )
            else:
                display_name = (
                    setting.replace("COMPRESSION_", "").replace("_", " ").title()
                )

            # For boolean settings, add toggle buttons
            if setting in [
                "COMPRESSION_ENABLED",
                "COMPRESSION_DELETE_ORIGINAL",
                "COMPRESSION_VIDEO_ENABLED",
                "COMPRESSION_AUDIO_ENABLED",
                "COMPRESSION_IMAGE_ENABLED",
                "COMPRESSION_DOCUMENT_ENABLED",
                "COMPRESSION_SUBTITLE_ENABLED",
                "COMPRESSION_ARCHIVE_ENABLED",
            ]:
                setting_value = getattr(Config, setting, False)
                status = "✅ ON" if setting_value else "❌ OFF"

                # Format display name with status
                if setting == "COMPRESSION_ENABLED":
                    display_name = f"Enabled: {status}"
                elif setting == "COMPRESSION_DELETE_ORIGINAL":
                    display_name = f"Delete Original: {status}"
                elif setting == "COMPRESSION_VIDEO_ENABLED":
                    display_name = f"Video Enabled: {status}"
                elif setting == "COMPRESSION_AUDIO_ENABLED":
                    display_name = f"Audio Enabled: {status}"
                elif setting == "COMPRESSION_IMAGE_ENABLED":
                    display_name = f"Image Enabled: {status}"
                elif setting == "COMPRESSION_DOCUMENT_ENABLED":
                    display_name = f"Document Enabled: {status}"
                elif setting == "COMPRESSION_SUBTITLE_ENABLED":
                    display_name = f"Subtitle Enabled: {status}"
                elif setting == "COMPRESSION_ARCHIVE_ENABLED":
                    display_name = f"Archive Enabled: {status}"
                else:
                    display_name = f"{display_name}: {status}"

                # Create toggle button
                buttons.data_button(
                    display_name,
                    f"botset toggle {setting} {not setting_value}",
                )
                continue

            # For non-boolean settings, use editvar
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_compression")
        else:
            buttons.data_button("View", "botset view mediatools_compression")

        buttons.data_button("Default", "botset default_compression")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current compression settings
        compression_enabled = (
            "✅ Enabled" if Config.COMPRESSION_ENABLED else "❌ Disabled"
        )
        compression_priority = f"{Config.COMPRESSION_PRIORITY}"
        compression_delete_original = (
            "✅ Enabled" if Config.COMPRESSION_DELETE_ORIGINAL else "❌ Disabled"
        )

        # Video settings
        video_enabled = (
            "✅ Enabled" if Config.COMPRESSION_VIDEO_ENABLED else "❌ Disabled"
        )
        video_preset = Config.COMPRESSION_VIDEO_PRESET
        video_crf = Config.COMPRESSION_VIDEO_CRF
        video_codec = Config.COMPRESSION_VIDEO_CODEC
        video_tune = Config.COMPRESSION_VIDEO_TUNE
        video_pixel_format = Config.COMPRESSION_VIDEO_PIXEL_FORMAT
        video_format = Config.COMPRESSION_VIDEO_FORMAT

        # Audio settings
        audio_enabled = (
            "✅ Enabled" if Config.COMPRESSION_AUDIO_ENABLED else "❌ Disabled"
        )
        audio_preset = Config.COMPRESSION_AUDIO_PRESET
        audio_codec = Config.COMPRESSION_AUDIO_CODEC
        audio_bitrate = Config.COMPRESSION_AUDIO_BITRATE
        audio_channels = Config.COMPRESSION_AUDIO_CHANNELS
        audio_format = Config.COMPRESSION_AUDIO_FORMAT

        # Image settings
        image_enabled = (
            "✅ Enabled" if Config.COMPRESSION_IMAGE_ENABLED else "❌ Disabled"
        )
        image_preset = Config.COMPRESSION_IMAGE_PRESET
        image_quality = Config.COMPRESSION_IMAGE_QUALITY
        image_resize = Config.COMPRESSION_IMAGE_RESIZE
        image_format = Config.COMPRESSION_IMAGE_FORMAT

        # Document settings
        document_enabled = (
            "✅ Enabled" if Config.COMPRESSION_DOCUMENT_ENABLED else "❌ Disabled"
        )
        document_preset = Config.COMPRESSION_DOCUMENT_PRESET
        document_dpi = Config.COMPRESSION_DOCUMENT_DPI
        document_format = Config.COMPRESSION_DOCUMENT_FORMAT

        # Subtitle settings
        subtitle_enabled = (
            "✅ Enabled" if Config.COMPRESSION_SUBTITLE_ENABLED else "❌ Disabled"
        )
        subtitle_preset = Config.COMPRESSION_SUBTITLE_PRESET
        subtitle_encoding = Config.COMPRESSION_SUBTITLE_ENCODING
        subtitle_format = Config.COMPRESSION_SUBTITLE_FORMAT

        # Archive settings
        archive_enabled = (
            "✅ Enabled" if Config.COMPRESSION_ARCHIVE_ENABLED else "❌ Disabled"
        )
        archive_preset = Config.COMPRESSION_ARCHIVE_PRESET
        archive_level = Config.COMPRESSION_ARCHIVE_LEVEL
        archive_method = Config.COMPRESSION_ARCHIVE_METHOD
        archive_format = Config.COMPRESSION_ARCHIVE_FORMAT

        msg = f"""<b>Compression Settings</b> | State: {state}

<b>General Settings:</b>
• <b>Status:</b> {compression_enabled}
• <b>Priority:</b> <code>{compression_priority}</code>
• <b>Delete Original:</b> {compression_delete_original}

<b>Video Compression Settings:</b>
• <b>Status:</b> {video_enabled}
• <b>Preset:</b> <code>{video_preset}</code>
• <b>CRF:</b> <code>{video_crf}</code>
• <b>Codec:</b> <code>{video_codec}</code>
• <b>Tune:</b> <code>{video_tune}</code>
• <b>Pixel Format:</b> <code>{video_pixel_format}</code>
• <b>Format:</b> <code>{video_format}</code>

<b>Audio Compression Settings:</b>
• <b>Status:</b> {audio_enabled}
• <b>Preset:</b> <code>{audio_preset}</code>
• <b>Codec:</b> <code>{audio_codec}</code>
• <b>Bitrate:</b> <code>{audio_bitrate}</code>
• <b>Channels:</b> <code>{audio_channels}</code>
• <b>Format:</b> <code>{audio_format}</code>

<b>Image Compression Settings:</b>
• <b>Status:</b> {image_enabled}
• <b>Preset:</b> <code>{image_preset}</code>
• <b>Quality:</b> <code>{image_quality}</code>
• <b>Resize:</b> <code>{image_resize}</code>
• <b>Format:</b> <code>{image_format}</code>

<b>Document Compression Settings:</b>
• <b>Status:</b> {document_enabled}
• <b>Preset:</b> <code>{document_preset}</code>
• <b>DPI:</b> <code>{document_dpi}</code>
• <b>Format:</b> <code>{document_format}</code>

<b>Subtitle Compression Settings:</b>
• <b>Status:</b> {subtitle_enabled}
• <b>Preset:</b> <code>{subtitle_preset}</code>
• <b>Encoding:</b> <code>{subtitle_encoding}</code>
• <b>Format:</b> <code>{subtitle_format}</code>

<b>Archive Compression Settings:</b>
• <b>Status:</b> {archive_enabled}
• <b>Preset:</b> <code>{archive_preset}</code>
• <b>Level:</b> <code>{archive_level}</code>
• <b>Method:</b> <code>{archive_method}</code>
• <b>Format:</b> <code>{archive_format}</code>

<b>Usage:</b>
• Main Compression toggle must be enabled
• Media type specific toggles must be enabled for respective compressions
• Use <code>-video-fast</code>, <code>-audio-medium</code>, etc. for preset flags
• Add <code>-del</code> to delete original files after compression

Configure global compression settings that will be used when user settings are not available."""

    elif key == "mediatools_convert":
        # Add buttons for convert settings
        # General convert settings
        general_settings = [
            "CONVERT_ENABLED",
            "CONVERT_PRIORITY",
            "CONVERT_DELETE_ORIGINAL",
        ]

        # Video convert settings
        video_settings = [
            "CONVERT_VIDEO_ENABLED",
            "CONVERT_VIDEO_FORMAT",
            "CONVERT_VIDEO_CODEC",
            "CONVERT_VIDEO_QUALITY",
            "CONVERT_VIDEO_CRF",
            "CONVERT_VIDEO_PRESET",
            "CONVERT_VIDEO_MAINTAIN_QUALITY",
            "CONVERT_VIDEO_RESOLUTION",
            "CONVERT_VIDEO_FPS",
        ]

        # Audio convert settings
        audio_settings = [
            "CONVERT_AUDIO_ENABLED",
            "CONVERT_AUDIO_FORMAT",
            "CONVERT_AUDIO_CODEC",
            "CONVERT_AUDIO_BITRATE",
            "CONVERT_AUDIO_CHANNELS",
            "CONVERT_AUDIO_SAMPLING",
            "CONVERT_AUDIO_VOLUME",
        ]

        # Subtitle convert settings
        subtitle_settings = [
            "CONVERT_SUBTITLE_ENABLED",
            "CONVERT_SUBTITLE_FORMAT",
            "CONVERT_SUBTITLE_ENCODING",
            "CONVERT_SUBTITLE_LANGUAGE",
        ]

        # Document convert settings
        document_settings = [
            "CONVERT_DOCUMENT_ENABLED",
            "CONVERT_DOCUMENT_FORMAT",
            "CONVERT_DOCUMENT_QUALITY",
            "CONVERT_DOCUMENT_DPI",
        ]

        # Archive convert settings
        archive_settings = [
            "CONVERT_ARCHIVE_ENABLED",
            "CONVERT_ARCHIVE_FORMAT",
            "CONVERT_ARCHIVE_LEVEL",
            "CONVERT_ARCHIVE_METHOD",
        ]

        # Combine all settings
        convert_settings = (
            general_settings
            + video_settings
            + audio_settings
            + subtitle_settings
            + document_settings
            + archive_settings
        )

        for setting in convert_settings:
            # Create display name based on setting type
            if setting.startswith("CONVERT_VIDEO_"):
                display_name = (
                    "Video "
                    + setting.replace("CONVERT_VIDEO_", "").replace("_", " ").title()
                )
            elif setting.startswith("CONVERT_AUDIO_"):
                display_name = (
                    "Audio "
                    + setting.replace("CONVERT_AUDIO_", "").replace("_", " ").title()
                )
            elif setting.startswith("CONVERT_SUBTITLE_"):
                display_name = (
                    "Subtitle "
                    + setting.replace("CONVERT_SUBTITLE_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("CONVERT_DOCUMENT_"):
                display_name = (
                    "Document "
                    + setting.replace("CONVERT_DOCUMENT_", "")
                    .replace("_", " ")
                    .title()
                )
            elif setting.startswith("CONVERT_ARCHIVE_"):
                display_name = (
                    "Archive "
                    + setting.replace("CONVERT_ARCHIVE_", "")
                    .replace("_", " ")
                    .title()
                )
            else:
                display_name = (
                    setting.replace("CONVERT_", "").replace("_", " ").title()
                )

            # For boolean settings, add toggle buttons
            if setting in [
                "CONVERT_ENABLED",
                "CONVERT_DELETE_ORIGINAL",
                "CONVERT_VIDEO_ENABLED",
                "CONVERT_VIDEO_MAINTAIN_QUALITY",
                "CONVERT_AUDIO_ENABLED",
                "CONVERT_SUBTITLE_ENABLED",
                "CONVERT_DOCUMENT_ENABLED",
                "CONVERT_ARCHIVE_ENABLED",
            ]:
                setting_value = getattr(Config, setting, False)
                status = "✅ ON" if setting_value else "❌ OFF"

                # Format display name with status
                if setting == "CONVERT_ENABLED":
                    display_name = f"Enabled: {status}"
                elif setting == "CONVERT_DELETE_ORIGINAL":
                    display_name = f"Delete Original: {status}"
                elif setting == "CONVERT_VIDEO_ENABLED":
                    display_name = f"Video Enabled: {status}"
                elif setting == "CONVERT_AUDIO_ENABLED":
                    display_name = f"Audio Enabled: {status}"
                elif setting == "CONVERT_SUBTITLE_ENABLED":
                    display_name = f"Subtitle Enabled: {status}"
                elif setting == "CONVERT_DOCUMENT_ENABLED":
                    display_name = f"Document Enabled: {status}"
                elif setting == "CONVERT_ARCHIVE_ENABLED":
                    display_name = f"Archive Enabled: {status}"
                else:
                    display_name = f"{display_name}: {status}"

                # Create toggle button
                buttons.data_button(
                    display_name,
                    f"botset toggle {setting} {not setting_value}",
                )
                continue

            # For non-boolean settings, use editvar
            buttons.data_button(display_name, f"botset editvar {setting}")

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_convert")
        else:
            buttons.data_button("View", "botset view mediatools_convert")

        buttons.data_button("Default", "botset default_convert")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current convert settings
        convert_enabled = "✅ Enabled" if Config.CONVERT_ENABLED else "❌ Disabled"
        convert_priority = f"{Config.CONVERT_PRIORITY}"
        convert_delete_original = (
            "✅ Enabled" if Config.CONVERT_DELETE_ORIGINAL else "❌ Disabled"
        )

        # Video settings
        video_enabled = (
            "✅ Enabled" if Config.CONVERT_VIDEO_ENABLED else "❌ Disabled"
        )
        video_format = Config.CONVERT_VIDEO_FORMAT
        video_codec = Config.CONVERT_VIDEO_CODEC
        video_quality = Config.CONVERT_VIDEO_QUALITY
        video_crf = Config.CONVERT_VIDEO_CRF
        video_preset = Config.CONVERT_VIDEO_PRESET
        video_maintain_quality = (
            "✅ Enabled" if Config.CONVERT_VIDEO_MAINTAIN_QUALITY else "❌ Disabled"
        )
        video_resolution = Config.CONVERT_VIDEO_RESOLUTION
        video_fps = Config.CONVERT_VIDEO_FPS

        # Audio settings
        audio_enabled = (
            "✅ Enabled" if Config.CONVERT_AUDIO_ENABLED else "❌ Disabled"
        )
        audio_format = Config.CONVERT_AUDIO_FORMAT
        audio_codec = Config.CONVERT_AUDIO_CODEC
        audio_bitrate = Config.CONVERT_AUDIO_BITRATE
        audio_channels = Config.CONVERT_AUDIO_CHANNELS
        audio_sampling = Config.CONVERT_AUDIO_SAMPLING
        audio_volume = Config.CONVERT_AUDIO_VOLUME

        # Subtitle settings
        subtitle_enabled = (
            "✅ Enabled" if Config.CONVERT_SUBTITLE_ENABLED else "❌ Disabled"
        )
        subtitle_format = Config.CONVERT_SUBTITLE_FORMAT
        subtitle_encoding = Config.CONVERT_SUBTITLE_ENCODING
        subtitle_language = Config.CONVERT_SUBTITLE_LANGUAGE

        # Document settings
        document_enabled = (
            "✅ Enabled" if Config.CONVERT_DOCUMENT_ENABLED else "❌ Disabled"
        )
        document_format = Config.CONVERT_DOCUMENT_FORMAT
        document_quality = Config.CONVERT_DOCUMENT_QUALITY
        document_dpi = Config.CONVERT_DOCUMENT_DPI

        # Archive settings
        archive_enabled = (
            "✅ Enabled" if Config.CONVERT_ARCHIVE_ENABLED else "❌ Disabled"
        )
        archive_format = Config.CONVERT_ARCHIVE_FORMAT
        archive_level = Config.CONVERT_ARCHIVE_LEVEL
        archive_method = Config.CONVERT_ARCHIVE_METHOD

        msg = f"""<b>Convert Settings</b> | State: {state}

<b>General Settings:</b>
• <b>Status:</b> {convert_enabled}
• <b>Priority:</b> <code>{convert_priority}</code>
• <b>Delete Original:</b> {convert_delete_original}

<b>Video Convert Settings:</b>
• <b>Status:</b> {video_enabled}
• <b>Format:</b> <code>{video_format}</code>
• <b>Codec:</b> <code>{video_codec}</code>
• <b>Quality:</b> <code>{video_quality}</code>
• <b>CRF:</b> <code>{video_crf}</code>
• <b>Preset:</b> <code>{video_preset}</code>
• <b>Maintain Quality:</b> {video_maintain_quality}
• <b>Resolution:</b> <code>{video_resolution}</code>
• <b>FPS:</b> <code>{video_fps}</code>

<b>Audio Convert Settings:</b>
• <b>Status:</b> {audio_enabled}
• <b>Format:</b> <code>{audio_format}</code>
• <b>Codec:</b> <code>{audio_codec}</code>
• <b>Bitrate:</b> <code>{audio_bitrate}</code>
• <b>Channels:</b> <code>{audio_channels}</code>
• <b>Sampling:</b> <code>{audio_sampling}</code>
• <b>Volume:</b> <code>{audio_volume}</code>

<b>Subtitle Convert Settings:</b>
• <b>Status:</b> {subtitle_enabled}
• <b>Format:</b> <code>{subtitle_format}</code>
• <b>Encoding:</b> <code>{subtitle_encoding}</code>
• <b>Language:</b> <code>{subtitle_language}</code>

<b>Document Convert Settings:</b>
• <b>Status:</b> {document_enabled}
• <b>Format:</b> <code>{document_format}</code>
• <b>Quality:</b> <code>{document_quality}</code>
• <b>DPI:</b> <code>{document_dpi}</code>

<b>Archive Convert Settings:</b>
• <b>Status:</b> {archive_enabled}
• <b>Format:</b> <code>{archive_format}</code>
• <b>Level:</b> <code>{archive_level}</code>
• <b>Method:</b> <code>{archive_method}</code>

<b>Usage:</b>
• Main Convert toggle must be enabled
• Media type specific toggles must be enabled for respective conversions
• Use <code>-cv format</code> for video conversion (e.g., <code>-cv mp4</code>)
• Use <code>-ca format</code> for audio conversion (e.g., <code>-ca mp3</code>)
• Use <code>-cs format</code> for subtitle conversion (e.g., <code>-cs srt</code>)
• Use <code>-cd format</code> for document conversion (e.g., <code>-cd pdf</code>)
• Use <code>-cr format</code> for archive conversion (e.g., <code>-cr zip</code>)
• Add <code>-del</code> to delete original files after conversion

Configure global convert settings that will be used when user settings are not available."""

    elif key == "mediatools_metadata":
        # Add buttons for each metadata setting in a 2-column layout
        # Global metadata settings
        global_settings = [
            "METADATA_ALL",
            "METADATA_TITLE",
            "METADATA_AUTHOR",
            "METADATA_COMMENT",
        ]

        # Video metadata settings
        video_settings = [
            "METADATA_VIDEO_TITLE",
            "METADATA_VIDEO_AUTHOR",
            "METADATA_VIDEO_COMMENT",
        ]

        # Audio metadata settings
        audio_settings = [
            "METADATA_AUDIO_TITLE",
            "METADATA_AUDIO_AUTHOR",
            "METADATA_AUDIO_COMMENT",
        ]

        # Subtitle metadata settings
        subtitle_settings = [
            "METADATA_SUBTITLE_TITLE",
            "METADATA_SUBTITLE_AUTHOR",
            "METADATA_SUBTITLE_COMMENT",
        ]

        # Combine all settings
        metadata_settings = (
            global_settings + video_settings + audio_settings + subtitle_settings
        )

        for setting in metadata_settings:
            # Skip the legacy key
            if setting == "METADATA_KEY":
                continue

            # Create a more user-friendly display name
            if setting == "METADATA_ALL":
                display_name = "All Fields"
            elif setting.startswith("METADATA_VIDEO_"):
                display_name = (
                    "Video " + setting.replace("METADATA_VIDEO_", "").title()
                )
            elif setting.startswith("METADATA_AUDIO_"):
                display_name = (
                    "Audio " + setting.replace("METADATA_AUDIO_", "").title()
                )
            elif setting.startswith("METADATA_SUBTITLE_"):
                display_name = (
                    "Subtitle " + setting.replace("METADATA_SUBTITLE_", "").title()
                )
            else:
                display_name = "Global " + setting.replace("METADATA_", "").title()

            # Always use editvar in both view and edit states to ensure consistent behavior
            callback_data = f"botset editvar {setting}"
            buttons.data_button(display_name, callback_data)

        if state == "view":
            buttons.data_button("Edit", "botset edit mediatools_metadata")
        else:
            buttons.data_button("View", "botset view mediatools_metadata")

        buttons.data_button("Default", "botset default_metadata")

        buttons.data_button("Back", "botset mediatools", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Get current global metadata settings
        metadata_all = Config.METADATA_ALL or "None"
        metadata_title = Config.METADATA_TITLE or "None"
        metadata_author = Config.METADATA_AUTHOR or "None"
        metadata_comment = Config.METADATA_COMMENT or "None"

        # Get current video metadata settings
        metadata_video_title = Config.METADATA_VIDEO_TITLE or "None"
        metadata_video_author = Config.METADATA_VIDEO_AUTHOR or "None"
        metadata_video_comment = Config.METADATA_VIDEO_COMMENT or "None"

        # Get current audio metadata settings
        metadata_audio_title = Config.METADATA_AUDIO_TITLE or "None"
        metadata_audio_author = Config.METADATA_AUDIO_AUTHOR or "None"
        metadata_audio_comment = Config.METADATA_AUDIO_COMMENT or "None"

        # Get current subtitle metadata settings
        metadata_subtitle_title = Config.METADATA_SUBTITLE_TITLE or "None"
        metadata_subtitle_author = Config.METADATA_SUBTITLE_AUTHOR or "None"
        metadata_subtitle_comment = Config.METADATA_SUBTITLE_COMMENT or "None"

        msg = f"""<b>Metadata Settings</b> | State: {state}

<b>Global Settings:</b>
<b>All Fields:</b> <code>{metadata_all}</code>
<b>Global Title:</b> <code>{metadata_title}</code>
<b>Global Author:</b> <code>{metadata_author}</code>
<b>Global Comment:</b> <code>{metadata_comment}</code>

<b>Video Track Settings:</b>
<b>Video Title:</b> <code>{metadata_video_title}</code>
<b>Video Author:</b> <code>{metadata_video_author}</code>
<b>Video Comment:</b> <code>{metadata_video_comment}</code>

<b>Audio Track Settings:</b>
<b>Audio Title:</b> <code>{metadata_audio_title}</code>
<b>Audio Author:</b> <code>{metadata_audio_author}</code>
<b>Audio Comment:</b> <code>{metadata_audio_comment}</code>

<b>Subtitle Track Settings:</b>
<b>Subtitle Title:</b> <code>{metadata_subtitle_title}</code>
<b>Subtitle Author:</b> <code>{metadata_subtitle_author}</code>
<b>Subtitle Comment:</b> <code>{metadata_subtitle_comment}</code>

<b>Note:</b> 'All Fields' takes priority over all other settings when set.

Configure global metadata settings that will be used when user settings are not available."""

    elif key == "mediatools_merge_config":
        # Add buttons for each merge configuration setting in a 2-column layout
        # Group settings by category
        formats = [
            "MERGE_OUTPUT_FORMAT_VIDEO",
            "MERGE_OUTPUT_FORMAT_AUDIO",
            "MERGE_OUTPUT_FORMAT_IMAGE",
            "MERGE_OUTPUT_FORMAT_DOCUMENT",
            "MERGE_OUTPUT_FORMAT_SUBTITLE",
        ]

        video_settings = [
            "MERGE_VIDEO_CODEC",
            "MERGE_VIDEO_QUALITY",
            "MERGE_VIDEO_PRESET",
            "MERGE_VIDEO_CRF",
            "MERGE_VIDEO_PIXEL_FORMAT",
            "MERGE_VIDEO_TUNE",
            "MERGE_VIDEO_FASTSTART",
        ]

        audio_settings = [
            "MERGE_AUDIO_CODEC",
            "MERGE_AUDIO_BITRATE",
            "MERGE_AUDIO_CHANNELS",
            "MERGE_AUDIO_SAMPLING",
            "MERGE_AUDIO_VOLUME",
        ]

        image_settings = [
            "MERGE_IMAGE_MODE",
            "MERGE_IMAGE_COLUMNS",
            "MERGE_IMAGE_QUALITY",
            "MERGE_IMAGE_DPI",
            "MERGE_IMAGE_RESIZE",
            "MERGE_IMAGE_BACKGROUND",
        ]

        subtitle_settings = [
            "MERGE_SUBTITLE_ENCODING",
            "MERGE_SUBTITLE_FONT",
            "MERGE_SUBTITLE_FONT_SIZE",
            "MERGE_SUBTITLE_FONT_COLOR",
            "MERGE_SUBTITLE_BACKGROUND",
        ]

        document_settings = [
            "MERGE_DOCUMENT_PAPER_SIZE",
            "MERGE_DOCUMENT_ORIENTATION",
            "MERGE_DOCUMENT_MARGIN",
        ]

        metadata_settings = [
            "MERGE_METADATA_TITLE",
            "MERGE_METADATA_AUTHOR",
            "MERGE_METADATA_COMMENT",
        ]

        # Combine all settings
        merge_config_settings = (
            formats
            + video_settings
            + audio_settings
            + image_settings
            + subtitle_settings
            + document_settings
            + metadata_settings
        )

        # 5 rows per page, 2 columns = 10 items per page
        items_per_page = 10  # 5 rows * 2 columns
        total_pages = (
            len(merge_config_settings) + items_per_page - 1
        ) // items_per_page

        # Ensure page is valid
        current_page = page
        if current_page >= total_pages:
            current_page = 0
        elif current_page < 0:
            current_page = total_pages - 1

        # Get settings for current page
        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, len(merge_config_settings))
        current_page_settings = merge_config_settings[start_idx:end_idx]

        # Add buttons for each setting on current page
        for setting in current_page_settings:
            display_name = setting.replace("MERGE_", "").replace("_", " ").title()
            buttons.data_button(display_name, f"botset editvar {setting}")

        # Add action buttons in a separate row
        if state == "view":
            buttons.data_button(
                "Edit", "botset edit mediatools_merge_config", "footer"
            )
        else:
            buttons.data_button(
                "View", "botset view mediatools_merge_config", "footer"
            )

        # Add Default button
        buttons.data_button("Default", "botset default_merge_config", "footer")

        # Add navigation buttons
        buttons.data_button("Back", "botset mediatools_merge", "footer")
        buttons.data_button("Close", "botset close", "footer")

        # Add pagination buttons in a separate row below action buttons
        if total_pages > 1:
            for i in range(total_pages):
                # Make the current page button different
                if i == current_page:
                    buttons.data_button(
                        f"[{i + 1}]", f"botset start_merge_config {i}", "page"
                    )
                else:
                    buttons.data_button(
                        str(i + 1), f"botset start_merge_config {i}", "page"
                    )

            # Add a debug log message# Get current merge configuration settings - Output formats
        video_format = Config.MERGE_OUTPUT_FORMAT_VIDEO or "mkv (Default)"
        audio_format = Config.MERGE_OUTPUT_FORMAT_AUDIO or "mp3 (Default)"
        image_format = Config.MERGE_OUTPUT_FORMAT_IMAGE or "jpg (Default)"
        document_format = Config.MERGE_OUTPUT_FORMAT_DOCUMENT or "pdf (Default)"
        subtitle_format = Config.MERGE_OUTPUT_FORMAT_SUBTITLE or "srt (Default)"

        # Video settings
        video_codec = Config.MERGE_VIDEO_CODEC or "copy (Default)"
        video_quality = Config.MERGE_VIDEO_QUALITY or "medium (Default)"
        video_preset = Config.MERGE_VIDEO_PRESET or "medium (Default)"
        video_crf = Config.MERGE_VIDEO_CRF or "23 (Default)"
        video_pixel_format = Config.MERGE_VIDEO_PIXEL_FORMAT or "yuv420p (Default)"
        video_tune = Config.MERGE_VIDEO_TUNE or "film (Default)"
        video_faststart = "Enabled" if Config.MERGE_VIDEO_FASTSTART else "Disabled"

        # Audio settings
        audio_codec = Config.MERGE_AUDIO_CODEC or "copy (Default)"
        audio_bitrate = Config.MERGE_AUDIO_BITRATE or "192k (Default)"
        audio_channels = Config.MERGE_AUDIO_CHANNELS or "2 (Default)"
        audio_sampling = Config.MERGE_AUDIO_SAMPLING or "44100 (Default)"
        audio_volume = Config.MERGE_AUDIO_VOLUME or "1.0 (Default)"

        # Image settings
        image_mode = Config.MERGE_IMAGE_MODE or "auto (Default)"
        image_columns = Config.MERGE_IMAGE_COLUMNS or "2 (Default)"
        image_quality = Config.MERGE_IMAGE_QUALITY or "90 (Default)"
        image_dpi = Config.MERGE_IMAGE_DPI or "300 (Default)"
        image_resize = Config.MERGE_IMAGE_RESIZE or "none (Default)"
        image_background = Config.MERGE_IMAGE_BACKGROUND or "white (Default)"

        # Subtitle settings
        subtitle_encoding = Config.MERGE_SUBTITLE_ENCODING or "utf-8 (Default)"
        subtitle_font = Config.MERGE_SUBTITLE_FONT or "Arial (Default)"
        subtitle_font_size = Config.MERGE_SUBTITLE_FONT_SIZE or "24 (Default)"
        subtitle_font_color = Config.MERGE_SUBTITLE_FONT_COLOR or "white (Default)"
        subtitle_background = Config.MERGE_SUBTITLE_BACKGROUND or "black (Default)"

        # Document settings
        document_paper_size = Config.MERGE_DOCUMENT_PAPER_SIZE or "a4 (Default)"
        document_orientation = (
            Config.MERGE_DOCUMENT_ORIENTATION or "portrait (Default)"
        )
        document_margin = Config.MERGE_DOCUMENT_MARGIN or "50 (Default)"

        # Metadata settings
        metadata_title = Config.MERGE_METADATA_TITLE or "(Default: empty)"
        metadata_author = Config.MERGE_METADATA_AUTHOR or "(Default: empty)"
        metadata_comment = Config.MERGE_METADATA_COMMENT or "(Default: empty)"

        msg = f"""<b>Merge Configuration</b> | State: {state}

<b>Output Formats:</b>
• <b>Video:</b> <code>{video_format}</code>
• <b>Audio:</b> <code>{audio_format}</code>
• <b>Image:</b> <code>{image_format}</code>
• <b>Document:</b> <code>{document_format}</code>
• <b>Subtitle:</b> <code>{subtitle_format}</code>

<b>Video Settings:</b>
• <b>Codec:</b> <code>{video_codec}</code>
• <b>Quality:</b> <code>{video_quality}</code>
• <b>Preset:</b> <code>{video_preset}</code>
• <b>CRF:</b> <code>{video_crf}</code>
• <b>Pixel Format:</b> <code>{video_pixel_format}</code>
• <b>Tune:</b> <code>{video_tune}</code>
• <b>Faststart:</b> <code>{video_faststart}</code>

<b>Audio Settings:</b>
• <b>Codec:</b> <code>{audio_codec}</code>
• <b>Bitrate:</b> <code>{audio_bitrate}</code>
• <b>Channels:</b> <code>{audio_channels}</code>
• <b>Sampling:</b> <code>{audio_sampling}</code>
• <b>Volume:</b> <code>{audio_volume}</code>

<b>Image Settings:</b>
• <b>Mode:</b> <code>{image_mode}</code>
• <b>Columns:</b> <code>{image_columns}</code>
• <b>Quality:</b> <code>{image_quality}</code>
• <b>DPI:</b> <code>{image_dpi}</code>
• <b>Resize:</b> <code>{image_resize}</code>
• <b>Background:</b> <code>{image_background}</code>

<b>Subtitle Settings:</b>
• <b>Encoding:</b> <code>{subtitle_encoding}</code>
• <b>Font:</b> <code>{subtitle_font}</code>
• <b>Font Size:</b> <code>{subtitle_font_size}</code>
• <b>Font Color:</b> <code>{subtitle_font_color}</code>
• <b>Background:</b> <code>{subtitle_background}</code>

<b>Document Settings:</b>
• <b>Paper Size:</b> <code>{document_paper_size}</code>
• <b>Orientation:</b> <code>{document_orientation}</code>
• <b>Margin:</b> <code>{document_margin}</code>

<b>Metadata:</b>
• <b>Title:</b> <code>{metadata_title}</code>
• <b>Author:</b> <code>{metadata_author}</code>
• <b>Comment:</b> <code>{metadata_comment}</code>

Configure advanced merge settings that will be used when user settings are not available."""

        # Determine which category is shown on the current page
        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, len(merge_config_settings))

        # Get the categories shown on the current page
        categories = []
        if any(
            setting in formats
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Formats")
        if any(
            setting in video_settings
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Video")
        if any(
            setting in audio_settings
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Audio")
        if any(
            setting in image_settings
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Image")
        if any(
            setting in subtitle_settings
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Subtitle")
        if any(
            setting in document_settings
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Document")
        if any(
            setting in metadata_settings
            for setting in merge_config_settings[start_idx:end_idx]
        ):
            categories.append("Metadata")

        category_text = ", ".join(categories)

        # Add category and page info to message
        msg += f"\n\nCurrent page shows: {category_text} settings."
        if total_pages > 1:
            msg += f"\n<b>Page:</b> {current_page + 1}/{total_pages}"

    if key is None:
        button = buttons.build_menu(1)
    elif key in {"mediatools_merge", "mediatools_merge_config"}:
        # Build the menu with 2 columns for settings, 4 columns for action buttons, and 8 columns for pagination
        button = buttons.build_menu(2, 8, 4, 8)
    elif key in {"mediatools_watermark", "mediatools_convert"}:
        # Build the menu with 2 columns for settings
        button = buttons.build_menu(2)
    else:
        button = buttons.build_menu(2)
    return msg, button


async def update_buttons(message, key=None, edit_type=None, page=0):
    user_id = message.chat.id
    LOGGER.debug(
        f"Updating buttons for user {user_id} with key {key}, edit_type {edit_type}"
    )

    msg, button = await get_buttons(key, edit_type, page, user_id)
    await edit_message(message, msg, button)


@new_task
async def edit_variable(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
        if key == "INCOMPLETE_TASK_NOTIFIER" and Config.DATABASE_URL:
            await database.trunc_table("tasks")
    elif key == "TORRENT_TIMEOUT":
        await TorrentManager.change_aria2_option("bt-stop-timeout", value)
        value = int(value)
    elif key == "LEECH_SPLIT_SIZE":
        # Always use owner's session for max split size calculation
        max_split_size = (
            TgClient.MAX_SPLIT_SIZE
            if hasattr(Config, "USER_SESSION_STRING") and Config.USER_SESSION_STRING
            else 2097152000
        )
        value = min(int(value), max_split_size)
    elif key == "LEECH_FILENAME_CAPTION":
        # Check if caption exceeds Telegram's limit (1024 characters)
        if len(value) > 1024:
            error_msg = await send_message(
                message,
                "❌ Error: Caption exceeds Telegram's limit of 1024 characters. Please use a shorter caption.",
            )
            # Auto-delete error message after 5 minutes
            create_task(auto_delete_message(error_msg, time=300))
            return
    elif key == "LEECH_FILENAME":
        # No specific validation needed for LEECH_FILENAME
        pass
    elif key in {
        "WATERMARK_SIZE",
        "WATERMARK_THREAD_NUMBER",
        "MERGE_THREAD_NUMBER",
        "MERGE_PRIORITY",
        "MERGE_VIDEO_CRF",
        "MERGE_IMAGE_COLUMNS",
        "MERGE_IMAGE_QUALITY",
        "MERGE_IMAGE_DPI",
        "MERGE_SUBTITLE_FONT_SIZE",
        "MERGE_DOCUMENT_MARGIN",
        "MERGE_AUDIO_CHANNELS",
        "CONVERT_PRIORITY",
        "CONVERT_VIDEO_CRF",
        "CONVERT_AUDIO_CHANNELS",
        "CONVERT_AUDIO_SAMPLING",
        "TASK_MONITOR_INTERVAL",
        "TASK_MONITOR_CONSECUTIVE_CHECKS",
        "TASK_MONITOR_SPEED_THRESHOLD",
        "TASK_MONITOR_ELAPSED_THRESHOLD",
        "TASK_MONITOR_ETA_THRESHOLD",
        "TASK_MONITOR_WAIT_TIME",
        "TASK_MONITOR_COMPLETION_THRESHOLD",
        "TASK_MONITOR_CPU_HIGH",
        "TASK_MONITOR_CPU_LOW",
        "TASK_MONITOR_MEMORY_HIGH",
        "TASK_MONITOR_MEMORY_LOW",
    }:
        try:
            value = int(value)
        except ValueError:
            # Use appropriate default values based on the key
            if key == "WATERMARK_SIZE":
                value = 20
            elif key in {"WATERMARK_THREAD_NUMBER", "MERGE_THREAD_NUMBER"}:
                value = 4
            elif key == "MERGE_PRIORITY":
                value = 1
            elif key == "MERGE_VIDEO_CRF":
                value = 23
            elif key == "MERGE_IMAGE_COLUMNS":
                value = 2
            elif key == "MERGE_IMAGE_QUALITY":
                value = 90
            elif key == "MERGE_IMAGE_DPI":
                value = 300
            elif key == "MERGE_SUBTITLE_FONT_SIZE":
                value = 24
            elif key == "MERGE_DOCUMENT_MARGIN":
                value = 50
            elif key == "MERGE_AUDIO_CHANNELS":
                value = 2
            elif key == "CONVERT_PRIORITY":
                value = 3
            elif key == "CONVERT_VIDEO_CRF":
                value = 23
            elif key == "CONVERT_AUDIO_CHANNELS":
                value = 2
            elif key == "CONVERT_AUDIO_SAMPLING":
                value = 44100
            elif key == "TASK_MONITOR_INTERVAL":
                value = 60
            elif key == "TASK_MONITOR_CONSECUTIVE_CHECKS":
                value = 3
            elif key == "TASK_MONITOR_SPEED_THRESHOLD":
                value = 50
            elif key == "TASK_MONITOR_ELAPSED_THRESHOLD":
                value = 3600
            elif key == "TASK_MONITOR_ETA_THRESHOLD":
                value = 86400
            elif key == "TASK_MONITOR_WAIT_TIME":
                value = 600
            elif key == "TASK_MONITOR_COMPLETION_THRESHOLD":
                value = 14400
            elif key == "TASK_MONITOR_CPU_HIGH":
                value = 90
            elif key == "TASK_MONITOR_CPU_LOW":
                value = 40
            elif key == "TASK_MONITOR_MEMORY_HIGH":
                value = 75
            elif key == "TASK_MONITOR_MEMORY_LOW":
                value = 60
    elif key == "WATERMARK_OPACITY":
        try:
            value = float(value)
            # Ensure opacity is between 0.0 and 1.0
            value = max(0.0, min(1.0, value))
        except ValueError:
            value = 1.0  # Default opacity if invalid input
    elif key == "AUDIO_WATERMARK_VOLUME":
        try:
            value = float(value)
            # Ensure volume is between 0.0 and 1.0
            value = max(0.0, min(1.0, value))
        except ValueError:
            value = 0.3  # Default volume if invalid input
    elif key in {"MERGE_AUDIO_VOLUME", "CONVERT_AUDIO_VOLUME"}:
        try:
            value = float(value)
        except ValueError:
            value = 1.0  # Default volume if invalid input
    elif key == "WATERMARK_POSITION" and value not in [
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
        "center",
    ]:
        value = "top_left"  # Default position if invalid input
    elif key == "SUBTITLE_WATERMARK_STYLE" and value not in [
        "normal",
        "bold",
        "italic",
        "underline",
    ]:
        value = "normal"  # Default style if invalid input
    elif key == "EXCLUDED_EXTENSIONS":
        fx = value.split()
        excluded_extensions.clear()
        excluded_extensions.extend(["aria2", "!qB"])
        for x in fx:
            x = x.lstrip(".")
            excluded_extensions.append(x.strip().lower())
    elif key == "GDRIVE_ID":
        if drives_names and drives_names[0] == "Main":
            drives_ids[0] = value
        else:
            drives_ids.insert(0, value)
    elif key == "INDEX_URL":
        if drives_names and drives_names[0] == "Main":
            index_urls[0] = value
        else:
            index_urls.insert(0, value)
    elif key == "AUTHORIZED_CHATS":
        aid = value.split()
        auth_chats.clear()
        for id_ in aid:
            chat_id, *thread_ids = id_.split("|")
            chat_id = int(chat_id.strip())
            if thread_ids:
                thread_ids = [int(x.strip()) for x in thread_ids]
                auth_chats[chat_id] = thread_ids
            else:
                auth_chats[chat_id] = []
    elif key == "SUDO_USERS":
        sudo_users.clear()
        aid = value.split()
        for id_ in aid:
            sudo_users.append(int(id_.strip()))
    elif key == "PIL_MEMORY_LIMIT":
        try:
            value = int(value)
        except ValueError:
            value = 2048  # Default to 2GB if invalid input

    elif key == "AUTO_RESTART_ENABLED":
        value = value.lower() in ("true", "1", "yes")
        # Always schedule or cancel auto-restart when this setting is changed
        from bot.helper.ext_utils.auto_restart import schedule_auto_restart

        create_task(schedule_auto_restart())
    elif key == "AUTO_RESTART_INTERVAL":
        try:
            value = max(1, int(value))  # Minimum 1 hour
            # Schedule the next auto-restart with the new interval if enabled
            if Config.AUTO_RESTART_ENABLED:
                from bot.helper.ext_utils.auto_restart import schedule_auto_restart

                create_task(schedule_auto_restart())
        except ValueError:
            value = 24  # Default to 24 hours if invalid input
    elif value.isdigit():
        value = int(value)
    elif (value.startswith("[") and value.endswith("]")) or (
        value.startswith("{") and value.endswith("}")
    ):
        value = eval(value)
    Config.set(key, value)

    # Determine which menu to return to based on the key
    if key.startswith(("WATERMARK_", "AUDIO_WATERMARK_", "SUBTITLE_WATERMARK_")):
        return_menu = "mediatools_watermark"
    elif key.startswith("METADATA_"):
        return_menu = "mediatools_metadata"
    elif key.startswith("CONVERT_"):
        return_menu = "mediatools_convert"
    elif key.startswith("COMPRESSION_"):
        return_menu = "mediatools_compression"
    elif key.startswith("MISTRAL_"):
        return_menu = "ai"
    elif key.startswith("TASK_MONITOR_"):
        return_menu = "taskmonitor"
    elif key.startswith("MERGE_") or key in [
        "CONCAT_DEMUXER_ENABLED",
        "FILTER_COMPLEX_ENABLED",
    ]:
        # Check if we're in the merge_config menu
        if (pre_message.text and "Merge Configuration" in pre_message.text) or (
            key.startswith("MERGE_")
            and any(
                x in key
                for x in [
                    "OUTPUT_FORMAT",
                    "VIDEO_",
                    "AUDIO_",
                    "IMAGE_",
                    "SUBTITLE_",
                    "DOCUMENT_",
                    "METADATA_",
                ]
            )
        ):
            return_menu = "mediatools_merge_config"
        # Check if we need to return to a specific page in mediatools_merge or mediatools_merge_config
        elif pre_message.text and "Page:" in pre_message.text:
            try:
                page_info = pre_message.text.split("Page:")[1].strip().split("/")[0]
                page_no = int(page_info) - 1

                # Determine which menu to return to based on the message content
                if "Merge Configuration" in pre_message.text:
                    return_menu = "mediatools_merge_config"
                else:
                    return_menu = "mediatools_merge"

                # Return to the correct page
                await update_buttons(pre_message, return_menu, page=page_no)
                await delete_message(message)
                await database.update_config({key: value})
                return
            except (ValueError, IndexError):
                if "Merge Configuration" in pre_message.text:
                    return_menu = "mediatools_merge_config"
                else:
                    return_menu = "mediatools_merge"
        else:
            return_menu = "mediatools_merge"
    elif key == "MEDIA_TOOLS_PRIORITY":
        return_menu = "mediatools"
    else:
        return_menu = "var"

    await update_buttons(pre_message, return_menu)
    await delete_message(message)
    await database.update_config({key: value})

    if key in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
        await start_from_queued()
    elif key in [
        "RCLONE_SERVE_URL",
        "RCLONE_SERVE_PORT",
        "RCLONE_SERVE_USER",
        "RCLONE_SERVE_PASS",
    ]:
        await rclone_serve_booter()
    elif key in ["JD_EMAIL", "JD_PASS"]:
        await jdownloader.boot()
    elif key == "RSS_DELAY":
        add_job()
    elif key == "USET_SERVERS":
        for s in value:
            await sabnzbd_client.set_special_config("servers", s)


@new_task
async def edit_aria(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if key == "newkey":
        key, value = [x.strip() for x in value.split(":", 1)]
    elif value.lower() == "true":
        value = "true"
    elif value.lower() == "false":
        value = "false"
    await TorrentManager.change_aria2_option(key, value)
    await update_buttons(pre_message, "aria")
    await delete_message(message)
    await database.update_aria2(key, value)


@new_task
async def edit_qbit(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
    elif key == "max_ratio":
        value = float(value)
    elif value.isdigit():
        value = int(value)
    await TorrentManager.qbittorrent.app.set_preferences({key: value})
    qbit_options[key] = value
    await update_buttons(pre_message, "qbit")
    await delete_message(message)
    await database.update_qbittorrent(key, value)


@new_task
async def edit_nzb(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if value.isdigit():
        value = int(value)
    elif value.startswith("[") and value.endswith("]"):
        try:
            value = ",".join(eval(value))
        except Exception as e:
            LOGGER.error(e)
            await update_buttons(pre_message, "nzb")
            return
    res = await sabnzbd_client.set_config("misc", key, value)
    nzb_options[key] = res["config"]["misc"][key]
    await update_buttons(pre_message, "nzb")
    await delete_message(message)
    await database.update_nzb_config()


@new_task
async def edit_nzb_server(_, message, pre_message, key, index=0):
    handler_dict[message.chat.id] = False
    value = message.text
    if key == "newser":
        if value.startswith("{") and value.endswith("}"):
            try:
                value = eval(value)
            except Exception:
                await send_message(message, "Invalid dict format!")
                await update_buttons(pre_message, "nzbserver")
                return
            res = await sabnzbd_client.add_server(value)
            if not res["config"]["servers"][0]["host"]:
                await send_message(message, "Invalid server!")
                await update_buttons(pre_message, "nzbserver")
                return
            Config.USENET_SERVERS.append(value)
            await update_buttons(pre_message, "nzbserver")
        else:
            await send_message(message, "Invalid dict format!")
            await update_buttons(pre_message, "nzbserver")
            return
    else:
        if value.isdigit():
            value = int(value)
        res = await sabnzbd_client.add_server(
            {"name": Config.USENET_SERVERS[index]["name"], key: value},
        )
        if res["config"]["servers"][0][key] == "":
            await send_message(message, "Invalid value")
            return
        Config.USENET_SERVERS[index][key] = value
        await update_buttons(pre_message, f"nzbser{index}")
    await delete_message(message)
    await database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})


async def sync_jdownloader():
    async with jd_listener_lock:
        if not Config.DATABASE_URL or not jdownloader.is_connected:
            return
        await jdownloader.device.system.exit_jd()
    if await aiopath.exists("cfg.zip"):
        await remove("cfg.zip")
    await (
        await create_subprocess_exec("7z", "a", "cfg.zip", "/JDownloader/cfg")
    ).wait()
    await database.update_private_file("cfg.zip")


@new_task
async def update_private_file(_, message, pre_message):
    handler_dict[message.chat.id] = False
    if not message.media and (file_name := message.text):
        if await aiopath.isfile(file_name) and file_name != "config.py":
            await remove(file_name)
        if file_name == "accounts.zip":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            Config.USE_SERVICE_ACCOUNTS = False
            await database.update_config({"USE_SERVICE_ACCOUNTS": False})
        elif file_name in [".netrc", "netrc"]:
            await (await create_subprocess_exec("touch", ".netrc")).wait()
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (
                await create_subprocess_exec("cp", ".netrc", "/root/.netrc")
            ).wait()
        await delete_message(message)
    elif doc := message.document:
        file_name = doc.file_name
        fpath = f"{getcwd()}/{file_name}"
        if await aiopath.exists(fpath):
            await remove(fpath)
        await message.download(file_name=fpath)
        if file_name == "accounts.zip":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            await (
                await create_subprocess_exec(
                    "7z",
                    "x",
                    "-o.",
                    "-aoa",
                    "accounts.zip",
                    "accounts/*.json",
                )
            ).wait()
            await (
                await create_subprocess_exec("chmod", "-R", "777", "accounts")
            ).wait()
        elif file_name == "list_drives.txt":
            drives_ids.clear()
            drives_names.clear()
            index_urls.clear()
            if Config.GDRIVE_ID:
                drives_names.append("Main")
                drives_ids.append(Config.GDRIVE_ID)
                index_urls.append(Config.INDEX_URL)
            async with aiopen("list_drives.txt", "r+") as f:
                lines = await f.readlines()
                for line in lines:
                    temp = line.strip().split()
                    drives_ids.append(temp[1])
                    drives_names.append(temp[0].replace("_", " "))
                    if len(temp) > 2:
                        index_urls.append(temp[2])
                    else:
                        index_urls.append("")
        elif file_name in [".netrc", "netrc"]:
            if file_name == "netrc":
                await rename("netrc", ".netrc")
                file_name = ".netrc"
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (
                await create_subprocess_exec("cp", ".netrc", "/root/.netrc")
            ).wait()
        elif file_name == "config.py":
            await load_config()
        await delete_message(message)
    if file_name == "rclone.conf":
        await rclone_serve_booter()
    await update_buttons(pre_message)
    await database.update_private_file(file_name)


async def event_handler(client, query, pfunc, rfunc, document=False):
    chat_id = query.message.chat.id
    handler_dict[chat_id] = True
    start_time = time()  # pylint: disable=unused-argument

    async def event_filter(_, *args):
        event = args[1]  # The event is the second argument
        user = event.from_user or event.sender_chat
        query_user = query.from_user

        # Check if both user and query_user are not None before comparing IDs
        if user is None or query_user is None:
            return False

        return bool(
            user.id == query_user.id
            and event.chat.id == chat_id
            and (event.text or (event.document and document)),
        )

    handler = client.add_handler(
        MessageHandler(pfunc, filters=create(event_filter)),
        group=-1,
    )
    while handler_dict[chat_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[chat_id] = False
            await rfunc()
    client.remove_handler(*handler)


@new_task
async def edit_bot_settings(client, query):
    data = query.data.split()
    message = query.message
    user_id = message.chat.id
    handler_dict[user_id] = False
    if data[1] == "close":
        await query.answer()
        # Only delete the menu message, not the command that triggered it
        await delete_message(message)
    elif data[1] == "back":
        await query.answer()
        globals()["start"] = 0
        await update_buttons(message, None)
    elif data[1] == "syncjd":
        if not Config.JD_EMAIL or not Config.JD_PASS:
            await query.answer(
                "No Email or Password provided!",
                show_alert=True,
            )
            return
        await query.answer(
            "Syncronization Started. JDownloader will get restarted. It takes up to 10 sec!",
            show_alert=True,
        )
        await sync_jdownloader()
    elif data[1] == "mediatools":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if media tools are enabled
        if not is_media_tool_enabled("mediatools"):
            await query.answer(
                "Media Tools are disabled by the bot owner.", show_alert=True
            )
            return

        await update_buttons(message, "mediatools")
    elif data[1] == "mediatools_watermark":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if watermark is enabled
        if not is_media_tool_enabled("watermark"):
            await query.answer(
                "Watermark tool is disabled by the bot owner.", show_alert=True
            )
            return

        await update_buttons(message, "mediatools_watermark")
    elif data[1] == "mediatools_merge":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if merge is enabled
        if not is_media_tool_enabled("merge"):
            await query.answer(
                "Merge tool is disabled by the bot owner.", show_alert=True
            )
            return

        # Always start at page 0 when first entering merge settings
        await update_buttons(message, "mediatools_merge", page=0)
    elif data[1] == "mediatools_merge_config":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if merge is enabled
        if not is_media_tool_enabled("merge"):
            await query.answer(
                "Merge tool is disabled by the bot owner.", show_alert=True
            )
            return

        # Always start at page 0 when first entering merge config settings
        await update_buttons(message, "mediatools_merge_config", page=0)
    elif data[1] == "mediatools_metadata":
        await query.answer()
        await update_buttons(message, "mediatools_metadata")
    elif data[1] == "mediatools_convert":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if convert is enabled
        if not is_media_tool_enabled("convert"):
            await query.answer(
                "Convert tool is disabled by the bot owner.", show_alert=True
            )
            return
        await update_buttons(message, "mediatools_convert")
    elif data[1] == "mediatools_trim":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if trim is enabled
        if not is_media_tool_enabled("trim"):
            await query.answer(
                "Trim tool is disabled by the bot owner.", show_alert=True
            )
            return
        await update_buttons(message, "mediatools_trim")

    elif data[1] == "mediatools_extract":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if extract is enabled
        if not is_media_tool_enabled("extract"):
            await query.answer(
                "Extract tool is disabled by the bot owner.", show_alert=True
            )
            return
        await update_buttons(message, "mediatools_extract")

    elif data[1] == "mediatools_compression":
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        await query.answer()
        # Check if compression is enabled
        if not is_media_tool_enabled("compression"):
            await query.answer(
                "Compression tool is disabled by the bot owner.", show_alert=True
            )
            return
        await update_buttons(message, "mediatools_compression")

    elif data[1] == "ai":
        await query.answer()
        await update_buttons(message, "ai")

    elif data[1] == "default_watermark":
        await query.answer("Resetting all watermark settings to default...")
        # Reset all watermark settings to default
        Config.WATERMARK_ENABLED = False
        Config.WATERMARK_KEY = ""
        Config.WATERMARK_POSITION = "top_left"
        Config.WATERMARK_SIZE = 20
        Config.WATERMARK_COLOR = "white"
        Config.WATERMARK_FONT = "default.otf"
        Config.WATERMARK_PRIORITY = 2
        Config.WATERMARK_THREADING = True
        Config.WATERMARK_THREAD_NUMBER = 4
        Config.WATERMARK_FAST_MODE = True
        Config.WATERMARK_MAINTAIN_QUALITY = True
        Config.WATERMARK_OPACITY = 1.0

        # Reset audio watermark settings
        Config.AUDIO_WATERMARK_ENABLED = False
        Config.AUDIO_WATERMARK_TEXT = ""
        Config.AUDIO_WATERMARK_VOLUME = 0.3

        # Reset subtitle watermark settings
        Config.SUBTITLE_WATERMARK_ENABLED = False
        Config.SUBTITLE_WATERMARK_TEXT = ""
        Config.SUBTITLE_WATERMARK_STYLE = "normal"

        # Update the database
        await database.update_config(
            {
                "WATERMARK_ENABLED": False,
                "WATERMARK_KEY": "",
                "WATERMARK_POSITION": "top_left",
                "WATERMARK_SIZE": 20,
                "WATERMARK_COLOR": "white",
                "WATERMARK_FONT": "default.otf",
                "WATERMARK_PRIORITY": 2,
                "WATERMARK_THREADING": True,
                "WATERMARK_THREAD_NUMBER": 4,
                "WATERMARK_FAST_MODE": True,
                "WATERMARK_MAINTAIN_QUALITY": True,
                "WATERMARK_OPACITY": 1.0,
                # Audio watermark settings
                "AUDIO_WATERMARK_ENABLED": False,
                "AUDIO_WATERMARK_TEXT": "",
                "AUDIO_WATERMARK_VOLUME": 0.3,
                # Subtitle watermark settings
                "SUBTITLE_WATERMARK_ENABLED": False,
                "SUBTITLE_WATERMARK_TEXT": "",
                "SUBTITLE_WATERMARK_STYLE": "normal",
            }
        )
        await update_buttons(message, "mediatools_watermark")

    elif data[1] == "default_compression":
        await query.answer("Resetting all compression settings to default...")
        # Reset all compression settings to default using DEFAULT_VALUES

        # General compression settings
        Config.COMPRESSION_ENABLED = DEFAULT_VALUES["COMPRESSION_ENABLED"]
        Config.COMPRESSION_PRIORITY = DEFAULT_VALUES["COMPRESSION_PRIORITY"]

        # Video compression settings
        Config.COMPRESSION_VIDEO_ENABLED = DEFAULT_VALUES[
            "COMPRESSION_VIDEO_ENABLED"
        ]
        Config.COMPRESSION_VIDEO_PRESET = DEFAULT_VALUES["COMPRESSION_VIDEO_PRESET"]
        Config.COMPRESSION_VIDEO_CRF = DEFAULT_VALUES["COMPRESSION_VIDEO_CRF"]
        Config.COMPRESSION_VIDEO_CODEC = DEFAULT_VALUES["COMPRESSION_VIDEO_CODEC"]
        Config.COMPRESSION_VIDEO_TUNE = DEFAULT_VALUES["COMPRESSION_VIDEO_TUNE"]
        Config.COMPRESSION_VIDEO_PIXEL_FORMAT = DEFAULT_VALUES[
            "COMPRESSION_VIDEO_PIXEL_FORMAT"
        ]

        # Audio compression settings
        Config.COMPRESSION_AUDIO_ENABLED = DEFAULT_VALUES[
            "COMPRESSION_AUDIO_ENABLED"
        ]
        Config.COMPRESSION_AUDIO_PRESET = DEFAULT_VALUES["COMPRESSION_AUDIO_PRESET"]
        Config.COMPRESSION_AUDIO_CODEC = DEFAULT_VALUES["COMPRESSION_AUDIO_CODEC"]
        Config.COMPRESSION_AUDIO_BITRATE = DEFAULT_VALUES[
            "COMPRESSION_AUDIO_BITRATE"
        ]
        Config.COMPRESSION_AUDIO_CHANNELS = DEFAULT_VALUES[
            "COMPRESSION_AUDIO_CHANNELS"
        ]

        # Image compression settings
        Config.COMPRESSION_IMAGE_ENABLED = DEFAULT_VALUES[
            "COMPRESSION_IMAGE_ENABLED"
        ]
        Config.COMPRESSION_IMAGE_PRESET = DEFAULT_VALUES["COMPRESSION_IMAGE_PRESET"]
        Config.COMPRESSION_IMAGE_QUALITY = DEFAULT_VALUES[
            "COMPRESSION_IMAGE_QUALITY"
        ]
        Config.COMPRESSION_IMAGE_RESIZE = DEFAULT_VALUES["COMPRESSION_IMAGE_RESIZE"]

        # Document compression settings
        Config.COMPRESSION_DOCUMENT_ENABLED = DEFAULT_VALUES[
            "COMPRESSION_DOCUMENT_ENABLED"
        ]
        Config.COMPRESSION_DOCUMENT_PRESET = DEFAULT_VALUES[
            "COMPRESSION_DOCUMENT_PRESET"
        ]
        Config.COMPRESSION_DOCUMENT_DPI = DEFAULT_VALUES["COMPRESSION_DOCUMENT_DPI"]

        # Subtitle compression settings
        Config.COMPRESSION_SUBTITLE_ENABLED = DEFAULT_VALUES[
            "COMPRESSION_SUBTITLE_ENABLED"
        ]
        Config.COMPRESSION_SUBTITLE_PRESET = DEFAULT_VALUES[
            "COMPRESSION_SUBTITLE_PRESET"
        ]
        Config.COMPRESSION_SUBTITLE_ENCODING = DEFAULT_VALUES[
            "COMPRESSION_SUBTITLE_ENCODING"
        ]

        # Archive compression settings
        Config.COMPRESSION_ARCHIVE_ENABLED = DEFAULT_VALUES[
            "COMPRESSION_ARCHIVE_ENABLED"
        ]
        Config.COMPRESSION_ARCHIVE_PRESET = DEFAULT_VALUES[
            "COMPRESSION_ARCHIVE_PRESET"
        ]
        Config.COMPRESSION_ARCHIVE_LEVEL = DEFAULT_VALUES[
            "COMPRESSION_ARCHIVE_LEVEL"
        ]
        Config.COMPRESSION_ARCHIVE_METHOD = DEFAULT_VALUES[
            "COMPRESSION_ARCHIVE_METHOD"
        ]

        # Update the database
        await database.update_config(
            {
                # General compression settings
                "COMPRESSION_ENABLED": DEFAULT_VALUES["COMPRESSION_ENABLED"],
                "COMPRESSION_PRIORITY": DEFAULT_VALUES["COMPRESSION_PRIORITY"],
                # Video compression settings
                "COMPRESSION_VIDEO_ENABLED": DEFAULT_VALUES[
                    "COMPRESSION_VIDEO_ENABLED"
                ],
                "COMPRESSION_VIDEO_PRESET": DEFAULT_VALUES[
                    "COMPRESSION_VIDEO_PRESET"
                ],
                "COMPRESSION_VIDEO_CRF": DEFAULT_VALUES["COMPRESSION_VIDEO_CRF"],
                "COMPRESSION_VIDEO_CODEC": DEFAULT_VALUES["COMPRESSION_VIDEO_CODEC"],
                "COMPRESSION_VIDEO_TUNE": DEFAULT_VALUES["COMPRESSION_VIDEO_TUNE"],
                "COMPRESSION_VIDEO_PIXEL_FORMAT": DEFAULT_VALUES[
                    "COMPRESSION_VIDEO_PIXEL_FORMAT"
                ],
                # Audio compression settings
                "COMPRESSION_AUDIO_ENABLED": DEFAULT_VALUES[
                    "COMPRESSION_AUDIO_ENABLED"
                ],
                "COMPRESSION_AUDIO_PRESET": DEFAULT_VALUES[
                    "COMPRESSION_AUDIO_PRESET"
                ],
                "COMPRESSION_AUDIO_CODEC": DEFAULT_VALUES["COMPRESSION_AUDIO_CODEC"],
                "COMPRESSION_AUDIO_BITRATE": DEFAULT_VALUES[
                    "COMPRESSION_AUDIO_BITRATE"
                ],
                "COMPRESSION_AUDIO_CHANNELS": DEFAULT_VALUES[
                    "COMPRESSION_AUDIO_CHANNELS"
                ],
                # Image compression settings
                "COMPRESSION_IMAGE_ENABLED": DEFAULT_VALUES[
                    "COMPRESSION_IMAGE_ENABLED"
                ],
                "COMPRESSION_IMAGE_PRESET": DEFAULT_VALUES[
                    "COMPRESSION_IMAGE_PRESET"
                ],
                "COMPRESSION_IMAGE_QUALITY": DEFAULT_VALUES[
                    "COMPRESSION_IMAGE_QUALITY"
                ],
                "COMPRESSION_IMAGE_RESIZE": DEFAULT_VALUES[
                    "COMPRESSION_IMAGE_RESIZE"
                ],
                # Document compression settings
                "COMPRESSION_DOCUMENT_ENABLED": DEFAULT_VALUES[
                    "COMPRESSION_DOCUMENT_ENABLED"
                ],
                "COMPRESSION_DOCUMENT_PRESET": DEFAULT_VALUES[
                    "COMPRESSION_DOCUMENT_PRESET"
                ],
                "COMPRESSION_DOCUMENT_DPI": DEFAULT_VALUES[
                    "COMPRESSION_DOCUMENT_DPI"
                ],
                # Subtitle compression settings
                "COMPRESSION_SUBTITLE_ENABLED": DEFAULT_VALUES[
                    "COMPRESSION_SUBTITLE_ENABLED"
                ],
                "COMPRESSION_SUBTITLE_PRESET": DEFAULT_VALUES[
                    "COMPRESSION_SUBTITLE_PRESET"
                ],
                "COMPRESSION_SUBTITLE_ENCODING": DEFAULT_VALUES[
                    "COMPRESSION_SUBTITLE_ENCODING"
                ],
                # Archive compression settings
                "COMPRESSION_ARCHIVE_ENABLED": DEFAULT_VALUES[
                    "COMPRESSION_ARCHIVE_ENABLED"
                ],
                "COMPRESSION_ARCHIVE_PRESET": DEFAULT_VALUES[
                    "COMPRESSION_ARCHIVE_PRESET"
                ],
                "COMPRESSION_ARCHIVE_LEVEL": DEFAULT_VALUES[
                    "COMPRESSION_ARCHIVE_LEVEL"
                ],
                "COMPRESSION_ARCHIVE_METHOD": DEFAULT_VALUES[
                    "COMPRESSION_ARCHIVE_METHOD"
                ],
            }
        )
        # Update the UI - pass the current state to maintain edit/view mode
        await update_buttons(message, "mediatools_compression")

    elif data[1] == "default_extract":
        await query.answer("Resetting all extract settings to default...")
        # Reset all extract settings to default using DEFAULT_VALUES

        # General extract settings
        Config.EXTRACT_ENABLED = DEFAULT_VALUES["EXTRACT_ENABLED"]
        Config.EXTRACT_PRIORITY = DEFAULT_VALUES["EXTRACT_PRIORITY"]
        Config.EXTRACT_DELETE_ORIGINAL = DEFAULT_VALUES["EXTRACT_DELETE_ORIGINAL"]

        # Video extract settings
        Config.EXTRACT_VIDEO_ENABLED = DEFAULT_VALUES["EXTRACT_VIDEO_ENABLED"]
        Config.EXTRACT_VIDEO_CODEC = DEFAULT_VALUES["EXTRACT_VIDEO_CODEC"]
        Config.EXTRACT_VIDEO_FORMAT = DEFAULT_VALUES.get(
            "EXTRACT_VIDEO_FORMAT", "none"
        )
        Config.EXTRACT_VIDEO_INDEX = DEFAULT_VALUES["EXTRACT_VIDEO_INDEX"]
        Config.EXTRACT_VIDEO_QUALITY = DEFAULT_VALUES["EXTRACT_VIDEO_QUALITY"]
        Config.EXTRACT_VIDEO_PRESET = DEFAULT_VALUES["EXTRACT_VIDEO_PRESET"]
        Config.EXTRACT_VIDEO_BITRATE = DEFAULT_VALUES["EXTRACT_VIDEO_BITRATE"]
        Config.EXTRACT_VIDEO_RESOLUTION = DEFAULT_VALUES["EXTRACT_VIDEO_RESOLUTION"]
        Config.EXTRACT_VIDEO_FPS = DEFAULT_VALUES["EXTRACT_VIDEO_FPS"]

        # Audio extract settings
        Config.EXTRACT_AUDIO_ENABLED = DEFAULT_VALUES["EXTRACT_AUDIO_ENABLED"]
        Config.EXTRACT_AUDIO_CODEC = DEFAULT_VALUES["EXTRACT_AUDIO_CODEC"]
        Config.EXTRACT_AUDIO_FORMAT = DEFAULT_VALUES.get(
            "EXTRACT_AUDIO_FORMAT", "none"
        )
        Config.EXTRACT_AUDIO_INDEX = DEFAULT_VALUES["EXTRACT_AUDIO_INDEX"]
        Config.EXTRACT_AUDIO_BITRATE = DEFAULT_VALUES["EXTRACT_AUDIO_BITRATE"]
        Config.EXTRACT_AUDIO_CHANNELS = DEFAULT_VALUES["EXTRACT_AUDIO_CHANNELS"]
        Config.EXTRACT_AUDIO_SAMPLING = DEFAULT_VALUES["EXTRACT_AUDIO_SAMPLING"]
        Config.EXTRACT_AUDIO_VOLUME = DEFAULT_VALUES["EXTRACT_AUDIO_VOLUME"]

        # Subtitle extract settings
        Config.EXTRACT_SUBTITLE_ENABLED = DEFAULT_VALUES["EXTRACT_SUBTITLE_ENABLED"]
        Config.EXTRACT_SUBTITLE_CODEC = DEFAULT_VALUES["EXTRACT_SUBTITLE_CODEC"]
        Config.EXTRACT_SUBTITLE_FORMAT = DEFAULT_VALUES.get(
            "EXTRACT_SUBTITLE_FORMAT", "none"
        )
        Config.EXTRACT_SUBTITLE_INDEX = DEFAULT_VALUES["EXTRACT_SUBTITLE_INDEX"]
        Config.EXTRACT_SUBTITLE_LANGUAGE = DEFAULT_VALUES[
            "EXTRACT_SUBTITLE_LANGUAGE"
        ]
        Config.EXTRACT_SUBTITLE_ENCODING = DEFAULT_VALUES[
            "EXTRACT_SUBTITLE_ENCODING"
        ]
        Config.EXTRACT_SUBTITLE_FONT = DEFAULT_VALUES["EXTRACT_SUBTITLE_FONT"]
        Config.EXTRACT_SUBTITLE_FONT_SIZE = DEFAULT_VALUES[
            "EXTRACT_SUBTITLE_FONT_SIZE"
        ]

        # Attachment extract settings
        Config.EXTRACT_ATTACHMENT_ENABLED = DEFAULT_VALUES[
            "EXTRACT_ATTACHMENT_ENABLED"
        ]
        Config.EXTRACT_ATTACHMENT_FORMAT = DEFAULT_VALUES.get(
            "EXTRACT_ATTACHMENT_FORMAT", "none"
        )
        Config.EXTRACT_ATTACHMENT_INDEX = DEFAULT_VALUES["EXTRACT_ATTACHMENT_INDEX"]
        Config.EXTRACT_ATTACHMENT_FILTER = DEFAULT_VALUES[
            "EXTRACT_ATTACHMENT_FILTER"
        ]

        # Quality settings
        Config.EXTRACT_MAINTAIN_QUALITY = DEFAULT_VALUES["EXTRACT_MAINTAIN_QUALITY"]

        # Update the database
        await database.update_config(
            {
                # General extract settings
                "EXTRACT_ENABLED": DEFAULT_VALUES["EXTRACT_ENABLED"],
                "EXTRACT_PRIORITY": DEFAULT_VALUES["EXTRACT_PRIORITY"],
                "EXTRACT_DELETE_ORIGINAL": DEFAULT_VALUES["EXTRACT_DELETE_ORIGINAL"],
                # Video extract settings
                "EXTRACT_VIDEO_ENABLED": DEFAULT_VALUES["EXTRACT_VIDEO_ENABLED"],
                "EXTRACT_VIDEO_CODEC": DEFAULT_VALUES["EXTRACT_VIDEO_CODEC"],
                "EXTRACT_VIDEO_FORMAT": DEFAULT_VALUES.get(
                    "EXTRACT_VIDEO_FORMAT", "none"
                ),
                "EXTRACT_VIDEO_INDEX": DEFAULT_VALUES["EXTRACT_VIDEO_INDEX"],
                "EXTRACT_VIDEO_QUALITY": DEFAULT_VALUES["EXTRACT_VIDEO_QUALITY"],
                "EXTRACT_VIDEO_PRESET": DEFAULT_VALUES["EXTRACT_VIDEO_PRESET"],
                "EXTRACT_VIDEO_BITRATE": DEFAULT_VALUES["EXTRACT_VIDEO_BITRATE"],
                "EXTRACT_VIDEO_RESOLUTION": DEFAULT_VALUES[
                    "EXTRACT_VIDEO_RESOLUTION"
                ],
                "EXTRACT_VIDEO_FPS": DEFAULT_VALUES["EXTRACT_VIDEO_FPS"],
                # Audio extract settings
                "EXTRACT_AUDIO_ENABLED": DEFAULT_VALUES["EXTRACT_AUDIO_ENABLED"],
                "EXTRACT_AUDIO_CODEC": DEFAULT_VALUES["EXTRACT_AUDIO_CODEC"],
                "EXTRACT_AUDIO_FORMAT": DEFAULT_VALUES.get(
                    "EXTRACT_AUDIO_FORMAT", "none"
                ),
                "EXTRACT_AUDIO_INDEX": DEFAULT_VALUES["EXTRACT_AUDIO_INDEX"],
                "EXTRACT_AUDIO_BITRATE": DEFAULT_VALUES["EXTRACT_AUDIO_BITRATE"],
                "EXTRACT_AUDIO_CHANNELS": DEFAULT_VALUES["EXTRACT_AUDIO_CHANNELS"],
                "EXTRACT_AUDIO_SAMPLING": DEFAULT_VALUES["EXTRACT_AUDIO_SAMPLING"],
                "EXTRACT_AUDIO_VOLUME": DEFAULT_VALUES["EXTRACT_AUDIO_VOLUME"],
                # Subtitle extract settings
                "EXTRACT_SUBTITLE_ENABLED": DEFAULT_VALUES[
                    "EXTRACT_SUBTITLE_ENABLED"
                ],
                "EXTRACT_SUBTITLE_CODEC": DEFAULT_VALUES["EXTRACT_SUBTITLE_CODEC"],
                "EXTRACT_SUBTITLE_FORMAT": DEFAULT_VALUES.get(
                    "EXTRACT_SUBTITLE_FORMAT", "none"
                ),
                "EXTRACT_SUBTITLE_INDEX": DEFAULT_VALUES["EXTRACT_SUBTITLE_INDEX"],
                "EXTRACT_SUBTITLE_LANGUAGE": DEFAULT_VALUES[
                    "EXTRACT_SUBTITLE_LANGUAGE"
                ],
                "EXTRACT_SUBTITLE_ENCODING": DEFAULT_VALUES[
                    "EXTRACT_SUBTITLE_ENCODING"
                ],
                "EXTRACT_SUBTITLE_FONT": DEFAULT_VALUES["EXTRACT_SUBTITLE_FONT"],
                "EXTRACT_SUBTITLE_FONT_SIZE": DEFAULT_VALUES[
                    "EXTRACT_SUBTITLE_FONT_SIZE"
                ],
                # Attachment extract settings
                "EXTRACT_ATTACHMENT_ENABLED": DEFAULT_VALUES[
                    "EXTRACT_ATTACHMENT_ENABLED"
                ],
                "EXTRACT_ATTACHMENT_FORMAT": DEFAULT_VALUES.get(
                    "EXTRACT_ATTACHMENT_FORMAT", "none"
                ),
                "EXTRACT_ATTACHMENT_INDEX": DEFAULT_VALUES[
                    "EXTRACT_ATTACHMENT_INDEX"
                ],
                "EXTRACT_ATTACHMENT_FILTER": DEFAULT_VALUES[
                    "EXTRACT_ATTACHMENT_FILTER"
                ],
                # Quality settings
                "EXTRACT_MAINTAIN_QUALITY": DEFAULT_VALUES[
                    "EXTRACT_MAINTAIN_QUALITY"
                ],
            }
        )
        # Update the UI - pass the current state to maintain edit/view mode
        await update_buttons(message, "mediatools_extract")

    elif data[1] == "default_trim":
        await query.answer("Resetting all trim settings to default...")
        # Reset all trim settings to default using DEFAULT_VALUES

        # General trim settings
        Config.TRIM_ENABLED = DEFAULT_VALUES["TRIM_ENABLED"]
        Config.TRIM_PRIORITY = DEFAULT_VALUES["TRIM_PRIORITY"]
        Config.TRIM_START_TIME = DEFAULT_VALUES.get("TRIM_START_TIME", "00:00:00")
        Config.TRIM_END_TIME = DEFAULT_VALUES.get("TRIM_END_TIME", "")
        Config.TRIM_DELETE_ORIGINAL = DEFAULT_VALUES["TRIM_DELETE_ORIGINAL"]

        # Video trim settings
        Config.TRIM_VIDEO_ENABLED = DEFAULT_VALUES["TRIM_VIDEO_ENABLED"]
        Config.TRIM_VIDEO_CODEC = DEFAULT_VALUES["TRIM_VIDEO_CODEC"]
        Config.TRIM_VIDEO_PRESET = DEFAULT_VALUES["TRIM_VIDEO_PRESET"]
        Config.TRIM_VIDEO_FORMAT = DEFAULT_VALUES["TRIM_VIDEO_FORMAT"]

        # Audio trim settings
        Config.TRIM_AUDIO_ENABLED = DEFAULT_VALUES["TRIM_AUDIO_ENABLED"]
        Config.TRIM_AUDIO_CODEC = DEFAULT_VALUES["TRIM_AUDIO_CODEC"]
        Config.TRIM_AUDIO_PRESET = DEFAULT_VALUES["TRIM_AUDIO_PRESET"]
        Config.TRIM_AUDIO_FORMAT = DEFAULT_VALUES["TRIM_AUDIO_FORMAT"]

        # Image trim settings
        Config.TRIM_IMAGE_ENABLED = DEFAULT_VALUES["TRIM_IMAGE_ENABLED"]
        Config.TRIM_IMAGE_QUALITY = DEFAULT_VALUES["TRIM_IMAGE_QUALITY"]
        Config.TRIM_IMAGE_FORMAT = DEFAULT_VALUES["TRIM_IMAGE_FORMAT"]

        # Document trim settings
        Config.TRIM_DOCUMENT_ENABLED = DEFAULT_VALUES["TRIM_DOCUMENT_ENABLED"]
        Config.TRIM_DOCUMENT_QUALITY = DEFAULT_VALUES["TRIM_DOCUMENT_QUALITY"]
        Config.TRIM_DOCUMENT_FORMAT = DEFAULT_VALUES["TRIM_DOCUMENT_FORMAT"]

        # Subtitle trim settings
        Config.TRIM_SUBTITLE_ENABLED = DEFAULT_VALUES["TRIM_SUBTITLE_ENABLED"]
        Config.TRIM_SUBTITLE_ENCODING = DEFAULT_VALUES["TRIM_SUBTITLE_ENCODING"]
        Config.TRIM_SUBTITLE_FORMAT = DEFAULT_VALUES["TRIM_SUBTITLE_FORMAT"]

        # Archive trim settings
        Config.TRIM_ARCHIVE_ENABLED = DEFAULT_VALUES["TRIM_ARCHIVE_ENABLED"]
        Config.TRIM_ARCHIVE_FORMAT = DEFAULT_VALUES["TRIM_ARCHIVE_FORMAT"]

        # Update the database
        await database.update_config(
            {
                # General trim settings
                "TRIM_ENABLED": DEFAULT_VALUES["TRIM_ENABLED"],
                "TRIM_PRIORITY": DEFAULT_VALUES["TRIM_PRIORITY"],
                "TRIM_START_TIME": DEFAULT_VALUES.get("TRIM_START_TIME", "00:00:00"),
                "TRIM_END_TIME": DEFAULT_VALUES.get("TRIM_END_TIME", ""),
                "TRIM_DELETE_ORIGINAL": DEFAULT_VALUES["TRIM_DELETE_ORIGINAL"],
                # Video trim settings
                "TRIM_VIDEO_ENABLED": DEFAULT_VALUES["TRIM_VIDEO_ENABLED"],
                "TRIM_VIDEO_CODEC": DEFAULT_VALUES["TRIM_VIDEO_CODEC"],
                "TRIM_VIDEO_PRESET": DEFAULT_VALUES["TRIM_VIDEO_PRESET"],
                "TRIM_VIDEO_FORMAT": DEFAULT_VALUES["TRIM_VIDEO_FORMAT"],
                # Audio trim settings
                "TRIM_AUDIO_ENABLED": DEFAULT_VALUES["TRIM_AUDIO_ENABLED"],
                "TRIM_AUDIO_CODEC": DEFAULT_VALUES["TRIM_AUDIO_CODEC"],
                "TRIM_AUDIO_PRESET": DEFAULT_VALUES["TRIM_AUDIO_PRESET"],
                "TRIM_AUDIO_FORMAT": DEFAULT_VALUES["TRIM_AUDIO_FORMAT"],
                # Image trim settings
                "TRIM_IMAGE_ENABLED": DEFAULT_VALUES["TRIM_IMAGE_ENABLED"],
                "TRIM_IMAGE_QUALITY": DEFAULT_VALUES["TRIM_IMAGE_QUALITY"],
                "TRIM_IMAGE_FORMAT": DEFAULT_VALUES["TRIM_IMAGE_FORMAT"],
                # Document trim settings
                "TRIM_DOCUMENT_ENABLED": DEFAULT_VALUES["TRIM_DOCUMENT_ENABLED"],
                "TRIM_DOCUMENT_QUALITY": DEFAULT_VALUES["TRIM_DOCUMENT_QUALITY"],
                "TRIM_DOCUMENT_FORMAT": DEFAULT_VALUES["TRIM_DOCUMENT_FORMAT"],
                # Subtitle trim settings
                "TRIM_SUBTITLE_ENABLED": DEFAULT_VALUES["TRIM_SUBTITLE_ENABLED"],
                "TRIM_SUBTITLE_ENCODING": DEFAULT_VALUES["TRIM_SUBTITLE_ENCODING"],
                "TRIM_SUBTITLE_FORMAT": DEFAULT_VALUES["TRIM_SUBTITLE_FORMAT"],
                # Archive trim settings
                "TRIM_ARCHIVE_ENABLED": DEFAULT_VALUES["TRIM_ARCHIVE_ENABLED"],
                "TRIM_ARCHIVE_FORMAT": DEFAULT_VALUES["TRIM_ARCHIVE_FORMAT"],
            }
        )
        # Update the UI - pass the current state to maintain edit/view mode
        await update_buttons(message, "mediatools_trim")

    elif data[1] == "default_convert":
        await query.answer("Resetting all convert settings to default...")
        # Reset all convert settings to default using DEFAULT_VALUES

        # General convert settings
        Config.CONVERT_ENABLED = DEFAULT_VALUES["CONVERT_ENABLED"]
        Config.CONVERT_PRIORITY = DEFAULT_VALUES["CONVERT_PRIORITY"]
        Config.CONVERT_DELETE_ORIGINAL = DEFAULT_VALUES["CONVERT_DELETE_ORIGINAL"]

        # Video convert settings
        Config.CONVERT_VIDEO_ENABLED = DEFAULT_VALUES["CONVERT_VIDEO_ENABLED"]
        Config.CONVERT_VIDEO_FORMAT = DEFAULT_VALUES["CONVERT_VIDEO_FORMAT"]
        Config.CONVERT_VIDEO_CODEC = DEFAULT_VALUES["CONVERT_VIDEO_CODEC"]
        Config.CONVERT_VIDEO_QUALITY = DEFAULT_VALUES["CONVERT_VIDEO_QUALITY"]
        Config.CONVERT_VIDEO_CRF = DEFAULT_VALUES["CONVERT_VIDEO_CRF"]
        Config.CONVERT_VIDEO_PRESET = DEFAULT_VALUES["CONVERT_VIDEO_PRESET"]
        Config.CONVERT_VIDEO_MAINTAIN_QUALITY = DEFAULT_VALUES[
            "CONVERT_VIDEO_MAINTAIN_QUALITY"
        ]
        Config.CONVERT_VIDEO_RESOLUTION = DEFAULT_VALUES["CONVERT_VIDEO_RESOLUTION"]
        Config.CONVERT_VIDEO_FPS = DEFAULT_VALUES["CONVERT_VIDEO_FPS"]
        Config.CONVERT_VIDEO_DELETE_ORIGINAL = DEFAULT_VALUES[
            "CONVERT_VIDEO_DELETE_ORIGINAL"
        ]

        # Audio convert settings
        Config.CONVERT_AUDIO_ENABLED = DEFAULT_VALUES["CONVERT_AUDIO_ENABLED"]
        Config.CONVERT_AUDIO_FORMAT = DEFAULT_VALUES["CONVERT_AUDIO_FORMAT"]
        Config.CONVERT_AUDIO_CODEC = DEFAULT_VALUES["CONVERT_AUDIO_CODEC"]
        Config.CONVERT_AUDIO_BITRATE = DEFAULT_VALUES["CONVERT_AUDIO_BITRATE"]
        Config.CONVERT_AUDIO_CHANNELS = DEFAULT_VALUES["CONVERT_AUDIO_CHANNELS"]
        Config.CONVERT_AUDIO_SAMPLING = DEFAULT_VALUES["CONVERT_AUDIO_SAMPLING"]
        Config.CONVERT_AUDIO_VOLUME = DEFAULT_VALUES["CONVERT_AUDIO_VOLUME"]
        Config.CONVERT_AUDIO_DELETE_ORIGINAL = DEFAULT_VALUES[
            "CONVERT_AUDIO_DELETE_ORIGINAL"
        ]

        # Subtitle convert settings
        Config.CONVERT_SUBTITLE_ENABLED = DEFAULT_VALUES["CONVERT_SUBTITLE_ENABLED"]
        Config.CONVERT_SUBTITLE_FORMAT = DEFAULT_VALUES["CONVERT_SUBTITLE_FORMAT"]
        Config.CONVERT_SUBTITLE_ENCODING = DEFAULT_VALUES[
            "CONVERT_SUBTITLE_ENCODING"
        ]
        Config.CONVERT_SUBTITLE_LANGUAGE = DEFAULT_VALUES[
            "CONVERT_SUBTITLE_LANGUAGE"
        ]
        Config.CONVERT_SUBTITLE_DELETE_ORIGINAL = DEFAULT_VALUES[
            "CONVERT_SUBTITLE_DELETE_ORIGINAL"
        ]

        # Document convert settings
        Config.CONVERT_DOCUMENT_ENABLED = DEFAULT_VALUES["CONVERT_DOCUMENT_ENABLED"]
        Config.CONVERT_DOCUMENT_FORMAT = DEFAULT_VALUES["CONVERT_DOCUMENT_FORMAT"]
        Config.CONVERT_DOCUMENT_QUALITY = DEFAULT_VALUES["CONVERT_DOCUMENT_QUALITY"]
        Config.CONVERT_DOCUMENT_DPI = DEFAULT_VALUES["CONVERT_DOCUMENT_DPI"]
        Config.CONVERT_DOCUMENT_DELETE_ORIGINAL = DEFAULT_VALUES[
            "CONVERT_DOCUMENT_DELETE_ORIGINAL"
        ]

        # Archive convert settings
        Config.CONVERT_ARCHIVE_ENABLED = DEFAULT_VALUES["CONVERT_ARCHIVE_ENABLED"]
        Config.CONVERT_ARCHIVE_FORMAT = DEFAULT_VALUES["CONVERT_ARCHIVE_FORMAT"]
        Config.CONVERT_ARCHIVE_LEVEL = DEFAULT_VALUES["CONVERT_ARCHIVE_LEVEL"]
        Config.CONVERT_ARCHIVE_METHOD = DEFAULT_VALUES["CONVERT_ARCHIVE_METHOD"]
        Config.CONVERT_ARCHIVE_DELETE_ORIGINAL = DEFAULT_VALUES[
            "CONVERT_ARCHIVE_DELETE_ORIGINAL"
        ]

        # Update the database
        await database.update_config(
            {
                # General convert settings
                "CONVERT_ENABLED": DEFAULT_VALUES["CONVERT_ENABLED"],
                "CONVERT_PRIORITY": DEFAULT_VALUES["CONVERT_PRIORITY"],
                "CONVERT_DELETE_ORIGINAL": DEFAULT_VALUES["CONVERT_DELETE_ORIGINAL"],
                # Video convert settings
                "CONVERT_VIDEO_ENABLED": DEFAULT_VALUES["CONVERT_VIDEO_ENABLED"],
                "CONVERT_VIDEO_FORMAT": DEFAULT_VALUES["CONVERT_VIDEO_FORMAT"],
                "CONVERT_VIDEO_CODEC": DEFAULT_VALUES["CONVERT_VIDEO_CODEC"],
                "CONVERT_VIDEO_QUALITY": DEFAULT_VALUES["CONVERT_VIDEO_QUALITY"],
                "CONVERT_VIDEO_CRF": DEFAULT_VALUES["CONVERT_VIDEO_CRF"],
                "CONVERT_VIDEO_PRESET": DEFAULT_VALUES["CONVERT_VIDEO_PRESET"],
                "CONVERT_VIDEO_MAINTAIN_QUALITY": DEFAULT_VALUES[
                    "CONVERT_VIDEO_MAINTAIN_QUALITY"
                ],
                "CONVERT_VIDEO_RESOLUTION": DEFAULT_VALUES[
                    "CONVERT_VIDEO_RESOLUTION"
                ],
                "CONVERT_VIDEO_FPS": DEFAULT_VALUES["CONVERT_VIDEO_FPS"],
                "CONVERT_VIDEO_DELETE_ORIGINAL": DEFAULT_VALUES[
                    "CONVERT_VIDEO_DELETE_ORIGINAL"
                ],
                # Audio convert settings
                "CONVERT_AUDIO_ENABLED": DEFAULT_VALUES["CONVERT_AUDIO_ENABLED"],
                "CONVERT_AUDIO_FORMAT": DEFAULT_VALUES["CONVERT_AUDIO_FORMAT"],
                "CONVERT_AUDIO_CODEC": DEFAULT_VALUES["CONVERT_AUDIO_CODEC"],
                "CONVERT_AUDIO_BITRATE": DEFAULT_VALUES["CONVERT_AUDIO_BITRATE"],
                "CONVERT_AUDIO_CHANNELS": DEFAULT_VALUES["CONVERT_AUDIO_CHANNELS"],
                "CONVERT_AUDIO_SAMPLING": DEFAULT_VALUES["CONVERT_AUDIO_SAMPLING"],
                "CONVERT_AUDIO_VOLUME": DEFAULT_VALUES["CONVERT_AUDIO_VOLUME"],
                "CONVERT_AUDIO_DELETE_ORIGINAL": DEFAULT_VALUES[
                    "CONVERT_AUDIO_DELETE_ORIGINAL"
                ],
                # Subtitle convert settings
                "CONVERT_SUBTITLE_ENABLED": DEFAULT_VALUES[
                    "CONVERT_SUBTITLE_ENABLED"
                ],
                "CONVERT_SUBTITLE_FORMAT": DEFAULT_VALUES["CONVERT_SUBTITLE_FORMAT"],
                "CONVERT_SUBTITLE_ENCODING": DEFAULT_VALUES[
                    "CONVERT_SUBTITLE_ENCODING"
                ],
                "CONVERT_SUBTITLE_LANGUAGE": DEFAULT_VALUES[
                    "CONVERT_SUBTITLE_LANGUAGE"
                ],
                "CONVERT_SUBTITLE_DELETE_ORIGINAL": DEFAULT_VALUES[
                    "CONVERT_SUBTITLE_DELETE_ORIGINAL"
                ],
                # Document convert settings
                "CONVERT_DOCUMENT_ENABLED": DEFAULT_VALUES[
                    "CONVERT_DOCUMENT_ENABLED"
                ],
                "CONVERT_DOCUMENT_FORMAT": DEFAULT_VALUES["CONVERT_DOCUMENT_FORMAT"],
                "CONVERT_DOCUMENT_QUALITY": DEFAULT_VALUES[
                    "CONVERT_DOCUMENT_QUALITY"
                ],
                "CONVERT_DOCUMENT_DPI": DEFAULT_VALUES["CONVERT_DOCUMENT_DPI"],
                "CONVERT_DOCUMENT_DELETE_ORIGINAL": DEFAULT_VALUES[
                    "CONVERT_DOCUMENT_DELETE_ORIGINAL"
                ],
                # Archive convert settings
                "CONVERT_ARCHIVE_ENABLED": DEFAULT_VALUES["CONVERT_ARCHIVE_ENABLED"],
                "CONVERT_ARCHIVE_FORMAT": DEFAULT_VALUES["CONVERT_ARCHIVE_FORMAT"],
                "CONVERT_ARCHIVE_LEVEL": DEFAULT_VALUES["CONVERT_ARCHIVE_LEVEL"],
                "CONVERT_ARCHIVE_METHOD": DEFAULT_VALUES["CONVERT_ARCHIVE_METHOD"],
                "CONVERT_ARCHIVE_DELETE_ORIGINAL": DEFAULT_VALUES[
                    "CONVERT_ARCHIVE_DELETE_ORIGINAL"
                ],
            }
        )
        # Update the UI - pass the current state to maintain edit/view mode
        await update_buttons(message, "mediatools_convert")

    elif data[1] == "default_metadata":
        await query.answer("Resetting all metadata settings to default...")
        # Reset all metadata settings to default
        Config.METADATA_KEY = ""
        Config.METADATA_ALL = ""
        Config.METADATA_TITLE = ""
        Config.METADATA_AUTHOR = ""
        Config.METADATA_COMMENT = ""

        # Reset video metadata settings
        Config.METADATA_VIDEO_TITLE = ""
        Config.METADATA_VIDEO_AUTHOR = ""
        Config.METADATA_VIDEO_COMMENT = ""

        # Reset audio metadata settings
        Config.METADATA_AUDIO_TITLE = ""
        Config.METADATA_AUDIO_AUTHOR = ""
        Config.METADATA_AUDIO_COMMENT = ""

        # Reset subtitle metadata settings
        Config.METADATA_SUBTITLE_TITLE = ""
        Config.METADATA_SUBTITLE_AUTHOR = ""
        Config.METADATA_SUBTITLE_COMMENT = ""

        # Update the database
        await database.update_config(
            {
                "METADATA_KEY": "",
                "METADATA_ALL": "",
                "METADATA_TITLE": "",
                "METADATA_AUTHOR": "",
                "METADATA_COMMENT": "",
                "METADATA_VIDEO_TITLE": "",
                "METADATA_VIDEO_AUTHOR": "",
                "METADATA_VIDEO_COMMENT": "",
                "METADATA_AUDIO_TITLE": "",
                "METADATA_AUDIO_AUTHOR": "",
                "METADATA_AUDIO_COMMENT": "",
                "METADATA_SUBTITLE_TITLE": "",
                "METADATA_SUBTITLE_AUTHOR": "",
                "METADATA_SUBTITLE_COMMENT": "",
            }
        )
        # Update the UI - pass the current state to maintain edit/view mode
        await update_buttons(message, "mediatools_metadata")
    elif data[1] == "default_ai":
        await query.answer("Resetting all AI settings to default...")
        # Reset all AI settings to default
        Config.DEFAULT_AI_PROVIDER = "mistral"
        Config.MISTRAL_API_KEY = ""
        Config.MISTRAL_API_URL = ""
        Config.DEEPSEEK_API_KEY = ""
        Config.DEEPSEEK_API_URL = ""
        Config.CHATGPT_API_KEY = ""
        Config.CHATGPT_API_URL = ""
        Config.GEMINI_API_KEY = ""
        Config.GEMINI_API_URL = ""

        # Update the database
        await database.update_config(
            {
                "DEFAULT_AI_PROVIDER": "mistral",
                "MISTRAL_API_KEY": "",
                "MISTRAL_API_URL": "",
                "DEEPSEEK_API_KEY": "",
                "DEEPSEEK_API_URL": "",
                "CHATGPT_API_KEY": "",
                "CHATGPT_API_URL": "",
                "GEMINI_API_KEY": "",
                "GEMINI_API_URL": "",
            }
        )
        # Update the UI
        await update_buttons(message, "ai")

    elif data[1] == "default_taskmonitor":
        await query.answer("Resetting all task monitoring settings to default...")
        # Reset all task monitoring settings to default
        Config.TASK_MONITOR_ENABLED = DEFAULT_VALUES["TASK_MONITOR_ENABLED"]
        Config.TASK_MONITOR_INTERVAL = DEFAULT_VALUES["TASK_MONITOR_INTERVAL"]
        Config.TASK_MONITOR_CONSECUTIVE_CHECKS = DEFAULT_VALUES[
            "TASK_MONITOR_CONSECUTIVE_CHECKS"
        ]
        Config.TASK_MONITOR_SPEED_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_SPEED_THRESHOLD"
        ]
        Config.TASK_MONITOR_ELAPSED_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_ELAPSED_THRESHOLD"
        ]
        Config.TASK_MONITOR_ETA_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_ETA_THRESHOLD"
        ]
        Config.TASK_MONITOR_WAIT_TIME = DEFAULT_VALUES["TASK_MONITOR_WAIT_TIME"]
        Config.TASK_MONITOR_COMPLETION_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_COMPLETION_THRESHOLD"
        ]
        Config.TASK_MONITOR_CPU_HIGH = DEFAULT_VALUES["TASK_MONITOR_CPU_HIGH"]
        Config.TASK_MONITOR_CPU_LOW = DEFAULT_VALUES["TASK_MONITOR_CPU_LOW"]
        Config.TASK_MONITOR_MEMORY_HIGH = DEFAULT_VALUES["TASK_MONITOR_MEMORY_HIGH"]
        Config.TASK_MONITOR_MEMORY_LOW = DEFAULT_VALUES["TASK_MONITOR_MEMORY_LOW"]
        # Update the database
        await database.update_config(
            {
                "TASK_MONITOR_ENABLED": DEFAULT_VALUES["TASK_MONITOR_ENABLED"],
                "TASK_MONITOR_INTERVAL": DEFAULT_VALUES["TASK_MONITOR_INTERVAL"],
                "TASK_MONITOR_CONSECUTIVE_CHECKS": DEFAULT_VALUES[
                    "TASK_MONITOR_CONSECUTIVE_CHECKS"
                ],
                "TASK_MONITOR_SPEED_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_SPEED_THRESHOLD"
                ],
                "TASK_MONITOR_ELAPSED_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_ELAPSED_THRESHOLD"
                ],
                "TASK_MONITOR_ETA_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_ETA_THRESHOLD"
                ],
                "TASK_MONITOR_WAIT_TIME": DEFAULT_VALUES["TASK_MONITOR_WAIT_TIME"],
                "TASK_MONITOR_COMPLETION_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_COMPLETION_THRESHOLD"
                ],
                "TASK_MONITOR_CPU_HIGH": DEFAULT_VALUES["TASK_MONITOR_CPU_HIGH"],
                "TASK_MONITOR_CPU_LOW": DEFAULT_VALUES["TASK_MONITOR_CPU_LOW"],
                "TASK_MONITOR_MEMORY_HIGH": DEFAULT_VALUES[
                    "TASK_MONITOR_MEMORY_HIGH"
                ],
                "TASK_MONITOR_MEMORY_LOW": DEFAULT_VALUES["TASK_MONITOR_MEMORY_LOW"],
            }
        )
        # Update the UI - pass the current state to maintain edit/view mode
        await update_buttons(message, "taskmonitor")
    elif data[1] == "default_merge":
        await query.answer("Resetting all merge settings to default...")
        # Reset all merge settings to default
        Config.MERGE_ENABLED = False
        Config.CONCAT_DEMUXER_ENABLED = True
        Config.FILTER_COMPLEX_ENABLED = False
        # Reset output formats
        Config.MERGE_OUTPUT_FORMAT_VIDEO = "mkv"
        Config.MERGE_OUTPUT_FORMAT_AUDIO = "mp3"
        Config.MERGE_OUTPUT_FORMAT_IMAGE = "jpg"
        Config.MERGE_OUTPUT_FORMAT_DOCUMENT = "pdf"
        Config.MERGE_OUTPUT_FORMAT_SUBTITLE = "srt"

        # Reset video settings
        Config.MERGE_VIDEO_CODEC = "none"
        Config.MERGE_VIDEO_QUALITY = "none"
        Config.MERGE_VIDEO_PRESET = "none"
        Config.MERGE_VIDEO_CRF = 0
        Config.MERGE_VIDEO_PIXEL_FORMAT = "none"
        Config.MERGE_VIDEO_TUNE = "none"
        Config.MERGE_VIDEO_FASTSTART = False

        # Reset audio settings
        Config.MERGE_AUDIO_CODEC = "none"
        Config.MERGE_AUDIO_BITRATE = "none"
        Config.MERGE_AUDIO_CHANNELS = 0
        Config.MERGE_AUDIO_SAMPLING = "none"
        Config.MERGE_AUDIO_VOLUME = 0.0

        # Reset image settings
        Config.MERGE_IMAGE_MODE = "none"
        Config.MERGE_IMAGE_COLUMNS = 0
        Config.MERGE_IMAGE_QUALITY = 0
        Config.MERGE_IMAGE_DPI = 0
        Config.MERGE_IMAGE_RESIZE = "none"
        Config.MERGE_IMAGE_BACKGROUND = "none"

        # Reset subtitle settings
        Config.MERGE_SUBTITLE_ENCODING = "none"
        Config.MERGE_SUBTITLE_FONT = "none"
        Config.MERGE_SUBTITLE_FONT_SIZE = 0
        Config.MERGE_SUBTITLE_FONT_COLOR = "none"
        Config.MERGE_SUBTITLE_BACKGROUND = "none"

        # Reset document settings
        Config.MERGE_DOCUMENT_PAPER_SIZE = "none"
        Config.MERGE_DOCUMENT_ORIENTATION = "none"
        Config.MERGE_DOCUMENT_MARGIN = 0

        # Reset general settings
        Config.MERGE_METADATA_TITLE = "none"
        Config.MERGE_METADATA_AUTHOR = "none"
        Config.MERGE_METADATA_COMMENT = "none"
        Config.MERGE_PRIORITY = 1
        Config.MERGE_THREADING = True
        Config.MERGE_THREAD_NUMBER = 4
        Config.MERGE_REMOVE_ORIGINAL = True
        # Update the database
        await database.update_config(
            {
                "MERGE_ENABLED": False,
                "CONCAT_DEMUXER_ENABLED": True,
                "FILTER_COMPLEX_ENABLED": False,
                # Output formats
                "MERGE_OUTPUT_FORMAT_VIDEO": "mkv",
                "MERGE_OUTPUT_FORMAT_AUDIO": "mp3",
                "MERGE_OUTPUT_FORMAT_IMAGE": "jpg",
                "MERGE_OUTPUT_FORMAT_DOCUMENT": "pdf",
                "MERGE_OUTPUT_FORMAT_SUBTITLE": "srt",
                # Video settings
                "MERGE_VIDEO_CODEC": "none",
                "MERGE_VIDEO_QUALITY": "none",
                "MERGE_VIDEO_PRESET": "none",
                "MERGE_VIDEO_CRF": 0,
                "MERGE_VIDEO_PIXEL_FORMAT": "none",
                "MERGE_VIDEO_TUNE": "none",
                "MERGE_VIDEO_FASTSTART": False,
                # Audio settings
                "MERGE_AUDIO_CODEC": "none",
                "MERGE_AUDIO_BITRATE": "none",
                "MERGE_AUDIO_CHANNELS": 0,
                "MERGE_AUDIO_SAMPLING": "none",
                "MERGE_AUDIO_VOLUME": 0.0,
                # Image settings
                "MERGE_IMAGE_MODE": "none",
                "MERGE_IMAGE_COLUMNS": 0,
                "MERGE_IMAGE_QUALITY": 0,
                "MERGE_IMAGE_DPI": 0,
                "MERGE_IMAGE_RESIZE": "none",
                "MERGE_IMAGE_BACKGROUND": "none",
                # Subtitle settings
                "MERGE_SUBTITLE_ENCODING": "none",
                "MERGE_SUBTITLE_FONT": "none",
                "MERGE_SUBTITLE_FONT_SIZE": 0,
                "MERGE_SUBTITLE_FONT_COLOR": "none",
                "MERGE_SUBTITLE_BACKGROUND": "none",
                # Document settings
                "MERGE_DOCUMENT_PAPER_SIZE": "none",
                "MERGE_DOCUMENT_ORIENTATION": "none",
                "MERGE_DOCUMENT_MARGIN": 0,
                # General settings
                "MERGE_METADATA_TITLE": "none",
                "MERGE_METADATA_AUTHOR": "none",
                "MERGE_METADATA_COMMENT": "none",
                "MERGE_PRIORITY": 1,
                "MERGE_THREADING": True,
                "MERGE_THREAD_NUMBER": 4,
                "MERGE_REMOVE_ORIGINAL": True,
            }
        )
        # Keep the current page
        await update_buttons(message, "mediatools_merge")
    # This is a duplicate handler, removed to avoid confusion
    elif data[1] == "edit" and data[2] in [
        "mediatools_watermark",
        "mediatools_merge",
        "mediatools_merge_config",
        "mediatools_metadata",
        "mediatools_convert",
        "mediatools_compression",
        "mediatools_trim",
        "mediatools_extract",
        "ai",
    ]:
        await query.answer()
        # Set the global state to edit mode
        globals()["state"] = "edit"
        # For merge settings, maintain the current page
        if data[2] == "mediatools_merge":
            # Just update the state, the page is maintained by the global merge_page variable
            LOGGER.debug(f"Using merge_page: {globals()['merge_page']}")
            await update_buttons(
                message, "mediatools_merge", page=globals()["merge_page"]
            )
        elif data[2] == "mediatools_metadata":
            await update_buttons(message, "mediatools_metadata")
        elif data[2] == "mediatools_convert":
            await update_buttons(message, "mediatools_convert")
        elif data[2] == "mediatools_compression":
            await update_buttons(message, "mediatools_compression")
        elif data[2] == "mediatools_trim":
            await update_buttons(message, "mediatools_trim")
        elif data[2] == "mediatools_extract":
            await update_buttons(message, "mediatools_extract")
        elif data[2] == "ai":
            await update_buttons(message, "ai")
        else:
            await update_buttons(message, data[2])
    elif data[1] == "view" and data[2] in [
        "mediatools_watermark",
        "mediatools_merge",
        "mediatools_merge_config",
        "mediatools_metadata",
        "mediatools_convert",
        "mediatools_compression",
        "mediatools_trim",
        "mediatools_extract",
        "ai",
    ]:
        await query.answer()
        # Set the global state to view mode
        globals()["state"] = "view"
        # For merge settings, maintain the current page
        if data[2] == "mediatools_merge":
            LOGGER.debug(f"Using merge_page: {globals()['merge_page']}")
            await update_buttons(
                message, "mediatools_merge", page=globals()["merge_page"]
            )
        elif data[2] == "mediatools_metadata":
            await update_buttons(message, "mediatools_metadata")
        elif data[2] == "mediatools_convert":
            await update_buttons(message, "mediatools_convert")
        elif data[2] == "mediatools_compression":
            await update_buttons(message, "mediatools_compression")
        elif data[2] == "mediatools_trim":
            await update_buttons(message, "mediatools_trim")
        elif data[2] == "mediatools_extract":
            await update_buttons(message, "mediatools_extract")
        elif data[2] == "ai":
            await update_buttons(message, "ai")
        else:
            await update_buttons(message, data[2])
        # This section is now handled above
    elif data[1] == "editvar" and data[2] in [
        "WATERMARK_ENABLED",
        "WATERMARK_KEY",
        "WATERMARK_POSITION",
        "WATERMARK_SIZE",
        "WATERMARK_COLOR",
        "WATERMARK_FONT",
        "WATERMARK_PRIORITY",
        "WATERMARK_THREADING",
        "WATERMARK_THREAD_NUMBER",
        "WATERMARK_FAST_MODE",
        "WATERMARK_MAINTAIN_QUALITY",
        "WATERMARK_OPACITY",
        "AUDIO_WATERMARK_ENABLED",
        "AUDIO_WATERMARK_TEXT",
        "AUDIO_WATERMARK_VOLUME",
        "SUBTITLE_WATERMARK_ENABLED",
        "SUBTITLE_WATERMARK_TEXT",
        "SUBTITLE_WATERMARK_STYLE",
        "MEDIAINFO_ENABLED",
        "METADATA_KEY",
        "METADATA_ALL",
        "METADATA_TITLE",
        "METADATA_AUTHOR",
        "METADATA_COMMENT",
        "METADATA_VIDEO_TITLE",
        "METADATA_VIDEO_AUTHOR",
        "METADATA_VIDEO_COMMENT",
        "METADATA_AUDIO_TITLE",
        "METADATA_AUDIO_AUTHOR",
        "METADATA_AUDIO_COMMENT",
        "METADATA_SUBTITLE_TITLE",
        "METADATA_SUBTITLE_AUTHOR",
        "METADATA_SUBTITLE_COMMENT",
        "MERGE_ENABLED",
        "CONCAT_DEMUXER_ENABLED",
        "FILTER_COMPLEX_ENABLED",
        "MERGE_OUTPUT_FORMAT_VIDEO",
        "MERGE_OUTPUT_FORMAT_AUDIO",
        "MERGE_OUTPUT_FORMAT_IMAGE",
        "MERGE_OUTPUT_FORMAT_DOCUMENT",
        "MERGE_OUTPUT_FORMAT_SUBTITLE",
        "MERGE_IMAGE_MODE",
        "MERGE_IMAGE_COLUMNS",
        "MERGE_IMAGE_QUALITY",
        "MERGE_IMAGE_DPI",
        "MERGE_IMAGE_RESIZE",
        "MERGE_IMAGE_BACKGROUND",
        "MERGE_VIDEO_CODEC",
        "MERGE_VIDEO_QUALITY",
        "MERGE_VIDEO_PRESET",
        "MERGE_VIDEO_CRF",
        "MERGE_VIDEO_PIXEL_FORMAT",
        "MERGE_VIDEO_TUNE",
        "MERGE_VIDEO_FASTSTART",
        "MERGE_AUDIO_CODEC",
        "MERGE_AUDIO_BITRATE",
        "MERGE_AUDIO_CHANNELS",
        "MERGE_AUDIO_SAMPLING",
        "MERGE_AUDIO_VOLUME",
        "MERGE_SUBTITLE_ENCODING",
        "MERGE_SUBTITLE_FONT",
        "MERGE_SUBTITLE_FONT_SIZE",
        "MERGE_SUBTITLE_FONT_COLOR",
        "MERGE_SUBTITLE_BACKGROUND",
        "MERGE_DOCUMENT_PAPER_SIZE",
        "MERGE_DOCUMENT_ORIENTATION",
        "MERGE_DOCUMENT_MARGIN",
        "MERGE_METADATA_TITLE",
        "MERGE_METADATA_AUTHOR",
        "MERGE_METADATA_COMMENT",
        "MERGE_PRIORITY",
        "MERGE_THREADING",
        "MERGE_THREAD_NUMBER",
        "MERGE_REMOVE_ORIGINAL",
        "CONVERT_ENABLED",
        "CONVERT_PRIORITY",
        "CONVERT_DELETE_ORIGINAL",
        "CONVERT_VIDEO_ENABLED",
        "CONVERT_VIDEO_FORMAT",
        "CONVERT_VIDEO_CODEC",
        "CONVERT_VIDEO_QUALITY",
        "CONVERT_VIDEO_CRF",
        "CONVERT_VIDEO_PRESET",
        "CONVERT_VIDEO_MAINTAIN_QUALITY",
        "CONVERT_VIDEO_RESOLUTION",
        "CONVERT_VIDEO_FPS",
        "CONVERT_VIDEO_DELETE_ORIGINAL",
        "CONVERT_AUDIO_ENABLED",
        "CONVERT_AUDIO_FORMAT",
        "CONVERT_AUDIO_CODEC",
        "CONVERT_AUDIO_BITRATE",
        "CONVERT_AUDIO_CHANNELS",
        "CONVERT_AUDIO_SAMPLING",
        "CONVERT_AUDIO_VOLUME",
        "CONVERT_AUDIO_DELETE_ORIGINAL",
        "CONVERT_SUBTITLE_ENABLED",
        "CONVERT_SUBTITLE_FORMAT",
        "CONVERT_SUBTITLE_ENCODING",
        "CONVERT_SUBTITLE_LANGUAGE",
        "CONVERT_SUBTITLE_DELETE_ORIGINAL",
        "CONVERT_DOCUMENT_ENABLED",
        "CONVERT_DOCUMENT_FORMAT",
        "CONVERT_DOCUMENT_QUALITY",
        "CONVERT_DOCUMENT_DPI",
        "CONVERT_DOCUMENT_DELETE_ORIGINAL",
        "CONVERT_ARCHIVE_ENABLED",
        "CONVERT_ARCHIVE_FORMAT",
        "CONVERT_ARCHIVE_LEVEL",
        "CONVERT_ARCHIVE_METHOD",
        "CONVERT_ARCHIVE_DELETE_ORIGINAL",
        "COMPRESSION_ENABLED",
        "COMPRESSION_PRIORITY",
        "COMPRESSION_VIDEO_ENABLED",
        "COMPRESSION_VIDEO_PRESET",
        "COMPRESSION_VIDEO_CRF",
        "COMPRESSION_VIDEO_CODEC",
        "COMPRESSION_VIDEO_TUNE",
        "COMPRESSION_VIDEO_PIXEL_FORMAT",
        "COMPRESSION_AUDIO_ENABLED",
        "COMPRESSION_AUDIO_PRESET",
        "COMPRESSION_AUDIO_CODEC",
        "COMPRESSION_AUDIO_BITRATE",
        "COMPRESSION_AUDIO_CHANNELS",
        "COMPRESSION_IMAGE_ENABLED",
        "COMPRESSION_IMAGE_PRESET",
        "COMPRESSION_IMAGE_QUALITY",
        "COMPRESSION_IMAGE_RESIZE",
        "COMPRESSION_DOCUMENT_ENABLED",
        "COMPRESSION_DOCUMENT_PRESET",
        "COMPRESSION_DOCUMENT_DPI",
        "COMPRESSION_SUBTITLE_ENABLED",
        "COMPRESSION_SUBTITLE_PRESET",
        "COMPRESSION_SUBTITLE_ENCODING",
        "COMPRESSION_ARCHIVE_ENABLED",
        "COMPRESSION_ARCHIVE_PRESET",
        "COMPRESSION_ARCHIVE_LEVEL",
        "COMPRESSION_ARCHIVE_METHOD",
        "TRIM_ENABLED",
        "TRIM_PRIORITY",
        "TRIM_START_TIME",
        "TRIM_END_TIME",
        "TRIM_VIDEO_ENABLED",
        "TRIM_VIDEO_CODEC",
        "TRIM_VIDEO_PRESET",
        "TRIM_AUDIO_ENABLED",
        "TRIM_AUDIO_CODEC",
        "TRIM_AUDIO_PRESET",
        "TRIM_IMAGE_ENABLED",
        "TRIM_IMAGE_QUALITY",
        "TRIM_DOCUMENT_ENABLED",
        "TRIM_DOCUMENT_QUALITY",
        "TRIM_SUBTITLE_ENABLED",
        "TRIM_SUBTITLE_ENCODING",
        "TRIM_ARCHIVE_ENABLED",
        "EXTRACT_ENABLED",
        "EXTRACT_PRIORITY",
        "EXTRACT_DELETE_ORIGINAL",
        "EXTRACT_VIDEO_ENABLED",
        "EXTRACT_VIDEO_CODEC",
        "EXTRACT_VIDEO_FORMAT",
        "EXTRACT_VIDEO_INDEX",
        "EXTRACT_VIDEO_QUALITY",
        "EXTRACT_VIDEO_PRESET",
        "EXTRACT_VIDEO_BITRATE",
        "EXTRACT_VIDEO_RESOLUTION",
        "EXTRACT_VIDEO_FPS",
        "EXTRACT_AUDIO_ENABLED",
        "EXTRACT_AUDIO_CODEC",
        "EXTRACT_AUDIO_FORMAT",
        "EXTRACT_AUDIO_INDEX",
        "EXTRACT_AUDIO_BITRATE",
        "EXTRACT_AUDIO_CHANNELS",
        "EXTRACT_AUDIO_SAMPLING",
        "EXTRACT_AUDIO_VOLUME",
        "EXTRACT_SUBTITLE_ENABLED",
        "EXTRACT_SUBTITLE_CODEC",
        "EXTRACT_SUBTITLE_FORMAT",
        "EXTRACT_SUBTITLE_INDEX",
        "EXTRACT_SUBTITLE_LANGUAGE",
        "EXTRACT_SUBTITLE_ENCODING",
        "EXTRACT_SUBTITLE_FONT",
        "EXTRACT_SUBTITLE_FONT_SIZE",
        "EXTRACT_ATTACHMENT_ENABLED",
        "EXTRACT_ATTACHMENT_FORMAT",
        "EXTRACT_ATTACHMENT_INDEX",
        "EXTRACT_ATTACHMENT_FILTER",
        "EXTRACT_MAINTAIN_QUALITY",
        "MEDIA_TOOLS_PRIORITY",
        "TASK_MONITOR_ENABLED",
        "TASK_MONITOR_INTERVAL",
        "TASK_MONITOR_CONSECUTIVE_CHECKS",
        "TASK_MONITOR_SPEED_THRESHOLD",
        "TASK_MONITOR_ELAPSED_THRESHOLD",
        "TASK_MONITOR_ETA_THRESHOLD",
        "TASK_MONITOR_WAIT_TIME",
        "TASK_MONITOR_COMPLETION_THRESHOLD",
        "TASK_MONITOR_CPU_HIGH",
        "TASK_MONITOR_CPU_LOW",
        "TASK_MONITOR_MEMORY_HIGH",
        "TASK_MONITOR_MEMORY_LOW",
        "DEFAULT_AI_PROVIDER",
        "MISTRAL_API_KEY",
        "MISTRAL_API_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_API_URL",
        "CHATGPT_API_KEY",
        "CHATGPT_API_URL",
        "GEMINI_API_KEY",
        "GEMINI_API_URL",
    ]:
        # Handle view mode for all settings
        if state == "view":
            # In view mode, show the current value in a popup
            value = f"{Config.get(data[2])}"
            if len(value) > 200:
                await query.answer()
                with BytesIO(str.encode(value)) as out_file:
                    out_file.name = f"{data[2]}.txt"
                    await send_file(message, out_file)
                return
            if value == "":
                value = None
            await query.answer(f"{value}", show_alert=True)
            return

        # Handle edit mode for all settings
        await query.answer()
        # Make sure we're in edit mode
        if state != "edit":
            globals()["state"] = "edit"
            await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_variable, pre_message=message, key=data[2])

        # Determine which menu to return to based on the key
        if (
            data[2].startswith("WATERMARK_")
            or data[2].startswith("AUDIO_WATERMARK_")
            or data[2].startswith("SUBTITLE_WATERMARK_")
        ):
            rfunc = partial(update_buttons, message, "mediatools_watermark")
        elif data[2].startswith("METADATA_"):
            rfunc = partial(update_buttons, message, "mediatools_metadata")
        elif data[2].startswith("CONVERT_"):
            rfunc = partial(update_buttons, message, "mediatools_convert")
        elif data[2].startswith("COMPRESSION_"):
            rfunc = partial(update_buttons, message, "mediatools_compression")
        elif data[2].startswith("TRIM_"):
            rfunc = partial(update_buttons, message, "mediatools_trim")
        elif data[2].startswith("EXTRACT_"):
            rfunc = partial(update_buttons, message, "mediatools_extract")
        elif data[2].startswith("TASK_MONITOR_"):
            rfunc = partial(update_buttons, message, "taskmonitor")
        elif (
            data[2] == "DEFAULT_AI_PROVIDER"
        ):  # Create a special menu for selecting the AI provider
            buttons = ButtonMaker()
            buttons.data_button("Mistral", "botset setprovider mistral")
            buttons.data_button("DeepSeek", "botset setprovider deepseek")
            buttons.data_button("ChatGPT", "botset setprovider chatgpt")
            buttons.data_button("Gemini", "botset setprovider gemini")
            buttons.data_button("Cancel", "botset cancel")

            await edit_message(
                message,
                "<b>Select Default AI Provider</b>\n\nChoose which AI provider to use with the /ask command:",
                buttons.build_menu(2),
            )
            return
        elif (
            data[2].startswith("MISTRAL_")
            or data[2].startswith("DEEPSEEK_")
            or data[2].startswith("CHATGPT_")
            or data[2].startswith("GEMINI_")
        ):
            rfunc = partial(update_buttons, message, "ai")
        elif data[2].startswith("MERGE_") or data[2] in [
            "CONCAT_DEMUXER_ENABLED",
            "FILTER_COMPLEX_ENABLED",
        ]:
            # Check if we're in the merge_config menu
            if (message.text and "Merge Configuration" in message.text) or (
                data[2].startswith("MERGE_")
                and any(
                    x in data[2]
                    for x in [
                        "OUTPUT_FORMAT",
                        "VIDEO_",
                        "AUDIO_",
                        "IMAGE_",
                        "SUBTITLE_",
                        "DOCUMENT_",
                        "METADATA_",
                    ]
                )
            ):
                rfunc = partial(update_buttons, message, "mediatools_merge_config")
            # Check if we need to return to a specific page in mediatools_merge
            elif message.text and "Page:" in message.text:
                try:
                    page_info = message.text.split("Page:")[1].strip().split("/")[0]
                    page_no = int(page_info) - 1
                    # Set the global merge_page variable to ensure we return to the correct page
                    globals()["merge_page"] = page_no
                    rfunc = partial(update_buttons, message, "mediatools_merge")
                except (ValueError, IndexError):
                    rfunc = partial(update_buttons, message, "mediatools_merge")
            else:
                # Use the global merge_page variable
                rfunc = partial(update_buttons, message, "mediatools_merge")
        else:
            rfunc = partial(update_buttons, message, "var")

        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == "default_taskmonitor":
        await query.answer("Resetting all task monitoring settings to default...")
        # Reset all task monitoring settings to default
        Config.TASK_MONITOR_ENABLED = DEFAULT_VALUES["TASK_MONITOR_ENABLED"]
        Config.TASK_MONITOR_INTERVAL = DEFAULT_VALUES["TASK_MONITOR_INTERVAL"]
        Config.TASK_MONITOR_CONSECUTIVE_CHECKS = DEFAULT_VALUES[
            "TASK_MONITOR_CONSECUTIVE_CHECKS"
        ]
        Config.TASK_MONITOR_SPEED_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_SPEED_THRESHOLD"
        ]
        Config.TASK_MONITOR_ELAPSED_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_ELAPSED_THRESHOLD"
        ]
        Config.TASK_MONITOR_ETA_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_ETA_THRESHOLD"
        ]
        Config.TASK_MONITOR_WAIT_TIME = DEFAULT_VALUES["TASK_MONITOR_WAIT_TIME"]
        Config.TASK_MONITOR_COMPLETION_THRESHOLD = DEFAULT_VALUES[
            "TASK_MONITOR_COMPLETION_THRESHOLD"
        ]
        Config.TASK_MONITOR_CPU_HIGH = DEFAULT_VALUES["TASK_MONITOR_CPU_HIGH"]
        Config.TASK_MONITOR_CPU_LOW = DEFAULT_VALUES["TASK_MONITOR_CPU_LOW"]
        Config.TASK_MONITOR_MEMORY_HIGH = DEFAULT_VALUES["TASK_MONITOR_MEMORY_HIGH"]
        Config.TASK_MONITOR_MEMORY_LOW = DEFAULT_VALUES["TASK_MONITOR_MEMORY_LOW"]

        # Update the database
        await database.update_config(
            {
                "TASK_MONITOR_ENABLED": DEFAULT_VALUES["TASK_MONITOR_ENABLED"],
                "TASK_MONITOR_INTERVAL": DEFAULT_VALUES["TASK_MONITOR_INTERVAL"],
                "TASK_MONITOR_CONSECUTIVE_CHECKS": DEFAULT_VALUES[
                    "TASK_MONITOR_CONSECUTIVE_CHECKS"
                ],
                "TASK_MONITOR_SPEED_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_SPEED_THRESHOLD"
                ],
                "TASK_MONITOR_ELAPSED_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_ELAPSED_THRESHOLD"
                ],
                "TASK_MONITOR_ETA_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_ETA_THRESHOLD"
                ],
                "TASK_MONITOR_WAIT_TIME": DEFAULT_VALUES["TASK_MONITOR_WAIT_TIME"],
                "TASK_MONITOR_COMPLETION_THRESHOLD": DEFAULT_VALUES[
                    "TASK_MONITOR_COMPLETION_THRESHOLD"
                ],
                "TASK_MONITOR_CPU_HIGH": DEFAULT_VALUES["TASK_MONITOR_CPU_HIGH"],
                "TASK_MONITOR_CPU_LOW": DEFAULT_VALUES["TASK_MONITOR_CPU_LOW"],
                "TASK_MONITOR_MEMORY_HIGH": DEFAULT_VALUES[
                    "TASK_MONITOR_MEMORY_HIGH"
                ],
                "TASK_MONITOR_MEMORY_LOW": DEFAULT_VALUES["TASK_MONITOR_MEMORY_LOW"],
            }
        )
        # Keep the current page
        await update_buttons(message, "taskmonitor")

    elif data[1] == "default_merge_config":
        await query.answer("Resetting all merge config settings to default...")
        # Reset all merge config settings to default
        # Reset output formats
        Config.MERGE_OUTPUT_FORMAT_VIDEO = "mkv"
        Config.MERGE_OUTPUT_FORMAT_AUDIO = "mp3"
        Config.MERGE_OUTPUT_FORMAT_IMAGE = "jpg"
        Config.MERGE_OUTPUT_FORMAT_DOCUMENT = "pdf"
        Config.MERGE_OUTPUT_FORMAT_SUBTITLE = "srt"

        # Reset video settings
        Config.MERGE_VIDEO_CODEC = "none"
        Config.MERGE_VIDEO_QUALITY = "none"
        Config.MERGE_VIDEO_PRESET = "none"
        Config.MERGE_VIDEO_CRF = 0
        Config.MERGE_VIDEO_PIXEL_FORMAT = "none"
        Config.MERGE_VIDEO_TUNE = "none"
        Config.MERGE_VIDEO_FASTSTART = False

        # Reset audio settings
        Config.MERGE_AUDIO_CODEC = "none"
        Config.MERGE_AUDIO_BITRATE = "none"
        Config.MERGE_AUDIO_CHANNELS = 0
        Config.MERGE_AUDIO_SAMPLING = "none"
        Config.MERGE_AUDIO_VOLUME = 0.0

        # Reset image settings
        Config.MERGE_IMAGE_MODE = "none"
        Config.MERGE_IMAGE_COLUMNS = 0
        Config.MERGE_IMAGE_QUALITY = 0
        Config.MERGE_IMAGE_DPI = 0
        Config.MERGE_IMAGE_RESIZE = "none"
        Config.MERGE_IMAGE_BACKGROUND = "none"

        # Reset subtitle settings
        Config.MERGE_SUBTITLE_ENCODING = "none"
        Config.MERGE_SUBTITLE_FONT = "none"
        Config.MERGE_SUBTITLE_FONT_SIZE = 0
        Config.MERGE_SUBTITLE_FONT_COLOR = "none"
        Config.MERGE_SUBTITLE_BACKGROUND = "none"

        # Reset document settings
        Config.MERGE_DOCUMENT_PAPER_SIZE = "none"
        Config.MERGE_DOCUMENT_ORIENTATION = "none"
        Config.MERGE_DOCUMENT_MARGIN = 0

        # Reset metadata settings
        Config.MERGE_METADATA_TITLE = "none"
        Config.MERGE_METADATA_AUTHOR = "none"
        Config.MERGE_METADATA_COMMENT = "none"

        # Update the database
        await database.update_config(
            {
                # Output formats
                "MERGE_OUTPUT_FORMAT_VIDEO": "mkv",
                "MERGE_OUTPUT_FORMAT_AUDIO": "mp3",
                "MERGE_OUTPUT_FORMAT_IMAGE": "jpg",
                "MERGE_OUTPUT_FORMAT_DOCUMENT": "pdf",
                "MERGE_OUTPUT_FORMAT_SUBTITLE": "srt",
                # Video settings
                "MERGE_VIDEO_CODEC": "none",
                "MERGE_VIDEO_QUALITY": "none",
                "MERGE_VIDEO_PRESET": "none",
                "MERGE_VIDEO_CRF": 0,
                "MERGE_VIDEO_PIXEL_FORMAT": "none",
                "MERGE_VIDEO_TUNE": "none",
                "MERGE_VIDEO_FASTSTART": False,
                # Audio settings
                "MERGE_AUDIO_CODEC": "none",
                "MERGE_AUDIO_BITRATE": "none",
                "MERGE_AUDIO_CHANNELS": 0,
                "MERGE_AUDIO_SAMPLING": "none",
                "MERGE_AUDIO_VOLUME": 0.0,
                # Image settings
                "MERGE_IMAGE_MODE": "none",
                "MERGE_IMAGE_COLUMNS": 0,
                "MERGE_IMAGE_QUALITY": 0,
                "MERGE_IMAGE_DPI": 0,
                "MERGE_IMAGE_RESIZE": "none",
                "MERGE_IMAGE_BACKGROUND": "none",
                # Subtitle settings
                "MERGE_SUBTITLE_ENCODING": "none",
                "MERGE_SUBTITLE_FONT": "none",
                "MERGE_SUBTITLE_FONT_SIZE": 0,
                "MERGE_SUBTITLE_FONT_COLOR": "none",
                "MERGE_SUBTITLE_BACKGROUND": "none",
                # Document settings
                "MERGE_DOCUMENT_PAPER_SIZE": "none",
                "MERGE_DOCUMENT_ORIENTATION": "none",
                "MERGE_DOCUMENT_MARGIN": 0,
                # Metadata settings
                "MERGE_METADATA_TITLE": "none",
                "MERGE_METADATA_AUTHOR": "none",
                "MERGE_METADATA_COMMENT": "none",
            }
        )
        # Keep the current page
        await update_buttons(message, "mediatools_merge_config")
    elif data[1] in [
        "var",
        "aria",
        "qbit",
        "nzb",
        "nzbserver",
        "mediatools",
        "mediatools_watermark",
        "mediatools_merge",
        "mediatools_merge_config",
        "mediatools_metadata",
        "mediatools_convert",
        "mediatools_compression",
        "mediatools_trim",
        "mediatools_extract",
        "ai",
        "taskmonitor",
    ] or data[1].startswith(
        "nzbser",
    ):
        if data[1] == "nzbserver":
            globals()["start"] = 0
        await query.answer()
        await update_buttons(message, data[1])
    elif data[1] == "resetvar":
        await query.answer()
        value = ""
        if data[2] in DEFAULT_VALUES:
            value = DEFAULT_VALUES[data[2]]
        elif data[2] == "EXCLUDED_EXTENSIONS":
            excluded_extensions.clear()
            excluded_extensions.extend(["aria2", "!qB"])
        elif data[2] == "TORRENT_TIMEOUT":
            await TorrentManager.change_aria2_option("bt-stop-timeout", "0")
            await database.update_aria2("bt-stop-timeout", "0")
        elif data[2] == "PIL_MEMORY_LIMIT":
            value = 2048  # Default to 2GB
        elif data[2] == "BASE_URL":
            await (
                await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")
            ).wait()
        elif data[2] == "BASE_URL_PORT":
            value = 80
            if Config.BASE_URL:
                await (
                    await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")
                ).wait()
                await create_subprocess_shell(
                    f"gunicorn -k uvicorn.workers.UvicornWorker -w 1 web.wserver:app --bind 0.0.0.0:{value}",
                )
        elif data[2] == "GDRIVE_ID":
            if drives_names and drives_names[0] == "Main":
                drives_names.pop(0)
                drives_ids.pop(0)
                index_urls.pop(0)
        elif data[2] == "INDEX_URL":
            if drives_names and drives_names[0] == "Main":
                index_urls[0] = ""
        elif data[2] == "INCOMPLETE_TASK_NOTIFIER":
            await database.trunc_table("tasks")
        elif data[2] in ["JD_EMAIL", "JD_PASS"]:
            await create_subprocess_exec("pkill", "-9", "-f", "java")
        elif data[2] == "USENET_SERVERS":
            for s in Config.USENET_SERVERS:
                await sabnzbd_client.delete_config("servers", s["name"])
        elif data[2] == "AUTHORIZED_CHATS":
            auth_chats.clear()
        elif data[2] == "SUDO_USERS":
            sudo_users.clear()
        Config.set(data[2], value)
        await update_buttons(message, "var")
        if data[2] == "DATABASE_URL":
            await database.disconnect()
        await database.update_config({data[2]: value})
        if data[2] in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
            await start_from_queued()
        elif data[2] in [
            "RCLONE_SERVE_URL",
            "RCLONE_SERVE_PORT",
            "RCLONE_SERVE_USER",
            "RCLONE_SERVE_PASS",
        ]:
            await rclone_serve_booter()
    elif data[1] == "syncaria":
        await query.answer()
        aria2_options.clear()
        await update_aria2_options()
        await update_buttons(message, "aria")
    elif data[1] == "syncqbit":
        await query.answer()
        qbit_options.clear()
        await update_qb_options()
        await database.save_qbit_settings()
    elif data[1] == "resetnzb":
        await query.answer()
        res = await sabnzbd_client.set_config_default(data[2])
        nzb_options[data[2]] = res["config"]["misc"][data[2]]
        await update_buttons(message, "nzb")
        await database.update_nzb_config()
    elif data[1] == "syncnzb":
        await query.answer(
            "Syncronization Started. It takes up to 2 sec!",
            show_alert=True,
        )
        nzb_options.clear()
        await update_nzb_options()
        await database.update_nzb_config()
    elif data[1] == "emptyaria":
        await query.answer()
        aria2_options[data[2]] = ""
        await update_buttons(message, "aria")
        await TorrentManager.change_aria2_option(data[2], "")
        await database.update_aria2(data[2], "")
    elif data[1] == "emptyqbit":
        await query.answer()
        value = ""
        if isinstance(qbit_options[data[2]], bool):
            value = False
        elif isinstance(qbit_options[data[2]], int):
            value = 0
        elif isinstance(qbit_options[data[2]], float):
            value = 0.0
        await TorrentManager.qbittorrent.app.set_preferences({data[2]: value})
        qbit_options[data[2]] = value
        await update_buttons(message, "qbit")
        await database.update_qbittorrent(data[2], value)
    elif data[1] == "emptynzb":
        await query.answer()
        res = await sabnzbd_client.set_config("misc", data[2], "")
        nzb_options[data[2]] = res["config"]["misc"][data[2]]
        await update_buttons(message, "nzb")
        await database.update_nzb_config()
    elif data[1] == "remser":
        index = int(data[2])
        await sabnzbd_client.delete_config(
            "servers",
            Config.USENET_SERVERS[index]["name"],
        )
        del Config.USENET_SERVERS[index]
        await update_buttons(message, "nzbserver")
        await database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})
    elif data[1] == "private":
        await query.answer()
        await update_buttons(message, data[1])
        pfunc = partial(update_private_file, pre_message=message)
        rfunc = partial(update_buttons, message)
        await event_handler(client, query, pfunc, rfunc, True)
    elif data[1] == "botvar" and state == "edit":
        await query.answer()  # Special handling for MEDIA_TOOLS_ENABLED
        if data[2] == "MEDIA_TOOLS_ENABLED":
            # Create a special menu for selecting media tools
            buttons = ButtonMaker()

            # Get current value
            current_value = Config.get(data[2])

            # List of all available media tools
            all_tools = [
                "watermark",
                "merge",
                "convert",
                "compression",
                "trim",
                "extract",
                "metadata",
                "ffmpeg",
                "sample",
            ]

            # If it's a string with comma-separated values, parse it
            enabled_tools = []
            if isinstance(current_value, str) and "," in current_value:
                enabled_tools = [t.strip().lower() for t in current_value.split(",")]
            elif (
                current_value is True
            ):  # If it's True (boolean), all tools are enabled
                enabled_tools = all_tools.copy()

            # Add toggle buttons for each tool
            for tool in all_tools:
                status = "✅" if tool in enabled_tools else "❌"
                buttons.data_button(
                    f"{tool.title()}: {status}",
                    f"botset toggle_tool {data[2]} {tool}",
                )

            # Add buttons to enable/disable all tools
            buttons.data_button("Enable All", f"botset enable_all_tools {data[2]}")
            buttons.data_button("Disable All", f"botset disable_all_tools {data[2]}")

            # Add cancel button
            buttons.data_button("Done", "botset var")

            # Show the number of enabled tools in the message
            await edit_message(
                message,
                f"<b>Configure Media Tools</b>\n\nSelect which media tools to enable ({len(enabled_tools)}/{len(all_tools)} enabled):",
                buttons.build_menu(2),
            )
            return

        # For other settings, proceed with normal botvar handling
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_variable, pre_message=message, key=data[2])

        # Determine which menu to return to based on the key
        if data[2].startswith("METADATA_"):
            rfunc = partial(update_buttons, message, "mediatools_metadata")
        elif data[2].startswith("CONVERT_"):
            rfunc = partial(update_buttons, message, "mediatools_convert")
        elif (
            data[2] == "DEFAULT_AI_PROVIDER"
        ):  # Create a special menu for selecting the AI provider
            buttons = ButtonMaker()
            buttons.data_button("Mistral", "botset setprovider mistral")
            buttons.data_button("DeepSeek", "botset setprovider deepseek")
            buttons.data_button("ChatGPT", "botset setprovider chatgpt")
            buttons.data_button("Gemini", "botset setprovider gemini")
            buttons.data_button("Cancel", "botset cancel")

            await edit_message(
                message,
                "<b>Select Default AI Provider</b>\n\nChoose which AI provider to use with the /ask command:",
                buttons.build_menu(2),
            )
            return
        elif (
            data[2].startswith("MISTRAL_")
            or data[2].startswith("DEEPSEEK_")
            or data[2].startswith("CHATGPT_")
            or data[2].startswith("GEMINI_")
        ):
            rfunc = partial(update_buttons, message, "ai")
        else:
            rfunc = partial(update_buttons, message, "var")

        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == "botvar" and state == "view":
        # In view mode, show the value
        value = f"{Config.get(data[2])}"

        # Show the value
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await send_file(message, out_file)
            return
        if value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "ariavar" and (state == "edit" or data[2] == "newkey"):
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_aria, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, "aria")
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == "ariavar" and state == "view":
        value = f"{aria2_options[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await send_file(message, out_file)
            return
        if value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "qbitvar" and state == "edit":
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_qbit, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, "qbit")
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == "qbitvar" and state == "view":
        value = f"{qbit_options[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await send_file(message, out_file)
            return
        if value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "nzbvar" and state == "edit":
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_nzb, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, "nzb")
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == "nzbvar" and state == "view":
        value = f"{nzb_options[data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await send_file(message, out_file)
            return
        if value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "emptyserkey":
        await query.answer()
        await update_buttons(message, f"nzbser{data[2]}")
        index = int(data[2])
        res = await sabnzbd_client.add_server(
            {"name": Config.USENET_SERVERS[index]["name"], data[3]: ""},
        )
        Config.USENET_SERVERS[index][data[3]] = res["config"]["servers"][0][data[3]]
        await database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})
    elif data[1].startswith("nzbsevar") and (state == "edit" or data[2] == "newser"):
        index = 0 if data[2] == "newser" else int(data[1].replace("nzbsevar", ""))
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(
            edit_nzb_server,
            pre_message=message,
            key=data[2],
            index=index,
        )
        rfunc = partial(update_buttons, message, data[1])
        await event_handler(client, query, pfunc, rfunc)
    elif data[1].startswith("nzbsevar") and state == "view":
        index = int(data[1].replace("nzbsevar", ""))
        value = f"{Config.USENET_SERVERS[index][data[2]]}"
        if len(value) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await send_file(message, out_file)
            return
        if value == "":
            value = None
        await query.answer(f"{value}", show_alert=True)
    elif data[1] == "toggle_tool":
        await query.answer()
        key = data[2]  # MEDIA_TOOLS_ENABLED
        tool = data[3]  # The tool to toggle

        # Get current value
        current_value = Config.get(key)

        # List of all available tools
        all_tools = [
            "watermark",
            "merge",
            "convert",
            "compression",
            "trim",
            "extract",
            "metadata",
            "ffmpeg",
            "sample",
        ]

        # Parse current enabled tools
        enabled_tools = []
        if isinstance(current_value, str):
            # Handle both comma-separated and single values
            if "," in current_value:
                enabled_tools = [
                    t.strip().lower() for t in current_value.split(",") if t.strip()
                ]
            elif current_value.strip():  # Single non-empty value
                enabled_tools = [current_value.strip().lower()]
        elif current_value is True:  # If it's True (boolean), all tools are enabled
            enabled_tools = all_tools.copy()
        elif current_value:  # Any other truthy value
            if isinstance(current_value, list | tuple | set):
                enabled_tools = [str(t).strip().lower() for t in current_value if t]
            else:
                # Try to convert to string and use as a single value
                try:
                    val = str(current_value).strip().lower()
                    if val:
                        enabled_tools = [val]
                except:
                    pass

        # Check if we're disabling a tool
        is_disabling = tool in enabled_tools

        # Toggle the tool
        if is_disabling:
            enabled_tools.remove(tool)
            # Import the reset function here to avoid circular imports
            from bot.helper.ext_utils.config_utils import reset_tool_configs

            # Reset tool-specific configurations when disabling a tool
            await reset_tool_configs(tool, database)
        else:
            enabled_tools.append(tool)

        # Update the config
        if enabled_tools:
            # Sort the tools to maintain consistent order
            enabled_tools.sort()
            new_value = ",".join(enabled_tools)
            Config.set(key, new_value)
        else:
            Config.set(key, False)

        # Update the database
        await database.update_config({key: Config.get(key)})

        # Force reload the current value after database update to ensure consistency
        current_value = Config.get(key)

        # Re-parse enabled tools after the update
        enabled_tools = []
        if isinstance(current_value, str):
            # Handle both comma-separated and single values
            if "," in current_value:
                enabled_tools = [
                    t.strip().lower() for t in current_value.split(",") if t.strip()
                ]
            elif current_value.strip():  # Single non-empty value
                enabled_tools = [current_value.strip().lower()]
        elif current_value is True:  # If it's True (boolean), all tools are enabled
            enabled_tools = all_tools.copy()
        elif current_value:  # Any other truthy value
            if isinstance(current_value, list | tuple | set):
                enabled_tools = [str(t).strip().lower() for t in current_value if t]
            else:
                # Try to convert to string and use as a single value
                try:
                    val = str(current_value).strip().lower()
                    if val:
                        enabled_tools = [val]
                except:
                    pass

        # Refresh the menu
        buttons = ButtonMaker()

        # Add toggle buttons for each tool
        for t in all_tools:
            status = "✅" if t in enabled_tools else "❌"
            buttons.data_button(
                f"{t.title()}: {status}",
                f"botset toggle_tool {key} {t}",
            )

        # Add buttons to enable/disable all tools
        buttons.data_button("Enable All", f"botset enable_all_tools {key}")
        buttons.data_button("Disable All", f"botset disable_all_tools {key}")

        # Add done button
        buttons.data_button("Done", "botset var")

        # Show the number of enabled tools in the message
        await edit_message(
            message,
            f"<b>Configure Media Tools</b>\n\nSelect which media tools to enable ({len(enabled_tools)}/{len(all_tools)} enabled):",
            buttons.build_menu(2),
        )

    elif data[1] == "enable_all_tools":
        await query.answer("Enabling all media tools")
        key = data[2]  # MEDIA_TOOLS_ENABLED

        # List of all available tools
        all_tools = [
            "watermark",
            "merge",
            "convert",
            "compression",
            "trim",
            "extract",
            "metadata",
            "ffmpeg",
            "sample",
        ]

        # Update the config - sort the tools to maintain consistent order
        all_tools.sort()
        new_value = ",".join(all_tools)
        Config.set(key, new_value)

        # Update the database
        await database.update_config({key: Config.get(key)})

        # Refresh the menu
        buttons = ButtonMaker()

        # Add toggle buttons for each tool
        for tool in all_tools:
            buttons.data_button(
                f"{tool.title()}: ✅",
                f"botset toggle_tool {key} {tool}",
            )

        # Add buttons to enable/disable all tools
        buttons.data_button("Enable All", f"botset enable_all_tools {key}")
        buttons.data_button("Disable All", f"botset disable_all_tools {key}")

        # Add done button
        buttons.data_button("Done", "botset var")

        await edit_message(
            message,
            f"<b>Configure Media Tools</b>\n\nSelect which media tools to enable ({len(all_tools)}/{len(all_tools)} enabled):",
            buttons.build_menu(2),
        )

    elif data[1] == "disable_all_tools":
        await query.answer("Disabling all media tools")
        key = data[2]  # MEDIA_TOOLS_ENABLED

        # List of all available tools
        all_tools = [
            "watermark",
            "merge",
            "convert",
            "compression",
            "trim",
            "extract",
            "metadata",
            "ffmpeg",
            "sample",
        ]

        # Reset configurations for all tools
        from bot.helper.ext_utils.config_utils import reset_tool_configs

        for tool in all_tools:
            await reset_tool_configs(tool, database)

        # Update the config
        Config.set(key, False)

        # Update the database
        await database.update_config({key: Config.get(key)})

        # Refresh the menu
        buttons = ButtonMaker()

        # Add toggle buttons for each tool
        for tool in all_tools:
            buttons.data_button(
                f"{tool.title()}: ❌",
                f"botset toggle_tool {key} {tool}",
            )

        # Add buttons to enable/disable all tools
        buttons.data_button("Enable All", f"botset enable_all_tools {key}")
        buttons.data_button("Disable All", f"botset disable_all_tools {key}")

        # Add done button
        buttons.data_button("Done", "botset var")

        await edit_message(
            message,
            f"<b>Configure Media Tools</b>\n\nSelect which media tools to enable (0/{len(all_tools)} enabled):",
            buttons.build_menu(2),
        )

    elif data[1] == "setprovider":
        await query.answer(f"Setting default AI provider to {data[2].capitalize()}")
        # Update the default AI provider
        Config.DEFAULT_AI_PROVIDER = data[2]
        # Update the database
        await database.update_config({"DEFAULT_AI_PROVIDER": data[2]})
        # Update the UI
        await update_buttons(message, "ai")
    elif data[1] == "edit":
        await query.answer()
        globals()["state"] = "edit"
        await update_buttons(message, data[2])
    elif data[1] == "view":
        await query.answer()
        globals()["state"] = "view"
        await update_buttons(message, data[2])
    elif data[1] == "start":
        await query.answer()
        if start != int(data[3]):
            globals()["start"] = int(data[3])
            await update_buttons(message, data[2])
    elif data[1] == "start_merge":
        await query.answer()
        try:
            if len(data) > 2:
                # Update the global merge_page variable
                globals()["merge_page"] = int(data[2])
                LOGGER.debug(f"Updated merge_page to {globals()['merge_page']}")
                await update_buttons(
                    message, "mediatools_merge", page=globals()["merge_page"]
                )
            else:
                # If no page number is provided, stay on the current page
                await update_buttons(
                    message, "mediatools_merge", page=globals()["merge_page"]
                )
        except (ValueError, IndexError) as e:
            # In case of any error, stay on the current page
            LOGGER.error(f"Error in start_merge handler: {e}")
            await update_buttons(
                message, "mediatools_merge", page=globals()["merge_page"]
            )
    elif data[1] == "start_merge_config":
        await query.answer()
        try:
            if len(data) > 2:
                page = int(data[2])
                await update_buttons(message, "mediatools_merge_config", page=page)
            else:
                # If no page number is provided, stay on the current page
                await update_buttons(message, "mediatools_merge_config")
        except (ValueError, IndexError):
            # In case of any error, stay on the current page
            await update_buttons(message, "mediatools_merge_config")
    elif data[1] == "start_convert":
        await query.answer()
        try:
            if len(data) > 2:
                page = int(data[2])
                await update_buttons(message, "mediatools_convert", page=page)
            else:
                # If no page number is provided, stay on the current page
                await update_buttons(message, "mediatools_convert")
        except (ValueError, IndexError):
            # In case of any error, stay on the current page
            await update_buttons(message, "mediatools_convert")
    elif data[1] == "toggle":
        await query.answer()
        key = data[2]
        value = data[3].lower() == "true"

        # Special handling for ENABLE_EXTRA_MODULES
        if key == "ENABLE_EXTRA_MODULES":
            # If it's a string with comma-separated values, toggle to True
            # If it's True, toggle to False
            # If it's False, toggle to True
            if (
                isinstance(Config.ENABLE_EXTRA_MODULES, str)
                and "," in Config.ENABLE_EXTRA_MODULES
            ):
                value = True

        # Special handling for MEDIA_TOOLS_ENABLED
        elif key == "MEDIA_TOOLS_ENABLED":
            # If toggling to True, set to a comma-separated list of all media tools
            if value:
                # List of all available media tools
                all_tools = [
                    "watermark",
                    "merge",
                    "convert",
                    "compression",
                    "trim",
                    "extract",
                    "metadata",
                    "ffmpeg",
                    "sample",
                ]
                # Sort the tools to maintain consistent order
                all_tools.sort()
                value = ",".join(all_tools)
            # If toggling to False, set to False (boolean)
            else:
                value = False

        Config.set(key, value)

        # Determine which menu to return to based on the key
        return_menu = "mediatools"
        if key.startswith(("WATERMARK_", "AUDIO_WATERMARK_", "SUBTITLE_WATERMARK_")):
            return_menu = "mediatools_watermark"
        elif key.startswith("CONVERT_"):
            return_menu = "mediatools_convert"
        elif key.startswith("COMPRESSION_"):
            return_menu = "mediatools_compression"
        elif key.startswith("TRIM_"):
            return_menu = "mediatools_trim"
        elif key.startswith("EXTRACT_"):
            return_menu = "mediatools_extract"
        elif key in {"ENABLE_EXTRA_MODULES", "MEDIA_TOOLS_ENABLED"}:
            return_menu = "var"
        elif key.startswith(("MISTRAL_", "DEEPSEEK_", "CHATGPT_", "GEMINI_")):
            return_menu = "ai"
        await update_buttons(message, return_menu)
        await database.update_config({key: value})
    # Handle redirects for mediatools callbacks
    elif data[0] == "mediatools" and len(data) >= 3 and data[2] == "merge_config":
        # This is a callback from the pagination buttons in mediatools_merge_config
        # Redirect it to the media_tools module
        from bot.modules.media_tools import media_tools_callback

        await media_tools_callback(client, query)


@new_task
async def send_bot_settings(_, message):
    user_id = message.chat.id
    handler_dict[user_id] = False
    msg, button = await get_buttons(user_id=user_id)
    globals()["start"] = 0
    # Don't auto-delete the bot settings message
    await send_message(message, msg, button)


async def load_config():
    Config.load()
    drives_ids.clear()
    drives_names.clear()
    index_urls.clear()
    await update_variables()

    if not await aiopath.exists("accounts"):
        Config.USE_SERVICE_ACCOUNTS = False

    if len(task_dict) != 0 and (st := intervals["status"]):
        for key, intvl in list(st.items()):
            intvl.cancel()
            intervals["status"][key] = SetInterval(
                1,
                update_status_message,
                key,
            )

    if Config.TORRENT_TIMEOUT:
        await TorrentManager.change_aria2_option(
            "bt-stop-timeout",
            f"{Config.TORRENT_TIMEOUT}",
        )
        await database.update_aria2("bt-stop-timeout", f"{Config.TORRENT_TIMEOUT}")

    if not Config.INCOMPLETE_TASK_NOTIFIER:
        await database.trunc_table("tasks")

    await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
    if Config.BASE_URL:
        await create_subprocess_shell(
            f"gunicorn -k uvicorn.workers.UvicornWorker -w 1 web.wserver:app --bind 0.0.0.0:{Config.BASE_URL_PORT}",
        )

    if Config.DATABASE_URL:
        await database.connect()
        config_dict = Config.get_all()
        await database.update_config(config_dict)
    else:
        await database.disconnect()
    await gather(start_from_queued(), rclone_serve_booter())
    add_job()
