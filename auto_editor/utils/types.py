from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal, Union


class CoerceError(Exception):
    pass


def _comma_coerce(name: str, val: str, num_args: int) -> list[str]:
    vals = val.strip().split(",")
    if num_args > len(vals):
        raise CoerceError(f"Too few arguments for {name}.")
    if len(vals) > num_args:
        raise CoerceError(f"Too many arguments for {name}.")
    return vals


def _split_num_str(val: str | float) -> tuple[float, str]:
    if isinstance(val, (float, int)):
        return val, ""

    NUM_CHARS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "_", " ", ".", "-"}
    index = 0
    for char in val:
        if char not in NUM_CHARS:
            break
        index += 1
    num, unit = val[:index], val[index:]
    try:
        float(num)
    except ValueError:
        raise CoerceError(f"Invalid number: '{val}'")
    return float(num), unit


def _unit_check(unit: str, allowed_units: tuple[str, ...]) -> None:
    if unit not in allowed_units:
        raise CoerceError(f"Unknown unit: '{unit}'")


# Numbers: 0, 1, 2, 3, ...
def natural(val: str | float) -> int:
    num, unit = _split_num_str(val)
    if unit != "":
        raise CoerceError(f"'{val}': Natural does not allow units.")
    if not isinstance(num, int) and not num.is_integer():
        raise CoerceError(f"'{val}': Natural must be a valid integer.")
    if num < 0:
        raise CoerceError(f"'{val}': Natural cannot be negative.")
    return int(num)


def natural_or_none(val: str | float | None) -> int | None:
    return None if val is None else natural(val)


def bool_coerce(val: str) -> bool:
    if val in ("#t", "#true", "true"):
        return True
    if val in ("#f", "#false", "false"):
        return False
    raise CoerceError(f"'{val}': Invalid boolean")


def number(val: str | float) -> float:
    if isinstance(val, str) and "/" in val:
        nd = val.split("/")
        if len(nd) != 2:
            raise CoerceError(f"'{val}': One divisor allowed.")
        vs = []
        for v in nd:
            try:
                vs.append(int(v))
            except ValueError:
                raise CoerceError(
                    f"'{val}': Numerator and Denominator must be integers."
                )
        if vs[1] == 0:
            raise CoerceError(f"'{val}': Denominator must not be zero.")
        return vs[0] / vs[1]

    num, unit = _split_num_str(val)
    if unit == "%":
        return num / 100
    _unit_check(unit, ("",))
    return num


def speed(val: str) -> float:
    _s = number(val)
    if _s <= 0 or _s > 99999:
        return 99999.0
    return _s


def db_number(val: str) -> float | str:
    num, unit = _split_num_str(val)
    if unit == "dB":
        return val

    return number(val)


def src(val: str) -> int | str:
    try:
        if int(val) > 0:
            return int(val)
    except ValueError:
        pass

    return val


def threshold(val: str | float) -> float:
    num = number(val)
    if num > 1 or num < 0:
        raise CoerceError(f"'{val}': Threshold must be between 0 and 1 (0%-100%)")
    return num


def db_threshold(val: str) -> str | float:
    num, unit = _split_num_str(val)
    if unit == "dB":
        if num > 0:
            raise CoerceError("dB only goes up to 0")
        return 10 ** (num / 20)

    return threshold(val)


def frame_rate(val: str) -> Fraction:
    if val == "ntsc":
        return Fraction(30000, 1001)
    if val == "ntsc_film":
        return Fraction(24000, 1001)
    if val == "pal":
        return Fraction(25)
    if val == "film":
        return Fraction(24)
    return Fraction(val)


def sample_rate(val: str) -> int:
    num, unit = _split_num_str(val)
    if unit in ("kHz", "KHz"):
        return natural(num * 1000)
    _unit_check(unit, ("", "Hz"))
    return natural(num)


def time(val: str) -> int | str:
    if ":" in val:
        boxes = val.split(":")
        if len(boxes) == 2:
            return str(int(boxes[0]) * 60 + float(boxes[1]))
        if len(boxes) == 3:
            return str(int(boxes[0]) * 3600 + int(boxes[1]) * 60 + float(boxes[2]))
        raise CoerceError(f"'{val}': Invalid time format")

    num, unit = _split_num_str(val)
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return str(num)
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return str(num * 60)
    if unit in ("h", "hour", "hours"):
        return str(num * 3600)

    _unit_check(unit, ("",))
    if not isinstance(num, int) and not num.is_integer():
        raise CoerceError(f"'{val}': Time specifier expects: integer?.")
    return int(num)


