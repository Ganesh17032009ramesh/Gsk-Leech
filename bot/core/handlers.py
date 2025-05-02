from pyrogram import filters
from pyrogram.filters import command, regex
from pyrogram.handlers import (
    CallbackQueryHandler,
    EditedMessageHandler,
    MessageHandler,
)

from bot.core.config_manager import Config
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.modules import (
    add_sudo,
    aeon_callback,
    aioexecute,
    arg_usage,
    ask_ai,
    authorize,
    bot_help,
    bot_stats,
    cancel,
    cancel_all_buttons,
    cancel_all_update,
    cancel_multi,
    check_scheduled_deletions,
    clear,
    clone_node,
    confirm_restart,
    confirm_selection,
    count_node,
    delete_file,
    delete_pending_messages,
    edit_bot_settings,
    edit_media_tools_settings,
    edit_user_settings,
    execute,
    font_styles_cmd,
    force_delete_all_messages,
    gdrive_search,
    gen_session,
    get_rss_menu,
    get_users_settings,
    handle_broadcast_command,
    handle_broadcast_media,
    handle_cancel_broadcast_command,
    handle_cancel_command,
    handle_command,
    handle_group_gensession,
    handle_no_suffix_commands,
    handle_qb_commands,
    handle_session_input,
    hydra_search,
    imdb_callback,
    imdb_search,
    jd_leech,
    jd_mirror,
    leech,
    log,
    login,
    media_tools_help_cmd,
    media_tools_settings,
    mediainfo,
    mirror,
    music_cancel_callback,
    music_get_callback,
    music_search,
    nzb_leech,
    nzb_mirror,
    ping,
    remove_from_queue,
    remove_sudo,
    restart_bot,
    rss_listener,
    run_shell,
    select,
    select_type,
    send_bot_settings,
    send_user_settings,
    speedtest,
    start,
    status_pages,
    task_status,
    torrent_search,
    torrent_search_update,
    truecaller_lookup,
    unauthorize,
    ytdl,
    ytdl_leech,
)
from bot.modules.font_styles import font_styles_callback
from bot.modules.media_tools_help import media_tools_help_callback

from .aeon_client import TgClient


