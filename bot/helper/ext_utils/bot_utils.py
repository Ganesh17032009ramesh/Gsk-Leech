import math
from asyncio import (
    create_subprocess_exec,
    create_subprocess_shell,
    run_coroutine_threadsafe,
    sleep,
)
from asyncio.subprocess import PIPE
from base64 import urlsafe_b64decode, urlsafe_b64encode
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps

from httpx import AsyncClient

from bot import bot_loop, user_data
from bot.core.config_manager import Config
from bot.helper.telegram_helper.button_build import ButtonMaker

try:
    from bot.helper.ext_utils.gc_utils import smart_garbage_collection
except ImportError:
    smart_garbage_collection = None

from .help_messages import (
    AI_HELP_DICT,
    CLONE_HELP_DICT,
    MIRROR_HELP_DICT,
    YT_HELP_DICT,
)
from .telegraph_helper import telegraph

COMMAND_USAGE = {}

THREAD_POOL = ThreadPoolExecutor(max_workers=500)


class SetInterval:
    def __init__(self, interval, action, *args, **kwargs):
        self.interval = interval
        self.action = action
        self.task = bot_loop.create_task(self._set_interval(*args, **kwargs))

    async def _set_interval(self, *args, **kwargs):
        while True:
            await sleep(self.interval)
            await self.action(*args, **kwargs)

    def cancel(self):
        self.task.cancel()


def _build_command_usage(help_dict, command_key):
    buttons = ButtonMaker()
    for name in list(help_dict.keys())[1:]:
        buttons.data_button(name, f"help {command_key} {name}")
    buttons.data_button("Close", "help close")
    COMMAND_USAGE[command_key] = [help_dict["main"], buttons.build_menu(3)]
    buttons.reset()


def create_help_buttons():
    _build_command_usage(MIRROR_HELP_DICT, "mirror")
    _build_command_usage(YT_HELP_DICT, "yt")
    _build_command_usage(CLONE_HELP_DICT, "clone")
    _build_command_usage(AI_HELP_DICT, "ai")


def bt_selection_buttons(id_):
    gid = id_[:12] if len(id_) > 25 else id_
    pin = "".join([n for n in id_ if n.isdigit()][:4])
    buttons = ButtonMaker()
    if Config.WEB_PINCODE:
        buttons.url_button("Select Files", f"{Config.BASE_URL}/app/files?gid={id_}")
        buttons.data_button("Pincode", f"sel pin {gid} {pin}")
    else:
        buttons.url_button(
            "Select Files",
            f"{Config.BASE_URL}/app/files?gid={id_}&pin={pin}",
        )
    buttons.data_button("Done Selecting", f"sel done {gid} {id_}")
    buttons.data_button("Cancel", f"sel cancel {gid}")
    return buttons.build_menu(2)


async def get_telegraph_list(telegraph_content):
    path = [
        (
            await telegraph.create_page(
                title="Mirror-Leech-Bot Drive Search",
                content=content,
            )
        )["path"]
        for content in telegraph_content
    ]
    if len(path) > 1:
        await telegraph.edit_telegraph(path, telegraph_content)
    buttons = ButtonMaker()
    buttons.url_button("🔎 VIEW", f"https://telegra.ph/{path[0]}")
    return buttons.build_menu(1)


