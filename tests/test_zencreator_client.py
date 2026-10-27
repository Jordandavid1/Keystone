"""Offline tests for scripts/zencreator_client.py.

The HTTP layer is stubbed so these run without network access or an API key.
Payload shapes come from the live tool catalogue captured from
``GET /api/public/v1/tools``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.zencreator_client import (  # noqa: E402
    NSFW_IMAGE_MODELS,
    NSFW_VIDEO_MODELS,
    ZenCreatorClient,
    ZenCreatorError,
    output_urls,
)

# Recorded from a real generation (POST -> poll -> result).
REAL_RESULT = {
    "id": "89d17c30-0260-499a-8431-0a7b49ecf8a1",
    "status": "succeeded",
    "error": None,
    "text": None,
    "outputs": [
        {
            "asset_id": "b2e0646d-447e-4e4c-ba27-a586f2fdff34",
            "url": "https://storage.zencreator.pro/preview_b2e0646d447e4e4cba27a586f2fdff34.webp",
            "download_url": "https://storage.zencreator.pro/c6ef554b4cc34203b1e7ec68ee32fec6.jpeg",
        }
    ],
}


class Recorder:
    """Stub transport that records requests and replays queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, method, url, headers, body):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": json.loads(body) if body and headers.get("Content-Type") == "application/json" else body,
            }
        )
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)


def make_client(responses):
    rec = Recorder(responses)
    return ZenCreatorClient("zc_live_test", transport=rec), rec


def test_generate_image_builds_by_prompt_payload():
    client, rec = make_client([(201, {"id": "g1", "status": "queued"})])

    client.generate_image("portrait, golden hour", model="Z_IMAGE_SPICY", ratio="3:4")

    call = rec.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/public/v1/generations")
    assert call["headers"]["Authorization"] == "Bearer zc_live_test"
    assert call["body"] == {
        "tool": "by_prompt",
        "input": {"positive_prompt": "portrait, golden hour", "model": "Z_IMAGE_SPICY", "ratio": "3:4", "tier": "2K"},
    }


def test_none_values_are_dropped_so_defaults_apply():
    client, rec = make_client([(201, {"id": "g1", "status": "queued"})])

    client.generate_image("x", negative_prompt=None, quality=None, width=None)

    assert "negative_prompt" not in rec.calls[0]["body"]["input"]
    assert "quality" not in rec.calls[0]["body"]["input"]


def test_nsfw_image_guard_rejects_censored_model():
    client, _ = make_client([])

    with pytest.raises(ValueError, match="not an NSFW image model"):
        client.generate_nsfw_image("x", model="NANO_BANANA")


def test_nsfw_video_guard_accepts_only_nsfw_video_models():
    client, rec = make_client([(201, {"id": "v1", "status": "queued"})])

    client.generate_nsfw_video("x", model=NSFW_VIDEO_MODELS[0], duration=5)

    body = rec.calls[0]["body"]
    assert body["tool"] == "text_to_video"
    assert body["input"]["model"] == "wan@3.0-nsfw"
    assert body["input"]["duration"] == 5

    with pytest.raises(ValueError, match="not an NSFW video model"):
        client.generate_nsfw_video("x", model="wan@2.7")


def test_photo_tool_payloads_match_schema():
    client, rec = make_client(
        [
            (201, {"id": "a", "status": "queued"}),
            (201, {"id": "b", "status": "queued"}),
            (201, {"id": "c", "status": "queued"}),
            (201, {"id": "d", "status": "queued"}),
        ]
    )

    client.generate_from_reference(ref_asset="r", character_assets=["c1", "c2"], strength=0.6)
    client.run_photoshoot(face_ref="f", body_ref="b", image_count=4)
    client.generate_face(gender="female", age=27, origin="nordic", hair_color="red")
    client.edit_image(image_assets=["i1"], prompt="add a hat", model="FLUX_KLEIN_NSFW")

    ref, shoot, face, edit = (c["body"] for c in rec.calls)
    assert ref == {"tool": "by_ref", "input": {"ref_asset": "r", "character_assets": ["c1", "c2"], "strength": 0.6}}
    assert shoot == {
        "tool": "photoshoot",
        "input": {"face_ref": "f", "body_ref": "b", "prompt": "", "image_count": 4},
    }
    assert face["tool"] == "facegen"
    assert face["input"]["gender"] == "female" and face["input"]["age"] == 27
    assert edit["tool"] == "image_editor"
    assert edit["input"]["image_assets"] == ["i1"]


