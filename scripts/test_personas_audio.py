"""
Verification script for Personas and ElevenLabs Audio APIs.
Tests end-to-end functionality including database persistence, voice catalog,
speech synthesis, asset registration, and persona endpoints.
"""

import sys
import asyncio
import uuid
from pathlib import Path
from starlette.testclient import TestClient

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.server import app
from apps.api.src.db.session import init_db


def main():
    print("[1] Initializing Database Schema...")
    asyncio.run(init_db())
    print("[+] DB Initialized.")

    client = TestClient(app)

    # 1.1 Register Test User for Auth Token
    print("\n[1.1] Registering test user for authentication...")
    user_email = f"persona_test_{uuid.uuid4().hex[:6]}@keystonestudio.ai"
    reg_resp = client.post("/v1/auth/register", json={
        "email": user_email,
        "password": "KeystoneSecretPassword123!",
        "display_name": "Auteur Test Director"
    })
    assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[+] User registered. Token acquired: {token[:16]}...")

    # 1. Test Audio Config
    print("\n[2] Testing GET /v1/audio/config...")
    resp = client.get("/v1/audio/config")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    config = resp.json()
    print(f"[+] Audio Config: {config}")
    assert config["provider"] == "elevenlabs"

    # 2. Test Audio Voices
    print("\n[3] Testing GET /v1/audio/voices")
    resp = client.get("/v1/audio/voices")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    voices_data = resp.json()
    voices = voices_data["voices"]
    print(f"[+] Found {len(voices)} voices. Premier voice: {voices[0]['name']} ({voices[0]['voice_id']})")
    assert len(voices) >= 8

    # 3. Test Direct Speech Synthesis
    print("\n[4] Testing POST /v1/audio/speech...")
    speech_payload = {
        "text": "Welcome to Keystone Multimodal Creative Studio. All systems operational.",
        "voice_id": voices[0]["voice_id"],
        "save_asset": True
    }
    resp = client.post("/v1/audio/speech", json=speech_payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    speech_res = resp.json()
    print(f"[+] Speech synthesized: asset_id={speech_res.get('asset_id')}, mime={speech_res.get('mime_type')}, bytes={speech_res.get('byte_size')}")
    assert speech_res["media_type"] == "audio"
    assert speech_res["byte_size"] > 0
    audio_asset_id = speech_res["asset_id"]

    # Verify audio content can be downloaded
    dl_url = speech_res["download_url"]
    dl_resp = client.get(dl_url, headers=headers)
    assert dl_resp.status_code == 200, f"Failed to download audio content: {dl_resp.status_code}"
    assert len(dl_resp.content) == speech_res["byte_size"]
    print(f"[+] Verified audio asset download ({len(dl_resp.content)} bytes retrieved).")

    # 4. Test Persona Creation
    print("\n[5] Testing POST /v1/personas...")
    persona_payload = {
        "name": "Aria Vance",
        "description": "Lead Cinematic Director and Cyberpunk Narrative Designer.",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "voice_name": "Rachel (American Calm)",
        "personality_traits": ["visionary", "cinematic", "sharp", "commanding"],
        "system_prompt": "You are Aria Vance, an auteur cinematic director crafting neo-noir sci-fi.",
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.80,
            "style": 0.25
        }
    }
    resp = client.post("/v1/personas", json=persona_payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    created = resp.json()["persona"]
    persona_id = created["id"]
    print(f"[+] Persona created: {created['name']} (ID: {persona_id})")
    assert created["name"] == "Aria Vance"
    assert "cinematic" in created["personality_traits"]

    # 5. Test List Personas
    print("\n[6] Testing GET /v1/personas...")
    resp = client.get("/v1/personas", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    listing = resp.json()
    print(f"[+] Total personas listed: {listing['count']}")
    assert any(p["id"] == persona_id for p in listing["personas"])

    # 6. Test Get Persona
    print(f"\n[7] Testing GET /v1/personas/{persona_id}...")
    resp = client.get(f"/v1/personas/{persona_id}", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    fetched = resp.json()["persona"]
    assert fetched["id"] == persona_id
    print(f"[+] Persona fetched successfully: {fetched['name']}")

    # 7. Test Persona Speak
    print(f"\n[8] Testing POST /v1/personas/{persona_id}/speak...")
    speak_payload = {
        "text": "Every frame tells a story. Look at the lighting in the lower quadrant—let's push the anamorphic flare."
    }
    resp = client.post(f"/v1/personas/{persona_id}/speak", json=speak_payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    speak_res = resp.json()
    print(f"[+] Persona speech generated: asset_id={speak_res['asset_id']}, bytes={speak_res['byte_size']}, provider={speak_res['provider']}")
    assert speak_res["persona_id"] == persona_id
    assert speak_res["media_type"] == "audio"
    assert speak_res["byte_size"] > 0

    # Verify persona audio content retrieval
    dl_url = speak_res["download_url"]
    dl_resp = client.get(dl_url, headers=headers)
    assert dl_resp.status_code == 200, f"Download failed: {dl_resp.status_code}"
    print(f"[+] Verified persona audio content download ({len(dl_resp.content)} bytes).")

    # 8. Test Persona Update
    print(f"\n[9] Testing PUT /v1/personas/{persona_id}...")
    update_payload = {
        "name": "Aria Vance (Director's Cut)",
        "personality_traits": ["visionary", "cinematic", "sharp", "perfectionist"]
    }
    resp = client.put(f"/v1/personas/{persona_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    updated = resp.json()["persona"]
    assert updated["name"] == "Aria Vance (Director's Cut)"
    assert "perfectionist" in updated["personality_traits"]
    print(f"[+] Persona successfully updated: {updated['name']}")

    # 9. Test Persona Deletion
    print(f"\n[10] Testing DELETE /v1/personas/{persona_id}...")
    resp = client.delete(f"/v1/personas/{persona_id}", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    print(f"[+] Persona deleted successfully.")

    # Confirm deletion
    resp = client.get(f"/v1/personas/{persona_id}", headers=headers)
    assert resp.status_code == 404
    print(f"[+] Confirmed 404 for deleted persona.")

    print("\n" + "="*60)
    print("ALL PERSONAS & ELEVENLABS AUDIO API TESTS PASSED 100%!")
    print("="*60)


if __name__ == "__main__":
    main()
