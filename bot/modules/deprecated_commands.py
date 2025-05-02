from bot.core.config_manager import Config
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    send_message,
)


async def handle_qb_commands(client, message):
    """Handle deprecated commands and show warning messages.

    Currently handles:
    - /qbleech and variants: Suggests using /leech instead
    - /qbmirror and variants: Suggests using /mirror instead

    Args:
        client: The client instance
        message: The message object containing the command
    """
    command = message.text.split()[0].lower()

    if "qbleech" in command:
        warning_msg = "⚠️ <b>Warning:</b> /qbleech command is deprecated. Please use /leech command instead."
    else:  # qbmirror
        warning_msg = "⚠️ <b>Warning:</b> /qbmirror command is deprecated. Please use /mirror command instead."

    # Send warning message
    reply = await send_message(message, warning_msg)

    # Schedule both messages for auto-deletion after 5 minutes (300 seconds)
    await auto_delete_message(reply, message, time=300)


async def handle_no_suffix_commands(client, message):
    """Handle commands without suffix and show warning messages.

    Shows a warning when users use commands without the command suffix.

    Args:
        client: The client instance
        message: The message object containing the command
    """
    command = message.text.split()[0].lower().lstrip("/")

    # Get the command suffix from config
    cmd_suffix = Config.CMD_SUFFIX

    if not cmd_suffix:
        # If no suffix is configured, don't show any warning
        return

    warning_msg = f"⚠️ <b>Warning:</b> For Bot <b>{cmd_suffix}</b> use /{command}{cmd_suffix}. Thank you."

    # Send warning message
    reply = await send_message(message, warning_msg)

    # Schedule both messages for auto-deletion after 5 minutes (300 seconds)
    await auto_delete_message(reply, message, time=300)
