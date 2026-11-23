"""
KEYSTONE Video Operations (Bible v2 §23.2 / §23.3).

Provides ffmpeg / ffprobe video utilities for:
  - extract_last_frame(video_path) -> PNG bytes
  - stitch_video_segments(segment_paths, output_path) -> Path (ffmpeg concat demuxer)
  - probe_video_metadata(video_path) -> {duration, width, height, fps, codec, ...}

Automatically resolves ffmpeg/ffprobe from environment overrides, system PATH,
or the bundled imageio-ffmpeg binary, with clean ffmpeg -i stderr fallback when
standalone ffprobe is unavailable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class VideoOpsError(RuntimeError):
    """Raised when ffmpeg/ffprobe execution fails or inputs are invalid."""


VIDEO_FPS_PRESETS: Tuple[int, ...] = (30, 60, 100, 120)
VIDEO_MIN_FPS: int = 8
VIDEO_MAX_FPS: int = 120
VIDEO_DEFAULT_FPS: int = 30
_MP4_TIMESCALE: str = "120000"


def _format_fps(fps: float) -> str:
    return f"{float(fps):.4f}".rstrip("0").rstrip(".")


def resolve_target_fps(raw_fps: Any = None, *, default: Optional[int] = None) -> Optional[int]:
    """Normalize numeric/string Hz/FPS inputs (`30`, `60`, `100`, `120`, `'120Hz'`) into [8, 120]."""
    if raw_fps is None or isinstance(raw_fps, bool):
        return default
    try:
        if isinstance(raw_fps, str):
            cleaned = raw_fps.strip().lower().replace("hz", "").replace("fps", "").strip()
            if not cleaned:
                return default
            parsed = int(round(float(cleaned)))
        else:
            parsed = int(round(float(raw_fps)))
    except (ValueError, TypeError):
        return default
    return max(VIDEO_MIN_FPS, min(parsed, VIDEO_MAX_FPS))


def _resolve_ffmpeg() -> str:
    """Resolve a runnable ffmpeg executable path."""
    env_bin = os.getenv("FFMPEG_BIN", "").strip()
    if env_bin and Path(env_bin).is_file():
        return env_bin

    path_bin = shutil.which("ffmpeg")
    if path_bin:
        return path_bin

    try:
        import imageio_ffmpeg  # type: ignore

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except Exception:
        pass

    raise VideoOpsError(
        "FFMPEG_NOT_FOUND: no ffmpeg executable found on PATH, FFMPEG_BIN, or imageio_ffmpeg"
    )


def _resolve_ffprobe() -> Optional[str]:
    """Resolve ffprobe executable path if available, otherwise return None."""
    env_bin = os.getenv("FFPROBE_BIN", "").strip()
    if env_bin and Path(env_bin).is_file():
        return env_bin

    path_bin = shutil.which("ffprobe")
    if path_bin:
        return path_bin

    try:
        ff = Path(_resolve_ffmpeg())
        for candidate_name in ("ffprobe.exe", "ffprobe"):
            sibling = ff.with_name(candidate_name)
            if sibling.is_file():
                return str(sibling)
    except VideoOpsError:
        pass

    return None


def _ensure_video_file(video_path: Path | str) -> Path:
    path = Path(video_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"VIDEO_NOT_FOUND: {path}")
    if path.stat().st_size == 0:
        raise VideoOpsError(f"EMPTY_VIDEO_FILE: {path}")
    return path


def _parse_fps(rate_str: str) -> float:
    raw = (rate_str or "").strip()
    if not raw or raw == "0/0":
        return 0.0
    if "/" in raw:
        num_s, den_s = raw.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
            return num / den if den != 0 else 0.0
        except ValueError:
            return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _probe_via_ffprobe(ffprobe_bin: str, path: Path) -> Dict[str, Any]:
    proc = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise VideoOpsError(f"FFPROBE_FAILED: {proc.stderr.strip() or 'non-zero exit'}")

    try:
        info = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoOpsError(f"FFPROBE_INVALID_JSON: {exc}") from exc

    streams = info.get("streams") or []
    fmt = info.get("format") or {}
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise VideoOpsError(f"FFPROBE_NO_VIDEO_STREAM: {path}")

    vs = video_streams[0]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    raw_duration = vs.get("duration") or fmt.get("duration") or 0.0
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = 0.0

    fps = _parse_fps(str(vs.get("avg_frame_rate") or ""))
    if fps <= 0.0:
        fps = _parse_fps(str(vs.get("r_frame_rate") or ""))

    width = int(vs.get("width") or 0)
    height = int(vs.get("height") or 0)
    codec = str(vs.get("codec_name") or "unknown")
    if width <= 0 or height <= 0:
        raise VideoOpsError(f"FFPROBE_INVALID_DIMENSIONS: {width}x{height} in {path}")

    return {
        "duration": round(duration, 6),
        "width": width,
        "height": height,
        "fps": round(fps, 4),
        "codec": codec,
        "has_audio": bool(audio_streams),
        "format_name": str(fmt.get("format_name") or ""),
        "size_bytes": path.stat().st_size,
    }


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_STREAM_RE = re.compile(
    r"Stream\s+#\d+:\d+[^:]*:\s*Video:\s*([^\s,(]+).*?,\s*(\d+)x(\d+)(?:\s*\[[^\]]*\])?(.*)"
)
_AUDIO_STREAM_RE = re.compile(r"Stream\s+#\d+:\d+[^:]*:\s*Audio:")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:fps|tbr)")


def _probe_via_ffmpeg_fallback(ffmpeg_bin: str, path: Path) -> Dict[str, Any]:
    """Parse video metadata from `ffmpeg -hide_banner -i` when ffprobe is absent."""
    proc = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    stderr = proc.stderr or ""
    v_match = _VIDEO_STREAM_RE.search(stderr)
    if not v_match:
        raise VideoOpsError(
            f"VIDEO_PROBE_FAILED: no video stream detected in {path}: {stderr.strip()[:400]}"
        )

    codec = v_match.group(1).strip()
    width = int(v_match.group(2))
    height = int(v_match.group(3))
    tail = v_match.group(4) or ""

    fps_match = _FPS_RE.search(tail)
    fps = float(fps_match.group(1)) if fps_match else 0.0

    duration = 0.0
    dur_match = _DURATION_RE.search(stderr)
    if dur_match:
        hours, minutes, seconds = dur_match.groups()
        duration = int(hours) * 3600.0 + int(minutes) * 60.0 + float(seconds)

    if width <= 0 or height <= 0:
        raise VideoOpsError(f"VIDEO_PROBE_INVALID_DIMENSIONS: {width}x{height} in {path}")

    return {
        "duration": round(duration, 6),
        "width": width,
        "height": height,
        "fps": round(fps, 4),
        "codec": codec,
        "has_audio": bool(_AUDIO_STREAM_RE.search(stderr)),
        "format_name": path.suffix.lstrip(".").lower(),
        "size_bytes": path.stat().st_size,
    }


def probe_video_metadata(video_path: Path) -> Dict[str, Any]:
    """
    Probe video metadata (duration, width, height, fps, codec) via ffprobe,
    falling back cleanly to ffmpeg stream inspection when ffprobe is absent.
    """
    path = _ensure_video_file(video_path)
    ffprobe_bin = _resolve_ffprobe()
    if ffprobe_bin:
        return _probe_via_ffprobe(ffprobe_bin, path)
    ffmpeg_bin = _resolve_ffmpeg()
    return _probe_via_ffmpeg_fallback(ffmpeg_bin, path)


def extract_last_frame(video_path: Path) -> bytes:
    """
    Extract the final video frame as PNG bytes using ffmpeg.

    First attempts a fast end-of-file seek (`-sseof -0.5` with `-update 1`);
    falls back to full stream scan if the clip is too short or container seeking
    fails to emit a frame.
    """
    path = _ensure_video_file(video_path)
    ffmpeg_bin = _resolve_ffmpeg()

    with tempfile.TemporaryDirectory(prefix="ks_lastframe_") as tmpdir:
        out_png = Path(tmpdir) / "last_frame.png"

        # Fast EOF-seek pass: -update 1 overwrites out_png with each decoded frame up to EOF.
        fast_cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-sseof",
            "-0.5",
            "-i",
            str(path),
            "-update",
            "1",
            "-f",
            "image2",
            str(out_png),
        ]
        proc = subprocess.run(fast_cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0 and out_png.is_file() and out_png.stat().st_size > 0:
            return out_png.read_bytes()

        # Full scan fallback for very short clips or containers lacking EOF seek tables.
        if out_png.exists():
            out_png.unlink()
        full_cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-update",
            "1",
            "-f",
            "image2",
            str(out_png),
        ]
        proc2 = subprocess.run(full_cmd, capture_output=True, text=True, timeout=120)
        if proc2.returncode == 0 and out_png.is_file() and out_png.stat().st_size > 0:
            return out_png.read_bytes()

        detail = (proc2.stderr or proc.stderr or "").strip()[:500]
        raise VideoOpsError(f"FFMPEG_EXTRACT_LAST_FRAME_FAILED: {detail or 'no frame emitted'}")


def _even_dim(value: int) -> int:
    return max(2, value - (value % 2))


def _concat_line(path: Path) -> str:
    escaped = path.resolve().as_posix().replace("'", "'\\''")
    return f"file '{escaped}'"


def convert_video_fps(
    input_path: Path,
    output_path: Path,
    target_fps: float,
    *,
    interpolation_mode: str = "auto",
) -> Path:
    """
    Convert an MP4/video file to `target_fps` (clamped to [8, 120] Hz, e.g. 30/60/100/120).
    Uses FFmpeg motion-compensated or frame-blended interpolation when upsampling and
    `-video_track_timescale 120000` so container timestamps represent 30/60/100/120 Hz cleanly.
    """
    in_path = _ensure_video_file(input_path)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_fps = float(max(VIDEO_MIN_FPS, min(float(target_fps), float(VIDEO_MAX_FPS))))
    fps_str = _format_fps(resolved_fps)
    meta = probe_video_metadata(in_path)
    current_fps = float(meta.get("fps") or 0.0)
    duration = float(meta.get("duration") or 0.0)
    has_audio = bool(meta.get("has_audio"))

    if current_fps > 0.0 and abs(current_fps - resolved_fps) <= 0.25:
        if in_path.resolve() != out_path.resolve():
            shutil.copyfile(in_path, out_path)
        return out_path

    ffmpeg_bin = _resolve_ffmpeg()

    def _run_vf(vf_expr: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            str(in_path),
            "-vf",
            vf_expr,
            "-r",
            fps_str,
            "-video_track_timescale",
            _MP4_TIMESCALE,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
        ]
        if has_audio:
            cmd.extend(["-c:a", "aac"])
        else:
            cmd.append("-an")
        cmd.extend(["-movflags", "+faststart", str(out_path)])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=240)

    mode = (interpolation_mode or "auto").strip().lower()
    est_frames = int(round(duration * (current_fps or 24.0)))
    upsampling = current_fps <= 0.0 or resolved_fps > current_fps + 0.25

    proc: Optional[subprocess.CompletedProcess[str]] = None
    if upsampling:
        if mode == "mci" or (mode == "auto" and est_frames > 4 and duration <= 15.0):
            proc = _run_vf(
                f"pad=ceil(iw/2)*2:ceil(ih/2)*2,minterpolate=fps={fps_str}:mi_mode=mci:mc_mode=obmc:me_mode=bidir:me=epzs"
            )
        if proc is None or proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            proc = _run_vf(f"pad=ceil(iw/2)*2:ceil(ih/2)*2,minterpolate=fps={fps_str}:mi_mode=blend")
    else:
        proc = _run_vf(f"pad=ceil(iw/2)*2:ceil(ih/2)*2,fps={fps_str}")

    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        raise VideoOpsError(f"FFMPEG_FPS_CONVERT_FAILED: {proc.stderr.strip()[:500] or 'empty output'}")
    return out_path


def convert_video_bytes_fps(
    video_bytes: bytes,
    target_fps: float,
    *,
    interpolation_mode: str = "auto",
) -> bytes:
    """In-memory wrapper converting MP4/video bytes to `target_fps` (up to 120 Hz)."""
    if not video_bytes:
        raise ValueError("EMPTY_VIDEO_BYTES: video_bytes must be non-empty")
    with tempfile.TemporaryDirectory(prefix="ks_fps_") as tmpdir:
        tmp_root = Path(tmpdir)
        in_path = tmp_root / "input.mp4"
        out_path = tmp_root / "output.mp4"
        in_path.write_bytes(video_bytes)
        convert_video_fps(in_path, out_path, target_fps, interpolation_mode=interpolation_mode)
        return out_path.read_bytes()


def stitch_video_segments(
    segment_paths: List[Path],
    output_path: Path,
    *,
    target_fps: Optional[float] = None,
) -> Path:
    """
    Stitch ordered video segments into a single H.264 MP4 via ffmpeg's concat demuxer,
    re-encoding to matching resolution, frame rate, and yuv420p pixel format.
    """
    if not segment_paths:
        raise ValueError("NO_SEGMENTS_PROVIDED: segment_paths must contain at least one path")

    resolved_segments = [_ensure_video_file(seg) for seg in segment_paths]
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = _resolve_ffmpeg()

    metas = [probe_video_metadata(seg) for seg in resolved_segments]
    target_w = _even_dim(int(metas[0]["width"]))
    target_h = _even_dim(int(metas[0]["height"]))
    explicit_fps = resolve_target_fps(target_fps, default=None)
    if explicit_fps is not None:
        resolved_target_fps = float(explicit_fps)
    else:
        resolved_target_fps = float(metas[0]["fps"] or 24.0)
        if resolved_target_fps <= 0.0:
            resolved_target_fps = 24.0
    target_fps_str = _format_fps(resolved_target_fps)
    keep_audio = all(bool(m.get("has_audio")) for m in metas)

    needs_normalization = explicit_fps is not None or any(
        _even_dim(int(m["width"])) != target_w
        or _even_dim(int(m["height"])) != target_h
        or abs(float(m.get("fps") or resolved_target_fps) - resolved_target_fps) > 0.25
        or str(m.get("codec") or "") != "h264"
        for m in metas
    )

    with tempfile.TemporaryDirectory(prefix="ks_stitch_") as tmpdir:
        tmp_root = Path(tmpdir)
        concat_inputs: List[Path] = []

        if needs_normalization:
            for idx, (seg, seg_meta) in enumerate(zip(resolved_segments, metas)):
                norm_path = tmp_root / f"seg_{idx:03d}.mp4"
                seg_input = seg
                seg_fps = float(seg_meta.get("fps") or 0.0)
                if explicit_fps is not None and (seg_fps <= 0.0 or resolved_target_fps > seg_fps + 0.25):
                    interp_path = tmp_root / f"seg_interp_{idx:03d}.mp4"
                    convert_video_fps(seg, interp_path, resolved_target_fps)
                    seg_input = interp_path

                vf = (
                    f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
                )
                norm_cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(seg_input),
                    "-vf",
                    vf,
                    "-r",
                    target_fps_str,
                    "-video_track_timescale",
                    _MP4_TIMESCALE,
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                ]
                if keep_audio:
                    norm_cmd.extend(["-c:a", "aac", "-ar", "44100", "-ac", "2"])
                else:
                    norm_cmd.append("-an")
                norm_cmd.append(str(norm_path))
                proc = subprocess.run(norm_cmd, capture_output=True, text=True, timeout=180)
                if proc.returncode != 0 or not norm_path.is_file():
                    raise VideoOpsError(
                        f"FFMPEG_NORMALIZE_FAILED ({seg}): {proc.stderr.strip()[:500]}"
                    )
                concat_inputs.append(norm_path)
        else:
            concat_inputs = resolved_segments

        concat_txt = tmp_root / "concat_list.txt"
        concat_txt.write_text(
            "\n".join(_concat_line(p) for p in concat_inputs) + "\n",
            encoding="utf-8",
        )

        concat_cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-vf",
            f"scale={target_w}:{target_h},setsar=1",
            "-r",
            target_fps_str,
            "-video_track_timescale",
            _MP4_TIMESCALE,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
        ]
        if keep_audio:
            concat_cmd.extend(["-c:a", "aac"])
        else:
            concat_cmd.append("-an")
        concat_cmd.extend(["-movflags", "+faststart", str(out_path)])

        proc = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=240)
        if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            raise VideoOpsError(
                f"FFMPEG_STITCH_FAILED: {proc.stderr.strip()[:500] or 'empty output'}"
            )

    return out_path


def extract_video_frames(video_path: Path, max_frames: Optional[int] = None) -> List[bytes]:
    """Extract ordered PNG frame bytes from a video file using ffmpeg."""
    path = _ensure_video_file(video_path)
    ffmpeg_bin = _resolve_ffmpeg()

    with tempfile.TemporaryDirectory(prefix="ks_frames_") as tmpdir:
        pattern = Path(tmpdir) / "frame_%06d.png"
        cmd = [ffmpeg_bin, "-y", "-v", "error", "-i", str(path)]
        if max_frames is not None and max_frames > 0:
            cmd.extend(["-frames:v", str(int(max_frames))])
        cmd.append(str(pattern))

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise VideoOpsError(f"FFMPEG_EXTRACT_FRAMES_FAILED: {proc.stderr.strip()[:500]}")

        frame_files = sorted(Path(tmpdir).glob("frame_*.png"))
        if not frame_files:
            raise VideoOpsError(f"FFMPEG_NO_FRAMES_EXTRACTED: {path}")
        return [f.read_bytes() for f in frame_files]


def encode_frames_to_video(
    frames: Sequence[bytes],
    output_path: Path,
    fps: float = 24.0,
    audio_source: Optional[Path] = None,
) -> Path:
    """Encode a sequence of PNG frame bytes into an H.264 MP4 file."""
    if not frames:
        raise ValueError("NO_FRAMES_PROVIDED: frames must be non-empty")

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = _resolve_ffmpeg()
    safe_fps = float(fps) if fps and fps > 0 else 24.0

    with tempfile.TemporaryDirectory(prefix="ks_encode_") as tmpdir:
        tmp_root = Path(tmpdir)
        for idx, frame_bytes in enumerate(frames, start=1):
            (tmp_root / f"frame_{idx:06d}.png").write_bytes(frame_bytes)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-framerate",
            _format_fps(safe_fps),
            "-i",
            str(tmp_root / "frame_%06d.png"),
        ]
        include_audio = False
        if audio_source is not None:
            audio_path = _ensure_video_file(audio_source)
            meta = probe_video_metadata(audio_path)
            if meta.get("has_audio"):
                cmd.extend(["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-shortest"])
                include_audio = True

        cmd.extend(
            [
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-r",
                _format_fps(safe_fps),
                "-video_track_timescale",
                _MP4_TIMESCALE,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
            ]
        )
        if include_audio:
            cmd.extend(["-c:a", "aac"])
        else:
            cmd.append("-an")
        cmd.extend(["-movflags", "+faststart", str(out_path)])

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            raise VideoOpsError(f"FFMPEG_ENCODE_FAILED: {proc.stderr.strip()[:500]}")

    return out_path
