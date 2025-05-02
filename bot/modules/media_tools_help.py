#!/usr/bin/env python3
from asyncio import create_task
from logging import getLogger

from bot.helper.telegram_helper.button_build import ButtonMaker

# No need to import help_messages as we've included the content directly
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    delete_message,
    edit_message,
    send_message,
)

LOGGER = getLogger(__name__)


# Define page content functions
def get_page_content(page_num):
    pages = {
        # Merge pages
        1: get_merge_intro_page(),
        2: get_merge_video_page(),
        3: get_merge_audio_page(),
        4: get_merge_subtitle_page(),
        5: get_merge_image_page(),
        6: get_merge_document_page(),
        7: get_merge_mixed_page(),
        8: get_merge_notes_page(),
        # Watermark pages
        9: get_watermark_intro_page(),
        10: get_watermark_settings_page(),
        # Convert pages
        11: get_convert_intro_page(),
        # Compression pages
        12: get_compression_intro_page(),
        # Trim pages
        13: get_trim_intro_page(),
        14: get_trim_settings_page(),
        # Extract pages
        15: get_extract_intro_page(),
        16: get_extract_settings_page(),
        # Other pages
        17: get_priority_guide_page(),
        18: get_usage_examples_page_1(),
        19: get_usage_examples_page_2(),
        # Metadata page
        20: get_metadata_guide_page(),
        # MT Flag page
        21: get_mt_flag_guide_page(),
    }
    return pages.get(page_num, "Invalid page")


def get_merge_intro_page():
    msg = "<b>Merge Feature Guide (1/20)</b>\n\n"
    msg += "<b>Merge Flags</b>: -merge-video -merge-audio -merge-subtitle -merge-image -merge-pdf -merge-all\n\n"

    msg += '<blockquote expandable="expandable"><b>Multi-Link Usage (reply to first link or file)</b>:\n'
    msg += "<code>/cmd link -m folder_name -merge-video</code> (merge only video files)\n"
    msg += "<code>/cmd link -m folder_name -merge-audio</code> (merge only audio files)\n"
    msg += "<code>/cmd -b -m folder_name -merge-subtitle</code>\n\n"

    msg += "or\n\n"

    msg += (
        "<b>Bulk Usage (reply to text file with links or message with links)</b>:\n"
    )
    msg += "<code>/cmd -b -m folder_name -merge-image</code>\n"
    msg += "<code>/cmd -b -m folder_name -merge-pdf</code>\n"
    msg += "<code>/cmd -b -m folder_name -merge-all</code>\n\n"

    msg += "This allows you to download multiple files from different sources and merge them together. The <code>-m folder_name</code> argument is important as it places all files in the same directory for merging.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Examples</b>:\n'
    msg += "<code>/leech https://example.com/videos.zip -merge-video</code> (merge only video files)\n"
    msg += "<code>/mirror https://example.com/music.zip -merge-audio</code> (merge only audio files)\n"
    msg += "<code>/mirror https://example.com/subtitle.zip -merge-subtitle</code> (merge only subtitle files)\n"
    msg += "<code>/leech https://example.com/images.zip -merge-image</code> (creates a collage or grid)\n"
    msg += "<code>/mirror https://example.com/documents.zip -merge-pdf</code> (combines PDFs into one file)\n"
    msg += "<code>/leech https://example.com/alltypes.zip -merge-all</code> (merge all files by type)\n\n"

    msg += "These flags help control which files to merge when using the merge feature. If no flag is specified, the system will automatically analyze the files and choose the best approach.</blockquote>\n\n"

    msg += "<b>Supported Merge Types:</b>\n"
    msg += "• Video + Video + Video + ... (creates a single video file)\n"
    msg += "  - Use <code>-merge-video</code> to preserve all video and subtitle tracks\n"
    msg += "• Audio + Audio + Audio + ... (creates a single audio file)\n"
    msg += "• Subtitle + Subtitle + ... (creates a single subtitle file)\n"
    msg += "• Video + Audio + Subtitle (adds audio and subtitle tracks to video)\n"
    msg += "• Images (creates a collage or horizontal/vertical image)\n"
    msg += "• Documents (combines PDFs into a single document)\n"
    msg += "  - Use <code>-merge-all</code> to preserve all video, audio, and subtitle tracks\n\n"

    msg += '<blockquote expandable="expandable"><b>File Order Preservation</b>:\n'
    msg += (
        "• All files are merged in the same order as they are provided by the user\n"
    )
    msg += "• This applies to all file types: videos, audios, subtitles, images, and documents\n"
    msg += "• The order is especially important for sequential content like video episodes or chapters</blockquote>\n\n"

    return msg


def get_merge_video_page():
    msg = "<b>Video Merging (2/20)</b>\n\n"
    msg += "<b>Video Merging Features:</b>\n"
    msg += "• Combines multiple video files into a single video file\n"
    msg += "• Preserves video quality and aspect ratio when possible\n"
    msg += "• Preserves all video and subtitle tracks when using -merge-video flag\n"
    msg += "• Supports different codecs (h264, h265, vp9, av1)\n"
    msg += "• Can handle videos with different resolutions and framerates\n"
    msg += "• Output format and codec can be configured in Media Tools settings\n"
    msg += "• Supports both concat demuxer (fast) and filter complex (compatible) methods\n\n"

    msg += "<b>Supported Video Formats:</b>\n"
    msg += "• Input: MP4, MKV, AVI, MOV, WebM, FLV, WMV, M4V, TS, 3GP\n"
    msg += "• Output: MKV (default), MP4, WebM, AVI\n"
    msg += "• Codecs: copy (default), h264, h265, vp9, av1\n\n"

    msg += '<blockquote expandable="expandable"><b>Video Merging Tips:</b>\n'
    msg += "• Use MKV container for best compatibility with different codecs\n"
    msg += "• The 'copy' codec is fastest and preserves quality but requires similar source files\n"
    msg += "• Use -merge-video flag to preserve all video and subtitle tracks\n"
    msg += (
        "• For files with different codecs or formats, use filter complex method\n"
    )
    msg += "• Set video quality in Media Tools settings for transcoding operations\n"
    msg += "• Higher CRF values mean lower quality but smaller file size\n"
    msg += "• Recommended CRF values: 18-23 for high quality, 23-28 for medium quality</blockquote>\n\n"

    return msg


def get_merge_audio_page():
    msg = "<b>Audio Merging (3/20)</b>\n\n"
    msg += "<b>Audio Merging Features:</b>\n"
    msg += "• Combines multiple audio files into a single audio file\n"
    msg += "• Preserves audio quality when possible\n"
    msg += "• Supports various audio codecs (AAC, MP3, OPUS, FLAC)\n"
    msg += "• Can handle different bitrates, sampling rates, and channel layouts\n"
    msg += "• Volume normalization available through settings\n"
    msg += "• Output format and codec can be configured in Media Tools settings\n\n"

    msg += "<b>Supported Audio Formats:</b>\n"
    msg += "• Input: MP3, M4A, AAC, FLAC, WAV, OGG, OPUS, WMA\n"
    msg += "• Output: MP3 (default), M4A, FLAC, WAV, OGG\n"
    msg += "• Codecs: copy (default), aac, mp3, opus, flac\n\n"

    msg += '<blockquote expandable="expandable"><b>Audio Merging Tips:</b>\n'
    msg += "• MP3 format is widely compatible but lossy\n"
    msg += "• FLAC format preserves audio quality but results in larger files\n"
    msg += "• AAC offers good quality-to-size ratio for most content\n"
    msg += "• Volume normalization helps balance audio levels across different sources\n"
    msg += "• For audiobooks or podcasts, consider mono audio (1 channel) to reduce file size\n"
    msg += "• 192kbps is a good balance between quality and file size for most content</blockquote>\n\n"

    return msg


def get_merge_subtitle_page():
    msg = "<b>Subtitle Merging (4/20)</b>\n\n"
    msg += "<b>Subtitle Merging Features:</b>\n"
    msg += "• Supports merging multiple subtitle files into a single file\n"
    msg += "• Preserves timing and sequence of subtitles\n"
    msg += "• Can merge different subtitle formats (SRT, VTT, ASS, SSA)\n"
    msg += "• Maintains styling information when merging advanced formats like ASS\n"
    msg += "• Output format can be configured in Media Tools settings\n\n"

    msg += "<b>Supported Subtitle Formats:</b>\n"
    msg += "• Input: SRT, VTT, ASS, SSA, SUB, SBV, LRC, TTML\n"
    msg += "• Output: SRT (default), VTT, ASS, SSA\n"
    msg += "• Features: Text formatting, timing preservation, language detection\n\n"

    msg += '<blockquote expandable="expandable"><b>Subtitle Merging Tips:</b>\n'
    msg += "• SRT format is most widely compatible but lacks styling options\n"
    msg += (
        "• ASS/SSA formats support advanced styling (colors, positioning, fonts)\n"
    )
    msg += "• When merging subtitles with different timings, they will be concatenated sequentially\n"
    msg += "• For multi-language subtitles, use language codes in filenames (movie.en.srt, movie.es.srt)\n"
    msg += "• Subtitle encoding can be configured in Media Tools settings (UTF-8 recommended)\n"
    msg += "• Merged subtitles can be embedded into video files using the mixed media merging feature</blockquote>\n\n"

    return msg


