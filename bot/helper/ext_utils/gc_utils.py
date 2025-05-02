import contextlib
import gc
import logging
import os
import sys
import time
import tracemalloc

try:
    import psutil
except ImportError:
    psutil = None

LOGGER = logging.getLogger(__name__)

# Track last garbage collection time to avoid too frequent collections
_last_gc_time = time.time()
_gc_interval = 60  # Default interval in seconds between forced collections

# Flag to enable/disable memory tracking for debugging
_memory_tracking_enabled = False


def force_garbage_collection(threshold_mb=100, log_stats=False, generation=None):
    """
    Force garbage collection if memory usage exceeds threshold or timer expired.

    Args:
        threshold_mb: Memory threshold in MB to trigger collection
        log_stats: Whether to log detailed statistics
        generation: Specific generation to collect (0, 1, 2, or None for all)

    Returns:
        bool: True if garbage collection was performed
    """
    global _last_gc_time

    # Check if enough time has passed since last collection
    current_time = time.time()
    time_since_last_gc = current_time - _last_gc_time

    # Get current memory usage
    try:
        global psutil
        if psutil is None:
            # If psutil is not available, collect based on time only
            if time_since_last_gc > _gc_interval:
                if generation is not None:
                    # Collect specific generation
                    gc.collect(generation)
                else:
                    # Collect all generations
                    gc.collect(0)
                    gc.collect(1)
                    gc.collect(2)
                _last_gc_time = current_time
                return True
            return False

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        # Decide whether to collect based on memory usage or time interval
        should_collect = (memory_mb > threshold_mb) or (
            time_since_last_gc > _gc_interval
        )

        if should_collect:
            # Run collection based on specified generation or full cycle
            if log_stats:
                # First run collection and get stats
                if generation is not None:
                    # Collect specific generation
                    collected = gc.collect(generation)
                    collected_gen0 = collected if generation == 0 else 0
                    collected_gen1 = collected if generation == 1 else 0
                    collected_gen2 = collected if generation == 2 else 0
                else:
                    # Collect all generations
                    collected_gen0 = gc.collect(0)  # Collect youngest generation
                    collected_gen1 = gc.collect(1)  # Collect middle generation
                    collected_gen2 = gc.collect(2)  # Collect oldest generation
                    (collected_gen0 + collected_gen1 + collected_gen2)

                # Get memory after collection
                memory_after = process.memory_info().rss / (1024 * 1024)
                max(0, memory_mb - memory_after)  # Avoid negative values

                # Only log if explicitly requested or if there's a significant memory issue
                # Log unreachable objects if there are any
                unreachable = gc.garbage
                if unreachable:
                    LOGGER.warning(f"Found {len(unreachable)} unreachable objects")
                    # Clear the list to avoid memory leaks
                    gc.garbage.clear()
            # Just collect without stats
            elif generation is not None:
                # Collect specific generation
                gc.collect(generation)
            else:
                # Collect all generations
                gc.collect(0)  # Collect youngest generation
                gc.collect(1)  # Collect middle generation
                gc.collect(2)  # Collect oldest generation

            # Update last collection time
            _last_gc_time = current_time
            return True
    except ImportError:
        # If psutil is not available, collect based on time only
        if time_since_last_gc > _gc_interval:
            if generation is not None:
                # Collect specific generation
                gc.collect(generation)
            else:
                # Collect all generations
                gc.collect(0)
                gc.collect(1)
                gc.collect(2)
            _last_gc_time = current_time
            return True
    except Exception as e:
        LOGGER.error(f"Error during garbage collection: {e}")
        # Try a simple collection even if there was an error
        try:
            if generation is not None:
                gc.collect(generation)
            else:
                gc.collect()
        except Exception as ex:
            LOGGER.error(f"Failed to perform fallback garbage collection: {ex}")

    return False


def start_memory_tracking():
    """Start tracking memory allocations for debugging."""
    global _memory_tracking_enabled

    try:
        tracemalloc.start()
        _memory_tracking_enabled = True
        LOGGER.info("Memory tracking started")
    except Exception as e:
        LOGGER.error(f"Failed to start memory tracking: {e}")


def stop_memory_tracking():
    """Stop tracking memory allocations."""
    global _memory_tracking_enabled

    if _memory_tracking_enabled:
        try:
            tracemalloc.stop()
            _memory_tracking_enabled = False
            LOGGER.info("Memory tracking stopped")
        except Exception as e:
            LOGGER.error(f"Failed to stop memory tracking: {e}")


