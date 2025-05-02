import asyncio
import contextlib
import json
import os
import os.path

import aiohttp

from bot import LOGGER, cpu_no
from bot.helper.ext_utils.bot_utils import cmd_exec
from bot.helper.ext_utils.media_utils import get_streams


async def download_google_font(font_name):
    """Download a font from Google Fonts API.

    Args:
        font_name: Name of the Google Font to download

    Returns:
        str: Path to the downloaded font file or default font if download fails
    """
    try:
        # Create fonts directory if it doesn't exist
        os.makedirs("fonts", exist_ok=True)

        # Check if font already exists
        font_path = f"fonts/{font_name}.ttf"
        if os.path.exists(font_path):
            return font_path

        # Format the font name for the Google Fonts API URL
        api_font_name = font_name.replace(" ", "+")
        font_url = (
            f"https://fonts.googleapis.com/css2?family={api_font_name}&display=swap"
        )

        async with aiohttp.ClientSession() as session:
            # Get the CSS file which contains the font URL
            async with session.get(
                font_url, headers={"User-Agent": "Mozilla/5.0"}
            ) as response:
                if response.status != 200:
                    LOGGER.error(
                        f"Failed to fetch Google Font CSS for {font_name}: {response.status}"
                    )
                    return "default.otf"

                css = await response.text()

                # Extract the font URL from the CSS
                font_url_start = css.find("src: url(")
                if font_url_start == -1:
                    LOGGER.error(f"Could not find font URL in CSS for {font_name}")
                    return "default.otf"

                font_url_start += 9  # Length of "src: url("
                font_url_end = css.find(")", font_url_start)
                font_url = css[font_url_start:font_url_end]

                # Download the font file
                async with session.get(font_url) as font_response:
                    if font_response.status != 200:
                        LOGGER.error(
                            f"Failed to download font file for {font_name}: {font_response.status}"
                        )
                        return "default.otf"

                    with open(font_path, "wb") as f:
                        f.write(await font_response.read())

                    LOGGER.info(f"Successfully downloaded Google Font: {font_name}")
                    return font_path
    except Exception as e:
        LOGGER.error(f"Error downloading Google Font {font_name}: {e!s}")
        return "default.otf"