def get_merge_image_page():
    msg = "<b>Image Merging (5/20)</b>\n\n"
    msg += "<b>Image Merging Modes:</b>\n"
    msg += (
        "• <b>Collage Mode</b> - Creates a grid of images (default for 3+ images)\n"
    )
    msg += "• <b>Horizontal Mode</b> - Places images side by side (default for 2 images)\n"
    msg += "• <b>Vertical Mode</b> - Stacks images on top of each other\n\n"

    msg += "<b>Supported Image Formats:</b>\n"
    msg += "• Input: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF, HEIC\n"
    msg += "• Output: JPG (default), PNG, WebP, TIFF\n"
    msg += "• Features: Resolution preservation, quality settings, metadata handling\n\n"

    msg += '<blockquote expandable="expandable"><b>Image Merging Tips:</b>\n'
    msg += "• JPG format offers good compression but is lossy (quality loss)\n"
    msg += "• PNG format preserves quality but results in larger files\n"
    msg += "• WebP offers good balance between quality and file size\n"
    msg += "• For collage mode, you can configure the number of columns in Media Tools settings\n"
    msg += (
        "• Background color for image merging can be customized (default: white)\n"
    )
    msg += "• Images can be resized to a uniform size before merging for better appearance</blockquote>\n\n"

    return msg


def get_merge_document_page():
    msg = "<b>Document Merging (6/20)</b>\n\n"
    msg += "<b>Document Merging Features:</b>\n"
    msg += "• Currently supports merging PDF files\n"
    msg += "• All PDF pages are preserved in the merged document\n"
    msg += "• Maintains original page order\n"
    msg += "• Preserves document metadata when possible\n\n"

    msg += "<b>Supported Document Formats:</b>\n"
    msg += "• Input: PDF\n"
    msg += "• Output: PDF\n"
    msg += "• Features: Page order preservation, metadata retention, bookmark handling\n\n"

    msg += '<blockquote expandable="expandable"><b>Document Merging Tips:</b>\n'
    msg += "• PDF merging works best with similar document types\n"
    msg += "• Page size and orientation are preserved from original documents\n"
    msg += "• Document properties like title and author can be configured in Media Tools settings\n"
    msg += "• Bookmarks from original PDFs are preserved in the merged document\n"
    msg += "• Password-protected PDFs may not merge correctly\n"
    msg += "• Future updates may add support for other document formats</blockquote>\n\n"

    return msg


def get_merge_mixed_page():
    msg = "<b>Mixed Media Merging (7/20)</b>\n\n"
    msg += "<b>Mixed Media Merging Features:</b>\n"
    msg += "• <b>Video + Audio</b>: Adds audio tracks to video files\n"
    msg += "• <b>Video + Subtitle</b>: Embeds subtitle tracks in video files\n"
    msg += "• <b>Video + Audio + Subtitle</b>: Creates complete media package with all tracks\n"
    msg += "• <b>Multiple Audio Tracks</b>: Adds multiple language/quality audio options\n"
    msg += "• <b>Multiple Subtitle Tracks</b>: Embeds multiple language subtitle options\n\n"

    msg += "<b>Mixed Merging Guide:</b>\n"
    msg += "1. Place all files in the same directory using <code>-m folder_name</code>\n"
    msg += "2. Use <code>-merge-all</code> to automatically detect and merge compatible files\n"
    msg += "3. File naming is important for proper track matching:\n"
    msg += "   • Use similar base names (video.mp4, video.srt, video.mp3)\n"
    msg += "   • Or use language codes (movie.mp4, movie.en.srt, movie.es.srt)\n\n"

    msg += '<blockquote expandable="expandable"><b>Advanced Configuration:</b>\n'
    msg += "Use Media Tools settings to configure:\n"
    msg += "• Track selection and ordering\n"
    msg += "• Default audio/subtitle language\n"
    msg += "• Forced subtitle handling\n"
    msg += "• Audio sync adjustment\n"
    msg += "• Default subtitle encoding\n"
    msg += "• Audio normalization options\n"
    msg += "• Video container format (MKV recommended for mixed media)\n"
    msg += "• Metadata preservation options</blockquote>\n\n"

    return msg


def get_merge_notes_page():
    msg = "<b>Merge Notes & Advanced Features (8/20)</b>\n\n"

    msg += "<b>Important Considerations:</b>\n"
    msg += "• File order is preserved during merging (important for sequential content)\n"
    msg += "• Both <code>-merge-video</code> and <code>-merge-all</code> flags preserve all tracks\n"
    msg += "• Mixed media merging works best with MKV container format\n"
    msg += "• Some combinations may require transcoding which affects quality\n"
    msg += "• Large files may require more processing time and resources\n"
    msg += "• Certain format combinations may have compatibility limitations\n"
    msg += "• Original files can be preserved or removed after merging (configurable)\n\n"

    msg += '<blockquote expandable="expandable"><b>Best Practices:</b>\n'
    msg += "• Use MKV container for most versatile track support\n"
    msg += "• Keep filenames consistent for better automatic matching\n"
    msg += "• Use language codes in filenames for multi-language content\n"
    msg += "• Process similar files together for best results\n"
    msg += "• Test settings with smaller files before large merges\n"
    msg += "• Use the -merge-all flag for automatic format detection\n"
    msg += "• Both -merge-video and -merge-all preserve all existing tracks\n"
    msg += "• Configure default settings in Media Tools for consistent results\n"
    msg += "• If merge fails, try using filter complex method\n"
    msg += '• Use "copy" codec when possible to preserve quality</blockquote>\n\n'

    msg += '<blockquote expandable="expandable"><b>Advanced Features</b>:\n'
    msg += "• <b>Concat Demuxer</b>: Fast merging for files with identical codecs\n"
    msg += (
        "• <b>Filter Complex</b>: Advanced merging for files with different codecs\n"
    )
    msg += "• <b>Output Format</b>: Choose the format for merged files (mkv, mp4, mp3, etc.)\n"
    msg += "• <b>Threading</b>: Process multiple files simultaneously\n"
    msg += "• <b>Thread Number</b>: Control parallel processing threads</blockquote>\n\n"

    msg += "<b>Important Notes:</b>\n"
    msg += "• For best results, use the -m flag to place all files in the same directory\n"
    msg += "• The rename flag (-n) will not work with merge operations\n"
    msg += "• Files with identical filenames may cause issues during merging\n"
    msg += "• Original files are removed after successful merge if enabled in settings\n"
    msg += "• User settings take priority over owner settings\n"
    msg += "• Default settings are used if no others are specified\n"

    return msg


def get_watermark_intro_page():
    msg = "<b>Watermark Feature Guide (9/20)</b>\n\n"
    msg += "<b>Watermark Feature</b>\n"
    msg += "Add text overlays to videos, images, audio files, and subtitles with customizable appearance.\n\n"

    msg += "<b>Important:</b> Make sure to enable watermark in Media Tools settings before using this feature.\n\n"

    msg += "<b>How to Use</b>:\n"
    msg += "Add the <code>-watermark</code> flag followed by your text in quotes:\n"
    msg += '<code>/leech https://example.com/video.mp4 -watermark "© My Channel"</code>\n\n'

    msg += "You can also use it without any flags. You can set the text and other settings in Media Tools settings. Then run the command:\n"
    msg += "<code>/leech https://example.com/video.mp4</code>\n\n"

    msg += "<b>Supported Media Types</b>:\n"
    msg += "• <b>Videos</b>: MKV, MP4, AVI, MOV, WebM, FLV, WMV, M4V, TS, 3GP\n"
    msg += "• <b>Images</b>: JPG, JPEG, PNG, BMP, WebP, GIF\n"
    msg += "• <b>Audio</b>: MP3, M4A, FLAC, WAV, OGG, OPUS, AAC, WMA\n"
    msg += "• <b>Subtitles</b>: SRT, ASS, SSA, VTT\n\n"

    msg += '<blockquote expandable="expandable"><b>Watermark Types</b>:\n'
    msg += "• <b>Visual Watermark</b>: Text overlay on videos and images\n"
    msg += "• <b>Audio Watermark</b>: Sound markers in audio files\n"
    msg += "• <b>Subtitle Watermark</b>: Text added to subtitle entries\n\n"

    msg += "Each type can be enabled/disabled separately in Media Tools settings. Audio and subtitle watermarks can use different text than the visual watermark.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Priority Settings</b>:\n'
    msg += "Watermark follows the same priority settings as the merge feature:\n"
    msg += "• Command line watermark text takes highest priority\n"
    msg += "• User settings take priority over owner settings\n"
    msg += "• Owner settings are used as fallback\n"
    msg += "• Default settings are used if no others are specified\n"
    msg += "• By Default watermark priority is 2 which means it will run after merge feature.</blockquote>\n\n"

    return msg


