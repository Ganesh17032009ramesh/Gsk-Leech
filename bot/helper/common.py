import contextlib
import math
import os
from asyncio import gather, sleep
from os import path as ospath
from os import walk
from re import IGNORECASE, sub
from secrets import token_hex
from shlex import split
from time import time

from aiofiles.os import listdir, makedirs, remove
from aiofiles.os import path as aiopath
from aioshutil import move, rmtree
from pyrogram.enums import ChatAction

from bot import (
    DOWNLOAD_DIR,
    LOGGER,
    cpu_eater_lock,
    cpu_no,
    excluded_extensions,
    intervals,
    multi_tags,
    task_dict,
    task_dict_lock,
    user_data,
)
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config
from bot.helper.aeon_utils.command_gen import (
    analyze_media_for_merge,
    get_embed_thumb_cmd,
    get_merge_concat_demuxer_cmd,
    get_merge_filter_complex_cmd,
    get_merge_mixed_cmd,
    get_metadata_cmd,
    get_trim_cmd,
    get_watermark_cmd,
)

from .ext_utils.bot_utils import get_size_bytes, new_task, sync_to_async
from .ext_utils.bulk_links import extract_bulk_links
from .ext_utils.files_utils import (
    SevenZ,
    get_base_name,
    get_path_size,
    is_archive,
    is_archive_split,
    is_first_archive_split,
    split_file,
)
from .ext_utils.links_utils import (
    is_gdrive_id,
    is_gdrive_link,
    is_rclone_path,
    is_telegram_link,
)
from .ext_utils.media_utils import (
    FFMpeg,
    apply_document_metadata,
    create_thumb,
    get_document_type,
    is_mkv,
    merge_documents,
    merge_images,
    take_ss,
)
from .mirror_leech_utils.gdrive_utils.list import GoogleDriveList
from .mirror_leech_utils.rclone_utils.list import RcloneList
from .mirror_leech_utils.status_utils.ffmpeg_status import FFmpegStatus
from .mirror_leech_utils.status_utils.sevenz_status import SevenZStatus
from .telegram_helper.message_utils import (
    get_tg_link_message,
    send_message,
    send_status_message,
)


