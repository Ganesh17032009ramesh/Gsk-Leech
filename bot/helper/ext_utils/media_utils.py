import contextlib
import gc
import json
import os
import resource
import shutil
from asyncio import create_subprocess_exec, gather, sleep, wait_for
from asyncio.subprocess import PIPE
from os import path as ospath
from pathlib import Path
from re import escape
from re import search as re_search
from time import time

import aiofiles
from aiofiles.os import makedirs, remove
from aiofiles.os import path as aiopath
from aioshutil import rmtree
from PIL import Image
from PyPDF2 import PdfMerger, PdfReader, PdfWriter

from bot import DOWNLOAD_DIR, LOGGER, cpu_no
from bot.core.config_manager import Config

from .bot_utils import cmd_exec, sync_to_async
from .files_utils import get_mime_type, get_path_size, is_archive, is_archive_split
from .status_utils import time_to_seconds

try:
    from bot.helper.ext_utils.gc_utils import smart_garbage_collection
except ImportError:
    smart_garbage_collection = None


def limit_memory_for_pil():
    """Apply memory limits for PIL operations based on config."""
    try:
        # Get memory limit from config
        memory_limit = Config.PIL_MEMORY_LIMIT

        if memory_limit > 0:
            # Convert MB to bytes for resource limit
            memory_limit_bytes = memory_limit * 1024 * 1024

            # Set soft limit (warning) and hard limit (error)
            resource.setrlimit(
                resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes)
            )

        return True
    except Exception as e:
        LOGGER.error(f"Error setting memory limit for PIL: {e}")
        return False


async def get_streams(file):
    """Get stream information from a media file using ffprobe.

    Args:
        file: Path to the media file

    Returns:
        list: List of stream dictionaries, or None if an error occurs
    """
    cmd = [
        "ffprobe",  # Keep as ffprobe, not xtra
        "-hide_banner",
        "-loglevel",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        file,
    ]

    # Execute the command
    stdout, stderr, code = await cmd_exec(cmd)

    if code != 0:
        LOGGER.error(f"Error getting stream info: {stderr}")
        return None

    try:
        return json.loads(stdout)["streams"]
    except KeyError:
        LOGGER.error(
            f"No streams found in the ffprobe output: {stdout}",
        )
        return None


async def create_thumb(msg, _id=""):
    if not _id:
        _id = time()
        path = f"{DOWNLOAD_DIR}thumbnails"
    else:
        path = "thumbnails"
    await makedirs(path, exist_ok=True)
    photo_dir = await msg.download()
    output = ospath.join(path, f"{_id}.jpg")

    # Use PIL to convert and save the image
    try:
        img = await sync_to_async(Image.open, photo_dir)
        img_rgb = await sync_to_async(img.convert, "RGB")
        await sync_to_async(img_rgb.save, output, "JPEG")

        # Close the images to free up memory
        await sync_to_async(img_rgb.close)
        await sync_to_async(img.close)
    except Exception as e:
        LOGGER.error(f"Error processing thumbnail: {e}")
        if await aiopath.exists(output):
            await remove(output)
        raise
    finally:
        # Clean up the downloaded file
        if await aiopath.exists(photo_dir):
            await remove(photo_dir)

    return output


async def get_media_info(path):
    try:
        result = await cmd_exec(
            [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-hide_banner",
                "-loglevel",
                "error",
                "-print_format",
                "json",
                "-show_format",
                path,
            ],
        )
    except Exception as e:
        LOGGER.error(f"Get Media Info: {e}. Mostly File not found! - File: {path}")
        return 0, None, None
    if result[0] and result[2] == 0:
        fields = eval(result[0]).get("format")
        if fields is None:
            LOGGER.error(f"get_media_info: {result}")
            return 0, None, None
        duration = round(float(fields.get("duration", 0)))
        tags = fields.get("tags", {})
        artist = tags.get("artist") or tags.get("ARTIST") or tags.get("Artist")
        title = tags.get("title") or tags.get("TITLE") or tags.get("Title")
        return duration, artist, title
    return 0, None, None


async def get_document_type(path):
    is_video, is_audio, is_image = False, False, False
    if (
        is_archive(path)
        or is_archive_split(path)
        or re_search(r".+(\.|_)(rar|7z|zip|bin)(\.0*\d+)?$", path)
    ):
        return is_video, is_audio, is_image
    mime_type = await get_mime_type(path)
    if mime_type.startswith("image"):
        return False, False, True
    try:
        result = await cmd_exec(
            [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-hide_banner",
                "-loglevel",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                path,
            ],
        )
        if result[1] and mime_type.startswith("video"):
            is_video = True
    except Exception as e:
        LOGGER.error(
            f"Get Document Type: {e}. Mostly File not found! - File: {path}",
        )
        if mime_type.startswith("audio"):
            return False, True, False
        if not mime_type.startswith("video") and not mime_type.endswith(
            "octet-stream",
        ):
            return is_video, is_audio, is_image
        if mime_type.startswith("video"):
            is_video = True
        return is_video, is_audio, is_image
    if result[0] and result[2] == 0:
        fields = eval(result[0]).get("streams")
        if fields is None:
            LOGGER.error(f"get_document_type: {result}")
            return is_video, is_audio, is_image
        is_video = False
        for stream in fields:
            if stream.get("codec_type") == "video":
                is_video = True
            elif stream.get("codec_type") == "audio":
                is_audio = True
    return is_video, is_audio, is_image


async def get_media_type(file_path):
    """Determine if a file is video, audio, or subtitle.

    Args:
        file_path: Path to the file

    Returns:
        str: 'video', 'audio', 'subtitle', 'image', 'document', 'archive', or None if can't determine
    """
    # First try to determine by extension
    file_ext = os.path.splitext(file_path)[1].lower()

    # Video extensions
    if file_ext in [
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".ts",
        ".3gp",
        ".mpg",
        ".mpeg",
        ".hevc",
    ]:
        return "video"
    # Audio extensions
    if file_ext in [
        ".mp3",
        ".m4a",
        ".wav",
        ".flac",
        ".ogg",
        ".opus",
        ".aac",
        ".ac3",
    ]:
        return "audio"
    # Image extensions
    if file_ext in [
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
        ".gif",
        ".svg",
        ".psd",
    ]:
        return "image"
    # Subtitle extensions
    if file_ext in [".srt", ".vtt", ".ass", ".ssa", ".sub"]:
        return "subtitle"
    # Document extensions
    if file_ext in [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".epub"]:
        return "document"
    # Archive extensions
    if file_ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"]:
        return "archive"

    # If extension doesn't match, try to determine by file content
    try:
        # Use ffprobe to get streams
        streams = await get_streams(file_path)
        if streams:
            # Check for video streams
            for stream in streams:
                if stream.get("codec_type") == "video":
                    # Check if it's not just a cover art
                    if not (
                        stream.get("disposition")
                        and stream.get("disposition").get("attached_pic") == 1
                    ):
                        return "video"

            # Check for audio streams
            for stream in streams:
                if stream.get("codec_type") == "audio":
                    return "audio"

            # Check for subtitle streams
            for stream in streams:
                if stream.get("codec_type") == "subtitle":
                    return "subtitle"
    except Exception as e:
        LOGGER.error(f"Error determining media type: {e}")

    # If all else fails, try to determine by mime type
    try:
        mime_type = await get_mime_type(file_path)
        if mime_type:
            if mime_type.startswith("video/"):
                return "video"
            if mime_type.startswith("image/"):
                return "image"
            if mime_type.startswith("audio/"):
                return "audio"
            if mime_type in ["text/plain", "application/x-subrip"]:
                # Check if it's a subtitle file by examining content
                with open(file_path, errors="ignore") as f:
                    content = f.read(1000)  # Read first 1000 chars
                    if "-->" in content and content[0].isdigit():
                        return "subtitle"
            elif mime_type.startswith(("application/pdf", "application/msword")):
                return "document"
            elif mime_type.startswith(("application/zip", "application/x-rar")):
                return "archive"
    except Exception as e:
        LOGGER.warning(f"Error determining mime type for {file_path}: {e}")

    return None


async def take_ss(video_file, ss_nb) -> bool:
    duration = (await get_media_info(video_file))[0]
    if duration != 0:
        dirpath, name = video_file.rsplit("/", 1)
        name, _ = ospath.splitext(name)
        dirpath = f"{dirpath}/{name}_ss"
        await makedirs(dirpath, exist_ok=True)
        interval = duration // (ss_nb + 1)
        cap_time = interval
        cmds = []
        for i in range(ss_nb):
            output = f"{dirpath}/SS.{name}_{i:02}.png"
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{cap_time}",
                "-i",
                video_file,
                "-q:v",
                "1",
                "-frames:v",
                "1",
                "-threads",
                f"{max(1, cpu_no // 2)}",
                output,
            ]
            cap_time += interval
            cmds.append(cmd_exec(cmd))
        try:
            resutls = await wait_for(gather(*cmds), timeout=60)
            if resutls[0][2] != 0:
                LOGGER.error(
                    f"Error while creating sreenshots from video. Path: {video_file}. stderr: {resutls[0][1]}",
                )
                await rmtree(dirpath, ignore_errors=True)
                return False
        except Exception:
            LOGGER.error(
                f"Error while creating sreenshots from video. Path: {video_file}. Error: Timeout some issues with xtra (ffmpeg) with specific arch!",
            )
            await rmtree(dirpath, ignore_errors=True)
            return False
        return dirpath
    LOGGER.error("take_ss: Can't get the duration of video")
    return False


async def get_audio_thumbnail(audio_file):
    output_dir = f"{DOWNLOAD_DIR}thumbnails"
    await makedirs(output_dir, exist_ok=True)
    output = ospath.join(output_dir, f"{time()}.jpg")
    cmd = [
        "xtra",  # Using xtra instead of ffmpeg
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        audio_file,
        "-an",
        "-vcodec",
        "copy",
        "-threads",
        f"{max(1, cpu_no // 2)}",
        output,
    ]
    try:
        _, err, code = await wait_for(cmd_exec(cmd), timeout=60)
        if code != 0 or not await aiopath.exists(output):
            LOGGER.error(
                f"Error while extracting thumbnail from audio. Name: {audio_file} stderr: {err}",
            )
            return None
    except Exception:
        LOGGER.error(
            f"Error while extracting thumbnail from audio. Name: {audio_file}. Error: Timeout some issues with xtra (ffmpeg) with specific arch!",
        )
        return None
    return output


# Output extension mappings for different track types and codecs
TRACK_OUTPUT_EXTENSIONS = {
    "video": {
        "copy": "mkv",
        "h264": "mp4",
        "libx264": "mp4",
        "h265": "mp4",
        "libx265": "mp4",
        "vp9": "webm",
        "libvpx-vp9": "webm",
        "av1": "mp4",
        "libaom-av1": "mp4",
    },
    "audio": {
        "copy": "mka",
        "aac": "m4a",
        "libfdk_aac": "m4a",
        "mp3": "mp3",
        "libmp3lame": "mp3",
        "opus": "opus",
        "libopus": "opus",
        "flac": "flac",
        "libflac": "flac",
    },
    "subtitle": {
        "copy": "srt",
        "srt": "srt",
        "ass": "ass",
        "ssa": "ssa",
        "vtt": "vtt",
        "webvtt": "vtt",
    },
}


def get_output_extension(track_type, codec, input_codec=None):
    """Get the appropriate output file extension based on track type and codec.

    Args:
        track_type: Type of track (video, audio, subtitle)
        codec: Codec to use for the track (can be None)
        input_codec: Original codec of the track (can be None)

    Returns:
        Appropriate file extension for the track type and codec
    """
    # Normalize codec and input_codec to lowercase if they're strings
    if isinstance(codec, str):
        codec = codec.lower()
    if isinstance(input_codec, str):
        input_codec = input_codec.lower()

    # If codec is None or "None", use default extension for the track type
    if codec is None or codec == "none":
        if track_type == "video":
            return "mkv"
        if track_type == "audio":
            return "mka"
        if track_type == "subtitle":
            # For subtitles, if no codec is specified, preserve the original format
            if input_codec:
                # Handle common subtitle formats
                if input_codec in ["ass", "ssa"]:
                    return "ass"
                if input_codec in ["srt", "subrip"]:
                    return "srt"
                if input_codec in ["vtt", "webvtt"]:
                    return "vtt"
                if input_codec in ["sub", "microdvd"]:
                    return "sub"
                if input_codec in ["idx", "vobsub"]:
                    return "idx"
            # Default to srt if input_codec is unknown or not provided
            return "srt"
        return "bin"  # Generic binary extension

    # If codec is specified, check if it's in the extensions dictionary
    if (
        track_type in TRACK_OUTPUT_EXTENSIONS
        and codec in TRACK_OUTPUT_EXTENSIONS[track_type]
    ):
        return TRACK_OUTPUT_EXTENSIONS[track_type][codec]

    # Special case for subtitle codecs not in the dictionary
    if track_type == "subtitle":
        if codec in ["srt", "subrip"]:
            return "srt"
        if codec in ["ass", "ssa"]:
            return "ass"
        if codec in ["vtt", "webvtt"]:
            return "vtt"
        if codec in ["sub", "microdvd"]:
            return "sub"
        if codec in ["idx", "vobsub"]:
            return "idx"

    # Default extensions if codec not found in the dictionary
    if track_type == "video":
        return "mkv"
    if track_type == "audio":
        return "mka"
    if track_type == "subtitle":
        return "srt"
    return "bin"  # Generic binary extension


async def get_track_info(file_path: str) -> dict[str, list[dict]]:
    """Get information about all tracks in the file using ffprobe.

    Args:
        file_path: Path to the media file

    Returns:
        Dictionary with track types as keys and lists of track info as values
    """
    tracks = {
        "video": [],
        "audio": [],
        "subtitle": [],
        "attachment": [],
    }

    try:
        # Get streams using the existing get_streams function
        streams = await get_streams(file_path)

        if not streams:
            LOGGER.error(f"No streams found in {file_path}")
            return tracks

        # Log all streams for debugging
        LOGGER.debug(f"Found {len(streams)} streams in {file_path}")
        for i, stream in enumerate(streams):
            codec_type = stream.get("codec_type", "unknown")
            codec_name = stream.get("codec_name", "unknown")
            LOGGER.debug(f"Stream {i}: type={codec_type}, codec={codec_name}")

        for i, stream in enumerate(streams):
            codec_type = stream.get("codec_type", "unknown")
            codec_name = stream.get("codec_name", "unknown")

            if codec_type == "video":
                # Skip attached pictures (cover art) for video tracks
                if stream.get("disposition", {}).get("attached_pic", 0) == 1:
                    LOGGER.debug(
                        f"Skipping stream {i} as it appears to be cover art"
                    )
                    continue

                tracks["video"].append(
                    {
                        "index": i,
                        "codec": codec_name,
                        "width": stream.get("width", 0),
                        "height": stream.get("height", 0),
                        "fps": eval(stream.get("r_frame_rate", "0/1")),
                        "language": stream.get("tags", {}).get("language", "und"),
                        "title": stream.get("tags", {}).get(
                            "title", f"Video Track {i}"
                        ),
                        "disposition": stream.get("disposition", {}),
                    }
                )
                LOGGER.debug(f"Added video track {i}: {codec_name}")
            elif codec_type == "audio":
                tracks["audio"].append(
                    {
                        "index": i,
                        "codec": codec_name,
                        "channels": stream.get("channels", 0),
                        "sample_rate": stream.get("sample_rate", 0),
                        "language": stream.get("tags", {}).get("language", "und"),
                        "title": stream.get("tags", {}).get(
                            "title", f"Audio Track {i}"
                        ),
                    }
                )
                LOGGER.debug(f"Added audio track {i}: {codec_name}")
            elif codec_type == "subtitle":
                tracks["subtitle"].append(
                    {
                        "index": i,
                        "codec": codec_name,
                        "language": stream.get("tags", {}).get("language", "und"),
                        "title": stream.get("tags", {}).get(
                            "title", f"Subtitle Track {i}"
                        ),
                    }
                )
                LOGGER.debug(
                    f"Added subtitle track {i}: {codec_name}, language: {stream.get('tags', {}).get('language', 'und')}"
                )
            elif codec_type == "attachment":
                tracks["attachment"].append(
                    {
                        "index": i,
                        "filename": stream.get("tags", {}).get(
                            "filename", f"Attachment {i}"
                        ),
                        "mimetype": stream.get("tags", {}).get(
                            "mimetype", "application/octet-stream"
                        ),
                    }
                )
                LOGGER.debug(
                    f"Added attachment {i}: {stream.get('tags', {}).get('filename', f'Attachment {i}')}"
                )
            else:
                LOGGER.debug(f"Skipping unknown stream type {i}: {codec_type}")

        # Log summary of found tracks
        LOGGER.debug(
            f"Found {len(tracks['video'])} video tracks, {len(tracks['audio'])} audio tracks, "
            f"{len(tracks['subtitle'])} subtitle tracks, and {len(tracks['attachment'])} attachments"
        )
    except Exception as e:
        LOGGER.error(f"Error getting track info: {e}")
        # Log the full exception traceback for debugging
        import traceback

        LOGGER.debug(f"Traceback: {traceback.format_exc()}")

    return tracks


async def extract_track(
    file_path: str,
    output_dir: str,
    track_type: str,
    track_indices: int | list[int] | None = None,
    codec: str | None = None,
    maintain_quality: bool = True,
) -> list[str]:
    """Extract specific track(s) from a media file.

    Args:
        file_path: Path to the input file
        output_dir: Directory to save extracted tracks
        track_type: Type of track to extract ('video', 'audio', 'subtitle', 'attachment')
        track_indices: Specific track index or list of indices to extract (None = all tracks of the type)
        codec: Codec to use for extraction
        maintain_quality: Whether to maintain high quality during extraction

    Returns:
        List of paths to extracted files
    """
    try:
        # Create output directory if it doesn't exist
        await makedirs(output_dir, exist_ok=True)

        # Get stream information directly using ffprobe
        streams = await get_streams(file_path)
        if not streams:
            LOGGER.error(f"No streams found in {file_path}")
            return []

        # Get track information
        tracks = await get_track_info(file_path)

        # Skip verbose track logging

        if not tracks[track_type]:
            LOGGER.warning(f"No {track_type} tracks found in {file_path}")
            return []

        # Determine which tracks to extract
        tracks_to_extract = []

        # Check if we should extract all tracks
        extract_all = False

        # Convert single index to list for uniform processing
        indices_list = []
        if track_indices is not None:
            if isinstance(track_indices, list):
                # Check if the list contains the special "all" value
                if any(
                    isinstance(idx, str) and str(idx).lower() == "all"
                    for idx in track_indices
                ):
                    extract_all = True
                    LOGGER.debug(
                        f"Extract all {track_type} tracks: 'all' value found in list"
                    )
                else:
                    # Filter valid indices and convert strings to integers
                    for idx in track_indices:
                        if isinstance(idx, int):
                            indices_list.append(idx)
                        elif isinstance(idx, str):
                            if idx.strip().lower() == "all":
                                extract_all = True
                                LOGGER.debug(
                                    f"Extract all {track_type} tracks: 'all' value found in list"
                                )
                                break
                            if idx.strip().isdigit():
                                indices_list.append(int(idx.strip()))
                            else:
                                LOGGER.warning(
                                    f"Invalid {track_type} track index: {idx}"
                                )
            elif isinstance(track_indices, str):
                # Check if it's the special "all" value
                if track_indices.strip().lower() == "all":
                    extract_all = True
                    LOGGER.debug(
                        f"Extract all {track_type} tracks: 'all' value specified"
                    )
                # Check if it's a comma-separated list
                elif "," in track_indices:
                    for idx in track_indices.split(","):
                        if idx.strip().lower() == "all":
                            extract_all = True
                            LOGGER.debug(
                                f"Extract all {track_type} tracks: 'all' value found in comma-separated list"
                            )
                            break
                        if idx.strip().isdigit():
                            indices_list.append(int(idx.strip()))
                        else:
                            LOGGER.warning(
                                f"Invalid {track_type} track index in list: {idx}"
                            )
                # Check if it's a single digit
                elif track_indices.strip().isdigit():
                    indices_list.append(int(track_indices.strip()))
                else:
                    LOGGER.warning(
                        f"Invalid {track_type} track index: {track_indices}"
                    )
            elif isinstance(track_indices, int):
                indices_list.append(track_indices)

        # Log the indices we're looking for
        if indices_list:
            LOGGER.debug(
                f"Looking for {track_type} tracks with indices: {indices_list}"
            )
        elif extract_all:
            LOGGER.debug(f"Extracting all {track_type} tracks")
        else:
            LOGGER.debug(
                f"No specific {track_type} indices provided, will extract all tracks"
            )

        if indices_list and not extract_all:
            # Extract specific tracks by indices
            for track in tracks[track_type]:
                if track["index"] in indices_list:
                    tracks_to_extract.append(track)
                    LOGGER.debug(
                        f"Found {track_type} track with index {track['index']}"
                    )

            # Log if no matching tracks were found
            if not tracks_to_extract:
                LOGGER.warning(
                    f"No {track_type} tracks with indices {indices_list} found"
                )
        else:
            # Extract all tracks of the specified type
            LOGGER.debug(f"Extracting all {track_type} tracks")
            tracks_to_extract = tracks[track_type]

        if not tracks_to_extract:
            LOGGER.warning(
                f"No matching {track_type} tracks found with indices {track_indices}"
            )
            return []

        # Extract each track
        extracted_files = []
        for track in tracks_to_extract:
            # Generate output filename
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            language = track.get("language", "und")

            if track_type == "attachment":
                # For attachments, use the original filename if available
                output_file = os.path.join(
                    output_dir,
                    track.get(
                        "filename", f"{file_name}.attachment.{track['index']}"
                    ),
                )
            else:
                # For media tracks, use a descriptive name with track type and index
                input_codec = track.get("codec", "")
                extension = get_output_extension(track_type, codec, input_codec)
                output_file = os.path.join(
                    output_dir,
                    f"{file_name}.{track_type}.{language}.{track['index']}.{extension}",
                )

            # Build FFmpeg command
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                file_path,
            ]  # Using xtra instead of ffmpeg

            if track_type == "attachment":
                # For attachments, use the attachment muxer
                cmd.extend(["-dump_attachment", str(track["index"]), output_file])
            else:
                # For media tracks, map the specific stream
                cmd.extend(["-map", f"0:{track['index']}"])

                # Set codec if specified and not None
                if codec is not None and codec not in {"None", "none"}:
                    if track_type == "video":
                        cmd.extend(["-c:v", codec])
                        if codec != "copy" and maintain_quality:
                            if codec in ["h264", "libx264"]:
                                cmd.extend(
                                    ["-crf", "18", "-preset", "medium"]
                                )  # Changed from slow to medium for better performance
                            elif codec in ["h265", "libx265"]:
                                cmd.extend(
                                    ["-crf", "22", "-preset", "medium"]
                                )  # Changed from slow to medium for better performance
                            elif codec in ["vp9", "libvpx-vp9"]:
                                cmd.extend(["-crf", "30", "-b:v", "0"])
                    elif track_type == "audio":
                        cmd.extend(["-c:a", codec])
                        if codec != "copy" and maintain_quality:
                            if codec in ["aac", "libfdk_aac"] or codec == "mp3":
                                cmd.extend(["-b:a", "320k"])
                            elif codec in ["opus", "libopus"]:
                                cmd.extend(["-b:a", "192k"])
                            elif codec in ["flac", "libflac"]:
                                cmd.extend(
                                    ["-compression_level", "5"]
                                )  # Changed from 8 to 5 for better performance
                    elif track_type == "subtitle":
                        cmd.extend(["-c:s", codec])
                        # Add special handling for ASS to SRT conversion if needed
                        input_codec = track.get("codec", "").lower()
                        if codec == "srt" and input_codec in ["ass", "ssa"]:
                            # Add extra parameters to help with ASS to SRT conversion
                            cmd.extend(["-scodec", "srt"])
                # If no codec is specified, use copy for subtitles
                elif track_type == "subtitle":
                    cmd.extend(["-c:s", "copy"])

                # Add thread count for better performance
                cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                # Add output file
                cmd.append(output_file)

            # Run FFmpeg command
            LOGGER.info(
                f"Extracting {track_type} track {track['index']} from {file_path}"
            )
            LOGGER.debug(f"FFmpeg command: {' '.join(cmd)}")

            try:
                stdout, stderr, code = await cmd_exec(cmd)
                if (
                    code == 0
                    and await aiopath.exists(output_file)
                    and (await aiopath.getsize(output_file)) > 0
                ):
                    extracted_files.append(output_file)
                    LOGGER.info(f"Successfully extracted to {output_file}")
                else:
                    LOGGER.error(
                        f"Failed to extract {track_type} track {track['index']}: {stderr}"
                    )

                    # Try alternative approach for subtitles if the first attempt failed
                    if track_type == "subtitle" and codec != "srt":
                        LOGGER.info(
                            f"Trying alternative approach with srt codec for track {track['index']}"
                        )
                        alt_output_file = os.path.join(
                            output_dir,
                            f"{file_name}.{track_type}.{language}.{track['index']}.srt",
                        )

                        alt_cmd = [
                            "xtra",
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-i",
                            file_path,  # Using xtra instead of ffmpeg
                            "-map",
                            f"0:{track['index']}",
                            "-c:s",
                            "srt",
                            alt_output_file,
                        ]

                        alt_stdout, alt_stderr, alt_code = await cmd_exec(alt_cmd)
                        if (
                            alt_code == 0
                            and await aiopath.exists(alt_output_file)
                            and (await aiopath.getsize(alt_output_file)) > 0
                        ):
                            extracted_files.append(alt_output_file)
                            LOGGER.info(
                                f"Successfully extracted to {alt_output_file} using alternative approach"
                            )
                        else:
                            LOGGER.error(
                                f"Alternative approach also failed: {alt_stderr}"
                            )
            except Exception as e:
                LOGGER.error(f"Error running FFmpeg: {e}")

        return extracted_files
    except Exception as e:
        LOGGER.error(f"Error extracting {track_type} track: {e}")
        return []