def get_watermark_settings_page():
    msg = "<b>Watermark Settings (10/20)</b>\n\n"

    msg += "<b>Visual Watermark Settings</b>:\n"
    msg += "• <b>Text</b>: The text to display as watermark\n"
    msg += "• <b>Position</b>: Where to place the watermark\n"
    msg += "• <b>Size</b>: Font size of the watermark text (default: 20)\n"
    msg += "• <b>Color</b>: Color of the watermark text\n"
    msg += "• <b>Font</b>: Font file to use (supports Google Fonts)\n"
    msg += "• <b>Opacity</b>: Transparency level of watermark (0.0-1.0)\n"
    msg += "• <b>Fast Mode</b>: Use faster encoding for large files\n"
    msg += "• <b>Maintain Quality</b>: Preserve original quality\n\n"

    msg += "<b>Audio Watermark Settings</b>:\n"
    msg += "• <b>Audio WM</b>: Enable/disable audio watermarking\n"
    msg += "• <b>Audio Text</b>: Custom text for audio watermarks (uses visual text if empty)\n"
    msg += "• <b>Audio Volume</b>: Volume level of audio watermark (0.0-1.0)\n\n"

    msg += "<b>Subtitle Watermark Settings</b>:\n"
    msg += "• <b>Subtitle WM</b>: Enable/disable subtitle watermarking\n"
    msg += "• <b>Subtitle Text</b>: Custom text for subtitle watermarks (uses visual text if empty)\n"
    msg += "• <b>Subtitle Style</b>: Styling for subtitle watermarks (normal, bold, italic)\n\n"

    msg += '<blockquote expandable="expandable"><b>Position Options</b>:\n'
    msg += "• <b>top_left</b>: Upper left corner\n"
    msg += "• <b>top_right</b>: Upper right corner\n"
    msg += "• <b>bottom_left</b>: Lower left corner\n"
    msg += "• <b>bottom_right</b>: Lower right corner\n"
    msg += "• <b>center</b>: Middle of the video/image\n"
    msg += "• <b>top_center</b>: Top middle\n"
    msg += "• <b>bottom_center</b>: Bottom middle\n"
    msg += "• <b>left_center</b>: Middle left side\n"
    msg += "• <b>right_center</b>: Middle right side</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Color Options</b>:\n'
    msg += "• <b>Basic Colors</b>: white, black, red, blue, green, yellow, etc.\n"
    msg += "• <b>Hex Colors</b>: #RRGGBB format (e.g., #FF0000 for red)\n"
    msg += "• <b>RGBA Colors</b>: rgba(r,g,b,a) format for transparency\n"
    msg += "• <b>Recommended</b>: White or yellow with black outline for visibility</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Font Options</b>:\n'
    msg += "• <b>Default</b>: System default sans-serif font\n"
    msg += "• <b>Google Fonts</b>: Any Google Font name (e.g., Roboto, Open Sans)\n"
    msg += "• <b>Custom Fonts</b>: Path to .ttf or .otf file\n"
    msg += "• <b>Recommended</b>: Sans-serif fonts for better readability</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Advanced Settings</b>:\n'
    msg += "• <b>Padding</b>: Space between watermark and edge\n"
    msg += "• <b>Shadow</b>: Enable/disable text shadow (always enabled)\n"
    msg += "• <b>Outline</b>: Enable/disable text outline\n"
    msg += "• <b>Threading</b>: Process multiple files simultaneously\n"
    msg += "• <b>Thread Number</b>: Number of parallel processing threads\n"
    msg += "• <b>Fast Mode</b>: Uses ultrafast preset for large files (>100MB)\n"
    msg += "• <b>Maintain Quality</b>: Uses higher quality settings (CRF 18 for videos)\n"
    msg += "• <b>Opacity</b>: Sets transparency (0.0 = fully transparent, 1.0 = fully opaque)</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Audio Watermark Details</b>:\n'
    msg += "• Adds beep tones at intervals in audio files\n"
    msg += "• Frequency and volume vary based on position and color settings\n"
    msg += "• Number of beeps is determined by size parameter\n"
    msg += "• Adds metadata with watermark text to audio files\n"
    msg += "• Will not be applied to video files with audio tracks\n"
    msg += (
        "• Can be enabled/disabled separately from visual watermark</blockquote>\n\n"
    )

    msg += '<blockquote expandable="expandable"><b>Subtitle Watermark Details</b>:\n'
    msg += "• Adds watermark text to subtitle entries\n"
    msg += "• Works with SRT, ASS/SSA, and WebVTT formats\n"
    msg += "• Preserves original subtitle timing and formatting\n"
    msg += "• Will not be applied to videos with embedded subtitle tracks\n"
    msg += "• Can be enabled/disabled separately from visual watermark\n"
    msg += (
        "• Custom text can be different from visual watermark text</blockquote>\n\n"
    )

    return msg


def get_convert_intro_page():
    msg = "<b>Convert Feature Guide (11/20)</b>\n\n"
    msg += "<b>Convert Feature</b>\n"
    msg += "Convert media files to different formats with customizable settings for video and audio.\n\n"

    msg += "<b>Important:</b> Make sure to enable convert in Media Tools settings before using this feature.\n\n"

    msg += "<b>How to Use</b>:\n"
    msg += "Add the <code>-cv</code> or <code>-ca</code> flags followed by the desired format:\n"
    msg += "<code>/leech https://example.com/video.mp4 -cv mp4</code> (convert video to MP4)\n"
    msg += "<code>/mirror https://example.com/audio.wav -ca mp3</code> (convert audio to MP3)\n\n"

    msg += "You can also use it without any flags. You can set the formats and other settings in Media Tools settings. Then run the command:\n"
    msg += "<code>/leech https://example.com/video.webm</code>\n\n"

    msg += "<b>Supported Media Types</b>:\n"
    msg += "• <b>Videos</b>: MKV, MP4, AVI, MOV, WebM, FLV, WMV, M4V, TS, 3GP\n"
    msg += "• <b>Audio</b>: MP3, M4A, FLAC, WAV, OGG, OPUS, AAC, WMA\n\n"

    msg += '<blockquote expandable="expandable"><b>Convert Options</b>:\n'
    msg += "• <b>Video Format</b>: Output format for videos (mp4, mkv, avi, webm)\n"
    msg += "• <b>Video Codec</b>: Encoding codec (h264, h265, vp9, av1)\n"
    msg += "• <b>Video Quality</b>: Encoding preset (ultrafast to veryslow)\n"
    msg += "• <b>Video CRF</b>: Quality factor (0-51, lower is better)\n"
    msg += "• <b>Video Preset</b>: Encoding speed vs compression ratio\n"
    msg += "• <b>Maintain Quality</b>: Preserve high quality during conversion\n"
    msg += (
        "• <b>Audio Format</b>: Output format for audio (mp3, m4a, flac, wav, ogg)\n"
    )
    msg += "• <b>Audio Codec</b>: Encoding codec (mp3, aac, opus, flac)\n"
    msg += "• <b>Audio Bitrate</b>: Quality setting (128k, 192k, 320k)\n"
    msg += "• <b>Audio Channels</b>: Mono (1) or stereo (2)\n"
    msg += "• <b>Audio Sampling</b>: Sample rate in Hz (44100, 48000)\n"
    msg += (
        "• <b>Audio Volume</b>: Volume adjustment (1.0 = original)</blockquote>\n\n"
    )

    msg += '<blockquote expandable="expandable"><b>Advanced Usage</b>:\n'
    msg += "• <b>Convert specific formats</b>:\n"
    msg += "<code>/leech https://example.com/videos.zip -cv mp4 + webm flv</code>\n"
    msg += "This will convert only WebM and FLV videos to MP4\n\n"
    msg += "• <b>Exclude specific formats</b>:\n"
    msg += "<code>/mirror https://example.com/audios.zip -ca mp3 - wav</code>\n"
    msg += "This will convert all audio formats to MP3 except WAV files\n\n"
    msg += "• <b>Combined video and audio conversion</b>:\n"
    msg += "<code>/leech https://example.com/media.zip -cv mp4 -ca mp3</code>\n"
    msg += (
        "This will convert all videos to MP4 and all audios to MP3</blockquote>\n\n"
    )

    msg += "<b>Priority Settings</b>:\n"
    msg += "Convert follows the same priority settings as other media tools:\n"
    msg += "• Command line flags take highest priority\n"
    msg += "• User settings take priority over owner settings\n"
    msg += "• Owner settings are used as fallback\n"
    msg += "• Default settings are used if no others are specified\n\n"

    return msg


