#!/usr/bin/env python3
import contextlib
import os
from logging import getLogger

import aiohttp

from bot.helper.ext_utils.gc_utils import smart_garbage_collection

LOGGER = getLogger(__name__)

# Directory to store Google Fonts
FONTS_DIR = "fonts"

# Font styles mapping
FONT_STYLES = {
    # Telegram HTML Styles
    "monospace": lambda text: f"<pre>{text}</pre>",
    "bold": lambda text: f"<b>{text}</b>",
    "italic": lambda text: f"<i>{text}</i>",
    "underline": lambda text: f"<u>{text}</u>",
    "strike": lambda text: f"<s>{text}</s>",
    # Using Electrogram's spoiler tag
    "spoiler": lambda text: f"<spoiler>{text}</spoiler>",
    "code": lambda text: f"<code>{text}</code>",
    "quote": lambda text: f"<blockquote>{text}</blockquote>",
    # Combined HTML Styles
    "bold_italic": lambda text: f"<b><i>{text}</i></b>",
    "underline_italic": lambda text: f"<u><i>{text}</i></u>",
    "underline_bold": lambda text: f"<u><b>{text}</b></u>",
    "underline_bold_italic": lambda text: f"<u><b><i>{text}</i></b></u>",
    "quote_expandable": lambda text: f"<blockquote expandable>{text}</blockquote>",
    "bold_quote": lambda text: f"<b><blockquote>{text}</blockquote></b>",
    # Google Unicode Font Styles - Mathematical Variants
    "serif": lambda text: "".join([_map_to_serif(c) for c in text]),
    "sans": lambda text: "".join([_map_to_sans(c) for c in text]),
    "script": lambda text: "".join([_map_to_script(c) for c in text]),
    "double": lambda text: "".join([_map_to_double(c) for c in text]),
    "gothic": lambda text: "".join([_map_to_gothic(c) for c in text]),
    "fraktur": lambda text: "".join([_map_to_fraktur(c) for c in text]),
    "mono": lambda text: "".join([_map_to_mono(c) for c in text]),
    # Additional Unicode Font Styles
    "small_caps": lambda text: "".join([_map_to_small_caps(c) for c in text]),
    "circled": lambda text: "".join([_map_to_circled(c) for c in text]),
    "bubble": lambda text: "".join([_map_to_bubble(c) for c in text]),
    "inverted": lambda text: "".join([_map_to_inverted(c) for c in text]),
    "squared": lambda text: "".join([_map_to_squared(c) for c in text]),
    "regional": lambda text: "".join([_map_to_regional(c) for c in text]),
    "superscript": lambda text: "".join([_map_to_superscript(c) for c in text]),
    "subscript": lambda text: "".join([_map_to_subscript(c) for c in text]),
    "wide": lambda text: "".join([_map_to_wide(c) for c in text]),
    "cursive": lambda text: "".join([_map_to_cursive(c) for c in text]),
    # Combined HTML styles
    "bold_code": lambda text: f"<b><code>{text}</code></b>",
    "italic_code": lambda text: f"<i><code>{text}</code></i>",
    "underline_code": lambda text: f"<u><code>{text}</code></u>",
    "bold_spoiler": lambda text: f"<b><spoiler>{text}</spoiler></b>",
    "italic_spoiler": lambda text: f"<i><spoiler>{text}</spoiler></i>",
    "bold_monospace": lambda text: f"<b><pre>{text}</pre></b>",
    "italic_monospace": lambda text: f"<i><pre>{text}</pre></i>",
    "bold_quote_expandable": lambda text: f"<b><blockquote expandable>{text}</blockquote></b>",
    "italic_quote_expandable": lambda text: f"<i><blockquote expandable>{text}</blockquote></i>",
}

# Unicode character mappings for different font styles
# These mappings convert regular ASCII characters to their Unicode variants