async def extract_all_tracks(
    file_path: str,
    output_dir: str,
    extract_video: bool = True,
    extract_audio: bool = True,
    extract_subtitle: bool = True,
    extract_attachment: bool = True,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    subtitle_codec: str | None = None,
    video_indices: int | list[int] | None = None,
    audio_indices: int | list[int] | None = None,
    subtitle_indices: int | list[int] | None = None,
    attachment_indices: int | list[int] | None = None,
    # Keep single index parameters for backward compatibility
    video_index: int | None = None,
    audio_index: int | None = None,
    subtitle_index: int | None = None,
    attachment_index: int | None = None,
    maintain_quality: bool = True,
) -> list[str]:
    """Extract all specified tracks from a media file.

    Args:
        file_path: Path to the input file
        output_dir: Directory to save extracted tracks
        extract_video: Whether to extract video tracks
        extract_audio: Whether to extract audio tracks
        extract_subtitle: Whether to extract subtitle tracks
        extract_attachment: Whether to extract attachments
        video_codec: Codec to use for video extraction
        audio_codec: Codec to use for audio extraction
        subtitle_codec: Codec to use for subtitle extraction
        video_indices: List of video track indices to extract (None = all)
        audio_indices: List of audio track indices to extract (None = all)
        subtitle_indices: List of subtitle track indices to extract (None = all)
        attachment_indices: List of attachment indices to extract (None = all)
        video_index: Specific video track index to extract (deprecated, use video_indices)
        audio_index: Specific audio track index to extract (deprecated, use audio_indices)
        subtitle_index: Specific subtitle track index to extract (deprecated, use subtitle_indices)
        attachment_index: Specific attachment index to extract (deprecated, use attachment_indices)
        maintain_quality: Whether to maintain high quality during extraction

    Returns:
        List of paths to extracted files
    """
    extracted_files = []

    # Handle backward compatibility - convert single indices to lists if provided
    if video_indices is None and video_index is not None:
        # Check if video_index is a string with comma-separated values
        if isinstance(video_index, str) and "," in video_index:
            video_indices = [
                int(idx.strip())
                for idx in video_index.split(",")
                if idx.strip().isdigit()
            ]
        else:
            video_indices = [video_index]

    if audio_indices is None and audio_index is not None:
        # Check if audio_index is a string with comma-separated values
        if isinstance(audio_index, str) and "," in audio_index:
            audio_indices = [
                int(idx.strip())
                for idx in audio_index.split(",")
                if idx.strip().isdigit()
            ]
        else:
            audio_indices = [audio_index]

    if subtitle_indices is None and subtitle_index is not None:
        # Check if subtitle_index is a string with comma-separated values
        if isinstance(subtitle_index, str) and "," in subtitle_index:
            subtitle_indices = [
                int(idx.strip())
                for idx in subtitle_index.split(",")
                if idx.strip().isdigit()
            ]
        else:
            subtitle_indices = [subtitle_index]

    if attachment_indices is None and attachment_index is not None:
        # Check if attachment_index is a string with comma-separated values
        if isinstance(attachment_index, str) and "," in attachment_index:
            attachment_indices = [
                int(idx.strip())
                for idx in attachment_index.split(",")
                if idx.strip().isdigit()
            ]
        else:
            attachment_indices = [attachment_index]

    if extract_video:
        video_files = await extract_track(
            file_path,
            output_dir,
            "video",
            video_indices,
            video_codec,
            maintain_quality,
        )
        extracted_files.extend(video_files)

    if extract_audio:
        audio_files = await extract_track(
            file_path,
            output_dir,
            "audio",
            audio_indices,
            audio_codec,
            maintain_quality,
        )
        extracted_files.extend(audio_files)

    if extract_subtitle:
        subtitle_files = await extract_track(
            file_path,
            output_dir,
            "subtitle",
            subtitle_indices,
            subtitle_codec,
            maintain_quality,
        )
        extracted_files.extend(subtitle_files)

    if extract_attachment:
        attachment_files = await extract_track(
            file_path,
            output_dir,
            "attachment",
            attachment_indices,
            "copy",  # Codec is ignored for attachments
            maintain_quality,
        )
        extracted_files.extend(attachment_files)

    return extracted_files


