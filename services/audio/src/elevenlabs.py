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

# Curated Premier ElevenLabs Voices Catalog
PREMIER_VOICES = [
    {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "name": "Rachel",
        "category": "premade",
        "gender": "female",
        "accent": "American",
        "description": "Calm, professional, versatile female voice ideal for narration and dialogue.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/21m00Tcm4TlvDq8ikWAM/df6788f9-5c96-470d-8312-aab3b3d8f50a.mp3",
    },
    {
        "voice_id": "pNInz6obpgDQGcFmaJgB",
        "name": "Adam",
        "category": "premade",
        "gender": "male",
        "accent": "American",
        "description": "Deep, warm, engaging voice suited for storytelling, commercials, and audiobooks.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/pNInz6obpgDQGcFmaJgB/6734d750-da3d-43c7-8213-9a84f33d02b8.mp3",
    },
    {
        "voice_id": "ErXwobaYiN019PkySvjV",
        "name": "Antoni",
        "category": "premade",
        "gender": "male",
        "accent": "American",
        "description": "Dramatic, well-rounded voice with rich expressive depth.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/ErXwobaYiN019PkySvjV/38d8f8f0-041e-47f4-b490-e51c8a779147.mp3",
    },
    {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "name": "Bella",
        "category": "premade",
        "gender": "female",
        "accent": "American",
        "description": "Soft, expressive young female voice ideal for cinematic intimacy.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/EXAVITQu4vr4xnSDxMaL/0152fdf5-94f2-495a-9976-9f848c1e8284.mp3",
    },
    {
        "voice_id": "VR6AewLTigWG4xSOukaG",
        "name": "Arnold",
        "category": "premade",
        "gender": "male",
        "accent": "American",
        "description": "Crisp, authoritative, clear male narrator with commanding presence.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/VR6AewLTigWG4xSOukaG/0819c9e5-9c5c-42cb-b0eb-8324483be992.mp3",
    },
    {
        "voice_id": "AZnzlk1XvdvUeBnXmlld",
        "name": "Domi",
        "category": "premade",
        "gender": "female",
        "accent": "American",
        "description": "Strong, engaging, high-energy young female voice.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/AZnzlk1XvdvUeBnXmlld/507e1523-a550-4228-a320-b467ec6a6401.mp3",
    },
    {
        "voice_id": "MF3mGyEYCl7XYWbV9V6O",
        "name": "Elli",
        "category": "premade",
        "gender": "female",
        "accent": "American",
        "description": "Clear, youthful, emotional storytelling female voice.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/MF3mGyEYCl7XYWbV9V6O/d86c757c-3b32-4740-9a3c-b26a10051e5e.mp3",
    },
    {
        "voice_id": "TxGEqnHWrfWFTfGW9XjX",
        "name": "Josh",
        "category": "premade",
        "gender": "male",
        "accent": "American",
        "description": "Deep, resonant, classic Hollywood narrative voice.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/TxGEqnHWrfWFTfGW9XjX/3a39e6a2-9b2d-456d-b20f-5e921d72379b.mp3",
    },
    {
        "voice_id": "yoZ06aMxZJJ28mfd3POQ",
        "name": "Sam",
        "category": "premade",
        "gender": "male",
        "accent": "American",
        "description": "Dynamic, gritty, raspy male character voice for intense dialogue.",
        "preview_url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/yoZ06aMxZJJ28mfd3POQ/1c4d29f8-7788-4674-8b6a-93f4e3c922a7.mp3",
    },
]


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

    is_female = voice_type.lower() in ("female", "rachel", "bella", "domi", "elli")
    gender_hint = "Female" if is_female else "Male"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        ps_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::{gender_hint}); "
            "$synth.SetOutputToWaveFile($env:KEYSTONE_TTS_OUT); "
            "$synth.Speak($env:KEYSTONE_TTS_TEXT); "
            "$synth.Dispose();"
        )
        env = dict(os.environ)
        env["KEYSTONE_TTS_OUT"] = str(wav_path)
        env["KEYSTONE_TTS_TEXT"] = clean_text
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


class ElevenLabsClient:
    """ElevenLabs TTS client with automatic fail-safe fallback."""

    @staticmethod
    def is_configured() -> bool:
        return bool(get_elevenlabs_api_key())

    @classmethod
    def list_voices(cls) -> List[Dict[str, Any]]:
        api_key = get_elevenlabs_api_key()
        if not api_key:
            return PREMIER_VOICES

        try:
            req = urllib.request.Request(f"{ELEVENLABS_API_URL}/voices", headers={"xi-api-key": api_key})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
                remote_voices = data.get("voices", [])
                if remote_voices:
                    results = []
                    for v in remote_voices:
                        results.append({
                            "voice_id": v.get("voice_id"),
                            "name": v.get("name"),
                            "category": v.get("category", "cloned"),
                            "description": v.get("description") or (v.get("labels", {}).get("description", "")),
                            "preview_url": v.get("preview_url") or "",
                            "gender": v.get("labels", {}).get("gender", "neutral"),
                            "accent": v.get("labels", {}).get("accent", "standard")
                        })
                    return results
        except Exception:
            pass
        return PREMIER_VOICES

    @classmethod
    def generate_speech(
        cls,
        text: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
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
            try:
                url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
                payload = json.dumps({
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": resolved_settings
                }).encode("utf-8")

                req = urllib.request.Request(url, data=payload, method="POST")
                req.add_header("xi-api-key", api_key)
                req.add_header("Content-Type", "application/json")
                req.add_header("Accept", "audio/mpeg")

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    audio_data = resp.read()
                    if audio_data:
                        return audio_data, "audio/mpeg", {
                            "provider": "elevenlabs",
                            "voice_id": voice_id,
                            "model_id": model_id,
                            "voice_settings": resolved_settings,
                            "byte_size": len(audio_data)
                        }
            except Exception as exc:
                if os.getenv("ELEVENLABS_STRICT", "0") == "1":
                    raise

        # High-fidelity PCM WAV fallback synthesis
        voice_meta = next((v for v in PREMIER_VOICES if v["voice_id"] == voice_id), {})
        gender = voice_meta.get("gender", "female")
        wav_data = synthesize_speech_wav(text, voice_type=gender)
        return wav_data, "audio/wav", {
            "provider": "keystone_speech_synth",
            "voice_id": voice_id,
            "voice_name": voice_meta.get("name", "Rachel"),
            "voice_settings": resolved_settings,
            "byte_size": len(wav_data)
        }


elevenlabs_client = ElevenLabsClient()