def arg_parser(items, arg_base):
    if not items:
        return

    arg_start = -1
    i = 0
    total = len(items)

    bool_arg_set = {
        "-b",
        "-e",
        "-z",
        "-s",
        "-j",
        "-d",
        "-sv",
        "-ss",
        "-f",
        "-fd",
        "-fu",
        "-sync",
        "-hl",
        "-doc",
        "-med",
        "-ut",
        "-bt",
        "-es",
        "-compress",
        "-comp-video",
        "-comp-audio",
        "-comp-image",
        "-comp-document",
        "-comp-subtitle",
        "-comp-archive",
        "-video-fast",
        "-video-medium",
        "-video-slow",
        "-audio-fast",
        "-audio-medium",
        "-audio-slow",
        "-image-fast",
        "-image-medium",
        "-image-slow",
        "-document-fast",
        "-document-medium",
        "-document-slow",
        "-subtitle-fast",
        "-subtitle-medium",
        "-subtitle-slow",
        "-archive-fast",
        "-archive-medium",
        "-archive-slow",
        "-extract",
        "-extract-video",
        "-extract-audio",
        "-extract-subtitle",
        "-extract-attachment",
        "-extract-priority",
        "-del",
        "-mt",
    }

    while i < total:
        part = items[i]
        if part in arg_base:
            if arg_start == -1:
                arg_start = i
            if (i + 1 == total and part in bool_arg_set) or part in [
                "-s",
                "-j",
                "-f",
                "-fd",
                "-fu",
                "-sync",
                "-hl",
                "-doc",
                "-med",
                "-ut",
                "-bt",
                "-es",
                "-compress",
                "-comp-video",
                "-comp-audio",
                "-comp-image",
                "-comp-document",
                "-comp-subtitle",
                "-comp-archive",
                "-video-fast",
                "-video-medium",
                "-video-slow",
                "-audio-fast",
                "-audio-medium",
                "-audio-slow",
                "-image-fast",
                "-image-medium",
                "-image-slow",
                "-document-fast",
                "-document-medium",
                "-document-slow",
                "-subtitle-fast",
                "-subtitle-medium",
                "-subtitle-slow",
                "-archive-fast",
                "-archive-medium",
                "-archive-slow",
                "-extract",
                "-extract-video",
                "-extract-audio",
                "-extract-subtitle",
                "-extract-attachment",
                "-del",
                "-mt",
            ]:
                arg_base[part] = True
            else:
                sub_list = []
                for j in range(i + 1, total):
                    if items[j] in arg_base:
                        if part in bool_arg_set and not sub_list:
                            arg_base[part] = True
                            break
                        if not sub_list:
                            break
                        check = " ".join(sub_list).strip()
                        if (
                            check.startswith("[") and check.endswith("]")
                        ) or not check.startswith("["):
                            break
                    sub_list.append(items[j])
                if sub_list:
                    value = " ".join(sub_list)
                    if part == "-ff" and not value.strip().startswith("["):
                        arg_base[part].add(value)
                    else:
                        arg_base[part] = value
                    i += len(sub_list)
        i += 1
    if "link" in arg_base:
        link_items = items[:arg_start] if arg_start != -1 else items
        if link_items:
            arg_base["link"] = " ".join(link_items)


def get_size_bytes(size):
    size = size.lower()
    if "k" in size:
        size = int(float(size.split("k")[0]) * 1024)
    elif "m" in size:
        size = int(float(size.split("m")[0]) * 1048576)
    elif "g" in size:
        size = int(float(size.split("g")[0]) * 1073741824)
    elif "t" in size:
        size = int(float(size.split("t")[0]) * 1099511627776)
    else:
        size = 0
    return size


async def get_content_type(url):
    try:
        async with AsyncClient() as client:
            response = await client.get(url, allow_redirects=True, verify=False)
            return response.headers.get("Content-Type")
    except Exception:
        return None