async def proceed_extract(
    file_path: str,
    output_dir: str,
    extract_video: bool = True,
    extract_audio: bool = True,
    extract_subtitle: bool = True,
    extract_attachment: bool = True,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    subtitle_codec: str | None = None,
    video_index: int | None = None,
    audio_index: int | None = None,
    subtitle_index: int | None = None,
    attachment_index: int | None = None,
    maintain_quality: bool = True,
    ffmpeg_path: str = "xtra",  # Using xtra instead of ffmpeg
    delete_original: bool = False,
    # Parameters for multiple indices
    video_indices: list[int] | None = None,
    audio_indices: list[int] | None = None,
    subtitle_indices: list[int] | None = None,
    attachment_indices: list[int] | None = None,
    # Format settings
    video_format: str | None = None,
    audio_format: str | None = None,
    subtitle_format: str | None = None,
    attachment_format: str | None = None,
    # Additional video settings
    video_quality: str | None = None,
    video_preset: str | None = None,
    video_bitrate: str | None = None,
    video_resolution: str | None = None,
    video_fps: str | None = None,
    # Additional audio settings
    audio_bitrate: str | None = None,
    audio_channels: str | None = None,
    audio_sampling: str | None = None,
    audio_volume: str | None = None,
    # Additional subtitle settings
    subtitle_language: str | None = None,
    subtitle_encoding: str | None = None,
    subtitle_font: str | None = None,
    subtitle_font_size: str | None = None,
    # Attachment settings
    attachment_filter: str | None = None,
) -> list[str]:
    """Process extraction of tracks from a media file using FFmpeg asynchronously.

    Args:
        file_path: Path to the input file
        output_dir: Directory to save extracted tracks
        extract_video: Whether to extract video tracks
        extract_audio: Whether to extract audio tracks
        extract_subtitle: Whether to extract subtitle tracks
        extract_attachment: Whether to extract attachments
        video_codec: Codec to use for video extraction
        audio_codec: Codec to use for audio extraction
        subtitle_codec: Codec to use for subtitle extraction
        video_index: Specific video track index to extract (deprecated, use video_indices)
        audio_index: Specific audio track index to extract (deprecated, use audio_indices)
        subtitle_index: Specific subtitle track index to extract (deprecated, use subtitle_indices)
        attachment_index: Specific attachment index to extract (deprecated, use attachment_indices)
        maintain_quality: Whether to maintain high quality during extraction
        ffmpeg_path: Path to the FFmpeg executable
        delete_original: Whether to delete the original file after extraction
        video_indices: List of video track indices to extract (None = all)
        audio_indices: List of audio track indices to extract (None = all)
        subtitle_indices: List of subtitle track indices to extract (None = all)
        attachment_indices: List of attachment indices to extract (None = all)
        video_format: Output format for video extraction (e.g., mp4, mkv)
        audio_format: Output format for audio extraction (e.g., mp3, aac)
        subtitle_format: Output format for subtitle extraction (e.g., srt, ass)
        attachment_format: Output format for attachment extraction
        video_quality: Quality setting for video extraction (e.g., crf value)
        video_preset: Preset for video encoding (e.g., medium, slow)
        video_bitrate: Bitrate for video encoding (e.g., 5M)
        video_resolution: Resolution for video extraction (e.g., 1920x1080)
        video_fps: Frame rate for video extraction (e.g., 30)
        audio_bitrate: Bitrate for audio encoding (e.g., 320k)
        audio_channels: Number of audio channels (e.g., 2)
        audio_sampling: Sampling rate for audio (e.g., 48000)
        audio_volume: Volume adjustment for audio (e.g., 1.5)
        subtitle_language: Language code for subtitle extraction (e.g., eng)
        subtitle_encoding: Character encoding for subtitles (e.g., UTF-8)
        subtitle_font: Font for subtitles (for formats that support it)
        subtitle_font_size: Font size for subtitles
        attachment_filter: Filter for attachment extraction (e.g., *.ttf)

    Returns:
        List of paths to extracted files
    """
    import asyncio
    import os
    from re import IGNORECASE
    from re import search as re_search

    # Check if file exists
    if not os.path.exists(file_path):
        LOGGER.error(f"File not found for extraction: {file_path}")
        return []

    # Check if the file is a split file
    file_name = os.path.basename(file_path)
    if re_search(r"\.part\d+\.(mkv|mp4|avi|mov|ts|webm)$", file_name, IGNORECASE):
        LOGGER.warning(f"Skipping extraction for split file: {file_path}")
        LOGGER.warning(
            "Extract feature does not support split files. Please join the files first."
        )
        return []

    # Check if file is a valid media file
    try:
        media_type = await get_media_type(file_path)
        if not media_type:
            LOGGER.error(
                f"Unable to determine media type for extraction: {file_path}"
            )
            return []

        LOGGER.debug(f"Detected media type for extraction: {media_type}")

        # Check if the requested extraction is compatible with the media type
        if extract_video and media_type not in ["video"]:
            LOGGER.debug(
                f"Video extraction requested but file is not a video: {file_path} (type: {media_type})"
            )
            extract_video = False

        if extract_audio and media_type not in ["video", "audio"]:
            LOGGER.debug(
                f"Audio extraction requested but file has no audio: {file_path} (type: {media_type})"
            )
            extract_audio = False

        if extract_subtitle and media_type not in ["video", "subtitle"]:
            LOGGER.debug(
                f"Subtitle extraction requested but file has no subtitles: {file_path} (type: {media_type})"
            )
            extract_subtitle = False

        if extract_attachment and media_type not in ["video"]:
            LOGGER.debug(
                f"Attachment extraction requested but file likely has no attachments: {file_path} (type: {media_type})"
            )
            extract_attachment = False

        # Check if any extraction type is still enabled
        if not any(
            [extract_video, extract_audio, extract_subtitle, extract_attachment]
        ):
            LOGGER.error(
                f"No compatible extraction types for this file: {file_path} (type: {media_type})"
            )
            return []
    except Exception as e:
        LOGGER.error(f"Error determining media type for extraction: {e}")
        return []

    # Create output directory if it doesn't exist
    await makedirs(output_dir, exist_ok=True)

    # Get track information
    tracks = await get_track_info(file_path)

    # Check if we have any tracks to extract
    if not any(tracks.values()):
        LOGGER.debug(f"No extractable tracks found in {file_path}")
        return []

    # Prepare extraction commands
    extracted_files = []

    # Process string indices to integers
    # Handle video_index
    if isinstance(video_index, str) and "," in video_index:
        try:
            video_indices = [
                int(idx.strip())
                for idx in video_index.split(",")
                if idx.strip().isdigit()
            ]
            LOGGER.debug(
                f"Converted video_index string '{video_index}' to indices: {video_indices}"
            )
        except Exception as e:
            LOGGER.error(f"Error converting video_index string to indices: {e}")

    # Handle audio_index
    if isinstance(audio_index, str) and "," in audio_index:
        try:
            audio_indices = [
                int(idx.strip())
                for idx in audio_index.split(",")
                if idx.strip().isdigit()
            ]
            LOGGER.debug(
                f"Converted audio_index string '{audio_index}' to indices: {audio_indices}"
            )
        except Exception as e:
            LOGGER.error(f"Error converting audio_index string to indices: {e}")

    # Handle subtitle_index
    if isinstance(subtitle_index, str) and "," in subtitle_index:
        try:
            subtitle_indices = [
                int(idx.strip())
                for idx in subtitle_index.split(",")
                if idx.strip().isdigit()
            ]
            LOGGER.debug(
                f"Converted subtitle_index string '{subtitle_index}' to indices: {subtitle_indices}"
            )
        except Exception as e:
            LOGGER.error(f"Error converting subtitle_index string to indices: {e}")

    # Handle attachment_index
    if isinstance(attachment_index, str) and "," in attachment_index:
        try:
            attachment_indices = [
                int(idx.strip())
                for idx in attachment_index.split(",")
                if idx.strip().isdigit()
            ]
            LOGGER.debug(
                f"Converted attachment_index string '{attachment_index}' to indices: {attachment_indices}"
            )
        except Exception as e:
            LOGGER.error(f"Error converting attachment_index string to indices: {e}")

    # Handle attachment extraction separately
    if extract_attachment and tracks["attachment"]:
        # Convert attachment_indices to a list if it's None but attachment_index is provided
        if attachment_indices is None and attachment_index is not None:
            try:
                # Check if attachment_index is a string with comma-separated values
                if isinstance(attachment_index, str) and "," in attachment_index:
                    attachment_indices = [
                        int(idx.strip())
                        for idx in attachment_index.split(",")
                        if idx.strip().isdigit()
                    ]
                    LOGGER.debug(
                        f"Converted attachment_index string '{attachment_index}' to indices: {attachment_indices}"
                    )
                else:
                    attachment_indices = (
                        [int(attachment_index)]
                        if isinstance(attachment_index, int | str)
                        and str(attachment_index).isdigit()
                        else None
                    )
            except Exception as e:
                LOGGER.error(f"Error converting attachment_index to integer: {e}")

        # Check if attachment_indices contains the special value "all"
        extract_all_attachments = False

        # If attachment_indices is None, extract all attachments
        if attachment_indices is None:
            extract_all_attachments = True
        # Check for "all" in various formats
        elif isinstance(attachment_indices, list):
            # If it's an empty list, extract all
            if not attachment_indices:
                extract_all_attachments = True
            else:
                # Check for "all" in the list
                for idx in attachment_indices:
                    if isinstance(idx, str) and idx.lower() == "all":
                        extract_all_attachments = True
                        break
        # Check if it's a string equal to "all"
        elif (
            isinstance(attachment_indices, str)
            and attachment_indices.lower() == "all"
        ):
            extract_all_attachments = True

        # Also check attachment_index for "all"
        if (
            not extract_all_attachments
            and attachment_index is not None
            and (
                isinstance(attachment_index, str)
                and attachment_index.lower() == "all"
            )
        ):
            extract_all_attachments = True

        if attachment_indices and not extract_all_attachments:
            # Extract specific attachments by indices
            LOGGER.info(
                f"Extracting only attachment files with indices: {attachment_indices}"
            )
            found_tracks = []
            for track in tracks["attachment"]:
                if track["index"] in attachment_indices:
                    found_tracks.append(track["index"])
                    filename = track.get("filename", f"attachment_{track['index']}")
                    output_path = os.path.join(output_dir, filename)

                    # Try to extract the attachment using multiple methods
                    LOGGER.debug(
                        f"Extracting attachment {track['index']} from {file_path}"
                    )

                    # Get attachment filename from track info
                    attachment_filename = track.get(
                        "filename", f"attachment_{track['index']}"
                    )

                    # Create a more descriptive output path if possible
                    if attachment_filename:
                        # Ensure the filename is safe for the filesystem
                        safe_filename = "".join(
                            c
                            for c in attachment_filename
                            if c.isalnum() or c in "._- "
                        )
                        output_path = os.path.join(output_dir, safe_filename)

                        # If the filename already exists, add the index to make it unique
                        if await aiopath.exists(output_path):
                            base_name, ext = os.path.splitext(safe_filename)
                            output_path = os.path.join(
                                output_dir, f"{base_name}_{track['index']}{ext}"
                            )

                    # Create a temporary directory for extraction attempts
                    temp_dir = os.path.join(output_dir, "temp_attachments")
                    await makedirs(temp_dir, exist_ok=True)

                    # Method 1: Use -dump_attachment option (works in some FFmpeg versions)
                    LOGGER.debug(
                        f"Trying extraction method 1 for attachment {track['index']}"
                    )
                    cmd = [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-dump_attachment",
                        str(track["index"]),
                        "-i",
                        file_path,
                        output_path,
                    ]

                    extraction_success = False

                    try:
                        proc = await create_subprocess_exec(
                            *cmd, stdout=PIPE, stderr=PIPE
                        )

                        _, stderr = await proc.communicate()

                        if (
                            proc.returncode == 0
                            and await aiopath.exists(output_path)
                            and await get_path_size(output_path) > 0
                        ):
                            extracted_files.append(output_path)
                            LOGGER.info(
                                f"Successfully extracted attachment to {output_path} using method 1"
                            )
                            extraction_success = True
                        else:
                            stderr_text = (
                                stderr.decode() if stderr else "Unknown error"
                            )
                            LOGGER.debug(f"Method 1 failed: {stderr_text}")
                    except Exception as e:
                        LOGGER.debug(f"Error in method 1: {e}")

                    # Method 2: Try using -map option with data format
                    if not extraction_success:
                        LOGGER.debug(
                            f"Trying extraction method 2 for attachment {track['index']}"
                        )
                        temp_file = os.path.join(
                            temp_dir, f"attachment_{track['index']}.bin"
                        )

                        alt_cmd = [
                            ffmpeg_path,
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-i",
                            file_path,
                            "-map",
                            f"0:{track['index']}",
                            "-c",
                            "copy",
                            "-f",
                            "data",
                            temp_file,
                        ]

                        try:
                            alt_proc = await create_subprocess_exec(
                                *alt_cmd, stdout=PIPE, stderr=PIPE
                            )

                            _, alt_stderr = await alt_proc.communicate()

                            if (
                                alt_proc.returncode == 0
                                and await aiopath.exists(temp_file)
                                and await get_path_size(temp_file) > 0
                            ):
                                # Copy the temporary file to the output path
                                await aiofiles.os.rename(temp_file, output_path)
                                extracted_files.append(output_path)
                                LOGGER.info(
                                    f"Successfully extracted attachment to {output_path} using method 2"
                                )
                                extraction_success = True
                            else:
                                alt_stderr_text = (
                                    alt_stderr.decode()
                                    if alt_stderr
                                    else "Unknown error"
                                )
                                LOGGER.debug(f"Method 2 failed: {alt_stderr_text}")
                        except Exception as alt_e:
                            LOGGER.debug(f"Error in method 2: {alt_e}")

                    # Method 3: Try using -c:t copy for attachments
                    if not extraction_success:
                        LOGGER.debug(
                            f"Trying extraction method 3 for attachment {track['index']}"
                        )
                        temp_file = os.path.join(
                            temp_dir, f"attachment_{track['index']}_method3.bin"
                        )

                        alt_cmd = [
                            ffmpeg_path,
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-i",
                            file_path,
                            "-map",
                            f"0:{track['index']}",
                            "-c:t",
                            "copy",
                            temp_file,
                        ]

                        try:
                            alt_proc = await create_subprocess_exec(
                                *alt_cmd, stdout=PIPE, stderr=PIPE
                            )

                            _, alt_stderr = await alt_proc.communicate()

                            if (
                                alt_proc.returncode == 0
                                and await aiopath.exists(temp_file)
                                and await get_path_size(temp_file) > 0
                            ):
                                # Copy the temporary file to the output path
                                await aiofiles.os.rename(temp_file, output_path)
                                extracted_files.append(output_path)
                                LOGGER.info(
                                    f"Successfully extracted attachment to {output_path} using method 3"
                                )
                                extraction_success = True
                            else:
                                alt_stderr_text = (
                                    alt_stderr.decode()
                                    if alt_stderr
                                    else "Unknown error"
                                )
                                LOGGER.debug(f"Method 3 failed: {alt_stderr_text}")
                        except Exception as alt_e:
                            LOGGER.debug(f"Error in method 3: {alt_e}")

                    # If all methods failed, create a placeholder file
                    if not extraction_success:
                        LOGGER.warning(
                            f"All extraction methods failed for attachment {track['index']}"
                        )
                        try:
                            # Create an empty file with a note about the failure
                            async with aiofiles.open(output_path, "w") as f:
                                await f.write(
                                    f"Failed to extract attachment {track['index']} - {track.get('filename', '')}"
                                )
                            LOGGER.debug(
                                f"Created placeholder file for failed attachment extraction: {output_path}"
                            )
                        except Exception as write_e:
                            LOGGER.error(
                                f"Error creating placeholder file: {write_e}"
                            )

            # Check if any tracks were found
            if not found_tracks:
                LOGGER.warning(
                    f"No attachments with indices {attachment_indices} found in {file_path}"
                )
        elif extract_all_attachments:
            # Extract all attachments
            LOGGER.info(f"Extracting all attachment files from {file_path}")
            for track in tracks["attachment"]:
                filename = track.get("filename", f"attachment_{track['index']}")
                output_path = os.path.join(output_dir, filename)

                # Try to extract the attachment using multiple methods
                LOGGER.debug(
                    f"Extracting attachment {track['index']} from {file_path}"
                )

                # Get attachment filename from track info
                attachment_filename = track.get(
                    "filename", f"attachment_{track['index']}"
                )

                # Create a more descriptive output path if possible
                if attachment_filename:
                    # Ensure the filename is safe for the filesystem
                    safe_filename = "".join(
                        c for c in attachment_filename if c.isalnum() or c in "._- "
                    )
                    output_path = os.path.join(output_dir, safe_filename)

                    # If the filename already exists, add the index to make it unique
                    if await aiopath.exists(output_path):
                        base_name, ext = os.path.splitext(safe_filename)
                        output_path = os.path.join(
                            output_dir, f"{base_name}_{track['index']}{ext}"
                        )

                # Create a temporary directory for extraction attempts
                temp_dir = os.path.join(output_dir, "temp_attachments")
                await makedirs(temp_dir, exist_ok=True)

                # Method 1: Use -dump_attachment option (works in some FFmpeg versions)
                LOGGER.debug(
                    f"Trying extraction method 1 for attachment {track['index']}"
                )
                cmd = [
                    ffmpeg_path,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-dump_attachment",
                    str(track["index"]),
                    "-i",
                    file_path,
                    output_path,
                ]

                extraction_success = False

                try:
                    proc = await create_subprocess_exec(
                        *cmd, stdout=PIPE, stderr=PIPE
                    )

                    _, stderr = await proc.communicate()

                    if (
                        proc.returncode == 0
                        and await aiopath.exists(output_path)
                        and await get_path_size(output_path) > 0
                    ):
                        extracted_files.append(output_path)
                        LOGGER.info(
                            f"Successfully extracted attachment to {output_path} using method 1"
                        )
                        extraction_success = True
                    else:
                        stderr_text = stderr.decode() if stderr else "Unknown error"
                        LOGGER.debug(f"Method 1 failed: {stderr_text}")
                except Exception as e:
                    LOGGER.debug(f"Error in method 1: {e}")

                # Method 2: Try using -map option with data format
                if not extraction_success:
                    LOGGER.debug(
                        f"Trying extraction method 2 for attachment {track['index']}"
                    )
                    temp_file = os.path.join(
                        temp_dir, f"attachment_{track['index']}.bin"
                    )

                    alt_cmd = [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{track['index']}",
                        "-c",
                        "copy",
                        "-f",
                        "data",
                        temp_file,
                    ]

                    try:
                        alt_proc = await create_subprocess_exec(
                            *alt_cmd, stdout=PIPE, stderr=PIPE
                        )

                        _, alt_stderr = await alt_proc.communicate()

                        if (
                            alt_proc.returncode == 0
                            and await aiopath.exists(temp_file)
                            and await get_path_size(temp_file) > 0
                        ):
                            # Copy the temporary file to the output path
                            await aiofiles.os.rename(temp_file, output_path)
                            extracted_files.append(output_path)
                            LOGGER.info(
                                f"Successfully extracted attachment to {output_path} using method 2"
                            )
                            extraction_success = True
                        else:
                            alt_stderr_text = (
                                alt_stderr.decode()
                                if alt_stderr
                                else "Unknown error"
                            )
                            LOGGER.debug(f"Method 2 failed: {alt_stderr_text}")
                    except Exception as alt_e:
                        LOGGER.debug(f"Error in method 2: {alt_e}")

                # Method 3: Try using -c:t copy for attachments
                if not extraction_success:
                    LOGGER.debug(
                        f"Trying extraction method 3 for attachment {track['index']}"
                    )
                    temp_file = os.path.join(
                        temp_dir, f"attachment_{track['index']}_method3.bin"
                    )

                    alt_cmd = [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{track['index']}",
                        "-c:t",
                        "copy",
                        temp_file,
                    ]

                    try:
                        alt_proc = await create_subprocess_exec(
                            *alt_cmd, stdout=PIPE, stderr=PIPE
                        )

                        _, alt_stderr = await alt_proc.communicate()

                        if (
                            alt_proc.returncode == 0
                            and await aiopath.exists(temp_file)
                            and await get_path_size(temp_file) > 0
                        ):
                            # Copy the temporary file to the output path
                            await aiofiles.os.rename(temp_file, output_path)
                            extracted_files.append(output_path)
                            LOGGER.info(
                                f"Successfully extracted attachment to {output_path} using method 3"
                            )
                            extraction_success = True
                        else:
                            alt_stderr_text = (
                                alt_stderr.decode()
                                if alt_stderr
                                else "Unknown error"
                            )
                            LOGGER.debug(f"Method 3 failed: {alt_stderr_text}")
                    except Exception as alt_e:
                        LOGGER.debug(f"Error in method 3: {alt_e}")

                # If all methods failed, create a placeholder file
                if not extraction_success:
                    LOGGER.warning(
                        f"All extraction methods failed for attachment {track['index']}"
                    )
                    try:
                        # Create an empty file with a note about the failure
                        async with aiofiles.open(output_path, "w") as f:
                            await f.write(
                                f"Failed to extract attachment {track['index']} - {track.get('filename', '')}"
                            )
                        LOGGER.debug(
                            f"Created placeholder file for failed attachment extraction: {output_path}"
                        )
                    except Exception as write_e:
                        LOGGER.error(f"Error creating placeholder file: {write_e}")

    # Extract video tracks
    if extract_video and tracks["video"]:
        # Convert video_indices to a list if it's None but video_index is provided
        if video_indices is None and video_index is not None:
            try:
                # Check if video_index is a string with comma-separated values
                if isinstance(video_index, str) and "," in video_index:
                    video_indices = [
                        int(idx.strip())
                        for idx in video_index.split(",")
                        if idx.strip().isdigit()
                    ]
                    LOGGER.debug(
                        f"Converted video_index string '{video_index}' to indices: {video_indices}"
                    )
                else:
                    video_indices = (
                        [int(video_index)]
                        if isinstance(video_index, int | str)
                        and str(video_index).isdigit()
                        else None
                    )
            except Exception as e:
                LOGGER.error(f"Error converting video_index to integer: {e}")

        # Check if video_indices contains the special value "all"
        extract_all_videos = False

        # If video_indices is None, extract all videos
        if video_indices is None:
            extract_all_videos = True
        # Check for "all" in various formats
        elif isinstance(video_indices, list):
            # If it's an empty list, extract all
            if not video_indices:
                extract_all_videos = True
            else:
                # Check for "all" in the list
                for idx in video_indices:
                    if isinstance(idx, str) and idx.lower() == "all":
                        extract_all_videos = True
                        break
        # Check if it's a string equal to "all"
        elif isinstance(video_indices, str) and video_indices.lower() == "all":
            extract_all_videos = True

        # Also check video_index for "all"
        if not extract_all_videos and video_index is not None:
            if isinstance(video_index, str) and video_index.lower() == "all":
                extract_all_videos = True

        if video_indices and not extract_all_videos:
            # Extract specific video tracks by indices
            LOGGER.info(
                f"Extracting only video tracks with indices: {video_indices}"
            )
            found_tracks = []
            for track in tracks["video"]:
                if track["index"] in video_indices:
                    found_tracks.append(track["index"])
                    # Skip attached pictures (cover art)
                    if (
                        "disposition" in track
                        and track["disposition"].get("attached_pic", 0) == 1
                    ):
                        LOGGER.debug(
                            f"Skipping video track {track['index']} as it appears to be cover art"
                        )
                        continue

                    # Determine output extension based on format config if available
                    # Use the video_format parameter passed to the function
                    if (
                        "video_format" in locals()
                        and video_format
                        and video_format.lower() != "none"
                    ):
                        output_ext = video_format
                    else:
                        # Otherwise use the codec-based extension
                        output_ext = get_output_extension("video", video_codec)

                    output_file = os.path.join(
                        output_dir,
                        f"{os.path.splitext(os.path.basename(file_path))[0]}.video.{track.get('language', 'und')}.{track['index']}.{output_ext}",
                    )

                    # Build FFmpeg command
                    cmd = [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{track['index']}",
                    ]

                    # Add video codec only if specified and not None
                    if video_codec is not None and video_codec not in {
                        "None",
                        "none",
                    }:
                        cmd.extend(["-c:v", video_codec])

                        # Add quality settings if not using copy codec
                        if video_codec != "copy":
                            # Use custom quality settings if provided
                            if video_quality:
                                cmd.extend(["-crf", video_quality])
                            elif maintain_quality:
                                if video_codec in ["h264", "libx264"]:
                                    cmd.extend(["-crf", "18"])
                                elif video_codec in ["h265", "libx265"]:
                                    cmd.extend(["-crf", "22"])
                                elif video_codec in ["vp9", "libvpx-vp9"]:
                                    cmd.extend(["-crf", "30"])

                            # Use custom preset if provided
                            if video_preset:
                                cmd.extend(["-preset", video_preset])
                            elif maintain_quality:
                                cmd.extend(["-preset", "medium"])  # Default preset

                            # Use custom bitrate if provided
                            if video_bitrate:
                                cmd.extend(["-b:v", video_bitrate])
                            elif (
                                video_codec in ["vp9", "libvpx-vp9"]
                                and maintain_quality
                            ):
                                cmd.extend(["-b:v", "0"])

                            # Use custom resolution if provided
                            if video_resolution:
                                cmd.extend(["-s", video_resolution])

                            # Use custom fps if provided
                            if video_fps:
                                cmd.extend(["-r", video_fps])

                    # Add thread count for better performance
                    cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                    cmd.append(output_file)

                    LOGGER.debug(
                        f"Extracting video track {track['index']} from {file_path}"
                    )

                    # Run the command
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )

                        _, stderr = await proc.communicate()

                        if proc.returncode == 0 and os.path.exists(output_file):
                            extracted_files.append(output_file)
                            LOGGER.debug(
                                f"Successfully extracted video to {output_file}"
                            )
                        else:
                            stderr_text = (
                                stderr.decode() if stderr else "Unknown error"
                            )
                            LOGGER.error(f"Failed to extract video: {stderr_text}")
                            # Log the command that failed
                            LOGGER.debug(f"Failed command: {' '.join(cmd)}")
                    except Exception as e:
                        LOGGER.error(
                            f"Error running FFmpeg for video extraction: {e}"
                        )
                        # Log the command that failed
                        LOGGER.debug(f"Failed command: {' '.join(cmd)}")

            # Check if any tracks were found
            if not found_tracks:
                LOGGER.warning(
                    f"No video tracks with indices {video_indices} found in {file_path}"
                )
        elif extract_all_videos:
            # Extract all video tracks
            LOGGER.info(f"Extracting all video tracks from {file_path}")
            for track in tracks["video"]:
                # Skip attached pictures (cover art)
                if (
                    "disposition" in track
                    and track["disposition"].get("attached_pic", 0) == 1
                ):
                    continue

                # Determine output extension based on format config if available
                # Use the video_format parameter passed to the function
                if (
                    "video_format" in locals()
                    and video_format
                    and video_format.lower() != "none"
                ):
                    output_ext = video_format
                else:
                    # Otherwise use the codec-based extension
                    output_ext = get_output_extension("video", video_codec)

                output_file = os.path.join(
                    output_dir,
                    f"{os.path.splitext(os.path.basename(file_path))[0]}.video.{track.get('language', 'und')}.{track['index']}.{output_ext}",
                )

                # Build FFmpeg command
                cmd = [
                    ffmpeg_path,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    file_path,
                    "-map",
                    f"0:{track['index']}",
                ]

                # Add video codec only if specified and not None
                if video_codec is not None and video_codec not in {"None", "none"}:
                    cmd.extend(["-c:v", video_codec])

                    # Add quality settings if not using copy codec
                    if video_codec != "copy":
                        # Use custom quality settings if provided
                        if video_quality:
                            cmd.extend(["-crf", video_quality])
                        elif maintain_quality:
                            if video_codec in ["h264", "libx264"]:
                                cmd.extend(["-crf", "18"])
                            elif video_codec in ["h265", "libx265"]:
                                cmd.extend(["-crf", "22"])
                            elif video_codec in ["vp9", "libvpx-vp9"]:
                                cmd.extend(["-crf", "30"])

                        # Use custom preset if provided
                        if video_preset:
                            cmd.extend(["-preset", video_preset])
                        elif maintain_quality:
                            cmd.extend(["-preset", "medium"])  # Default preset

                        # Use custom bitrate if provided
                        if video_bitrate:
                            cmd.extend(["-b:v", video_bitrate])
                        elif (
                            video_codec in ["vp9", "libvpx-vp9"] and maintain_quality
                        ):
                            cmd.extend(["-b:v", "0"])

                        # Use custom resolution if provided
                        if video_resolution:
                            cmd.extend(["-s", video_resolution])

                        # Use custom fps if provided
                        if video_fps:
                            cmd.extend(["-r", video_fps])

                # Add thread count for better performance
                cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                cmd.append(output_file)

                LOGGER.debug(
                    f"Extracting video track {track['index']} from {file_path}"
                )

                # Run the command
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    _, stderr = await proc.communicate()

                    if proc.returncode == 0 and os.path.exists(output_file):
                        extracted_files.append(output_file)
                        LOGGER.info(f"Successfully extracted video to {output_file}")
                    else:
                        stderr_text = stderr.decode() if stderr else "Unknown error"
                        LOGGER.error(f"Failed to extract video: {stderr_text}")
                        # Log the command that failed
                        LOGGER.debug(f"Failed command: {' '.join(cmd)}")
                except Exception as e:
                    LOGGER.error(f"Error running FFmpeg for video extraction: {e}")
                    # Log the command that failed
                    LOGGER.debug(f"Failed command: {' '.join(cmd)}")

    # Extract audio tracks
    if extract_audio and tracks["audio"]:
        # Convert audio_indices to a list if it's None but audio_index is provided
        if audio_indices is None and audio_index is not None:
            try:
                # Check if audio_index is a string with comma-separated values
                if isinstance(audio_index, str) and "," in audio_index:
                    audio_indices = [
                        int(idx.strip())
                        for idx in audio_index.split(",")
                        if idx.strip().isdigit()
                    ]
                    LOGGER.debug(
                        f"Converted audio_index string '{audio_index}' to indices: {audio_indices}"
                    )
                else:
                    audio_indices = (
                        [int(audio_index)]
                        if isinstance(audio_index, int | str)
                        and str(audio_index).isdigit()
                        else None
                    )
            except Exception as e:
                LOGGER.error(f"Error converting audio_index to integer: {e}")

        # Check if audio_indices contains the special value "all"
        extract_all_audios = False

        # If audio_indices is None, extract all audios
        if audio_indices is None:
            extract_all_audios = True
        # Check for "all" in various formats
        elif isinstance(audio_indices, list):
            # If it's an empty list, extract all
            if not audio_indices:
                extract_all_audios = True
            else:
                # Check for "all" in the list
                for idx in audio_indices:
                    if isinstance(idx, str) and idx.lower() == "all":
                        extract_all_audios = True
                        break
        # Check if it's a string equal to "all"
        elif isinstance(audio_indices, str) and audio_indices.lower() == "all":
            extract_all_audios = True

        # Also check audio_index for "all"
        if not extract_all_audios and audio_index is not None:
            if isinstance(audio_index, str) and audio_index.lower() == "all":
                extract_all_audios = True

        if audio_indices and not extract_all_audios:
            # Extract specific audio tracks by indices
            LOGGER.info(
                f"Extracting only audio tracks with indices: {audio_indices}"
            )
            found_tracks = []
            for track in tracks["audio"]:
                if track["index"] in audio_indices:
                    found_tracks.append(track["index"])
                    # Determine output extension based on format config if available
                    # Use the audio_format parameter passed to the function
                    if (
                        "audio_format" in locals()
                        and audio_format
                        and audio_format.lower() != "none"
                    ):
                        output_ext = audio_format
                    else:
                        # Otherwise use the codec-based extension
                        output_ext = get_output_extension("audio", audio_codec)

                    output_file = os.path.join(
                        output_dir,
                        f"{os.path.splitext(os.path.basename(file_path))[0]}.audio.{track.get('language', 'und')}.{track['index']}.{output_ext}",
                    )

                    # Build FFmpeg command
                    cmd = [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{track['index']}",
                    ]

                    # Add audio codec only if specified and not None
                    if audio_codec is not None and audio_codec not in {
                        "None",
                        "none",
                    }:
                        cmd.extend(["-c:a", audio_codec])

                        # Add quality settings if not using copy codec
                        if audio_codec != "copy":
                            # Use custom bitrate if provided
                            if audio_bitrate:
                                cmd.extend(["-b:a", audio_bitrate])
                            elif maintain_quality:
                                if audio_codec in ["aac", "libfdk_aac", "mp3"]:
                                    cmd.extend(["-b:a", "320k"])
                                elif audio_codec in ["opus", "libopus"]:
                                    cmd.extend(["-b:a", "192k"])

                            # Use custom channels if provided
                            if audio_channels:
                                cmd.extend(["-ac", audio_channels])

                            # Use custom sampling rate if provided
                            if audio_sampling:
                                cmd.extend(["-ar", audio_sampling])

                            # Use custom volume if provided
                            if audio_volume:
                                cmd.extend(["-filter:a", f"volume={audio_volume}"])

                            # Add compression level for FLAC
                            if (
                                audio_codec in ["flac", "libflac"]
                                and maintain_quality
                            ):
                                cmd.extend(
                                    ["-compression_level", "5"]
                                )  # Changed from 8 to 5 for better performance

                    # Add thread count for better performance
                    cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                    cmd.append(output_file)

                    LOGGER.debug(
                        f"Extracting audio track {track['index']} from {file_path}"
                    )

                    # Run the command
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )

                        _, stderr = await proc.communicate()

                        if proc.returncode == 0 and os.path.exists(output_file):
                            extracted_files.append(output_file)
                            LOGGER.debug(
                                f"Successfully extracted audio to {output_file}"
                            )
                        else:
                            stderr_text = (
                                stderr.decode() if stderr else "Unknown error"
                            )
                            LOGGER.error(f"Failed to extract audio: {stderr_text}")
                            # Log the command that failed
                            LOGGER.debug(f"Failed command: {' '.join(cmd)}")
                    except Exception as e:
                        LOGGER.error(
                            f"Error running FFmpeg for audio extraction: {e}"
                        )
                        # Log the command that failed
                        LOGGER.debug(f"Failed command: {' '.join(cmd)}")

            # Check if any tracks were found
            if not found_tracks:
                LOGGER.warning(
                    f"No audio tracks with indices {audio_indices} found in {file_path}"
                )
        elif extract_all_audios:
            # Extract all audio tracks
            LOGGER.info(f"Extracting all audio tracks from {file_path}")
            for track in tracks["audio"]:
                # Determine output extension based on format config if available
                # Use the audio_format parameter passed to the function
                if (
                    "audio_format" in locals()
                    and audio_format
                    and audio_format.lower() != "none"
                ):
                    output_ext = audio_format
                else:
                    # Otherwise use the codec-based extension
                    output_ext = get_output_extension("audio", audio_codec)

                output_file = os.path.join(
                    output_dir,
                    f"{os.path.splitext(os.path.basename(file_path))[0]}.audio.{track.get('language', 'und')}.{track['index']}.{output_ext}",
                )

                # Build FFmpeg command
                cmd = [
                    ffmpeg_path,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    file_path,
                    "-map",
                    f"0:{track['index']}",
                ]

                # Add audio codec only if specified and not None
                if audio_codec is not None and audio_codec not in {"None", "none"}:
                    cmd.extend(["-c:a", audio_codec])

                    # Add quality settings if not using copy codec and maintain_quality is True
                    if audio_codec != "copy":
                        # Use custom bitrate if provided
                        if audio_bitrate:
                            cmd.extend(["-b:a", audio_bitrate])
                        elif maintain_quality:
                            if audio_codec in ["aac", "libfdk_aac", "mp3"]:
                                cmd.extend(["-b:a", "320k"])
                            elif audio_codec in ["opus", "libopus"]:
                                cmd.extend(["-b:a", "192k"])

                        # Use custom channels if provided
                        if audio_channels:
                            cmd.extend(["-ac", audio_channels])

                        # Use custom sampling rate if provided
                        if audio_sampling:
                            cmd.extend(["-ar", audio_sampling])

                        # Use custom volume if provided
                        if audio_volume:
                            cmd.extend(["-filter:a", f"volume={audio_volume}"])

                        # Add compression level for FLAC
                        if audio_codec in ["flac", "libflac"] and maintain_quality:
                            cmd.extend(
                                ["-compression_level", "5"]
                            )  # Changed from 8 to 5 for better performance

                # Add thread count for better performance
                cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                cmd.append(output_file)

                LOGGER.debug(
                    f"Extracting audio track {track['index']} from {file_path}"
                )

                # Run the command
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    _, stderr = await proc.communicate()

                    if proc.returncode == 0 and os.path.exists(output_file):
                        extracted_files.append(output_file)
                        LOGGER.info(f"Successfully extracted audio to {output_file}")
                    else:
                        stderr_text = stderr.decode() if stderr else "Unknown error"
                        LOGGER.error(f"Failed to extract audio: {stderr_text}")
                        # Log the command that failed
                        LOGGER.debug(f"Failed command: {' '.join(cmd)}")
                except Exception as e:
                    LOGGER.error(f"Error running FFmpeg for audio extraction: {e}")
                    # Log the command that failed
                    LOGGER.debug(f"Failed command: {' '.join(cmd)}")

    # Extract subtitle tracks
    if extract_subtitle and tracks["subtitle"]:
        # Skip verbose track logging

        # Convert subtitle_indices to a list if it's None but subtitle_index is provided
        if subtitle_indices is None and subtitle_index is not None:
            try:
                # Check if subtitle_index is a string with comma-separated values
                if isinstance(subtitle_index, str) and "," in subtitle_index:
                    subtitle_indices = [
                        int(idx.strip())
                        for idx in subtitle_index.split(",")
                        if idx.strip().isdigit()
                    ]
                    LOGGER.info(
                        f"Converted subtitle_index string '{subtitle_index}' to indices: {subtitle_indices}"
                    )
                elif (
                    isinstance(subtitle_index, str)
                    and subtitle_index.strip().lower() == "all"
                ):
                    subtitle_indices = "all"
                    LOGGER.info(
                        "Subtitle index is 'all', will extract all subtitle tracks"
                    )
                elif (
                    isinstance(subtitle_index, int | str)
                    and str(subtitle_index).isdigit()
                ):
                    subtitle_indices = [int(subtitle_index)]
                    LOGGER.info(f"Using single subtitle index: {subtitle_indices}")
                else:
                    subtitle_indices = None
                    LOGGER.info(
                        "No valid subtitle index provided, will extract all subtitle tracks"
                    )
            except Exception as e:
                LOGGER.error(f"Error converting subtitle_index to integer: {e}")
                # Log the full exception traceback for debugging
                import traceback

                LOGGER.debug(f"Traceback: {traceback.format_exc()}")

        # Check if subtitle_indices contains the special value "all"
        extract_all_subtitles = False

        # If subtitle_indices is None, extract all subtitles
        if subtitle_indices is None:
            extract_all_subtitles = True
        # Check for "all" in various formats
        elif isinstance(subtitle_indices, list):
            # If it's an empty list, extract all
            if not subtitle_indices:
                extract_all_subtitles = True
            else:
                # Check for "all" in the list
                for idx in subtitle_indices:
                    if isinstance(idx, str) and idx.lower() == "all":
                        extract_all_subtitles = True
                        break
        # Check if it's a string equal to "all"
        elif isinstance(subtitle_indices, str) and subtitle_indices.lower() == "all":
            extract_all_subtitles = True

        # Also check subtitle_index for "all"
        if not extract_all_subtitles and subtitle_index is not None:
            if isinstance(subtitle_index, str) and subtitle_index.lower() == "all":
                extract_all_subtitles = True

        # If no indices are specified, extract all
        if (
            subtitle_indices is None
            or (isinstance(subtitle_indices, list) and not subtitle_indices)
        ) and subtitle_index is None:
            extract_all_subtitles = True

        if (
            subtitle_indices is not None
            and not isinstance(subtitle_indices, str)
            and not extract_all_subtitles
        ):
            # Extract specific subtitle tracks by indices
            LOGGER.info(
                f"Extracting only subtitle tracks with indices: {subtitle_indices}"
            )
            found_tracks = []
            for track in tracks["subtitle"]:
                if subtitle_indices and track["index"] in subtitle_indices:
                    found_tracks.append(track["index"])
                    LOGGER.info(
                        f"Found subtitle track with index {track['index']} to extract"
                    )

                    # Determine output extension based on format config if available
                    # Use the subtitle_format parameter passed to the function

                    # Get the input codec
                    input_codec = track.get("codec", "").lower()

                    # Determine the output codec based on settings
                    output_codec = (
                        subtitle_codec.lower()
                        if subtitle_codec and subtitle_codec.lower() != "none"
                        else "copy"
                    )

                    # Determine the output extension based on the codec
                    if output_codec == "copy":
                        # When using copy, use the same extension as the input
                        if input_codec in ["ass", "ssa"]:
                            output_ext = "ass"
                        elif input_codec in {"srt", "subrip"}:
                            output_ext = "srt"
                        elif input_codec in {"vtt", "webvtt"}:
                            output_ext = "vtt"
                        else:
                            # Default to a generic extension
                            output_ext = "sub"
                    elif output_codec == "srt":
                        output_ext = "srt"
                    elif output_codec == "ass":
                        output_ext = "ass"
                    elif output_codec in {"webvtt", "vtt"}:
                        output_ext = "vtt"
                    else:
                        # Use the output codec as the extension
                        output_ext = output_codec

                    # Override with format if specified
                    if subtitle_format and subtitle_format.lower() != "none":
                        output_ext = subtitle_format

                    output_file = os.path.join(
                        output_dir,
                        f"{os.path.splitext(os.path.basename(file_path))[0]}.subtitle.{track.get('language', 'und')}.{track['index']}.{output_ext}",
                    )

                    # Build FFmpeg command
                    cmd = [
                        ffmpeg_path,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{track['index']}",
                    ]

                    # Handle subtitle codec based on input and output formats
                    input_codec = track.get("codec", "").lower()

                    # Normalize input codec names
                    if input_codec == "subrip":
                        input_codec = "srt"
                    elif input_codec in ["ass", "ssa"]:
                        input_codec = "ass"

                    # Determine output format based on subtitle_format or codec
                    output_format = None
                    if subtitle_format and subtitle_format.lower() != "none":
                        output_format = subtitle_format.lower()
                    elif subtitle_codec and subtitle_codec.lower() != "none":
                        if subtitle_codec.lower() == "copy":
                            output_format = input_codec
                        else:
                            output_format = subtitle_codec.lower()
                    else:
                        # Default to SRT if no format/codec specified
                        output_format = "srt"

                    # Handle format conversion
                    if output_format and output_format != input_codec:
                        # Converting between formats
                        if output_format == "srt" and input_codec in ["ass", "ssa"]:
                            # Converting from ASS/SSA to SRT
                            cmd.extend(["-c:s", "srt"])
                        elif output_format == "ass" and input_codec == "srt":
                            # Converting from SRT to ASS
                            cmd.extend(["-c:s", "ass"])
                        elif output_format == "vtt" and input_codec in [
                            "srt",
                            "ass",
                            "ssa",
                        ]:
                            # Converting to WebVTT
                            cmd.extend(["-c:s", "webvtt"])
                        # For other conversions, let FFmpeg choose the appropriate codec
                        elif subtitle_codec and subtitle_codec.lower() != "none":
                            cmd.extend(["-c:s", subtitle_codec])
                    # No conversion needed, use copy if possible
                    elif input_codec in ["ass", "ssa", "srt", "vtt", "webvtt"]:
                        cmd.extend(["-c:s", "copy"])
                    # For other formats, let FFmpeg choose the appropriate codec
                    elif subtitle_codec and subtitle_codec.lower() != "none":
                        cmd.extend(["-c:s", subtitle_codec])
                    else:
                        # Default to SRT for unknown formats
                        cmd.extend(["-c:s", "srt"])

                    # For ASS/SSA subtitles, make sure the output format matches the codec
                    if input_codec in ["ass", "ssa"] and output_format == "srt":
                        # Force output format to match the codec
                        cmd.extend(["-f", "srt"])

                        # Make sure the output file has the correct extension
                        output_file = os.path.splitext(output_file)[0] + ".srt"

                    # Add subtitle language if specified
                    if subtitle_language:
                        cmd.extend(
                            ["-metadata:s:s:0", f"language={subtitle_language}"]
                        )

                    # Add subtitle encoding if specified
                    if subtitle_encoding:
                        cmd.extend(["-sub_charenc", subtitle_encoding])

                    # Add subtitle font if specified
                    if subtitle_font and subtitle_codec in ["ass", "ssa"]:
                        cmd.extend(["-metadata:s:s:0", f"font={subtitle_font}"])

                    # Add subtitle font size if specified
                    if subtitle_font_size and subtitle_codec in ["ass", "ssa"]:
                        cmd.extend(
                            ["-metadata:s:s:0", f"fontsize={subtitle_font_size}"]
                        )

                    cmd.append(output_file)

                    LOGGER.info(
                        f"Extracting subtitle track {track['index']} from {file_path}"
                    )

                    # Run the command
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )

                        _, stderr = await proc.communicate()

                        if (
                            proc.returncode == 0
                            and os.path.exists(output_file)
                            and os.path.getsize(output_file) > 0
                        ):
                            extracted_files.append(output_file)
                            LOGGER.info(
                                f"Successfully extracted subtitle to {output_file}"
                            )
                        else:
                            stderr_text = (
                                stderr.decode() if stderr else "Unknown error"
                            )
                            LOGGER.error(
                                f"Failed to extract subtitle: {stderr_text}"
                            )

                            # Try alternative approaches for subtitle extraction
                            input_codec = track.get("codec", "").lower()

                            # First try: Use the same codec as input for output (copy)
                            LOGGER.info(
                                f"Trying first alternative approach: copy codec for track {track['index']}"
                            )

                            # For ASS/SSA subtitles, use .ass extension
                            ext = "ass" if input_codec in ["ass", "ssa"] else "srt"

                            alt_output_file = os.path.join(
                                output_dir,
                                f"{os.path.splitext(os.path.basename(file_path))[0]}.subtitle.{track.get('language', 'und')}.{track['index']}.{ext}",
                            )

                            alt_cmd = [
                                ffmpeg_path,
                                "-hide_banner",
                                "-loglevel",
                                "error",
                                "-i",
                                file_path,
                                "-map",
                                f"0:{track['index']}",
                                "-c:s",
                                "copy",
                                alt_output_file,
                            ]

                            # Skip logging the full command

                            alt_proc = await asyncio.create_subprocess_exec(
                                *alt_cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )

                            _, alt_stderr = await alt_proc.communicate()

                            if (
                                alt_proc.returncode == 0
                                and os.path.exists(alt_output_file)
                                and os.path.getsize(alt_output_file) > 0
                            ):
                                extracted_files.append(alt_output_file)
                                LOGGER.info(
                                    f"Successfully extracted subtitle to {alt_output_file} using copy codec"
                                )
                            else:
                                alt_stderr_text = (
                                    alt_stderr.decode()
                                    if alt_stderr
                                    else "Unknown error"
                                )
                                LOGGER.error(
                                    f"First alternative approach failed: {alt_stderr_text}"
                                )

                                # Second try: For ASS/SSA, try extracting to SRT with explicit conversion
                                if input_codec in ["ass", "ssa"]:
                                    LOGGER.info(
                                        f"Trying second alternative approach: ASS to SRT conversion for track {track['index']}"
                                    )
                                    alt_output_file2 = os.path.join(
                                        output_dir,
                                        f"{os.path.splitext(os.path.basename(file_path))[0]}.subtitle.{track.get('language', 'und')}.{track['index']}.srt",
                                    )

                                    # Use more explicit conversion parameters
                                    alt_cmd2 = [
                                        ffmpeg_path,
                                        "-hide_banner",
                                        "-loglevel",
                                        "error",
                                        "-i",
                                        file_path,
                                        "-map",
                                        f"0:{track['index']}",
                                        "-f",
                                        "srt",  # Force SRT format
                                        alt_output_file2,
                                    ]

                                    LOGGER.info(
                                        f"Second alternative FFmpeg command: {' '.join(alt_cmd2)}"
                                    )

                                    alt_proc2 = await asyncio.create_subprocess_exec(
                                        *alt_cmd2,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                    )

                                    _, alt_stderr2 = await alt_proc2.communicate()

                                    if (
                                        alt_proc2.returncode == 0
                                        and os.path.exists(alt_output_file2)
                                        and os.path.getsize(alt_output_file2) > 0
                                    ):
                                        extracted_files.append(alt_output_file2)
                                        LOGGER.info(
                                            f"Successfully extracted subtitle to {alt_output_file2} using ASS to SRT conversion"
                                        )
                                    else:
                                        alt_stderr_text2 = (
                                            alt_stderr2.decode()
                                            if alt_stderr2
                                            else "Unknown error"
                                        )
                                        LOGGER.error(
                                            f"Second alternative approach also failed: {alt_stderr_text2}"
                                        )
                                else:
                                    LOGGER.error(
                                        f"All extraction attempts failed for track {track['index']}"
                                    )
                    except Exception as e:
                        LOGGER.error(
                            f"Error running FFmpeg for subtitle extraction: {e}"
                        )
                        # Log the full exception traceback for debugging
                        import traceback

                        LOGGER.debug(f"Traceback: {traceback.format_exc()}")

            # Check if any tracks were found
            if not found_tracks:
                LOGGER.warning(
                    f"No subtitle tracks with indices {subtitle_indices} found in {file_path}"
                )
        elif extract_all_subtitles:
            # Extract all subtitle tracks
            LOGGER.info(f"Extracting all subtitle tracks from {file_path}")
            for track in tracks["subtitle"]:
                # Determine output extension based on format config if available
                # Use the subtitle_format parameter passed to the function

                # Get the input codec
                input_codec = track.get("codec", "").lower()

                # Normalize input codec names
                if input_codec == "subrip":
                    input_codec = "srt"
                elif input_codec in ["ass", "ssa"]:
                    input_codec = "ass"

                # If format is specified and not 'none', use it directly
                if subtitle_format and subtitle_format.lower() != "none":
                    output_ext = subtitle_format
                else:
                    # Otherwise use the codec-based extension
                    output_ext = get_output_extension(
                        "subtitle", subtitle_codec, input_codec
                    )

                # Determine output format based on subtitle_format or codec
                output_format = None
                if subtitle_format and subtitle_format.lower() != "none":
                    output_format = subtitle_format.lower()
                    LOGGER.debug(f"Using specified subtitle format: {output_format}")
                elif subtitle_codec and subtitle_codec.lower() != "none":
                    if subtitle_codec.lower() == "copy":
                        output_format = input_codec
                        LOGGER.debug(
                            f"Using copy codec, preserving original format: {input_codec}"
                        )
                    else:
                        output_format = subtitle_codec.lower()
                        LOGGER.debug(
                            f"Using specified subtitle codec as format: {output_format}"
                        )
                # For ASS/SSA subtitles, preserve the format when using copy
                elif input_codec in ["ass", "ssa"]:
                    output_format = "ass"
                    LOGGER.debug(
                        f"Preserving ASS/SSA format for track {track['index']}"
                    )
                else:
                    # Default to SRT if no format/codec specified
                    output_format = "srt"
                    LOGGER.debug("No format/codec specified, defaulting to SRT")

                # For ASS/SSA subtitles, make sure the extension matches the codec
                if input_codec in ["ass", "ssa"] and output_format == "srt":
                    # Force output format to match the codec
                    output_ext = "srt"
                    LOGGER.debug(
                        f"Forcing SRT extension for ASS/SSA subtitle track {track['index']}"
                    )
                elif input_codec in ["ass", "ssa"] and (
                    output_format in {"ass", "copy"}
                ):
                    # Use ASS extension for ASS/SSA subtitles when copying
                    output_ext = "ass"
                    LOGGER.debug(
                        f"Using ASS extension for ASS/SSA subtitle track {track['index']}"
                    )

                output_file = os.path.join(
                    output_dir,
                    f"{os.path.splitext(os.path.basename(file_path))[0]}.subtitle.{track.get('language', 'und')}.{track['index']}.{output_ext}",
                )

                # Build FFmpeg command
                cmd = [
                    ffmpeg_path,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    file_path,
                    "-map",
                    f"0:{track['index']}",
                ]

                # Handle subtitle codec based on input and output formats
                input_codec = track.get("codec", "").lower()
                LOGGER.debug(
                    f"Original input codec for track {track['index']}: {input_codec}"
                )

                # Normalize input codec names
                if input_codec == "subrip":
                    input_codec = "srt"
                    LOGGER.debug(
                        f"Normalized 'subrip' codec to 'srt' for track {track['index']}"
                    )
                elif input_codec in ["ass", "ssa"]:
                    input_codec = "ass"
                    LOGGER.debug(
                        f"Normalized '{input_codec}' codec to 'ass' for track {track['index']}"
                    )

                # Determine output format based on subtitle_format or codec
                output_format = None
                if subtitle_format and subtitle_format.lower() != "none":
                    output_format = subtitle_format.lower()
                    LOGGER.debug(f"Using specified subtitle format: {output_format}")
                elif subtitle_codec and subtitle_codec.lower() != "none":
                    if subtitle_codec.lower() == "copy":
                        output_format = input_codec
                        LOGGER.debug(
                            f"Using copy codec, preserving original format: {input_codec}"
                        )
                    else:
                        output_format = subtitle_codec.lower()
                        LOGGER.debug(
                            f"Using specified subtitle codec as format: {output_format}"
                        )
                # For ASS/SSA subtitles, preserve the format when using copy
                elif input_codec in ["ass", "ssa"]:
                    output_format = "ass"
                    LOGGER.debug(
                        f"Preserving ASS/SSA format for track {track['index']}"
                    )
                else:
                    # Default to SRT if no format/codec specified
                    output_format = "srt"
                    LOGGER.debug("No format/codec specified, defaulting to SRT")

                # Handle format conversion
                if output_format and output_format != input_codec:
                    # Converting between formats
                    if output_format == "srt" and input_codec in ["ass", "ssa"]:
                        # Converting from ASS/SSA to SRT
                        cmd.extend(["-c:s", "srt"])
                        # Force SRT format for output
                        cmd.extend(["-f", "srt"])
                        LOGGER.debug(
                            f"Converting from {input_codec} to SRT with forced format"
                        )
                    elif output_format == "ass" and input_codec == "srt":
                        # Converting from SRT to ASS
                        cmd.extend(["-c:s", "ass"])
                        LOGGER.debug("Converting from SRT to ASS")
                    elif output_format == "vtt" and input_codec in [
                        "srt",
                        "ass",
                        "ssa",
                    ]:
                        # Converting to WebVTT
                        cmd.extend(["-c:s", "webvtt"])
                        LOGGER.debug(f"Converting from {input_codec} to WebVTT")
                    else:
                        # For other conversions, let FFmpeg choose the appropriate codec
                        LOGGER.debug(
                            f"Converting subtitle from {input_codec} to {output_format}"
                        )
                        if subtitle_codec and subtitle_codec.lower() != "none":
                            cmd.extend(["-c:s", subtitle_codec])
                # No conversion needed, use copy if possible
                elif input_codec in ["ass", "ssa", "srt", "vtt", "webvtt"]:
                    cmd.extend(["-c:s", "copy"])
                    LOGGER.debug(f"Using copy codec for {input_codec}")
                else:
                    # For other formats, let FFmpeg choose the appropriate codec
                    LOGGER.debug(
                        f"Using default codec for subtitle format: {input_codec}"
                    )
                    if subtitle_codec and subtitle_codec.lower() != "none":
                        cmd.extend(["-c:s", subtitle_codec])
                    else:
                        # Default to SRT for unknown formats
                        cmd.extend(["-c:s", "srt"])
                        LOGGER.debug("Using SRT codec for unknown format")

                # Add subtitle language if specified
                if subtitle_language:
                    cmd.extend(["-metadata:s:s:0", f"language={subtitle_language}"])

                # Add subtitle encoding if specified
                if subtitle_encoding:
                    cmd.extend(["-sub_charenc", subtitle_encoding])

                # Add subtitle font if specified
                if subtitle_font and subtitle_codec in ["ass", "ssa"]:
                    cmd.extend(["-metadata:s:s:0", f"font={subtitle_font}"])

                # Add subtitle font size if specified
                if subtitle_font_size and subtitle_codec in ["ass", "ssa"]:
                    cmd.extend(["-metadata:s:s:0", f"fontsize={subtitle_font_size}"])

                cmd.append(output_file)

                LOGGER.debug(
                    f"Extracting subtitle track {track['index']} from {file_path}"
                )

                # Run the command
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    _, stderr = await proc.communicate()

                    if proc.returncode == 0 and os.path.exists(output_file):
                        extracted_files.append(output_file)
                        LOGGER.info(
                            f"Successfully extracted subtitle to {output_file}"
                        )
                    else:
                        stderr_text = stderr.decode() if stderr else "Unknown error"
                        LOGGER.error(f"Failed to extract subtitle: {stderr_text}")
                        # Log the command that failed
                        LOGGER.debug(f"Failed command: {' '.join(cmd)}")
                except Exception as e:
                    LOGGER.error(
                        f"Error running FFmpeg for subtitle extraction: {e}"
                    )
                    # Log the command that failed
                    LOGGER.debug(f"Failed command: {' '.join(cmd)}")

    # Delete original file if requested
    if delete_original and extracted_files:
        try:
            LOGGER.info(f"Deleting original file after extraction: {file_path}")
            await remove(file_path)
        except Exception as e:
            LOGGER.error(f"Error deleting original file: {e}")
            # Try again with a different approach
            try:
                import os

                os.remove(file_path)
            except Exception as e2:
                LOGGER.error(f"Second attempt to delete file failed: {e2}")
    elif delete_original and not extracted_files:
        LOGGER.warning(
            f"No files were extracted, so original file will not be deleted: {file_path}"
        )

    return extracted_files


