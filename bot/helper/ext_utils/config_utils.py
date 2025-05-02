from bot import user_data
from bot.core.config_manager import Config


async def reset_tool_configs(tool_name, database):
    """Reset all configurations related to a specific tool to their default values.

    Args:
        tool_name (str): The name of the tool to reset configurations for
        database: The database instance to update configurations
    """
    # Define prefixes for each tool
    tool_prefixes = {
        "watermark": ["WATERMARK_", "AUDIO_WATERMARK_", "SUBTITLE_WATERMARK_"],
        "merge": ["MERGE_", "CONCAT_DEMUXER_", "FILTER_COMPLEX_"],
        "convert": ["CONVERT_"],
        "compression": ["COMPRESSION_"],
        "trim": ["TRIM_"],
        "extract": ["EXTRACT_"],
        "metadata": ["METADATA_"],
        "ffmpeg": [],  # No specific configs for ffmpeg
        "sample": [],  # No specific configs for sample
    }

    # Define default values for each tool
    default_values = {
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
        # Audio watermark settings
        "AUDIO_WATERMARK_ENABLED": False,
        "AUDIO_WATERMARK_TEXT": "",
        "AUDIO_WATERMARK_VOLUME": 0.3,
        # Subtitle watermark settings
        "SUBTITLE_WATERMARK_ENABLED": False,
        "SUBTITLE_WATERMARK_TEXT": "",
        "SUBTITLE_WATERMARK_STYLE": "normal",
        # Merge Settings
        "MERGE_ENABLED": False,
        "MERGE_PRIORITY": 1,
        "MERGE_THREADING": True,
        "MERGE_THREAD_NUMBER": 4,
        "CONCAT_DEMUXER_ENABLED": True,
        "FILTER_COMPLEX_ENABLED": False,
        "MERGE_REMOVE_ORIGINAL": True,
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
        # Metadata Settings
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

    # Get prefixes for the specified tool
    prefixes = tool_prefixes.get(tool_name.lower(), [])
    if not prefixes:
        return

    # Step 1: Reset global (owner) configurations
    configs_to_reset = {}

    # Get all current configurations
    all_configs = Config.get_all()

    # Find configurations that match the tool's prefixes
    for key in all_configs:
        for prefix in prefixes:
            if key.startswith(prefix):
                # Get the default value if it exists, otherwise skip
                default_value = default_values.get(key)
                if default_value is not None:
                    configs_to_reset[key] = default_value
                    # Also update the Config class
                    Config.set(key, default_value)

    # Update the database if there are configurations to reset
    if configs_to_reset:
        await database.update_config(configs_to_reset)

    # Step 2: Reset user-specific configurations
    # Iterate through all users
    for user_id, user_dict in list(user_data.items()):
        user_configs_to_reset = False

        # Find user configurations that match the tool's prefixes
        for key in list(user_dict):
            for prefix in prefixes:
                if key.startswith(prefix):
                    # Remove the configuration from the user's data
                    user_dict.pop(key, None)
                    user_configs_to_reset = True

        # Update the database if there are user configurations to reset
        if user_configs_to_reset:
            await database.update_user_data(user_id)