def add_handlers():
    command_filters = {
        "authorize": (
            authorize,
            BotCommands.AuthorizeCommand,
            CustomFilters.sudo,
        ),
        "unauthorize": (
            unauthorize,
            BotCommands.UnAuthorizeCommand,
            CustomFilters.sudo,
        ),
        "add_sudo": (
            add_sudo,
            BotCommands.AddSudoCommand,
            CustomFilters.sudo,
        ),
        "remove_sudo": (
            remove_sudo,
            BotCommands.RmSudoCommand,
            CustomFilters.sudo,
        ),
        "send_bot_settings": (
            send_bot_settings,
            BotCommands.BotSetCommand,
            CustomFilters.sudo,
        ),
        "cancel_all_buttons": (
            cancel_all_buttons,
            BotCommands.CancelAllCommand,
            CustomFilters.authorized,
        ),
        "clone_node": (
            clone_node,
            BotCommands.CloneCommand,
            CustomFilters.authorized,
        ),
        "aioexecute": (
            aioexecute,
            BotCommands.AExecCommand,
            CustomFilters.sudo,
        ),
        "execute": (
            execute,
            BotCommands.ExecCommand,
            CustomFilters.sudo,
        ),
        "clear": (
            clear,
            BotCommands.ClearLocalsCommand,
            CustomFilters.sudo,
        ),
        "select": (
            select,
            BotCommands.SelectCommand,
            CustomFilters.authorized,
        ),
        "remove_from_queue": (
            remove_from_queue,
            BotCommands.ForceStartCommand,
            CustomFilters.authorized,
        ),
        "count_node": (
            count_node,
            BotCommands.CountCommand,
            CustomFilters.authorized,
        ),
        "delete_file": (
            delete_file,
            BotCommands.DeleteCommand,
            CustomFilters.authorized,
        ),
        "gdrive_search": (
            gdrive_search,
            BotCommands.ListCommand,
            CustomFilters.authorized,
        ),
        "mirror": (
            mirror,
            BotCommands.MirrorCommand,
            CustomFilters.authorized,
        ),
        "jd_mirror": (
            jd_mirror,
            BotCommands.JdMirrorCommand,
            CustomFilters.authorized,
        ),
        "leech": (
            leech,
            BotCommands.LeechCommand,
            CustomFilters.authorized,
        ),
        "jd_leech": (
            jd_leech,
            BotCommands.JdLeechCommand,
            CustomFilters.authorized,
        ),
        "get_rss_menu": (
            get_rss_menu,
            BotCommands.RssCommand,
            CustomFilters.owner,
        ),
        "run_shell": (
            run_shell,
            BotCommands.ShellCommand,
            CustomFilters.owner,
        ),
        "start": (
            start,
            BotCommands.StartCommand,
            None,
        ),
        "log": (
            log,
            BotCommands.LogCommand,
            CustomFilters.sudo,
        ),
        "restart_bot": (
            restart_bot,
            BotCommands.RestartCommand,
            CustomFilters.sudo,
        ),
        "ping": (
            ping,
            BotCommands.PingCommand,
            CustomFilters.authorized,
        ),
        "bot_help": (
            bot_help,
            BotCommands.HelpCommand,
            CustomFilters.authorized,
        ),
        "bot_stats": (
            bot_stats,
            BotCommands.StatsCommand,
            CustomFilters.authorized,
        ),
        "check_scheduled_deletions": (
            check_scheduled_deletions,
            BotCommands.CheckDeletionsCommand,
            CustomFilters.sudo,
        ),
        "task_status": (
            task_status,
            BotCommands.StatusCommand,
            CustomFilters.authorized,
        ),
        "s": (
            task_status,
            BotCommands.StatusCommand,
            CustomFilters.authorized,
        ),
        "statusall": (
            task_status,
            BotCommands.StatusCommand,
            CustomFilters.authorized,
        ),
        "sall": (
            task_status,
            BotCommands.StatusCommand,
            CustomFilters.authorized,
        ),
        "torrent_search": (
            torrent_search,
            BotCommands.SearchCommand,
            CustomFilters.authorized,
        ),
        "get_users_settings": (
            get_users_settings,
            BotCommands.UsersCommand,
            CustomFilters.sudo,
        ),
        "send_user_settings": (
            send_user_settings,
            BotCommands.UserSetCommand,
            CustomFilters.authorized & filters.group,
        ),
        "ytdl": (
            ytdl,
            BotCommands.YtdlCommand,
            CustomFilters.authorized,
        ),
        "ytdl_leech": (
            ytdl_leech,
            BotCommands.YtdlLeechCommand,
            CustomFilters.authorized,
        ),
        #    "restart_sessions": (
        #        restart_sessions,
        #        BotCommands.RestartSessionsCommand,
        #        CustomFilters.sudo,
        #    ),
        "mediainfo": (
            mediainfo,
            BotCommands.MediaInfoCommand,
            CustomFilters.authorized,
        ),
        "speedtest": (
            speedtest,
            BotCommands.SpeedTest,
            CustomFilters.authorized,
        ),
        "broadcast": (
            handle_broadcast_command,
            BotCommands.BroadcastCommand,
            CustomFilters.owner,
        ),
        "nzb_mirror": (
            nzb_mirror,
            BotCommands.NzbMirrorCommand,
            CustomFilters.authorized,
        ),
        "nzb_leech": (
            nzb_leech,
            BotCommands.NzbLeechCommand,
            CustomFilters.authorized,
        ),
        "hydra_search": (
            hydra_search,
            BotCommands.HydraSearchCommamd,
            CustomFilters.authorized,
        ),
        "font_styles_cmd": (
            font_styles_cmd,
            BotCommands.FontStylesCommand,
            CustomFilters.authorized & filters.group,
        ),
        "imdb_search": (
            imdb_search,
            BotCommands.IMDBCommand,
            CustomFilters.authorized,
        ),
        "login": (
            login,
            BotCommands.LoginCommand,
            None,
        ),
        "music_search": (
            music_search,
            BotCommands.MusicSearchCommand,
            CustomFilters.authorized,
        ),
        "media_tools_settings": (
            media_tools_settings,
            BotCommands.MediaToolsCommand,
            CustomFilters.authorized & filters.group,
        ),
        "media_tools_help_cmd": (
            media_tools_help_cmd,
            BotCommands.MediaToolsHelpCommand,
            CustomFilters.authorized & filters.group,
        ),
        "gen_session": (
            handle_command,
            BotCommands.GenSessionCommand,
            filters.private,  # Only allow in private chats
        ),
        "truecaller_lookup": (
            truecaller_lookup,
            BotCommands.TruecallerCommand,
            CustomFilters.authorized,
        ),
        "ask_ai": (
            ask_ai,
            BotCommands.AskCommand,
            CustomFilters.authorized,
        ),
    }

    for handler_func, command_name, custom_filter in command_filters.values():
        if custom_filter:
            filters_to_apply = (
                command(command_name, case_sensitive=True) & custom_filter
            )
        else:
            filters_to_apply = command(command_name, case_sensitive=True)

        TgClient.bot.add_handler(
            MessageHandler(
                handler_func,
                filters=filters_to_apply,
            ),
            group=0,
        )

    regex_filters = {
        "^botset": edit_bot_settings,
        "^canall": cancel_all_update,
        "^stopm": cancel_multi,
        "^sel": confirm_selection,
        "^list_types": select_type,
        "^rss": rss_listener,
        "^torser": torrent_search_update,
        "^userset": edit_user_settings,
        "^mediatools": edit_media_tools_settings,
        "^help": arg_usage,
        "^status": status_pages,
        "^botrestart": confirm_restart,
        "^aeon": aeon_callback,
        "^imdb": imdb_callback,
        "^musget": music_get_callback,
        "^muscancel": music_cancel_callback,
        "^fontstyles": font_styles_callback,
        "^mthelp": media_tools_help_callback,
        "^gensession": gen_session,
        "delete_pending": delete_pending_messages,
        "force_delete_all": force_delete_all_messages,
    }

    # Add handlers for other callbacks
    for regex_filter, handler_func in regex_filters.items():
        TgClient.bot.add_handler(
            CallbackQueryHandler(handler_func, filters=regex(regex_filter)),
            group=0,
        )

    TgClient.bot.add_handler(
        EditedMessageHandler(
            run_shell,
            filters=command(BotCommands.ShellCommand, case_sensitive=True)
            & CustomFilters.owner,
        ),
        group=0,
    )
    TgClient.bot.add_handler(
        MessageHandler(
            cancel,
            filters=regex(r"^/stop(_\w+)?(?!all)") & CustomFilters.authorized,
        ),
        group=0,
    )

    # Add handler for deprecated commands (qbleech, qbmirror) with any suffix
    TgClient.bot.add_handler(
        MessageHandler(
            handle_qb_commands,
            filters=regex(r"^/qb(leech|mirror)(\d+|[a-zA-Z0-9_]+)?")
            & CustomFilters.authorized,
        ),
        group=0,
    )

    # Add handler for commands without suffix
    TgClient.bot.add_handler(
        MessageHandler(
            handle_no_suffix_commands,
            filters=regex(
                r"^/(mirror|leech|jdmirror|jdleech|nzbmirror|nzbleech|ytdl|ytdlleech|clone|count|del|list|search|mediainfo|mi|status|s|ping|help|speedtest|ask)$"
            )
            & CustomFilters.authorized,
        ),
        group=0,
    )

    # Add a handler for /gensession in groups to guide users to PM
    TgClient.bot.add_handler(
        MessageHandler(
            handle_group_gensession,
            filters=command(BotCommands.GenSessionCommand, case_sensitive=True)
            & filters.group,
        ),
        group=0,
    )

    # Add handlers for settings commands in private chats without authorization
    TgClient.bot.add_handler(
        MessageHandler(
            send_user_settings,
            filters=command(BotCommands.UserSetCommand, case_sensitive=True)
            & filters.private,
        ),
        group=0,
    )

    TgClient.bot.add_handler(
        MessageHandler(
            media_tools_settings,
            filters=command(BotCommands.MediaToolsCommand, case_sensitive=True)
            & filters.private,
        ),
        group=0,
    )

    TgClient.bot.add_handler(
        MessageHandler(
            media_tools_help_cmd,
            filters=command(BotCommands.MediaToolsHelpCommand, case_sensitive=True)
            & filters.private,
        ),
        group=0,
    )

    TgClient.bot.add_handler(
        MessageHandler(
            font_styles_cmd,
            filters=command(BotCommands.FontStylesCommand, case_sensitive=True)
            & filters.private,
        ),
        group=0,
    )

    # Add a handler for /cancel command in private chats
    TgClient.bot.add_handler(
        MessageHandler(
            handle_cancel_command,
            filters=command("cancel", case_sensitive=False) & filters.private,
        ),
        group=0,
    )

    # Add a handler for /cancelbc command for broadcast cancellation
    TgClient.bot.add_handler(
        MessageHandler(
            # Use our dedicated cancel function
            handle_cancel_broadcast_command,
            filters=command("cancelbc", case_sensitive=False)
            & filters.private
            & filters.create(
                lambda _, __, m: m.from_user and m.from_user.id == Config.OWNER_ID
                # We don't check broadcast_awaiting_message here to allow cancellation
                # even if the state tracking has issues
            ),
        ),
        group=4,  # Use a specific group number for this handler
    )

    # Add handler for broadcast media (second step) - text messages
    TgClient.bot.add_handler(
        MessageHandler(
            # Use our dedicated media handler function (works for text too)
            handle_broadcast_media,
            filters=filters.private
            & filters.text
            & filters.create(
                lambda _, __, m: (
                    # Must be from owner
                    m.from_user
                    and m.from_user.id == Config.OWNER_ID
                    # Exclude commands
                    and not (
                        hasattr(m, "text") and m.text and m.text.startswith("/")
                    )
                )
                # We'll check broadcast_awaiting_message inside the handler
            ),
        ),
        group=5,  # Use a higher group number to ensure it's processed after command handlers
    )

    # Add handler for broadcast media (second step) - media messages
    TgClient.bot.add_handler(
        MessageHandler(
            # Use our dedicated media handler function
            handle_broadcast_media,
            filters=filters.private
            & (
                filters.photo
                | filters.video
                | filters.document
                | filters.audio
                | filters.voice
                | filters.sticker
                | filters.animation
            )
            & filters.create(
                lambda _, __, m: (
                    # Must be from owner
                    m.from_user and m.from_user.id == Config.OWNER_ID
                )
                # We'll check broadcast_awaiting_message inside the handler
            ),
        ),
        group=3,  # Use a lower group number to ensure it's processed before other handlers
    )

    # Define a custom filter for non-command messages, but allow /cancel
    def session_input_filter(*args):
        # Extract update from args (args[2])
        update = args[2]
        if update.text:
            # Allow /cancel command specifically
            if update.text.lower() == "/cancel":
                return True

            # Filter out other commands
            for prefix in ["/", "!", "."]:
                if update.text.startswith(prefix):
                    return False
        return True

    # Add a persistent handler for session generation input
    TgClient.bot.add_handler(
        MessageHandler(
            handle_session_input,
            # Use a filter that allows normal messages and /cancel command
            filters=filters.private
            & filters.incoming
            & filters.create(session_input_filter),
        ),
        group=1,  # Higher priority group
    )