async def create_default_audio_thumbnail(output_dir, user_id=None):
    # Try user thumbnail first if available
    if user_id and await aiopath.exists(f"thumbnails/{user_id}.jpg"):
        LOGGER.debug("Using user thumbnail for audio file")
        return f"thumbnails/{user_id}.jpg"
    # Then try owner thumbnail
    if await aiopath.exists(f"thumbnails/{Config.OWNER_ID}.jpg"):
        LOGGER.debug("Using owner thumbnail for audio file")
        return f"thumbnails/{Config.OWNER_ID}.jpg"

    # Create a default audio thumbnail if no user/owner thumbnail
    default_thumb = ospath.join(output_dir, "default_audio.jpg")

    # First check if the default thumbnail already exists
    if await aiopath.exists(default_thumb):
        return default_thumb

    # Try to create the default thumbnail using FFmpeg
    try:
        # Make sure the output directory exists
        await makedirs(output_dir, exist_ok=True)

        # Create a simple default audio thumbnail
        cmd = [
            "xtra",  # Using xtra instead of ffmpeg
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x320",
            "-ignore_unknown",
            "-frames:v",
            "1",
            default_thumb,
        ]

        # Execute the command
        _, err, code = await cmd_exec(cmd)

        if code != 0 or not await aiopath.exists(default_thumb):
            LOGGER.debug(f"Failed to create default audio thumbnail: {err}")
            # Try with a different approach
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=320x320",
                "-ignore_unknown",
                "-y",  # Overwrite output file
                "-frames:v",
                "1",
                default_thumb,
            ]

            # Execute the command
            _, err, code = await cmd_exec(cmd)

            if code != 0 or not await aiopath.exists(default_thumb):
                LOGGER.debug(
                    f"Failed to create default audio thumbnail with second method: {err}",
                )
                # As a last resort, try to create a simple image file directly
                try:
                    # Create a simple blue image (320x320 pixel) and save it
                    from PIL import Image

                    # Apply memory limits for PIL operations
                    limit_memory_for_pil()

                    img = Image.new("RGB", (320, 320), color=(0, 0, 255))
                    img.save(default_thumb)
                    LOGGER.debug("Created default audio thumbnail using PIL")
                except Exception as e:
                    LOGGER.debug(
                        f"Failed to create default audio thumbnail with PIL: {e}",
                    )
                    # Create an even simpler fallback image
                    try:
                        # Create a tiny blue image and save it
                        # Apply memory limits for PIL operations
                        limit_memory_for_pil()

                        img = Image.new("RGB", (32, 32), color=(0, 0, 255))
                        img.save(default_thumb)
                        LOGGER.debug(
                            "Created tiny default audio thumbnail using PIL"
                        )
                    except Exception as e2:
                        LOGGER.debug(f"All thumbnail creation methods failed: {e2}")
                        return None
    except Exception as e:
        LOGGER.debug(f"Error creating default audio thumbnail: {e}")
        return None

    # Final check to make sure the thumbnail exists
    if await aiopath.exists(default_thumb):
        return default_thumb
    return None


async def get_video_thumbnail(video_file, duration):
    output_dir = f"{DOWNLOAD_DIR}thumbnails"
    await makedirs(output_dir, exist_ok=True)
    output = ospath.join(output_dir, f"{time()}.jpg")

    if duration is None:
        duration = (await get_media_info(video_file))[0]
    if duration == 0:
        duration = 3
    duration = duration // 2
    cmd = [
        "xtra",  # Using xtra instead of ffmpeg
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{duration}",
        "-i",
        video_file,
        "-vf",
        "scale=640:-1",
        "-q:v",
        "5",
        "-vframes",
        "1",
        "-threads",
        "1",
        output,
    ]
    try:
        _, err, code = await wait_for(cmd_exec(cmd), timeout=60)
        if code != 0 or not await aiopath.exists(output):
            LOGGER.error(
                f"Error while extracting thumbnail from video. Name: {video_file} stderr: {err}",
            )
            return None
    except Exception:
        LOGGER.error(
            f"Error while extracting thumbnail from video. Name: {video_file}. Error: Timeout some issues with ffmpeg with specific arch!",
        )
        return None
    return output


async def create_default_text_thumbnail(output_dir, user_id=None):
    # Try user thumbnail first if available
    if user_id and await aiopath.exists(f"thumbnails/{user_id}.jpg"):
        LOGGER.debug("Using user thumbnail for text file")
        return f"thumbnails/{user_id}.jpg"
    # Then try owner thumbnail
    if await aiopath.exists(f"thumbnails/{Config.OWNER_ID}.jpg"):
        LOGGER.debug("Using owner thumbnail for text file")
        return f"thumbnails/{Config.OWNER_ID}.jpg"

    # Create a default thumbnail for text files if no user/owner thumbnail
    default_thumb = ospath.join(output_dir, "default_text.jpg")
    if not await aiopath.exists(default_thumb):
        # Create a simple default text file thumbnail
        cmd = [
            "xtra",  # Using xtra instead of ffmpeg
            "-f",
            "lavfi",
            "-i",
            "color=c=gray:s=320x320",
            "-frames:v",
            "1",
            default_thumb,
        ]
        _, _, code = await cmd_exec(cmd)

        if code != 0 or not await aiopath.exists(default_thumb):
            # If FFmpeg fails, try with PIL
            try:
                # Apply memory limits for PIL operations
                limit_memory_for_pil()

                # Create a simple gray image
                img = Image.new("RGB", (320, 320), color=(128, 128, 128))
                img.save(default_thumb)
                LOGGER.debug("Created default text thumbnail using PIL")
            except Exception as e:
                LOGGER.debug(
                    f"Failed to create default text thumbnail with PIL: {e}"
                )
                return None

    if await aiopath.exists(default_thumb):
        return default_thumb
    return None


