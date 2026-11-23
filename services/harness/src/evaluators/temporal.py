"""
Tier-B Temporal Consistency & Extend-Boundary Evaluator (KHF — Bible v2 §13.2, specs/SPEC_EVALUATORS.md).

Samples `KEYSTONE_EVAL_VIDEO_SAMPLE_FRAMES` (default 8) frames via `ffmpeg`, computes:
  1. Adjacent-frame windowed Structural Similarity Index (SSIM)
  2. Luminance & block-level sign-reversal flicker score
  3. Block-matching optical-flow displacement coherence and residual drift
  4. Stitch discontinuity / drift across `extend` video segment boundaries
"""

from __future__ import annotations

import io
import math
import os
import struct
import subprocess
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from packages.contracts.src.models import HarnessResult
from services.comfy.src.video_ops import (
    VideoOpsError,
    _resolve_ffmpeg,
    extract_last_frame,
    probe_video_metadata,
)

HARNESS_ID = "khf.temporal_consistency"
HARNESS_VERSION = "1.0.0"

DEFAULT_VIDEO_SAMPLE_FRAMES = 8
DEFAULT_TEMPORAL_THRESHOLD = 0.65
DEFAULT_SSIM_THRESHOLD = 0.50
DEFAULT_FLICKER_THRESHOLD = 0.35
DEFAULT_FLOW_DRIFT_THRESHOLD = 0.45
DEFAULT_BOUNDARY_DRIFT_THRESHOLD = 0.45

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ANALYSIS_GRID_SIZE = 48
_SSIM_WINDOW = 8
_FLOW_BLOCK = 8
_FLOW_SEARCH_RADIUS = 4


def get_video_sample_frames(override: Optional[int] = None) -> int:
    """Resolve the number of video frames to sample (default 8 via KEYSTONE_EVAL_VIDEO_SAMPLE_FRAMES)."""
    if override is not None:
        return max(2, int(override))
    raw = os.getenv("KEYSTONE_EVAL_VIDEO_SAMPLE_FRAMES", str(DEFAULT_VIDEO_SAMPLE_FRAMES)).strip()
    try:
        val = int(raw)
    except ValueError:
        val = DEFAULT_VIDEO_SAMPLE_FRAMES
    return max(2, val)


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


def _decode_png_rgb(data: bytes) -> Tuple[int, int, bytearray]:
    """Pure-Python PNG decoder returning (width, height, rgb_bytes)."""
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("NOT_A_PNG")

    pos = 8
    width: Optional[int] = None
    height: Optional[int] = None
    bit_depth: Optional[int] = None
    color_type: Optional[int] = None
    interlace = 0
    palette: bytes = b""
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
                raise ValueError("CORRUPT_PNG: invalid IHDR")
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", chunk_data[:13]
            )
        elif chunk_type == b"PLTE":
            palette = chunk_data
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("CORRUPT_PNG: missing IHDR")
    if interlace != 0 or bit_depth not in (8, 16):
        raise ValueError("UNSUPPORTED_PNG_LAYOUT")

    channels_map = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_map:
        raise ValueError(f"UNSUPPORTED_PNG_COLOR_TYPE: {color_type}")

    channels = channels_map[color_type]
    sample_bytes = bit_depth // 8
    bpp = channels * sample_bytes
    stride = width * bpp

    raw = zlib.decompress(bytes(idat))
    expected_len = height * (1 + stride)
    if len(raw) < expected_len:
        raise ValueError("CORRUPT_PNG: truncated IDAT stream")

    prev_row = bytearray(stride)
    curr_row = bytearray(stride)
    rgb = bytearray(width * height * 3)

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
                raise ValueError(f"CORRUPT_PNG: invalid filter {ftype}")
            curr_row[i] = val
        prev_row[:] = curr_row

        row_out = y * width * 3
        for px in range(width):
            in_off = px * bpp
            out_off = row_out + px * 3
            if color_type in (2, 6):
                rgb[out_off] = curr_row[in_off]
                rgb[out_off + 1] = curr_row[in_off + sample_bytes]
                rgb[out_off + 2] = curr_row[in_off + 2 * sample_bytes]
            elif color_type in (0, 4):
                lum = curr_row[in_off]
                rgb[out_off] = lum
                rgb[out_off + 1] = lum
                rgb[out_off + 2] = lum
            elif color_type == 3:
                idx = curr_row[in_off]
                pal_off = idx * 3
                if pal_off + 3 > len(palette):
                    raise ValueError("CORRUPT_PNG: palette index out of bounds")
                rgb[out_off] = palette[pal_off]
                rgb[out_off + 1] = palette[pal_off + 1]
                rgb[out_off + 2] = palette[pal_off + 2]

    return width, height, rgb