class TaskConfig:
    def __init__(self):
        self.mid = self.message.id
        self.user = self.message.from_user or self.message.sender_chat
        self.user_id = self.user.id
        self.user_dict = user_data.get(self.user_id, {})
        self.dir = f"{DOWNLOAD_DIR}{self.mid}"
        self.up_dir = ""
        self.link = ""
        self.up_dest = ""
        self.rc_flags = ""
        self.tag = ""
        self.name = ""
        self.subname = ""
        self.name_sub = ""
        self.metadata = ""
        self.metadata_title = ""
        self.metadata_author = ""
        self.metadata_comment = ""
        self.metadata_all = ""
        self.watermark = ""
        self.watermark_enabled = False
        self.watermark_position = ""
        self.watermark_size = 0
        self.watermark_color = ""
        self.watermark_font = ""
        self.watermark_priority = 0
        self.watermark_threading = False
        self.watermark_fast_mode = True
        self.watermark_maintain_quality = True
        self.watermark_opacity = 1.0
        self.audio_watermark_enabled = False
        self.audio_watermark_text = ""
        self.subtitle_watermark_enabled = False
        self.subtitle_watermark_text = ""
        self.merge_enabled = False
        self.merge_priority = 0
        self.trim = ""
        self.trim_enabled = False
        self.trim_priority = 0
        self.trim_start_time = None
        self.trim_end_time = None
        self.trim_video_enabled = False
        self.trim_video_codec = ""
        self.trim_video_preset = ""
        self.trim_audio_enabled = False
        self.trim_audio_codec = ""
        self.trim_audio_preset = ""
        self.trim_image_enabled = False
        self.trim_image_quality = 0
        self.trim_document_enabled = False
        self.trim_document_quality = 0
        self.trim_subtitle_enabled = False
        self.trim_subtitle_encoding = ""
        self.trim_subtitle_format = ""
        self.trim_archive_enabled = False
        self.trim_archive_format = ""
        self.trim_video_format = ""
        self.trim_audio_format = ""
        self.trim_image_format = ""
        self.trim_document_format = ""
        self.trim_delete_original = False
        self.merge_threading = False
        self.concat_demuxer_enabled = False
        self.filter_complex_enabled = False
        self.merge_output_format_video = ""
        self.merge_output_format_audio = ""
        self.merge_video = False
        self.merge_audio = False
        self.merge_subtitle = False
        self.merge_all = False
        self.merge_image = False
        self.merge_pdf = False
        # Extract settings
        self.extract_enabled = False
        self.extract_priority = 0
        self.extract_video_enabled = False
        self.extract_audio_enabled = False
        self.extract_subtitle_enabled = False
        self.extract_attachment_enabled = False
        self.extract_video_indices = None  # List of video track indices to extract
        self.extract_audio_indices = None  # List of audio track indices to extract
        self.extract_subtitle_indices = (
            None  # List of subtitle track indices to extract
        )
        self.extract_attachment_indices = (
            None  # List of attachment indices to extract
        )
        # Keep single index variables for backward compatibility
        self.extract_video_index = None
        self.extract_audio_index = None
        self.extract_subtitle_index = None
        self.extract_attachment_index = None

        # Video extract settings
        self.extract_video_codec = "none"
        self.extract_video_format = "none"
        self.extract_video_quality = "none"
        self.extract_video_preset = "none"
        self.extract_video_bitrate = "none"
        self.extract_video_resolution = "none"
        self.extract_video_fps = "none"

        # Audio extract settings
        self.extract_audio_codec = "none"
        self.extract_audio_format = "none"
        self.extract_audio_bitrate = "none"
        self.extract_audio_channels = "none"
        self.extract_audio_sampling = "none"
        self.extract_audio_volume = "none"

        # Subtitle extract settings
        self.extract_subtitle_codec = "none"
        self.extract_subtitle_format = "none"
        self.extract_subtitle_language = "none"
        self.extract_subtitle_encoding = "none"
        self.extract_subtitle_font = "none"
        self.extract_subtitle_font_size = "none"

        # Attachment extract settings
        self.extract_attachment_format = "none"
        self.extract_attachment_filter = "none"

        # General extract settings
        self.extract_maintain_quality = True
        self.extract_delete_original = False
        self.thumbnail_layout = ""
        self.folder_name = ""
        self.split_size = 0
        self.max_split_size = 0
        self.multi = 0
        self.size = 0
        self.subsize = 0
        self.proceed_count = 0
        self.is_leech = False
        self.is_jd = False
        self.is_qbit = False
        self.is_nzb = False
        self.is_clone = False
        self.is_ytdlp = False
        self.user_transmission = False
        self.hybrid_leech = False
        self.extract = False
        self.compress = False
        self.select = False
        self.seed = False
        self.join = False
        self.private_link = False
        self.stop_duplicate = False
        self.sample_video = False
        self.convert_audio = False
        self.convert_video = False
        self.screen_shots = False
        self.is_cancelled = False
        self.force_run = False
        self.force_download = False
        self.force_upload = False
        self.is_torrent = False
        self.as_med = False
        self.as_doc = False
        self.is_file = False
        self.bot_trans = False
        self.user_trans = False
        self.progress = True
        self.ffmpeg_cmds = None
        self.chat_thread_id = None
        self.subproc = None
        self.thumb = None
        self.excluded_extensions = []
        self.files_to_proceed = []
        self.is_super_chat = self.message.chat.type.name in ["SUPERGROUP", "CHANNEL"]

    def get_token_path(self, dest):
        if dest.startswith("mtp:"):
            return f"tokens/{self.user_id}.pickle"
        if dest.startswith("sa:") or (
            Config.USE_SERVICE_ACCOUNTS and not dest.startswith("tp:")
        ):
            return "accounts"
        return "token.pickle"

    def get_config_path(self, dest):
        return (
            f"rclone/{self.user_id}.conf"
            if dest.startswith("mrcc:")
            else "rclone.conf"
        )

    async def is_token_exists(self, path, status):
        if is_rclone_path(path):
            config_path = self.get_config_path(path)
            if config_path != "rclone.conf" and status == "up":
                self.private_link = True
            if not await aiopath.exists(config_path):
                raise ValueError(f"Rclone Config: {config_path} not Exists!")
        elif (status == "dl" and is_gdrive_link(path)) or (
            status == "up" and is_gdrive_id(path)
        ):
            token_path = self.get_token_path(path)
            if token_path.startswith("tokens/") and status == "up":
                self.private_link = True
            if not await aiopath.exists(token_path):
                raise ValueError(f"NO TOKEN! {token_path} not Exists!")

    async def before_start(self):
        self.name_sub = (
            self.name_sub
            or self.user_dict.get("NAME_SUBSTITUTE", False)
            or (
                Config.NAME_SUBSTITUTE
                if "NAME_SUBSTITUTE" not in self.user_dict
                else ""
            )
        )
        # Get metadata settings with priority
        # Command line arguments take highest priority
        self.metadata = (
            self.metadata
            or self.user_dict.get("METADATA_KEY", False)
            or (Config.METADATA_KEY if "METADATA_KEY" not in self.user_dict else "")
        )

        # Get enhanced metadata settings with priority: command line > user settings > owner settings
        # Command line arguments take highest priority

        # Global metadata settings
        self.metadata_all = (
            self.metadata_all
            or self.user_dict.get("METADATA_ALL", False)
            or (Config.METADATA_ALL if "METADATA_ALL" not in self.user_dict else "")
        )

        self.metadata_title = (
            self.metadata_title
            or self.user_dict.get("METADATA_TITLE", False)
            or (
                Config.METADATA_TITLE
                if "METADATA_TITLE" not in self.user_dict
                else ""
            )
        )

        self.metadata_author = (
            self.metadata_author
            or self.user_dict.get("METADATA_AUTHOR", False)
            or (
                Config.METADATA_AUTHOR
                if "METADATA_AUTHOR" not in self.user_dict
                else ""
            )
        )

        self.metadata_comment = (
            self.metadata_comment
            or self.user_dict.get("METADATA_COMMENT", False)
            or (
                Config.METADATA_COMMENT
                if "METADATA_COMMENT" not in self.user_dict
                else ""
            )
        )

        # Video track metadata settings
        self.metadata_video_title = self.user_dict.get(
            "METADATA_VIDEO_TITLE", False
        ) or (
            Config.METADATA_VIDEO_TITLE
            if "METADATA_VIDEO_TITLE" not in self.user_dict
            else ""
        )

        self.metadata_video_author = self.user_dict.get(
            "METADATA_VIDEO_AUTHOR", False
        ) or (
            Config.METADATA_VIDEO_AUTHOR
            if "METADATA_VIDEO_AUTHOR" not in self.user_dict
            else ""
        )

        self.metadata_video_comment = self.user_dict.get(
            "METADATA_VIDEO_COMMENT", False
        ) or (
            Config.METADATA_VIDEO_COMMENT
            if "METADATA_VIDEO_COMMENT" not in self.user_dict
            else ""
        )

        # Audio track metadata settings
        self.metadata_audio_title = self.user_dict.get(
            "METADATA_AUDIO_TITLE", False
        ) or (
            Config.METADATA_AUDIO_TITLE
            if "METADATA_AUDIO_TITLE" not in self.user_dict
            else ""
        )

        self.metadata_audio_author = self.user_dict.get(
            "METADATA_AUDIO_AUTHOR", False
        ) or (
            Config.METADATA_AUDIO_AUTHOR
            if "METADATA_AUDIO_AUTHOR" not in self.user_dict
            else ""
        )

        self.metadata_audio_comment = self.user_dict.get(
            "METADATA_AUDIO_COMMENT", False
        ) or (
            Config.METADATA_AUDIO_COMMENT
            if "METADATA_AUDIO_COMMENT" not in self.user_dict
            else ""
        )

        # Subtitle track metadata settings
        self.metadata_subtitle_title = self.user_dict.get(
            "METADATA_SUBTITLE_TITLE", False
        ) or (
            Config.METADATA_SUBTITLE_TITLE
            if "METADATA_SUBTITLE_TITLE" not in self.user_dict
            else ""
        )

        self.metadata_subtitle_author = self.user_dict.get(
            "METADATA_SUBTITLE_AUTHOR", False
        ) or (
            Config.METADATA_SUBTITLE_AUTHOR
            if "METADATA_SUBTITLE_AUTHOR" not in self.user_dict
            else ""
        )

        self.metadata_subtitle_comment = self.user_dict.get(
            "METADATA_SUBTITLE_COMMENT", False
        ) or (
            Config.METADATA_SUBTITLE_COMMENT
            if "METADATA_SUBTITLE_COMMENT" not in self.user_dict
            else ""
        )
        # Initialize media tools settings with the correct priority
        # First check if user has enabled watermark
        user_watermark_enabled = self.user_dict.get("WATERMARK_ENABLED", False)

        # Check if owner has enabled watermark
        owner_watermark_enabled = Config.WATERMARK_ENABLED

        # Set watermark_enabled based on the following priority:
        # Global (enabled) & User (disabled) -> Apply global
        # User (enabled) & Global (disabled) -> Apply user
        # Global (enabled) & User (enabled) -> Apply user
        # Global (disabled) & User (disabled) -> Don't apply

        if "WATERMARK_ENABLED" in self.user_dict:
            # User has explicitly set watermark enabled/disabled
            if user_watermark_enabled:
                # User has enabled watermark - apply user settings
                self.watermark_enabled = True
            else:
                # User has disabled watermark - check owner settings
                self.watermark_enabled = owner_watermark_enabled
        else:
            # User hasn't set watermark enabled/disabled - use owner settings
            self.watermark_enabled = owner_watermark_enabled

        # Initialize merge settings with the same priority logic
        user_merge_enabled = self.user_dict.get("MERGE_ENABLED", False)
        owner_merge_enabled = Config.MERGE_ENABLED

        if "MERGE_ENABLED" in self.user_dict:
            if user_merge_enabled:
                self.merge_enabled = True
            else:
                self.merge_enabled = owner_merge_enabled
        else:
            self.merge_enabled = owner_merge_enabled

        # Watermark enabled status has been logged in the priority logic above

        # Initialize watermark text based on the following priority:
        # 1. If watermark_text is provided via command line (-watermark flag), use that
        # 2. If user has explicitly enabled watermark and set text, use that
        # 3. If user has enabled watermark but not set text, or owner has enabled watermark, use owner's text
        # 4. Otherwise, use empty string

        # Check if watermark_text is provided via command line
        if hasattr(self, "watermark_text") and self.watermark_text:
            # Command line watermark text takes highest priority
            self.watermark = self.watermark_text
            # Force enable watermark when text is provided via command
            self.watermark_enabled = True
        elif (
            user_watermark_enabled
            and "WATERMARK_KEY" in self.user_dict
            and self.user_dict["WATERMARK_KEY"]
        ):
            # User has enabled watermark and set text - use user's text
            self.watermark = self.user_dict["WATERMARK_KEY"]
        elif self.watermark_enabled and Config.WATERMARK_KEY:
            # Either user has enabled watermark but not set text, or owner has enabled watermark
            # Use owner's text
            self.watermark = Config.WATERMARK_KEY
        else:
            # Default case: no watermark text
            self.watermark = ""

        # Initialize other watermark settings with the same priority logic
        # Position
        if (
            user_watermark_enabled
            and "WATERMARK_POSITION" in self.user_dict
            and self.user_dict["WATERMARK_POSITION"]
        ):
            # User has enabled watermark and set position - use user's position
            self.watermark_position = self.user_dict["WATERMARK_POSITION"]
        elif self.watermark_enabled and Config.WATERMARK_POSITION:
            # Either user has enabled watermark but not set position, or owner has enabled watermark
            # Use owner's position if available
            self.watermark_position = Config.WATERMARK_POSITION
        else:
            # Default position
            self.watermark_position = "top_left"

        # Size
        if (
            user_watermark_enabled
            and "WATERMARK_SIZE" in self.user_dict
            and self.user_dict["WATERMARK_SIZE"]
        ):
            # User has enabled watermark and set size - use user's size
            self.watermark_size = self.user_dict["WATERMARK_SIZE"]
        elif self.watermark_enabled and Config.WATERMARK_SIZE:
            # Either user has enabled watermark but not set size, or owner has enabled watermark
            # Use owner's size if available
            self.watermark_size = Config.WATERMARK_SIZE
        else:
            # Default size
            self.watermark_size = 20

        # Color
        if (
            user_watermark_enabled
            and "WATERMARK_COLOR" in self.user_dict
            and self.user_dict["WATERMARK_COLOR"]
            and self.user_dict["WATERMARK_COLOR"] != "None"
        ):
            # User has enabled watermark and set color - use user's color
            self.watermark_color = self.user_dict["WATERMARK_COLOR"]
        elif (
            self.watermark_enabled
            and Config.WATERMARK_COLOR
            and Config.WATERMARK_COLOR != "None"
        ):
            # Either user has enabled watermark but not set color, or owner has enabled watermark
            # Use owner's color if available
            self.watermark_color = Config.WATERMARK_COLOR
        else:
            # Default color
            self.watermark_color = "white"

        # Font
        if (
            user_watermark_enabled
            and "WATERMARK_FONT" in self.user_dict
            and self.user_dict["WATERMARK_FONT"]
        ):
            # User has enabled watermark and set font - use user's font
            self.watermark_font = self.user_dict["WATERMARK_FONT"]
        elif self.watermark_enabled and Config.WATERMARK_FONT:
            # Either user has enabled watermark but not set font, or owner has enabled watermark
            # Use owner's font if available
            self.watermark_font = Config.WATERMARK_FONT
        else:
            # Default font
            self.watermark_font = "default.otf"

        # Watermark Priority
        if (
            user_watermark_enabled
            and "WATERMARK_PRIORITY" in self.user_dict
            and self.user_dict["WATERMARK_PRIORITY"]
        ):
            self.watermark_priority = self.user_dict["WATERMARK_PRIORITY"]
        elif self.watermark_enabled and Config.WATERMARK_PRIORITY:
            self.watermark_priority = Config.WATERMARK_PRIORITY
        else:
            self.watermark_priority = 2

        # Watermark Threading
        if user_watermark_enabled and "WATERMARK_THREADING" in self.user_dict:
            self.watermark_threading = self.user_dict["WATERMARK_THREADING"]
        elif self.watermark_enabled and Config.WATERMARK_THREADING:
            self.watermark_threading = Config.WATERMARK_THREADING
        else:
            self.watermark_threading = True

        # Watermark Fast Mode
        if user_watermark_enabled and "WATERMARK_FAST_MODE" in self.user_dict:
            self.watermark_fast_mode = self.user_dict["WATERMARK_FAST_MODE"]
        elif self.watermark_enabled and hasattr(Config, "WATERMARK_FAST_MODE"):
            self.watermark_fast_mode = Config.WATERMARK_FAST_MODE
        else:
            self.watermark_fast_mode = True

        # Watermark Maintain Quality
        if user_watermark_enabled and "WATERMARK_MAINTAIN_QUALITY" in self.user_dict:
            self.watermark_maintain_quality = self.user_dict[
                "WATERMARK_MAINTAIN_QUALITY"
            ]
        elif self.watermark_enabled and hasattr(
            Config, "WATERMARK_MAINTAIN_QUALITY"
        ):
            self.watermark_maintain_quality = Config.WATERMARK_MAINTAIN_QUALITY
        else:
            self.watermark_maintain_quality = True

        # Watermark Opacity
        if user_watermark_enabled and "WATERMARK_OPACITY" in self.user_dict:
            self.watermark_opacity = self.user_dict["WATERMARK_OPACITY"]
        elif self.watermark_enabled and hasattr(Config, "WATERMARK_OPACITY"):
            self.watermark_opacity = Config.WATERMARK_OPACITY
        else:
            self.watermark_opacity = 1.0

        # Audio Watermark Enabled
        user_audio_watermark_enabled = self.user_dict.get(
            "AUDIO_WATERMARK_ENABLED", False
        )
        owner_audio_watermark_enabled = (
            Config.AUDIO_WATERMARK_ENABLED
            if hasattr(Config, "AUDIO_WATERMARK_ENABLED")
            else False
        )

        if "AUDIO_WATERMARK_ENABLED" in self.user_dict:
            # User has explicitly set audio watermark enabled/disabled
            if user_audio_watermark_enabled:
                # User has enabled audio watermark - apply user settings
                self.audio_watermark_enabled = True
            else:
                # User has disabled audio watermark - check owner settings
                self.audio_watermark_enabled = owner_audio_watermark_enabled
        else:
            # User hasn't set audio watermark enabled/disabled - use owner settings
            self.audio_watermark_enabled = owner_audio_watermark_enabled

        # Audio Watermark Text
        if (
            user_audio_watermark_enabled
            and "AUDIO_WATERMARK_TEXT" in self.user_dict
            and self.user_dict["AUDIO_WATERMARK_TEXT"]
        ):
            # User has enabled audio watermark and set text - use user's text
            self.audio_watermark_text = self.user_dict["AUDIO_WATERMARK_TEXT"]
        elif (
            self.audio_watermark_enabled
            and hasattr(Config, "AUDIO_WATERMARK_TEXT")
            and Config.AUDIO_WATERMARK_TEXT
        ):
            # Either user has enabled audio watermark but not set text, or owner has enabled audio watermark
            # Use owner's text
            self.audio_watermark_text = Config.AUDIO_WATERMARK_TEXT
        else:
            # Default case: no audio watermark text, will use the general watermark text
            self.audio_watermark_text = ""

        # Subtitle Watermark Enabled
        user_subtitle_watermark_enabled = self.user_dict.get(
            "SUBTITLE_WATERMARK_ENABLED", False
        )
        owner_subtitle_watermark_enabled = (
            Config.SUBTITLE_WATERMARK_ENABLED
            if hasattr(Config, "SUBTITLE_WATERMARK_ENABLED")
            else False
        )

        if "SUBTITLE_WATERMARK_ENABLED" in self.user_dict:
            # User has explicitly set subtitle watermark enabled/disabled
            if user_subtitle_watermark_enabled:
                # User has enabled subtitle watermark - apply user settings
                self.subtitle_watermark_enabled = True
            else:
                # User has disabled subtitle watermark - check owner settings
                self.subtitle_watermark_enabled = owner_subtitle_watermark_enabled
        else:
            # User hasn't set subtitle watermark enabled/disabled - use owner settings
            self.subtitle_watermark_enabled = owner_subtitle_watermark_enabled

        # Subtitle Watermark Text
        if (
            user_subtitle_watermark_enabled
            and "SUBTITLE_WATERMARK_TEXT" in self.user_dict
            and self.user_dict["SUBTITLE_WATERMARK_TEXT"]
        ):
            # User has enabled subtitle watermark and set text - use user's text
            self.subtitle_watermark_text = self.user_dict["SUBTITLE_WATERMARK_TEXT"]
        elif (
            self.subtitle_watermark_enabled
            and hasattr(Config, "SUBTITLE_WATERMARK_TEXT")
            and Config.SUBTITLE_WATERMARK_TEXT
        ):
            # Either user has enabled subtitle watermark but not set text, or owner has enabled subtitle watermark
            # Use owner's text
            self.subtitle_watermark_text = Config.SUBTITLE_WATERMARK_TEXT
        else:
            # Default case: no subtitle watermark text, will use the general watermark text
            self.subtitle_watermark_text = ""

        # Initialize merge settings with the same priority logic
        # Concat Demuxer
        if user_merge_enabled and "CONCAT_DEMUXER_ENABLED" in self.user_dict:
            self.concat_demuxer_enabled = self.user_dict["CONCAT_DEMUXER_ENABLED"]
        elif self.merge_enabled and Config.CONCAT_DEMUXER_ENABLED:
            self.concat_demuxer_enabled = Config.CONCAT_DEMUXER_ENABLED
        else:
            self.concat_demuxer_enabled = True

        # Filter Complex
        if user_merge_enabled and "FILTER_COMPLEX_ENABLED" in self.user_dict:
            self.filter_complex_enabled = self.user_dict["FILTER_COMPLEX_ENABLED"]
        elif self.merge_enabled and Config.FILTER_COMPLEX_ENABLED:
            self.filter_complex_enabled = Config.FILTER_COMPLEX_ENABLED
        else:
            self.filter_complex_enabled = False

        # Merge Output Format Video
        if (
            user_merge_enabled
            and "MERGE_OUTPUT_FORMAT_VIDEO" in self.user_dict
            and self.user_dict["MERGE_OUTPUT_FORMAT_VIDEO"]
        ):
            self.merge_output_format_video = self.user_dict[
                "MERGE_OUTPUT_FORMAT_VIDEO"
            ]
        elif self.merge_enabled and Config.MERGE_OUTPUT_FORMAT_VIDEO:
            self.merge_output_format_video = Config.MERGE_OUTPUT_FORMAT_VIDEO
        else:
            self.merge_output_format_video = "mkv"

        # Merge Output Format Audio
        if (
            user_merge_enabled
            and "MERGE_OUTPUT_FORMAT_AUDIO" in self.user_dict
            and self.user_dict["MERGE_OUTPUT_FORMAT_AUDIO"]
        ):
            self.merge_output_format_audio = self.user_dict[
                "MERGE_OUTPUT_FORMAT_AUDIO"
            ]
        elif self.merge_enabled and Config.MERGE_OUTPUT_FORMAT_AUDIO:
            self.merge_output_format_audio = Config.MERGE_OUTPUT_FORMAT_AUDIO
        else:
            self.merge_output_format_audio = "mp3"

        # Merge Priority
        if (
            user_merge_enabled
            and "MERGE_PRIORITY" in self.user_dict
            and self.user_dict["MERGE_PRIORITY"]
        ):
            self.merge_priority = self.user_dict["MERGE_PRIORITY"]
        elif self.merge_enabled and Config.MERGE_PRIORITY:
            self.merge_priority = Config.MERGE_PRIORITY
        else:
            self.merge_priority = 1

        # Merge Threading
        if user_merge_enabled and "MERGE_THREADING" in self.user_dict:
            self.merge_threading = self.user_dict["MERGE_THREADING"]
        elif self.merge_enabled and Config.MERGE_THREADING:
            self.merge_threading = Config.MERGE_THREADING
        else:
            self.merge_threading = True

        # Initialize convert settings with the same priority logic
        self.user_convert_enabled = self.user_dict.get("CONVERT_ENABLED", False)
        self.owner_convert_enabled = (
            hasattr(Config, "CONVERT_ENABLED") and Config.CONVERT_ENABLED
        )

        # Initialize trim settings with the same priority logic
        user_trim_enabled = self.user_dict.get("TRIM_ENABLED", False)
        owner_trim_enabled = hasattr(Config, "TRIM_ENABLED") and Config.TRIM_ENABLED

        if "TRIM_ENABLED" in self.user_dict:
            if user_trim_enabled:
                self.trim_enabled = True
            else:
                self.trim_enabled = owner_trim_enabled
        else:
            self.trim_enabled = owner_trim_enabled

        # Check if trim is provided via command line
        if hasattr(self, "trim") and self.trim:
            # Command line trim text takes highest priority
            # Force enable trim when text is provided via command
            self.trim_enabled = True

        # Initialize start time and end time settings
        # Get start time with priority: command line > user settings > owner settings
        if hasattr(self, "trim_start_time") and self.trim_start_time:
            # Command line start time takes highest priority
            self.trim_start_time = self.trim_start_time
        elif (
            user_trim_enabled
            and "TRIM_START_TIME" in self.user_dict
            and self.user_dict["TRIM_START_TIME"]
        ):
            # User has enabled trim and set start time - use user's start time
            self.trim_start_time = self.user_dict["TRIM_START_TIME"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_START_TIME")
            and Config.TRIM_START_TIME
        ):
            # Either user has enabled trim but not set start time, or owner has enabled trim
            # Use owner's start time
            self.trim_start_time = Config.TRIM_START_TIME
        else:
            # Default start time (beginning of file)
            self.trim_start_time = "00:00:00"

        # Get end time with priority: command line > user settings > owner settings
        if hasattr(self, "trim_end_time") and self.trim_end_time:
            # Command line end time takes highest priority
            self.trim_end_time = self.trim_end_time
        elif (
            user_trim_enabled
            and "TRIM_END_TIME" in self.user_dict
            and self.user_dict["TRIM_END_TIME"]
        ):
            # User has enabled trim and set end time - use user's end time
            self.trim_end_time = self.user_dict["TRIM_END_TIME"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_END_TIME")
            and Config.TRIM_END_TIME
        ):
            # Either user has enabled trim but not set end time, or owner has enabled trim
            # Use owner's end time
            self.trim_end_time = Config.TRIM_END_TIME
        else:
            # Default end time (end of file)
            self.trim_end_time = ""

        # Initialize trim priority
        if (
            user_trim_enabled
            and "TRIM_PRIORITY" in self.user_dict
            and self.user_dict["TRIM_PRIORITY"]
        ):
            self.trim_priority = self.user_dict["TRIM_PRIORITY"]
        elif self.trim_enabled and Config.TRIM_PRIORITY:
            self.trim_priority = Config.TRIM_PRIORITY
        else:
            self.trim_priority = 5

        # Initialize video trim settings
        if user_trim_enabled and "TRIM_VIDEO_ENABLED" in self.user_dict:
            self.trim_video_enabled = self.user_dict["TRIM_VIDEO_ENABLED"]
        elif self.trim_enabled and hasattr(Config, "TRIM_VIDEO_ENABLED"):
            self.trim_video_enabled = Config.TRIM_VIDEO_ENABLED
        else:
            self.trim_video_enabled = False

        if (
            user_trim_enabled
            and "TRIM_VIDEO_CODEC" in self.user_dict
            and self.user_dict["TRIM_VIDEO_CODEC"]
        ):
            self.trim_video_codec = self.user_dict["TRIM_VIDEO_CODEC"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_VIDEO_CODEC")
            and Config.TRIM_VIDEO_CODEC
        ):
            self.trim_video_codec = Config.TRIM_VIDEO_CODEC
        else:
            self.trim_video_codec = "copy"

        if (
            user_trim_enabled
            and "TRIM_VIDEO_PRESET" in self.user_dict
            and self.user_dict["TRIM_VIDEO_PRESET"]
        ):
            self.trim_video_preset = self.user_dict["TRIM_VIDEO_PRESET"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_VIDEO_PRESET")
            and Config.TRIM_VIDEO_PRESET
        ):
            self.trim_video_preset = Config.TRIM_VIDEO_PRESET
        else:
            self.trim_video_preset = "medium"

        # Initialize audio trim settings
        if user_trim_enabled and "TRIM_AUDIO_ENABLED" in self.user_dict:
            self.trim_audio_enabled = self.user_dict["TRIM_AUDIO_ENABLED"]
        elif self.trim_enabled and hasattr(Config, "TRIM_AUDIO_ENABLED"):
            self.trim_audio_enabled = Config.TRIM_AUDIO_ENABLED
        else:
            self.trim_audio_enabled = False

        if (
            user_trim_enabled
            and "TRIM_AUDIO_CODEC" in self.user_dict
            and self.user_dict["TRIM_AUDIO_CODEC"]
        ):
            self.trim_audio_codec = self.user_dict["TRIM_AUDIO_CODEC"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_AUDIO_CODEC")
            and Config.TRIM_AUDIO_CODEC
        ):
            self.trim_audio_codec = Config.TRIM_AUDIO_CODEC
        else:
            self.trim_audio_codec = "copy"

        if (
            user_trim_enabled
            and "TRIM_AUDIO_PRESET" in self.user_dict
            and self.user_dict["TRIM_AUDIO_PRESET"]
        ):
            self.trim_audio_preset = self.user_dict["TRIM_AUDIO_PRESET"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_AUDIO_PRESET")
            and Config.TRIM_AUDIO_PRESET
        ):
            self.trim_audio_preset = Config.TRIM_AUDIO_PRESET
        else:
            self.trim_audio_preset = "medium"

        # Initialize image trim settings
        if user_trim_enabled and "TRIM_IMAGE_ENABLED" in self.user_dict:
            self.trim_image_enabled = self.user_dict["TRIM_IMAGE_ENABLED"]
        elif self.trim_enabled and hasattr(Config, "TRIM_IMAGE_ENABLED"):
            self.trim_image_enabled = Config.TRIM_IMAGE_ENABLED
        else:
            self.trim_image_enabled = False

        if (
            user_trim_enabled
            and "TRIM_IMAGE_QUALITY" in self.user_dict
            and self.user_dict["TRIM_IMAGE_QUALITY"]
        ):
            self.trim_image_quality = self.user_dict["TRIM_IMAGE_QUALITY"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_IMAGE_QUALITY")
            and Config.TRIM_IMAGE_QUALITY
        ):
            self.trim_image_quality = Config.TRIM_IMAGE_QUALITY
        else:
            self.trim_image_quality = 90

        # Initialize document trim settings
        if user_trim_enabled and "TRIM_DOCUMENT_ENABLED" in self.user_dict:
            self.trim_document_enabled = self.user_dict["TRIM_DOCUMENT_ENABLED"]
        elif self.trim_enabled and hasattr(Config, "TRIM_DOCUMENT_ENABLED"):
            self.trim_document_enabled = Config.TRIM_DOCUMENT_ENABLED
        else:
            self.trim_document_enabled = False

        if (
            user_trim_enabled
            and "TRIM_DOCUMENT_QUALITY" in self.user_dict
            and self.user_dict["TRIM_DOCUMENT_QUALITY"]
        ):
            self.trim_document_quality = self.user_dict["TRIM_DOCUMENT_QUALITY"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_DOCUMENT_QUALITY")
            and Config.TRIM_DOCUMENT_QUALITY
        ):
            self.trim_document_quality = Config.TRIM_DOCUMENT_QUALITY
        else:
            self.trim_document_quality = 90

        # Initialize subtitle trim settings
        if user_trim_enabled and "TRIM_SUBTITLE_ENABLED" in self.user_dict:
            self.trim_subtitle_enabled = self.user_dict["TRIM_SUBTITLE_ENABLED"]
        elif self.trim_enabled and hasattr(Config, "TRIM_SUBTITLE_ENABLED"):
            self.trim_subtitle_enabled = Config.TRIM_SUBTITLE_ENABLED
        else:
            self.trim_subtitle_enabled = False

        if (
            user_trim_enabled
            and "TRIM_SUBTITLE_ENCODING" in self.user_dict
            and self.user_dict["TRIM_SUBTITLE_ENCODING"]
        ):
            self.trim_subtitle_encoding = self.user_dict["TRIM_SUBTITLE_ENCODING"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_SUBTITLE_ENCODING")
            and Config.TRIM_SUBTITLE_ENCODING
        ):
            self.trim_subtitle_encoding = Config.TRIM_SUBTITLE_ENCODING
        else:
            self.trim_subtitle_encoding = "utf-8"

        # Initialize archive trim settings
        if user_trim_enabled and "TRIM_ARCHIVE_ENABLED" in self.user_dict:
            self.trim_archive_enabled = self.user_dict["TRIM_ARCHIVE_ENABLED"]
        elif self.trim_enabled and hasattr(Config, "TRIM_ARCHIVE_ENABLED"):
            self.trim_archive_enabled = Config.TRIM_ARCHIVE_ENABLED
        else:
            self.trim_archive_enabled = False

        # Initialize trim delete original setting
        if user_trim_enabled and "TRIM_DELETE_ORIGINAL" in self.user_dict:
            self.trim_delete_original = self.user_dict["TRIM_DELETE_ORIGINAL"]
        elif self.trim_enabled and hasattr(Config, "TRIM_DELETE_ORIGINAL"):
            self.trim_delete_original = Config.TRIM_DELETE_ORIGINAL
        else:
            self.trim_delete_original = False

        # Check for -del flag in command line arguments
        if hasattr(self, "args") and self.args:
            # The -del flag takes precedence over settings for trim
            if self.args.get("-del") == "t" or self.args.get("-del") is True:
                self.trim_delete_original = True
                LOGGER.info("Setting trim_delete_original=True due to -del flag")
            elif self.args.get("-del") == "f" or self.args.get("-del") is False:
                self.trim_delete_original = False
                LOGGER.info("Setting trim_delete_original=False due to -del flag")

        # Initialize video format setting
        if (
            user_trim_enabled
            and "TRIM_VIDEO_FORMAT" in self.user_dict
            and self.user_dict["TRIM_VIDEO_FORMAT"]
            and self.user_dict["TRIM_VIDEO_FORMAT"].lower() != "none"
        ):
            self.trim_video_format = self.user_dict["TRIM_VIDEO_FORMAT"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_VIDEO_FORMAT")
            and Config.TRIM_VIDEO_FORMAT
            and Config.TRIM_VIDEO_FORMAT.lower() != "none"
        ):
            self.trim_video_format = Config.TRIM_VIDEO_FORMAT
        else:
            self.trim_video_format = "none"

        # Initialize audio format setting
        if (
            user_trim_enabled
            and "TRIM_AUDIO_FORMAT" in self.user_dict
            and self.user_dict["TRIM_AUDIO_FORMAT"]
            and self.user_dict["TRIM_AUDIO_FORMAT"].lower() != "none"
        ):
            self.trim_audio_format = self.user_dict["TRIM_AUDIO_FORMAT"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_AUDIO_FORMAT")
            and Config.TRIM_AUDIO_FORMAT
            and Config.TRIM_AUDIO_FORMAT.lower() != "none"
        ):
            self.trim_audio_format = Config.TRIM_AUDIO_FORMAT
        else:
            self.trim_audio_format = "none"

        # Initialize image format setting
        if (
            user_trim_enabled
            and "TRIM_IMAGE_FORMAT" in self.user_dict
            and self.user_dict["TRIM_IMAGE_FORMAT"]
            and self.user_dict["TRIM_IMAGE_FORMAT"].lower() != "none"
        ):
            self.trim_image_format = self.user_dict["TRIM_IMAGE_FORMAT"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_IMAGE_FORMAT")
            and Config.TRIM_IMAGE_FORMAT
            and Config.TRIM_IMAGE_FORMAT.lower() != "none"
        ):
            self.trim_image_format = Config.TRIM_IMAGE_FORMAT
        else:
            self.trim_image_format = "none"

        # Initialize document format setting
        if (
            user_trim_enabled
            and "TRIM_DOCUMENT_FORMAT" in self.user_dict
            and self.user_dict["TRIM_DOCUMENT_FORMAT"]
            and self.user_dict["TRIM_DOCUMENT_FORMAT"].lower() != "none"
        ):
            self.trim_document_format = self.user_dict["TRIM_DOCUMENT_FORMAT"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_DOCUMENT_FORMAT")
            and Config.TRIM_DOCUMENT_FORMAT
            and Config.TRIM_DOCUMENT_FORMAT.lower() != "none"
        ):
            self.trim_document_format = Config.TRIM_DOCUMENT_FORMAT
        else:
            self.trim_document_format = "none"

        # Initialize subtitle format setting
        if (
            user_trim_enabled
            and "TRIM_SUBTITLE_FORMAT" in self.user_dict
            and self.user_dict["TRIM_SUBTITLE_FORMAT"]
            and self.user_dict["TRIM_SUBTITLE_FORMAT"].lower() != "none"
        ):
            self.trim_subtitle_format = self.user_dict["TRIM_SUBTITLE_FORMAT"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_SUBTITLE_FORMAT")
            and Config.TRIM_SUBTITLE_FORMAT
            and Config.TRIM_SUBTITLE_FORMAT.lower() != "none"
        ):
            self.trim_subtitle_format = Config.TRIM_SUBTITLE_FORMAT
        else:
            self.trim_subtitle_format = "none"

        # Initialize archive format setting
        if (
            user_trim_enabled
            and "TRIM_ARCHIVE_FORMAT" in self.user_dict
            and self.user_dict["TRIM_ARCHIVE_FORMAT"]
            and self.user_dict["TRIM_ARCHIVE_FORMAT"].lower() != "none"
        ):
            self.trim_archive_format = self.user_dict["TRIM_ARCHIVE_FORMAT"]
        elif (
            self.trim_enabled
            and hasattr(Config, "TRIM_ARCHIVE_FORMAT")
            and Config.TRIM_ARCHIVE_FORMAT
            and Config.TRIM_ARCHIVE_FORMAT.lower() != "none"
        ):
            self.trim_archive_format = Config.TRIM_ARCHIVE_FORMAT
        else:
            self.trim_archive_format = "none"

        # Initialize extract settings
        await self.initialize_extract_settings()

    async def initialize_extract_settings(self):
        """Initialize extract settings with priority logic."""
        # Get user and owner settings
        user_extract_enabled = self.user_dict.get("EXTRACT_ENABLED", False)
        owner_extract_enabled = (
            hasattr(Config, "EXTRACT_ENABLED") and Config.EXTRACT_ENABLED
        )

        if "EXTRACT_ENABLED" in self.user_dict:
            if user_extract_enabled:
                self.extract_enabled = True
                LOGGER.debug("Extract enabled by user settings")
            else:
                self.extract_enabled = owner_extract_enabled
                if self.extract_enabled:
                    LOGGER.debug("Extract enabled by owner settings (user disabled)")
                else:
                    LOGGER.debug("Extract disabled (both user and owner disabled)")
        else:
            self.extract_enabled = owner_extract_enabled
            if self.extract_enabled:
                LOGGER.debug("Extract enabled by owner settings (user not set)")
            else:
                LOGGER.debug("Extract disabled (owner disabled, user not set)")

        # Initialize extract priority
        if (
            user_extract_enabled
            and "EXTRACT_PRIORITY" in self.user_dict
            and self.user_dict["EXTRACT_PRIORITY"]
        ):
            self.extract_priority = self.user_dict["EXTRACT_PRIORITY"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_PRIORITY")
            and Config.EXTRACT_PRIORITY
        ):
            self.extract_priority = Config.EXTRACT_PRIORITY
        else:
            self.extract_priority = 6

        # Initialize video extract settings
        if user_extract_enabled and "EXTRACT_VIDEO_ENABLED" in self.user_dict:
            self.extract_video_enabled = self.user_dict["EXTRACT_VIDEO_ENABLED"]
        elif self.extract_enabled and hasattr(Config, "EXTRACT_VIDEO_ENABLED"):
            self.extract_video_enabled = Config.EXTRACT_VIDEO_ENABLED
        else:
            self.extract_video_enabled = False

        # Initialize video index from user settings
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_INDEX" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_INDEX"] is not None
        ):
            self.extract_video_index = self.user_dict["EXTRACT_VIDEO_INDEX"]
            # Convert to list format for extract_video_indices
            if isinstance(self.extract_video_index, str):
                if self.extract_video_index.lower() == "all":
                    self.extract_video_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "User setting 'all' found for video indices, will extract all video tracks"
                    )
                elif "," in self.extract_video_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_video_indices = [
                            int(idx.strip())
                            for idx in self.extract_video_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"User setting for video indices: {self.extract_video_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid video index in user settings: {self.extract_video_index}"
                        )
                        self.extract_video_indices = []
                else:
                    # Single index
                    try:
                        self.extract_video_indices = [int(self.extract_video_index)]
                        LOGGER.info(
                            f"User setting for video index: {self.extract_video_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid video index in user settings: {self.extract_video_index}"
                        )
                        self.extract_video_indices = []
            elif isinstance(self.extract_video_index, int):
                self.extract_video_indices = [self.extract_video_index]
                LOGGER.info(
                    f"User setting for video index: {self.extract_video_indices}"
                )
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_INDEX")
            and Config.EXTRACT_VIDEO_INDEX is not None
        ):
            self.extract_video_index = Config.EXTRACT_VIDEO_INDEX
            # Convert to list format for extract_video_indices
            if isinstance(self.extract_video_index, str):
                if self.extract_video_index.lower() == "all":
                    self.extract_video_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "Owner setting 'all' found for video indices, will extract all video tracks"
                    )
                elif "," in self.extract_video_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_video_indices = [
                            int(idx.strip())
                            for idx in self.extract_video_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"Owner setting for video indices: {self.extract_video_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid video index in owner settings: {self.extract_video_index}"
                        )
                        self.extract_video_indices = []
                else:
                    # Single index
                    try:
                        self.extract_video_indices = [int(self.extract_video_index)]
                        LOGGER.info(
                            f"Owner setting for video index: {self.extract_video_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid video index in owner settings: {self.extract_video_index}"
                        )
                        self.extract_video_indices = []
            elif isinstance(self.extract_video_index, int):
                self.extract_video_indices = [self.extract_video_index]
                LOGGER.info(
                    f"Owner setting for video index: {self.extract_video_indices}"
                )

        # Video codec
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_CODEC" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_CODEC"]
            and self.user_dict["EXTRACT_VIDEO_CODEC"].lower() != "none"
        ):
            self.extract_video_codec = self.user_dict["EXTRACT_VIDEO_CODEC"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_CODEC")
            and Config.EXTRACT_VIDEO_CODEC
            and Config.EXTRACT_VIDEO_CODEC.lower() != "none"
        ):
            self.extract_video_codec = Config.EXTRACT_VIDEO_CODEC
        else:
            self.extract_video_codec = "none"

        # Video format
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_FORMAT" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_FORMAT"]
            and self.user_dict["EXTRACT_VIDEO_FORMAT"].lower() != "none"
        ):
            self.extract_video_format = self.user_dict["EXTRACT_VIDEO_FORMAT"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_FORMAT")
            and Config.EXTRACT_VIDEO_FORMAT
            and Config.EXTRACT_VIDEO_FORMAT.lower() != "none"
        ):
            self.extract_video_format = Config.EXTRACT_VIDEO_FORMAT
        else:
            self.extract_video_format = "none"

        # Video quality
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_QUALITY" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_QUALITY"]
            and self.user_dict["EXTRACT_VIDEO_QUALITY"].lower() != "none"
        ):
            self.extract_video_quality = self.user_dict["EXTRACT_VIDEO_QUALITY"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_QUALITY")
            and Config.EXTRACT_VIDEO_QUALITY
            and Config.EXTRACT_VIDEO_QUALITY.lower() != "none"
        ):
            self.extract_video_quality = Config.EXTRACT_VIDEO_QUALITY
        else:
            self.extract_video_quality = "none"

        # Video preset
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_PRESET" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_PRESET"]
            and self.user_dict["EXTRACT_VIDEO_PRESET"].lower() != "none"
        ):
            self.extract_video_preset = self.user_dict["EXTRACT_VIDEO_PRESET"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_PRESET")
            and Config.EXTRACT_VIDEO_PRESET
            and Config.EXTRACT_VIDEO_PRESET.lower() != "none"
        ):
            self.extract_video_preset = Config.EXTRACT_VIDEO_PRESET
        else:
            self.extract_video_preset = "none"

        # Video bitrate
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_BITRATE" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_BITRATE"]
            and self.user_dict["EXTRACT_VIDEO_BITRATE"].lower() != "none"
        ):
            self.extract_video_bitrate = self.user_dict["EXTRACT_VIDEO_BITRATE"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_BITRATE")
            and Config.EXTRACT_VIDEO_BITRATE
            and Config.EXTRACT_VIDEO_BITRATE.lower() != "none"
        ):
            self.extract_video_bitrate = Config.EXTRACT_VIDEO_BITRATE
        else:
            self.extract_video_bitrate = "none"

        # Video resolution
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_RESOLUTION" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_RESOLUTION"]
            and self.user_dict["EXTRACT_VIDEO_RESOLUTION"].lower() != "none"
        ):
            self.extract_video_resolution = self.user_dict[
                "EXTRACT_VIDEO_RESOLUTION"
            ]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_RESOLUTION")
            and Config.EXTRACT_VIDEO_RESOLUTION
            and Config.EXTRACT_VIDEO_RESOLUTION.lower() != "none"
        ):
            self.extract_video_resolution = Config.EXTRACT_VIDEO_RESOLUTION
        else:
            self.extract_video_resolution = "none"

        # Video FPS
        if (
            user_extract_enabled
            and "EXTRACT_VIDEO_FPS" in self.user_dict
            and self.user_dict["EXTRACT_VIDEO_FPS"]
            and self.user_dict["EXTRACT_VIDEO_FPS"].lower() != "none"
        ):
            self.extract_video_fps = self.user_dict["EXTRACT_VIDEO_FPS"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_VIDEO_FPS")
            and Config.EXTRACT_VIDEO_FPS
            and Config.EXTRACT_VIDEO_FPS.lower() != "none"
        ):
            self.extract_video_fps = Config.EXTRACT_VIDEO_FPS
        else:
            self.extract_video_fps = "none"

        # Initialize audio extract settings
        if user_extract_enabled and "EXTRACT_AUDIO_ENABLED" in self.user_dict:
            self.extract_audio_enabled = self.user_dict["EXTRACT_AUDIO_ENABLED"]
        elif self.extract_enabled and hasattr(Config, "EXTRACT_AUDIO_ENABLED"):
            self.extract_audio_enabled = Config.EXTRACT_AUDIO_ENABLED
        else:
            self.extract_audio_enabled = False

        # Initialize audio index from user settings
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_INDEX" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_INDEX"] is not None
        ):
            self.extract_audio_index = self.user_dict["EXTRACT_AUDIO_INDEX"]
            # Convert to list format for extract_audio_indices
            if isinstance(self.extract_audio_index, str):
                if self.extract_audio_index.lower() == "all":
                    self.extract_audio_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "User setting 'all' found for audio indices, will extract all audio tracks"
                    )
                elif "," in self.extract_audio_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_audio_indices = [
                            int(idx.strip())
                            for idx in self.extract_audio_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"User setting for audio indices: {self.extract_audio_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid audio index in user settings: {self.extract_audio_index}"
                        )
                        self.extract_audio_indices = []
                else:
                    # Single index
                    try:
                        self.extract_audio_indices = [int(self.extract_audio_index)]
                        LOGGER.info(
                            f"User setting for audio index: {self.extract_audio_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid audio index in user settings: {self.extract_audio_index}"
                        )
                        self.extract_audio_indices = []
            elif isinstance(self.extract_audio_index, int):
                self.extract_audio_indices = [self.extract_audio_index]
                LOGGER.info(
                    f"User setting for audio index: {self.extract_audio_indices}"
                )
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_INDEX")
            and Config.EXTRACT_AUDIO_INDEX is not None
        ):
            self.extract_audio_index = Config.EXTRACT_AUDIO_INDEX
            # Convert to list format for extract_audio_indices
            if isinstance(self.extract_audio_index, str):
                if self.extract_audio_index.lower() == "all":
                    self.extract_audio_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "Owner setting 'all' found for audio indices, will extract all audio tracks"
                    )
                elif "," in self.extract_audio_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_audio_indices = [
                            int(idx.strip())
                            for idx in self.extract_audio_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"Owner setting for audio indices: {self.extract_audio_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid audio index in owner settings: {self.extract_audio_index}"
                        )
                        self.extract_audio_indices = []
                else:
                    # Single index
                    try:
                        self.extract_audio_indices = [int(self.extract_audio_index)]
                        LOGGER.info(
                            f"Owner setting for audio index: {self.extract_audio_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid audio index in owner settings: {self.extract_audio_index}"
                        )
                        self.extract_audio_indices = []
            elif isinstance(self.extract_audio_index, int):
                self.extract_audio_indices = [self.extract_audio_index]
                LOGGER.info(
                    f"Owner setting for audio index: {self.extract_audio_indices}"
                )

        # Audio codec
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_CODEC" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_CODEC"]
            and self.user_dict["EXTRACT_AUDIO_CODEC"].lower() != "none"
        ):
            self.extract_audio_codec = self.user_dict["EXTRACT_AUDIO_CODEC"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_CODEC")
            and Config.EXTRACT_AUDIO_CODEC
            and Config.EXTRACT_AUDIO_CODEC.lower() != "none"
        ):
            self.extract_audio_codec = Config.EXTRACT_AUDIO_CODEC
        else:
            self.extract_audio_codec = "none"

        # Audio format
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_FORMAT" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_FORMAT"]
            and self.user_dict["EXTRACT_AUDIO_FORMAT"].lower() != "none"
        ):
            self.extract_audio_format = self.user_dict["EXTRACT_AUDIO_FORMAT"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_FORMAT")
            and Config.EXTRACT_AUDIO_FORMAT
            and Config.EXTRACT_AUDIO_FORMAT.lower() != "none"
        ):
            self.extract_audio_format = Config.EXTRACT_AUDIO_FORMAT
        else:
            self.extract_audio_format = "none"

        # Audio bitrate
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_BITRATE" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_BITRATE"]
            and self.user_dict["EXTRACT_AUDIO_BITRATE"].lower() != "none"
        ):
            self.extract_audio_bitrate = self.user_dict["EXTRACT_AUDIO_BITRATE"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_BITRATE")
            and Config.EXTRACT_AUDIO_BITRATE
            and Config.EXTRACT_AUDIO_BITRATE.lower() != "none"
        ):
            self.extract_audio_bitrate = Config.EXTRACT_AUDIO_BITRATE
        else:
            self.extract_audio_bitrate = "none"

        # Audio channels
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_CHANNELS" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_CHANNELS"]
            and self.user_dict["EXTRACT_AUDIO_CHANNELS"].lower() != "none"
        ):
            self.extract_audio_channels = self.user_dict["EXTRACT_AUDIO_CHANNELS"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_CHANNELS")
            and Config.EXTRACT_AUDIO_CHANNELS
            and Config.EXTRACT_AUDIO_CHANNELS.lower() != "none"
        ):
            self.extract_audio_channels = Config.EXTRACT_AUDIO_CHANNELS
        else:
            self.extract_audio_channels = "none"

        # Audio sampling
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_SAMPLING" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_SAMPLING"]
            and self.user_dict["EXTRACT_AUDIO_SAMPLING"].lower() != "none"
        ):
            self.extract_audio_sampling = self.user_dict["EXTRACT_AUDIO_SAMPLING"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_SAMPLING")
            and Config.EXTRACT_AUDIO_SAMPLING
            and Config.EXTRACT_AUDIO_SAMPLING.lower() != "none"
        ):
            self.extract_audio_sampling = Config.EXTRACT_AUDIO_SAMPLING
        else:
            self.extract_audio_sampling = "none"

        # Audio volume
        if (
            user_extract_enabled
            and "EXTRACT_AUDIO_VOLUME" in self.user_dict
            and self.user_dict["EXTRACT_AUDIO_VOLUME"]
            and self.user_dict["EXTRACT_AUDIO_VOLUME"].lower() != "none"
        ):
            self.extract_audio_volume = self.user_dict["EXTRACT_AUDIO_VOLUME"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_AUDIO_VOLUME")
            and Config.EXTRACT_AUDIO_VOLUME
            and Config.EXTRACT_AUDIO_VOLUME.lower() != "none"
        ):
            self.extract_audio_volume = Config.EXTRACT_AUDIO_VOLUME
        else:
            self.extract_audio_volume = "none"

        # Initialize subtitle extract settings
        if user_extract_enabled and "EXTRACT_SUBTITLE_ENABLED" in self.user_dict:
            self.extract_subtitle_enabled = self.user_dict[
                "EXTRACT_SUBTITLE_ENABLED"
            ]
        elif self.extract_enabled and hasattr(Config, "EXTRACT_SUBTITLE_ENABLED"):
            self.extract_subtitle_enabled = Config.EXTRACT_SUBTITLE_ENABLED
        else:
            self.extract_subtitle_enabled = False

        # Initialize subtitle index from user settings
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_INDEX" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_INDEX"] is not None
        ):
            self.extract_subtitle_index = self.user_dict["EXTRACT_SUBTITLE_INDEX"]
            # Convert to list format for extract_subtitle_indices
            if isinstance(self.extract_subtitle_index, str):
                if self.extract_subtitle_index.lower() == "all":
                    self.extract_subtitle_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "User setting 'all' found for subtitle indices, will extract all subtitle tracks"
                    )
                elif "," in self.extract_subtitle_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_subtitle_indices = [
                            int(idx.strip())
                            for idx in self.extract_subtitle_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"User setting for subtitle indices: {self.extract_subtitle_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid subtitle index in user settings: {self.extract_subtitle_index}"
                        )
                        self.extract_subtitle_indices = []
                else:
                    # Single index
                    try:
                        self.extract_subtitle_indices = [
                            int(self.extract_subtitle_index)
                        ]
                        LOGGER.info(
                            f"User setting for subtitle index: {self.extract_subtitle_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid subtitle index in user settings: {self.extract_subtitle_index}"
                        )
                        self.extract_subtitle_indices = []
            elif isinstance(self.extract_subtitle_index, int):
                self.extract_subtitle_indices = [self.extract_subtitle_index]
                LOGGER.info(
                    f"User setting for subtitle index: {self.extract_subtitle_indices}"
                )
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_INDEX")
            and Config.EXTRACT_SUBTITLE_INDEX is not None
        ):
            self.extract_subtitle_index = Config.EXTRACT_SUBTITLE_INDEX
            # Convert to list format for extract_subtitle_indices
            if isinstance(self.extract_subtitle_index, str):
                if self.extract_subtitle_index.lower() == "all":
                    self.extract_subtitle_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "Owner setting 'all' found for subtitle indices, will extract all subtitle tracks"
                    )
                elif "," in self.extract_subtitle_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_subtitle_indices = [
                            int(idx.strip())
                            for idx in self.extract_subtitle_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"Owner setting for subtitle indices: {self.extract_subtitle_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid subtitle index in owner settings: {self.extract_subtitle_index}"
                        )
                        self.extract_subtitle_indices = []
                else:
                    # Single index
                    try:
                        self.extract_subtitle_indices = [
                            int(self.extract_subtitle_index)
                        ]
                        LOGGER.info(
                            f"Owner setting for subtitle index: {self.extract_subtitle_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid subtitle index in owner settings: {self.extract_subtitle_index}"
                        )
                        self.extract_subtitle_indices = []
            elif isinstance(self.extract_subtitle_index, int):
                self.extract_subtitle_indices = [self.extract_subtitle_index]
                LOGGER.info(
                    f"Owner setting for subtitle index: {self.extract_subtitle_indices}"
                )

        # Subtitle codec
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_CODEC" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_CODEC"]
            and self.user_dict["EXTRACT_SUBTITLE_CODEC"].lower() != "none"
        ):
            self.extract_subtitle_codec = self.user_dict["EXTRACT_SUBTITLE_CODEC"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_CODEC")
            and Config.EXTRACT_SUBTITLE_CODEC
            and Config.EXTRACT_SUBTITLE_CODEC.lower() != "none"
        ):
            self.extract_subtitle_codec = Config.EXTRACT_SUBTITLE_CODEC
        else:
            self.extract_subtitle_codec = "none"

        # Subtitle format
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_FORMAT" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_FORMAT"]
            and self.user_dict["EXTRACT_SUBTITLE_FORMAT"].lower() != "none"
        ):
            self.extract_subtitle_format = self.user_dict["EXTRACT_SUBTITLE_FORMAT"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_FORMAT")
            and Config.EXTRACT_SUBTITLE_FORMAT
            and Config.EXTRACT_SUBTITLE_FORMAT.lower() != "none"
        ):
            self.extract_subtitle_format = Config.EXTRACT_SUBTITLE_FORMAT
        else:
            self.extract_subtitle_format = "none"

        # Subtitle language
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_LANGUAGE" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_LANGUAGE"]
            and self.user_dict["EXTRACT_SUBTITLE_LANGUAGE"].lower() != "none"
        ):
            self.extract_subtitle_language = self.user_dict[
                "EXTRACT_SUBTITLE_LANGUAGE"
            ]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_LANGUAGE")
            and Config.EXTRACT_SUBTITLE_LANGUAGE
            and Config.EXTRACT_SUBTITLE_LANGUAGE.lower() != "none"
        ):
            self.extract_subtitle_language = Config.EXTRACT_SUBTITLE_LANGUAGE
        else:
            self.extract_subtitle_language = "none"

        # Subtitle encoding
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_ENCODING" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_ENCODING"]
            and self.user_dict["EXTRACT_SUBTITLE_ENCODING"].lower() != "none"
        ):
            self.extract_subtitle_encoding = self.user_dict[
                "EXTRACT_SUBTITLE_ENCODING"
            ]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_ENCODING")
            and Config.EXTRACT_SUBTITLE_ENCODING
            and Config.EXTRACT_SUBTITLE_ENCODING.lower() != "none"
        ):
            self.extract_subtitle_encoding = Config.EXTRACT_SUBTITLE_ENCODING
        else:
            self.extract_subtitle_encoding = "none"

        # Subtitle font
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_FONT" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_FONT"]
            and self.user_dict["EXTRACT_SUBTITLE_FONT"].lower() != "none"
        ):
            self.extract_subtitle_font = self.user_dict["EXTRACT_SUBTITLE_FONT"]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_FONT")
            and Config.EXTRACT_SUBTITLE_FONT
            and Config.EXTRACT_SUBTITLE_FONT.lower() != "none"
        ):
            self.extract_subtitle_font = Config.EXTRACT_SUBTITLE_FONT
        else:
            self.extract_subtitle_font = "none"

        # Subtitle font size
        if (
            user_extract_enabled
            and "EXTRACT_SUBTITLE_FONT_SIZE" in self.user_dict
            and self.user_dict["EXTRACT_SUBTITLE_FONT_SIZE"]
            and self.user_dict["EXTRACT_SUBTITLE_FONT_SIZE"].lower() != "none"
        ):
            self.extract_subtitle_font_size = self.user_dict[
                "EXTRACT_SUBTITLE_FONT_SIZE"
            ]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_SUBTITLE_FONT_SIZE")
            and Config.EXTRACT_SUBTITLE_FONT_SIZE
            and Config.EXTRACT_SUBTITLE_FONT_SIZE.lower() != "none"
        ):
            self.extract_subtitle_font_size = Config.EXTRACT_SUBTITLE_FONT_SIZE
        else:
            self.extract_subtitle_font_size = "none"

        # Initialize attachment extract settings
        if user_extract_enabled and "EXTRACT_ATTACHMENT_ENABLED" in self.user_dict:
            self.extract_attachment_enabled = self.user_dict[
                "EXTRACT_ATTACHMENT_ENABLED"
            ]
        elif self.extract_enabled and hasattr(Config, "EXTRACT_ATTACHMENT_ENABLED"):
            self.extract_attachment_enabled = Config.EXTRACT_ATTACHMENT_ENABLED
        else:
            self.extract_attachment_enabled = False

        # Initialize attachment index from user settings
        if (
            user_extract_enabled
            and "EXTRACT_ATTACHMENT_INDEX" in self.user_dict
            and self.user_dict["EXTRACT_ATTACHMENT_INDEX"] is not None
        ):
            self.extract_attachment_index = self.user_dict[
                "EXTRACT_ATTACHMENT_INDEX"
            ]
            # Convert to list format for extract_attachment_indices
            if isinstance(self.extract_attachment_index, str):
                if self.extract_attachment_index.lower() == "all":
                    self.extract_attachment_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "User setting 'all' found for attachment indices, will extract all attachment files"
                    )
                elif "," in self.extract_attachment_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_attachment_indices = [
                            int(idx.strip())
                            for idx in self.extract_attachment_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"User setting for attachment indices: {self.extract_attachment_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid attachment index in user settings: {self.extract_attachment_index}"
                        )
                        self.extract_attachment_indices = []
                else:
                    # Single index
                    try:
                        self.extract_attachment_indices = [
                            int(self.extract_attachment_index)
                        ]
                        LOGGER.info(
                            f"User setting for attachment index: {self.extract_attachment_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid attachment index in user settings: {self.extract_attachment_index}"
                        )
                        self.extract_attachment_indices = []
            elif isinstance(self.extract_attachment_index, int):
                self.extract_attachment_indices = [self.extract_attachment_index]
                LOGGER.info(
                    f"User setting for attachment index: {self.extract_attachment_indices}"
                )
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_ATTACHMENT_INDEX")
            and Config.EXTRACT_ATTACHMENT_INDEX is not None
        ):
            self.extract_attachment_index = Config.EXTRACT_ATTACHMENT_INDEX
            # Convert to list format for extract_attachment_indices
            if isinstance(self.extract_attachment_index, str):
                if self.extract_attachment_index.lower() == "all":
                    self.extract_attachment_indices = []  # Empty list means extract all
                    LOGGER.info(
                        "Owner setting 'all' found for attachment indices, will extract all attachment files"
                    )
                elif "," in self.extract_attachment_index:
                    # Handle comma-separated indices
                    try:
                        self.extract_attachment_indices = [
                            int(idx.strip())
                            for idx in self.extract_attachment_index.split(",")
                            if idx.strip().isdigit()
                        ]
                        LOGGER.info(
                            f"Owner setting for attachment indices: {self.extract_attachment_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid attachment index in owner settings: {self.extract_attachment_index}"
                        )
                        self.extract_attachment_indices = []
                else:
                    # Single index
                    try:
                        self.extract_attachment_indices = [
                            int(self.extract_attachment_index)
                        ]
                        LOGGER.info(
                            f"Owner setting for attachment index: {self.extract_attachment_indices}"
                        )
                    except ValueError:
                        LOGGER.warning(
                            f"Invalid attachment index in owner settings: {self.extract_attachment_index}"
                        )
                        self.extract_attachment_indices = []
            elif isinstance(self.extract_attachment_index, int):
                self.extract_attachment_indices = [self.extract_attachment_index]
                LOGGER.info(
                    f"Owner setting for attachment index: {self.extract_attachment_indices}"
                )

        # Attachment format
        if (
            user_extract_enabled
            and "EXTRACT_ATTACHMENT_FORMAT" in self.user_dict
            and self.user_dict["EXTRACT_ATTACHMENT_FORMAT"]
            and self.user_dict["EXTRACT_ATTACHMENT_FORMAT"].lower() != "none"
        ):
            self.extract_attachment_format = self.user_dict[
                "EXTRACT_ATTACHMENT_FORMAT"
            ]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_ATTACHMENT_FORMAT")
            and Config.EXTRACT_ATTACHMENT_FORMAT
            and Config.EXTRACT_ATTACHMENT_FORMAT.lower() != "none"
        ):
            self.extract_attachment_format = Config.EXTRACT_ATTACHMENT_FORMAT
        else:
            self.extract_attachment_format = "none"

        # Attachment filter
        if (
            user_extract_enabled
            and "EXTRACT_ATTACHMENT_FILTER" in self.user_dict
            and self.user_dict["EXTRACT_ATTACHMENT_FILTER"]
            and self.user_dict["EXTRACT_ATTACHMENT_FILTER"].lower() != "none"
        ):
            self.extract_attachment_filter = self.user_dict[
                "EXTRACT_ATTACHMENT_FILTER"
            ]
        elif (
            self.extract_enabled
            and hasattr(Config, "EXTRACT_ATTACHMENT_FILTER")
            and Config.EXTRACT_ATTACHMENT_FILTER
            and Config.EXTRACT_ATTACHMENT_FILTER.lower() != "none"
        ):
            self.extract_attachment_filter = Config.EXTRACT_ATTACHMENT_FILTER
        else:
            self.extract_attachment_filter = "none"

        # Initialize extract maintain quality setting
        if user_extract_enabled and "EXTRACT_MAINTAIN_QUALITY" in self.user_dict:
            self.extract_maintain_quality = self.user_dict[
                "EXTRACT_MAINTAIN_QUALITY"
            ]
        elif self.extract_enabled and hasattr(Config, "EXTRACT_MAINTAIN_QUALITY"):
            self.extract_maintain_quality = Config.EXTRACT_MAINTAIN_QUALITY
        else:
            self.extract_maintain_quality = True

        # Initialize extract delete original setting
        # First check if it's set in user or owner settings
        if user_extract_enabled and "EXTRACT_DELETE_ORIGINAL" in self.user_dict:
            self.extract_delete_original = self.user_dict["EXTRACT_DELETE_ORIGINAL"]
            LOGGER.debug(
                f"Using user's extract delete original setting: {self.extract_delete_original}"
            )
        elif self.extract_enabled and hasattr(Config, "EXTRACT_DELETE_ORIGINAL"):
            self.extract_delete_original = Config.EXTRACT_DELETE_ORIGINAL
            LOGGER.debug(
                f"Using owner's extract delete original setting: {self.extract_delete_original}"
            )
        else:
            # Default to True when extract is enabled through settings
            self.extract_delete_original = True
            LOGGER.debug("Using default extract delete original setting: True")

        # Command line arguments override settings
        if hasattr(self, "args") and self.args:
            # The -del flag takes precedence over settings
            if self.args.get("-del") == "t" or self.args.get("-del") is True:
                self.extract_delete_original = True
                LOGGER.info("Setting extract_delete_original=True due to -del flag")
            elif self.args.get("-del") == "f" or self.args.get("-del") is False:
                self.extract_delete_original = False
                LOGGER.info("Setting extract_delete_original=False due to -del flag")

            # Handle extract flags
            if self.args.get("-extract") is True:
                self.extract_enabled = True
                LOGGER.debug("Extract enabled via command-line flag")

            if self.args.get("-extract-video") is True:
                self.extract_video_enabled = True
                LOGGER.debug("Video extraction enabled via command-line flag")

            if self.args.get("-extract-audio") is True:
                self.extract_audio_enabled = True
                LOGGER.debug("Audio extraction enabled via command-line flag")

            # Handle extract priority flag
            if self.args.get("-extract-priority") is not None:
                try:
                    self.extract_priority = int(self.args.get("-extract-priority"))
                    LOGGER.debug(
                        f"Extract priority set to {self.extract_priority} via command-line flag"
                    )
                except ValueError:
                    LOGGER.warning(
                        f"Invalid extract priority value: {self.args.get('-extract-priority')}, using default"
                    )
                    self.extract_priority = 6

            if self.args.get("-extract-subtitle") is True:
                self.extract_subtitle_enabled = True

            if self.args.get("-extract-attachment") is True:
                self.extract_attachment_enabled = True

            # Handle extract index flags (both long and short formats)
            # Video indices
            if self.args.get("-extract-video-index") is not None:
                # Handle multiple indices separated by commas or spaces
                video_indices = str(self.args.get("-extract-video-index")).split(",")
                for idx in video_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for video indices, will extract all video tracks"
                            )
                            # Clear any existing indices to extract all
                            self.extract_video_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_video_indices.append(index)
                        # For backward compatibility
                        if self.extract_video_index is None:
                            self.extract_video_index = index
                        # Auto-enable video extraction when index is specified
                        self.extract_enabled = True
                        self.extract_video_enabled = True
                        LOGGER.info(f"Added video index {index} to extraction list")
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid video index: {idx}")

                # Log the final list of indices
                if self.extract_video_indices:
                    LOGGER.info(
                        f"Will extract video tracks with indices: {self.extract_video_indices}"
                    )
                elif self.extract_video_enabled:
                    LOGGER.info(
                        "Will extract all video tracks (no specific indices)"
                    )

            elif self.args.get("-vi") is not None:
                # Handle multiple indices separated by commas or spaces
                video_indices = str(self.args.get("-vi")).split(",")
                for idx in video_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for video indices, will extract all video tracks"
                            )
                            # Clear any existing indices to extract all
                            self.extract_video_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_video_indices.append(index)
                        # For backward compatibility
                        if self.extract_video_index is None:
                            self.extract_video_index = index
                        # Auto-enable video extraction when index is specified
                        self.extract_enabled = True
                        self.extract_video_enabled = True
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid video index: {idx}")

            # Audio indices
            if self.args.get("-extract-audio-index") is not None:
                # Handle multiple indices separated by commas or spaces
                audio_indices = str(self.args.get("-extract-audio-index")).split(",")
                for idx in audio_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for audio indices, will extract all audio tracks"
                            )
                            # Clear any existing indices to extract all
                            self.extract_audio_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_audio_indices.append(index)
                        # For backward compatibility
                        if self.extract_audio_index is None:
                            self.extract_audio_index = index
                        # Auto-enable audio extraction when index is specified
                        self.extract_enabled = True
                        self.extract_audio_enabled = True
                        LOGGER.info(f"Added audio index {index} to extraction list")
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid audio index: {idx}")

                # Log the final list of indices
                if self.extract_audio_indices:
                    LOGGER.info(
                        f"Will extract audio tracks with indices: {self.extract_audio_indices}"
                    )
                elif self.extract_audio_enabled:
                    LOGGER.info(
                        "Will extract all audio tracks (no specific indices)"
                    )
            elif self.args.get("-ai") is not None:
                # Handle multiple indices separated by commas or spaces
                audio_indices = str(self.args.get("-ai")).split(",")
                for idx in audio_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for audio indices, will extract all audio tracks"
                            )
                            # Clear any existing indices to extract all
                            self.extract_audio_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_audio_indices.append(index)
                        # For backward compatibility
                        if self.extract_audio_index is None:
                            self.extract_audio_index = index
                        # Auto-enable audio extraction when index is specified
                        self.extract_enabled = True
                        self.extract_audio_enabled = True
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid audio index: {idx}")

            # Subtitle indices
            if self.args.get("-extract-subtitle-index") is not None:
                # Handle multiple indices separated by commas or spaces
                subtitle_indices = str(
                    self.args.get("-extract-subtitle-index")
                ).split(",")
                for idx in subtitle_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for subtitle indices, will extract all subtitle tracks"
                            )
                            # Clear any existing indices to extract all
                            self.extract_subtitle_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_subtitle_indices.append(index)
                        # For backward compatibility
                        if self.extract_subtitle_index is None:
                            self.extract_subtitle_index = index
                        # Auto-enable subtitle extraction when index is specified
                        self.extract_enabled = True
                        self.extract_subtitle_enabled = True
                        LOGGER.info(
                            f"Added subtitle index {index} to extraction list"
                        )
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid subtitle index: {idx}")

                # Log the final list of indices
                if self.extract_subtitle_indices:
                    LOGGER.info(
                        f"Will extract subtitle tracks with indices: {self.extract_subtitle_indices}"
                    )
                elif self.extract_subtitle_enabled:
                    LOGGER.info(
                        "Will extract all subtitle tracks (no specific indices)"
                    )
            elif self.args.get("-si") is not None:
                # Handle multiple indices separated by commas or spaces
                subtitle_indices = str(self.args.get("-si")).split(",")
                for idx in subtitle_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for subtitle indices, will extract all subtitle tracks"
                            )
                            # Clear any existing indices to extract all
                            self.extract_subtitle_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_subtitle_indices.append(index)
                        # For backward compatibility
                        if self.extract_subtitle_index is None:
                            self.extract_subtitle_index = index
                        # Auto-enable subtitle extraction when index is specified
                        self.extract_enabled = True
                        self.extract_subtitle_enabled = True
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid subtitle index: {idx}")

            # Attachment indices
            if self.args.get("-extract-attachment-index") is not None:
                # Handle multiple indices separated by commas or spaces
                attachment_indices = str(
                    self.args.get("-extract-attachment-index")
                ).split(",")
                for idx in attachment_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for attachment indices, will extract all attachment files"
                            )
                            # Clear any existing indices to extract all
                            self.extract_attachment_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_attachment_indices.append(index)
                        # For backward compatibility
                        if self.extract_attachment_index is None:
                            self.extract_attachment_index = index
                        # Auto-enable attachment extraction when index is specified
                        self.extract_enabled = True
                        self.extract_attachment_enabled = True
                        LOGGER.info(
                            f"Added attachment index {index} to extraction list"
                        )
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid attachment index: {idx}")

                # Log the final list of indices
                if self.extract_attachment_indices:
                    LOGGER.info(
                        f"Will extract attachment files with indices: {self.extract_attachment_indices}"
                    )
                elif self.extract_attachment_enabled:
                    LOGGER.info(
                        "Will extract all attachment files (no specific indices)"
                    )
            elif self.args.get("-ati") is not None:
                # Handle multiple indices separated by commas or spaces
                attachment_indices = str(self.args.get("-ati")).split(",")
                for idx in attachment_indices:
                    try:
                        # Check for special value "all"
                        if idx.strip().lower() == "all":
                            LOGGER.info(
                                "Special value 'all' found for attachment indices, will extract all attachment files"
                            )
                            # Clear any existing indices to extract all
                            self.extract_attachment_indices = []
                            break
                        # Strip any whitespace and convert to int
                        index = int(idx.strip())
                        self.extract_attachment_indices.append(index)
                        # For backward compatibility
                        if self.extract_attachment_index is None:
                            self.extract_attachment_index = index
                        # Auto-enable attachment extraction when index is specified
                        self.extract_enabled = True
                        self.extract_attachment_enabled = True
                    except ValueError:
                        if idx.strip() and idx.strip().lower() != "all":
                            LOGGER.warning(f"Invalid attachment index: {idx}")

            # Handle extract codec flags
            if self.args.get("-extract-video-codec"):
                self.extract_video_codec = self.args.get("-extract-video-codec")

            if self.args.get("-extract-video-format"):
                self.extract_video_format = self.args.get("-extract-video-format")

            if self.args.get("-extract-audio-codec"):
                self.extract_audio_codec = self.args.get("-extract-audio-codec")

            if self.args.get("-extract-audio-format"):
                self.extract_audio_format = self.args.get("-extract-audio-format")

            if self.args.get("-extract-subtitle-codec"):
                self.extract_subtitle_codec = self.args.get(
                    "-extract-subtitle-codec"
                )

            if self.args.get("-extract-subtitle-format"):
                self.extract_subtitle_format = self.args.get(
                    "-extract-subtitle-format"
                )

            if self.args.get("-extract-attachment-format"):
                self.extract_attachment_format = self.args.get(
                    "-extract-attachment-format"
                )

            # Handle extract maintain quality flag
            if self.args.get("-extract-maintain-quality"):
                maintain_quality = self.args.get("-extract-maintain-quality")
                if isinstance(maintain_quality, str):
                    self.extract_maintain_quality = maintain_quality.lower() in (
                        "true",
                        "t",
                        "1",
                        "yes",
                        "y",
                    )
                else:
                    self.extract_maintain_quality = bool(maintain_quality)

        # Initialize compression settings with the same priority logic
        user_compression_enabled = self.user_dict.get("COMPRESSION_ENABLED", False)
        owner_compression_enabled = (
            hasattr(Config, "COMPRESSION_ENABLED") and Config.COMPRESSION_ENABLED
        )

        # Set compression_enabled based on the same priority logic as other tools
        if hasattr(self, "compress_video") and self.compress_video:
            self.compression_enabled = True
            self.compression_video_enabled = True
        elif hasattr(self, "compress_audio") and self.compress_audio:
            self.compression_enabled = True
            self.compression_audio_enabled = True
        elif hasattr(self, "compress_image") and self.compress_image:
            self.compression_enabled = True
            self.compression_image_enabled = True
        elif hasattr(self, "compress_document") and self.compress_document:
            self.compression_enabled = True
            self.compression_document_enabled = True
        elif hasattr(self, "compress_subtitle") and self.compress_subtitle:
            self.compression_enabled = True
            self.compression_subtitle_enabled = True
        elif hasattr(self, "compress_archive") and self.compress_archive:
            self.compression_enabled = True
            self.compression_archive_enabled = True
        elif user_compression_enabled or (
            owner_compression_enabled and "COMPRESSION_ENABLED" not in self.user_dict
        ):
            self.compression_enabled = True
        else:
            self.compression_enabled = False

        # Set compression type enabled flags based on user or owner settings
        if self.compression_enabled:
            # Video compression
            if not hasattr(self, "compression_video_enabled"):
                user_compression_video_enabled = self.user_dict.get(
                    "COMPRESSION_VIDEO_ENABLED", False
                )
                owner_compression_video_enabled = Config.COMPRESSION_VIDEO_ENABLED
                if user_compression_video_enabled or (
                    owner_compression_video_enabled
                    and "COMPRESSION_VIDEO_ENABLED" not in self.user_dict
                ):
                    self.compression_video_enabled = True
                else:
                    self.compression_video_enabled = False

            # Audio compression
            if not hasattr(self, "compression_audio_enabled"):
                user_compression_audio_enabled = self.user_dict.get(
                    "COMPRESSION_AUDIO_ENABLED", False
                )
                owner_compression_audio_enabled = Config.COMPRESSION_AUDIO_ENABLED
                if user_compression_audio_enabled or (
                    owner_compression_audio_enabled
                    and "COMPRESSION_AUDIO_ENABLED" not in self.user_dict
                ):
                    self.compression_audio_enabled = True
                else:
                    self.compression_audio_enabled = False

            # Image compression
            if not hasattr(self, "compression_image_enabled"):
                user_compression_image_enabled = self.user_dict.get(
                    "COMPRESSION_IMAGE_ENABLED", False
                )
                owner_compression_image_enabled = Config.COMPRESSION_IMAGE_ENABLED
                if user_compression_image_enabled or (
                    owner_compression_image_enabled
                    and "COMPRESSION_IMAGE_ENABLED" not in self.user_dict
                ):
                    self.compression_image_enabled = True
                else:
                    self.compression_image_enabled = False

            # Document compression
            if not hasattr(self, "compression_document_enabled"):
                user_compression_document_enabled = self.user_dict.get(
                    "COMPRESSION_DOCUMENT_ENABLED", False
                )
                owner_compression_document_enabled = (
                    Config.COMPRESSION_DOCUMENT_ENABLED
                )
                if user_compression_document_enabled or (
                    owner_compression_document_enabled
                    and "COMPRESSION_DOCUMENT_ENABLED" not in self.user_dict
                ):
                    self.compression_document_enabled = True
                else:
                    self.compression_document_enabled = False

            # Subtitle compression
            if not hasattr(self, "compression_subtitle_enabled"):
                user_compression_subtitle_enabled = self.user_dict.get(
                    "COMPRESSION_SUBTITLE_ENABLED", False
                )
                owner_compression_subtitle_enabled = (
                    Config.COMPRESSION_SUBTITLE_ENABLED
                )
                if user_compression_subtitle_enabled or (
                    owner_compression_subtitle_enabled
                    and "COMPRESSION_SUBTITLE_ENABLED" not in self.user_dict
                ):
                    self.compression_subtitle_enabled = True
                else:
                    self.compression_subtitle_enabled = False

            # Archive compression
            if not hasattr(self, "compression_archive_enabled"):
                user_compression_archive_enabled = self.user_dict.get(
                    "COMPRESSION_ARCHIVE_ENABLED", False
                )
                owner_compression_archive_enabled = (
                    Config.COMPRESSION_ARCHIVE_ENABLED
                )
                if user_compression_archive_enabled or (
                    owner_compression_archive_enabled
                    and "COMPRESSION_ARCHIVE_ENABLED" not in self.user_dict
                ):
                    self.compression_archive_enabled = True
                else:
                    self.compression_archive_enabled = False

        # Compression Priority
        if (
            user_compression_enabled
            and "COMPRESSION_PRIORITY" in self.user_dict
            and self.user_dict["COMPRESSION_PRIORITY"]
        ):
            self.compression_priority = self.user_dict["COMPRESSION_PRIORITY"]
        elif self.compression_enabled and Config.COMPRESSION_PRIORITY:
            self.compression_priority = Config.COMPRESSION_PRIORITY
        else:
            self.compression_priority = 4

        # Compression Delete Original
        user_compression_delete_original = self.user_dict.get(
            "COMPRESSION_DELETE_ORIGINAL", False
        )
        owner_compression_delete_original = (
            hasattr(Config, "COMPRESSION_DELETE_ORIGINAL")
            and Config.COMPRESSION_DELETE_ORIGINAL
        )

        if "COMPRESSION_DELETE_ORIGINAL" in self.user_dict:
            self.compression_delete_original = user_compression_delete_original
        else:
            self.compression_delete_original = owner_compression_delete_original

        # Initialize compression format attributes
        # Video format
        user_video_format = self.user_dict.get("COMPRESSION_VIDEO_FORMAT")
        owner_video_format = getattr(Config, "COMPRESSION_VIDEO_FORMAT", None)

        if (
            user_video_format is not None
            and str(user_video_format).lower() != "none"
        ):
            self.compression_video_format = user_video_format
        elif (
            owner_video_format is not None
            and str(owner_video_format).lower() != "none"
        ):
            self.compression_video_format = owner_video_format
        else:
            self.compression_video_format = "none"  # Default format (keep original)

        # Audio format
        user_audio_format = self.user_dict.get("COMPRESSION_AUDIO_FORMAT")
        owner_audio_format = getattr(Config, "COMPRESSION_AUDIO_FORMAT", None)

        if (
            user_audio_format is not None
            and str(user_audio_format).lower() != "none"
        ):
            self.compression_audio_format = user_audio_format
        elif (
            owner_audio_format is not None
            and str(owner_audio_format).lower() != "none"
        ):
            self.compression_audio_format = owner_audio_format
        else:
            self.compression_audio_format = "none"  # Default format (keep original)

        # Image format
        user_image_format = self.user_dict.get("COMPRESSION_IMAGE_FORMAT")
        owner_image_format = getattr(Config, "COMPRESSION_IMAGE_FORMAT", None)

        if (
            user_image_format is not None
            and str(user_image_format).lower() != "none"
        ):
            self.compression_image_format = user_image_format
        elif (
            owner_image_format is not None
            and str(owner_image_format).lower() != "none"
        ):
            self.compression_image_format = owner_image_format
        else:
            self.compression_image_format = "none"  # Default format (keep original)

        # Document format
        user_document_format = self.user_dict.get("COMPRESSION_DOCUMENT_FORMAT")
        owner_document_format = getattr(Config, "COMPRESSION_DOCUMENT_FORMAT", None)

        if (
            user_document_format is not None
            and str(user_document_format).lower() != "none"
        ):
            self.compression_document_format = user_document_format
        elif (
            owner_document_format is not None
            and str(owner_document_format).lower() != "none"
        ):
            self.compression_document_format = owner_document_format
        else:
            self.compression_document_format = (
                "none"  # Default format (keep original)
            )

        # Subtitle format
        user_subtitle_format = self.user_dict.get("COMPRESSION_SUBTITLE_FORMAT")
        owner_subtitle_format = getattr(Config, "COMPRESSION_SUBTITLE_FORMAT", None)

        if (
            user_subtitle_format is not None
            and str(user_subtitle_format).lower() != "none"
        ):
            self.compression_subtitle_format = user_subtitle_format
        elif (
            owner_subtitle_format is not None
            and str(owner_subtitle_format).lower() != "none"
        ):
            self.compression_subtitle_format = owner_subtitle_format
        else:
            self.compression_subtitle_format = (
                "none"  # Default format (keep original)
            )

        # Archive format
        user_archive_format = self.user_dict.get("COMPRESSION_ARCHIVE_FORMAT")
        owner_archive_format = getattr(Config, "COMPRESSION_ARCHIVE_FORMAT", None)

        if (
            user_archive_format is not None
            and str(user_archive_format).lower() != "none"
        ):
            self.compression_archive_format = user_archive_format
        elif (
            owner_archive_format is not None
            and str(owner_archive_format).lower() != "none"
        ):
            self.compression_archive_format = owner_archive_format
        else:
            self.compression_archive_format = (
                "none"  # Default format (keep original)
            )

        # Set compression presets based on command line flags or settings
        if hasattr(self, "video_preset") and self.video_preset:
            self.compression_video_preset = self.video_preset
        elif (
            user_compression_enabled
            and "COMPRESSION_VIDEO_PRESET" in self.user_dict
            and self.user_dict["COMPRESSION_VIDEO_PRESET"] is not None
            and self.user_dict["COMPRESSION_VIDEO_PRESET"] != "none"
            and self.user_dict["COMPRESSION_VIDEO_PRESET"].lower() != "none"
        ):
            self.compression_video_preset = self.user_dict[
                "COMPRESSION_VIDEO_PRESET"
            ]
        elif (
            self.compression_enabled
            and hasattr(Config, "COMPRESSION_VIDEO_PRESET")
            and Config.COMPRESSION_VIDEO_PRESET is not None
            and Config.COMPRESSION_VIDEO_PRESET != "none"
            and Config.COMPRESSION_VIDEO_PRESET.lower() != "none"
        ):
            self.compression_video_preset = Config.COMPRESSION_VIDEO_PRESET
        else:
            self.compression_video_preset = "medium"

        if hasattr(self, "audio_preset") and self.audio_preset:
            self.compression_audio_preset = self.audio_preset
        elif (
            user_compression_enabled
            and "COMPRESSION_AUDIO_PRESET" in self.user_dict
            and self.user_dict["COMPRESSION_AUDIO_PRESET"] is not None
            and self.user_dict["COMPRESSION_AUDIO_PRESET"] != "none"
            and self.user_dict["COMPRESSION_AUDIO_PRESET"].lower() != "none"
        ):
            self.compression_audio_preset = self.user_dict[
                "COMPRESSION_AUDIO_PRESET"
            ]
        elif (
            self.compression_enabled
            and hasattr(Config, "COMPRESSION_AUDIO_PRESET")
            and Config.COMPRESSION_AUDIO_PRESET is not None
            and Config.COMPRESSION_AUDIO_PRESET != "none"
            and Config.COMPRESSION_AUDIO_PRESET.lower() != "none"
        ):
            self.compression_audio_preset = Config.COMPRESSION_AUDIO_PRESET
        else:
            self.compression_audio_preset = "medium"

        if hasattr(self, "image_preset") and self.image_preset:
            self.compression_image_preset = self.image_preset
        elif (
            user_compression_enabled
            and "COMPRESSION_IMAGE_PRESET" in self.user_dict
            and self.user_dict["COMPRESSION_IMAGE_PRESET"] is not None
            and self.user_dict["COMPRESSION_IMAGE_PRESET"] != "none"
            and self.user_dict["COMPRESSION_IMAGE_PRESET"].lower() != "none"
        ):
            self.compression_image_preset = self.user_dict[
                "COMPRESSION_IMAGE_PRESET"
            ]
        elif (
            self.compression_enabled
            and hasattr(Config, "COMPRESSION_IMAGE_PRESET")
            and Config.COMPRESSION_IMAGE_PRESET is not None
            and Config.COMPRESSION_IMAGE_PRESET != "none"
            and Config.COMPRESSION_IMAGE_PRESET.lower() != "none"
        ):
            self.compression_image_preset = Config.COMPRESSION_IMAGE_PRESET
        else:
            self.compression_image_preset = "medium"

        if hasattr(self, "document_preset") and self.document_preset:
            self.compression_document_preset = self.document_preset
        elif (
            user_compression_enabled
            and "COMPRESSION_DOCUMENT_PRESET" in self.user_dict
            and self.user_dict["COMPRESSION_DOCUMENT_PRESET"] is not None
            and self.user_dict["COMPRESSION_DOCUMENT_PRESET"] != "none"
            and self.user_dict["COMPRESSION_DOCUMENT_PRESET"].lower() != "none"
        ):
            self.compression_document_preset = self.user_dict[
                "COMPRESSION_DOCUMENT_PRESET"
            ]
        elif (
            self.compression_enabled
            and hasattr(Config, "COMPRESSION_DOCUMENT_PRESET")
            and Config.COMPRESSION_DOCUMENT_PRESET is not None
            and Config.COMPRESSION_DOCUMENT_PRESET != "none"
            and Config.COMPRESSION_DOCUMENT_PRESET.lower() != "none"
        ):
            self.compression_document_preset = Config.COMPRESSION_DOCUMENT_PRESET
        else:
            self.compression_document_preset = "medium"

        if hasattr(self, "subtitle_preset") and self.subtitle_preset:
            self.compression_subtitle_preset = self.subtitle_preset
        elif (
            user_compression_enabled
            and "COMPRESSION_SUBTITLE_PRESET" in self.user_dict
            and self.user_dict["COMPRESSION_SUBTITLE_PRESET"] is not None
            and self.user_dict["COMPRESSION_SUBTITLE_PRESET"] != "none"
            and self.user_dict["COMPRESSION_SUBTITLE_PRESET"].lower() != "none"
        ):
            self.compression_subtitle_preset = self.user_dict[
                "COMPRESSION_SUBTITLE_PRESET"
            ]
        elif (
            self.compression_enabled
            and hasattr(Config, "COMPRESSION_SUBTITLE_PRESET")
            and Config.COMPRESSION_SUBTITLE_PRESET is not None
            and Config.COMPRESSION_SUBTITLE_PRESET != "none"
            and Config.COMPRESSION_SUBTITLE_PRESET.lower() != "none"
        ):
            self.compression_subtitle_preset = Config.COMPRESSION_SUBTITLE_PRESET
        else:
            self.compression_subtitle_preset = "medium"

        if hasattr(self, "archive_preset") and self.archive_preset:
            self.compression_archive_preset = self.archive_preset
        elif (
            user_compression_enabled
            and "COMPRESSION_ARCHIVE_PRESET" in self.user_dict
            and self.user_dict["COMPRESSION_ARCHIVE_PRESET"] is not None
            and self.user_dict["COMPRESSION_ARCHIVE_PRESET"] != "none"
            and self.user_dict["COMPRESSION_ARCHIVE_PRESET"].lower() != "none"
        ):
            self.compression_archive_preset = self.user_dict[
                "COMPRESSION_ARCHIVE_PRESET"
            ]
        elif (
            self.compression_enabled
            and hasattr(Config, "COMPRESSION_ARCHIVE_PRESET")
            and Config.COMPRESSION_ARCHIVE_PRESET is not None
            and Config.COMPRESSION_ARCHIVE_PRESET != "none"
            and Config.COMPRESSION_ARCHIVE_PRESET.lower() != "none"
        ):
            self.compression_archive_preset = Config.COMPRESSION_ARCHIVE_PRESET
        else:
            self.compression_archive_preset = "medium"

        if "CONVERT_ENABLED" in self.user_dict:
            if self.user_convert_enabled:
                # User has enabled convert - apply user settings
                convert_enabled = True
                LOGGER.debug("Convert enabled by user settings")
            else:
                # User has disabled convert - check owner settings
                convert_enabled = self.owner_convert_enabled
                if convert_enabled:
                    LOGGER.debug("Convert enabled by owner settings (user disabled)")
                else:
                    LOGGER.debug("Convert disabled (both user and owner disabled)")
        else:
            # User hasn't set convert enabled/disabled - use owner settings
            convert_enabled = self.owner_convert_enabled
            if convert_enabled:
                LOGGER.debug("Convert enabled by owner settings (user not set)")
            else:
                LOGGER.debug("Convert disabled (owner disabled, user not set)")

        # Only apply convert settings if not explicitly set via command line
        if convert_enabled and not self.convert_video and not self.convert_audio:
            # Check for video convert settings
            user_video_format = self.user_dict.get("CONVERT_VIDEO_FORMAT", "")
            owner_video_format = (
                hasattr(Config, "CONVERT_VIDEO_FORMAT")
                and Config.CONVERT_VIDEO_FORMAT
            )

            # Check if user has video convert enabled
            user_video_enabled = self.user_dict.get("CONVERT_VIDEO_ENABLED", False)
            owner_video_enabled = (
                hasattr(Config, "CONVERT_VIDEO_ENABLED")
                and Config.CONVERT_VIDEO_ENABLED
            )

            # Determine if video convert should be enabled
            video_convert_enabled = False
            if "CONVERT_VIDEO_ENABLED" in self.user_dict:
                video_convert_enabled = user_video_enabled
            else:
                video_convert_enabled = owner_video_enabled

            if video_convert_enabled:
                if user_video_format and user_video_format.lower() != "none":
                    self.convert_video = user_video_format
                    LOGGER.debug(
                        f"Using user's video convert format: {self.convert_video}"
                    )
                elif owner_video_format and owner_video_format.lower() != "none":
                    self.convert_video = owner_video_format
                    LOGGER.debug(
                        f"Using owner's video convert format: {self.convert_video}"
                    )
                else:
                    # Don't set any format if none is specified
                    self.convert_video = None
                    LOGGER.debug(
                        "No video convert format specified, skipping video conversion"
                    )

            # Check for audio convert settings
            user_audio_format = self.user_dict.get("CONVERT_AUDIO_FORMAT", "")
            owner_audio_format = (
                hasattr(Config, "CONVERT_AUDIO_FORMAT")
                and Config.CONVERT_AUDIO_FORMAT
            )

            # Check if user has audio convert enabled
            user_audio_enabled = self.user_dict.get("CONVERT_AUDIO_ENABLED", False)
            owner_audio_enabled = (
                hasattr(Config, "CONVERT_AUDIO_ENABLED")
                and Config.CONVERT_AUDIO_ENABLED
            )

            # Determine if audio convert should be enabled
            audio_convert_enabled = False
            if "CONVERT_AUDIO_ENABLED" in self.user_dict:
                audio_convert_enabled = user_audio_enabled
            else:
                audio_convert_enabled = owner_audio_enabled

            if audio_convert_enabled:
                if user_audio_format and user_audio_format.lower() != "none":
                    self.convert_audio = user_audio_format
                    LOGGER.debug(
                        f"Using user's audio convert format: {self.convert_audio}"
                    )
                elif owner_audio_format and owner_audio_format.lower() != "none":
                    self.convert_audio = owner_audio_format
                    LOGGER.debug(
                        f"Using owner's audio convert format: {self.convert_audio}"
                    )
                else:
                    # Don't set any format if none is specified
                    self.convert_audio = None
                    LOGGER.debug(
                        "No audio convert format specified, skipping audio conversion"
                    )

        if self.name_sub:
            self.name_sub = [x.split("/") for x in self.name_sub.split(" | ")]
        self.excluded_extensions = self.user_dict.get("EXCLUDED_EXTENSIONS") or (
            excluded_extensions
            if "EXCLUDED_EXTENSIONS" not in self.user_dict
            else ["aria2", "!qB"]
        )
        if not self.rc_flags:
            if self.user_dict.get("RCLONE_FLAGS"):
                self.rc_flags = self.user_dict["RCLONE_FLAGS"]
            elif "RCLONE_FLAGS" not in self.user_dict and Config.RCLONE_FLAGS:
                self.rc_flags = Config.RCLONE_FLAGS
        if self.link not in ["rcl", "gdl"]:
            if not self.is_jd:
                if is_rclone_path(self.link):
                    if not self.link.startswith("mrcc:") and self.user_dict.get(
                        "USER_TOKENS",
                        False,
                    ):
                        self.link = f"mrcc:{self.link}"
                    await self.is_token_exists(self.link, "dl")
            elif is_gdrive_link(self.link):
                if not self.link.startswith(
                    ("mtp:", "tp:", "sa:"),
                ) and self.user_dict.get("USER_TOKENS", False):
                    self.link = f"mtp:{self.link}"
                await self.is_token_exists(self.link, "dl")
        elif self.link == "rcl":
            if not self.is_ytdlp and not self.is_jd:
                self.link = await RcloneList(self).get_rclone_path("rcd")
                if not is_rclone_path(self.link):
                    raise ValueError(self.link)
        elif self.link == "gdl" and not self.is_ytdlp and not self.is_jd:
            self.link = await GoogleDriveList(self).get_target_id("gdd")
            if not is_gdrive_id(self.link):
                raise ValueError(self.link)

        self.user_transmission = TgClient.IS_PREMIUM_USER and (
            self.user_dict.get("USER_TRANSMISSION")
            or (
                Config.USER_TRANSMISSION
                and "USER_TRANSMISSION" not in self.user_dict
            )
        )

        if self.user_dict.get("UPLOAD_PATHS", False):
            if self.up_dest in self.user_dict["UPLOAD_PATHS"]:
                self.up_dest = self.user_dict["UPLOAD_PATHS"][self.up_dest]
        elif (
            "UPLOAD_PATHS" not in self.user_dict
            and Config.UPLOAD_PATHS
            and self.up_dest in Config.UPLOAD_PATHS
        ):
            self.up_dest = Config.UPLOAD_PATHS[self.up_dest]

        if self.ffmpeg_cmds and not isinstance(self.ffmpeg_cmds, list):
            if self.user_dict.get("FFMPEG_CMDS", None):
                ffmpeg_dict = self.user_dict["FFMPEG_CMDS"]
                self.ffmpeg_cmds = [
                    value
                    for key in list(self.ffmpeg_cmds)
                    if key in ffmpeg_dict
                    for value in ffmpeg_dict[key]
                ]
            elif "FFMPEG_CMDS" not in self.user_dict and Config.FFMPEG_CMDS:
                ffmpeg_dict = Config.FFMPEG_CMDS
                self.ffmpeg_cmds = [
                    value
                    for key in list(self.ffmpeg_cmds)
                    if key in ffmpeg_dict
                    for value in ffmpeg_dict[key]
                ]
            else:
                self.ffmpeg_cmds = None
        if not self.is_leech:
            self.stop_duplicate = self.user_dict.get("STOP_DUPLICATE") or (
                "STOP_DUPLICATE" not in self.user_dict and Config.STOP_DUPLICATE
            )
            default_upload = (
                self.user_dict.get("DEFAULT_UPLOAD", "") or Config.DEFAULT_UPLOAD
            )
            if (not self.up_dest and default_upload == "rc") or self.up_dest == "rc":
                # User's RCLONE_PATH has higher priority than owner's
                if "RCLONE_PATH" in self.user_dict:
                    self.up_dest = self.user_dict["RCLONE_PATH"]
                elif Config.RCLONE_PATH:
                    self.up_dest = Config.RCLONE_PATH
                else:
                    self.up_dest = ""
            elif (
                not self.up_dest and default_upload == "gd"
            ) or self.up_dest == "gd":
                self.up_dest = self.user_dict.get("GDRIVE_ID") or Config.GDRIVE_ID
            if not self.up_dest:
                raise ValueError("No Upload Destination!")
            if is_gdrive_id(self.up_dest):
                if not self.up_dest.startswith(
                    ("mtp:", "tp:", "sa:"),
                ) and self.user_dict.get("USER_TOKENS", False):
                    self.up_dest = f"mtp:{self.up_dest}"
            elif is_rclone_path(self.up_dest):
                if not self.up_dest.startswith("mrcc:") and self.user_dict.get(
                    "USER_TOKENS",
                    False,
                ):
                    self.up_dest = f"mrcc:{self.up_dest}"
                self.up_dest = self.up_dest.strip("/")
            else:
                raise ValueError("Wrong Upload Destination!")

            if self.up_dest not in ["rcl", "gdl"]:
                await self.is_token_exists(self.up_dest, "up")

            if self.up_dest == "rcl":
                if self.is_clone:
                    if not is_rclone_path(self.link):
                        raise ValueError(
                            "You can't clone from different types of tools",
                        )
                    config_path = self.get_config_path(self.link)
                else:
                    config_path = None
                self.up_dest = await RcloneList(self).get_rclone_path(
                    "rcu",
                    config_path,
                )
                if not is_rclone_path(self.up_dest):
                    raise ValueError(self.up_dest)
            elif self.up_dest == "gdl":
                if self.is_clone:
                    if not is_gdrive_link(self.link):
                        raise ValueError(
                            "You can't clone from different types of tools",
                        )
                    token_path = self.get_token_path(self.link)
                else:
                    token_path = None
                self.up_dest = await GoogleDriveList(self).get_target_id(
                    "gdu",
                    token_path,
                )
                if not is_gdrive_id(self.up_dest):
                    raise ValueError(self.up_dest)
            elif self.is_clone:
                if is_gdrive_link(self.link) and self.get_token_path(
                    self.link,
                ) != self.get_token_path(self.up_dest):
                    raise ValueError("You must use the same token to clone!")
                if is_rclone_path(self.link) and self.get_config_path(
                    self.link,
                ) != self.get_config_path(self.up_dest):
                    raise ValueError("You must use the same config to clone!")
        else:
            self.up_dest = (
                self.up_dest
                or self.user_dict.get("LEECH_DUMP_CHAT")
                or Config.LEECH_DUMP_CHAT
            )
            self.hybrid_leech = TgClient.IS_PREMIUM_USER and (
                self.user_dict.get("HYBRID_LEECH")
                or (Config.HYBRID_LEECH and "HYBRID_LEECH" not in self.user_dict)
            )
            if self.bot_trans:
                self.user_transmission = False
                self.hybrid_leech = False
            if self.user_trans:
                self.user_transmission = TgClient.IS_PREMIUM_USER
            if self.up_dest:
                if not isinstance(self.up_dest, int):
                    if self.up_dest.startswith("b:"):
                        self.up_dest = self.up_dest.replace("b:", "", 1)
                        self.user_transmission = False
                        self.hybrid_leech = False
                    elif self.up_dest.startswith("u:"):
                        self.up_dest = self.up_dest.replace("u:", "", 1)
                        self.user_transmission = TgClient.IS_PREMIUM_USER
                    elif self.up_dest.startswith("h:"):
                        self.up_dest = self.up_dest.replace("h:", "", 1)
                        self.user_transmission = TgClient.IS_PREMIUM_USER
                        self.hybrid_leech = self.user_transmission
                    if "|" in self.up_dest:
                        self.up_dest, self.chat_thread_id = [
                            int(x) if x.lstrip("-").isdigit() else x
                            for x in self.up_dest.split("|", 1)
                        ]
                    elif self.up_dest.lstrip("-").isdigit():
                        self.up_dest = int(self.up_dest)
                    elif self.up_dest.lower() == "pm":
                        self.up_dest = self.user_id

                if self.user_transmission:
                    try:
                        chat = await TgClient.user.get_chat(self.up_dest)
                    except Exception:
                        chat = None
                    if chat is None:
                        self.user_transmission = False
                        self.hybrid_leech = False
                    else:
                        uploader_id = TgClient.user.me.id
                        if chat.type.name not in ["SUPERGROUP", "CHANNEL", "GROUP"]:
                            self.user_transmission = False
                            self.hybrid_leech = False
                        else:
                            member = await chat.get_member(uploader_id)
                            if (
                                not member.privileges.can_manage_chat
                                or not member.privileges.can_delete_messages
                            ):
                                self.user_transmission = False
                                self.hybrid_leech = False

                if not self.user_transmission or self.hybrid_leech:
                    try:
                        chat = await self.client.get_chat(self.up_dest)
                    except Exception:
                        chat = None
                    if chat is None:
                        if self.user_transmission:
                            self.hybrid_leech = False
                        else:
                            raise ValueError("Chat not found!")
                    else:
                        uploader_id = self.client.me.id
                        if chat.type.name in ["SUPERGROUP", "CHANNEL", "GROUP"]:
                            member = await chat.get_member(uploader_id)
                            if (
                                not member.privileges.can_manage_chat
                                or not member.privileges.can_delete_messages
                            ):
                                if not self.user_transmission:
                                    raise ValueError(
                                        "You don't have enough privileges in this chat!",
                                    )
                                self.hybrid_leech = False
                        else:
                            try:
                                await self.client.send_chat_action(
                                    self.up_dest,
                                    ChatAction.TYPING,
                                )
                            except Exception:
                                raise ValueError(
                                    "Start the bot and try again!",
                                ) from None
            elif (
                self.user_transmission or self.hybrid_leech
            ) and not self.is_super_chat:
                self.user_transmission = False
                self.hybrid_leech = False
            # Calculate max split size based on owner's session only
            # Always use owner's session for max split size calculation, not user's own session
            self.max_split_size = (
                TgClient.MAX_SPLIT_SIZE
                if hasattr(Config, "USER_SESSION_STRING")
                and Config.USER_SESSION_STRING
                else 2097152000
            )

            # Process command-line split size if provided
            if self.split_size:
                if self.split_size.isdigit():
                    self.split_size = int(self.split_size)
                else:
                    self.split_size = get_size_bytes(self.split_size)

            # Get split size from command args, user settings, or bot config (in that order)
            # This ensures custom split sizes set by user or owner get priority
            if not self.split_size:
                # User settings have second priority
                if self.user_dict.get("LEECH_SPLIT_SIZE"):
                    self.split_size = self.user_dict.get("LEECH_SPLIT_SIZE")
                # Owner settings have third priority
                elif Config.LEECH_SPLIT_SIZE:
                    self.split_size = Config.LEECH_SPLIT_SIZE
                # Default to max split size if no custom size is set
                else:
                    self.split_size = self.max_split_size

            # Ensure split size doesn't exceed maximum allowed
            self.split_size = min(self.split_size, self.max_split_size)

            if not self.as_doc:
                self.as_doc = (
                    not self.as_med
                    if self.as_med
                    else (
                        self.user_dict.get("AS_DOCUMENT", False)
                        or (
                            Config.AS_DOCUMENT
                            and "AS_DOCUMENT" not in self.user_dict
                        )
                    )
                )

            self.thumbnail_layout = (
                self.thumbnail_layout
                or self.user_dict.get("THUMBNAIL_LAYOUT", False)
                or (
                    Config.THUMBNAIL_LAYOUT
                    if "THUMBNAIL_LAYOUT" not in self.user_dict
                    else ""
                )
            )

            if self.thumb != "none" and is_telegram_link(self.thumb):
                msg, _ = (await get_tg_link_message(self.thumb))[0]
                self.thumb = (
                    await create_thumb(msg) if msg.photo or msg.document else ""
                )

    async def get_tag(self, text: list):
        if len(text) > 1 and text[1].startswith("Tag: "):
            user_info = text[1].split("Tag: ")
            if len(user_info) >= 3:
                id_ = user_info[-1]
                self.tag = " ".join(user_info[:-1])
            else:
                self.tag, id_ = text[1].split("Tag: ")[1].split()
            self.user = self.message.from_user = await self.client.get_users(id_)
            self.user_id = self.user.id
            self.user_dict = user_data.get(self.user_id, {})
            with contextlib.suppress(Exception):
                await self.message.unpin()
        if self.user:
            if username := self.user.username:
                self.tag = f"@{username}"
            elif hasattr(self.user, "mention"):
                self.tag = self.user.mention
            else:
                self.tag = self.user.title

    @new_task
    async def run_multi(self, input_list, obj):
        await sleep(7)
        if not self.multi_tag and self.multi > 1:
            self.multi_tag = token_hex(2)
            multi_tags.add(self.multi_tag)
        elif self.multi <= 1:
            if self.multi_tag in multi_tags:
                multi_tags.discard(self.multi_tag)
            return
        if self.multi_tag and self.multi_tag not in multi_tags:
            await send_message(
                self.message,
                f"{self.tag} Multi Task has been cancelled!",
            )
            await send_status_message(self.message)
            async with task_dict_lock:
                for fd_name in self.same_dir:
                    self.same_dir[fd_name]["total"] -= self.multi
            return
        if len(self.bulk) != 0:
            msg = input_list[:1]
            msg.append(f"{self.bulk[0]} -i {self.multi - 1} {self.options}")
            msgts = " ".join(msg)
            if self.multi > 2:
                msgts += f"\nCancel Multi: <code>/stop {self.multi_tag}</code>"
            nextmsg = await send_message(self.message, msgts)
        else:
            msg = [s.strip() for s in input_list]
            # Check if "-i" exists in the command
            if "-i" in msg:
                index = msg.index("-i")
                msg[index + 1] = f"{self.multi - 1}"
            else:
                # If "-i" is not found, add it to the command
                LOGGER.warning(f"Command missing -i parameter: {msg}")
                msg.extend(["-i", f"{self.multi - 1}"])
            nextmsg = await self.client.get_messages(
                chat_id=self.message.chat.id,
                message_ids=self.message.reply_to_message_id + 1,
            )
            msgts = " ".join(msg)
            if self.multi > 2:
                msgts += f"\nCancel Multi: <code>/stop {self.multi_tag}</code>"
            nextmsg = await send_message(nextmsg, msgts)
        # Check if nextmsg is a Message object or a string
        if isinstance(nextmsg, str):
            LOGGER.warning(f"nextmsg is a string, not a Message object: {nextmsg}")
            # Try to find the message by content instead
            # Electrogram doesn't support 'limit' parameter for get_messages
            # Instead, use get_chat_history which supports limit
            try:
                messages = await self.client.get_chat_history(
                    chat_id=self.message.chat.id,
                    limit=5,  # Look at the last few messages
                )
            except Exception as e:
                LOGGER.error(f"Error getting chat history: {e}")
                messages = []
            for msg in messages:
                if msg and msg.text and msg.text == nextmsg:
                    nextmsg = msg
                    break
            # If we still couldn't find it, create a new message
            if isinstance(nextmsg, str):
                nextmsg = await send_message(self.message.chat.id, nextmsg)
        else:
            # Normal case - nextmsg is a Message object
            try:
                # Get the message by its ID
                try:
                    nextmsg = await self.client.get_messages(
                        chat_id=self.message.chat.id,
                        message_ids=nextmsg.id,
                    )
                except TypeError as e:
                    # Handle case where get_messages has different parameters in Electrogram
                    if "unexpected keyword argument" in str(e):
                        LOGGER.debug(f"Adapting to Electrogram API: {e}")
                        # Try alternative approach for Electrogram
                        nextmsg = await self.client.get_messages(
                            self.message.chat.id,  # chat_id as positional argument
                            nextmsg.id,  # message_ids as positional argument
                        )
                    else:
                        raise
            except Exception as e:
                LOGGER.error(f"Error getting message: {e}")
                # Create a new message if we can't get the original
                if hasattr(nextmsg, "text") and nextmsg.text:
                    nextmsg = await send_message(self.message.chat.id, nextmsg.text)
                else:
                    # If all else fails, create a generic message
                    nextmsg = await send_message(
                        self.message.chat.id,
                        "Processing your request...",
                    )
        if self.message.from_user:
            nextmsg.from_user = self.user
        else:
            nextmsg.sender_chat = self.user
        if intervals["stopAll"]:
            return
        await obj(
            self.client,
            nextmsg,
            self.is_qbit,
            self.is_leech,
            self.is_jd,
            self.is_nzb,
            self.same_dir,
            self.bulk,
            self.multi_tag,
            self.options,
        ).new_event()

    async def init_bulk(self, input_list, bulk_start, bulk_end, obj):
        try:
            self.bulk = await extract_bulk_links(self.message, bulk_start, bulk_end)
            if len(self.bulk) == 0:
                raise ValueError("Bulk Empty!")
            b_msg = input_list[:1]
            self.options = input_list[1:]
            index = self.options.index("-b")
            del self.options[index]
            if bulk_start or bulk_end:
                del self.options[index + 1]
            self.options = " ".join(self.options)
            b_msg.append(f"{self.bulk[0]} -i {len(self.bulk)} {self.options}")
            msg = " ".join(b_msg)
            if len(self.bulk) > 2:
                self.multi_tag = token_hex(2)
                multi_tags.add(self.multi_tag)
                msg += f"\nCancel Multi: <code>/stop {self.multi_tag}</code>"
            nextmsg = await send_message(self.message, msg)
            # Get the message by its ID with Electrogram compatibility
            try:
                nextmsg = await self.client.get_messages(
                    chat_id=self.message.chat.id,
                    message_ids=nextmsg.id,
                )
            except TypeError as e:
                # Handle case where get_messages has different parameters in Electrogram
                if "unexpected keyword argument" in str(e):
                    LOGGER.debug(f"Adapting to Electrogram API: {e}")
                    # Try alternative approach for Electrogram
                    nextmsg = await self.client.get_messages(
                        self.message.chat.id,  # chat_id as positional argument
                        nextmsg.id,  # message_ids as positional argument
                    )
                else:
                    raise
            if self.message.from_user:
                nextmsg.from_user = self.user
            else:
                nextmsg.sender_chat = self.user
            await obj(
                self.client,
                nextmsg,
                self.is_qbit,
                self.is_leech,
                self.is_jd,
                self.is_nzb,
                self.same_dir,
                self.bulk,
                self.multi_tag,
                self.options,
            ).new_event()
        except Exception:
            await send_message(
                self.message,
                "Reply to text file or to telegram message that have links separated by new line!",
            )

    async def proceed_extract(self, dl_path, gid):
        # This is the archive extraction method
        pswd = self.extract if isinstance(self.extract, str) else ""
        self.files_to_proceed = []
        if self.is_file and is_archive(dl_path):
            self.files_to_proceed.append(dl_path)
        else:
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    if is_first_archive_split(file_) or (
                        is_archive(file_)
                        and not file_.strip().lower().endswith(".rar")
                    ):
                        f_path = ospath.join(dirpath, file_)
                        self.files_to_proceed.append(f_path)

        if not self.files_to_proceed:
            return dl_path
        sevenz = SevenZ(self)
        LOGGER.info(f"Extracting: {self.name}")
        async with task_dict_lock:
            task_dict[self.mid] = SevenZStatus(self, sevenz, gid, "Extract")
        for dirpath, _, files in await sync_to_async(
            walk,
            self.up_dir or self.dir,
            topdown=False,
        ):
            for file_ in files:
                if self.is_cancelled:
                    return False
                if is_first_archive_split(file_) or (
                    is_archive(file_) and not file_.strip().lower().endswith(".rar")
                ):
                    self.proceed_count += 1
                    f_path = ospath.join(dirpath, file_)
                    t_path = get_base_name(f_path) if self.is_file else dirpath
                    if not self.is_file:
                        self.subname = file_
                    code = await sevenz.extract(f_path, t_path, pswd)
                else:
                    code = 0
            if self.is_cancelled:
                return code
            if code == 0:
                for file_ in files:
                    if is_archive_split(file_) or is_archive(file_):
                        del_path = ospath.join(dirpath, file_)
                        try:
                            await remove(del_path)
                        except Exception:
                            self.is_cancelled = True
        return t_path if self.is_file and code == 0 else dl_path

    async def proceed_ffmpeg(self, dl_path, gid):
        checked = False
        cmds = []

        # Log the FFmpeg commands for debugging
        LOGGER.debug(f"FFmpeg commands before processing: {self.ffmpeg_cmds}")

        # Check if ffmpeg_cmds is empty or None
        if not self.ffmpeg_cmds:
            LOGGER.warning(
                "FFmpeg commands list is empty or None, nothing to process"
            )
            return dl_path

        # Process each FFmpeg command with error handling for unclosed quotations
        for item in self.ffmpeg_cmds:
            try:
                # Try to split the command using shlex.split
                parts = [part.strip() for part in split(item) if part.strip()]
                cmds.append(parts)
            except ValueError as e:
                # Handle the "No closing quotation" error
                if "No closing quotation" in str(e):
                    # Fix the command by adding the missing quotation mark
                    fixed_item = item
                    if item.count('"') % 2 != 0:  # Odd number of double quotes
                        fixed_item = item + '"'
                    elif item.count("'") % 2 != 0:  # Odd number of single quotes
                        fixed_item = item + "'"

                    try:
                        # Try again with the fixed command
                        parts = [
                            part.strip()
                            for part in split(fixed_item)
                            if part.strip()
                        ]
                        cmds.append(parts)
                        LOGGER.debug(
                            f"Fixed unclosed quotation in FFmpeg command: {item} -> {fixed_item}"
                        )
                    except ValueError:
                        # If still failing, use a simple space-based split as fallback
                        LOGGER.debug(
                            f"Using fallback split for FFmpeg command with quotation error: {item}"
                        )
                        parts = [part for part in item.split() if part]
                        cmds.append(parts)
                else:
                    # For other ValueError exceptions, use simple split
                    LOGGER.debug(
                        f"Error parsing FFmpeg command: {e}. Using fallback split."
                    )
                    parts = [part for part in item.split() if part]
                    cmds.append(parts)

        # Log the processed commands
        LOGGER.debug(f"Processed FFmpeg commands: {cmds}")

        # Check if any command is empty or missing input parameter
        for i, cmd in enumerate(cmds):
            if not cmd:
                LOGGER.warning(f"Empty FFmpeg command at index {i}")
            elif "-i" not in cmd:
                LOGGER.warning(
                    f"FFmpeg command at index {i} missing input parameter: {cmd}"
                )

        # Skip processing if all commands are empty
        if not cmds:
            LOGGER.warning("No valid FFmpeg commands to process after parsing")
            return dl_path

        try:
            ffmpeg = FFMpeg(self)
            for ffmpeg_cmd in cmds:
                # Skip empty commands
                if not ffmpeg_cmd:
                    LOGGER.warning("Skipping empty FFmpeg command")
                    continue
                self.proceed_count = 0
                # Resource manager removed

                # Check for -del in ffmpeg_cmd before creating the base command
                delete_files = False
                if "-del" in ffmpeg_cmd:
                    ffmpeg_cmd.remove("-del")
                    delete_files = True
                    LOGGER.debug(
                        "Detected -del flag, will delete original files after processing"
                    )

                # Create the base command
                cmd = [
                    "xtra",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-threads",
                    f"{max(1, cpu_no // 2)}",  # Default thread count, will be replaced by resource manager if needed
                    *ffmpeg_cmd,
                ]

                # Resource manager removed

                # Special case: if the command starts with 'bash' and '-c', it's a wrapped command
                if len(cmd) >= 3 and cmd[0] == "bash" and cmd[1] == "-c":
                    LOGGER.debug(f"Detected bash -c wrapped command: {cmd}")
                    # The actual command is in the third element as a string
                    # We need to check if it contains '-i' anywhere in the string
                    if "-i" not in cmd[2]:
                        LOGGER.warning(
                            f"FFmpeg command missing -i parameter in bash wrapper: {cmd}"
                        )
                        # Insert the -i parameter before the output file (which is typically at the end)
                        # This is a bit tricky since it's a string, so we'll need to modify the string
                        cmd_parts = cmd[2].split(" && ", 1)
                        if len(cmd_parts) > 1:
                            # There's a ulimit command before the actual ffmpeg command
                            ulimit_part = cmd_parts[0]
                            ffmpeg_part = cmd_parts[1]
                            # Add -i parameter before the last argument (assumed to be output file)
                            ffmpeg_parts = ffmpeg_part.split()
                            ffmpeg_parts.insert(-1, "-i")
                            ffmpeg_parts.insert(-1, "input.mp4")
                            cmd[2] = f"{ulimit_part} && {' '.join(ffmpeg_parts)}"
                        else:
                            # No ulimit, just the ffmpeg command
                            ffmpeg_parts = cmd[2].split()
                            ffmpeg_parts.insert(-1, "-i")
                            ffmpeg_parts.insert(-1, "input.mp4")
                            cmd[2] = " ".join(ffmpeg_parts)
                        LOGGER.debug(f"Modified bash wrapped command: {cmd}")
                        # For bash wrapped commands, we need to extract the input file differently
                        # We'll look for the -i parameter in the string
                        input_file = "input.mp4"  # Default value
                        index = -1  # Special marker for bash wrapped commands
                    else:
                        # The command already has -i parameter, extract the input file
                        # This is a bit tricky since it's a string
                        cmd_str = cmd[2]
                        parts = cmd_str.split()
                        for i, part in enumerate(parts):
                            if part == "-i" and i + 1 < len(parts):
                                input_file = parts[i + 1]
                                index = (
                                    -1
                                )  # Special marker for bash wrapped commands
                                break
                        else:
                            # Couldn't find -i parameter, use default
                            input_file = "input.mp4"
                            index = -1  # Special marker for bash wrapped commands
                # Normal case: command is a list of arguments
                elif "-i" in cmd:
                    index = cmd.index("-i")
                    input_file = cmd[index + 1]
                else:
                    # Log the issue and add -i parameter if missing
                    LOGGER.warning(f"FFmpeg command missing -i parameter: {cmd}")
                    # Add default input parameter
                    cmd.extend(["-i", "input.mp4"])
                    index = cmd.index("-i")
                    input_file = cmd[index + 1]
                if input_file.lower().endswith(".video"):
                    ext = "video"
                elif input_file.lower().endswith(".audio"):
                    ext = "audio"
                elif "." not in input_file:
                    ext = "all"
                else:
                    ext = ospath.splitext(input_file)[-1].lower()
                if await aiopath.isfile(dl_path):
                    is_video, is_audio, _ = await get_document_type(dl_path)
                    if (not is_video and not is_audio) or (
                        is_video and ext == "audio"
                    ):
                        break
                    if (is_audio and not is_video and ext == "video") or (
                        ext
                        not in [
                            "all",
                            "audio",
                            "video",
                        ]
                        and not dl_path.strip().lower().endswith(ext)
                    ):
                        break
                    new_folder = ospath.splitext(dl_path)[0]
                    name = ospath.basename(dl_path)
                    try:
                        await makedirs(new_folder, exist_ok=True)
                        file_path = f"{new_folder}/{name}"
                        await move(dl_path, file_path)
                    except FileExistsError:
                        LOGGER.warning(f"Folder already exists: {new_folder}")
                        # Try with a different folder name using timestamp
                        new_folder = f"{ospath.splitext(dl_path)[0]}_{int(time())}"
                        await makedirs(new_folder, exist_ok=True)
                        file_path = f"{new_folder}/{name}"
                        await move(dl_path, file_path)
                    if not checked:
                        checked = True
                        async with task_dict_lock:
                            task_dict[self.mid] = FFmpegStatus(
                                self,
                                ffmpeg,
                                gid,
                                "FFmpeg",
                            )
                        self.progress = False
                        await cpu_eater_lock.acquire()
                        self.progress = True
                    LOGGER.info(f"Running ffmpeg cmd for: {file_path}")
                    # Special case for bash-wrapped commands
                    if index == -1:
                        # This is a bash-wrapped command, we need to update the input file in the string
                        if len(cmd) >= 3 and cmd[0] == "bash" and cmd[1] == "-c":
                            cmd_str = cmd[2]
                            # Replace the input file in the command string
                            cmd_parts = cmd_str.split(" && ", 1)
                            if len(cmd_parts) > 1:
                                # There's a ulimit command before the actual ffmpeg command
                                ulimit_part = cmd_parts[0]
                                ffmpeg_part = cmd_parts[1]
                                # Replace the input file after -i
                                parts = ffmpeg_part.split()
                                for i, part in enumerate(parts):
                                    if part == "-i" and i + 1 < len(parts):
                                        parts[i + 1] = file_path
                                        break
                                cmd[2] = f"{ulimit_part} && {' '.join(parts)}"
                            else:
                                # No ulimit, just the ffmpeg command
                                parts = cmd_str.split()
                                for i, part in enumerate(parts):
                                    if part == "-i" and i + 1 < len(parts):
                                        parts[i + 1] = file_path
                                        break
                                cmd[2] = " ".join(parts)
                            LOGGER.debug(
                                f"Updated bash wrapped command with new input file: {cmd}"
                            )
                    else:
                        # Normal case: command is a list of arguments
                        cmd[index + 1] = file_path
                    self.subsize = self.size
                    # Execute the command
                    res = await ffmpeg.ffmpeg_cmds(cmd, file_path)

                    # Resource manager removed

                    if res:
                        if delete_files:
                            await remove(file_path)
                            if len(await listdir(new_folder)) == 1:
                                folder = new_folder.rsplit("/", 1)[0]
                                self.name = ospath.basename(res[0])
                                if self.name.startswith(
                                    "ffmpeg"
                                ) or self.name.startswith(
                                    "xtra"
                                ):  # Check for both ffmpeg and xtra
                                    self.name = self.name.split(".", 1)[-1]
                                dl_path = ospath.join(folder, self.name)
                                await move(res[0], dl_path)
                                await rmtree(new_folder)
                            else:
                                dl_path = new_folder
                                self.name = new_folder.rsplit("/", 1)[-1]
                        else:
                            dl_path = new_folder
                            self.name = new_folder.rsplit("/", 1)[-1]
                    else:
                        await move(file_path, dl_path)
                        await rmtree(new_folder)
                else:
                    for dirpath, _, files in await sync_to_async(
                        walk,
                        dl_path,
                        topdown=False,
                    ):
                        for file_ in files:
                            var_cmd = cmd.copy()
                            if self.is_cancelled:
                                return False
                            f_path = ospath.join(dirpath, file_)
                            is_video, is_audio, _ = await get_document_type(f_path)
                            if (not is_video and not is_audio) or (
                                is_video and ext == "audio"
                            ):
                                continue
                            if (is_audio and not is_video and ext == "video") or (
                                ext
                                not in [
                                    "all",
                                    "audio",
                                    "video",
                                ]
                                and not f_path.strip().lower().endswith(ext)
                            ):
                                continue
                            self.proceed_count += 1

                            # Make sure -del flag is not passed to ffmpeg
                            if "-del" in var_cmd:
                                var_cmd.remove("-del")
                                # delete_files is already set from the main command

                            # Special case: if the command starts with 'bash' and '-c', it's a wrapped command
                            # Special case for wrapped commands
                            if (
                                len(var_cmd) >= 3
                                and var_cmd[0] == "bash"
                                and var_cmd[1] == "-c"
                            ):
                                LOGGER.debug(
                                    f"Detected bash -c wrapped command: {var_cmd}"
                                )
                                # The actual command is in the third element as a string
                                # We need to check if it contains '-i' anywhere in the string
                                if "-i" not in var_cmd[2]:
                                    LOGGER.warning(
                                        f"FFmpeg command missing -i parameter in bash wrapper: {var_cmd}"
                                    )
                                    # Insert the -i parameter before the output file (which is typically at the end)
                                    # This is a bit tricky since it's a string, so we'll need to modify the string
                                    cmd_parts = var_cmd[2].split(" && ", 1)
                                    if len(cmd_parts) > 1:
                                        # There's a ulimit command before the actual ffmpeg command
                                        ulimit_part = cmd_parts[0]
                                        ffmpeg_part = cmd_parts[1]
                                        # Add -i parameter before the last argument (assumed to be output file)
                                        ffmpeg_parts = ffmpeg_part.split()
                                        ffmpeg_parts.insert(-1, "-i")
                                        ffmpeg_parts.insert(-1, f_path)
                                        var_cmd[2] = (
                                            f"{ulimit_part} && {' '.join(ffmpeg_parts)}"
                                        )
                                    else:
                                        # No ulimit, just the ffmpeg command
                                        ffmpeg_parts = var_cmd[2].split()
                                        ffmpeg_parts.insert(-1, "-i")
                                        ffmpeg_parts.insert(-1, f_path)
                                        var_cmd[2] = " ".join(ffmpeg_parts)
                                    LOGGER.debug(
                                        f"Modified bash wrapped command: {var_cmd}"
                                    )
                                    # For bash wrapped commands, we need to extract the input file differently
                                    index = (
                                        -1
                                    )  # Special marker for bash wrapped commands
                                else:
                                    # The command already has -i parameter, update the input file
                                    # This is a bit tricky since it's a string
                                    cmd_str = var_cmd[2]
                                    cmd_parts = cmd_str.split(" && ", 1)
                                    if len(cmd_parts) > 1:
                                        # There's a ulimit command before the actual ffmpeg command
                                        ulimit_part = cmd_parts[0]
                                        ffmpeg_part = cmd_parts[1]
                                        # Replace the input file after -i
                                        parts = ffmpeg_part.split()
                                        for i, part in enumerate(parts):
                                            if part == "-i" and i + 1 < len(parts):
                                                parts[i + 1] = f_path
                                                break
                                        var_cmd[2] = (
                                            f"{ulimit_part} && {' '.join(parts)}"
                                        )
                                    else:
                                        # No ulimit, just the ffmpeg command
                                        parts = cmd_str.split()
                                        for i, part in enumerate(parts):
                                            if part == "-i" and i + 1 < len(parts):
                                                parts[i + 1] = f_path
                                                break
                                        var_cmd[2] = " ".join(parts)
                                    LOGGER.debug(
                                        f"Updated bash wrapped command with new input file: {var_cmd}"
                                    )
                                    index = (
                                        -1
                                    )  # Special marker for bash wrapped commands
                            # Normal case: command is a list of arguments
                            elif "-i" in var_cmd:
                                var_cmd[index + 1] = f_path
                            else:
                                # Log the issue and add -i parameter if missing
                                LOGGER.warning(
                                    f"FFmpeg command missing -i parameter: {var_cmd}"
                                )
                                # Add default input parameter with the current file
                                var_cmd.extend(["-i", f_path])
                                # Update index for future reference
                                index = var_cmd.index("-i")
                            if not checked:
                                checked = True
                                async with task_dict_lock:
                                    task_dict[self.mid] = FFmpegStatus(
                                        self,
                                        ffmpeg,
                                        gid,
                                        "FFmpeg",
                                    )
                                self.progress = False
                                await cpu_eater_lock.acquire()
                                self.progress = True

                            # Resource manager removed

                            LOGGER.info(f"Running ffmpeg cmd for: {f_path}")
                            self.subsize = await get_path_size(f_path)
                            self.subname = file_
                            # Execute the command
                            res = await ffmpeg.ffmpeg_cmds(var_cmd, f_path)

                            if res and delete_files:
                                await remove(f_path)
                                if len(res) == 1:
                                    file_name = ospath.basename(res[0])
                                    if file_name.startswith(
                                        ("ffmpeg", "xtra")
                                    ):  # Check for both ffmpeg and xtra
                                        newname = file_name.split(".", 1)[-1]
                                        newres = ospath.join(dirpath, newname)
                                        await move(res[0], newres)
        finally:
            if checked:
                cpu_eater_lock.release()
        return dl_path

    async def substitute(self, dl_path):
        def perform_substitution(name, substitutions):
            for substitution in substitutions:
                sen = False
                pattern = substitution[0]
                if len(substitution) > 1:
                    if len(substitution) > 2:
                        sen = substitution[2] == "s"
                        res = substitution[1]
                    elif len(substitution[1]) == 0:
                        res = " "
                    else:
                        res = substitution[1]
                else:
                    res = ""
                try:
                    name = sub(
                        rf"{pattern}",
                        res,
                        name,
                        flags=IGNORECASE if sen else 0,
                    )
                except Exception as e:
                    LOGGER.debug(
                        f"Substitute Error: pattern: {pattern} res: {res}. Error: {e}",
                    )
                    return False
                if len(name.encode()) > 255:
                    LOGGER.error(f"Substitute: {name} is too long")
                    return False
            return name

        if self.is_file:
            up_dir, name = dl_path.rsplit("/", 1)
            new_name = perform_substitution(name, self.name_sub)
            if not new_name:
                return dl_path
            new_path = ospath.join(up_dir, new_name)
            with contextlib.suppress(Exception):
                await move(dl_path, new_path)
            return new_path
        for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
            for file_ in files:
                f_path = ospath.join(dirpath, file_)
                new_name = perform_substitution(file_, self.name_sub)
                if not new_name:
                    continue
                with contextlib.suppress(Exception):
                    await move(f_path, ospath.join(dirpath, new_name))
        return dl_path

    async def remove_www_prefix(self, dl_path):
        def clean_filename(name):
            return sub(
                r"^www\.[^ ]+\s*-\s*|\s*^www\.[^ ]+\s*",
                "",
                name,
                flags=IGNORECASE,
            ).lstrip()

        if self.is_file:
            up_dir, name = dl_path.rsplit("/", 1)
            new_name = clean_filename(name)
            if new_name == name:
                return dl_path
            new_path = ospath.join(up_dir, new_name)
            with contextlib.suppress(Exception):
                await move(dl_path, new_path)
            return new_path

        for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
            for file_ in files:
                f_path = ospath.join(dirpath, file_)
                new_name = clean_filename(file_)
                if new_name == file_:
                    continue
                with contextlib.suppress(Exception):
                    await move(f_path, ospath.join(dirpath, new_name))

        return dl_path

    async def generate_screenshots(self, dl_path):
        ss_nb = int(self.screen_shots) if isinstance(self.screen_shots, str) else 10
        if self.is_file:
            if (await get_document_type(dl_path))[0]:
                LOGGER.info(f"Creating Screenshot for: {dl_path}")
                res = await take_ss(dl_path, ss_nb)
                if res:
                    new_folder = ospath.splitext(dl_path)[0]
                    name = ospath.basename(dl_path)
                    try:
                        await makedirs(new_folder, exist_ok=True)
                        await gather(
                            move(dl_path, f"{new_folder}/{name}"),
                            move(res, new_folder),
                        )
                    except FileExistsError:
                        LOGGER.warning(f"Folder already exists: {new_folder}")
                        # Try with a different folder name using timestamp
                        new_folder = f"{ospath.splitext(dl_path)[0]}_{int(time())}"
                        await makedirs(new_folder, exist_ok=True)
                        await gather(
                            move(dl_path, f"{new_folder}/{name}"),
                            move(res, new_folder),
                        )
                    return new_folder
        else:
            LOGGER.info(f"Creating Screenshot for: {dl_path}")
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    if (await get_document_type(f_path))[0]:
                        await take_ss(f_path, ss_nb)
        return dl_path

    async def convert_media(self, dl_path, gid):
        # Check if convert is enabled in user settings or bot settings
        convert_enabled = False
        delete_original = False

        # Initialize flags for settings-based conversion detection
        self.is_settings_based_video_conversion = False
        self.is_settings_based_audio_conversion = False
        self.is_settings_based_subtitle_conversion = False
        self.is_settings_based_document_conversion = False
        self.is_settings_based_archive_conversion = False

        # Add a global flag to track if this is a settings-based conversion
        # This will be used to force delete_original=True for all settings-based conversions
        self.is_settings_based_conversion = False

        # Check if convert is enabled in user settings
        user_convert_enabled = self.user_dict.get("CONVERT_ENABLED", False)
        # Check if convert is enabled in bot settings
        owner_convert_enabled = (
            Config.CONVERT_ENABLED if hasattr(Config, "CONVERT_ENABLED") else False
        )

        # Determine if convert is enabled based on priority
        if "CONVERT_ENABLED" in self.user_dict:
            # User has explicitly set convert enabled/disabled
            convert_enabled = user_convert_enabled
        else:
            # User hasn't set convert enabled/disabled - use owner settings
            convert_enabled = owner_convert_enabled

        # Check if video convert is enabled
        user_video_enabled = self.user_dict.get("CONVERT_VIDEO_ENABLED", False)
        owner_video_enabled = (
            Config.CONVERT_VIDEO_ENABLED
            if hasattr(Config, "CONVERT_VIDEO_ENABLED")
            else False
        )

        # Check if audio convert is enabled
        user_audio_enabled = self.user_dict.get("CONVERT_AUDIO_ENABLED", False)
        owner_audio_enabled = (
            Config.CONVERT_AUDIO_ENABLED
            if hasattr(Config, "CONVERT_AUDIO_ENABLED")
            else False
        )

        # Log the convert settings
        LOGGER.debug(
            f"Convert settings - User: {user_convert_enabled}, Owner: {owner_convert_enabled}, Enabled: {convert_enabled}"
        )
        LOGGER.debug(
            f"Video convert settings - User: {user_video_enabled}, Owner: {owner_video_enabled}"
        )
        LOGGER.debug(
            f"Audio convert settings - User: {user_audio_enabled}, Owner: {owner_audio_enabled}"
        )

        fvext = []
        if self.convert_video:
            # Clean up the convert_video parameter by removing the -del flag if present
            clean_convert_video = self.convert_video.replace("-del", "").strip()
            vdata = clean_convert_video.split()
            vext = vdata[0].lower()
            if len(vdata) > 2:
                if "+" in vdata[1]:
                    vstatus = "+"
                elif "-" in vdata[1]:
                    vstatus = "-"
                else:
                    vstatus = ""
                fvext.extend(f".{ext.lower()}" for ext in vdata[2:])
            else:
                vstatus = ""

            # Check if -del flag is present in convert_video
            if "-del" in self.convert_video:
                delete_original = True
                LOGGER.warning("Flag-based video conversion with -del flag detected")
                LOGGER.warning(
                    "Setting delete_original=True for flag-based video conversion"
                )
            else:
                # For flag-based conversion without -del, we'll still delete the original
                # This ensures consistent behavior with settings-based conversion
                delete_original = True
                LOGGER.warning(
                    "Flag-based video conversion without -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for all video conversions for consistency"
                )
        # If convert_video is not set via command line, check if it's enabled in settings
        elif convert_enabled:
            # Determine if video convert is enabled based on priority
            video_enabled = False
            if "CONVERT_VIDEO_ENABLED" in self.user_dict:
                # User has explicitly set video convert enabled/disabled
                video_enabled = user_video_enabled
            else:
                # User hasn't set video convert enabled/disabled - use owner settings
                video_enabled = owner_video_enabled

            if video_enabled:
                # Get video format from settings
                user_video_format = self.user_dict.get("CONVERT_VIDEO_FORMAT", "")
                owner_video_format = (
                    Config.CONVERT_VIDEO_FORMAT
                    if hasattr(Config, "CONVERT_VIDEO_FORMAT")
                    else "mp4"
                )

                # Check if format is set to "None" (case-insensitive)
                if user_video_format and (user_video_format.lower() == "none"):
                    LOGGER.debug(
                        "User has set video format to None, skipping video conversion"
                    )
                    vext = ""
                elif (
                    not user_video_format
                    and owner_video_format
                    and (owner_video_format.lower() == "none")
                ):
                    LOGGER.debug(
                        "Owner has set video format to None, skipping video conversion"
                    )
                    vext = ""
                else:
                    # Use user format if set, otherwise use owner format
                    vext = user_video_format or owner_video_format
                    vstatus = ""
                    LOGGER.debug(f"Using video format from settings: {vext}")

                    # Get video codec from settings
                    user_video_codec = self.user_dict.get("CONVERT_VIDEO_CODEC", "")
                    owner_video_codec = (
                        Config.CONVERT_VIDEO_CODEC
                        if hasattr(Config, "CONVERT_VIDEO_CODEC")
                        else "libx264"
                    )

                    # Determine which codec to use based on priority
                    if user_video_codec and user_video_codec.lower() != "none":
                        self.convert_video_codec = user_video_codec
                        LOGGER.debug(
                            f"Using user's video codec: {self.convert_video_codec}"
                        )
                    elif owner_video_codec and owner_video_codec.lower() != "none":
                        self.convert_video_codec = owner_video_codec
                        LOGGER.debug(
                            f"Using owner's video codec: {self.convert_video_codec}"
                        )
                    else:
                        self.convert_video_codec = None
                        LOGGER.debug("No video codec specified, using default")

                    # Get video CRF from settings
                    user_video_crf = self.user_dict.get("CONVERT_VIDEO_CRF", 0)
                    owner_video_crf = (
                        Config.CONVERT_VIDEO_CRF
                        if hasattr(Config, "CONVERT_VIDEO_CRF")
                        else 23
                    )

                    # Determine which CRF to use based on priority
                    if user_video_crf and user_video_crf != 0:
                        self.convert_video_crf = user_video_crf
                        LOGGER.debug(
                            f"Using user's video CRF: {self.convert_video_crf}"
                        )
                    elif owner_video_crf and owner_video_crf != 0:
                        self.convert_video_crf = owner_video_crf
                        LOGGER.debug(
                            f"Using owner's video CRF: {self.convert_video_crf}"
                        )
                    else:
                        self.convert_video_crf = None
                        LOGGER.debug("No video CRF specified, using default")

                    # Get video preset from settings
                    user_video_preset = self.user_dict.get(
                        "CONVERT_VIDEO_PRESET", ""
                    )
                    owner_video_preset = (
                        Config.CONVERT_VIDEO_PRESET
                        if hasattr(Config, "CONVERT_VIDEO_PRESET")
                        else "medium"
                    )

                    # Determine which preset to use based on priority
                    if user_video_preset and user_video_preset.lower() != "none":
                        self.convert_video_preset = user_video_preset
                        LOGGER.debug(
                            f"Using user's video preset: {self.convert_video_preset}"
                        )
                    elif owner_video_preset and owner_video_preset.lower() != "none":
                        self.convert_video_preset = owner_video_preset
                        LOGGER.debug(
                            f"Using owner's video preset: {self.convert_video_preset}"
                        )
                    else:
                        self.convert_video_preset = None
                        LOGGER.debug("No video preset specified, using default")

                    # Get video maintain quality setting
                    user_video_maintain_quality = self.user_dict.get(
                        "CONVERT_VIDEO_MAINTAIN_QUALITY", False
                    )
                    owner_video_maintain_quality = (
                        Config.CONVERT_VIDEO_MAINTAIN_QUALITY
                        if hasattr(Config, "CONVERT_VIDEO_MAINTAIN_QUALITY")
                        else False
                    )

                    # Determine which maintain quality setting to use based on priority
                    if "CONVERT_VIDEO_MAINTAIN_QUALITY" in self.user_dict:
                        self.convert_video_maintain_quality = (
                            user_video_maintain_quality
                        )
                        LOGGER.debug(
                            f"Using user's video maintain quality: {self.convert_video_maintain_quality}"
                        )
                    else:
                        self.convert_video_maintain_quality = (
                            owner_video_maintain_quality
                        )
                        LOGGER.debug(
                            f"Using owner's video maintain quality: {self.convert_video_maintain_quality}"
                        )

                    # Set delete_original to True when convert is enabled through settings
                    # and a valid format is specified
                    if vext:
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.info(
                            "Settings-based video conversion will delete original files after conversion"
                        )
                        # Add more detailed logging
                        LOGGER.debug(
                            f"Video conversion settings: Format={vext}, Delete Original=True"
                        )
                        # Add a warning log to make it more visible
                        LOGGER.warning(
                            f"IMPORTANT: Setting delete_original=True for video conversion with format {vext}"
                        )
                        # Add a flag to indicate this is a settings-based conversion
                        self.is_settings_based_video_conversion = True
                        self.is_settings_based_conversion = True
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.warning(
                            f"Set is_settings_based_video_conversion flag to {self.is_settings_based_video_conversion}"
                        )
                        LOGGER.warning(
                            f"Set global is_settings_based_conversion flag to: {self.is_settings_based_conversion}"
                        )
                        LOGGER.warning(
                            "IMPORTANT: Forcing delete_original=True for settings-based video conversion"
                        )
            else:
                vext = ""
                vstatus = ""
        else:
            vext = ""
            vstatus = ""

        faext = []
        if self.convert_audio:
            # Clean up the convert_audio parameter by removing the -del flag if present
            clean_convert_audio = self.convert_audio.replace("-del", "").strip()
            adata = clean_convert_audio.split()
            aext = adata[0].lower()
            if len(adata) > 2:
                if "+" in adata[1]:
                    astatus = "+"
                elif "-" in adata[1]:
                    astatus = "-"
                else:
                    astatus = ""
                faext.extend(f".{ext.lower()}" for ext in adata[2:])
            else:
                astatus = ""

            # Check if -del flag is present in convert_audio
            if "-del" in self.convert_audio:
                delete_original = True
                LOGGER.warning("Flag-based audio conversion with -del flag detected")
                LOGGER.warning(
                    "Setting delete_original=True for flag-based audio conversion"
                )
            else:
                # For flag-based conversion without -del, we'll still delete the original
                # This ensures consistent behavior with settings-based conversion
                delete_original = True
                LOGGER.warning(
                    "Flag-based audio conversion without -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for all audio conversions for consistency"
                )
        # If convert_audio is not set via command line, check if it's enabled in settings
        elif convert_enabled:
            # Determine if audio convert is enabled based on priority
            audio_enabled = False
            if "CONVERT_AUDIO_ENABLED" in self.user_dict:
                # User has explicitly set audio convert enabled/disabled
                audio_enabled = user_audio_enabled
            else:
                # User hasn't set audio convert enabled/disabled - use owner settings
                audio_enabled = owner_audio_enabled

            if audio_enabled:
                # Get audio format from settings
                user_audio_format = self.user_dict.get("CONVERT_AUDIO_FORMAT", "")
                owner_audio_format = (
                    Config.CONVERT_AUDIO_FORMAT
                    if hasattr(Config, "CONVERT_AUDIO_FORMAT")
                    else "mp3"
                )

                # Check if format is set to "None" (case-insensitive)
                if user_audio_format and (user_audio_format.lower() == "none"):
                    LOGGER.debug(
                        "User has set audio format to None, skipping audio conversion"
                    )
                    aext = ""
                elif (
                    not user_audio_format
                    and owner_audio_format
                    and (owner_audio_format.lower() == "none")
                ):
                    LOGGER.debug(
                        "Owner has set audio format to None, skipping audio conversion"
                    )
                    aext = ""
                else:
                    # Use user format if set, otherwise use owner format
                    aext = user_audio_format or owner_audio_format
                    astatus = ""
                    LOGGER.debug(f"Using audio format from settings: {aext}")

                    # Get audio codec from settings
                    user_audio_codec = self.user_dict.get("CONVERT_AUDIO_CODEC", "")
                    owner_audio_codec = (
                        Config.CONVERT_AUDIO_CODEC
                        if hasattr(Config, "CONVERT_AUDIO_CODEC")
                        else "libmp3lame"
                    )

                    # Determine which codec to use based on priority
                    if user_audio_codec and user_audio_codec.lower() != "none":
                        self.convert_audio_codec = user_audio_codec
                        LOGGER.debug(
                            f"Using user's audio codec: {self.convert_audio_codec}"
                        )
                    elif owner_audio_codec and owner_audio_codec.lower() != "none":
                        self.convert_audio_codec = owner_audio_codec
                        LOGGER.debug(
                            f"Using owner's audio codec: {self.convert_audio_codec}"
                        )
                    else:
                        self.convert_audio_codec = None
                        LOGGER.debug("No audio codec specified, using default")

                    # Get audio bitrate from settings
                    user_audio_bitrate = self.user_dict.get(
                        "CONVERT_AUDIO_BITRATE", ""
                    )
                    owner_audio_bitrate = (
                        Config.CONVERT_AUDIO_BITRATE
                        if hasattr(Config, "CONVERT_AUDIO_BITRATE")
                        else "192k"
                    )

                    # Determine which bitrate to use based on priority
                    if user_audio_bitrate and user_audio_bitrate.lower() != "none":
                        self.convert_audio_bitrate = user_audio_bitrate
                        LOGGER.debug(
                            f"Using user's audio bitrate: {self.convert_audio_bitrate}"
                        )
                    elif (
                        owner_audio_bitrate and owner_audio_bitrate.lower() != "none"
                    ):
                        self.convert_audio_bitrate = owner_audio_bitrate
                        LOGGER.debug(
                            f"Using owner's audio bitrate: {self.convert_audio_bitrate}"
                        )
                    else:
                        self.convert_audio_bitrate = None
                        LOGGER.debug("No audio bitrate specified, using default")

                    # Get audio channels from settings
                    user_audio_channels = self.user_dict.get(
                        "CONVERT_AUDIO_CHANNELS", 0
                    )
                    owner_audio_channels = (
                        Config.CONVERT_AUDIO_CHANNELS
                        if hasattr(Config, "CONVERT_AUDIO_CHANNELS")
                        else 2
                    )

                    # Determine which channels to use based on priority
                    if user_audio_channels and user_audio_channels != 0:
                        self.convert_audio_channels = user_audio_channels
                        LOGGER.debug(
                            f"Using user's audio channels: {self.convert_audio_channels}"
                        )
                    elif owner_audio_channels and owner_audio_channels != 0:
                        self.convert_audio_channels = owner_audio_channels
                        LOGGER.debug(
                            f"Using owner's audio channels: {self.convert_audio_channels}"
                        )
                    else:
                        self.convert_audio_channels = None
                        LOGGER.debug("No audio channels specified, using default")

                    # Get audio sampling from settings
                    user_audio_sampling = self.user_dict.get(
                        "CONVERT_AUDIO_SAMPLING", 0
                    )
                    owner_audio_sampling = (
                        Config.CONVERT_AUDIO_SAMPLING
                        if hasattr(Config, "CONVERT_AUDIO_SAMPLING")
                        else 44100
                    )

                    # Determine which sampling to use based on priority
                    if user_audio_sampling and user_audio_sampling != 0:
                        self.convert_audio_sampling = user_audio_sampling
                        LOGGER.debug(
                            f"Using user's audio sampling: {self.convert_audio_sampling}"
                        )
                    elif owner_audio_sampling and owner_audio_sampling != 0:
                        self.convert_audio_sampling = owner_audio_sampling
                        LOGGER.debug(
                            f"Using owner's audio sampling: {self.convert_audio_sampling}"
                        )
                    else:
                        self.convert_audio_sampling = None
                        LOGGER.debug("No audio sampling specified, using default")

                    # Get audio volume from settings
                    user_audio_volume = self.user_dict.get(
                        "CONVERT_AUDIO_VOLUME", 0.0
                    )
                    owner_audio_volume = (
                        Config.CONVERT_AUDIO_VOLUME
                        if hasattr(Config, "CONVERT_AUDIO_VOLUME")
                        else 1.0
                    )

                    # Determine which volume to use based on priority
                    if user_audio_volume and user_audio_volume != 0.0:
                        self.convert_audio_volume = user_audio_volume
                        LOGGER.debug(
                            f"Using user's audio volume: {self.convert_audio_volume}"
                        )
                    elif owner_audio_volume and owner_audio_volume != 0.0:
                        self.convert_audio_volume = owner_audio_volume
                        LOGGER.debug(
                            f"Using owner's audio volume: {self.convert_audio_volume}"
                        )
                    else:
                        self.convert_audio_volume = None
                        LOGGER.debug("No audio volume specified, using default")

                    # Set delete_original to True when convert is enabled through settings
                    # and a valid format is specified
                    if aext:
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.info(
                            "Settings-based audio conversion will delete original files after conversion"
                        )
                        # Add more detailed logging
                        LOGGER.debug(
                            f"Audio conversion settings: Format={aext}, Delete Original=True"
                        )
                        # Add a warning log to make it more visible
                        LOGGER.warning(
                            f"IMPORTANT: Setting delete_original=True for audio conversion with format {aext}"
                        )
                        # Add a flag to indicate this is a settings-based conversion
                        self.is_settings_based_audio_conversion = True
                        self.is_settings_based_conversion = True
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.warning(
                            f"Set is_settings_based_audio_conversion flag to {self.is_settings_based_audio_conversion}"
                        )
                        LOGGER.warning(
                            f"Set global is_settings_based_conversion flag to: {self.is_settings_based_conversion}"
                        )
                        LOGGER.warning(
                            "IMPORTANT: Forcing delete_original=True for settings-based audio conversion"
                        )
            else:
                aext = ""
                astatus = ""
        else:
            aext = ""
            astatus = ""

        # Check for subtitle, document, and archive convert commands
        sext = ""
        sstatus = ""
        fsext = []
        dext = ""
        dstatus = ""
        fdext = []
        rext = ""
        rstatus = ""
        frext = []

        # Handle subtitle convert command
        if hasattr(self, "convert_subtitle") and self.convert_subtitle:
            # Clean up the convert_subtitle parameter by removing the -del flag if present
            clean_convert_subtitle = self.convert_subtitle.replace(
                "-del", ""
            ).strip()
            sdata = clean_convert_subtitle.split()
            sext = sdata[0].lower()
            if len(sdata) > 2:
                if "+" in sdata[1]:
                    sstatus = "+"
                elif "-" in sdata[1]:
                    sstatus = "-"
                else:
                    sstatus = ""
                fsext.extend(f".{ext.lower()}" for ext in sdata[2:])
            else:
                sstatus = ""

            # Check if -del flag is present in convert_subtitle
            if "-del" in self.convert_subtitle:
                delete_original = True
                LOGGER.warning(
                    "Flag-based subtitle conversion with -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for flag-based subtitle conversion"
                )
            else:
                # For flag-based conversion without -del, we'll still delete the original
                # This ensures consistent behavior with settings-based conversion
                delete_original = True
                LOGGER.warning(
                    "Flag-based subtitle conversion without -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for all subtitle conversions for consistency"
                )
        # If convert_subtitle is not set via command line, check if it's enabled in settings
        elif convert_enabled:
            # Determine if subtitle convert is enabled based on priority
            subtitle_enabled = False
            if "CONVERT_SUBTITLE_ENABLED" in self.user_dict:
                # User has explicitly set subtitle convert enabled/disabled
                subtitle_enabled = self.user_dict.get(
                    "CONVERT_SUBTITLE_ENABLED", False
                )
            else:
                # User hasn't set subtitle convert enabled/disabled - use owner settings
                subtitle_enabled = (
                    Config.CONVERT_SUBTITLE_ENABLED
                    if hasattr(Config, "CONVERT_SUBTITLE_ENABLED")
                    else False
                )

            if subtitle_enabled:
                # Get subtitle format from settings
                user_subtitle_format = self.user_dict.get(
                    "CONVERT_SUBTITLE_FORMAT", ""
                )
                owner_subtitle_format = (
                    Config.CONVERT_SUBTITLE_FORMAT
                    if hasattr(Config, "CONVERT_SUBTITLE_FORMAT")
                    else "srt"
                )

                # Check if format is set to "None" (case-insensitive)
                if user_subtitle_format and (user_subtitle_format.lower() == "none"):
                    LOGGER.debug(
                        "User has set subtitle format to None, skipping subtitle conversion"
                    )
                    sext = ""
                elif (
                    not user_subtitle_format
                    and owner_subtitle_format
                    and (owner_subtitle_format.lower() == "none")
                ):
                    LOGGER.debug(
                        "Owner has set subtitle format to None, skipping subtitle conversion"
                    )
                    sext = ""
                else:
                    # Use user format if set, otherwise use owner format
                    sext = user_subtitle_format or owner_subtitle_format
                    sstatus = ""
                    LOGGER.debug(f"Using subtitle format from settings: {sext}")

                    # Set delete_original to True when convert is enabled through settings
                    # and a valid format is specified
                    if sext:
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.info(
                            "Settings-based subtitle conversion will delete original files after conversion"
                        )
                        # Add more detailed logging
                        LOGGER.debug(
                            f"Subtitle conversion settings: Format={sext}, Delete Original=True"
                        )
                        # Add a warning log to make it more visible
                        LOGGER.warning(
                            f"IMPORTANT: Setting delete_original=True for subtitle conversion with format {sext}"
                        )
                        # Add a flag to indicate this is a settings-based conversion
                        self.is_settings_based_subtitle_conversion = True
                        self.is_settings_based_conversion = True
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.warning(
                            f"Set is_settings_based_subtitle_conversion flag to {self.is_settings_based_subtitle_conversion}"
                        )
                        LOGGER.warning(
                            f"Set global is_settings_based_conversion flag to: {self.is_settings_based_conversion}"
                        )
                        LOGGER.warning(
                            "IMPORTANT: Forcing delete_original=True for settings-based subtitle conversion"
                        )
            else:
                sext = ""
                sstatus = ""
        else:
            sext = ""
            sstatus = ""

        # Handle document convert command
        if hasattr(self, "convert_document") and self.convert_document:
            # Clean up the convert_document parameter by removing the -del flag if present
            clean_convert_document = self.convert_document.replace(
                "-del", ""
            ).strip()
            ddata = clean_convert_document.split()
            dext = ddata[0].lower()
            if len(ddata) > 2:
                if "+" in ddata[1]:
                    dstatus = "+"
                elif "-" in ddata[1]:
                    dstatus = "-"
                else:
                    dstatus = ""
                fdext.extend(f".{ext.lower()}" for ext in ddata[2:])
            else:
                dstatus = ""

            # Check if -del flag is present in convert_document
            if "-del" in self.convert_document:
                delete_original = True
                LOGGER.warning(
                    "Flag-based document conversion with -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for flag-based document conversion"
                )
            else:
                # For flag-based conversion without -del, we'll still delete the original
                # This ensures consistent behavior with settings-based conversion
                delete_original = True
                LOGGER.warning(
                    "Flag-based document conversion without -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for all document conversions for consistency"
                )
        # If convert_document is not set via command line, check if it's enabled in settings
        elif convert_enabled:
            # Determine if document convert is enabled based on priority
            document_enabled = False
            if "CONVERT_DOCUMENT_ENABLED" in self.user_dict:
                # User has explicitly set document convert enabled/disabled
                document_enabled = self.user_dict.get(
                    "CONVERT_DOCUMENT_ENABLED", False
                )
            else:
                # User hasn't set document convert enabled/disabled - use owner settings
                document_enabled = (
                    Config.CONVERT_DOCUMENT_ENABLED
                    if hasattr(Config, "CONVERT_DOCUMENT_ENABLED")
                    else False
                )

            if document_enabled:
                # Get document format from settings
                user_document_format = self.user_dict.get(
                    "CONVERT_DOCUMENT_FORMAT", ""
                )
                owner_document_format = (
                    Config.CONVERT_DOCUMENT_FORMAT
                    if hasattr(Config, "CONVERT_DOCUMENT_FORMAT")
                    else "pdf"
                )

                # Check if format is set to "None" (case-insensitive)
                if user_document_format and (user_document_format.lower() == "none"):
                    LOGGER.debug(
                        "User has set document format to None, skipping document conversion"
                    )
                    dext = ""
                elif (
                    not user_document_format
                    and owner_document_format
                    and (owner_document_format.lower() == "none")
                ):
                    LOGGER.debug(
                        "Owner has set document format to None, skipping document conversion"
                    )
                    dext = ""
                else:
                    # Use user format if set, otherwise use owner format
                    dext = user_document_format or owner_document_format
                    dstatus = ""
                    LOGGER.debug(f"Using document format from settings: {dext}")

                    # Set delete_original to True when convert is enabled through settings
                    # and a valid format is specified
                    if dext:
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.info(
                            "Settings-based document conversion will delete original files after conversion"
                        )
                        # Add more detailed logging
                        LOGGER.debug(
                            f"Document conversion settings: Format={dext}, Delete Original=True"
                        )
                        # Add a warning log to make it more visible
                        LOGGER.warning(
                            f"IMPORTANT: Setting delete_original=True for document conversion with format {dext}"
                        )
                        # Add a flag to indicate this is a settings-based conversion
                        self.is_settings_based_document_conversion = True
                        self.is_settings_based_conversion = True
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.warning(
                            f"Set is_settings_based_document_conversion flag to {self.is_settings_based_document_conversion}"
                        )
                        LOGGER.warning(
                            f"Set global is_settings_based_conversion flag to: {self.is_settings_based_conversion}"
                        )
                        LOGGER.warning(
                            "IMPORTANT: Forcing delete_original=True for settings-based document conversion"
                        )
            else:
                dext = ""
                dstatus = ""
        else:
            dext = ""
            dstatus = ""

        # Handle archive convert command
        if hasattr(self, "convert_archive") and self.convert_archive:
            # Clean up the convert_archive parameter by removing the -del flag if present
            clean_convert_archive = self.convert_archive.replace("-del", "").strip()
            rdata = clean_convert_archive.split()
            rext = rdata[0].lower()
            if len(rdata) > 2:
                if "+" in rdata[1]:
                    rstatus = "+"
                elif "-" in rdata[1]:
                    rstatus = "-"
                else:
                    rstatus = ""
                frext.extend(f".{ext.lower()}" for ext in rdata[2:])
            else:
                rstatus = ""

            # Check if -del flag is present in convert_archive
            if "-del" in self.convert_archive:
                delete_original = True
                LOGGER.warning(
                    "Flag-based archive conversion with -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for flag-based archive conversion"
                )
            else:
                # For flag-based conversion without -del, we'll still delete the original
                # This ensures consistent behavior with settings-based conversion
                delete_original = True
                LOGGER.warning(
                    "Flag-based archive conversion without -del flag detected"
                )
                LOGGER.warning(
                    "Setting delete_original=True for all archive conversions for consistency"
                )
        # If convert_archive is not set via command line, check if it's enabled in settings
        elif convert_enabled:
            # Determine if archive convert is enabled based on priority
            archive_enabled = False
            if "CONVERT_ARCHIVE_ENABLED" in self.user_dict:
                # User has explicitly set archive convert enabled/disabled
                archive_enabled = self.user_dict.get(
                    "CONVERT_ARCHIVE_ENABLED", False
                )
            else:
                # User hasn't set archive convert enabled/disabled - use owner settings
                archive_enabled = (
                    Config.CONVERT_ARCHIVE_ENABLED
                    if hasattr(Config, "CONVERT_ARCHIVE_ENABLED")
                    else False
                )

            if archive_enabled:
                # Get archive format from settings
                user_archive_format = self.user_dict.get(
                    "CONVERT_ARCHIVE_FORMAT", ""
                )
                owner_archive_format = (
                    Config.CONVERT_ARCHIVE_FORMAT
                    if hasattr(Config, "CONVERT_ARCHIVE_FORMAT")
                    else "zip"
                )

                # Check if format is set to "None" (case-insensitive)
                if user_archive_format and (user_archive_format.lower() == "none"):
                    LOGGER.debug(
                        "User has set archive format to None, skipping archive conversion"
                    )
                    rext = ""
                elif (
                    not user_archive_format
                    and owner_archive_format
                    and (owner_archive_format.lower() == "none")
                ):
                    LOGGER.debug(
                        "Owner has set archive format to None, skipping archive conversion"
                    )
                    rext = ""
                else:
                    # Use user format if set, otherwise use owner format
                    rext = user_archive_format or owner_archive_format
                    rstatus = ""
                    LOGGER.debug(f"Using archive format from settings: {rext}")

                    # Set delete_original to True when convert is enabled through settings
                    # and a valid format is specified
                    if rext:
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.info(
                            "Settings-based archive conversion will delete original files after conversion"
                        )
                        # Add more detailed logging
                        LOGGER.debug(
                            f"Archive conversion settings: Format={rext}, Delete Original=True"
                        )
                        # Add a warning log to make it more visible
                        LOGGER.warning(
                            f"IMPORTANT: Setting delete_original=True for archive conversion with format {rext}"
                        )
                        # Add a flag to indicate this is a settings-based conversion
                        self.is_settings_based_archive_conversion = True
                        self.is_settings_based_conversion = True
                        # Force delete_original to True for settings-based conversion
                        delete_original = True
                        LOGGER.warning(
                            f"Set is_settings_based_archive_conversion flag to {self.is_settings_based_archive_conversion}"
                        )
                        LOGGER.warning(
                            f"Set global is_settings_based_conversion flag to: {self.is_settings_based_conversion}"
                        )
                        LOGGER.warning(
                            "IMPORTANT: Forcing delete_original=True for settings-based archive conversion"
                        )
            else:
                rext = ""
                rstatus = ""
        else:
            rext = ""
            rstatus = ""

        self.files_to_proceed = {}
        all_files = []
        if self.is_file:
            all_files.append(dl_path)
        else:
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    all_files.append(f_path)

        for f_path in all_files:
            is_video, is_audio, _ = await get_document_type(f_path)
            file_ext = ospath.splitext(f_path)[1].lower()

            # Define supported file extensions for different media types
            supported_subtitle_exts = [
                ".srt",
                ".ass",
                ".ssa",
                ".vtt",
                ".sub",
                ".sbv",
            ]
            supported_document_exts = [
                ".pdf",
                ".doc",
                ".docx",
                ".ppt",
                ".pptx",
                ".xls",
                ".xlsx",
                ".odt",
                ".ods",
                ".odp",
                ".txt",
                ".rtf",
            ]
            supported_archive_exts = [
                ".zip",
                ".rar",
                ".7z",
                ".tar",
                ".gz",
                ".bz2",
                ".xz",
            ]

            # Skip if vext is empty or "none" (case-insensitive)
            if (
                is_video
                and vext
                and vext.lower() != "none"
                and not f_path.strip().lower().endswith(f".{vext}")
                and (
                    (
                        vstatus == "+"
                        and f_path.strip().lower().endswith(tuple(fvext))
                    )
                    or (
                        vstatus == "-"
                        and not f_path.strip().lower().endswith(tuple(fvext))
                    )
                    or not vstatus
                )
            ):
                self.files_to_proceed[f_path] = "video"

            # Skip if aext is empty or "none" (case-insensitive)
            elif (
                is_audio
                and aext
                and aext.lower() != "none"
                and not is_video
                and not f_path.strip().lower().endswith(f".{aext}")
                and (
                    (
                        astatus == "+"
                        and f_path.strip().lower().endswith(tuple(faext))
                    )
                    or (
                        astatus == "-"
                        and not f_path.strip().lower().endswith(tuple(faext))
                    )
                    or not astatus
                )
            ):
                self.files_to_proceed[f_path] = "audio"

            # Skip if sext is empty or "none" (case-insensitive)
            elif (
                file_ext in supported_subtitle_exts
                and sext
                and sext.lower() != "none"
                and not f_path.strip().lower().endswith(f".{sext}")
                and (
                    (
                        sstatus == "+"
                        and f_path.strip().lower().endswith(tuple(fsext))
                    )
                    or (
                        sstatus == "-"
                        and not f_path.strip().lower().endswith(tuple(fsext))
                    )
                    or not sstatus
                )
            ):
                self.files_to_proceed[f_path] = "subtitle"

            # Skip if dext is empty or "none" (case-insensitive)
            elif (
                file_ext in supported_document_exts
                and dext
                and dext.lower() != "none"
                and not f_path.strip().lower().endswith(f".{dext}")
                and (
                    (
                        dstatus == "+"
                        and f_path.strip().lower().endswith(tuple(fdext))
                    )
                    or (
                        dstatus == "-"
                        and not f_path.strip().lower().endswith(tuple(fdext))
                    )
                    or not dstatus
                )
            ):
                self.files_to_proceed[f_path] = "document"

            # Skip if rext is empty or "none" (case-insensitive)
            elif (
                file_ext in supported_archive_exts
                and rext
                and rext.lower() != "none"
                and not f_path.strip().lower().endswith(f".{rext}")
                and (
                    (
                        rstatus == "+"
                        and f_path.strip().lower().endswith(tuple(frext))
                    )
                    or (
                        rstatus == "-"
                        and not f_path.strip().lower().endswith(tuple(frext))
                    )
                    or not rstatus
                )
            ):
                self.files_to_proceed[f_path] = "archive"
        del all_files

        if self.files_to_proceed:
            ffmpeg = FFMpeg(self)
            async with task_dict_lock:
                task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Convert")
            self.progress = False
            async with cpu_eater_lock:
                self.progress = True
                for f_path, f_type in self.files_to_proceed.items():
                    self.proceed_count += 1
                    LOGGER.info(f"Converting: {f_path}")
                    if self.is_file:
                        self.subsize = self.size
                    else:
                        self.subsize = await get_path_size(f_path)
                        self.subname = ospath.basename(f_path)
                    # delete_original is now set at the beginning of the function
                    # based on command line flags or settings
                    # We'll pass it directly to the conversion methods

                    # First check the global settings-based conversion flag
                    if self.is_settings_based_conversion:
                        delete_original = True

                    # Check if this is a settings-based conversion
                    if f_type == "video":
                        is_settings_based = self.is_settings_based_video_conversion
                        LOGGER.info(f"Converting video: {f_path} to {vext}")

                        # For settings-based conversion, always force delete_original=True
                        if is_settings_based:
                            delete_original = True

                        # Use the final delete_original value for conversion
                        res = await ffmpeg.convert_video(
                            f_path, vext, delete_original=delete_original
                        )

                        # If conversion was successful but original file still exists, delete it
                        if res and delete_original and await aiopath.exists(f_path):
                            try:
                                await remove(f_path)
                            except Exception as e:
                                LOGGER.error(f"Error deleting original file: {e}")
                                # Try again with a different approach
                                try:
                                    import os

                                    os.remove(f_path)
                                except Exception:
                                    # Try one more time with a delay
                                    try:
                                        from asyncio import sleep

                                        await sleep(2)  # Wait 2 seconds
                                        if await aiopath.exists(f_path):
                                            await remove(f_path)
                                    except Exception as e3:
                                        LOGGER.error(
                                            f"All attempts to delete file failed: {e3}"
                                        )
                    else:
                        is_settings_based = self.is_settings_based_audio_conversion
                        LOGGER.info(f"Converting audio: {f_path} to {aext}")

                        # For settings-based conversion, always force delete_original=True
                        if is_settings_based:
                            delete_original = True

                        # Use the final delete_original value for conversion
                        res = await ffmpeg.convert_audio(
                            f_path, aext, delete_original=delete_original
                        )

                        # If conversion was successful but original file still exists, delete it
                        if res and delete_original and await aiopath.exists(f_path):
                            try:
                                await remove(f_path)
                            except Exception as e:
                                LOGGER.error(f"Error deleting original file: {e}")
                                # Try again with a different approach
                                try:
                                    import os

                                    os.remove(f_path)
                                except Exception:
                                    # Try one more time with a delay
                                    try:
                                        from asyncio import sleep

                                        await sleep(2)  # Wait 2 seconds
                                        if await aiopath.exists(f_path):
                                            await remove(f_path)
                                    except Exception as e3:
                                        LOGGER.error(
                                            f"All attempts to delete file failed: {e3}"
                                        )

                    if res:
                        # The original file is now deleted inside the conversion methods if delete_original is True
                        # We don't need to delete it here anymore
                        if self.is_file:
                            return res
        return dl_path

    async def generate_sample_video(self, dl_path, gid):
        data = (
            self.sample_video.split(":")
            if isinstance(self.sample_video, str)
            else ""
        )
        if data:
            sample_duration = int(data[0]) if data[0] else 60
            part_duration = int(data[1]) if len(data) > 1 else 4
        else:
            sample_duration = 60
            part_duration = 4

        self.files_to_proceed = {}
        if self.is_file and (await get_document_type(dl_path))[0]:
            file_ = ospath.basename(dl_path)
            self.files_to_proceed[dl_path] = file_
        else:
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    if (await get_document_type(f_path))[0]:
                        self.files_to_proceed[f_path] = file_
        if self.files_to_proceed:
            ffmpeg = FFMpeg(self)
            async with task_dict_lock:
                task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Sample Video")
            self.progress = False
            async with cpu_eater_lock:
                self.progress = True
                LOGGER.info(f"Creating Sample video: {self.name}")
                for f_path, file_ in self.files_to_proceed.items():
                    self.proceed_count += 1
                    if self.is_file:
                        self.subsize = self.size
                    else:
                        self.subsize = await get_path_size(f_path)
                        self.subname = file_
                    res = await ffmpeg.sample_video(
                        f_path,
                        sample_duration,
                        part_duration,
                    )
                    if res and self.is_file:
                        new_folder = ospath.splitext(f_path)[0]
                        try:
                            await makedirs(new_folder, exist_ok=True)
                            await gather(
                                move(f_path, f"{new_folder}/{file_}"),
                                move(res, f"{new_folder}/SAMPLE.{file_}"),
                            )
                            return new_folder
                        except FileExistsError:
                            LOGGER.warning(f"Folder already exists: {new_folder}")
                            # Try with a different folder name
                            new_folder = (
                                f"{ospath.splitext(f_path)[0]}_{int(time())}"
                            )
                            await makedirs(new_folder, exist_ok=True)
                            await gather(
                                move(f_path, f"{new_folder}/{file_}"),
                                move(res, f"{new_folder}/SAMPLE.{file_}"),
                            )
                            return new_folder
        return dl_path

    async def proceed_compress(self, dl_path, gid):
        # Skip if compression is not enabled
        if not self.compression_enabled:
            LOGGER.info("Compression not applied: compression is not enabled")
            return dl_path

        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        # Check if the path is a directory
        if await aiopath.isdir(dl_path):
            LOGGER.info(f"Compressing directory: {dl_path}")

            # Process all files in the directory recursively
            processed_files = 0
            for dirpath, _, files in await sync_to_async(
                walk, dl_path, topdown=False
            ):
                for file_ in files:
                    if self.is_cancelled:
                        return dl_path

                    f_path = ospath.join(dirpath, file_)
                    # Process this individual file with compression
                    await self._compress_single_file(f_path, gid)
                    processed_files += 1

            LOGGER.info(f"Compressed {processed_files} files in directory")
            return dl_path

        # For single files, use the helper method
        return await self._compress_single_file(dl_path, gid)

    async def _compress_single_file(self, dl_path, gid):
        """Helper method to compress a single file"""
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        # Check if the path is a directory (shouldn't happen when called from proceed_compress)
        if await aiopath.isdir(dl_path):
            return dl_path

        # Check if the file is empty or too small
        file_size = await get_path_size(dl_path)
        if file_size < 1024:  # 1KB
            return dl_path

        # Determine file type and apply appropriate compression
        file_ext = ospath.splitext(dl_path)[1].lower()

        # Get mime type if possible
        try:
            import mimetypes

            mime_type = mimetypes.guess_type(dl_path)[0]
        except Exception:
            mime_type = None

        # Check if file is a subtitle - check extension first, then mime type
        if file_ext.lower() in [
            ".srt",
            ".sub",
            ".sbv",
            ".ass",
            ".ssa",
            ".vtt",
        ] or (mime_type and mime_type.startswith("text/")):
            # Check if subtitle compression is enabled by command-line flag
            if hasattr(self, "compress_subtitle") and self.compress_subtitle:
                LOGGER.info("Compressing subtitle file")
                # Set preset from command-line if specified
                if hasattr(self, "subtitle_preset") and self.subtitle_preset:
                    self.compression_subtitle_preset = self.subtitle_preset
                return await self.compress_subtitle_file(dl_path, gid)
            # Otherwise check if it's enabled in settings
            if self.compression_subtitle_enabled:
                LOGGER.info("Compressing subtitle file")
                return await self.compress_subtitle_file(dl_path, gid)
            return dl_path

        # Check if file is a video
        if (mime_type and mime_type.startswith("video/")) or file_ext in [
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".flv",
            ".webm",
            ".wmv",
            ".m4v",
            ".3gp",
        ]:
            # Check if video compression is enabled by command-line flag
            if hasattr(self, "compress_video") and self.compress_video:
                LOGGER.info("Compressing video file")
                # Set preset from command-line if specified
                if hasattr(self, "video_preset") and self.video_preset:
                    self.compression_video_preset = self.video_preset
                return await self.compress_video_file(dl_path, gid)
            # Otherwise check if it's enabled in settings
            if self.compression_video_enabled:
                LOGGER.info("Compressing video file")
                return await self.compress_video_file(dl_path, gid)
            return dl_path

        # Check if file is an audio
        if (mime_type and mime_type.startswith("audio/")) or file_ext in [
            ".mp3",
            ".wav",
            ".flac",
            ".ogg",
            ".m4a",
            ".aac",
            ".opus",
        ]:
            # Check if audio compression is enabled by command-line flag
            if hasattr(self, "compress_audio") and self.compress_audio:
                LOGGER.info("Compressing audio file")
                # Set preset from command-line if specified
                if hasattr(self, "audio_preset") and self.audio_preset:
                    self.compression_audio_preset = self.audio_preset
                return await self.compress_audio_file(dl_path, gid)
            # Otherwise check if it's enabled in settings
            if self.compression_audio_enabled:
                LOGGER.info("Compressing audio file")
                return await self.compress_audio_file(dl_path, gid)
            return dl_path

        # Check if file is an image
        if (mime_type and mime_type.startswith("image/")) or file_ext in [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".tiff",
            ".svg",
        ]:
            # Check if image compression is enabled by command-line flag
            if hasattr(self, "compress_image") and self.compress_image:
                LOGGER.info("Compressing image file")
                # Set preset from command-line if specified
                if hasattr(self, "image_preset") and self.image_preset:
                    self.compression_image_preset = self.image_preset
                return await self.compress_image_file(dl_path, gid)
            # Otherwise check if it's enabled in settings
            if self.compression_image_enabled:
                LOGGER.info("Compressing image file")
                return await self.compress_image_file(dl_path, gid)
            return dl_path

        # Check if file is a document
        if (mime_type and mime_type.startswith("application/pdf")) or file_ext in [
            ".pdf",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
        ]:
            # Check if document compression is enabled by command-line flag
            if hasattr(self, "compress_document") and self.compress_document:
                LOGGER.info("Compressing document file")
                # Set preset from command-line if specified
                if hasattr(self, "document_preset") and self.document_preset:
                    self.compression_document_preset = self.document_preset
                return await self.compress_document_file(dl_path, gid)
            # Otherwise check if it's enabled in settings
            if self.compression_document_enabled:
                LOGGER.info("Compressing document file")
                return await self.compress_document_file(dl_path, gid)
            return dl_path

        # Check if file is an archive
        if file_ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"]:
            # Check if archive compression is enabled by command-line flag
            if hasattr(self, "compress_archive") and self.compress_archive:
                LOGGER.info("Compressing archive file")
                # Set preset from command-line if specified
                if hasattr(self, "archive_preset") and self.archive_preset:
                    self.compression_archive_preset = self.archive_preset
                return await self.compress_archive_file(dl_path, gid)
            # Otherwise check if it's enabled in settings
            if self.compression_archive_enabled:
                LOGGER.info("Compressing archive file")
                return await self.compress_archive_file(dl_path, gid)
            return dl_path

        # If no specific compression is enabled or file type doesn't match, use 7z compression
        LOGGER.info("Using default compression")
        return await self.compress_with_7z(dl_path, gid)

    async def compress_with_7z(self, dl_path, gid):
        pswd = self.compress if isinstance(self.compress, str) else ""
        if self.is_leech and self.is_file:
            new_folder = ospath.splitext(dl_path)[0]
            name = ospath.basename(dl_path)
            try:
                await makedirs(new_folder, exist_ok=True)
                new_dl_path = f"{new_folder}/{name}"
                await move(dl_path, new_dl_path)
            except FileExistsError:
                # Try with a different folder name using timestamp
                new_folder = f"{ospath.splitext(dl_path)[0]}_{int(time())}"
                await makedirs(new_folder, exist_ok=True)
                new_dl_path = f"{new_folder}/{name}"
                await move(dl_path, new_dl_path)
            dl_path = new_dl_path
            up_path = f"{new_dl_path}.zip"
            self.is_file = False
        else:
            up_path = f"{dl_path}.zip"
        sevenz = SevenZ(self)
        async with task_dict_lock:
            task_dict[self.mid] = SevenZStatus(self, sevenz, gid, "Zip")
        return await sevenz.zip(dl_path, up_path, pswd)

    async def compress_video_file(self, dl_path, gid):
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        file_ext = ospath.splitext(dl_path)[1].lower()

        # Check if the file is a valid video file
        if file_ext not in [
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".flv",
            ".webm",
            ".wmv",
            ".m4v",
            ".3gp",
            ".ts",
            ".mpg",
            ".mpeg",
        ]:
            return dl_path

        # Use specified format if available
        if (
            self.compression_video_format
            and self.compression_video_format.lower() != "none"
        ):
            out_ext = f".{self.compression_video_format.lower()}"
        else:
            out_ext = file_ext

        out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

        # Validate the video file using ffprobe
        try:
            # Check if xtra binary exists
            import shutil
            import subprocess

            xtra_path = shutil.which("xtra")
            ffprobe_cmd = [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                dl_path,
            ]

            if xtra_path:
                # Use ffprobe from the same directory as xtra
                xtra_dir = os.path.dirname(xtra_path)
                ffprobe_path = os.path.join(xtra_dir, "ffprobe")
                if os.path.exists(ffprobe_path):
                    ffprobe_cmd[0] = ffprobe_path

            # Run ffprobe to check if the file is a valid video
            process = subprocess.run(
                ffprobe_cmd, capture_output=True, text=True, check=False
            )

            if process.returncode != 0:
                LOGGER.error(f"Invalid video file: {dl_path}")
                LOGGER.debug(f"ffprobe error: {process.stderr}")
                return dl_path

            # Check if the video has a valid duration
            try:
                duration = float(process.stdout.strip())
                if duration <= 0:
                    LOGGER.error(f"Video has invalid duration: {duration}")
                    return dl_path
            except (ValueError, TypeError):
                LOGGER.error(f"Could not determine video duration: {process.stdout}")
                return dl_path

        except Exception as e:
            LOGGER.error(f"Error validating video file: {e}")
            # Continue anyway, as the validation is just a precaution

        # Set FFmpeg parameters based on preset
        preset = self.compression_video_preset

        # Get CRF with proper None handling
        user_crf = self.user_dict.get("COMPRESSION_VIDEO_CRF")
        owner_crf = getattr(Config, "COMPRESSION_VIDEO_CRF", None)

        if user_crf is not None and str(user_crf).lower() != "none":
            crf = user_crf
        elif owner_crf is not None and str(owner_crf).lower() != "none":
            crf = owner_crf
        else:
            crf = 23  # Default CRF value

        # Get codec with proper None handling
        user_codec = self.user_dict.get("COMPRESSION_VIDEO_CODEC")
        owner_codec = getattr(Config, "COMPRESSION_VIDEO_CODEC", None)

        if user_codec is not None and str(user_codec).lower() != "none":
            codec = user_codec
        elif owner_codec is not None and str(owner_codec).lower() != "none":
            codec = owner_codec
        else:
            codec = "libx264"  # Default codec

        # Get tune with proper None handling
        user_tune = self.user_dict.get("COMPRESSION_VIDEO_TUNE")
        owner_tune = getattr(Config, "COMPRESSION_VIDEO_TUNE", None)

        if user_tune is not None and str(user_tune).lower() != "none":
            tune = user_tune
        elif owner_tune is not None and str(owner_tune).lower() != "none":
            tune = owner_tune
        else:
            tune = "film"  # Default tune

        # Get pixel format with proper None handling
        user_pixel_format = self.user_dict.get("COMPRESSION_VIDEO_PIXEL_FORMAT")
        owner_pixel_format = getattr(Config, "COMPRESSION_VIDEO_PIXEL_FORMAT", None)

        if (
            user_pixel_format is not None
            and str(user_pixel_format).lower() != "none"
        ):
            pixel_format = user_pixel_format
        elif (
            owner_pixel_format is not None
            and str(owner_pixel_format).lower() != "none"
        ):
            pixel_format = owner_pixel_format
        else:
            pixel_format = "yuv420p"  # Default pixel format

        # Video format is already initialized in the class constructor

        # Adjust parameters based on preset
        if preset == "fast":
            preset_str = "veryfast"
            try:
                crf = min(
                    int(crf) + 3, 51
                )  # Increase CRF for faster encoding (lower quality)
            except (ValueError, TypeError):
                crf = 26  # Default for fast preset if crf is None or invalid
        elif preset == "medium":
            preset_str = "medium"
            try:
                # Use default CRF
                crf = int(crf)
            except (ValueError, TypeError):
                crf = 23  # Default for medium preset if crf is None or invalid
        elif preset == "slow":
            preset_str = "slow"
            try:
                crf = max(
                    int(crf) - 3, 0
                )  # Decrease CRF for slower encoding (higher quality)
            except (ValueError, TypeError):
                crf = 20  # Default for slow preset if crf is None or invalid
        else:
            preset_str = "medium"  # Default

        # Build FFmpeg command
        ffmpeg_cmd = [
            "xtra",  # Using the renamed binary for FFmpeg
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            dl_path,
            "-c:v",
            codec,
            "-preset",
            preset_str,
            "-crf",
            str(crf),
            "-tune",
            tune,
            "-pix_fmt",
            pixel_format,
            "-c:a",
            "aac",  # Always use AAC for audio
            "-b:a",
            "128k",  # Default audio bitrate
            "-movflags",
            "+faststart",  # Optimize for web streaming
            "-y",  # Overwrite output file if it exists
            out_path,
        ]

        # Execute FFmpeg command
        ffmpeg = FFMpeg(self)
        async with task_dict_lock:
            task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Compress")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        try:
            # Check if xtra binary exists
            import shutil

            xtra_path = shutil.which("xtra")
            if not xtra_path:
                LOGGER.error("xtra binary not found in PATH")
                # Try to find ffmpeg instead
                ffmpeg_path = shutil.which("ffmpeg")
                if ffmpeg_path:
                    # Replace xtra with ffmpeg in the command
                    ffmpeg_cmd[0] = "ffmpeg"  # Use ffmpeg as fallback
                else:
                    LOGGER.error("Neither xtra nor ffmpeg binary found in PATH")
                    return dl_path

            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start FFmpeg progress tracking
            if hasattr(ffmpeg, "progress"):
                await ffmpeg.progress(self.subproc)
            elif hasattr(ffmpeg, "_ffmpeg_progress"):
                await ffmpeg._ffmpeg_progress()

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"Video compression failed: {stderr}")
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    await remove(dl_path)
                    return out_path
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                await remove(dl_path)
                return out_path
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during video compression: {e!s}")
            return dl_path

    async def compress_audio_file(self, dl_path, gid):
        # Create output path with same extension
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        file_ext = ospath.splitext(dl_path)[1].lower()

        # Check if the file is a valid audio file
        if file_ext not in [
            ".mp3",
            ".wav",
            ".flac",
            ".ogg",
            ".m4a",
            ".aac",
            ".opus",
            ".wma",
        ]:
            LOGGER.info(f"File is not a supported audio format: {file_ext}")
            return dl_path

        # Use specified format if available
        if (
            self.compression_audio_format
            and self.compression_audio_format.lower() != "none"
        ):
            out_ext = f".{self.compression_audio_format.lower()}"
        # For certain formats, we'll convert to AAC for better compression if no format specified
        elif file_ext in [".ogg", ".wav", ".flac"]:
            out_ext = ".m4a"
        else:
            out_ext = file_ext

        out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

        # Prepare for compression

        # Validate the audio file using ffprobe
        try:
            # Check if xtra binary exists
            import shutil
            import subprocess

            xtra_path = shutil.which("xtra")
            ffprobe_cmd = [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                dl_path,
            ]

            if xtra_path:
                # Use ffprobe from the same directory as xtra
                xtra_dir = os.path.dirname(xtra_path)
                ffprobe_path = os.path.join(xtra_dir, "ffprobe")
                if os.path.exists(ffprobe_path):
                    ffprobe_cmd[0] = ffprobe_path

            # Run ffprobe to check if the file is a valid audio
            process = subprocess.run(
                ffprobe_cmd, capture_output=True, text=True, check=False
            )

            if process.returncode != 0:
                LOGGER.error(f"Invalid audio file: {dl_path}")
                LOGGER.debug(f"ffprobe error: {process.stderr}")
                return dl_path

            # Check if the audio has a valid duration
            try:
                duration = float(process.stdout.strip())
                if duration <= 0:
                    LOGGER.error(f"Audio has invalid duration: {duration}")
                    return dl_path
            except (ValueError, TypeError):
                LOGGER.error(f"Could not determine audio duration: {process.stdout}")
                return dl_path

        except Exception as e:
            LOGGER.error(f"Error validating audio file: {e}")
            # Continue anyway, as the validation is just a precaution

        # Set FFmpeg parameters based on preset
        preset = self.compression_audio_preset

        # Get codec with proper None handling
        user_codec = self.user_dict.get("COMPRESSION_AUDIO_CODEC")
        owner_codec = getattr(Config, "COMPRESSION_AUDIO_CODEC", None)

        if user_codec is not None and str(user_codec).lower() != "none":
            codec = user_codec
        elif owner_codec is not None and str(owner_codec).lower() != "none":
            codec = owner_codec
        else:
            codec = "aac"  # Default codec

        # Get bitrate with proper None handling
        user_bitrate = self.user_dict.get("COMPRESSION_AUDIO_BITRATE")
        owner_bitrate = getattr(Config, "COMPRESSION_AUDIO_BITRATE", None)

        if user_bitrate is not None and str(user_bitrate).lower() != "none":
            bitrate = user_bitrate
        elif owner_bitrate is not None and str(owner_bitrate).lower() != "none":
            bitrate = owner_bitrate
        else:
            bitrate = "128k"  # Default bitrate

        # Get channels with proper None handling
        user_channels = self.user_dict.get("COMPRESSION_AUDIO_CHANNELS")
        owner_channels = getattr(Config, "COMPRESSION_AUDIO_CHANNELS", None)

        if user_channels is not None and str(user_channels).lower() != "none":
            channels = user_channels
        elif owner_channels is not None and str(owner_channels).lower() != "none":
            channels = owner_channels
        else:
            channels = 2  # Default channels

        # Audio format is already initialized in the class constructor

        # Adjust parameters based on preset
        if preset == "fast":
            # Lower quality for faster encoding
            try:
                if isinstance(bitrate, str) and "k" in bitrate:
                    bitrate_value = int(bitrate.replace("k", ""))
                    bitrate = f"{max(bitrate_value - 32, 64)}k"
                else:
                    bitrate = "96k"  # Default for fast preset
            except (ValueError, TypeError):
                bitrate = (
                    "96k"  # Default for fast preset if bitrate is None or invalid
                )
        elif preset == "medium":
            # Use default bitrate
            if not isinstance(bitrate, str) or "k" not in bitrate:
                bitrate = "128k"  # Default for medium preset
        elif preset == "slow":
            # Higher quality for slower encoding
            try:
                if isinstance(bitrate, str) and "k" in bitrate:
                    bitrate_value = int(bitrate.replace("k", ""))
                    bitrate = f"{bitrate_value + 32}k"
                else:
                    bitrate = "192k"  # Default for slow preset
            except (ValueError, TypeError):
                bitrate = (
                    "192k"  # Default for slow preset if bitrate is None or invalid
                )

        # Build FFmpeg command
        ffmpeg_cmd = [
            "xtra",  # Using the renamed binary for FFmpeg
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            dl_path,
        ]

        # Check output format
        out_ext = ospath.splitext(out_path)[1].lower()

        # Special handling for MP3 input to MP3 output to avoid codec issues
        if file_ext == ".mp3" and out_ext == ".mp3":
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "4",  # Quality level (0-9)
                    "-map",
                    "0:a",  # Only map audio streams
                ]
            )
        # For M4A output (AAC codec)
        elif out_ext == ".m4a":
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "aac",
                    "-b:a",
                    bitrate,
                    "-ac",
                    str(channels),
                    "-movflags",
                    "+faststart",  # Optimize for streaming
                ]
            )
        # For FLAC output
        elif out_ext == ".flac":
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "flac",
                    "-compression_level",
                    "8",  # Maximum compression
                ]
            )
        # For OGG output
        elif out_ext == ".ogg":
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "libvorbis",
                    "-q:a",
                    "4",  # Quality level (0-10)
                ]
            )
        # For WAV output
        elif out_ext == ".wav":
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "pcm_s16le",  # 16-bit PCM
                    "-ar",
                    "44100",  # 44.1kHz sample rate
                ]
            )
        # For MP3 output
        elif out_ext == ".mp3":
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "4",  # Quality level (0-9)
                ]
            )
        # For other audio formats
        else:
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    codec,
                    "-b:a",
                    bitrate,
                    "-ac",
                    str(channels),
                ]
            )

        # Add output path
        ffmpeg_cmd.extend(
            [
                "-y",  # Overwrite output file if it exists
                out_path,
            ]
        )

        # Execute FFmpeg command
        ffmpeg = FFMpeg(self)
        async with task_dict_lock:
            task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Compress")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        try:
            # Check if xtra binary exists
            import shutil

            xtra_path = shutil.which("xtra")
            if not xtra_path:
                LOGGER.error("xtra binary not found in PATH")
                # Try to find ffmpeg instead
                ffmpeg_path = shutil.which("ffmpeg")
                if ffmpeg_path:
                    LOGGER.info(f"Using ffmpeg instead: {ffmpeg_path}")
                    # Replace xtra with ffmpeg in the command
                    ffmpeg_cmd[0] = "ffmpeg"  # Use ffmpeg as fallback
                else:
                    LOGGER.error("Neither xtra nor ffmpeg binary found in PATH")
                    return dl_path

            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start FFmpeg progress tracking
            # Check if the progress method exists
            if hasattr(ffmpeg, "progress"):
                await ffmpeg.progress(self.subproc)
            elif hasattr(ffmpeg, "_ffmpeg_progress"):
                await ffmpeg._ffmpeg_progress()
            else:
                LOGGER.warning(
                    "FFmpeg object has no progress tracking method, skipping progress tracking"
                )

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"Audio compression failed: {stderr}")
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Audio compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during audio compression: {e!s}")
            return dl_path

    async def compress_image_file(self, dl_path, gid):
        # Create output path with same extension
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        file_ext = ospath.splitext(dl_path)[1].lower()

        # Check if the file is a valid image file
        if file_ext not in [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".tiff",
            ".tif",
            ".svg",
        ]:
            LOGGER.info(f"File is not a supported image format: {file_ext}")
            return dl_path

        # Use specified format if available
        if (
            self.compression_image_format
            and self.compression_image_format.lower() != "none"
        ):
            out_ext = f".{self.compression_image_format.lower()}"
            LOGGER.info(
                f"Using specified image format: {self.compression_image_format}"
            )
        # For certain formats, we'll convert to PNG for better compression if no format specified
        elif file_ext in [".bmp", ".tiff", ".tif", ".svg"]:
            out_ext = ".png"
            LOGGER.info(f"Converting {file_ext} to PNG for better compression")
        else:
            out_ext = file_ext
            LOGGER.info(f"Using original file extension: {file_ext}")

        out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

        # Prepare for compression

        # Validate the image file
        try:
            # Check if the file is a valid image by trying to read its dimensions
            import shutil
            import subprocess

            # For SVG files, we need special handling
            if file_ext == ".svg":
                # SVG files are text-based, so we can just check if it's a valid XML file
                try:
                    import xml.etree.ElementTree as ET

                    tree = ET.parse(dl_path)
                    root = tree.getroot()
                    if not root.tag.endswith("svg"):
                        LOGGER.error(f"Invalid SVG file: {dl_path}")
                        return dl_path
                except Exception as e:
                    LOGGER.error(f"Invalid SVG file: {dl_path}, error: {e}")
                    return dl_path

                # For SVG files, we'll convert to PNG using a different approach
                # First, check if convert (ImageMagick) is available
                convert_path = shutil.which("convert")
                if convert_path:
                    # Use ImageMagick to convert SVG to PNG
                    convert_cmd = [convert_path, dl_path, out_path]
                    try:
                        process = subprocess.run(
                            convert_cmd,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if process.returncode == 0:
                            # Conversion successful
                            return out_path
                    except Exception as e:
                        LOGGER.error(
                            f"Error converting SVG to PNG using ImageMagick: {e}"
                        )

                # If ImageMagick is not available or failed, just return the original file
                return dl_path

            # For other image formats, use ffprobe
            xtra_path = shutil.which("xtra")
            ffprobe_cmd = [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                dl_path,
            ]

            if xtra_path:
                # Use ffprobe from the same directory as xtra
                xtra_dir = os.path.dirname(xtra_path)
                ffprobe_path = os.path.join(xtra_dir, "ffprobe")
                if os.path.exists(ffprobe_path):
                    ffprobe_cmd[0] = ffprobe_path

            # Run ffprobe to check if the file is a valid image
            process = subprocess.run(
                ffprobe_cmd, capture_output=True, text=True, check=False
            )

            if process.returncode != 0:
                LOGGER.error(f"Invalid image file: {dl_path}")

                # For BMP and TIFF files, try using ImageMagick if available
                if file_ext in [".bmp", ".tiff", ".tif"]:
                    convert_path = shutil.which("convert")
                    if convert_path:
                        # Use ImageMagick to convert to PNG
                        convert_cmd = [convert_path, dl_path, out_path]
                        try:
                            process = subprocess.run(
                                convert_cmd,
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                            if process.returncode == 0:
                                # Conversion successful
                                return out_path
                        except Exception as e:
                            LOGGER.error(
                                f"Error converting {file_ext} to PNG using ImageMagick: {e}"
                            )

                # If all else fails, return the original file
                return dl_path

            # Check if the image has valid dimensions
            try:
                dimensions = process.stdout.strip().split(",")
                if len(dimensions) != 2 or not all(
                    dim.isdigit() for dim in dimensions
                ):
                    LOGGER.error(f"Image has invalid dimensions: {process.stdout}")
                    return dl_path

                width, height = map(int, dimensions)
                if width <= 0 or height <= 0:
                    LOGGER.error(f"Image has invalid dimensions: {width}x{height}")
                    return dl_path

                # Image dimensions are valid
            except Exception as e:
                LOGGER.error(f"Could not determine image dimensions: {e}")
                return dl_path

        except Exception as e:
            LOGGER.error(f"Error validating image file: {e}")
            # Continue anyway, as the validation is just a precaution

        # Set parameters based on preset
        preset = self.compression_image_preset

        # Get quality with proper None handling
        user_quality = self.user_dict.get("COMPRESSION_IMAGE_QUALITY")
        owner_quality = getattr(Config, "COMPRESSION_IMAGE_QUALITY", None)

        if user_quality is not None and str(user_quality).lower() != "none":
            quality = user_quality
        elif owner_quality is not None and str(owner_quality).lower() != "none":
            quality = owner_quality
        else:
            quality = 80  # Default quality

        # Get resize with proper None handling
        user_resize = self.user_dict.get("COMPRESSION_IMAGE_RESIZE")
        owner_resize = getattr(Config, "COMPRESSION_IMAGE_RESIZE", None)

        if user_resize is not None and str(user_resize).lower() != "none":
            resize = user_resize
        elif owner_resize is not None and str(owner_resize).lower() != "none":
            resize = owner_resize
        else:
            resize = None  # Default resize (no resize)

        # Image format is already initialized in the class constructor

        # Adjust parameters based on preset
        try:
            quality = int(quality)  # Ensure quality is an integer

            if preset == "fast":
                quality = min(quality - 10, 100)  # Lower quality for faster encoding
            elif preset == "medium":
                # Use default quality
                pass
            elif preset == "slow":
                quality = min(
                    quality + 10, 100
                )  # Higher quality for slower encoding

            # Ensure quality is within valid range
            quality = max(1, min(quality, 100))
        except (ValueError, TypeError):
            # Default quality if conversion fails
            if preset == "fast":
                quality = 70
            elif preset == "medium":
                quality = 80
            elif preset == "slow":
                quality = 90
            else:
                quality = 80

        # Build FFmpeg command
        ffmpeg_cmd = [
            "xtra",  # Using the renamed binary for FFmpeg
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            dl_path,
        ]

        # Check output format
        out_ext = ospath.splitext(out_path)[1].lower()

        # For PNG output
        if out_ext == ".png":
            # For PNG output, use pngquant filter for better compression
            ffmpeg_cmd.extend(
                [
                    "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
                    "-c:v",
                    "png",
                    "-compression_level",
                    "9",  # Maximum compression
                ]
            )
        # For JPEG output
        elif out_ext in {".jpg", ".jpeg"}:
            # For JPEG output, use quality parameter
            ffmpeg_cmd.extend(
                [
                    "-q:v",
                    str(quality),
                ]
            )
        # For WebP output
        elif out_ext == ".webp":
            # For WebP output, use libwebp codec
            ffmpeg_cmd.extend(
                [
                    "-c:v",
                    "libwebp",
                    "-lossless",
                    "0",
                    "-q:v",
                    str(quality),
                    "-compression_level",
                    "6",
                ]
            )
        # For GIF output
        elif out_ext == ".gif":
            # For GIF output, use palette
            ffmpeg_cmd.extend(
                [
                    "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                ]
            )
        # For BMP output
        elif out_ext == ".bmp":
            # Convert BMP to PNG for better compression
            out_path = f"{ospath.splitext(out_path)[0]}.png"
            ffmpeg_cmd.extend(
                [
                    "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
                    "-c:v",
                    "png",
                    "-compression_level",
                    "9",  # Maximum compression
                ]
            )
        # For TIFF output
        elif out_ext in {".tiff", ".tif"}:
            # Convert TIFF to PNG for better compression
            out_path = f"{ospath.splitext(out_path)[0]}.png"
            ffmpeg_cmd.extend(
                [
                    "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
                    "-c:v",
                    "png",
                    "-compression_level",
                    "9",  # Maximum compression
                ]
            )
        # For SVG output
        elif out_ext == ".svg":
            # SVG is already a compressed format, just copy it
            return dl_path
        # For other image formats
        else:
            # For other image formats, use quality parameter
            ffmpeg_cmd.extend(
                [
                    "-q:v",
                    str(quality),
                ]
            )

        # Add resize parameter if specified
        if resize and resize != "none":
            # If we already have a filter, append to it
            if "-vf" in ffmpeg_cmd:
                idx = ffmpeg_cmd.index("-vf")
                ffmpeg_cmd[idx + 1] = ffmpeg_cmd[idx + 1] + f",scale={resize}"
            else:
                ffmpeg_cmd.extend(["-vf", f"scale={resize}"])

        # Add output path
        ffmpeg_cmd.extend(["-y", out_path])

        # Execute FFmpeg command
        ffmpeg = FFMpeg(self)
        async with task_dict_lock:
            task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Compress")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        try:
            # Check if xtra binary exists
            import shutil

            xtra_path = shutil.which("xtra")
            if not xtra_path:
                LOGGER.error("xtra binary not found in PATH")
                # Try to find ffmpeg instead
                ffmpeg_path = shutil.which("ffmpeg")
                if ffmpeg_path:
                    LOGGER.info(f"Using ffmpeg instead: {ffmpeg_path}")
                    # Replace xtra with ffmpeg in the command
                    ffmpeg_cmd[0] = "ffmpeg"  # Use ffmpeg as fallback
                else:
                    LOGGER.error("Neither xtra nor ffmpeg binary found in PATH")
                    return dl_path

            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start FFmpeg progress tracking
            # Check if the progress method exists
            if hasattr(ffmpeg, "progress"):
                await ffmpeg.progress(self.subproc)
            elif hasattr(ffmpeg, "_ffmpeg_progress"):
                await ffmpeg._ffmpeg_progress()
            else:
                LOGGER.warning(
                    "FFmpeg object has no progress tracking method, skipping progress tracking"
                )

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"Image compression failed: {stderr}")
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Image compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during image compression: {e!s}")
            return dl_path

    async def compress_document_file(self, dl_path, gid):
        # For PDF files, we can use Ghostscript to compress
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        file_ext = ospath.splitext(dl_path)[1].lower()

        # Log the paths for debugging
        LOGGER.debug(f"Document compression input path: {dl_path}")

        if file_ext == ".pdf":
            # Use specified format if available
            if (
                self.compression_document_format
                and self.compression_document_format.lower() != "none"
            ):
                out_ext = f".{self.compression_document_format.lower()}"
                LOGGER.info(
                    f"Using specified document format: {self.compression_document_format}"
                )
            else:
                out_ext = file_ext
                LOGGER.info(f"Using original file extension: {file_ext}")

            out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

            # Set parameters based on preset
            preset = self.compression_document_preset

            # Get DPI with proper None handling
            user_dpi = self.user_dict.get("COMPRESSION_DOCUMENT_DPI")
            owner_dpi = getattr(Config, "COMPRESSION_DOCUMENT_DPI", None)

            if user_dpi is not None and str(user_dpi).lower() != "none":
                dpi = user_dpi
            elif owner_dpi is not None and str(owner_dpi).lower() != "none":
                dpi = owner_dpi
            else:
                dpi = 150  # Default DPI

            # Document format is already initialized in the class constructor

            # Adjust parameters based on preset
            try:
                dpi = int(dpi)  # Ensure DPI is an integer

                if preset == "fast":
                    dpi = min(dpi - 50, 300)  # Lower DPI for faster encoding
                elif preset == "medium":
                    # Use default DPI
                    pass
                elif preset == "slow":
                    dpi = max(dpi + 50, 72)  # Higher DPI for slower encoding

                # Ensure DPI is within valid range
                dpi = max(72, min(dpi, 300))
            except (ValueError, TypeError):
                # Default DPI if conversion fails
                if preset == "fast":
                    dpi = 100
                elif preset == "medium":
                    dpi = 150
                elif preset == "slow":
                    dpi = 200
                else:
                    dpi = 150

            # Build Ghostscript command
            # Check if we need to use a renamed binary for Ghostscript
            gs_binary = "gs"

            # Log the command for debugging
            LOGGER.debug(f"Using Ghostscript binary: {gs_binary}")

            gs_cmd = [
                gs_binary,
                "-sDEVICE=pdfwrite",
                "-dPDFSETTINGS=/ebook",
                "-dDEVICEWIDTHPOINTS=595",
                "-dDEVICEHEIGHTPOINTS=842",
                "-dCompatibilityLevel=1.4",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-r{dpi}",
                f"-sOutputFile={out_path}",
                dl_path,
            ]

            try:
                # Check if gs binary exists
                import shutil

                gs_path = shutil.which(gs_binary)
                if not gs_path:
                    LOGGER.error(f"{gs_binary} binary not found in PATH")
                    LOGGER.info("Falling back to FFmpeg for PDF compression")
                    return await self._compress_document_with_ffmpeg(
                        dl_path, out_path, gid
                    )
                LOGGER.debug(f"Found {gs_binary} binary at: {gs_path}")

                # Log the full command for debugging
                LOGGER.debug(f"Ghostscript command: {' '.join(gs_cmd)}")

                # Use subprocess.run for simplicity
                import subprocess

                # Check if the input file is a valid PDF
                try:
                    with open(dl_path, "rb") as f:
                        header = f.read(5)
                        if header != b"%PDF-":
                            LOGGER.error(f"File is not a valid PDF: {dl_path}")
                            return dl_path
                except Exception as e:
                    LOGGER.error(f"Error checking PDF file: {e}")
                    return dl_path

                # Make sure the output directory exists
                out_dir = os.path.dirname(out_path)
                if not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)

                # Run the Ghostscript command
                try:
                    process = subprocess.run(
                        gs_cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except Exception as e:
                    LOGGER.error(f"Error running Ghostscript command: {e}")
                    LOGGER.info("Falling back to FFmpeg for PDF compression")
                    return await self._compress_document_with_ffmpeg(
                        dl_path, out_path, gid
                    )

                if process.returncode != 0:
                    LOGGER.error(f"PDF compression failed: {process.stderr}")
                    LOGGER.info("Falling back to FFmpeg for PDF compression")
                    return await self._compress_document_with_ffmpeg(
                        dl_path, out_path, gid
                    )

                # Check if compressed file is smaller
                orig_size = await get_path_size(dl_path)
                comp_size = await get_path_size(out_path)

                if comp_size < orig_size:
                    LOGGER.info(
                        f"PDF compression successful: {orig_size} -> {comp_size} bytes"
                    )
                    # Remove original file if compression was successful or delete_original is set
                    if self.compression_delete_original:
                        LOGGER.info(
                            "Deleting original file as requested by delete_original setting"
                        )
                        await remove(dl_path)
                        return out_path
                    LOGGER.info(
                        "Removing original file as compression was successful"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Compressed file is not smaller than original")
                # Check if we should still delete the original
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Keeping original file and removing compressed file")
                await remove(out_path)
                return dl_path

            except Exception as e:
                LOGGER.error(f"Error during PDF compression: {e!s}")
                LOGGER.info("Falling back to FFmpeg for PDF compression")
                return await self._compress_document_with_ffmpeg(
                    dl_path, out_path, gid
                )
        elif file_ext in [
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".odt",
            ".ods",
            ".odp",
        ]:
            # For office documents, try to convert to PDF first, then compress
            LOGGER.info(
                f"Converting office document {file_ext} to PDF for compression"
            )

            # Use specified format if available
            if (
                self.compression_document_format
                and self.compression_document_format.lower() != "none"
            ):
                out_ext = f".{self.compression_document_format.lower()}"
                LOGGER.info(
                    f"Using specified document format: {self.compression_document_format}"
                )
            else:
                out_ext = ".pdf"  # Default to PDF for office documents
                LOGGER.info("Converting to PDF for better compression")

            out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

            # Try to use LibreOffice for conversion if available
            import shutil

            libreoffice_binary = "libreoffice"
            libreoffice_path = shutil.which(libreoffice_binary)

            if libreoffice_path:
                LOGGER.info(
                    f"Using LibreOffice for document conversion: {libreoffice_path}"
                )

                # Build LibreOffice command
                libreoffice_cmd = [
                    libreoffice_binary,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    os.path.dirname(out_path),
                    dl_path,
                ]

                try:
                    # Execute LibreOffice command
                    import subprocess

                    process = subprocess.run(
                        libreoffice_cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if process.returncode != 0:
                        LOGGER.error(
                            f"LibreOffice conversion failed: {process.stderr}"
                        )
                        # Fall back to 7z compression
                        return await self._compress_document_with_7z(dl_path, gid)

                    # LibreOffice creates the output file with the original name but .pdf extension
                    pdf_path = f"{ospath.splitext(dl_path)[0]}.pdf"

                    if await aiopath.exists(pdf_path):
                        # Now compress the PDF
                        LOGGER.info(
                            f"Successfully converted to PDF, now compressing: {pdf_path}"
                        )
                        compressed_path = await self.compress_document_file(
                            pdf_path, gid
                        )

                        # If the original wasn't compressed (same path returned), rename to our desired output
                        if compressed_path == pdf_path and pdf_path != out_path:
                            os.rename(pdf_path, out_path)
                            compressed_path = out_path

                        # Delete the original file if requested
                        if self.compression_delete_original:
                            LOGGER.info(
                                "Deleting original file as requested by delete_original setting"
                            )
                            await remove(dl_path)

                        return compressed_path
                    LOGGER.error(
                        "LibreOffice conversion failed: output file not found"
                    )
                    # Fall back to 7z compression
                    return await self._compress_document_with_7z(dl_path, gid)

                except Exception as e:
                    LOGGER.error(f"Error during LibreOffice conversion: {e!s}")
                    # Fall back to 7z compression
                    return await self._compress_document_with_7z(dl_path, gid)
            else:
                LOGGER.info("LibreOffice not found, falling back to 7z compression")
                # Fall back to 7z compression
                return await self._compress_document_with_7z(dl_path, gid)
        else:
            # For other document types, use 7z compression
            return await self._compress_document_with_7z(dl_path, gid)

    async def _compress_document_with_ffmpeg(self, dl_path, out_path, gid):
        """Fallback method to compress PDF using FFmpeg"""
        LOGGER.info(f"Using FFmpeg to compress PDF: {dl_path}")

        # Create a simple FFmpeg object for status tracking
        ffmpeg = FFMpeg(self)
        async with task_dict_lock:
            task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Compress")

        # Build FFmpeg command
        ffmpeg_cmd = [
            "xtra",  # Using the renamed binary for FFmpeg
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            dl_path,
            "-c:v",
            "libx264",  # Use H.264 for PDF pages
            "-crf",
            "28",  # Higher CRF for more compression
            "-preset",
            "medium",
            "-y",
            out_path,
        ]

        # Check if xtra binary exists
        import shutil

        xtra_path = shutil.which("xtra")
        if not xtra_path:
            LOGGER.error("xtra binary not found in PATH")
            # Try to find ffmpeg instead
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                LOGGER.info(f"Using ffmpeg instead: {ffmpeg_path}")
                # Replace xtra with ffmpeg in the command
                ffmpeg_cmd[0] = "ffmpeg"  # Use ffmpeg as fallback
            else:
                LOGGER.error("Neither xtra nor ffmpeg binary found in PATH")
                return dl_path

        try:
            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start FFmpeg progress tracking
            if hasattr(ffmpeg, "progress"):
                await ffmpeg.progress(self.subproc)
            elif hasattr(ffmpeg, "_ffmpeg_progress"):
                await ffmpeg._ffmpeg_progress()
            else:
                LOGGER.warning(
                    "FFmpeg object has no progress tracking method, skipping progress tracking"
                )

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"FFmpeg PDF compression failed: {stderr}")
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"FFmpeg PDF compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during FFmpeg PDF compression: {e!s}")
            return dl_path

    async def _compress_document_with_7z(self, dl_path, gid):
        """Helper method to compress documents using 7z"""
        try:
            # Check if 7z binary exists
            import shutil

            # Check for 7z binary
            sevenzip_binary = "7z"
            sevenzip_path = shutil.which(sevenzip_binary)

            if not sevenzip_path:
                LOGGER.error(f"{sevenzip_binary} binary not found in PATH")
                return dl_path

            # Use specified format if available
            if (
                self.compression_document_format
                and self.compression_document_format.lower() != "none"
            ):
                out_ext = f".{self.compression_document_format.lower()}"
                LOGGER.info(
                    f"Using specified document format: {self.compression_document_format}"
                )
            else:
                out_ext = ".7z"  # Default to 7z for better compression
                LOGGER.info("Using 7z format for better compression")

            # Create output path
            out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

            # Build 7z command
            sevenzip_cmd = [
                sevenzip_binary,
                "a",  # Add to archive
                "-t7z",  # Archive type
                "-mx=9",  # Ultra compression
                "-mfb=64",  # Filter block size
                "-md=32m",  # Dictionary size
                "-ms=on",  # Solid archive
                out_path,
                dl_path,
            ]

            # Log the command for debugging
            LOGGER.debug(f"7z command: {' '.join(sevenzip_cmd)}")

            # Create a simple SevenZ object for status tracking
            sevenz = SevenZ(self)
            async with task_dict_lock:
                task_dict[self.mid] = SevenZStatus(self, sevenz, gid, "Compress")

            # Make sure the is_cancelled attribute exists
            if not hasattr(self, "is_cancelled"):
                self.is_cancelled = False

            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *sevenzip_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start 7z progress tracking
            if hasattr(sevenz, "_sevenz_progress"):
                await sevenz._sevenz_progress()
            else:
                LOGGER.warning(
                    "SevenZ object has no progress tracking method, skipping progress tracking"
                )

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"7z compression failed: {stderr}")
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Document compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during document compression: {e!s}")
            return dl_path

    async def compress_subtitle_file(self, dl_path, gid):
        # For subtitle files, we can convert to a more efficient encoding
        # gid parameter is used for task tracking in other compression methods
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        file_ext = ospath.splitext(dl_path)[1].lower()

        # Use specified format if available
        if (
            self.compression_subtitle_format
            and self.compression_subtitle_format.lower() != "none"
        ):
            out_ext = f".{self.compression_subtitle_format.lower()}"
            LOGGER.info(
                f"Using specified subtitle format: {self.compression_subtitle_format}"
            )
        # For certain formats, we'll convert to SRT for better compatibility if no format specified
        elif file_ext in [".ass", ".ssa", ".vtt", ".sub", ".sbv", ".stl"]:
            out_ext = ".srt"
            LOGGER.info(f"Converting {file_ext} to SRT for better compatibility")
        else:
            out_ext = file_ext
            LOGGER.info(f"Using original file extension: {file_ext}")

        out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

        # Log the paths for debugging
        LOGGER.debug(f"Subtitle compression input path: {dl_path}")
        LOGGER.debug(f"Subtitle compression output path: {out_path}")

        # Get encoding with proper None handling
        user_encoding = self.user_dict.get("COMPRESSION_SUBTITLE_ENCODING")
        owner_encoding = getattr(Config, "COMPRESSION_SUBTITLE_ENCODING", None)

        if user_encoding is not None and str(user_encoding).lower() != "none":
            encoding = user_encoding
        elif owner_encoding is not None and str(owner_encoding).lower() != "none":
            encoding = owner_encoding
        else:
            encoding = "utf-8"  # Default encoding

        # Subtitle format is already initialized in the class constructor

        # Create a simple FFmpeg object for status tracking
        ffmpeg = FFMpeg(self)
        async with task_dict_lock:
            task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Compress")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        # Set initial progress values
        # Check if the FFMpeg object has these properties
        try:
            ffmpeg._processed_bytes = 0
            ffmpeg._progress_raw = 0
            ffmpeg._speed_raw = 0
            ffmpeg._eta_raw = 0
        except Exception as e:
            LOGGER.warning(f"Could not set FFMpeg progress values: {e}")

        try:
            # For format conversion, use FFmpeg
            if file_ext != out_ext or file_ext in [
                ".ass",
                ".ssa",
                ".vtt",
                ".sub",
                ".sbv",
                ".stl",
            ]:
                LOGGER.info(
                    f"Using FFmpeg to convert subtitle from {file_ext} to {out_ext}"
                )

                # Build FFmpeg command
                ffmpeg_cmd = [
                    "xtra",  # Using the renamed binary for FFmpeg
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    dl_path,
                ]

                # Add format-specific options
                if out_ext == ".srt":
                    ffmpeg_cmd.extend(["-c:s", "srt"])
                elif out_ext in {".ass", ".ssa"}:
                    ffmpeg_cmd.extend(["-c:s", "ass"])
                elif out_ext == ".vtt":
                    ffmpeg_cmd.extend(["-c:s", "webvtt"])
                else:
                    ffmpeg_cmd.extend(["-c:s", "copy"])

                # Add output path
                ffmpeg_cmd.extend(["-y", out_path])

                # Check if xtra binary exists
                import shutil

                xtra_path = shutil.which("xtra")
                if not xtra_path:
                    LOGGER.error("xtra binary not found in PATH")
                    # Try to find ffmpeg instead
                    ffmpeg_path = shutil.which("ffmpeg")
                    if ffmpeg_path:
                        LOGGER.info(f"Using ffmpeg instead: {ffmpeg_path}")
                        # Replace xtra with ffmpeg in the command
                        ffmpeg_cmd[0] = "ffmpeg"  # Use ffmpeg as fallback
                    else:
                        LOGGER.error("Neither xtra nor ffmpeg binary found in PATH")
                        return dl_path

                # Create subprocess with pipes
                from asyncio.subprocess import PIPE, create_subprocess_exec

                self.subproc = await create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                )

                # Wait for process to complete
                _, stderr = await self.subproc.communicate()
                code = self.subproc.returncode

                if code != 0:
                    stderr = stderr.decode().strip()
                    LOGGER.error(f"Subtitle conversion failed: {stderr}")

                    # Fallback to simple text encoding conversion
                    LOGGER.info("Falling back to simple text encoding conversion")
                    return await self._compress_subtitle_text(
                        dl_path, out_path, encoding
                    )

                # Check if compressed file exists
                if not await aiopath.exists(out_path):
                    LOGGER.error("Subtitle conversion failed: output file not found")
                    return dl_path
            else:
                # For simple encoding change without format conversion
                return await self._compress_subtitle_text(
                    dl_path, out_path, encoding
                )

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Subtitle compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during subtitle compression: {e!s}")
            return dl_path

    async def _compress_subtitle_text(self, dl_path, out_path, encoding):
        """Helper method for simple text-based subtitle compression"""
        try:
            import time

            # Create a simple FFmpeg object for status tracking
            ffmpeg = FFMpeg(self)

            # Set initial progress values
            try:
                ffmpeg._processed_bytes = 0
                ffmpeg._progress_raw = 0
                ffmpeg._speed_raw = 0
                ffmpeg._eta_raw = 0
            except Exception as e:
                LOGGER.warning(f"Could not set FFMpeg progress values: {e}")

            # Update progress to 25%
            with contextlib.suppress(Exception):
                ffmpeg._progress_raw = 25
            start_time = time.time()

            # Read the subtitle file
            with open(dl_path, encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Update progress to 50%
            with contextlib.suppress(Exception):
                ffmpeg._progress_raw = 50

            # Get file size for progress tracking
            orig_size = await get_path_size(dl_path)
            try:
                ffmpeg._processed_bytes = orig_size // 2
                elapsed = time.time() - start_time
                if elapsed > 0:
                    ffmpeg._speed_raw = (orig_size // 2) / elapsed
                    ffmpeg._eta_raw = elapsed  # Estimate same time to finish
            except Exception as e:
                LOGGER.debug(f"Could not update FFMpeg progress values: {e}")

            # Write the subtitle file with the specified encoding
            with open(out_path, "w", encoding=encoding) as f:
                f.write(content)

            # Update progress to 100%
            try:
                ffmpeg._progress_raw = 100
                ffmpeg._processed_bytes = orig_size
                elapsed = time.time() - start_time
                if elapsed > 0:
                    ffmpeg._speed_raw = orig_size / elapsed
                    ffmpeg._eta_raw = 0  # Done
            except Exception as e:
                LOGGER.debug(f"Could not update final FFMpeg progress values: {e}")

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Subtitle text compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during subtitle text compression: {e!s}")
            return dl_path

    async def compress_archive_file(self, dl_path, gid):
        # For archive files, we can recompress with 7z
        # gid parameter is used for task tracking in other compression methods
        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for compression: {dl_path}")
            return dl_path

        file_ext = ospath.splitext(dl_path)[1].lower()

        # Check if the file is already a compressed archive
        already_compressed_exts = [
            ".7z",
            ".zip",
            ".rar",
            ".gz",
            ".bz2",
            ".xz",
            ".lzma",
            ".lz4",
            ".zst",
        ]

        # For already compressed archives, check if we should try to recompress
        if file_ext in already_compressed_exts:
            LOGGER.info(f"File is already a compressed archive: {file_ext}")

            # If the user specifically requested a different format, proceed with conversion
            if (
                self.compression_archive_format
                and self.compression_archive_format.lower() != "none"
                and f".{self.compression_archive_format.lower()}" != file_ext
            ):
                LOGGER.info(
                    f"Converting from {file_ext} to .{self.compression_archive_format.lower()} as requested"
                )
            # If the user wants to delete the original regardless of compression
            elif self.compression_delete_original:
                LOGGER.info(
                    "Keeping original file as it's already compressed, but marking as deleted due to delete_original setting"
                )
                return dl_path
            else:
                LOGGER.info("Skipping compression for already compressed archive")
                return dl_path

        # Use specified format if available
        if (
            self.compression_archive_format
            and self.compression_archive_format.lower() != "none"
        ):
            out_ext = f".{self.compression_archive_format.lower()}"
            LOGGER.info(
                f"Using specified archive format: {self.compression_archive_format}"
            )
        else:
            out_ext = ".7z"  # Default to 7z for better compression
            LOGGER.info("Using 7z format for better compression")

        out_path = f"{ospath.splitext(dl_path)[0]}_compressed{out_ext}"

        # Log the paths for debugging
        LOGGER.debug(f"Archive compression input path: {dl_path}")
        LOGGER.debug(f"Archive compression output path: {out_path}")

        # Set parameters based on preset
        preset = self.compression_archive_preset

        # Get level with proper None handling
        user_level = self.user_dict.get("COMPRESSION_ARCHIVE_LEVEL")
        owner_level = getattr(Config, "COMPRESSION_ARCHIVE_LEVEL", None)

        if user_level is not None and str(user_level).lower() != "none":
            level = user_level
        elif owner_level is not None and str(owner_level).lower() != "none":
            level = owner_level
        else:
            level = 5  # Default level

        # Get method with proper None handling
        user_method = self.user_dict.get("COMPRESSION_ARCHIVE_METHOD")
        owner_method = getattr(Config, "COMPRESSION_ARCHIVE_METHOD", None)

        if user_method is not None and str(user_method).lower() != "none":
            method = user_method
        elif owner_method is not None and str(owner_method).lower() != "none":
            method = owner_method
        else:
            method = "deflate"  # Default method

        # Archive format is already initialized in the class constructor

        # Adjust parameters based on preset
        try:
            level = int(level)  # Ensure level is an integer

            if preset == "fast":
                level = min(level - 2, 9)  # Lower level for faster compression
            elif preset == "medium":
                # Use default level
                pass
            elif preset == "slow":
                level = min(level + 2, 9)  # Higher level for better compression

            # Ensure level is within valid range
            level = max(1, min(level, 9))
        except (ValueError, TypeError):
            # Default level if conversion fails
            if preset == "fast":
                level = 3
            elif preset == "medium":
                level = 5
            elif preset == "slow":
                level = 7
            else:
                level = 5

        # Check if we need to extract the archive first (for format conversion)
        if file_ext in already_compressed_exts and out_ext != file_ext:
            LOGGER.info(f"Converting archive format from {file_ext} to {out_ext}")

            # First, extract the archive to a temporary directory
            temp_dir = f"{ospath.splitext(dl_path)[0]}_temp"

            # Create the temporary directory
            os.makedirs(temp_dir, exist_ok=True)

            # Extract the archive
            extract_success = await self._extract_archive_for_conversion(
                dl_path, temp_dir, gid
            )

            if not extract_success:
                LOGGER.error(f"Failed to extract archive for conversion: {dl_path}")
                # Clean up the temporary directory
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)
                return dl_path

            # Now compress the extracted files to the new format
            compress_success = await self._compress_directory(
                temp_dir, out_path, level, method, gid
            )

            # Clean up the temporary directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

            if not compress_success:
                LOGGER.error(
                    f"Failed to compress extracted files to new format: {out_path}"
                )
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Archive conversion successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Converted archive is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing converted file")
            await remove(out_path)
            return dl_path
        # Direct compression without extraction
        return await self._compress_archive_directly(
            dl_path, out_path, level, method, gid
        )

    async def _extract_archive_for_conversion(self, archive_path, extract_dir, gid):
        """Helper method to extract an archive for format conversion"""
        LOGGER.info(
            f"Extracting archive for format conversion: {archive_path} to {extract_dir}"
        )

        # Check if 7z binary exists
        import shutil

        sevenz_binary = "7z"
        sevenz_path = shutil.which(sevenz_binary)

        if not sevenz_path:
            LOGGER.error(f"{sevenz_binary} binary not found in PATH")
            return False

        # Build 7z extract command
        sevenz_cmd = [
            sevenz_binary,
            "x",  # Extract with full paths
            "-y",  # Assume yes on all queries
            "-o" + extract_dir,  # Output directory
            archive_path,
        ]

        # Use SevenZ for extraction with status tracking
        sevenz = SevenZ(self)
        async with task_dict_lock:
            task_dict[self.mid] = SevenZStatus(self, sevenz, gid, "Extract")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        try:
            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *sevenz_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start 7z progress tracking
            if hasattr(sevenz, "_sevenz_progress"):
                await sevenz._sevenz_progress()

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"Archive extraction failed: {stderr}")
                return False

            return True

        except Exception as e:
            LOGGER.error(f"Error during archive extraction: {e!s}")
            return False

    async def _compress_directory(
        self, directory_path, out_path, level, method, gid
    ):
        """Helper method to compress a directory to an archive"""
        LOGGER.info(
            f"Compressing directory to archive: {directory_path} to {out_path}"
        )

        # Check if 7z binary exists
        import shutil

        sevenz_binary = "7z"
        sevenz_path = shutil.which(sevenz_binary)

        if not sevenz_path:
            LOGGER.error(f"{sevenz_binary} binary not found in PATH")
            return False

        # Build 7z compress command
        sevenz_cmd = [
            sevenz_binary,
            "a",  # Add to archive
            "-t7z",  # Archive type (will be overridden by output extension if different)
            f"-mx={level}",  # Compression level
            f"-m0={method}",  # Compression method
            "-bsp1",  # Show progress
            "-bse1",  # Show errors
            "-bso0",  # No standard output
            "-y",  # Overwrite output file if it exists
            out_path,
            f"{directory_path}/*",  # All files in the directory
        ]

        # Use SevenZ for compression with status tracking
        sevenz = SevenZ(self)
        async with task_dict_lock:
            task_dict[self.mid] = SevenZStatus(self, sevenz, gid, "Compress")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        try:
            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *sevenz_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start 7z progress tracking
            if hasattr(sevenz, "_sevenz_progress"):
                await sevenz._sevenz_progress()

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"Directory compression failed: {stderr}")
                return False

            return True

        except Exception as e:
            LOGGER.error(f"Error during directory compression: {e!s}")
            return False

    async def _compress_archive_directly(
        self, dl_path, out_path, level, method, gid
    ):
        """Helper method to compress an archive directly without extraction"""
        # Build 7z command
        sevenz_binary = "7z"

        # Log the command for debugging
        LOGGER.debug(f"Using 7z binary: {sevenz_binary}")

        sevenz_cmd = [
            sevenz_binary,
            "a",
            "-t7z",
            f"-mx={level}",
            f"-m0={method}",
            "-bsp1",  # Show progress
            "-bse1",  # Show errors
            "-bso0",  # No standard output
            "-y",  # Overwrite output file if it exists
            out_path,
            dl_path,
        ]

        # Use SevenZ for compression with status tracking
        sevenz = SevenZ(self)
        async with task_dict_lock:
            task_dict[self.mid] = SevenZStatus(self, sevenz, gid, "Compress")

        # Make sure the is_cancelled attribute exists
        if not hasattr(self, "is_cancelled"):
            self.is_cancelled = False

        try:
            # Check if 7z binary exists
            import shutil

            sevenz_path = shutil.which(sevenz_binary)
            if not sevenz_path:
                LOGGER.error(f"{sevenz_binary} binary not found in PATH")
                return dl_path
            LOGGER.debug(f"Found {sevenz_binary} binary at: {sevenz_path}")

            # Log the full command for debugging
            LOGGER.debug(f"7z command: {' '.join(sevenz_cmd)}")

            # Create subprocess with pipes
            from asyncio.subprocess import PIPE, create_subprocess_exec

            self.subproc = await create_subprocess_exec(
                *sevenz_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            # Start 7z progress tracking
            if hasattr(sevenz, "_sevenz_progress"):
                await sevenz._sevenz_progress()
            else:
                LOGGER.warning(
                    "SevenZ object has no progress tracking method, skipping progress tracking"
                )

            # Wait for process to complete
            _, stderr = await self.subproc.communicate()
            code = self.subproc.returncode

            if code != 0:
                stderr = stderr.decode().strip()
                LOGGER.error(f"Archive compression failed: {stderr}")
                return dl_path

            # Check if compressed file is smaller
            orig_size = await get_path_size(dl_path)
            comp_size = await get_path_size(out_path)

            if comp_size < orig_size:
                LOGGER.info(
                    f"Archive compression successful: {orig_size} -> {comp_size} bytes"
                )
                # Remove original file if compression was successful or delete_original is set
                if self.compression_delete_original:
                    LOGGER.info(
                        "Deleting original file as requested by delete_original setting"
                    )
                    await remove(dl_path)
                    return out_path
                LOGGER.info("Removing original file as compression was successful")
                await remove(dl_path)
                return out_path
            LOGGER.info("Compressed file is not smaller than original")
            # Check if we should still delete the original
            if self.compression_delete_original:
                LOGGER.info(
                    "Deleting original file as requested by delete_original setting"
                )
                await remove(dl_path)
                return out_path
            LOGGER.info("Keeping original file and removing compressed file")
            await remove(out_path)
            return dl_path

        except Exception as e:
            LOGGER.error(f"Error during archive compression: {e!s}")
            return dl_path

    async def proceed_split(self, dl_path, gid):
        # Import the get_user_split_size function
        from bot.helper.ext_utils.bot_utils import get_user_split_size

        self.files_to_proceed = {}
        if self.is_file:
            f_size = await get_path_size(dl_path)
            if f_size > self.split_size:
                self.files_to_proceed[dl_path] = [f_size, ospath.basename(dl_path)]
        else:
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    f_size = await get_path_size(f_path)
                    if f_size > self.split_size:
                        self.files_to_proceed[f_path] = [f_size, file_]
        if self.files_to_proceed:
            ffmpeg = FFMpeg(self)
            async with task_dict_lock:
                task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Split")
            LOGGER.info(f"Splitting: {self.name}")
            for f_path, (f_size, file_) in self.files_to_proceed.items():
                self.proceed_count += 1
                if self.is_file:
                    self.subsize = self.size
                else:
                    self.subsize = f_size
                    self.subname = file_

                # Check if equal splits is enabled in user settings
                user_dict = self.user_dict
                equal_splits = user_dict.get("EQUAL_SPLITS", False) or (
                    Config.EQUAL_SPLITS and "EQUAL_SPLITS" not in user_dict
                )

                # Check for command override if args attribute exists
                if hasattr(self, "args") and self.args:
                    if self.args.get("-es") == "t":
                        equal_splits = True
                    elif self.args.get("-es") == "f":
                        equal_splits = False

                # Use get_user_split_size to determine split size and whether to skip splitting
                if equal_splits:
                    # Set a flag to indicate equal splits is enabled for this task
                    self.equal_splits_enabled = True
                    # Use get_user_split_size with equal_splits=True to get equal split size
                    # Equal splits always divides the file into equal parts based on max split size
                    # Pass args only if it exists
                    args = self.args if hasattr(self, "args") else None
                    split_size, skip_splitting = get_user_split_size(
                        self.user_id, args, f_size, equal_splits=True
                    )

                    if skip_splitting:
                        LOGGER.info(
                            f"File size ({f_size} bytes) is less than max split size ({self.max_split_size} bytes). No need for equal splits."
                        )
                        return False

                    # Calculate number of parts for logging
                    parts = math.ceil(f_size / split_size)
                    LOGGER.info(
                        f"Equal Splits enabled. File will be split into {parts} equal parts of approximately {split_size} bytes each."
                    )
                else:
                    # Set a flag to indicate equal splits is disabled for this task
                    self.equal_splits_enabled = False
                    # Use get_user_split_size to determine split size and whether to skip splitting
                    # Pass args only if it exists
                    args = self.args if hasattr(self, "args") else None
                    split_size, skip_splitting = get_user_split_size(
                        self.user_id, args, f_size, equal_splits=False
                    )

                    if skip_splitting:
                        LOGGER.info(
                            f"File size ({f_size} bytes) is less than split size ({self.split_size} bytes). Skipping split."
                        )
                        return False

                    LOGGER.debug(
                        f"Using {'custom' if self.split_size != self.max_split_size else 'default'} split size: {split_size} bytes"
                    )

                # Calculate number of parts using math.ceil for consistency
                parts = math.ceil(f_size / split_size)
                LOGGER.debug(f"File will be split into {parts} parts")

                if not self.as_doc and (await get_document_type(f_path))[0]:
                    self.progress = True
                    res = await ffmpeg.split(f_path, file_, parts, split_size)
                else:
                    self.progress = False
                    res = await split_file(f_path, split_size, self)
                if self.is_cancelled:
                    return False
                if res or f_size >= self.max_split_size:
                    try:
                        await remove(f_path)
                    except Exception:
                        self.is_cancelled = True
            return None
        return None

    async def proceed_metadata(self, dl_path, gid):
        # Get global metadata values with priority
        # metadata_all takes priority over individual settings
        metadata_all = self.metadata_all
        metadata_title = self.metadata_title
        metadata_author = self.metadata_author
        metadata_comment = self.metadata_comment

        # Get video track metadata values
        metadata_video_title = self.metadata_video_title
        metadata_video_author = self.metadata_video_author
        metadata_video_comment = self.metadata_video_comment

        # Get audio track metadata values
        metadata_audio_title = self.metadata_audio_title
        metadata_audio_author = self.metadata_audio_author
        metadata_audio_comment = self.metadata_audio_comment

        # Get subtitle track metadata values
        metadata_subtitle_title = self.metadata_subtitle_title
        metadata_subtitle_author = self.metadata_subtitle_author
        metadata_subtitle_comment = self.metadata_subtitle_comment

        # Legacy key for backward compatibility
        key = self.metadata

        # Log metadata settings with source information
        LOGGER.info(
            f"Metadata settings - All: {metadata_all}, Title: {metadata_title}, Author: {metadata_author}, Comment: {metadata_comment}, Legacy Key: {key}"
        )
        LOGGER.info(
            f"Video metadata - Title: {metadata_video_title}, Author: {metadata_video_author}, Comment: {metadata_video_comment}"
        )
        LOGGER.info(
            f"Audio metadata - Title: {metadata_audio_title}, Author: {metadata_audio_author}, Comment: {metadata_audio_comment}"
        )
        LOGGER.info(
            f"Subtitle metadata - Title: {metadata_subtitle_title}, Author: {metadata_subtitle_author}, Comment: {metadata_subtitle_comment}"
        )

        # Log if command line arguments were used
        if self.metadata_all:
            LOGGER.info(f"Using metadata-all from command line: {self.metadata_all}")
        if self.metadata_title:
            LOGGER.info(
                f"Using metadata-title from command line: {self.metadata_title}"
            )
        if self.metadata_author:
            LOGGER.info(
                f"Using metadata-author from command line: {self.metadata_author}"
            )
        if self.metadata_comment:
            LOGGER.info(
                f"Using metadata-comment from command line: {self.metadata_comment}"
            )

        # Function to check if a file is supported for metadata
        async def is_metadata_supported(file_path):
            # Get file extension
            ext = ospath.splitext(file_path)[1].lower()

            # Check if it's a media file that supports metadata
            is_video, is_audio, is_image = await get_document_type(file_path)

            # List of supported extensions for metadata
            supported_video_exts = [
                ".mkv",
                ".mp4",
                ".avi",
                ".mov",
                ".webm",
                ".m4v",
                ".ts",
                ".3gp",
                ".flv",
                ".wmv",
                ".mpeg",
                ".hevc",
                ".m2ts",
                ".vob",
                ".divx",
                ".mpg",
            ]
            supported_audio_exts = [
                ".mp3",
                ".m4a",
                ".flac",
                ".wav",
                ".ogg",
                ".opus",
                ".aac",
                ".ac3",
                ".wma",
                ".aiff",
                ".alac",
                ".dts",
                ".amr",
            ]
            supported_image_exts = [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".tiff",
                ".tif",
                ".webp",
                ".bmp",
                ".heic",
                ".heif",
                ".avif",
                ".jfif",
                ".svg",
                ".ico",
                ".psd",
                ".eps",
                ".raw",
                ".cr2",
                ".nef",
                ".orf",
                ".sr2",
            ]
            supported_subtitle_exts = [
                ".srt",
                ".ass",
                ".ssa",
                ".vtt",
                ".webvtt",
                ".sub",
                ".sbv",
                ".stl",
                ".scc",
                ".ttml",
                ".dfxp",
            ]
            supported_document_exts = [
                ".pdf",
                ".epub",
                ".mobi",
                ".azw",
                ".azw3",
                ".djvu",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".odt",
                ".ods",
                ".odp",
                ".txt",
                ".rtf",
                ".md",
                ".csv",
            ]

            # Check if the file is supported
            if is_video and ext in supported_video_exts:
                return True, "video"
            if is_audio and not is_video and ext in supported_audio_exts:
                return True, "audio"
            if is_image and ext in supported_image_exts:
                return True, "image"
            if ext in supported_subtitle_exts:
                return True, "subtitle"
            if ext in supported_document_exts:
                # For document files, we don't need to check if it's a media file
                return True, "document"
            return False, ""

        ffmpeg = FFMpeg(self)
        checked = False
        if self.is_file:
            # Check if the file is supported for metadata
            is_supported, media_type = await is_metadata_supported(dl_path)
            if is_supported:
                LOGGER.info(f"Applying metadata to {media_type} file: {dl_path}")

                # Handle document files differently
                if media_type == "document":
                    # For PDF and other document files, use a different approach
                    success = await apply_document_metadata(
                        dl_path,
                        title=metadata_title or key,
                        author=metadata_author or key,
                        comment=metadata_comment or key,
                    )
                    if success:
                        LOGGER.info(
                            f"Successfully applied document metadata to {dl_path}"
                        )
                    else:
                        LOGGER.warning(
                            f"Failed to apply document metadata to {dl_path}"
                        )
                else:
                    # For media files, use FFmpeg
                    cmd, temp_file = await get_metadata_cmd(
                        dl_path,
                        key,
                        title=metadata_title,
                        author=metadata_author,
                        comment=metadata_comment,
                        metadata_all=metadata_all,
                        video_title=metadata_video_title,
                        video_author=metadata_video_author,
                        video_comment=metadata_video_comment,
                        audio_title=metadata_audio_title,
                        audio_author=metadata_audio_author,
                        audio_comment=metadata_audio_comment,
                        subtitle_title=metadata_subtitle_title,
                        subtitle_author=metadata_subtitle_author,
                        subtitle_comment=metadata_subtitle_comment,
                    )
                    if cmd:
                        if not checked:
                            checked = True
                            async with task_dict_lock:
                                task_dict[self.mid] = FFmpegStatus(
                                    self,
                                    ffmpeg,
                                    gid,
                                    "Metadata",
                                )
                            self.progress = False
                            await cpu_eater_lock.acquire()
                            self.progress = True
                        self.subsize = self.size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res:
                            os.replace(temp_file, dl_path)
                            LOGGER.info(
                                f"Successfully applied metadata to {dl_path}"
                            )
                        elif await aiopath.exists(temp_file):
                            os.remove(temp_file)
                            LOGGER.warning(f"Failed to apply metadata to {dl_path}")
                    else:
                        LOGGER.warning(
                            f"Failed to generate metadata command for {dl_path}"
                        )
            else:
                # Check if it's a document file that we can handle with document_utils
                file_ext = ospath.splitext(dl_path)[1].lower()
                if file_ext in [".pdf", ".epub", ".doc", ".docx"]:
                    LOGGER.info(
                        f"Applying document metadata to {file_ext} file: {dl_path}"
                    )
                    success = await apply_document_metadata(
                        dl_path,
                        title=metadata_title or key,
                        author=metadata_author or key,
                        comment=metadata_comment or key,
                    )
                    if success:
                        LOGGER.info(
                            f"Successfully applied document metadata to {dl_path}"
                        )
                    else:
                        LOGGER.warning(
                            f"Failed to apply document metadata to {dl_path}"
                        )
                else:
                    LOGGER.info(f"Skipping metadata for unsupported file: {dl_path}")

        # Process all files in the directory if it's not a single file
        if not self.is_file:
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    file_path = ospath.join(dirpath, file_)
                    if self.is_cancelled:
                        if checked:
                            cpu_eater_lock.release()
                        return ""

                    # Check if the file is supported for metadata
                    is_supported, media_type = await is_metadata_supported(file_path)
                    if not is_supported:
                        LOGGER.debug(
                            f"Skipping metadata for unsupported file: {file_path}"
                        )
                        continue

                    self.proceed_count += 1
                    LOGGER.info(
                        f"Applying metadata to {media_type} file: {file_path}"
                    )

                    cmd, temp_file = await get_metadata_cmd(
                        file_path,
                        key,
                        title=metadata_title,
                        author=metadata_author,
                        comment=metadata_comment,
                        metadata_all=metadata_all,
                        video_title=metadata_video_title,
                        video_author=metadata_video_author,
                        video_comment=metadata_video_comment,
                        audio_title=metadata_audio_title,
                        audio_author=metadata_audio_author,
                        audio_comment=metadata_audio_comment,
                        subtitle_title=metadata_subtitle_title,
                        subtitle_author=metadata_subtitle_author,
                        subtitle_comment=metadata_subtitle_comment,
                    )

                    if cmd:
                        if not checked:
                            checked = True
                            async with task_dict_lock:
                                task_dict[self.mid] = FFmpegStatus(
                                    self,
                                    ffmpeg,
                                    gid,
                                    "Metadata",
                                )
                            self.progress = False
                            await cpu_eater_lock.acquire()
                            self.progress = True

                        LOGGER.debug(f"Running metadata cmd for: {file_path}")
                        self.subsize = await aiopath.getsize(file_path)
                        self.subname = file_

                        res = await ffmpeg.metadata_watermark_cmds(
                            cmd,
                            file_path,
                        )

                        if res:
                            os.replace(temp_file, file_path)
                            LOGGER.info(
                                f"Successfully applied metadata to {file_path}"
                            )
                        elif await aiopath.exists(temp_file):
                            os.remove(temp_file)
                            LOGGER.warning(
                                f"Failed to apply metadata to {file_path}"
                            )
                    else:
                        LOGGER.warning(
                            f"Failed to generate metadata command for {file_path}"
                        )

        if checked:
            cpu_eater_lock.release()

        return dl_path

    async def proceed_merge(self, dl_path, gid):
        # Skip if merge is not enabled
        if not self.merge_enabled:
            LOGGER.info("Merge not applied: merge is not enabled")
            return dl_path

        LOGGER.info(f"Analyzing directory for merge: {dl_path}")

        # Get all files in the directory
        all_files = []
        if self.is_file:
            # If it's a single file, we can't merge it
            LOGGER.info("Merge not applied: single file cannot be merged")
            return dl_path
        for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
            for file_ in files:
                f_path = ospath.join(dirpath, file_)
                all_files.append(f_path)

        if not all_files:
            LOGGER.info("Merge not applied: no files found")
            return dl_path

        # Analyze media files for merging with enhanced analysis
        analysis = await analyze_media_for_merge(all_files)

        if not analysis["recommended_approach"]:
            LOGGER.info("Merge not applied: no suitable files for merging")
            return dl_path

        LOGGER.info(
            f"Merge analysis recommended approach: {analysis['recommended_approach']}"
        )
        LOGGER.info(
            f"Found {len(analysis['video_files'])} video files, {len(analysis['audio_files'])} audio files, "
            f"{len(analysis['subtitle_files'])} subtitle files, {len(analysis['image_files'])} image files, "
            f"{len(analysis['document_files'])} document files"
        )

        # Check for merge flags
        merge_video_only = self.merge_video
        merge_audio_only = self.merge_audio
        merge_subtitle_only = self.merge_subtitle
        merge_image_only = self.merge_image
        merge_pdf_only = self.merge_pdf
        merge_all_types = self.merge_all

        # Filter files based on merge flags
        if merge_video_only:
            LOGGER.info(
                "Merge flag: -merge-video detected, only merging video files"
            )
            if not analysis["video_files"]:
                LOGGER.info("Merge not applied: no video files found")
                return dl_path
            # Only use video files
            analysis["audio_files"] = []
            analysis["subtitle_files"] = []
            analysis["image_files"] = []
            analysis["document_files"] = []
            # Use the recommended approach based on codec compatibility
            if (
                "video_codec_groups" in analysis
                and len(analysis["video_codec_groups"]) > 1
            ):
                # Multiple codec groups - need to use filter_complex
                analysis["recommended_approach"] = "filter_complex"
                LOGGER.info(
                    f"Multiple video codec groups detected: {len(analysis['video_codec_groups'])}. Using filter_complex approach."
                )
            else:
                # Single codec group - can use concat_demuxer
                analysis["recommended_approach"] = "concat_demuxer"
                LOGGER.info(
                    "Single video codec group detected. Using concat_demuxer approach."
                )
        elif merge_audio_only:
            LOGGER.info(
                "Merge flag: -merge-audio detected, only merging audio files"
            )
            if not analysis["audio_files"]:
                LOGGER.info("Merge not applied: no audio files found")
                return dl_path
            # Only use audio files
            analysis["video_files"] = []
            analysis["subtitle_files"] = []
            analysis["image_files"] = []
            analysis["document_files"] = []
            # Use the recommended approach based on codec compatibility
            if (
                "audio_codec_groups" in analysis
                and len(analysis["audio_codec_groups"]) > 1
            ):
                # Multiple codec groups - need to use filter_complex
                analysis["recommended_approach"] = "filter_complex"
                LOGGER.info(
                    f"Multiple audio codec groups detected: {len(analysis['audio_codec_groups'])}. Using filter_complex approach."
                )
            else:
                # Single codec group - can use concat_demuxer
                analysis["recommended_approach"] = "concat_demuxer"
                LOGGER.info(
                    "Single audio codec group detected. Using concat_demuxer approach."
                )
        elif merge_subtitle_only:
            LOGGER.info(
                "Merge flag: -merge-subtitle detected, only merging subtitle files"
            )
            if not analysis["subtitle_files"]:
                LOGGER.info("Merge not applied: no subtitle files found")
                return dl_path
            # Only use subtitle files
            analysis["video_files"] = []
            analysis["audio_files"] = []
            analysis["image_files"] = []
            analysis["document_files"] = []
            # Use the recommended approach based on format compatibility
            if (
                "subtitle_format_groups" in analysis
                and len(analysis["subtitle_format_groups"]) > 1
            ):
                # Multiple format groups - need to use special handling
                analysis["recommended_approach"] = "subtitle_special"
                LOGGER.info(
                    f"Multiple subtitle format groups detected: {len(analysis['subtitle_format_groups'])}. Using special subtitle handling."
                )
            else:
                # Single format group - can use concat_demuxer
                analysis["recommended_approach"] = "concat_demuxer"
                LOGGER.info(
                    "Single subtitle format group detected. Using concat_demuxer approach."
                )
        elif merge_image_only:
            LOGGER.info(
                "Merge flag: -merge-image detected, only merging image files"
            )
            if not analysis["image_files"]:
                LOGGER.info("Merge not applied: no image files found")
                return dl_path
            # Only use image files
            analysis["video_files"] = []
            analysis["audio_files"] = []
            analysis["subtitle_files"] = []
            analysis["document_files"] = []
            # Set the recommended approach to image_merge
            analysis["recommended_approach"] = "image_merge"
            LOGGER.info("Using image_merge approach for image files")

        elif merge_pdf_only:
            LOGGER.info("Merge flag: -merge-pdf detected, only merging PDF files")
            # Filter document files to only include PDFs
            pdf_files = [
                f for f in analysis["document_files"] if f.lower().endswith(".pdf")
            ]
            if not pdf_files:
                LOGGER.info("Merge not applied: no PDF files found")
                return dl_path
            # Only use PDF files
            analysis["video_files"] = []
            analysis["audio_files"] = []
            analysis["subtitle_files"] = []
            analysis["image_files"] = []
            analysis["document_files"] = pdf_files
            # Set the recommended approach to document_merge
            analysis["recommended_approach"] = "document_merge"
            LOGGER.info("Using document_merge approach for PDF files")

        elif merge_all_types:
            LOGGER.info(
                "Merge flag: -merge-all detected, merging all file types separately"
            )
            # Keep all files but change approach to mixed
            if (
                len(analysis["video_files"])
                + len(analysis["audio_files"])
                + len(analysis["subtitle_files"])
                + len(analysis["image_files"])
                + len(analysis["document_files"])
                == 0
            ):
                LOGGER.info("Merge not applied: no media files found")
                return dl_path
            # Set approach to mixed to preserve all video and audio tracks
            analysis["recommended_approach"] = "mixed"
            LOGGER.info(
                "Using mixed approach to preserve all video and audio tracks"
            )

        # Determine which approach to use based on settings and analysis
        approach = analysis["recommended_approach"]
        ffmpeg = FFMpeg(self)

        # Create status for merge operation
        async with task_dict_lock:
            task_dict[self.mid] = FFmpegStatus(self, ffmpeg, gid, "Merge")

        self.progress = False
        await cpu_eater_lock.acquire()
        self.progress = True

        # Log the workflow being used
        if (
            self.merge_video
            or self.merge_audio
            or self.merge_subtitle
            or self.merge_image
            or self.merge_pdf
            or self.merge_all
        ):
            LOGGER.info("Using Special Flag Merge Workflow")
        else:
            LOGGER.info("Using Standard Merge Workflow")

        # Log the settings being used
        LOGGER.info(
            f"Merge settings - Concat Demuxer: {self.concat_demuxer_enabled}, Filter Complex: {self.filter_complex_enabled}"
        )

        try:
            # Special Flag Merge Workflow for -merge-video
            if self.merge_video:
                LOGGER.info("Special Flag Workflow: -merge-video")

                # Check if we have video files
                if not analysis["video_files"]:
                    LOGGER.info("Merge not applied: no video files found")
                    return dl_path

                # Try concat demuxer first if enabled
                if self.concat_demuxer_enabled:
                    LOGGER.info("Trying concat demuxer approach for -merge-video")
                    cmd, output_file = await get_merge_concat_demuxer_cmd(
                        analysis["video_files"],
                        self.merge_output_format_video,
                        "video",
                    )

                    if cmd:
                        # Calculate total size
                        total_size = 0
                        for f in all_files:
                            total_size += await get_path_size(f)
                        self.subsize = total_size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res and await aiopath.exists(output_file):
                            LOGGER.info(
                                f"Video merge successful with concat demuxer: {output_file}"
                            )
                            # Remove original files after successful merge if enabled
                            if self.merge_remove_original:
                                for f in all_files:
                                    try:
                                        if (
                                            await aiopath.exists(f)
                                            and f != output_file
                                        ):
                                            LOGGER.debug(
                                                f"Removing original file after merge: {f}"
                                            )
                                            await remove(f)
                                    except Exception as e:
                                        LOGGER.error(
                                            f"Error removing original file {f}: {e!s}"
                                        )
                            return output_file
                        LOGGER.warning(
                            "Concat demuxer approach failed, trying filter complex"
                        )

                # If concat demuxer failed or is not enabled, try filter complex
                if self.filter_complex_enabled:
                    LOGGER.info("Trying filter complex approach for -merge-video")
                    cmd, output_file = await get_merge_filter_complex_cmd(
                        analysis["video_files"],
                        "video",
                        self.merge_output_format_video,
                    )

                    if cmd:
                        # Calculate total size
                        total_size = 0
                        for f in all_files:
                            total_size += await get_path_size(f)
                        self.subsize = total_size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res and await aiopath.exists(output_file):
                            LOGGER.info(
                                f"Video merge successful with filter complex: {output_file}"
                            )
                            # Remove original files after successful merge if enabled
                            if self.merge_remove_original:
                                for f in all_files:
                                    try:
                                        if (
                                            await aiopath.exists(f)
                                            and f != output_file
                                        ):
                                            LOGGER.debug(
                                                f"Removing original file after merge: {f}"
                                            )
                                            await remove(f)
                                    except Exception as e:
                                        LOGGER.error(
                                            f"Error removing original file {f}: {e!s}"
                                        )
                            return output_file
                        LOGGER.warning("Filter complex approach failed")

                # If both approaches failed, return original path
                LOGGER.info("Video merge failed: all approaches failed")
                return dl_path

            # Special Flag Merge Workflow for -merge-image
            if self.merge_image:
                LOGGER.info("Special Flag Workflow: -merge-image")

                # For image files, use PIL to merge images
                # Using the function from ext_utils.media_utils

                if analysis["image_files"]:
                    # Determine merge mode based on number of images
                    if len(analysis["image_files"]) <= 2:
                        mode = "horizontal"
                    elif len(analysis["image_files"]) <= 4:
                        mode = "collage"
                        columns = 2
                    else:
                        mode = "collage"
                        columns = 3

                    # Get output format from first image or default to jpg
                    first_ext = os.path.splitext(analysis["image_files"][0])[
                        1
                    ].lower()[1:]
                    output_format = (
                        first_ext if first_ext in ["jpg", "jpeg", "png"] else "jpg"
                    )

                    LOGGER.info(
                        f"Merging {len(analysis['image_files'])} images in {mode} mode"
                    )
                    output_file = await merge_images(
                        analysis["image_files"],
                        output_format=output_format,
                        mode=mode,
                        columns=columns,
                    )

                    if output_file and await aiopath.exists(output_file):
                        LOGGER.info(f"Image merge successful: {output_file}")
                        # Remove original files after successful merge
                        for f in all_files:
                            try:
                                if await aiopath.exists(f) and f != output_file:
                                    LOGGER.debug(
                                        f"Removing original file after merge: {f}"
                                    )
                                    await remove(f)
                            except Exception as e:
                                LOGGER.error(
                                    f"Error removing original file {f}: {e!s}"
                                )
                        return output_file
                    LOGGER.warning("Image merge failed")
                    return dl_path
                LOGGER.info("No image files found for merging")
                return dl_path

            # Special Flag Merge Workflow for -merge-pdf
            if self.merge_pdf:
                LOGGER.info("Special Flag Workflow: -merge-pdf")

                # For PDF files, use PyPDF2 to merge PDFs
                # Using the function from ext_utils.media_utils

                # Check if we have PDF files
                pdf_files = [
                    f
                    for f in analysis["document_files"]
                    if f.lower().endswith(".pdf")
                ]

                if pdf_files:
                    LOGGER.info(f"Merging {len(pdf_files)} PDF documents")
                    output_file = await merge_documents(pdf_files)

                    if output_file and await aiopath.exists(output_file):
                        LOGGER.info(f"Document merge successful: {output_file}")
                        # Remove original files after successful merge
                        for f in all_files:
                            try:
                                if await aiopath.exists(f) and f != output_file:
                                    LOGGER.debug(
                                        f"Removing original file after merge: {f}"
                                    )
                                    await remove(f)
                            except Exception as e:
                                LOGGER.error(
                                    f"Error removing original file {f}: {e!s}"
                                )
                        return output_file
                    LOGGER.warning("Document merge failed")
                    return dl_path
                LOGGER.info("No PDF files found for merging")
                return dl_path

            # Special Flag Merge Workflow for -merge-audio, -merge-subtitle, or -merge-all
            if self.merge_audio or self.merge_subtitle or self.merge_all:
                LOGGER.debug(
                    f"Special Flag Workflow: {'-merge-audio' if self.merge_audio else '-merge-subtitle' if self.merge_subtitle else '-merge-all'}"
                )

                # For these flags, always try filter_complex first
                if self.filter_complex_enabled:
                    LOGGER.debug(
                        "Trying filter complex approach first (user/owner setting)"
                    )

                    if approach in ["mixed", "subtitle_special", "slideshow"]:
                        # Mixed media types, use filter complex or mixed approach
                        LOGGER.debug(
                            f"Using {approach} approach for different media types"
                        )
                        # For -merge-all flag, ensure we preserve all tracks
                        if self.merge_all:
                            LOGGER.debug(
                                "Preserving all video, audio, and subtitle tracks during merge"
                            )
                        cmd, output_file = await get_merge_mixed_cmd(
                            analysis["video_files"],
                            analysis["audio_files"],
                            analysis["subtitle_files"],
                            self.merge_output_format_video,
                        )
                    elif self.merge_audio and analysis["audio_files"]:
                        LOGGER.debug("Using filter complex for audio files")
                        cmd, output_file = await get_merge_filter_complex_cmd(
                            analysis["audio_files"],
                            "audio",
                            self.merge_output_format_audio,
                        )
                    elif self.merge_subtitle and analysis["subtitle_files"]:
                        LOGGER.debug("Using filter complex for subtitle files")
                        cmd, output_file = await get_merge_filter_complex_cmd(
                            analysis["subtitle_files"], "subtitle", "srt"
                        )
                    else:
                        cmd, output_file = None, None

                    if cmd:
                        # Calculate total size
                        total_size = 0
                        for f in all_files:
                            total_size += await get_path_size(f)
                        self.subsize = total_size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res and await aiopath.exists(output_file):
                            LOGGER.info(
                                f"Merge successful with filter complex: {output_file}"
                            )
                            # Remove original files after successful merge
                            for f in all_files:
                                try:
                                    if await aiopath.exists(f) and f != output_file:
                                        LOGGER.debug(
                                            f"Removing original file after merge: {f}"
                                        )
                                        await remove(f)
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error removing original file {f}: {e!s}"
                                    )
                            return output_file
                        LOGGER.warning(
                            "Filter complex approach failed, trying concat demuxer"
                        )

                # If filter complex failed or is not enabled, try concat demuxer
                if self.concat_demuxer_enabled:
                    LOGGER.debug(
                        "Trying concat demuxer approach (user/owner setting)"
                    )

                    if self.merge_audio and analysis["audio_files"]:
                        LOGGER.debug("Using concat demuxer for audio files")
                        cmd, output_file = await get_merge_concat_demuxer_cmd(
                            analysis["audio_files"],
                            self.merge_output_format_audio,
                            "audio",
                        )
                    elif self.merge_subtitle and analysis["subtitle_files"]:
                        LOGGER.debug("Using concat demuxer for subtitle files")
                        cmd, output_file = await get_merge_concat_demuxer_cmd(
                            analysis["subtitle_files"], "srt", "subtitle"
                        )
                    else:
                        cmd, output_file = None, None

                    if cmd:
                        # Calculate total size
                        total_size = 0
                        for f in all_files:
                            total_size += await get_path_size(f)
                        self.subsize = total_size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res and await aiopath.exists(output_file):
                            LOGGER.info(
                                f"Merge successful with concat demuxer: {output_file}"
                            )
                            # Remove original files after successful merge
                            for f in all_files:
                                try:
                                    if await aiopath.exists(f) and f != output_file:
                                        LOGGER.debug(
                                            f"Removing original file after merge: {f}"
                                        )
                                        await remove(f)
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error removing original file {f}: {e!s}"
                                    )
                            return output_file
                        LOGGER.warning(
                            "Concat demuxer approach failed, trying fallback approach"
                        )

            # Standard Merge Workflow (no special flags)
            else:
                LOGGER.debug("Standard Merge Workflow")

                # For same file types, try concat demuxer first if enabled
                if approach == "concat_demuxer" and self.concat_demuxer_enabled:
                    # All files are of the same type, use concat demuxer
                    LOGGER.debug(
                        "Trying concat demuxer approach (user/owner setting)"
                    )
                    if analysis["video_files"]:
                        LOGGER.debug("Using concat demuxer for video files")
                        cmd, output_file = await get_merge_concat_demuxer_cmd(
                            analysis["video_files"],
                            self.merge_output_format_video,
                            "video",
                        )
                    elif analysis["audio_files"]:
                        LOGGER.debug("Using concat demuxer for audio files")
                        cmd, output_file = await get_merge_concat_demuxer_cmd(
                            analysis["audio_files"],
                            self.merge_output_format_audio,
                            "audio",
                        )
                    elif analysis["subtitle_files"]:
                        LOGGER.debug("Using concat demuxer for subtitle files")
                        cmd, output_file = await get_merge_concat_demuxer_cmd(
                            analysis["subtitle_files"], "srt", "subtitle"
                        )
                    else:
                        cmd, output_file = None, None

                    if cmd:
                        # Calculate total size by summing individual file sizes
                        total_size = 0
                        for f in all_files:
                            total_size += await get_path_size(f)
                        self.subsize = total_size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res and await aiopath.exists(output_file):
                            LOGGER.info(
                                f"Merge successful with concat demuxer: {output_file}"
                            )
                            # Remove original files after successful merge
                            for f in all_files:
                                try:
                                    if await aiopath.exists(f) and f != output_file:
                                        LOGGER.debug(
                                            f"Removing original file after merge: {f}"
                                        )
                                        await remove(f)
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error removing original file {f}: {e!s}"
                                    )
                            return output_file
                        LOGGER.warning(
                            "Concat demuxer approach failed, trying filter complex approach"
                        )

                # If concat demuxer failed or is disabled, try filter complex
                if self.filter_complex_enabled:
                    if approach in ["mixed", "subtitle_special", "slideshow"]:
                        # Mixed media types, use filter complex or mixed approach
                        LOGGER.debug(
                            f"Using {approach} approach for different media types"
                        )
                        # For -merge-all flag, ensure we preserve all tracks
                        if self.merge_all:
                            LOGGER.debug(
                                "Preserving all video, audio, and subtitle tracks during merge"
                            )
                        cmd, output_file = await get_merge_mixed_cmd(
                            analysis["video_files"],
                            analysis["audio_files"],
                            analysis["subtitle_files"],
                            self.merge_output_format_video,
                        )
                    elif approach == "image_merge" and analysis["image_files"]:
                        # For image files, use PIL to merge images
                        # Using the function from ext_utils.media_utils

                        # Determine merge mode based on number of images
                        if len(analysis["image_files"]) <= 2:
                            mode = "horizontal"
                        elif len(analysis["image_files"]) <= 4:
                            mode = "collage"
                            columns = 2
                        else:
                            mode = "collage"
                            columns = 3

                        # Get output format from first image or default to jpg
                        first_ext = os.path.splitext(analysis["image_files"][0])[
                            1
                        ].lower()[1:]
                        output_format = (
                            first_ext
                            if first_ext in ["jpg", "jpeg", "png"]
                            else "jpg"
                        )

                        LOGGER.debug(
                            f"Merging {len(analysis['image_files'])} images in {mode} mode"
                        )
                        output_file = await merge_images(
                            analysis["image_files"],
                            output_format=output_format,
                            mode=mode,
                            columns=columns,
                        )

                        if output_file and await aiopath.exists(output_file):
                            LOGGER.info(f"Image merge successful: {output_file}")
                            return output_file
                        LOGGER.warning("Image merge failed")
                        return dl_path

                    elif approach == "document_merge" and analysis["document_files"]:
                        # For document files, use PyPDF2 to merge PDFs
                        # Using the function from ext_utils.media_utils

                        # Check if we have PDF files
                        pdf_files = [
                            f
                            for f in analysis["document_files"]
                            if f.lower().endswith(".pdf")
                        ]

                        if pdf_files:
                            LOGGER.info(f"Merging {len(pdf_files)} PDF documents")
                            output_file = await merge_documents(pdf_files)

                            if output_file and await aiopath.exists(output_file):
                                LOGGER.info(
                                    f"Document merge successful: {output_file}"
                                )
                                return output_file
                            LOGGER.warning("Document merge failed")
                            return dl_path
                        LOGGER.info("No PDF files found for merging")
                        return dl_path
                    # Try filter complex for same media types
                    elif analysis["video_files"]:
                        LOGGER.debug("Using filter complex for video files")
                        cmd, output_file = await get_merge_filter_complex_cmd(
                            analysis["video_files"],
                            "video",
                            self.merge_output_format_video,
                        )
                    elif analysis["audio_files"]:
                        LOGGER.debug("Using filter complex for audio files")
                        cmd, output_file = await get_merge_filter_complex_cmd(
                            analysis["audio_files"],
                            "audio",
                            self.merge_output_format_audio,
                        )
                    elif analysis["subtitle_files"]:
                        LOGGER.debug("Using filter complex for subtitle files")
                        cmd, output_file = await get_merge_filter_complex_cmd(
                            analysis["subtitle_files"], "subtitle", "srt"
                        )
                    else:
                        cmd, output_file = None, None

                    if cmd:
                        # Calculate total size by summing individual file sizes
                        total_size = 0
                        for f in all_files:
                            total_size += await get_path_size(f)
                        self.subsize = total_size
                        res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                        if res and await aiopath.exists(output_file):
                            LOGGER.info(
                                f"Merge successful with filter complex: {output_file}"
                            )
                            # Remove original files after successful merge
                            for f in all_files:
                                try:
                                    if await aiopath.exists(f) and f != output_file:
                                        LOGGER.debug(
                                            f"Removing original file after merge: {f}"
                                        )
                                        await remove(f)
                                except Exception as e:
                                    LOGGER.error(
                                        f"Error removing original file {f}: {e!s}"
                                    )
                            return output_file
                        LOGGER.warning(
                            "Filter complex approach failed, trying fallback approach"
                        )

            # If all approaches failed, try a fallback approach for video files
            if analysis["video_files"] and len(analysis["video_files"]) > 1:
                LOGGER.debug("Trying fallback approach for video files")
                # Create a temporary file list for concat demuxer
                concat_list_path = "concat_list.txt"
                with open(concat_list_path, "w") as f:
                    for file_path in sorted(analysis["video_files"]):
                        # Escape single quotes in file paths
                        escaped_path = file_path.replace("'", "'\\''")
                        f.write(f"file '{escaped_path}'\n")

                # Determine output path
                base_dir = os.path.dirname(analysis["video_files"][0])
                output_file = os.path.join(
                    base_dir, f"merged.{self.merge_output_format_video}"
                )

                # Use a simpler concat command with minimal options
                # Always preserve all tracks in the fallback approach
                LOGGER.debug(
                    "Using fallback approach with -map 0 to preserve all tracks"
                )
                cmd = [
                    "xtra",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    concat_list_path,
                    "-c",
                    "copy",
                    "-map",
                    "0",  # Map all streams to preserve all video, audio, and subtitle tracks
                    "-threads",
                    f"{max(1, cpu_no // 2)}",
                    output_file,
                ]

                # Calculate total size by summing individual file sizes
                total_size = 0
                for f in analysis["video_files"]:
                    total_size += await get_path_size(f)
                self.subsize = total_size
                res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                if res and await aiopath.exists(output_file):
                    LOGGER.info(
                        f"Merge successful with fallback approach: {output_file}"
                    )
                    # Remove original files after successful merge
                    for f in analysis["video_files"]:
                        try:
                            if await aiopath.exists(f) and f != output_file:
                                LOGGER.debug(
                                    f"Removing original file after merge: {f}"
                                )
                                await remove(f)
                        except Exception as e:
                            LOGGER.error(f"Error removing original file {f}: {e!s}")
                    return output_file

            # If all approaches failed, return original path
            LOGGER.warning("Merge failed: all approaches failed")
            return dl_path
        finally:
            cpu_eater_lock.release()

    async def proceed_watermark(self, dl_path, gid):
        # Skip if watermark is not enabled or no watermark text is provided
        # This follows the priority logic set in before_start method
        if not self.watermark_enabled or not self.watermark:
            # Log why watermark is not being applied at debug level
            if not self.watermark_enabled:
                LOGGER.debug("Watermark not applied: watermark is not enabled")
            elif not self.watermark:
                LOGGER.debug("Watermark not applied: no watermark text provided")
            return dl_path

        # Use the settings that were determined in before_start method
        # These already follow the correct priority logic
        key = self.watermark
        position = self.watermark_position
        size = self.watermark_size
        color = self.watermark_color
        font = self.watermark_font

        # Get the new watermark settings with the correct priority logic
        fast_mode = self.user_dict.get(
            "WATERMARK_FAST_MODE", Config.WATERMARK_FAST_MODE
        )
        maintain_quality = self.user_dict.get(
            "WATERMARK_MAINTAIN_QUALITY", Config.WATERMARK_MAINTAIN_QUALITY
        )
        opacity = self.user_dict.get("WATERMARK_OPACITY", Config.WATERMARK_OPACITY)

        # Determine the source of the watermark settings
        user_enabled = "WATERMARK_ENABLED" in self.user_dict and self.user_dict.get(
            "WATERMARK_ENABLED", False
        )
        owner_enabled = Config.WATERMARK_ENABLED

        # Determine the source of the settings for detailed logging
        settings_source = {
            "text": "user"
            if self.user_dict.get("WATERMARK_KEY")
            else ("owner" if Config.WATERMARK_KEY else "default"),
            "position": "user"
            if self.user_dict.get("WATERMARK_POSITION")
            else ("owner" if Config.WATERMARK_POSITION else "default"),
            "size": "user"
            if self.user_dict.get("WATERMARK_SIZE")
            else ("owner" if Config.WATERMARK_SIZE else "default"),
            "color": "user"
            if self.user_dict.get("WATERMARK_COLOR")
            else ("owner" if Config.WATERMARK_COLOR else "default"),
            "font": "user"
            if self.user_dict.get("WATERMARK_FONT")
            else ("owner" if Config.WATERMARK_FONT else "default"),
            "fast_mode": "user"
            if "WATERMARK_FAST_MODE" in self.user_dict
            else ("owner" if hasattr(Config, "WATERMARK_FAST_MODE") else "default"),
            "maintain_quality": "user"
            if "WATERMARK_MAINTAIN_QUALITY" in self.user_dict
            else (
                "owner"
                if hasattr(Config, "WATERMARK_MAINTAIN_QUALITY")
                else "default"
            ),
            "opacity": "user"
            if "WATERMARK_OPACITY" in self.user_dict
            else ("owner" if hasattr(Config, "WATERMARK_OPACITY") else "default"),
        }

        # Log detailed information about the sources of each setting at debug level
        LOGGER.debug(f"Watermark settings sources: {settings_source}")

        # Determine the overall source
        if user_enabled:
            source = "user"
        elif owner_enabled:
            source = "owner"
        else:
            source = "default"

        LOGGER.debug(
            f"Applying watermark with {source} settings: Text='{key}', Position={position}, Size={size}, Color={color}, Font={font}, "
            f"Fast Mode={fast_mode}, Quality={maintain_quality}, Opacity={opacity}"
        )

        ffmpeg = FFMpeg(self)
        checked = False
        if self.is_file:
            # Check if the file is a supported media type for watermarking
            if is_mkv(dl_path):  # is_mkv now checks for all supported media types
                cmd, temp_file = await get_watermark_cmd(
                    dl_path,
                    key,
                    position,
                    size,
                    color,
                    font,
                    fast_mode,
                    maintain_quality,
                    opacity,
                    self.audio_watermark_enabled,
                    self.audio_watermark_text,
                    self.subtitle_watermark_enabled,
                    self.subtitle_watermark_text,
                )
                if cmd:
                    if not checked:
                        checked = True
                        async with task_dict_lock:
                            task_dict[self.mid] = FFmpegStatus(
                                self,
                                ffmpeg,
                                gid,
                                "Watermark",
                            )
                        self.progress = False
                        await cpu_eater_lock.acquire()
                        self.progress = True
                    self.subsize = self.size
                    LOGGER.debug(f"Applying watermark to: {dl_path}")
                    res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                    if res:
                        os.replace(temp_file, dl_path)
                        LOGGER.info(f"Successfully applied watermark to: {dl_path}")
                    elif await aiopath.exists(temp_file):
                        os.remove(temp_file)
                        LOGGER.warning(f"Failed to apply watermark to: {dl_path}")
                else:
                    LOGGER.warning(
                        f"Could not generate watermark command for: {dl_path}"
                    )
        else:
            # Process all files in the directory
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    file_path = ospath.join(dirpath, file_)
                    if self.is_cancelled:
                        if checked:
                            cpu_eater_lock.release()
                        return ""

                    # Check if the file is a supported media type for watermarking
                    if is_mkv(
                        file_path
                    ):  # is_mkv now checks for all supported media types
                        cmd, temp_file = await get_watermark_cmd(
                            file_path,
                            key,
                            position,
                            size,
                            color,
                            font,
                            fast_mode,
                            maintain_quality,
                            opacity,
                            self.audio_watermark_enabled,
                            self.audio_watermark_text,
                            self.subtitle_watermark_enabled,
                            self.subtitle_watermark_text,
                        )
                        if cmd:
                            if not checked:
                                checked = True
                                async with task_dict_lock:
                                    task_dict[self.mid] = FFmpegStatus(
                                        self,
                                        ffmpeg,
                                        gid,
                                        "Watermark",
                                    )
                                self.progress = False
                                await cpu_eater_lock.acquire()
                                self.progress = True
                            LOGGER.debug(f"Applying watermark to: {file_path}")
                            self.subsize = await aiopath.getsize(file_path)
                            self.subname = file_
                            res = await ffmpeg.metadata_watermark_cmds(
                                cmd,
                                file_path,
                            )
                            if res:
                                os.replace(temp_file, file_path)
                                LOGGER.info(
                                    f"Successfully applied watermark to: {file_path}"
                                )
                            elif await aiopath.exists(temp_file):
                                os.remove(temp_file)
                                LOGGER.warning(
                                    f"Failed to apply watermark to: {file_path}"
                                )
                        else:
                            LOGGER.warning(
                                f"Could not generate watermark command for: {file_path}"
                            )
        if checked:
            cpu_eater_lock.release()
        return dl_path

    async def proceed_extract_tracks(self, dl_path, gid):
        """Extract media tracks from files using FFmpeg."""
        # Skip if extract is not enabled
        if not self.extract_enabled:
            LOGGER.info("Extract not applied: extract is not enabled")
            return dl_path

        # Check if any extract options are enabled
        if not (
            self.extract_video_enabled
            or self.extract_audio_enabled
            or self.extract_subtitle_enabled
            or self.extract_attachment_enabled
        ):
            LOGGER.info("Extract not applied: no extract options are enabled")
            return dl_path

        # Log extract settings
        LOGGER.info(
            f"Extract settings: delete_original={self.extract_delete_original}"
        )

        # Log video extract settings
        if self.extract_video_enabled:
            if (
                hasattr(self, "extract_video_indices")
                and self.extract_video_indices
                and isinstance(self.extract_video_indices, list)
                and self.extract_video_indices
            ):
                LOGGER.info(
                    f"Video extraction enabled: extracting specific video tracks with indices: {self.extract_video_indices}"
                )
            else:
                LOGGER.info("Video extraction enabled: extracting all video tracks")

        # Log audio extract settings
        if self.extract_audio_enabled:
            if (
                hasattr(self, "extract_audio_indices")
                and self.extract_audio_indices
                and isinstance(self.extract_audio_indices, list)
                and self.extract_audio_indices
            ):
                LOGGER.info(
                    f"Audio extraction enabled: extracting specific audio tracks with indices: {self.extract_audio_indices}"
                )
            else:
                LOGGER.info("Audio extraction enabled: extracting all audio tracks")

        # Log subtitle extract settings
        if self.extract_subtitle_enabled:
            if (
                hasattr(self, "extract_subtitle_indices")
                and self.extract_subtitle_indices
                and isinstance(self.extract_subtitle_indices, list)
                and self.extract_subtitle_indices
            ):
                LOGGER.info(
                    f"Subtitle extraction enabled: extracting specific subtitle tracks with indices: {self.extract_subtitle_indices}"
                )
            else:
                LOGGER.info(
                    "Subtitle extraction enabled: extracting all subtitle tracks"
                )

        # Log attachment extract settings
        if self.extract_attachment_enabled:
            if (
                hasattr(self, "extract_attachment_indices")
                and self.extract_attachment_indices
                and isinstance(self.extract_attachment_indices, list)
                and self.extract_attachment_indices
            ):
                LOGGER.info(
                    f"Attachment extraction enabled: extracting specific attachments with indices: {self.extract_attachment_indices}"
                )
            else:
                LOGGER.info(
                    "Attachment extraction enabled: extracting all attachment files"
                )

        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for extraction: {dl_path}")
            return dl_path

        # Log the full path for debugging
        LOGGER.debug(f"Extract input path: {dl_path}")

        # Initialize variables
        ffmpeg = FFMpeg(self)
        checked = False

        # Import the media_utils module
        from bot.helper.ext_utils.media_utils import proceed_extract

        # Determine codec settings based on user preferences
        video_codec = (
            self.extract_video_codec if self.extract_video_codec != "none" else None
        )
        audio_codec = (
            self.extract_audio_codec if self.extract_audio_codec != "none" else None
        )
        subtitle_codec = (
            self.extract_subtitle_codec
            if self.extract_subtitle_codec != "none"
            else None
        )
        maintain_quality = self.extract_maintain_quality

        # Get additional video settings
        video_quality = (
            self.extract_video_quality
            if self.extract_video_quality != "none"
            else None
        )
        video_preset = (
            self.extract_video_preset
            if self.extract_video_preset != "none"
            else None
        )
        video_bitrate = (
            self.extract_video_bitrate
            if self.extract_video_bitrate != "none"
            else None
        )
        video_resolution = (
            self.extract_video_resolution
            if self.extract_video_resolution != "none"
            else None
        )
        video_fps = (
            self.extract_video_fps if self.extract_video_fps != "none" else None
        )

        # Get additional audio settings
        audio_bitrate = (
            self.extract_audio_bitrate
            if self.extract_audio_bitrate != "none"
            else None
        )
        audio_channels = (
            self.extract_audio_channels
            if self.extract_audio_channels != "none"
            else None
        )
        audio_sampling = (
            self.extract_audio_sampling
            if self.extract_audio_sampling != "none"
            else None
        )
        audio_volume = (
            self.extract_audio_volume
            if self.extract_audio_volume != "none"
            else None
        )

        # Get additional subtitle settings
        subtitle_language = (
            self.extract_subtitle_language
            if self.extract_subtitle_language != "none"
            else None
        )
        subtitle_encoding = (
            self.extract_subtitle_encoding
            if self.extract_subtitle_encoding != "none"
            else None
        )
        subtitle_font = (
            self.extract_subtitle_font
            if self.extract_subtitle_font != "none"
            else None
        )
        subtitle_font_size = (
            self.extract_subtitle_font_size
            if self.extract_subtitle_font_size != "none"
            else None
        )

        # Get attachment settings
        attachment_filter = (
            self.extract_attachment_filter
            if self.extract_attachment_filter != "none"
            else None
        )

        if self.is_file:
            # Process a single file
            # Set up FFmpeg status
            if not checked:
                checked = True
                async with task_dict_lock:
                    task_dict[self.mid] = FFmpegStatus(
                        self,
                        ffmpeg,
                        gid,
                        "Extract",
                    )
                self.progress = False
                await cpu_eater_lock.acquire()
                self.progress = True

            self.subsize = self.size
            LOGGER.info(f"Extracting tracks from file: {dl_path}")

            # Use the proceed_extract function
            output_dir = ospath.dirname(dl_path)

            # Get format settings - ensure they're properly normalized
            video_format = (
                self.extract_video_format
                if hasattr(self, "extract_video_format")
                and self.extract_video_format
                and self.extract_video_format.lower() != "none"
                else None
            )
            audio_format = (
                self.extract_audio_format
                if hasattr(self, "extract_audio_format")
                and self.extract_audio_format
                and self.extract_audio_format.lower() != "none"
                else None
            )
            subtitle_format = (
                self.extract_subtitle_format
                if hasattr(self, "extract_subtitle_format")
                and self.extract_subtitle_format
                and self.extract_subtitle_format.lower() != "none"
                else None
            )
            attachment_format = (
                self.extract_attachment_format
                if hasattr(self, "extract_attachment_format")
                and self.extract_attachment_format
                and self.extract_attachment_format.lower() != "none"
                else None
            )

            # Log format settings
            if video_format:
                LOGGER.info(f"Using video format: {video_format}")
            if audio_format:
                LOGGER.info(f"Using audio format: {audio_format}")
            if subtitle_format:
                LOGGER.info(f"Using subtitle format: {subtitle_format}")
            if attachment_format:
                LOGGER.info(f"Using attachment format: {attachment_format}")

            extracted_files = await proceed_extract(
                dl_path,
                output_dir,
                self.extract_video_enabled,
                self.extract_audio_enabled,
                self.extract_subtitle_enabled,
                self.extract_attachment_enabled,
                video_codec,
                audio_codec,
                subtitle_codec,
                self.extract_video_index,
                self.extract_audio_index,
                self.extract_subtitle_index,
                self.extract_attachment_index,
                maintain_quality,
                "xtra",
                self.extract_delete_original,
                # Pass the indices lists as well
                video_indices=self.extract_video_indices,
                audio_indices=self.extract_audio_indices,
                subtitle_indices=self.extract_subtitle_indices,
                attachment_indices=self.extract_attachment_indices,
                # Pass format settings
                video_format=video_format,
                audio_format=audio_format,
                subtitle_format=subtitle_format,
                attachment_format=attachment_format,
                # Pass additional video settings
                video_quality=video_quality,
                video_preset=video_preset,
                video_bitrate=video_bitrate,
                video_resolution=video_resolution,
                video_fps=video_fps,
                # Pass additional audio settings
                audio_bitrate=audio_bitrate,
                audio_channels=audio_channels,
                audio_sampling=audio_sampling,
                audio_volume=audio_volume,
                # Pass additional subtitle settings
                subtitle_language=subtitle_language,
                subtitle_encoding=subtitle_encoding,
                subtitle_font=subtitle_font,
                subtitle_font_size=subtitle_font_size,
                # Pass attachment settings
                attachment_filter=attachment_filter,
            )

            # Check if extraction was successful
            if extracted_files:
                LOGGER.info(
                    f"Successfully extracted {len(extracted_files)} tracks from: {dl_path}"
                )
                for file in extracted_files:
                    LOGGER.debug(f"Extracted file: {file}")

                # If original file was deleted, return the directory instead
                if self.extract_delete_original and not await aiopath.exists(
                    dl_path
                ):
                    LOGGER.info(
                        f"Original file was deleted, returning directory: {output_dir}"
                    )
                    return output_dir
            else:
                LOGGER.warning(f"No tracks were extracted from: {dl_path}")
        else:
            # Process all files in the directory
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    file_path = ospath.join(dirpath, file_)
                    if self.is_cancelled:
                        if checked:
                            cpu_eater_lock.release()
                        return ""

                    # Set up FFmpeg status if not already done
                    if not checked:
                        checked = True
                        async with task_dict_lock:
                            task_dict[self.mid] = FFmpegStatus(
                                self,
                                ffmpeg,
                                gid,
                                "Extract",
                            )
                        self.progress = False
                        await cpu_eater_lock.acquire()
                        self.progress = True

                    LOGGER.info(f"Extracting tracks from file: {file_path}")
                    self.subsize = await aiopath.getsize(file_path)
                    self.subname = file_

                    # Use the proceed_extract function
                    output_dir = dirpath

                    # Get format settings - ensure they're properly normalized
                    video_format = (
                        self.extract_video_format
                        if hasattr(self, "extract_video_format")
                        and self.extract_video_format
                        and self.extract_video_format.lower() != "none"
                        else None
                    )
                    audio_format = (
                        self.extract_audio_format
                        if hasattr(self, "extract_audio_format")
                        and self.extract_audio_format
                        and self.extract_audio_format.lower() != "none"
                        else None
                    )
                    subtitle_format = (
                        self.extract_subtitle_format
                        if hasattr(self, "extract_subtitle_format")
                        and self.extract_subtitle_format
                        and self.extract_subtitle_format.lower() != "none"
                        else None
                    )
                    attachment_format = (
                        self.extract_attachment_format
                        if hasattr(self, "extract_attachment_format")
                        and self.extract_attachment_format
                        and self.extract_attachment_format.lower() != "none"
                        else None
                    )

                    extracted_files = await proceed_extract(
                        file_path,
                        output_dir,
                        self.extract_video_enabled,
                        self.extract_audio_enabled,
                        self.extract_subtitle_enabled,
                        self.extract_attachment_enabled,
                        video_codec,
                        audio_codec,
                        subtitle_codec,
                        self.extract_video_index,
                        self.extract_audio_index,
                        self.extract_subtitle_index,
                        self.extract_attachment_index,
                        maintain_quality,
                        "xtra",
                        self.extract_delete_original,
                        # Pass the indices lists as well
                        video_indices=self.extract_video_indices,
                        audio_indices=self.extract_audio_indices,
                        subtitle_indices=self.extract_subtitle_indices,
                        attachment_indices=self.extract_attachment_indices,
                        # Pass format settings
                        video_format=video_format,
                        audio_format=audio_format,
                        subtitle_format=subtitle_format,
                        attachment_format=attachment_format,
                        # Pass additional video settings
                        video_quality=video_quality,
                        video_preset=video_preset,
                        video_bitrate=video_bitrate,
                        video_resolution=video_resolution,
                        video_fps=video_fps,
                        # Pass additional audio settings
                        audio_bitrate=audio_bitrate,
                        audio_channels=audio_channels,
                        audio_sampling=audio_sampling,
                        audio_volume=audio_volume,
                        # Pass additional subtitle settings
                        subtitle_language=subtitle_language,
                        subtitle_encoding=subtitle_encoding,
                        subtitle_font=subtitle_font,
                        subtitle_font_size=subtitle_font_size,
                        # Pass attachment settings
                        attachment_filter=attachment_filter,
                    )

                    # Check if extraction was successful
                    if extracted_files:
                        LOGGER.info(
                            f"Successfully extracted {len(extracted_files)} tracks from: {file_path}"
                        )
                        for file in extracted_files:
                            LOGGER.debug(f"Extracted file: {file}")
                    else:
                        LOGGER.warning(f"No tracks were extracted from: {file_path}")

        if checked:
            cpu_eater_lock.release()
        return dl_path

    async def proceed_trim(self, dl_path, gid):
        # Skip if trim is not enabled
        if not self.trim_enabled:
            LOGGER.info("Trim not applied: trim is not enabled")
            return dl_path

        # Check if we have either trim parameters or start/end time
        if not self.trim and not hasattr(self, "trim_start_time"):
            LOGGER.info(
                "Trim not applied: no trim parameters or start/end time provided"
            )
            return dl_path

        # Check if file exists
        if not await aiopath.exists(dl_path):
            LOGGER.error(f"File not found for trimming: {dl_path}")
            return dl_path

        # Log the full path for debugging
        if self.trim:
            LOGGER.info(f"Trim parameters: {self.trim}")
        if hasattr(self, "trim_start_time"):
            LOGGER.info(f"Trim start time: {self.trim_start_time}")
        if hasattr(self, "trim_end_time"):
            LOGGER.info(f"Trim end time: {self.trim_end_time}")

        # Initialize variables
        ffmpeg = FFMpeg(self)
        checked = False

        # Determine video and audio codec settings based on user preferences
        video_codec = (
            self.trim_video_codec
            if self.trim_video_enabled
            and self.trim_video_codec
            and self.trim_video_codec.lower() != "none"
            else "none"
        )
        video_preset = (
            self.trim_video_preset
            if self.trim_video_enabled
            and self.trim_video_preset
            and self.trim_video_preset.lower() != "none"
            else "none"
        )
        video_format = (
            self.trim_video_format
            if self.trim_video_enabled
            and self.trim_video_format
            and self.trim_video_format.lower() != "none"
            else "none"
        )
        audio_codec = (
            self.trim_audio_codec
            if self.trim_audio_enabled
            and self.trim_audio_codec
            and self.trim_audio_codec.lower() != "none"
            else "none"
        )
        audio_preset = (
            self.trim_audio_preset
            if self.trim_audio_enabled
            and self.trim_audio_preset
            and self.trim_audio_preset.lower() != "none"
            else "none"
        )
        audio_format = (
            self.trim_audio_format
            if self.trim_audio_enabled
            and self.trim_audio_format
            and self.trim_audio_format.lower() != "none"
            else "none"
        )
        image_quality = (
            self.trim_image_quality
            if self.trim_image_enabled
            and self.trim_image_quality
            and self.trim_image_quality != 0
            else "none"
        )
        image_format = (
            self.trim_image_format
            if self.trim_image_enabled
            and self.trim_image_format
            and self.trim_image_format.lower() != "none"
            else "none"
        )
        document_quality = (
            self.trim_document_quality
            if self.trim_document_enabled
            and self.trim_document_quality
            and self.trim_document_quality != 0
            else "none"
        )
        document_format = (
            self.trim_document_format
            if self.trim_document_enabled
            and self.trim_document_format
            and self.trim_document_format.lower() != "none"
            else "none"
        )
        subtitle_encoding = (
            self.trim_subtitle_encoding
            if self.trim_subtitle_enabled
            and self.trim_subtitle_encoding
            and self.trim_subtitle_encoding.lower() != "none"
            else "none"
        )
        subtitle_format = (
            self.trim_subtitle_format
            if self.trim_subtitle_enabled
            and self.trim_subtitle_format
            and self.trim_subtitle_format.lower() != "none"
            else "none"
        )
        archive_format = (
            self.trim_archive_format
            if self.trim_archive_enabled
            and self.trim_archive_format
            and self.trim_archive_format.lower() != "none"
            else "none"
        )

        # Use the trim_delete_original setting which already includes command line flag handling
        delete_original = self.trim_delete_original

        if self.is_file:
            # Process a single file
            cmd, temp_file = await get_trim_cmd(
                dl_path,
                self.trim,
                video_codec,
                video_preset,
                video_format,
                audio_codec,
                audio_preset,
                audio_format,
                image_quality,
                image_format,
                document_quality,
                document_format,
                subtitle_encoding,
                subtitle_format,
                archive_format,
                getattr(self, "trim_start_time", None),
                getattr(self, "trim_end_time", None),
                delete_original,
            )

            if cmd:
                if not checked:
                    checked = True
                    async with task_dict_lock:
                        task_dict[self.mid] = FFmpegStatus(
                            self,
                            ffmpeg,
                            gid,
                            "Trim",
                        )
                    self.progress = False
                    await cpu_eater_lock.acquire()
                    self.progress = True

                self.subsize = self.size
                LOGGER.info(f"Trimming file: {dl_path}")

                # Check if this is a special trim command
                if cmd[0] == "srt_trim":
                    # Handle SRT trimming manually
                    res = await self.trim_srt_file(cmd[1], cmd[2], cmd[3], cmd[4])
                elif cmd[0] == "pdf_trim":
                    # Handle PDF trimming manually
                    res = await self.trim_pdf_file(cmd[1], cmd[2], cmd[3], cmd[4])
                else:
                    # Use FFmpeg for other files
                    res = await ffmpeg.ffmpeg_cmds(cmd, dl_path)

                # Check if the temp file exists after the command completes
                temp_file_exists = await aiopath.exists(temp_file)

                # Check if the temp file has valid content
                if temp_file_exists:
                    try:
                        temp_file_size = await aiopath.getsize(temp_file)
                        temp_file_valid = temp_file_size > 0
                    except Exception as e:
                        LOGGER.error(f"Error checking temp file size: {e}")
                        temp_file_valid = False
                else:
                    temp_file_valid = False

                # Handle the result based on the command output and temp file status
                if isinstance(res, list) and res:
                    # ffmpeg_cmds returns a list of output files on success
                    if temp_file_exists and temp_file_valid:
                        if delete_original:
                            # Replace the original file with the trimmed file
                            os.replace(temp_file, dl_path)
                            LOGGER.info(
                                f"Successfully trimmed file and replaced original: {dl_path}"
                            )
                        else:
                            # Keep both files
                            trimmed_path = f"{os.path.splitext(dl_path)[0]}.trimmed{os.path.splitext(temp_file)[1]}"
                            os.replace(temp_file, trimmed_path)
                            LOGGER.info(
                                f"Successfully trimmed file (keeping original): {trimmed_path}"
                            )
                    else:
                        LOGGER.error(
                            "Trim command succeeded but output file is not valid"
                        )
                elif res is True:
                    # Direct boolean success
                    if temp_file_exists and temp_file_valid:
                        if delete_original:
                            # Replace the original file with the trimmed file
                            os.replace(temp_file, dl_path)
                            LOGGER.info(
                                f"Successfully trimmed file and replaced original: {dl_path}"
                            )
                        else:
                            # Keep both files
                            trimmed_path = f"{os.path.splitext(dl_path)[0]}.trimmed{os.path.splitext(temp_file)[1]}"
                            os.replace(temp_file, trimmed_path)
                            LOGGER.info(
                                f"Successfully trimmed file (keeping original): {trimmed_path}"
                            )
                    else:
                        LOGGER.error(
                            "Trim command reported success but output file is not valid"
                        )
                elif await aiopath.exists(temp_file):
                    # Command failed but temp file exists
                    if temp_file_valid:
                        LOGGER.warning(
                            "Command failed but output file is valid, trying to use it anyway"
                        )
                        if delete_original:
                            # Replace the original file with the trimmed file
                            os.replace(temp_file, dl_path)
                            LOGGER.info(
                                f"Successfully trimmed file and replaced original: {dl_path}"
                            )
                        else:
                            # Keep both files
                            trimmed_path = f"{os.path.splitext(dl_path)[0]}.trimmed{os.path.splitext(temp_file)[1]}"
                            os.replace(temp_file, trimmed_path)
                            LOGGER.info(
                                f"Successfully trimmed file (keeping original): {trimmed_path}"
                            )
                    else:
                        # Temp file exists but is not valid
                        os.remove(temp_file)
                        LOGGER.warning(f"Failed to trim file: {dl_path}")
                else:
                    LOGGER.error(f"Failed to trim file: {dl_path}")
            else:
                LOGGER.warning(f"Could not generate trim command for: {dl_path}")
        else:
            # Process all files in the directory
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    file_path = ospath.join(dirpath, file_)
                    if self.is_cancelled:
                        if checked:
                            cpu_eater_lock.release()
                        return ""

                    # Generate trim command for the file
                    cmd, temp_file = await get_trim_cmd(
                        file_path,
                        self.trim,
                        video_codec,
                        video_preset,
                        video_format,
                        audio_codec,
                        audio_preset,
                        audio_format,
                        image_quality,
                        image_format,
                        document_quality,
                        document_format,
                        subtitle_encoding,
                        subtitle_format,
                        archive_format,
                        getattr(self, "trim_start_time", None),
                        getattr(self, "trim_end_time", None),
                        delete_original,
                    )

                    if cmd:
                        if not checked:
                            checked = True
                            async with task_dict_lock:
                                task_dict[self.mid] = FFmpegStatus(
                                    self,
                                    ffmpeg,
                                    gid,
                                    "Trim",
                                )
                            self.progress = False
                            await cpu_eater_lock.acquire()
                            self.progress = True

                        LOGGER.info(f"Trimming file: {file_path}")
                        self.subsize = await aiopath.getsize(file_path)
                        self.subname = file_

                        # Check if this is a special trim command
                        if cmd[0] == "srt_trim":
                            # Handle SRT trimming manually
                            res = await self.trim_srt_file(
                                cmd[1], cmd[2], cmd[3], cmd[4]
                            )
                        elif cmd[0] == "pdf_trim":
                            # Handle PDF trimming manually
                            res = await self.trim_pdf_file(
                                cmd[1], cmd[2], cmd[3], cmd[4]
                            )
                        else:
                            # Use FFmpeg for other files
                            res = await ffmpeg.ffmpeg_cmds(cmd, file_path)

                        # Check if the temp file exists after the command completes
                        temp_file_exists = await aiopath.exists(temp_file)

                        # Check if the temp file has valid content
                        if temp_file_exists:
                            try:
                                temp_file_size = await aiopath.getsize(temp_file)
                                temp_file_valid = temp_file_size > 0
                            except Exception as e:
                                LOGGER.error(f"Error checking temp file size: {e}")
                                temp_file_valid = False
                        else:
                            temp_file_valid = False

                        # Handle the result based on the command output and temp file status
                        if isinstance(res, list) and res:
                            # ffmpeg_cmds returns a list of output files on success
                            if temp_file_exists and temp_file_valid:
                                if delete_original:
                                    # Replace the original file with the trimmed file
                                    os.replace(temp_file, file_path)
                                    LOGGER.info(
                                        f"Successfully trimmed file and replaced original: {file_path}"
                                    )
                                else:
                                    # Keep both files
                                    trimmed_path = f"{os.path.splitext(file_path)[0]}.trimmed{os.path.splitext(temp_file)[1]}"
                                    os.replace(temp_file, trimmed_path)
                                    LOGGER.info(
                                        f"Successfully trimmed file (keeping original): {trimmed_path}"
                                    )
                            else:
                                LOGGER.error(
                                    f"FFmpeg command succeeded but temp file is not valid: {temp_file}"
                                )
                        elif res is True:
                            # Direct boolean success
                            if temp_file_exists and temp_file_valid:
                                if delete_original:
                                    # Replace the original file with the trimmed file
                                    os.replace(temp_file, file_path)
                                    LOGGER.info(
                                        f"Successfully trimmed file and replaced original: {file_path}"
                                    )
                                else:
                                    # Keep both files
                                    trimmed_path = f"{os.path.splitext(file_path)[0]}.trimmed{os.path.splitext(temp_file)[1]}"
                                    os.replace(temp_file, trimmed_path)
                                    LOGGER.info(
                                        f"Successfully trimmed file (keeping original): {trimmed_path}"
                                    )
                            else:
                                LOGGER.error(
                                    f"Command reported success but temp file is not valid: {temp_file}"
                                )
                        elif await aiopath.exists(temp_file):
                            # Command failed but temp file exists
                            if temp_file_valid:
                                LOGGER.warning(
                                    "Command failed but temp file is valid, trying to use it anyway"
                                )
                                if delete_original:
                                    # Replace the original file with the trimmed file
                                    os.replace(temp_file, file_path)
                                    LOGGER.info(
                                        f"Replaced original file with temp file despite command failure: {file_path}"
                                    )
                                else:
                                    # Keep both files
                                    trimmed_path = f"{os.path.splitext(file_path)[0]}.trimmed{os.path.splitext(temp_file)[1]}"
                                    os.replace(temp_file, trimmed_path)
                                    LOGGER.info(
                                        f"Kept temp file despite command failure: {trimmed_path}"
                                    )
                            else:
                                # Temp file exists but is not valid
                                os.remove(temp_file)
                                LOGGER.warning(
                                    f"Failed to trim file, removed invalid temp file: {file_path}"
                                )
                        else:
                            LOGGER.error(
                                f"Trim failed and no temp file was created for: {file_path}"
                            )
                    else:
                        LOGGER.warning(
                            f"Could not generate trim command for: {file_path}"
                        )

        if checked:
            cpu_eater_lock.release()

        return dl_path

    async def trim_pdf_file(
        self, input_file, start_page_str, end_page_str, output_file
    ):
        """Trim a PDF file by extracting a range of pages.

        Args:
            input_file: Path to the input PDF file
            start_page_str: Start page number (1-based)
            end_page_str: End page number (1-based)
            output_file: Path to the output PDF file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Import PyPDF2 for PDF manipulation
            try:
                from PyPDF2 import PdfReader, PdfWriter
            except ImportError:
                LOGGER.error("PyPDF2 is not installed. Cannot trim PDF files.")
                return False

            # Convert page numbers to integers
            try:
                start_page = int(start_page_str)
                # Handle special case for end page
                if end_page_str in {"999", "999:59:59"}:
                    end_page = None  # Will be set to the last page
                else:
                    end_page = int(end_page_str)
            except ValueError:
                LOGGER.error(
                    f"Invalid page numbers: start={start_page_str}, end={end_page_str}"
                )
                return False

            # Check if the file exists
            if not await aiopath.exists(input_file):
                LOGGER.error(f"Input PDF file not found: {input_file}")
                return False

            # Open the PDF file
            with open(input_file, "rb") as f:
                pdf = PdfReader(f)
                total_pages = len(pdf.pages)

                # Adjust page numbers (convert from 1-based to 0-based)
                start_page = max(
                    0, start_page - 1
                )  # Ensure start_page is at least 0
                if end_page is None:
                    end_page = total_pages - 1
                else:
                    end_page = min(
                        end_page - 1, total_pages - 1
                    )  # Ensure end_page doesn't exceed total pages

                LOGGER.info(
                    f"Trimming PDF from page {start_page + 1} to {end_page + 1} (total pages: {total_pages})"
                )

                # Create a new PDF with the selected pages
                pdf_writer = PdfWriter()
                for page_num in range(start_page, end_page + 1):
                    pdf_writer.add_page(pdf.pages[page_num])

                # Write the output file
                with open(output_file, "wb") as out_f:
                    pdf_writer.write(out_f)

            # Check if the output file was created
            if await aiopath.exists(output_file):
                LOGGER.info(
                    f"Successfully trimmed PDF file: {input_file} -> {output_file}"
                )
                LOGGER.info(
                    f"Extracted {end_page - start_page + 1} pages from the PDF"
                )
                return True
            LOGGER.error(f"Failed to create output PDF file: {output_file}")
            return False

        except Exception as e:
            LOGGER.error(f"Error trimming PDF file: {e}")
            import traceback

            LOGGER.error(traceback.format_exc())
            return False

    async def trim_srt_file(
        self, input_file, start_time_str, end_time_str, output_file
    ):
        """Trim an SRT subtitle file based on start and end times.

        Args:
            input_file: Path to the input SRT file
            start_time_str: Start time in HH:MM:SS format
            end_time_str: End time in HH:MM:SS format
            output_file: Path to the output SRT file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert time strings to seconds
            def time_to_seconds(time_str):
                # Handle empty or None time strings
                if not time_str:
                    return 0 if time_str == start_time_str else float("inf")

                # Handle different time formats
                if ":" not in time_str:
                    # Assume it's already in seconds
                    return float(time_str)

                # Handle HH:MM:SS format
                parts = time_str.split(":")
                if len(parts) == 3:
                    hours, minutes, seconds = parts
                    # Handle milliseconds if present
                    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                if len(parts) == 2:
                    minutes, seconds = parts
                    return int(minutes) * 60 + float(seconds)
                raise ValueError(f"Invalid time format: {time_str}")

            # Convert SRT timestamp to seconds
            def srt_time_to_seconds(time_str):
                # SRT format: 00:00:00,000
                hours, minutes, rest = time_str.split(":")
                seconds, milliseconds = rest.split(",")
                return (
                    int(hours) * 3600
                    + int(minutes) * 60
                    + int(seconds)
                    + int(milliseconds) / 1000
                )

            # Convert seconds to SRT timestamp
            def seconds_to_srt_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                seconds = seconds % 60
                whole_seconds = int(seconds)
                milliseconds = int((seconds - whole_seconds) * 1000)
                return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"

            start_seconds = time_to_seconds(start_time_str)
            end_seconds = (
                time_to_seconds(end_time_str) if end_time_str else float("inf")
            )

            LOGGER.info(
                f"Trimming SRT file from {start_seconds}s to {end_seconds if end_seconds != float('inf') else 'end'}s"
            )

            # Check if the file exists
            if not await aiopath.exists(input_file):
                LOGGER.error(f"Input subtitle file not found: {input_file}")
                return False

            # Read the input file
            with open(input_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Parse the SRT file
            subtitles = []
            blocks = content.strip().split("\n\n")

            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) >= 3:  # Valid subtitle block has at least 3 lines
                    try:
                        index = int(lines[0])
                        time_line = lines[1]
                        text = "\n".join(lines[2:])

                        # Parse the time line
                        start_time, end_time = time_line.split(" --> ")
                        start_sec = srt_time_to_seconds(start_time)
                        end_sec = srt_time_to_seconds(end_time)

                        # Check if this subtitle is within our trim range
                        if end_sec >= start_seconds and start_sec <= end_seconds:
                            # Adjust times if needed
                            start_sec = max(start_sec, start_seconds)
                            if end_sec > end_seconds and end_seconds != float("inf"):
                                end_sec = end_seconds

                            # Add to our list of subtitles to keep
                            subtitles.append(
                                {
                                    "index": index,
                                    "start": start_sec
                                    - start_seconds,  # Adjust to new timeline
                                    "end": end_sec
                                    - start_seconds,  # Adjust to new timeline
                                    "text": text,
                                }
                            )
                    except (ValueError, IndexError) as e:
                        LOGGER.warning(f"Error parsing subtitle block: {e}")
                        continue

            # Write the trimmed subtitles to the output file
            with open(output_file, "w", encoding="utf-8") as f:
                for i, sub in enumerate(subtitles, 1):
                    f.write(f"{i}\n")
                    f.write(
                        f"{seconds_to_srt_time(sub['start'])} --> {seconds_to_srt_time(sub['end'])}\n"
                    )
                    f.write(f"{sub['text']}\n\n")

            # Return success if we wrote any subtitles
            if subtitles:
                LOGGER.info(
                    f"Successfully trimmed SRT file: {input_file} -> {output_file}"
                )
                LOGGER.info(f"Kept {len(subtitles)} subtitles in the trimmed file")
                return True
            LOGGER.warning(f"No subtitles found in the trim range for: {input_file}")
            # Create an empty file to avoid errors
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("")
            return True

        except Exception as e:
            LOGGER.error(f"Error trimming SRT file: {e}")
            return False

    async def proceed_embed_thumb(self, dl_path, gid):
        thumb = self.e_thumb
        ffmpeg = FFMpeg(self)
        checked = False
        if self.is_file:
            if is_mkv(dl_path):
                cmd, temp_file = await get_embed_thumb_cmd(dl_path, thumb)
                if cmd:
                    if not checked:
                        checked = True
                        async with task_dict_lock:
                            task_dict[self.mid] = FFmpegStatus(
                                self,
                                ffmpeg,
                                gid,
                                "E_thumb",
                            )
                        self.progress = False
                        await cpu_eater_lock.acquire()
                        self.progress = True
                    self.subsize = self.size
                    res = await ffmpeg.metadata_watermark_cmds(cmd, dl_path)
                    if res:
                        os.replace(temp_file, dl_path)
                    elif await aiopath.exists(temp_file):
                        os.remove(temp_file)
        else:
            for dirpath, _, files in await sync_to_async(
                walk,
                dl_path,
                topdown=False,
            ):
                for file_ in files:
                    file_path = ospath.join(dirpath, file_)
                    if self.is_cancelled:
                        cpu_eater_lock.release()
                        return ""
                    if is_mkv(file_path):
                        cmd, temp_file = await get_embed_thumb_cmd(file_path, thumb)
                        if cmd:
                            if not checked:
                                checked = True
                                async with task_dict_lock:
                                    task_dict[self.mid] = FFmpegStatus(
                                        self,
                                        ffmpeg,
                                        gid,
                                        "E_thumb",
                                    )
                                self.progress = False
                                await cpu_eater_lock.acquire()
                                self.progress = True
                            LOGGER.info(f"Running cmd for: {file_path}")
                            self.subsize = await aiopath.getsize(file_path)
                            self.subname = file_
                            res = await ffmpeg.metadata_watermark_cmds(
                                cmd,
                                file_path,
                            )
                            if res:
                                os.replace(temp_file, file_path)
                            elif await aiopath.exists(temp_file):
                                os.remove(temp_file)
        if checked:
            cpu_eater_lock.release()
        return dl_path