def get_user_split_size(user_id, args, file_size, equal_splits=False):
    """
    Calculate the split size based on user settings, command arguments, and file size.
    User settings take priority over owner bot settings.

    Args:
        user_id: User ID for retrieving user settings
        args: Command arguments that may override settings
        file_size: Size of the file to be split
        equal_splits: Whether to use equal splits calculation

    Returns:
        int: Calculated split size in bytes
        bool: Whether to skip splitting
    """
    from bot import user_data
    from bot.core.aeon_client import TgClient
    from bot.core.config_manager import Config

    user_dict = user_data.get(user_id, {})

    # Calculate max split size based on owner's session only
    # Always use owner's session for max split size calculation, not user's own session
    max_split_size = (
        TgClient.MAX_SPLIT_SIZE
        if hasattr(Config, "USER_SESSION_STRING") and Config.USER_SESSION_STRING
        else 2097152000
    )

    # Get split size from command args, user settings, or bot config (in that order)
    # This ensures custom split sizes set by user or owner get priority
    split_size = 0

    # Command args have highest priority (if args is provided)
    if args is not None and args.get("-sp"):
        split_arg = args.get("-sp")
        if split_arg.isdigit():
            split_size = int(split_arg)
        else:
            split_size = get_size_bytes(split_arg)
    # User settings have second priority
    elif user_dict.get("LEECH_SPLIT_SIZE"):
        split_size = user_dict.get("LEECH_SPLIT_SIZE")
    # Owner settings have third priority
    elif Config.LEECH_SPLIT_SIZE and max_split_size != Config.LEECH_SPLIT_SIZE:
        split_size = Config.LEECH_SPLIT_SIZE
    # Default to max split size if no custom size is set
    else:
        split_size = max_split_size

    # Ensure split size never exceeds Telegram's limit (based on premium status)
    # TgClient.MAX_SPLIT_SIZE is already set based on premium status
    # This will be 4000 MiB for premium users and 2000 MiB for regular users
    telegram_limit = TgClient.MAX_SPLIT_SIZE

    # Add a safety margin to ensure we never exceed Telegram's limit
    # Use a 10 MiB safety margin to account for any overhead or rounding issues
    safety_margin = 10 * 1024 * 1024  # 10 MiB
    safe_telegram_limit = telegram_limit - safety_margin

    if split_size > safe_telegram_limit:
        telegram_limit / (1024 * 1024 * 1024)
        safe_telegram_limit / (1024 * 1024 * 1024)
        split_size = safe_telegram_limit

    # Ensure split size doesn't exceed maximum allowed
    split_size = min(split_size, max_split_size)

    # If equal splits is enabled, always split the file into equal parts based on max split size
    if equal_splits:
        if file_size <= max_split_size:
            # If file size is less than max split size, no need to split
            return file_size, True
        # Calculate number of parts needed based on max split size
        parts = math.ceil(file_size / max_split_size)
        # Calculate equal split size
        equal_split_size = math.ceil(file_size / parts)
        # Ensure the calculated equal split size is never greater than max split size
        equal_split_size = min(equal_split_size, max_split_size)
        # Never skip splitting if equal splits is on and file size is greater than max split size
        return equal_split_size, False
    # For regular splitting (not equal splits):
    # Skip splitting if file size is less than the split size
    if file_size <= split_size:
        return file_size, True
    # Always split the file if it's larger than split_size, regardless of max_split_size
    # This ensures files larger than max_split_size still get split when equal_splits is off
    return split_size, False


def update_user_ldata(id_, key, value):
    user_data.setdefault(id_, {})
    user_data[id_][key] = value


def encode_slink(string):
    return (urlsafe_b64encode(string.encode("ascii")).decode("ascii")).strip("=")


def decode_slink(b64_str):
    return urlsafe_b64decode(
        (b64_str.strip("=") + "=" * (-len(b64_str.strip("=")) % 4)).encode("ascii"),
    ).decode("ascii")


async def cmd_exec(
    cmd, shell=False, apply_limits=False, process_id=None, task_type="FFmpeg"
):
    """Execute a command and return its output.

    Args:
        cmd: Command to execute (list or string)
        shell: Whether to use shell execution
        apply_limits: Whether to apply resource limits (deprecated, kept for compatibility)
        process_id: Unique identifier for the process (deprecated, kept for compatibility)
        task_type: Type of task (e.g., "FFmpeg", "Watermark", "Merge")

    Returns:
        tuple: (stdout, stderr, return_code)
    """
    import shlex

    # Handle shell commands with special characters
    if shell and isinstance(cmd, str):
        # Use shlex.quote to properly escape the command for shell execution
        cmd_parts = shlex.split(cmd)
        cmd = " ".join(shlex.quote(part) for part in cmd_parts)

    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)

    stdout, stderr = await proc.communicate()
    try:
        stdout = stdout.decode().strip()
    except Exception:
        stdout = "Unable to decode the response!"
    try:
        stderr = stderr.decode().strip()
    except Exception:
        stderr = "Unable to decode the error!"

    # Force garbage collection after resource-intensive operations
    if (
        task_type in ["FFmpeg", "Watermark", "Merge", "7z", "Split File"]
        and smart_garbage_collection is not None
    ):
        smart_garbage_collection(
            aggressive=True
        )  # Use aggressive mode for resource-intensive operations
    elif proc.returncode != 0 and smart_garbage_collection is not None:
        # Also collect garbage after failed operations to clean up any partial resources
        smart_garbage_collection(aggressive=False)

    return stdout, stderr, proc.returncode