def get_memory_snapshot():
    """Get current memory snapshot if tracking is enabled."""
    if not _memory_tracking_enabled:
        return None

    try:
        return tracemalloc.take_snapshot()
    except Exception as e:
        LOGGER.error(f"Failed to take memory snapshot: {e}")
        return None


def compare_memory_snapshots(old_snapshot, new_snapshot, limit=10):
    """
    Compare two memory snapshots and return the differences.

    Args:
        old_snapshot: Previous memory snapshot
        new_snapshot: Current memory snapshot
        limit: Number of top differences to return

    Returns:
        List of memory differences
    """
    if not old_snapshot or not new_snapshot:
        return []

    try:
        differences = new_snapshot.compare_to(old_snapshot, "lineno")
        return differences[:limit]
    except Exception as e:
        LOGGER.error(f"Failed to compare memory snapshots: {e}")
        return []


def log_memory_usage():
    """Log current memory usage information."""
    global psutil

    try:
        if psutil is None:
            return None

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        # Calculate memory usage in MB
        rss_mb = memory_info.rss / (1024 * 1024)
        vms_mb = memory_info.vms / (1024 * 1024)

        # Get system memory info
        system_memory = psutil.virtual_memory()
        system_memory_percent = system_memory.percent

        # Only log if memory usage is high
        if system_memory_percent > 85:
            LOGGER.warning(f"High memory usage: System at {system_memory_percent}%")

        return {
            "rss_mb": rss_mb,
            "vms_mb": vms_mb,
            "system_percent": system_memory_percent,
        }
    except Exception as e:
        LOGGER.error(f"Error logging memory usage: {e}")
        return None


def set_gc_parameters(threshold=700, interval=60):
    """
    Configure garbage collection parameters.

    Args:
        threshold: Memory threshold in MB to trigger collection
        interval: Minimum time in seconds between collections
    """
    global _gc_interval

    try:
        # Set Python's GC thresholds
        # These control how many allocations trigger automatic collection
        current_thresholds = gc.get_threshold()

        # Only change if significantly different to avoid unnecessary changes
        if abs(current_thresholds[0] - threshold) > 50:
            gc.set_threshold(threshold, current_thresholds[1], current_thresholds[2])
        # Set our custom interval
        _gc_interval = interval
    except Exception as e:
        LOGGER.error(f"Failed to set garbage collection parameters: {e}")


def optimized_garbage_collection(aggressive=False, log_stats=False):
    """
    Perform an optimized garbage collection with minimal impact on performance.

    Args:
        aggressive: Whether to perform a more aggressive collection
        log_stats: Whether to log detailed statistics

    Returns:
        bool: True if collection was performed successfully
    """
    try:
        global psutil

        # Get memory before collection if we're logging stats
        memory_before = None
        if log_stats and psutil is not None:
            try:
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                memory_before = memory_info.rss / (1024 * 1024)
            except Exception:
                pass

        # First collect only generation 0 (youngest objects)
        # This is usually very fast and frees up most temporary objects
        collected_gen0 = gc.collect(0)

        # If we're in aggressive mode or if we collected many objects in gen0,
        # also collect generation 1
        collected_gen1 = 0
        collected_gen2 = 0
        if aggressive or collected_gen0 > 1000:
            collected_gen1 = gc.collect(1)

            # Only collect generation 2 (oldest, most expensive) if in aggressive mode
            # or if we collected many objects in gen1
            if aggressive or collected_gen1 > 100:
                collected_gen2 = gc.collect(2)

        # Clear any unreachable objects
        unreachable_count = 0
        if gc.garbage:
            unreachable_count = len(gc.garbage)
            gc.garbage.clear()

        # Log statistics if requested
        if log_stats and memory_before is not None:
            try:
                # Get memory after collection
                process = psutil.Process(os.getpid())
                memory_after = process.memory_info().rss / (1024 * 1024)
                max(0, memory_before - memory_after)  # Avoid negative values

                collected_gen0 + collected_gen1 + collected_gen2

                # Only log if significant memory was freed or in debug mode
                # Always log unreachable objects as they indicate potential memory leaks
                if unreachable_count > 0:
                    LOGGER.warning(
                        f"Cleared {unreachable_count} unreachable objects"
                    )
            except Exception:
                pass

        return True
    except Exception as e:
        LOGGER.error(f"Error during optimized garbage collection: {e}")
        return False