def get_compression_intro_page():
    msg = "<b>Compression Feature Guide (12/20)</b>\n\n"
    msg += "<b>Compression Feature</b>\n"
    msg += "Compress media files to reduce file size while maintaining acceptable quality.\n\n"

    msg += "<b>Important:</b> Make sure to enable compression in Media Tools settings before using this feature.\n\n"

    msg += "<b>How to Use</b>:\n"
    msg += "Add the compression flags to your download commands:\n"
    msg += "<code>/leech https://example.com/video.mp4 -video-fast</code> (compress video with fast preset)\n"
    msg += "<code>/mirror https://example.com/audio.mp3 -audio-medium</code> (compress audio with medium preset)\n"
    msg += "<code>/leech https://example.com/image.png -image-slow</code> (compress image with slow preset)\n\n"

    msg += "You can also use it without any flags if you've enabled compression in Media Tools settings:\n"
    msg += "<code>/leech https://example.com/video.mp4</code>\n\n"

    msg += "<b>Supported Media Types</b>:\n"
    msg += "• <b>Videos</b>: MKV, MP4, AVI, MOV, WebM, FLV, WMV, M4V, TS, 3GP\n"
    msg += "• <b>Audio</b>: MP3, M4A, FLAC, WAV, OGG, OPUS, AAC, WMA\n"
    msg += "• <b>Images</b>: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF\n"
    msg += "• <b>Documents</b>: PDF, DOCX, PPTX, XLSX\n"
    msg += "• <b>Subtitles</b>: SRT, VTT, ASS, SSA\n"
    msg += "• <b>Archives</b>: ZIP, RAR, 7Z, TAR, GZ\n\n"

    msg += '<blockquote expandable="expandable"><b>Compression Presets</b>:\n'
    msg += "Each media type supports three compression presets:\n"
    msg += "• <b>Fast</b>: Quick compression with moderate file size reduction\n"
    msg += "• <b>Medium</b>: Balanced compression with good file size reduction\n"
    msg += "• <b>Slow</b>: Thorough compression with maximum file size reduction\n\n"

    msg += "Usage examples:\n"
    msg += "<code>/leech https://example.com/video.mp4 -video-fast</code>\n"
    msg += "<code>/mirror https://example.com/audio.mp3 -audio-medium</code>\n"
    msg += "<code>/leech https://example.com/image.png -image-slow</code>\n"
    msg += "<code>/mirror https://example.com/document.pdf -document-medium</code>\n"
    msg += "<code>/leech https://example.com/subtitle.srt -subtitle-fast</code>\n"
    msg += "<code>/mirror https://example.com/archive.zip -archive-slow</code></blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Video Compression Settings</b>:\n'
    msg += "• <b>Preset</b>: Fast, medium, or slow compression\n"
    msg += "• <b>CRF</b>: Quality factor (higher values = smaller files but lower quality)\n"
    msg += "• <b>Codec</b>: Encoding codec (h264, h265, etc.)\n"
    msg += "• <b>Tune</b>: Optimization for specific content types\n"
    msg += "• <b>Pixel Format</b>: Color encoding format\n\n"

    msg += "The fast preset uses higher CRF values and faster encoding settings, while the slow preset uses lower CRF values and more thorough encoding for better quality.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Audio Compression Settings</b>:\n'
    msg += "• <b>Preset</b>: Fast, medium, or slow compression\n"
    msg += "• <b>Codec</b>: Encoding codec (aac, mp3, opus, etc.)\n"
    msg += "• <b>Bitrate</b>: Target bitrate (lower = smaller files)\n"
    msg += "• <b>Channels</b>: Mono (1) or stereo (2)\n\n"

    msg += "The fast preset uses lower bitrates, while the slow preset uses more efficient encoding algorithms.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Image Compression Settings</b>:\n'
    msg += "• <b>Preset</b>: Fast, medium, or slow compression\n"
    msg += "• <b>Quality</b>: JPEG/WebP quality factor\n"
    msg += "• <b>Resize</b>: Optional downsizing of dimensions\n\n"

    msg += "The fast preset uses higher quality reduction, while the slow preset uses more advanced algorithms to maintain visual quality.</blockquote>\n\n"

    msg += (
        '<blockquote expandable="expandable"><b>Document Compression Settings</b>:\n'
    )
    msg += "• <b>Preset</b>: Fast, medium, or slow compression\n"
    msg += "• <b>DPI</b>: Resolution for embedded images\n\n"

    msg += "The fast preset uses lower DPI values for embedded images, while the slow preset uses more thorough optimization techniques.</blockquote>\n\n"

    msg += (
        '<blockquote expandable="expandable"><b>Subtitle Compression Settings</b>:\n'
    )
    msg += "• <b>Preset</b>: Fast, medium, or slow compression\n"
    msg += "• <b>Encoding</b>: Character encoding (UTF-8, ASCII, etc.)\n\n"

    msg += "The fast preset uses simpler encoding, while the slow preset optimizes formatting and timing information.</blockquote>\n\n"

    msg += (
        '<blockquote expandable="expandable"><b>Archive Compression Settings</b>:\n'
    )
    msg += "• <b>Preset</b>: Fast, medium, or slow compression\n"
    msg += "• <b>Level</b>: Compression level (1-9)\n"
    msg += "• <b>Method</b>: Compression algorithm\n\n"

    msg += "The fast preset uses lower compression levels, while the slow preset uses maximum compression levels and more efficient algorithms.</blockquote>\n\n"

    msg += "<b>Additional Options</b>:\n"
    msg += "• <code>-del</code>: Delete original files after compression\n"
    msg += "Example: <code>/leech https://example.com/video.mp4 -video-medium -del</code>\n\n"

    msg += "<b>Priority Settings</b>:\n"
    msg += "Compression follows the same priority settings as other media tools:\n"
    msg += "• Command line flags take highest priority\n"
    msg += "• User settings take priority over owner settings\n"
    msg += "• Owner settings are used as fallback\n"
    msg += "• Default settings are used if no others are specified\n"
    msg += "• Default compression priority is 4 (runs after merge, watermark, and convert)\n\n"

    return msg


def get_trim_intro_page():
    msg = "<b>Trim Feature Guide (13/20)</b>\n\n"
    msg += "<b>Trim Feature</b>\n"
    msg += "Trim media files to extract specific portions based on start and end times.\n\n"

    msg += "<b>Important:</b> Make sure to enable trim in Media Tools settings before using this feature.\n\n"

    msg += "<b>How to Use</b>:\n"
    msg += "Add the <code>-trim</code> flag followed by the time range in format <code>start_time-end_time</code>:\n"
    msg += '<code>/leech https://example.com/video.mp4 -trim "00:01:30-00:02:45"</code>\n'
    msg += "This will extract the portion from 1 minute 30 seconds to 2 minutes 45 seconds.\n\n"

    msg += "You can also use it without specifying end time to trim from a specific point to the end:\n"
    msg += '<code>/mirror https://example.com/audio.mp3 -trim "00:30:00-"</code>\n'
    msg += (
        "This will extract the portion from 30 minutes to the end of the file.\n\n"
    )

    msg += "Or trim from the beginning to a specific point:\n"
    msg += '<code>/leech https://example.com/video.mp4 -trim "-00:05:00"</code>\n'
    msg += "This will extract the portion from the beginning to 5 minutes.\n\n"

    msg += "To delete the original file after trimming, add the <code>-del</code> flag:\n"
    msg += '<code>/leech https://example.com/video.mp4 -trim "00:01:30-00:02:45" -del</code>\n'
    msg += "This will trim the video and delete the original file after successful trimming.\n\n"

    msg += "You can also configure output formats for different media types in the trim settings menu.\n"
    msg += "For example, you can set the output format for trimmed videos to MP4, MKV, or other formats.\n\n"

    msg += "<b>Supported Media Types</b>:\n"
    msg += "• <b>Videos</b>: MKV, MP4, AVI, MOV, WebM, FLV, WMV, M4V, TS, 3GP\n"
    msg += "• <b>Audio</b>: MP3, M4A, FLAC, WAV, OGG, OPUS, AAC, WMA\n"
    msg += "• <b>Images</b>: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF\n"
    msg += "• <b>Documents</b>: PDF (extracts specific pages)\n"
    msg += "• <b>Subtitles</b>: SRT, VTT, ASS, SSA\n"
    msg += "• <b>Archives</b>: ZIP, RAR, 7Z, TAR, GZ (extracts specific files)\n\n"

    msg += '<blockquote expandable="expandable"><b>Time Format</b>:\n'
    msg += "The trim feature supports several time formats:\n"
    msg += "• <b>HH:MM:SS</b>: Hours, minutes, seconds (00:30:45)\n"
    msg += "• <b>MM:SS</b>: Minutes, seconds (05:30)\n"
    msg += "• <b>SS</b>: Seconds only (90)\n"
    msg += "• <b>Decimal seconds</b>: For precise trimming (00:01:23.456)\n\n"

    msg += "Examples:\n"
    msg += (
        '<code>/leech video.mp4 -trim "00:01:30-00:02:45"</code> (HH:MM:SS format)\n'
    )
    msg += '<code>/mirror audio.mp3 -trim "5:30-10:45"</code> (MM:SS format)\n'
    msg += '<code>/leech video.mp4 -trim "90-180"</code> (seconds only)\n'
    msg += '<code>/mirror audio.mp3 -trim "01:23.456-02:34.567"</code> (with decimal seconds)</blockquote>\n\n'

    return msg