async def get_watermark_cmd(
    file,
    key,
    position="top_left",
    size=20,
    color="white",  # Default color is white
    font="default.otf",
    fast_mode=False,
    maintain_quality=True,
    opacity=1.0,
    audio_watermark_enabled=False,
    audio_watermark_text="",
    subtitle_watermark_enabled=False,
    subtitle_watermark_text="",
):
    """Generate FFmpeg command for adding watermark to media files with improved handling.

    Args:
        file: Path to the input file
        key: Watermark text
        position: Position of watermark (top_left, top_right, bottom_left, bottom_right, center, etc.)
        size: Font size
        color: Font color
        font: Font file name or Google Font name
        fast_mode: Whether to use ultrafast preset for large files
        maintain_quality: Whether to maintain original quality
        opacity: Opacity of watermark (0.0-1.0)

    Returns:
        tuple: FFmpeg command and temporary output file path, or None, None if not supported
    """
    # Import the function to determine media type
    # Resource manager removed
    from bot.helper.ext_utils.bot_utils import cmd_exec
    from bot.helper.ext_utils.media_utils import get_media_type_for_watermark

    # Determine the media type
    media_type = await get_media_type_for_watermark(file)
    if not media_type:
        return None, None

    # Check if file dimensions are divisible by 2 for video files
    needs_padding = True  # Always use padding for safety
    width = 0
    height = 0

    if media_type == "video":
        try:
            # Use ffprobe to get dimensions
            cmd = [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                file,
            ]

            # Execute the command
            stdout, _, code = await cmd_exec(cmd)

            if code == 0:
                data = json.loads(stdout)
                if data.get("streams"):
                    width = int(data["streams"][0].get("width", 0))
                    height = int(data["streams"][0].get("height", 0))

                    # Check if dimensions are divisible by 2
                    if width % 2 != 0 or height % 2 != 0:
                        needs_padding = True
                    else:
                        needs_padding = False

        except Exception:
            pass

    # Determine output file extension based on input file
    file_ext = os.path.splitext(file)[1].lower()

    # For videos, always use .mkv as temp extension for maximum compatibility
    if media_type == "video":
        temp_file = f"{file}.temp.mkv"
    elif media_type == "audio":
        # For audio files, preserve the original extension
        temp_file = f"{file}.temp{file_ext}"
    elif media_type == "subtitle":
        # For subtitle files, preserve the original extension
        temp_file = f"{file}.temp{file_ext}"
    else:
        # For images, preserve the original extension
        temp_file = f"{file}.temp{file_ext}"

    # Check if font is a Google Font or a local file
    if font.endswith((".ttf", ".otf")):
        font_path = font
    else:
        # Assume it's a Google Font name and try to download it
        font_path = await download_google_font(font)

    # Set position coordinates based on position parameter
    if position == "top_left":
        x_pos, y_pos = "10", "10"
    elif position == "top_right":
        x_pos, y_pos = "w-tw-10", "10"
    elif position == "bottom_left":
        x_pos, y_pos = "10", "h-th-10"
    elif position == "bottom_right":
        x_pos, y_pos = "w-tw-10", "h-th-10"
    elif position == "center":
        x_pos, y_pos = "(w-tw)/2", "(h-th)/2"
    elif position == "top_center":
        x_pos, y_pos = "(w-tw)/2", "10"
    elif position == "bottom_center":
        x_pos, y_pos = "(w-tw)/2", "h-th-10"
    elif position == "left_center":
        x_pos, y_pos = "10", "(h-th)/2"
    elif position == "right_center":
        x_pos, y_pos = "w-tw-10", "(h-th)/2"
    else:  # Default to top_left if invalid position
        x_pos, y_pos = "10", "10"

    # Create the drawtext filter with shadow for better visibility
    # Add a shadow effect to make text more readable on any background

    # Handle None values for color by using default color "white"
    if color is None or color == "None":
        color = "white"
        LOGGER.info(f"Color parameter was None, using default color: {color}")

    shadow_color = "black" if color.lower() != "black" else "white"
    drawtext_filter = (
        f"drawtext=text='{key}':fontfile={font_path}:fontsize={size}:"
        f"fontcolor={color}:x={x_pos}:y={y_pos}:shadowcolor={shadow_color}:shadowx=1:shadowy=1"
    )

    # Add opacity if specified
    if opacity < 1.0:
        drawtext_filter += f":alpha={opacity}"

    # Base command for all media types
    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file,
        "-ignore_unknown",
    ]

    # Check file size for fast mode
    large_file_threshold = 100 * 1024 * 1024  # 100MB
    file_size = os.path.getsize(file)
    use_fast_mode = fast_mode and file_size > large_file_threshold

    # Use default thread count
    thread_count = max(1, cpu_no // 2)

    # Add media-specific parameters
    if media_type == "video":
        # For video files - use a simpler approach that selects only the main video stream
        # This avoids issues with multiple video streams with odd dimensions

        # First, select only the main video stream (usually the first one)
        cmd.extend(["-map", "0:v:0"])

        # Add the watermark filter with padding if needed
        if needs_padding:
            cmd.extend(
                [
                    "-vf",
                    f"scale=iw:ih,pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2,{drawtext_filter}",
                ]
            )
        else:
            cmd.extend(["-vf", drawtext_filter])

        # Map audio and subtitle streams
        cmd.extend(["-map", "0:a?", "-map", "0:s?", "-map", "0:t?"])

        # Copy audio and subtitle streams
        cmd.extend(["-c:a", "copy", "-c:s", "copy"])

        # Add quality settings if maintain_quality is enabled
        if maintain_quality:
            cmd.extend(["-crf", "18"])  # High quality

        # Add fast mode if needed
        if use_fast_mode:
            cmd.extend(["-preset", "ultrafast"])

    elif media_type == "image":
        # For static images, use the drawtext filter with appropriate output format
        # Use higher quality settings for better results
        if file_ext in [".jpg", ".jpeg"]:
            # For JPEG, use quality parameter
            cmd.extend(
                [
                    "-vf",
                    drawtext_filter,
                    "-q:v",
                    "1"
                    if maintain_quality
                    else "2",  # Highest quality (1-31, lower is better)
                    "-threads",
                    f"{thread_count}",
                    temp_file,
                ]
            )
        elif file_ext in [".png", ".webp"]:
            # For PNG and WebP, preserve transparency
            cmd.extend(
                [
                    "-vf",
                    drawtext_filter,
                    "-compression_level",
                    "0" if maintain_quality else "3",  # Lossless compression
                    "-threads",
                    f"{thread_count}",
                    temp_file,
                ]
            )
        else:
            # For other image formats, use general high quality settings
            cmd.extend(
                [
                    "-vf",
                    drawtext_filter,
                    "-q:v",
                    "2" if maintain_quality else "5",  # High quality
                    "-threads",
                    f"{thread_count}",
                    temp_file,
                ]
            )
    elif media_type == "animated_image":
        # For animated images (GIFs), we need to use a different approach
        # The issue with the previous approach was that we can't use both -vf and -lavfi
        # Instead, we'll incorporate the drawtext filter into the complex filtergraph

        # Create a complex filtergraph that includes both the watermark and palette generation
        complex_filter = (
            f"[0:v]scale=iw:ih,pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2,{drawtext_filter}[marked];"
            f"[marked]split[v1][v2];"
            f"[v1]palettegen=reserve_transparent=1[pal];"
            f"[v2][pal]paletteuse=alpha_threshold=128"
        )

        cmd.extend(
            [
                "-lavfi",
                complex_filter,
                "-threads",
                f"{thread_count}",
                temp_file,
            ]
        )
    elif media_type == "audio":
        # For audio files, we'll add a voice watermark using FFmpeg's built-in sine tone
        # This adds a beep sound at specified intervals with the watermark text

        # Get audio duration
        try:
            audio_info_cmd = [
                "ffprobe",  # Keep as ffprobe, not xtra
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                file,
            ]
            stdout, _, code = await cmd_exec(audio_info_cmd)
            duration = 10  # Default duration if we can't determine

            if code == 0:
                data = json.loads(stdout)
                if data.get("format") and data["format"].get("duration"):
                    duration = float(data["format"]["duration"])

            # Use audio_watermark_text if provided, otherwise use the general watermark text
            watermark_text = audio_watermark_text if audio_watermark_text else key

            # Determine beep parameters based on position and color
            beep_frequency = 1000  # Default frequency in Hz
            beep_duration = 0.5  # Default duration in seconds

            # Use the audio_watermark_volume parameter if provided, otherwise use default
            from bot.core.config_manager import Config

            beep_volume = (
                Config.AUDIO_WATERMARK_VOLUME
                if hasattr(Config, "AUDIO_WATERMARK_VOLUME")
                else 0.3
            )

            # Adjust parameters based on position
            if position in ["top_left", "top_right", "top_center"]:
                beep_frequency = 1500  # Higher pitch for top positions
                beep_volume = beep_volume * 0.7  # Quieter for top positions
            elif position in ["bottom_left", "bottom_right", "bottom_center"]:
                beep_frequency = 800  # Lower pitch for bottom positions
                beep_volume = (
                    beep_volume * 1.2
                )  # Louder for bottom positions (but cap at 1.0)
                beep_volume = min(
                    beep_volume, 1.0
                )  # Ensure volume doesn't exceed 1.0
            elif position == "center":
                beep_frequency = 1200  # Medium pitch for center position
                beep_volume = (
                    beep_volume * 1.1
                )  # Slightly louder for center position
                beep_volume = min(
                    beep_volume, 1.0
                )  # Ensure volume doesn't exceed 1.0

            # Adjust parameters based on color
            if color.lower() == "red":
                beep_frequency = 1800  # Higher pitch for red
            elif color.lower() == "blue":
                beep_frequency = 600  # Lower pitch for blue
            elif color.lower() == "green":
                beep_frequency = 1200  # Medium pitch for green
            elif color.lower() == "yellow":
                beep_frequency = 1500  # Higher medium pitch for yellow

            # Calculate spacing for watermark insertion
            # We'll use duration to determine spacing of beeps

            # Create filter to add beep tones at intervals
            filter_complex = ""

            # Use size parameter to determine number of beeps (10=1, 20=2, 30=3, 40=4)
            num_beeps = max(1, min(size // 10, 4))

            # Use opacity to determine volume
            beep_volume = beep_volume * opacity

            # Skip audio watermarking if it's explicitly disabled
            if not audio_watermark_enabled:
                # Just copy the audio without modification
                cmd = [
                    "xtra",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-i",
                    file,
                    "-c:a",
                    "copy",
                    "-metadata",
                    f"comment=Watermarked with: {watermark_text}",
                    "-metadata",
                    f"title=Original title + {watermark_text}",
                    "-threads",
                    f"{thread_count}",
                    temp_file,
                ]
            else:
                # Apply audio watermark
                if duration <= 30:
                    # For short files, add beep at beginning and end
                    filter_complex = (
                        f"[0:a]asetpts=PTS-STARTPTS[a];"
                        f"aevalsrc=0.1*sin({beep_frequency}*2*PI*t):d={beep_duration}:s=44100[beep];"
                        f"[a][beep]amix=inputs=2:duration=first:weights=1 {beep_volume}[aout]"
                    )
                else:
                    # For longer files, add beeps at intervals
                    beep_points = []
                    for i in range(num_beeps):
                        point = i * (duration / (num_beeps - 0.5))
                        if point < duration:
                            beep_points.append(point)

                    # Create a complex filter to insert beeps at intervals
                    beep_parts = []
                    for i, point in enumerate(beep_points):
                        beep_parts.append(
                            f"aevalsrc=0.1*sin({beep_frequency}*2*PI*t):d={beep_duration}:s=44100,adelay={int(point * 1000)}|{int(point * 1000)}[beep{i + 1}];"
                        )

                    # Combine all beeps
                    beep_inputs = "".join(
                        f"[beep{i + 1}]" for i in range(len(beep_points))
                    )
                    weights = " ".join(["1"] * len(beep_points))
                    beep_volumes = " ".join([str(beep_volume)] * len(beep_points))

                    filter_complex = (
                        f"[0:a]asetpts=PTS-STARTPTS[a];"
                        f"{''.join(beep_parts)}"
                        f"[a]{beep_inputs}amix=inputs={len(beep_points) + 1}:duration=first:weights={weights} {beep_volumes}[aout]"
                    )

                # Create command to add beep watermark
                cmd = [
                    "xtra",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-i",
                    file,
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[aout]",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k" if maintain_quality else "128k",
                    "-metadata",
                    f"comment=Watermarked with: {watermark_text}",
                    "-metadata",
                    f"title=Original title + {watermark_text}",
                    "-threads",
                    f"{thread_count}",
                    temp_file,
                ]

        except Exception as e:
            LOGGER.error(f"Error creating audio watermark command: {e}")
            return None, None

    elif media_type == "video_with_subtitle":
        # For videos with subtitle streams, we should handle them as regular videos
        # but skip the subtitle watermarking

        # Use the same code as for regular videos, but make sure we don't modify subtitle streams
        # First, select only the main video stream (usually the first one)
        cmd.extend(["-map", "0:v:0"])

        # Add the watermark filter with padding if needed
        if needs_padding:
            cmd.extend(
                [
                    "-vf",
                    f"scale=iw:ih,pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2,{drawtext_filter}",
                ]
            )
        else:
            cmd.extend(["-vf", drawtext_filter])

        # Map audio and subtitle streams, but copy subtitle streams without modification
        cmd.extend(["-map", "0:a?", "-map", "0:s?", "-map", "0:t?"])

        # Copy audio and subtitle streams
        cmd.extend(["-c:a", "copy", "-c:s", "copy"])

        # Add quality settings if maintain_quality is enabled
        if maintain_quality:
            cmd.extend(["-crf", "18"])  # High quality

        # Add fast mode if needed
        if use_fast_mode:
            cmd.extend(["-preset", "ultrafast"])

        return cmd, temp_file

    elif media_type == "subtitle":
        # For subtitle files, we'll add the watermark text to each subtitle entry
        # This requires parsing and modifying the subtitle file

        # Skip subtitle watermarking if it's explicitly disabled
        if not subtitle_watermark_enabled:
            # For subtitle files with watermarking disabled, just return the file as is
            return None, None

        try:
            # Read the subtitle file
            with open(file, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Create a temporary file for the modified subtitles
            # Use a unique name to avoid conflicts
            import uuid

            temp_file = (
                f"{os.path.splitext(file)[0]}_wm_{uuid.uuid4().hex[:8]}{file_ext}"
            )

            # Determine watermark style based on parameters
            # First check if we have a specific subtitle style set in config
            from bot.core.config_manager import Config

            subtitle_style = (
                Config.SUBTITLE_WATERMARK_STYLE
                if hasattr(Config, "SUBTITLE_WATERMARK_STYLE")
                else "normal"
            )

            # Set style based on subtitle_style parameter
            if subtitle_style.lower() == "bold":
                watermark_style = "**"  # Bold style
            elif subtitle_style.lower() == "italic":
                watermark_style = "_"  # Italic style
            elif subtitle_style.lower() == "underline":
                watermark_style = "__"  # Underline style
            else:
                # If no specific style or "normal", use color-based styling
                watermark_style = ""
                if color.lower() == "white":
                    watermark_style = ""  # Default, no special styling
                elif color.lower() == "black":
                    watermark_style = "▓"  # Dark background
                elif color.lower() == "red":
                    watermark_style = "❤️"  # Red heart symbol
                elif color.lower() == "green":
                    watermark_style = "✅"  # Green checkmark
                elif color.lower() == "blue":
                    watermark_style = "🔷"  # Blue diamond
                elif color.lower() == "yellow":
                    watermark_style = "⭐"  # Yellow star

            # Use size parameter to determine frequency
            # 10 = every subtitle, 20 = every 2nd, 30 = every 3rd, 40 = every 4th
            frequency = max(1, size // 10)

            # Use opacity to determine visibility (1.0 = full text, lower = abbreviated)
            abbreviated = opacity < 0.7

            with open(temp_file, "w", encoding="utf-8") as f:
                # Check if it's an SRT file (most common)
                if file_ext.lower() == ".srt":
                    # Enhanced watermarking: add the watermark text with styling
                    import re

                    # Pattern to match SRT entries
                    pattern = r"(\d+)\r?\n(\d{2}:\d{2}:\d{2},\d{3}\s-->\s\d{2}:\d{2}:\d{2},\d{3})\r?\n(.*?)(?=\r?\n\r?\n\d+|\Z)"

                    # Function to add watermark to each subtitle entry
                    def add_watermark(match):
                        index = int(match.group(1))
                        timing = match.group(2)
                        text = match.group(3).strip()

                        # Only add watermark based on frequency
                        if index % frequency != 0:
                            return f"{index}\n{timing}\n{text}\n\n"

                        # Prepare watermark text - use subtitle_watermark_text if provided
                        watermark_text = (
                            subtitle_watermark_text
                            if subtitle_watermark_text
                            else key
                        )
                        if abbreviated and len(watermark_text) > 10:
                            # Use abbreviated version for lower opacity
                            words = watermark_text.split()
                            if len(words) > 1:
                                watermark_text = "".join(word[0] for word in words)
                            else:
                                watermark_text = watermark_text[:5] + "..."

                        # Format with style
                        formatted_watermark = (
                            f"{watermark_style}[{watermark_text}]{watermark_style}"
                        )

                        # Add watermark based on position
                        if position in [
                            "bottom_left",
                            "bottom_right",
                            "bottom_center",
                        ]:
                            # Add at the end
                            watermarked_text = f"{text}\n{formatted_watermark}"
                        elif position in ["top_left", "top_right", "top_center"]:
                            # Add at the beginning
                            watermarked_text = f"{formatted_watermark}\n{text}"
                        elif position == "center":
                            # Add in the middle of the text if possible
                            lines = text.split("\n")
                            if len(lines) > 1:
                                middle = len(lines) // 2
                                lines.insert(middle, formatted_watermark)
                                watermarked_text = "\n".join(lines)
                            else:
                                # If single line, add at the end
                                watermarked_text = f"{text} {formatted_watermark}"
                        else:
                            # For other positions, add inline
                            watermarked_text = f"{text} {formatted_watermark}"

                        return f"{index}\n{timing}\n{watermarked_text}\n\n"

                    # Apply the watermark
                    watermarked_content = re.sub(
                        pattern, add_watermark, content, flags=re.DOTALL
                    )
                    f.write(watermarked_content)

                    # For subtitle files, we don't use FFmpeg, so return None for the command
                    # but keep the temp_file for the result
                    return None, temp_file

                if file_ext.lower() in [".ass", ".ssa"]:
                    # For ASS/SSA files, add the watermark to the style or as a separate line
                    # This is more complex and would require a proper ASS parser
                    import re

                    # Try to find the Events section
                    events_match = re.search(
                        r"(\[Events\].*?)(?=\[|\Z)", content, re.DOTALL
                    )
                    if events_match:
                        events_section = events_match.group(1)
                        # Find the format line
                        format_match = re.search(
                            r"Format:(.*?)$", events_section, re.MULTILINE
                        )
                        if format_match:
                            # Get the format fields
                            format_fields = [
                                f.strip() for f in format_match.group(1).split(",")
                            ]

                            # Find the dialogue lines
                            dialogue_pattern = r"(Dialogue:.*?)$"

                            # Function to add watermark to dialogue lines
                            def add_ass_watermark(match):
                                line = match.group(1)
                                parts = line.split(",", len(format_fields))

                                # Get the text part (last part)
                                if len(parts) >= len(format_fields):
                                    text = parts[-1]

                                    # Add watermark based on position
                                    if position in [
                                        "bottom_left",
                                        "bottom_right",
                                        "bottom_center",
                                    ]:
                                        # Add at the end
                                        # Use subtitle_watermark_text if provided
                                        watermark_text = (
                                            subtitle_watermark_text
                                            if subtitle_watermark_text
                                            else key
                                        )
                                        watermarked_text = f"{text}\\N{watermark_style}[{watermark_text}]{watermark_style}"
                                    else:
                                        # Add at the beginning
                                        # Use subtitle_watermark_text if provided
                                        watermark_text = (
                                            subtitle_watermark_text
                                            if subtitle_watermark_text
                                            else key
                                        )
                                        watermarked_text = f"{watermark_style}[{watermark_text}]{watermark_style}\\N{text}"

                                    # Replace the text part
                                    parts[-1] = watermarked_text
                                    return ",".join(parts)
                                return line

                            # Apply watermark to every nth dialogue line based on frequency
                            lines = events_section.split("\n")
                            dialogue_count = 0
                            for i in range(len(lines)):
                                if lines[i].startswith("Dialogue:"):
                                    dialogue_count += 1
                                    if dialogue_count % frequency == 0:
                                        lines[i] = re.sub(
                                            dialogue_pattern,
                                            add_ass_watermark,
                                            lines[i],
                                        )

                            # Replace the events section in the content
                            modified_events = "\n".join(lines)
                            modified_content = content.replace(
                                events_match.group(1), modified_events
                            )
                            f.write(modified_content)
                            return None, temp_file

                    # If we couldn't parse the ASS file properly, just add a comment
                    # Use subtitle_watermark_text if provided
                    watermark_text = (
                        subtitle_watermark_text if subtitle_watermark_text else key
                    )
                    f.write(f"; Watermarked with: {watermark_text}\n{content}")
                    return None, temp_file

                # For other subtitle formats, try to add watermark based on common patterns
                # WebVTT format
                if file_ext.lower() == ".vtt":
                    import re

                    # Pattern for WebVTT cues
                    pattern = r"(\d{2}:\d{2}:\d{2}\.\d{3}\s-->\s\d{2}:\d{2}:\d{2}\.\d{3}.*?\n)(.*?)(?=\n\n|\Z)"

                    # Function to add watermark to WebVTT cues
                    def add_vtt_watermark(match):
                        timing = match.group(1)
                        text = match.group(2).strip()

                        # Add watermark based on position
                        if position in [
                            "bottom_left",
                            "bottom_right",
                            "bottom_center",
                        ]:
                            # Add at the end
                            # Use subtitle_watermark_text if provided
                            watermark_text = (
                                subtitle_watermark_text
                                if subtitle_watermark_text
                                else key
                            )
                            watermarked_text = f"{text}\n{watermark_style}[{watermark_text}]{watermark_style}"
                        else:
                            # Add at the beginning
                            # Use subtitle_watermark_text if provided
                            watermark_text = (
                                subtitle_watermark_text
                                if subtitle_watermark_text
                                else key
                            )
                            watermarked_text = f"{watermark_style}[{watermark_text}]{watermark_style}\n{text}"

                        return f"{timing}{watermarked_text}\n\n"

                    # Apply the watermark
                    watermarked_content = re.sub(
                        pattern, add_vtt_watermark, content, flags=re.DOTALL
                    )
                    f.write(watermarked_content)
                    return None, temp_file

                # For other formats, just add a comment if possible
                # Use subtitle_watermark_text if provided
                watermark_text = (
                    subtitle_watermark_text if subtitle_watermark_text else key
                )
                f.write(f"# Watermarked with: {watermark_text}\n{content}")
                return None, temp_file

        except Exception as e:
            LOGGER.error(f"Error watermarking subtitle file: {e}")
            return None, None
    else:
        # This should not happen as we already checked media_type
        LOGGER.error(f"Unknown media type: {media_type}")
        return None, None

    # Add threads parameter if not already added
    if "-threads" not in cmd and media_type not in ["subtitle"]:
        cmd.extend(["-threads", f"{thread_count}", temp_file])

    # Log the generated command for debugging only

    return cmd, temp_file


async def get_metadata_cmd(
    file_path,
    key,
    title=None,
    author=None,
    comment=None,
    metadata_all=None,
    video_title=None,
    video_author=None,
    video_comment=None,
    audio_title=None,
    audio_author=None,
    audio_comment=None,
    subtitle_title=None,
    subtitle_author=None,
    subtitle_comment=None,
):
    """Processes a single file to update metadata.

    Args:
        file_path: Path to the file to process
        key: Legacy metadata key (for backward compatibility)
        title: Global title metadata value
        author: Global author metadata value
        comment: Global comment metadata value
        metadata_all: Value to use for all metadata fields (takes priority over all)
        video_title: Video track title metadata value
        video_author: Video track author metadata value
        video_comment: Video track comment metadata value
        audio_title: Audio track title metadata value
        audio_author: Audio track author metadata value
        audio_comment: Audio track comment metadata value
        subtitle_title: Subtitle track title metadata value
        subtitle_author: Subtitle track author metadata value
        subtitle_comment: Subtitle track comment metadata value

    Returns:
        tuple: FFmpeg command and temporary output file path, or None, None if not supported
    """
    # Resource manager removed

    # Get file extension
    file_ext = os.path.splitext(file_path)[1].lower()

    # For most files, use .mkv as temp extension for maximum metadata compatibility
    # For HEVC files, use .mp4 as temp extension for better compatibility
    # For MPEG files, use .mp4 as temp extension for better compatibility
    # For image files, use appropriate extensions
    # For subtitle files, use .srt for maximum compatibility
    if file_ext in [".hevc", ".mpeg"]:
        temp_file = f"{file_path}.temp.mp4"
    elif file_ext in [".jpg", ".jpeg", ".png", ".gif", ".tiff", ".tif", ".webp"]:
        # For image files, keep the same extension for better compatibility
        temp_file = f"{file_path}.temp{file_ext}"
    elif file_ext in [
        ".srt",
        ".ass",
        ".ssa",
        ".vtt",
        ".webvtt",
        ".sub",
        ".sbv",
        ".stl",
    ]:
        # For subtitle files, use .srt for maximum compatibility
        temp_file = f"{file_path}.temp.srt"
    else:
        temp_file = f"{file_path}.temp.mkv"

    # Get stream information
    # For subtitle files, we might not get proper stream info, so handle them specially
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in [
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
    ]:
        # For subtitle files, create a simple command that just copies the file and adds metadata
        # For some subtitle formats, we need to convert them to SRT for better compatibility

        # Create a temporary text file with metadata
        meta_file = f"{file_path}.meta"
        with open(meta_file, "w") as f:
            if title:
                f.write(f";TITLE={title}\n")
            if author:
                f.write(f";AUTHOR={author}\n")
            if comment:
                f.write(f";COMMENT={comment}\n")
            if subtitle_title:
                f.write(f";SUBTITLE_TITLE={subtitle_title}\n")
            if subtitle_author:
                f.write(f";SUBTITLE_AUTHOR={subtitle_author}\n")
            if subtitle_comment:
                f.write(f";SUBTITLE_COMMENT={subtitle_comment}\n")

        # For problematic formats, try to convert to SRT first
        if file_ext in [
            ".vtt",
            ".webvtt",
            ".sbv",
            ".stl",
            ".scc",
            ".ttml",
            ".dfxp",
            ".sub",
        ]:  # First, try to convert using FFmpeg
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                file_path,
                "-map_metadata",
                "-1",  # Remove existing metadata
            ]

            # Add global metadata
            if title:
                cmd.extend(["-metadata", f"title={title}"])
            if author:
                cmd.extend(
                    [
                        "-metadata",
                        f"artist={author}",
                        "-metadata",
                        f"author={author}",
                    ]
                )
            if comment:
                cmd.extend(["-metadata", f"comment={comment}"])

            # Add subtitle-specific metadata
            if subtitle_title:
                cmd.extend(["-metadata", f"subtitle_title={subtitle_title}"])
            if subtitle_author:
                cmd.extend(["-metadata", f"subtitle_author={subtitle_author}"])
            if subtitle_comment:
                cmd.extend(["-metadata", f"subtitle_comment={subtitle_comment}"])

            # Convert to SRT format
            cmd.extend(
                [
                    "-c:s",
                    "srt",  # Convert to SRT format
                    "-threads",
                    "8",
                    temp_file,
                ]
            )

            # If this is a .sub file, try a different approach as fallback
            if file_ext == ".sub":
                # For .sub files, we need to check if it's a SubRip or MicroDVD format
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        first_line = f.readline().strip()

                    # Check if it's MicroDVD format (starts with {number}{number})
                    if first_line.startswith("{") and "}" in first_line:
                        LOGGER.info(
                            f"Detected MicroDVD format for {file_path}, using special handling"
                        )
                        # For MicroDVD, we need to use a different approach
                        # Create a new command that handles MicroDVD format
                        cmd = [
                            "xtra",
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-progress",
                            "pipe:1",
                            "-i",
                            file_path,
                            "-map_metadata",
                            "-1",  # Remove existing metadata
                            "-sub_charenc",
                            "UTF-8",  # Ensure UTF-8 encoding
                            "-f",
                            "srt",  # Force SRT output format
                        ]

                        # Add metadata
                        if title:
                            cmd.extend(["-metadata", f"title={title}"])
                        if author:
                            cmd.extend(
                                [
                                    "-metadata",
                                    f"artist={author}",
                                    "-metadata",
                                    f"author={author}",
                                ]
                            )
                        if comment:
                            cmd.extend(["-metadata", f"comment={comment}"])
                        if subtitle_title:
                            cmd.extend(
                                ["-metadata", f"subtitle_title={subtitle_title}"]
                            )
                        if subtitle_author:
                            cmd.extend(
                                ["-metadata", f"subtitle_author={subtitle_author}"]
                            )
                        if subtitle_comment:
                            cmd.extend(
                                ["-metadata", f"subtitle_comment={subtitle_comment}"]
                            )

                        cmd.append(temp_file)
                except Exception as e:
                    LOGGER.error(f"Error checking SUB format: {e}")
        else:
            # For SRT, ASS, SSA formats, just copy
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                file_path,
                "-map_metadata",
                "-1",  # Remove existing metadata
            ]

            # Add global metadata
            if title:
                cmd.extend(["-metadata", f"title={title}"])
            if author:
                cmd.extend(
                    [
                        "-metadata",
                        f"artist={author}",
                        "-metadata",
                        f"author={author}",
                    ]
                )
            if comment:
                cmd.extend(["-metadata", f"comment={comment}"])

            # Add subtitle-specific metadata
            if subtitle_title:
                cmd.extend(["-metadata", f"subtitle_title={subtitle_title}"])
            if subtitle_author:
                cmd.extend(["-metadata", f"subtitle_author={subtitle_author}"])
            if subtitle_comment:
                cmd.extend(["-metadata", f"subtitle_comment={subtitle_comment}"])

            # Finish the command
            cmd.extend(["-c", "copy", "-threads", "8", temp_file])

        # Add cleanup for the metadata file
        LOGGER.info(f"Created temporary metadata file: {meta_file}")

        return cmd, temp_file

    # Special handling for image and document files
    file_ext = os.path.splitext(file_path)[1].lower()
    image_extensions = [
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

    document_extensions = [
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

    if file_ext in document_extensions:
        LOGGER.info(
            f"Detected document file: {file_path}, using special handling for metadata"
        )

        # For document files, use the document_utils module

        # Create a dummy command that will be replaced by the document_utils module
        cmd = ["echo", "Using document_utils module for metadata"]

        # The temp_file will be created by the document_utils module
        temp_file = f"{file_path}.temp{file_ext}"

        # Return the dummy command and temp_file
        # The actual metadata application will be handled by the document_utils module
        # in the metadata_watermark_cmds method
        return cmd, temp_file

    if file_ext in image_extensions:
        LOGGER.info(
            f"Detected image file: {file_path}, using special handling for metadata"
        )

        # For image files, we'll use a different approach
        # First, create a temporary file with the same extension
        if ".temp" not in file_path:
            temp_file = f"{file_path}.temp{file_ext}"
        else:
            temp_file = file_path

        # Create the command based on the image type
        if file_ext in [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".bmp",
            ".tiff",
            ".tif",
        ]:
            # For common image formats, use FFmpeg
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                file_path,
                "-map_metadata",
                "-1",  # Remove existing metadata
            ]

            # Add global metadata
            if title:
                cmd.extend(["-metadata", f"title={title}"])
            if author:
                cmd.extend(
                    [
                        "-metadata",
                        f"artist={author}",
                        "-metadata",
                        f"author={author}",
                    ]
                )
            if comment:
                cmd.extend(["-metadata", f"comment={comment}"])

            # Finish the command
            cmd.extend(["-c", "copy", "-threads", "8", temp_file])

            return cmd, temp_file
        # For other image formats, try to use exiftool if available
        try:
            # Check if exiftool is available
            result = await cmd_exec(["which", "exiftool"])
            if result[0] and result[2] == 0:
                # exiftool is available, use it
                cmd = ["exiftool"]

                # Add metadata
                if title:
                    cmd.extend(["-Title=" + title])
                if author:
                    cmd.extend(["-Artist=" + author, "-Author=" + author])
                if comment:
                    cmd.extend(["-Comment=" + comment])

                # Add output file
                cmd.extend(["-o", temp_file, file_path])

                return cmd, temp_file
            # exiftool not available, fall back to FFmpeg
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                file_path,
                "-map_metadata",
                "-1",  # Remove existing metadata
            ]

            # Add global metadata
            if title:
                cmd.extend(["-metadata", f"title={title}"])
            if author:
                cmd.extend(
                    [
                        "-metadata",
                        f"artist={author}",
                        "-metadata",
                        f"author={author}",
                    ]
                )
            if comment:
                cmd.extend(["-metadata", f"comment={comment}"])

            # Finish the command
            cmd.extend(["-c", "copy", "-threads", "8", temp_file])

            return cmd, temp_file
        except Exception as e:
            LOGGER.error(f"Error checking for exiftool: {e}")
            # Fall back to FFmpeg
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                file_path,
                "-map_metadata",
                "-1",  # Remove existing metadata
            ]

            # Add global metadata
            if title:
                cmd.extend(["-metadata", f"title={title}"])
            if author:
                cmd.extend(
                    [
                        "-metadata",
                        f"artist={author}",
                        "-metadata",
                        f"author={author}",
                    ]
                )
            if comment:
                cmd.extend(["-metadata", f"comment={comment}"])

            # Finish the command
            cmd.extend(["-c", "copy", "-threads", "8", temp_file])

            return cmd, temp_file

    # For other files, get stream information
    streams = await get_streams(file_path)
    if not streams:
        LOGGER.error(f"Failed to get stream information for {file_path}")
        return None, None

    # Extract language information from streams
    languages = {}
    with contextlib.suppress(Exception):
        languages = {
            stream["index"]: stream["tags"]["language"]
            for stream in streams
            if "tags" in stream and "language" in stream["tags"]
        }

    # Use default thread count
    thread_count = max(1, cpu_no // 2)

    # Determine which metadata values to use
    # metadata_all takes priority over all other settings
    if metadata_all:
        # Use metadata_all for all fields
        global_title_value = global_author_value = global_comment_value = (
            metadata_all
        )
        video_title_value = video_author_value = video_comment_value = metadata_all
        audio_title_value = audio_author_value = audio_comment_value = metadata_all
        subtitle_title_value = subtitle_author_value = subtitle_comment_value = (
            metadata_all
        )
    else:
        # Global metadata (fallback to legacy key if not provided)
        global_title_value = title if title else key
        global_author_value = author if author else key
        global_comment_value = comment if comment else key

        # Video track metadata (fallback to global values if not provided)
        video_title_value = video_title if video_title else global_title_value
        video_author_value = video_author if video_author else global_author_value
        video_comment_value = (
            video_comment if video_comment else global_comment_value
        )

        # Audio track metadata (fallback to global values if not provided)
        audio_title_value = audio_title if audio_title else global_title_value
        audio_author_value = audio_author if audio_author else global_author_value
        audio_comment_value = (
            audio_comment if audio_comment else global_comment_value
        )

        # Subtitle track metadata (fallback to global values if not provided)
        subtitle_title_value = (
            subtitle_title if subtitle_title else global_title_value
        )
        subtitle_author_value = (
            subtitle_author if subtitle_author else global_author_value
        )
        subtitle_comment_value = (
            subtitle_comment if subtitle_comment else global_comment_value
        )

    # Start building the FFmpeg command
    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file_path,
    ]

    # Add -map_metadata -1 to clear existing metadata
    cmd.extend(["-map_metadata", "-1"])

    # Always use copy codec to preserve quality
    cmd.extend(["-c", "copy"])

    # Add global metadata
    cmd.extend(["-metadata", f"title={global_title_value}"])

    # Add author and comment metadata if they exist
    if global_author_value:
        cmd.extend(["-metadata", f"artist={global_author_value}"])
        cmd.extend(["-metadata", f"author={global_author_value}"])

    if global_comment_value:
        cmd.extend(["-metadata", f"comment={global_comment_value}"])

    # Count stream types for proper indexing
    video_count = 0
    audio_count = 0
    subtitle_count = 0
    other_count = 0

    # First pass: count streams by type
    for stream in streams:
        stream_type = stream.get("codec_type", "unknown")
        if stream_type == "video":
            video_count += 1
        elif stream_type == "audio":
            audio_count += 1
        elif stream_type == "subtitle":
            subtitle_count += 1
        else:
            other_count += 1

    LOGGER.info(
        f"File {file_path} has {video_count} video, {audio_count} audio, {subtitle_count} subtitle, and {other_count} other streams"
    )

    # Second pass: map all streams and add metadata
    video_index = 0
    audio_index = 0
    subtitle_index = 0
    attachment_index = 0

    # Map all streams to preserve them
    cmd.extend(["-map", "0"])

    # Add stream-specific metadata
    for stream in streams:
        stream_index = stream["index"]
        stream_type = stream.get("codec_type", "unknown")

        if stream_type == "video":
            # Skip attached pictures (cover art)
            if stream.get("disposition", {}).get("attached_pic", 0) == 1:
                LOGGER.info(f"Skipping attached picture in stream {stream_index}")
                continue

            # Add video metadata
            cmd.extend(
                [f"-metadata:s:v:{video_index}", f"title={video_title_value}"]
            )

            if video_author_value:
                cmd.extend(
                    [f"-metadata:s:v:{video_index}", f"artist={video_author_value}"]
                )

            if video_comment_value:
                cmd.extend(
                    [
                        f"-metadata:s:v:{video_index}",
                        f"comment={video_comment_value}",
                    ]
                )

            # Preserve language tag if it exists
            if stream_index in languages:
                cmd.extend(
                    [
                        f"-metadata:s:v:{video_index}",
                        f"language={languages[stream_index]}",
                    ]
                )

            video_index += 1

        elif stream_type == "audio":
            # Add audio metadata
            cmd.extend(
                [f"-metadata:s:a:{audio_index}", f"title={audio_title_value}"]
            )

            if audio_author_value:
                cmd.extend(
                    [f"-metadata:s:a:{audio_index}", f"artist={audio_author_value}"]
                )

            if audio_comment_value:
                cmd.extend(
                    [
                        f"-metadata:s:a:{audio_index}",
                        f"comment={audio_comment_value}",
                    ]
                )

            # Preserve language tag if it exists
            if stream_index in languages:
                cmd.extend(
                    [
                        f"-metadata:s:a:{audio_index}",
                        f"language={languages[stream_index]}",
                    ]
                )

            audio_index += 1

        elif stream_type == "subtitle":
            codec_name = stream.get("codec_name", "unknown")

            # Some subtitle formats don't support metadata well
            if codec_name in ["webvtt", "unknown"]:
                pass

            # Add subtitle metadata
            cmd.extend(
                [f"-metadata:s:s:{subtitle_index}", f"title={subtitle_title_value}"]
            )

            if subtitle_author_value:
                cmd.extend(
                    [
                        f"-metadata:s:s:{subtitle_index}",
                        f"artist={subtitle_author_value}",
                    ]
                )

            if subtitle_comment_value:
                cmd.extend(
                    [
                        f"-metadata:s:s:{subtitle_index}",
                        f"comment={subtitle_comment_value}",
                    ]
                )

            # Preserve language tag if it exists
            if stream_index in languages:
                cmd.extend(
                    [
                        f"-metadata:s:s:{subtitle_index}",
                        f"language={languages[stream_index]}",
                    ]
                )

            subtitle_index += 1

        elif stream_type == "attachment":
            # Handle attachment streams
            # Check if the attachment has a filename tag
            if "tags" in stream and "filename" in stream["tags"]:
                # Preserve the original filename
                cmd.extend(
                    [
                        f"-metadata:s:t:{attachment_index}",
                        f"filename={stream['tags']['filename']}",
                    ]
                )
            else:
                # If no filename tag exists, add a default one
                LOGGER.info(
                    f"Adding default filename for attachment stream {stream_index}"
                )
                cmd.extend(
                    [
                        f"-metadata:s:t:{attachment_index}",
                        f"filename=attachment_{attachment_index}.bin",
                    ]
                )

            # Add mimetype if available, or use a default
            if "tags" in stream and "mimetype" in stream["tags"]:
                mimetype = stream["tags"]["mimetype"]
                cmd.extend(
                    [f"-metadata:s:t:{attachment_index}", f"mimetype={mimetype}"]
                )
            else:
                # Determine mimetype based on codec_name if available
                codec_name = stream.get("codec_name", "").lower()
                if codec_name in ["ttf"]:
                    mimetype = "application/x-truetype-font"
                elif codec_name in ["otf"]:
                    mimetype = "application/vnd.ms-opentype"
                elif codec_name in ["woff"]:
                    mimetype = "application/font-woff"
                elif codec_name in ["woff2"]:
                    mimetype = "application/font-woff2"
                else:
                    # Use a generic mimetype
                    mimetype = "application/octet-stream"

                cmd.extend(
                    [f"-metadata:s:t:{attachment_index}", f"mimetype={mimetype}"]
                )

            attachment_index += 1

    # Add thread count for better performance
    cmd.extend(["-threads", f"{thread_count}"])

    # Add output file
    cmd.append(temp_file)

    # Log the command for debugging}")

    return cmd, temp_file


# TODO later
async def get_embed_thumb_cmd(file, attachment_path):
    # Resource manager removed

    temp_file = f"{file}.temp.mkv"
    attachment_ext = attachment_path.split(".")[-1].lower()
    mime_type = "application/octet-stream"
    if attachment_ext in ["jpg", "jpeg"]:
        mime_type = "image/jpeg"
    elif attachment_ext == "png":
        mime_type = "image/png"

    # Use default thread count
    thread_count = max(1, cpu_no // 2)

    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file,
        "-ignore_unknown",
        "-attach",
        attachment_path,
        "-metadata:s:t",
        f"mimetype={mime_type}",
        "-c",
        "copy",
        "-map",
        "0",
        "-threads",
        f"{thread_count}",
        temp_file,
    ]

    return cmd, temp_file


async def get_media_type_internal(file_path):
    """Determine if a file is video, audio, or subtitle.

    Args:
        file_path: Path to the file

    Returns:
        str: 'video', 'audio', 'subtitle', or None if can't determine
    """
    streams = await get_streams(file_path)
    if not streams:
        return None

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

    return None


async def get_merge_concat_demuxer_cmd(files, output_format="mkv", media_type=None):
    """Generate FFmpeg command for merging files using concat demuxer.

    Args:
        files: List of file paths to merge
        output_format: Output file format (default: mkv)
        media_type: Type of media ('video', 'audio', 'subtitle', 'image') for specialized handling

    Returns:
        tuple: FFmpeg command and output file path
    """
    # Resource manager removed

    if not files:
        return None, None

    # Use files in the order they were provided
    # (No sorting to preserve user's intended order)

    # Check if all files have the same codec for video and audio
    # This is important for concat demuxer to work properly
    if media_type in ["video", "audio"]:
        try:
            import json
            import subprocess

            # Get codec information for all files
            codecs = []
            for file_path in files:
                cmd = [
                    "ffprobe",  # Keep as ffprobe, not xtra
                    "-v",
                    "error",
                    "-select_streams",
                    "v" if media_type == "video" else "a",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "json",
                    file_path,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if data.get("streams"):
                        codecs.append(data["streams"][0].get("codec_name", ""))
                    else:
                        # If we can't determine codec, assume it's different
                        codecs.append(f"unknown_{len(codecs)}")
                else:
                    # If ffprobe fails, assume it's a different codec
                    codecs.append(f"unknown_{len(codecs)}")

            # Check if all codecs are the same
            if len(set(codecs)) > 1:
                pass
        except Exception:
            pass

    # Create a temporary file list for concat demuxer
    concat_list_path = "concat_list.txt"
    with open(concat_list_path, "w") as f:
        for file_path in files:
            # Escape single quotes in file paths
            escaped_path = file_path.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")

    # Determine output path based on first file and media type
    base_dir = os.path.dirname(files[0])
    if media_type == "video":
        output_file = os.path.join(base_dir, f"merged_video.{output_format}")
    elif media_type == "audio":
        output_file = os.path.join(base_dir, f"merged_audio.{output_format}")
    elif media_type == "subtitle":
        output_file = os.path.join(base_dir, f"merged_subtitle.{output_format}")
    else:
        output_file = os.path.join(base_dir, f"merged.{output_format}")

    # Basic command for concat demuxer
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
        "-ignore_unknown",
    ]

    # Add specialized options based on media type
    if media_type == "video":
        # For video files, we need to handle potential codec issues
        # Check if all files have the same codec
        streams_list = []
        for file_path in files:
            streams = await get_streams(file_path)
            if streams:
                streams_list.append(streams)

        # Check if all files have the same codecs
        same_codecs = True
        same_resolution = True
        reference_width = None
        reference_height = None

        # Always add -map 0 to preserve all streams from the input
        cmd.extend(["-map", "0"])

        if streams_list:
            reference_streams = streams_list[0]
            # Check for video dimensions in the first file
            for stream in reference_streams:
                if stream.get("codec_type") == "video" and not stream.get(
                    "disposition", {}
                ).get("attached_pic"):
                    reference_width = stream.get("width")
                    reference_height = stream.get("height")
                    break

            # Compare codecs and dimensions with other files
            for streams in streams_list[1:]:
                if len(streams) != len(reference_streams):
                    same_codecs = False

                # Check for resolution differences
                for stream in streams:
                    if stream.get("codec_type") == "video" and not stream.get(
                        "disposition", {}
                    ).get("attached_pic"):
                        if (
                            stream.get("width") != reference_width
                            or stream.get("height") != reference_height
                        ):
                            same_resolution = False
                        break

                # Check for codec differences
                for i, stream in enumerate(streams):
                    if i >= len(reference_streams):
                        break
                    if stream.get("codec_name") != reference_streams[i].get(
                        "codec_name"
                    ) or stream.get("codec_type") != reference_streams[i].get(
                        "codec_type"
                    ):
                        same_codecs = False
                        break

        LOGGER.info(
            f"Video merge analysis: same_codecs={same_codecs}, same_resolution={same_resolution}"
        )

        if same_codecs and same_resolution:
            # All files have the same codecs and resolution, we can use copy
            # Use -map 0 to preserve all streams including video, audio, and subtitles
            cmd.extend(["-c", "copy"])
            LOGGER.info(
                "Using direct stream copy for identical video files, preserving all streams"
            )
        else:
            # Files have different codecs or resolutions, we need to transcode
            # Use high-quality settings for video and audio, but preserve all streams
            if output_format in ["mp4", "mov"]:
                # For MP4 output, use H.264 for maximum compatibility
                cmd.extend(
                    [
                        # No need to add -map 0 again, it's already added above
                        "-c",
                        "copy",  # Start with copying all streams
                        "-c:v",  # Override video codec only
                        "libx264",
                        "-crf",
                        "18",  # High quality
                        "-preset",
                        "slow",  # Better compression
                        "-c:a",  # Override audio codec only if needed
                        "aac",
                        "-b:a",
                        "192k",
                        "-c:s",  # Override subtitle codec for MP4 compatibility
                        "mov_text",
                    ]
                )
                LOGGER.info(
                    "Using H.264/AAC encoding for MP4 output while preserving all streams"
                )
            elif output_format == "webm":
                # For WebM output, use VP9 and Opus
                cmd.extend(
                    [
                        # No need to add -map 0 again, it's already added above
                        "-c:v",
                        "libvpx-vp9",
                        "-crf",
                        "30",
                        "-b:v",
                        "0",
                        "-c:a",
                        "libopus",
                        "-b:a",
                        "128k",
                        # WebM doesn't support many subtitle formats, so we don't specify -c:s
                    ]
                )
                LOGGER.info(
                    "Using VP9/Opus encoding for WebM output while preserving compatible streams"
                )
            else:
                # For MKV and other formats, use H.264 with high quality
                # MKV supports virtually all codecs, so we can preserve more
                cmd.extend(
                    [
                        # No need to add -map 0 again, it's already added above
                        "-c",
                        "copy",  # Start with copying all streams
                        "-c:v",  # Override video codec only
                        "libx264",
                        "-crf",
                        "18",
                        "-preset",
                        "slow",
                        "-c:a",  # Override audio codec only if needed
                        "aac",
                        "-b:a",
                        "192k",
                        # Keep subtitle copying as is
                    ]
                )
                LOGGER.info(
                    "Using H.264/AAC encoding for MKV output while preserving all streams"
                )

            # If resolutions differ, we need to handle that in filter_complex instead
            if not same_resolution and not same_codecs:
                LOGGER.info(
                    "Videos have different resolutions and codecs, consider using filter_complex instead"
                )
    elif media_type == "audio":
        # For audio files, check if we need to transcode
        streams_list = []
        for file_path in files:
            streams = await get_streams(file_path)
            if streams:
                streams_list.append(streams)

        # Check if all files have the same audio codec
        same_codec = True
        audio_codec = None
        for streams in streams_list:
            for stream in streams:
                if stream.get("codec_type") == "audio":
                    if audio_codec is None:
                        audio_codec = stream.get("codec_name")
                    elif audio_codec != stream.get("codec_name"):
                        same_codec = False
                        break

        LOGGER.info(
            f"Audio merge analysis: same_codec={same_codec}, codec={audio_codec}"
        )

        if same_codec and audio_codec:
            # All files have the same audio codec, we can use copy
            cmd.extend(["-c", "copy"])
            LOGGER.info(
                f"Using direct stream copy for identical audio files with codec {audio_codec}"
            )
        # Files have different audio codecs, we need to transcode
        # Use high-quality settings for audio based on output format
        elif output_format == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-q:a", "0"])  # Highest quality MP3
            LOGGER.info("Using MP3 encoding with highest quality")
        elif output_format in {"aac", "m4a"}:
            cmd.extend(["-c:a", "aac", "-b:a", "320k"])  # High bitrate AAC
            LOGGER.info("Using AAC encoding with 320k bitrate")
        elif output_format == "flac":
            cmd.extend(["-c:a", "flac"])  # Lossless FLAC
            LOGGER.info("Using lossless FLAC encoding")
        elif output_format == "opus":
            cmd.extend(["-c:a", "libopus", "-b:a", "256k"])  # High quality Opus
            LOGGER.info("Using Opus encoding with 256k bitrate")
        elif output_format == "ogg":
            cmd.extend(["-c:a", "libvorbis", "-q:a", "10"])  # High quality Vorbis
            LOGGER.info("Using Vorbis encoding with quality level 10")
        else:
            # Default to AAC for other formats
            cmd.extend(["-c:a", "aac", "-b:a", "320k"])
            LOGGER.info("Using default AAC encoding with 320k bitrate")
    elif media_type == "subtitle":
        # For subtitle files, we need to handle different formats
        # Check the output format and set appropriate codec
        if output_format == "srt":
            cmd.extend(["-c:s", "srt"])
            LOGGER.info("Using SRT subtitle format")
        elif output_format in {"ass", "ssa"}:
            cmd.extend(["-c:s", "ass"])
            LOGGER.info("Using ASS/SSA subtitle format")
        elif output_format == "vtt":
            cmd.extend(["-c:s", "webvtt"])
            LOGGER.info("Using WebVTT subtitle format")
        else:
            # Default to copy for other formats
            cmd.extend(["-c:s", "copy"])
            LOGGER.info("Using copy for subtitle format")
    elif media_type == "image":
        # For image files, we need to use a different approach
        # This is just a placeholder as concat demuxer doesn't work well for images
        # The actual image merging will be handled by PIL in a separate function
        LOGGER.info(
            "Concat demuxer not suitable for images, use filter_complex or PIL instead"
        )
        return None, None
    else:
        # Default to copy for unknown media types
        cmd.extend(["-c", "copy"])
        LOGGER.info(f"Using copy for unknown media type: {media_type}")

    # Add threading and output file
    # Use default thread count
    thread_count = max(1, cpu_no // 2)
    cmd.extend(
        [
            "-threads",
            f"{thread_count}",
            output_file,
        ]
    )

    return cmd, output_file


async def get_merge_filter_complex_cmd(files, media_type, output_format=None):
    """Generate FFmpeg command for merging files using filter_complex.

    Args:
        files: List of file paths to merge
        media_type: Type of media ('video', 'audio', 'subtitle')
        output_format: Output file format (default: based on media_type)

    Returns:
        tuple: FFmpeg command and output file path
    """
    # Resource manager removed

    if not files:
        return None, None

    # Use files in the order they were provided
    # (No sorting to preserve user's intended order)

    # Set default output format based on media type if not specified
    if not output_format:
        if media_type == "video":
            output_format = "mkv"
        elif media_type == "audio":
            output_format = "mp3"
        else:
            output_format = "srt"

    # For video and audio, check if we need to handle different resolutions or sample rates
    if media_type in ["video", "audio"]:
        try:
            import json
            import subprocess

            # Get media information for all files
            media_info = []
            for file_path in files:
                info = {}
                # Get codec information
                cmd = [
                    "ffprobe",  # Keep as ffprobe, not xtra
                    "-v",
                    "error",
                    "-select_streams",
                    "v" if media_type == "video" else "a",
                    "-show_entries",
                    "stream=codec_name,width,height,sample_rate,channels",
                    "-of",
                    "json",
                    file_path,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if data.get("streams"):
                        stream = data["streams"][0]
                        info["codec"] = stream.get("codec_name", "")
                        if media_type == "video":
                            info["width"] = int(stream.get("width", 0))
                            info["height"] = int(stream.get("height", 0))
                        else:  # audio
                            info["sample_rate"] = int(stream.get("sample_rate", 0))
                            info["channels"] = int(stream.get("channels", 0))
                media_info.append(info)

            # Log the media information for debugging
            LOGGER.info(f"Media info for {media_type} files: {media_info}")
        except Exception:
            media_info = []

    # Determine output path based on first file and media type
    base_dir = os.path.dirname(files[0])
    if media_type == "video":
        output_file = os.path.join(base_dir, f"merged_video.{output_format}")
    elif media_type == "audio":
        output_file = os.path.join(base_dir, f"merged_audio.{output_format}")
    elif media_type == "subtitle":
        output_file = os.path.join(base_dir, f"merged_subtitle.{output_format}")
    else:
        output_file = os.path.join(base_dir, f"merged.{output_format}")

    # Build input arguments
    input_args = []
    for file_path in files:
        input_args.extend(["-i", file_path])

    # Build filter complex string based on media type
    if media_type == "video":
        # For video files, we need to check each file for video and audio streams
        filter_complex = ""
        video_inputs = []
        audio_inputs = []
        subtitle_streams = []  # Track subtitle streams for mapping

        # First, identify which files have video and audio streams
        for i, file_path in enumerate(files):
            streams = await get_streams(file_path)
            if not streams:
                continue

            # Find video, audio, and subtitle streams
            video_stream = None
            audio_stream = None
            for stream in streams:
                if stream.get("codec_type") == "video" and not stream.get(
                    "disposition", {}
                ).get("attached_pic"):
                    video_stream = stream
                elif stream.get("codec_type") == "audio":
                    audio_stream = stream
                elif stream.get("codec_type") == "subtitle":
                    # Track subtitle streams for mapping
                    subtitle_streams.append((i, stream.get("index", 0)))

            # Add video stream if found
            if video_stream:
                video_index = video_stream.get("index", 0)
                video_inputs.append((i, video_index))

            # Add audio stream if found
            if audio_stream:
                audio_index = audio_stream.get("index", 0)
                audio_inputs.append((i, audio_index))

        # If we have video streams, create a video concat filter
        if video_inputs:
            # Check if we need to scale videos to the same dimensions
            need_scaling = False
            target_width = None
            target_height = None

            # Get dimensions of all videos
            video_dimensions = []
            for i, file_path in enumerate(files):
                streams = await get_streams(file_path)
                if not streams:
                    continue

                for stream in streams:
                    if stream.get("codec_type") == "video" and not stream.get(
                        "disposition", {}
                    ).get("attached_pic"):
                        width = stream.get("width")
                        height = stream.get("height")
                        if width and height:
                            video_dimensions.append((i, width, height))
                            if target_width is None or target_height is None:
                                target_width = width
                                target_height = height
                            elif width != target_width or height != target_height:
                                need_scaling = True

            # If videos have different dimensions, we need to scale them
            if need_scaling and target_width and target_height:
                # Create a new filter complex with scaling
                scaled_inputs = []
                for i, width, height in video_dimensions:
                    if width != target_width or height != target_height:
                        filter_complex += (
                            f"[{i}:v]scale={target_width}:{target_height}[v{i}];"
                        )
                        scaled_inputs.append(f"[v{i}]")
                    else:
                        scaled_inputs.append(f"[{i}:v]")

                # Use scaled inputs for concat
                video_filter = (
                    "".join(scaled_inputs)
                    + f"concat=n={len(scaled_inputs)}:v=1:a=0[outv]"
                )
            else:
                # Use original inputs for concat
                video_filter = (
                    "".join([f"[{i}:v:{idx}]" for i, idx in video_inputs])
                    + f"concat=n={len(video_inputs)}:v=1:a=0[outv]"
                )

            if filter_complex and not filter_complex.endswith(";"):
                filter_complex += ";"
            filter_complex += video_filter

        # If we have audio streams, create an audio concat filter
        if audio_inputs:
            if filter_complex and not filter_complex.endswith(";"):
                filter_complex += ";"  # Separator for multiple filters

            # Use a safer approach for audio inputs
            # First check if the audio stream exists in each file
            valid_audio_inputs = []
            for i, file_path in enumerate(files):
                streams = await get_streams(file_path)
                if not streams:
                    continue

                # Find all audio streams in each file
                audio_stream_count = 0
                for stream in streams:
                    if stream.get("codec_type") == "audio":
                        # Use actual stream index for more reliable mapping
                        stream_index = stream.get("index", audio_stream_count)
                        valid_audio_inputs.append((i, stream_index))
                        audio_stream_count += 1
                        LOGGER.info(
                            f"Found audio stream in file {i}: index={stream_index}, codec={stream.get('codec_name')}"
                        )

            if valid_audio_inputs:
                # Group audio inputs by file to preserve all audio tracks
                audio_inputs_by_file = {}
                for i, idx in valid_audio_inputs:
                    if i not in audio_inputs_by_file:
                        audio_inputs_by_file[i] = []
                    audio_inputs_by_file[i].append(idx)

                # Create separate concat filters for each audio track position
                audio_track_count = max(
                    len(inputs) for inputs in audio_inputs_by_file.values()
                )
                LOGGER.info(
                    f"Found {audio_track_count} audio track positions across {len(audio_inputs_by_file)} files"
                )

                # If we have multiple audio tracks, create a separate concat filter for each position
                if audio_track_count > 0:
                    for track_pos in range(audio_track_count):
                        # Collect inputs for this track position from each file
                        track_inputs = []
                        for file_idx, track_indices in audio_inputs_by_file.items():
                            if track_pos < len(track_indices):
                                track_inputs.append(
                                    (file_idx, track_indices[track_pos])
                                )

                        if track_inputs:
                            # Create concat filter for this track position
                            if filter_complex and not filter_complex.endswith(";"):
                                filter_complex += ";"
                            audio_filter = (
                                "".join(
                                    [f"[{i}:a:{idx}]" for i, idx in track_inputs]
                                )
                                + f"concat=n={len(track_inputs)}:v=0:a=1[outa{track_pos}]"
                            )
                            filter_complex += audio_filter
                            LOGGER.info(
                                f"Created audio concat filter for track position {track_pos} with {len(track_inputs)} inputs"
                            )
                else:
                    pass
            else:
                pass

        # Set up mapping based on available streams
        map_args = []

        # First map the merged video stream
        if video_inputs:
            map_args.extend(["-map", "[outv]"])
            # Set video codec based on output format
            if output_format == "mp4":
                map_args.extend(["-c:v", "libx264", "-crf", "18"])
            elif output_format == "webm":
                map_args.extend(["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0"])
            else:  # Default for mkv and others
                map_args.extend(["-c:v", "libx264", "-crf", "18"])

        # Map audio streams from filter_complex outputs
        # Check for [outaX] patterns in filter_complex
        import re

        outa_pattern = r"\[outa(\d*)\]"
        outa_matches = re.findall(outa_pattern, filter_complex)

        if outa_matches:
            # Map all audio outputs from filter_complex
            for match in outa_matches:
                track_num = match if match else "0"
                map_args.extend(["-map", f"[outa{track_num}]"])
                LOGGER.info(
                    f"Mapping audio track from filter_complex: [outa{track_num}]"
                )
        elif "[outa]" in filter_complex:
            # Legacy single audio track
            map_args.extend(["-map", "[outa]"])
            LOGGER.info("Mapping single audio track from filter_complex: [outa]")
        else:
            # Otherwise, map all audio streams from all input files directly
            audio_track_count = 0
            for i, file_path in enumerate(files):
                streams = await get_streams(file_path)
                if not streams:
                    continue

                # Find and map all audio streams
                for stream in streams:
                    if stream.get("codec_type") == "audio":
                        audio_index = stream.get("index", 0)
                        map_args.extend(
                            ["-map", f"{i}:a:{audio_index}?"]
                        )  # Add ? to make it optional
                        audio_track_count += 1

            LOGGER.info(
                f"Directly mapping {audio_track_count} audio tracks from input files"
            )

        # Set audio codec based on output format
        if output_format == "mp4":
            map_args.extend(["-c:a", "aac", "-b:a", "192k"])
        elif output_format == "webm":
            map_args.extend(["-c:a", "libopus", "-b:a", "128k"])
        else:  # Default for mkv and others
            map_args.extend(["-c:a", "aac", "-b:a", "192k"])

        # Now map all subtitle streams from all input files
        # This preserves all subtitle tracks in the merged output
        for i, file_path in enumerate(files):
            streams = await get_streams(file_path)
            if not streams:
                continue

            # Find and map all subtitle streams
            for stream in streams:
                if stream.get("codec_type") == "subtitle":
                    subtitle_index = stream.get("index", 0)
                    # Add a question mark to make the mapping optional
                    # This prevents errors when a subtitle stream doesn't exist
                    map_args.extend(["-map", f"{i}:s:{subtitle_index}?"])
                    LOGGER.info(
                        f"Mapping subtitle track from file {i}: index={subtitle_index}, codec={stream.get('codec_name')}"
                    )

        # Set subtitle codec based on output format
        if output_format == "mp4":
            map_args.extend(["-c:s", "mov_text"])  # MP4 compatible subtitles
        else:  # For MKV and other formats that support most subtitle formats
            map_args.extend(["-c:s", "copy"])  # Copy subtitle streams as is

        # Add metadata to indicate this is a merged file
        map_args.extend(["-metadata", "title=Merged Video"])

        # If no valid streams found, use a simpler approach
        if not filter_complex:
            return None, None

    elif media_type == "audio":
        # For audio files, check if we need to normalize audio levels
        normalize_audio = False  # Set to True to enable audio normalization

        if normalize_audio:
            # First pass: analyze audio levels
            filter_complex = ""
            for i, _ in enumerate(files):
                filter_complex += f"[{i}:a:0]loudnorm=print_format=json[a{i}];"

            # Second pass: normalize and concat
            for i, _ in enumerate(files):
                filter_complex += f"[a{i}]"
            filter_complex += f"concat=n={len(files)}:v=0:a=1[outa]"
        else:
            # Simple concat without normalization
            filter_complex = ""
            for i, _ in enumerate(files):
                filter_complex += f"[{i}:a:0]"
            filter_complex += f"concat=n={len(files)}:v=0:a=1[outa]"

        map_args = ["-map", "[outa]"]

        # Set audio codec based on output format
        if output_format == "mp3":
            map_args.extend(["-c:a", "libmp3lame", "-q:a", "0"])
        elif output_format in {"aac", "m4a"}:
            map_args.extend(["-c:a", "aac", "-b:a", "320k"])
        elif output_format == "flac":
            map_args.extend(["-c:a", "flac"])
        elif output_format == "opus":
            map_args.extend(["-c:a", "libopus", "-b:a", "256k"])
        else:
            # Default to AAC for other formats
            map_args.extend(["-c:a", "aac", "-b:a", "320k"])

    elif media_type == "subtitle":
        # For subtitle files, we'll use a custom approach for merging
        # This is a more advanced approach than just copying the first file

        # Check the subtitle formats
        subtitle_formats = [os.path.splitext(f)[1][1:].lower() for f in files]
        LOGGER.info(f"Merging subtitle files with formats: {subtitle_formats}")

        # Check if we need to convert formats
        need_conversion = len(set(subtitle_formats)) > 1
        if need_conversion:
            LOGGER.info(
                "Different subtitle formats detected, will convert to SRT before merging"
            )

            # For SRT files or if we need to convert to SRT
            # For SRT files, we can use a special approach to merge them
            # We'll create a temporary script to merge SRT files with proper timing
            # Use raw string to avoid escape sequence issues
            merge_script = r"""#!/usr/bin/env python3
import sys
import re

def parse_time(time_str):
    h, m, s = time_str.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

def parse_srt(content):
    pattern = r'(\\d+)\\s+(\\d{2}:\\d{2}:\\d{2},\\d{3}) --> (\\d{2}:\\d{2}:\\d{2},\\d{3})\\s+(.*?)(?=\\n\\d+\\s+\\d{2}:\\d{2}:\\d{2},\\d{3}|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    return [(int(idx), start, end, text.strip()) for idx, start, end, text in matches]

def parse_vtt(content):
    # Remove WEBVTT header if present
    if content.startswith('WEBVTT'):
        content = '\n'.join(content.split('\n')[2:])

    # VTT format: HH:MM:SS.mmm --> HH:MM:SS.mmm
    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\s+(.*?)(?=\n\n|$)'
    matches = re.findall(pattern, content, re.DOTALL)

    # Convert to SRT-like format with indices
    result = []
    for i, (start, end, text) in enumerate(matches, 1):
        # Convert VTT timestamp format to SRT format
        start_srt = start.replace('.', ',')
        end_srt = end.replace('.', ',')
        result.append((i, start_srt, end_srt, text.strip()))

    return result

def parse_ass(content):
    # Extract events section
    events_section = re.search(r'\[Events\].*?Format:.*?\n(.*)', content, re.DOTALL)
    if not events_section:
        return []

    events_text = events_section.group(1)

    # Extract dialogue lines
    dialogue_pattern = r'Dialogue: [^,]*,([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),(.*)'
    matches = re.findall(dialogue_pattern, events_text)

    result = []
    for i, match in enumerate(matches, 1):
        start_time = match[1].strip()
        end_time = match[2].strip()
        text = match[8].strip()

        # Convert ASS timestamp format (H:MM:SS.cc) to SRT format (HH:MM:SS,mmm)
        start_parts = start_time.split(':')
        if len(start_parts) == 2:  # MM:SS.cc
            start_srt = f"00:{start_parts[0]}:{start_parts[1]}".replace('.', ',')
        else:  # H:MM:SS.cc
            h = start_parts[0].zfill(2)
            start_srt = f"{h}:{start_parts[1]}:{start_parts[2]}".replace('.', ',')

        end_parts = end_time.split(':')
        if len(end_parts) == 2:  # MM:SS.cc
            end_srt = f"00:{end_parts[0]}:{end_parts[1]}".replace('.', ',')
        else:  # H:MM:SS.cc
            h = end_parts[0].zfill(2)
            end_srt = f"{h}:{end_parts[1]}:{end_parts[2]}".replace('.', ',')

        result.append((i, start_srt, end_srt, text))

    return result

def detect_subtitle_format(file_path):
    # Detect subtitle format based on file extension and content
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.srt':
        return 'srt'
    elif ext == '.vtt':
        return 'vtt'
    elif ext in ['.ass', '.ssa']:
        return 'ass'

    # If extension is not recognized, try to detect from content
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(1000)  # Read first 1000 chars

        if content.startswith('WEBVTT'):
            return 'vtt'
        elif '[Script Info]' in content and '[Events]' in content:
            return 'ass'
        elif re.search(r'\d+\s+\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', content):
            return 'srt'
    except Exception:
        pass

    # Default to SRT if we can't determine
    return 'srt'

def merge_subtitle_files(file_paths):
    all_subtitles = []
    current_offset = 0

    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Detect format and parse accordingly
            format_type = detect_subtitle_format(file_path)
            if format_type == 'srt':
                subtitles = parse_srt(content)
            elif format_type == 'vtt':
                subtitles = parse_vtt(content)
            elif format_type == 'ass':
                subtitles = parse_ass(content)
            else:
                # Default to SRT parser
                subtitles = parse_srt(content)

            if not subtitles:
                continue

            # Get the last end time from previous file
            if all_subtitles:
                last_end_time = parse_time(all_subtitles[-1][2])
            else:
                last_end_time = 0

            # Adjust timing for current file
            for idx, start, end, text in subtitles:
                start_time = parse_time(start) + current_offset
                end_time = parse_time(end) + current_offset

                # Handle overlapping timestamps
                if all_subtitles and start_time < last_end_time:
                    # Option 1: Shift this subtitle to start after the last one
                    start_time = last_end_time + 0.1
                    end_time = max(end_time, start_time + 1.0)  # Ensure at least 1 second duration

                all_subtitles.append((len(all_subtitles) + 1, format_time(start_time), format_time(end_time), text))
                last_end_time = end_time

            # Update offset for next file
            if subtitles:
                current_offset = parse_time(all_subtitles[-1][2]) + 0.5  # Add a small gap between files
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue

    # Sort subtitles by start time to handle any potential overlaps
    all_subtitles.sort(key=lambda x: parse_time(x[1]))

    # Renumber subtitles after sorting
    all_subtitles = [(i+1, start, end, text) for i, (_, start, end, text) in enumerate(all_subtitles)]

    # Generate merged SRT content
    merged_content = ""
    for idx, start, end, text in all_subtitles:
        merged_content += f"{idx}\n{start} --> {end}\n{text}\n\n"

    return merged_content

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python merge_srt.py output.srt input1.srt input2.srt ...")
        sys.exit(1)

    output_file = sys.argv[1]
    input_files = sys.argv[2:]

    merged_content = merge_subtitle_files(input_files)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(merged_content)
"""

            # Save the merge script
            script_path = "merge_srt.py"
            with open(script_path, "w") as f:
                f.write(merge_script)

            # Create a command to run the script
            cmd = ["python3", script_path, output_file, *files]

            # Run the script to merge SRT files
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()

            # Check if the output file was created
            if os.path.exists(output_file):
                return ["echo", "Subtitle merge completed"], output_file
            # Fallback to copying the first subtitle file
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-i",
                files[0],
                "-c",
                "copy",
                "-threads",
                f"{max(1, cpu_no // 2)}",
                output_file,
            ]
            return cmd, output_file
        # For other subtitle formats, just copy the first file as a placeholder
        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-i",
            files[0],
            "-c",
            "copy",
            "-threads",
            f"{max(1, cpu_no // 2)}",
            output_file,
        ]
        return cmd, output_file
    else:
        return None, None

    # Use default thread count
    thread_count = max(1, cpu_no // 2)

    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        *input_args,
        "-ignore_unknown",
        "-filter_complex",
        filter_complex,
        *map_args,
        "-threads",
        f"{thread_count}",
        output_file,
    ]

    return cmd, output_file


async def get_merge_mixed_cmd(
    video_files,
    audio_files,
    subtitle_files,
    output_format="mkv",
    # codec_groups parameter removed - will be added back when implemented
):
    import os

    # Resource manager removed

    """Generate FFmpeg command for merging mixed media types.

    Args:
        video_files: List of video file paths
        audio_files: List of audio file paths
        subtitle_files: List of subtitle file paths
        output_format: Output file format (default: mkv)

    Returns:
        tuple: FFmpeg command and output file path
    """
    # Note: codec_groups parameter is reserved for future use to optimize codec selection
    if not video_files and not audio_files:
        return None, None

    # Use files in the order they were provided
    # (No sorting to preserve user's intended order)
    video_files = video_files if video_files else []
    audio_files = audio_files if audio_files else []
    subtitle_files = subtitle_files if subtitle_files else []

    # Determine output path based on first available file and media types
    base_files = video_files or audio_files or subtitle_files
    base_dir = os.path.dirname(base_files[0])

    # Determine appropriate output file name based on media types
    if video_files:
        output_file = os.path.join(base_dir, f"merged_video.{output_format}")
    elif audio_files:
        output_file = os.path.join(base_dir, f"merged_audio.{output_format}")
    elif subtitle_files:
        output_file = os.path.join(base_dir, f"merged_subtitle.{output_format}")
    else:
        output_file = os.path.join(base_dir, f"merged.{output_format}")

    # For mixed media types, we have several approaches:
    # 1. If we have multiple video files, merge them first, then add audio and subtitles
    # 2. If we have one video file and multiple audio files, use the video as base and add all audio tracks
    # 3. If we have multiple audio files only, merge them using filter_complex

    # Approach 1: Multiple video files with or without audio/subtitles
    if len(video_files) > 1:
        # First, merge all video files using concat demuxer
        # Create a temporary file list for concat demuxer
        concat_list_path = "concat_list.txt"
        with open(concat_list_path, "w") as f:
            for file_path in video_files:
                # Escape single quotes in file paths
                escaped_path = file_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # Create a temporary merged video file
        temp_video_output = os.path.join(
            base_dir, f"temp_merged_video.{output_format}"
        )
        video_cmd = [
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
            "-map",
            "0",  # Map all streams from input to preserve all video and audio tracks
            "-c",
            "copy",
            "-metadata",
            "title=Merged Video",
            "-threads",
            f"{max(1, cpu_no // 2)}",
            temp_video_output,
        ]

        # If we have audio files, add them to the merged video
        if audio_files:
            # Build input arguments
            input_args = ["-i", temp_video_output]  # Merged video as first input
            map_args = [
                "-map",
                "0",
            ]  # Map all streams from merged video to preserve all tracks

            # Add audio files
            for i, audio_file in enumerate(audio_files):
                input_args.extend(["-i", audio_file])
                map_args.extend(
                    [
                        "-map",
                        f"{i + 1}:a:0",
                        f"-metadata:s:a:{i}",
                        f"title=Audio Track {i + 1}",
                    ]
                )

            # Add subtitle files if supported by the output format
            if subtitle_files and output_format in ["mkv", "mp4"]:
                for i, sub_file in enumerate(subtitle_files):
                    input_args.extend(["-i", sub_file])
                    map_args.extend(
                        [
                            "-map",
                            f"{i + 1 + len(audio_files)}:s?",
                            f"-metadata:s:s:{i}",
                            f"title=Subtitle Track {i + 1}",
                        ]
                    )

            # Use default thread count
            thread_count = max(1, cpu_no // 2)

            # Create final command
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                *input_args,
                "-ignore_unknown",
                *map_args,  # Map all streams including video, audio, and subtitle streams
                "-c",
                "copy",
                "-threads",
                f"{thread_count}",
                output_file,
            ]

            return cmd, output_file
        # Just return the merged video command
        return video_cmd, temp_video_output

    # Approach 2: Single video file with multiple audio/subtitle tracks
    if len(video_files) == 1:
        # Use the video file as the base
        video_base = video_files[0]

        # Get video stream info
        video_streams = await get_streams(video_base)
        if not video_streams:
            return None, None

        # Log video stream info for debugging
        LOGGER.info(f"Using video file as base: {video_base}")
        video_info = {}
        for stream in video_streams:
            if stream.get("codec_type") == "video":
                video_info["codec"] = stream.get("codec_name")
                video_info["width"] = stream.get("width")
                video_info["height"] = stream.get("height")
                video_info["duration"] = stream.get("duration")
                break
        LOGGER.info(f"Video base info: {video_info}")

        # Build input arguments
        input_args = ["-i", video_base]
        map_args = [
            "-map",
            "0",
        ]  # Map all streams from the video file to preserve all tracks

        # Count audio tracks in video file for metadata
        audio_tracks_in_video = 0
        for stream in video_streams:
            if stream.get("codec_type") == "audio":
                audio_tracks_in_video += 1

        has_audio_in_video = audio_tracks_in_video > 0

        # Add external audio files
        audio_track_num = 1 if has_audio_in_video else 0
        for i, audio_file in enumerate(audio_files):
            input_args.extend(["-i", audio_file])
            map_args.extend(
                [
                    "-map",
                    f"{i + 1}:a:0",
                    f"-metadata:s:a:{audio_track_num}",
                    f"title=External Audio {i + 1}",
                ]
            )
            audio_track_num += 1

        # Add subtitle files if supported by the output format
        if subtitle_files and output_format in ["mkv", "mp4"]:
            sub_offset = len(audio_files) + 1
            for i, sub_file in enumerate(subtitle_files):
                # Get subtitle format
                sub_format = os.path.splitext(sub_file)[1].lower()

                # Handle subtitles differently based on format
                if sub_format in [".srt", ".vtt", ".ass", ".ssa"]:
                    # For text-based subtitles, we need to handle them specially to fix duration issues
                    # First, get video duration
                    video_duration = None
                    video_streams = await get_streams(video_base)
                    if video_streams:
                        for stream in video_streams:
                            if stream.get("codec_type") == "video":
                                # Try to get duration from stream or format info
                                try:
                                    import json
                                    import subprocess

                                    cmd = [
                                        "ffprobe",  # Keep as ffprobe, not xtra
                                        "-v",
                                        "error",
                                        "-show_entries",
                                        "format=duration",
                                        "-of",
                                        "json",
                                        video_base,
                                    ]
                                    result = subprocess.run(
                                        cmd,
                                        capture_output=True,
                                        text=True,
                                        check=False,
                                    )
                                    if result.returncode == 0:
                                        data = json.loads(result.stdout)
                                        if (
                                            "format" in data
                                            and "duration" in data["format"]
                                        ):
                                            video_duration = float(
                                                data["format"]["duration"]
                                            )
                                except Exception:
                                    pass

                    # If we have video duration, create a temporary subtitle file with correct duration
                    if video_duration:
                        LOGGER.info(
                            f"Using video duration {video_duration} for subtitle"
                        )
                        # Create a temporary subtitle file with adjusted timestamps
                        try:
                            import os
                            import re
                            import tempfile

                            # Create a temporary file for the adjusted subtitle
                            temp_sub_file = tempfile.NamedTemporaryFile(
                                suffix=".srt", delete=False
                            )
                            temp_sub_path = temp_sub_file.name
                            temp_sub_file.close()

                            # Read the original subtitle file
                            with open(sub_file, encoding="utf-8") as f:
                                content = f.read()

                            # Find the last timestamp in the subtitle file
                            last_timestamp_match = re.findall(
                                r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})",
                                content,
                            )
                            if last_timestamp_match:
                                # Get the last end timestamp
                                last_end_time = last_timestamp_match[-1][1]

                                # Convert timestamp to seconds
                                h, m, s = last_end_time.split(":")[0:3]
                                s, ms = s.split(",")
                                last_time_seconds = (
                                    int(h) * 3600
                                    + int(m) * 60
                                    + int(s)
                                    + int(ms) / 1000
                                )

                                # If the last subtitle timestamp is beyond video duration or too short, adjust all timestamps
                                if (
                                    last_time_seconds > video_duration
                                    or last_time_seconds < (video_duration * 0.5)
                                ):
                                    # If subtitle is too short, extend it. If too long, compress it.
                                    scale_factor = video_duration / last_time_seconds
                                    LOGGER.info(
                                        f"Adjusting subtitle timing with scale factor {scale_factor:.2f} (subtitle duration: {last_time_seconds:.2f}s, video duration: {video_duration:.2f}s)"
                                    )

                                    # Function to adjust timestamp
                                    def adjust_timestamp(timestamp, scale):
                                        h, m, s = timestamp.split(":")[0:3]
                                        s, ms = s.split(",")
                                        total_seconds = (
                                            int(h) * 3600
                                            + int(m) * 60
                                            + int(s)
                                            + int(ms) / 1000
                                        ) * scale

                                        new_h = int(total_seconds // 3600)
                                        new_m = int((total_seconds % 3600) // 60)
                                        new_s = int(total_seconds % 60)
                                        new_ms = int((total_seconds * 1000) % 1000)

                                        return f"{new_h:02d}:{new_m:02d}:{new_s:02d},{new_ms:03d}"

                                    # Adjust all timestamps in the subtitle file
                                    adjusted_content = re.sub(
                                        r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})",
                                        lambda m: f"{adjust_timestamp(m.group(1), scale_factor)} --> {adjust_timestamp(m.group(2), scale_factor)}",
                                        content,
                                    )

                                    # Write the adjusted subtitle to the temporary file
                                    with open(
                                        temp_sub_path, "w", encoding="utf-8"
                                    ) as f:
                                        f.write(adjusted_content)

                                    # Use the temporary subtitle file instead
                                    sub_file = temp_sub_path
                                    LOGGER.info(
                                        f"Created adjusted subtitle file with scale factor {scale_factor}"
                                    )
                        except Exception:
                            pass

                        # Add input with the adjusted subtitle file
                        input_args.extend(["-i", sub_file])
                        map_args.extend(
                            [
                                "-map",
                                f"{sub_offset + i}:s?",
                                f"-metadata:s:s:{i}",
                                f"title=External Subtitle {i + 1}",
                                # Force subtitle duration to match video
                                "-c:s",
                                "copy",
                            ]
                        )
                    else:
                        # Fallback to standard mapping
                        input_args.extend(["-i", sub_file])
                        map_args.extend(
                            [
                                "-map",
                                f"{sub_offset + i}:s?",
                                f"-metadata:s:s:{i}",
                                f"title=External Subtitle {i + 1}",
                                "-c:s",
                                "copy",
                            ]
                        )
                else:
                    # For other subtitle formats, use standard mapping
                    input_args.extend(["-i", sub_file])
                    map_args.extend(
                        [
                            "-map",
                            f"{sub_offset + i}:s?",
                            f"-metadata:s:s:{i}",
                            f"title=External Subtitle {i + 1}",
                        ]
                    )

        # Use default thread count
        thread_count = max(1, cpu_no // 2)

        # Create final command
        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            *input_args,
            "-ignore_unknown",
            *map_args,  # Map all streams including video, audio, and subtitle streams
            "-c",
            "copy",
            "-threads",
            f"{thread_count}",
            output_file,
        ]

        return cmd, output_file

    # Approach 3: Audio files only
    if audio_files:
        # For audio-only merge, use filter_complex
        filter_complex = ""
        for i, _ in enumerate(audio_files):
            filter_complex += f"[{i}:a:0]"
        filter_complex += f"concat=n={len(audio_files)}:v=0:a=1[outa]"

        # Build input arguments
        input_args = []
        for file_path in audio_files:
            input_args.extend(["-i", file_path])

        # Set audio codec based on output format
        codec_args = []
        if output_format == "mp3":
            codec_args = ["-c:a", "libmp3lame", "-q:a", "0"]
        elif output_format in {"aac", "m4a"}:
            codec_args = ["-c:a", "aac", "-b:a", "320k"]
        elif output_format == "flac":
            codec_args = ["-c:a", "flac"]
        elif output_format == "opus":
            codec_args = ["-c:a", "libopus", "-b:a", "256k"]
        else:
            # Default to AAC for other formats
            codec_args = ["-c:a", "aac", "-b:a", "320k"]

        # Use default thread count
        thread_count = max(1, cpu_no // 2)

        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            *input_args,
            "-filter_complex",
            filter_complex,
            "-map",
            "[outa]",
            *codec_args,
            "-threads",
            f"{thread_count}",
            output_file,
        ]

        return cmd, output_file

    # Fallback to a simpler approach if needed
    # This approach works for a single video file with a single audio file and optional subtitle
    if len(video_files) == 1 and len(audio_files) <= 1:
        # Build input arguments
        input_args = ["-i", video_files[0]]  # Video file
        map_args = [
            "-map",
            "0",
        ]  # Map all streams from video file to preserve all tracks

        # Add external audio file if available
        if audio_files:
            input_args.extend(["-i", audio_files[0]])
            map_args.extend(
                ["-map", "1:a:0", "-metadata:s:a:0", "title=External Audio"]
            )

        # Add subtitle file if available and supported by the output format
        if subtitle_files and output_format in ["mkv", "mp4"]:
            sub_file = subtitle_files[0]
            # Get subtitle format
            sub_format = os.path.splitext(sub_file)[1].lower()

            # Handle subtitles differently based on format
            if sub_format in [".srt", ".vtt", ".ass", ".ssa"]:
                # For text-based subtitles, we need to handle them specially to fix duration issues
                # First, get video duration
                video_duration = None
                video_streams = await get_streams(video_files[0])
                if video_streams:
                    try:
                        import json
                        import subprocess

                        cmd = [
                            "ffprobe",  # Keep as ffprobe, not xtra
                            "-v",
                            "error",
                            "-show_entries",
                            "format=duration",
                            "-of",
                            "json",
                            video_files[0],
                        ]
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, check=False
                        )
                        if result.returncode == 0:
                            data = json.loads(result.stdout)
                            if "format" in data and "duration" in data["format"]:
                                video_duration = float(data["format"]["duration"])
                    except Exception:
                        pass

                # Create a temporary subtitle file with adjusted timestamps
                try:
                    # Read the original subtitle file
                    with open(sub_file, encoding="utf-8") as f:
                        content = f.read()

                    # Find the last timestamp in the subtitle file
                    last_timestamp_match = re.findall(
                        r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})",
                        content,
                    )
                    if last_timestamp_match:
                        # Get the last end timestamp
                        last_end_time = last_timestamp_match[-1][1]

                        # Convert timestamp to seconds
                        h, m, s = last_end_time.split(":")[0:3]
                        s, ms = s.split(",")
                        last_time_seconds = (
                            int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
                        )

                        # If the last subtitle timestamp is beyond video duration, adjust all timestamps
                        if last_time_seconds > video_duration:
                            scale_factor = video_duration / last_time_seconds

                            # Function to adjust timestamp
                            def adjust_timestamp(timestamp, scale):
                                h, m, s = timestamp.split(":")[0:3]
                                s, ms = s.split(",")
                                total_seconds = (
                                    int(h) * 3600
                                    + int(m) * 60
                                    + int(s)
                                    + int(ms) / 1000
                                ) * scale

                                new_h = int(total_seconds // 3600)
                                new_m = int((total_seconds % 3600) // 60)
                                new_s = int(total_seconds % 60)
                                new_ms = int((total_seconds * 1000) % 1000)

                                return f"{new_h:02d}:{new_m:02d}:{new_s:02d},{new_ms:03d}"

                            # Adjust all timestamps in the subtitle file
                            adjusted_content = re.sub(
                                r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})",
                                lambda m: f"{adjust_timestamp(m.group(1), scale_factor)} --> {adjust_timestamp(m.group(2), scale_factor)}",
                                content,
                            )

                            # Create a temporary file for the adjusted subtitle
                            temp_sub_file = tempfile.NamedTemporaryFile(
                                suffix=".srt", delete=False
                            )
                            temp_sub_path = temp_sub_file.name
                            temp_sub_file.close()

                            # Write the adjusted subtitle to the temporary file
                            with open(temp_sub_path, "w", encoding="utf-8") as f:
                                f.write(adjusted_content)

                            # Use the temporary subtitle file instead
                            sub_file = temp_sub_path

                except Exception:
                    pass

                # Add input with the adjusted subtitle file
                input_args.extend(["-i", sub_file])

                # Map subtitle with appropriate options
                map_args.extend(
                    [
                        "-map",
                        f"{1 + (1 if audio_files else 0)}:s?",
                        "-metadata:s:s:0",
                        "title=External Subtitle",
                        # Force subtitle duration to match video
                        "-c:s",
                        "copy",
                    ]
                )
            else:
                # For other subtitle formats, use standard mapping
                input_args.extend(["-i", sub_file])
                map_args.extend(
                    [
                        "-map",
                        f"{1 + (1 if audio_files else 0)}:s?",
                        "-metadata:s:s:0",
                        "title=External Subtitle",
                    ]
                )

        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            *input_args,
            *map_args,
            "-c",
            "copy",
            "-threads",
            f"{max(1, cpu_no // 2)}",
            output_file,
        ]

        return cmd, output_file

    # If all else fails, use a very simple approach
    # Just use the first video file and preserve all its tracks
    if video_files:
        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-i",
            video_files[0],
            "-map",
            "0",  # Map all streams to preserve all video, audio, and subtitle tracks
            "-c",
            "copy",
            "-threads",
            f"{max(1, cpu_no // 2)}",
            output_file,
        ]
        return cmd, output_file

    # If no video files, use the first audio file and preserve all its tracks
    if audio_files:
        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-i",
            audio_files[0],
            "-map",
            "0",  # Map all streams to preserve all audio tracks
            "-c",
            "copy",
            "-threads",
            f"{max(1, cpu_no // 2)}",
            output_file,
        ]
        return cmd, output_file

    return None, None