async def create_default_video_thumbnail(output_dir, user_id=None):
    # Try user thumbnail first if available
    if user_id and await aiopath.exists(f"thumbnails/{user_id}.jpg"):
        LOGGER.debug("Using user thumbnail for video file")
        return f"thumbnails/{user_id}.jpg"
    # Then try owner thumbnail
    if await aiopath.exists(f"thumbnails/{Config.OWNER_ID}.jpg"):
        LOGGER.debug("Using owner thumbnail for video file")
        return f"thumbnails/{Config.OWNER_ID}.jpg"

    # Create a default thumbnail for video files if no user/owner thumbnail
    default_thumb = ospath.join(output_dir, "default_video.jpg")
    if not await aiopath.exists(default_thumb):
        # Create a simple default video thumbnail
        cmd = [
            "xtra",  # Using xtra instead of ffmpeg
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=640x360",
            "-vf",
            "drawtext=text='Video':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2",
            "-frames:v",
            "1",
            default_thumb,
        ]
        _, _, code = await cmd_exec(cmd)

        if code != 0 or not await aiopath.exists(default_thumb):
            # If FFmpeg fails, try with PIL
            try:
                # Apply memory limits for PIL operations
                limit_memory_for_pil()

                # Create a simple black image
                img = Image.new("RGB", (640, 360), color=(0, 0, 0))
                img.save(default_thumb)
                LOGGER.debug("Created default video thumbnail using PIL")
            except Exception as e:
                LOGGER.debug(
                    f"Failed to create default video thumbnail with PIL: {e}"
                )
                return None

    if await aiopath.exists(default_thumb):
        return default_thumb
    return None


async def create_default_image_thumbnail(output_dir, user_id=None):
    # Try user thumbnail first if available
    if user_id and await aiopath.exists(f"thumbnails/{user_id}.jpg"):
        LOGGER.debug("Using user thumbnail for image file")
        return f"thumbnails/{user_id}.jpg"
    # Then try owner thumbnail
    if await aiopath.exists(f"thumbnails/{Config.OWNER_ID}.jpg"):
        LOGGER.debug("Using owner thumbnail for image file")
        return f"thumbnails/{Config.OWNER_ID}.jpg"

    # Create a default thumbnail for image files if no user/owner thumbnail
    default_thumb = ospath.join(output_dir, "default_image.jpg")
    if not await aiopath.exists(default_thumb):
        # Create a simple default image thumbnail
        cmd = [
            "xtra",  # Using xtra instead of ffmpeg
            "-f",
            "lavfi",
            "-i",
            "color=c=purple:s=640x360",
            "-vf",
            "drawtext=text='Image':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2",
            "-frames:v",
            "1",
            default_thumb,
        ]
        _, _, code = await cmd_exec(cmd)

        if code != 0 or not await aiopath.exists(default_thumb):
            # If FFmpeg fails, try with PIL
            try:
                # Apply memory limits for PIL operations
                limit_memory_for_pil()

                # Create a simple purple image
                img = Image.new("RGB", (640, 360), color=(128, 0, 128))
                img.save(default_thumb)
                LOGGER.debug("Created default image thumbnail using PIL")
            except Exception as e:
                LOGGER.debug(
                    f"Failed to create default image thumbnail with PIL: {e}"
                )
                return None

    if await aiopath.exists(default_thumb):
        return default_thumb
    return None


async def get_multiple_frames_thumbnail(video_file, layout, keep_screenshots):
    ss_nb = layout.split("x")
    ss_nb = int(ss_nb[0]) * int(ss_nb[1])
    dirpath = await take_ss(video_file, ss_nb)
    if not dirpath:
        return None
    output_dir = f"{DOWNLOAD_DIR}thumbnails"
    await makedirs(output_dir, exist_ok=True)
    output = ospath.join(output_dir, f"{time()}.jpg")
    cmd = [
        "xtra",  # Using xtra instead of ffmpeg
        "-hide_banner",
        "-loglevel",
        "error",
        "-pattern_type",
        "glob",
        "-i",
        f"{escape(dirpath)}/*.png",
        "-vf",
        f"tile={layout}, thumbnail",
        "-q:v",
        "1",
        "-frames:v",
        "1",
        "-f",
        "mjpeg",
        "-threads",
        f"{max(1, cpu_no // 2)}",
        output,
    ]
    try:
        _, err, code = await wait_for(cmd_exec(cmd), timeout=60)
        if code != 0 or not await aiopath.exists(output):
            LOGGER.error(
                f"Error while combining thumbnails for video. Name: {video_file} stderr: {err}",
            )
            return None
    except Exception:
        LOGGER.error(
            f"Error while combining thumbnails from video. Name: {video_file}. Error: Timeout some issues with ffmpeg with specific arch!",
        )
        return None
    finally:
        if not keep_screenshots:
            await rmtree(dirpath, ignore_errors=True)
    return output


def is_mkv(file):
    """Legacy function name, now checks if file is a supported media format for metadata and watermarking.

    Args:
        file: Path to the file

    Returns:
        bool: True if the file is a supported media format for metadata or watermarking
    """
    # Video formats (expanded list for better compatibility)
    video_extensions = [
        ".mkv",
        ".mp4",
        ".avi",
        ".mov",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".ts",
        ".3gp",
        ".mpg",
        ".mpeg",
        ".vob",
        ".divx",
        ".asf",
        ".m2ts",
        ".mts",
    ]
    # Audio formats (expanded list for better compatibility)
    audio_extensions = [
        ".mp3",
        ".m4a",
        ".flac",
        ".wav",
        ".ogg",
        ".opus",
        ".aac",
        ".wma",
        ".alac",
        ".ape",
    ]
    # Image formats (expanded list for better compatibility)
    image_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
        ".svg",
        ".heic",
        ".heif",
        ".gif",
        ".apng",
        ".mng",
    ]
    # Subtitle formats that support metadata
    subtitle_extensions = [
        ".srt",
        ".ass",
        ".ssa",
        ".sub",
        ".idx",
    ]

    # Check if the file has a supported extension
    file_lower = file.lower()
    return any(
        file_lower.endswith(ext)
        for ext in video_extensions
        + audio_extensions
        + image_extensions
        + subtitle_extensions
    )


async def get_media_type_for_watermark(file):
    """Determine the media type for watermarking purposes.

    Args:
        file: Path to the file

    Returns:
        str: 'image', 'video', 'animated_image', 'audio', 'subtitle', or None if not supported
    """
    import os  # Import os module for path operations

    # Video formats (expanded list for better compatibility)
    video_extensions = [
        ".mkv",
        ".mp4",
        ".avi",
        ".mov",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".ts",
        ".3gp",
        ".mpg",
        ".mpeg",
        ".vob",
        ".divx",
        ".asf",
        ".m2ts",
        ".mts",
    ]
    # Image formats (expanded list for better compatibility)
    image_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
        ".svg",
        ".heic",
        ".heif",
    ]
    # Animated image formats (special handling)
    animated_extensions = [
        ".gif",
        ".apng",
        ".mng",
    ]
    # Audio formats
    audio_extensions = [
        ".mp3",
        ".m4a",
        ".flac",
        ".wav",
        ".ogg",
        ".opus",
        ".aac",
        ".wma",
        ".alac",
        ".ape",
    ]
    # Subtitle formats
    subtitle_extensions = [
        ".srt",
        ".ass",
        ".ssa",
        ".sub",
        ".idx",
        ".vtt",
    ]

    # Check if file exists
    if not os.path.exists(file):
        LOGGER.error(f"File not found for watermarking: {file}")
        return None

    file_lower = file.lower()

    # First try to determine type by extension
    if any(file_lower.endswith(ext) for ext in video_extensions):
        return "video"
    if any(file_lower.endswith(ext) for ext in image_extensions):
        return "image"
    if any(file_lower.endswith(ext) for ext in animated_extensions):
        return "animated_image"
    if any(file_lower.endswith(ext) for ext in audio_extensions):
        return "audio"
    if any(file_lower.endswith(ext) for ext in subtitle_extensions):
        return "subtitle"

    # If extension doesn't match, try to determine by file content using ffprobe
    try:
        import json

        from .bot_utils import cmd_exec

        # Use ffprobe to get file information
        cmd = [
            "ffprobe",  # Keep as ffprobe, not xtra
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,avg_frame_rate",
            "-of",
            "json",
            file,
        ]

        # Execute the command
        stdout, _, code = await cmd_exec(cmd)

        if code == 0:
            data = json.loads(stdout)
            if data.get("streams"):
                # First check if there's a video stream - if so, it's a video file
                # This ensures that files with both video and audio are treated as videos
                has_video = False
                has_audio = False
                has_subtitle = False

                for stream in data["streams"]:
                    codec_type = stream.get("codec_type")
                    codec_name = stream.get("codec_name")
                    avg_frame_rate = stream.get("avg_frame_rate", "")

                    if codec_type == "video":
                        # Check if it's an animated image
                        if codec_name in ["gif", "apng"]:
                            return "animated_image"
                        # Check if it's a single frame (likely an image)
                        if avg_frame_rate in {"0/0", "1/1"}:
                            return "image"
                        has_video = True
                    elif codec_type == "audio":
                        has_audio = True
                    elif codec_type == "subtitle":
                        has_subtitle = True

                # Prioritize video over audio over subtitle
                if has_video:
                    if has_subtitle:
                        return "video_with_subtitle"
                    return "video"
                if has_audio:
                    return "audio"
                if has_subtitle:
                    return "subtitle"
    except Exception as e:
        LOGGER.warning(f"Error determining media type for {file}: {e!s}")

    # If all else fails, try to determine by mime type
    try:
        from .files_utils import get_mime_type

        mime_type = await get_mime_type(file)
        if mime_type:
            if mime_type.startswith("video/"):
                return "video"
            if mime_type.startswith("image/"):
                if mime_type in ["image/gif", "image/apng"]:
                    return "animated_image"
                return "image"
            if mime_type.startswith("audio/"):
                return "audio"
            if mime_type in ["text/plain", "application/x-subrip"]:
                # Check if it's a subtitle file by examining content
                with open(file, errors="ignore") as f:
                    content = f.read(1000)  # Read first 1000 chars
                    if "-->" in content and content[0].isdigit():
                        return "subtitle"
    except Exception as e:
        LOGGER.warning(f"Error determining mime type for {file}: {e!s}")

    # If all else fails, return None
    LOGGER.warning(f"Could not determine media type for watermarking: {file}")
    return None