def get_trim_settings_page():
    msg = "<b>Trim Settings (14/20)</b>\n\n"

    msg += "<b>Trim Settings</b>:\n"
    msg += "• <b>Enable Trim</b>: Master toggle for the trim feature\n"
    msg += "• <b>Video Trim</b>: Enable/disable trimming for video files\n"
    msg += "• <b>Audio Trim</b>: Enable/disable trimming for audio files\n"
    msg += "• <b>Image Trim</b>: Enable/disable trimming for image files\n"
    msg += "• <b>Document Trim</b>: Enable/disable trimming for document files\n"
    msg += "• <b>Subtitle Trim</b>: Enable/disable trimming for subtitle files\n"
    msg += "• <b>Archive Trim</b>: Enable/disable trimming for archive files\n"
    msg += "• <b>Trim Priority</b>: Set the execution order among media tools (default: 5)\n"
    msg += "• <b>Delete Original</b>: Remove original file after successful trim\n\n"

    msg += "<b>Media-Specific Settings</b>:\n"
    msg += (
        "• <b>Video Codec</b>: Codec to use for video trimming (copy, h264, h265)\n"
    )
    msg += "• <b>Video Preset</b>: Encoding preset for video trimming (fast, medium, slow)\n"
    msg += "• <b>Video Format</b>: Output format for trimmed videos (mp4, mkv, avi, webm)\n"
    msg += "• <b>Audio Codec</b>: Codec to use for audio trimming (copy, aac, mp3)\n"
    msg += "• <b>Audio Preset</b>: Encoding preset for audio trimming (fast, medium, slow)\n"
    msg += "• <b>Audio Format</b>: Output format for trimmed audio (mp3, m4a, flac, opus, wav)\n"
    msg += "• <b>Image Quality</b>: Quality setting for image processing (0-100, 0 or 'none' means use original quality)\n"
    msg += "• <b>Image Format</b>: Output format for trimmed images (jpg, png, webp, gif)\n"
    msg += "• <b>Document Quality</b>: Quality setting for document processing (0-100, 0 or 'none' means use original quality)\n"
    msg += "• <b>Document Format</b>: Output format for trimmed documents (pdf, docx, txt)\n"
    msg += (
        "• <b>Subtitle Encoding</b>: Character encoding for subtitle files (UTF-8)\n"
    )
    msg += "• <b>Subtitle Format</b>: Output format for trimmed subtitles (srt, ass, vtt)\n"
    msg += "• <b>Archive Format</b>: Output format for trimmed archives (zip, 7z, tar)\n\n"

    msg += '<blockquote expandable="expandable"><b>Format Settings</b>:\n'
    msg += "• Setting any format to 'none' will use the original file format\n"
    msg += "• Format settings allow you to convert media during trimming\n"
    msg += "• For example, setting Video Format to 'mp4' will output MP4 files regardless of input format\n"
    msg += "• Format settings work with the -del flag to replace original files with trimmed versions\n"
    msg += "• Command line format flags take priority over user settings\n"
    msg += (
        "• User format settings take priority over owner settings</blockquote>\n\n"
    )

    msg += '<blockquote expandable="expandable"><b>Advanced Settings</b>:\n'
    msg += "• <b>Fast Mode</b>: Use faster encoding for large files\n"
    msg += (
        "• <b>Accurate Mode</b>: More precise trimming (slower but more accurate)\n"
    )
    msg += (
        "• <b>Keyframe Mode</b>: Trim at keyframes only (faster but less precise)\n"
    )
    msg += "• <b>Thread Count</b>: Number of CPU threads to use for processing\n"
    msg += "• <b>Max Memory</b>: Maximum memory allocation for trimming operations\n"
    msg += "• <b>Temp Directory</b>: Location for temporary files during processing</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Special Media Handling</b>:\n'
    msg += (
        "• <b>Videos</b>: Trimming preserves all streams (video, audio, subtitles)\n"
    )
    msg += "• <b>Audio</b>: Trimming preserves metadata (artist, album, etc.)\n"
    msg += "• <b>Images</b>: For static images, trimming creates a copy with quality settings\n"
    msg += "• <b>Animated GIFs</b>: Trimming extracts specific frame ranges\n"
    msg += "• <b>Documents</b>: PDF trimming extracts specific page ranges\n"
    msg += "• <b>Subtitles</b>: Trimming extracts entries within the specified time range\n"
    msg += "• <b>Archives</b>: Trimming extracts specific files based on patterns</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Delete Original Flag</b>:\n'
    msg += (
        "• Use the <code>-del</code> flag to delete original files after trimming\n"
    )
    msg += "• Example: <code>/leech https://example.com/video.mp4 -trim 00:01:30-00:02:45 -del</code>\n"
    msg += (
        "• This is useful for saving space when you only need the trimmed portion\n"
    )
    msg += "• The Delete Original setting in the trim configuration menu has the same effect\n"
    msg += "• Command line -del flag takes priority over user settings\n"
    msg += "• User Delete Original setting takes priority over owner settings</blockquote>\n\n"

    msg += "<b>Priority Settings</b>:\n"
    msg += "Trim follows the same priority settings as other media tools:\n"
    msg += "• Command line flags take highest priority\n"
    msg += "• User settings take priority over owner settings\n"
    msg += "• Owner settings are used as fallback\n"
    msg += "• Default settings are used if no others are specified\n\n"

    return msg


