import asyncio
import logging

import psutil

from bot.core.config_manager import Config

LOGGER = logging.getLogger(__name__)

# Global variables to track system resources
system_load = {
    "cpu_percent": 0,
    "memory_percent": 0,
    "available_memory_mb": 0,
    "total_memory_mb": 0,
}

# Track active FFmpeg processes
active_ffmpeg_processes = {}


async def update_system_load():
    """Update system resource usage information."""
    try:
        # Get CPU usage
        system_load["cpu_percent"] = psutil.cpu_percent(interval=1)

        # Get memory usage
        memory = psutil.virtual_memory()
        system_load["memory_percent"] = memory.percent
        system_load["available_memory_mb"] = memory.available // (1024 * 1024)
        system_load["total_memory_mb"] = memory.total // (1024 * 1024)
    except Exception as e:
        LOGGER.error(f"Error updating system load: {e}")


async def monitor_system_resources():
    """Periodically monitor system resources."""
    while True:
        await update_system_load()
        await asyncio.sleep(10)  # Update every 10 seconds


async def get_optimal_thread_count():
    """Calculate optimal thread count based on current system load."""
    if not Config.FFMPEG_DYNAMIC_THREADS:
        # If dynamic threading is disabled, use the configured thread count
        return None

    # Get number of CPU cores
    cpu_count = psutil.cpu_count(logical=True)

    # Calculate available cores based on current CPU usage
    # If CPU is 80% busy, we'll use fewer threads
    available_cores = max(1, int(cpu_count * (1 - system_load["cpu_percent"] / 100)))

    # Ensure we use at least 1 thread but not more than available cores
    return max(1, min(available_cores, cpu_count))


def get_cpu_affinity():
    """Get CPU affinity setting from config."""
    if not Config.FFMPEG_CPU_AFFINITY:
        return None

    try:
        # Parse CPU affinity string (e.g., "0-3" or "0,2,4,6")
        affinity = []
        for part in Config.FFMPEG_CPU_AFFINITY.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                affinity.extend(range(start, end + 1))
            else:
                affinity.append(int(part))

        # Ensure affinity is valid
        cpu_count = psutil.cpu_count(logical=True)
        affinity = [cpu for cpu in affinity if 0 <= cpu < cpu_count]

        if not affinity:
            LOGGER.warning("Invalid CPU affinity configuration, using all cores")
            return None

        return affinity
    except Exception as e:
        LOGGER.error(f"Error parsing CPU affinity: {e}")
        return None


async def apply_resource_limits(cmd, process_id=None, task_type="FFmpeg"):
    """
    Apply resource limits to a command before execution.

    Args:
        cmd: Command list to execute
        process_id: Unique identifier for the process (optional, used for logging)
        task_type: Type of task (e.g., "FFmpeg", "Watermark", "Merge")

    Returns:
        Modified command with resource limits applied
    """
    import shlex

    # Log the process ID if provided
    if process_id:
        pass
    # Apply memory limits if configured
    memory_limit = Config.FFMPEG_MEMORY_LIMIT

    if memory_limit > 0:
        # Convert MB to KB for ulimit
        memory_limit_kb = memory_limit * 1024

        # Properly escape command arguments to handle special characters
        escaped_cmd = " ".join(shlex.quote(str(arg)) for arg in cmd)

        # Prepend ulimit command to limit memory
        # -v: virtual memory limit
        cmd = [
            "bash",
            "-c",
            f"ulimit -v {memory_limit_kb} && {escaped_cmd}",
        ]  # Apply CPU affinity if configured
    cpu_affinity = get_cpu_affinity()
    if cpu_affinity:
        # Use taskset to set CPU affinity
        affinity_str = ",".join(map(str, cpu_affinity))
        cmd = [
            "taskset",
            "-c",
            affinity_str,
            *cmd,
        ]  # Apply thread count if dynamic threading is enabled
    if Config.FFMPEG_DYNAMIC_THREADS:
        thread_count = await get_optimal_thread_count()
        if thread_count is not None:
            # Find and replace the -threads parameter if it exists
            for i, arg in enumerate(cmd):
                if arg == "-threads" and i + 1 < len(cmd):
                    cmd[i + 1] = str(thread_count)
                    break

    return cmd


async def execute_with_resource_limits(cmd, process_id=None, task_type="FFmpeg"):
    """
    Execute a command with resource limits applied.

    Args:
        cmd: Command list to execute
        process_id: Unique identifier for the process (optional)
        task_type: Type of task (e.g., "FFmpeg", "Watermark", "Merge")

    Returns:
        Process object
    """
    # Apply resource limits
    limited_cmd = await apply_resource_limits(cmd, process_id, task_type)

    # Execute the command
    process = await asyncio.create_subprocess_exec(
        *limited_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Track the process if ID is provided
    if process_id:
        active_ffmpeg_processes[process_id] = process

    return process


def cleanup_process(process_id):
    """Remove a process from tracking."""
    active_ffmpeg_processes.pop(process_id, None)


# Start the system resource monitor
async def start_resource_monitor():
    """Start the system resource monitoring task."""
    LOGGER.info("Starting resource monitoring system...")
    await update_system_load()  # Get initial system load
    LOGGER.info(
        f"Initial system load: CPU {system_load['cpu_percent']}%, Memory {system_load['memory_percent']}%"
    )
    asyncio.create_task(monitor_system_resources())
    LOGGER.info("Resource monitoring system started successfully")