class FFMpeg:
    def __init__(self, listener):
        self._listener = listener
        self._processed_bytes = 0
        self._last_processed_bytes = 0
        self._processed_time = 0
        self._last_processed_time = 0
        self._speed_raw = 0
        self._progress_raw = 0
        self._total_time = 0
        self._eta_raw = 0
        self._time_rate = 0.1
        self._start_time = 0

    @property
    def processed_bytes(self):
        return self._processed_bytes

    @property
    def speed_raw(self):
        return self._speed_raw

    @property
    def progress_raw(self):
        return self._progress_raw

    @property
    def eta_raw(self):
        return self._eta_raw

    def clear(self):
        self._start_time = time()
        self._processed_bytes = 0
        self._processed_time = 0
        self._speed_raw = 0
        self._progress_raw = 0
        self._eta_raw = 0
        self._time_rate = 0.1
        self._last_processed_time = 0
        self._last_processed_bytes = 0

    async def _ffmpeg_progress(self):
        while not (
            self._listener.subproc.returncode is not None
            or self._listener.is_cancelled
            or self._listener.subproc.stdout.at_eof()
        ):
            try:
                line = await wait_for(self._listener.subproc.stdout.readline(), 60)
            except Exception:
                break
            line = line.decode().strip()
            if not line:
                break
            if "=" in line:
                key, value = line.split("=", 1)
                if value != "N/A":
                    if key == "total_size":
                        self._processed_bytes = (
                            int(value) + self._last_processed_bytes
                        )
                        self._speed_raw = self._processed_bytes / (
                            time() - self._start_time
                        )

                        # If this is a trim operation and we have a valid total_time,
                        # update progress based on processed bytes
                        if (
                            hasattr(self._listener, "subsize")
                            and self._listener.subsize > 0
                        ):
                            try:
                                # For trim operations, we need to handle progress differently
                                # based on the media type
                                if (
                                    hasattr(self._listener, "cstatus")
                                    and self._listener.cstatus == "Trim"
                                ):
                                    # For trim operations, use a combination of time and bytes for more accurate progress
                                    if (
                                        self._total_time > 0
                                        and self._processed_time > 0
                                    ):
                                        # Calculate progress based on processed time
                                        time_progress = (
                                            self._processed_time / self._total_time
                                        ) * 100

                                        # Calculate progress based on processed bytes
                                        byte_progress = (
                                            self._processed_bytes
                                            / self._listener.subsize
                                        ) * 100

                                        # Use the average of both methods for more accurate progress
                                        self._progress_raw = min(
                                            (time_progress + byte_progress) / 2, 99.9
                                        )

                                        # Calculate ETA based on current speed and remaining bytes/time
                                        if self._speed_raw > 0:
                                            remaining_bytes = max(
                                                0,
                                                self._listener.subsize
                                                - self._processed_bytes,
                                            )
                                            eta_bytes = (
                                                remaining_bytes / self._speed_raw
                                            )

                                            remaining_time = max(
                                                0,
                                                self._total_time
                                                - self._processed_time,
                                            )
                                            eta_time = (
                                                remaining_time / self._time_rate
                                                if self._time_rate > 0
                                                else 0
                                            )

                                            # Use the average of both methods for more accurate ETA
                                            self._eta_raw = (
                                                eta_bytes + eta_time
                                            ) / 2
                                        else:
                                            self._eta_raw = 0
                                    else:
                                        # Fallback to byte-based progress if time is not available
                                        self._progress_raw = min(
                                            (
                                                self._processed_bytes
                                                / self._listener.subsize
                                            )
                                            * 100,
                                            99.9,
                                        )
                                        # Calculate ETA based on current speed and remaining bytes
                                        remaining_bytes = max(
                                            0,
                                            self._listener.subsize
                                            - self._processed_bytes,
                                        )
                                        if self._speed_raw > 0:
                                            self._eta_raw = (
                                                remaining_bytes / self._speed_raw
                                            )
                                        else:
                                            self._eta_raw = 0
                                else:
                                    # For non-trim operations, use the original byte-based progress
                                    self._progress_raw = min(
                                        (
                                            self._processed_bytes
                                            / self._listener.subsize
                                        )
                                        * 100,
                                        99.9,
                                    )
                                    # Calculate ETA based on current speed and remaining bytes
                                    remaining_bytes = max(
                                        0,
                                        self._listener.subsize
                                        - self._processed_bytes,
                                    )
                                    if self._speed_raw > 0:
                                        self._eta_raw = (
                                            remaining_bytes / self._speed_raw
                                        )
                                    else:
                                        self._eta_raw = 0
                            except Exception as e:
                                LOGGER.debug(f"Error calculating trim progress: {e}")

                    elif key == "speed":
                        self._time_rate = max(0.1, float(value.strip("x")))
                    elif key == "out_time":
                        self._processed_time = (
                            time_to_seconds(value) + self._last_processed_time
                        )
                        try:
                            # Only use time-based progress if we don't have a better byte-based calculation
                            if not (
                                hasattr(self._listener, "subsize")
                                and self._listener.subsize > 0
                            ):
                                self._progress_raw = (
                                    self._processed_time / self._total_time * 100
                                )
                                self._eta_raw = (
                                    self._total_time - self._processed_time
                                ) / self._time_rate
                        except Exception:
                            self._progress_raw = 0
                            self._eta_raw = 0
            await sleep(0.05)

    async def ffmpeg_cmds(self, ffmpeg, f_path):
        self.clear()
        self._total_time = (await get_media_info(f_path))[0]
        base_name, ext = ospath.splitext(f_path)
        dir, base_name = base_name.rsplit("/", 1)

        # Check for -del flag to delete original files after processing
        delete_files = False
        if "-del" in ffmpeg:
            ffmpeg.remove("-del")
            delete_files = True
            LOGGER.debug(
                "Detected -del flag, will delete original files after processing"
            )

        # Replace 'ffmpeg' with 'xtra' as the command name
        if ffmpeg and ffmpeg[0] == "ffmpeg":
            ffmpeg[0] = "xtra"

        # Normal case: command is a list of arguments
        if "-i" not in ffmpeg:
            LOGGER.warning(f"FFmpeg command missing -i parameter: {ffmpeg}")
            # Add the input parameter using the provided file path
            ffmpeg.extend(["-i", f_path])

        # Check if this is a trim command (which typically has a .trim extension in the output)
        is_trim_command = False
        for item in ffmpeg:
            if isinstance(item, str) and ".trim" in item:
                is_trim_command = True
                LOGGER.debug(f"Detected trim command: {' '.join(ffmpeg)}")
                break

        # Find all output files in the command
        indices = [
            index
            for index, item in enumerate(ffmpeg)
            if item.startswith("mltb") or item == "mltb"
        ]

        # If no mltb placeholders are found and this is a trim command,
        # we need to find the output file in the command
        if not indices and is_trim_command and len(ffmpeg) > 2:
            # For trim commands, the output file is typically after the input file
            # and before any options that start with "-"
            output_file = None

            # First, try to find a file with .trim. in the name
            for i, arg in enumerate(ffmpeg):
                if (
                    isinstance(arg, str)
                    and ".trim." in arg
                    and not arg.startswith("-")
                ):
                    output_file = arg
                    LOGGER.debug(
                        f"Found output file with .trim. in name: {output_file}"
                    )
                    break

            # If that didn't work, look for the last argument that doesn't start with "-"
            # and is after the input file
            if not output_file:
                input_index = -1
                for i, arg in enumerate(ffmpeg):
                    if arg == "-i" and i + 1 < len(ffmpeg):
                        input_index = i + 1
                        break

                if input_index >= 0:
                    for i in range(input_index + 1, len(ffmpeg)):
                        if not ffmpeg[i].startswith("-") and "." in ffmpeg[i]:
                            output_file = ffmpeg[i]

                    if output_file:
                        LOGGER.debug(
                            f"Found output file after input file: {output_file}"
                        )

            # If we still don't have an output file, check if the second-to-last argument
            # looks like a file path (before the -y flag)
            if not output_file and len(ffmpeg) >= 2 and ffmpeg[-1] == "-y":
                if not ffmpeg[-2].startswith("-") and "." in ffmpeg[-2]:
                    output_file = ffmpeg[-2]
                    LOGGER.debug(f"Found output file before -y flag: {output_file}")

            # If we found an output file, add it to the outputs list
            if output_file:
                LOGGER.debug(f"Using identified output file: {output_file}")
                outputs = [output_file]
            else:
                LOGGER.warning(
                    f"Could not identify output file in trim command: {' '.join(ffmpeg)}"
                )
                outputs = []
        else:
            # Process mltb placeholders
            outputs = []
            for index in indices:
                output_file = ffmpeg[index]
                if output_file != "mltb" and output_file.startswith("mltb"):
                    bo, oext = ospath.splitext(output_file)
                    if oext:
                        if ext == oext:
                            prefix = f"ffmpeg{index}." if bo == "mltb" else ""
                        else:
                            prefix = ""
                        ext = ""
                    else:
                        prefix = ""
                else:
                    prefix = f"ffmpeg{index}."
                output = (
                    f"{dir}/{prefix}{output_file.replace('mltb', base_name)}{ext}"
                )
                outputs.append(output)
                ffmpeg[index] = output

            # Log the identified output files
            LOGGER.debug(
                f"Identified output files from mltb placeholders: {outputs}"
            )

        if self._listener.is_cancelled:
            return False

        # Save the original file size for comparison
        original_file_size = 0
        try:
            if await aiopath.exists(f_path):
                original_file_size = await aiopath.getsize(f_path)
                LOGGER.debug(f"Original file size: {original_file_size} bytes")
        except Exception as e:
            LOGGER.error(f"Error getting original file size: {e}")

        # Execute the command
        self._listener.subproc = await create_subprocess_exec(
            *ffmpeg,
            stdout=PIPE,
            stderr=PIPE,
        )

        await self._ffmpeg_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode

        if self._listener.is_cancelled:
            return False

        # Check if the command was successful
        if code == 0:
            # Check if all output files exist and have valid content before deleting the original
            all_outputs_valid = True
            total_output_size = 0

            # First check if any output files exist
            any_outputs_exist = False
            for output in outputs:
                if await aiopath.exists(output):
                    any_outputs_exist = True
                    break

            if not any_outputs_exist:
                LOGGER.error(
                    "FFmpeg command completed successfully but no output files were created"
                )
                return False

            # Now check if all output files are valid
            for output in outputs:
                if not await aiopath.exists(output):
                    all_outputs_valid = False
                    LOGGER.error(f"Output file does not exist: {output}")
                    break

                # Check if the output file has valid content (non-zero size)
                try:
                    output_size = await aiopath.getsize(output)
                    total_output_size += output_size

                    if output_size == 0:
                        all_outputs_valid = False
                        LOGGER.error(
                            f"Output file exists but has zero size: {output}"
                        )
                        break
                    LOGGER.debug(
                        f"Output file is valid with size {output_size} bytes: {output}"
                    )
                except Exception as e:
                    all_outputs_valid = False
                    LOGGER.error(f"Error checking output file size: {e}")
                    break

            # Additional check: make sure the total output size is reasonable
            # (at least 1% of the original file size for most operations)
            if (
                all_outputs_valid
                and original_file_size > 0
                and total_output_size < (original_file_size * 0.01)
            ):
                # For trim operations, the output can be much smaller than the original
                # So we'll only log a warning but still consider it valid
                LOGGER.warning(
                    f"Output files are much smaller than the original file: {total_output_size} vs {original_file_size} bytes"
                )

            # If -del flag was used and all outputs are valid, delete original files
            if delete_files and all_outputs_valid and await aiopath.exists(f_path):
                try:
                    await remove(f_path)
                    LOGGER.info(f"Deleted original file after processing: {f_path}")
                except Exception as e:
                    LOGGER.error(f"Error deleting original file: {e}")

            # Only return the outputs if they are valid
            if all_outputs_valid:
                return outputs
            LOGGER.error("FFmpeg command completed but output files are not valid")
            return False
        if code == -9:
            self._listener.is_cancelled = True
            return False
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(
            f"{stderr}. Something went wrong while running ffmpeg cmd, mostly file requires different/specific arguments. Path: {f_path}",
        )
        for op in outputs:
            if await aiopath.exists(op):
                await remove(op)
        return False

    async def metadata_watermark_cmds(self, ffmpeg, f_path):
        self.clear()

        # Check for any temporary metadata files that might have been created
        meta_file = f"{f_path}.meta"

        # Special case for document files - check if the command is a dummy command
        if (
            ffmpeg
            and len(ffmpeg) >= 2
            and ffmpeg[0] == "echo"
            and "apply_document_metadata" in ffmpeg[1]
        ):
            # This is a document file that should be processed with apply_document_metadata
            LOGGER.info(
                f"Processing document file with apply_document_metadata: {f_path}"
            )

            # Get the original file path (remove .temp extension if present)
            original_file = f_path
            if ".temp" in original_file:
                original_file = original_file.replace(".temp", "")

            # Use the apply_document_metadata function from this module

            # Get metadata from listener
            try:
                title = self._listener.user_dict.get("metadata-title", "")
                author = self._listener.user_dict.get("metadata-author", "")
                comment = self._listener.user_dict.get("metadata-comment", "")
            except AttributeError:
                # For testing purposes, use default values
                LOGGER.info("Using default metadata values for testing")
                title = "Test Title"
                author = "Test Author"
                comment = "Test Comment"

            # Apply metadata
            success = await apply_document_metadata(
                original_file, title, author, comment
            )

            if success:
                LOGGER.info(
                    f"Successfully applied metadata to document file: {original_file}"
                )
                return True
            LOGGER.error(
                f"Failed to apply metadata to document file: {original_file}"
            )
            return False

        # Special case for subtitle watermarking - ffmpeg will be None
        if ffmpeg is None:
            # This is a subtitle file that was processed directly without FFmpeg
            # The temp_file is in f_path, and we need to replace the original file with it
            temp_file = f_path
            original_file = temp_file.replace(".temp", "")

            try:
                # Check if the temp file exists
                if await aiopath.exists(temp_file):
                    # Replace the original file with the watermarked version
                    import shutil

                    shutil.move(temp_file, original_file)
                    LOGGER.info(
                        f"Replaced original subtitle file with watermarked version: {original_file}"
                    )

                    # Clean up any temporary metadata files
                    if await aiopath.exists(meta_file):
                        try:
                            await remove(meta_file)
                            LOGGER.info(
                                f"Removed temporary metadata file: {meta_file}"
                            )
                        except Exception as e:
                            LOGGER.warning(
                                f"Failed to remove temporary metadata file {meta_file}: {e}"
                            )

                    return True
                LOGGER.error(f"Temp subtitle file not found: {temp_file}")
                return False
            except Exception as e:
                LOGGER.error(f"Error replacing subtitle file: {e}")

                # Clean up any temporary metadata files even if there was an error
                if await aiopath.exists(meta_file):
                    try:
                        await remove(meta_file)
                        LOGGER.info(
                            f"Removed temporary metadata file after error: {meta_file}"
                        )
                    except Exception as e2:
                        LOGGER.warning(
                            f"Failed to remove temporary metadata file {meta_file} after error: {e2}"
                        )

                return False

        # Normal case with FFmpeg command
        self._total_time = (await get_media_info(f_path))[0]
        if self._listener.is_cancelled:
            return False

        # Check for -del flag to delete original files after processing
        delete_files = False
        if "-del" in ffmpeg:
            ffmpeg.remove("-del")
            delete_files = True
            LOGGER.debug(
                "Detected -del flag, will delete original files after processing"
            )

        # Replace 'ffmpeg' with 'xtra' as the command name
        if ffmpeg and ffmpeg[0] == "ffmpeg":
            ffmpeg[0] = "xtra"

        # Execute the command
        self._listener.subproc = await create_subprocess_exec(
            *ffmpeg,
            stdout=PIPE,
            stderr=PIPE,
        )

        await self._ffmpeg_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode

        # Clean up any temporary metadata files
        if await aiopath.exists(meta_file):
            try:
                await remove(meta_file)
                LOGGER.info(f"Removed temporary metadata file: {meta_file}")
            except Exception as e:
                LOGGER.warning(
                    f"Failed to remove temporary metadata file {meta_file}: {e}"
                )

        if self._listener.is_cancelled:
            return False
        if code == 0:
            # Save the original file size for comparison
            original_file_size = 0
            try:
                if await aiopath.exists(f_path):
                    original_file_size = await aiopath.getsize(f_path)
                    LOGGER.debug(f"Original file size: {original_file_size} bytes")
            except Exception as e:
                LOGGER.error(f"Error getting original file size: {e}")

            # Check if the operation produced valid output files
            # For metadata operations, we need to check if the output file exists and has valid content
            output_valid = True

            # For most metadata operations, the output is written back to the original file
            # So we need to check if the original file still exists and has valid content
            if await aiopath.exists(f_path):
                try:
                    output_size = await aiopath.getsize(f_path)
                    if output_size == 0:
                        output_valid = False
                        LOGGER.error(
                            f"Output file exists but has zero size: {f_path}"
                        )
                    else:
                        LOGGER.debug(
                            f"Output file is valid with size {output_size} bytes: {f_path}"
                        )

                        # Additional check: make sure the output size is reasonable
                        # (at least 1% of the original file size for most operations)
                        if original_file_size > 0 and output_size < (
                            original_file_size * 0.01
                        ):
                            # For some operations, the output can be much smaller than the original
                            # So we'll only log a warning but still consider it valid
                            LOGGER.warning(
                                f"Output file is much smaller than the original file: {output_size} vs {original_file_size} bytes"
                            )
                except Exception as e:
                    output_valid = False
                    LOGGER.error(f"Error checking output file size: {e}")
            else:
                output_valid = False
                LOGGER.error(f"Output file does not exist: {f_path}")

            # Handle -del flag if needed, but only if the operation was successful and produced valid output
            if delete_files and output_valid and await aiopath.exists(f_path):
                try:
                    await remove(f_path)
                    LOGGER.info(f"Deleted original file after processing: {f_path}")
                except Exception as e:
                    LOGGER.error(f"Error deleting original file: {e}")

            # Return success only if the output is valid
            return output_valid
        if code == -9:
            self._listener.is_cancelled = True
            return False
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(
            f"{stderr}. Something went wrong while running ffmpeg cmd, mostly file requires different/specific arguments. Path: {f_path}",
        )
        return False

    async def convert_video(
        self, video_file, ext, retry=False, second_retry=False, delete_original=False
    ):
        self.clear()

        # Ensure video_file is an absolute path
        video_file = ospath.abspath(video_file)

        # Check if the file exists
        if not await aiopath.exists(video_file):
            LOGGER.error(f"Video file does not exist: {video_file}")
            return False

        self._total_time = (await get_media_info(video_file))[0]

        # For settings-based configs, check if ext is None or "none" (case-insensitive)
        # This check is only for settings-based configs, not for command-line flags
        # Command-line flags are already validated before calling this function
        if not ext or ext.lower() == "none":
            LOGGER.info(
                f"Video conversion format is empty or 'none', skipping conversion for: {video_file}"
            )
            return video_file

        base_name = ospath.splitext(video_file)[0]
        output = f"{base_name}.{ext}"

        LOGGER.debug(
            f"Input file: {video_file} (exists: {await aiopath.exists(video_file)})"
        )
        LOGGER.debug(f"Output file: {output}")

        # Check if the output file already exists and is the same as input
        if output == video_file:
            LOGGER.info(f"Output file is the same as input file: {video_file}")
            return video_file

        # Log if we're going to delete the original file after conversion
        if delete_original:
            LOGGER.debug(f"Will delete original file after conversion: {video_file}")

        # Get custom video settings from listener if available
        video_codec = getattr(self._listener, "convert_video_codec", None)
        # Removed unused variable: video_quality
        video_crf = getattr(self._listener, "convert_video_crf", None)
        video_preset = getattr(self._listener, "convert_video_preset", None)
        # Removed unused variable: maintain_quality

        # Check if custom settings are valid (not None or "none")
        has_custom_codec = video_codec and video_codec.lower() != "none"
        # Removed unused variable: has_custom_quality
        has_custom_crf = video_crf and video_crf != 0
        has_custom_preset = video_preset and video_preset.lower() != "none"

        # Special handling for WebM format
        if ext == "webm":
            # Base command
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                video_file,
                "-map",
                "0:v:0",  # Take only the first video stream
                "-map",
                "0:a:0?",  # Take the first audio stream if it exists
            ]

            # Add video codec
            if has_custom_codec:
                cmd.extend(["-c:v", video_codec])
            else:
                cmd.extend(["-c:v", "libvpx-vp9"])  # Use VP9 codec for video

            # Add audio codec
            cmd.extend(["-c:a", "libopus"])  # Use Opus codec for audio

            # Add video bitrate
            cmd.extend(["-b:v", "1M"])  # Video bitrate

            # Add audio bitrate
            cmd.extend(["-b:a", "128k"])  # Audio bitrate

            # Add pixel format
            cmd.extend(["-pix_fmt", "yuv420p"])  # Pixel format

            # Add scale filter
            cmd.extend(
                ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
            )  # Ensure even dimensions

            # Add CRF if specified
            if has_custom_crf:
                cmd.extend(["-crf", str(video_crf)])

            # Add preset if specified
            if has_custom_preset:
                cmd.extend(["-preset", video_preset])

            # Add threads
            cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

            # Add output file
            cmd.append(output)
        elif second_retry:
            # For complex files with multiple streams, use only video and audio streams
            # Special handling for anime files with multiple streams
            if ext == "mp4":
                # Base command
                cmd = [
                    "xtra",  # Using xtra instead of ffmpeg
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-i",
                    video_file,
                    "-map",
                    "0:v:0",  # Take only the first video stream
                    "-map",
                    "0:a:0?",  # Take the first audio stream if it exists
                ]

                # Add video codec
                if has_custom_codec:
                    cmd.extend(["-c:v", video_codec])
                else:
                    cmd.extend(["-c:v", "libx264"])

                # Add audio codec
                cmd.extend(["-c:a", "aac"])

                # Add pixel format
                cmd.extend(["-pix_fmt", "yuv420p"])  # Ensure compatible pixel format

                # Add scale filter
                cmd.extend(
                    ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
                )  # Ensure even dimensions

                # Add preset
                if has_custom_preset:
                    cmd.extend(["-preset", video_preset])
                else:
                    cmd.extend(
                        ["-preset", "medium"]
                    )  # Balance between speed and quality

                # Add CRF
                if has_custom_crf:
                    cmd.extend(["-crf", str(video_crf)])
                else:
                    cmd.extend(["-crf", "23"])  # Quality level (lower is better)

                # Add threads
                cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                # Add output file
                cmd.append(output)
            else:
                # For MKV, we can include subtitles
                # Base command
                cmd = [
                    "xtra",  # Using xtra instead of ffmpeg
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-i",
                    video_file,
                    "-map",
                    "0:v:0",  # Take only the first video stream
                    "-map",
                    "0:a:0?",  # Take the first audio stream if it exists
                    "-map",
                    "0:s:0?",  # Take the first subtitle stream if it exists
                ]

                # Add video codec
                if has_custom_codec:
                    cmd.extend(["-c:v", video_codec])
                else:
                    cmd.extend(["-c:v", "libx264"])

                # Add audio codec
                cmd.extend(["-c:a", "aac"])

                # Add subtitle codec
                cmd.extend(["-c:s", "copy"])  # Copy subtitles

                # Add pixel format
                cmd.extend(["-pix_fmt", "yuv420p"])  # Ensure compatible pixel format

                # Add scale filter
                cmd.extend(
                    ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
                )  # Ensure even dimensions

                # Add preset
                if has_custom_preset:
                    cmd.extend(["-preset", video_preset])
                else:
                    cmd.extend(
                        ["-preset", "medium"]
                    )  # Balance between speed and quality

                # Add CRF
                if has_custom_crf:
                    cmd.extend(["-crf", str(video_crf)])
                else:
                    cmd.extend(["-crf", "23"])  # Quality level (lower is better)

                # Add threads
                cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

                # Add output file
                cmd.append(output)
        elif retry:
            # Base command
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                video_file,
                "-map",
                "0",
                "-ignore_unknown",
            ]

            # Add video codec
            if has_custom_codec:
                cmd.extend(["-c:v", video_codec])
            else:
                cmd.extend(["-c:v", "libx264"])

            # Add audio codec
            cmd.extend(["-c:a", "aac"])

            # Add pixel format
            cmd.extend(["-pix_fmt", "yuv420p"])  # Ensure compatible pixel format

            # Add scale filter
            cmd.extend(
                ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
            )  # Ensure even dimensions

            # Add CRF if specified
            if has_custom_crf:
                cmd.extend(["-crf", str(video_crf)])
            else:
                cmd.extend(["-crf", "23"])  # Default CRF

            # Add preset if specified
            if has_custom_preset:
                cmd.extend(["-preset", video_preset])
            else:
                cmd.extend(["-preset", "medium"])  # Default preset

            # Add threads
            cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

            # Add output file
            cmd.append(output)

            # Add subtitle codec based on output format
            if ext == "mp4":
                cmd[21:21] = ["-c:s", "mov_text"]
            elif ext == "mkv":
                cmd[21:21] = ["-c:s", "ass"]
            else:
                cmd[21:21] = ["-c:s", "copy"]
        # First try with simple copy (faster if format is compatible)
        # But if user has specified custom settings, we'll use them instead of copy
        elif has_custom_codec or has_custom_crf or has_custom_preset:
            # Base command
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                video_file,
                "-map",
                "0",
                "-ignore_unknown",
            ]

            # Add video codec
            if has_custom_codec:
                cmd.extend(["-c:v", video_codec])
            else:
                cmd.extend(["-c:v", "copy"])

            # Add audio codec (always copy in first attempt)
            cmd.extend(["-c:a", "copy"])

            # Add subtitle codec (always copy in first attempt)
            cmd.extend(["-c:s", "copy"])

            # Add CRF if specified and not using copy codec
            if has_custom_crf and has_custom_codec and video_codec.lower() != "copy":
                cmd.extend(["-crf", str(video_crf)])

            # Add preset if specified and not using copy codec
            if (
                has_custom_preset
                and has_custom_codec
                and video_codec.lower() != "copy"
            ):
                cmd.extend(["-preset", video_preset])

            # Add threads
            cmd.extend(["-threads", f"{max(1, cpu_no // 2)}"])

            # Add output file
            cmd.append(output)
        else:
            # Use simple copy for all streams
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                video_file,
                "-map",
                "0",
                "-ignore_unknown",
                "-c",
                "copy",
                "-threads",
                f"{max(1, cpu_no // 2)}",
                output,
            ]

        if self._listener.is_cancelled:
            return False

        # Execute the command
        self._listener.subproc = await create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        await self._ffmpeg_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode

        if self._listener.is_cancelled:
            return False
        if code == 0:
            # If delete_original is True, delete the original file after successful conversion
            if (
                delete_original
                and await aiopath.exists(video_file)
                and video_file != output
            ):
                try:
                    LOGGER.warning(
                        f"Deleting original file after conversion: {video_file}"
                    )
                    await remove(video_file)
                    LOGGER.info(f"Successfully deleted original file: {video_file}")
                except Exception as e:
                    LOGGER.error(
                        f"Error deleting original file in convert_video: {e}"
                    )
                    # Try again with a different approach
                    try:
                        import os

                        LOGGER.warning(
                            f"Trying alternative method to delete file: {video_file}"
                        )
                        os.remove(video_file)
                        LOGGER.info(
                            f"Successfully deleted original file using os.remove: {video_file}"
                        )
                    except Exception as e2:
                        LOGGER.error(f"Second attempt to delete file failed: {e2}")
            return output
        if code == -9:
            self._listener.is_cancelled = True
            return False
        if await aiopath.exists(output):
            await remove(output)

        # If first attempt failed and we're not in retry mode, try with transcoding
        if not retry:
            LOGGER.info(
                f"Copy codec failed for {video_file}, trying with transcoding"
            )
            LOGGER.debug(
                f"Passing delete_original={delete_original} to retry attempt"
            )
            return await self.convert_video(
                video_file, ext, True, False, delete_original
            )

        # If first retry failed, try with only video and audio streams
        if retry and not second_retry:
            LOGGER.info(
                f"Full stream transcoding failed for {video_file}, trying with only video and audio streams"
            )
            LOGGER.debug(
                f"Passing delete_original={delete_original} to second retry attempt"
            )
            return await self.convert_video(
                video_file, ext, True, True, delete_original
            )

        # If we're in second retry mode and it's a WebM conversion that failed, try with VP8
        if second_retry and ext == "webm":
            LOGGER.info(f"VP9 codec failed for {video_file}, trying with VP8")
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                video_file,
                "-map",
                "0:v:0",  # Take only the first video stream
                "-map",
                "0:a:0?",  # Take the first audio stream if it exists
                "-c:v",
                "libvpx",  # Use VP8 codec for video
                "-c:a",
                "libvorbis",  # Use Vorbis codec for audio
                "-b:v",
                "1M",  # Video bitrate
                "-b:a",
                "128k",  # Audio bitrate
                "-pix_fmt",
                "yuv420p",  # Pixel format
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
                "-threads",
                f"{max(1, cpu_no // 2)}",
                output,
            ]

            self._listener.subproc = await create_subprocess_exec(
                *cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            await self._ffmpeg_progress()
            _, stderr = await self._listener.subproc.communicate()
            code = self._listener.subproc.returncode

            if self._listener.is_cancelled:
                return False
            if code == 0:
                # If delete_original is True, delete the original file after successful conversion
                if (
                    delete_original
                    and await aiopath.exists(video_file)
                    and video_file != output
                ):
                    try:
                        await remove(video_file)
                        LOGGER.info(
                            f"Deleted original file after WebM VP8 conversion: {video_file}"
                        )
                    except Exception as e:
                        LOGGER.error(
                            f"Error deleting original file after WebM VP8 conversion: {e}"
                        )
                return output
            if code == -9:
                self._listener.is_cancelled = True
                return False
            if await aiopath.exists(output):
                await remove(output)

        # If all attempts failed, log the error and return False
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(
            f"{stderr}. Something went wrong while converting video, mostly file need specific codec. Path: {video_file}",
        )
        return False

    async def convert_audio(
        self, audio_file, ext, retry=False, delete_original=False
    ):
        self.clear()

        # Ensure audio_file is an absolute path
        audio_file = ospath.abspath(audio_file)

        # Check if the file exists
        if not await aiopath.exists(audio_file):
            LOGGER.error(f"Audio file does not exist: {audio_file}")
            return False

        self._total_time = (await get_media_info(audio_file))[0]

        # For settings-based configs, check if ext is None or "none" (case-insensitive)
        # This check is only for settings-based configs, not for command-line flags
        # Command-line flags are already validated before calling this function
        if not ext or ext.lower() == "none":
            LOGGER.info(
                f"Audio conversion format is empty or 'none', skipping conversion for: {audio_file}"
            )
            return audio_file

        base_name = ospath.splitext(audio_file)[0]
        output = f"{base_name}.{ext}"

        LOGGER.debug(
            f"Input file: {audio_file} (exists: {await aiopath.exists(audio_file)})"
        )
        LOGGER.debug(f"Output file: {output}")

        # Check if the output file already exists and is the same as input
        if output == audio_file:
            LOGGER.info(f"Output file is the same as input file: {audio_file}")
            return audio_file

        # Get custom audio settings from listener if available
        audio_codec = getattr(self._listener, "convert_audio_codec", None)
        audio_bitrate = getattr(self._listener, "convert_audio_bitrate", None)
        audio_channels = getattr(self._listener, "convert_audio_channels", None)
        audio_sampling = getattr(self._listener, "convert_audio_sampling", None)
        audio_volume = getattr(self._listener, "convert_audio_volume", None)

        # Check if custom settings are valid (not None or "none")
        has_custom_codec = audio_codec and audio_codec.lower() != "none"
        has_custom_bitrate = audio_bitrate and audio_bitrate.lower() != "none"
        has_custom_channels = audio_channels and audio_channels != 0
        has_custom_sampling = audio_sampling and audio_sampling != 0
        has_custom_volume = audio_volume and audio_volume != 0.0

        # Configure codec based on output format or custom settings
        if has_custom_codec:
            codec = ["-c:a", audio_codec]
        elif ext == "mp3":
            codec = ["-c:a", "libmp3lame", "-q:a", "2"]
        elif ext == "m4a":
            codec = ["-c:a", "aac", "-b:a", "192k"]
        elif ext == "opus":
            codec = ["-c:a", "libopus", "-b:a", "128k"]
        elif ext == "ogg":
            codec = ["-c:a", "libvorbis", "-q:a", "4"]
        elif ext == "flac":
            codec = ["-c:a", "flac"]
        elif ext == "wav":
            codec = ["-c:a", "pcm_s16le"]
        else:
            # Default to AAC for unknown formats
            codec = ["-c:a", "aac", "-b:a", "192k"]

        # Add custom bitrate if specified
        if has_custom_bitrate:
            # Remove any existing bitrate settings
            for i in range(len(codec) - 1):
                if codec[i] == "-b:a":
                    codec.pop(i)
                    codec.pop(i)  # Remove the value too
                    break
            codec.extend(["-b:a", audio_bitrate])

        # Add custom channels if specified
        if has_custom_channels:
            codec.extend(["-ac", str(audio_channels)])

        # Add custom sampling rate if specified
        if has_custom_sampling:
            codec.extend(["-ar", str(audio_sampling)])

        # Add custom volume if specified
        if has_custom_volume:
            codec.extend(["-filter:a", f"volume={audio_volume}"])

        if retry:
            # If we're retrying, use the codec with more options
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                audio_file,
                "-map",
                "0:a:0",  # Take only the first audio stream
                "-threads",
                f"{max(1, cpu_no // 2)}",
            ]
            cmd.extend(codec)
            cmd.append(output)
        else:
            # First try with simple copy (faster if format is compatible)
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                audio_file,
                "-c:a",
                "copy",
                "-threads",
                f"{max(1, cpu_no // 2)}",
                output,
            ]

        if self._listener.is_cancelled:
            return False

        # Execute the command
        self._listener.subproc = await create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        await self._ffmpeg_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode

        if self._listener.is_cancelled:
            return False
        if code == 0:
            # If delete_original is True, delete the original file after successful conversion
            if (
                delete_original
                and await aiopath.exists(audio_file)
                and audio_file != output
            ):
                try:
                    LOGGER.warning(
                        f"Deleting original file after conversion: {audio_file}"
                    )
                    await remove(audio_file)
                    LOGGER.info(f"Successfully deleted original file: {audio_file}")
                except Exception as e:
                    LOGGER.error(
                        f"Error deleting original file in convert_audio: {e}"
                    )
                    # Try again with a different approach
                    try:
                        import os

                        LOGGER.warning(
                            f"Trying alternative method to delete file: {audio_file}"
                        )
                        os.remove(audio_file)
                        LOGGER.info(
                            f"Successfully deleted original file using os.remove: {audio_file}"
                        )
                    except Exception as e2:
                        LOGGER.error(f"Second attempt to delete file failed: {e2}")
            return output
        if code == -9:
            self._listener.is_cancelled = True
            return False

        # If copy failed and we're not in retry mode, try with transcoding
        if not retry:
            if await aiopath.exists(output):
                await remove(output)
            LOGGER.info(
                f"Copy codec failed for {audio_file}, trying with transcoding"
            )
            LOGGER.debug(
                f"Passing delete_original={delete_original} to audio retry attempt"
            )
            return await self.convert_audio(audio_file, ext, True, delete_original)

        # If all attempts failed, log the error and return False
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(
            f"{stderr}. Something went wrong while converting audio, mostly file need specific codec. Path: {audio_file}",
        )
        if await aiopath.exists(output):
            await remove(output)
        return False

    async def convert_subtitle(
        self, subtitle_file, ext, retry=False, delete_original=False
    ):
        self.clear()

        # Ensure subtitle_file is an absolute path
        subtitle_file = ospath.abspath(subtitle_file)

        # Check if the file exists
        if not await aiopath.exists(subtitle_file):
            LOGGER.error(f"Subtitle file does not exist: {subtitle_file}")
            return False

        # For settings-based configs, check if ext is None or "none" (case-insensitive)
        if not ext or ext.lower() == "none":
            LOGGER.info(
                f"Subtitle conversion format is empty or 'none', skipping conversion for: {subtitle_file}"
            )
            return subtitle_file

        # Get file extension and base name
        file_ext = ospath.splitext(subtitle_file)[1].lower()
        output = f"{ospath.splitext(subtitle_file)[0]}.{ext}"

        LOGGER.debug(
            f"Input file: {subtitle_file} (exists: {await aiopath.exists(subtitle_file)})"
        )
        LOGGER.debug(f"Output file: {output}")

        # Get custom subtitle settings from listener if available
        subtitle_encoding = getattr(
            self._listener, "convert_subtitle_encoding", None
        )
        subtitle_language = getattr(
            self._listener, "convert_subtitle_language", None
        )

        # Check if custom settings are valid (not None or "none")
        has_custom_encoding = (
            subtitle_encoding and subtitle_encoding.lower() != "none"
        )
        has_custom_language = (
            subtitle_language and subtitle_language.lower() != "none"
        )

        # Determine input subtitle format based on file extension
        # This information is used for logging purposes
        input_format = ""
        if file_ext == ".srt":
            input_format = "srt"
        elif file_ext in [".ass", ".ssa"]:
            input_format = "ass"
        elif file_ext in [".vtt", ".webvtt"]:
            input_format = "webvtt"
        elif file_ext == ".sub":
            # For .sub files, we need to check if it's SubRip or MicroDVD format
            try:
                with open(subtitle_file, encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                if first_line.startswith("{") and "}" in first_line:
                    input_format = "microdvd"
                else:
                    input_format = "subviewer"
            except Exception:
                input_format = (
                    "subviewer"  # Default to subviewer if we can't determine
                )
        else:
            input_format = "unknown"

        LOGGER.debug(
            f"Detected subtitle format: {input_format} for file: {subtitle_file}"
        )

        # Build FFmpeg command
        cmd = [
            "xtra",  # Using xtra instead of ffmpeg
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
        ]

        # Add subtitle encoding if specified
        if has_custom_encoding:
            cmd.extend(["-sub_charenc", subtitle_encoding])

        # Add input file
        cmd.extend(["-i", subtitle_file])

        # Determine output format and codec
        if ext == "srt":
            cmd.extend(["-c:s", "srt"])
        elif ext in {"ass", "ssa"}:
            cmd.extend(["-c:s", "ass"])
        elif ext in {"vtt", "webvtt"}:
            cmd.extend(["-c:s", "webvtt"])
        else:
            # For other formats, let FFmpeg choose the appropriate codec
            cmd.extend(["-c:s", "copy"])

        # Add subtitle language if specified
        if has_custom_language:
            cmd.extend(["-metadata:s:s:0", f"language={subtitle_language}"])

        # Add threads and output file
        cmd.extend(["-threads", f"{max(1, cpu_no // 2)}", output])

        if self._listener.is_cancelled:
            return False

        # Execute the command
        self._listener.subproc = await create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        await self._ffmpeg_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode

        if code == 0:
            if delete_original and await aiopath.exists(output):
                try:
                    await remove(subtitle_file)
                    LOGGER.info(
                        f"Successfully deleted original file: {subtitle_file}"
                    )
                except Exception as e:
                    LOGGER.error(
                        f"Error deleting original file in convert_subtitle: {e}"
                    )
                    # Try again with a different approach
                    try:
                        LOGGER.warning(
                            f"Trying alternative method to delete file: {subtitle_file}"
                        )
                        os.remove(subtitle_file)
                        LOGGER.info(
                            f"Successfully deleted original file using os.remove: {subtitle_file}"
                        )
                    except Exception as e2:
                        LOGGER.error(f"Second attempt to delete file failed: {e2}")
            return output
        if code == -9:
            self._listener.is_cancelled = True
            return False

        # If conversion failed, log the error and return False
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(
            f"{stderr}. Something went wrong while converting subtitle. Path: {subtitle_file}",
        )
        if await aiopath.exists(output):
            await remove(output)
        return False

    async def convert_document(
        self, document_file, ext, retry=False, delete_original=False
    ):
        self.clear()

        # Ensure document_file is an absolute path
        document_file = ospath.abspath(document_file)

        # Check if the file exists
        if not await aiopath.exists(document_file):
            LOGGER.error(f"Document file does not exist: {document_file}")
            return False

        # For settings-based configs, check if ext is None or "none" (case-insensitive)
        if not ext or ext.lower() == "none":
            LOGGER.info(
                f"Document conversion format is empty or 'none', skipping conversion for: {document_file}"
            )
            return document_file

        # Get base name and output path
        output = f"{ospath.splitext(document_file)[0]}.{ext}"

        LOGGER.debug(
            f"Input file: {document_file} (exists: {await aiopath.exists(document_file)})"
        )
        LOGGER.debug(f"Output file: {output}")

        # Check if the output file already exists and is the same as input
        if output == document_file:
            LOGGER.info(f"Output file is the same as input file: {document_file}")
            return document_file

        # Check if we have libreoffice or unoconv for document conversion
        import shutil

        libreoffice_path = shutil.which("libreoffice")
        unoconv_path = shutil.which("unoconv")

        if not libreoffice_path and not unoconv_path:
            LOGGER.error(
                "Neither LibreOffice nor unoconv found for document conversion"
            )
            return document_file

        # Build conversion command
        if libreoffice_path:
            # Use LibreOffice for conversion
            cmd = [
                libreoffice_path,
                "--headless",
                "--convert-to",
                ext,
                "--outdir",
                ospath.dirname(document_file),
                document_file,
            ]

            # Execute the command
            try:
                process = await create_subprocess_exec(
                    *cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                )
                _, stderr = await process.communicate()
                code = process.returncode

                if code == 0:
                    # LibreOffice creates the output file with the same name but different extension
                    if await aiopath.exists(output):
                        if delete_original:
                            try:
                                await remove(document_file)
                                LOGGER.info(
                                    f"Successfully deleted original file: {document_file}"
                                )
                            except Exception as e:
                                LOGGER.error(
                                    f"Error deleting original file in convert_document: {e}"
                                )
                                # Try again with a different approach
                                try:
                                    LOGGER.warning(
                                        f"Trying alternative method to delete file: {document_file}"
                                    )
                                    os.remove(document_file)
                                    LOGGER.info(
                                        f"Successfully deleted original file using os.remove: {document_file}"
                                    )
                                except Exception as e2:
                                    LOGGER.error(
                                        f"Second attempt to delete file failed: {e2}"
                                    )
                        return output
                    LOGGER.error(f"Output file not found after conversion: {output}")
                    return document_file
                LOGGER.error(
                    f"LibreOffice conversion failed with code {code}: {stderr.decode()}"
                )
                return document_file
            except Exception as e:
                LOGGER.error(f"Error during LibreOffice conversion: {e}")
                return document_file
        elif unoconv_path:
            # Use unoconv for conversion
            cmd = [unoconv_path, "-f", ext, document_file]

            # Execute the command
            try:
                process = await create_subprocess_exec(
                    *cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                )
                _, stderr = await process.communicate()
                code = process.returncode

                if code == 0:
                    # unoconv creates the output file with the same name but different extension
                    if await aiopath.exists(output):
                        if delete_original:
                            try:
                                await remove(document_file)
                                LOGGER.info(
                                    f"Successfully deleted original file: {document_file}"
                                )
                            except Exception as e:
                                LOGGER.error(
                                    f"Error deleting original file in convert_document: {e}"
                                )
                                # Try again with a different approach
                                try:
                                    LOGGER.warning(
                                        f"Trying alternative method to delete file: {document_file}"
                                    )
                                    os.remove(document_file)
                                    LOGGER.info(
                                        f"Successfully deleted original file using os.remove: {document_file}"
                                    )
                                except Exception as e2:
                                    LOGGER.error(
                                        f"Second attempt to delete file failed: {e2}"
                                    )
                        return output
                    LOGGER.error(f"Output file not found after conversion: {output}")
                    return document_file
                LOGGER.error(
                    f"unoconv conversion failed with code {code}: {stderr.decode()}"
                )
                return document_file
            except Exception as e:
                LOGGER.error(f"Error during unoconv conversion: {e}")
                return document_file

        # If we reach here, conversion failed
        return document_file

    async def convert_archive(
        self, archive_file, ext, retry=False, delete_original=False
    ):
        self.clear()

        # Ensure archive_file is an absolute path
        archive_file = ospath.abspath(archive_file)

        # Check if the file exists
        if not await aiopath.exists(archive_file):
            LOGGER.error(f"Archive file does not exist: {archive_file}")
            return False

        # For settings-based configs, check if ext is None or "none" (case-insensitive)
        if not ext or ext.lower() == "none":
            LOGGER.info(
                f"Archive conversion format is empty or 'none', skipping conversion for: {archive_file}"
            )
            return archive_file

        # Get output path
        output = f"{ospath.splitext(archive_file)[0]}.{ext}"

        LOGGER.debug(
            f"Input file: {archive_file} (exists: {await aiopath.exists(archive_file)})"
        )
        LOGGER.debug(f"Output file: {output}")

        # Check if the output file already exists and is the same as input
        if output == archive_file:
            LOGGER.info(f"Output file is the same as input file: {archive_file}")
            return archive_file

        # Get custom archive settings from listener if available
        archive_level = getattr(self._listener, "convert_archive_level", None)
        archive_method = getattr(self._listener, "convert_archive_method", None)

        # Check if we have 7z for archive conversion
        import shutil

        sevenzip_path = shutil.which("7z")

        if not sevenzip_path:
            LOGGER.error("7z not found for archive conversion")
            return archive_file

        # Create a temporary directory for extraction
        temp_dir = f"{ospath.splitext(archive_file)[0]}_temp"
        await makedirs(temp_dir, exist_ok=True)

        try:
            # Step 1: Extract the archive to the temporary directory
            extract_cmd = [
                sevenzip_path,
                "x",  # Extract with full paths
                "-y",  # Yes to all prompts
                f"-o{temp_dir}",  # Output directory
                archive_file,
            ]

            extract_process = await create_subprocess_exec(
                *extract_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )
            _, stderr = await extract_process.communicate()
            extract_code = extract_process.returncode

            if extract_code != 0:
                LOGGER.error(f"Failed to extract archive: {stderr.decode()}")
                # Clean up temp directory
                await rmtree(temp_dir, ignore_errors=True)
                return archive_file

            # Step 2: Create a new archive in the desired format
            archive_cmd = [
                sevenzip_path,
                "a",  # Add to archive
                "-y",  # Yes to all prompts
            ]

            # Add compression level if specified
            if archive_level and archive_level.isdigit():
                archive_cmd.append(f"-mx={archive_level}")
            else:
                archive_cmd.append("-mx=5")  # Default compression level

            # Add compression method if specified
            if archive_method and archive_method.lower() != "none":
                archive_cmd.append(f"-m0={archive_method}")

            # Add output file and input directory
            archive_cmd.extend([output, f"{temp_dir}/*"])

            archive_process = await create_subprocess_exec(
                *archive_cmd,
                stdout=PIPE,
                stderr=PIPE,
            )
            _, stderr = await archive_process.communicate()
            archive_code = archive_process.returncode

            # Clean up temp directory
            await rmtree(temp_dir, ignore_errors=True)

            if archive_code != 0:
                LOGGER.error(f"Failed to create new archive: {stderr.decode()}")
                return archive_file

            # If successful and delete_original is True, delete the original file
            if delete_original and await aiopath.exists(output):
                try:
                    await remove(archive_file)
                    LOGGER.info(
                        f"Successfully deleted original file: {archive_file}"
                    )
                except Exception as e:
                    LOGGER.error(
                        f"Error deleting original file in convert_archive: {e}"
                    )
                    # Try again with a different approach
                    try:
                        LOGGER.warning(
                            f"Trying alternative method to delete file: {archive_file}"
                        )
                        import os

                        os.remove(archive_file)
                        LOGGER.info(
                            f"Successfully deleted original file using os.remove: {archive_file}"
                        )
                    except Exception as e2:
                        LOGGER.error(f"Second attempt to delete file failed: {e2}")

            return output

        except Exception as e:
            LOGGER.error(f"Error during archive conversion: {e}")
            # Clean up temp directory
            await rmtree(temp_dir, ignore_errors=True)
            return archive_file

    async def sample_video(self, video_file, sample_duration, part_duration):
        self.clear()
        self._total_time = sample_duration
        dir, name = video_file.rsplit("/", 1)
        output_file = f"{dir}/SAMPLE.{name}"
        segments = [(0, part_duration)]
        duration = (await get_media_info(video_file))[0]
        remaining_duration = duration - (part_duration * 2)
        parts = (sample_duration - (part_duration * 2)) // part_duration
        time_interval = remaining_duration // parts
        next_segment = time_interval
        for _ in range(parts):
            segments.append((next_segment, next_segment + part_duration))
            next_segment += time_interval
        segments.append((duration - part_duration, duration))

        filter_complex = ""
        for i, (start, end) in enumerate(segments):
            filter_complex += (
                f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]; "
            )
            filter_complex += (
                f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]; "
            )

        for i in range(len(segments)):
            filter_complex += f"[v{i}][a{i}]"

        filter_complex += f"concat=n={len(segments)}:v=1:a=1[vout][aout]"

        cmd = [
            "xtra",  # Using xtra instead of ffmpeg
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-i",
            video_file,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-threads",
            f"{max(1, cpu_no // 2)}",
            output_file,
        ]

        if self._listener.is_cancelled:
            return False

        # Execute the command
        self._listener.subproc = await create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        await self._ffmpeg_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode

        if self._listener.is_cancelled:
            return False
        if code == -9:
            self._listener.is_cancelled = True
            return False
        if code == 0:
            return output_file
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(
            f"{stderr}. Something went wrong while creating sample video, mostly file is corrupted. Path: {video_file}",
        )
        if await aiopath.exists(output_file):
            await remove(output_file)
        return False

    async def split(self, f_path, file_, parts, split_size):
        self.clear()
        multi_streams = True
        self._total_time = duration = (await get_media_info(f_path))[0]
        base_name, extension = ospath.splitext(file_)

        # Check if equal splits is enabled by checking if parts is a reasonable number
        # When equal splits is enabled, parts will typically be a small number (2-20)
        # When using regular split size, parts can be very large for big files
        # We also check if the listener has an equal_splits attribute that was set in proceed_split
        is_equal_splits = (
            hasattr(self._listener, "equal_splits_enabled")
            and self._listener.equal_splits_enabled
        )

        # If the attribute isn't set, fall back to the heuristic
        if not is_equal_splits:
            is_equal_splits = parts <= 20 and parts > 1

        # For equal splits, calculate the exact duration for each part
        if is_equal_splits and duration > 0:
            LOGGER.debug(f"Using equal splits mode with {parts} parts")
            # Calculate duration per part (in seconds)
            duration_per_part = duration / parts
            # Reserve some buffer for each part (3 seconds)
            duration_per_part -= 3
            LOGGER.debug(
                f"Each part will be approximately {duration_per_part:.2f} seconds"
            )

            # Process each part with exact duration
            for i in range(1, parts + 1):
                start_time = (i - 1) * (duration_per_part + 3)
                # For the last part, use the remaining duration
                end_time = duration if i == parts else i * (duration_per_part + 3)

                out_path = f_path.replace(
                    file_, f"{base_name}.part{i:03}{extension}"
                )

                # Use duration parameter instead of file size for equal splits
                cmd = [
                    "xtra",  # Using xtra instead of ffmpeg
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-ss",
                    str(start_time),
                    "-i",
                    f_path,
                    "-to",
                    str(end_time - start_time),  # Duration of this segment
                    "-map",
                    "0",
                    "-map_chapters",
                    "-1",
                    "-async",
                    "1",
                    "-strict",
                    "-2",
                    "-c",
                    "copy",
                    "-threads",
                    f"{max(1, cpu_no // 2)}",
                    out_path,
                ]

                # Process this part
                if self._listener.is_cancelled:
                    return False

                # Execute the command
                self._listener.subproc = await create_subprocess_exec(
                    *cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                )

                await self._ffmpeg_progress()
                _, stderr = await self._listener.subproc.communicate()
                code = self._listener.subproc.returncode

                if self._listener.is_cancelled:
                    return False
                if code == -9:
                    self._listener.is_cancelled = True
                    return False
                if code != 0:
                    try:
                        stderr = stderr.decode().strip()
                    except Exception:
                        stderr = "Unable to decode the error!"
                    with contextlib.suppress(Exception):
                        await remove(out_path)
                    LOGGER.warning(
                        f"{stderr}. Error splitting part {i}/{parts}. Path: {f_path}",
                    )
                    continue

                # Update progress
                self._last_processed_time += end_time - start_time
                self._last_processed_bytes += await get_path_size(out_path)

            return True
        # Use traditional file size-based splitting for non-equal splits
        LOGGER.info(f"Using traditional split with size: {split_size} bytes")
        # Get the appropriate Telegram limit based on premium status
        from bot.core.aeon_client import TgClient

        # Use the MAX_SPLIT_SIZE from TgClient which is already set based on premium status
        # This will be 4000 MiB for premium users and 2000 MiB for regular users
        telegram_limit = TgClient.MAX_SPLIT_SIZE

        # If split size is larger than Telegram's limit, reduce it with a safety margin
        # Use a 20 MiB safety margin to ensure we never exceed Telegram's limit
        safety_margin = 20 * 1024 * 1024  # 20 MiB
        safe_telegram_limit = telegram_limit - safety_margin

        if split_size > safe_telegram_limit:
            premium_status = "premium" if TgClient.IS_PREMIUM_USER else "non-premium"
            limit_in_gb = telegram_limit / (1024 * 1024 * 1024)
            safe_limit_in_gb = safe_telegram_limit / (1024 * 1024 * 1024)
            LOGGER.warning(
                f"Split size {split_size} exceeds Telegram's {limit_in_gb:.1f} GiB {premium_status} limit. Reducing to {safe_telegram_limit} bytes ({safe_limit_in_gb:.1f} GiB) with safety margin."
            )
            split_size = safe_telegram_limit

        # Apply an additional safety buffer for multi-part files
        if parts > 2:
            buffer_size = 5000000  # 5MB additional buffer for multi-part files
            LOGGER.debug(
                f"Applying additional buffer of {buffer_size} bytes for multi-part split"
            )
            split_size -= buffer_size
        start_time = 0
        i = 1
        while i <= parts or start_time < duration - 4:
            out_path = f_path.replace(file_, f"{base_name}.part{i:03}{extension}")
            cmd = [
                "xtra",  # Using xtra instead of ffmpeg
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-ss",
                str(start_time),
                "-i",
                f_path,
                "-fs",
                str(split_size),
                "-map",
                "0",
                "-map_chapters",
                "-1",
                "-async",
                "1",
                "-strict",
                "-2",
                "-c",
                "copy",
                "-threads",
                f"{max(1, cpu_no // 2)}",
                out_path,
            ]
            if not multi_streams:
                # Remove the mapping arguments (2 entries)
                del cmd[12]
                del cmd[12]
            if self._listener.is_cancelled:
                return False

            # Execute the command
            self._listener.subproc = await create_subprocess_exec(
                *cmd,
                stdout=PIPE,
                stderr=PIPE,
            )

            await self._ffmpeg_progress()
            _, stderr = await self._listener.subproc.communicate()
            code = self._listener.subproc.returncode

            if self._listener.is_cancelled:
                return False
            if code == -9:
                self._listener.is_cancelled = True
                return False
            if code != 0:
                try:
                    stderr = stderr.decode().strip()
                except Exception:
                    stderr = "Unable to decode the error!"
                with contextlib.suppress(Exception):
                    await remove(out_path)
                if multi_streams:
                    LOGGER.warning(
                        f"{stderr}. Retrying without map, -map 0 not working in all situations. Path: {f_path}",
                    )
                    multi_streams = False
                    continue
                LOGGER.warning(
                    f"{stderr}. Unable to split this video, if it's size less than {self._listener.max_split_size} will be uploaded as it is. Path: {f_path}",
                )
                return False
            out_size = await aiopath.getsize(out_path)
            # Check against both max_split_size and Telegram's limit (based on premium status)
            from bot.core.aeon_client import TgClient

            # Use the MAX_SPLIT_SIZE from TgClient which is already set based on premium status
            telegram_limit = TgClient.MAX_SPLIT_SIZE
            effective_limit = min(self._listener.max_split_size, telegram_limit)

            if out_size > effective_limit:
                # Calculate a more appropriate reduction based on the overage percentage
                overage = out_size - effective_limit
                overage_percent = overage / effective_limit

                # More aggressive reduction for files that exceed Telegram's limit
                if out_size > telegram_limit:
                    # If we're over Telegram's limit, use a much larger buffer
                    reduction = overage + 20000000  # 20MB extra buffer
                    premium_status = (
                        "premium" if TgClient.IS_PREMIUM_USER else "non-premium"
                    )
                    limit_in_gb = telegram_limit / (1024 * 1024 * 1024)
                    LOGGER.warning(
                        f"Part size is {out_size} bytes ({round(out_size / 1024 / 1024, 2)} MB), which exceeds Telegram's {limit_in_gb:.1f} GiB {premium_status} limit. "
                        f"Reducing split size by {round(reduction / 1024 / 1024, 2)} MB for next attempt. Path: {f_path}",
                    )
                else:
                    # Adjust reduction based on overage percentage
                    if overage_percent > 0.2:  # If more than 20% over
                        reduction = overage + 10000000  # 10MB extra buffer
                    else:
                        reduction = overage + 5000000  # 5MB extra buffer

                    LOGGER.warning(
                        f"Part size is {out_size} bytes ({round(out_size / 1024 / 1024, 2)} MB), which exceeds max split size. "
                        f"Reducing split size by {round(reduction / 1024 / 1024, 2)} MB for next attempt. Path: {f_path}",
                    )

                split_size -= reduction
                await remove(out_path)
                continue
            lpd = (await get_media_info(out_path))[0]
            if lpd == 0:
                LOGGER.error(
                    f"Something went wrong while splitting, mostly file is corrupted. Path: {f_path}",
                )
                break
            if duration == lpd:
                LOGGER.warning(
                    f"This file has been splitted with default stream and audio, so you will only see one part with less size from orginal one because it doesn't have all streams and audios. This happens mostly with MKV videos. Path: {f_path}",
                )
                break
            if lpd <= 3:
                await remove(out_path)
                break
            self._last_processed_time += lpd
            self._last_processed_bytes += out_size
            start_time += lpd - 3
            i += 1

        return True