def get_extract_intro_page():
    msg = "<b>Extract Feature Guide (15/20)</b>\n\n"
    msg += "<b>Extract Feature</b>\n"
    msg += "Extract specific tracks (video, audio, subtitle, attachment) from media files.\n\n"

    msg += "<b>Important:</b> Make sure to enable extract in Media Tools settings before using this feature.\n\n"

    msg += "<b>How to Use</b>:\n"
    msg += "Add the <code>-extract</code> flag to extract all enabled track types:\n"
    msg += "<code>/leech https://example.com/video.mkv -extract</code>\n\n"

    msg += "Or specify track types to extract:\n"
    msg += "<code>/leech https://example.com/video.mkv -extract-video</code> (extract video tracks)\n"
    msg += "<code>/mirror https://example.com/video.mkv -extract-audio</code> (extract audio tracks)\n"
    msg += "<code>/leech https://example.com/video.mkv -extract-subtitle</code> (extract subtitle tracks)\n"
    msg += "<code>/mirror https://example.com/video.mkv -extract-attachment</code> (extract attachments)\n\n"

    msg += "You can also extract specific track indices (long format):\n"
    msg += "<code>/leech https://example.com/video.mkv -extract-video-index 0</code> (extract first video track)\n"
    msg += "<code>/mirror https://example.com/video.mkv -extract-audio-index 1</code> (extract second audio track)\n\n"

    msg += "Extract multiple tracks by specifying comma-separated indices:\n"
    msg += "<code>/leech https://example.com/video.mkv -extract-audio-index 0,1,2</code> (extract first, second, and third audio tracks)\n"
    msg += "<code>/mirror https://example.com/video.mkv -extract-subtitle-index 0,2</code> (extract first and third subtitle tracks)\n\n"

    msg += "Or use the shorter index flags:\n"
    msg += "<code>/leech https://example.com/video.mkv -vi 0</code> (extract first video track)\n"
    msg += "<code>/mirror https://example.com/video.mkv -ai 1</code> (extract second audio track)\n"
    msg += "<code>/leech https://example.com/video.mkv -si 2</code> (extract third subtitle track)\n"
    msg += "<code>/mirror https://example.com/video.mkv -ati 0</code> (extract first attachment)\n\n"

    msg += "Short flags also support multiple indices:\n"
    msg += "<code>/leech https://example.com/video.mkv -ai 0,1,2</code> (extract first, second, and third audio tracks)\n"
    msg += "<code>/mirror https://example.com/video.mkv -si 0,2</code> (extract first and third subtitle tracks)\n\n"

    msg += "<b>Supported Media Types</b>:\n"
    msg += "• <b>Container Formats</b>: MKV, MP4, AVI, MOV, WebM, FLV, WMV, M4V, TS, 3GP\n"
    msg += "• <b>Video Codecs</b>: H.264, H.265, VP9, AV1, MPEG-4, etc.\n"
    msg += "• <b>Audio Codecs</b>: AAC, MP3, OPUS, FLAC, AC3, DTS, etc.\n"
    msg += "• <b>Subtitle Formats</b>: SRT, ASS, SSA, VTT, etc.\n"
    msg += "• <b>Attachments</b>: Fonts, images, and other embedded files\n\n"

    msg += '<blockquote expandable="expandable"><b>Extract Options</b>:\n'
    msg += "• <b>Video Extract</b>: Extract video tracks from container\n"
    msg += "• <b>Video Codec</b>: Output codec for video tracks (copy, h264, h265, etc.)\n"
    msg += "• <b>Video Index</b>: Specific video track to extract (0-based index)\n"
    msg += "• <b>Audio Extract</b>: Extract audio tracks from container\n"
    msg += "• <b>Audio Codec</b>: Output codec for audio tracks (copy, aac, mp3, etc.)\n"
    msg += "• <b>Audio Index</b>: Specific audio track to extract (0-based index)\n"
    msg += "• <b>Subtitle Extract</b>: Extract subtitle tracks from container\n"
    msg += "• <b>Subtitle Codec</b>: Output codec for subtitle tracks (copy, srt, ass, etc.)\n"
    msg += "• <b>Subtitle Index</b>: Specific subtitle track to extract (0-based index)\n"
    msg += "• <b>Attachment Extract</b>: Extract attachments from container\n"
    msg += (
        "• <b>Attachment Index</b>: Specific attachment to extract (0-based index)\n"
    )
    msg += "• <b>Maintain Quality</b>: Preserve high quality during extraction</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Advanced Usage</b>:\n'
    msg += "• <b>Extract multiple track types</b>:\n"
    msg += "<code>/leech https://example.com/video.mkv -extract-video -extract-audio</code>\n"
    msg += "This will extract both video and audio tracks\n\n"
    msg += "• <b>Extract specific tracks by index</b>:\n"
    msg += "<code>/mirror https://example.com/video.mkv -extract-audio-index 0,2</code>\n"
    msg += "This will extract the first and third audio tracks\n\n"
    msg += "• <b>Extract multiple tracks with short flags</b>:\n"
    msg += "<code>/leech https://example.com/video.mkv -ai 0,1,2 -si 0,1</code>\n"
    msg += "This will extract the first three audio tracks and first two subtitle tracks\n\n"
    msg += "• <b>Delete original file after extraction</b>:\n"
    msg += "<code>/leech https://example.com/video.mkv -extract -del</code>\n"
    msg += "This will extract tracks and delete the original file</blockquote>\n\n"

    msg += "<b>Priority Settings</b>:\n"
    msg += "Extract follows the same priority settings as other media tools:\n"
    msg += "• Command line flags take highest priority\n"
    msg += "• User settings take priority over owner settings\n"
    msg += "• Owner settings are used as fallback\n"
    msg += "• Default settings are used if no others are specified\n\n"

    return msg


def get_extract_settings_page():
    msg = "<b>Extract Settings (16/20)</b>\n\n"

    msg += "<b>General Extract Settings</b>:\n"
    msg += "• <b>Enabled</b>: Master toggle for extract feature\n"
    msg += "• <b>Priority</b>: Order in which extract runs (default: 6)\n"
    msg += (
        "• <b>Maintain Quality</b>: Preserve original quality during extraction\n\n"
    )

    msg += "<b>Video Extract Settings</b>:\n"
    msg += "• <b>Video Extract</b>: Enable/disable video track extraction\n"
    msg += "• <b>Video Codec</b>: Output codec for video tracks\n"
    msg += "• <b>Video Index</b>: Specific video track(s) to extract (0-based)\n"
    msg += "• <b>Video Index Flag</b>: -extract-video-index or -vi\n"
    msg += "• <b>Multiple Indices</b>: Use comma-separated values (e.g., 0,1,2)\n\n"

    msg += "<b>Audio Extract Settings</b>:\n"
    msg += "• <b>Audio Extract</b>: Enable/disable audio track extraction\n"
    msg += "• <b>Audio Codec</b>: Output codec for audio tracks\n"
    msg += "• <b>Audio Index</b>: Specific audio track(s) to extract (0-based)\n"
    msg += "• <b>Audio Index Flag</b>: -extract-audio-index or -ai\n"
    msg += "• <b>Multiple Indices</b>: Use comma-separated values (e.g., 0,1,2)\n\n"

    msg += "<b>Subtitle Extract Settings</b>:\n"
    msg += "• <b>Subtitle Extract</b>: Enable/disable subtitle track extraction\n"
    msg += "• <b>Subtitle Codec</b>: Output codec for subtitle tracks\n"
    msg += (
        "• <b>Subtitle Index</b>: Specific subtitle track(s) to extract (0-based)\n"
    )
    msg += "• <b>Subtitle Index Flag</b>: -extract-subtitle-index or -si\n"
    msg += "• <b>Multiple Indices</b>: Use comma-separated values (e.g., 0,1,2)\n\n"

    msg += "<b>Attachment Extract Settings</b>:\n"
    msg += "• <b>Attachment Extract</b>: Enable/disable attachment extraction\n"
    msg += "• <b>Attachment Index</b>: Specific attachment(s) to extract (0-based)\n"
    msg += "• <b>Attachment Index Flag</b>: -extract-attachment-index or -ati\n"
    msg += "• <b>Multiple Indices</b>: Use comma-separated values (e.g., 0,1,2)\n\n"

    msg += '<blockquote expandable="expandable"><b>Codec Options</b>:\n'
    msg += "• <b>copy</b>: Copy stream without re-encoding (fastest, best quality)\n"
    msg += "• <b>Video Codecs</b>: h264, h265, vp9, av1, etc.\n"
    msg += "• <b>Audio Codecs</b>: aac, mp3, opus, flac, etc.\n"
    msg += "• <b>Subtitle Codecs</b>: srt, ass, vtt, etc.\n\n"
    msg += "Using 'copy' is recommended for most cases as it preserves quality and is much faster.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Index Options</b>:\n'
    msg += "• <b>None/Empty</b>: Extract all tracks of the specified type\n"
    msg += "• <b>0</b>: Extract only the first track (index starts at 0)\n"
    msg += "• <b>1</b>: Extract only the second track\n"
    msg += "• <b>2</b>: Extract only the third track\n"
    msg += "• <b>0,1</b>: Extract first and second tracks\n"
    msg += "• <b>0,2,3</b>: Extract first, third, and fourth tracks\n"
    msg += "• <b>etc.</b>: Extract specific tracks by index\n\n"
    msg += "Multiple indices can be specified in both settings and command flags.\n"
    msg += "Example setting: 0,1,2\n"
    msg += "Example command: -extract-audio-index 0,1,2 or -ai 0,1,2\n\n"
    msg += "If you're unsure about track indices, use MediaInfo to view track information.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Output Format</b>:\n'
    msg += "• <b>Video</b>: Output container depends on codec (mp4, mkv, etc.)\n"
    msg += "• <b>Audio</b>: Output container depends on codec (mp3, m4a, etc.)\n"
    msg += "• <b>Subtitle</b>: Output format matches codec (srt, ass, etc.)\n"
    msg += "• <b>Attachment</b>: Original format preserved\n\n"
    msg += "The system automatically selects appropriate containers based on the codec.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Best Practices</b>:\n'
    msg += "• Use 'copy' codec whenever possible to preserve quality\n"
    msg += "• Leave index empty to extract all tracks of a type\n"
    msg += "• Use MediaInfo to identify track indices before extraction\n"
    msg += "• Enable 'Maintain Quality' for best results\n"
    msg += "• Extract feature works best with MKV containers\n"
    msg += "• Some containers may not support certain track types\n"
    msg += "• MP4 containers have limited subtitle format support</blockquote>\n\n"

    return msg


