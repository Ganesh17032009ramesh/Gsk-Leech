import ast
import os
from importlib import import_module
from typing import Any, ClassVar


class Config:
    AS_DOCUMENT: bool = False
    AUTHORIZED_CHATS: str = ""
    BASE_URL: str = ""
    BASE_URL_PORT: int = 80
    BOT_TOKEN: str = ""
    CMD_SUFFIX: str = ""
    DATABASE_URL: str = ""
    DEFAULT_UPLOAD: str = "rc"
    EXCLUDED_EXTENSIONS: str = ""
    FFMPEG_CMDS: ClassVar[dict[str, list[str]]] = {}
    FILELION_API: str = ""
    GDRIVE_ID: str = ""
    INCOMPLETE_TASK_NOTIFIER: bool = False
    INDEX_URL: str = ""
    IMDB_TEMPLATE: str = ""
    JD_EMAIL: str = ""
    JD_PASS: str = ""
    IS_TEAM_DRIVE: bool = False
    LEECH_DUMP_CHAT: str = ""
    LEECH_FILENAME_PREFIX: str = ""
    LEECH_SUFFIX: str = ""
    LEECH_FONT: str = ""
    LEECH_FILENAME: str = ""
    LEECH_SPLIT_SIZE: int = 2097152000
    EQUAL_SPLITS: bool = False
    LOGIN_PASS: str = ""
    MEDIA_GROUP: bool = False
    HYBRID_LEECH: bool = False
    MUSIC_SEARCH_CHATS: ClassVar[list] = []
    NAME_SUBSTITUTE: str = r""
    OWNER_ID: int = 0
    QUEUE_ALL: int = 0
    QUEUE_DOWNLOAD: int = 0
    QUEUE_UPLOAD: int = 0
    RCLONE_FLAGS: str = ""
    RCLONE_PATH: str = ""
    RCLONE_SERVE_URL: str = ""
    RCLONE_SERVE_USER: str = ""
    RCLONE_SERVE_PASS: str = ""
    RCLONE_SERVE_PORT: int = 8080
    RSS_CHAT: str = ""
    RSS_DELAY: int = 600
    RSS_SIZE_LIMIT: int = 0
    STOP_DUPLICATE: bool = False
    STREAMWISH_API: str = ""
    SUDO_USERS: str = ""
    TELEGRAM_API: int = 0
    TELEGRAM_HASH: str = ""
    TG_PROXY: dict | None = None
    THUMBNAIL_LAYOUT: str = ""
    TORRENT_TIMEOUT: int = 0
    UPLOAD_PATHS: ClassVar[dict] = {}
    UPSTREAM_REPO: str = ""
    USENET_SERVERS: ClassVar[list] = []
    UPSTREAM_BRANCH: str = "main"
    USER_SESSION_STRING: str = ""
    USER_TRANSMISSION: bool = False
    USE_SERVICE_ACCOUNTS: bool = False
    WEB_PINCODE: bool = False
    YT_DLP_OPTIONS: ClassVar[dict] = {}

    # INKYPINKY
    # Global metadata settings
    METADATA_KEY: str = ""  # Legacy metadata key
    METADATA_ALL: str = ""  # Global metadata for all fields
    METADATA_TITLE: str = ""  # Global title metadata
    METADATA_AUTHOR: str = ""  # Global author metadata
    METADATA_COMMENT: str = ""  # Global comment metadata

    # Video track metadata
    METADATA_VIDEO_TITLE: str = ""  # Video track title metadata
    METADATA_VIDEO_AUTHOR: str = ""  # Video track author metadata
    METADATA_VIDEO_COMMENT: str = ""  # Video track comment metadata

    # Audio track metadata
    METADATA_AUDIO_TITLE: str = ""  # Audio track title metadata
    METADATA_AUDIO_AUTHOR: str = ""  # Audio track author metadata
    METADATA_AUDIO_COMMENT: str = ""  # Audio track comment metadata

    # Subtitle track metadata
    METADATA_SUBTITLE_TITLE: str = ""  # Subtitle track title metadata
    METADATA_SUBTITLE_AUTHOR: str = ""  # Subtitle track author metadata
    METADATA_SUBTITLE_COMMENT: str = ""  # Subtitle track comment metadata
    SET_COMMANDS: bool = True
    TOKEN_TIMEOUT: int = 0
    PAID_CHANNEL_ID: int = 0
    PAID_CHANNEL_LINK: str = ""
    DELETE_LINKS: bool = False
    FSUB_IDS: str = ""
    LOG_CHAT_ID: int = 0
    LEECH_FILENAME_CAPTION: str = ""
    HYDRA_IP: str = ""
    HYDRA_API_KEY: str = ""
    INSTADL_API: str = ""
    MEDIA_STORE: bool = False

    # Media Tools Settings
    MEDIA_TOOLS_ENABLED: bool = True
    MEDIAINFO_ENABLED: bool = False

    # Compression Settings
    COMPRESSION_ENABLED: bool = False
    COMPRESSION_PRIORITY: int = 4
    COMPRESSION_DELETE_ORIGINAL: bool = False

    # Video Compression Settings
    COMPRESSION_VIDEO_ENABLED: bool = False
    COMPRESSION_VIDEO_PRESET: str = "none"  # none, fast, medium, slow
    COMPRESSION_VIDEO_CRF: int = 0
    COMPRESSION_VIDEO_CODEC: str = "none"
    COMPRESSION_VIDEO_TUNE: str = "none"
    COMPRESSION_VIDEO_PIXEL_FORMAT: str = "none"
    COMPRESSION_VIDEO_FORMAT: str = (
        "none"  # Output format for video compression (e.g., mp4, mkv)
    )

    # Audio Compression Settings
    COMPRESSION_AUDIO_ENABLED: bool = False
    COMPRESSION_AUDIO_PRESET: str = "none"  # none, fast, medium, slow
    COMPRESSION_AUDIO_CODEC: str = "none"
    COMPRESSION_AUDIO_BITRATE: str = "none"
    COMPRESSION_AUDIO_CHANNELS: int = 0
    COMPRESSION_AUDIO_FORMAT: str = (
        "none"  # Output format for audio compression (e.g., mp3, aac)
    )

    # Image Compression Settings
    COMPRESSION_IMAGE_ENABLED: bool = False
    COMPRESSION_IMAGE_PRESET: str = "none"  # none, fast, medium, slow
    COMPRESSION_IMAGE_QUALITY: int = 0
    COMPRESSION_IMAGE_RESIZE: str = "none"
    COMPRESSION_IMAGE_FORMAT: str = (
        "none"  # Output format for image compression (e.g., jpg, png)
    )

    # Document Compression Settings
    COMPRESSION_DOCUMENT_ENABLED: bool = False
    COMPRESSION_DOCUMENT_PRESET: str = "none"  # none, fast, medium, slow
    COMPRESSION_DOCUMENT_DPI: int = 0
    COMPRESSION_DOCUMENT_FORMAT: str = (
        "none"  # Output format for document compression (e.g., pdf)
    )

    # Subtitle Compression Settings
    COMPRESSION_SUBTITLE_ENABLED: bool = False
    COMPRESSION_SUBTITLE_PRESET: str = "none"  # none, fast, medium, slow
    COMPRESSION_SUBTITLE_ENCODING: str = "none"
    COMPRESSION_SUBTITLE_FORMAT: str = (
        "none"  # Output format for subtitle compression (e.g., srt)
    )

    # Archive Compression Settings
    COMPRESSION_ARCHIVE_ENABLED: bool = False
    COMPRESSION_ARCHIVE_PRESET: str = "none"  # none, fast, medium, slow
    COMPRESSION_ARCHIVE_LEVEL: int = 0
    COMPRESSION_ARCHIVE_METHOD: str = "none"
    COMPRESSION_ARCHIVE_FORMAT: str = (
        "none"  # Output format for archive compression (e.g., zip, 7z)
    )

    # Trim Settings
    TRIM_ENABLED: bool = False
    TRIM_PRIORITY: int = 5
    TRIM_START_TIME: str = "00:00:00"
    TRIM_END_TIME: str = ""
    TRIM_DELETE_ORIGINAL: bool = False

    # Video Trim Settings
    TRIM_VIDEO_ENABLED: bool = False
    TRIM_VIDEO_CODEC: str = "none"  # none, copy, libx264, etc.
    TRIM_VIDEO_PRESET: str = "none"  # none, fast, medium, slow
    TRIM_VIDEO_FORMAT: str = (
        "none"  # Output format for video trimming (e.g., mp4, mkv)
    )

    # Audio Trim Settings
    TRIM_AUDIO_ENABLED: bool = False
    TRIM_AUDIO_CODEC: str = "none"  # none, copy, aac, etc.
    TRIM_AUDIO_PRESET: str = "none"  # none, fast, medium, slow
    TRIM_AUDIO_FORMAT: str = (
        "none"  # Output format for audio trimming (e.g., mp3, aac)
    )

    # Image Trim Settings
    TRIM_IMAGE_ENABLED: bool = False
    TRIM_IMAGE_QUALITY: int = 90
    TRIM_IMAGE_FORMAT: str = (
        "none"  # Output format for image trimming (e.g., jpg, png)
    )

    # Document Trim Settings
    TRIM_DOCUMENT_ENABLED: bool = False
    TRIM_DOCUMENT_QUALITY: int = 90
    TRIM_DOCUMENT_FORMAT: str = (
        "none"  # Output format for document trimming (e.g., pdf)
    )

    # Subtitle Trim Settings
    TRIM_SUBTITLE_ENABLED: bool = False
    TRIM_SUBTITLE_ENCODING: str = "none"
    TRIM_SUBTITLE_FORMAT: str = (
        "none"  # Output format for subtitle trimming (e.g., srt)
    )

    # Archive Trim Settings
    TRIM_ARCHIVE_ENABLED: bool = False
    TRIM_ARCHIVE_FORMAT: str = (
        "none"  # Output format for archive trimming (e.g., zip, 7z)
    )

    # Extract Settings
    EXTRACT_ENABLED: bool = False
    EXTRACT_PRIORITY: int = 6
    EXTRACT_DELETE_ORIGINAL: bool = True

    # Video Extract Settings
    EXTRACT_VIDEO_ENABLED: bool = False
    EXTRACT_VIDEO_CODEC: str = "none"
    EXTRACT_VIDEO_FORMAT: str = (
        "none"  # Output format for video extraction (e.g., mp4, mkv)
    )
    EXTRACT_VIDEO_INDEX: int | None = None
    EXTRACT_VIDEO_QUALITY: str = (
        "none"  # Quality setting for video extraction (e.g., crf value)
    )
    EXTRACT_VIDEO_PRESET: str = (
        "none"  # Preset for video encoding (e.g., medium, slow)
    )
    EXTRACT_VIDEO_BITRATE: str = "none"  # Bitrate for video encoding (e.g., 5M)
    EXTRACT_VIDEO_RESOLUTION: str = (
        "none"  # Resolution for video extraction (e.g., 1920x1080)
    )
    EXTRACT_VIDEO_FPS: str = "none"  # Frame rate for video extraction (e.g., 30)

    # Audio Extract Settings
    EXTRACT_AUDIO_ENABLED: bool = False
    EXTRACT_AUDIO_CODEC: str = "none"
    EXTRACT_AUDIO_FORMAT: str = (
        "none"  # Output format for audio extraction (e.g., mp3, aac)
    )
    EXTRACT_AUDIO_INDEX: int | None = None
    EXTRACT_AUDIO_BITRATE: str = "none"  # Bitrate for audio encoding (e.g., 320k)
    EXTRACT_AUDIO_CHANNELS: str = "none"  # Number of audio channels (e.g., 2)
    EXTRACT_AUDIO_SAMPLING: str = "none"  # Sampling rate for audio (e.g., 48000)
    EXTRACT_AUDIO_VOLUME: str = "none"  # Volume adjustment for audio (e.g., 1.5)

    # Subtitle Extract Settings
    EXTRACT_SUBTITLE_ENABLED: bool = False
    EXTRACT_SUBTITLE_CODEC: str = "none"
    EXTRACT_SUBTITLE_FORMAT: str = (
        "none"  # Output format for subtitle extraction (e.g., srt, ass)
    )
    EXTRACT_SUBTITLE_INDEX: int | None = None
    EXTRACT_SUBTITLE_LANGUAGE: str = (
        "none"  # Language code for subtitle extraction (e.g., eng)
    )
    EXTRACT_SUBTITLE_ENCODING: str = (
        "none"  # Character encoding for subtitles (e.g., UTF-8)
    )
    EXTRACT_SUBTITLE_FONT: str = (
        "none"  # Font for subtitles (for formats that support it)
    )
    EXTRACT_SUBTITLE_FONT_SIZE: str = "none"  # Font size for subtitles

    # Attachment Extract Settings
    EXTRACT_ATTACHMENT_ENABLED: bool = False
    EXTRACT_ATTACHMENT_FORMAT: str = (
        "none"  # Output format for attachment extraction (e.g., png, jpg)
    )
    EXTRACT_ATTACHMENT_INDEX: int | None = None
    EXTRACT_ATTACHMENT_FILTER: str = (
        "none"  # Filter for attachment extraction (e.g., *.ttf)
    )

    # Extract Quality Settings
    EXTRACT_MAINTAIN_QUALITY: bool = True

    # Convert Settings
    CONVERT_ENABLED: bool = False
    CONVERT_PRIORITY: int = 3
    CONVERT_DELETE_ORIGINAL: bool = False

    # Video Convert Settings
    CONVERT_VIDEO_ENABLED: bool = False
    CONVERT_VIDEO_FORMAT: str = "none"
    CONVERT_VIDEO_CODEC: str = "none"
    CONVERT_VIDEO_QUALITY: str = "none"
    CONVERT_VIDEO_CRF: int = 0
    CONVERT_VIDEO_PRESET: str = "none"
    CONVERT_VIDEO_MAINTAIN_QUALITY: bool = True
    CONVERT_VIDEO_RESOLUTION: str = "none"
    CONVERT_VIDEO_FPS: str = "none"

    # Audio Convert Settings
    CONVERT_AUDIO_ENABLED: bool = False
    CONVERT_AUDIO_FORMAT: str = "none"
    CONVERT_AUDIO_CODEC: str = "none"
    CONVERT_AUDIO_BITRATE: str = "none"
    CONVERT_AUDIO_CHANNELS: int = 0
    CONVERT_AUDIO_SAMPLING: int = 0
    CONVERT_AUDIO_VOLUME: float = 0.0

    # Subtitle Convert Settings
    CONVERT_SUBTITLE_ENABLED: bool = False
    CONVERT_SUBTITLE_FORMAT: str = "none"
    CONVERT_SUBTITLE_ENCODING: str = "none"
    CONVERT_SUBTITLE_LANGUAGE: str = "none"

    # Document Convert Settings
    CONVERT_DOCUMENT_ENABLED: bool = False
    CONVERT_DOCUMENT_FORMAT: str = "none"
    CONVERT_DOCUMENT_QUALITY: int = 0
    CONVERT_DOCUMENT_DPI: int = 0

    # Archive Convert Settings
    CONVERT_ARCHIVE_ENABLED: bool = False
    CONVERT_ARCHIVE_FORMAT: str = "none"
    CONVERT_ARCHIVE_LEVEL: int = 0
    CONVERT_ARCHIVE_METHOD: str = "none"

    # Watermark Settings
    WATERMARK_ENABLED: bool = False
    WATERMARK_KEY: str = ""
    WATERMARK_POSITION: str = "top_left"
    WATERMARK_SIZE: int = 20
    WATERMARK_COLOR: str = "white"
    WATERMARK_FONT: str = "default.otf"
    WATERMARK_PRIORITY: int = 2
    WATERMARK_THREADING: bool = True
    WATERMARK_THREAD_NUMBER: int = 4
    WATERMARK_FAST_MODE: bool = True
    WATERMARK_OPACITY: float = 1.0
    WATERMARK_MAINTAIN_QUALITY: bool = True

    # Audio Watermark Settings
    AUDIO_WATERMARK_ENABLED: bool = False
    AUDIO_WATERMARK_TEXT: str = ""
    AUDIO_WATERMARK_VOLUME: float = 0.3

    # Subtitle Watermark Settings
    SUBTITLE_WATERMARK_ENABLED: bool = False
    SUBTITLE_WATERMARK_TEXT: str = ""
    SUBTITLE_WATERMARK_STYLE: str = "normal"

    # Merge Settings
    MERGE_ENABLED: bool = False
    MERGE_PRIORITY: int = 1
    MERGE_THREADING: bool = True
    MERGE_THREAD_NUMBER: int = 4
    CONCAT_DEMUXER_ENABLED: bool = True
    FILTER_COMPLEX_ENABLED: bool = False

    # Output formats
    MERGE_OUTPUT_FORMAT_VIDEO: str = "mkv"
    MERGE_OUTPUT_FORMAT_AUDIO: str = "mp3"
    MERGE_OUTPUT_FORMAT_IMAGE: str = "jpg"
    MERGE_OUTPUT_FORMAT_DOCUMENT: str = "pdf"
    MERGE_OUTPUT_FORMAT_SUBTITLE: str = "srt"

    # Video settings
    MERGE_VIDEO_CODEC: str = "none"
    MERGE_VIDEO_QUALITY: str = "none"
    MERGE_VIDEO_PRESET: str = "none"
    MERGE_VIDEO_CRF: int = 0
    MERGE_VIDEO_PIXEL_FORMAT: str = "none"
    MERGE_VIDEO_TUNE: str = "none"
    MERGE_VIDEO_FASTSTART: bool = False

    # Audio settings
    MERGE_AUDIO_CODEC: str = "none"
    MERGE_AUDIO_BITRATE: str = "none"
    MERGE_AUDIO_CHANNELS: int = 0
    MERGE_AUDIO_SAMPLING: str = "none"
    MERGE_AUDIO_VOLUME: float = 0.0

    # Image settings
    MERGE_IMAGE_MODE: str = "none"
    MERGE_IMAGE_COLUMNS: int = 0
    MERGE_IMAGE_QUALITY: int = 0
    MERGE_IMAGE_DPI: int = 0
    MERGE_IMAGE_RESIZE: str = "none"
    MERGE_IMAGE_BACKGROUND: str = "none"

    # Subtitle settings
    MERGE_SUBTITLE_ENCODING: str = "none"
    MERGE_SUBTITLE_FONT: str = "none"
    MERGE_SUBTITLE_FONT_SIZE: int = 0
    MERGE_SUBTITLE_FONT_COLOR: str = "none"
    MERGE_SUBTITLE_BACKGROUND: str = "none"

    # Document settings
    MERGE_DOCUMENT_PAPER_SIZE: str = "none"
    MERGE_DOCUMENT_ORIENTATION: str = "none"
    MERGE_DOCUMENT_MARGIN: int = 0

    # General settings
    MERGE_REMOVE_ORIGINAL: bool = True
    MERGE_METADATA_TITLE: str = "none"
    MERGE_METADATA_AUTHOR: str = "none"
    MERGE_METADATA_COMMENT: str = "none"

    # Resource Management Settings
    PIL_MEMORY_LIMIT: int = 2048

    # Auto Restart Settings
    AUTO_RESTART_ENABLED: bool = False
    AUTO_RESTART_INTERVAL: int = 24  # in hours

    # Task Monitoring Settings
    TASK_MONITOR_ENABLED: bool = True
    TASK_MONITOR_INTERVAL: int = 60  # in seconds
    TASK_MONITOR_CONSECUTIVE_CHECKS: int = 3
    TASK_MONITOR_SPEED_THRESHOLD: int = 50  # in KB/s
    TASK_MONITOR_ELAPSED_THRESHOLD: int = 3600  # in seconds (1 hour)
    TASK_MONITOR_ETA_THRESHOLD: int = 86400  # in seconds (24 hours)
    TASK_MONITOR_WAIT_TIME: int = 600  # in seconds (10 minutes)
    TASK_MONITOR_COMPLETION_THRESHOLD: int = 14400  # in seconds (4 hours)
    TASK_MONITOR_CPU_HIGH: int = 90  # percentage
    TASK_MONITOR_CPU_LOW: int = 40  # percentage
    TASK_MONITOR_MEMORY_HIGH: int = 75  # percentage
    TASK_MONITOR_MEMORY_LOW: int = 60  # percentage

    # Truecaller API Settings
    TRUECALLER_API_URL: str = ""

    # Extra Modules Settings
    ENABLE_EXTRA_MODULES: bool = True

    # AI Settings
    # Default AI Provider (mistral, deepseek, chatgpt, gemini)
    DEFAULT_AI_PROVIDER: str = "mistral"

    # Mistral AI Settings
    MISTRAL_API_KEY: str = ""
    MISTRAL_API_URL: str = ""

    # DeepSeek AI Settings
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_URL: str = ""

    # ChatGPT Settings
    CHATGPT_API_KEY: str = ""
    CHATGPT_API_URL: str = ""

    # Gemini AI Settings
    GEMINI_API_KEY: str = ""
    GEMINI_API_URL: str = ""

    @classmethod
    def get(cls, key):
        return getattr(cls, key) if hasattr(cls, key) else None

    @classmethod
    def set(cls, key, value):
        if hasattr(cls, key):
            setattr(cls, key, value)
        else:
            raise KeyError(f"{key} is not a valid configuration key.")

    @classmethod
    def get_all(cls):
        return {
            key: getattr(cls, key)
            for key in sorted(cls.__dict__)
            if not key.startswith("__") and not callable(getattr(cls, key))
        }

    @classmethod
    def load(cls):
        try:
            settings = import_module("config")
        except ModuleNotFoundError:
            return
        else:
            for attr in dir(settings):
                if hasattr(cls, attr):
                    value = getattr(settings, attr)
                    if not value:
                        continue
                    if isinstance(value, str):
                        value = value.strip()
                    if attr == "DEFAULT_UPLOAD" and value != "gd":
                        value = "rc"
                    elif (
                        attr
                        in [
                            "BASE_URL",
                            "RCLONE_SERVE_URL",
                            "INDEX_URL",
                        ]
                        and value
                    ):
                        value = value.strip("/")
                    elif attr == "USENET_SERVERS":
                        try:
                            if not value[0].get("host"):
                                continue
                        except Exception:
                            continue
                    setattr(cls, attr, value)

    @classmethod
    def load_dict(cls, config_dict):
        for key, value in config_dict.items():
            if hasattr(cls, key):
                if key == "DEFAULT_UPLOAD" and value != "gd":
                    value = "rc"
                elif (
                    key
                    in [
                        "BASE_URL",
                        "RCLONE_SERVE_URL",
                        "INDEX_URL",
                    ]
                    and value
                ):
                    value = value.strip("/")
                elif key == "USENET_SERVERS":
                    try:
                        if not value[0].get("host"):
                            value = []
                    except Exception:
                        value = []
                setattr(cls, key, value)


class SystemEnv:
    @classmethod
    def load(cls):
        config_vars = Config.get_all()
        for key in config_vars:
            env_value = os.getenv(key)
            if env_value is not None:
                converted_value = cls._convert_type(key, env_value)
                Config.set(key, converted_value)

    @classmethod
    def _convert_type(cls, key: str, value: str) -> Any:
        original_value = getattr(Config, key, None)

        if original_value is None:
            return value

        if isinstance(original_value, bool):
            return value.lower() in ("true", "1", "yes")

        if isinstance(original_value, int):
            try:
                return int(value)
            except ValueError:
                return original_value

        if isinstance(original_value, float):
            try:
                return float(value)
            except ValueError:
                return original_value

        if isinstance(original_value, list):
            return value.split(",")

        if isinstance(original_value, dict):
            try:
                return ast.literal_eval(value)
            except (SyntaxError, ValueError):
                return original_value

        return value