def test_video_tool_payloads_match_schema():
    client, rec = make_client(
        [
            (201, {"id": "a", "status": "queued"}),
            (201, {"id": "b", "status": "queued"}),
            (201, {"id": "c", "status": "queued"}),
            (201, {"id": "d", "status": "queued"}),
        ]
    )

    client.image_to_video(ref_asset="img", prompt="slow pan", duration=8)
    client.video_to_video(video_asset="vid", mode="animate_nsfw")
    client.lipsync(image_asset="face", audio_asset="voice", model="GENERAL_NSFW")
    client.merge_videos(clips=["c1", "c2"])

    i2v, v2v, lip, merge = (c["body"] for c in rec.calls)
    assert i2v["tool"] == "videogen"
    assert i2v["input"]["duration"] == 8
    assert v2v["tool"] == "video2video" and v2v["input"]["mode"] == "animate_nsfw"
    assert lip == {
        "tool": "lipsync",
        "input": {"image_asset": "face", "audio_asset": "voice", "model": "GENERAL_NSFW"},
    }
    assert merge == {"tool": "video_merger", "input": {"clips": ["c1", "c2"]}}


def test_upscaler_faceswap_collab_payloads():
    client, rec = make_client(
        [
            (201, {"id": "a", "status": "queued"}),
            (201, {"id": "b", "status": "queued"}),
            (201, {"id": "c", "status": "queued"}),
        ]
    )

    client.upscale_image(image_asset="img", target_resolution="4K")
    client.face_swap(ref_asset="photo", face_asset="face", tier="2K")
    client.collab_image(asset_image_1="a1", asset_image_2="a2")

    up, swap, collab = (c["body"] for c in rec.calls)
    assert up == {"tool": "upscaler", "input": {"image_asset": "img", "target_resolution": "4K"}}
    assert swap == {"tool": "faceswap", "input": {"ref_asset": "photo", "face_asset": "face", "tier": "2K"}}
    assert collab == {"tool": "collaber", "input": {"asset_image_1": "a1", "asset_image_2": "a2"}}


def test_video_to_video_requires_a_source():
    client, _ = make_client([])

    with pytest.raises(ValueError, match="needs one of"):
        client.video_to_video(mode="animate_sfw")


def test_video_merger_clip_bounds():
    client, _ = make_client([])

    with pytest.raises(ValueError, match="2-5"):
        client.merge_videos(clips=["only-one"])


def test_wait_polls_until_terminal(monkeypatch):
    client, rec = make_client(
        [
            (200, {"id": "g1", "status": "queued", "progress": 0, "error": None}),
            (200, {"id": "g1", "status": "processing", "progress": 40, "error": None}),
            (200, {"id": "g1", "status": "succeeded", "progress": 100, "error": None}),
        ]
    )
    monkeypatch.setattr("scripts.zencreator_client.time.sleep", lambda _s: None)

    seen = []
    final = client.wait("g1", interval=0, on_progress=seen.append)

    assert final["status"] == "succeeded"
    assert [s["progress"] for s in seen] == [0, 40, 100]
    assert len(rec.calls) == 3