def get_priority_guide_page():
    msg = "<b>Media Tools Priority Guide (17/20)</b>\n\n"
    msg += "<b>Understanding Priority Settings:</b>\n"
    msg += "Media tools (merge, watermark, convert, compression, trim, extract) use a priority system to determine the order of processing.\n\n"

    msg += "<b>Priority Values:</b>\n"
    msg += "• Lower number = Higher priority (runs first)\n"
    msg += "• Default merge priority: 1 (runs first)\n"
    msg += "• Default watermark priority: 2 (runs second)\n"
    msg += "• Default convert priority: 3 (runs third)\n"
    msg += "• Default compression priority: 4 (runs fourth)\n"
    msg += "• Default trim priority: 5 (runs fifth)\n"
    msg += "• Default extract priority: 6 (runs sixth)\n\n"

    msg += "<b>Priority Hierarchy:</b>\n"
    msg += "1. Command line settings (highest priority)\n"
    msg += "2. User settings (from /usettings)\n"
    msg += "3. Owner settings (from /bsettings)\n"
    msg += "4. Default settings (lowest priority)\n\n"

    msg += "<b>Setting Priority:</b>\n"
    msg += "• Use /mediatools command to set priority\n"
    msg += "• Select 'Media Tools Priority' option\n"
    msg += "• Enter a number (1 for highest priority)\n\n"

    msg += "<b>Example Scenarios:</b>\n"
    msg += "• If merge priority=1, watermark priority=2, convert priority=3, compression priority=4:\n"
    msg += "  Files will be merged first, then watermarked, then converted, then compressed\n\n"
    msg += "• If compression priority=1, convert priority=2, watermark priority=3, merge priority=4:\n"
    msg += "  Files will be compressed first, then converted, then watermarked, then merged\n\n"
    msg += "• If watermark priority=1, compression priority=2, convert priority=3, merge priority=4:\n"
    msg += "  Files will be watermarked first, then compressed, then converted, then merged\n\n"

    msg += "<b>Note:</b> Equal priority values will process in default order (merge, watermark, convert, compression)"

    return msg


def get_metadata_guide_page():
    msg = "<b>Metadata Feature Guide (20/21)</b>\n\n"
    msg += "<b>Metadata Feature</b>\n"
    msg += "Add custom metadata to your media files (videos, audio, images) to enhance organization and information.\n\n"

    msg += "<b>How to Use</b>:\n"
    msg += "Add metadata to your files using the following methods:\n"
    msg += "• <code>/leech https://example.com/video.mp4 -metadata 'My Custom Title'</code> (legacy method)\n"
    msg += "• <code>/mirror https://example.com/audio.mp3 -metadata-title 'Song Title'</code>\n"
    msg += "• <code>/leech https://example.com/video.mp4 -metadata-author 'Creator Name'</code>\n"
    msg += "• <code>/mirror https://example.com/audio.mp3 -metadata-comment 'Additional info'</code>\n"
    msg += "• <code>/leech https://example.com/video.mp4 -metadata-all 'Apply to all fields'</code>\n\n"

    msg += "<b>Track-Specific Metadata</b>:\n"
    msg += "• <code>/leech https://example.com/video.mp4 -metadata-video-title 'Video Title'</code>\n"
    msg += "• <code>/mirror https://example.com/audio.mp3 -metadata-audio-author 'Audio Author'</code>\n"
    msg += "• <code>/leech https://example.com/video.mp4 -metadata-subtitle-comment 'Subtitle Notes'</code>\n\n"

    msg += "<b>Metadata Types</b>:\n"
    msg += "• <b>Global Metadata</b>:\n"
    msg += "  - <b>Title</b>: The title of the media (shown in players and file managers)\n"
    msg += "  - <b>Author</b>: Creator or artist information\n"
    msg += "  - <b>Comment</b>: Additional notes or information\n"
    msg += "  - <b>All</b>: Single value applied to all metadata fields\n"
    msg += "• <b>Track-Specific Metadata</b>:\n"
    msg += "  - <b>Video</b>: Separate title, author, comment for video tracks\n"
    msg += "  - <b>Audio</b>: Separate title, author, comment for audio tracks\n"
    msg += "  - <b>Subtitle</b>: Separate title, author, comment for subtitle tracks\n\n"

    msg += "<b>Priority Order</b>:\n"
    msg += "1. Command line arguments (highest priority)\n"
    msg += "2. User settings from /usettings menu\n"
    msg += "3. Global settings from bot owner\n"
    msg += "4. Default values (if any)\n\n"

    msg += '<blockquote expandable="expandable"><b>Supported File Types</b>:\n'
    msg += "• <b>Video</b>: MP4, MKV, WebM, AVI, MOV, etc.\n"
    msg += "• <b>Audio</b>: MP3, M4A, FLAC, OGG, WAV, etc.\n"
    msg += "• <b>Images</b>: JPG, PNG, WebP (limited metadata support)\n"
    msg += "• <b>Documents</b>: PDF (title, author, subject)\n\n"

    msg += "Different file formats support different metadata fields. Some formats may have limitations on which metadata can be modified.</blockquote>\n\n"

    msg += '<blockquote expandable="expandable"><b>Tips for Using Metadata</b>:\n'
    msg += "• Use quotes around metadata values with spaces\n"
    msg += "• Keep metadata concise for better compatibility\n"
    msg += "• Use -metadata-all for quick application to all fields\n"
    msg += "• Individual field settings (-metadata-title, etc.) override -metadata-all\n"
    msg += "• Track-specific settings override global settings\n"
    msg += "• Some players and devices may only display certain metadata fields\n"
    msg += (
        "• Metadata is preserved during file transfers and uploads</blockquote>\n\n"
    )

    msg += '<blockquote expandable="expandable"><b>Examples</b>:\n'
    msg += "• <code>/leech https://example.com/music.zip -metadata-title 'Album Name'</code>\n"
    msg += "  Adds title metadata to all audio files\n\n"
    msg += "• <code>/mirror https://example.com/video.mp4 -metadata-author 'Channel Name'</code>\n"
    msg += "  Sets the author/artist metadata field\n\n"
    msg += "• <code>/leech https://example.com/podcast.mp3 -metadata-all 'My Podcast'</code>\n"
    msg += "  Sets all metadata fields to 'My Podcast'\n\n"
    msg += "• <code>/mirror https://example.com/video.mp4 -metadata-video-title 'Episode 1' -metadata-audio-author 'My Channel'</code>\n"
    msg += "  Sets different metadata for video and audio tracks</blockquote>\n\n"

    msg += "<b>Managing Metadata</b>:\n"
    msg += "• Configure default metadata in your user settings with /usettings\n"
    msg += "• Access the metadata settings page from the main menu\n"
    msg += "• Set different values for different metadata fields and tracks\n"
    msg += "• Reset all metadata settings with the 'Reset All Metadata' button\n"

    return msg


def get_usage_examples_page_1():
    msg = "<b>Media Tools Usage Examples (1/2) (18/21)</b>\n\n"

    msg += "<b>Merge Examples:</b>\n"
    msg += "• <code>/leech https://example.com/videos.zip -merge-video</code>\n"
    msg += "  Merges all video files in the archive while preserving all video and subtitle tracks\n\n"
    msg += "• <code>/mirror https://example.com/music.zip -merge-audio</code>\n"
    msg += "  Combines all audio files into a single audio file\n\n"
    msg += "• <code>/leech https://example.com/files.zip -m folder_name -merge-all</code>\n"
    msg += "  Merges all files by type in a custom folder while preserving all tracks\n\n"

    msg += "<b>Watermark Examples:</b>\n"
    msg += '• <code>/leech https://example.com/video.mp4 -wm "My Watermark"</code>\n'
    msg += "  Adds text watermark to the video\n\n"
    msg += '• <code>/mirror https://example.com/videos.zip -wm "© 2023"</code>\n'
    msg += "  Adds copyright watermark to all videos\n\n"
    msg += '• <code>/leech https://example.com/images.zip -wm "My Logo" -wm-position bottom_right</code>\n'
    msg += "  Adds watermark at bottom right position to all images\n\n"

    msg += "<b>Convert Examples:</b>\n"
    msg += "• <code>/leech https://example.com/video.webm -cv mp4</code>\n"
    msg += "  Converts WebM video to MP4 format\n\n"
    msg += "• <code>/mirror https://example.com/audio.wav -ca mp3</code>\n"
    msg += "  Converts WAV audio to MP3 format\n\n"
    msg += "• <code>/leech https://example.com/media.zip -cv mp4 -ca mp3</code>\n"
    msg += "  Converts all videos to MP4 and all audios to MP3\n\n"

    msg += "<b>Combined Usage:</b>\n"
    msg += '• <code>/leech https://example.com/videos.zip -merge-video -wm "My Channel"</code>\n'
    msg += "  Merges videos first, then adds watermark (default priority)\n\n"
    msg += '• <code>/mirror https://example.com/files.zip -m folder -merge-all -wm "© 2023"</code>\n'
    msg += (
        "  Merges files by type while preserving all tracks, then adds watermark\n\n"
    )

    msg += "<b>Note:</b> See next page for more examples"

    return msg


