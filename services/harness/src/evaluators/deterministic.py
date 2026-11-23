"""
Tier-A deterministic asset evaluator (KHF).

Validates generated image, video, and audio bytes without external LLM calls.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from packages.contracts.src.models import HarnessResult

HARNESS_ID = "khf.deterministic_asset"
HARNESS_VERSION = "1.0.0"


def _laplacian_variance(img: Any) -> float:
    """Compute discrete Laplacian variance on a grayscale PIL Image."""
    gray = img.convert("L")
    # Downsample very large images for fast deterministic sharpness check
    if gray.width > 512 or gray.height > 512:
        gray.thumbnail((512, 512))
    w, h = gray.size
    if w < 3 or h < 3:
        return 0.0
    pixels = list(gray.getdata())
    lap_vals: List[float] = []
    for y in range(1, h - 1):
        row_offset = y * w
        for x in range(1, w - 1):
            idx = row_offset + x
            val = (
                pixels[idx - w]
                + pixels[idx + w]
                + pixels[idx - 1]
                + pixels[idx + 1]
                - 4 * pixels[idx]
            )
            lap_vals.append(float(val))
    if not lap_vals:
        return 0.0
    mean = sum(lap_vals) / len(lap_vals)
    return sum((v - mean) ** 2 for v in lap_vals) / len(lap_vals)


def _parse_image_dimensions_fallback(data: bytes) -> Optional[Tuple[int, int]]:
    """Pure-Python header parser fallback when Pillow is not installed."""
    # PNG: 8-byte signature + IHDR chunk (width, height at bytes 16..24)
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return w, h
    # GIF: GIF87a / GIF89a
    if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        w = int.from_bytes(data[6:8], "little")
        h = int.from_bytes(data[8:10], "little")
        return w, h
    # JPEG: SOI 0xFFD8
    if len(data) >= 4 and data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h = int.from_bytes(data[i + 5 : i + 7], "big")
                w = int.from_bytes(data[i + 7 : i + 9], "big")
                return w, h
            if i + 4 > len(data):
                break
            seg_len = int.from_bytes(data[i + 2 : i + 4], "big")
            if seg_len < 2:
                break
            i += 2 + seg_len
    return None


def _validate_image(
    data: bytes,
    expected_mime: str,
    source_dimensions: Optional[Tuple[int, int]],
    require_upscale_delta: bool,
) -> Tuple[str, List[str], Dict[str, Any]]:
    reason_codes: List[str] = []
    evidence: Dict[str, Any] = {"expected_mime": expected_mime, "byte_length": len(data)}

    try:
        from PIL import Image
    except ImportError:
        dims = _parse_image_dimensions_fallback(data)
        if not dims or dims[0] <= 0 or dims[1] <= 0:
            reason_codes.append("CORRUPT_IMAGE: PIL_UNAVAILABLE_AND_INVALID_HEADER")
            return "fail", reason_codes, evidence
        width, height = dims
        evidence["width"] = width
        evidence["height"] = height
        evidence["pil_fallback"] = True
        if require_upscale_delta:
            if not source_dimensions:
                reason_codes.append("MISSING_SOURCE_DIMENSIONS")
                return "fail", reason_codes, evidence
            if width <= source_dimensions[0] or height <= source_dimensions[1]:
                reason_codes.append("UPSCALE_DIMENSION_NOT_EXCEEDED")
                return "fail", reason_codes, evidence
        return "pass", reason_codes, evidence

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = img.size
            fmt = img.format
            evidence["width"] = width
            evidence["height"] = height
            evidence["format"] = fmt
            if width <= 0 or height <= 0:
                reason_codes.append("INVALID_IMAGE_DIMENSIONS")
                return "fail", reason_codes, evidence

            if require_upscale_delta:
                if not source_dimensions:
                    reason_codes.append("MISSING_SOURCE_DIMENSIONS")
                    return "fail", reason_codes, evidence
                src_w, src_h = source_dimensions
                evidence["source_width"] = src_w
                evidence["source_height"] = src_h
                if width <= src_w or height <= src_h:
                    reason_codes.append("UPSCALE_DIMENSION_NOT_EXCEEDED")
                    return "fail", reason_codes, evidence
                sharpness = _laplacian_variance(img)
                evidence["laplacian_variance"] = sharpness
                if sharpness <= 0.0:
                    reason_codes.append("UPSCALE_ZERO_SHARPNESS_DELTA")
                    return "fail", reason_codes, evidence
    except Exception as exc:
        reason_codes.append(f"CORRUPT_IMAGE: {type(exc).__name__}")
        return "fail", reason_codes, evidence

    return "pass", reason_codes, evidence


def _validate_video_header(data: bytes) -> bool:
    if len(data) < 12:
        return False
    # MP4 / MOV: 'ftyp' at offset 4
    if data[4:8] == b"ftyp":
        return True
    # WebM / MKV: EBML header
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return True
    # AVI: RIFF....AVI
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return True
    return False


def _validate_video(data: bytes, expected_mime: str) -> Tuple[str, List[str], Dict[str, Any]]:
    reason_codes: List[str] = []
    evidence: Dict[str, Any] = {"expected_mime": expected_mime, "byte_length": len(data)}

    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin:
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            proc = subprocess.run(
                [
                    ffprobe_bin,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                reason_codes.append("FFPROBE_INVALID_CONTAINER")
                return "fail", reason_codes, evidence
            info = json.loads(proc.stdout or "{}")
            streams = info.get("streams", [])
            fmt = info.get("format", {})
            duration = float(fmt.get("duration") or 0.0)
            evidence["duration"] = duration
            evidence["stream_count"] = len(streams)
            if not streams or duration <= 0.0:
                reason_codes.append("VIDEO_ZERO_DURATION_OR_NO_STREAMS")
                return "fail", reason_codes, evidence
            return "pass", reason_codes, evidence
        except Exception as exc:
            reason_codes.append(f"VIDEO_PROBE_ERROR: {type(exc).__name__}")
            return "fail", reason_codes, evidence
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    else:
        evidence["ffprobe_fallback"] = True
        if not _validate_video_header(data):
            reason_codes.append("INVALID_VIDEO_HEADER")
            return "fail", reason_codes, evidence
        return "pass", reason_codes, evidence


def _validate_audio(data: bytes, expected_mime: str) -> Tuple[str, List[str], Dict[str, Any]]:
    reason_codes: List[str] = []
    evidence: Dict[str, Any] = {"expected_mime": expected_mime, "byte_length": len(data)}

    if len(data) < 12:
        reason_codes.append("AUDIO_TOO_SMALL")
        return "fail", reason_codes, evidence

    is_wav = data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    is_mp3 = data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    is_ogg = data[:4] == b"OggS"

    if not (is_wav or is_mp3 or is_ogg):
        reason_codes.append("INVALID_AUDIO_HEADER")
        return "fail", reason_codes, evidence

    evidence["detected_format"] = "wav" if is_wav else ("mp3" if is_mp3 else "ogg")
    return "pass", reason_codes, evidence


def validate_asset_bytes(
    data: bytes,
    expected_media_type: str,
    expected_mime: str,
    source_dimensions: Optional[Tuple[int, int]] = None,
    require_upscale_delta: bool = False,
) -> HarnessResult:
    """
    Validate generated asset bytes deterministically (Tier-A).
    """
    start = time.perf_counter()
    if not data:
        return HarnessResult(
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            phase="post-execution",
            verdict="fail",
            score=0.0,
            reason_codes=["EMPTY_ASSET_BYTES"],
            evidence={"expected_media_type": expected_media_type, "byte_length": 0},
            runtime_ms=(time.perf_counter() - start) * 1000.0,
        )

    media_type = expected_media_type.lower().strip()
    if media_type == "image":
        verdict, reason_codes, evidence = _validate_image(
            data, expected_mime, source_dimensions, require_upscale_delta
        )
    elif media_type == "video":
        verdict, reason_codes, evidence = _validate_video(data, expected_mime)
    elif media_type == "audio":
        verdict, reason_codes, evidence = _validate_audio(data, expected_mime)
    else:
        verdict = "fail"
        reason_codes = [f"UNSUPPORTED_MEDIA_TYPE: {expected_media_type}"]
        evidence = {"expected_media_type": expected_media_type, "byte_length": len(data)}

    return HarnessResult(
        harness_id=HARNESS_ID,
        harness_version=HARNESS_VERSION,
        phase="post-execution",
        verdict=verdict,
        score=1.0 if verdict == "pass" else 0.0,
        reason_codes=reason_codes,
        evidence=evidence,
        runtime_ms=(time.perf_counter() - start) * 1000.0,
    )