async def analyze_media_for_merge(files):
    """Analyze media files and categorize them for merging.

    Args:
        files: List of file paths

    Returns:
        dict: Dictionary with categorized files and recommended merge approach
    """
    video_files = []
    audio_files = []
    subtitle_files = []
    image_files = []
    document_files = []
    unknown_files = []

    # Detailed media info for advanced analysis
    video_info = []
    audio_info = []
    subtitle_info = []
    image_info = []
    document_info = []

    # Categorize files by media type with detailed info
    for file_path in files:
        # Check file extension first for faster categorization
        ext = os.path.splitext(file_path)[1].lower()

        # Categorize images by extension
        if ext in [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".tiff",
            ".tif",
        ]:
            image_files.append(file_path)
            image_info.append(
                {
                    "path": file_path,
                    "format": ext[1:],  # Remove the dot
                    "size": os.path.getsize(file_path),
                }
            )
            continue

        # Categorize documents by extension
        if ext in [".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf"]:
            document_files.append(file_path)
            document_info.append(
                {
                    "path": file_path,
                    "format": ext[1:],  # Remove the dot
                    "size": os.path.getsize(file_path),
                }
            )
            continue

        # For other files, use FFprobe to determine media type
        media_type = await get_media_type_internal(file_path)
        if media_type == "video":
            video_files.append(file_path)
            # Get detailed video info
            streams = await get_streams(file_path)
            if streams:
                video_info.append(
                    {
                        "path": file_path,
                        "streams": streams,
                        "format": os.path.splitext(file_path)[1][1:].lower(),
                        "size": os.path.getsize(file_path),
                    }
                )
        elif media_type == "audio":
            audio_files.append(file_path)
            # Get detailed audio info
            streams = await get_streams(file_path)
            if streams:
                audio_info.append(
                    {
                        "path": file_path,
                        "streams": streams,
                        "format": os.path.splitext(file_path)[1][1:].lower(),
                        "size": os.path.getsize(file_path),
                    }
                )
        elif media_type == "subtitle":
            subtitle_files.append(file_path)
            # Get subtitle format
            subtitle_info.append(
                {
                    "path": file_path,
                    "format": os.path.splitext(file_path)[1][1:].lower(),
                    "size": os.path.getsize(file_path),
                }
            )
        else:
            unknown_files.append(file_path)

    # Check for codec compatibility in video files
    video_codec_groups = {}
    video_resolution_groups = {}

    for info in video_info:
        video_codec = None
        audio_codec = None
        width = None
        height = None

        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video" and not stream.get(
                "disposition", {}
            ).get("attached_pic"):
                video_codec = stream.get("codec_name")
                width = stream.get("width")
                height = stream.get("height")
            elif stream.get("codec_type") == "audio":
                audio_codec = stream.get("codec_name")

        # Group by video codec for better merge strategy
        codec_key = f"{video_codec}_{audio_codec}"
        if codec_key not in video_codec_groups:
            video_codec_groups[codec_key] = []
        video_codec_groups[codec_key].append(info["path"])

        # Group by resolution for better scaling decisions
        if width and height:
            resolution_key = f"{width}x{height}"
            if resolution_key not in video_resolution_groups:
                video_resolution_groups[resolution_key] = []
            video_resolution_groups[resolution_key].append(info["path"])

    # Check for codec compatibility in audio files
    audio_codec_groups = {}
    for info in audio_info:
        audio_codec = None
        # Note: We collect these properties for future enhancements
        # sample_rate and channels could be used for advanced audio merging

        for stream in info.get("streams", []):
            if stream.get("codec_type") == "audio":
                audio_codec = stream.get("codec_name")
                # These properties are collected but not used yet
                # sample_rate = stream.get("sample_rate")
                # channels = stream.get("channels")
                break

        # Group by audio codec and properties for better merge strategy
        codec_key = audio_codec or "unknown"
        if codec_key not in audio_codec_groups:
            audio_codec_groups[codec_key] = []
        audio_codec_groups[codec_key].append(info["path"])

    # Group subtitle files by format
    subtitle_format_groups = {}
    for info in subtitle_info:
        subtitle_format = info["format"]
        if subtitle_format not in subtitle_format_groups:
            subtitle_format_groups[subtitle_format] = []
        subtitle_format_groups[subtitle_format].append(info["path"])

    # Group image files by format
    image_format_groups = {}
    for info in image_info:
        image_format = info["format"]
        if image_format not in image_format_groups:
            image_format_groups[image_format] = []
        image_format_groups[image_format].append(info["path"])

    # Group document files by format
    document_format_groups = {}
    for info in document_info:
        document_format = info["format"]
        if document_format not in document_format_groups:
            document_format_groups[document_format] = []
        document_format_groups[document_format].append(info["path"])

    # Determine recommended merge approach based on detailed analysis
    total_media_files = (
        len(video_files)
        + len(audio_files)
        + len(subtitle_files)
        + len(image_files)
        + len(document_files)
    )

    if total_media_files == 0:
        recommended_approach = None
    elif (
        len(video_files) > 0
        and len(audio_files) == 0
        and len(subtitle_files) == 0
        and len(image_files) == 0
        and len(document_files) == 0
    ):
        # All videos - check if we can use concat demuxer (same codec and resolution)
        if len(video_codec_groups) == 1 and len(video_resolution_groups) == 1:
            # All videos have same codec and resolution - can use concat demuxer
            recommended_approach = "concat_demuxer"
        elif len(video_resolution_groups) > 1:
            # Different resolutions - need to use filter_complex with scaling
            recommended_approach = "filter_complex"
        else:
            # Different codecs but same resolution - can try concat demuxer with transcoding
            recommended_approach = "concat_demuxer"
    elif (
        len(audio_files) > 0
        and len(video_files) == 0
        and len(subtitle_files) == 0
        and len(image_files) == 0
        and len(document_files) == 0
    ):
        # All audios - check if we can use concat demuxer (same codec)
        if len(audio_codec_groups) == 1:
            # All audios have same codec - can use concat demuxer
            recommended_approach = "concat_demuxer"
        else:
            # Different codecs - need to use filter_complex
            recommended_approach = "filter_complex"
    elif (
        len(subtitle_files) > 0
        and len(video_files) == 0
        and len(audio_files) == 0
        and len(image_files) == 0
        and len(document_files) == 0
    ):
        # All subtitles - check if we can use concat demuxer (same format)
        if len(subtitle_format_groups) == 1:
            # All subtitles have same format - can use concat demuxer
            recommended_approach = "concat_demuxer"
        else:
            # Different formats - need special handling
            recommended_approach = "subtitle_special"
    elif (
        len(image_files) > 0
        and len(video_files) == 0
        and len(audio_files) == 0
        and len(subtitle_files) == 0
        and len(document_files) == 0
    ):
        # All images - use PIL for merging
        recommended_approach = "image_merge"
    elif (
        len(document_files) > 0
        and len(video_files) == 0
        and len(audio_files) == 0
        and len(subtitle_files) == 0
        and len(image_files) == 0
    ):
        # All documents - use PDF merging
        recommended_approach = "document_merge"
    # Mixed media types - need to use filter_complex or mixed approach
    elif len(video_files) > 0 and (len(audio_files) > 0 or len(subtitle_files) > 0):
        recommended_approach = "mixed"
    elif len(video_files) > 0 and len(image_files) > 0:
        # Video and images - can create a slideshow
        recommended_approach = "slideshow"
    else:
        # Other combinations - use separate merges
        recommended_approach = "separate"

    return {
        "video_files": video_files,
        "audio_files": audio_files,
        "subtitle_files": subtitle_files,
        "image_files": image_files,
        "document_files": document_files,
        "unknown_files": unknown_files,
        "video_codec_groups": video_codec_groups,
        "video_resolution_groups": video_resolution_groups,
        "audio_codec_groups": audio_codec_groups,
        "subtitle_format_groups": subtitle_format_groups,
        "image_format_groups": image_format_groups,
        "document_format_groups": document_format_groups,
        "recommended_approach": recommended_approach,
    }