def test_wait_times_out(monkeypatch):
    client, _ = make_client(
        [(200, {"id": "g1", "status": "processing", "progress": 10, "error": None})] * 3
    )
    monkeypatch.setattr("scripts.zencreator_client.time.sleep", lambda _s: None)
    clock = iter([0.0, 0.0, 5.0, 20.0])
    monkeypatch.setattr("scripts.zencreator_client.time.monotonic", lambda: next(clock, 999.0))

    with pytest.raises(ZenCreatorError, match="Timed out"):
        client.wait("g1", interval=0, timeout=1)


def test_run_returns_result_and_surfaces_urls(monkeypatch):
    client, _ = make_client(
        [
            (201, {"id": "g1", "status": "queued", "created_at": "2026-10-23T00:00:00Z"}),
            (200, {"id": "g1", "status": "succeeded", "progress": 100, "error": None}),
            (200, REAL_RESULT),
        ]
    )
    monkeypatch.setattr("scripts.zencreator_client.time.sleep", lambda _s: None)

    result = client.run("by_prompt", {"positive_prompt": "x", "ratio": "3:4"})

    assert result["status"] == "succeeded"
    assert output_urls(result) == ["https://storage.zencreator.pro/c6ef554b4cc34203b1e7ec68ee32fec6.jpeg"]


def test_run_raises_on_failed_generation(monkeypatch):
    client, _ = make_client(
        [
            (201, {"id": "g1", "status": "queued"}),
            (200, {"id": "g1", "status": "failed", "progress": 0, "error": "content policy"}),
            (200, {"id": "g1", "status": "failed", "outputs": [], "error": "content policy"}),
        ]
    )
    monkeypatch.setattr("scripts.zencreator_client.time.sleep", lambda _s: None)

    with pytest.raises(ZenCreatorError, match="content policy"):
        client.run("by_prompt", {"positive_prompt": "x"})


def test_http_error_is_wrapped_with_code_and_status():
    client, _ = make_client(
        [(422, {"error": {"code": "bad_request", "message": "input.ratio: invalid value"}})]
    )

    with pytest.raises(ZenCreatorError) as excinfo:
        client.generate_image("x", ratio="nope")

    assert excinfo.value.status == 422
    assert excinfo.value.code == "bad_request"
    assert "ratio" in str(excinfo.value)


def test_unauthorized_error():
    client, _ = make_client([(401, {"error": {"code": "unauthorized", "message": "Invalid API key"}})])

    with pytest.raises(ZenCreatorError) as excinfo:
        client.get_balance()

    assert excinfo.value.status == 401


def test_list_tools_flattens_numeric_ids_to_names():
    client, _ = make_client(
        [(200, {"tools": {"0": {"name": "run_any_llm"}, "3": {"name": "by_prompt"}}})]
    )

    tools = client.list_tools()

    assert list(tools) == ["run_any_llm", "by_prompt"]


def test_upload_asset_builds_multipart(tmp_path):
    file = tmp_path / "face.png"
    file.write_bytes(b"PNGDATA")
    client, rec = make_client([(200, {"asset_id": "a1"})])

    client.upload_asset(file)

    call = rec.calls[0]
    assert call["url"].endswith("/api/public/v1/assets")
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="face.png"' in call["body"]
    assert b"Content-Type: image/png" in call["body"]
    assert b"PNGDATA" in call["body"]


def test_idempotency_key_header():
    client, rec = make_client([(201, {"id": "g1", "status": "queued"})])

    client.start_generation("by_prompt", {"positive_prompt": "x"}, idempotency_key="abc123")

    assert rec.calls[0]["headers"]["Idempotency-Key"] == "abc123"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ZC_API_KEY", raising=False)

    with pytest.raises(ZenCreatorError, match="No API key"):
        ZenCreatorClient()


def test_nsfw_model_lists_exclude_censored_models():
    assert "NANO_BANANA" not in NSFW_IMAGE_MODELS
    assert "FLUX_KLEIN_NSFW" in NSFW_IMAGE_MODELS
    assert all(m for m in NSFW_VIDEO_MODELS)
