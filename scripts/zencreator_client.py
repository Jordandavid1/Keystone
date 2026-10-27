"""ZenCreator public API client.

Covers the photo generation, video generation and NSFW-capable tools behind
``https://api.zencreator.pro/api/public/v1``.

Stdlib only on purpose: the repo pins fastapi/uvicorn/pydantic/pytest and adding
an HTTP dependency for one integration would be gratuitous.

Auth
----
Every request needs ``Authorization: Bearer <key>`` where the key looks like
``zc_live_<key_id>_<secret>``. Keys are created at
https://app.zencreator.pro/api-keys with scopes ``read`` and/or ``generate``.
Read the key from the environment, never hardcode it:

    export ZC_API_KEY=zc_live_...

Generation lifecycle
--------------------
Generations are asynchronous and billed per accepted generation (refunded on
failure)::

    gen = client.start_generation("by_prompt", {...})   # -> queued
    client.wait(gen["id"])                              # -> succeeded
    result = client.get_result(gen["id"])               # -> outputs[].download_url

Status flow: ``queued`` -> ``processing`` -> ``succeeded`` | ``partial`` | ``failed``.

CLI
---
    python scripts/zencreator_client.py tools
    python scripts/zencreator_client.py image "portrait, golden hour" --ratio 3:4
    python scripts/zencreator_client.py nsfw-image "..." --model Z_IMAGE_SPICY
    python scripts/zencreator_client.py t2v "a slow dolly shot" --duration 5
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

DEFAULT_BASE_URL = "https://api.zencreator.pro"
API_PREFIX = "/api/public/v1"

TERMINAL_STATUSES = frozenset({"succeeded", "partial", "failed"})

# ---------------------------------------------------------------------------
# Model catalogues
# ---------------------------------------------------------------------------

#: Image models that will produce full NSFW content from a text prompt.
#: ``FLUX_KLEIN_NSFW`` and ``Z_IMAGE_SPICY`` are the only two built for it;
#: the rest of the NSFW-marked models transform NSFW references instead.
NSFW_IMAGE_MODELS: tuple[str, ...] = (
    "FLUX_KLEIN_NSFW",
    "Z_IMAGE_SPICY",
    "GENERAL_NSFW",
    "KREA_2",
)

#: Image models that will not refuse, but do not invent full NSFW anatomy.
UNCENSORED_IMAGE_MODELS: tuple[str, ...] = (
    "WAN_2_7_IMAGE",
    "WAN_2_7_IMAGE_PRO",
    "QWEN_IMAGE",
    "QWEN_IMAGE_PRO",
    "SEEDREAM_5",
    "SEEDREAM_5_PRO",
)

#: Censored, high-fidelity image models.
CENSORED_IMAGE_MODELS: tuple[str, ...] = (
    "NANO_BANANA",
    "NANO_BANANA_2_1",
    "GPT_IMAGE_2_5_FLARE",
    "GPT_IMAGE_2_5_SUNBURST",
    "IDEOGRAM_4_5",
    "GENERAL_SFW",
)

#: Video models with an explicit NSFW variant.
NSFW_VIDEO_MODELS: tuple[str, ...] = (
    "wan@3.0-nsfw",
    "wan@3.0-prime-nsfw",
    "wan@2.7-nsfw",
)

#: ``video2video`` modes that expose NSFW behaviour.
NSFW_VIDEO_MODES: tuple[str, ...] = (
    "animate_nsfw",
    "replace_nsfw",
    "seedance_2_0_nsfw",
    "seedance_2_0_fast_nsfw",
    "seedance_2_0_mini_nsfw",
    "seedance_2_5_nsfw",
    "wan3_0_nsfw",
    "wan3_0_prime_nsfw",
)

#: ``lipsync`` models; ``GENERAL_NSFW`` is the uncensored one.
LIPSYNC_MODELS: tuple[str, ...] = ("GENERAL_NSFW", "OMNIHUMAN")

VIDEO_RATIOS: tuple[str, ...] = ("16:9", "1:1", "21:9", "3:4", "4:3", "9:16", "adaptive")
IMAGE_RATIOS: tuple[str, ...] = (
    "16:9",
    "1:1",
    "1:2",
    "1:3",
    "1:4",
    "1:8",
    "21:9",
    "2:1",
    "2:3",
    "3:1",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "9:21",
)
RESOLUTIONS: tuple[str, ...] = ("480p", "720p", "1080p")
TIERS: tuple[str, ...] = ("1K", "2K", "4K")

#: ``videogen``/``video2video`` accept ``-1`` for "let the model decide".
DURATIONS: tuple[int, ...] = (-1, 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 24, 25, 26, 28, 30)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ZenCreatorError(RuntimeError):
    """An API call failed.

    ``status`` is the HTTP status (or ``None`` for transport failures), ``code``
    is the API's machine-readable error code when present.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.body = body


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ZenCreatorClient:
    """Thin synchronous client for the ZenCreator public API.

    Pass ``transport`` to swap the HTTP layer (tests do this); it must accept
    ``(method, url, headers, body)`` and return ``(status, payload)``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        transport: Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, Any]] | None = None,
    ) -> None:
        key = api_key or os.environ.get("ZC_API_KEY")
        if not key and transport is None:
            raise ZenCreatorError(
                "No API key. Set ZC_API_KEY or pass api_key=... "
                "(create one at https://app.zencreator.pro/api-keys)."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport

    # -- transport ---------------------------------------------------------

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        raw: tuple[bytes, str] | None = None,
        query: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            clean = {k: v for k, v in query.items() if v is not None}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean)}"

        headers = self._headers(extra_headers)
        payload: bytes | None = None
        if raw is not None:
            payload, content_type = raw
            headers["Content-Type"] = content_type
        elif body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if self._transport is not None:
            status, data = self._transport(method, url, headers, payload)
        else:
            status, data = self._http(method, url, headers, payload)

        if status >= 400:
            code = None
            message = f"HTTP {status}"
            if isinstance(data, Mapping):
                err = data.get("error")
                if isinstance(err, Mapping):
                    code = err.get("code")
                    message = err.get("message") or message
                elif isinstance(err, str):
                    message = err
                elif data.get("message"):
                    message = str(data["message"])
            raise ZenCreatorError(message, status=status, code=code, body=data)
        return data

    def _http(
        self, method: str, url: str, headers: Mapping[str, str], payload: bytes | None
    ) -> tuple[int, Any]:
        request = urllib.request.Request(url, data=payload, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, _decode(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _decode(exc.read())
        except urllib.error.URLError as exc:  # pragma: no cover - network failure
            raise ZenCreatorError(f"Request failed: {exc.reason}") from exc

    # -- metadata ----------------------------------------------------------

    def list_tools(self) -> dict[str, Any]:
        """Return the tool catalogue keyed by tool name."""
        data = self._request("GET", f"{API_PREFIX}/tools")
        tools = data.get("tools", data) if isinstance(data, Mapping) else data
        if isinstance(tools, Mapping):
            return {
                (tool.get("name") or str(tool_id)): tool
                for tool_id, tool in tools.items()
            }
        return {tool["name"]: tool for tool in tools}

    def get_tool(self, tool_name: str) -> dict[str, Any]:
        """Return one tool, including its ``input_schema`` and ``output_schema``."""
        return self._request("GET", f"{API_PREFIX}/tools/{urllib.parse.quote(tool_name)}")

    def get_balance(self) -> int:
        """Return the credit balance."""
        data = self._request("GET", f"{API_PREFIX}/balance")
        return int(data.get("credits", 0)) if isinstance(data, Mapping) else int(data)

    def list_transactions(self, **query: Any) -> Any:
        return self._request("GET", f"{API_PREFIX}/transactions", query=query)

    def list_templates(self, *, page: int = 1, limit: int = 10, **query: Any) -> dict[str, Any]:
        return self._request(
            "GET", f"{API_PREFIX}/templates", query={"page": page, "limit": limit, **query}
        )

    def get_template(self, template_id: str) -> dict[str, Any]:
        return self._request(
            "GET", f"{API_PREFIX}/templates/{urllib.parse.quote(template_id)}"
        )

    def list_loras(self, **query: Any) -> Any:
        return self._request("GET", f"{API_PREFIX}/loras", query=query)

    def list_photoshoot_categories(self) -> Any:
        return self._request("GET", f"{API_PREFIX}/photoshoot-categories")

    # -- assets ------------------------------------------------------------

    def upload_asset(self, path: str | Path, *, field: str = "file") -> dict[str, Any]:
        """Upload a local file and return the asset record.

        The endpoint is ``multipart/form-data``; JSON bodies are rejected with
        ``400 Invalid multipart/form-data``.
        """
        path = Path(path)
        data = path.read_bytes()
        boundary = f"----zencreator{uuid.uuid4().hex}"
        content_type = _guess_content_type(path.suffix)
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                data,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        return self._request(
            "POST",
            f"{API_PREFIX}/assets",
            raw=(body, f"multipart/form-data; boundary={boundary}"),
        )

    # -- generations -------------------------------------------------------

    def start_generation(
        self,
        tool: str,
        inputs: Mapping[str, Any],
        *,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Queue one generation. Returns ``{"id", "status", "created_at"}``.

        ``inputs`` is validated server-side against the tool's ``input_schema``
        before credits are charged; invalid payloads raise ``ZenCreatorError``
        with status 422.
        """
        body: dict[str, Any] = {"tool": tool, "input": dict(inputs)}
        if metadata is not None:
            body["metadata"] = dict(metadata)
        extra = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._request(
            "POST", f"{API_PREFIX}/generations", body=body, extra_headers=extra
        )

    def get_generation(self, generation_id: str) -> dict[str, Any]:
        """Poll one generation: ``{id, status, progress, error}``."""
        return self._request(
            "GET", f"{API_PREFIX}/generations/{urllib.parse.quote(generation_id)}"
        )

    def get_result(self, generation_id: str) -> dict[str, Any]:
        """Fetch outputs: ``{id, status, text, outputs[{asset_id,url,download_url}], error}``."""
        return self._request(
            "GET",
            f"{API_PREFIX}/generations/{urllib.parse.quote(generation_id)}/result",
        )

    def wait(
        self,
        generation_id: str,
        *,
        interval: float = 5.0,
        timeout: float = 900.0,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Poll until the generation reaches a terminal status, then return it."""
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = self.get_generation(generation_id)
            status = str(last.get("status", ""))
            if on_progress is not None:
                on_progress(last)
            if status in TERMINAL_STATUSES:
                return last
            if time.monotonic() >= deadline:
                raise ZenCreatorError(
                    f"Timed out after {timeout:.0f}s waiting for generation "
                    f"{generation_id} (last status: {status or 'unknown'}).",
                    body=last,
                )
            time.sleep(interval)

    def run(
        self,
        tool: str,
        inputs: Mapping[str, Any],
        *,
        interval: float = 5.0,
        timeout: float = 900.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start, wait and return the finished result in one call.

        Raises ``ZenCreatorError`` when the generation ends ``failed``.
        """
        created = self.start_generation(tool, inputs, metadata=metadata)
        final = self.wait(created["id"], interval=interval, timeout=timeout)
        result = self.get_result(created["id"])
        if final.get("status") == "failed":
            raise ZenCreatorError(
                str(final.get("error") or "Generation failed"),
                body=result,
            )
        return result

    # -- photo generation --------------------------------------------------

    def generate_image(
        self,
        prompt: str,
        *,
        model: str = "GENERAL_NSFW",
        ratio: str = "1:1",
        tier: str | None = "2K",
        negative_prompt: str | None = None,
        quality: str | None = None,
        transparent_background: bool | None = None,
        mode: str | None = None,
        thinking_level: str | None = None,
        web_search: bool | None = None,
        rewrite_prompt: bool | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        """Text-to-image (``by_prompt``). One image per call; ``batch_size`` is capped at 1."""
        inputs = _compact(
            positive_prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            ratio=ratio,
            tier=tier,
            quality=quality,
            transparent_background=transparent_background,
            mode=mode,
            thinking_level=thinking_level,
            web_search=web_search,
            rewrite_prompt=rewrite_prompt,
            width=width,
            height=height,
        )
        return self.start_generation("by_prompt", inputs)

    def generate_nsfw_image(
        self, prompt: str, *, model: str = "FLUX_KLEIN_NSFW", ratio: str = "1:1", **kwargs: Any
    ) -> dict[str, Any]:
        """Text-to-image pinned to an NSFW-capable model.

        ``FLUX_KLEIN_NSFW`` and ``Z_IMAGE_SPICY`` are the models that create full
        NSFW content from a prompt; both are gated to trusted accounts.
        """
        if model not in NSFW_IMAGE_MODELS:
            raise ValueError(
                f"{model!r} is not an NSFW image model. Pick one of {NSFW_IMAGE_MODELS}."
            )
        return self.generate_image(prompt, model=model, ratio=ratio, **kwargs)

    def generate_from_reference(
        self,
        *,
        ref_asset: str,
        character_assets: Sequence[str],
        positive_prompt: str | None = None,
        face_asset: str | None = None,
        body_asset: str | None = None,
        model: str | None = None,
        strength: float | None = None,
        keep_pose: bool | None = None,
        ratio: str | None = None,
        tier: str | None = None,
    ) -> dict[str, Any]:
        """Image-to-image that recreates a reference scene for your character (``by_ref``)."""
        inputs = _compact(
            ref_asset=ref_asset,
            character_assets=list(character_assets),
            positive_prompt=positive_prompt,
            face_asset=face_asset,
            body_asset=body_asset,
            model=model,
            strength=strength,
            keep_pose=keep_pose,
            ratio=ratio,
            tier=tier,
        )
        return self.start_generation("by_ref", inputs)

    def run_photoshoot(
        self,
        *,
        face_ref: str,
        body_ref: str,
        prompt: str = "",
        category_id: str | None = None,
        image_count: int = 1,
        ratio: str | None = None,
        width: int | None = None,
        height: int | None = None,
        rewrite_prompt: bool | None = None,
    ) -> dict[str, Any]:
        """Consistent multi-shot photoshoot of one character (``photoshoot``)."""
        inputs = _compact(
            face_ref=face_ref,
            body_ref=body_ref,
            prompt=prompt,
            category_id=category_id,
            image_count=image_count,
            ratio=ratio,
            width=width,
            height=height,
            rewrite_prompt=rewrite_prompt,
        )
        return self.start_generation("photoshoot", inputs)

    def generate_face(
        self,
        *,
        gender: str,
        age: Any,
        origin: str,
        body_type: str | None = None,
        eye_color: str | None = None,
        hair_color: str | None = None,
        hair_type: str | None = None,
        hair_style: str | None = None,
        beard: Any = None,
        beard_color: str | None = None,
        makeup: Any = None,
        tier: str | None = None,
    ) -> dict[str, Any]:
        """Create a new face from structured attributes (``facegen``)."""
        inputs = _compact(
            gender=gender,
            age=age,
            origin=origin,
            body_type=body_type,
            eye_color=eye_color,
            hair_color=hair_color,
            hair_type=hair_type,
            hair_style=hair_style,
            beard=beard,
            beard_color=beard_color,
            makeup=makeup,
            tier=tier,
        )
        return self.start_generation("facegen", inputs)

    def generate_carousel(
        self,
        *,
        asset_ref: str,
        number_of_images: int | None = None,
        ratio: str | None = None,
        tier: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        """Same subject from different camera angles, up to 10 (``carousel``)."""
        inputs = _compact(
            asset_ref=asset_ref,
            number_of_images=number_of_images,
            ratio=ratio,
            tier=tier,
            width=width,
            height=height,
        )
        return self.start_generation("carousel", inputs)

    def upscale_image(
        self,
        *,
        image_asset: str,
        version: str | None = None,
        target_resolution: Any = None,
        detail: Any = None,
        noise_scale: Any = None,
    ) -> dict[str, Any]:
        """Increase resolution while restoring detail (``upscaler``)."""
        inputs = _compact(
            image_asset=image_asset,
            version=version,
            target_resolution=target_resolution,
            detail=detail,
            noise_scale=noise_scale,
        )
        return self.start_generation("upscaler", inputs)

    def face_swap(
        self,
        *,
        ref_asset: str,
        face_asset: str,
        model: str | None = None,
        seed: int | None = None,
        swap_type: str | None = None,
        tier: str | None = None,
    ) -> dict[str, Any]:
        """Place the face from ``face_asset`` onto the person in ``ref_asset`` (``faceswap``)."""
        inputs = _compact(
            ref_asset=ref_asset,
            face_asset=face_asset,
            model=model,
            seed=seed,
            swap_type=swap_type,
            tier=tier,
        )
        return self.start_generation("faceswap", inputs)

    def collab_image(
        self,
        *,
        asset_image_1: str,
        asset_image_2: str,
        prompt: str | None = None,
        location_asset: str | None = None,
        model: str | None = None,
        ratio: str | None = None,
        tier: str | None = None,
        number_of_images: int | None = None,
    ) -> dict[str, Any]:
        """Put two characters in one frame (``collaber``)."""
        inputs = _compact(
            asset_image_1=asset_image_1,
            asset_image_2=asset_image_2,
            prompt=prompt,
            location_asset=location_asset,
            model=model,
            ratio=ratio,
            tier=tier,
            number_of_images=number_of_images,
        )
        return self.start_generation("collaber", inputs)

    def edit_image(
        self,
        *,
        image_assets: Sequence[str],
        prompt: str,
        model: str = "GENERAL_NSFW",
        mask_asset: str | None = None,
        ratio: str | None = None,
        tier: str | None = None,
        number_of_images: int | None = None,
        width: int | None = None,
        height: int | None = None,
        transparency: bool | None = None,
        lora_id: str | None = None,
        edit_precision: Any = None,
    ) -> dict[str, Any]:
        """Prompt-driven edit/composite of existing images (``image_editor``)."""
        inputs = _compact(
            image_assets=list(image_assets),
            prompt=prompt,
            model=model,
            mask_asset=mask_asset,
            ratio=ratio,
            tier=tier,
            number_of_images=number_of_images,
            width=width,
            height=height,
            transparent_background=transparency,
            lora_id=lora_id,
            edit_precision=edit_precision,
        )
        return self.start_generation("image_editor", inputs)

    # -- video generation --------------------------------------------------

    def text_to_video(
        self,
        prompt: str,
        *,
        model: str = "wan@2.7",
        duration: int = 5,
        resolution: str = "1080p",
        ratio: str = "16:9",
        seed: int | None = None,
        generate_audio: bool | None = None,
        camera_fixed: bool | None = None,
    ) -> dict[str, Any]:
        """Text-only video (``text_to_video``)."""
        inputs = _compact(
            prompt=prompt,
            model=model,
            duration=duration,
            resolution=resolution,
            ratio=ratio,
            seed=seed,
            generate_audio=generate_audio,
            camera_fixed=camera_fixed,
        )
        return self.start_generation("text_to_video", inputs)

    def generate_nsfw_video(
        self, prompt: str, *, model: str = "wan@3.0-nsfw", **kwargs: Any
    ) -> dict[str, Any]:
        """Text-to-video pinned to an NSFW video model."""
        if model not in NSFW_VIDEO_MODELS:
            raise ValueError(
                f"{model!r} is not an NSFW video model. Pick one of {NSFW_VIDEO_MODELS}."
            )
        return self.text_to_video(prompt, model=model, **kwargs)

    def image_to_video(
        self,
        *,
        ref_asset: str,
        prompt: str = "",
        model: str = "wan@2.7",
        duration: int = 5,
        resolution: str = "1080p",
        ratio: str = "16:9",
        last_frame: str | None = None,
        audio_asset: str | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
        generate_audio: bool | None = None,
        camera_fixed: bool | None = None,
        prompt_extend: bool | None = None,
        loras: Any = None,
    ) -> dict[str, Any]:
        """Animate a still image (``videogen``)."""
        inputs = _compact(
            ref_asset=ref_asset,
            prompt=prompt,
            model=model,
            duration=duration,
            resolution=resolution,
            ratio=ratio,
            last_frame=last_frame,
            audio_asset=audio_asset,
            negative_prompt=negative_prompt,
            seed=seed,
            generate_audio=generate_audio,
            camera_fixed=camera_fixed,
            prompt_extend=prompt_extend,
            loras=loras,
        )
        return self.start_generation("videogen", inputs)

    def video_to_video(
        self,
        *,
        video_asset: str | None = None,
        image_asset: str | None = None,
        mode: str = "seedance_2_0_sfw",
        prompt: str = "",
        duration: int = 5,
        resolution: str = "1080p",
        ratio: str = "16:9",
        keep_original_sound: bool | None = None,
        seed: int | None = None,
        generate_audio: bool | None = None,
        camera_fixed: bool | None = None,
        instagram_url: str | None = None,
        tiktok_url: str | None = None,
    ) -> dict[str, Any]:
        """Motion transfer / character replacement in a video (``video2video``).

        ``mode`` selects the engine; the ``*_nsfw`` modes are listed in
        :data:`NSFW_VIDEO_MODES`.
        """
        if video_asset is None and image_asset is None and not (instagram_url or tiktok_url):
            raise ValueError(
                "video2video needs one of video_asset, image_asset, instagram_url or tiktok_url."
            )
        inputs = _compact(
            video_asset=video_asset,
            image_asset=image_asset,
            mode=mode,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            ratio=ratio,
            keep_original_sound=keep_original_sound,
            seed=seed,
            generate_audio=generate_audio,
            camera_fixed=camera_fixed,
            instagram_url=instagram_url,
            tiktok_url=tiktok_url,
        )
        return self.start_generation("video2video", inputs)

    def lipsync(
        self,
        *,
        image_asset: str,
        audio_asset: str,
        model: str = "OMNIHUMAN",
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Make a portrait speak an audio track (``lipsync``)."""
        inputs = _compact(
            image_asset=image_asset,
            audio_asset=audio_asset,
            model=model,
            prompt=prompt,
        )
        return self.start_generation("lipsync", inputs)

    def upscale_video(
        self, *, video_asset: str, mode: str | None = None, resolution: str | None = None
    ) -> dict[str, Any]:
        """Sharpen and upscale an existing video (``video_upscaler``)."""
        inputs = _compact(video_asset=video_asset, mode=mode, resolution=resolution)
        return self.start_generation("video_upscaler", inputs)

    def merge_videos(
        self,
        *,
        clips: Sequence[str],
        transition: Any = None,
        keep_audio: bool | None = None,
        fps: Any = None,
        width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        """Concatenate 2-5 clips with transitions (``video_merger``)."""
        if not 2 <= len(clips) <= 5:
            raise ValueError("video_merger takes 2-5 clips.")
        inputs = _compact(
            clips=list(clips),
            transition=transition,
            keep_audio=keep_audio,
            fps=fps,
            width=width,
            height=height,
        )
        return self.start_generation("video_merger", inputs)

    def couple_video(
        self,
        *,
        left_asset: str,
        right_asset: str,
        duration: int | None = None,
        lora_id: str | None = None,
        loras: Any = None,
    ) -> dict[str, Any]:
        """Combine two characters then animate them (``couplegen``)."""
        inputs = _compact(
            left_asset=left_asset,
            right_asset=right_asset,
            duration=duration,
            lora_id=lora_id,
            loras=loras,
        )
        return self.start_generation("couplegen", inputs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def output_urls(result: Mapping[str, Any]) -> list[str]:
    """Return download URLs from a result payload, preferring the full asset."""
    urls: list[str] = []
    for item in result.get("outputs") or []:
        if isinstance(item, Mapping):
            url = item.get("download_url") or item.get("url")
            if url:
                urls.append(str(url))
    return urls


def _compact(**values: Any) -> dict[str, Any]:
    """Drop ``None`` values so the API applies its own defaults."""
    return {key: value for key, value in values.items() if value is not None}


def _decode(raw: bytes) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw": raw.decode("utf-8", errors="replace")}


def _guess_content_type(suffix: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
    }.get(suffix.lower(), "application/octet-stream")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="ZenCreator API client")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("tools", help="list tools with their input schemas")
    sub.add_parser("balance", help="show credit balance")

    img = sub.add_parser("image", help="text-to-image (by_prompt)")
    img.add_argument("prompt")
    img.add_argument("--model", default="GENERAL_NSFW")
    img.add_argument("--ratio", default="1:1")

    nsfw = sub.add_parser("nsfw-image", help="text-to-image on an NSFW model")
    nsfw.add_argument("prompt")
    nsfw.add_argument("--model", default="FLUX_KLEIN_NSFW")
    nsfw.add_argument("--ratio", default="1:1")

    t2v = sub.add_parser("t2v", help="text-to-video")
    t2v.add_argument("prompt")
    t2v.add_argument("--model", default="wan@2.7")
    t2v.add_argument("--duration", type=int, default=5)
    t2v.add_argument("--resolution", default="1080p")
    t2v.add_argument("--ratio", default="16:9")

    nsfw_v = sub.add_parser("nsfw-video", help="text-to-video on an NSFW model")
    nsfw_v.add_argument("prompt")
    nsfw_v.add_argument("--model", default="wan@3.0-nsfw")
    nsfw_v.add_argument("--duration", type=int, default=5)

    for p in (img, nsfw, t2v, nsfw_v):
        p.add_argument("--wait", action="store_true", help="block until the result is ready")

    args = parser.parse_args(list(argv) if argv is not None else None)
    client = ZenCreatorClient()

    if args.command == "tools":
        for name, tool in sorted(client.list_tools().items()):
            props = ", ".join((tool.get("input_schema") or {}).get("properties", {}))
            print(f"{name}: {props}")
        return 0

    if args.command == "balance":
        print(f"credits: {client.get_balance()}")
        return 0

    if args.command == "image":
        created = client.generate_image(args.prompt, model=args.model, ratio=args.ratio)
    elif args.command == "nsfw-image":
        created = client.generate_nsfw_image(args.prompt, model=args.model, ratio=args.ratio)
    elif args.command == "t2v":
        created = client.text_to_video(
            args.prompt,
            model=args.model,
            duration=args.duration,
            resolution=args.resolution,
            ratio=args.ratio,
        )
    else:
        created = client.generate_nsfw_video(args.prompt, model=args.model, duration=args.duration)

    print(f"queued: {created['id']}  status={created.get('status')}")
    if not args.wait:
        return 0

    final = client.wait(created["id"], on_progress=lambda s: print(f"  {s.get('status')} {s.get('progress')}%"))
    result = client.get_result(created["id"])
    print(json.dumps({"status": final.get("status"), "urls": output_urls(result)}, indent=2))
    return 0 if final.get("status") != "failed" else 1


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(_main())
    except ZenCreatorError as exc:
        print(f"error: {exc}")
        raise SystemExit(1)
