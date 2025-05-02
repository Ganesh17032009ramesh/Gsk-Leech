import logging
from asyncio import sleep
from functools import partial

from pyrogram import filters
from pyrogram.filters import create
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

from bot import user_data
from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.ext_utils.db_handler import database
from bot.helper.ext_utils.help_messages import media_tools_text
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_message,
    edit_message,
    send_message,
)

LOGGER = logging.getLogger(__name__)

handler_dict = {}
merge_config_page = 0  # Global variable to track merge_config page


async def get_media_tools_settings(from_user, stype="main", page_no=0):
    """Get media tools settings for a user."""
    user_id = from_user.id
    user_name = from_user.mention(style="html")
    buttons = ButtonMaker()
    user_dict = user_data.get(user_id, {})
    text = ""  # Initialize text variable to avoid UnboundLocalError

    if stype == "main":
        # Main Media Tools menu - only show enabled tools
        from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

        if is_media_tool_enabled("watermark"):
            buttons.data_button("Watermark", f"mediatools {user_id} watermark")

        if is_media_tool_enabled("merge"):
            buttons.data_button("Merge", f"mediatools {user_id} merge")

        if is_media_tool_enabled("convert"):
            buttons.data_button("Convert", f"mediatools {user_id} convert")

        if is_media_tool_enabled("compression"):
            buttons.data_button("Compression", f"mediatools {user_id} compression")

        if is_media_tool_enabled("trim"):
            buttons.data_button("Trim", f"mediatools {user_id} trim")

        if is_media_tool_enabled("extract"):
            buttons.data_button("Extract", f"mediatools {user_id} extract")

        buttons.data_button("Help", f"mediatools {user_id} help")
        buttons.data_button("Remove All", f"mediatools {user_id} remove_all")
        buttons.data_button("Reset All", f"mediatools {user_id} reset_all")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Check if watermark is enabled for the user
        user_watermark_enabled = user_dict.get("WATERMARK_ENABLED", False)
        owner_watermark_enabled = Config.WATERMARK_ENABLED

        if user_watermark_enabled:
            watermark_status = "✅ Enabled (User)"
        elif owner_watermark_enabled:
            watermark_status = "✅ Enabled (Global)"
        else:
            watermark_status = "❌ Disabled"

        # Get watermark text based on priority
        user_has_text = "WATERMARK_KEY" in user_dict and user_dict["WATERMARK_KEY"]
        owner_has_text = Config.WATERMARK_KEY

        if user_has_text:
            watermark_text = f"{user_dict['WATERMARK_KEY']} (User)"
        elif (user_watermark_enabled and owner_has_text) or (
            owner_watermark_enabled and owner_has_text
        ):
            watermark_text = f"{Config.WATERMARK_KEY} (Global)"
        else:
            watermark_text = "None"

        # Check if merge is enabled for the user
        user_merge_enabled = user_dict.get("MERGE_ENABLED", False)
        owner_merge_enabled = Config.MERGE_ENABLED

        if user_merge_enabled:
            merge_status = "✅ Enabled (User)"
        elif owner_merge_enabled:
            merge_status = "✅ Enabled (Global)"
        else:
            merge_status = "❌ Disabled"

        # Check if convert is enabled for the user
        user_convert_enabled = user_dict.get("CONVERT_ENABLED", False)
        owner_convert_enabled = (
            Config.CONVERT_ENABLED if hasattr(Config, "CONVERT_ENABLED") else False
        )

        if user_convert_enabled:
            convert_status = "✅ Enabled (User)"
        elif owner_convert_enabled:
            convert_status = "✅ Enabled (Global)"
        else:
            convert_status = "❌ Disabled"

        # Get video convert enabled status
        video_convert_enabled = user_dict.get("CONVERT_VIDEO_ENABLED", False)
        owner_video_enabled = (
            hasattr(Config, "CONVERT_VIDEO_ENABLED") and Config.CONVERT_VIDEO_ENABLED
        )

        if "CONVERT_VIDEO_ENABLED" in user_dict:
            if video_convert_enabled:
                video_enabled_status = "✅ Enabled (User)"
            else:
                video_enabled_status = "❌ Disabled (User)"
        elif owner_video_enabled:
            video_enabled_status = "✅ Enabled (Global)"
        else:
            video_enabled_status = "❌ Disabled"

        # Get audio convert enabled status
        audio_convert_enabled = user_dict.get("CONVERT_AUDIO_ENABLED", False)
        owner_audio_enabled = (
            hasattr(Config, "CONVERT_AUDIO_ENABLED") and Config.CONVERT_AUDIO_ENABLED
        )

        if "CONVERT_AUDIO_ENABLED" in user_dict:
            if audio_convert_enabled:
                audio_enabled_status = "✅ Enabled (User)"
            else:
                audio_enabled_status = "❌ Disabled (User)"
        elif owner_audio_enabled:
            audio_enabled_status = "✅ Enabled (Global)"
        else:
            audio_enabled_status = "❌ Disabled"

        # Check if compression is enabled for the user
        user_compression_enabled = user_dict.get("COMPRESSION_ENABLED", False)
        owner_compression_enabled = (
            Config.COMPRESSION_ENABLED
            if hasattr(Config, "COMPRESSION_ENABLED")
            else False
        )

        if user_compression_enabled:
            compression_status = "✅ Enabled (User)"
        elif owner_compression_enabled:
            compression_status = "✅ Enabled (Global)"
        else:
            compression_status = "❌ Disabled"

        # Get video compression enabled status
        video_compression_enabled = user_dict.get("COMPRESSION_VIDEO_ENABLED", False)
        owner_video_compression_enabled = (
            hasattr(Config, "COMPRESSION_VIDEO_ENABLED")
            and Config.COMPRESSION_VIDEO_ENABLED
        )

        if "COMPRESSION_VIDEO_ENABLED" in user_dict:
            if video_compression_enabled:
                video_compression_status = "✅ Enabled (User)"
            else:
                video_compression_status = "❌ Disabled (User)"
        elif owner_video_compression_enabled:
            video_compression_status = "✅ Enabled (Global)"
        else:
            video_compression_status = "❌ Disabled"

        # Get audio compression enabled status
        audio_compression_enabled = user_dict.get("COMPRESSION_AUDIO_ENABLED", False)
        owner_audio_compression_enabled = (
            hasattr(Config, "COMPRESSION_AUDIO_ENABLED")
            and Config.COMPRESSION_AUDIO_ENABLED
        )

        if "COMPRESSION_AUDIO_ENABLED" in user_dict:
            if audio_compression_enabled:
                audio_compression_status = "✅ Enabled (User)"
            else:
                audio_compression_status = "❌ Disabled (User)"
        elif owner_audio_compression_enabled:
            audio_compression_status = "✅ Enabled (Global)"
        else:
            audio_compression_status = "❌ Disabled"

        # Check if trim is enabled for the user
        user_trim_enabled = user_dict.get("TRIM_ENABLED", False)
        owner_trim_enabled = (
            Config.TRIM_ENABLED if hasattr(Config, "TRIM_ENABLED") else False
        )

        if user_trim_enabled:
            trim_status = "✅ Enabled (User)"
        elif owner_trim_enabled:
            trim_status = "✅ Enabled (Global)"
        else:
            trim_status = "❌ Disabled"

        # Get video trim enabled status
        video_trim_enabled = user_dict.get("TRIM_VIDEO_ENABLED", False)
        owner_video_trim_enabled = (
            hasattr(Config, "TRIM_VIDEO_ENABLED") and Config.TRIM_VIDEO_ENABLED
        )

        if "TRIM_VIDEO_ENABLED" in user_dict:
            if video_trim_enabled:
                video_trim_status = "✅ Enabled (User)"
            else:
                video_trim_status = "❌ Disabled (User)"
        elif owner_video_trim_enabled:
            video_trim_status = "✅ Enabled (Global)"
        else:
            video_trim_status = "❌ Disabled"

        # Get audio trim enabled status
        audio_trim_enabled = user_dict.get("TRIM_AUDIO_ENABLED", False)
        owner_audio_trim_enabled = (
            hasattr(Config, "TRIM_AUDIO_ENABLED") and Config.TRIM_AUDIO_ENABLED
        )

        if "TRIM_AUDIO_ENABLED" in user_dict:
            if audio_trim_enabled:
                audio_trim_status = "✅ Enabled (User)"
            else:
                audio_trim_status = "❌ Disabled (User)"
        elif owner_audio_trim_enabled:
            audio_trim_status = "✅ Enabled (Global)"
        else:
            audio_trim_status = "❌ Disabled"

        # Get extract status
        extract_enabled = user_dict.get("EXTRACT_ENABLED", False)
        owner_extract_enabled = (
            hasattr(Config, "EXTRACT_ENABLED") and Config.EXTRACT_ENABLED
        )

        if extract_enabled:
            extract_status = "✅ Enabled (User)"
        elif owner_extract_enabled:
            extract_status = "✅ Enabled (Global)"
        else:
            extract_status = "❌ Disabled"

        # Get extract video status
        video_extract_enabled = user_dict.get("EXTRACT_VIDEO_ENABLED", False)
        owner_video_extract_enabled = (
            hasattr(Config, "EXTRACT_VIDEO_ENABLED") and Config.EXTRACT_VIDEO_ENABLED
        )

        if "EXTRACT_VIDEO_ENABLED" in user_dict:
            if video_extract_enabled:
                video_extract_status = "✅ Enabled (User)"
            else:
                video_extract_status = "❌ Disabled (User)"
        elif owner_video_extract_enabled:
            video_extract_status = "✅ Enabled (Global)"
        else:
            video_extract_status = "❌ Disabled"

        # Get extract audio status
        audio_extract_enabled = user_dict.get("EXTRACT_AUDIO_ENABLED", False)
        owner_audio_extract_enabled = (
            hasattr(Config, "EXTRACT_AUDIO_ENABLED") and Config.EXTRACT_AUDIO_ENABLED
        )

        if "EXTRACT_AUDIO_ENABLED" in user_dict:
            if audio_extract_enabled:
                audio_extract_status = "✅ Enabled (User)"
            else:
                audio_extract_status = "❌ Disabled (User)"
        elif owner_audio_extract_enabled:
            audio_extract_status = "✅ Enabled (Global)"
        else:
            audio_extract_status = "❌ Disabled"

        text = f"""⌬ <b>Media Tools Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Watermark</b> → {watermark_status}
┠ <b>Watermark Text</b> → <code>{watermark_text}</code>
┃
┠ <b>Merge</b> → {merge_status}
┃
┠ <b>Convert</b> → {convert_status}
┠ <b>Video Convert</b> → {video_enabled_status}
┠ <b>Audio Convert</b> → {audio_enabled_status}
┃
┠ <b>Compression</b> → {compression_status}
┠ <b>Video Compression</b> → {video_compression_status}
┠ <b>Audio Compression</b> → {audio_compression_status}
┃
┠ <b>Trim</b> → {trim_status}
┠ <b>Video Trim</b> → {video_trim_status}
┠ <b>Audio Trim</b> → {audio_trim_status}
┃
┠ <b>Extract</b> → {extract_status}
┠ <b>Video Extract</b> → {video_extract_status}
┠ <b>Audio Extract</b> → {audio_extract_status}
┃
┖ <b>Priority</b> → {user_dict.get("MEDIA_TOOLS_PRIORITY", "Default Order")}"""

    elif stype == "watermark":
        # Watermark settings menu
        watermark_enabled = user_dict.get("WATERMARK_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if watermark_enabled else "❌ Disabled",
            f"mediatools {user_id} tog WATERMARK_ENABLED {'f' if watermark_enabled else 't'}",
        )
        buttons.data_button("Configure", f"mediatools {user_id} watermark_config")
        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu WATERMARK_PRIORITY"
        )
        buttons.data_button("Reset", f"mediatools {user_id} reset_watermark")
        buttons.data_button("Remove", f"mediatools {user_id} remove_watermark")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get watermark text based on priority
        user_has_text = "WATERMARK_KEY" in user_dict and user_dict["WATERMARK_KEY"]
        owner_has_text = Config.WATERMARK_KEY

        if user_has_text:
            watermark_text = f"{user_dict['WATERMARK_KEY']} (User)"
        elif (watermark_enabled and owner_has_text) or (
            Config.WATERMARK_ENABLED and owner_has_text
        ):
            watermark_text = f"{Config.WATERMARK_KEY} (Global)"
        else:
            watermark_text = "None"

        # Get watermark position based on priority
        user_has_position = (
            "WATERMARK_POSITION" in user_dict and user_dict["WATERMARK_POSITION"]
        )
        owner_has_position = Config.WATERMARK_POSITION

        if user_has_position:
            watermark_position = f"{user_dict['WATERMARK_POSITION']} (User)"
        elif (watermark_enabled and owner_has_position) or (
            Config.WATERMARK_ENABLED and owner_has_position
        ):
            watermark_position = f"{Config.WATERMARK_POSITION} (Global)"
        else:
            watermark_position = "top_left (Default)"

        # Get watermark size based on priority
        user_has_size = "WATERMARK_SIZE" in user_dict and user_dict["WATERMARK_SIZE"]
        owner_has_size = Config.WATERMARK_SIZE

        if user_has_size:
            watermark_size = f"{user_dict['WATERMARK_SIZE']} (User)"
        elif (watermark_enabled and owner_has_size) or (
            Config.WATERMARK_ENABLED and owner_has_size
        ):
            watermark_size = f"{Config.WATERMARK_SIZE} (Global)"
        else:
            watermark_size = "20 (Default)"

        # Get watermark color based on priority
        user_has_color = (
            "WATERMARK_COLOR" in user_dict and user_dict["WATERMARK_COLOR"]
        )
        owner_has_color = Config.WATERMARK_COLOR

        if user_has_color:
            watermark_color = f"{user_dict['WATERMARK_COLOR']} (User)"
        elif (watermark_enabled and owner_has_color) or (
            Config.WATERMARK_ENABLED and owner_has_color
        ):
            watermark_color = f"{Config.WATERMARK_COLOR} (Global)"
        else:
            watermark_color = "white (Default)"

        # Get watermark font based on priority
        user_has_font = "WATERMARK_FONT" in user_dict and user_dict["WATERMARK_FONT"]
        owner_has_font = Config.WATERMARK_FONT

        if user_has_font:
            watermark_font = f"{user_dict['WATERMARK_FONT']} (User)"
        elif (watermark_enabled and owner_has_font) or (
            Config.WATERMARK_ENABLED and owner_has_font
        ):
            watermark_font = f"{Config.WATERMARK_FONT} (Global)"
        else:
            watermark_font = "default.otf (Default)"

        # Get watermark threading status
        user_has_threading = "WATERMARK_THREADING" in user_dict
        if user_has_threading:
            threading_status = (
                "✅ Enabled (User)"
                if user_dict["WATERMARK_THREADING"]
                else "❌ Disabled (User)"
            )
        elif Config.WATERMARK_THREADING:
            threading_status = "✅ Enabled (Global)"
        else:
            threading_status = "❌ Disabled"

        # Get thread number
        user_has_thread_number = (
            "WATERMARK_THREAD_NUMBER" in user_dict
            and user_dict["WATERMARK_THREAD_NUMBER"]
        )
        if user_has_thread_number:
            thread_number = f"{user_dict['WATERMARK_THREAD_NUMBER']} (User)"
        elif Config.WATERMARK_THREAD_NUMBER:
            thread_number = f"{Config.WATERMARK_THREAD_NUMBER} (Global)"
        else:
            thread_number = "4 (Default)"

        # Get fast mode status
        user_has_fast_mode = "WATERMARK_FAST_MODE" in user_dict
        if user_has_fast_mode:
            fast_mode_status = (
                "✅ Enabled (User)"
                if user_dict["WATERMARK_FAST_MODE"]
                else "❌ Disabled (User)"
            )
        elif Config.WATERMARK_FAST_MODE:
            fast_mode_status = "✅ Enabled (Global)"
        else:
            fast_mode_status = "❌ Disabled"

        # Get maintain quality status
        user_has_maintain_quality = "WATERMARK_MAINTAIN_QUALITY" in user_dict
        if user_has_maintain_quality:
            maintain_quality_status = (
                "✅ High (User)"
                if user_dict["WATERMARK_MAINTAIN_QUALITY"]
                else "❌ Normal (User)"
            )
        elif Config.WATERMARK_MAINTAIN_QUALITY:
            maintain_quality_status = "✅ High (Global)"
        else:
            maintain_quality_status = "❌ Normal"

        # Get opacity value
        user_has_opacity = (
            "WATERMARK_OPACITY" in user_dict
            and user_dict["WATERMARK_OPACITY"] is not None
        )
        if user_has_opacity:
            opacity_value = f"{user_dict['WATERMARK_OPACITY']} (User)"
        elif Config.WATERMARK_OPACITY != 1.0:
            opacity_value = f"{Config.WATERMARK_OPACITY} (Global)"
        else:
            opacity_value = "1.0 (Default)"

        text = f"""⌬ <b>Watermark Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {"✅ Enabled" if watermark_enabled else "❌ Disabled"}
┠ <b>Text</b> → <code>{watermark_text}</code>
┠ <b>Position</b> → <code>{watermark_position}</code>
┠ <b>Size</b> → <code>{watermark_size}</code>
┠ <b>Color</b> → <code>{watermark_color}</code>
┠ <b>Font</b> → <code>{watermark_font}</code>
┠ <b>Opacity</b> → <code>{opacity_value}</code>
┠ <b>Fast Mode</b> → {fast_mode_status}
┠ <b>Quality</b> → {maintain_quality_status}
┠ <b>Threading</b> → {threading_status}
┖ <b>Thread Number</b> → <code>{thread_number}</code>"""

    elif stype == "watermark_config":
        # Watermark configuration menu
        buttons.data_button("Set Text", f"mediatools {user_id} menu WATERMARK_KEY")
        buttons.data_button(
            "Set Position", f"mediatools {user_id} menu WATERMARK_POSITION"
        )
        buttons.data_button("Set Size", f"mediatools {user_id} menu WATERMARK_SIZE")
        buttons.data_button(
            "Set Color", f"mediatools {user_id} menu WATERMARK_COLOR"
        )
        buttons.data_button("Set Font", f"mediatools {user_id} menu WATERMARK_FONT")
        buttons.data_button(
            "Set Opacity", f"mediatools {user_id} menu WATERMARK_OPACITY"
        )

        # Audio watermark settings
        audio_watermark_enabled = user_dict.get("AUDIO_WATERMARK_ENABLED", False)
        buttons.data_button(
            f"Audio WM: {'✅ ON' if audio_watermark_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog AUDIO_WATERMARK_ENABLED {'f' if audio_watermark_enabled else 't'}",
        )
        buttons.data_button(
            "Audio Text", f"mediatools {user_id} menu AUDIO_WATERMARK_TEXT"
        )

        # Subtitle watermark settings
        subtitle_watermark_enabled = user_dict.get(
            "SUBTITLE_WATERMARK_ENABLED", False
        )
        buttons.data_button(
            f"Subtitle WM: {'✅ ON' if subtitle_watermark_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog SUBTITLE_WATERMARK_ENABLED {'f' if subtitle_watermark_enabled else 't'}",
        )
        buttons.data_button(
            "Subtitle Text", f"mediatools {user_id} menu SUBTITLE_WATERMARK_TEXT"
        )

        # Add fast mode toggle
        fast_mode_enabled = user_dict.get("WATERMARK_FAST_MODE", True)
        buttons.data_button(
            f"Fast Mode: {'✅ ON' if fast_mode_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog WATERMARK_FAST_MODE {'f' if fast_mode_enabled else 't'}",
        )

        # Add maintain quality toggle
        maintain_quality = user_dict.get("WATERMARK_MAINTAIN_QUALITY", True)
        buttons.data_button(
            f"Quality: {'✅ High' if maintain_quality else '❌ Normal'}",
            f"mediatools {user_id} tog WATERMARK_MAINTAIN_QUALITY {'f' if maintain_quality else 't'}",
        )

        buttons.data_button("Back", f"mediatools {user_id} watermark", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get watermark text based on priority
        watermark_enabled = user_dict.get("WATERMARK_ENABLED", False)
        user_has_text = "WATERMARK_KEY" in user_dict and user_dict["WATERMARK_KEY"]
        owner_has_text = Config.WATERMARK_KEY

        if user_has_text:
            watermark_text = f"{user_dict['WATERMARK_KEY']} (User)"
        elif (watermark_enabled and owner_has_text) or (
            Config.WATERMARK_ENABLED and owner_has_text
        ):
            watermark_text = f"{Config.WATERMARK_KEY} (Global)"
        else:
            watermark_text = "None"

        # Get watermark position based on priority
        user_has_position = (
            "WATERMARK_POSITION" in user_dict and user_dict["WATERMARK_POSITION"]
        )
        owner_has_position = Config.WATERMARK_POSITION

        if user_has_position:
            watermark_position = f"{user_dict['WATERMARK_POSITION']} (User)"
        elif (watermark_enabled and owner_has_position) or (
            Config.WATERMARK_ENABLED and owner_has_position
        ):
            watermark_position = f"{Config.WATERMARK_POSITION} (Global)"
        else:
            watermark_position = "top_left (Default)"

        # Get watermark size based on priority
        user_has_size = "WATERMARK_SIZE" in user_dict and user_dict["WATERMARK_SIZE"]
        owner_has_size = Config.WATERMARK_SIZE

        if user_has_size:
            watermark_size = f"{user_dict['WATERMARK_SIZE']} (User)"
        elif (watermark_enabled and owner_has_size) or (
            Config.WATERMARK_ENABLED and owner_has_size
        ):
            watermark_size = f"{Config.WATERMARK_SIZE} (Global)"
        else:
            watermark_size = "20 (Default)"

        # Get watermark color based on priority
        user_has_color = (
            "WATERMARK_COLOR" in user_dict and user_dict["WATERMARK_COLOR"]
        )
        owner_has_color = Config.WATERMARK_COLOR

        if user_has_color:
            watermark_color = f"{user_dict['WATERMARK_COLOR']} (User)"
        elif (watermark_enabled and owner_has_color) or (
            Config.WATERMARK_ENABLED and owner_has_color
        ):
            watermark_color = f"{Config.WATERMARK_COLOR} (Global)"
        else:
            watermark_color = "white (Default)"

        # Get watermark font based on priority
        user_has_font = "WATERMARK_FONT" in user_dict and user_dict["WATERMARK_FONT"]
        owner_has_font = Config.WATERMARK_FONT

        if user_has_font:
            watermark_font = f"{user_dict['WATERMARK_FONT']} (User)"
        elif (watermark_enabled and owner_has_font) or (
            Config.WATERMARK_ENABLED and owner_has_font
        ):
            watermark_font = f"{Config.WATERMARK_FONT} (Global)"
        else:
            watermark_font = "default.otf (Default)"

        # Get watermark threading status
        user_has_threading = "WATERMARK_THREADING" in user_dict
        if user_has_threading:
            threading_status = (
                "✅ Enabled (User)"
                if user_dict["WATERMARK_THREADING"]
                else "❌ Disabled (User)"
            )
        elif Config.WATERMARK_THREADING:
            threading_status = "✅ Enabled (Global)"
        else:
            threading_status = "❌ Disabled"

        # Get thread number
        user_has_thread_number = (
            "WATERMARK_THREAD_NUMBER" in user_dict
            and user_dict["WATERMARK_THREAD_NUMBER"]
        )
        if user_has_thread_number:
            thread_number = f"{user_dict['WATERMARK_THREAD_NUMBER']} (User)"
        elif Config.WATERMARK_THREAD_NUMBER:
            thread_number = f"{Config.WATERMARK_THREAD_NUMBER} (Global)"
        else:
            thread_number = "4 (Default)"

        # Get fast mode status
        user_has_fast_mode = "WATERMARK_FAST_MODE" in user_dict
        if user_has_fast_mode:
            fast_mode_status = (
                "✅ Enabled (User)"
                if user_dict["WATERMARK_FAST_MODE"]
                else "❌ Disabled (User)"
            )
        elif Config.WATERMARK_FAST_MODE:
            fast_mode_status = "✅ Enabled (Global)"
        else:
            fast_mode_status = "❌ Disabled"

        # Get maintain quality status
        user_has_maintain_quality = "WATERMARK_MAINTAIN_QUALITY" in user_dict
        if user_has_maintain_quality:
            maintain_quality_status = (
                "✅ High (User)"
                if user_dict["WATERMARK_MAINTAIN_QUALITY"]
                else "❌ Normal (User)"
            )
        elif Config.WATERMARK_MAINTAIN_QUALITY:
            maintain_quality_status = "✅ High (Global)"
        else:
            maintain_quality_status = "❌ Normal"

        # Get opacity value
        user_has_opacity = (
            "WATERMARK_OPACITY" in user_dict
            and user_dict["WATERMARK_OPACITY"] is not None
        )
        if user_has_opacity:
            opacity_value = f"{user_dict['WATERMARK_OPACITY']} (User)"
        elif Config.WATERMARK_OPACITY != 1.0:
            opacity_value = f"{Config.WATERMARK_OPACITY} (Global)"
        else:
            opacity_value = "1.0 (Default)"

        # Get audio watermark text
        audio_watermark_enabled = user_dict.get("AUDIO_WATERMARK_ENABLED", False)
        user_has_audio_text = (
            "AUDIO_WATERMARK_TEXT" in user_dict and user_dict["AUDIO_WATERMARK_TEXT"]
        )
        owner_has_audio_text = Config.AUDIO_WATERMARK_TEXT

        if user_has_audio_text:
            audio_watermark_text = f"{user_dict['AUDIO_WATERMARK_TEXT']} (User)"
        elif (audio_watermark_enabled and owner_has_audio_text) or (
            Config.AUDIO_WATERMARK_ENABLED and owner_has_audio_text
        ):
            audio_watermark_text = f"{Config.AUDIO_WATERMARK_TEXT} (Global)"
        else:
            audio_watermark_text = "Same as visual watermark"

        # Get subtitle watermark text
        subtitle_watermark_enabled = user_dict.get(
            "SUBTITLE_WATERMARK_ENABLED", False
        )
        user_has_subtitle_text = (
            "SUBTITLE_WATERMARK_TEXT" in user_dict
            and user_dict["SUBTITLE_WATERMARK_TEXT"]
        )
        owner_has_subtitle_text = Config.SUBTITLE_WATERMARK_TEXT

        if user_has_subtitle_text:
            subtitle_watermark_text = (
                f"{user_dict['SUBTITLE_WATERMARK_TEXT']} (User)"
            )
        elif (subtitle_watermark_enabled and owner_has_subtitle_text) or (
            Config.SUBTITLE_WATERMARK_ENABLED and owner_has_subtitle_text
        ):
            subtitle_watermark_text = f"{Config.SUBTITLE_WATERMARK_TEXT} (Global)"
        else:
            subtitle_watermark_text = "Same as visual watermark"

        text = f"""⌬ <b>Configure Watermark :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Visual Watermark</b>
┠ <b>Text</b> → <code>{watermark_text}</code>
┠ <b>Position</b> → <code>{watermark_position}</code>
┠ <b>Size</b> → <code>{watermark_size}</code>
┠ <b>Color</b> → <code>{watermark_color}</code>
┠ <b>Font</b> → <code>{watermark_font}</code>
┠ <b>Opacity</b> → <code>{opacity_value}</code>
┠ <b>Fast Mode</b> → {fast_mode_status}
┠ <b>Quality</b> → {maintain_quality_status}
┠ <b>Threading</b> → {threading_status}
┠ <b>Thread Number</b> → <code>{thread_number}</code>
┃
┠ <b>Audio Watermark</b> → {"✅ Enabled" if audio_watermark_enabled else "❌ Disabled"}
┠ <b>Audio Text</b> → <code>{audio_watermark_text}</code>
┃
┖ <b>Subtitle Watermark</b> → {"✅ Enabled" if subtitle_watermark_enabled else "❌ Disabled"}
   <b>Subtitle Text</b> → <code>{subtitle_watermark_text}</code>"""

    elif stype == "merge":
        # Merge settings menu
        merge_enabled = user_dict.get("MERGE_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if merge_enabled else "❌ Disabled",
            f"mediatools {user_id} tog MERGE_ENABLED {'f' if merge_enabled else 't'}",
        )

        # Add Concat Demuxer/Filter Complex toggle
        concat_enabled = user_dict.get("CONCAT_DEMUXER_ENABLED", True)
        filter_enabled = user_dict.get("FILTER_COMPLEX_ENABLED", True)

        # Show a single toggle button that cycles through the states
        if concat_enabled and filter_enabled:
            # Both enabled - next state is concat only
            buttons.data_button(
                "Concat & Filter: Both ON",
                f"mediatools {user_id} toggle_concat_filter concat",
            )
        elif concat_enabled and not filter_enabled:
            # Only concat enabled - next state is filter only
            buttons.data_button(
                "Concat: ON | Filter: OFF",
                f"mediatools {user_id} toggle_concat_filter filter",
            )
        elif not concat_enabled and filter_enabled:
            # Only filter enabled - next state is both enabled
            buttons.data_button(
                "Concat: OFF | Filter: ON",
                f"mediatools {user_id} toggle_concat_filter both",
            )
        else:
            # Both disabled - next state is both enabled
            buttons.data_button(
                "Concat & Filter: Both OFF",
                f"mediatools {user_id} toggle_concat_filter both",
            )

        buttons.data_button("Configure", f"mediatools {user_id} merge_config")
        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu MERGE_PRIORITY"
        )

        # Add Remove Original toggle button
        remove_original = user_dict.get("MERGE_REMOVE_ORIGINAL", False)
        buttons.data_button(
            f"Remove Original: {'✅ ON' if remove_original else '❌ OFF'}",
            f"mediatools {user_id} tog MERGE_REMOVE_ORIGINAL {'f' if remove_original else 't'}",
        )

        buttons.data_button("Reset", f"mediatools {user_id} reset_merge")
        buttons.data_button("Remove", f"mediatools {user_id} remove_merge")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get concat demuxer status
        user_has_concat = "CONCAT_DEMUXER_ENABLED" in user_dict
        if user_has_concat:
            concat_status = (
                "✅ Enabled (User)"
                if user_dict["CONCAT_DEMUXER_ENABLED"]
                else "❌ Disabled (User)"
            )
        elif Config.CONCAT_DEMUXER_ENABLED:
            concat_status = "✅ Enabled (Global)"
        else:
            concat_status = "❌ Disabled"

        # Get filter complex status
        user_has_filter = "FILTER_COMPLEX_ENABLED" in user_dict
        if user_has_filter:
            filter_status = (
                "✅ Enabled (User)"
                if user_dict["FILTER_COMPLEX_ENABLED"]
                else "❌ Disabled (User)"
            )
        elif Config.FILTER_COMPLEX_ENABLED:
            filter_status = "✅ Enabled (Global)"
        else:
            filter_status = "❌ Disabled"

        # Get output formats
        user_has_video_format = (
            "MERGE_OUTPUT_FORMAT_VIDEO" in user_dict
            and user_dict["MERGE_OUTPUT_FORMAT_VIDEO"]
        )
        user_has_audio_format = (
            "MERGE_OUTPUT_FORMAT_AUDIO" in user_dict
            and user_dict["MERGE_OUTPUT_FORMAT_AUDIO"]
        )

        if user_has_video_format:
            video_format = f"{user_dict['MERGE_OUTPUT_FORMAT_VIDEO']} (User)"
        elif Config.MERGE_OUTPUT_FORMAT_VIDEO:
            video_format = f"{Config.MERGE_OUTPUT_FORMAT_VIDEO} (Global)"
        else:
            video_format = "mkv (Default)"

        if user_has_audio_format:
            audio_format = f"{user_dict['MERGE_OUTPUT_FORMAT_AUDIO']} (User)"
        elif Config.MERGE_OUTPUT_FORMAT_AUDIO:
            audio_format = f"{Config.MERGE_OUTPUT_FORMAT_AUDIO} (Global)"
        else:
            audio_format = "mp3 (Default)"

        # Get threading status
        user_has_threading = "MERGE_THREADING" in user_dict
        if user_has_threading:
            threading_status = (
                "✅ Enabled (User)"
                if user_dict["MERGE_THREADING"]
                else "❌ Disabled (User)"
            )
        elif Config.MERGE_THREADING:
            threading_status = "✅ Enabled (Global)"
        else:
            threading_status = "❌ Disabled"

        # Get thread number
        user_has_thread_number = (
            "MERGE_THREAD_NUMBER" in user_dict and user_dict["MERGE_THREAD_NUMBER"]
        )
        if user_has_thread_number:
            thread_number = f"{user_dict['MERGE_THREAD_NUMBER']} (User)"
        elif Config.MERGE_THREAD_NUMBER:
            thread_number = f"{Config.MERGE_THREAD_NUMBER} (Global)"
        else:
            thread_number = "4 (Default)"

        # Get remove original status
        user_has_remove_original = "MERGE_REMOVE_ORIGINAL" in user_dict
        if user_has_remove_original:
            remove_original = (
                "✅ Enabled (User)"
                if user_dict["MERGE_REMOVE_ORIGINAL"]
                else "❌ Disabled (User)"
            )
        elif Config.MERGE_REMOVE_ORIGINAL:
            remove_original = "✅ Enabled (Global)"
        else:
            remove_original = "❌ Disabled"

        text = f"""⌬ <b>Merge Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {"✅ Enabled" if merge_enabled else "❌ Disabled"}
┠ <b>Concat Demuxer</b> → {concat_status}
┠ <b>Filter Complex</b> → {filter_status}
┠ <b>Threading</b> → {threading_status}
┠ <b>Thread Number</b> → <code>{thread_number}</code>
┠ <b>Remove Original</b> → {remove_original}
┠ <b>Video Format</b> → <code>{video_format}</code>
┖ <b>Audio Format</b> → <code>{audio_format}</code>"""

    elif stype.startswith("merge_config"):
        # Get all merge settings and sort them alphabetically
        merge_settings = [
            # Output formats
            "MERGE_OUTPUT_FORMAT_VIDEO",
            "MERGE_OUTPUT_FORMAT_AUDIO",
            "MERGE_OUTPUT_FORMAT_IMAGE",
            "MERGE_OUTPUT_FORMAT_DOCUMENT",
            "MERGE_OUTPUT_FORMAT_SUBTITLE",
            # Video settings
            "MERGE_VIDEO_CODEC",
            "MERGE_VIDEO_QUALITY",
            "MERGE_VIDEO_PRESET",
            "MERGE_VIDEO_CRF",
            "MERGE_VIDEO_PIXEL_FORMAT",
            "MERGE_VIDEO_TUNE",
            "MERGE_VIDEO_FASTSTART",
            # Audio settings
            "MERGE_AUDIO_CODEC",
            "MERGE_AUDIO_BITRATE",
            "MERGE_AUDIO_CHANNELS",
            "MERGE_AUDIO_SAMPLING",
            "MERGE_AUDIO_VOLUME",
            # Image settings
            "MERGE_IMAGE_MODE",
            "MERGE_IMAGE_COLUMNS",
            "MERGE_IMAGE_QUALITY",
            "MERGE_IMAGE_DPI",
            "MERGE_IMAGE_RESIZE",
            "MERGE_IMAGE_BACKGROUND",
            # Subtitle settings
            "MERGE_SUBTITLE_ENCODING",
            "MERGE_SUBTITLE_FONT",
            "MERGE_SUBTITLE_FONT_SIZE",
            "MERGE_SUBTITLE_FONT_COLOR",
            "MERGE_SUBTITLE_BACKGROUND",
            # Document settings
            "MERGE_DOCUMENT_PAPER_SIZE",
            "MERGE_DOCUMENT_ORIENTATION",
            "MERGE_DOCUMENT_MARGIN",
            # Metadata settings
            "MERGE_METADATA_TITLE",
            "MERGE_METADATA_AUTHOR",
            "MERGE_METADATA_COMMENT",
        ]

        # Sort settings alphabetically
        merge_settings.sort()

        # Pagination setup
        global merge_config_page

        # If a specific page is requested in the stype parameter, use that
        if len(stype.split()) > 1:
            try:
                page_no = int(stype.split()[1])
                # Update the global variable
                merge_config_page = page_no
            except (ValueError, IndexError):
                # Use the global variable
                page_no = merge_config_page
                # This else block is not needed since we're already setting page_no
        else:
            # Use the global variable if no page is specified
            page_no = merge_config_page
        # 5 rows per page, 2 columns = 10 items per page
        items_per_page = 10  # 5 rows * 2 columns
        total_pages = (len(merge_settings) + items_per_page - 1) // items_per_page

        # Ensure page_no is valid
        if page_no >= total_pages:
            page_no = 0
            merge_config_page = 0  # Update global variableelif page_no < 0:
            page_no = total_pages - 1
            merge_config_page = (
                total_pages - 1
            )  # Update global variable# Get settings for current page
        current_page_settings = merge_settings[
            page_no * items_per_page : (page_no * items_per_page) + items_per_page
        ]

        # Add buttons for each setting on current page
        for setting in current_page_settings:
            display_name = setting.replace("MERGE_", "").replace("_", " ").title()
            buttons.data_button(display_name, f"mediatools {user_id} menu {setting}")

        # Add action buttons in a separate row
        buttons.data_button("Back", f"mediatools {user_id} merge", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")

        # Add pagination buttons in a separate row below action buttons
        if (
            total_pages > 1
        ):  # Log the current state of the buttons}, Header: {len(buttons._header_button)}, Footer: {len(buttons._footer_button)}, Page: {len(buttons._page_button)}"
            for i in range(total_pages):
                # Make the current page button different
                if (
                    i == page_no
                ):  # Make sure the page number is passed as a separate parameter
                    buttons.data_button(
                        f"[{i + 1}]",
                        f"mediatools {user_id} merge_config {i}",
                        "page",
                    )
                else:  # Make sure the page number is passed as a separate parameter
                    buttons.data_button(
                        str(i + 1), f"mediatools {user_id} merge_config {i}", "page"
                    )

            # Log the state after adding pagination buttons}, Header: {len(buttons._header_button)}, Footer: {len(buttons._footer_button)}, Page: {len(buttons._page_button)}"

            # Add a debug log message# Build the menu with 2 columns for settings, 4 columns for action buttons, and 8 columns for paginationbtns = buttons.build_menu(2, 8, 4, 8)} rows of buttons")

        # Define category groups
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

        # Get the categories shown on the current page
        categories = []
        # Calculate the start index for the current page
        current_page_settings = merge_settings[
            page_no * items_per_page : (page_no * items_per_page) + items_per_page
        ]
        if any(setting in formats for setting in current_page_settings):
            categories.append("Formats")
        if any(setting in video_settings for setting in current_page_settings):
            categories.append("Video")
        if any(setting in audio_settings for setting in current_page_settings):
            categories.append("Audio")
        if any(setting in image_settings for setting in current_page_settings):
            categories.append("Image")
        if any(setting in subtitle_settings for setting in current_page_settings):
            categories.append("Subtitle")
        if any(setting in document_settings for setting in current_page_settings):
            categories.append("Document")
        if any(setting in metadata_settings for setting in current_page_settings):
            categories.append("Metadata")

        category_text = ", ".join(categories)

        # Get page info for message
        page_info = f"\n\nCurrent page shows: {category_text} settings."
        if total_pages > 1:
            page_info += f"\n<b>Page:</b> {page_no + 1}/{total_pages}"

        # Get concat demuxer status
        user_has_concat = "CONCAT_DEMUXER_ENABLED" in user_dict
        if user_has_concat:
            concat_status = (
                "✅ Enabled (User)"
                if user_dict["CONCAT_DEMUXER_ENABLED"]
                else "❌ Disabled (User)"
            )
        elif Config.CONCAT_DEMUXER_ENABLED:
            concat_status = "✅ Enabled (Global)"
        else:
            concat_status = "❌ Disabled"

        # Get filter complex status
        user_has_filter = "FILTER_COMPLEX_ENABLED" in user_dict
        if user_has_filter:
            filter_status = (
                "✅ Enabled (User)"
                if user_dict["FILTER_COMPLEX_ENABLED"]
                else "❌ Disabled (User)"
            )
        elif Config.FILTER_COMPLEX_ENABLED:
            filter_status = "✅ Enabled (Global)"
        else:
            filter_status = "❌ Disabled"

        # Get output formats
        user_has_video_format = (
            "MERGE_OUTPUT_FORMAT_VIDEO" in user_dict
            and user_dict["MERGE_OUTPUT_FORMAT_VIDEO"]
        )
        user_has_audio_format = (
            "MERGE_OUTPUT_FORMAT_AUDIO" in user_dict
            and user_dict["MERGE_OUTPUT_FORMAT_AUDIO"]
        )

        if user_has_video_format:
            video_format = f"{user_dict['MERGE_OUTPUT_FORMAT_VIDEO']} (User)"
        elif Config.MERGE_OUTPUT_FORMAT_VIDEO:
            video_format = f"{Config.MERGE_OUTPUT_FORMAT_VIDEO} (Global)"
        else:
            video_format = "mkv (Default)"

        if user_has_audio_format:
            audio_format = f"{user_dict['MERGE_OUTPUT_FORMAT_AUDIO']} (User)"
        elif Config.MERGE_OUTPUT_FORMAT_AUDIO:
            audio_format = f"{Config.MERGE_OUTPUT_FORMAT_AUDIO} (Global)"
        else:
            audio_format = "mp3 (Default)"

        # Get priority
        user_has_priority = (
            "MERGE_PRIORITY" in user_dict and user_dict["MERGE_PRIORITY"]
        )
        if user_has_priority:
            priority = f"{user_dict['MERGE_PRIORITY']} (User)"
        elif Config.MERGE_PRIORITY:
            priority = f"{Config.MERGE_PRIORITY} (Global)"
        else:
            priority = "1 (Default)"

        # Get threading
        user_has_threading = "MERGE_THREADING" in user_dict
        if user_has_threading:
            threading = (
                "✅ Enabled (User)"
                if user_dict["MERGE_THREADING"]
                else "❌ Disabled (User)"
            )
        elif Config.MERGE_THREADING:
            threading = "✅ Enabled (Global)"
        else:
            threading = "❌ Disabled"

        # Get thread number
        user_has_thread_number = (
            "MERGE_THREAD_NUMBER" in user_dict and user_dict["MERGE_THREAD_NUMBER"]
        )
        if user_has_thread_number:
            thread_number = f"{user_dict['MERGE_THREAD_NUMBER']} (User)"
        elif Config.MERGE_THREAD_NUMBER:
            thread_number = f"{Config.MERGE_THREAD_NUMBER} (Global)"
        else:
            thread_number = "4 (Default)"

        # Get format options
        # Video settings
        user_has_video_format = (
            "MERGE_OUTPUT_FORMAT_VIDEO" in user_dict
            and user_dict["MERGE_OUTPUT_FORMAT_VIDEO"]
        )

        # Audio settings
        user_has_audio_format = (
            "MERGE_OUTPUT_FORMAT_AUDIO" in user_dict
            and user_dict["MERGE_OUTPUT_FORMAT_AUDIO"]
        )

        # We only need a few variables for the text display
        user_has_remove_original = "MERGE_REMOVE_ORIGINAL" in user_dict

        # Get values for video options
        if user_has_video_format:
            video_format = f"{user_dict['MERGE_OUTPUT_FORMAT_VIDEO']} (User)"
        elif Config.MERGE_OUTPUT_FORMAT_VIDEO:
            video_format = f"{Config.MERGE_OUTPUT_FORMAT_VIDEO} (Global)"
        else:
            video_format = "mkv (Default)"

        # Get values for audio options
        if user_has_audio_format:
            audio_format = f"{user_dict['MERGE_OUTPUT_FORMAT_AUDIO']} (User)"
        elif Config.MERGE_OUTPUT_FORMAT_AUDIO:
            audio_format = f"{Config.MERGE_OUTPUT_FORMAT_AUDIO} (Global)"
        else:
            audio_format = "mp3 (Default)"

        # We don't need to get all values since we're only showing a few in the text

        if user_has_remove_original:
            remove_original = (
                "✅ Enabled (User)"
                if user_dict["MERGE_REMOVE_ORIGINAL"]
                else "❌ Disabled (User)"
            )
        elif Config.MERGE_REMOVE_ORIGINAL:
            remove_original = "✅ Enabled (Global)"
        else:
            remove_original = "❌ Disabled"

        text = f"""⌬ <b>Configure Merge :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Select a setting to configure</b>
┃
┠ <b>Current Settings:</b>
┃ • <b>Concat Demuxer:</b> {concat_status}
┃ • <b>Filter Complex:</b> {filter_status}
┃ • <b>Priority:</b> <code>{priority}</code>
┃ • <b>Threading:</b> {threading}
┃ • <b>Thread Number:</b> <code>{thread_number}</code>
┃ • <b>Remove Original:</b> {remove_original}
┃ • <b>Video Format:</b> <code>{video_format}</code>
┃ • <b>Audio Format:</b> <code>{audio_format}</code>
┖ <b>Note:</b> Most settings default to 'none' unless specified{page_info}"""

    elif stype == "help":
        # Media Tools Help menu
        buttons.data_button("Merge Help", f"mediatools {user_id} help_merge")
        buttons.data_button("Watermark Help", f"mediatools {user_id} help_watermark")
        buttons.data_button("Convert Help", f"mediatools {user_id} help_convert")
        buttons.data_button(
            "Compression Help", f"mediatools {user_id} help_compression"
        )
        buttons.data_button("Trim Help", f"mediatools {user_id} help_trim")
        buttons.data_button("Extract Help", f"mediatools {user_id} help_extract")
        buttons.data_button("Priority Guide", f"mediatools {user_id} help_priority")
        buttons.data_button("Usage Examples", f"mediatools {user_id} help_examples")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Media Tools Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Select a help topic from the buttons below.</b>
┃
┠ <b>Merge Help</b> - Information about merging media files
┠ <b>Watermark Help</b> - Information about watermarking media
┠ <b>Convert Help</b> - Information about converting media files
┠ <b>Compression Help</b> - Information about compressing files
┠ <b>Trim Help</b> - Information about trimming media files
┠ <b>Priority Guide</b> - How tool priority affects processing
┖ <b>Usage Examples</b> - Examples of how to use media tools"""

    elif stype == "help_watermark":
        # Watermark Help
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Watermark Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ The watermark feature allows you to add text overlays to your videos and images.
┃
┠ <b>Supported Media Types:</b>
┃ • <b>Videos</b> - MP4, MKV, AVI, WebM, etc.
┃ • <b>Images</b> - JPG, PNG, WebP, etc.
┃
┠ <b>Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle watermark feature
┃ • <b>Text</b> - The text to display as watermark
┃ • <b>Position</b> - Where to place the watermark on the media
┃ • <b>Size</b> - Font size of the watermark text
┃ • <b>Color</b> - Color of the watermark text
┃ • <b>Font</b> - Font to use for the watermark text
┃ • <b>Priority</b> - Processing order when multiple tools are enabled
┃ • <b>Threading</b> - Enable/disable parallel processing
┃
┠ <b>Usage:</b>
┃ Add <code>-watermark "Your Text"</code> to any download command
┃ Example: <code>/leech https://example.com/media.zip -watermark "© My Channel"</code>
┃
┖ <b>Note:</b> For best results, use short text and contrasting colors."""

    elif stype == "help_merge":
        # Merge Help
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Merge Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ Combine multiple media files into a single file
┃
┠ <b>Supported Types:</b>
┃ • <b>Video:</b> Multiple videos → single video
┃ • <b>Audio:</b> Multiple audio files → single audio
┃ • <b>Subtitle:</b> Multiple subtitle files → single subtitle
┃ • <b>Mixed:</b> Video + Audio + Subtitle → complete media
┃ • <b>Image:</b> Multiple images → collage/grid
┃ • <b>PDF:</b> Multiple PDFs → single document
┃
┠ <b>Merge Flags:</b>
┃ • <code>-merge-video</code> - Merge videos (preserves all tracks)
┃ • <code>-merge-audio</code> - Merge audio files
┃ • <code>-merge-subtitle</code> - Merge subtitle files
┃ • <code>-merge-image</code> - Merge images (collage/grid)
┃ • <code>-merge-pdf</code> - Merge PDF documents
┃ • <code>-merge-all</code> - Merge all files by type
┃
┠ <b>Key Settings:</b>
┃ • <b>Method:</b> Concat Demuxer (fast) or Filter Complex (compatible)
┃ • <b>Output:</b> Format for merged files (mkv, mp4, mp3, etc.)
┃ • <b>Video:</b> Codec, quality, preset settings
┃ • <b>Audio:</b> Codec, bitrate, channels settings
┃ • <b>Image:</b> Mode (auto, horizontal, vertical, collage), quality
┃
┠ <b>Tips:</b>
┃ • Use <code>-m folder_name</code> to place files in same directory
┃ • MKV format best for preserving multiple tracks
┃ • 'copy' codec preserves quality but requires similar formats
┃
┖ <b>Note:</b> For more details, use /mthelp command."""

    elif stype == "help_convert":
        # Convert Help
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Convert Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ The convert feature allows you to convert media files to different formats.
┃
┠ <b>Supported Media Types:</b>
┃ • <b>Videos</b> - MP4, MKV, AVI, WebM, etc.
┃ • <b>Audio</b> - MP3, AAC, FLAC, WAV, etc.
┃
┠ <b>Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle convert feature
┃ • <b>Priority</b> - Processing order when multiple tools are enabled
┃
┠ <b>Video Convert Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle video convert feature
┃ • <b>Format</b> - Output format for converted videos (mp4, mkv, etc.)
┃ • <b>Codec</b> - Video codec to use (libx264, libx265, etc.)
┃ • <b>Quality</b> - Video quality preset (low, medium, high, etc.)
┃ • <b>CRF</b> - Quality control (0-51, lower is better quality)
┃ • <b>Preset</b> - Encoding speed vs compression (medium, slow, etc.)
┃ • <b>Maintain Quality</b> - Preserve original quality when possible
┃
┠ <b>Audio Convert Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle audio convert feature
┃ • <b>Format</b> - Output format for converted audio (mp3, aac, etc.)
┃ • <b>Codec</b> - Audio codec to use (libmp3lame, aac, etc.)
┃ • <b>Bitrate</b> - Audio quality (128k, 192k, 320k, etc.)
┃ • <b>Channels</b> - Number of audio channels (1=mono, 2=stereo)
┃ • <b>Sampling</b> - Audio sampling rate (44100, 48000, etc.)
┃ • <b>Volume</b> - Volume adjustment (1.0=normal, 2.0=double)
┃
┠ <b>Usage:</b>
┃ • <b>Convert Video:</b> Add <code>-cv format</code> to any download command
┃   Example: <code>/leech https://example.com/video.mp4 -cv mp4</code>
┃
┃ • <b>Convert Audio:</b> Add <code>-ca format</code> to any download command
┃   Example: <code>/mirror https://example.com/audio.wav -ca mp3</code>
┃
┖ <b>Note:</b> Convert uses FFmpeg for processing and supports most media formats."""

    elif stype == "help_trim":
        # Trim Guide
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Trim Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ The trim feature allows you to cut specific portions of media files.
┃
┠ <b>Supported Media Types:</b>
┃ • <b>Videos</b> - MP4, MKV, AVI, WebM, etc.
┃ • <b>Audio</b> - MP3, AAC, FLAC, WAV, etc.
┃ • <b>Images</b> - JPG, PNG, WebP, etc.
┃ • <b>Documents</b> - PDF, DOC, DOCX, etc.
┃ • <b>Subtitles</b> - SRT, ASS, VTT, etc.
┃ • <b>Archives</b> - ZIP, RAR, 7Z, etc.
┃
┠ <b>Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle trim feature
┃ • <b>Priority</b> - Processing order when multiple tools are enabled
┃ • <b>Delete Original</b> - Remove original file after successful trim
┃
┠ <b>Video Trim Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle video trim
┃ • <b>Codec</b> - Video codec to use (copy, libx264, etc.)
┃ • <b>Preset</b> - Encoding speed/quality (fast, medium, slow)
┃ • <b>Format</b> - Output format (mp4, mkv, avi, webm, etc.)
┃
┠ <b>Audio Trim Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle audio trim
┃ • <b>Codec</b> - Audio codec to use (copy, aac, etc.)
┃ • <b>Preset</b> - Encoding speed/quality (fast, medium, slow)
┃ • <b>Format</b> - Output format (mp3, m4a, flac, opus, wav, etc.)
┃
┠ <b>Image Trim Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle image trim
┃ • <b>Quality</b> - Image quality (1-100)
┃ • <b>Format</b> - Output format (jpg, png, webp, gif, etc.)
┃
┠ <b>Document Trim Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle document trim
┃ • <b>Quality</b> - Document quality (1-100)
┃ • <b>Format</b> - Output format (pdf, docx, txt, etc.)
┃
┠ <b>Subtitle Trim Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle subtitle trim
┃ • <b>Encoding</b> - Character encoding (utf-8, latin1, etc.)
┃ • <b>Format</b> - Output format (srt, ass, vtt, etc.)
┃
┠ <b>Archive Trim Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle archive trim
┃ • <b>Format</b> - Output format (zip, 7z, tar, etc.)
┃
┠ <b>Usage:</b>
┃ • <b>Trim Media:</b> Add <code>-trim from-time to-time</code> to any download command
┃   Example: <code>/leech https://example.com/video.mp4 -trim 00:01:30 00:02:45</code>
┃   This will trim the video from 1 minute 30 seconds to 2 minutes 45 seconds
┃
┃ • <b>Delete Original:</b> Add <code>-del</code> to delete the original file after trimming
┃   Example: <code>/leech https://example.com/video.mp4 -trim 00:01:30 00:02:45 -del</code>
┃
┃ • <b>Time Format:</b> Use HH:MM:SS or seconds
┃   Example: <code>-trim 90 165</code> (trim from 90 seconds to 165 seconds)
┃   Example: <code>-trim 00:01:30 00:02:45</code> (trim from 1m30s to 2m45s)
┃
┖ <b>Note:</b> Trim uses FFmpeg for processing and supports most media formats. Format settings with value 'none' will use the original file format."""

    elif stype == "help_extract":
        # Extract Guide
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Extract Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ The extract feature allows you to extract specific tracks from media files.
┃
┠ <b>Supported Media Types:</b>
┃ • <b>Container Formats</b> - MKV, MP4, AVI, MOV, WebM, etc.
┃ • <b>Video Codecs</b> - H.264, H.265, VP9, AV1, etc.
┃ • <b>Audio Codecs</b> - AAC, MP3, OPUS, FLAC, etc.
┃ • <b>Subtitle Formats</b> - SRT, ASS, SSA, VTT, etc.
┃ • <b>Attachments</b> - Fonts, images, and other embedded files
┃
┠ <b>Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle extract feature
┃ • <b>Priority</b> - Processing order when multiple tools are enabled
┃ • <b>Maintain Quality</b> - Preserve high quality during extraction
┃
┠ <b>Video Extract Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle video extraction
┃ • <b>Codec</b> - Video codec to use (copy, h264, h265, etc.)
┃ • <b>Index</b> - Specific video track to extract (0-based index)
┃
┠ <b>Audio Extract Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle audio extraction
┃ • <b>Codec</b> - Audio codec to use (copy, aac, mp3, etc.)
┃ • <b>Index</b> - Specific audio track to extract (0-based index)
┃
┠ <b>Subtitle Extract Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle subtitle extraction
┃ • <b>Codec</b> - Subtitle codec to use (copy, srt, ass, etc.)
┃ • <b>Index</b> - Specific subtitle track to extract (0-based index)
┃
┠ <b>Attachment Extract Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle attachment extraction
┃ • <b>Index</b> - Specific attachment to extract (0-based index)
┃
┠ <b>Usage:</b>
┃ • <b>Extract All Tracks:</b> Add <code>-extract</code> to any download command
┃   Example: <code>/leech https://example.com/video.mkv -extract</code>
┃
┃ • <b>Extract Specific Track Types:</b>
┃   Example: <code>/leech https://example.com/video.mkv -extract-video</code>
┃   Example: <code>/mirror https://example.com/video.mkv -extract-audio</code>
┃   Example: <code>/leech https://example.com/video.mkv -extract-subtitle</code>
┃
┃ • <b>Extract Specific Track by Index:</b>
┃   Example: <code>/leech https://example.com/video.mkv -extract-audio-index 1</code>
┃   This will extract the second audio track (index starts at 0)
┃
┖ <b>Note:</b> Extract uses FFmpeg for processing and works best with MKV containers."""

    elif stype == "help_compression":
        # Compression Guide
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Compression Help :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ The compression feature reduces file size while maintaining acceptable quality.
┃
┠ <b>Supported Media Types:</b>
┃ • <b>Videos</b> - MP4, MKV, AVI, WebM, etc.
┃ • <b>Audio</b> - MP3, AAC, FLAC, WAV, etc.
┃ • <b>Images</b> - JPG, PNG, WebP, etc.
┃ • <b>Documents</b> - PDF, DOC, DOCX, etc.
┃ • <b>Subtitles</b> - SRT, ASS, VTT, etc.
┃ • <b>Archives</b> - ZIP, RAR, 7Z, etc.
┃
┠ <b>Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle compression feature
┃ • <b>Priority</b> - Processing order when multiple tools are enabled
┃
┠ <b>Video Compression Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle video compression
┃ • <b>Preset</b> - Compression speed/quality (fast, medium, slow)
┃ • <b>CRF</b> - Quality control (0-51, lower is better quality)
┃ • <b>Codec</b> - Video codec to use (libx264, libx265, etc.)
┃ • <b>Tune</b> - Content-specific optimizations (film, animation, etc.)
┃ • <b>Pixel Format</b> - Color encoding format (yuv420p, etc.)
┃
┠ <b>Audio Compression Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle audio compression
┃ • <b>Preset</b> - Compression speed/quality (fast, medium, slow)
┃ • <b>Codec</b> - Audio codec to use (aac, mp3, etc.)
┃ • <b>Bitrate</b> - Audio quality (128k, 192k, 320k, etc.)
┃ • <b>Channels</b> - Number of audio channels (1=mono, 2=stereo)
┃
┠ <b>Image Compression Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle image compression
┃ • <b>Preset</b> - Compression speed/quality (fast, medium, slow)
┃ • <b>Quality</b> - Image quality (1-100)
┃ • <b>Resize</b> - Image dimensions (none, 1920x1080, etc.)
┃
┠ <b>Document Compression Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle document compression
┃ • <b>Preset</b> - Compression speed/quality (fast, medium, slow)
┃ • <b>DPI</b> - Resolution for PDF compression (72-300)
┃
┠ <b>Subtitle Compression Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle subtitle compression
┃ • <b>Preset</b> - Compression speed/quality (fast, medium, slow)
┃ • <b>Encoding</b> - Character encoding (utf-8, latin1, etc.)
┃
┠ <b>Archive Compression Settings:</b>
┃ • <b>Enabled/Disabled</b> - Toggle archive compression
┃ • <b>Preset</b> - Compression speed/quality (fast, medium, slow)
┃ • <b>Level</b> - Compression level (1-9)
┃ • <b>Method</b> - Compression algorithm (deflate, lzma, etc.)
┃
┠ <b>Usage:</b>
┃ • <b>Enable Compression:</b> Add <code>-compress</code> to any download command
┃   Example: <code>/leech https://example.com/video.mp4 -compress</code>
┃
┃ • <b>Video Compression:</b> Add <code>-video-fast</code>, <code>-video-medium</code>, or <code>-video-slow</code>
┃   Example: <code>/mirror https://example.com/video.mp4 -video-medium</code>
┃
┃ • <b>Audio Compression:</b> Add <code>-audio-fast</code>, <code>-audio-medium</code>, or <code>-audio-slow</code>
┃   Example: <code>/leech https://example.com/audio.mp3 -audio-medium</code>
┃
┃ • <b>Image Compression:</b> Add <code>-image-fast</code>, <code>-image-medium</code>, or <code>-image-slow</code>
┃   Example: <code>/mirror https://example.com/image.jpg -image-medium</code>
┃
┃ • <b>Document Compression:</b> Add <code>-document-fast</code>, <code>-document-medium</code>, or <code>-document-slow</code>
┃   Example: <code>/leech https://example.com/document.pdf -document-medium</code>
┃
┃ • <b>Subtitle Compression:</b> Add <code>-subtitle-fast</code>, <code>-subtitle-medium</code>, or <code>-subtitle-slow</code>
┃   Example: <code>/mirror https://example.com/subtitle.srt -subtitle-medium</code>
┃
┃ • <b>Archive Compression:</b> Add <code>-archive-fast</code>, <code>-archive-medium</code>, or <code>-archive-slow</code>
┃   Example: <code>/leech https://example.com/archive.zip -archive-medium</code>
┃
┖ <b>Note:</b> Compression only keeps the compressed file if it's smaller than the original."""

    elif stype == "help_priority":
        # Priority Guide
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Media Tools Priority Guide :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Overview:</b>
┃ The priority system controls the order in which media tools are applied.
┃
┠ <b>How Priority Works:</b>
┃ • Lower number means higher priority (1 is highest priority)
┃ • When multiple media tools are enabled, they run in priority order
┃ • Default priorities: Merge (1), Watermark (2), Convert (3), Compression (4), Trim (5)
┃
┠ <b>Why Priority Matters:</b>
┃ The order of processing affects the final result:
┃ • <b>Merge → Watermark</b>: Watermark appears once on the merged file
┃ • <b>Watermark → Merge</b>: Each file is watermarked before merging
┃ • <b>Convert → Watermark</b>: Watermark appears on converted file
┃ • <b>Watermark → Convert</b>: Watermark is applied before conversion
┃ • <b>Compression → Convert</b>: Compressed file is then converted
┃ • <b>Convert → Compression</b>: Converted file is then compressed
┃ • <b>Trim → Convert</b>: Trimmed file is then converted
┃ • <b>Convert → Trim</b>: Converted file is then trimmed
┃
┠ <b>Setting Priority:</b>
┃ 1. Go to Media Tools settings
┃ 2. Select the tool (Watermark, Merge, Convert, Compression, or Trim)
┃ 3. Click "Set Priority"
┃ 4. Enter a number (lower = higher priority)
┃
┖ <b>Note:</b> Priorities follow the user/owner/default configuration hierarchy."""

    elif stype == "compression":
        # Compression settings menu
        compression_enabled = user_dict.get("COMPRESSION_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if compression_enabled else "❌ Disabled",
            f"mediatools {user_id} tog COMPRESSION_ENABLED {'f' if compression_enabled else 't'}",
        )

        # Add delete original toggle
        delete_original = user_dict.get("COMPRESSION_DELETE_ORIGINAL", False)
        buttons.data_button(
            f"Delete Original: {'✅ ON' if delete_original else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_DELETE_ORIGINAL {'f' if delete_original else 't'}",
        )

        buttons.data_button("Configure", f"mediatools {user_id} compression_config")
        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu COMPRESSION_PRIORITY"
        )
        buttons.data_button("Reset", f"mediatools {user_id} reset_compression")
        buttons.data_button("Remove", f"mediatools {user_id} remove_compression")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get compression priority
        user_has_priority = "COMPRESSION_PRIORITY" in user_dict
        if user_has_priority:
            compression_priority = f"{user_dict['COMPRESSION_PRIORITY']} (User)"
        elif hasattr(Config, "COMPRESSION_PRIORITY"):
            compression_priority = f"{Config.COMPRESSION_PRIORITY} (Global)"
        else:
            compression_priority = "4 (Default)"

        # Get delete original status
        delete_original = user_dict.get("COMPRESSION_DELETE_ORIGINAL", False)
        owner_delete_original = (
            hasattr(Config, "COMPRESSION_DELETE_ORIGINAL")
            and Config.COMPRESSION_DELETE_ORIGINAL
        )

        if "COMPRESSION_DELETE_ORIGINAL" in user_dict:
            if delete_original:
                delete_original_status = "✅ Enabled (User)"
            else:
                delete_original_status = "❌ Disabled (User)"
        elif owner_delete_original:
            delete_original_status = "✅ Enabled (Global)"
        else:
            delete_original_status = "❌ Disabled (Default)"

        # Get video compression status
        video_enabled = user_dict.get("COMPRESSION_VIDEO_ENABLED", False)
        if "COMPRESSION_VIDEO_ENABLED" in user_dict:
            video_status = (
                "✅ Enabled (User)" if video_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "COMPRESSION_VIDEO_ENABLED")
            and Config.COMPRESSION_VIDEO_ENABLED
        ):
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Get audio compression status
        audio_enabled = user_dict.get("COMPRESSION_AUDIO_ENABLED", False)
        if "COMPRESSION_AUDIO_ENABLED" in user_dict:
            audio_status = (
                "✅ Enabled (User)" if audio_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "COMPRESSION_AUDIO_ENABLED")
            and Config.COMPRESSION_AUDIO_ENABLED
        ):
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Get image compression status
        image_enabled = user_dict.get("COMPRESSION_IMAGE_ENABLED", False)
        if "COMPRESSION_IMAGE_ENABLED" in user_dict:
            image_status = (
                "✅ Enabled (User)" if image_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "COMPRESSION_IMAGE_ENABLED")
            and Config.COMPRESSION_IMAGE_ENABLED
        ):
            image_status = "✅ Enabled (Global)"
        else:
            image_status = "❌ Disabled"

        # Get document compression status
        document_enabled = user_dict.get("COMPRESSION_DOCUMENT_ENABLED", False)
        if "COMPRESSION_DOCUMENT_ENABLED" in user_dict:
            document_status = (
                "✅ Enabled (User)" if document_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "COMPRESSION_DOCUMENT_ENABLED")
            and Config.COMPRESSION_DOCUMENT_ENABLED
        ):
            document_status = "✅ Enabled (Global)"
        else:
            document_status = "❌ Disabled"

        # Get subtitle compression status
        subtitle_enabled = user_dict.get("COMPRESSION_SUBTITLE_ENABLED", False)
        if "COMPRESSION_SUBTITLE_ENABLED" in user_dict:
            subtitle_status = (
                "✅ Enabled (User)" if subtitle_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "COMPRESSION_SUBTITLE_ENABLED")
            and Config.COMPRESSION_SUBTITLE_ENABLED
        ):
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Get archive compression status
        archive_enabled = user_dict.get("COMPRESSION_ARCHIVE_ENABLED", False)
        if "COMPRESSION_ARCHIVE_ENABLED" in user_dict:
            archive_status = (
                "✅ Enabled (User)" if archive_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "COMPRESSION_ARCHIVE_ENABLED")
            and Config.COMPRESSION_ARCHIVE_ENABLED
        ):
            archive_status = "✅ Enabled (Global)"
        else:
            archive_status = "❌ Disabled"

        text = f"""⌬ <b>Compression Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {"✅ Enabled" if compression_enabled else "❌ Disabled"}
┠ <b>Priority</b> → <code>{compression_priority}</code>
┠ <b>Delete Original</b> → {delete_original_status}
┃
┠ <b>Video Compression</b> → {video_status}
┠ <b>Audio Compression</b> → {audio_status}
┠ <b>Image Compression</b> → {image_status}
┠ <b>Document Compression</b> → {document_status}
┠ <b>Subtitle Compression</b> → {subtitle_status}
┖ <b>Archive Compression</b> → {archive_status}"""

    elif stype == "trim":
        # Trim settings menu
        trim_enabled = user_dict.get("TRIM_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if trim_enabled else "❌ Disabled",
            f"mediatools {user_id} tog TRIM_ENABLED {'f' if trim_enabled else 't'}",
        )
        buttons.data_button("Configure", f"mediatools {user_id} trim_config")
        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu TRIM_PRIORITY"
        )
        buttons.data_button("Reset", f"mediatools {user_id} reset_trim")
        buttons.data_button("Remove", f"mediatools {user_id} remove_trim")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get trim priority
        user_has_priority = "TRIM_PRIORITY" in user_dict
        if user_has_priority:
            priority = f"{user_dict['TRIM_PRIORITY']} (User)"
        elif hasattr(Config, "TRIM_PRIORITY") and Config.TRIM_PRIORITY:
            priority = f"{Config.TRIM_PRIORITY} (Global)"
        else:
            priority = "5 (Default)"

        # Get start and end time settings
        start_time = user_dict.get("TRIM_START_TIME", None)
        if start_time is None and hasattr(Config, "TRIM_START_TIME"):
            start_time = Config.TRIM_START_TIME
        start_time_str = f"{start_time}" if start_time else "00:00:00 (Default)"

        end_time = user_dict.get("TRIM_END_TIME", None)
        if end_time is None and hasattr(Config, "TRIM_END_TIME"):
            end_time = Config.TRIM_END_TIME
        end_time_str = f"{end_time}" if end_time else "End of file (Default)"

        # Get video trim status
        video_trim_enabled = user_dict.get("TRIM_VIDEO_ENABLED", False)
        owner_video_trim_enabled = (
            hasattr(Config, "TRIM_VIDEO_ENABLED") and Config.TRIM_VIDEO_ENABLED
        )

        if "TRIM_VIDEO_ENABLED" in user_dict:
            if video_trim_enabled:
                video_status = "✅ Enabled (User)"
            else:
                video_status = "❌ Disabled (User)"
        elif owner_video_trim_enabled:
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Get audio trim status
        audio_trim_enabled = user_dict.get("TRIM_AUDIO_ENABLED", False)
        owner_audio_trim_enabled = (
            hasattr(Config, "TRIM_AUDIO_ENABLED") and Config.TRIM_AUDIO_ENABLED
        )

        if "TRIM_AUDIO_ENABLED" in user_dict:
            if audio_trim_enabled:
                audio_status = "✅ Enabled (User)"
            else:
                audio_status = "❌ Disabled (User)"
        elif owner_audio_trim_enabled:
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Get image trim status
        image_trim_enabled = user_dict.get("TRIM_IMAGE_ENABLED", False)
        owner_image_trim_enabled = (
            hasattr(Config, "TRIM_IMAGE_ENABLED") and Config.TRIM_IMAGE_ENABLED
        )

        if "TRIM_IMAGE_ENABLED" in user_dict:
            if image_trim_enabled:
                image_status = "✅ Enabled (User)"
            else:
                image_status = "❌ Disabled (User)"
        elif owner_image_trim_enabled:
            image_status = "✅ Enabled (Global)"
        else:
            image_status = "❌ Disabled"

        # Get document trim status
        document_trim_enabled = user_dict.get("TRIM_DOCUMENT_ENABLED", False)
        owner_document_trim_enabled = (
            hasattr(Config, "TRIM_DOCUMENT_ENABLED") and Config.TRIM_DOCUMENT_ENABLED
        )

        if "TRIM_DOCUMENT_ENABLED" in user_dict:
            if document_trim_enabled:
                document_status = "✅ Enabled (User)"
            else:
                document_status = "❌ Disabled (User)"
        elif owner_document_trim_enabled:
            document_status = "✅ Enabled (Global)"
        else:
            document_status = "❌ Disabled"

        # Get subtitle trim status
        subtitle_trim_enabled = user_dict.get("TRIM_SUBTITLE_ENABLED", False)
        owner_subtitle_trim_enabled = (
            hasattr(Config, "TRIM_SUBTITLE_ENABLED") and Config.TRIM_SUBTITLE_ENABLED
        )

        if "TRIM_SUBTITLE_ENABLED" in user_dict:
            if subtitle_trim_enabled:
                subtitle_status = "✅ Enabled (User)"
            else:
                subtitle_status = "❌ Disabled (User)"
        elif owner_subtitle_trim_enabled:
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Get archive trim status
        archive_trim_enabled = user_dict.get("TRIM_ARCHIVE_ENABLED", False)
        owner_archive_trim_enabled = (
            hasattr(Config, "TRIM_ARCHIVE_ENABLED") and Config.TRIM_ARCHIVE_ENABLED
        )

        if "TRIM_ARCHIVE_ENABLED" in user_dict:
            if archive_trim_enabled:
                archive_status = "✅ Enabled (User)"
            else:
                archive_status = "❌ Disabled (User)"
        elif owner_archive_trim_enabled:
            archive_status = "✅ Enabled (Global)"
        else:
            archive_status = "❌ Disabled"

        # Build text for trim menu
        text = f"""⌬ <b>Trim Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {"✅ Enabled" if trim_enabled else "❌ Disabled"}
┠ <b>Priority</b> → {priority}
┃
┠ <b>Start Time</b> → <code>{start_time_str}</code>
┠ <b>End Time</b> → <code>{end_time_str}</code>
┃
┠ <b>Video Trim</b> → {video_status}
┠ <b>Audio Trim</b> → {audio_status}
┠ <b>Image Trim</b> → {image_status}
┠ <b>Document Trim</b> → {document_status}
┠ <b>Subtitle Trim</b> → {subtitle_status}
┃
┖ <b>Archive Trim</b> → {archive_status}"""

    elif stype == "extract":
        # Extract settings menu
        extract_enabled = user_dict.get("EXTRACT_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if extract_enabled else "❌ Disabled",
            f"mediatools {user_id} tog EXTRACT_ENABLED {'f' if extract_enabled else 't'}",
        )
        buttons.data_button("Configure", f"mediatools {user_id} extract_config")
        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu EXTRACT_PRIORITY"
        )
        buttons.data_button("Reset", f"mediatools {user_id} reset_extract")
        buttons.data_button("Remove", f"mediatools {user_id} remove_extract")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get extract priority
        user_has_priority = "EXTRACT_PRIORITY" in user_dict
        if user_has_priority:
            priority = f"{user_dict['EXTRACT_PRIORITY']} (User)"
        elif hasattr(Config, "EXTRACT_PRIORITY") and Config.EXTRACT_PRIORITY:
            priority = f"{Config.EXTRACT_PRIORITY} (Global)"
        else:
            priority = "6 (Default)"

        # Get extract video status
        video_extract_enabled = user_dict.get("EXTRACT_VIDEO_ENABLED", False)
        owner_video_extract_enabled = (
            hasattr(Config, "EXTRACT_VIDEO_ENABLED") and Config.EXTRACT_VIDEO_ENABLED
        )

        if "EXTRACT_VIDEO_ENABLED" in user_dict:
            if video_extract_enabled:
                video_status = "✅ Enabled (User)"
            else:
                video_status = "❌ Disabled (User)"
        elif owner_video_extract_enabled:
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Get extract audio status
        audio_extract_enabled = user_dict.get("EXTRACT_AUDIO_ENABLED", False)
        owner_audio_extract_enabled = (
            hasattr(Config, "EXTRACT_AUDIO_ENABLED") and Config.EXTRACT_AUDIO_ENABLED
        )

        if "EXTRACT_AUDIO_ENABLED" in user_dict:
            if audio_extract_enabled:
                audio_status = "✅ Enabled (User)"
            else:
                audio_status = "❌ Disabled (User)"
        elif owner_audio_extract_enabled:
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Get extract subtitle status
        subtitle_extract_enabled = user_dict.get("EXTRACT_SUBTITLE_ENABLED", False)
        owner_subtitle_extract_enabled = (
            hasattr(Config, "EXTRACT_SUBTITLE_ENABLED")
            and Config.EXTRACT_SUBTITLE_ENABLED
        )

        if "EXTRACT_SUBTITLE_ENABLED" in user_dict:
            if subtitle_extract_enabled:
                subtitle_status = "✅ Enabled (User)"
            else:
                subtitle_status = "❌ Disabled (User)"
        elif owner_subtitle_extract_enabled:
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Get extract attachment status
        attachment_extract_enabled = user_dict.get(
            "EXTRACT_ATTACHMENT_ENABLED", False
        )
        owner_attachment_extract_enabled = (
            hasattr(Config, "EXTRACT_ATTACHMENT_ENABLED")
            and Config.EXTRACT_ATTACHMENT_ENABLED
        )

        if "EXTRACT_ATTACHMENT_ENABLED" in user_dict:
            if attachment_extract_enabled:
                attachment_status = "✅ Enabled (User)"
            else:
                attachment_status = "❌ Disabled (User)"
        elif owner_attachment_extract_enabled:
            attachment_status = "✅ Enabled (Global)"
        else:
            attachment_status = "❌ Disabled"

        # Get maintain quality status
        maintain_quality_enabled = user_dict.get("EXTRACT_MAINTAIN_QUALITY", True)
        owner_maintain_quality_enabled = (
            hasattr(Config, "EXTRACT_MAINTAIN_QUALITY")
            and Config.EXTRACT_MAINTAIN_QUALITY
        )

        if "EXTRACT_MAINTAIN_QUALITY" in user_dict:
            if maintain_quality_enabled:
                maintain_quality_status = "✅ Enabled (User)"
            else:
                maintain_quality_status = "❌ Disabled (User)"
        elif owner_maintain_quality_enabled:
            maintain_quality_status = "✅ Enabled (Global)"
        else:
            maintain_quality_status = "✅ Enabled (Default)"

        text = f"""⌬ <b>Extract Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {"✅ Enabled" if extract_enabled else "❌ Disabled"}
┠ <b>Priority</b> → {priority}
┃
┠ <b>Video Extract</b> → {video_status}
┠ <b>Audio Extract</b> → {audio_status}
┠ <b>Subtitle Extract</b> → {subtitle_status}
┠ <b>Attachment Extract</b> → {attachment_status}
┃
┖ <b>Maintain Quality</b> → {maintain_quality_status}"""

    elif stype == "trim_config":
        # Trim configuration menu# Add start time and end time settings at the top
        buttons.data_button(
            "Start Time", f"mediatools {user_id} menu TRIM_START_TIME"
        )
        buttons.data_button("End Time", f"mediatools {user_id} menu TRIM_END_TIME")

        # Add delete original toggle
        delete_original = user_dict.get("TRIM_DELETE_ORIGINAL", False)
        buttons.data_button(
            f"Delete Original: {'✅ ON' if delete_original else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_DELETE_ORIGINAL {'f' if delete_original else 't'}",
        )

        # Format settings button removed as requested

        # Video trim settings
        video_enabled = user_dict.get("TRIM_VIDEO_ENABLED", False)
        buttons.data_button(
            f"Video: {'✅ ON' if video_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_VIDEO_ENABLED {'f' if video_enabled else 't'}",
        )
        buttons.data_button(
            "Video Codec", f"mediatools {user_id} menu TRIM_VIDEO_CODEC"
        )
        buttons.data_button(
            "Video Preset", f"mediatools {user_id} menu TRIM_VIDEO_PRESET"
        )
        buttons.data_button(
            "Video Format", f"mediatools {user_id} menu TRIM_VIDEO_FORMAT"
        )

        # Audio trim settings
        audio_enabled = user_dict.get("TRIM_AUDIO_ENABLED", False)
        buttons.data_button(
            f"Audio: {'✅ ON' if audio_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_AUDIO_ENABLED {'f' if audio_enabled else 't'}",
        )
        buttons.data_button(
            "Audio Codec", f"mediatools {user_id} menu TRIM_AUDIO_CODEC"
        )
        buttons.data_button(
            "Audio Preset", f"mediatools {user_id} menu TRIM_AUDIO_PRESET"
        )
        buttons.data_button(
            "Audio Format", f"mediatools {user_id} menu TRIM_AUDIO_FORMAT"
        )

        # Image trim settings
        image_enabled = user_dict.get("TRIM_IMAGE_ENABLED", False)
        buttons.data_button(
            f"Image: {'✅ ON' if image_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_IMAGE_ENABLED {'f' if image_enabled else 't'}",
        )
        buttons.data_button(
            "Image Quality", f"mediatools {user_id} menu TRIM_IMAGE_QUALITY"
        )
        buttons.data_button(
            "Image Format", f"mediatools {user_id} menu TRIM_IMAGE_FORMAT"
        )

        # Document trim settings
        document_enabled = user_dict.get("TRIM_DOCUMENT_ENABLED", False)
        buttons.data_button(
            f"Document: {'✅ ON' if document_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_DOCUMENT_ENABLED {'f' if document_enabled else 't'}",
        )
        buttons.data_button(
            "Document Quality", f"mediatools {user_id} menu TRIM_DOCUMENT_QUALITY"
        )
        buttons.data_button(
            "Document Format", f"mediatools {user_id} menu TRIM_DOCUMENT_FORMAT"
        )

        # Subtitle trim settings
        subtitle_enabled = user_dict.get("TRIM_SUBTITLE_ENABLED", False)
        buttons.data_button(
            f"Subtitle: {'✅ ON' if subtitle_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_SUBTITLE_ENABLED {'f' if subtitle_enabled else 't'}",
        )
        buttons.data_button(
            "Subtitle Encoding", f"mediatools {user_id} menu TRIM_SUBTITLE_ENCODING"
        )
        buttons.data_button(
            "Subtitle Format", f"mediatools {user_id} menu TRIM_SUBTITLE_FORMAT"
        )

        # Archive trim settings
        archive_enabled = user_dict.get("TRIM_ARCHIVE_ENABLED", False)
        buttons.data_button(
            f"Archive: {'✅ ON' if archive_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog TRIM_ARCHIVE_ENABLED {'f' if archive_enabled else 't'}",
        )
        buttons.data_button(
            "Archive Format", f"mediatools {user_id} menu TRIM_ARCHIVE_FORMAT"
        )

        buttons.data_button("Back", f"mediatools {user_id} trim", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)  # Get start and end time settings
        start_time = user_dict.get("TRIM_START_TIME", None)
        if start_time is None and hasattr(Config, "TRIM_START_TIME"):
            start_time = Config.TRIM_START_TIME
        start_time_str = f"{start_time}" if start_time else "00:00:00 (Default)"

        end_time = user_dict.get("TRIM_END_TIME", None)
        if end_time is None and hasattr(Config, "TRIM_END_TIME"):
            end_time = Config.TRIM_END_TIME
        end_time_str = f"{end_time}" if end_time else "End of file (Default)"

        # Get delete original setting
        delete_original = user_dict.get("TRIM_DELETE_ORIGINAL", None)
        if delete_original is None and hasattr(Config, "TRIM_DELETE_ORIGINAL"):
            delete_original = Config.TRIM_DELETE_ORIGINAL
        delete_original_str = "✅ Enabled" if delete_original else "❌ Disabled"

        # Get video trim settings
        video_codec = user_dict.get("TRIM_VIDEO_CODEC", None)
        if video_codec is None and hasattr(Config, "TRIM_VIDEO_CODEC"):
            video_codec = Config.TRIM_VIDEO_CODEC
        video_codec_str = f"{video_codec}" if video_codec else "copy (Default)"

        video_preset = user_dict.get("TRIM_VIDEO_PRESET", None)
        if video_preset is None and hasattr(Config, "TRIM_VIDEO_PRESET"):
            video_preset = Config.TRIM_VIDEO_PRESET
        video_preset_str = f"{video_preset}" if video_preset else "medium (Default)"

        video_format = user_dict.get("TRIM_VIDEO_FORMAT", None)
        if video_format is None and hasattr(Config, "TRIM_VIDEO_FORMAT"):
            video_format = Config.TRIM_VIDEO_FORMAT
        video_format_str = (
            f"{video_format}"
            if video_format and video_format != "none"
            else "Same as input (Default)"
        )

        # Get audio trim settings
        audio_codec = user_dict.get("TRIM_AUDIO_CODEC", None)
        if audio_codec is None and hasattr(Config, "TRIM_AUDIO_CODEC"):
            audio_codec = Config.TRIM_AUDIO_CODEC
        audio_codec_str = f"{audio_codec}" if audio_codec else "copy (Default)"

        audio_preset = user_dict.get("TRIM_AUDIO_PRESET", None)
        if audio_preset is None and hasattr(Config, "TRIM_AUDIO_PRESET"):
            audio_preset = Config.TRIM_AUDIO_PRESET
        audio_preset_str = f"{audio_preset}" if audio_preset else "medium (Default)"

        audio_format = user_dict.get("TRIM_AUDIO_FORMAT", None)
        if audio_format is None and hasattr(Config, "TRIM_AUDIO_FORMAT"):
            audio_format = Config.TRIM_AUDIO_FORMAT
        audio_format_str = (
            f"{audio_format}"
            if audio_format and audio_format != "none"
            else "Same as input (Default)"
        )

        # Get image trim settings
        image_quality = user_dict.get("TRIM_IMAGE_QUALITY", None)
        if image_quality is None and hasattr(Config, "TRIM_IMAGE_QUALITY"):
            image_quality = Config.TRIM_IMAGE_QUALITY
        if not image_quality or image_quality in {"none", "0", 0}:
            image_quality_str = "Original Quality (Default)"
        else:
            image_quality_str = f"{image_quality}"

        image_format = user_dict.get("TRIM_IMAGE_FORMAT", None)
        if image_format is None and hasattr(Config, "TRIM_IMAGE_FORMAT"):
            image_format = Config.TRIM_IMAGE_FORMAT
        image_format_str = (
            f"{image_format}"
            if image_format and image_format != "none"
            else "Same as input (Default)"
        )

        # Get document trim settings
        document_quality = user_dict.get("TRIM_DOCUMENT_QUALITY", None)
        if document_quality is None and hasattr(Config, "TRIM_DOCUMENT_QUALITY"):
            document_quality = Config.TRIM_DOCUMENT_QUALITY
        if not document_quality or document_quality in {"none", "0", 0}:
            document_quality_str = "Original Quality (Default)"
        else:
            document_quality_str = f"{document_quality}"

        document_format = user_dict.get("TRIM_DOCUMENT_FORMAT", None)
        if document_format is None and hasattr(Config, "TRIM_DOCUMENT_FORMAT"):
            document_format = Config.TRIM_DOCUMENT_FORMAT
        document_format_str = (
            f"{document_format}"
            if document_format and document_format != "none"
            else "Same as input (Default)"
        )

        # Get subtitle trim settings
        subtitle_encoding = user_dict.get("TRIM_SUBTITLE_ENCODING", None)
        if subtitle_encoding is None and hasattr(Config, "TRIM_SUBTITLE_ENCODING"):
            subtitle_encoding = Config.TRIM_SUBTITLE_ENCODING
        subtitle_encoding_str = (
            f"{subtitle_encoding}" if subtitle_encoding else "utf-8 (Default)"
        )

        subtitle_format = user_dict.get("TRIM_SUBTITLE_FORMAT", None)
        if subtitle_format is None and hasattr(Config, "TRIM_SUBTITLE_FORMAT"):
            subtitle_format = Config.TRIM_SUBTITLE_FORMAT
        subtitle_format_str = (
            f"{subtitle_format}"
            if subtitle_format and subtitle_format != "none"
            else "Same as input (Default)"
        )

        # Get archive trim settings
        archive_format = user_dict.get("TRIM_ARCHIVE_FORMAT", None)
        if archive_format is None and hasattr(Config, "TRIM_ARCHIVE_FORMAT"):
            archive_format = Config.TRIM_ARCHIVE_FORMAT
        archive_format_str = (
            f"{archive_format}"
            if archive_format and archive_format != "none"
            else "Same as input (Default)"
        )

        # Get trim enabled status for each type
        # Video trim status
        video_trim_enabled = user_dict.get("TRIM_VIDEO_ENABLED", False)
        owner_video_trim_enabled = (
            hasattr(Config, "TRIM_VIDEO_ENABLED") and Config.TRIM_VIDEO_ENABLED
        )

        if "TRIM_VIDEO_ENABLED" in user_dict:
            if video_trim_enabled:
                video_status = "✅ Enabled (User)"
            else:
                video_status = "❌ Disabled (User)"
        elif owner_video_trim_enabled:
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Audio trim status
        audio_trim_enabled = user_dict.get("TRIM_AUDIO_ENABLED", False)
        owner_audio_trim_enabled = (
            hasattr(Config, "TRIM_AUDIO_ENABLED") and Config.TRIM_AUDIO_ENABLED
        )

        if "TRIM_AUDIO_ENABLED" in user_dict:
            if audio_trim_enabled:
                audio_status = "✅ Enabled (User)"
            else:
                audio_status = "❌ Disabled (User)"
        elif owner_audio_trim_enabled:
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Image trim status
        image_trim_enabled = user_dict.get("TRIM_IMAGE_ENABLED", False)
        owner_image_trim_enabled = (
            hasattr(Config, "TRIM_IMAGE_ENABLED") and Config.TRIM_IMAGE_ENABLED
        )

        if "TRIM_IMAGE_ENABLED" in user_dict:
            if image_trim_enabled:
                image_status = "✅ Enabled (User)"
            else:
                image_status = "❌ Disabled (User)"
        elif owner_image_trim_enabled:
            image_status = "✅ Enabled (Global)"
        else:
            image_status = "❌ Disabled"

        # Document trim status
        document_trim_enabled = user_dict.get("TRIM_DOCUMENT_ENABLED", False)
        owner_document_trim_enabled = (
            hasattr(Config, "TRIM_DOCUMENT_ENABLED") and Config.TRIM_DOCUMENT_ENABLED
        )

        if "TRIM_DOCUMENT_ENABLED" in user_dict:
            if document_trim_enabled:
                document_status = "✅ Enabled (User)"
            else:
                document_status = "❌ Disabled (User)"
        elif owner_document_trim_enabled:
            document_status = "✅ Enabled (Global)"
        else:
            document_status = "❌ Disabled"

        # Subtitle trim status
        subtitle_trim_enabled = user_dict.get("TRIM_SUBTITLE_ENABLED", False)
        owner_subtitle_trim_enabled = (
            hasattr(Config, "TRIM_SUBTITLE_ENABLED") and Config.TRIM_SUBTITLE_ENABLED
        )

        if "TRIM_SUBTITLE_ENABLED" in user_dict:
            if subtitle_trim_enabled:
                subtitle_status = "✅ Enabled (User)"
            else:
                subtitle_status = "❌ Disabled (User)"
        elif owner_subtitle_trim_enabled:
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Archive trim status
        archive_trim_enabled = user_dict.get("TRIM_ARCHIVE_ENABLED", False)
        owner_archive_trim_enabled = (
            hasattr(Config, "TRIM_ARCHIVE_ENABLED") and Config.TRIM_ARCHIVE_ENABLED
        )

        if "TRIM_ARCHIVE_ENABLED" in user_dict:
            if archive_trim_enabled:
                archive_status = "✅ Enabled (User)"
            else:
                archive_status = "❌ Disabled (User)"
        elif owner_archive_trim_enabled:
            archive_status = "✅ Enabled (Global)"
        else:
            archive_status = "❌ Disabled"

        # Build text for trim_config
        text = f"""⌬ <b>Trim Configuration :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Start Time</b> → <code>{start_time_str}</code>
┠ <b>End Time</b> → <code>{end_time_str}</code>
┠ <b>Delete Original</b> → {delete_original_str}
┃
┠ <b>Video Trim</b> → {video_status}
┠ <b>Video Codec</b> → <code>{video_codec_str}</code>
┠ <b>Video Preset</b> → <code>{video_preset_str}</code>
┠ <b>Video Format</b> → <code>{video_format_str}</code>
┃
┠ <b>Audio Trim</b> → {audio_status}
┠ <b>Audio Codec</b> → <code>{audio_codec_str}</code>
┠ <b>Audio Preset</b> → <code>{audio_preset_str}</code>
┠ <b>Audio Format</b> → <code>{audio_format_str}</code>
┃
┠ <b>Image Trim</b> → {image_status}
┠ <b>Image Quality</b> → <code>{image_quality_str}</code>
┠ <b>Image Format</b> → <code>{image_format_str}</code>
┃
┠ <b>Document Trim</b> → {document_status}
┠ <b>Document Quality</b> → <code>{document_quality_str}</code>
┠ <b>Document Format</b> → <code>{document_format_str}</code>
┃
┠ <b>Subtitle Trim</b> → {subtitle_status}
┠ <b>Subtitle Encoding</b> → <code>{subtitle_encoding_str}</code>
┠ <b>Subtitle Format</b> → <code>{subtitle_format_str}</code>
┃
┠ <b>Archive Trim</b> → {archive_status}
┠ <b>Archive Format</b> → <code>{archive_format_str}</code>
┃
┖ <b>Note:</b> Settings with value 'none' will not be used in command generation"""

    elif stype == "extract_config":
        # Extract configuration menu
        # Video extract settings
        video_enabled = user_dict.get("EXTRACT_VIDEO_ENABLED", False)
        buttons.data_button(
            f"Video: {'✅ ON' if video_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_VIDEO_ENABLED {'f' if video_enabled else 't'}",
        )
        buttons.data_button(
            "Video Codec", f"mediatools {user_id} menu EXTRACT_VIDEO_CODEC"
        )
        buttons.data_button(
            "Video Format", f"mediatools {user_id} menu EXTRACT_VIDEO_FORMAT"
        )
        buttons.data_button(
            "Video Index", f"mediatools {user_id} menu EXTRACT_VIDEO_INDEX"
        )
        buttons.data_button(
            "Video Quality", f"mediatools {user_id} menu EXTRACT_VIDEO_QUALITY"
        )
        buttons.data_button(
            "Video Preset", f"mediatools {user_id} menu EXTRACT_VIDEO_PRESET"
        )
        buttons.data_button(
            "Video Bitrate", f"mediatools {user_id} menu EXTRACT_VIDEO_BITRATE"
        )
        buttons.data_button(
            "Video Resolution", f"mediatools {user_id} menu EXTRACT_VIDEO_RESOLUTION"
        )
        buttons.data_button(
            "Video FPS", f"mediatools {user_id} menu EXTRACT_VIDEO_FPS"
        )

        # Audio extract settings
        audio_enabled = user_dict.get("EXTRACT_AUDIO_ENABLED", False)
        buttons.data_button(
            f"Audio: {'✅ ON' if audio_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_AUDIO_ENABLED {'f' if audio_enabled else 't'}",
        )
        buttons.data_button(
            "Audio Codec", f"mediatools {user_id} menu EXTRACT_AUDIO_CODEC"
        )
        buttons.data_button(
            "Audio Format", f"mediatools {user_id} menu EXTRACT_AUDIO_FORMAT"
        )
        buttons.data_button(
            "Audio Index", f"mediatools {user_id} menu EXTRACT_AUDIO_INDEX"
        )
        buttons.data_button(
            "Audio Bitrate", f"mediatools {user_id} menu EXTRACT_AUDIO_BITRATE"
        )
        buttons.data_button(
            "Audio Channels", f"mediatools {user_id} menu EXTRACT_AUDIO_CHANNELS"
        )
        buttons.data_button(
            "Audio Sampling", f"mediatools {user_id} menu EXTRACT_AUDIO_SAMPLING"
        )
        buttons.data_button(
            "Audio Volume", f"mediatools {user_id} menu EXTRACT_AUDIO_VOLUME"
        )

        # Subtitle extract settings
        subtitle_enabled = user_dict.get("EXTRACT_SUBTITLE_ENABLED", False)
        buttons.data_button(
            f"Subtitle: {'✅ ON' if subtitle_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_SUBTITLE_ENABLED {'f' if subtitle_enabled else 't'}",
        )
        buttons.data_button(
            "Subtitle Codec", f"mediatools {user_id} menu EXTRACT_SUBTITLE_CODEC"
        )
        buttons.data_button(
            "Subtitle Format", f"mediatools {user_id} menu EXTRACT_SUBTITLE_FORMAT"
        )
        buttons.data_button(
            "Subtitle Index", f"mediatools {user_id} menu EXTRACT_SUBTITLE_INDEX"
        )
        buttons.data_button(
            "Subtitle Language",
            f"mediatools {user_id} menu EXTRACT_SUBTITLE_LANGUAGE",
        )
        buttons.data_button(
            "Subtitle Encoding",
            f"mediatools {user_id} menu EXTRACT_SUBTITLE_ENCODING",
        )
        buttons.data_button(
            "Subtitle Font", f"mediatools {user_id} menu EXTRACT_SUBTITLE_FONT"
        )
        buttons.data_button(
            "Subtitle Font Size",
            f"mediatools {user_id} menu EXTRACT_SUBTITLE_FONT_SIZE",
        )

        # Attachment extract settings
        attachment_enabled = user_dict.get("EXTRACT_ATTACHMENT_ENABLED", False)
        buttons.data_button(
            f"Attachment: {'✅ ON' if attachment_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_ATTACHMENT_ENABLED {'f' if attachment_enabled else 't'}",
        )
        buttons.data_button(
            "Attachment Format",
            f"mediatools {user_id} menu EXTRACT_ATTACHMENT_FORMAT",
        )
        buttons.data_button(
            "Attachment Index", f"mediatools {user_id} menu EXTRACT_ATTACHMENT_INDEX"
        )
        buttons.data_button(
            "Attachment Filter",
            f"mediatools {user_id} menu EXTRACT_ATTACHMENT_FILTER",
        )

        # Maintain quality toggle
        maintain_quality = user_dict.get("EXTRACT_MAINTAIN_QUALITY", True)
        buttons.data_button(
            f"Quality: {'✅ High' if maintain_quality else '❌ Normal'}",
            f"mediatools {user_id} tog EXTRACT_MAINTAIN_QUALITY {'f' if maintain_quality else 't'}",
        )

        # Delete original toggle
        delete_original = user_dict.get("EXTRACT_DELETE_ORIGINAL", True)
        buttons.data_button(
            f"Delete Original: {'✅ ON' if delete_original else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_DELETE_ORIGINAL {'f' if delete_original else 't'}",
        )

        buttons.data_button("Back", f"mediatools {user_id} extract", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get video extract settings
        video_codec = user_dict.get("EXTRACT_VIDEO_CODEC", None)
        if video_codec is None and hasattr(Config, "EXTRACT_VIDEO_CODEC"):
            video_codec = Config.EXTRACT_VIDEO_CODEC
        video_codec_str = f"{video_codec}" if video_codec else "None (Default)"

        video_format = user_dict.get("EXTRACT_VIDEO_FORMAT", None)
        if video_format is None and hasattr(Config, "EXTRACT_VIDEO_FORMAT"):
            video_format = Config.EXTRACT_VIDEO_FORMAT
        video_format_str = f"{video_format}" if video_format else "None (Default)"

        video_index = user_dict.get("EXTRACT_VIDEO_INDEX", None)
        if video_index is None and hasattr(Config, "EXTRACT_VIDEO_INDEX"):
            video_index = Config.EXTRACT_VIDEO_INDEX
        video_index_str = (
            f"{video_index}" if video_index is not None else "All (Default)"
        )

        video_quality = user_dict.get("EXTRACT_VIDEO_QUALITY", None)
        if video_quality is None and hasattr(Config, "EXTRACT_VIDEO_QUALITY"):
            video_quality = Config.EXTRACT_VIDEO_QUALITY
        video_quality_str = f"{video_quality}" if video_quality else "None (Default)"

        video_preset = user_dict.get("EXTRACT_VIDEO_PRESET", None)
        if video_preset is None and hasattr(Config, "EXTRACT_VIDEO_PRESET"):
            video_preset = Config.EXTRACT_VIDEO_PRESET
        video_preset_str = f"{video_preset}" if video_preset else "None (Default)"

        video_bitrate = user_dict.get("EXTRACT_VIDEO_BITRATE", None)
        if video_bitrate is None and hasattr(Config, "EXTRACT_VIDEO_BITRATE"):
            video_bitrate = Config.EXTRACT_VIDEO_BITRATE
        video_bitrate_str = f"{video_bitrate}" if video_bitrate else "None (Default)"

        video_resolution = user_dict.get("EXTRACT_VIDEO_RESOLUTION", None)
        if video_resolution is None and hasattr(Config, "EXTRACT_VIDEO_RESOLUTION"):
            video_resolution = Config.EXTRACT_VIDEO_RESOLUTION
        video_resolution_str = (
            f"{video_resolution}" if video_resolution else "None (Default)"
        )

        video_fps = user_dict.get("EXTRACT_VIDEO_FPS", None)
        if video_fps is None and hasattr(Config, "EXTRACT_VIDEO_FPS"):
            video_fps = Config.EXTRACT_VIDEO_FPS
        video_fps_str = f"{video_fps}" if video_fps else "None (Default)"

        # Get audio extract settings
        audio_codec = user_dict.get("EXTRACT_AUDIO_CODEC", None)
        if audio_codec is None and hasattr(Config, "EXTRACT_AUDIO_CODEC"):
            audio_codec = Config.EXTRACT_AUDIO_CODEC
        audio_codec_str = f"{audio_codec}" if audio_codec else "None (Default)"

        audio_format = user_dict.get("EXTRACT_AUDIO_FORMAT", None)
        if audio_format is None and hasattr(Config, "EXTRACT_AUDIO_FORMAT"):
            audio_format = Config.EXTRACT_AUDIO_FORMAT
        audio_format_str = f"{audio_format}" if audio_format else "None (Default)"

        audio_index = user_dict.get("EXTRACT_AUDIO_INDEX", None)
        if audio_index is None and hasattr(Config, "EXTRACT_AUDIO_INDEX"):
            audio_index = Config.EXTRACT_AUDIO_INDEX
        audio_index_str = (
            f"{audio_index}" if audio_index is not None else "All (Default)"
        )

        audio_bitrate = user_dict.get("EXTRACT_AUDIO_BITRATE", None)
        if audio_bitrate is None and hasattr(Config, "EXTRACT_AUDIO_BITRATE"):
            audio_bitrate = Config.EXTRACT_AUDIO_BITRATE
        audio_bitrate_str = f"{audio_bitrate}" if audio_bitrate else "None (Default)"

        audio_channels = user_dict.get("EXTRACT_AUDIO_CHANNELS", None)
        if audio_channels is None and hasattr(Config, "EXTRACT_AUDIO_CHANNELS"):
            audio_channels = Config.EXTRACT_AUDIO_CHANNELS
        audio_channels_str = (
            f"{audio_channels}" if audio_channels else "None (Default)"
        )

        audio_sampling = user_dict.get("EXTRACT_AUDIO_SAMPLING", None)
        if audio_sampling is None and hasattr(Config, "EXTRACT_AUDIO_SAMPLING"):
            audio_sampling = Config.EXTRACT_AUDIO_SAMPLING
        audio_sampling_str = (
            f"{audio_sampling}" if audio_sampling else "None (Default)"
        )

        audio_volume = user_dict.get("EXTRACT_AUDIO_VOLUME", None)
        if audio_volume is None and hasattr(Config, "EXTRACT_AUDIO_VOLUME"):
            audio_volume = Config.EXTRACT_AUDIO_VOLUME
        audio_volume_str = f"{audio_volume}" if audio_volume else "None (Default)"

        # Get subtitle extract settings
        subtitle_codec = user_dict.get("EXTRACT_SUBTITLE_CODEC", None)
        if subtitle_codec is None and hasattr(Config, "EXTRACT_SUBTITLE_CODEC"):
            subtitle_codec = Config.EXTRACT_SUBTITLE_CODEC
        subtitle_codec_str = (
            f"{subtitle_codec}" if subtitle_codec else "None (Default)"
        )

        subtitle_format = user_dict.get("EXTRACT_SUBTITLE_FORMAT", None)
        if subtitle_format is None and hasattr(Config, "EXTRACT_SUBTITLE_FORMAT"):
            subtitle_format = Config.EXTRACT_SUBTITLE_FORMAT
        subtitle_format_str = (
            f"{subtitle_format}" if subtitle_format else "None (Default)"
        )

        subtitle_index = user_dict.get("EXTRACT_SUBTITLE_INDEX", None)
        if subtitle_index is None and hasattr(Config, "EXTRACT_SUBTITLE_INDEX"):
            subtitle_index = Config.EXTRACT_SUBTITLE_INDEX
        subtitle_index_str = (
            f"{subtitle_index}" if subtitle_index is not None else "All (Default)"
        )

        subtitle_language = user_dict.get("EXTRACT_SUBTITLE_LANGUAGE", None)
        if subtitle_language is None and hasattr(
            Config, "EXTRACT_SUBTITLE_LANGUAGE"
        ):
            subtitle_language = Config.EXTRACT_SUBTITLE_LANGUAGE
        subtitle_language_str = (
            f"{subtitle_language}" if subtitle_language else "None (Default)"
        )

        subtitle_encoding = user_dict.get("EXTRACT_SUBTITLE_ENCODING", None)
        if subtitle_encoding is None and hasattr(
            Config, "EXTRACT_SUBTITLE_ENCODING"
        ):
            subtitle_encoding = Config.EXTRACT_SUBTITLE_ENCODING
        subtitle_encoding_str = (
            f"{subtitle_encoding}" if subtitle_encoding else "None (Default)"
        )

        subtitle_font = user_dict.get("EXTRACT_SUBTITLE_FONT", None)
        if subtitle_font is None and hasattr(Config, "EXTRACT_SUBTITLE_FONT"):
            subtitle_font = Config.EXTRACT_SUBTITLE_FONT
        subtitle_font_str = f"{subtitle_font}" if subtitle_font else "None (Default)"

        subtitle_font_size = user_dict.get("EXTRACT_SUBTITLE_FONT_SIZE", None)
        if subtitle_font_size is None and hasattr(
            Config, "EXTRACT_SUBTITLE_FONT_SIZE"
        ):
            subtitle_font_size = Config.EXTRACT_SUBTITLE_FONT_SIZE
        subtitle_font_size_str = (
            f"{subtitle_font_size}" if subtitle_font_size else "None (Default)"
        )

        # Get attachment extract settings
        attachment_format = user_dict.get("EXTRACT_ATTACHMENT_FORMAT", None)
        if attachment_format is None and hasattr(
            Config, "EXTRACT_ATTACHMENT_FORMAT"
        ):
            attachment_format = Config.EXTRACT_ATTACHMENT_FORMAT
        attachment_format_str = (
            f"{attachment_format}" if attachment_format else "None (Default)"
        )

        attachment_index = user_dict.get("EXTRACT_ATTACHMENT_INDEX", None)
        if attachment_index is None and hasattr(Config, "EXTRACT_ATTACHMENT_INDEX"):
            attachment_index = Config.EXTRACT_ATTACHMENT_INDEX
        attachment_index_str = (
            f"{attachment_index}"
            if attachment_index is not None
            else "All (Default)"
        )

        attachment_filter = user_dict.get("EXTRACT_ATTACHMENT_FILTER", None)
        if attachment_filter is None and hasattr(
            Config, "EXTRACT_ATTACHMENT_FILTER"
        ):
            attachment_filter = Config.EXTRACT_ATTACHMENT_FILTER
        attachment_filter_str = (
            f"{attachment_filter}" if attachment_filter else "None (Default)"
        )

        # Get extract enabled status for each type
        # Video extract status
        video_extract_enabled = user_dict.get("EXTRACT_VIDEO_ENABLED", False)
        owner_video_extract_enabled = (
            hasattr(Config, "EXTRACT_VIDEO_ENABLED") and Config.EXTRACT_VIDEO_ENABLED
        )

        if "EXTRACT_VIDEO_ENABLED" in user_dict:
            if video_extract_enabled:
                video_status = "✅ Enabled (User)"
            else:
                video_status = "❌ Disabled (User)"
        elif owner_video_extract_enabled:
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Audio extract status
        audio_extract_enabled = user_dict.get("EXTRACT_AUDIO_ENABLED", False)
        owner_audio_extract_enabled = (
            hasattr(Config, "EXTRACT_AUDIO_ENABLED") and Config.EXTRACT_AUDIO_ENABLED
        )

        if "EXTRACT_AUDIO_ENABLED" in user_dict:
            if audio_extract_enabled:
                audio_status = "✅ Enabled (User)"
            else:
                audio_status = "❌ Disabled (User)"
        elif owner_audio_extract_enabled:
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Subtitle extract status
        subtitle_extract_enabled = user_dict.get("EXTRACT_SUBTITLE_ENABLED", False)
        owner_subtitle_extract_enabled = (
            hasattr(Config, "EXTRACT_SUBTITLE_ENABLED")
            and Config.EXTRACT_SUBTITLE_ENABLED
        )

        if "EXTRACT_SUBTITLE_ENABLED" in user_dict:
            if subtitle_extract_enabled:
                subtitle_status = "✅ Enabled (User)"
            else:
                subtitle_status = "❌ Disabled (User)"
        elif owner_subtitle_extract_enabled:
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Attachment extract status
        attachment_extract_enabled = user_dict.get(
            "EXTRACT_ATTACHMENT_ENABLED", False
        )
        owner_attachment_extract_enabled = (
            hasattr(Config, "EXTRACT_ATTACHMENT_ENABLED")
            and Config.EXTRACT_ATTACHMENT_ENABLED
        )

        if "EXTRACT_ATTACHMENT_ENABLED" in user_dict:
            if attachment_extract_enabled:
                attachment_status = "✅ Enabled (User)"
            else:
                attachment_status = "❌ Disabled (User)"
        elif owner_attachment_extract_enabled:
            attachment_status = "✅ Enabled (Global)"
        else:
            attachment_status = "❌ Disabled"

        # Get maintain quality status
        maintain_quality_enabled = user_dict.get("EXTRACT_MAINTAIN_QUALITY", True)
        owner_maintain_quality_enabled = (
            hasattr(Config, "EXTRACT_MAINTAIN_QUALITY")
            and Config.EXTRACT_MAINTAIN_QUALITY
        )

        if "EXTRACT_MAINTAIN_QUALITY" in user_dict:
            if maintain_quality_enabled:
                maintain_quality_status = "✅ Enabled (User)"
            else:
                maintain_quality_status = "❌ Disabled (User)"
        elif owner_maintain_quality_enabled:
            maintain_quality_status = "✅ Enabled (Global)"
        else:
            maintain_quality_status = "✅ Enabled (Default)"

        # Get delete original status
        delete_original_enabled = user_dict.get("EXTRACT_DELETE_ORIGINAL", True)
        owner_delete_original_enabled = (
            hasattr(Config, "EXTRACT_DELETE_ORIGINAL")
            and Config.EXTRACT_DELETE_ORIGINAL
        )

        if "EXTRACT_DELETE_ORIGINAL" in user_dict:
            if delete_original_enabled:
                delete_original_status = "✅ Enabled (User)"
            else:
                delete_original_status = "❌ Disabled (User)"
        elif owner_delete_original_enabled:
            delete_original_status = "✅ Enabled (Global)"
        else:
            delete_original_status = "✅ Enabled (Default)"

        text = f"""⌬ <b>Extract Configuration :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Video Extract</b> → {video_status}
┠ <b>Video Codec</b> → <code>{video_codec_str}</code>
┠ <b>Video Format</b> → <code>{video_format_str}</code>
┠ <b>Video Index</b> → <code>{video_index_str}</code>
┠ <b>Video Quality</b> → <code>{video_quality_str}</code>
┠ <b>Video Preset</b> → <code>{video_preset_str}</code>
┠ <b>Video Bitrate</b> → <code>{video_bitrate_str}</code>
┠ <b>Video Resolution</b> → <code>{video_resolution_str}</code>
┠ <b>Video FPS</b> → <code>{video_fps_str}</code>
┃
┠ <b>Audio Extract</b> → {audio_status}
┠ <b>Audio Codec</b> → <code>{audio_codec_str}</code>
┠ <b>Audio Format</b> → <code>{audio_format_str}</code>
┠ <b>Audio Index</b> → <code>{audio_index_str}</code>
┠ <b>Audio Bitrate</b> → <code>{audio_bitrate_str}</code>
┠ <b>Audio Channels</b> → <code>{audio_channels_str}</code>
┠ <b>Audio Sampling</b> → <code>{audio_sampling_str}</code>
┠ <b>Audio Volume</b> → <code>{audio_volume_str}</code>
┃
┠ <b>Subtitle Extract</b> → {subtitle_status}
┠ <b>Subtitle Codec</b> → <code>{subtitle_codec_str}</code>
┠ <b>Subtitle Format</b> → <code>{subtitle_format_str}</code>
┠ <b>Subtitle Index</b> → <code>{subtitle_index_str}</code>
┠ <b>Subtitle Language</b> → <code>{subtitle_language_str}</code>
┠ <b>Subtitle Encoding</b> → <code>{subtitle_encoding_str}</code>
┠ <b>Subtitle Font</b> → <code>{subtitle_font_str}</code>
┠ <b>Subtitle Font Size</b> → <code>{subtitle_font_size_str}</code>
┃
┠ <b>Attachment Extract</b> → {attachment_status}
┠ <b>Attachment Format</b> → <code>{attachment_format_str}</code>
┠ <b>Attachment Index</b> → <code>{attachment_index_str}</code>
┠ <b>Attachment Filter</b> → <code>{attachment_filter_str}</code>
┃
┠ <b>Maintain Quality</b> → {maintain_quality_status}
┖ <b>Delete Original</b> → {delete_original_status}"""

    elif stype == "compression_config":
        # Compression configuration menu
        # Add global delete original toggle
        delete_original = user_dict.get("COMPRESSION_DELETE_ORIGINAL", False)
        buttons.data_button(
            f"Delete Original: {'✅ ON' if delete_original else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_DELETE_ORIGINAL {'f' if delete_original else 't'}",
        )

        # Video compression settings
        video_enabled = user_dict.get("COMPRESSION_VIDEO_ENABLED", False)
        buttons.data_button(
            f"Video: {'✅ ON' if video_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_VIDEO_ENABLED {'f' if video_enabled else 't'}",
        )
        buttons.data_button(
            "Video Preset", f"mediatools {user_id} menu COMPRESSION_VIDEO_PRESET"
        )
        buttons.data_button(
            "Video CRF", f"mediatools {user_id} menu COMPRESSION_VIDEO_CRF"
        )
        buttons.data_button(
            "Video Codec", f"mediatools {user_id} menu COMPRESSION_VIDEO_CODEC"
        )
        buttons.data_button(
            "Video Tune", f"mediatools {user_id} menu COMPRESSION_VIDEO_TUNE"
        )
        buttons.data_button(
            "Video Pixel Format",
            f"mediatools {user_id} menu COMPRESSION_VIDEO_PIXEL_FORMAT",
        )
        buttons.data_button(
            "Video Format", f"mediatools {user_id} menu COMPRESSION_VIDEO_FORMAT"
        )

        # Audio compression settings
        audio_enabled = user_dict.get("COMPRESSION_AUDIO_ENABLED", False)
        buttons.data_button(
            f"Audio: {'✅ ON' if audio_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_AUDIO_ENABLED {'f' if audio_enabled else 't'}",
        )
        buttons.data_button(
            "Audio Preset", f"mediatools {user_id} menu COMPRESSION_AUDIO_PRESET"
        )
        buttons.data_button(
            "Audio Codec", f"mediatools {user_id} menu COMPRESSION_AUDIO_CODEC"
        )
        buttons.data_button(
            "Audio Bitrate", f"mediatools {user_id} menu COMPRESSION_AUDIO_BITRATE"
        )
        buttons.data_button(
            "Audio Channels", f"mediatools {user_id} menu COMPRESSION_AUDIO_CHANNELS"
        )
        buttons.data_button(
            "Audio Format", f"mediatools {user_id} menu COMPRESSION_AUDIO_FORMAT"
        )

        # Image compression settings
        image_enabled = user_dict.get("COMPRESSION_IMAGE_ENABLED", False)
        buttons.data_button(
            f"Image: {'✅ ON' if image_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_IMAGE_ENABLED {'f' if image_enabled else 't'}",
        )
        buttons.data_button(
            "Image Preset", f"mediatools {user_id} menu COMPRESSION_IMAGE_PRESET"
        )
        buttons.data_button(
            "Image Quality", f"mediatools {user_id} menu COMPRESSION_IMAGE_QUALITY"
        )
        buttons.data_button(
            "Image Resize", f"mediatools {user_id} menu COMPRESSION_IMAGE_RESIZE"
        )
        buttons.data_button(
            "Image Format", f"mediatools {user_id} menu COMPRESSION_IMAGE_FORMAT"
        )

        # Document compression settings
        document_enabled = user_dict.get("COMPRESSION_DOCUMENT_ENABLED", False)
        buttons.data_button(
            f"Document: {'✅ ON' if document_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_DOCUMENT_ENABLED {'f' if document_enabled else 't'}",
        )
        buttons.data_button(
            "Document Preset",
            f"mediatools {user_id} menu COMPRESSION_DOCUMENT_PRESET",
        )
        buttons.data_button(
            "Document DPI", f"mediatools {user_id} menu COMPRESSION_DOCUMENT_DPI"
        )
        buttons.data_button(
            "Document Format",
            f"mediatools {user_id} menu COMPRESSION_DOCUMENT_FORMAT",
        )

        # Subtitle compression settings
        subtitle_enabled = user_dict.get("COMPRESSION_SUBTITLE_ENABLED", False)
        buttons.data_button(
            f"Subtitle: {'✅ ON' if subtitle_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_SUBTITLE_ENABLED {'f' if subtitle_enabled else 't'}",
        )
        buttons.data_button(
            "Subtitle Preset",
            f"mediatools {user_id} menu COMPRESSION_SUBTITLE_PRESET",
        )
        buttons.data_button(
            "Subtitle Encoding",
            f"mediatools {user_id} menu COMPRESSION_SUBTITLE_ENCODING",
        )
        buttons.data_button(
            "Subtitle Format",
            f"mediatools {user_id} menu COMPRESSION_SUBTITLE_FORMAT",
        )

        # Archive compression settings
        archive_enabled = user_dict.get("COMPRESSION_ARCHIVE_ENABLED", False)
        buttons.data_button(
            f"Archive: {'✅ ON' if archive_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog COMPRESSION_ARCHIVE_ENABLED {'f' if archive_enabled else 't'}",
        )
        buttons.data_button(
            "Archive Preset", f"mediatools {user_id} menu COMPRESSION_ARCHIVE_PRESET"
        )
        buttons.data_button(
            "Archive Level", f"mediatools {user_id} menu COMPRESSION_ARCHIVE_LEVEL"
        )
        buttons.data_button(
            "Archive Method", f"mediatools {user_id} menu COMPRESSION_ARCHIVE_METHOD"
        )
        buttons.data_button(
            "Archive Format", f"mediatools {user_id} menu COMPRESSION_ARCHIVE_FORMAT"
        )

        buttons.data_button("Back", f"mediatools {user_id} compression", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get delete original setting
        delete_original = user_dict.get("COMPRESSION_DELETE_ORIGINAL", False)
        owner_delete_original = (
            hasattr(Config, "COMPRESSION_DELETE_ORIGINAL")
            and Config.COMPRESSION_DELETE_ORIGINAL
        )

        if "COMPRESSION_DELETE_ORIGINAL" in user_dict:
            if delete_original:
                delete_original_status = "✅ Enabled (User)"
            else:
                delete_original_status = "❌ Disabled (User)"
        elif owner_delete_original:
            delete_original_status = "✅ Enabled (Global)"
        else:
            delete_original_status = "❌ Disabled (Default)"

        # Get video compression settings
        video_preset = user_dict.get("COMPRESSION_VIDEO_PRESET", None)
        if video_preset is None and hasattr(Config, "COMPRESSION_VIDEO_PRESET"):
            video_preset = Config.COMPRESSION_VIDEO_PRESET
        video_preset_str = f"{video_preset}" if video_preset else "medium (Default)"

        video_crf = user_dict.get("COMPRESSION_VIDEO_CRF", None)
        if video_crf is None and hasattr(Config, "COMPRESSION_VIDEO_CRF"):
            video_crf = Config.COMPRESSION_VIDEO_CRF
        video_crf_str = f"{video_crf}" if video_crf else "23 (Default)"

        video_codec = user_dict.get("COMPRESSION_VIDEO_CODEC", None)
        if video_codec is None and hasattr(Config, "COMPRESSION_VIDEO_CODEC"):
            video_codec = Config.COMPRESSION_VIDEO_CODEC
        video_codec_str = f"{video_codec}" if video_codec else "libx264 (Default)"

        video_tune = user_dict.get("COMPRESSION_VIDEO_TUNE", None)
        if video_tune is None and hasattr(Config, "COMPRESSION_VIDEO_TUNE"):
            video_tune = Config.COMPRESSION_VIDEO_TUNE
        video_tune_str = f"{video_tune}" if video_tune else "film (Default)"

        video_pixel_format = user_dict.get("COMPRESSION_VIDEO_PIXEL_FORMAT", None)
        if video_pixel_format is None and hasattr(
            Config, "COMPRESSION_VIDEO_PIXEL_FORMAT"
        ):
            video_pixel_format = Config.COMPRESSION_VIDEO_PIXEL_FORMAT
        video_pixel_format_str = (
            f"{video_pixel_format}" if video_pixel_format else "yuv420p (Default)"
        )

        video_format = user_dict.get("COMPRESSION_VIDEO_FORMAT", None)
        if video_format is None and hasattr(Config, "COMPRESSION_VIDEO_FORMAT"):
            video_format = Config.COMPRESSION_VIDEO_FORMAT
        video_format_str = f"{video_format}" if video_format else "none (Default)"

        # Get audio compression settings
        audio_preset = user_dict.get("COMPRESSION_AUDIO_PRESET", None)
        if audio_preset is None and hasattr(Config, "COMPRESSION_AUDIO_PRESET"):
            audio_preset = Config.COMPRESSION_AUDIO_PRESET
        audio_preset_str = f"{audio_preset}" if audio_preset else "medium (Default)"

        audio_codec = user_dict.get("COMPRESSION_AUDIO_CODEC", None)
        if audio_codec is None and hasattr(Config, "COMPRESSION_AUDIO_CODEC"):
            audio_codec = Config.COMPRESSION_AUDIO_CODEC
        audio_codec_str = f"{audio_codec}" if audio_codec else "aac (Default)"

        audio_bitrate = user_dict.get("COMPRESSION_AUDIO_BITRATE", None)
        if audio_bitrate is None and hasattr(Config, "COMPRESSION_AUDIO_BITRATE"):
            audio_bitrate = Config.COMPRESSION_AUDIO_BITRATE
        audio_bitrate_str = f"{audio_bitrate}" if audio_bitrate else "128k (Default)"

        audio_channels = user_dict.get("COMPRESSION_AUDIO_CHANNELS", None)
        if audio_channels is None and hasattr(Config, "COMPRESSION_AUDIO_CHANNELS"):
            audio_channels = Config.COMPRESSION_AUDIO_CHANNELS
        audio_channels_str = f"{audio_channels}" if audio_channels else "2 (Default)"

        audio_format = user_dict.get("COMPRESSION_AUDIO_FORMAT", None)
        if audio_format is None and hasattr(Config, "COMPRESSION_AUDIO_FORMAT"):
            audio_format = Config.COMPRESSION_AUDIO_FORMAT
        audio_format_str = f"{audio_format}" if audio_format else "none (Default)"

        # Get image compression settings
        image_preset = user_dict.get("COMPRESSION_IMAGE_PRESET", None)
        if image_preset is None and hasattr(Config, "COMPRESSION_IMAGE_PRESET"):
            image_preset = Config.COMPRESSION_IMAGE_PRESET
        image_preset_str = f"{image_preset}" if image_preset else "medium (Default)"

        image_quality = user_dict.get("COMPRESSION_IMAGE_QUALITY", None)
        if image_quality is None and hasattr(Config, "COMPRESSION_IMAGE_QUALITY"):
            image_quality = Config.COMPRESSION_IMAGE_QUALITY
        image_quality_str = f"{image_quality}" if image_quality else "80 (Default)"

        image_resize = user_dict.get("COMPRESSION_IMAGE_RESIZE", None)
        if image_resize is None and hasattr(Config, "COMPRESSION_IMAGE_RESIZE"):
            image_resize = Config.COMPRESSION_IMAGE_RESIZE
        image_resize_str = f"{image_resize}" if image_resize else "none (Default)"

        image_format = user_dict.get("COMPRESSION_IMAGE_FORMAT", None)
        if image_format is None and hasattr(Config, "COMPRESSION_IMAGE_FORMAT"):
            image_format = Config.COMPRESSION_IMAGE_FORMAT
        image_format_str = f"{image_format}" if image_format else "none (Default)"

        # Get document compression settings
        document_preset = user_dict.get("COMPRESSION_DOCUMENT_PRESET", None)
        if document_preset is None and hasattr(
            Config, "COMPRESSION_DOCUMENT_PRESET"
        ):
            document_preset = Config.COMPRESSION_DOCUMENT_PRESET
        document_preset_str = (
            f"{document_preset}" if document_preset else "medium (Default)"
        )

        document_dpi = user_dict.get("COMPRESSION_DOCUMENT_DPI", None)
        if document_dpi is None and hasattr(Config, "COMPRESSION_DOCUMENT_DPI"):
            document_dpi = Config.COMPRESSION_DOCUMENT_DPI
        document_dpi_str = f"{document_dpi}" if document_dpi else "150 (Default)"

        document_format = user_dict.get("COMPRESSION_DOCUMENT_FORMAT", None)
        if document_format is None and hasattr(
            Config, "COMPRESSION_DOCUMENT_FORMAT"
        ):
            document_format = Config.COMPRESSION_DOCUMENT_FORMAT
        document_format_str = (
            f"{document_format}" if document_format else "none (Default)"
        )

        # Get subtitle compression settings
        subtitle_preset = user_dict.get("COMPRESSION_SUBTITLE_PRESET", None)
        if subtitle_preset is None and hasattr(
            Config, "COMPRESSION_SUBTITLE_PRESET"
        ):
            subtitle_preset = Config.COMPRESSION_SUBTITLE_PRESET
        subtitle_preset_str = (
            f"{subtitle_preset}" if subtitle_preset else "medium (Default)"
        )

        subtitle_encoding = user_dict.get("COMPRESSION_SUBTITLE_ENCODING", None)
        if subtitle_encoding is None and hasattr(
            Config, "COMPRESSION_SUBTITLE_ENCODING"
        ):
            subtitle_encoding = Config.COMPRESSION_SUBTITLE_ENCODING
        subtitle_encoding_str = (
            f"{subtitle_encoding}" if subtitle_encoding else "utf-8 (Default)"
        )

        subtitle_format = user_dict.get("COMPRESSION_SUBTITLE_FORMAT", None)
        if subtitle_format is None and hasattr(
            Config, "COMPRESSION_SUBTITLE_FORMAT"
        ):
            subtitle_format = Config.COMPRESSION_SUBTITLE_FORMAT
        subtitle_format_str = (
            f"{subtitle_format}" if subtitle_format else "none (Default)"
        )

        # Get archive compression settings
        archive_preset = user_dict.get("COMPRESSION_ARCHIVE_PRESET", None)
        if archive_preset is None and hasattr(Config, "COMPRESSION_ARCHIVE_PRESET"):
            archive_preset = Config.COMPRESSION_ARCHIVE_PRESET
        archive_preset_str = (
            f"{archive_preset}" if archive_preset else "medium (Default)"
        )

        archive_level = user_dict.get("COMPRESSION_ARCHIVE_LEVEL", None)
        if archive_level is None and hasattr(Config, "COMPRESSION_ARCHIVE_LEVEL"):
            archive_level = Config.COMPRESSION_ARCHIVE_LEVEL
        archive_level_str = f"{archive_level}" if archive_level else "5 (Default)"

        archive_method = user_dict.get("COMPRESSION_ARCHIVE_METHOD", None)
        if archive_method is None and hasattr(Config, "COMPRESSION_ARCHIVE_METHOD"):
            archive_method = Config.COMPRESSION_ARCHIVE_METHOD
        archive_method_str = (
            f"{archive_method}" if archive_method else "deflate (Default)"
        )

        archive_format = user_dict.get("COMPRESSION_ARCHIVE_FORMAT", None)
        if archive_format is None and hasattr(Config, "COMPRESSION_ARCHIVE_FORMAT"):
            archive_format = Config.COMPRESSION_ARCHIVE_FORMAT
        archive_format_str = (
            f"{archive_format}" if archive_format else "none (Default)"
        )

        # Get compression enabled status for each type
        # Video compression status
        video_compression_enabled = user_dict.get("COMPRESSION_VIDEO_ENABLED", False)
        owner_video_compression_enabled = (
            hasattr(Config, "COMPRESSION_VIDEO_ENABLED")
            and Config.COMPRESSION_VIDEO_ENABLED
        )

        if "COMPRESSION_VIDEO_ENABLED" in user_dict:
            if video_compression_enabled:
                video_status = "✅ Enabled (User)"
            else:
                video_status = "❌ Disabled (User)"
        elif owner_video_compression_enabled:
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Audio compression status
        audio_compression_enabled = user_dict.get("COMPRESSION_AUDIO_ENABLED", False)
        owner_audio_compression_enabled = (
            hasattr(Config, "COMPRESSION_AUDIO_ENABLED")
            and Config.COMPRESSION_AUDIO_ENABLED
        )

        if "COMPRESSION_AUDIO_ENABLED" in user_dict:
            if audio_compression_enabled:
                audio_status = "✅ Enabled (User)"
            else:
                audio_status = "❌ Disabled (User)"
        elif owner_audio_compression_enabled:
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Image compression status
        image_compression_enabled = user_dict.get("COMPRESSION_IMAGE_ENABLED", False)
        owner_image_compression_enabled = (
            hasattr(Config, "COMPRESSION_IMAGE_ENABLED")
            and Config.COMPRESSION_IMAGE_ENABLED
        )

        if "COMPRESSION_IMAGE_ENABLED" in user_dict:
            if image_compression_enabled:
                image_status = "✅ Enabled (User)"
            else:
                image_status = "❌ Disabled (User)"
        elif owner_image_compression_enabled:
            image_status = "✅ Enabled (Global)"
        else:
            image_status = "❌ Disabled"

        # Document compression status
        document_compression_enabled = user_dict.get(
            "COMPRESSION_DOCUMENT_ENABLED", False
        )
        owner_document_compression_enabled = (
            hasattr(Config, "COMPRESSION_DOCUMENT_ENABLED")
            and Config.COMPRESSION_DOCUMENT_ENABLED
        )

        if "COMPRESSION_DOCUMENT_ENABLED" in user_dict:
            if document_compression_enabled:
                document_status = "✅ Enabled (User)"
            else:
                document_status = "❌ Disabled (User)"
        elif owner_document_compression_enabled:
            document_status = "✅ Enabled (Global)"
        else:
            document_status = "❌ Disabled"

        # Subtitle compression status
        subtitle_compression_enabled = user_dict.get(
            "COMPRESSION_SUBTITLE_ENABLED", False
        )
        owner_subtitle_compression_enabled = (
            hasattr(Config, "COMPRESSION_SUBTITLE_ENABLED")
            and Config.COMPRESSION_SUBTITLE_ENABLED
        )

        if "COMPRESSION_SUBTITLE_ENABLED" in user_dict:
            if subtitle_compression_enabled:
                subtitle_status = "✅ Enabled (User)"
            else:
                subtitle_status = "❌ Disabled (User)"
        elif owner_subtitle_compression_enabled:
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Archive compression status
        archive_compression_enabled = user_dict.get(
            "COMPRESSION_ARCHIVE_ENABLED", False
        )
        owner_archive_compression_enabled = (
            hasattr(Config, "COMPRESSION_ARCHIVE_ENABLED")
            and Config.COMPRESSION_ARCHIVE_ENABLED
        )

        if "COMPRESSION_ARCHIVE_ENABLED" in user_dict:
            if archive_compression_enabled:
                archive_status = "✅ Enabled (User)"
            else:
                archive_status = "❌ Disabled (User)"
        elif owner_archive_compression_enabled:
            archive_status = "✅ Enabled (Global)"
        else:
            archive_status = "❌ Disabled"

        text = f"""⌬ <b>Compression Configuration :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Delete Original</b> → {delete_original_status}
┃
┠ <b>Video Compression</b> → {video_status}
┠ <b>Video Preset</b> → <code>{video_preset_str}</code>
┠ <b>Video CRF</b> → <code>{video_crf_str}</code>
┠ <b>Video Codec</b> → <code>{video_codec_str}</code>
┠ <b>Video Tune</b> → <code>{video_tune_str}</code>
┠ <b>Video Pixel Format</b> → <code>{video_pixel_format_str}</code>
┠ <b>Video Format</b> → <code>{video_format_str}</code>
┃
┠ <b>Audio Compression</b> → {audio_status}
┠ <b>Audio Preset</b> → <code>{audio_preset_str}</code>
┠ <b>Audio Codec</b> → <code>{audio_codec_str}</code>
┠ <b>Audio Bitrate</b> → <code>{audio_bitrate_str}</code>
┠ <b>Audio Channels</b> → <code>{audio_channels_str}</code>
┠ <b>Audio Format</b> → <code>{audio_format_str}</code>
┃
┠ <b>Image Compression</b> → {image_status}
┠ <b>Image Preset</b> → <code>{image_preset_str}</code>
┠ <b>Image Quality</b> → <code>{image_quality_str}</code>
┠ <b>Image Resize</b> → <code>{image_resize_str}</code>
┠ <b>Image Format</b> → <code>{image_format_str}</code>
┃
┠ <b>Document Compression</b> → {document_status}
┠ <b>Document Preset</b> → <code>{document_preset_str}</code>
┠ <b>Document DPI</b> → <code>{document_dpi_str}</code>
┠ <b>Document Format</b> → <code>{document_format_str}</code>
┃
┠ <b>Subtitle Compression</b> → {subtitle_status}
┠ <b>Subtitle Preset</b> → <code>{subtitle_preset_str}</code>
┠ <b>Subtitle Encoding</b> → <code>{subtitle_encoding_str}</code>
┠ <b>Subtitle Format</b> → <code>{subtitle_format_str}</code>
┃
┠ <b>Archive Compression</b> → {archive_status}
┠ <b>Archive Preset</b> → <code>{archive_preset_str}</code>
┠ <b>Archive Level</b> → <code>{archive_level_str}</code>
┠ <b>Archive Method</b> → <code>{archive_method_str}</code>
┖ <b>Archive Format</b> → <code>{archive_format_str}</code>"""

    elif stype == "convert":
        # Convert settings menu
        convert_enabled = user_dict.get("CONVERT_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if convert_enabled else "❌ Disabled",
            f"mediatools {user_id} tog CONVERT_ENABLED {'f' if convert_enabled else 't'}",
        )

        # Add global delete original toggle
        delete_original = user_dict.get("CONVERT_DELETE_ORIGINAL", False)
        buttons.data_button(
            f"Delete Original: {'✅ ON' if delete_original else '❌ OFF'}",
            f"mediatools {user_id} tog CONVERT_DELETE_ORIGINAL {'f' if delete_original else 't'}",
        )

        # Media type buttons
        buttons.data_button("Video Convert", f"mediatools {user_id} convert_video")
        buttons.data_button("Audio Convert", f"mediatools {user_id} convert_audio")
        buttons.data_button(
            "Subtitle Convert", f"mediatools {user_id} convert_subtitle"
        )
        buttons.data_button(
            "Document Convert", f"mediatools {user_id} convert_document"
        )
        buttons.data_button(
            "Archive Convert", f"mediatools {user_id} convert_archive"
        )

        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu CONVERT_PRIORITY"
        )
        buttons.data_button("Reset", f"mediatools {user_id} reset_convert")
        buttons.data_button("Remove", f"mediatools {user_id} remove_convert")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get convert settings
        convert_priority = user_dict.get("CONVERT_PRIORITY", "3")

        # Get delete original status
        if "CONVERT_DELETE_ORIGINAL" in user_dict:
            delete_original_status = (
                "✅ Enabled (User)" if delete_original else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "CONVERT_DELETE_ORIGINAL")
            and Config.CONVERT_DELETE_ORIGINAL
        ):
            delete_original_status = "✅ Enabled (Global)"
        else:
            delete_original_status = "❌ Disabled"

        # Get video convert enabled status
        video_convert_enabled = user_dict.get("CONVERT_VIDEO_ENABLED", False)
        owner_video_enabled = (
            hasattr(Config, "CONVERT_VIDEO_ENABLED") and Config.CONVERT_VIDEO_ENABLED
        )

        if "CONVERT_VIDEO_ENABLED" in user_dict:
            if video_convert_enabled:
                video_enabled_status = "✅ Enabled (User)"
            else:
                video_enabled_status = "❌ Disabled (User)"
        elif owner_video_enabled:
            video_enabled_status = "✅ Enabled (Global)"
        else:
            video_enabled_status = "❌ Disabled"

        # Get audio convert enabled status
        audio_convert_enabled = user_dict.get("CONVERT_AUDIO_ENABLED", False)
        owner_audio_enabled = (
            hasattr(Config, "CONVERT_AUDIO_ENABLED") and Config.CONVERT_AUDIO_ENABLED
        )

        if "CONVERT_AUDIO_ENABLED" in user_dict:
            if audio_convert_enabled:
                audio_enabled_status = "✅ Enabled (User)"
            else:
                audio_enabled_status = "❌ Disabled (User)"
        elif owner_audio_enabled:
            audio_enabled_status = "✅ Enabled (Global)"
        else:
            audio_enabled_status = "❌ Disabled"

        # Get subtitle convert enabled status
        subtitle_convert_enabled = user_dict.get("CONVERT_SUBTITLE_ENABLED", False)
        owner_subtitle_enabled = (
            hasattr(Config, "CONVERT_SUBTITLE_ENABLED")
            and Config.CONVERT_SUBTITLE_ENABLED
        )

        if "CONVERT_SUBTITLE_ENABLED" in user_dict:
            if subtitle_convert_enabled:
                subtitle_enabled_status = "✅ Enabled (User)"
            else:
                subtitle_enabled_status = "❌ Disabled (User)"
        elif owner_subtitle_enabled:
            subtitle_enabled_status = "✅ Enabled (Global)"
        else:
            subtitle_enabled_status = "❌ Disabled"

        # Get document convert enabled status
        document_convert_enabled = user_dict.get("CONVERT_DOCUMENT_ENABLED", False)
        owner_document_enabled = (
            hasattr(Config, "CONVERT_DOCUMENT_ENABLED")
            and Config.CONVERT_DOCUMENT_ENABLED
        )

        if "CONVERT_DOCUMENT_ENABLED" in user_dict:
            if document_convert_enabled:
                document_enabled_status = "✅ Enabled (User)"
            else:
                document_enabled_status = "❌ Disabled (User)"
        elif owner_document_enabled:
            document_enabled_status = "✅ Enabled (Global)"
        else:
            document_enabled_status = "❌ Disabled"

        # Get archive convert enabled status
        archive_convert_enabled = user_dict.get("CONVERT_ARCHIVE_ENABLED", False)
        owner_archive_enabled = (
            hasattr(Config, "CONVERT_ARCHIVE_ENABLED")
            and Config.CONVERT_ARCHIVE_ENABLED
        )

        if "CONVERT_ARCHIVE_ENABLED" in user_dict:
            if archive_convert_enabled:
                archive_enabled_status = "✅ Enabled (User)"
            else:
                archive_enabled_status = "❌ Disabled (User)"
        elif owner_archive_enabled:
            archive_enabled_status = "✅ Enabled (Global)"
        else:
            archive_enabled_status = "❌ Disabled"

        # Get video convert format
        user_has_video_format = (
            "CONVERT_VIDEO_FORMAT" in user_dict and user_dict["CONVERT_VIDEO_FORMAT"]
        )
        owner_has_video_format = (
            hasattr(Config, "CONVERT_VIDEO_FORMAT") and Config.CONVERT_VIDEO_FORMAT
        )

        if user_has_video_format:
            video_format = f"{user_dict['CONVERT_VIDEO_FORMAT']} (User)"
        elif owner_has_video_format:
            video_format = f"{Config.CONVERT_VIDEO_FORMAT} (Global)"
        else:
            video_format = "mp4 (Default)"

        # Get audio convert format
        user_has_audio_format = (
            "CONVERT_AUDIO_FORMAT" in user_dict and user_dict["CONVERT_AUDIO_FORMAT"]
        )
        owner_has_audio_format = (
            hasattr(Config, "CONVERT_AUDIO_FORMAT") and Config.CONVERT_AUDIO_FORMAT
        )

        if user_has_audio_format:
            audio_format = f"{user_dict['CONVERT_AUDIO_FORMAT']} (User)"
        elif owner_has_audio_format:
            audio_format = f"{Config.CONVERT_AUDIO_FORMAT} (Global)"
        else:
            audio_format = "mp3 (Default)"

        # Get subtitle convert format
        user_has_subtitle_format = (
            "CONVERT_SUBTITLE_FORMAT" in user_dict
            and user_dict["CONVERT_SUBTITLE_FORMAT"]
        )
        owner_has_subtitle_format = (
            hasattr(Config, "CONVERT_SUBTITLE_FORMAT")
            and Config.CONVERT_SUBTITLE_FORMAT
        )

        if user_has_subtitle_format:
            subtitle_format = f"{user_dict['CONVERT_SUBTITLE_FORMAT']} (User)"
        elif owner_has_subtitle_format:
            subtitle_format = f"{Config.CONVERT_SUBTITLE_FORMAT} (Global)"
        else:
            subtitle_format = "srt (Default)"

        # Get document convert format
        user_has_document_format = (
            "CONVERT_DOCUMENT_FORMAT" in user_dict
            and user_dict["CONVERT_DOCUMENT_FORMAT"]
        )
        owner_has_document_format = (
            hasattr(Config, "CONVERT_DOCUMENT_FORMAT")
            and Config.CONVERT_DOCUMENT_FORMAT
        )

        if user_has_document_format:
            document_format = f"{user_dict['CONVERT_DOCUMENT_FORMAT']} (User)"
        elif owner_has_document_format:
            document_format = f"{Config.CONVERT_DOCUMENT_FORMAT} (Global)"
        else:
            document_format = "pdf (Default)"

        # Get archive convert format
        user_has_archive_format = (
            "CONVERT_ARCHIVE_FORMAT" in user_dict
            and user_dict["CONVERT_ARCHIVE_FORMAT"]
        )
        owner_has_archive_format = (
            hasattr(Config, "CONVERT_ARCHIVE_FORMAT")
            and Config.CONVERT_ARCHIVE_FORMAT
        )

        if user_has_archive_format:
            archive_format = f"{user_dict['CONVERT_ARCHIVE_FORMAT']} (User)"
        elif owner_has_archive_format:
            archive_format = f"{Config.CONVERT_ARCHIVE_FORMAT} (Global)"
        else:
            archive_format = "zip (Default)"

        text = f"""⌬ <b>Convert Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {"✅ Enabled" if convert_enabled else "❌ Disabled"}
┠ <b>Priority</b> → <code>{convert_priority}</code>
┠ <b>Delete Original</b> → {delete_original_status}
┃
┠ <b>Video Convert</b> → {video_enabled_status}
┠ <b>Video Format</b> → <code>{video_format}</code>
┃
┠ <b>Audio Convert</b> → {audio_enabled_status}
┠ <b>Audio Format</b> → <code>{audio_format}</code>
┃
┠ <b>Subtitle Convert</b> → {subtitle_enabled_status}
┠ <b>Subtitle Format</b> → <code>{subtitle_format}</code>
┃
┠ <b>Document Convert</b> → {document_enabled_status}
┠ <b>Document Format</b> → <code>{document_format}</code>
┃
┠ <b>Archive Convert</b> → {archive_enabled_status}
┖ <b>Archive Format</b> → <code>{archive_format}</code>

<b>Usage:</b>
• Use <code>-cv format</code> for video conversion (e.g., <code>-cv mp4</code>)
• Use <code>-ca format</code> for audio conversion (e.g., <code>-ca mp3</code>)
• Use <code>-cs format</code> for subtitle conversion (e.g., <code>-cs srt</code>)
• Use <code>-cd format</code> for document conversion (e.g., <code>-cd pdf</code>)
• Use <code>-cr format</code> for archive conversion (e.g., <code>-cr zip</code>)
• Add <code>-del</code> to delete original files after conversion"""

    elif stype == "convert_video":
        # Video Convert settings menu
        # Add toggle for video convert enabled
        video_convert_enabled = user_dict.get("CONVERT_VIDEO_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if video_convert_enabled else "❌ Disabled",
            f"mediatools {user_id} tog CONVERT_VIDEO_ENABLED {'f' if video_convert_enabled else 't'}",
        )

        buttons.data_button(
            "Set Format", f"mediatools {user_id} menu CONVERT_VIDEO_FORMAT"
        )
        buttons.data_button(
            "Set Codec", f"mediatools {user_id} menu CONVERT_VIDEO_CODEC"
        )
        buttons.data_button(
            "Set Quality", f"mediatools {user_id} menu CONVERT_VIDEO_QUALITY"
        )
        buttons.data_button(
            "Set CRF", f"mediatools {user_id} menu CONVERT_VIDEO_CRF"
        )
        buttons.data_button(
            "Set Preset", f"mediatools {user_id} menu CONVERT_VIDEO_PRESET"
        )
        buttons.data_button(
            "Set Resolution", f"mediatools {user_id} menu CONVERT_VIDEO_RESOLUTION"
        )
        buttons.data_button(
            "Set FPS", f"mediatools {user_id} menu CONVERT_VIDEO_FPS"
        )

        # Add toggle for maintaining original quality
        maintain_quality = user_dict.get("CONVERT_VIDEO_MAINTAIN_QUALITY", True)
        buttons.data_button(
            f"Quality: {'✅ High' if maintain_quality else '❌ Normal'}",
            f"mediatools {user_id} tog CONVERT_VIDEO_MAINTAIN_QUALITY {'f' if maintain_quality else 't'}",
        )

        buttons.data_button("Back", f"mediatools {user_id} convert", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get video convert settings
        user_has_format = (
            "CONVERT_VIDEO_FORMAT" in user_dict
            and user_dict["CONVERT_VIDEO_FORMAT"]
            and user_dict["CONVERT_VIDEO_FORMAT"].lower() != "none"
        )
        owner_has_format = (
            hasattr(Config, "CONVERT_VIDEO_FORMAT")
            and Config.CONVERT_VIDEO_FORMAT
            and Config.CONVERT_VIDEO_FORMAT.lower() != "none"
        )

        if user_has_format:
            video_format = f"{user_dict['CONVERT_VIDEO_FORMAT']} (User)"
        elif owner_has_format:
            video_format = f"{Config.CONVERT_VIDEO_FORMAT} (Global)"
        else:
            video_format = "none (Default)"

        # Get video codec
        user_has_codec = (
            "CONVERT_VIDEO_CODEC" in user_dict
            and user_dict["CONVERT_VIDEO_CODEC"]
            and user_dict["CONVERT_VIDEO_CODEC"].lower() != "none"
        )
        owner_has_codec = (
            hasattr(Config, "CONVERT_VIDEO_CODEC")
            and Config.CONVERT_VIDEO_CODEC
            and Config.CONVERT_VIDEO_CODEC.lower() != "none"
        )

        if user_has_codec:
            video_codec = f"{user_dict['CONVERT_VIDEO_CODEC']} (User)"
        elif owner_has_codec:
            video_codec = f"{Config.CONVERT_VIDEO_CODEC} (Global)"
        else:
            video_codec = "none (Default)"

        # Get video quality
        user_has_quality = (
            "CONVERT_VIDEO_QUALITY" in user_dict
            and user_dict["CONVERT_VIDEO_QUALITY"]
            and user_dict["CONVERT_VIDEO_QUALITY"].lower() != "none"
        )
        owner_has_quality = (
            hasattr(Config, "CONVERT_VIDEO_QUALITY")
            and Config.CONVERT_VIDEO_QUALITY
            and Config.CONVERT_VIDEO_QUALITY.lower() != "none"
        )

        if user_has_quality:
            video_quality = f"{user_dict['CONVERT_VIDEO_QUALITY']} (User)"
        elif owner_has_quality:
            video_quality = f"{Config.CONVERT_VIDEO_QUALITY} (Global)"
        else:
            video_quality = "none (Default)"

        # Get video CRF
        user_has_crf = (
            "CONVERT_VIDEO_CRF" in user_dict
            and user_dict["CONVERT_VIDEO_CRF"]
            and user_dict["CONVERT_VIDEO_CRF"] != 0
        )
        owner_has_crf = (
            hasattr(Config, "CONVERT_VIDEO_CRF")
            and Config.CONVERT_VIDEO_CRF
            and Config.CONVERT_VIDEO_CRF != 0
        )

        if user_has_crf:
            video_crf = f"{user_dict['CONVERT_VIDEO_CRF']} (User)"
        elif owner_has_crf:
            video_crf = f"{Config.CONVERT_VIDEO_CRF} (Global)"
        else:
            video_crf = "0 (Default)"

        # Get video preset
        user_has_preset = (
            "CONVERT_VIDEO_PRESET" in user_dict
            and user_dict["CONVERT_VIDEO_PRESET"]
            and user_dict["CONVERT_VIDEO_PRESET"].lower() != "none"
        )
        owner_has_preset = (
            hasattr(Config, "CONVERT_VIDEO_PRESET")
            and Config.CONVERT_VIDEO_PRESET
            and Config.CONVERT_VIDEO_PRESET.lower() != "none"
        )

        if user_has_preset:
            video_preset = f"{user_dict['CONVERT_VIDEO_PRESET']} (User)"
        elif owner_has_preset:
            video_preset = f"{Config.CONVERT_VIDEO_PRESET} (Global)"
        else:
            video_preset = "none (Default)"

        # Get video resolution
        user_has_resolution = (
            "CONVERT_VIDEO_RESOLUTION" in user_dict
            and user_dict["CONVERT_VIDEO_RESOLUTION"]
            and user_dict["CONVERT_VIDEO_RESOLUTION"].lower() != "none"
        )
        owner_has_resolution = (
            hasattr(Config, "CONVERT_VIDEO_RESOLUTION")
            and Config.CONVERT_VIDEO_RESOLUTION
            and Config.CONVERT_VIDEO_RESOLUTION.lower() != "none"
        )

        if user_has_resolution:
            video_resolution = f"{user_dict['CONVERT_VIDEO_RESOLUTION']} (User)"
        elif owner_has_resolution:
            video_resolution = f"{Config.CONVERT_VIDEO_RESOLUTION} (Global)"
        else:
            video_resolution = "none (Default)"

        # Get video FPS
        user_has_fps = (
            "CONVERT_VIDEO_FPS" in user_dict
            and user_dict["CONVERT_VIDEO_FPS"]
            and user_dict["CONVERT_VIDEO_FPS"].lower() != "none"
        )
        owner_has_fps = (
            hasattr(Config, "CONVERT_VIDEO_FPS")
            and Config.CONVERT_VIDEO_FPS
            and Config.CONVERT_VIDEO_FPS.lower() != "none"
        )

        if user_has_fps:
            video_fps = f"{user_dict['CONVERT_VIDEO_FPS']} (User)"
        elif owner_has_fps:
            video_fps = f"{Config.CONVERT_VIDEO_FPS} (Global)"
        else:
            video_fps = "none (Default)"

        # Get maintain quality status
        user_has_maintain_quality = "CONVERT_VIDEO_MAINTAIN_QUALITY" in user_dict
        if user_has_maintain_quality:
            maintain_quality_status = (
                "✅ High (User)"
                if user_dict["CONVERT_VIDEO_MAINTAIN_QUALITY"]
                else "❌ Normal (User)"
            )
        elif hasattr(Config, "CONVERT_VIDEO_MAINTAIN_QUALITY"):
            # Check the global setting
            maintain_quality_status = (
                "✅ High (Global)"
                if Config.CONVERT_VIDEO_MAINTAIN_QUALITY
                else "❌ Normal (Global)"
            )
        else:
            # Default value from config is True
            maintain_quality_status = "✅ High (Default)"

        # Get video convert enabled status
        video_convert_enabled = user_dict.get("CONVERT_VIDEO_ENABLED", False)
        owner_video_enabled = (
            hasattr(Config, "CONVERT_VIDEO_ENABLED") and Config.CONVERT_VIDEO_ENABLED
        )

        if "CONVERT_VIDEO_ENABLED" in user_dict:
            if video_convert_enabled:
                video_enabled_status = "✅ Enabled (User)"
            else:
                video_enabled_status = "❌ Disabled (User)"
        elif owner_video_enabled:
            video_enabled_status = "✅ Enabled (Global)"
        else:
            video_enabled_status = "❌ Disabled"

        text = f"""⌬ <b>Video Convert Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {video_enabled_status}
┠ <b>Format</b> → <code>{video_format}</code>
┠ <b>Codec</b> → <code>{video_codec}</code>
┠ <b>Quality</b> → <code>{video_quality}</code>
┠ <b>CRF</b> → <code>{video_crf}</code>
┠ <b>Preset</b> → <code>{video_preset}</code>
┠ <b>Resolution</b> → <code>{video_resolution}</code>
┠ <b>FPS</b> → <code>{video_fps}</code>
┖ <b>Maintain Quality</b> → {maintain_quality_status}"""

    elif stype == "extract":
        # Extract settings menu
        extract_enabled = user_dict.get("EXTRACT_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if extract_enabled else "❌ Disabled",
            f"mediatools {user_id} tog EXTRACT_ENABLED {'f' if extract_enabled else 't'}",
        )
        buttons.data_button("Configure", f"mediatools {user_id} extract_config")
        buttons.data_button(
            "Set Priority", f"mediatools {user_id} menu EXTRACT_PRIORITY"
        )
        buttons.data_button("Reset", f"mediatools {user_id} reset_extract")
        buttons.data_button("Remove", f"mediatools {user_id} remove_extract")
        buttons.data_button("Back", f"mediatools {user_id} back", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get extract priority
        user_has_priority = (
            "EXTRACT_PRIORITY" in user_dict and user_dict["EXTRACT_PRIORITY"]
        )
        if user_has_priority:
            priority = f"{user_dict['EXTRACT_PRIORITY']} (User)"
        elif hasattr(Config, "EXTRACT_PRIORITY") and Config.EXTRACT_PRIORITY:
            priority = f"{Config.EXTRACT_PRIORITY} (Global)"
        else:
            priority = "6 (Default)"

        # Get video extract status
        video_enabled = user_dict.get("EXTRACT_VIDEO_ENABLED", False)
        if "EXTRACT_VIDEO_ENABLED" in user_dict:
            video_status = (
                "✅ Enabled (User)" if video_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "EXTRACT_VIDEO_ENABLED") and Config.EXTRACT_VIDEO_ENABLED
        ):
            video_status = "✅ Enabled (Global)"
        else:
            video_status = "❌ Disabled"

        # Get audio extract status
        audio_enabled = user_dict.get("EXTRACT_AUDIO_ENABLED", False)
        if "EXTRACT_AUDIO_ENABLED" in user_dict:
            audio_status = (
                "✅ Enabled (User)" if audio_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "EXTRACT_AUDIO_ENABLED") and Config.EXTRACT_AUDIO_ENABLED
        ):
            audio_status = "✅ Enabled (Global)"
        else:
            audio_status = "❌ Disabled"

        # Get subtitle extract status
        subtitle_enabled = user_dict.get("EXTRACT_SUBTITLE_ENABLED", False)
        if "EXTRACT_SUBTITLE_ENABLED" in user_dict:
            subtitle_status = (
                "✅ Enabled (User)" if subtitle_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "EXTRACT_SUBTITLE_ENABLED")
            and Config.EXTRACT_SUBTITLE_ENABLED
        ):
            subtitle_status = "✅ Enabled (Global)"
        else:
            subtitle_status = "❌ Disabled"

        # Get attachment extract status
        attachment_enabled = user_dict.get("EXTRACT_ATTACHMENT_ENABLED", False)
        if "EXTRACT_ATTACHMENT_ENABLED" in user_dict:
            attachment_status = (
                "✅ Enabled (User)" if attachment_enabled else "❌ Disabled (User)"
            )
        elif (
            hasattr(Config, "EXTRACT_ATTACHMENT_ENABLED")
            and Config.EXTRACT_ATTACHMENT_ENABLED
        ):
            attachment_status = "✅ Enabled (Global)"
        else:
            attachment_status = "❌ Disabled"

        text = f"""<b>Extract Settings</b>

<b>Status:</b> {"✅ Enabled" if extract_enabled else "❌ Disabled"}
<b>Priority:</b> {priority}

<b>Track Types:</b>
┃
┣ <b>Video:</b> {video_status}
┃
┣ <b>Audio:</b> {audio_status}
┃
┣ <b>Subtitle:</b> {subtitle_status}
┃
┗ <b>Attachment:</b> {attachment_status}

<b>Help:</b>
• Click the "✅ Enabled/❌ Disabled" button to toggle extract feature
• Click "Configure" to set up detailed extraction options
• Click "Set Priority" to change when extraction runs in the pipeline
• Enable specific track types in the Configure menu
• Use track indices to extract only specific tracks
• The extract feature extracts media tracks from container files
• Example: Extract audio tracks from video files as MP3s
• Example: Extract subtitles from video files as SRT files"""

    elif stype == "extract_config":
        # Extract configuration menu
        # Video extract settings
        video_enabled = user_dict.get("EXTRACT_VIDEO_ENABLED", False)
        buttons.data_button(
            f"Video: {'✅ ON' if video_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_VIDEO_ENABLED {'f' if video_enabled else 't'}",
        )
        buttons.data_button(
            "Video Settings", f"mediatools {user_id} extract_video_config"
        )

        # Audio extract settings
        audio_enabled = user_dict.get("EXTRACT_AUDIO_ENABLED", False)
        buttons.data_button(
            f"Audio: {'✅ ON' if audio_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_AUDIO_ENABLED {'f' if audio_enabled else 't'}",
        )
        buttons.data_button(
            "Audio Settings", f"mediatools {user_id} extract_audio_config"
        )

        # Subtitle extract settings
        subtitle_enabled = user_dict.get("EXTRACT_SUBTITLE_ENABLED", False)
        buttons.data_button(
            f"Subtitle: {'✅ ON' if subtitle_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_SUBTITLE_ENABLED {'f' if subtitle_enabled else 't'}",
        )
        buttons.data_button(
            "Subtitle Settings", f"mediatools {user_id} extract_subtitle_config"
        )

        # Attachment extract settings
        attachment_enabled = user_dict.get("EXTRACT_ATTACHMENT_ENABLED", False)
        buttons.data_button(
            f"Attachment: {'✅ ON' if attachment_enabled else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_ATTACHMENT_ENABLED {'f' if attachment_enabled else 't'}",
        )
        buttons.data_button(
            "Attachment Settings", f"mediatools {user_id} extract_attachment_config"
        )

        # Delete original toggle
        delete_original = user_dict.get("EXTRACT_DELETE_ORIGINAL", True)
        buttons.data_button(
            f"Delete Original: {'✅ ON' if delete_original else '❌ OFF'}",
            f"mediatools {user_id} tog EXTRACT_DELETE_ORIGINAL {'f' if delete_original else 't'}",
        )

        # Maintain quality toggle
        maintain_quality = user_dict.get("EXTRACT_MAINTAIN_QUALITY", True)
        buttons.data_button(
            f"Quality: {'✅ High' if maintain_quality else '❌ Normal'}",
            f"mediatools {user_id} tog EXTRACT_MAINTAIN_QUALITY {'f' if maintain_quality else 't'}",
        )

        buttons.data_button("Back", f"mediatools {user_id} extract", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get delete original setting
        delete_original_str = "✅ Enabled" if delete_original else "❌ Disabled"

        # Get maintain quality setting
        maintain_quality_str = "✅ Enabled" if maintain_quality else "❌ Disabled"

        text = f"""<b>Extract Configuration</b>

<b>Video Extract:</b> {"✅ Enabled" if video_enabled else "❌ Disabled"}
<b>Audio Extract:</b> {"✅ Enabled" if audio_enabled else "❌ Disabled"}
<b>Subtitle Extract:</b> {"✅ Enabled" if subtitle_enabled else "❌ Disabled"}
<b>Attachment Extract:</b> {"✅ Enabled" if attachment_enabled else "❌ Disabled"}

<b>General Settings:</b>
┣ <b>Delete Original:</b> {delete_original_str}
┗ <b>Maintain Quality:</b> {maintain_quality_str}

<b>Help:</b>
• Click on a track type toggle to enable/disable extraction for that type
• Click on a track type's "Settings" button to configure detailed options
• Set track indices to extract specific tracks (e.g., 0,1,2 or "all")
• Use 'copy' codec to preserve original quality
• When set to 'none', settings won't be used in command generation
• Delete Original: When enabled, original files are deleted after extraction
• Maintain Quality: When enabled, preserves highest possible quality"""

    elif stype == "extract_video_config":
        # Video extract configuration menu
        buttons.data_button(
            "Codec", f"mediatools {user_id} menu EXTRACT_VIDEO_CODEC"
        )
        buttons.data_button(
            "Format", f"mediatools {user_id} menu EXTRACT_VIDEO_FORMAT"
        )
        buttons.data_button(
            "Index", f"mediatools {user_id} menu EXTRACT_VIDEO_INDEX"
        )
        buttons.data_button(
            "Quality", f"mediatools {user_id} menu EXTRACT_VIDEO_QUALITY"
        )
        buttons.data_button(
            "Preset", f"mediatools {user_id} menu EXTRACT_VIDEO_PRESET"
        )
        buttons.data_button(
            "Bitrate", f"mediatools {user_id} menu EXTRACT_VIDEO_BITRATE"
        )
        buttons.data_button(
            "Resolution", f"mediatools {user_id} menu EXTRACT_VIDEO_RESOLUTION"
        )
        buttons.data_button("FPS", f"mediatools {user_id} menu EXTRACT_VIDEO_FPS")

        buttons.data_button("Back", f"mediatools {user_id} extract_config", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get video extract settings
        video_codec = user_dict.get("EXTRACT_VIDEO_CODEC", "none")
        if video_codec == "none" and hasattr(Config, "EXTRACT_VIDEO_CODEC"):
            video_codec = Config.EXTRACT_VIDEO_CODEC
        video_codec_str = (
            f"{video_codec}" if video_codec != "none" else "none (Default)"
        )

        video_format = user_dict.get("EXTRACT_VIDEO_FORMAT", "none")
        if video_format == "none" and hasattr(Config, "EXTRACT_VIDEO_FORMAT"):
            video_format = Config.EXTRACT_VIDEO_FORMAT
        video_format_str = (
            f"{video_format}" if video_format != "none" else "none (Default)"
        )

        video_index = user_dict.get("EXTRACT_VIDEO_INDEX", None)
        if video_index is None and hasattr(Config, "EXTRACT_VIDEO_INDEX"):
            video_index = Config.EXTRACT_VIDEO_INDEX
        video_index_str = (
            f"{video_index}" if video_index is not None else "All (Default)"
        )

        # Get additional video settings
        video_quality = user_dict.get("EXTRACT_VIDEO_QUALITY", "none")
        if video_quality == "none" and hasattr(Config, "EXTRACT_VIDEO_QUALITY"):
            video_quality = Config.EXTRACT_VIDEO_QUALITY
        video_quality_str = (
            f"{video_quality}" if video_quality != "none" else "none (Default)"
        )

        video_preset = user_dict.get("EXTRACT_VIDEO_PRESET", "none")
        if video_preset == "none" and hasattr(Config, "EXTRACT_VIDEO_PRESET"):
            video_preset = Config.EXTRACT_VIDEO_PRESET
        video_preset_str = (
            f"{video_preset}" if video_preset != "none" else "none (Default)"
        )

        video_bitrate = user_dict.get("EXTRACT_VIDEO_BITRATE", "none")
        if video_bitrate == "none" and hasattr(Config, "EXTRACT_VIDEO_BITRATE"):
            video_bitrate = Config.EXTRACT_VIDEO_BITRATE
        video_bitrate_str = (
            f"{video_bitrate}" if video_bitrate != "none" else "none (Default)"
        )

        video_resolution = user_dict.get("EXTRACT_VIDEO_RESOLUTION", "none")
        if video_resolution == "none" and hasattr(
            Config, "EXTRACT_VIDEO_RESOLUTION"
        ):
            video_resolution = Config.EXTRACT_VIDEO_RESOLUTION
        video_resolution_str = (
            f"{video_resolution}" if video_resolution != "none" else "none (Default)"
        )

        video_fps = user_dict.get("EXTRACT_VIDEO_FPS", "none")
        if video_fps == "none" and hasattr(Config, "EXTRACT_VIDEO_FPS"):
            video_fps = Config.EXTRACT_VIDEO_FPS
        video_fps_str = f"{video_fps}" if video_fps != "none" else "none (Default)"

        text = f"""<b>Video Extract Configuration</b>

<b>Basic Settings:</b>
┣ <b>Codec:</b> {video_codec_str}
┣ <b>Format:</b> {video_format_str}
┗ <b>Index:</b> {video_index_str}

<b>Advanced Settings:</b>
┣ <b>Quality:</b> {video_quality_str}
┣ <b>Preset:</b> {video_preset_str}
┣ <b>Bitrate:</b> {video_bitrate_str}
┣ <b>Resolution:</b> {video_resolution_str}
┗ <b>FPS:</b> {video_fps_str}

<b>Help:</b>
• <b>Codec:</b> Set the video codec (e.g., copy, h264, h265)
• <b>Format:</b> Set the output format (e.g., mp4, mkv, avi)
• <b>Index:</b> Set specific track indices to extract (e.g., 0,1,2 or "all")
• <b>Quality:</b> Set the quality/CRF value (lower is better quality)
• <b>Preset:</b> Set encoding preset (e.g., ultrafast, medium, veryslow)
• <b>Bitrate:</b> Set video bitrate (e.g., 5M, 10M)
• <b>Resolution:</b> Set video resolution (e.g., 1920x1080)
• <b>FPS:</b> Set video frame rate (e.g., 30, 60)

Use 'copy' codec to preserve original quality. When set to 'none', settings won't be used in command generation."""

    elif stype == "extract_audio_config":
        # Audio extract configuration menu
        buttons.data_button(
            "Codec", f"mediatools {user_id} menu EXTRACT_AUDIO_CODEC"
        )
        buttons.data_button(
            "Format", f"mediatools {user_id} menu EXTRACT_AUDIO_FORMAT"
        )
        buttons.data_button(
            "Index", f"mediatools {user_id} menu EXTRACT_AUDIO_INDEX"
        )
        buttons.data_button(
            "Bitrate", f"mediatools {user_id} menu EXTRACT_AUDIO_BITRATE"
        )
        buttons.data_button(
            "Channels", f"mediatools {user_id} menu EXTRACT_AUDIO_CHANNELS"
        )
        buttons.data_button(
            "Sampling", f"mediatools {user_id} menu EXTRACT_AUDIO_SAMPLING"
        )
        buttons.data_button(
            "Volume", f"mediatools {user_id} menu EXTRACT_AUDIO_VOLUME"
        )

        buttons.data_button("Back", f"mediatools {user_id} extract_config", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get audio extract settings
        audio_codec = user_dict.get("EXTRACT_AUDIO_CODEC", "none")
        if audio_codec == "none" and hasattr(Config, "EXTRACT_AUDIO_CODEC"):
            audio_codec = Config.EXTRACT_AUDIO_CODEC
        audio_codec_str = (
            f"{audio_codec}" if audio_codec != "none" else "none (Default)"
        )

        audio_format = user_dict.get("EXTRACT_AUDIO_FORMAT", "none")
        if audio_format == "none" and hasattr(Config, "EXTRACT_AUDIO_FORMAT"):
            audio_format = Config.EXTRACT_AUDIO_FORMAT
        audio_format_str = (
            f"{audio_format}" if audio_format != "none" else "none (Default)"
        )

        audio_index = user_dict.get("EXTRACT_AUDIO_INDEX", None)
        if audio_index is None and hasattr(Config, "EXTRACT_AUDIO_INDEX"):
            audio_index = Config.EXTRACT_AUDIO_INDEX
        audio_index_str = (
            f"{audio_index}" if audio_index is not None else "All (Default)"
        )

        # Get additional audio settings
        audio_bitrate = user_dict.get("EXTRACT_AUDIO_BITRATE", "none")
        if audio_bitrate == "none" and hasattr(Config, "EXTRACT_AUDIO_BITRATE"):
            audio_bitrate = Config.EXTRACT_AUDIO_BITRATE
        audio_bitrate_str = (
            f"{audio_bitrate}" if audio_bitrate != "none" else "none (Default)"
        )

        audio_channels = user_dict.get("EXTRACT_AUDIO_CHANNELS", "none")
        if audio_channels == "none" and hasattr(Config, "EXTRACT_AUDIO_CHANNELS"):
            audio_channels = Config.EXTRACT_AUDIO_CHANNELS
        audio_channels_str = (
            f"{audio_channels}" if audio_channels != "none" else "none (Default)"
        )

        audio_sampling = user_dict.get("EXTRACT_AUDIO_SAMPLING", "none")
        if audio_sampling == "none" and hasattr(Config, "EXTRACT_AUDIO_SAMPLING"):
            audio_sampling = Config.EXTRACT_AUDIO_SAMPLING
        audio_sampling_str = (
            f"{audio_sampling}" if audio_sampling != "none" else "none (Default)"
        )

        audio_volume = user_dict.get("EXTRACT_AUDIO_VOLUME", "none")
        if audio_volume == "none" and hasattr(Config, "EXTRACT_AUDIO_VOLUME"):
            audio_volume = Config.EXTRACT_AUDIO_VOLUME
        audio_volume_str = (
            f"{audio_volume}" if audio_volume != "none" else "none (Default)"
        )

        text = f"""<b>Audio Extract Configuration</b>

<b>Basic Settings:</b>
┣ <b>Codec:</b> {audio_codec_str}
┣ <b>Format:</b> {audio_format_str}
┗ <b>Index:</b> {audio_index_str}

<b>Advanced Settings:</b>
┣ <b>Bitrate:</b> {audio_bitrate_str}
┣ <b>Channels:</b> {audio_channels_str}
┣ <b>Sampling:</b> {audio_sampling_str}
┗ <b>Volume:</b> {audio_volume_str}

<b>Help:</b>
• <b>Codec:</b> Set the audio codec (e.g., copy, aac, mp3, opus)
• <b>Format:</b> Set the output format (e.g., mp3, aac, flac, wav)
• <b>Index:</b> Set specific track indices to extract (e.g., 0,1,2 or "all")
• <b>Bitrate:</b> Set audio bitrate (e.g., 128k, 192k, 320k)
• <b>Channels:</b> Set number of audio channels (e.g., 1 for mono, 2 for stereo)
• <b>Sampling:</b> Set audio sampling rate (e.g., 44100, 48000)
• <b>Volume:</b> Set volume adjustment (e.g., 1.0 normal, 1.5 louder)

Use 'copy' codec to preserve original quality. When set to 'none', settings won't be used in command generation."""

    elif stype == "extract_subtitle_config":
        # Subtitle extract configuration menu
        buttons.data_button(
            "Codec", f"mediatools {user_id} menu EXTRACT_SUBTITLE_CODEC"
        )
        buttons.data_button(
            "Format", f"mediatools {user_id} menu EXTRACT_SUBTITLE_FORMAT"
        )
        buttons.data_button(
            "Index", f"mediatools {user_id} menu EXTRACT_SUBTITLE_INDEX"
        )
        buttons.data_button(
            "Language", f"mediatools {user_id} menu EXTRACT_SUBTITLE_LANGUAGE"
        )
        buttons.data_button(
            "Encoding", f"mediatools {user_id} menu EXTRACT_SUBTITLE_ENCODING"
        )
        buttons.data_button(
            "Font", f"mediatools {user_id} menu EXTRACT_SUBTITLE_FONT"
        )
        buttons.data_button(
            "Font Size", f"mediatools {user_id} menu EXTRACT_SUBTITLE_FONT_SIZE"
        )

        buttons.data_button("Back", f"mediatools {user_id} extract_config", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get subtitle extract settings
        subtitle_codec = user_dict.get("EXTRACT_SUBTITLE_CODEC", "none")
        if subtitle_codec == "none" and hasattr(Config, "EXTRACT_SUBTITLE_CODEC"):
            subtitle_codec = Config.EXTRACT_SUBTITLE_CODEC
        subtitle_codec_str = (
            f"{subtitle_codec}" if subtitle_codec != "none" else "none (Default)"
        )

        subtitle_format = user_dict.get("EXTRACT_SUBTITLE_FORMAT", "none")
        if subtitle_format == "none" and hasattr(Config, "EXTRACT_SUBTITLE_FORMAT"):
            subtitle_format = Config.EXTRACT_SUBTITLE_FORMAT
        subtitle_format_str = (
            f"{subtitle_format}" if subtitle_format != "none" else "none (Default)"
        )

        subtitle_index = user_dict.get("EXTRACT_SUBTITLE_INDEX", None)
        if subtitle_index is None and hasattr(Config, "EXTRACT_SUBTITLE_INDEX"):
            subtitle_index = Config.EXTRACT_SUBTITLE_INDEX
        subtitle_index_str = (
            f"{subtitle_index}" if subtitle_index is not None else "All (Default)"
        )

        # Get additional subtitle settings
        subtitle_language = user_dict.get("EXTRACT_SUBTITLE_LANGUAGE", "none")
        if subtitle_language == "none" and hasattr(
            Config, "EXTRACT_SUBTITLE_LANGUAGE"
        ):
            subtitle_language = Config.EXTRACT_SUBTITLE_LANGUAGE
        subtitle_language_str = (
            f"{subtitle_language}"
            if subtitle_language != "none"
            else "none (Default)"
        )

        subtitle_encoding = user_dict.get("EXTRACT_SUBTITLE_ENCODING", "none")
        if subtitle_encoding == "none" and hasattr(
            Config, "EXTRACT_SUBTITLE_ENCODING"
        ):
            subtitle_encoding = Config.EXTRACT_SUBTITLE_ENCODING
        subtitle_encoding_str = (
            f"{subtitle_encoding}"
            if subtitle_encoding != "none"
            else "none (Default)"
        )

        subtitle_font = user_dict.get("EXTRACT_SUBTITLE_FONT", "none")
        if subtitle_font == "none" and hasattr(Config, "EXTRACT_SUBTITLE_FONT"):
            subtitle_font = Config.EXTRACT_SUBTITLE_FONT
        subtitle_font_str = (
            f"{subtitle_font}" if subtitle_font != "none" else "none (Default)"
        )

        subtitle_font_size = user_dict.get("EXTRACT_SUBTITLE_FONT_SIZE", "none")
        if subtitle_font_size == "none" and hasattr(
            Config, "EXTRACT_SUBTITLE_FONT_SIZE"
        ):
            subtitle_font_size = Config.EXTRACT_SUBTITLE_FONT_SIZE
        subtitle_font_size_str = (
            f"{subtitle_font_size}"
            if subtitle_font_size != "none"
            else "none (Default)"
        )

        text = f"""<b>Subtitle Extract Configuration</b>

<b>Basic Settings:</b>
┣ <b>Codec:</b> {subtitle_codec_str}
┣ <b>Format:</b> {subtitle_format_str}
┗ <b>Index:</b> {subtitle_index_str}

<b>Advanced Settings:</b>
┣ <b>Language:</b> {subtitle_language_str}
┣ <b>Encoding:</b> {subtitle_encoding_str}
┣ <b>Font:</b> {subtitle_font_str}
┗ <b>Font Size:</b> {subtitle_font_size_str}

<b>Help:</b>
• <b>Codec:</b> Set the subtitle codec (e.g., copy, srt, ass, vtt)
• <b>Format:</b> Set the output format (e.g., srt, ass, vtt)
• <b>Index:</b> Set specific track indices to extract (e.g., 0,1,2 or "all")
• <b>Language:</b> Set subtitle language code (e.g., eng, spa, fre)
• <b>Encoding:</b> Set character encoding (e.g., UTF-8, latin1)
• <b>Font:</b> Set font for ASS/SSA subtitles (e.g., Arial)
• <b>Font Size:</b> Set font size for ASS/SSA subtitles (e.g., 24)

Use 'copy' codec to preserve original format or 'srt' to convert ASS/SSA to SRT. When set to 'none', settings won't be used in command generation."""

    elif stype == "extract_attachment_config":
        # Attachment extract configuration menu
        buttons.data_button(
            "Format", f"mediatools {user_id} menu EXTRACT_ATTACHMENT_FORMAT"
        )
        buttons.data_button(
            "Index", f"mediatools {user_id} menu EXTRACT_ATTACHMENT_INDEX"
        )
        buttons.data_button(
            "Filter", f"mediatools {user_id} menu EXTRACT_ATTACHMENT_FILTER"
        )

        buttons.data_button("Back", f"mediatools {user_id} extract_config", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get attachment extract settings
        attachment_format = user_dict.get("EXTRACT_ATTACHMENT_FORMAT", "none")
        if attachment_format == "none" and hasattr(
            Config, "EXTRACT_ATTACHMENT_FORMAT"
        ):
            attachment_format = Config.EXTRACT_ATTACHMENT_FORMAT
        attachment_format_str = (
            f"{attachment_format}"
            if attachment_format != "none"
            else "none (Default)"
        )

        attachment_index = user_dict.get("EXTRACT_ATTACHMENT_INDEX", None)
        if attachment_index is None and hasattr(Config, "EXTRACT_ATTACHMENT_INDEX"):
            attachment_index = Config.EXTRACT_ATTACHMENT_INDEX
        attachment_index_str = (
            f"{attachment_index}"
            if attachment_index is not None
            else "All (Default)"
        )

        # Get additional attachment settings
        attachment_filter = user_dict.get("EXTRACT_ATTACHMENT_FILTER", "none")
        if attachment_filter == "none" and hasattr(
            Config, "EXTRACT_ATTACHMENT_FILTER"
        ):
            attachment_filter = Config.EXTRACT_ATTACHMENT_FILTER
        attachment_filter_str = (
            f"{attachment_filter}"
            if attachment_filter != "none"
            else "none (Default)"
        )

        text = f"""<b>Attachment Extract Configuration</b>

<b>Basic Settings:</b>
┣ <b>Format:</b> {attachment_format_str}
┣ <b>Index:</b> {attachment_index_str}
┗ <b>Filter:</b> {attachment_filter_str}

<b>Help:</b>
• <b>Format:</b> Set the output format for attachments (e.g., original, zip)
• <b>Index:</b> Set specific attachment indices to extract (e.g., 0,1,2 or "all")
• <b>Filter:</b> Set a filter pattern for attachments (e.g., *.ttf, *.jpg)

<b>Tips:</b>
• Set index to a specific number or comma-separated list (e.g., 0,1,2)
• Leave index empty to extract all attachments
• Use filter to extract only specific file types (e.g., *.ttf for fonts)
• When set to 'none', settings won't be used in command generation"""

    elif stype == "convert_audio":
        # Audio Convert settings menu
        # Add toggle for audio convert enabled
        audio_convert_enabled = user_dict.get("CONVERT_AUDIO_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if audio_convert_enabled else "❌ Disabled",
            f"mediatools {user_id} tog CONVERT_AUDIO_ENABLED {'f' if audio_convert_enabled else 't'}",
        )

        buttons.data_button(
            "Set Format", f"mediatools {user_id} menu CONVERT_AUDIO_FORMAT"
        )
        buttons.data_button(
            "Set Codec", f"mediatools {user_id} menu CONVERT_AUDIO_CODEC"
        )
        buttons.data_button(
            "Set Bitrate", f"mediatools {user_id} menu CONVERT_AUDIO_BITRATE"
        )
        buttons.data_button(
            "Set Channels", f"mediatools {user_id} menu CONVERT_AUDIO_CHANNELS"
        )
        buttons.data_button(
            "Set Sampling", f"mediatools {user_id} menu CONVERT_AUDIO_SAMPLING"
        )
        buttons.data_button(
            "Set Volume", f"mediatools {user_id} menu CONVERT_AUDIO_VOLUME"
        )

        buttons.data_button("Back", f"mediatools {user_id} convert", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get audio convert settings
        user_has_format = (
            "CONVERT_AUDIO_FORMAT" in user_dict
            and user_dict["CONVERT_AUDIO_FORMAT"]
            and user_dict["CONVERT_AUDIO_FORMAT"].lower() != "none"
        )
        owner_has_format = (
            hasattr(Config, "CONVERT_AUDIO_FORMAT")
            and Config.CONVERT_AUDIO_FORMAT
            and Config.CONVERT_AUDIO_FORMAT.lower() != "none"
        )

        if user_has_format:
            audio_format = f"{user_dict['CONVERT_AUDIO_FORMAT']} (User)"
        elif owner_has_format:
            audio_format = f"{Config.CONVERT_AUDIO_FORMAT} (Global)"
        else:
            audio_format = "none (Default)"

        # Get audio codec
        user_has_codec = (
            "CONVERT_AUDIO_CODEC" in user_dict
            and user_dict["CONVERT_AUDIO_CODEC"]
            and user_dict["CONVERT_AUDIO_CODEC"].lower() != "none"
        )
        owner_has_codec = (
            hasattr(Config, "CONVERT_AUDIO_CODEC")
            and Config.CONVERT_AUDIO_CODEC
            and Config.CONVERT_AUDIO_CODEC.lower() != "none"
        )

        if user_has_codec:
            audio_codec = f"{user_dict['CONVERT_AUDIO_CODEC']} (User)"
        elif owner_has_codec:
            audio_codec = f"{Config.CONVERT_AUDIO_CODEC} (Global)"
        else:
            audio_codec = "none (Default)"

        # Get audio bitrate
        user_has_bitrate = (
            "CONVERT_AUDIO_BITRATE" in user_dict
            and user_dict["CONVERT_AUDIO_BITRATE"]
            and user_dict["CONVERT_AUDIO_BITRATE"].lower() != "none"
        )
        owner_has_bitrate = (
            hasattr(Config, "CONVERT_AUDIO_BITRATE")
            and Config.CONVERT_AUDIO_BITRATE
            and Config.CONVERT_AUDIO_BITRATE.lower() != "none"
        )

        if user_has_bitrate:
            audio_bitrate = f"{user_dict['CONVERT_AUDIO_BITRATE']} (User)"
        elif owner_has_bitrate:
            audio_bitrate = f"{Config.CONVERT_AUDIO_BITRATE} (Global)"
        else:
            audio_bitrate = "none (Default)"

        # Get audio channels
        user_has_channels = (
            "CONVERT_AUDIO_CHANNELS" in user_dict
            and user_dict["CONVERT_AUDIO_CHANNELS"]
            and user_dict["CONVERT_AUDIO_CHANNELS"] != 0
        )
        owner_has_channels = (
            hasattr(Config, "CONVERT_AUDIO_CHANNELS")
            and Config.CONVERT_AUDIO_CHANNELS
            and Config.CONVERT_AUDIO_CHANNELS != 0
        )

        if user_has_channels:
            audio_channels = f"{user_dict['CONVERT_AUDIO_CHANNELS']} (User)"
        elif owner_has_channels:
            audio_channels = f"{Config.CONVERT_AUDIO_CHANNELS} (Global)"
        else:
            audio_channels = "0 (Default)"

        # Get audio sampling
        user_has_sampling = (
            "CONVERT_AUDIO_SAMPLING" in user_dict
            and user_dict["CONVERT_AUDIO_SAMPLING"]
            and user_dict["CONVERT_AUDIO_SAMPLING"] != 0
        )
        owner_has_sampling = (
            hasattr(Config, "CONVERT_AUDIO_SAMPLING")
            and Config.CONVERT_AUDIO_SAMPLING
            and Config.CONVERT_AUDIO_SAMPLING != 0
        )

        if user_has_sampling:
            audio_sampling = f"{user_dict['CONVERT_AUDIO_SAMPLING']} (User)"
        elif owner_has_sampling:
            audio_sampling = f"{Config.CONVERT_AUDIO_SAMPLING} (Global)"
        else:
            audio_sampling = "0 (Default)"

        # Get audio volume
        user_has_volume = (
            "CONVERT_AUDIO_VOLUME" in user_dict
            and user_dict["CONVERT_AUDIO_VOLUME"]
            and user_dict["CONVERT_AUDIO_VOLUME"] != 0.0
        )
        owner_has_volume = (
            hasattr(Config, "CONVERT_AUDIO_VOLUME")
            and Config.CONVERT_AUDIO_VOLUME
            and Config.CONVERT_AUDIO_VOLUME != 0.0
        )

        if user_has_volume:
            audio_volume = f"{user_dict['CONVERT_AUDIO_VOLUME']} (User)"
        elif owner_has_volume:
            audio_volume = f"{Config.CONVERT_AUDIO_VOLUME} (Global)"
        else:
            audio_volume = "0.0 (Default)"

        # Get audio convert enabled status
        audio_convert_enabled = user_dict.get("CONVERT_AUDIO_ENABLED", False)
        owner_audio_enabled = (
            hasattr(Config, "CONVERT_AUDIO_ENABLED") and Config.CONVERT_AUDIO_ENABLED
        )

        if "CONVERT_AUDIO_ENABLED" in user_dict:
            if audio_convert_enabled:
                audio_enabled_status = "✅ Enabled (User)"
            else:
                audio_enabled_status = "❌ Disabled (User)"
        elif owner_audio_enabled:
            audio_enabled_status = "✅ Enabled (Global)"
        else:
            audio_enabled_status = "❌ Disabled"

        text = f"""⌬ <b>Audio Convert Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {audio_enabled_status}
┠ <b>Format</b> → <code>{audio_format}</code>
┠ <b>Codec</b> → <code>{audio_codec}</code>
┠ <b>Bitrate</b> → <code>{audio_bitrate}</code>
┠ <b>Channels</b> → <code>{audio_channels}</code>
┠ <b>Sampling</b> → <code>{audio_sampling}</code>
┖ <b>Volume</b> → <code>{audio_volume}</code>"""

    elif stype == "convert_subtitle":
        # Subtitle Convert settings menu
        # Add toggle for subtitle convert enabled
        subtitle_convert_enabled = user_dict.get("CONVERT_SUBTITLE_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if subtitle_convert_enabled else "❌ Disabled",
            f"mediatools {user_id} tog CONVERT_SUBTITLE_ENABLED {'f' if subtitle_convert_enabled else 't'}",
        )

        buttons.data_button(
            "Set Format", f"mediatools {user_id} menu CONVERT_SUBTITLE_FORMAT"
        )
        buttons.data_button(
            "Set Encoding", f"mediatools {user_id} menu CONVERT_SUBTITLE_ENCODING"
        )
        buttons.data_button(
            "Set Language", f"mediatools {user_id} menu CONVERT_SUBTITLE_LANGUAGE"
        )

        buttons.data_button("Back", f"mediatools {user_id} convert", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get subtitle convert settings
        user_has_format = (
            "CONVERT_SUBTITLE_FORMAT" in user_dict
            and user_dict["CONVERT_SUBTITLE_FORMAT"]
            and user_dict["CONVERT_SUBTITLE_FORMAT"].lower() != "none"
        )
        owner_has_format = (
            hasattr(Config, "CONVERT_SUBTITLE_FORMAT")
            and Config.CONVERT_SUBTITLE_FORMAT
            and Config.CONVERT_SUBTITLE_FORMAT.lower() != "none"
        )

        if user_has_format:
            subtitle_format = f"{user_dict['CONVERT_SUBTITLE_FORMAT']} (User)"
        elif owner_has_format:
            subtitle_format = f"{Config.CONVERT_SUBTITLE_FORMAT} (Global)"
        else:
            subtitle_format = "none (Default)"

        # Get subtitle encoding
        user_has_encoding = (
            "CONVERT_SUBTITLE_ENCODING" in user_dict
            and user_dict["CONVERT_SUBTITLE_ENCODING"]
            and user_dict["CONVERT_SUBTITLE_ENCODING"].lower() != "none"
        )
        owner_has_encoding = (
            hasattr(Config, "CONVERT_SUBTITLE_ENCODING")
            and Config.CONVERT_SUBTITLE_ENCODING
            and Config.CONVERT_SUBTITLE_ENCODING.lower() != "none"
        )

        if user_has_encoding:
            subtitle_encoding = f"{user_dict['CONVERT_SUBTITLE_ENCODING']} (User)"
        elif owner_has_encoding:
            subtitle_encoding = f"{Config.CONVERT_SUBTITLE_ENCODING} (Global)"
        else:
            subtitle_encoding = "none (Default)"

        # Get subtitle language
        user_has_language = (
            "CONVERT_SUBTITLE_LANGUAGE" in user_dict
            and user_dict["CONVERT_SUBTITLE_LANGUAGE"]
            and user_dict["CONVERT_SUBTITLE_LANGUAGE"].lower() != "none"
        )
        owner_has_language = (
            hasattr(Config, "CONVERT_SUBTITLE_LANGUAGE")
            and Config.CONVERT_SUBTITLE_LANGUAGE
            and Config.CONVERT_SUBTITLE_LANGUAGE.lower() != "none"
        )

        if user_has_language:
            subtitle_language = f"{user_dict['CONVERT_SUBTITLE_LANGUAGE']} (User)"
        elif owner_has_language:
            subtitle_language = f"{Config.CONVERT_SUBTITLE_LANGUAGE} (Global)"
        else:
            subtitle_language = "none (Default)"

        # Get subtitle convert enabled status
        subtitle_convert_enabled = user_dict.get("CONVERT_SUBTITLE_ENABLED", False)
        owner_subtitle_enabled = (
            hasattr(Config, "CONVERT_SUBTITLE_ENABLED")
            and Config.CONVERT_SUBTITLE_ENABLED
        )

        if "CONVERT_SUBTITLE_ENABLED" in user_dict:
            if subtitle_convert_enabled:
                subtitle_enabled_status = "✅ Enabled (User)"
            else:
                subtitle_enabled_status = "❌ Disabled (User)"
        elif owner_subtitle_enabled:
            subtitle_enabled_status = "✅ Enabled (Global)"
        else:
            subtitle_enabled_status = "❌ Disabled"

        text = f"""⌬ <b>Subtitle Convert Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {subtitle_enabled_status}
┠ <b>Format</b> → <code>{subtitle_format}</code>
┠ <b>Encoding</b> → <code>{subtitle_encoding}</code>
┖ <b>Language</b> → <code>{subtitle_language}</code>"""

    elif stype == "convert_document":
        # Document Convert settings menu
        # Add toggle for document convert enabled
        document_convert_enabled = user_dict.get("CONVERT_DOCUMENT_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if document_convert_enabled else "❌ Disabled",
            f"mediatools {user_id} tog CONVERT_DOCUMENT_ENABLED {'f' if document_convert_enabled else 't'}",
        )

        buttons.data_button(
            "Set Format", f"mediatools {user_id} menu CONVERT_DOCUMENT_FORMAT"
        )
        buttons.data_button(
            "Set Quality", f"mediatools {user_id} menu CONVERT_DOCUMENT_QUALITY"
        )
        buttons.data_button(
            "Set DPI", f"mediatools {user_id} menu CONVERT_DOCUMENT_DPI"
        )

        buttons.data_button("Back", f"mediatools {user_id} convert", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get document convert settings
        user_has_format = (
            "CONVERT_DOCUMENT_FORMAT" in user_dict
            and user_dict["CONVERT_DOCUMENT_FORMAT"]
            and user_dict["CONVERT_DOCUMENT_FORMAT"].lower() != "none"
        )
        owner_has_format = (
            hasattr(Config, "CONVERT_DOCUMENT_FORMAT")
            and Config.CONVERT_DOCUMENT_FORMAT
            and Config.CONVERT_DOCUMENT_FORMAT.lower() != "none"
        )

        if user_has_format:
            document_format = f"{user_dict['CONVERT_DOCUMENT_FORMAT']} (User)"
        elif owner_has_format:
            document_format = f"{Config.CONVERT_DOCUMENT_FORMAT} (Global)"
        else:
            document_format = "none (Default)"

        # Get document quality
        user_has_quality = (
            "CONVERT_DOCUMENT_QUALITY" in user_dict
            and user_dict["CONVERT_DOCUMENT_QUALITY"]
            and user_dict["CONVERT_DOCUMENT_QUALITY"] != 0
        )
        owner_has_quality = (
            hasattr(Config, "CONVERT_DOCUMENT_QUALITY")
            and Config.CONVERT_DOCUMENT_QUALITY
            and Config.CONVERT_DOCUMENT_QUALITY != 0
        )

        if user_has_quality:
            document_quality = f"{user_dict['CONVERT_DOCUMENT_QUALITY']} (User)"
        elif owner_has_quality:
            document_quality = f"{Config.CONVERT_DOCUMENT_QUALITY} (Global)"
        else:
            document_quality = "none (Default)"

        # Get document DPI
        user_has_dpi = (
            "CONVERT_DOCUMENT_DPI" in user_dict
            and user_dict["CONVERT_DOCUMENT_DPI"]
            and user_dict["CONVERT_DOCUMENT_DPI"] != 0
        )
        owner_has_dpi = (
            hasattr(Config, "CONVERT_DOCUMENT_DPI")
            and Config.CONVERT_DOCUMENT_DPI
            and Config.CONVERT_DOCUMENT_DPI != 0
        )

        if user_has_dpi:
            document_dpi = f"{user_dict['CONVERT_DOCUMENT_DPI']} (User)"
        elif owner_has_dpi:
            document_dpi = f"{Config.CONVERT_DOCUMENT_DPI} (Global)"
        else:
            document_dpi = "none (Default)"

        # Get document convert enabled status
        document_convert_enabled = user_dict.get("CONVERT_DOCUMENT_ENABLED", False)
        owner_document_enabled = (
            hasattr(Config, "CONVERT_DOCUMENT_ENABLED")
            and Config.CONVERT_DOCUMENT_ENABLED
        )

        if "CONVERT_DOCUMENT_ENABLED" in user_dict:
            if document_convert_enabled:
                document_enabled_status = "✅ Enabled (User)"
            else:
                document_enabled_status = "❌ Disabled (User)"
        elif owner_document_enabled:
            document_enabled_status = "✅ Enabled (Global)"
        else:
            document_enabled_status = "❌ Disabled"

        text = f"""⌬ <b>Document Convert Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {document_enabled_status}
┠ <b>Format</b> → <code>{document_format}</code>
┠ <b>Quality</b> → <code>{document_quality}</code>
┖ <b>DPI</b> → <code>{document_dpi}</code>"""

    elif stype == "convert_archive":
        # Archive Convert settings menu
        # Add toggle for archive convert enabled
        archive_convert_enabled = user_dict.get("CONVERT_ARCHIVE_ENABLED", False)
        buttons.data_button(
            "✅ Enabled" if archive_convert_enabled else "❌ Disabled",
            f"mediatools {user_id} tog CONVERT_ARCHIVE_ENABLED {'f' if archive_convert_enabled else 't'}",
        )

        buttons.data_button(
            "Set Format", f"mediatools {user_id} menu CONVERT_ARCHIVE_FORMAT"
        )
        buttons.data_button(
            "Set Level", f"mediatools {user_id} menu CONVERT_ARCHIVE_LEVEL"
        )
        buttons.data_button(
            "Set Method", f"mediatools {user_id} menu CONVERT_ARCHIVE_METHOD"
        )

        buttons.data_button("Back", f"mediatools {user_id} convert", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        # Get archive convert settings
        user_has_format = (
            "CONVERT_ARCHIVE_FORMAT" in user_dict
            and user_dict["CONVERT_ARCHIVE_FORMAT"]
            and user_dict["CONVERT_ARCHIVE_FORMAT"].lower() != "none"
        )
        owner_has_format = (
            hasattr(Config, "CONVERT_ARCHIVE_FORMAT")
            and Config.CONVERT_ARCHIVE_FORMAT
            and Config.CONVERT_ARCHIVE_FORMAT.lower() != "none"
        )

        if user_has_format:
            archive_format = f"{user_dict['CONVERT_ARCHIVE_FORMAT']} (User)"
        elif owner_has_format:
            archive_format = f"{Config.CONVERT_ARCHIVE_FORMAT} (Global)"
        else:
            archive_format = "none (Default)"

        # Get archive level
        user_has_level = (
            "CONVERT_ARCHIVE_LEVEL" in user_dict
            and user_dict["CONVERT_ARCHIVE_LEVEL"]
            and user_dict["CONVERT_ARCHIVE_LEVEL"] != 0
        )
        owner_has_level = (
            hasattr(Config, "CONVERT_ARCHIVE_LEVEL")
            and Config.CONVERT_ARCHIVE_LEVEL
            and Config.CONVERT_ARCHIVE_LEVEL != 0
        )

        if user_has_level:
            archive_level = f"{user_dict['CONVERT_ARCHIVE_LEVEL']} (User)"
        elif owner_has_level:
            archive_level = f"{Config.CONVERT_ARCHIVE_LEVEL} (Global)"
        else:
            archive_level = "none (Default)"

        # Get archive method
        user_has_method = (
            "CONVERT_ARCHIVE_METHOD" in user_dict
            and user_dict["CONVERT_ARCHIVE_METHOD"]
            and user_dict["CONVERT_ARCHIVE_METHOD"].lower() != "none"
        )
        owner_has_method = (
            hasattr(Config, "CONVERT_ARCHIVE_METHOD")
            and Config.CONVERT_ARCHIVE_METHOD
            and Config.CONVERT_ARCHIVE_METHOD.lower() != "none"
        )

        if user_has_method:
            archive_method = f"{user_dict['CONVERT_ARCHIVE_METHOD']} (User)"
        elif owner_has_method:
            archive_method = f"{Config.CONVERT_ARCHIVE_METHOD} (Global)"
        else:
            archive_method = "none (Default)"

        # Get archive convert enabled status
        archive_convert_enabled = user_dict.get("CONVERT_ARCHIVE_ENABLED", False)
        owner_archive_enabled = (
            hasattr(Config, "CONVERT_ARCHIVE_ENABLED")
            and Config.CONVERT_ARCHIVE_ENABLED
        )

        if "CONVERT_ARCHIVE_ENABLED" in user_dict:
            if archive_convert_enabled:
                archive_enabled_status = "✅ Enabled (User)"
            else:
                archive_enabled_status = "❌ Disabled (User)"
        elif owner_archive_enabled:
            archive_enabled_status = "✅ Enabled (Global)"
        else:
            archive_enabled_status = "❌ Disabled"

        text = f"""⌬ <b>Archive Convert Settings :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Status</b> → {archive_enabled_status}
┠ <b>Format</b> → <code>{archive_format}</code>
┠ <b>Level</b> → <code>{archive_level}</code>
┖ <b>Method</b> → <code>{archive_method}</code>"""

    # Removed duplicate sections

    elif stype == "help_examples":
        # Usage Examples
        buttons.data_button("Back to Help", f"mediatools {user_id} help", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        btns = buttons.build_menu(2)

        text = f"""⌬ <b>Media Tools Usage Examples :</b>
┟ <b>Name</b> → {user_name}
┃
┠ <b>Watermark Examples:</b>
┃ • <b>Basic Usage:</b>
┃   <code>/mirror https://example.com/media.zip -watermark "© My Channel"</code>
┃   This will add the watermark to all media files
┃
┃ • <b>With Images:</b>
┃   <code>/leech https://example.com/photos.zip -watermark "My Brand"</code>
┃   This will add the watermark to all image files
┃
┠ <b>Merge Examples:</b>
┃ • <b>Video Merge:</b>
┃   <code>/leech https://example.com/videos.zip -merge-video</code>
┃   This will merge only video files into a single video
┃
┃ • <b>Audio Merge:</b>
┃   <code>/mirror https://example.com/music.zip -merge-audio</code>
┃   This will merge only audio files into a single audio file
┃
┃ • <b>Image Merge:</b>
┃   <code>/mirror https://example.com/images.zip -merge-image</code>
┃   This will merge image files into a collage or grid
┃
┃ • <b>PDF Merge:</b>
┃   <code>/leech https://example.com/documents.zip -merge-pdf</code>
┃   This will merge PDF documents into a single PDF file
┃
┃ • <b>All Types Merge:</b>
┃   <code>/mirror https://example.com/media.zip -merge-all</code>
┃
┠ <b>Trim Examples:</b>
┃ • <b>Basic Trim:</b>
┃   <code>/leech https://example.com/video.mp4 -trim "00:01:30-00:02:45"</code>
┃   This will extract the portion from 1m30s to 2m45s
┃
┃ • <b>Trim with Delete Original:</b>
┃   <code>/mirror https://example.com/video.mp4 -trim "00:01:30-00:02:45" -del</code>
┃   This will trim the video and delete the original file
┃
┃ • <b>Trim from Start:</b>
┃   <code>/leech https://example.com/audio.mp3 -trim "-00:05:00"</code>
┃   This will extract from the beginning to 5 minutes
┃
┃ • <b>Trim to End:</b>
┃   <code>/mirror https://example.com/video.mp4 -trim "00:10:00-"</code>
┃   This will extract from 10 minutes to the end
┃
┠ <b>Convert Examples:</b>
┃ • <b>Video Convert:</b>
┃   <code>/leech https://example.com/video.mp4 -cv mp4</code>
┃   This will convert the video to MP4 format
┃
┃ • <b>Audio Convert:</b>
┃   <code>/mirror https://example.com/audio.wav -ca mp3</code>
┃   This will convert the audio to MP3 format
┃
┃ • <b>Subtitle Convert:</b>
┃   <code>/leech https://example.com/subtitle.ass -cs srt</code>
┃   This will convert the subtitle to SRT format
┃
┃ • <b>Document Convert:</b>
┃   <code>/mirror https://example.com/document.docx -cd pdf</code>
┃   This will convert the document to PDF format
┃
┃ • <b>Archive Convert:</b>
┃   <code>/leech https://example.com/archive.rar -cr zip</code>
┃   This will convert the archive to ZIP format
┃
┃ • <b>Delete Original:</b>
┃   <code>/leech https://example.com/video.mp4 -cv mp4 -del</code>
┃   This will convert the video and delete the original file
┃
┃ • <b>Batch Convert:</b>
┃   <code>/leech https://example.com/videos.zip -cv mkv</code>
┃   This will convert all videos in the archive to MKV format
┃
┃ • <b>Note:</b>
┃   All convert settings default to 'none', meaning they won't be used for command generation unless explicitly set.
┃
┠ <b>Combined Examples:</b>
┃ • <b>Trim + Convert:</b>
┃   <code>/leech https://example.com/video.mp4 -trim "00:01:30-00:02:45" -cv mp4</code>
┃   This will trim the video and convert it to MP4 format
┃
┃ • <b>Watermark + Convert:</b>
┃   <code>/leech https://example.com/video.mp4 -watermark "© My Channel" -cv mp4</code>
┃   This will add a watermark and convert the video to MP4 format
┃
┃ • <b>Convert + Merge:</b>
┃   <code>/mirror https://example.com/videos.zip -cv mp4 -merge-video</code>
┃   This will convert all videos to MP4 format and then merge them
┃
┃ • <b>Watermark + Merge:</b>
┃   <code>/leech https://example.com/videos.zip -watermark "© 2025" -merge-video</code>
┃   This will apply both watermark and merge operations
┃
┃ • <b>Multi-Link with Merge:</b>
┃   <code>/mirror -i 3 -m merge-folder -merge-video</code> (reply to first link)
┃   This will download multiple links and merge the videos
┃
┃ • <b>Bulk Download with Merge:</b>
┃   <code>/leech -b -m merge-folder -merge-audio</code> (reply to text with links)
┃   This will download all links and merge the audio files
┃
┃ • <b>All Tools Combined:</b>
┃   <code>/leech https://example.com/videos.zip -watermark "© My Channel" -cv mp4 -merge-video</code>
┃   This will apply watermark, convert to MP4, and merge all videos
┃
┠ <b>Priority Example:</b>
┃ If all tools are enabled with default priorities:
┃ • Merge (priority 1) runs first
┃ • Convert (priority 1) runs second
┃ • Watermark (priority 2) runs last
┃ • Result: One watermark on the final converted merged file
┃
┖ <b>Note:</b> Use the Media Tools settings to configure all options."""

    return text, btns


async def update_media_tools_settings(query, stype="main"):
    """Update media tools settings UI."""
    handler_dict[query.from_user.id] = False

    # Extract page number if present in stype
    page_no = 0
    global merge_config_page
    # Add more detailed logging for trim and trim_config
    if stype in {"trim", "trim_config"}:
        pass
    elif stype.startswith("merge_config "):
        try:
            # Format: merge_config X
            page_no = int(stype.split(" ")[1])
            # Update the global variable
            merge_config_page = page_no
            stype = "merge_config"
        except (ValueError, IndexError) as e:
            # Use the global variable
            page_no = merge_config_page
            LOGGER.error(
                f"Failed to extract page number from stype: {stype}, using global merge_config_page: {page_no}. Error: {e}"
            )
    elif stype == "merge_config":
        # Use the global variable for merge_config
        page_no = merge_config_page
        msg, button = await get_media_tools_settings(
            query.from_user, stype, page_no=page_no
        )
    await edit_message(query.message, msg, button)


def update_user_ldata(user_id, key, value):
    """Update user data with the provided key and value."""
    if user_id in user_data:
        user_data[user_id][key] = value
    else:
        user_data[user_id] = {key: value}


async def get_menu(option, message, user_id):
    """Get menu for a specific option."""
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})
    buttons = ButtonMaker()

    key = "set"
    buttons.data_button(
        "Change" if user_dict.get(option, False) else "Set",
        f"mediatools {user_id} {key} {option}",
    )

    if option in user_dict:
        buttons.data_button("Reset", f"mediatools {user_id} reset {option}")

    # Determine the back button target based on the option
    if option == "WATERMARK_PRIORITY":
        back_target = "watermark"
    elif option == "MERGE_PRIORITY":
        back_target = "merge"
    elif option == "CONVERT_PRIORITY":
        back_target = "convert"
    elif option == "COMPRESSION_PRIORITY":
        back_target = "compression"
    elif option == "TRIM_PRIORITY":
        back_target = "trim"
    elif option == "EXTRACT_PRIORITY":
        back_target = "extract"
    elif option.startswith("WATERMARK_"):
        back_target = "watermark_config"
    elif option.startswith("CONVERT_VIDEO_"):
        back_target = "convert_video"
    elif option.startswith("CONVERT_AUDIO_"):
        back_target = "convert_audio"
    elif option.startswith("CONVERT_SUBTITLE_"):
        back_target = "convert_subtitle"
    elif option.startswith("CONVERT_DOCUMENT_"):
        back_target = "convert_document"
    elif option.startswith("CONVERT_ARCHIVE_"):
        back_target = "convert_archive"
    elif option.startswith("CONVERT_"):
        back_target = "convert"
    elif option in ["TRIM_START_TIME", "TRIM_END_TIME"] or option.startswith(
        (
            "TRIM_VIDEO_",
            "TRIM_AUDIO_",
            "TRIM_IMAGE_",
            "TRIM_DOCUMENT_",
            "TRIM_SUBTITLE_",
            "TRIM_ARCHIVE_",
        )
    ):
        back_target = "trim_config"
    elif option.startswith("TRIM_"):
        back_target = "trim"
    elif option.startswith(
        (
            "EXTRACT_VIDEO_",
            "EXTRACT_AUDIO_",
            "EXTRACT_SUBTITLE_",
            "EXTRACT_ATTACHMENT_",
            "EXTRACT_MAINTAIN_QUALITY",
        )
    ):
        back_target = "extract_config"
    elif option.startswith("EXTRACT_"):
        back_target = "extract"
    elif option.startswith(
        (
            "COMPRESSION_VIDEO_",
            "COMPRESSION_AUDIO_",
            "COMPRESSION_IMAGE_",
            "COMPRESSION_DOCUMENT_",
            "COMPRESSION_SUBTITLE_",
            "COMPRESSION_ARCHIVE_",
        )
    ):
        back_target = "compression_config"
    elif option.startswith("COMPRESSION_"):
        back_target = "compression"
    elif option.startswith("MERGE_") or option in [
        "CONCAT_DEMUXER_ENABLED",
        "FILTER_COMPLEX_ENABLED",
    ]:
        # Check if we need to return to a specific page in merge_config
        global merge_config_page

        if message.text and "Page:" in message.text:
            try:
                page_info = message.text.split("Page:")[1].strip().split("/")[0]
                page_no = int(page_info) - 1
                # Update the global variable
                merge_config_page = page_no
                back_target = f"merge_config {page_no}"
            except (ValueError, IndexError) as e:
                LOGGER.error(
                    f"Failed to extract page number from message text: {e}, using global merge_config_page: {merge_config_page}"
                )
                back_target = f"merge_config {merge_config_page}"
        else:
            # Use the global variable
            back_target = f"merge_config {merge_config_page}"
    else:
        back_target = "back"

    buttons.data_button("Back", f"mediatools {user_id} {back_target}", "footer")
    buttons.data_button("Close", f"mediatools {user_id} close", "footer")

    # Get current value
    if option in user_dict:
        current_value = user_dict[option]
    elif hasattr(Config, option) and getattr(Config, option):
        current_value = f"{getattr(Config, option)} (Global)"
    elif option == "WATERMARK_POSITION":
        current_value = "top_left (Default)"
    elif option == "WATERMARK_SIZE":
        current_value = "20 (Default)"
    elif option == "WATERMARK_COLOR":
        current_value = "white (Default)"
    elif option == "WATERMARK_FONT":
        current_value = "default.otf (Default)"
    elif option == "WATERMARK_PRIORITY":
        current_value = "2 (Default)"
    elif (
        option in {"WATERMARK_THREADING", "WATERMARK_FAST_MODE"}
        or option == "WATERMARK_MAINTAIN_QUALITY"
    ):
        current_value = "True (Default)"
    elif option == "WATERMARK_OPACITY":
        current_value = "1.0 (Default)"
    elif option == "CONVERT_PRIORITY":
        current_value = "3 (Default)"
    elif option == "TRIM_PRIORITY":
        current_value = "4 (Default)"
    elif option == "EXTRACT_PRIORITY":
        current_value = "6 (Default)"
    elif option == "EXTRACT_DELETE_ORIGINAL":
        current_value = "True (Default)"
    elif (
        option in {"EXTRACT_VIDEO_QUALITY", "EXTRACT_VIDEO_PRESET"}
        or option in {"EXTRACT_VIDEO_BITRATE", "EXTRACT_VIDEO_RESOLUTION"}
        or option in {"EXTRACT_VIDEO_FPS", "EXTRACT_AUDIO_BITRATE"}
        or option in {"EXTRACT_AUDIO_CHANNELS", "EXTRACT_AUDIO_SAMPLING"}
        or option in {"EXTRACT_AUDIO_VOLUME", "EXTRACT_SUBTITLE_LANGUAGE"}
        or option in {"EXTRACT_SUBTITLE_ENCODING", "EXTRACT_SUBTITLE_FONT"}
        or option in {"EXTRACT_SUBTITLE_FONT_SIZE", "EXTRACT_ATTACHMENT_FILTER"}
    ):
        current_value = "none (Default)"
    elif option == "COMPRESSION_PRIORITY":
        current_value = "5 (Default)"
    elif (
        option in {"CONVERT_VIDEO_FORMAT", "CONVERT_VIDEO_CODEC"}
        or option == "CONVERT_VIDEO_QUALITY"
    ):
        current_value = "none (Default)"
    elif option == "CONVERT_VIDEO_CRF":
        current_value = "0 (Default)"
    elif option in {"CONVERT_VIDEO_PRESET", "CONVERT_AUDIO_FORMAT"} or option in {
        "CONVERT_AUDIO_CODEC",
        "CONVERT_AUDIO_BITRATE",
    }:
        current_value = "none (Default)"
    elif option in {"CONVERT_AUDIO_CHANNELS", "CONVERT_AUDIO_SAMPLING"}:
        current_value = "0 (Default)"
    elif option == "CONVERT_AUDIO_VOLUME":
        current_value = "0.0 (Default)"
    elif option in {"CONVERT_VIDEO_RESOLUTION", "CONVERT_VIDEO_FPS"}:
        current_value = "none (Default)"
    elif option == "CONVERT_DELETE_ORIGINAL":
        current_value = "False (Default)"
    elif (
        option in {"CONVERT_SUBTITLE_FORMAT", "CONVERT_SUBTITLE_ENCODING"}
        or option in {"CONVERT_SUBTITLE_LANGUAGE", "CONVERT_DOCUMENT_FORMAT"}
        or option == "CONVERT_DOCUMENT_QUALITY"
    ):
        current_value = "none (Default)"
    elif option == "CONVERT_DOCUMENT_DPI":
        current_value = "0 (Default)"
    elif option == "CONVERT_ARCHIVE_FORMAT":
        current_value = "none (Default)"
    elif option == "CONVERT_ARCHIVE_LEVEL":
        current_value = "0 (Default)"
    elif option == "CONVERT_ARCHIVE_METHOD":
        current_value = "none (Default)"
    elif option == "MERGE_PRIORITY":
        current_value = "1 (Default)"
    elif (
        option in {"MERGE_THREADING", "CONCAT_DEMUXER_ENABLED"}
        or option == "FILTER_COMPLEX_ENABLED"
    ):
        current_value = "True (Default)"
    elif option == "MERGE_OUTPUT_FORMAT_VIDEO":
        current_value = "mkv (Default)"
    elif option == "MERGE_OUTPUT_FORMAT_AUDIO":
        current_value = "mp3 (Default)"
    elif option == "MERGE_OUTPUT_FORMAT_IMAGE":
        current_value = "jpg (Default)"
    elif option == "MERGE_OUTPUT_FORMAT_DOCUMENT":
        current_value = "pdf (Default)"
    elif option == "MERGE_OUTPUT_FORMAT_SUBTITLE":
        current_value = "srt (Default)"
    elif option == "MERGE_IMAGE_MODE":
        current_value = "auto (Default)"
    elif option == "MERGE_IMAGE_COLUMNS":
        current_value = "2 (Default)"
    elif option == "MERGE_IMAGE_QUALITY":
        current_value = "90 (Default)"
    elif option == "MERGE_IMAGE_DPI":
        current_value = "300 (Default)"
    elif option == "MERGE_IMAGE_RESIZE":
        current_value = "none (Default)"
    elif option == "MERGE_IMAGE_BACKGROUND":
        current_value = "white (Default)"
    elif option == "MERGE_VIDEO_CODEC":
        current_value = "copy (Default)"
    elif option in {"MERGE_VIDEO_QUALITY", "MERGE_VIDEO_PRESET"}:
        current_value = "medium (Default)"
    elif option == "MERGE_VIDEO_CRF":
        current_value = "23 (Default)"
    elif option == "MERGE_VIDEO_PIXEL_FORMAT":
        current_value = "yuv420p (Default)"
    elif option == "MERGE_VIDEO_TUNE":
        current_value = "film (Default)"
    elif option == "MERGE_VIDEO_FASTSTART":
        current_value = "True (Default)"
    elif option == "MERGE_AUDIO_CODEC":
        current_value = "copy (Default)"
    elif option == "MERGE_AUDIO_BITRATE":
        current_value = "192k (Default)"
    elif option == "MERGE_AUDIO_CHANNELS":
        current_value = "2 (Default)"
    elif option == "MERGE_AUDIO_SAMPLING":
        current_value = "44100 (Default)"
    elif option == "MERGE_AUDIO_VOLUME":
        current_value = "1.0 (Default)"
    elif option == "MERGE_SUBTITLE_ENCODING":
        current_value = "utf-8 (Default)"
    elif option == "MERGE_SUBTITLE_FONT":
        current_value = "Arial (Default)"
    elif option == "MERGE_SUBTITLE_FONT_SIZE":
        current_value = "24 (Default)"
    elif option == "MERGE_SUBTITLE_FONT_COLOR":
        current_value = "white (Default)"
    elif option == "MERGE_SUBTITLE_BACKGROUND":
        current_value = "black (Default)"
    elif option == "MERGE_DOCUMENT_PAPER_SIZE":
        current_value = "a4 (Default)"
    elif option == "MERGE_DOCUMENT_ORIENTATION":
        current_value = "portrait (Default)"
    elif option == "MERGE_DOCUMENT_MARGIN":
        current_value = "50 (Default)"
    elif (
        option in {"MERGE_METADATA_TITLE", "MERGE_METADATA_AUTHOR"}
        or option == "MERGE_METADATA_COMMENT"
    ):
        current_value = "(Default: empty)"
    elif option == "MERGE_REMOVE_ORIGINAL":
        current_value = "True (Default)"
    elif option == "MEDIA_TOOLS_PRIORITY":
        current_value = "Default Order"
    elif option == "TRIM_START_TIME":
        current_value = "00:00:00 (Default)"
    elif option == "TRIM_END_TIME":
        current_value = "End of file (Default)"
    else:
        current_value = "None"

    text = f"<b>Option:</b> {option}\n<b>Current Value:</b> <code>{current_value}</code>\n\n{media_tools_text.get(option, 'Set a value for this option.')}"

    await edit_message(message, text, buttons.build_menu(1))


async def set_option(_, message, option, rfunc):
    """Set an option value from user input."""
    user_id = message.from_user.id
    value = message.text
    # Set handler_dict to False to signal that we've received input

    if option == "WATERMARK_OPACITY":
        try:
            value = float(value)
            if value < 0.0 or value > 1.0:
                error_msg = await send_message(
                    message, "Opacity must be between 0.0 and 1.0!"
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message, "Value must be a valid decimal number between 0.0 and 1.0!"
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option in {"WATERMARK_SIZE", "MERGE_IMAGE_COLUMNS", "MERGE_THREAD_NUMBER"}:
        try:
            value = int(value)
            if value <= 0:
                error_msg = await send_message(
                    message, "Value must be a positive integer!"
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(message, "Value must be a valid integer!")
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "WATERMARK_POSITION":
        valid_positions = [
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "center",
            "top_center",
            "bottom_center",
            "left_center",
            "right_center",
        ]
        if value not in valid_positions:
            error_msg = await send_message(
                message,
                f"Invalid position! Valid options are: {', '.join(valid_positions)}",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_IMAGE_MODE":
        valid_modes = ["auto", "horizontal", "vertical", "collage"]
        if value not in valid_modes:
            error_msg = await send_message(
                message,
                f"Invalid image mode! Valid options are: {', '.join(valid_modes)}",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_CODEC":
        valid_codecs = ["copy", "h264", "h265", "vp9", "av1"]
        if value not in valid_codecs:
            error_msg = await send_message(
                message,
                f"Invalid video codec! Valid options are: {', '.join(valid_codecs)}\nExample: copy - preserves original codec when possible\nExample: h264 - widely compatible codec",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_QUALITY":
        valid_qualities = ["low", "medium", "high", "veryhigh"]
        if value not in valid_qualities:
            error_msg = await send_message(
                message,
                f"Invalid video quality! Valid options are: {', '.join(valid_qualities)}\nExample: medium - balanced quality and file size\nExample: high - better quality but larger file size",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_PRESET":
        valid_presets = [
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ]
        if value not in valid_presets:
            error_msg = await send_message(
                message,
                f"Invalid video preset! Valid options are: {', '.join(valid_presets)}\nExample: medium - balanced encoding speed and compression\nExample: slow - better compression but slower encoding",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_CRF":
        try:
            crf = int(value)
            if crf < 0 or crf > 51:
                error_msg = await send_message(
                    message,
                    "CRF value must be between 0 and 51! Lower values mean better quality but larger file size.\nExample: 23 - default value, good balance\nExample: 18 - visually lossless",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "CRF value must be an integer between 0 and 51!\nExample: 23 - default value, good balance\nExample: 18 - visually lossless",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_PIXEL_FORMAT":
        valid_formats = [
            "yuv420p",
            "yuv422p",
            "yuv444p",
            "yuv420p10le",
            "yuv422p10le",
            "yuv444p10le",
        ]
        if value not in valid_formats:
            error_msg = await send_message(
                message,
                f"Invalid pixel format! Valid options are: {', '.join(valid_formats)}\nExample: yuv420p - most compatible format\nExample: yuv444p - highest quality but larger file size",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_TUNE":
        valid_tunes = [
            "film",
            "animation",
            "grain",
            "stillimage",
            "fastdecode",
            "zerolatency",
        ]
        if value not in valid_tunes:
            error_msg = await send_message(
                message,
                f"Invalid video tune! Valid options are: {', '.join(valid_tunes)}\nExample: film - for live-action content\nExample: animation - for animated content",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_VIDEO_FASTSTART":
        if value.lower() not in ["true", "false"]:
            error_msg = await send_message(
                message,
                "Faststart value must be 'true' or 'false'!\nEnabling faststart allows videos to start playing before they are fully downloaded.",
            )
            await auto_delete_message(error_msg, time=300)
            return
        value = value.lower() == "true"
    elif option == "MERGE_AUDIO_CODEC":
        valid_codecs = ["copy", "aac", "mp3", "opus", "flac"]
        if value not in valid_codecs:
            error_msg = await send_message(
                message,
                f"Invalid audio codec! Valid options are: {', '.join(valid_codecs)}\nExample: copy - preserves original codec when possible\nExample: aac - good quality and compatibility",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_AUDIO_BITRATE":
        valid_bitrates = ["64k", "96k", "128k", "192k", "256k", "320k"]
        if value not in valid_bitrates and not (
            value.endswith("k") and value[:-1].isdigit()
        ):
            error_msg = await send_message(
                message,
                f"Invalid audio bitrate! Common options are: {', '.join(valid_bitrates)}\nExample: 192k - good quality for most content\nExample: 320k - high quality audio",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_AUDIO_CHANNELS":
        try:
            channels = int(value)
            if channels < 1 or channels > 8:
                error_msg = await send_message(
                    message,
                    "Audio channels must be between 1 and 8!\nExample: 2 - stereo audio\nExample: 1 - mono audio",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "Audio channels must be an integer between 1 and 8!\nExample: 2 - stereo audio\nExample: 1 - mono audio",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_AUDIO_SAMPLING":
        valid_rates = ["8000", "11025", "22050", "44100", "48000", "96000"]
        if value not in valid_rates and not value.isdigit():
            error_msg = await send_message(
                message,
                f"Invalid sampling rate! Common options are: {', '.join(valid_rates)}\nExample: 44100 - CD quality\nExample: 48000 - DVD/professional audio quality",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_AUDIO_VOLUME":
        try:
            volume = float(value)
            if volume < 0 or volume > 10:
                error_msg = await send_message(
                    message,
                    "Volume must be between 0 and 10!\nExample: 1.0 - original volume\nExample: 2.0 - double volume",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "Volume must be a number between 0 and 10!\nExample: 1.0 - original volume\nExample: 2.0 - double volume",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "TRIM_START_TIME":
        # Allow empty value for start time (beginning of file)
        if value == "":
            value = "00:00:00"
        # Validate time format (HH:MM:SS or MM:SS or SS)
        import re

        time_pattern = re.compile(r"^(\d+:)?(\d+:)?(\d+)(\.\d+)?$")
        if not time_pattern.match(value):
            error_msg = await send_message(
                message,
                "Invalid time format! Use HH:MM:SS, MM:SS, or SS format.\nExample: 00:01:30 (1 minute 30 seconds)\nExample: 5:45 (5 minutes 45 seconds)\nExample: 90 (90 seconds)",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "TRIM_END_TIME":
        # Allow empty value for end time (end of file)
        if value == "":
            value = ""  # Empty string means end of file
        else:
            # Validate time format (HH:MM:SS or MM:SS or SS)
            import re

            time_pattern = re.compile(r"^(\d+:)?(\d+:)?(\d+)(\.\d+)?$")
            if not time_pattern.match(value):
                error_msg = await send_message(
                    message,
                    "Invalid time format! Use HH:MM:SS, MM:SS, or SS format.\nExample: 00:02:30 (2 minutes 30 seconds)\nExample: 10:45 (10 minutes 45 seconds)\nExample: 180 (180 seconds)",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_DELETE_ORIGINAL":
        if value.lower() not in ["true", "false"]:
            error_msg = await send_message(
                message,
                "Value must be 'true' or 'false'!\nExample: true - delete original files after extraction\nExample: false - keep original files",
            )
            await auto_delete_message(error_msg, time=300)
            return
        value = value.lower() == "true"
    elif option == "EXTRACT_VIDEO_QUALITY":
        if value.lower() == "none":
            value = "none"
        else:
            try:
                quality = int(value)
                if quality < 0 or quality > 51:
                    error_msg = await send_message(
                        message,
                        "CRF value must be between 0 and 51 or 'none'! Lower values mean better quality but larger file size.\nExample: 23 - default value, good balance\nExample: 18 - visually lossless\nExample: none - don't set quality",
                    )
                    await auto_delete_message(error_msg, time=300)
                    return
            except ValueError:
                error_msg = await send_message(
                    message,
                    "CRF value must be an integer between 0 and 51 or 'none'!\nExample: 23 - default value, good balance\nExample: 18 - visually lossless\nExample: none - don't set quality",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_VIDEO_PRESET":
        if value.lower() == "none":
            value = "none"
        else:
            valid_presets = [
                "ultrafast",
                "superfast",
                "veryfast",
                "faster",
                "fast",
                "medium",
                "slow",
                "slower",
                "veryslow",
            ]
            if value not in valid_presets:
                error_msg = await send_message(
                    message,
                    f"Invalid video preset! Valid options are: {', '.join(valid_presets)} or 'none'\nExample: medium - balanced encoding speed and compression\nExample: slow - better compression but slower encoding\nExample: none - don't set preset",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_VIDEO_BITRATE":
        if value.lower() == "none":
            value = "none"
        else:
            valid_bitrates = ["1M", "2M", "5M", "8M", "10M", "15M", "20M"]
            if value not in valid_bitrates and not (
                (value.endswith("k") and value[:-1].isdigit())
                or (value.endswith("M") and value[:-1].isdigit())
            ):
                error_msg = await send_message(
                    message,
                    f"Invalid video bitrate! Common options are: {', '.join(valid_bitrates)} or 'none'\nExample: 5M - 5 megabits per second\nExample: 500k - 500 kilobits per second\nExample: none - don't set bitrate",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_VIDEO_RESOLUTION":
        if value.lower() == "none":
            value = "none"
        else:
            valid_resolutions = ["1920x1080", "1280x720", "854x480", "640x360"]
            if value not in valid_resolutions and not (
                value.count("x") == 1
                and all(part.isdigit() for part in value.split("x"))
            ):
                error_msg = await send_message(
                    message,
                    f"Invalid resolution! Common options are: {', '.join(valid_resolutions)} or 'none'\nExample: 1920x1080 - Full HD\nExample: 1280x720 - HD\nExample: none - don't set resolution",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_VIDEO_FPS":
        if value.lower() == "none":
            value = "none"
        else:
            valid_fps = ["24", "25", "30", "50", "60"]
            if value not in valid_fps and not value.isdigit():
                error_msg = await send_message(
                    message,
                    f"Invalid FPS! Common options are: {', '.join(valid_fps)} or 'none'\nExample: 30 - 30 frames per second\nExample: 60 - 60 frames per second\nExample: none - don't set FPS",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_AUDIO_BITRATE":
        if value.lower() == "none":
            value = "none"
        else:
            valid_bitrates = ["64k", "96k", "128k", "192k", "256k", "320k"]
            if value not in valid_bitrates and not (
                value.endswith("k") and value[:-1].isdigit()
            ):
                error_msg = await send_message(
                    message,
                    f"Invalid audio bitrate! Common options are: {', '.join(valid_bitrates)} or 'none'\nExample: 192k - good quality for most content\nExample: 320k - high quality audio\nExample: none - don't set bitrate",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_AUDIO_CHANNELS":
        if value.lower() == "none":
            value = "none"
        else:
            try:
                channels = int(value)
                if channels < 1 or channels > 8:
                    error_msg = await send_message(
                        message,
                        "Audio channels must be between 1 and 8 or 'none'!\nExample: 2 - stereo audio\nExample: 1 - mono audio\nExample: none - don't set channels",
                    )
                    await auto_delete_message(error_msg, time=300)
                    return
            except ValueError:
                error_msg = await send_message(
                    message,
                    "Audio channels must be an integer between 1 and 8 or 'none'!\nExample: 2 - stereo audio\nExample: 1 - mono audio\nExample: none - don't set channels",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_AUDIO_SAMPLING":
        if value.lower() == "none":
            value = "none"
        else:
            valid_rates = ["8000", "11025", "22050", "44100", "48000", "96000"]
            if value not in valid_rates and not value.isdigit():
                error_msg = await send_message(
                    message,
                    f"Invalid sampling rate! Common options are: {', '.join(valid_rates)} or 'none'\nExample: 44100 - CD quality\nExample: 48000 - DVD/professional audio quality\nExample: none - don't set sampling rate",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_AUDIO_VOLUME":
        if value.lower() == "none":
            value = "none"
        else:
            try:
                volume = float(value)
                if volume < 0 or volume > 10:
                    error_msg = await send_message(
                        message,
                        "Volume must be between 0 and 10 or 'none'!\nExample: 1.0 - original volume\nExample: 2.0 - double volume\nExample: none - don't set volume",
                    )
                    await auto_delete_message(error_msg, time=300)
                    return
            except ValueError:
                error_msg = await send_message(
                    message,
                    "Volume must be a number between 0 and 10 or 'none'!\nExample: 1.0 - original volume\nExample: 2.0 - double volume\nExample: none - don't set volume",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_SUBTITLE_LANGUAGE":
        if value.lower() == "none":
            value = "none"
        else:
            valid_languages = [
                "eng",
                "spa",
                "fre",
                "ger",
                "ita",
                "jpn",
                "chi",
                "kor",
                "rus",
            ]
            if len(value) != 3 and value not in valid_languages:
                error_msg = await send_message(
                    message,
                    f"Invalid language code! Common options are: {', '.join(valid_languages)} or 'none'\nExample: eng - English\nExample: spa - Spanish\nExample: none - don't set language",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_SUBTITLE_ENCODING":
        if value.lower() == "none":
            value = "none"
        else:
            valid_encodings = ["utf-8", "utf-16", "ascii", "latin1", "cp1252"]
            if value not in valid_encodings:
                error_msg = await send_message(
                    message,
                    f"Invalid encoding! Common options are: {', '.join(valid_encodings)} or 'none'\nExample: utf-8 - universal encoding\nExample: latin1 - for Western European languages\nExample: none - don't set encoding",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_SUBTITLE_FONT":
        if value.lower() == "none":
            value = "none"
        elif value.strip() == "":
            error_msg = await send_message(
                message,
                "Font name cannot be empty! Use 'none' to not set a font.\nExample: Arial - widely available font\nExample: DejaVu Sans - good for multiple languages\nExample: none - don't set font",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "EXTRACT_SUBTITLE_FONT_SIZE":
        if value.lower() == "none":
            value = "none"
        else:
            try:
                size = int(value)
                if size < 8 or size > 72:
                    error_msg = await send_message(
                        message,
                        "Font size must be between 8 and 72 or 'none'!\nExample: 24 - medium size\nExample: 32 - larger size for better readability\nExample: none - don't set font size",
                    )
                    await auto_delete_message(error_msg, time=300)
                    return
            except ValueError:
                error_msg = await send_message(
                    message,
                    "Font size must be an integer between 8 and 72 or 'none'!\nExample: 24 - medium size\nExample: 32 - larger size for better readability\nExample: none - don't set font size",
                )
                await auto_delete_message(error_msg, time=300)
                return
    elif option == "EXTRACT_ATTACHMENT_FILTER":
        if value.lower() == "none":
            value = "none"
        elif value.strip() == "":
            error_msg = await send_message(
                message,
                "Filter pattern cannot be empty! Use 'none' to not set a filter.\nExample: *.ttf - extract only TTF font files\nExample: *.jpg - extract only JPG images\nExample: none - don't set filter",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_IMAGE_MODE":
        valid_modes = ["auto", "horizontal", "vertical", "collage"]
        if value not in valid_modes:
            error_msg = await send_message(
                message,
                f"Invalid image mode! Valid options are: {', '.join(valid_modes)}\nExample: auto - choose based on number of images\nExample: collage - grid layout",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_IMAGE_QUALITY":
        try:
            quality = int(value)
            if quality < 1 or quality > 100:
                error_msg = await send_message(
                    message,
                    "Image quality must be between 1 and 100!\nExample: 90 - high quality\nExample: 75 - good balance of quality and size",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "Image quality must be an integer between 1 and 100!\nExample: 90 - high quality\nExample: 75 - good balance of quality and size",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_IMAGE_DPI":
        try:
            dpi = int(value)
            if dpi < 72 or dpi > 1200:
                error_msg = await send_message(
                    message,
                    "DPI must be between 72 and 1200!\nExample: 300 - good for printing\nExample: 72 - standard screen resolution",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "DPI must be an integer between 72 and 1200!\nExample: 300 - good for printing\nExample: 72 - standard screen resolution",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_IMAGE_RESIZE":
        if value != "none" and not (
            value.count("x") == 1
            and all(part.isdigit() for part in value.split("x"))
        ):
            error_msg = await send_message(
                message,
                "Resize value must be 'none' or in the format 'widthxheight'!\nExample: none - keep original size\nExample: 1920x1080 - resize to Full HD",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_IMAGE_BACKGROUND":
        valid_colors = [
            "white",
            "black",
            "transparent",
            "red",
            "green",
            "blue",
            "yellow",
        ]
        if value not in valid_colors and not (
            value.startswith("#") and len(value) == 7
        ):
            error_msg = await send_message(
                message,
                f"Invalid background color! Common options are: {', '.join(valid_colors)} or hex code like #RRGGBB\nExample: white - white background\nExample: #FF0000 - red background",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_SUBTITLE_ENCODING":
        valid_encodings = ["utf-8", "utf-16", "ascii", "latin1", "cp1252"]
        if value not in valid_encodings:
            error_msg = await send_message(
                message,
                f"Invalid encoding! Common options are: {', '.join(valid_encodings)}\nExample: utf-8 - universal encoding\nExample: latin1 - for Western European languages",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_SUBTITLE_FONT":
        # Any font name is valid, but suggest common ones
        if value.strip() == "":
            error_msg = await send_message(
                message,
                "Font name cannot be empty!\nExample: Arial - widely available font\nExample: DejaVu Sans - good for multiple languages",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_SUBTITLE_FONT_SIZE":
        try:
            size = int(value)
            if size < 8 or size > 72:
                error_msg = await send_message(
                    message,
                    "Font size must be between 8 and 72!\nExample: 24 - medium size\nExample: 32 - larger size for better readability",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "Font size must be an integer between 8 and 72!\nExample: 24 - medium size\nExample: 32 - larger size for better readability",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option in {"MERGE_SUBTITLE_FONT_COLOR", "MERGE_SUBTITLE_BACKGROUND"}:
        valid_colors = [
            "white",
            "black",
            "yellow",
            "red",
            "green",
            "blue",
            "transparent",
        ]
        if value not in valid_colors and not (
            value.startswith("#") and len(value) == 7
        ):
            error_msg = await send_message(
                message,
                f"Invalid color! Common options are: {', '.join(valid_colors)} or hex code like #RRGGBB\nExample: white - white text\nExample: #FFFF00 - yellow text",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_DOCUMENT_PAPER_SIZE":
        valid_sizes = ["a4", "letter", "legal", "a3", "a5"]
        if value not in valid_sizes:
            error_msg = await send_message(
                message,
                f"Invalid paper size! Common options are: {', '.join(valid_sizes)}\nExample: a4 - standard international paper size\nExample: letter - standard US paper size",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_DOCUMENT_ORIENTATION":
        valid_orientations = ["portrait", "landscape"]
        if value not in valid_orientations:
            error_msg = await send_message(
                message,
                f"Invalid orientation! Valid options are: {', '.join(valid_orientations)}\nExample: portrait - vertical orientation\nExample: landscape - horizontal orientation",
            )
            await auto_delete_message(error_msg, time=300)
            return
    elif option == "MERGE_DOCUMENT_MARGIN":
        try:
            margin = int(value)
            if margin < 0 or margin > 100:
                error_msg = await send_message(
                    message,
                    "Margin must be between 0 and 100!\nExample: 50 - standard margin\nExample: 0 - no margin",
                )
                await auto_delete_message(error_msg, time=300)
                return
        except ValueError:
            error_msg = await send_message(
                message,
                "Margin must be an integer between 0 and 100!\nExample: 50 - standard margin\nExample: 0 - no margin",
            )
            await auto_delete_message(error_msg, time=300)
            return

    # Set handler_dict to False to signal that we've received input
    handler_dict[user_id] = False

    update_user_ldata(user_id, option, value)
    await delete_message(message)

    # If we're in a merge_config menu with pagination, extract the page number
    if (
        (
            option.startswith("MERGE_")
            or option in ["CONCAT_DEMUXER_ENABLED", "FILTER_COMPLEX_ENABLED"]
        )
        and hasattr(message, "reply_to_message")
        and message.reply_to_message
        and message.reply_to_message.text
        and "Page:" in message.reply_to_message.text
    ):
        try:
            page_info = (
                message.reply_to_message.text.split("Page:")[1].strip().split("/")[0]
            )
            page_no = int(page_info) - 1
            # Update the global merge_config_page variable
            global merge_config_page
            merge_config_page = (
                page_no  # Create a new rfunc that will return to the correct page
            )
            await update_media_tools_settings(message, f"merge_config {page_no}")
        except (ValueError, IndexError) as e:
            LOGGER.error(f"Failed to extract page number from message text: {e}")
            await rfunc()
    else:
        await rfunc()

    await database.update_user_data(user_id)


async def event_handler(client, query, pfunc, rfunc, photo=False, document=False):
    """Handle user input events."""
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = 60  # seconds
    handler = None

    try:
        # Create a custom filter using the event_filter_func
        # We need to create a class to hold our filter method
        class CustomFilter:
            async def event_filter_func(self, _, update):
                # Check if update is a message and has the required attributes
                if (
                    not update
                    or not hasattr(update, "from_user")
                    or update.from_user is None
                ):
                    return False

                if update.from_user.id != user_id:
                    return False
                if photo and (not hasattr(update, "photo") or update.photo is None):
                    return False
                return not (
                    document
                    and (not hasattr(update, "document") or update.document is None)
                )

        # Create the filter using the method from our class
        custom_filter = create(CustomFilter().event_filter_func)

        # Add the handler with the custom filter
        handler = client.add_handler(
            MessageHandler(pfunc, filters=custom_filter), group=-1
        )

        # Wait for user input (up to start_time seconds)
        for _ in range(start_time):
            if not handler_dict[user_id]:
                break
            await sleep(1)

        # Clean up
        if handler_dict[user_id]:
            handler_dict[user_id] = False
            await auto_delete_message(query.message, time=300)
            # If we timed out, call rfunc to go back to the menu
            await rfunc()
    finally:
        # Always remove the handler, even if there was an exception
        if handler:
            client.remove_handler(*handler)


@new_task
async def media_tools_settings(_, message):
    """Show media tools settings."""
    from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

    # Check if media tools are enabled
    if not is_media_tool_enabled("mediatools"):
        error_msg = await send_message(
            message,
            "<b>Media Tools are disabled</b>\n\nMedia Tools have been disabled by the bot owner.",
        )
        # Auto-delete the command message immediately
        await delete_message(message)
        # Auto-delete the error message after 5 minutes
        await auto_delete_message(error_msg, time=300)
        return

    msg, btns = await get_media_tools_settings(message.from_user)
    settings_msg = await send_message(message, msg, btns)
    # Auto-delete the command message immediately
    await delete_message(message)
    # Auto-delete the settings menu after 5 minutes
    await auto_delete_message(settings_msg, time=300)


@new_task
async def edit_media_tools_settings(client, query):
    """Handle media tools settings callback queries."""
    from_user = query.from_user
    user_id = from_user.id
    message = query.message
    data = query.data.split()
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})

    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
        return

    if data[2] == "back":
        await query.answer()
        await update_media_tools_settings(query)
    elif data[2] == "close":
        await query.answer()
        await delete_message(message)
    elif (
        data[2]
        in [
            "watermark",
            "watermark_config",
            "merge",
            "convert",
            "compression",
            "compression_config",
            "trim",
            "trim_config",
            "extract",
            "extract_config",
        ]
        or data[2]
        in [
            "convert_video",
            "convert_audio",
            "convert_subtitle",
            "convert_document",
            "convert_archive",
        ]
        or data[2]
        in [
            "help",
            "help_watermark",
            "help_merge",
            "help_convert",
            "help_compression",
            "help_trim",
            "help_extract",
            "help_priority",
            "help_examples",
        ]
    ):
        await query.answer()
        await update_media_tools_settings(query, data[2])
    elif data[2] == "merge_config" or (len(data) > 3 and data[2] == "merge_config"):
        await query.answer()
        # Declare global variable first
        global merge_config_page
        if len(data) > 3:
            # Page number is provided
            try:
                # Format: merge_config X
                page_no = int(data[3])
                # Update the global variable
                merge_config_page = page_no
                await update_media_tools_settings(query, f"merge_config {page_no}")
            except ValueError as e:
                LOGGER.error(
                    f"Invalid page number: {data[3]}, using global merge_config_page: {merge_config_page}. Error: {e}"
                )
                # If page number is not a valid integer, use the global variable
                await update_media_tools_settings(
                    query, f"merge_config {merge_config_page}"
                )
        else:
            # No page number provided, use the global variable
            await update_media_tools_settings(
                query, f"merge_config {merge_config_page}"
            )
    elif data[2] == "tog":
        await query.answer()
        update_user_ldata(user_id, data[3], data[4] == "t")
        # Determine which menu to return to based on the toggled option
        if data[3].startswith("WATERMARK_"):
            await update_media_tools_settings(query, "watermark")
        elif data[3].startswith("MERGE_") or data[3] in [
            "CONCAT_DEMUXER_ENABLED",
            "FILTER_COMPLEX_ENABLED",
        ]:
            await update_media_tools_settings(query, "merge")
        elif data[3].startswith("CONVERT_"):
            if data[3].startswith("CONVERT_VIDEO_"):
                await update_media_tools_settings(query, "convert_video")
            elif data[3].startswith("CONVERT_AUDIO_"):
                await update_media_tools_settings(query, "convert_audio")
            elif data[3].startswith("CONVERT_SUBTITLE_"):
                await update_media_tools_settings(query, "convert_subtitle")
            elif data[3].startswith("CONVERT_DOCUMENT_"):
                await update_media_tools_settings(query, "convert_document")
            elif data[3].startswith("CONVERT_ARCHIVE_"):
                await update_media_tools_settings(query, "convert_archive")
            else:
                await update_media_tools_settings(query, "convert")
        elif data[3].startswith("COMPRESSION_"):
            if data[3] == "COMPRESSION_ENABLED":
                await update_media_tools_settings(query, "compression")
            elif (
                data[3].startswith("COMPRESSION_VIDEO_")
                or data[3].startswith("COMPRESSION_AUDIO_")
                or data[3].startswith("COMPRESSION_IMAGE_")
                or data[3].startswith("COMPRESSION_DOCUMENT_")
                or data[3].startswith("COMPRESSION_SUBTITLE_")
                or data[3].startswith("COMPRESSION_ARCHIVE_")
            ):
                await update_media_tools_settings(query, "compression_config")
            else:
                await update_media_tools_settings(query, "compression")
        elif data[3].startswith("TRIM_"):
            if data[3] == "TRIM_ENABLED":
                await update_media_tools_settings(query, "trim")
            elif (
                data[3]
                in ["TRIM_START_TIME", "TRIM_END_TIME", "TRIM_DELETE_ORIGINAL"]
                or data[3].startswith("TRIM_VIDEO_")
                or data[3].startswith("TRIM_AUDIO_")
                or data[3].startswith("TRIM_IMAGE_")
                or data[3].startswith("TRIM_DOCUMENT_")
                or data[3].startswith("TRIM_SUBTITLE_")
                or data[3].startswith("TRIM_ARCHIVE_")
            ):
                await update_media_tools_settings(query, "trim_config")
            else:
                await update_media_tools_settings(query, "trim")
        elif data[3].startswith("EXTRACT_"):
            if data[3] == "EXTRACT_ENABLED":
                await update_media_tools_settings(query, "extract")
            elif (
                data[3].startswith("EXTRACT_VIDEO_")
                or data[3].startswith("EXTRACT_AUDIO_")
                or data[3].startswith("EXTRACT_SUBTITLE_")
                or data[3].startswith("EXTRACT_ATTACHMENT_")
            ):
                await update_media_tools_settings(query, "extract_config")
            else:
                await update_media_tools_settings(query, "extract")
        else:
            await update_media_tools_settings(query)
        await database.update_user_data(user_id)
    elif data[2] == "menu":
        await query.answer()
        await get_menu(data[3], message, user_id)
    elif data[2] == "set":
        await query.answer()
        buttons = ButtonMaker()
        text = media_tools_text.get(
            data[3], f"Send a value for {data[3]}. Timeout: 60 sec"
        )
        buttons.data_button("Back", f"mediatools {user_id} menu {data[3]}", "footer")
        buttons.data_button("Close", f"mediatools {user_id} close", "footer")
        await edit_message(message, text, buttons.build_menu(1))

        # Set up function to handle user input
        rfunc = partial(get_menu, data[3], message, user_id)
        pfunc = partial(set_option, option=data[3], rfunc=rfunc)
        await event_handler(client, query, pfunc, rfunc)
    elif data[2] == "reset":
        await query.answer()
        if data[3] in user_dict:
            del user_dict[data[3]]
            await database.update_user_data(user_id)
        await get_menu(data[3], message, user_id)
    elif data[2] == "reset_watermark":
        await query.answer("Resetting all watermark settings to default...")
        # Remove all watermark settings from user_dict
        watermark_keys = [
            "WATERMARK_ENABLED",
            "WATERMARK_KEY",
            "WATERMARK_POSITION",
            "WATERMARK_SIZE",
            "WATERMARK_COLOR",
            "WATERMARK_FONT",
            "WATERMARK_PRIORITY",
            "WATERMARK_THREADING",
        ]
        for key in watermark_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "watermark")
    elif data[2] == "reset_merge":
        await query.answer("Resetting all merge settings to default...")
        # Remove all merge settings from user_dict
        merge_keys = [
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
        ]
        for key in merge_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "merge")
    elif data[2] == "remove_watermark":
        await query.answer("Setting all watermark settings to None...")
        # Set all watermark settings to None/False
        watermark_keys = [
            "WATERMARK_KEY",
            "WATERMARK_POSITION",
            "WATERMARK_SIZE",
            "WATERMARK_COLOR",
            "WATERMARK_FONT",
        ]
        update_user_ldata(user_id, "WATERMARK_ENABLED", False)
        for key in watermark_keys:
            update_user_ldata(user_id, key, "None")
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "watermark")
    elif data[2] == "remove_merge":
        await query.answer("Setting all merge settings to None...")
        # Set all merge settings to None/False
        merge_keys = [
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
            "MERGE_THREAD_NUMBER",
        ]
        update_user_ldata(user_id, "MERGE_ENABLED", False)
        update_user_ldata(user_id, "MERGE_THREADING", False)
        update_user_ldata(user_id, "MERGE_REMOVE_ORIGINAL", False)
        for key in merge_keys:
            if key in [
                "MERGE_VIDEO_CRF",
                "MERGE_IMAGE_COLUMNS",
                "MERGE_IMAGE_QUALITY",
                "MERGE_IMAGE_DPI",
                "MERGE_AUDIO_CHANNELS",
                "MERGE_SUBTITLE_FONT_SIZE",
                "MERGE_DOCUMENT_MARGIN",
            ]:
                update_user_ldata(user_id, key, 0)
            elif key == "MERGE_AUDIO_VOLUME":
                update_user_ldata(user_id, key, 0.0)
            elif key == "MERGE_VIDEO_FASTSTART":
                update_user_ldata(user_id, key, False)
            else:
                update_user_ldata(user_id, key, "none")
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "merge")
    elif data[2] == "reset_trim":
        await query.answer("Resetting all trim settings to default...")
        # Remove all trim settings from user_dict
        trim_keys = [
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
        ]
        for key in trim_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "trim")

    elif data[2] == "reset_extract":
        await query.answer("Resetting all extract settings to default...")
        # Remove all extract settings from user_dict
        extract_keys = [
            "EXTRACT_ENABLED",
            "EXTRACT_PRIORITY",
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
            "EXTRACT_DELETE_ORIGINAL",
        ]
        for key in extract_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "extract")

    elif data[2] == "reset_compression":
        await query.answer("Resetting all compression settings to default...")
        # Remove all compression settings from user_dict
        compression_keys = [
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
        ]
        for key in compression_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "compression")

    elif data[2] == "reset_convert":
        await query.answer("Resetting all convert settings to default...")
        # Remove all convert settings from user_dict
        convert_keys = [
            "CONVERT_ENABLED",
            "CONVERT_PRIORITY",
            "CONVERT_DELETE_ORIGINAL",
            "CONVERT_VIDEO_ENABLED",
            "CONVERT_VIDEO_FORMAT",
            "CONVERT_VIDEO_CODEC",
            "CONVERT_VIDEO_QUALITY",
            "CONVERT_VIDEO_CRF",
            "CONVERT_VIDEO_PRESET",
            "CONVERT_VIDEO_RESOLUTION",
            "CONVERT_VIDEO_FPS",
            "CONVERT_VIDEO_MAINTAIN_QUALITY",
            "CONVERT_AUDIO_ENABLED",
            "CONVERT_AUDIO_FORMAT",
            "CONVERT_AUDIO_CODEC",
            "CONVERT_AUDIO_BITRATE",
            "CONVERT_AUDIO_CHANNELS",
            "CONVERT_AUDIO_SAMPLING",
            "CONVERT_AUDIO_VOLUME",
            "CONVERT_SUBTITLE_ENABLED",
            "CONVERT_SUBTITLE_FORMAT",
            "CONVERT_SUBTITLE_ENCODING",
            "CONVERT_SUBTITLE_LANGUAGE",
            "CONVERT_DOCUMENT_ENABLED",
            "CONVERT_DOCUMENT_FORMAT",
            "CONVERT_DOCUMENT_QUALITY",
            "CONVERT_DOCUMENT_DPI",
            "CONVERT_ARCHIVE_ENABLED",
            "CONVERT_ARCHIVE_FORMAT",
            "CONVERT_ARCHIVE_LEVEL",
            "CONVERT_ARCHIVE_METHOD",
        ]
        for key in convert_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "convert")
    elif data[2] == "remove_trim":
        await query.answer("Setting all trim settings to None...")
        # Set all trim settings to None/False
        trim_keys = [
            "TRIM_VIDEO_CODEC",
            "TRIM_VIDEO_PRESET",
            "TRIM_AUDIO_CODEC",
            "TRIM_AUDIO_PRESET",
            "TRIM_IMAGE_QUALITY",
            "TRIM_DOCUMENT_QUALITY",
            "TRIM_SUBTITLE_ENCODING",
        ]
        update_user_ldata(user_id, "TRIM_ENABLED", False)
        update_user_ldata(user_id, "TRIM_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "TRIM_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "TRIM_IMAGE_ENABLED", False)
        update_user_ldata(user_id, "TRIM_DOCUMENT_ENABLED", False)
        update_user_ldata(user_id, "TRIM_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "TRIM_ARCHIVE_ENABLED", False)
        # Set start and end time to default values
        update_user_ldata(user_id, "TRIM_START_TIME", "00:00:00")
        update_user_ldata(user_id, "TRIM_END_TIME", "")
        for key in trim_keys:
            update_user_ldata(user_id, key, "none")
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "trim")

    elif data[2] == "remove_extract":
        await query.answer("Setting all extract settings to None...")
        # Set all extract settings to None/False
        extract_keys = [
            "EXTRACT_VIDEO_CODEC",
            "EXTRACT_VIDEO_FORMAT",
            "EXTRACT_VIDEO_INDEX",
            "EXTRACT_VIDEO_QUALITY",
            "EXTRACT_VIDEO_PRESET",
            "EXTRACT_VIDEO_BITRATE",
            "EXTRACT_VIDEO_RESOLUTION",
            "EXTRACT_VIDEO_FPS",
            "EXTRACT_AUDIO_CODEC",
            "EXTRACT_AUDIO_FORMAT",
            "EXTRACT_AUDIO_INDEX",
            "EXTRACT_AUDIO_BITRATE",
            "EXTRACT_AUDIO_CHANNELS",
            "EXTRACT_AUDIO_SAMPLING",
            "EXTRACT_AUDIO_VOLUME",
            "EXTRACT_SUBTITLE_CODEC",
            "EXTRACT_SUBTITLE_FORMAT",
            "EXTRACT_SUBTITLE_INDEX",
            "EXTRACT_SUBTITLE_LANGUAGE",
            "EXTRACT_SUBTITLE_ENCODING",
            "EXTRACT_SUBTITLE_FONT",
            "EXTRACT_SUBTITLE_FONT_SIZE",
            "EXTRACT_ATTACHMENT_FORMAT",
            "EXTRACT_ATTACHMENT_INDEX",
            "EXTRACT_ATTACHMENT_FILTER",
        ]
        update_user_ldata(user_id, "EXTRACT_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_ATTACHMENT_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_MAINTAIN_QUALITY", True)
        for key in extract_keys:
            update_user_ldata(user_id, key, None)
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "extract")

    elif data[2] == "remove_compression":
        await query.answer("Setting all compression settings to None...")
        # Set all compression settings to None/False
        compression_keys = [
            "COMPRESSION_VIDEO_PRESET",
            "COMPRESSION_VIDEO_CRF",
            "COMPRESSION_VIDEO_CODEC",
            "COMPRESSION_VIDEO_TUNE",
            "COMPRESSION_VIDEO_PIXEL_FORMAT",
            "COMPRESSION_AUDIO_PRESET",
            "COMPRESSION_AUDIO_CODEC",
            "COMPRESSION_AUDIO_BITRATE",
            "COMPRESSION_AUDIO_CHANNELS",
            "COMPRESSION_IMAGE_PRESET",
            "COMPRESSION_IMAGE_QUALITY",
            "COMPRESSION_IMAGE_RESIZE",
            "COMPRESSION_DOCUMENT_PRESET",
            "COMPRESSION_DOCUMENT_DPI",
            "COMPRESSION_SUBTITLE_PRESET",
            "COMPRESSION_SUBTITLE_ENCODING",
            "COMPRESSION_ARCHIVE_PRESET",
            "COMPRESSION_ARCHIVE_LEVEL",
            "COMPRESSION_ARCHIVE_METHOD",
        ]
        update_user_ldata(user_id, "COMPRESSION_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_IMAGE_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_DOCUMENT_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_ARCHIVE_ENABLED", False)
        for key in compression_keys:
            if key in [
                "COMPRESSION_VIDEO_CRF",
                "COMPRESSION_AUDIO_CHANNELS",
                "COMPRESSION_IMAGE_QUALITY",
                "COMPRESSION_DOCUMENT_DPI",
                "COMPRESSION_ARCHIVE_LEVEL",
            ]:
                update_user_ldata(user_id, key, 0)
            else:
                update_user_ldata(user_id, key, "none")
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "compression")

    elif data[2] == "remove_convert":
        await query.answer("Setting all convert settings to None...")
        # Set all convert settings to None/False
        convert_keys = [
            "CONVERT_VIDEO_FORMAT",
            "CONVERT_VIDEO_CODEC",
            "CONVERT_VIDEO_QUALITY",
            "CONVERT_VIDEO_CRF",
            "CONVERT_VIDEO_PRESET",
            "CONVERT_VIDEO_RESOLUTION",
            "CONVERT_VIDEO_FPS",
            "CONVERT_AUDIO_FORMAT",
            "CONVERT_AUDIO_CODEC",
            "CONVERT_AUDIO_BITRATE",
            "CONVERT_AUDIO_CHANNELS",
            "CONVERT_AUDIO_SAMPLING",
            "CONVERT_AUDIO_VOLUME",
            "CONVERT_SUBTITLE_FORMAT",
            "CONVERT_SUBTITLE_ENCODING",
            "CONVERT_SUBTITLE_LANGUAGE",
            "CONVERT_DOCUMENT_FORMAT",
            "CONVERT_DOCUMENT_QUALITY",
            "CONVERT_DOCUMENT_DPI",
            "CONVERT_ARCHIVE_FORMAT",
            "CONVERT_ARCHIVE_LEVEL",
            "CONVERT_ARCHIVE_METHOD",
        ]
        update_user_ldata(user_id, "CONVERT_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_DOCUMENT_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_ARCHIVE_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_VIDEO_MAINTAIN_QUALITY", False)
        update_user_ldata(user_id, "CONVERT_DELETE_ORIGINAL", False)
        for key in convert_keys:
            if key in [
                "CONVERT_VIDEO_CRF",
                "CONVERT_AUDIO_CHANNELS",
                "CONVERT_AUDIO_SAMPLING",
            ]:
                update_user_ldata(user_id, key, 0)
            elif key == "CONVERT_AUDIO_VOLUME":
                update_user_ldata(user_id, key, 0.0)
            else:
                update_user_ldata(user_id, key, "none")
        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "convert")
    elif data[2] == "remove_all":
        await query.answer("Setting all media tools settings to None...")
        # Set all media tools settings to None/False
        watermark_keys = [
            "WATERMARK_KEY",
            "WATERMARK_POSITION",
            "WATERMARK_SIZE",
            "WATERMARK_COLOR",
            "WATERMARK_FONT",
        ]
        merge_keys = [
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
            "MERGE_THREAD_NUMBER",
        ]
        convert_keys = [
            "CONVERT_VIDEO_FORMAT",
            "CONVERT_VIDEO_CODEC",
            "CONVERT_VIDEO_QUALITY",
            "CONVERT_VIDEO_CRF",
            "CONVERT_VIDEO_PRESET",
            "CONVERT_VIDEO_RESOLUTION",
            "CONVERT_VIDEO_FPS",
            "CONVERT_AUDIO_FORMAT",
            "CONVERT_AUDIO_CODEC",
            "CONVERT_AUDIO_BITRATE",
            "CONVERT_AUDIO_CHANNELS",
            "CONVERT_AUDIO_SAMPLING",
            "CONVERT_AUDIO_VOLUME",
            "CONVERT_SUBTITLE_FORMAT",
            "CONVERT_SUBTITLE_ENCODING",
            "CONVERT_SUBTITLE_LANGUAGE",
            "CONVERT_DOCUMENT_FORMAT",
            "CONVERT_DOCUMENT_QUALITY",
            "CONVERT_DOCUMENT_DPI",
            "CONVERT_ARCHIVE_FORMAT",
            "CONVERT_ARCHIVE_LEVEL",
            "CONVERT_ARCHIVE_METHOD",
        ]
        update_user_ldata(user_id, "WATERMARK_ENABLED", False)
        update_user_ldata(user_id, "MERGE_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_DOCUMENT_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_ARCHIVE_ENABLED", False)
        update_user_ldata(user_id, "CONVERT_VIDEO_MAINTAIN_QUALITY", False)
        update_user_ldata(user_id, "CONVERT_DELETE_ORIGINAL", False)
        update_user_ldata(user_id, "COMPRESSION_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_IMAGE_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_DOCUMENT_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "COMPRESSION_ARCHIVE_ENABLED", False)
        update_user_ldata(user_id, "TRIM_ENABLED", False)
        update_user_ldata(user_id, "TRIM_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "TRIM_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "TRIM_IMAGE_ENABLED", False)
        update_user_ldata(user_id, "TRIM_DOCUMENT_ENABLED", False)
        update_user_ldata(user_id, "TRIM_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "TRIM_ARCHIVE_ENABLED", False)
        update_user_ldata(user_id, "TRIM_START_TIME", "00:00:00")
        update_user_ldata(user_id, "TRIM_END_TIME", "")
        update_user_ldata(user_id, "TRIM_IMAGE_QUALITY", "none")
        update_user_ldata(user_id, "TRIM_DOCUMENT_QUALITY", "none")
        update_user_ldata(user_id, "TRIM_VIDEO_CODEC", "none")
        update_user_ldata(user_id, "TRIM_VIDEO_PRESET", "none")
        update_user_ldata(user_id, "TRIM_AUDIO_CODEC", "none")
        update_user_ldata(user_id, "TRIM_AUDIO_PRESET", "none")
        update_user_ldata(user_id, "TRIM_SUBTITLE_ENCODING", "none")

        # Extract settings
        update_user_ldata(user_id, "EXTRACT_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_VIDEO_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_AUDIO_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_ATTACHMENT_ENABLED", False)
        update_user_ldata(user_id, "EXTRACT_MAINTAIN_QUALITY", True)
        update_user_ldata(user_id, "EXTRACT_DELETE_ORIGINAL", True)

        # Video extract settings
        update_user_ldata(user_id, "EXTRACT_VIDEO_CODEC", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_FORMAT", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_INDEX", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_QUALITY", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_PRESET", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_BITRATE", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_RESOLUTION", None)
        update_user_ldata(user_id, "EXTRACT_VIDEO_FPS", None)

        # Audio extract settings
        update_user_ldata(user_id, "EXTRACT_AUDIO_CODEC", None)
        update_user_ldata(user_id, "EXTRACT_AUDIO_FORMAT", None)
        update_user_ldata(user_id, "EXTRACT_AUDIO_INDEX", None)
        update_user_ldata(user_id, "EXTRACT_AUDIO_BITRATE", None)
        update_user_ldata(user_id, "EXTRACT_AUDIO_CHANNELS", None)
        update_user_ldata(user_id, "EXTRACT_AUDIO_SAMPLING", None)
        update_user_ldata(user_id, "EXTRACT_AUDIO_VOLUME", None)

        # Subtitle extract settings
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_CODEC", None)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_FORMAT", None)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_INDEX", None)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_LANGUAGE", None)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_ENCODING", None)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_FONT", None)
        update_user_ldata(user_id, "EXTRACT_SUBTITLE_FONT_SIZE", None)

        # Attachment extract settings
        update_user_ldata(user_id, "EXTRACT_ATTACHMENT_FORMAT", None)
        update_user_ldata(user_id, "EXTRACT_ATTACHMENT_INDEX", None)
        update_user_ldata(user_id, "EXTRACT_ATTACHMENT_FILTER", None)

        for key in watermark_keys:
            update_user_ldata(user_id, key, "None")

        for key in merge_keys:
            if key in [
                "MERGE_VIDEO_CRF",
                "MERGE_IMAGE_COLUMNS",
                "MERGE_IMAGE_QUALITY",
                "MERGE_IMAGE_DPI",
                "MERGE_AUDIO_CHANNELS",
                "MERGE_SUBTITLE_FONT_SIZE",
                "MERGE_DOCUMENT_MARGIN",
            ]:
                update_user_ldata(user_id, key, 0)
            elif key == "MERGE_AUDIO_VOLUME":
                update_user_ldata(user_id, key, 0.0)
            elif key == "MERGE_VIDEO_FASTSTART":
                update_user_ldata(user_id, key, False)
            else:
                update_user_ldata(user_id, key, "none")

        for key in convert_keys:
            if key in [
                "CONVERT_VIDEO_CRF",
                "CONVERT_AUDIO_CHANNELS",
                "CONVERT_AUDIO_SAMPLING",
            ]:
                update_user_ldata(user_id, key, 0)
            elif key == "CONVERT_AUDIO_VOLUME":
                update_user_ldata(user_id, key, 0.0)
            else:
                update_user_ldata(user_id, key, "none")

        compression_keys = [
            "COMPRESSION_VIDEO_PRESET",
            "COMPRESSION_VIDEO_CRF",
            "COMPRESSION_VIDEO_CODEC",
            "COMPRESSION_VIDEO_TUNE",
            "COMPRESSION_VIDEO_PIXEL_FORMAT",
            "COMPRESSION_AUDIO_PRESET",
            "COMPRESSION_AUDIO_CODEC",
            "COMPRESSION_AUDIO_BITRATE",
            "COMPRESSION_AUDIO_CHANNELS",
            "COMPRESSION_IMAGE_PRESET",
            "COMPRESSION_IMAGE_QUALITY",
            "COMPRESSION_IMAGE_RESIZE",
            "COMPRESSION_DOCUMENT_PRESET",
            "COMPRESSION_DOCUMENT_DPI",
            "COMPRESSION_SUBTITLE_PRESET",
            "COMPRESSION_SUBTITLE_ENCODING",
            "COMPRESSION_ARCHIVE_PRESET",
            "COMPRESSION_ARCHIVE_LEVEL",
            "COMPRESSION_ARCHIVE_METHOD",
        ]

        for key in compression_keys:
            if key in [
                "COMPRESSION_VIDEO_CRF",
                "COMPRESSION_AUDIO_CHANNELS",
                "COMPRESSION_IMAGE_QUALITY",
                "COMPRESSION_DOCUMENT_DPI",
                "COMPRESSION_ARCHIVE_LEVEL",
            ]:
                update_user_ldata(user_id, key, 0)
            else:
                update_user_ldata(user_id, key, "none")

        await database.update_user_data(user_id)
        await update_media_tools_settings(query)
    elif data[2] == "reset_all":
        await query.answer("Resetting all media tools settings to default...")
        # Remove all media tools settings from user_dict
        media_tools_keys = [
            "WATERMARK_ENABLED",
            "WATERMARK_KEY",
            "WATERMARK_POSITION",
            "WATERMARK_SIZE",
            "WATERMARK_COLOR",
            "WATERMARK_FONT",
            "WATERMARK_PRIORITY",
            "WATERMARK_THREADING",
            "MERGE_ENABLED",
            "CONCAT_DEMUXER_ENABLED",
            "FILTER_COMPLEX_ENABLED",
            "MERGE_OUTPUT_FORMAT_VIDEO",
            "MERGE_OUTPUT_FORMAT_AUDIO",
            "MERGE_PRIORITY",
            "MERGE_THREADING",
            "CONVERT_ENABLED",
            "CONVERT_PRIORITY",
            "CONVERT_VIDEO_ENABLED",
            "CONVERT_VIDEO_FORMAT",
            "CONVERT_VIDEO_CODEC",
            "CONVERT_VIDEO_QUALITY",
            "CONVERT_VIDEO_CRF",
            "CONVERT_VIDEO_PRESET",
            "CONVERT_VIDEO_MAINTAIN_QUALITY",
            "CONVERT_AUDIO_ENABLED",
            "CONVERT_AUDIO_FORMAT",
            "CONVERT_AUDIO_CODEC",
            "CONVERT_AUDIO_BITRATE",
            "CONVERT_AUDIO_CHANNELS",
            "CONVERT_AUDIO_SAMPLING",
            "CONVERT_AUDIO_VOLUME",
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
            "EXTRACT_DELETE_ORIGINAL",
            "MEDIA_TOOLS_PRIORITY",
        ]
        for key in media_tools_keys:
            if key in user_dict:
                del user_dict[key]
        await database.update_user_data(user_id)
        await update_media_tools_settings(query)
    elif data[2] == "toggle_concat_filter":
        # Toggle between concat demuxer and filter complex
        toggle_mode = data[3]  # 'both', 'concat', or 'filter'

        if toggle_mode == "both":
            # Enable both
            update_user_ldata(user_id, "CONCAT_DEMUXER_ENABLED", True)
            update_user_ldata(user_id, "FILTER_COMPLEX_ENABLED", True)
            await query.answer("Both Concat Demuxer and Filter Complex enabled")
        elif toggle_mode == "concat":
            # Enable only concat
            update_user_ldata(user_id, "CONCAT_DEMUXER_ENABLED", True)
            update_user_ldata(user_id, "FILTER_COMPLEX_ENABLED", False)
            await query.answer("Only Concat Demuxer enabled")
        elif toggle_mode == "filter":
            # Enable only filter
            update_user_ldata(user_id, "CONCAT_DEMUXER_ENABLED", False)
            update_user_ldata(user_id, "FILTER_COMPLEX_ENABLED", True)
            await query.answer("Only Filter Complex enabled")
        else:
            # Fallback - enable both
            update_user_ldata(user_id, "CONCAT_DEMUXER_ENABLED", True)
            update_user_ldata(user_id, "FILTER_COMPLEX_ENABLED", True)
            await query.answer("Both Concat Demuxer and Filter Complex enabled")

        await database.update_user_data(user_id)
        await update_media_tools_settings(query, "merge")


async def add_media_tools_button_to_bot_settings(buttons):
    """Add Media Tools button to bot settings."""
    from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

    # Only add the Media Tools button if media tools are enabled
    if is_media_tool_enabled("mediatools"):
        buttons.data_button("Media Tools", "botset mediatools")

    return buttons


async def show_media_tools_for_task(client, message, task_obj):
    """Show media tools settings with a Done button for task execution.

    This function is called when a command is used with the -mt flag.
    It displays the media tools settings and adds a Done button to start the task.

    Args:
        client: The client instance
        message: The message object containing the command
        task_obj: The task object (Mirror instance) to be executed after settings

    Returns:
        bool: True if the task should proceed, False if it was cancelled
    """
    from bot.helper.ext_utils.bot_utils import is_media_tool_enabled

    # Check if media tools are enabled
    if not is_media_tool_enabled("mediatools"):
        error_msg = await send_message(
            message,
            "<b>Media Tools are disabled</b>\n\nMedia Tools have been disabled by the bot owner. The -mt flag cannot be used.",
        )
        # Auto-delete the error message after 5 minutes
        await auto_delete_message(error_msg, time=300)
        return False

    user_id = message.from_user.id if message.from_user else 0
    handler_dict[user_id] = True

    # Get media tools settings
    msg, btns = await get_media_tools_settings(message.from_user)

    # Create new buttons with the original menu buttons
    buttons = ButtonMaker()

    # Copy all buttons from the original menu except Close
    for row in btns.inline_keyboard:
        for btn in row:
            if btn.text == "Close":
                continue  # Skip the Close button
            if "footer" in btn.callback_data:
                buttons.data_button(btn.text, btn.callback_data, "footer")
            else:
                buttons.data_button(btn.text, btn.callback_data)

    # Add the Done and Cancel buttons to the footer
    buttons.data_button("Done", f"mediatools {user_id} task_done", "footer")
    buttons.data_button("Cancel", f"mediatools {user_id} task_cancel", "footer")

    # Send the message with the settings and buttons
    settings_msg = await send_message(message, msg, buttons.build_menu(2))

    # Create an event to wait for the user's response
    from asyncio import Event

    done_event = Event()
    task_proceed = [True]  # Use a list to store the result (mutable)

    # Define the callback handler for the buttons
    async def task_button_callback(c, query):
        if query.from_user.id != user_id:
            await query.answer("Not Yours!", show_alert=True)
            return

        data = query.data.split()
        if len(data) < 3:
            return

        if data[2] == "task_done":
            # User clicked Done, proceed with the task
            await query.answer("Starting task with current media tools settings...")
            handler_dict[user_id] = False

            # Send a confirmation message that will be auto-deleted
            done_msg = await send_message(
                message,
                "✅ Starting task with current media tools settings...",
            )
            await auto_delete_message(
                done_msg, time=5
            )  # Auto-delete after 5 seconds

            done_event.set()

        elif data[2] == "task_cancel":
            # User clicked Cancel, cancel the task
            await query.answer("Task cancelled!")
            task_proceed[0] = False
            handler_dict[user_id] = False

            # Send cancellation message and auto-delete after 5 minutes
            cancel_msg = await send_message(
                message,
                "❌ Task cancelled by user.",
            )
            await auto_delete_message(cancel_msg, time=300)

            done_event.set()

        elif data[2] in [
            "watermark",
            "watermark_config",
            "merge",
            "convert",
            "compression",
            "compression_config",
            "trim",
            "trim_config",
            "extract",
            "extract_config",
            "help",
            "help_watermark",
            "help_merge",
            "help_convert",
            "help_compression",
            "help_trim",
            "help_extract",
            "help_priority",
            "help_examples",
            "convert_video",
            "convert_audio",
            "convert_subtitle",
            "convert_document",
            "convert_archive",
            "merge_config",
            "back",
        ]:
            # Handle navigation within the media tools settings
            await query.answer()
            await update_media_tools_settings(query, data[2])

        elif (
            data[2] == "tog"
            or data[2] == "menu"
            or data[2] == "set"
            or data[2] == "reset"
            or data[2].startswith("reset_")
            or data[2].startswith("remove_")
            or data[2] == "toggle_concat_filter"
        ):
            # Handle other media tools settings actions
            # This will reuse the existing edit_media_tools_settings logic
            await edit_media_tools_settings(c, query)

    # Add the callback handler
    handler = client.add_handler(
        CallbackQueryHandler(
            task_button_callback,
            filters=filters.regex("^mediatools"),
        ),
        group=-1,
    )

    try:
        # Wait for the user to click Done or Cancel, or for the timeout
        timeout = 60  # 60 seconds timeout
        for _ in range(timeout):
            if done_event.is_set():
                break
            await sleep(1)

        # If we timed out, cancel the task
        if not done_event.is_set():
            task_proceed[0] = False
            handler_dict[user_id] = False

            # Send timeout message
            timeout_msg = await send_message(
                message,
                "⏱️ Media tools settings timeout. Task has been cancelled!",
            )

            # Auto-delete the timeout message after 5 minutes
            await auto_delete_message(timeout_msg, time=300)
    finally:
        # Clean up
        client.remove_handler(*handler)

        # Delete the settings message
        await delete_message(settings_msg)

    # Return whether to proceed with the task
    return task_proceed[0]
