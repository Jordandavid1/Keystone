"""
KEYSTONE ElevenLabs Audio & Persona Voice Synthesis Service.
Provides official ElevenLabs Text-to-Speech (TTS) integration with voice catalog discovery
and POSIX-compatible local TTS fallback (piper / espeak-ng, or deterministic error when
no local TTS binary is installed).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"


def get_elevenlabs_api_key() -> str:
    """Reads ELEVENLABS_API_KEY from environment or repo .env file."""
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    return ""


def _find_piper_voices() -> List[Dict[str, Any]]:
    """Discover installed Piper TTS ONNX voice models if `piper` binary is available."""
    piper_bin = shutil.which("piper")
    if not piper_bin:
        return []

    voices: List[Dict[str, Any]] = []
    explicit_model = (os.getenv("PIPER_MODEL_PATH") or os.getenv("KEYSTONE_PIPER_MODEL") or "").strip()
    if explicit_model and Path(explicit_model).is_file():
        mpath = Path(explicit_model)
        voices.append({
            "voice_id": str(mpath),
            "name": mpath.stem,
            "category": "local_posix",
            "gender": "neutral",
            "accent": "standard",
            "description": f"Local Piper neural TTS model ({mpath.name})",
            "preview_url": "",
            "provider": "piper",
            "model_path": str(mpath),
        })

    models_dir = (os.getenv("PIPER_MODELS_DIR") or "").strip()
    if models_dir and Path(models_dir).is_dir():
        for onnx_file in sorted(Path(models_dir).glob("*.onnx")):
            if str(onnx_file) == explicit_model:
                continue
            voices.append({
                "voice_id": str(onnx_file),
                "name": onnx_file.stem,
                "category": "local_posix",
                "gender": "neutral",
                "accent": "standard",
                "description": f"Local Piper neural TTS model ({onnx_file.name})",
                "preview_url": "",
                "provider": "piper",
                "model_path": str(onnx_file),
            })
    return voices


def _find_espeak_binary() -> Optional[str]:
    """Return path to `espeak-ng` or `espeak` on PATH if installed."""
    return shutil.which("espeak-ng") or shutil.which("espeak")


def _list_espeak_voices(espeak_bin: str) -> List[Dict[str, Any]]:
    """Query live installed voices from `espeak-ng --voices`."""
    proc = subprocess.run(
        [espeak_bin, "--voices"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(
            f"AUDIO_VOICES_UNAVAILABLE: Could not enumerate espeak-ng voices ({proc.stderr.strip() or 'no output'})."
        )

    voices: List[Dict[str, Any]] = []
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Pty"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        lang = parts[1]
        age_gender = parts[2]
        voice_name = parts[3]
        voice_file = parts[4]
        gender = "female" if "F" in age_gender.upper() else ("male" if "M" in age_gender.upper() else "neutral")
        voices.append({
            "voice_id": voice_file,
            "name": voice_name,
            "category": "local_posix",
            "gender": gender,
            "accent": lang,
            "description": f"Local espeak-ng voice ({lang})",
            "preview_url": "",
            "provider": "espeak_ng",
        })
    if not voices:
        raise RuntimeError("AUDIO_VOICES_UNAVAILABLE: espeak-ng returned zero voices.")
    return voices


def _list_windows_sapi_voices() -> List[Dict[str, Any]]:
    """Windows-only fallback querying live installed System.Speech voices (never invoked on POSIX/Linux)."""
    if sys.platform != "win32":
        raise RuntimeError(
            "AUDIO_VOICES_UNAVAILABLE: Windows SAPI is unsupported on non-Windows platforms. "
            "Install espeak-ng/piper or set ELEVENLABS_API_KEY."
        )

    ps_script = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$voices = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { "
        "$info = $_.VoiceInfo; "
        "[PSCustomObject]@{ "
        "voice_id = $info.Name; "
        "name = $info.Name; "
        "category = 'local_sapi'; "
        "gender = ($info.Gender.ToString().ToLower()); "
        "accent = $info.Culture.Name; "
        "description = $info.Description; "
        "preview_url = ''; "
        "provider = 'windows_sapi_speech' "
        "} "
        "}); "
        "$synth.Dispose(); "
        "$voices | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(
            f"AUDIO_VOICES_UNAVAILABLE: Could not enumerate local Windows SAPI voices ({proc.stderr.strip() or 'no output'}). "
            "Configure ELEVENLABS_API_KEY for ElevenLabs voices."
        )
    parsed = json.loads(proc.stdout.strip())
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list) and parsed:
        return parsed
    raise RuntimeError("AUDIO_VOICES_UNAVAILABLE: No enabled Windows SAPI voices found and ELEVENLABS_API_KEY is not set.")


def _synthesize_piper_wav(piper_bin: str, model_path: str, text: str, wav_path: Path) -> bytes:
    proc = subprocess.run(
        [piper_bin, "--model", model_path, "--output_file", str(wav_path)],
        input=text,
        capture_output=True,
        text=True,
        timeout=25,
    )
    if proc.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size <= 44:
        raise RuntimeError(
            f"AUDIO_SYNTHESIS_UNAVAILABLE: Piper synthesis failed ({proc.stderr.strip() or 'no audio output'})."
        )
    return wav_path.read_bytes()


def _synthesize_espeak_wav(espeak_bin: str, text: str, voice_type: str, wav_path: Path) -> bytes:
    selector = (voice_type or "").strip()
    cmd = [espeak_bin, "-w", str(wav_path)]
    if selector and selector.lower() not in ("female", "male"):
        cmd.extend(["-v", selector])
    elif selector.lower() in ("female", "rachel", "bella", "domi", "elli"):
        cmd.extend(["-v", "en+f3"])
    elif selector.lower() == "male":
        cmd.extend(["-v", "en+m3"])
    cmd.append(text)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    if proc.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size <= 44:
        raise RuntimeError(
            f"AUDIO_SYNTHESIS_UNAVAILABLE: espeak-ng synthesis failed ({proc.stderr.strip() or 'no audio output'})."
        )
    return wav_path.read_bytes()


def _synthesize_windows_sapi_wav(clean_text: str, selector: str, wav_path: Path) -> bytes:
    """Windows-only SAPI speech synthesis (never called on Linux/POSIX)."""
    if sys.platform != "win32":
        raise RuntimeError(
            "AUDIO_SYNTHESIS_UNAVAILABLE: Windows SAPI is unsupported on non-Windows platforms."
        )

    is_female = selector.lower() in ("female", "rachel", "bella", "domi", "elli")
    gender_hint = "Female" if is_female else "Male"
    ps_script = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$target = $env:KEYSTONE_TTS_VOICE; "
        "$matched = $false; "
        "if ($target) { "
        "  foreach ($v in $synth.GetInstalledVoices()) { "
        "    if ($v.Enabled -and $v.VoiceInfo.Name -eq $target) { $synth.SelectVoice($v.VoiceInfo.Name); $matched = $true; break } "
        "  } "
        "} "
        "if (-not $matched) { $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::" + gender_hint + ") } "
        "$synth.SetOutputToWaveFile($env:KEYSTONE_TTS_OUT); "
        "$synth.Speak($env:KEYSTONE_TTS_TEXT); "
        "$synth.Dispose();"
    )
    env = dict(os.environ)
    env["KEYSTONE_TTS_OUT"] = str(wav_path)
    env["KEYSTONE_TTS_TEXT"] = clean_text
    env["KEYSTONE_TTS_VOICE"] = selector
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
    )
    if proc.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size <= 44:
        raise RuntimeError(
            f"AUDIO_SYNTHESIS_UNAVAILABLE: Real speech synthesis failed ({proc.stderr.strip() or 'no audio output'}). "
            "Configure ELEVENLABS_API_KEY for cloud neural voices."
        )
    return wav_path.read_bytes()


def synthesize_speech_wav(text: str, voice_type: str = "female") -> bytes:
    """
    Real-time local speech synthesis using POSIX-compatible engines (`piper` or `espeak-ng`)
    first, falling back to Windows SAPI strictly on `win32` when POSIX engines are absent,
    and raising a deterministic RuntimeError when no local TTS engine is available.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("EMPTY_SPEECH_TEXT: Speech synthesis requires non-empty text")

    selector = (voice_type or "").strip()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        piper_voices = _find_piper_voices()
        piper_bin = shutil.which("piper")
        if piper_bin and piper_voices:
            chosen = next(
                (v for v in piper_voices if v.get("voice_id") == selector or v.get("name") == selector),
                piper_voices[0],
            )
            return _synthesize_piper_wav(piper_bin, str(chosen["model_path"]), clean_text, wav_path)

        espeak_bin = _find_espeak_binary()
        if espeak_bin:
            return _synthesize_espeak_wav(espeak_bin, clean_text, selector, wav_path)

        if sys.platform == "win32":
            return _synthesize_windows_sapi_wav(clean_text, selector, wav_path)

        raise RuntimeError(
            "AUDIO_SYNTHESIS_UNAVAILABLE: No POSIX local TTS engine (piper or espeak-ng) is installed "
            "and ELEVENLABS_API_KEY is not configured."
        )
    finally:
        try:
            if wav_path.exists():
                wav_path.unlink()
        except Exception:
            pass