async def apply_document_metadata(file_path, title=None, author=None, comment=None):
    """Apply metadata to document files like PDF using appropriate tools.

    Args:
        file_path: Path to the document file
        title: Title metadata to apply
        author: Author metadata to apply
        comment: Comment metadata to apply

    Returns:
        bool: True if metadata was successfully applied, False otherwise
    """
    if not file_path or not await aiopath.exists(file_path):
        LOGGER.error(f"File not found: {file_path}")
        return False

    # Skip if no metadata to apply
    if not title and not author and not comment:
        LOGGER.debug("No metadata provided, skipping")
        return True

    # Get file extension
    ext = os.path.splitext(file_path)[1].lower()

    # Create a temporary file for output
    temp_file = f"{file_path}.temp{ext}"

    # Handle different document types
    if ext == ".pdf":
        return await apply_pdf_metadata(file_path, temp_file, title, author, comment)
    if ext in [".epub", ".mobi", ".azw", ".azw3"]:
        return await apply_ebook_metadata(
            file_path, temp_file, title, author, comment
        )
    if ext in [
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
    ]:
        return await apply_office_metadata(
            file_path, temp_file, title, author, comment
        )
    if ext in [".txt", ".md", ".csv", ".rtf"]:
        return await apply_text_metadata(
            file_path, temp_file, title, author, comment
        )
    # Try exiftool for other document types
    return await apply_exiftool_metadata(
        file_path, temp_file, title, author, comment
    )


async def apply_pdf_metadata(
    file_path, temp_file, title=None, author=None, comment=None
):
    """Apply metadata to PDF files using pdftk or exiftool.

    Args:
        file_path: Path to the PDF file
        temp_file: Path to the temporary file
        title: Title metadata to apply
        author: Author metadata to apply
        comment: Comment metadata to apply

    Returns:
        bool: True if metadata was successfully applied, False otherwise
    """
    try:
        # Check if pdftk is available
        pdftk_check = await cmd_exec(["which", "pdftk"])

        if pdftk_check[0]:  # pdftk is available
            LOGGER.info(f"Using pdftk to apply metadata to {file_path}")

            # Create a temporary info file
            info_file = f"{file_path}.info"
            with open(info_file, "w") as f:
                if title:
                    f.write(f"InfoKey: Title\nInfoValue: {title}\n")
                if author:
                    f.write(f"InfoKey: Author\nInfoValue: {author}\n")
                if comment:
                    f.write(f"InfoKey: Subject\nInfoValue: {comment}\n")

            # Apply metadata
            cmd = ["pdftk", file_path, "update_info", info_file, "output", temp_file]

            result = await cmd_exec(cmd)

            # Clean up
            if await aiopath.exists(info_file):
                await remove(info_file)

            if result[2] == 0 and await aiopath.exists(temp_file):
                os.replace(temp_file, file_path)
                return True
            if await aiopath.exists(temp_file):
                await remove(temp_file)
            LOGGER.error(f"pdftk failed: {result[1]}")
            # Fall back to exiftool
            return await apply_exiftool_metadata(
                file_path, temp_file, title, author, comment
            )
        # Fall back to exiftool
        return await apply_exiftool_metadata(
            file_path, temp_file, title, author, comment
        )

    except Exception as e:
        LOGGER.error(f"Error applying PDF metadata: {e}")
        # Fall back to exiftool
        return await apply_exiftool_metadata(
            file_path, temp_file, title, author, comment
        )