def _map_to_serif(char):
    # Serif font (Mathematical Serif)
    if "a" <= char <= "z":
        return chr(ord("𝐚") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝐀") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("𝟎") + ord(char) - ord("0"))
    return char


def _map_to_sans(char):
    # Sans-serif font
    if "a" <= char <= "z":
        return chr(ord("𝗮") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝗔") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("𝟬") + ord(char) - ord("0"))
    return char


def _map_to_script(char):
    # Script/cursive font
    if "a" <= char <= "z":
        return chr(ord("𝓪") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝓐") + ord(char) - ord("A"))
    return char


def _map_to_double(char):
    # Double-struck (blackboard bold)
    if "a" <= char <= "z":
        return chr(ord("𝕒") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝔸") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("𝟘") + ord(char) - ord("0"))
    return char


def _map_to_gothic(char):
    # Gothic/Fraktur font
    if "a" <= char <= "z":
        return chr(ord("𝖆") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝕬") + ord(char) - ord("A"))
    return char


def _map_to_fraktur(char):
    # Fraktur font
    if "a" <= char <= "z":
        return chr(ord("𝔞") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝔄") + ord(char) - ord("A"))
    return char


def _map_to_mono(char):
    # Monospace font
    if "a" <= char <= "z":
        return chr(ord("𝚊") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("𝙰") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("𝟶") + ord(char) - ord("0"))
    return char


def _map_to_small_caps(char):
    # Small Caps font
    if "a" <= char <= "z":
        return chr(ord("ᴀ") + ord(char) - ord("a"))
    return char


def _map_to_circled(char):
    # Circled font
    if "a" <= char <= "z":
        return chr(ord("ⓐ") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("Ⓐ") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("⓪") + ord(char) - ord("0"))
    return char


def _map_to_bubble(char):
    # Bubble font (Fullwidth)
    if "a" <= char <= "z":
        return chr(ord("ａ") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("Ａ") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("０") + ord(char) - ord("0"))
    return char


def _map_to_inverted(char):
    # Inverted/upside-down font
    inverted_chars = {
        "a": "ɐ",
        "b": "q",
        "c": "ɔ",
        "d": "p",
        "e": "ǝ",
        "f": "ɟ",
        "g": "ƃ",
        "h": "ɥ",
        "i": "ᴉ",
        "j": "ɾ",
        "k": "ʞ",
        "l": "l",
        "m": "ɯ",
        "n": "u",
        "o": "o",
        "p": "d",
        "q": "b",
        "r": "ɹ",
        "s": "s",
        "t": "ʇ",
        "u": "n",
        "v": "ʌ",
        "w": "ʍ",
        "x": "x",
        "y": "ʎ",
        "z": "z",
        "A": "∀",
        "B": "B",
        "C": "Ɔ",
        "D": "D",
        "E": "Ǝ",
        "F": "Ⅎ",
        "G": "פ",
        "H": "H",
        "I": "I",
        "J": "ſ",
        "K": "K",
        "L": "˥",
        "M": "W",
        "N": "N",
        "O": "O",
        "P": "Ԁ",
        "Q": "Q",
        "R": "R",
        "S": "S",
        "T": "┴",
        "U": "∩",
        "V": "Λ",
        "W": "M",
        "X": "X",
        "Y": "⅄",
        "Z": "Z",
        "0": "0",
        "1": "Ɩ",
        "2": "ᄅ",
        "3": "Ɛ",
        "4": "ㄣ",
        "5": "ϛ",
        "6": "9",
        "7": "ㄥ",
        "8": "8",
        "9": "6",
        ".": "˙",
        ",": "'",
        "'": ",",
        '"': ",,",
        "`": ",",
        "?": "¿",
        "!": "¡",
        "(": ")",
        ")": "(",
        "[": "]",
        "]": "[",
        "{": "}",
        "}": "{",
        "<": ">",
        ">": "<",
        "&": "⅋",
        "_": "‾",
        "^": "v",
        "/": "\\",
        "\\": "/",
    }
    return inverted_chars.get(char, char)


def _map_to_squared(char):
    # Squared font
    if "a" <= char <= "z":
        return chr(ord("🇦") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("🇦") + ord(char) - ord("A"))
    return char


def _map_to_regional(char):
    # Regional indicator symbols (flag emojis)
    if "a" <= char <= "z":
        return chr(ord("🇦") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("🇦") + ord(char) - ord("A"))
    return char


def _map_to_superscript(char):
    # Superscript font
    superscript_map = {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "a": "ᵃ",
        "b": "ᵇ",
        "c": "ᶜ",
        "d": "ᵈ",
        "e": "ᵉ",
        "f": "ᶠ",
        "g": "ᵍ",
        "h": "ʰ",
        "i": "ⁱ",
        "j": "ʲ",
        "k": "ᵏ",
        "l": "ˡ",
        "m": "ᵐ",
        "n": "ⁿ",
        "o": "ᵒ",
        "p": "ᵖ",
        "q": "ᵠ",
        "r": "ʳ",
        "s": "ˢ",
        "t": "ᵗ",
        "u": "ᵘ",
        "v": "ᵛ",
        "w": "ʷ",
        "x": "ˣ",
        "y": "ʸ",
        "z": "ᶻ",
        "A": "ᴬ",
        "B": "ᴮ",
        "C": "ᶜ",
        "D": "ᴰ",
        "E": "ᴱ",
        "F": "ᶠ",
        "G": "ᴳ",
        "H": "ᴴ",
        "I": "ᴵ",
        "J": "ᴶ",
        "K": "ᴷ",
        "L": "ᴸ",
        "M": "ᴹ",
        "N": "ᴺ",
        "O": "ᴼ",
        "P": "ᴾ",
        "Q": "ᵠ",
        "R": "ᴿ",
        "S": "ˢ",
        "T": "ᵀ",
        "U": "ᵁ",
        "V": "ⱽ",
        "W": "ᵂ",
        "X": "ˣ",
        "Y": "ʸ",
        "Z": "ᶻ",
        "+": "⁺",
        "-": "⁻",
        "=": "⁼",
        "(": "⁽",
        ")": "⁾",
    }
    return superscript_map.get(char, char)


def _map_to_subscript(char):
    # Subscript font
    subscript_map = {
        "0": "₀",
        "1": "₁",
        "2": "₂",
        "3": "₃",
        "4": "₄",
        "5": "₅",
        "6": "₆",
        "7": "₇",
        "8": "₈",
        "9": "₉",
        "a": "ₐ",
        "e": "ₑ",
        "h": "ₕ",
        "i": "ᵢ",
        "j": "ⱼ",
        "k": "ₖ",
        "l": "ₗ",
        "m": "ₘ",
        "n": "ₙ",
        "o": "ₒ",
        "p": "ₚ",
        "r": "ᵣ",
        "s": "ₛ",
        "t": "ₜ",
        "u": "ᵤ",
        "v": "ᵥ",
        "x": "ₓ",
        "+": "₊",
        "-": "₋",
        "=": "₌",
        "(": "₍",
        ")": "₎",
    }
    return subscript_map.get(char, char)


def _map_to_wide(char):
    # Wide text (fullwidth)
    if "a" <= char <= "z":
        return chr(ord("ａ") + ord(char) - ord("a"))
    if "A" <= char <= "Z":
        return chr(ord("Ａ") + ord(char) - ord("A"))
    if "0" <= char <= "9":
        return chr(ord("０") + ord(char) - ord("0"))
    # Map common punctuation
    wide_punct = {
        " ": "　",
        "!": "！",
        '"': "＂",
        "#": "＃",
        "$": "＄",
        "%": "％",
        "&": "＆",
        "'": "＇",
        "(": "（",
        ")": "）",
        "*": "＊",
        "+": "＋",
        ",": "，",
        "-": "－",
        ".": "．",
        "/": "／",
        ":": "：",
        ";": "；",
        "<": "＜",
        "=": "＝",
        ">": "＞",
        "?": "？",
        "@": "＠",
        "[": "［",
        "\\": "＼",
        "]": "］",
        "^": "＾",
        "_": "＿",
        "`": "｀",
        "{": "｛",
        "|": "｜",
        "}": "｝",
        "~": "～",
    }
    return wide_punct.get(char, char)


def _map_to_cursive(char):
    # Cursive/script font (alternative to the existing script font)
    cursive_map = {
        "a": "𝓪",
        "b": "𝓫",
        "c": "𝓬",
        "d": "𝓭",
        "e": "𝓮",
        "f": "𝓯",
        "g": "𝓰",
        "h": "𝓱",
        "i": "𝓲",
        "j": "𝓳",
        "k": "𝓴",
        "l": "𝓵",
        "m": "𝓶",
        "n": "𝓷",
        "o": "𝓸",
        "p": "𝓹",
        "q": "𝓺",
        "r": "𝓻",
        "s": "𝓼",
        "t": "𝓽",
        "u": "𝓾",
        "v": "𝓿",
        "w": "𝔀",
        "x": "𝔁",
        "y": "𝔂",
        "z": "𝔃",
        "A": "𝓐",
        "B": "𝓑",
        "C": "𝓒",
        "D": "𝓓",
        "E": "𝓔",
        "F": "𝓕",
        "G": "𝓖",
        "H": "𝓗",
        "I": "𝓘",
        "J": "𝓙",
        "K": "𝓚",
        "L": "𝓛",
        "M": "𝓜",
        "N": "𝓝",
        "O": "𝓞",
        "P": "𝓟",
        "Q": "𝓠",
        "R": "𝓡",
        "S": "𝓢",
        "T": "𝓣",
        "U": "𝓤",
        "V": "𝓥",
        "W": "𝓦",
        "X": "𝓧",
        "Y": "𝓨",
        "Z": "𝓩",
    }
    return cursive_map.get(char, char)


async def apply_font_style(text, style):
    """
    Apply a font style to the given text.

    Args:
        text (str): The text to style
        style (str): The style to apply (can be a FONT_STYLES key, Google Font name, or Unicode character)

    Returns:
        str: The styled text
    """
    if not style:
        return text

    # Handle the literal string "style" as a special case
    if style.lower() == "style":
        return f"<code>{text}</code>"

    style_lower = style.lower()

    # Check if it's a predefined style in FONT_STYLES
    if style_lower in FONT_STYLES:
        try:
            return FONT_STYLES[style_lower](text)
        except Exception as e:
            LOGGER.error(f"Error applying font style {style}: {e}")
            return text

    # Check if it's a Unicode emoji or special character
    if len(style) == 1 or style.startswith("U+"):
        try:
            # Try to use it as a prefix/suffix for each character
            if style.startswith("U+"):
                # Convert U+XXXX format to actual Unicode character
                try:
                    hex_val = style[2:]
                    char = chr(int(hex_val, 16))
                    return char + text + char
                except ValueError:
                    LOGGER.error(f"Invalid Unicode format: {style}")
                    return text
            else:
                return style + text + style
        except Exception as e:
            LOGGER.error(f"Error applying custom style {style}: {e}")
            return text

    # Check if it's a Google Font
    try:
        # Try to apply Google Font style
        google_font_text = await apply_google_font_style(text, style)
        if google_font_text != f"<code>{text}</code>":
            # If the Google Font was successfully applied
            return google_font_text
    except Exception as e:
        LOGGER.error(f"Error checking Google Font {style}: {e}")

    # If all else fails, return the original text with a code tag
    return f"<code>{text}</code>"


async def download_google_font(font_name):
    """
    Download a font from Google Fonts API.

    Args:
        font_name: Name of the Google Font to download

    Returns:
        str: Path to the downloaded font file or None if download fails
    """
    try:
        # Create fonts directory if it doesn't exist
        os.makedirs(FONTS_DIR, exist_ok=True)

        # Check if font already exists
        font_path = f"{FONTS_DIR}/{font_name}.ttf"
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
                    return None

                css = await response.text()

                # Extract the font URL from the CSS
                font_url_start = css.find("src: url(")
                if font_url_start == -1:
                    LOGGER.error(f"Could not find font URL in CSS for {font_name}")
                    return None

                font_url_start += 9  # Length of "src: url("
                font_url_end = css.find(")", font_url_start)
                font_url = css[font_url_start:font_url_end]

                # Download the font file
                async with session.get(font_url) as font_response:
                    if font_response.status != 200:
                        LOGGER.error(
                            f"Failed to download font file for {font_name}: {font_response.status}"
                        )
                        return None

                    # Use context manager to ensure file is properly closed
                    try:
                        with open(font_path, "wb") as f:
                            font_data = await font_response.read()
                            f.write(font_data)
                            # Explicitly delete large data after writing
                            del font_data
                            # Force garbage collection after handling large data
                            # Use normal mode for better performance with binary data
                            smart_garbage_collection(aggressive=False)
                    except Exception as e:
                        LOGGER.error(f"Error writing font file {font_name}: {e}")
                        # Clean up partial file if there was an error
                        with contextlib.suppress(Exception):
                            if os.path.exists(font_path):
                                os.remove(font_path)
                        return None

                    LOGGER.info(f"Successfully downloaded Google Font: {font_name}")
                    return font_path
    except Exception as e:
        LOGGER.error(f"Error downloading Google Font {font_name}: {e!s}")
        return None


async def is_google_font(font_name):
    """
    Check if a font name is a valid Google Font.

    Args:
        font_name: Name of the font to check (can include weight, e.g., "Roboto:700")

    Returns:
        bool: True if the font is a valid Google Font, False otherwise
    """
    # Check if it's just a numeric weight (like "400")
    if font_name.isdigit():
        return False

    # Extract just the font name if weight is included
    if ":" in font_name:
        font_name = font_name.split(":", 1)[0]

    # If it's already a file path, it's not a Google Font name
    if font_name.endswith((".ttf", ".otf")):
        return False

    # If it's in the FONT_STYLES dictionary, it's not a Google Font
    if font_name.lower() in FONT_STYLES:
        return False

    # If it's the literal string "style", it's not a valid font
    if font_name.lower() == "style":
        return False

    # Try to download the font to check if it exists
    font_path = await download_google_font(font_name)
    return font_path is not None


async def apply_google_font_style(text, font_name):
    """
    Apply a Google Font style to the given text using HTML formatting.
    Since Telegram doesn't support actual font files in messages,
    this function wraps the text in a span with a font-family style.

    Args:
        text (str): The text to style
        font_name (str): The Google Font name to apply (can include weight, e.g., "Roboto:700")

    Returns:
        str: The styled text with HTML font-family attribute
    """
    # Parse font name and weight if provided (e.g., "Roboto:700")
    font_weight = ""
    if ":" in font_name:
        font_name, font_weight = font_name.split(":", 1)

    # Check if the font exists
    font_exists = await is_google_font(font_name)
    if not font_exists:
        return f"<code>{text}</code>"

    # Apply the font using HTML (this is just for visual indication in the caption)
    # Note: Telegram doesn't actually render custom fonts, but this shows the user what font was applied
    if font_weight:
        return f"<span style='font-family: \"{font_name}\"; font-weight: {font_weight};'>{text}</span>"
    return f"<span style='font-family: \"{font_name}\";'>{text}</span>"


def get_available_fonts():
    """
    Get a list of available font styles.

    Returns:
        list: List of available font style names
    """
    return list(FONT_STYLES.keys())


async def list_google_fonts():
    """
    Get a list of popular Google Fonts.

    Returns:
        list: List of popular Google Font names
    """
    # List of popular Google Fonts
    return [
        "Roboto",
        "Open Sans",
        "Lato",
        "Montserrat",
        "Roboto Condensed",
        "Source Sans Pro",
        "Oswald",
        "Raleway",
        "Ubuntu",
        "Merriweather",
        "Playfair Display",
        "Roboto Mono",
        "Poppins",
        "Noto Sans",
        "Roboto Slab",
        "PT Sans",
        "Lora",
        "Nunito",
        "Work Sans",
        "Fira Sans",
    ]