def list_local_tts_voices() -> List[Dict[str, Any]]:
    """
    Queries installed local TTS voices in priority order:
      1. Piper ONNX models (when `piper` + model path/dir configured)
      2. eSpeak NG / eSpeak (`espeak-ng --voices`)
      3. Windows SAPI (`System.Speech`) strictly on `win32`
    Never returns hardcoded static voice catalogs and never invokes powershell on Linux/POSIX.
    """
    piper_voices = _find_piper_voices()
    if piper_voices:
        return piper_voices

    espeak_bin = _find_espeak_binary()
    if espeak_bin:
        return _list_espeak_voices(espeak_bin)

    if sys.platform == "win32":
        return _list_windows_sapi_voices()

    raise RuntimeError(
        "AUDIO_VOICES_UNAVAILABLE: No POSIX local TTS engine (piper or espeak-ng) found "
        "and ELEVENLABS_API_KEY is not set."
    )


def list_local_sapi_voices() -> List[Dict[str, Any]]:
    """Backward-compatible alias delegating to POSIX-first `list_local_tts_voices`."""
    return list_local_tts_voices()


class ElevenLabsClient:
    """ElevenLabs & POSIX-compatible local TTS client (zero silent fallbacks or fake voice lists)."""

    @staticmethod
    def is_configured() -> bool:
        return bool(get_elevenlabs_api_key())

    @classmethod
    def list_voices(cls) -> List[Dict[str, Any]]:
        api_key = get_elevenlabs_api_key()
        if not api_key:
            return list_local_tts_voices()

        try:
            req = urllib.request.Request(f"{ELEVENLABS_API_URL}/voices", headers={"xi-api-key": api_key})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
                remote_voices = data.get("voices", [])
                if not remote_voices:
                    raise RuntimeError("ELEVENLABS_EMPTY_VOICES: ElevenLabs /v1/voices returned 0 voices")
                results = []
                for v in remote_voices:
                    results.append({
                        "voice_id": v.get("voice_id"),
                        "name": v.get("name"),
                        "category": v.get("category", "cloned"),
                        "description": v.get("description") or (v.get("labels", {}).get("description", "")),
                        "preview_url": v.get("preview_url") or "",
                        "gender": v.get("labels", {}).get("gender", "neutral"),
                        "accent": v.get("labels", {}).get("accent", "standard"),
                        "provider": "elevenlabs",
                    })
                return results
        except urllib.error.HTTPError as exc:
            body = exc.read()[:600].decode("utf-8", errors="replace")
            raise RuntimeError(f"ELEVENLABS_HTTP_{exc.code}: {body or exc.reason}") from exc
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"ELEVENLABS_VOICES_FAILED: {type(exc).__name__}: {exc}") from exc

    @classmethod
    def generate_speech(
        cls,
        text: str,
        voice_id: Optional[str] = None,
        model_id: str = ELEVENLABS_DEFAULT_MODEL,
        voice_settings: Optional[Dict[str, Any]] = None,
        timeout: float = 25.0,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """Synthesizes speech from text. Returns (audio_bytes, mime_type, metadata)."""
        api_key = get_elevenlabs_api_key()
        resolved_settings = voice_settings or {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.20,
            "use_speaker_boost": True
        }

        if api_key:
            resolved_voice = (voice_id or "").strip()
            if not resolved_voice:
                voices = cls.list_voices()
                resolved_voice = str(voices[0]["voice_id"])
            url = f"{ELEVENLABS_API_URL}/text-to-speech/{resolved_voice}"
            payload = json.dumps({
                "text": text,
                "model_id": model_id,
                "voice_settings": resolved_settings
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("xi-api-key", api_key)
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "audio/mpeg")

            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    audio_data = resp.read()
                    if not audio_data:
                        raise RuntimeError("ELEVENLABS_EMPTY_AUDIO: ElevenLabs returned 0 audio bytes")
                    return audio_data, "audio/mpeg", {
                        "provider": "elevenlabs",
                        "voice_id": resolved_voice,
                        "voice_name": resolved_voice,
                        "model_id": model_id,
                        "voice_settings": resolved_settings,
                        "byte_size": len(audio_data)
                    }
            except urllib.error.HTTPError as exc:
                body = exc.read()[:600].decode("utf-8", errors="replace")
                raise RuntimeError(f"ELEVENLABS_HTTP_{exc.code}: {body or exc.reason}") from exc
            except Exception as exc:
                if isinstance(exc, RuntimeError):
                    raise
                raise RuntimeError(f"ELEVENLABS_SYNTHESIS_FAILED: {type(exc).__name__}: {exc}") from exc

        # POSIX-first local TTS fallback when ELEVENLABS_API_KEY is not configured
        local_voices = list_local_tts_voices()
        requested = (voice_id or "").strip()
        selected = next(
            (v for v in local_voices if v.get("voice_id") == requested or v.get("name") == requested),
            local_voices[0],
        )
        voice_selector = str(selected.get("voice_id") or selected.get("name") or selected.get("gender") or "female")
        wav_data = synthesize_speech_wav(text, voice_type=voice_selector)
        return wav_data, "audio/wav", {
            "provider": selected.get("provider", "local_tts"),
            "voice_id": selected["voice_id"],
            "voice_name": selected["name"],
            "voice_settings": resolved_settings,
            "byte_size": len(wav_data)
        }


elevenlabs_client = ElevenLabsClient()