async def apply_ebook_metadata(
    file_path, temp_file, title=None, author=None, comment=None
):
    """Apply metadata to ebook files using ebook-meta or exiftool.

    Args:
        file_path: Path to the ebook file
        temp_file: Path to the temporary file
        title: Title metadata to apply
        author: Author metadata to apply
        comment: Comment metadata to apply

    Returns:
        bool: True if metadata was successfully applied, False otherwise
    """
    try:
        # Check if ebook-meta (from Calibre) is available
        ebook_meta_check = await cmd_exec(["which", "ebook-meta"])

        if ebook_meta_check[0]:  # ebook-meta is available
            LOGGER.info(f"Using ebook-meta to apply metadata to {file_path}")

            # Create a copy of the file first
            shutil.copy2(file_path, temp_file)

            # Build the command
            cmd = ["ebook-meta", temp_file]
            if title:
                cmd.extend(["--title", title])
            if author:
                cmd.extend(["--author", author])
            if comment:
                cmd.extend(["--comments", comment])

            result = await cmd_exec(cmd)

            if result[2] == 0:
                os.replace(temp_file, file_path)
                return True
            if await aiopath.exists(temp_file):
                await remove(temp_file)
            LOGGER.error(f"ebook-meta failed: {result[1]}")
            # Fall back to exiftool
            return await apply_exiftool_metadata(
                file_path, temp_file, title, author, comment
            )
        # Fall back to exiftool
        return await apply_exiftool_metadata(
            file_path, temp_file, title, author, comment
        )

    except Exception as e:
        LOGGER.error(f"Error applying ebook metadata: {e}")
        # Fall back to exiftool
        return await apply_exiftool_metadata(
            file_path, temp_file, title, author, comment
        )


async def apply_office_metadata(
    file_path, temp_file, title=None, author=None, comment=None
):
    """Apply metadata to office document files.

    Args:
        file_path: Path to the office document file
        temp_file: Path to the temporary file
        title: Title metadata to apply
        author: Author metadata to apply
        comment: Comment metadata to apply

    Returns:
        bool: True if metadata was successfully applied, False otherwise
    """
    # For office documents, use exiftool
    return await apply_exiftool_metadata(
        file_path, temp_file, title, author, comment
    )


async def apply_text_metadata(
    file_path, temp_file, title=None, author=None, comment=None
):
    """Apply metadata to text files by adding comments at the top.

    Args:
        file_path: Path to the text file
        temp_file: Path to the temporary file
        title: Title metadata to apply
        author: Author metadata to apply
        comment: Comment metadata to apply

    Returns:
        bool: True if metadata was successfully applied, False otherwise
    """
    try:
        # For text files, we can add metadata as comments at the top of the file
        with open(file_path, encoding="utf-8", errors="ignore") as f_in:
            content = f_in.read()

        with open(temp_file, "w", encoding="utf-8") as f_out:
            # Add metadata as comments
            if title or author or comment:
                f_out.write("/*\n")
                if title:
                    f_out.write(f"Title: {title}\n")
                if author:
                    f_out.write(f"Author: {author}\n")
                if comment:
                    f_out.write(f"Comment: {comment}\n")
                f_out.write("*/\n\n")

            # Write the original content
            f_out.write(content)

        # Replace the original file
        os.replace(temp_file, file_path)
        return True

    except Exception as e:
        LOGGER.error(f"Error applying text metadata: {e}")
        return False


async def apply_exiftool_metadata(
    file_path, temp_file, title=None, author=None, comment=None
):
    """Apply metadata to files using exiftool.

    Args:
        file_path: Path to the file
        temp_file: Path to the temporary file
        title: Title metadata to apply
        author: Author metadata to apply
        comment: Comment metadata to apply

    Returns:
        bool: True if metadata was successfully applied, False otherwise
    """
    try:
        # Check if exiftool is available
        exiftool_check = await cmd_exec(["which", "exiftool"])

        if exiftool_check[0]:  # exiftool is available
            LOGGER.info(f"Using exiftool to apply metadata to {file_path}")

            cmd = ["exiftool"]
            if title:
                cmd.extend(["-Title=" + title])
            if author:
                cmd.extend(["-Author=" + author, "-Creator=" + author])
            if comment:
                cmd.extend(["-Subject=" + comment, "-Description=" + comment])

            # Add output file
            cmd.extend(["-o", temp_file, file_path])

            result = await cmd_exec(cmd)

            if result[2] == 0 and await aiopath.exists(temp_file):
                os.replace(temp_file, file_path)
                return True
            if await aiopath.exists(temp_file):
                await remove(temp_file)
            LOGGER.error(f"exiftool failed: {result[1]}")
            return False
        LOGGER.warning("exiftool not found, cannot apply metadata")
        return False

    except Exception as e:
        LOGGER.error(f"Error applying metadata with exiftool: {e}")
        return False


async def merge_pdfs(files, output_filename="merged.pdf"):
    """
    Merge multiple PDF files into a single PDF.

    Args:
        files: List of PDF file paths
        output_filename: Name of the output PDF file

    Returns:
        str: Path to the merged PDF file
    """
    if not files:
        LOGGER.error("No PDF files provided for merging")
        return None

    try:
        # Use files in the order they were provided
        # (No sorting to preserve user's intended order)

        # Create a PDF merger object
        merger = PdfMerger()

        # Add each PDF to the merger with error handling
        valid_pdfs = 0
        for pdf in files:
            try:
                # Check if the PDF is valid and not password-protected
                with open(pdf, "rb") as pdf_file:
                    reader = PdfReader(pdf_file)
                    if reader.is_encrypted:
                        LOGGER.warning(f"Skipping encrypted PDF: {pdf}")
                        continue

                # Add the PDF to the merger
                merger.append(pdf)
                valid_pdfs += 1
            except Exception as pdf_error:
                LOGGER.error(f"Error processing PDF {pdf}: {pdf_error}")
                continue

        if valid_pdfs == 0:
            LOGGER.error("No valid PDFs found for merging")
            return None

        # Determine output path
        base_dir = os.path.dirname(files[0])
        output_file = os.path.join(base_dir, output_filename)

        # Write the merged PDF to file
        with open(output_file, "wb") as f:
            merger.write(f)

        # Close the merger
        merger.close()

        LOGGER.info(f"Successfully merged {valid_pdfs} PDFs into {output_file}")

        # Force garbage collection after PDF merging
        # This can create large objects in memory
        if smart_garbage_collection:
            smart_garbage_collection(aggressive=True)
        else:
            gc.collect()

        return output_file

    except Exception as e:
        LOGGER.error(f"Error merging PDFs: {e}")
        return None


async def create_pdf_from_images(
    image_files, output_file="merged.pdf", page_size=None
):
    """
    Create a PDF from multiple image files.

    Args:
        image_files: List of image file paths
        output_file: Path to the output PDF file
        page_size: Size of the PDF pages (default: letter size)

    Returns:
        str: Path to the created PDF file
    """
    # Default to letter size if not specified
    if page_size is None:
        page_size = (612, 792)  # Standard letter size
    if not image_files:
        LOGGER.error("No image files provided for PDF creation")
        return None

    # Apply memory limits for PIL operations
    limit_memory_for_pil()

    try:
        # Use files in the order they were provided
        # (No sorting to preserve user's intended order)

        # Create a PDF writer
        writer = PdfWriter()

        # Process each image
        valid_images = 0
        for img_path in image_files:
            try:
                # Try to open as an image
                img = Image.open(img_path)

                # Convert to RGB if needed (handle more color modes)
                if img.mode == "RGBA":
                    # Create white background for transparent images
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(
                        img, mask=img.split()[3]
                    )  # Use alpha channel as mask
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                # Create a temporary file for the image
                temp_pdf = f"{img_path}.temp.pdf"

                # Save the image as a PDF with better quality
                img.save(temp_pdf, "PDF", resolution=300.0, quality=95)

                # Add the PDF to the writer
                reader = PdfReader(temp_pdf)
                writer.add_page(reader.pages[0])

                # Remove the temporary file
                os.remove(temp_pdf)
                valid_images += 1

            except Exception as e:
                LOGGER.error(f"Error processing image {img_path}: {e}")
                continue

        if valid_images == 0:
            LOGGER.error("No valid images could be processed for PDF creation")
            return None

        # Write the output PDF
        with open(output_file, "wb") as f:
            writer.write(f)

        LOGGER.info(
            f"Successfully created PDF with {valid_images} images: {output_file}"
        )
        return output_file

    except Exception as e:
        LOGGER.error(f"Error creating PDF from images: {e}")
        return None


async def merge_images(
    files, output_format="jpg", mode="collage", columns=None, quality=85
):
    """
    Merge multiple image files into a single image.

    Args:
        files: List of image file paths
        output_format: Output format (jpg, png, etc.)
        mode: 'collage' or 'vertical' or 'horizontal'
        columns: Number of columns for collage mode (auto-calculated if None)
        quality: Output image quality (1-100, only for jpg)

    Returns:
        str: Path to the merged image file
    """
    if not files:
        LOGGER.error("No image files provided for merging")
        return None

    # Apply memory limits for PIL operations
    limit_memory_for_pil()

    try:
        # Filter valid image files
        valid_files = []
        for f in files:
            if os.path.exists(f) and os.path.getsize(f) > 0:
                valid_files.append(f)
            else:
                LOGGER.warning(f"Skipping invalid or empty image file: {f}")

        if not valid_files:
            LOGGER.error("No valid image files found for merging")
            return None

        # Normalize output format
        output_format = output_format.lower().strip(".")
        if output_format not in ["jpg", "jpeg", "png", "webp", "tiff", "bmp", "gif"]:
            LOGGER.warning(
                f"Unsupported output format: {output_format}. Using jpg instead."
            )
            output_format = "jpg"

        # Determine base directory for output
        base_dir = os.path.dirname(valid_files[0])
        output_file = os.path.join(base_dir, f"merged.{int(time())}.{output_format}")

        # Open all valid images
        images = []
        for f in valid_files:
            try:
                # Skip the merged output file if it exists in the input list
                if os.path.basename(f) == f"merged.{output_format}":
                    LOGGER.info(f"Skipping previous merged output file: {f}")
                    continue

                # Skip any extremely large images (potential memory issues)
                file_size = os.path.getsize(f)
                if file_size > 50 * 1024 * 1024:  # 50 MB limit
                    LOGGER.warning(
                        f"Skipping very large image file ({file_size / 1024 / 1024:.2f} MB): {f}"
                    )
                    continue

                img = Image.open(f)

                # Skip images with extreme dimensions
                if img.width > 5000 or img.height > 5000:
                    LOGGER.warning(
                        f"Skipping image with extreme dimensions ({img.width}x{img.height}): {f}"
                    )
                    continue

                # Convert to RGB if needed (handle more color modes)
                if img.mode == "RGBA" and output_format.lower() in ["jpg", "jpeg"]:
                    # Create white background for transparent images
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(
                        img, mask=img.split()[3]
                    )  # Use alpha channel as mask
                    img = background
                elif img.mode != "RGB" and output_format.lower() in ["jpg", "jpeg"]:
                    img = img.convert("RGB")

                images.append(img)
            except Exception as e:
                LOGGER.error(f"Error opening image {f}: {e}")
                # Skip invalid images
                continue

        if not images:
            LOGGER.error("No valid images found for merging")
            return None

        # Determine merge mode
        if mode not in ["collage", "vertical", "horizontal"]:
            LOGGER.warning(
                f"Invalid merge mode: {mode}. Using 'collage' as default."
            )
            mode = "collage"

        # For collage mode, determine number of columns
        if mode == "collage":
            if columns is None:
                # Auto-calculate columns based on number of images
                if len(images) <= 2:
                    columns = 1
                elif len(images) <= 6:
                    columns = 2
                elif len(images) <= 12:
                    columns = 3
                else:
                    columns = 4

            columns = max(1, min(columns, len(images)))  # Ensure valid column count
            rows = (len(images) + columns - 1) // columns  # Ceiling division

            # Find the average dimensions for better proportions
            avg_width = sum(img.width for img in images) // len(images)
            avg_height = sum(img.height for img in images) // len(images)

            # Decide on cell dimensions - can use average or maximum
            # Using average dimensions with a margin for better aesthetics
            cell_width = int(avg_width * 1.1)  # 10% margin
            cell_height = int(avg_height * 1.1)  # 10% margin

            # Check if the total dimensions would be too large
            MAX_DIMENSION = 10000  # Maximum dimension in pixels
            total_width = cell_width * columns
            total_height = cell_height * rows

            if total_width > MAX_DIMENSION or total_height > MAX_DIMENSION:
                # Scale down to fit within limits
                scale_factor = min(
                    MAX_DIMENSION / total_width, MAX_DIMENSION / total_height
                )
                cell_width = int(cell_width * scale_factor)
                cell_height = int(cell_height * scale_factor)
                total_width = cell_width * columns
                total_height = cell_height * rows

            # Create a new image with the calculated dimensions
            if output_format.lower() in ["jpg", "jpeg"]:
                merged_image = Image.new(
                    "RGB", (total_width, total_height), (255, 255, 255)
                )
            else:
                merged_image = Image.new(
                    "RGBA", (total_width, total_height), (255, 255, 255, 0)
                )

            # Paste each image into the grid
            for i, img in enumerate(images):
                if i >= rows * columns:  # Skip if we've filled all cells
                    break

                row = i // columns
                col = i % columns

                # Calculate position
                x = col * cell_width
                y = row * cell_height

                # Resize image to fit cell (preserving aspect ratio)
                img_aspect = img.width / img.height
                cell_aspect = cell_width / cell_height

                if img_aspect > cell_aspect:  # Image is wider than cell
                    new_width = cell_width
                    new_height = int(cell_width / img_aspect)
                else:  # Image is taller than cell
                    new_height = cell_height
                    new_width = int(cell_height * img_aspect)

                # Resize with high quality
                resized_img = img.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )

                # Center in cell
                paste_x = x + (cell_width - new_width) // 2
                paste_y = y + (cell_height - new_height) // 2

                # Paste the image
                if resized_img.mode == "RGBA" and merged_image.mode == "RGB":
                    # Handle transparency for RGB output
                    background = Image.new("RGB", resized_img.size, (255, 255, 255))
                    background.paste(
                        resized_img, mask=resized_img.split()[3]
                    )  # Use alpha channel as mask
                    merged_image.paste(background, (paste_x, paste_y))
                else:
                    # Direct paste for compatible modes
                    merged_image.paste(resized_img, (paste_x, paste_y))

        elif mode == "vertical":
            # Stack images vertically
            total_width = max(img.width for img in images)
            total_height = sum(img.height for img in images)

            # Check if the total dimensions would be too large
            MAX_DIMENSION = 10000  # Maximum dimension in pixels
            if total_height > MAX_DIMENSION:
                # Scale down to fit within limits
                scale_factor = MAX_DIMENSION / total_height
                total_width = int(total_width * scale_factor)
                total_height = MAX_DIMENSION

                # Resize all images proportionally
                scaled_images = []
                for img in images:
                    new_width = int(img.width * scale_factor)
                    new_height = int(img.height * scale_factor)
                    scaled_img = img.resize(
                        (new_width, new_height), Image.Resampling.LANCZOS
                    )
                    scaled_images.append(scaled_img)
                images = scaled_images

            # Create a new image
            if output_format.lower() in ["jpg", "jpeg"]:
                merged_image = Image.new(
                    "RGB", (total_width, total_height), (255, 255, 255)
                )
            else:
                merged_image = Image.new(
                    "RGBA", (total_width, total_height), (255, 255, 255, 0)
                )

            # Paste each image
            y_offset = 0
            for img in images:
                # Center horizontally
                x_offset = (total_width - img.width) // 2

                # Paste the image
                if img.mode == "RGBA" and merged_image.mode == "RGB":
                    # Handle transparency for RGB output
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(
                        img, mask=img.split()[3]
                    )  # Use alpha channel as mask
                    merged_image.paste(background, (x_offset, y_offset))
                else:
                    # Direct paste for compatible modes
                    merged_image.paste(img, (x_offset, y_offset))

                y_offset += img.height

        elif mode == "horizontal":
            # Place images side by side
            total_width = sum(img.width for img in images)
            total_height = max(img.height for img in images)

            # Check if the total dimensions would be too large
            MAX_DIMENSION = 10000  # Maximum dimension in pixels
            if total_width > MAX_DIMENSION:
                # Scale down to fit within limits
                scale_factor = MAX_DIMENSION / total_width
                total_width = MAX_DIMENSION
                total_height = int(total_height * scale_factor)

                # Resize all images proportionally
                scaled_images = []
                for img in images:
                    new_width = int(img.width * scale_factor)
                    new_height = int(img.height * scale_factor)
                    scaled_img = img.resize(
                        (new_width, new_height), Image.Resampling.LANCZOS
                    )
                    scaled_images.append(scaled_img)
                images = scaled_images

            # Create a new image
            if output_format.lower() in ["jpg", "jpeg"]:
                merged_image = Image.new(
                    "RGB", (total_width, total_height), (255, 255, 255)
                )
            else:
                merged_image = Image.new(
                    "RGBA", (total_width, total_height), (255, 255, 255, 0)
                )

            # Paste each image
            x_offset = 0
            for img in images:
                # Center vertically
                y_offset = (total_height - img.height) // 2

                # Paste the image
                if img.mode == "RGBA" and merged_image.mode == "RGB":
                    # Handle transparency for RGB output
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(
                        img, mask=img.split()[3]
                    )  # Use alpha channel as mask
                    merged_image.paste(background, (x_offset, y_offset))
                else:
                    # Direct paste for compatible modes
                    merged_image.paste(img, (x_offset, y_offset))

                x_offset += img.width

        # Save the merged image
        if output_format.lower() in ["jpg", "jpeg"]:
            merged_image.save(output_file, quality=quality, optimize=True)
        elif output_format.lower() == "png":
            merged_image.save(output_file, optimize=True)
        elif output_format.lower() == "webp":
            merged_image.save(output_file, quality=quality, method=4)
        elif output_format.lower() == "gif":
            if merged_image.mode == "RGBA":
                # Use transparency mask for GIF
                mask = Image.eval(
                    merged_image.split()[3], lambda a: 255 if a <= 128 else 0
                )
                merged_image.save(
                    output_file, transparency=255, optimize=True, mask=mask
                )
            else:
                merged_image.save(output_file)
        else:
            # Default save for other formats
            merged_image.save(output_file)

        LOGGER.info(f"Successfully merged {len(images)} images into {output_file}")

        # Force garbage collection after image merging
        # This can create large objects in memory
        if smart_garbage_collection:
            smart_garbage_collection(aggressive=True)
        else:
            gc.collect()

        return output_file

    except Exception as e:
        LOGGER.error(f"Error merging images: {e}")
        return None


async def merge_documents(files, output_format="pdf"):
    """
    Merge multiple document files into a single document.
    Supports PDF merging and converting images to PDF.

    Args:
        files: List of document file paths
        output_format: Output format (currently only 'pdf' is supported)

    Returns:
        str: Path to the merged document file
    """
    if not files:
        LOGGER.error("No document files provided for merging")
        return None

    if output_format.lower() != "pdf":
        LOGGER.error(
            f"Unsupported output format: {output_format}. Only PDF is supported."
        )
        return None

    # Apply memory limits for PIL operations (for image processing)
    limit_memory_for_pil()

    # Group files by extension with validation
    file_groups = {}
    valid_files = []

    for file_path in files:
        # Check if file exists
        if not os.path.exists(file_path):
            LOGGER.error(f"Document file not found: {file_path}")
            continue

        # Get file extension
        ext = Path(file_path).suffix.lower()[1:]  # Remove the dot
        if not ext:
            LOGGER.error(f"File has no extension: {file_path}")
            continue

        # Group by extension
        if ext not in file_groups:
            file_groups[ext] = []
        file_groups[ext].append(file_path)
        valid_files.append(file_path)

    if not valid_files:
        LOGGER.error("No valid files found for merging")
        return None

    # Determine base directory for output
    base_dir = os.path.dirname(valid_files[0])
    output_file = os.path.join(base_dir, f"merged.{int(time())}.pdf")

    # Case 1: Only PDF files
    if len(file_groups) == 1 and "pdf" in file_groups:
        LOGGER.info("Merging PDF files only")
        return await merge_pdfs(file_groups["pdf"], output_file)

    # Case 2: Only image files
    image_extensions = ["jpg", "jpeg", "png", "bmp", "gif", "tiff", "webp"]
    image_files = []
    for ext in image_extensions:
        if ext in file_groups:
            image_files.extend(file_groups[ext])

    if len(image_files) == len(valid_files):
        LOGGER.info("Converting and merging image files to PDF")
        return await create_pdf_from_images(image_files, output_file)

    # Case 3: Mixed file types (PDFs and images)
    LOGGER.info("Processing mixed file types (PDFs and images)")

    # Create a PDF writer for the final output
    writer = PdfWriter()

    # Process PDF files first
    pdf_count = 0
    if "pdf" in file_groups:
        for pdf_path in file_groups["pdf"]:
            try:
                # Check if the PDF is valid and not password-protected
                with open(pdf_path, "rb") as pdf_file:
                    reader = PdfReader(pdf_file)
                    if reader.is_encrypted:
                        LOGGER.warning(f"Skipping encrypted PDF: {pdf_path}")
                        continue

                    # Add all pages from this PDF
                    for page in reader.pages:
                        writer.add_page(page)

                    pdf_count += 1
            except Exception as e:
                LOGGER.error(f"Error processing PDF {pdf_path}: {e}")
                continue

    # Process image files
    image_count = 0
    for img_path in image_files:
        try:
            # Try to open as an image
            img = Image.open(img_path)

            # Convert to RGB if needed
            if img.mode == "RGBA":
                # Create white background for transparent images
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(
                    img, mask=img.split()[3]
                )  # Use alpha channel as mask
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Create a temporary file for the image
            temp_pdf = f"{img_path}.temp.pdf"

            # Save the image as a PDF with better quality
            img.save(temp_pdf, "PDF", resolution=300.0, quality=95)

            # Add the PDF to the writer
            reader = PdfReader(temp_pdf)
            writer.add_page(reader.pages[0])

            # Remove the temporary file
            os.remove(temp_pdf)
            image_count += 1

        except Exception as e:
            LOGGER.error(f"Error processing image {img_path}: {e}")
            continue

    # Check if we have any valid files to merge
    if pdf_count == 0 and image_count == 0:
        LOGGER.error("No valid files found for merging")
        return None

    # Write the merged PDF
    try:
        with open(output_file, "wb") as f:
            writer.write(f)

        LOGGER.info(
            f"Successfully merged {pdf_count} PDFs and {image_count} images into {output_file}"
        )

        # Force garbage collection after document merging
        # This can create large objects in memory
        if smart_garbage_collection:
            smart_garbage_collection(aggressive=True)
        else:
            gc.collect()

        return output_file
    except Exception as e:
        LOGGER.error(f"Error writing merged PDF: {e}")
        return None