def get_usage_examples_page_2():
    msg = "<b>Media Tools Usage Examples (2/2) (19/21)</b>\n\n"

    msg += "<b>Compression Examples:</b>\n"
    msg += "• <code>/leech https://example.com/video.mp4 -video-fast</code>\n"
    msg += "  Compresses video using fast preset\n\n"
    msg += "• <code>/mirror https://example.com/audio.mp3 -audio-medium</code>\n"
    msg += "  Compresses audio using medium preset\n\n"
    msg += "• <code>/leech https://example.com/image.png -image-slow</code>\n"
    msg += "  Compresses image using slow preset\n\n"

    msg += "<b>Extract Examples:</b>\n"
    msg += "• <code>/leech https://example.com/video.mkv -extract</code>\n"
    msg += "  Extracts all enabled track types based on settings\n\n"
    msg += "• <code>/mirror https://example.com/video.mkv -extract-video</code>\n"
    msg += "  Extracts only video tracks from the container\n\n"
    msg += "• <code>/leech https://example.com/video.mkv -extract-audio</code>\n"
    msg += "  Extracts only audio tracks from the container\n\n"
    msg += "• <code>/mirror https://example.com/video.mkv -extract-subtitle</code>\n"
    msg += "  Extracts only subtitle tracks from the container\n\n"
    msg += "• <code>/leech https://example.com/video.mkv -extract-video-index 0 -extract-audio-index 1</code>\n"
    msg += "  Extracts first video track and second audio track\n\n"
    msg += "• <code>/mirror https://example.com/video.mkv -vi 0 -ai 1</code>\n"
    msg += "  Same as above but using shorter index flags\n\n"
    msg += "• <code>/leech https://example.com/video.mkv -extract-audio-index 0,1,2</code>\n"
    msg += "  Extracts first, second, and third audio tracks\n\n"

    msg += "<b>Combined with Other Tools:</b>\n"
    msg += '• <code>/leech https://example.com/videos.zip -merge-video -video-medium -wm "My Channel"</code>\n'
    msg += "  Merges videos, compresses with medium preset, then adds watermark\n\n"
    msg += '• <code>/mirror https://example.com/media.zip -cv mp4 -video-fast -wm "© 2023"</code>\n'
    msg += "  Converts to MP4, compresses with fast preset, then adds watermark\n\n"
    msg += "• <code>/leech https://example.com/video.mkv -extract-audio -ca mp3 -del</code>\n"
    msg += "  Extracts audio tracks, converts them to MP3, and deletes original file\n\n"

    msg += "<b>Using the -mt Flag:</b>\n"
    msg += "• <code>/mirror https://example.com/video.mp4 -mt</code>\n"
    msg += "  Opens media tools settings before starting the task\n\n"
    msg += "• <code>/leech https://example.com/files.zip -merge-video -mt</code>\n"
    msg += "  Opens media tools settings before merging videos\n\n"

    msg += "<b>Note:</b> Use /mediatools command to configure advanced settings or use the -mt flag with any command"

    return msg


def get_mt_flag_guide_page():
    msg = "<b>Media Tools Flag Guide (21/21)</b>\n\n"
    msg += "<b>-mt Flag Feature</b>\n"
    msg += "The <code>-mt</code> flag allows you to customize media tools settings before starting a task.\n\n"

    msg += "<b>How It Works</b>:\n"
    msg += "1. Add the <code>-mt</code> flag to any download command\n"
    msg += "2. The bot will show the media tools settings menu\n"
    msg += "3. Customize your settings as needed\n"
    msg += "4. Click <b>Done</b> to start the task with your settings\n"
    msg += "5. Click <b>Cancel</b> to abort the task\n"
    msg += (
        "6. If no action is taken within 60 seconds, the task will be cancelled\n\n"
    )

    msg += "<b>Key Features</b>:\n"
    msg += "• Pause task execution to allow customization\n"
    msg += "• All command and cancellation messages are auto-deleted\n"
    msg += "• 60-second timeout for user interaction\n"
    msg += "• <b>Done</b> button to start the task when ready\n"
    msg += "• <b>Cancel</b> button to abort the task\n\n"

    msg += '<blockquote expandable="expandable"><b>Usage Examples</b>:\n'
    msg += "• <code>/mirror https://example.com/video.mp4 -mt</code>\n"
    msg += "  Shows media tools settings before starting the mirror task\n\n"
    msg += "• <code>/leech https://example.com/files.zip -z -mt</code>\n"
    msg += "  Shows media tools settings before starting the leech task with zip extraction\n\n"
    msg += "• <code>/ytdl https://youtube.com/watch?v=example -mt</code>\n"
    msg += "  Shows media tools settings before starting the YouTube download\n\n"
    msg += "• <code>/mirror https://example.com/videos.zip -merge-video -mt</code>\n"
    msg += "  Shows media tools settings before starting a task with video merging</blockquote>\n\n"

    msg += "<b>Benefits</b>:\n"
    msg += "• Configure media tools settings on-the-fly for specific tasks\n"
    msg += "• No need to use separate commands to change settings\n"
    msg += "• Preview and adjust settings before processing large files\n"
    msg += "• Easily cancel tasks if settings aren't right\n"
    msg += "• Works with all download commands and other flags\n\n"

    msg += "<b>Note</b>: All messages related to the <code>-mt</code> flag interaction are automatically deleted after 5 minutes for a cleaner chat experience.\n\n"

    return msg


def get_pagination_buttons(current_page):
    buttons = ButtonMaker()

    # Total number of pages
    total_pages = 21

    # Add navigation buttons
    if current_page > 1:
        buttons.data_button("⬅️ Previous", f"mthelp_page_{current_page - 1}")

    # Page indicator
    buttons.data_button(f"Page {current_page}/{total_pages}", "mthelp_current")

    if current_page < total_pages:
        buttons.data_button("Next ➡️", f"mthelp_page_{current_page + 1}")

    # Close button
    buttons.data_button("Close", "mthelp_close", "footer")

    return buttons.build_menu(3)


async def media_tools_help_cmd(_, message):
    """
    Display media tools help with pagination
    """
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

    # Delete the command message immediately
    await delete_message(message)

    # Start with page 1
    current_page = 1

    # Check if the user is trying to access a specific page
    if hasattr(message, "text") and len(message.text.split()) > 1:
        try:
            requested_page = int(message.text.split()[1])
            if 1 <= requested_page <= 21:  # Assuming 21 is the max page
                current_page = requested_page
        except ValueError:
            pass

    content = get_page_content(current_page)
    buttons = get_pagination_buttons(current_page)

    # Send the first page
    help_msg = await send_message(message, content, buttons)

    # Schedule auto-deletion after 5 minutes
    create_task(auto_delete_message(help_msg, time=300))


async def media_tools_help_callback(_, callback_query):
    """
    Handle callback queries for media tools help pagination
    """
    message = callback_query.message
    data = callback_query.data

    # User ID and debug message removed to reduce logging

    # Handle close button
    if data == "mthelp_close":
        await delete_message(message)
        await callback_query.answer()
        return

    # Skip processing for current page indicator
    if data == "mthelp_current":
        await callback_query.answer("Current page")
        return

    # Extract page number from callback data
    if data.startswith("mthelp_page_"):
        try:
            page_num = int(data.split("_")[-1])
            # Debug logs removed to reduce logging
            content = get_page_content(page_num)
            buttons = get_pagination_buttons(page_num)

            # Edit the message with new page content
            await edit_message(message, content, buttons)
            await callback_query.answer(f"Page {page_num}")
        except Exception as e:
            LOGGER.error(f"Error in media_tools_help_callback: {e!s}")
            await callback_query.answer("Error processing request")


# Handler will be added in core/handlers.py
# Also need to register the callback handler
