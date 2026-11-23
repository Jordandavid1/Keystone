"""
KEYSTONE Deterministic Grade Lane (Bible v2 §23.2).

Pure Pillow/NumPy deterministic image/frame grading with strictly clamped
parameter bounds and deterministic PNG output hashes. Includes a pure-Python
PNG fallback when Pillow or NumPy is absent from the runtime environment so
the grade lane remains deterministic and self-contained across minimal venvs.
"""

from __future__ import annotations

import hashlib
import io
import math
import struct
import zlib
from typing import Dict, Optional, Tuple

try:
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore

    _HAS_PIL_NUMPY = True
except ImportError:  # pragma: no cover - exercised in minimal venvs
    np = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]
    _HAS_PIL_NUMPY = False

EXPOSURE_BOUNDS: Tuple[float, float] = (-2.0, 2.0)
CONTRAST_BOUNDS: Tuple[float, float] = (0.0, 2.0)
SATURATION_BOUNDS: Tuple[float, float] = (0.0, 2.0)
WARMTH_BOUNDS: Tuple[float, float] = (-1.0, 1.0)

GRADE_BOUNDS: Dict[str, Tuple[float, float]] = {
    "exposure": EXPOSURE_BOUNDS,
    "contrast": CONTRAST_BOUNDS,
    "saturation": SATURATION_BOUNDS,
    "warmth": WARMTH_BOUNDS,
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _clamp_float(value: float, bounds: Tuple[float, float], name: str) -> float:
    val = float(value)
    if math.isnan(val):
        raise ValueError(f"INVALID_GRADE_PARAMETER: {name} cannot be NaN")
    lo, hi = bounds
    if val < lo:
        return lo
    if val > hi:
        return hi
    # Normalize -0.0 to 0.0 so hashes never diverge on signed zero
    return 0.0 if val == 0.0 else val


def clamp_grade_params(
    exposure: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    warmth: float = 0.0,
) -> Tuple[float, float, float, float]:
    """Clamp grade controls to strict canonical bounds."""
    return (
        _clamp_float(exposure, EXPOSURE_BOUNDS, "exposure"),
        _clamp_float(contrast, CONTRAST_BOUNDS, "contrast"),
        _clamp_float(saturation, SATURATION_BOUNDS, "saturation"),
        _clamp_float(warmth, WARMTH_BOUNDS, "warmth"),
    )


def is_neutral_grade(
    exposure: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    warmth: float = 0.0,
) -> bool:
    """Return True when clamped grade parameters represent an identity transform."""
    exp, con, sat, warm = clamp_grade_params(exposure, contrast, saturation, warmth)
    return (
        abs(exp) < 1e-9
        and abs(con - 1.0) < 1e-9
        and abs(sat - 1.0) < 1e-9
        and abs(warm) < 1e-9
    )


def grade_digest(image_bytes: bytes) -> str:
    """Return the deterministic SHA-256 hex digest of graded image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def _grade_rgb_pixel(
    r: float,
    g: float,
    b: float,
    exp_scale: float,
    contrast: float,
    saturation: float,
    warmth: float,
) -> Tuple[int, int, int]:
    """Apply deterministic exposure, contrast, saturation, and warmth to one RGB pixel."""
    # 1. Exposure (EV stops)
    if exp_scale != 1.0:
        r *= exp_scale
        g *= exp_scale
        b *= exp_scale

    # 2. Contrast around mid-gray pivot 127.5
    if contrast != 1.0:
        r = 127.5 + (r - 127.5) * contrast
        g = 127.5 + (g - 127.5) * contrast
        b = 127.5 + (b - 127.5) * contrast

    # 3. Saturation using ITU-R BT.601 luma
    if saturation != 1.0:
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        r = luma + (r - luma) * saturation
        g = luma + (g - luma) * saturation
        b = luma + (b - luma) * saturation

    # 4. Warmth (red/amber boost vs blue attenuation)
    if warmth != 0.0:
        r = r * (1.0 + 0.15 * warmth) + 18.0 * warmth
        g = g + 4.0 * warmth
        b = b * (1.0 - 0.15 * warmth) - 18.0 * warmth

    return (
        max(0, min(255, int(round(r)))),
        max(0, min(255, int(round(g)))),
        max(0, min(255, int(round(b)))),
    )


def _apply_grade_pil_numpy(
    image_bytes: bytes,
    exp: float,
    con: float,
    sat: float,
    warm: float,
) -> bytes:
    """Vectorized Pillow + NumPy grading path with deterministic PNG encoding."""
    with Image.open(io.BytesIO(image_bytes)) as src:
        has_alpha = "A" in src.getbands() or ("transparency" in src.info and src.mode in ("P", "LA", "L", "RGB"))
        target_mode = "RGBA" if has_alpha else "RGB"
        converted = src.convert(target_mode)
        arr = np.asarray(converted, dtype=np.float32)

    rgb = arr[..., :3].copy()
    exp_scale = np.float32(2.0 ** exp)
    if exp != 0.0:
        rgb *= exp_scale

    if con != 1.0:
        rgb = np.float32(127.5) + (rgb - np.float32(127.5)) * np.float32(con)

    if sat != 1.0:
        luma = (
            np.float32(0.299) * rgb[..., 0:1]
            + np.float32(0.587) * rgb[..., 1:2]
            + np.float32(0.114) * rgb[..., 2:3]
        )
        rgb = luma + (rgb - luma) * np.float32(sat)

    if warm != 0.0:
        w = np.float32(warm)
        rgb[..., 0] = rgb[..., 0] * np.float32(1.0 + 0.15 * warm) + np.float32(18.0) * w
        rgb[..., 1] = rgb[..., 1] + np.float32(4.0) * w
        rgb[..., 2] = rgb[..., 2] * np.float32(1.0 - 0.15 * warm) - np.float32(18.0) * w

    graded_rgb = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    if target_mode == "RGBA":
        alpha = np.clip(np.rint(arr[..., 3:4]), 0, 255).astype(np.uint8)
        out_arr = np.concatenate([graded_rgb, alpha], axis=-1)
    else:
        out_arr = graded_rgb

    out_img = Image.fromarray(out_arr, mode=target_mode)
    buf = io.BytesIO()
    out_img.save(buf, format="PNG", compress_level=6, optimize=False)
    return buf.getvalue()


def _paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _decode_png(data: bytes) -> Tuple[int, int, bool, bytearray]:
    """Decode standard PNG (color types 0, 2, 3, 4, 6; bit depth 8 or 16) to RGB/RGBA pixels."""
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("UNSUPPORTED_IMAGE_FORMAT: Pillow is unavailable and input is not PNG")

    pos = 8
    width: Optional[int] = None
    height: Optional[int] = None
    bit_depth: Optional[int] = None
    color_type: Optional[int] = None
    interlace = 0
    palette: bytes = b""
    trns: bytes = b""
    idat = bytearray()

    while pos + 8 <= len(data):
        length, chunk_type = struct.unpack(">I4s", data[pos : pos + 8])
        pos += 8
        if pos + length + 4 > len(data):
            raise ValueError("CORRUPT_PNG: truncated chunk")
        chunk_data = data[pos : pos + length]
        pos += length + 4
        if chunk_type == b"IHDR":
            if length < 13:
                raise ValueError("CORRUPT_PNG: invalid IHDR length")
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", chunk_data[:13]
            )
        elif chunk_type == b"PLTE":
            palette = chunk_data
        elif chunk_type == b"tRNS":
            trns = chunk_data
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("CORRUPT_PNG: missing or invalid IHDR")
    if interlace != 0:
        raise ValueError("UNSUPPORTED_PNG: interlaced PNG decoding requires Pillow")
    if bit_depth not in (8, 16):
        raise ValueError(f"UNSUPPORTED_PNG: bit_depth={bit_depth} requires Pillow")

    channels_map = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_map:
        raise ValueError(f"UNSUPPORTED_PNG: unsupported color_type={color_type}")

    channels = channels_map[color_type]
    sample_bytes = bit_depth // 8
    bpp = channels * sample_bytes
    stride = width * bpp

    raw = zlib.decompress(bytes(idat))
    expected_len = height * (1 + stride)
    if len(raw) < expected_len:
        raise ValueError("CORRUPT_PNG: truncated decompressed image data")

    prev_row = bytearray(stride)
    curr_row = bytearray(stride)
    has_alpha = color_type in (4, 6) or (color_type == 3 and bool(trns))
    out_channels = 4 if has_alpha else 3
    pixels = bytearray(width * height * out_channels)

    src_pos = 0
    for y in range(height):
        ftype = raw[src_pos]
        src_pos += 1
        scanline = raw[src_pos : src_pos + stride]
        src_pos += stride
        for i in range(stride):
            x = scanline[i]
            a = curr_row[i - bpp] if i >= bpp else 0
            b = prev_row[i]
            c = prev_row[i - bpp] if i >= bpp else 0
            if ftype == 0:
                val = x
            elif ftype == 1:
                val = (x + a) & 0xFF
            elif ftype == 2:
                val = (x + b) & 0xFF
            elif ftype == 3:
                val = (x + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                val = (x + _paeth_predictor(a, b, c)) & 0xFF
            else:
                raise ValueError(f"CORRUPT_PNG: invalid scanline filter {ftype}")
            curr_row[i] = val
        prev_row[:] = curr_row

        row_out = y * width * out_channels
        for px_idx in range(width):
            in_off = px_idx * bpp
            out_off = row_out + px_idx * out_channels
            if color_type == 6:
                pixels[out_off] = curr_row[in_off]
                pixels[out_off + 1] = curr_row[in_off + sample_bytes]
                pixels[out_off + 2] = curr_row[in_off + 2 * sample_bytes]
                pixels[out_off + 3] = curr_row[in_off + 3 * sample_bytes]
            elif color_type == 2:
                pixels[out_off] = curr_row[in_off]
                pixels[out_off + 1] = curr_row[in_off + sample_bytes]
                pixels[out_off + 2] = curr_row[in_off + 2 * sample_bytes]
            elif color_type == 0:
                lum = curr_row[in_off]
                pixels[out_off] = lum
                pixels[out_off + 1] = lum
                pixels[out_off + 2] = lum
            elif color_type == 4:
                lum = curr_row[in_off]
                pixels[out_off] = lum
                pixels[out_off + 1] = lum
                pixels[out_off + 2] = lum
                pixels[out_off + 3] = curr_row[in_off + sample_bytes]
            elif color_type == 3:
                idx = curr_row[in_off]
                pal_off = idx * 3
                if pal_off + 3 > len(palette):
                    raise ValueError("CORRUPT_PNG: palette index out of range")
                pixels[out_off] = palette[pal_off]
                pixels[out_off + 1] = palette[pal_off + 1]
                pixels[out_off + 2] = palette[pal_off + 2]
                if has_alpha:
                    pixels[out_off + 3] = trns[idx] if idx < len(trns) else 255

    return width, height, has_alpha, pixels


def _encode_png(width: int, height: int, has_alpha: bool, pixels: bytearray) -> bytes:
    """Deterministically encode RGB or RGBA pixel buffer to PNG bytes."""
    color_type = 6 if has_alpha else 2
    channels = 4 if has_alpha else 3
    row_bytes = width * channels
    raw = bytearray(height * (1 + row_bytes))
    for y in range(height):
        src_start = y * row_bytes
        dst_start = y * (1 + row_bytes)
        raw[dst_start] = 0  # Filter type 0 (None)
        raw[dst_start + 1 : dst_start + 1 + row_bytes] = pixels[src_start : src_start + row_bytes]

    def _chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 6)
    return _PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _apply_grade_pure_python(
    image_bytes: bytes,
    exp: float,
    con: float,
    sat: float,
    warm: float,
) -> bytes:
    """Pure-Python deterministic PNG grading fallback when Pillow/NumPy are absent."""
    width, height, has_alpha, pixels = _decode_png(image_bytes)
    channels = 4 if has_alpha else 3
    exp_scale = 2.0 ** exp
    out = bytearray(len(pixels))

    for i in range(0, len(pixels), channels):
        r, g, b = _grade_rgb_pixel(
            float(pixels[i]),
            float(pixels[i + 1]),
            float(pixels[i + 2]),
            exp_scale,
            con,
            sat,
            warm,
        )
        out[i] = r
        out[i + 1] = g
        out[i + 2] = b
        if has_alpha:
            out[i + 3] = pixels[i + 3]

    return _encode_png(width, height, has_alpha, out)


def apply_grade(
    image_bytes: bytes,
    exposure: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    warmth: float = 0.0,
) -> bytes:
    """
    Apply deterministic color grading (exposure, contrast, saturation, warmth)
    to an image or video frame.

    Parameters are strictly clamped to canonical bounds:
      - exposure:   [-2.0, 2.0] (neutral: 0.0)
      - contrast:   [0.0, 2.0]  (neutral: 1.0)
      - saturation: [0.0, 2.0]  (neutral: 1.0)
      - warmth:     [-1.0, 1.0] (neutral: 0.0)

    Identical inputs always produce bit-identical output bytes and SHA-256 hash.
    Neutral parameters return the input bytes unmodified after basic validation.
    """
    if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) == 0:
        raise ValueError("EMPTY_IMAGE_BYTES: image_bytes must be non-empty")

    raw_bytes = bytes(image_bytes)
    exp, con, sat, warm = clamp_grade_params(exposure, contrast, saturation, warmth)

    if is_neutral_grade(exp, con, sat, warm):
        return raw_bytes

    if _HAS_PIL_NUMPY:
        return _apply_grade_pil_numpy(raw_bytes, exp, con, sat, warm)
    return _apply_grade_pure_python(raw_bytes, exp, con, sat, warm)