def anchor(val: str) -> str:
    allowed = ("tl", "tr", "bl", "br", "ce")
    if val not in allowed:
        raise CoerceError(f"Anchor must be: {' '.join(allowed)}")
    return val


Margin = tuple[Union[int, str], Union[int, str]]


def margin(val: str) -> Margin:
    vals = val.strip().split(",")
    if len(vals) == 1:
        vals.append(vals[0])
    if len(vals) != 2:
        raise CoerceError("--margin has too many arguments.")
    return time(vals[0]), time(vals[1])


def time_range(val: str) -> list[str]:
    return _comma_coerce("time_range", val, 2)


def speed_range(val: str) -> tuple[float, str, str]:
    a = _comma_coerce("speed_range", val, 3)
    return number(a[0]), a[1], a[2]


Align = Literal["left", "center", "right"]


def align(val: str) -> Align:
    if val == "left":
        return "left"
    if val == "center":
        return "center"
    if val == "right":
        return "right"
    raise CoerceError("Align must be 'left', 'right', or 'center'")


Stream = Union[int, Literal["all"]]


def stream(val: str) -> Stream:
    if val == "all":
        return "all"
    return natural(val)


def color(val: str) -> str:
    """
    Convert a color str into an RGB tuple

    Accepts:
        - color names (black, red, blue)
        - 3 digit hex codes (#FFF, #3AE)
        - 6 digit hex codes (#3F0401, #005601)
    """

    color = val.lower()

    if color in colormap:
        color = colormap[color]

    if re.match("#[a-f0-9]{3}$", color):
        return "#" + "".join([x * 2 for x in color[1:]])

    if re.match("#[a-f0-9]{6}$", color):
        return color

    raise ValueError(f"Invalid Color: '{color}'")


def resolution(val: str | None) -> tuple[int, int] | None:
    if val is None:
        return None
    vals = val.strip().split(",")
    if len(vals) != 2:
        raise CoerceError(f"'{val}': Resolution takes two numbers")

    return natural(vals[0]), natural(vals[1])


def pos(val: tuple[float | str, int]) -> int:
    num, unit = _split_num_str(val[0])
    if unit == "%":
        return round((num / 100) * val[1])
    _unit_check(unit, ("",))
    return round(num)


@dataclass
class Args:
    add: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=list)
    yt_dlp_location: str = "yt-dlp"
    download_format: str | None = None
    output_format: str | None = None
    yt_dlp_extras: str | None = None
    video_codec: str = "auto"
    audio_codec: str = "auto"
    video_bitrate: str = "10m"
    audio_bitrate: str = "unset"
    video_quality_scale: str = "unset"
    scale: float = 1.0
    extras: str | None = None
    no_seek: bool = False
    cut_out: list[list[str]] = field(default_factory=list)
    add_in: list[list[str]] = field(default_factory=list)
    mark_as_loud: list[list[str]] = field(default_factory=list)
    mark_as_silent: list[list[str]] = field(default_factory=list)
    set_speed_for_range: list[tuple[float, str, str]] = field(default_factory=list)
    frame_rate: Fraction | None = None
    sample_rate: int | None = None
    resolution: tuple[int, int] | None = None
    background: str = "#000"
    edit_based_on: str = "audio"
    keep_tracks_separate: bool = False
    export: str | None = None
    player: str | None = None
    no_open: bool = False
    temp_dir: str | None = None
    ffmpeg_location: str | None = None
    my_ffmpeg: bool = False
    progress: str = "modern"
    version: bool = False
    debug: bool = False
    show_ffmpeg_debug: bool = False
    quiet: bool = False
    preview: bool = False
    margin: Margin = ("0.2", "0.2")
    silent_speed: float = 99999.0
    video_speed: float = 1.0
    output_file: str | None = None
    help: bool = False
    input: list[str] = field(default_factory=list)


colormap = {
    # Taken from https://www.w3.org/TR/css-color-4/#named-color
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgrey": "#a9a9a9",
    "darkgreen": "#006400",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "grey": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgreen": "#90ee90",
    "lightgray": "#d3d3d3",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "rebeccapurple": "#663399",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}