def new_task(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return bot_loop.create_task(func(*args, **kwargs))

    return wrapper


async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREAD_POOL, pfunc)
    result = await future if wait else future

    # Force garbage collection after large operations
    if (
        smart_garbage_collection is not None
        and hasattr(func, "__name__")
        and func.__name__
        in ["walk", "get_media_info", "extract", "zip", "get_path_size"]
    ):
        smart_garbage_collection(
            aggressive=False
        )  # Use normal mode for standard operations

    return result


def async_to_sync(func, *args, wait=True, **kwargs):
    future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
    return future.result() if wait else future


def loop_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future

    return wrapper


def is_media_tool_enabled(tool_name):
    """Check if a specific media tool is enabled in the global configuration.

    Args:
        tool_name (str): The name of the tool to check (merge, watermark, convert, etc.)
                         Use 'mediatools' to check if all media tools are enabled.

    Returns:
        bool: True if the tool is enabled, False otherwise
    """
    from bot.core.config_manager import Config

    # If ENABLE_EXTRA_MODULES is False, all extra modules are disabled
    if not Config.ENABLE_EXTRA_MODULES:
        return False

    # If media tools are completely disabled (boolean False), return False
    if Config.MEDIA_TOOLS_ENABLED is False:
        return False

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

    # Parse enabled tools from the configuration
    enabled_tools = []

    # If MEDIA_TOOLS_ENABLED is a string
    if isinstance(Config.MEDIA_TOOLS_ENABLED, str):
        # Handle both comma-separated and single values
        if "," in Config.MEDIA_TOOLS_ENABLED:
            enabled_tools = [
                t.strip().lower()
                for t in Config.MEDIA_TOOLS_ENABLED.split(",")
                if t.strip()
            ]
        elif Config.MEDIA_TOOLS_ENABLED.strip():  # Single non-empty value
            enabled_tools = [Config.MEDIA_TOOLS_ENABLED.strip().lower()]

    # If MEDIA_TOOLS_ENABLED is True (boolean), all tools are enabled
    elif Config.MEDIA_TOOLS_ENABLED is True:
        enabled_tools = all_tools.copy()

    # If MEDIA_TOOLS_ENABLED is some other truthy value
    elif Config.MEDIA_TOOLS_ENABLED:
        if isinstance(Config.MEDIA_TOOLS_ENABLED, list | tuple | set):
            enabled_tools = [
                str(t).strip().lower() for t in Config.MEDIA_TOOLS_ENABLED if t
            ]
        else:
            # Try to convert to string and use as a single value
            try:
                val = str(Config.MEDIA_TOOLS_ENABLED).strip().lower()
                if val:
                    enabled_tools = [val]
            except:
                pass

    # If checking for 'mediatools' (general media tools status), return True if any tool is enabled
    if tool_name.lower() == "mediatools":
        return len(enabled_tools) > 0

    # Otherwise, check if the specific tool is in the enabled list
    return tool_name.lower() in enabled_tools


def is_flag_enabled(flag_name):
    """Check if a specific command flag is enabled based on media tools configuration.

    Args:
        flag_name (str): The name of the flag to check (ff, sv, mt, etc.)

    Returns:
        bool: True if the flag is enabled, False otherwise
    """
    # Map flags to their corresponding media tools
    flag_to_tool_map = {
        "ff": "ffmpeg",  # Custom FFmpeg commands flag
        "sv": "sample",  # Sample video flag
        "mt": "mediatools",  # Media tools flag
        "md": "metadata",  # Metadata flag
        "merge-video": "merge",
        "merge-audio": "merge",
        "merge-subtitle": "merge",
        "merge-all": "merge",
        "merge-image": "merge",
        "merge-pdf": "merge",
        "watermark": "watermark",
        "extract": "extract",
        "extract-video": "extract",
        "extract-audio": "extract",
        "extract-subtitle": "extract",
        "extract-attachment": "extract",
        "trim": "trim",
        "compress": "compression",
        "comp-video": "compression",
        "comp-audio": "compression",
        "comp-image": "compression",
        "comp-document": "compression",
        "comp-subtitle": "compression",
        "comp-archive": "compression",
    }

    # If the flag is not in the map, assume it's enabled
    if flag_name.lstrip("-") not in flag_to_tool_map:
        return True

    # Get the tool name for this flag
    tool_name = flag_to_tool_map[flag_name.lstrip("-")]

    # Check if the tool is enabled
    return is_media_tool_enabled(tool_name)