def _decode_via_ffmpeg_rgb(data: bytes, target_size: int = _ANALYSIS_GRID_SIZE) -> Tuple[int, int, bytearray]:
    """Decode any image/frame bytes to raw RGB24 via ffmpeg."""
    ffmpeg_bin = _resolve_ffmpeg()
    with tempfile.TemporaryDirectory(prefix="ks_frame_dec_") as tmpdir:
        in_path = Path(tmpdir) / "input.bin"
        in_path.write_bytes(data)
        cmd = [
            ffmpeg_bin,
            "-v",
            "error",
            "-i",
            str(in_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={target_size}:{target_size}:flags=bilinear",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
        expected = target_size * target_size * 3
        if proc.returncode != 0 or len(proc.stdout) < expected:
            raise ValueError(
                f"FRAME_DECODE_FAILED: {(proc.stderr or b'').decode('utf-8', errors='ignore').strip()[:240]}"
            )
        return target_size, target_size, bytearray(proc.stdout[:expected])


def _decode_frame_rgb(frame_input: Union[bytes, bytearray, str, Path, Tuple[int, int, bytes]]) -> Tuple[int, int, bytearray]:
    """Decode a frame from PNG/JPEG bytes, file path, or pre-decoded (w, h, rgb) tuple."""
    if isinstance(frame_input, tuple) and len(frame_input) == 3:
        w, h, buf = frame_input
        return int(w), int(h), bytearray(buf)

    if isinstance(frame_input, (str, Path)):
        raw_bytes = Path(frame_input).read_bytes()
    elif isinstance(frame_input, (bytes, bytearray)):
        raw_bytes = bytes(frame_input)
    else:
        raise TypeError(f"Unsupported frame input type: {type(frame_input).__name__}")

    if not raw_bytes:
        raise ValueError("EMPTY_FRAME_BYTES")

    if raw_bytes.startswith(_PNG_SIGNATURE):
        try:
            return _decode_png_rgb(raw_bytes)
        except Exception:
            pass

    try:
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            return w, h, bytearray(rgb_img.tobytes())
    except Exception:
        pass

    return _decode_via_ffmpeg_rgb(raw_bytes, target_size=_ANALYSIS_GRID_SIZE)


def _resample_rgb_and_luma(
    width: int,
    height: int,
    rgb: Union[bytes, bytearray],
    grid_size: int = _ANALYSIS_GRID_SIZE,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Resample an RGB buffer of shape (height, width, 3) onto a (grid_size x grid_size)
    canonical analysis grid, returning flattened lists (luma, r_plane, g_plane, b_plane).
    """
    n = grid_size * grid_size
    luma = [0.0] * n
    r_plane = [0.0] * n
    g_plane = [0.0] * n
    b_plane = [0.0] * n

    for gy in range(grid_size):
        sy = min(height - 1, int((gy + 0.5) * height / grid_size))
        row_off = sy * width * 3
        out_row = gy * grid_size
        for gx in range(grid_size):
            sx = min(width - 1, int((gx + 0.5) * width / grid_size))
            px_off = row_off + sx * 3
            r = float(rgb[px_off])
            g = float(rgb[px_off + 1])
            b = float(rgb[px_off + 2])
            idx = out_row + gx
            r_plane[idx] = r
            g_plane[idx] = g
            b_plane[idx] = b
            luma[idx] = 0.299 * r + 0.587 * g + 0.114 * b

    return luma, r_plane, g_plane, b_plane


def sample_video_frames(
    video_source: Union[bytes, bytearray, str, Path],
    num_frames: Optional[int] = None,
) -> List[bytes]:
    """
    Sample up to `num_frames` (default `KEYSTONE_EVAL_VIDEO_SAMPLE_FRAMES` = 8) evenly
    spaced PNG frames from a video file or video bytes using `ffmpeg`.
    """
    target_count = get_video_sample_frames(num_frames)
    ffmpeg_bin = _resolve_ffmpeg()

    temp_video_file: Optional[Path] = None
    try:
        if isinstance(video_source, (str, Path)):
            video_path = Path(video_source)
            if not video_path.exists() or not video_path.is_file():
                raise FileNotFoundError(f"VIDEO_NOT_FOUND: {video_path}")
            if video_path.stat().st_size == 0:
                raise VideoOpsError(f"EMPTY_VIDEO_FILE: {video_path}")
        elif isinstance(video_source, (bytes, bytearray)):
            if len(video_source) == 0:
                raise VideoOpsError("EMPTY_VIDEO_BYTES")
            fd, tmp_name = tempfile.mkstemp(prefix="ks_temporal_", suffix=".mp4")
            os.close(fd)
            temp_video_file = Path(tmp_name)
            temp_video_file.write_bytes(bytes(video_source))
            video_path = temp_video_file
        else:
            raise TypeError(f"Unsupported video_source type: {type(video_source).__name__}")

        meta = probe_video_metadata(video_path)
        duration = float(meta.get("duration") or 0.0)

        with tempfile.TemporaryDirectory(prefix="ks_eval_frames_") as tmpdir:
            tmp_root = Path(tmpdir)
            pattern = tmp_root / "frame_%06d.png"

            extracted_files: List[Path] = []
            # For longer clips (> 2.5s), use an fps filter so ffmpeg decodes only ~target_count frames.
            if duration > 2.5:
                sample_fps = max(1.0, float(target_count) / duration)
                fps_cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(video_path),
                    "-vf",
                    f"fps={sample_fps:.4f}",
                    "-frames:v",
                    str(target_count * 2),
                    str(pattern),
                ]
                proc = subprocess.run(fps_cmd, capture_output=True, text=True, timeout=120)
                if proc.returncode == 0:
                    extracted_files = sorted(tmp_root.glob("frame_*.png"))

            # Fallback / short-clip path: extract decoded frames directly up to a safe cap
            if len(extracted_files) < 2:
                for f in extracted_files:
                    try:
                        f.unlink()
                    except OSError:
                        pass
                max_extract = max(target_count * 6, 48)
                direct_cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    str(max_extract),
                    str(pattern),
                ]
                proc2 = subprocess.run(direct_cmd, capture_output=True, text=True, timeout=120)
                if proc2.returncode != 0:
                    raise VideoOpsError(
                        f"FFMPEG_SAMPLE_FRAMES_FAILED: {(proc2.stderr or '').strip()[:400]}"
                    )
                extracted_files = sorted(tmp_root.glob("frame_*.png"))

            if not extracted_files:
                raise VideoOpsError(f"FFMPEG_NO_FRAMES_EXTRACTED: {video_path}")

            total = len(extracted_files)
            if total <= target_count:
                selected_files = extracted_files
            else:
                indices: List[int] = []
                for i in range(target_count):
                    idx = int(round(i * (total - 1) / float(target_count - 1)))
                    if not indices or idx != indices[-1]:
                        indices.append(idx)
                selected_files = [extracted_files[idx] for idx in indices]

            return [f.read_bytes() for f in selected_files]
    finally:
        if temp_video_file is not None and temp_video_file.exists():
            try:
                temp_video_file.unlink()
            except OSError:
                pass


def _plane_window_ssim(
    plane_a: List[float],
    plane_b: List[float],
    grid_size: int = _ANALYSIS_GRID_SIZE,
    window_size: int = _SSIM_WINDOW,
) -> float:
    """Compute mean windowed SSIM in [0.0, 1.0] across non-overlapping blocks on a 2D plane."""
    c1 = (0.01 * 255.0) ** 2  # 6.5025
    c2 = (0.03 * 255.0) ** 2  # 58.5225

    ssim_sum = 0.0
    block_count = 0

    for by in range(0, grid_size, window_size):
        bh = min(window_size, grid_size - by)
        for bx in range(0, grid_size, window_size):
            bw = min(window_size, grid_size - bx)
            count = float(bh * bw)
            if count <= 1.0:
                continue

            sum_a = 0.0
            sum_b = 0.0
            for y in range(by, by + bh):
                row = y * grid_size
                for x in range(bx, bx + bw):
                    idx = row + x
                    sum_a += plane_a[idx]
                    sum_b += plane_b[idx]

            mu_a = sum_a / count
            mu_b = sum_b / count

            var_a = 0.0
            var_b = 0.0
            cov_ab = 0.0
            for y in range(by, by + bh):
                row = y * grid_size
                for x in range(bx, bx + bw):
                    idx = row + x
                    da = plane_a[idx] - mu_a
                    db = plane_b[idx] - mu_b
                    var_a += da * da
                    var_b += db * db
                    cov_ab += da * db

            var_a /= count
            var_b /= count
            cov_ab /= count

            numerator = (2.0 * mu_a * mu_b + c1) * (2.0 * cov_ab + c2)
            denominator = (mu_a * mu_a + mu_b * mu_b + c1) * (var_a + var_b + c2)
            block_ssim = numerator / denominator if denominator > 0.0 else 1.0
            ssim_sum += max(0.0, min(1.0, block_ssim))
            block_count += 1

    if block_count == 0:
        return 0.0
    return max(0.0, min(1.0, ssim_sum / float(block_count)))


def compute_frame_ssim(
    frame_a: Union[bytes, bytearray, str, Path, Tuple[int, int, bytes]],
    frame_b: Union[bytes, bytearray, str, Path, Tuple[int, int, bytes]],
) -> float:
    """
    Compute windowed Structural Similarity Index (SSIM) in [0.0, 1.0] between two frames.
    """
    wa, ha, rgba = _decode_frame_rgb(frame_a)
    wb, hb, rgbb = _decode_frame_rgb(frame_b)
    luma_a, _, _, _ = _resample_rgb_and_luma(wa, ha, rgba, _ANALYSIS_GRID_SIZE)
    luma_b, _, _, _ = _resample_rgb_and_luma(wb, hb, rgbb, _ANALYSIS_GRID_SIZE)
    return round(_plane_window_ssim(luma_a, luma_b, _ANALYSIS_GRID_SIZE, _SSIM_WINDOW), 6)


def compute_luminance_flicker(
    frames: Sequence[Union[bytes, bytearray, str, Path, Tuple[int, int, bytes]]],
) -> Dict[str, Any]:
    """
    Compute per-frame luminance series, adjacent deltas, and sign-reversal
    flicker oscillation score across global and block-level luminance trajectories.
    """
    if not frames:
        return {
            "luminance_series": [],
            "adjacent_luma_deltas": [],
            "mean_luma_delta": 0.0,
            "max_luma_delta": 0.0,
            "flicker_score": 1.0,
            "flicker_stability": 0.0,
        }

    grid = _ANALYSIS_GRID_SIZE
    block = _SSIM_WINDOW
    luma_planes: List[List[float]] = []
    mean_lumas: List[float] = []
    block_luma_series: List[List[float]] = []

    for frame in frames:
        w, h, rgb = _decode_frame_rgb(frame)
        luma, _, _, _ = _resample_rgb_and_luma(w, h, rgb, grid)
        luma_planes.append(luma)
        mean_lumas.append(sum(luma) / float(len(luma)))

        blocks: List[float] = []
        for by in range(0, grid, block):
            bh = min(block, grid - by)
            for bx in range(0, grid, block):
                bw = min(block, grid - bx)
                s = 0.0
                for y in range(by, by + bh):
                    row = y * grid
                    for x in range(bx, bx + bw):
                        s += luma[row + x]
                blocks.append(s / float(bh * bw))
        block_luma_series.append(blocks)

    if len(luma_planes) == 1:
        return {
            "luminance_series": [round( mean_lumas[0], 3)],
            "adjacent_luma_deltas": [],
            "mean_luma_delta": 0.0,
            "max_luma_delta": 0.0,
            "flicker_score": 0.0,
            "flicker_stability": 1.0,
        }

    adjacent_deltas: List[float] = []
    for i in range(len(mean_lumas) - 1):
        adjacent_deltas.append(abs(mean_lumas[i + 1] - mean_lumas[i]) / 255.0)

    # Triplet sign-reversal oscillation (captures alternating strobe/flicker both globally and per block)
    triplet_scores: List[float] = []
    num_blocks = len(block_luma_series[0])
    for t in range(1, len(luma_planes) - 1):
        d1_global = (mean_lumas[t] - mean_lumas[t - 1]) / 255.0
        d2_global = (mean_lumas[t + 1] - mean_lumas[t]) / 255.0
        global_osc = abs(d1_global * d2_global) if (d1_global * d2_global < 0.0) else 0.0

        block_osc_sum = 0.0
        for b_idx in range(num_blocks):
            b1 = (block_luma_series[t][b_idx] - block_luma_series[t - 1][b_idx]) / 255.0
            b2 = (block_luma_series[t + 1][b_idx] - block_luma_series[t][b_idx]) / 255.0
            if b1 * b2 < 0.0:
                block_osc_sum += abs(b1 * b2)
        block_osc = block_osc_sum / float(max(1, num_blocks))
        triplet_scores.append(max(global_osc, block_osc))

    mean_delta = sum(adjacent_deltas) / float(len(adjacent_deltas))
    max_delta = max(adjacent_deltas)
    mean_triplet_osc = (
        sum(triplet_scores) / float(len(triplet_scores))
        if triplet_scores
        else (max_delta * max_delta)
    )

    # Combine oscillation energy with extreme single-step luminance spike penalty
    extreme_spike = max(0.0, (max_delta - 0.55) / 0.45)
    flicker_score = max(0.0, min(1.0, max(mean_triplet_osc, 0.75 * mean_triplet_osc + 0.25 * extreme_spike)))

    return {
        "luminance_series": [round(v, 3) for v in mean_lumas],
        "adjacent_luma_deltas": [round(d, 6) for d in adjacent_deltas],
        "mean_luma_delta": round(mean_delta, 6),
        "max_luma_delta": round(max_delta, 6),
        "flicker_score": round(flicker_score, 6),
        "flicker_stability": round(1.0 - flicker_score, 6),
    }


def compute_optical_flow_drift(
    frame_a: Union[bytes, bytearray, str, Path, Tuple[int, int, bytes]],
    frame_b: Union[bytes, bytearray, str, Path, Tuple[int, int, bytes]],
    *,
    block_size: int = _FLOW_BLOCK,
    search_radius: int = _FLOW_SEARCH_RADIUS,
) -> Dict[str, float]:
    """
    Estimate block-matching optical flow between two frames on the canonical luminance grid,
    returning mean motion magnitude, spatial vector incoherence, motion-compensated residual
    error, and composite optical_flow_drift in [0.0, 1.0].
    """
    wa, ha, rgba = _decode_frame_rgb(frame_a)
    wb, hb, rgbb = _decode_frame_rgb(frame_b)
    grid = _ANALYSIS_GRID_SIZE
    luma_a, _, _, _ = _resample_rgb_and_luma(wa, ha, rgba, grid)
    luma_b, _, _, _ = _resample_rgb_and_luma(wb, hb, rgbb, grid)

    vectors: List[Tuple[float, float]] = []
    residuals: List[float] = []
    max_disp = math.sqrt(2.0 * float(search_radius * search_radius)) or 1.0

    for by in range(0, grid, block_size):
        bh = min(block_size, grid - by)
        for bx in range(0, grid, block_size):
            bw = min(block_size, grid - bx)
            best_dx = 0
            best_dy = 0
            best_sad = float("inf")

            # Prefer (0, 0) on ties by evaluating (0, 0) first
            candidates = [(0, 0)] + [
                (dy, dx)
                for dy in range(-search_radius, search_radius + 1)
                for dx in range(-search_radius, search_radius + 1)
                if not (dy == 0 and dx == 0)
            ]

            for dy, dx in candidates:
                ty = by + dy
                tx = bx + dx
                if ty < 0 or tx < 0 or ty + bh > grid or tx + bw > grid:
                    continue
                sad = 0.0
                for y in range(bh):
                    row_a = (by + y) * grid + bx
                    row_b = (ty + y) * grid + tx
                    for x in range(bw):
                        sad += abs(luma_a[row_a + x] - luma_b[row_b + x])
                # Slight regularization penalty for non-zero displacement to prevent aperture noise on flat regions
                reg_sad = sad + 0.25 * float(abs(dx) + abs(dy)) * float(bh * bw)
                if reg_sad < best_sad:
                    best_sad = reg_sad
                    best_dx = dx
                    best_dy = dy

            vectors.append((float(best_dx), float(best_dy)))
            residuals.append((best_sad / float(bh * bw)) / 255.0)

    if not vectors:
        return {
            "mean_flow_magnitude": 0.0,
            "flow_incoherence": 0.0,
            "residual_error": 0.0,
            "optical_flow_drift": 0.0,
            "optical_flow_consistency": 1.0,
        }

    n_vec = float(len(vectors))
    mean_dx = sum(v[0] for v in vectors) / n_vec
    mean_dy = sum(v[1] for v in vectors) / n_vec

    magnitudes = [math.sqrt(v[0] * v[0] + v[1] * v[1]) / max_disp for v in vectors]
    mean_mag = sum(magnitudes) / n_vec

    var_vec = sum((v[0] - mean_dx) ** 2 + (v[1] - mean_dy) ** 2 for v in vectors) / n_vec
    incoherence = min(1.0, math.sqrt(var_vec) / max_disp)
    mean_residual = min(1.0, sum(residuals) / n_vec)

    # High residual after best motion match or chaotic non-coherent block displacements indicate temporal drift
    drift = max(0.0, min(1.0, 0.55 * incoherence + 0.45 * max(0.0, (mean_residual - 0.15) / 0.85)))

    return {
        "mean_flow_magnitude": round(mean_mag, 6),
        "flow_incoherence": round(incoherence, 6),
        "residual_error": round(mean_residual, 6),
        "optical_flow_drift": round(drift, 6),
        "optical_flow_consistency": round(1.0 - drift, 6),
    }


def _extract_boundary_frame(
    segment: Union[bytes, bytearray, str, Path, Sequence[bytes]],
    *,
    take_last: bool,
) -> bytes:
    """Extract the first or last PNG frame from a video segment (path, bytes, or frame list)."""
    if isinstance(segment, (list, tuple)):
        if not segment:
            raise ValueError("EMPTY_SEGMENT_FRAME_SEQUENCE")
        item = segment[-1] if take_last else segment[0]
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, (str, Path)):
            return Path(item).read_bytes()
        raise TypeError(f"Unsupported segment frame item: {type(item).__name__}")

    if isinstance(segment, (bytes, bytearray)) and bytes(segment).startswith(_PNG_SIGNATURE):
        return bytes(segment)

    if take_last:
        if isinstance(segment, (str, Path)):
            p = Path(segment)
            if p.suffix.lower() == ".png":
                return p.read_bytes()
            return extract_last_frame(p)
        if isinstance(segment, (bytes, bytearray)):
            fd, tmp_name = tempfile.mkstemp(prefix="ks_seg_last_", suffix=".mp4")
            os.close(fd)
            tmp_path = Path(tmp_name)
            try:
                tmp_path.write_bytes(bytes(segment))
                return extract_last_frame(tmp_path)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

    sampled = sample_video_frames(segment, num_frames=2)
    return sampled[-1] if take_last else sampled[0]


def compute_extend_boundary_drift(
    segment_a: Union[bytes, bytearray, str, Path, Sequence[bytes]],
    segment_b: Union[bytes, bytearray, str, Path, Sequence[bytes]],
) -> Dict[str, Any]:
    """
    Compute temporal discontinuity / drift across the stitch boundary between
    the final frame of `segment_a` and the initial frame of `segment_b`.
    """
    last_frame_a = _extract_boundary_frame(segment_a, take_last=True)
    first_frame_b = _extract_boundary_frame(segment_b, take_last=False)

    boundary_ssim = compute_frame_ssim(last_frame_a, first_frame_b)
    flow_info = compute_optical_flow_drift(last_frame_a, first_frame_b)
    flicker_info = compute_luminance_flicker([last_frame_a, first_frame_b])
    luma_delta = float(flicker_info["max_luma_delta"])
    flow_drift = float(flow_info["optical_flow_drift"])

    ssim_deficit = max(0.0, 1.0 - boundary_ssim)
    boundary_drift = max(
        0.0,
        min(1.0, 0.50 * ssim_deficit + 0.30 * luma_delta + 0.20 * flow_drift),
    )

    return {
        "boundary_ssim": round(boundary_ssim, 6),
        "boundary_luma_delta": round(luma_delta, 6),
        "boundary_flow_drift": round(flow_drift, 6),
        "boundary_drift_score": round(boundary_drift, 6),
        "boundary_consistency": round(1.0 - boundary_drift, 6),
    }


def evaluate_temporal_consistency(
    video_data: Optional[Union[bytes, bytearray, str, Path, Sequence[bytes], Dict[str, Any]]] = None,
    *,
    video_bytes: Optional[bytes] = None,
    video_path: Optional[Union[str, Path]] = None,
    frames: Optional[Sequence[bytes]] = None,
    sample_frames: Optional[int] = None,
    segment_paths: Optional[Sequence[Union[str, Path]]] = None,
    segments: Optional[Sequence[Union[bytes, bytearray, str, Path, Sequence[bytes]]]] = None,
    previous_segment: Optional[Union[bytes, bytearray, str, Path, Sequence[bytes]]] = None,
    boundary_frame_indices: Optional[Sequence[int]] = None,
    is_extend: bool = False,
    threshold: float = DEFAULT_TEMPORAL_THRESHOLD,
    ssim_threshold: float = DEFAULT_SSIM_THRESHOLD,
    flicker_threshold: float = DEFAULT_FLICKER_THRESHOLD,
    flow_drift_threshold: float = DEFAULT_FLOW_DRIFT_THRESHOLD,
    boundary_drift_threshold: float = DEFAULT_BOUNDARY_DRIFT_THRESHOLD,
    phase: str = "post-execution",
    **kwargs: Any,
) -> HarnessResult:
    """
    Execute Tier-B temporal evaluation on a generated video (or sampled frame set),
    including adjacent-frame SSIM, luminance/block flicker score, optical-flow drift,
    and stitch continuity across `extend` segment boundaries.
    """
    start = time.perf_counter()
    target_sample_frames = get_video_sample_frames(sample_frames)

    # Unpack dict payloads if passed a structured dict
    if isinstance(video_data, dict):
        payload = video_data
        video_bytes = video_bytes or payload.get("video_bytes") or payload.get("asset_bytes") or payload.get("data")
        video_path = video_path or payload.get("video_path") or payload.get("path")
        frames = frames or payload.get("frames")
        segment_paths = segment_paths or payload.get("segment_paths")
        segments = segments or payload.get("segments")
        previous_segment = previous_segment or payload.get("previous_segment") or payload.get("parent_video")
        boundary_frame_indices = boundary_frame_indices or payload.get("boundary_frame_indices")
        if payload.get("is_extend") or str(payload.get("intent", "")).lower() == "extend":
            is_extend = True
        video_data = None

    if not is_extend and str(kwargs.get("intent", "")).lower() == "extend":
        is_extend = True

    if video_bytes is None and isinstance(kwargs.get("data"), (bytes, bytearray)):
        video_bytes = bytes(kwargs["data"])
    if video_bytes is None and isinstance(kwargs.get("asset_bytes"), (bytes, bytearray)):
        video_bytes = bytes(kwargs["asset_bytes"])
    if video_path is None and kwargs.get("path") is not None:
        video_path = kwargs["path"]

    # Resolve frames list
    sampled_frames: List[bytes] = []
    try:
        if frames is not None:
            sampled_frames = [
                bytes(f) if isinstance(f, (bytes, bytearray)) else Path(f).read_bytes()
                for f in frames
            ]
        elif isinstance(video_data, (list, tuple)):
            sampled_frames = [
                bytes(f) if isinstance(f, (bytes, bytearray)) else Path(f).read_bytes()
                for f in video_data
            ]
        elif video_bytes is not None:
            if isinstance(video_bytes, (bytes, bytearray)) and bytes(video_bytes).startswith(_PNG_SIGNATURE):
                sampled_frames = [bytes(video_bytes)]
            else:
                sampled_frames = sample_video_frames(video_bytes, num_frames=target_sample_frames)
        elif video_path is not None:
            sampled_frames = sample_video_frames(video_path, num_frames=target_sample_frames)
        elif isinstance(video_data, (bytes, bytearray, str, Path)):
            if isinstance(video_data, (bytes, bytearray)) and bytes(video_data).startswith(_PNG_SIGNATURE):
                sampled_frames = [bytes(video_data)]
            else:
                sampled_frames = sample_video_frames(video_data, num_frames=target_sample_frames)
        elif segments or segment_paths:
            all_segs = list(segments or segment_paths or [])
            per_seg = max(2, target_sample_frames // max(1, len(all_segs)))
            for seg in all_segs:
                if isinstance(seg, (list, tuple)):
                    sampled_frames.extend(
                        bytes(f) if isinstance(f, (bytes, bytearray)) else Path(f).read_bytes()
                        for f in seg
                    )
                else:
                    sampled_frames.extend(sample_video_frames(seg, num_frames=per_seg))
        else:
            return HarnessResult(
                harness_id=HARNESS_ID,
                harness_version=HARNESS_VERSION,
                phase=phase,  # type: ignore[arg-type]
                verdict="fail",
                score=0.0,
                reason_codes=["EMPTY_VIDEO_INPUT"],
                evidence={
                    "family": "temporal",
                    "sampled_frame_count": 0,
                    "requested_sample_frames": target_sample_frames,
                    "defects": ["EMPTY_VIDEO_INPUT"],
                },
                runtime_ms=round((time.perf_counter() - start) * 1000.0, 2),
            )
    except Exception as exc:
        code = f"TEMPORAL_FRAME_SAMPLE_FAILED: {type(exc).__name__}"
        return HarnessResult(
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            phase=phase,  # type: ignore[arg-type]
            verdict="fail",
            score=0.0,
            reason_codes=["TEMPORAL_FRAME_SAMPLE_FAILED"],
            evidence={
                "family": "temporal",
                "error": str(exc),
                "error_code": code,
                "sampled_frame_count": 0,
                "requested_sample_frames": target_sample_frames,
                "defects": ["TEMPORAL_FRAME_SAMPLE_FAILED"],
            },
            runtime_ms=round((time.perf_counter() - start) * 1000.0, 2),
        )

    if len(sampled_frames) < 2:
        return HarnessResult(
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            phase=phase,  # type: ignore[arg-type]
            verdict="fail",
            score=0.0,
            reason_codes=["INSUFFICIENT_VIDEO_FRAMES"],
            evidence={
                "family": "temporal",
                "sampled_frame_count": len(sampled_frames),
                "requested_sample_frames": target_sample_frames,
                "defects": ["INSUFFICIENT_VIDEO_FRAMES"],
            },
            runtime_ms=round((time.perf_counter() - start) * 1000.0, 2),
        )

    try:
        decoded_frames = [_decode_frame_rgb(f) for f in sampled_frames]
    except Exception as exc:
        return HarnessResult(
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            phase=phase,  # type: ignore[arg-type]
            verdict="fail",
            score=0.0,
            reason_codes=["CORRUPT_VIDEO_FRAME"],
            evidence={
                "family": "temporal",
                "error": str(exc),
                "sampled_frame_count": len(sampled_frames),
                "requested_sample_frames": target_sample_frames,
                "defects": ["CORRUPT_VIDEO_FRAME"],
            },
            runtime_ms=round((time.perf_counter() - start) * 1000.0, 2),
        )

    # 1. Adjacent-frame SSIM & optical-flow drift
    adjacent_ssim: List[float] = []
    flow_drifts: List[float] = []
    flow_magnitudes: List[float] = []

    for idx in range(len(decoded_frames) - 1):
        fa = decoded_frames[idx]
        fb = decoded_frames[idx + 1]
        s_val = compute_frame_ssim(fa, fb)
        adjacent_ssim.append(s_val)

        flow_res = compute_optical_flow_drift(fa, fb)
        flow_drifts.append(float(flow_res["optical_flow_drift"]))
        flow_magnitudes.append(float(flow_res["mean_flow_magnitude"]))

    mean_ssim = sum(adjacent_ssim) / float(len(adjacent_ssim))
    min_ssim = min(adjacent_ssim)
    mean_flow_drift = sum(flow_drifts) / float(len(flow_drifts))
    max_flow_drift = max(flow_drifts)
    mean_flow_mag = sum(flow_magnitudes) / float(len(flow_magnitudes))

    # 2. Luminance & block flicker score
    flicker_res = compute_luminance_flicker(decoded_frames)
    flicker_score = float(flicker_res["flicker_score"])
    flicker_stability = float(flicker_res["flicker_stability"])

    # 3. Extend segment boundary drift evaluation
    boundary_reports: List[Dict[str, Any]] = []
    active_segments = list(segments or segment_paths or [])
    try:
        if len(active_segments) >= 2:
            for s_idx in range(len(active_segments) - 1):
                boundary_reports.append(
                    compute_extend_boundary_drift(active_segments[s_idx], active_segments[s_idx + 1])
                )
        elif previous_segment is not None:
            boundary_reports.append(
                compute_extend_boundary_drift(previous_segment, [sampled_frames[0]])
            )
        elif boundary_frame_indices:
            for b_idx in boundary_frame_indices:
                if 0 <= int(b_idx) < len(sampled_frames) - 1:
                    boundary_reports.append(
                        compute_extend_boundary_drift(
                            [sampled_frames[int(b_idx)]],
                            [sampled_frames[int(b_idx) + 1]],
                        )
                    )
        elif is_extend and len(sampled_frames) >= 2:
            mid = max(0, (len(sampled_frames) // 2) - 1)
            boundary_reports.append(
                compute_extend_boundary_drift(
                    [sampled_frames[mid]],
                    [sampled_frames[mid + 1]],
                )
            )
    except Exception as exc:
        boundary_reports.append(
            {
                "boundary_ssim": 0.0,
                "boundary_luma_delta": 1.0,
                "boundary_flow_drift": 1.0,
                "boundary_drift_score": 1.0,
                "boundary_consistency": 0.0,
                "error": str(exc),
            }
        )

    extend_evaluated = len(boundary_reports) > 0
    if extend_evaluated:
        extend_boundary_drift = max(float(r["boundary_drift_score"]) for r in boundary_reports)
        extend_boundary_ssim = min(float(r["boundary_ssim"]) for r in boundary_reports)
    else:
        # Track worst adjacent frame jump even on non-extend videos
        worst_idx = min(range(len(adjacent_ssim)), key=lambda i: adjacent_ssim[i])
        extend_boundary_ssim = adjacent_ssim[worst_idx]
        extend_boundary_drift = round(
            0.50 * (1.0 - adjacent_ssim[worst_idx])
            + 0.30 * float(flicker_res["adjacent_luma_deltas"][worst_idx])
            + 0.20 * flow_drifts[worst_idx],
            6,
        )

    # 4. Aggregate score and reason codes
    reason_codes: List[str] = []
    if mean_ssim < ssim_threshold:
        reason_codes.append("TEMPORAL_SSIM_BELOW_THRESHOLD")
    if flicker_score > flicker_threshold:
        reason_codes.append("TEMPORAL_FLICKER_DETECTED")
    if mean_flow_drift > flow_drift_threshold:
        reason_codes.append("TEMPORAL_OPTICAL_FLOW_DRIFT")
    if extend_evaluated and (
        extend_boundary_drift > boundary_drift_threshold or extend_boundary_ssim < ssim_threshold
    ):
        reason_codes.append("EXTEND_BOUNDARY_DRIFT")

    flow_consistency = 1.0 - mean_flow_drift
    boundary_consistency = 1.0 - extend_boundary_drift
    if extend_evaluated:
        overall_score = (
            0.35 * mean_ssim
            + 0.25 * flicker_stability
            + 0.20 * flow_consistency
            + 0.20 * boundary_consistency
        )
    else:
        overall_score = (
            0.45 * mean_ssim
            + 0.30 * flicker_stability
            + 0.25 * flow_consistency
        )
    overall_score = max(0.0, min(1.0, round(overall_score, 4)))

    if overall_score < threshold and "TEMPORAL_CONSISTENCY_BELOW_THRESHOLD" not in reason_codes:
        reason_codes.append("TEMPORAL_CONSISTENCY_BELOW_THRESHOLD")

    verdict = "fail" if (reason_codes or overall_score < threshold) else "pass"

    evidence: Dict[str, Any] = {
        "family": "temporal",
        "sampled_frame_count": len(decoded_frames),
        "requested_sample_frames": target_sample_frames,
        "adjacent_ssim": [round(s, 6) for s in adjacent_ssim],
        "mean_ssim": round(mean_ssim, 6),
        "min_ssim": round(min_ssim, 6),
        "luminance_series": flicker_res["luminance_series"],
        "adjacent_luma_deltas": flicker_res["adjacent_luma_deltas"],
        "flicker_score": round(flicker_score, 6),
        "flicker_stability": round(flicker_stability, 6),
        "optical_flow_drift": round(mean_flow_drift, 6),
        "max_optical_flow_drift": round(max_flow_drift, 6),
        "optical_flow_consistency": round(flow_consistency, 6),
        "mean_flow_magnitude": round(mean_flow_mag, 6),
        "extend_boundary_evaluated": extend_evaluated,
        "extend_boundary_drift": round(extend_boundary_drift, 6),
        "extend_boundary_ssim": round(extend_boundary_ssim, 6),
        "boundary_reports": boundary_reports,
        "defects": list(reason_codes),
    }

    return HarnessResult(
        harness_id=HARNESS_ID,
        harness_version=HARNESS_VERSION,
        phase=phase,  # type: ignore[arg-type]
        verdict=verdict,  # type: ignore[arg-type]
        score=overall_score,
        reason_codes=reason_codes,
        evidence=evidence,
        runtime_ms=round((time.perf_counter() - start) * 1000.0, 2),
    )


# Convenient aliases for orchestrator / test callers
evaluate_temporal = evaluate_temporal_consistency
validate_temporal_consistency = evaluate_temporal_consistency
evaluate_video_temporal = evaluate_temporal_consistency


class _ClassOrInstanceMethod:
    """Descriptor allowing TemporalEvaluator.evaluate(...) to be called on class or instance."""

    def __init__(self, fn: Any) -> None:
        self.fn = fn

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        target = instance if instance is not None else owner

        def _bound(*args: Any, **kwargs: Any) -> Any:
            return self.fn(target, *args, **kwargs)

        return _bound


class TemporalEvaluator:
    """Object-oriented wrapper for the Tier-B temporal consistency evaluator."""

    HARNESS_ID = HARNESS_ID
    HARNESS_VERSION = HARNESS_VERSION
    DEFAULT_SAMPLE_FRAMES = DEFAULT_VIDEO_SAMPLE_FRAMES
    DEFAULT_THRESHOLD = DEFAULT_TEMPORAL_THRESHOLD

    def __init__(
        self,
        *,
        sample_frames: Optional[int] = None,
        threshold: float = DEFAULT_TEMPORAL_THRESHOLD,
        ssim_threshold: float = DEFAULT_SSIM_THRESHOLD,
        flicker_threshold: float = DEFAULT_FLICKER_THRESHOLD,
        flow_drift_threshold: float = DEFAULT_FLOW_DRIFT_THRESHOLD,
        boundary_drift_threshold: float = DEFAULT_BOUNDARY_DRIFT_THRESHOLD,
    ) -> None:
        self.sample_frames = sample_frames
        self.threshold = threshold
        self.ssim_threshold = ssim_threshold
        self.flicker_threshold = flicker_threshold
        self.flow_drift_threshold = flow_drift_threshold
        self.boundary_drift_threshold = boundary_drift_threshold

    @_ClassOrInstanceMethod
    def evaluate(
        target: Any,
        video_data: Optional[Union[bytes, bytearray, str, Path, Sequence[bytes], Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> HarnessResult:
        if isinstance(target, TemporalEvaluator):
            kwargs.setdefault("sample_frames", target.sample_frames)
            kwargs.setdefault("threshold", target.threshold)
            kwargs.setdefault("ssim_threshold", target.ssim_threshold)
            kwargs.setdefault("flicker_threshold", target.flicker_threshold)
            kwargs.setdefault("flow_drift_threshold", target.flow_drift_threshold)
            kwargs.setdefault("boundary_drift_threshold", target.boundary_drift_threshold)
        return evaluate_temporal_consistency(video_data, **kwargs)

    evaluate_video = evaluate


__all__ = [
    "HARNESS_ID",
    "HARNESS_VERSION",
    "DEFAULT_VIDEO_SAMPLE_FRAMES",
    "DEFAULT_TEMPORAL_THRESHOLD",
    "DEFAULT_SSIM_THRESHOLD",
    "DEFAULT_FLICKER_THRESHOLD",
    "DEFAULT_FLOW_DRIFT_THRESHOLD",
    "DEFAULT_BOUNDARY_DRIFT_THRESHOLD",
    "TemporalEvaluator",
    "get_video_sample_frames",
    "sample_video_frames",
    "compute_frame_ssim",
    "compute_luminance_flicker",
    "compute_optical_flow_drift",
    "compute_extend_boundary_drift",
    "evaluate_temporal_consistency",
    "evaluate_temporal",
    "validate_temporal_consistency",
    "evaluate_video_temporal",
]