async def get_convert_cmd(
    file,
    output_format,
    media_type=None,
    video_codec="libx264",
    audio_codec="aac",
    video_preset="medium",
    video_crf=23,
    audio_bitrate="128k",
    # subtitle_encoding is not used but kept for API compatibility
    maintain_quality=True,
):
    """Generate FFmpeg command for converting media files to different formats.

    Args:
        file: Path to the input file
        output_format: Desired output format (e.g., mp4, mkv, mp3, etc.)
        media_type: Type of media (video, audio, subtitle, document, archive)
        video_codec: Video codec to use for video conversion
        audio_codec: Audio codec to use for audio conversion
        video_preset: Video encoding preset for video conversion
        video_crf: Constant Rate Factor for video quality (lower is better)
        audio_bitrate: Audio bitrate for audio conversion
        subtitle_encoding: Subtitle encoding for subtitle conversion
        maintain_quality: Whether to maintain original quality

    Returns:
        tuple: FFmpeg command and temporary output file path, or None, None if not supported
    """
    # Import necessary modules
    from bot import cpu_no
    from bot.helper.ext_utils.media_utils import get_media_type

    # Determine media type if not provided
    if not media_type:
        media_type = await get_media_type(file)
        if not media_type:
            return None, None

    # Determine output file extension based on output format
    output_ext = f".{output_format.lower()}"
    temp_file = f"{file}.temp{output_ext}"

    # Use default thread count
    thread_count = max(1, cpu_no // 2)

    # Base command for all media types
    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file,
        "-ignore_unknown",
    ]

    # Add media-specific parameters
    if media_type == "video":
        # For video files
        if maintain_quality:
            video_crf = min(
                video_crf, 18
            )  # Use better quality if maintain_quality is enabled

        cmd.extend(
            [
                "-c:v",
                video_codec,
                "-preset",
                video_preset,
                "-crf",
                str(video_crf),
                "-c:a",
                audio_codec,
                "-b:a",
                audio_bitrate,
                "-map",
                "0:v?",
                "-map",
                "0:a?",
                "-map",
                "0:s?",
                "-map",
                "0:t?",
                "-threads",
                f"{thread_count}",
                temp_file,
            ]
        )

    elif media_type == "audio":
        # For audio files
        if output_format.lower() in ["mp3", "aac", "ogg", "opus", "flac", "wav"]:
            # Set codec based on output format
            if output_format.lower() == "mp3":
                audio_codec = "libmp3lame"
            elif output_format.lower() == "aac":
                audio_codec = "aac"
            elif output_format.lower() == "ogg":
                audio_codec = "libvorbis"
            elif output_format.lower() == "opus":
                audio_codec = "libopus"
            elif output_format.lower() == "flac":
                audio_codec = "flac"
            elif output_format.lower() == "wav":
                audio_codec = "pcm_s16le"

            # Set quality based on maintain_quality flag
            if maintain_quality:
                if output_format.lower() == "mp3":
                    audio_bitrate = "320k"
                elif (
                    output_format.lower() == "aac" or output_format.lower() == "ogg"
                ):
                    audio_bitrate = "256k"
                elif output_format.lower() == "opus":
                    audio_bitrate = "192k"
                # For lossless formats like FLAC and WAV, bitrate doesn't apply

            cmd.extend(
                [
                    "-c:a",
                    audio_codec,
                    "-b:a",
                    audio_bitrate
                    if audio_codec not in ["flac", "pcm_s16le"]
                    else "",
                    "-map",
                    "0:a",
                    "-threads",
                    f"{thread_count}",
                    temp_file,
                ]
            )
        else:
            return None, None

    elif media_type == "subtitle":
        # For subtitle files
        if output_format.lower() in ["srt", "ass", "ssa", "vtt", "sub"]:
            cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                file,
                "-c:s",
                "text" if output_format.lower() == "srt" else output_format.lower(),
                "-threads",
                f"{thread_count}",
                temp_file,
            ]
        else:
            return None, None

    elif media_type == "document":
        # For document files (PDF, DOCX, etc.)
        # Document conversion is complex and might require specialized tools
        # For now, we'll just return None for unsupported formats
        return None, None

    elif media_type == "archive":
        # For archive files (ZIP, RAR, etc.)
        # Archive conversion is complex and might require specialized tools
        # For now, we'll just return None for unsupported formats
        return None, None

    else:
        # For other media types
        return None, None

    return cmd, temp_file


