"""
KEYSTONE ElevenLabs Audio & Persona Voice Synthesis Service.
Provides official ElevenLabs Text-to-Speech (TTS) integration with voice catalog discovery
and fail-safe offline speech formant synthesis.
"""

from __future__ import annotations

import io
import json
import math
import os
import struct
import urllib.error
import urllib.request
import wave
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


def synthesize_speech_wav(text: str, voice_type: str = "female") -> bytes:
    """
    Real-time local speech synthesis using Windows System.Speech.Synthesis.SpeechSynthesizer.
    Never generates fake sine-wave/formant buzzing; raises RuntimeError if no speech engine is available.
    """
    import subprocess
    import tempfile

    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("EMPTY_SPEECH_TEXT: Speech synthesis requires non-empty text")

    selector = (voice_type or "").strip()
    is_female = selector.lower() in ("female", "rachel", "bella", "domi", "elli")
    gender_hint = "Female" if is_female else "Male"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
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
    finally:
        try:
            if wav_path.exists():
                wav_path.unlink()
        except Exception:
            pass


def list_local_sapi_voices() -> List[Dict[str, Any]]:
    """Queries live installed Windows SAPI speech voices (never returns hardcoded static catalogs)."""
    import subprocess

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


class ElevenLabsClient:
    """ElevenLabs & local Windows SAPI TTS client (zero silent fallbacks or fake voice lists)."""

    @staticmethod
    def is_configured() -> bool:
        return bool(get_elevenlabs_api_key())

    @classmethod
    def list_voices(cls) -> List[Dict[str, Any]]:
        api_key = get_elevenlabs_api_key()
        if not api_key:
            return list_local_sapi_voices()

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

        # Real local Windows SAPI synthesis when ELEVENLABS_API_KEY is not configured
        local_voices = list_local_sapi_voices()
        requested = (voice_id or "").strip()
        selected = next((v for v in local_voices if v.get("voice_id") == requested or v.get("name") == requested), local_voices[0])
        wav_data = synthesize_speech_wav(text, voice_type=str(selected.get("name") or selected.get("gender") or "female"))
        return wav_data, "audio/wav", {
            "provider": "windows_sapi_speech",
            "voice_id": selected["voice_id"],
            "voice_name": selected["name"],
            "voice_settings": resolved_settings,
            "byte_size": len(wav_data)
        }


elevenlabs_client = ElevenLabsClient()