def cleanup_large_objects():
    """
    Find and clean up large objects in memory.
    This is a more aggressive approach for when memory usage is critical.
    """
    try:
        # Get memory before collection if psutil is available
        memory_before = None
        if psutil is not None:
            try:
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                memory_before = memory_info.rss / (1024 * 1024)
            except Exception:
                pass

        # Force a full collection first
        gc.collect()

        # Get all objects
        objects = gc.get_objects()

        # Find large objects (>10MB)
        large_objects = []
        for obj in objects:
            try:
                size = sys.getsizeof(obj)
                if size > 10 * 1024 * 1024:  # >10MB
                    large_objects.append((obj, size))
            except Exception:
                # Some objects can't have their size measured
                pass

        # Log information about large objects
        if large_objects:
            for _i, (obj, size) in enumerate(
                sorted(large_objects, key=lambda x: x[1], reverse=True)[:5]
            ):
                # Try to identify what the object is
                try:
                    if hasattr(obj, "__dict__"):
                        list(obj.__dict__.keys())[:5]  # Get first 5 attributes
                    elif hasattr(obj, "__len__"):
                        pass
                except Exception:
                    pass

                # For lists, tuples, and dicts, try to identify contents
                if isinstance(obj, list | tuple) and len(obj) > 0:
                    with contextlib.suppress(Exception):
                        pass
                elif isinstance(obj, dict) and len(obj) > 0:
                    with contextlib.suppress(Exception):
                        next(iter(obj.keys()))

        # Store the count before clearing references
        count = len(large_objects) if large_objects else 0

        # Clear references to help garbage collection
        del objects
        del large_objects

        # Force another collection on all generations
        gc.collect(0)
        gc.collect(1)
        gc.collect(2)

        # Clear any unreachable objects
        unreachable_count = 0
        if gc.garbage:
            unreachable_count = len(gc.garbage)
            gc.garbage.clear()

        # Log memory freed if psutil is available
        if memory_before is not None and psutil is not None:
            try:
                # Get memory after collection
                process = psutil.Process(os.getpid())
                memory_after = process.memory_info().rss / (1024 * 1024)
                max(0, memory_before - memory_after)  # Avoid negative values

                # Only log if significant memory was freed
                if unreachable_count > 0:
                    LOGGER.warning(
                        f"Cleared {unreachable_count} unreachable objects"
                    )
            except Exception:
                pass

        return count
    except Exception as e:
        LOGGER.error(f"Error cleaning up large objects: {e}")
        # Try a simple collection even if there was an error
        with contextlib.suppress(Exception):
            gc.collect()
        return 0


def smart_garbage_collection(aggressive=False, for_split_file=False):
    """
    Perform a smart garbage collection that adapts based on memory usage.
    This function decides whether to use optimized_garbage_collection or
    a more aggressive approach with cleanup_large_objects.

    Args:
        aggressive: Whether to force aggressive collection regardless of memory usage
        for_split_file: Whether this is being called for a split file upload (more aggressive)

    Returns:
        bool: True if collection was performed successfully
    """
    try:
        # Check current memory usage if psutil is available
        memory_percent = 0
        if psutil is not None:
            try:
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
            except Exception:
                pass

        # For split files, always be more aggressive
        if for_split_file:
            aggressive = True

        # Decide which collection method to use
        if (
            aggressive or memory_percent > 80
        ):  # High memory usage or forced aggressive mode
            # First try optimized collection with logging
            optimized_garbage_collection(aggressive=True, log_stats=True)

            # For split files or very high memory usage, do extra cleanup
            if memory_percent > 90 or aggressive:
                cleanup_large_objects()

                # For split files, do an extra round of collection
                if for_split_file:
                    # Clear any unreachable objects
                    if gc.garbage:
                        gc.garbage.clear()

                    # Force collection on all generations again
                    gc.collect(0)
                    gc.collect(1)
                    gc.collect(2)

                    # Try to free more memory by clearing caches
                    import sys

                    try:
                        sys._clear_type_cache()
                        # Clear module caches that might be holding references
                        for module in list(sys.modules.values()):
                            if hasattr(module, "_cache") and isinstance(
                                module._cache, dict
                            ):
                                module._cache.clear()
                    except Exception:
                        pass

            return True
        # Normal memory usage
        # Use optimized collection with logging if memory usage is moderate
        log_stats = memory_percent > 60
        return optimized_garbage_collection(aggressive=False, log_stats=log_stats)
    except Exception as e:
        LOGGER.error(f"Error during smart garbage collection: {e}")
        # Try a simple collection as fallback
        try:
            gc.collect()
            return True
        except Exception:
            return False