async def get_trim_cmd(
    file,
    trim_params=None,
    video_codec="none",
    video_preset="none",
    video_format="none",
    audio_codec="none",
    audio_preset="none",  # audio_preset is not used but kept for API compatibility
    audio_format="none",
    image_quality="none",
    image_format="none",
    document_quality="none",  # document_quality is not used but kept for API compatibility
    document_format="none",
    subtitle_encoding="none",
    subtitle_format="none",
    archive_format="none",
    start_time=None,
    end_time=None,
    delete_original=False,
):
    """Generate FFmpeg command for trimming media files.

    Args:
        file: Path to the input file
        trim_params: String containing trim parameters in format "start_time-end_time" (deprecated)
        video_codec: Video codec to use for trimming
        video_preset: Video preset to use for trimming
        video_format: Output format for video trimming
        audio_codec: Audio codec to use for trimming
        audio_preset: Audio preset to use for trimming
        audio_format: Output format for audio trimming
        image_quality: Quality for image trimming
        image_format: Output format for image trimming
        document_quality: Quality for document trimming
        document_format: Output format for document trimming
        subtitle_encoding: Encoding for subtitle trimming
        subtitle_format: Output format for subtitle trimming
        archive_format: Output format for archive trimming
        start_time: Start time for trimming (overrides trim_params)
        end_time: End time for trimming (overrides trim_params)
        delete_original: Whether to delete the original file after trimming

    Returns:
        tuple: FFmpeg command and temporary output file path, or None, None if not supported
    """
    # Import necessary modules
    import os

    from bot import LOGGER
    from bot.helper.ext_utils.media_utils import get_media_type, get_streams

    # First try to determine media type using get_media_type
    media_type = await get_media_type(file)

    # If get_media_type fails, try to determine by file extension
    if not media_type:
        file_ext = os.path.splitext(file)[1].lower()
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
        ]:
            media_type = "video"
        # Audio extensions
        elif file_ext in [".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aac"]:
            media_type = "audio"
        # Image extensions
        elif file_ext in [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".webp",
            ".tiff",
            ".tif",
            ".gif",
        ]:
            media_type = "image"
        # Subtitle extensions
        elif file_ext in [".srt", ".vtt", ".ass", ".ssa", ".sub"]:
            media_type = "subtitle"
        # Document extensions
        elif file_ext in [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"]:
            media_type = "document"
        # Archive extensions
        elif file_ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"]:
            media_type = "archive"

    if not media_type:
        return None, None

    # Parse trim parameters
    try:
        # If start_time and end_time are provided directly, use them
        if start_time is None and end_time is None and trim_params:
            # Fallback to the old trim_params format for backward compatibility
            if "-" in trim_params:
                start_time, end_time = trim_params.split("-", 1)
            else:
                # If only one time is provided, assume it's the start time and trim to the end
                start_time = trim_params
                end_time = None

            LOGGER.info(
                f"Using deprecated trim_params format: {trim_params}, parsed to start_time={start_time}, end_time={end_time}"
            )

        # If start_time is empty or "00:00:00", set it to None (beginning of file)
        if start_time in {"", "00:00:00"}:
            start_time = "00:00:00"

        # If end_time is empty, set it to None (end of file)
        if end_time == "":
            end_time = None

    except ValueError:
        LOGGER.error(
            f"Invalid trim parameters: trim_params={trim_params}, start_time={start_time}, end_time={end_time}"
        )
        return None, None

    # Enhanced time format validation
    def validate_time(time_str):
        if time_str is None:
            return None

        # Check if it's in seconds format (e.g., "120")
        if time_str.isdigit():
            return time_str

        # Check if it's in HH:MM:SS format (e.g., "00:02:00")
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) <= 3 and all(part.isdigit() for part in parts):
                return time_str

        # Check if it's in HH:MM:SS.mmm format (e.g., "00:02:00.500")
        if ":" in time_str and "." in time_str:
            time_parts = time_str.split(".")
            if len(time_parts) == 2 and time_parts[1].isdigit():
                parts = time_parts[0].split(":")
                if len(parts) <= 3 and all(part.isdigit() for part in parts):
                    return time_str

        LOGGER.error(f"Invalid time format: {time_str}")
        return None

    start_time = validate_time(start_time)
    end_time = validate_time(end_time)

    if start_time is None:
        LOGGER.error("Invalid start time for trimming")
        return None, None

    # Determine output file extension based on input file or specified format
    file_ext = os.path.splitext(file)[1].lower()

    # We already have the media type from earlier, no need to get it again

    # Determine output extension based on specified format
    if media_type == "video" and video_format and video_format != "none":
        output_ext = f".{video_format.lower()}"
    elif media_type == "audio" and audio_format and audio_format != "none":
        output_ext = f".{audio_format.lower()}"
    elif media_type == "image" and image_format and image_format != "none":
        output_ext = f".{image_format.lower()}"
    elif media_type == "document" and document_format and document_format != "none":
        output_ext = f".{document_format.lower()}"
    elif media_type == "subtitle" and subtitle_format and subtitle_format != "none":
        output_ext = f".{subtitle_format.lower()}"
    elif media_type == "archive" and archive_format and archive_format != "none":
        output_ext = f".{archive_format.lower()}"
    else:
        # Use the original extension if no format is specified
        output_ext = file_ext

    temp_file = f"{file}.trim{output_ext}"

    # Get file information for better handling
    streams = await get_streams(file)

    # Base command for all media types
    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
    ]

    # Add trim parameters - for better accuracy, put -ss before -i for seeking
    if start_time:
        cmd.extend(["-ss", start_time])

    # Add input file
    cmd.extend(["-i", file])

    # Add end time parameter
    if end_time:
        cmd.extend(["-to", end_time])

    # Add media-specific parameters
    if media_type == "video":
        # Check if the file has video streams
        has_video = False
        has_audio = False
        # We don't need to track subtitle streams here as we always copy them

        if streams:
            for stream in streams:
                if stream.get("codec_type") == "video" and not stream.get(
                    "disposition", {}
                ).get("attached_pic"):
                    has_video = True
                elif stream.get("codec_type") == "audio":
                    has_audio = True
                # We don't need to check for subtitles here as we're always copying them

        # Add video codec parameters
        if has_video:
            # Check if this is a HEVC/10-bit MKV file
            is_hevc_10bit = file_ext.lower() == ".mkv" and (
                "10bit" in file.lower()
                or "10bi" in file.lower()
                or "hevc" in file.lower()
            )

            # For HEVC/10-bit MKV files, always use copy codec for better compatibility
            if is_hevc_10bit:
                LOGGER.info(
                    f"Detected HEVC/10-bit MKV file, using copy codec: {file}"
                )
                cmd.extend(["-c:v", "copy"])
            # Check if video_codec is "none" (case-insensitive) or None
            elif not video_codec or video_codec.lower() == "none":
                # Use copy codec as default when none is specified
                cmd.extend(["-c:v", "copy"])
            else:
                cmd.extend(["-c:v", video_codec])

                if video_codec != "copy":
                    # Check if video_preset is "none" (case-insensitive) or None
                    if video_preset and video_preset.lower() != "none":
                        cmd.extend(["-preset", video_preset])
                    # Ensure even dimensions for encoded video
                    cmd.extend(["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                    # Ensure compatible pixel format
                    cmd.extend(["-pix_fmt", "yuv420p"])
                    # Add quality parameter for better results
                    cmd.extend(["-crf", "23"])

        # Add audio codec parameters
        if has_audio:
            # Check if audio_codec is "none" (case-insensitive) or None
            if not audio_codec or audio_codec.lower() == "none":
                # Use copy codec as default when none is specified
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-c:a", audio_codec])

                if audio_codec != "copy":
                    if audio_codec == "aac":
                        cmd.extend(["-b:a", "192k"])
                    elif audio_codec == "libmp3lame":
                        cmd.extend(["-q:a", "3"])
                    elif audio_codec == "libopus":
                        cmd.extend(["-b:a", "128k"])

        # Always copy subtitle tracks
        cmd.extend(["-c:s", "copy"])

        # Map all streams
        cmd.extend(["-map", "0"])

        # Add avoid_negative_ts to fix timestamp issues
        cmd.extend(["-avoid_negative_ts", "make_zero"])

        # Add container-specific parameters
        if file_ext == ".mp4":
            # For MP4, ensure compatibility
            cmd.extend(["-movflags", "+faststart"])
        elif file_ext == ".mkv":
            # For MKV, no special parameters needed
            pass
        elif file_ext == ".avi":
            # For AVI, ensure compatibility
            if video_codec != "copy":
                cmd.extend(["-c:v", "libx264"])
        elif file_ext == ".webm":
            # For WebM, use VP9 and Opus
            if video_codec != "copy":
                cmd.extend(["-c:v", "libvpx-vp9", "-b:v", "1M"])
            if audio_codec != "copy":
                cmd.extend(["-c:a", "libopus", "-b:a", "128k"])
        elif file_ext == ".hevc":
            # For HEVC files, ensure we use a proper container
            # Change the output file extension to .mp4
            temp_file = f"{os.path.splitext(file)[0]}.trim.mp4"

            # For raw HEVC files, we need to specify the format
            cmd.extend(["-f", "hevc"])

            # Use H.265 codec
            if video_codec == "copy":
                cmd.extend(["-c:v", "copy"])
            else:
                cmd.extend(
                    ["-c:v", "libx265", "-crf", "28", "-preset", video_preset]
                )

            # Add MP4 container flags
            cmd.extend(["-movflags", "+faststart"])

    elif media_type == "audio":
        # For audio files
        # Check if audio_codec is "none" (case-insensitive) or None
        if not audio_codec or audio_codec.lower() == "none":
            # Use copy codec as default when none is specified
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-c:a", audio_codec])

            if audio_codec != "copy":
                if audio_codec == "aac":
                    cmd.extend(["-b:a", "192k"])
                elif audio_codec == "libmp3lame":
                    cmd.extend(["-q:a", "3"])
                elif audio_codec == "libopus":
                    cmd.extend(["-b:a", "128k"])
                elif audio_codec == "flac":
                    cmd.extend(["-compression_level", "8"])

        # Map all audio streams
        cmd.extend(["-map", "0:a"])

        # Add avoid_negative_ts to fix timestamp issues
        cmd.extend(["-avoid_negative_ts", "make_zero"])

        # Add container-specific parameters
        if file_ext == ".mp3":
            if audio_codec == "copy":
                # For MP3 files, sometimes copy doesn't work well with trimming
                # Use re-encoding with high quality
                cmd.extend(["-c:a", "libmp3lame", "-q:a", "3"])
        elif file_ext == ".m4a":
            if audio_codec == "copy":
                # For M4A files, sometimes copy doesn't work well with trimming
                # Use re-encoding with high quality
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        elif file_ext == ".opus":
            if audio_codec == "copy":
                # For Opus files, sometimes copy doesn't work well with trimming
                # Use re-encoding with high quality
                cmd.extend(["-c:a", "libopus", "-b:a", "128k"])
        elif file_ext == ".flac":
            # For FLAC files, ensure we preserve quality
            if audio_codec == "copy":
                # No special parameters needed for FLAC copy
                pass
            else:
                # Use high quality for re-encoding
                cmd.extend(["-compression_level", "8"])

    elif media_type == "image":
        # For image files, we need special handling since images don't have duration
        # We'll create a short video from the image

        # Remove any existing trim parameters since they don't apply to images
        cmd = [
            "xtra",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-i",
            file,
        ]

        # For JPEG files
        if file_ext in [".jpg", ".jpeg"]:
            if (
                not image_quality
                or image_quality.lower() == "none"
                or image_quality == "0"
            ):
                cmd.extend(["-q:v", "1"])  # Best quality
            else:
                try:
                    quality_val = int(image_quality)
                    cmd.extend(["-q:v", str(min(31, 31 - int(quality_val * 0.31)))])
                except (ValueError, TypeError):
                    cmd.extend(["-q:v", "1"])  # Default to best quality
        # For PNG files
        elif file_ext in [".png"]:
            if (
                not image_quality
                or image_quality.lower() == "none"
                or image_quality == "0"
            ):
                cmd.extend(["-compression_level", "0"])  # Best quality
            else:
                try:
                    quality_val = int(image_quality)
                    cmd.extend(
                        [
                            "-compression_level",
                            str(min(9, 9 - int(quality_val * 0.09))),
                        ]
                    )
                except (ValueError, TypeError):
                    cmd.extend(
                        ["-compression_level", "0"]
                    )  # Default to best quality
        # For SVG files
        elif file_ext == ".svg":
            # SVG files need special handling - convert to PNG first
            return None, None
        # For PSD files
        elif file_ext == ".psd":
            # PSD files need special handling
            return None, None
        # For GIF files
        elif file_ext == ".gif":
            # For GIF, we need special handling
            # Check if it's an animated GIF by getting the number of frames
            streams = await get_streams(file)
            if streams and len(streams) > 0:
                # Try to get the number of frames
                nb_frames = 1
                for stream in streams:
                    if stream.get("codec_type") == "video" and stream.get(
                        "nb_frames"
                    ):
                        with contextlib.suppress(ValueError, TypeError):
                            nb_frames = int(stream.get("nb_frames"))

                # If it's an animated GIF (more than 1 frame)
                if nb_frames > 1:
                    LOGGER.info(
                        f"Detected animated GIF with {nb_frames} frames: {file}"
                    )

                    # For animated GIFs, we need to use a different approach
                    # We'll use palettegen and paletteuse filters to maintain quality
                    cmd = [
                        "xtra",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-progress",
                        "pipe:1",
                    ]

                    # Add input file with seek if needed
                    if start_time:
                        cmd.extend(["-ss", start_time])

                    cmd.extend(["-i", file])

                    # Add duration limit if needed
                    if end_time:
                        cmd.extend(["-to", end_time])

                    # Create a palette for better quality
                    cmd.extend(
                        [
                            "-vf",
                            "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a",
                            "-loop",
                            "0",  # Preserve looping
                        ]
                    )

                    # Ensure we're using the GIF format
                    cmd.extend(["-f", "gif"])
                else:
                    # For static GIFs, use a simpler approach
                    LOGGER.info(f"Detected static GIF: {file}")
                    cmd = [
                        "xtra",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-progress",
                        "pipe:1",
                    ]

                    # For static GIFs, it's better to put -ss before -i for accurate seeking
                    if start_time:
                        cmd.extend(["-ss", start_time])

                    cmd.extend(["-i", file])

                    if end_time:
                        cmd.extend(["-to", end_time])

                    # Use a simple filter to ensure the output is a valid GIF
                    cmd.extend(
                        ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-f", "gif"]
                    )
            else:
                # Fallback to a more robust approach if we can't determine frame count
                cmd = [
                    "xtra",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-progress",
                    "pipe:1",
                ]

                # Put -ss before -i for accurate seeking
                if start_time:
                    cmd.extend(["-ss", start_time])

                cmd.extend(["-i", file])

                if end_time:
                    cmd.extend(["-to", end_time])

                # Use a simple filter to ensure the output is a valid GIF
                cmd.extend(["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-f", "gif"])

    elif media_type == "subtitle":
        # For subtitle files

        # Determine subtitle format
        subtitle_format = "srt"  # Default format
        if file_ext == ".vtt":
            subtitle_format = "webvtt"
        elif file_ext in [".ass", ".ssa"]:
            subtitle_format = "ass"
        elif file_ext == ".sub":
            subtitle_format = "subviewer"

        # For subtitle files, we need a different approach
        # FFmpeg's subtitle trimming can be unreliable

        # We'll use a custom approach for SRT files
        if file_ext == ".srt":
            # For SRT files, we'll use a special approach
            # First, we'll read the file and parse it
            LOGGER.info(f"Using custom SRT trimming approach for {file}")

            # Create a temporary file with the same name but .trim extension
            temp_file = f"{file}.trim{file_ext}"

            # We'll handle SRT trimming in the proceed_trim method
            # For now, just return a special command that will be recognized
            cmd = [
                "srt_trim",
                file,
                start_time or "0",
                end_time or "999:59:59",
                temp_file,
            ]
            return cmd, temp_file
        if file_ext == ".vtt":
            # For VTT files, we'll use a similar approach to SRT
            # First convert to SRT, then trim, then convert back to VTT
            LOGGER.info(f"Using custom VTT trimming approach for {file}")

            # Create temporary files
            temp_srt = f"{file}.temp.srt"
            temp_file = f"{file}.trim{file_ext}"

            # First convert VTT to SRT for easier processing
            convert_cmd = [
                "xtra",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                file,
                "-f",
                "srt",
                temp_srt,
            ]

            # Execute the conversion command
            try:
                import subprocess

                result = subprocess.run(
                    convert_cmd, capture_output=True, text=True, check=False
                )
                if result.returncode != 0:
                    LOGGER.error(f"Failed to convert VTT to SRT: {result.stderr}")
                    # Fallback to standard approach
                    cmd.extend(["-c:s", "copy", "-f", subtitle_format])
                    return cmd, temp_file

                # Now use the SRT trimming approach
                cmd = [
                    "srt_trim",
                    temp_srt,
                    start_time or "0",
                    end_time or "999:59:59",
                    temp_srt + ".trim",
                ]

                # After trimming, we'll need to convert back to VTT
                # This will be handled in the proceed_trim method
                return cmd, temp_file
            except Exception as e:
                LOGGER.error(f"Error in VTT trimming: {e}")
                # Fallback to standard approach
                cmd.extend(["-c:s", "copy", "-f", subtitle_format])
        # For other subtitle formats, try the standard approach
        # Check if subtitle_encoding is "none" (case-insensitive) or None
        elif not subtitle_encoding or subtitle_encoding.lower() == "none":
            # Use copy codec as default when none is specified
            cmd.extend(["-c:s", "copy", "-f", subtitle_format])
        else:
            # For subtitle encoding, we typically use "copy" anyway
            cmd.extend(["-c:s", "copy", "-f", subtitle_format])

    elif media_type == "document":
        # For document files, we need to use a different approach
        if file_ext == ".pdf":
            # For PDF files, we can use a special approach to extract pages
            LOGGER.info(f"Using PDF trimming approach for {file}")

            # Create a temporary file with the same name but .trim extension
            temp_file = f"{file}.trim{file_ext}"

            # We'll handle PDF trimming in the proceed_trim method
            # For now, just return a special command that will be recognized
            cmd = [
                "pdf_trim",
                file,
                start_time or "0",  # Use start_time as start page
                end_time or "999",  # Use end_time as end page
                temp_file,
            ]
            return cmd, temp_file
        # For other document types, we can't use FFmpeg directly
        return None, None

    elif media_type == "archive":
        # For archive files, we can't use FFmpeg
        return None, None

    # Add output file
    cmd.append(temp_file)

    # Add -y flag to force overwrite without prompting
    if "-y" not in cmd:
        cmd.append("-y")

    # Remove any -map options for GIF files to ensure our special handling works
    if file_ext == ".gif" and "-map" in cmd:
        map_index = cmd.index("-map")
        if map_index < len(cmd) - 1:
            # Remove the -map option and its argument
            cmd.pop(map_index)  # Remove -map
            cmd.pop(map_index)  # Remove the argument (e.g., 0)

    # Add delete_original flag to the command for handling in the proceed_trim method
    if delete_original:
        LOGGER.info(f"Original file will be deleted after trimming: {file}")
        # We'll handle this in the proceed_trim method, but we need to pass this information
        # Use -del flag which is recognized and handled by the proceed_trim method
        cmd.append("-del")

    return cmd, temp_file


async def get_compression_cmd(
    file_path,
    media_type=None,
    video_preset="medium",
    video_crf=23,
    video_codec="libx264",
    video_tune="film",
    video_pixel_format="yuv420p",
    video_format="none",
    audio_preset="medium",
    audio_codec="aac",
    audio_bitrate="128k",
    audio_channels=2,
    audio_format="none",
    image_preset="medium",
    image_quality=80,
    image_resize="none",
    image_format="none",
    document_preset="medium",
    document_dpi=150,
    document_format="none",
    subtitle_preset="medium",
    subtitle_encoding="utf-8",
    subtitle_format="none",
    archive_preset="medium",
    archive_level=5,
    archive_method="deflate",
    archive_format="none",
    # delete_original is not used here but kept for API compatibility
    # It's handled in the proceed_compression method
    delete_original=False,
):
    """Generate FFmpeg command for compressing media files.

    Args:
        file_path: Path to the input file
        media_type: Type of media (video, audio, image, document, subtitle, archive)
        video_preset: Compression preset for video (fast, medium, slow)
        video_crf: Constant Rate Factor for video quality (0-51, lower is better)
        video_codec: Video codec to use (libx264, libx265, etc.)
        video_tune: Video tuning parameter (film, animation, grain, etc.)
        video_pixel_format: Pixel format for video (yuv420p, yuv444p, etc.)
        video_format: Output format for video (mp4, mkv, etc.)
        audio_preset: Compression preset for audio (fast, medium, slow)
        audio_codec: Audio codec to use (aac, mp3, opus, etc.)
        audio_bitrate: Audio bitrate (64k, 128k, 192k, etc.)
        audio_channels: Number of audio channels (1=mono, 2=stereo)
        audio_format: Output format for audio (mp3, aac, etc.)
        image_preset: Compression preset for images (fast, medium, slow)
        image_quality: Quality for image compression (1-100)
        image_resize: Size to resize images to (e.g., 1280x720)
        image_format: Output format for images (jpg, png, etc.)
        document_preset: Compression preset for documents (fast, medium, slow)
        document_dpi: DPI for document compression
        document_format: Output format for documents (pdf, etc.)
        subtitle_preset: Compression preset for subtitles (fast, medium, slow)
        subtitle_encoding: Character encoding for subtitles
        subtitle_format: Output format for subtitles (srt, ass, etc.)
        archive_preset: Compression preset for archives (fast, medium, slow)
        archive_level: Compression level for archives (1-9)
        archive_method: Compression method for archives (deflate, lzma, etc.)
        archive_format: Output format for archives (zip, 7z, etc.)
        delete_original: Whether to delete the original file after compression

    Returns:
        tuple: FFmpeg command and temporary output file path, or None, None if not supported
    """
    # Import necessary modules
    from bot import LOGGER, cpu_no
    from bot.helper.ext_utils.media_utils import get_media_type, get_streams

    # Determine media type if not provided
    if not media_type:
        media_type = await get_media_type(file_path)
        if not media_type:
            return None, None

    # Get file extension
    file_ext = os.path.splitext(file_path)[1].lower()

    # Determine output file extension based on format settings
    if media_type == "video" and video_format and video_format.lower() != "none":
        output_ext = f".{video_format.lower()}"
    elif media_type == "audio" and audio_format and audio_format.lower() != "none":
        output_ext = f".{audio_format.lower()}"
    elif media_type == "image" and image_format and image_format.lower() != "none":
        output_ext = f".{image_format.lower()}"
    elif (
        media_type == "document"
        and document_format
        and document_format.lower() != "none"
    ):
        output_ext = f".{document_format.lower()}"
    elif (
        media_type == "subtitle"
        and subtitle_format
        and subtitle_format.lower() != "none"
    ):
        output_ext = f".{subtitle_format.lower()}"
    elif (
        media_type == "archive"
        and archive_format
        and archive_format.lower() != "none"
    ):
        output_ext = f".{archive_format.lower()}"
    else:
        # Keep original extension if no format specified
        output_ext = file_ext

    # Create temporary output file path
    temp_file = f"{file_path}.compressed{output_ext}"

    # Get stream information
    streams = await get_streams(file_path)

    # Use default thread count
    thread_count = max(1, cpu_no // 2)

    # Base command for all media types
    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file_path,
        "-ignore_unknown",
    ]

    # Add media-specific parameters
    if media_type == "video":
        # Check if the file has video streams
        has_video = False
        has_audio = False
        has_subtitle = False

        if streams:
            for stream in streams:
                if stream.get("codec_type") == "video" and not stream.get(
                    "disposition", {}
                ).get("attached_pic"):
                    has_video = True
                elif stream.get("codec_type") == "audio":
                    has_audio = True
                elif stream.get("codec_type") == "subtitle":
                    has_subtitle = True

        # Add video codec parameters
        if has_video:
            # Check if this is a HEVC/10-bit MKV file
            is_hevc_10bit = file_ext.lower() == ".mkv" and (
                "10bit" in file_path.lower()
                or "10bi" in file_path.lower()
                or "hevc" in file_path.lower()
            )

            # For HEVC/10-bit MKV files, always use copy codec for better compatibility
            if is_hevc_10bit:
                LOGGER.info(
                    f"Detected HEVC/10-bit MKV file, using copy codec: {file_path}"
                )
                cmd.extend(["-c:v", "copy"])
            else:
                # Add video codec
                cmd.extend(["-c:v", video_codec])

                # Add video preset
                if video_preset and video_preset.lower() != "none":
                    if video_codec in ["libx264", "libx265"]:
                        cmd.extend(["-preset", video_preset])

                # Add CRF for quality control
                if video_crf > 0:
                    cmd.extend(["-crf", str(video_crf)])

                # Add tune parameter
                if video_tune and video_tune.lower() != "none":
                    if video_codec in ["libx264", "libx265"]:
                        cmd.extend(["-tune", video_tune])

                # Add pixel format
                if video_pixel_format and video_pixel_format.lower() != "none":
                    cmd.extend(["-pix_fmt", video_pixel_format])

        # Add audio codec parameters
        if has_audio:
            # Add audio codec
            cmd.extend(["-c:a", audio_codec])

            # Add audio bitrate
            if audio_bitrate and audio_bitrate.lower() != "none":
                cmd.extend(["-b:a", audio_bitrate])

            # Add audio channels
            if audio_channels > 0:
                cmd.extend(["-ac", str(audio_channels)])

        # Add subtitle parameters
        if has_subtitle:
            # For subtitles, we typically use copy codec
            cmd.extend(["-c:s", "copy"])

        # Map all streams
        cmd.extend(["-map", "0"])

    elif media_type == "audio":
        # Add audio codec
        cmd.extend(["-c:a", audio_codec])

        # Add audio preset
        if audio_preset and audio_preset.lower() != "none":
            if audio_codec == "libopus":
                cmd.extend(
                    [
                        "-compression_level",
                        "10"
                        if audio_preset == "slow"
                        else "5"
                        if audio_preset == "medium"
                        else "0",
                    ]
                )

        # Add audio bitrate
        if audio_bitrate and audio_bitrate.lower() != "none":
            cmd.extend(["-b:a", audio_bitrate])

        # Add audio channels
        if audio_channels > 0:
            cmd.extend(["-ac", str(audio_channels)])

        # Map all audio streams
        cmd.extend(["-map", "0:a"])

    elif media_type == "image":
        # For image files
        if file_ext in [".jpg", ".jpeg"]:
            # For JPEG, use quality parameter
            quality_val = (
                min(31, 31 - int(int(image_quality) * 0.31))
                if image_quality > 0
                else 1
            )
            cmd.extend(["-q:v", str(quality_val)])
        elif file_ext in [".png", ".webp"]:
            # For PNG and WebP, use compression level
            compression_level = (
                min(9, 9 - int(int(image_quality) * 0.09))
                if image_quality > 0
                else 0
            )
            cmd.extend(["-compression_level", str(compression_level)])
        else:
            # For other image formats, use general quality settings
            cmd.extend(["-q:v", "2"])

        # Add resize filter if specified
        if image_resize and image_resize.lower() != "none":
            cmd.extend(["-vf", f"scale={image_resize}"])

    elif media_type == "document":
        # For document files (mainly PDF)
        if file_ext == ".pdf":
            # For PDF files, we'll use a special approach
            # This will be handled separately in the proceed_compression method
            # Just return a special command that will be recognized
            cmd = [
                "pdf_compress",
                file_path,
                str(document_dpi),
                document_preset,
                temp_file,
            ]
            return cmd, temp_file
        # For other document types, we can't use FFmpeg directly
        return None, None

    elif media_type == "subtitle":
        # For subtitle files
        if file_ext in [".srt", ".ass", ".ssa", ".vtt"]:
            # For text-based subtitles, we'll use a special approach
            # This will be handled separately in the proceed_compression method
            cmd = [
                "subtitle_compress",
                file_path,
                subtitle_encoding,
                subtitle_preset,
                temp_file,
            ]
            return cmd, temp_file
        # For other subtitle formats, try standard approach
        cmd.extend(["-c:s", "copy"])

    elif media_type == "archive":
        # For archive files, we'll use a special approach
        # This will be handled separately in the proceed_compression method
        cmd = [
            "archive_compress",
            file_path,
            str(archive_level),
            archive_method,
            archive_preset,
            temp_file,
        ]
        return cmd, temp_file

    else:
        # For other media types
        return None, None

    # Add threads parameter
    cmd.extend(["-threads", f"{thread_count}"])

    # Add output file
    cmd.append(temp_file)

    return cmd, temp_file


async def get_extract_cmd(
    file_path,
    extract_video=False,
    extract_audio=False,
    extract_subtitle=False,
    extract_attachment=False,
    video_index=None,
    audio_index=None,
    subtitle_index=None,
    attachment_index=None,
    video_codec="copy",
    audio_codec="copy",
    subtitle_codec="copy",
    maintain_quality=True,
):
    """Generate FFmpeg command for extracting tracks from a media file.

    Args:
        file_path: Path to the input file
        extract_video: Whether to extract video tracks
        extract_audio: Whether to extract audio tracks
        extract_subtitle: Whether to extract subtitle tracks
        extract_attachment: Whether to extract attachments
        video_index: Specific video track index to extract (None for all)
        audio_index: Specific audio track index to extract (None for all)
        subtitle_index: Specific subtitle track index to extract (None for all)
        attachment_index: Specific attachment index to extract (None for all)
        video_codec: Codec to use for video extraction
        audio_codec: Codec to use for audio extraction
        subtitle_codec: Codec to use for subtitle extraction
        maintain_quality: Whether to maintain high quality during extraction

    Returns:
        Tuple containing the FFmpeg command and the temporary output file path
    """
    # Check if file exists
    if not os.path.exists(file_path):
        LOGGER.error(f"File not found for extraction: {file_path}")
        return [], ""

    # Get file information
    file_name = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    file_base, file_ext = os.path.splitext(file_name)

    # Create a temporary output file path
    temp_file = os.path.join(file_dir, f"{file_base}.extract.temp{file_ext}")

    # Check if any extraction option is enabled
    if not (
        extract_video or extract_audio or extract_subtitle or extract_attachment
    ):
        return [], temp_file

    # Get track information
    streams = await get_streams(file_path)
    if not streams:
        LOGGER.error(f"Failed to get stream information for {file_path}")
        return [], temp_file

    # Group streams by type
    video_streams = []
    audio_streams = []
    subtitle_streams = []
    attachment_streams = []

    for i, stream in enumerate(streams):
        stream_type = stream.get("codec_type")
        if stream_type == "video":
            video_streams.append((i, stream))
        elif stream_type == "audio":
            audio_streams.append((i, stream))
        elif stream_type == "subtitle":
            subtitle_streams.append((i, stream))
        elif stream_type == "attachment":
            attachment_streams.append((i, stream))

    # Check if we have any streams to extract
    if (
        (extract_video and not video_streams)
        and (extract_audio and not audio_streams)
        and (extract_subtitle and not subtitle_streams)
        and (extract_attachment and not attachment_streams)
    ):
        LOGGER.error(f"No streams found to extract from {file_path}")
        return [], temp_file

    # Handle attachment extraction separately
    if extract_attachment and attachment_streams:
        # For attachments, we need to use a different approach
        if attachment_index is not None:
            # Extract specific attachment
            try:
                attachment_index = int(attachment_index)
                if 0 <= attachment_index < len(attachment_streams):
                    stream_index, stream = attachment_streams[attachment_index]
                    filename = stream.get("tags", {}).get(
                        "filename", f"attachment_{attachment_index}"
                    )
                    output_path = os.path.join(file_dir, filename)
                    return [
                        "EXTRACT_ATTACHMENTS_ONLY",
                        file_path,
                        f"EXTRACT_ATTACHMENT:{stream_index}:{output_path}",
                    ], temp_file
            except ValueError:
                LOGGER.error(f"Invalid attachment index: {attachment_index}")
        else:
            # Extract all attachments
            commands = ["EXTRACT_ATTACHMENTS_ONLY", file_path]
            for i, (stream_index, stream) in enumerate(attachment_streams):
                filename = stream.get("tags", {}).get("filename", f"attachment_{i}")
                output_path = os.path.join(file_dir, filename)
                commands.append(f"EXTRACT_ATTACHMENT:{stream_index}:{output_path}")
            return commands, temp_file

    # For media tracks, we'll use multiple FFmpeg commands if needed
    commands = []

    # Extract video streams
    if extract_video and video_streams:
        if video_index is not None:
            # Extract specific video track by index
            try:
                video_index = int(video_index)
                if 0 <= video_index < len(video_streams):
                    stream_index, stream = video_streams[video_index]
                    codec_name = stream.get("codec_name", "unknown")
                    # We don't need width and height for extraction
                    # but we could use them for logging or future enhancements

                    # Determine output extension based on codec
                    output_ext = (
                        "mp4" if video_codec in ["h264", "libx264"] else "mkv"
                    )
                    output_file = os.path.join(
                        file_dir,
                        f"{file_base}.video.{stream.get('tags', {}).get('language', 'und')}.{stream_index}.{output_ext}",
                    )

                    cmd = [
                        "xtra",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{stream_index}",
                        "-c:v",
                        video_codec,
                    ]

                    # Add quality settings if not using copy codec
                    if video_codec != "copy" and maintain_quality:
                        if video_codec in ["h264", "libx264"]:
                            cmd.extend(["-crf", "18", "-preset", "slow"])
                        elif video_codec in ["h265", "libx265"]:
                            cmd.extend(["-crf", "22", "-preset", "slow"])
                        elif video_codec in ["vp9", "libvpx-vp9"]:
                            cmd.extend(["-crf", "30", "-b:v", "0"])

                    cmd.append(output_file)
                    commands.append(" ".join(cmd))
                else:
                    pass
            except ValueError:
                LOGGER.error(f"Invalid video index: {video_index}")
        else:
            # Extract all video tracks
            for i, (stream_index, stream) in enumerate(video_streams):
                # Skip attached pictures (cover art)
                if stream.get("disposition", {}).get("attached_pic", 0) == 1:
                    continue

                # Determine output extension based on codec
                output_ext = "mp4" if video_codec in ["h264", "libx264"] else "mkv"
                output_file = os.path.join(
                    file_dir,
                    f"{file_base}.video.{stream.get('tags', {}).get('language', 'und')}.{stream_index}.{output_ext}",
                )

                cmd = [
                    "xtra",
                    "-i",
                    file_path,
                    "-map",
                    f"0:{stream_index}",
                    "-c:v",
                    video_codec,
                ]

                # Add quality settings if not using copy codec
                if video_codec != "copy" and maintain_quality:
                    if video_codec in ["h264", "libx264"]:
                        cmd.extend(["-crf", "18", "-preset", "slow"])
                    elif video_codec in ["h265", "libx265"]:
                        cmd.extend(["-crf", "22", "-preset", "slow"])
                    elif video_codec in ["vp9", "libvpx-vp9"]:
                        cmd.extend(["-crf", "30", "-b:v", "0"])

                cmd.append(output_file)
                commands.append(" ".join(cmd))

    # Extract audio streams
    if extract_audio and audio_streams:
        if audio_index is not None:
            # Extract specific audio track by indexbut by default all the configs should be none and none means none and those configs should not be used for command generation. global settings will use that settings by default
            try:
                audio_index = int(audio_index)
                if 0 <= audio_index < len(audio_streams):
                    stream_index, stream = audio_streams[audio_index]
                    codec_name = stream.get("codec_name", "unknown")

                    # Determine output extension based on codec
                    output_ext = (
                        "m4a"
                        if audio_codec in ["aac", "libfdk_aac"]
                        else audio_codec
                    )
                    output_file = os.path.join(
                        file_dir,
                        f"{file_base}.audio.{stream.get('tags', {}).get('language', 'und')}.{stream_index}.{output_ext}",
                    )

                    cmd = [
                        "xtra",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{stream_index}",
                        "-c:a",
                        audio_codec,
                    ]

                    # Add quality settings if not using copy codec
                    if audio_codec != "copy" and maintain_quality:
                        if (
                            audio_codec in ["aac", "libfdk_aac"]
                            or audio_codec == "mp3"
                        ):
                            cmd.extend(["-b:a", "320k"])
                        elif audio_codec in ["opus", "libopus"]:
                            cmd.extend(["-b:a", "192k"])
                        elif audio_codec in ["flac", "libflac"]:
                            cmd.extend(["-compression_level", "8"])

                    cmd.append(output_file)
                    commands.append(" ".join(cmd))
                else:
                    pass
            except ValueError:
                LOGGER.error(f"Invalid audio index: {audio_index}")
        else:
            # Extract all audio tracks
            for i, (stream_index, stream) in enumerate(audio_streams):
                # Determine output extension based on codec
                output_ext = (
                    "m4a" if audio_codec in ["aac", "libfdk_aac"] else audio_codec
                )
                output_file = os.path.join(
                    file_dir,
                    f"{file_base}.audio.{stream.get('tags', {}).get('language', 'und')}.{stream_index}.{output_ext}",
                )

                cmd = [
                    "xtra",
                    "-i",
                    file_path,
                    "-map",
                    f"0:{stream_index}",
                    "-c:a",
                    audio_codec,
                ]

                # Add quality settings if not using copy codec
                if audio_codec != "copy" and maintain_quality:
                    if audio_codec in ["aac", "libfdk_aac"] or audio_codec == "mp3":
                        cmd.extend(["-b:a", "320k"])
                    elif audio_codec in ["opus", "libopus"]:
                        cmd.extend(["-b:a", "192k"])
                    elif audio_codec in ["flac", "libflac"]:
                        cmd.extend(["-compression_level", "8"])

                cmd.append(output_file)
                commands.append(" ".join(cmd))

    # Extract subtitle streams
    if extract_subtitle and subtitle_streams:
        if subtitle_index is not None:
            # Extract specific subtitle track by index
            try:
                subtitle_index = int(subtitle_index)
                if 0 <= subtitle_index < len(subtitle_streams):
                    stream_index, stream = subtitle_streams[subtitle_index]
                    codec_name = stream.get("codec_name", "unknown")

                    # Determine output extension based on codec
                    if codec_name in ["subrip", "srt"]:
                        output_ext = "srt"
                    elif codec_name in ["ass", "ssa"]:
                        output_ext = "ass"
                    elif codec_name in ["webvtt", "vtt"]:
                        output_ext = "vtt"
                    else:
                        output_ext = "srt"  # Default format

                    output_file = os.path.join(
                        file_dir,
                        f"{file_base}.subtitle.{stream.get('tags', {}).get('language', 'und')}.{stream_index}.{output_ext}",
                    )

                    cmd = [
                        "xtra",
                        "-i",
                        file_path,
                        "-map",
                        f"0:{stream_index}",
                        "-c:s",
                        subtitle_codec,
                    ]
                    cmd.append(output_file)
                    commands.append(" ".join(cmd))
                else:
                    pass
            except ValueError:
                LOGGER.error(f"Invalid subtitle index: {subtitle_index}")
        else:
            # Extract all subtitle tracks
            for i, (stream_index, stream) in enumerate(subtitle_streams):
                codec_name = stream.get("codec_name", "unknown")

                # Determine output extension based on codec
                if codec_name in ["subrip", "srt"]:
                    output_ext = "srt"
                elif codec_name in ["ass", "ssa"]:
                    output_ext = "ass"
                elif codec_name in ["webvtt", "vtt"]:
                    output_ext = "vtt"
                else:
                    output_ext = "srt"  # Default format

                output_file = os.path.join(
                    file_dir,
                    f"{file_base}.subtitle.{stream.get('tags', {}).get('language', 'und')}.{stream_index}.{output_ext}",
                )

                cmd = [
                    "xtra",
                    "-i",
                    file_path,
                    "-map",
                    f"0:{stream_index}",
                    "-c:s",
                    subtitle_codec,
                ]
                cmd.append(output_file)
                commands.append(" ".join(cmd))

    # Return the commands
    if len(commands) == 1:
        # If there's only one command, return it directly
        return commands[0].split(), temp_file
    if len(commands) > 1:
        # If there are multiple commands, return them as a special format
        return ["EXTRACT_MULTI_COMMAND", *commands], temp_file
    # No commands were generated
    return [], temp_file
