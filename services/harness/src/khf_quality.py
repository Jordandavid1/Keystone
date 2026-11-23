"""
KEYSTONE Quality Harness Framework (KHF) Orchestrator (Bible v2 §13, §14 & specs/SPEC_EVALUATORS.md).

Replaces legacy float-averaging stubs with real 5-family artifact evaluation:
  - Tier A (ALWAYS):
      1. `deterministic.py` — File integrity, dimensions, duration, format validity, upscale delta.
  - Tier B (Conditional per §13.3 budget, retry flag, modality, and persona presence):
      2. `ocr.py`          — Rendered text fidelity vs. requested text string (`OCR_TEXT_MISMATCH`).
      3. `vlm_critique.py` — Output alignment vs. compiled intent, persona sheet, and mode-aware
                             SFW / UNRESTRICTED rubric via local Qwen-VL behind `CognitiveProvider`.
      4. `temporal.py`     — Sampled-frame SSIM, luminance flicker, optical-flow drift, and
                             `extend` boundary continuity on video outputs.
      5. `identity.py`     — Persona face/subject embedding cosine similarity vs. `reference_assets`
                             (`PERSONA_IDENTITY_DRIFT` below 0.72).

Invariants enforced:
  - Zero hardcoded default dimensional scores.
  - Un-evaluated or self-reported dict-only inputs (e.g. `{"x": 1}`) are strictly rejected (`verdict="fail"`).
  - Every evaluation run can be persisted as a durable `HarnessRun` row in PostgreSQL/SQLite.
"""

from __future__ import annotations

import hashlib
import inspect
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

from packages.contracts.src.models import (
    HarnessResult,
    QualityDimensions,
    QualityScore,
)
from services.harness.src.evaluators.deterministic import validate_asset_bytes
from services.harness.src.evaluators.identity import (
    DEFAULT_IDENTITY_THRESHOLD,
    PERSONA_IDENTITY_DRIFT,
    evaluate_identity,
)
from services.harness.src.evaluators.ocr import (
    DEFAULT_OCR_THRESHOLD,
    OCR_TEXT_MISMATCH,
    evaluate_ocr,
    extract_requested_texts_from_prompt,
)
from services.harness.src.evaluators.temporal import (
    DEFAULT_TEMPORAL_THRESHOLD,
    evaluate_temporal_consistency,
)
from services.harness.src.evaluators.vlm_critique import (
    SFW_PASS_THRESHOLD,
    UNRESTRICTED_PASS_THRESHOLD,
    evaluate_vlm_critique,
    evaluate_vlm_critique_async,
)

SERVICE_TIER_VLM_BUDGET_DEFAULTS: Dict[str, float] = {
    "draft": 0.0,
    "standard": 0.0,
    "quality": 100.0,
}


def _as_uuid_or_none(value: Optional[Any]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _detect_media_type_and_mime(
    raw_bytes: Optional[bytes],
    payload: Dict[str, Any],
    explicit_media_type: Optional[str] = None,
    explicit_mime: Optional[str] = None,
) -> Tuple[str, str]:
    """Infer `(media_type, mime_type)` from explicit arguments, payload metadata, or magic bytes."""
    mime = str(
        explicit_mime
        or payload.get("mime_type")
        or payload.get("expected_mime")
        or payload.get("content_type")
        or ""
    ).strip().lower()

    media_type = str(
        explicit_media_type
        or payload.get("media_type")
        or payload.get("expected_media_type")
        or payload.get("asset_type")
        or payload.get("type")
        or ""
    ).strip().lower()

    fmt = str(payload.get("format") or "").strip().lower()

    if not media_type:
        if mime.startswith("video/") or fmt in ("mp4", "webm", "mov", "mkv", "avi"):
            media_type = "video"
        elif mime.startswith("audio/") or fmt in ("wav", "mp3", "ogg"):
            media_type = "audio"
        elif mime.startswith("image/") or fmt in ("png", "jpg", "jpeg", "webp", "gif"):
            media_type = "image"
        elif any(k in payload for k in ("video_bytes", "video_path", "frames", "segments", "segment_paths")):
            media_type = "video"
        elif any(k in payload for k in ("audio_bytes", "audio_path")):
            media_type = "audio"
        elif raw_bytes:
            if len(raw_bytes) >= 12 and (
                raw_bytes[4:8] == b"ftyp"
                or raw_bytes[:4] == b"\x1a\x45\xdf\xa3"
                or (raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"AVI ")
            ):
                media_type = "video"
            elif len(raw_bytes) >= 12 and (
                (raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WAVE")
                or raw_bytes[:4] == b"OggS"
                or raw_bytes[:3] == b"ID3"
            ):
                media_type = "audio"
            else:
                media_type = "image"
        else:
            media_type = "image"

    if not mime:
        if media_type == "video":
            mime = "video/mp4"
        elif media_type == "audio":
            mime = "audio/wav"
        else:
            mime = f"image/{fmt}" if fmt in ("png", "jpeg", "webp", "gif") else "image/png"

    return media_type, mime


def _extract_artifact_bytes(
    output_data: Any,
) -> Tuple[Optional[bytes], Dict[str, Any]]:
    """
    Extract `(artifact_bytes, metadata_dict)` from `output_data`.
    Returns `(None, metadata_dict)` when no real binary artifact or file path is present.
    """
    if output_data is None:
        return None, {}

    if isinstance(output_data, (bytes, bytearray, memoryview)):
        return bytes(output_data), {}

    if isinstance(output_data, Path):
        if output_data.exists() and output_data.is_file():
            return output_data.read_bytes(), {"file_path": str(output_data)}
        return None, {"file_path": str(output_data), "file_missing": True}

    if isinstance(output_data, str):
        p = Path(output_data)
        if p.exists() and p.is_file():
            return p.read_bytes(), {"file_path": str(p)}
        return None, {}

    if isinstance(output_data, dict):
        meta = dict(output_data)
        for byte_key in (
            "bytes",
            "asset_bytes",
            "data",
            "payload",
            "image_bytes",
            "video_bytes",
            "audio_bytes",
            "content",
            "raw_bytes",
        ):
            val = output_data.get(byte_key)
            if isinstance(val, (bytes, bytearray, memoryview)):
                return bytes(val), meta

        for path_key in ("file_path", "path", "video_path", "image_path", "audio_path"):
            p_val = output_data.get(path_key)
            if isinstance(p_val, (str, Path)) and str(p_val).strip():
                p = Path(p_val)
                if p.exists() and p.is_file():
                    return p.read_bytes(), meta

        # Support nested `outputs: [{"bytes": ...}]` from ComfyUI / worker execution results
        outputs_list = output_data.get("outputs")
        if isinstance(outputs_list, list) and outputs_list:
            first = outputs_list[0]
            if isinstance(first, (bytes, bytearray, memoryview)):
                return bytes(first), meta
            if isinstance(first, dict):
                sub_bytes, sub_meta = _extract_artifact_bytes(first)
                if sub_bytes is not None:
                    merged = {**sub_meta, **meta}
                    return sub_bytes, merged

        return None, meta

    # ORM Asset or object with .bytes / .data / .image_bytes
    meta_obj: Dict[str, Any] = {}
    for attr in ("id", "mime_type", "asset_type", "width", "height", "duration_seconds", "mature"):
        if hasattr(output_data, attr):
            meta_obj[attr] = getattr(output_data, attr)
    for byte_attr in ("bytes", "asset_bytes", "data", "image_bytes", "video_bytes"):
        val = getattr(output_data, byte_attr, None)
        if isinstance(val, (bytes, bytearray, memoryview)):
            return bytes(val), meta_obj

    return None, meta_obj


def resolve_vlm_budget_pct(
    vlm_budget_pct: Optional[float] = None,
    *,
    service_tier: Optional[str] = None,
) -> float:
    """
    Resolve the active VLM evaluation sample percentage (`0.0` to `100.0`) from
    explicit override, `KEYSTONE_EVAL_BUDGET_VLM_PCT`, or `service_tier` (`draft | quality`).
    """
    if vlm_budget_pct is not None:
        val = float(vlm_budget_pct)
        if 0.0 < val <= 1.0 and os.getenv("KEYSTONE_EVAL_BUDGET_VLM_PCT") is None:
            # Handle callers passing a fraction in (0, 1.0] only when explicitly fractional
            pass
        return max(0.0, min(100.0, val))

    raw_env = os.getenv("KEYSTONE_EVAL_BUDGET_VLM_PCT", "").strip()
    if raw_env:
        try:
            return max(0.0, min(100.0, float(raw_env)))
        except ValueError:
            return 0.0

    if service_tier:
        tier_key = str(service_tier).strip().lower()
        if tier_key in SERVICE_TIER_VLM_BUDGET_DEFAULTS:
            return SERVICE_TIER_VLM_BUDGET_DEFAULTS[tier_key]

    return 0.0


def should_run_vlm_critique(
    *,
    is_retry: bool = False,
    has_persona: bool = False,
    vlm_budget_pct: Optional[float] = None,
    service_tier: Optional[str] = None,
    sample_key: Optional[str] = None,
    run_vlm: Optional[bool] = None,
) -> bool:
    """
    Determine whether Tier-B VLM critique (`vlm_critique.py`) should run per
    Bible v2 §13.3 and `specs/SPEC_EVALUATORS.md` §2 & §4:
      - Always runs on retries (`is_retry=True`).
      - Always runs on persona-bearing assets (`has_persona=True`).
      - Otherwise runs on `KEYSTONE_EVAL_BUDGET_VLM_PCT` percentage of jobs.
    """
    if run_vlm is False:
        return False
    if run_vlm is True:
        return True
    if is_retry or has_persona:
        return True

    pct = resolve_vlm_budget_pct(vlm_budget_pct, service_tier=service_tier)
    if pct <= 0.0:
        return False
    if pct >= 100.0:
        return True

    seed_str = str(sample_key or "keystone-vlm-default-sample")
    bucket = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16) % 10000
    return (bucket / 100.0) < pct


class KHFQualityHarness:
    """
    Orchestrates Tier-A (`deterministic.py`, ALWAYS) and Tier-B (`ocr`, `vlm_critique`,
    `temporal`, `identity`) evaluators, rejects un-evaluated or self-reported dict-only
    inputs, aggregates multidimensional quality scores without hardcoded defaults, and
    persists every evaluation verdict as a durable `HarnessRun` row in the database.
    """

    HARNESS_ID = "khf.creative_evaluator"
    VERSION = "2.0.0"

    PASS_THRESHOLD = 0.70
    WARN_THRESHOLD = 0.50

    @classmethod
    def persist_harness_run(
        cls,
        db: Any,
        result: HarnessResult,
        *,
        job_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        resource_cost: Optional[Dict[str, Any]] = None,
        flush: bool = False,
    ) -> Any:
        """
        Persist a `HarnessResult` verdict as a durable `HarnessRun` row in PostgreSQL/SQLite.
        Supports both synchronous SQLAlchemy `Session` and `_AsyncSessionAdapter` / `AsyncSession`.
        """
        if db is None:
            return None

        from apps.api.src.db.models import HarnessRun

        row = HarnessRun(
            id=str(uuid.uuid4()),
            job_id=_as_uuid_or_none(job_id),
            attempt_id=_as_uuid_or_none(attempt_id),
            harness_id=result.harness_id or cls.HARNESS_ID,
            harness_version=result.harness_version or cls.VERSION,
            phase=result.phase or "post-execution",
            verdict=result.verdict,
            score=float(result.score) if result.score is not None else 0.0,
            reason_codes=list(result.reason_codes or []),
            evidence=dict(result.evidence or {}),
            runtime_ms=int(round(float(result.runtime_ms or 0.0))),
            resource_cost=resource_cost,
        )
        db.add(row)
        if flush:
            sync_sess = getattr(db, "_s", None)
            if sync_sess is not None and hasattr(sync_sess, "flush"):
                sync_sess.flush()
            elif hasattr(db, "flush"):
                res = db.flush()
                # If db is a pure AsyncSession and flush() returned a coroutine in sync caller, close it safely
                if inspect.iscoroutine(res):
                    res.close()
        return row

    @classmethod
    async def persist_harness_run_async(
        cls,
        db: Any,
        result: HarnessResult,
        *,
        job_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        resource_cost: Optional[Dict[str, Any]] = None,
        flush: bool = True,
    ) -> Any:
        """Async version of `persist_harness_run` that awaits `db.flush()` when requested."""
        row = cls.persist_harness_run(
            db,
            result,
            job_id=job_id,
            attempt_id=attempt_id,
            resource_cost=resource_cost,
            flush=False,
        )
        if row is not None and flush and hasattr(db, "flush"):
            maybe_coro = db.flush()
            if inspect.isawaitable(maybe_coro):
                await maybe_coro
        return row

    @classmethod
    def evaluate_output(
        cls,
        output_data: Any,
        prompt: str = "",
        phase: str = "post-execution",
        reference_asset_ids: Optional[Sequence[Any]] = None,
        *,
        reference_assets: Optional[Sequence[Any]] = None,
        persona_id: Optional[str] = None,
        persona_sheet: Optional[Any] = None,
        persona: Optional[Any] = None,
        content_mode: Optional[str] = None,
        mode: Optional[str] = None,
        requested_text: Optional[Union[str, Sequence[str]]] = None,
        expected_text: Optional[Union[str, Sequence[str]]] = None,
        media_type: Optional[str] = None,
        mime_type: Optional[str] = None,
        source_dimensions: Optional[Tuple[int, int]] = None,
        require_upscale_delta: bool = False,
        is_retry: bool = False,
        attempt_number: int = 1,
        vlm_budget_pct: Optional[float] = None,
        service_tier: Optional[str] = None,
        vlm_provider: Optional[Any] = None,
        ocr_hook: Optional[Callable[[bytes], str]] = None,
        identity_embedding_fn: Optional[Callable[[bytes], Sequence[float]]] = None,
        allow_cpu_fallback: Optional[bool] = None,
        sample_frames: Optional[int] = None,
        segments: Optional[Sequence[Any]] = None,
        segment_paths: Optional[Sequence[Union[str, Path]]] = None,
        previous_segment: Optional[Any] = None,
        is_extend: bool = False,
        run_ocr: Optional[bool] = None,
        run_vlm: Optional[bool] = None,
        run_temporal: Optional[bool] = None,
        run_identity: Optional[bool] = None,
        db: Optional[Any] = None,
        job_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        persist_per_family: bool = False,
        storage_dir: Optional[Union[str, Path]] = None,
    ) -> HarnessResult:
        """
        Execute real multi-family KHF evaluation on a generated output artifact.

        1. Rejects empty, un-evaluated, or self-reported dict-only inputs (`{"x": 1}` -> `fail`).
        2. Always runs Tier-A `deterministic.py` (`validate_asset_bytes`).
        3. Conditionally runs Tier-B evaluators (`ocr`, `vlm_critique`, `temporal`, `identity`)
           gated by `KEYSTONE_EVAL_BUDGET_VLM_PCT`, `is_retry`, modality, and persona presence.
        4. Aggregates real measured scores (zero hardcoded defaults) and persists `HarnessRun` row(s)
           when `db` is provided.
        """
        start = time.perf_counter()

        def _finalize(
            verdict_val: Literal["pass", "warn", "fail"],
            score_val: float,
            reasons: List[str],
            ev: Dict[str, Any],
            family_results: List[Tuple[str, HarnessResult]],
        ) -> HarnessResult:
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            overall_res = HarnessResult(
                harness_id=cls.HARNESS_ID,
                harness_version=cls.VERSION,
                phase=phase,  # type: ignore[arg-type]
                verdict=verdict_val,
                score=round(max(0.0, min(1.0, float(score_val))), 4),
                reason_codes=reasons,
                evidence=ev,
                runtime_ms=elapsed_ms,
            )
            if db is not None:
                eff_job_id = job_id or (output_data.get("job_id") if isinstance(output_data, dict) else None)
                eff_attempt_id = attempt_id or (output_data.get("attempt_id") if isinstance(output_data, dict) else None)
                if persist_per_family and family_results:
                    for _fam_name, fam_res in family_results:
                        cls.persist_harness_run(
                            db,
                            fam_res,
                            job_id=eff_job_id,
                            attempt_id=eff_attempt_id,
                        )
                else:
                    cls.persist_harness_run(
                        db,
                        overall_res,
                        job_id=eff_job_id,
                        attempt_id=eff_attempt_id,
                    )
            return overall_res

        # 1. Empty payload check
        if not output_data:
            return _finalize(
                "fail",
                0.0,
                ["EMPTY_OUTPUT_PAYLOAD"],
                {"error": "Output payload is empty", "verdicts": []},
                [],
            )

        raw_bytes, payload_meta = _extract_artifact_bytes(output_data)
        frames_input = payload_meta.get("frames") if isinstance(payload_meta.get("frames"), (list, tuple)) else None
        segs_input = segments or segment_paths or payload_meta.get("segments") or payload_meta.get("segment_paths")

        # Check for explicit error flag on payload
        has_error = bool(payload_meta.get("has_error", False))

        # 2. Reject un-evaluated or self-reported dict-only inputs (e.g. `{"x": 1}` or float-only dicts without real bytes)
        if raw_bytes is None and not frames_input and not segs_input:
            reject_codes: List[str] = [
                "UNEVALUATED_INPUT",
                "SELF_REPORTED_INPUT_REJECTED",
                "MISSING_ARTIFACT_BYTES",
            ]
            if has_error:
                reject_codes.append("RENDER_ERROR_FLAGGED")
            if isinstance(payload_meta.get("artifact_score"), (int, float)) and float(payload_meta["artifact_score"]) > 0.40:
                reject_codes.append("HIGH_ARTIFACT_DENSITY")
            return _finalize(
                "fail",
                0.0,
                reject_codes,
                {
                    "error": (
                        "Un-evaluated or self-reported dict-only input rejected: "
                        "no evaluator may rely solely on numbers supplied without real artifact bytes."
                    ),
                    "supplied_keys": sorted(str(k) for k in payload_meta.keys()),
                    "verdicts": [],
                },
                [],
            )

        # Unpack metadata overrides from payload_meta when not passed explicitly
        eff_prompt = str(prompt or payload_meta.get("prompt") or payload_meta.get("compiled_prompt") or "")
        eff_mode = str(
            content_mode
            or mode
            or payload_meta.get("content_mode")
            or payload_meta.get("mode")
            or "sfw"
        ).strip().lower()
        if eff_mode not in ("sfw", "unrestricted"):
            eff_mode = "sfw"

        eff_persona_id = persona_id or payload_meta.get("persona_id")
        eff_persona_sheet = persona_sheet or payload_meta.get("persona_sheet")
        eff_persona = persona or payload_meta.get("persona")
        eff_refs: List[Any] = list(
            reference_assets
            or reference_asset_ids
            or payload_meta.get("reference_assets")
            or payload_meta.get("reference_asset_ids")
            or payload_meta.get("persona_references")
            or []
        )
        if not eff_refs and eff_persona is not None:
            if hasattr(eff_persona, "reference_assets"):
                eff_refs = list(getattr(eff_persona, "reference_assets") or [])
            elif isinstance(eff_persona, dict) and eff_persona.get("reference_assets"):
                eff_refs = list(eff_persona.get("reference_assets") or [])

        eff_is_retry = bool(
            is_retry
            or payload_meta.get("is_retry")
            or payload_meta.get("retry")
            or int(attempt_number or payload_meta.get("attempt_number") or 1) > 1
        )
        eff_req_text = (
            requested_text
            or expected_text
            or payload_meta.get("requested_text")
            or payload_meta.get("expected_text")
            or payload_meta.get("target_text")
        )
        eff_source_dims = source_dimensions or payload_meta.get("source_dimensions")
        eff_upscale_delta = bool(require_upscale_delta or payload_meta.get("require_upscale_delta", False))
        eff_service_tier = service_tier or payload_meta.get("service_tier")
        eff_is_extend = bool(
            is_extend
            or payload_meta.get("is_extend")
            or str(payload_meta.get("intent") or "").lower() == "extend"
        )

        resolved_media_type, resolved_mime = _detect_media_type_and_mime(
            raw_bytes,
            payload_meta,
            explicit_media_type=media_type,
            explicit_mime=mime_type,
        )

        family_results: List[Tuple[str, HarnessResult]] = []
        verdict_objects: List[Dict[str, Any]] = []
        families_map: Dict[str, Dict[str, Any]] = {}
        all_reason_codes: List[str] = []

        if has_error:
            all_reason_codes.append("RENDER_ERROR_FLAGGED")

        def _record_family(family_name: str, res: HarnessResult) -> None:
            family_results.append((family_name, res))
            v_obj = {
                "family": family_name,
                "harness_id": res.harness_id,
                "verdict": res.verdict,
                "score": float(res.score) if res.score is not None else 0.0,
                "defects": list(res.reason_codes or []),
                "runtime_ms": res.runtime_ms,
                "evidence": res.evidence,
            }
            verdict_objects.append(v_obj)
            families_map[family_name] = v_obj
            for code in res.reason_codes or []:
                if code not in all_reason_codes:
                    all_reason_codes.append(code)

        # ---------------------------------------------------------------------
        # Family 1 (Tier A — ALWAYS): Deterministic Evaluator (`deterministic.py`)
        # ---------------------------------------------------------------------
        if raw_bytes is not None:
            det_res = validate_asset_bytes(
                raw_bytes,
                expected_media_type=resolved_media_type,
                expected_mime=resolved_mime,
                source_dimensions=eff_source_dims,
                require_upscale_delta=eff_upscale_delta,
            )
        else:
            # Frame sequence or segment paths provided for video temporal evaluation
            first_bytes: Optional[bytes] = None
            if frames_input:
                f0 = frames_input[0]
                first_bytes = bytes(f0) if isinstance(f0, (bytes, bytearray)) else (Path(f0).read_bytes() if Path(str(f0)).exists() else None)
            elif segs_input:
                s0 = list(segs_input)[0]
                first_bytes = bytes(s0) if isinstance(s0, (bytes, bytearray)) else (Path(s0).read_bytes() if Path(str(s0)).exists() else None)
            det_res = validate_asset_bytes(
                first_bytes or b"",
                expected_media_type="image" if (first_bytes and first_bytes.startswith(b"\x89PNG\r\n\x1a\n")) else resolved_media_type,
                expected_mime="image/png" if (first_bytes and first_bytes.startswith(b"\x89PNG\r\n\x1a\n")) else resolved_mime,
                source_dimensions=eff_source_dims,
                require_upscale_delta=eff_upscale_delta,
            )
        _record_family("deterministic", det_res)

        # If Tier-A deterministic file integrity failed, short-circuit Tier-B neural/OCR evaluators
        if det_res.verdict == "fail":
            return _finalize(
                "fail",
                0.0,
                all_reason_codes or ["DETERMINISTIC_VALIDATION_FAILED"],
                {
                    "media_type": resolved_media_type,
                    "mime_type": resolved_mime,
                    "content_mode": eff_mode,
                    "tier_a_passed": False,
                    "verdicts": verdict_objects,
                    "families": families_map,
                },
                family_results,
            )

        # ---------------------------------------------------------------------
        # Family 2 (Tier B): OCR Text Fidelity (`ocr.py`) — text-bearing images
        # ---------------------------------------------------------------------
        prompt_quoted_texts = (
            extract_requested_texts_from_prompt(eff_prompt)
            if (resolved_media_type == "image" and eff_prompt and eff_req_text is None and run_ocr is None)
            else []
        )
        should_ocr = bool(
            run_ocr is True
            or (
                run_ocr is not False
                and resolved_media_type == "image"
                and raw_bytes is not None
                and (eff_req_text is not None or len(prompt_quoted_texts) > 0)
            )
        )
        if should_ocr and raw_bytes is not None:
            ocr_res = evaluate_ocr(
                raw_bytes,
                requested_text=eff_req_text if eff_req_text is not None else prompt_quoted_texts,
                prompt=eff_prompt,
                ocr_hook=ocr_hook or payload_meta.get("ocr_hook"),
                phase=phase,
            )
            _record_family("ocr", ocr_res)

        # ---------------------------------------------------------------------
        # Family 3 (Tier B): VLM Prompt-Adherence & Mode Rubric (`vlm_critique.py`)
        # Gated by KEYSTONE_EVAL_BUDGET_VLM_PCT, is_retry, and persona presence
        # ---------------------------------------------------------------------
        has_persona = bool(eff_persona_id or eff_persona_sheet or eff_persona is not None or len(eff_refs) > 0)
        sample_key = str(
            job_id
            or attempt_id
            or payload_meta.get("job_id")
            or payload_meta.get("attempt_id")
            or eff_prompt
            or (hashlib.sha256(raw_bytes[:256]).hexdigest() if raw_bytes else "sample")
        )
        vlm_gated_in = should_run_vlm_critique(
            is_retry=eff_is_retry,
            has_persona=has_persona,
            vlm_budget_pct=vlm_budget_pct if vlm_budget_pct is not None else payload_meta.get("vlm_budget_pct"),
            service_tier=eff_service_tier,
            sample_key=sample_key,
            run_vlm=run_vlm if run_vlm is not None else payload_meta.get("run_vlm"),
        )
        if vlm_gated_in and resolved_media_type in ("image", "video"):
            vlm_res = evaluate_vlm_critique(
                asset_bytes=raw_bytes,
                intent=payload_meta.get("intent") or eff_prompt,
                content_mode=eff_mode,
                persona_sheet=eff_persona_sheet,
                provider=vlm_provider or payload_meta.get("vlm_provider"),
                mime_type=resolved_mime,
                phase=phase,
                **{
                    k: v
                    for k, v in payload_meta.items()
                    if k in ("explicit", "mature", "nsfw", "content_rating", "tags", "theme", "description")
                },
            )
            _record_family("vlm_critique", vlm_res)

        # ---------------------------------------------------------------------
        # Family 4 (Tier B): Temporal Consistency (`temporal.py`) — video outputs
        # ---------------------------------------------------------------------
        should_temporal = bool(
            run_temporal is True
            or (
                run_temporal is not False
                and (resolved_media_type == "video" or frames_input is not None or segs_input is not None)
            )
        )
        if should_temporal:
            temp_res = evaluate_temporal_consistency(
                video_bytes=raw_bytes if resolved_media_type == "video" else None,
                frames=frames_input,
                sample_frames=sample_frames or payload_meta.get("sample_frames"),
                segments=segments or payload_meta.get("segments"),
                segment_paths=segment_paths or payload_meta.get("segment_paths"),
                previous_segment=previous_segment or payload_meta.get("previous_segment"),
                is_extend=eff_is_extend,
                phase=phase,
            )
            _record_family("temporal", temp_res)

        # ---------------------------------------------------------------------
        # Family 5 (Tier B): Persona Identity Continuity (`identity.py`)
        # Runs on all persona-bearing assets
        # ---------------------------------------------------------------------
        should_identity = bool(
            run_identity is True
            or (
                run_identity is not False
                and (len(eff_refs) > 0 or (eff_persona_id is not None and eff_persona is not None))
            )
        )
        if should_identity:
            id_res = evaluate_identity(
                candidate=raw_bytes if raw_bytes is not None else output_data,
                reference_assets=eff_refs if eff_refs else eff_persona,
                allow_cpu_fallback=allow_cpu_fallback,
                embedding_fn=identity_embedding_fn or payload_meta.get("identity_embedding_fn"),
                db=db,
                storage_dir=storage_dir,
                phase=phase,
            )
            _record_family("identity", id_res)

        # ---------------------------------------------------------------------
        # Aggregate Verdict & Score Across Executed Evaluator Families
        # ---------------------------------------------------------------------
        measured_scores = [
            float(res.score)
            for _fam, res in family_results
            if res.score is not None
        ]
        tier_b_scores = [
            float(res.score)
            for fam, res in family_results
            if fam != "deterministic" and res.score is not None
        ]

        if tier_b_scores:
            # Weight Tier-B semantic/perceptual scores (80%) + Tier-A integrity (20%)
            tier_a_score = float(det_res.score or 0.0)
            mean_tier_b = sum(tier_b_scores) / float(len(tier_b_scores))
            composite_score = round(0.20 * tier_a_score + 0.80 * mean_tier_b, 4)
        elif measured_scores:
            composite_score = round(sum(measured_scores) / float(len(measured_scores)), 4)
        else:
            composite_score = 0.0

        any_family_failed = any(res.verdict == "fail" for _fam, res in family_results)
        any_family_warned = any(res.verdict == "warn" for _fam, res in family_results)

        pass_threshold = (
            UNRESTRICTED_PASS_THRESHOLD
            if (eff_mode == "unrestricted" and "vlm_critique" in families_map)
            else cls.PASS_THRESHOLD
        )

        if has_error or any_family_failed or composite_score < cls.WARN_THRESHOLD:
            verdict: Literal["pass", "warn", "fail"] = "fail"
            if not all_reason_codes:
                all_reason_codes.append("SUB_MINIMUM_QUALITY_SCORE")
        elif any_family_warned or composite_score < pass_threshold:
            verdict = "fail" if composite_score < pass_threshold else "warn"
            if "MARGINAL_QUALITY_SCORE" not in all_reason_codes:
                all_reason_codes.append("MARGINAL_QUALITY_SCORE")
        else:
            verdict = "pass"

        evidence: Dict[str, Any] = {
            "composite_score": composite_score,
            "media_type": resolved_media_type,
            "mime_type": resolved_mime,
            "content_mode": eff_mode,
            "is_retry": eff_is_retry,
            "has_persona": has_persona,
            "vlm_gated_in": vlm_gated_in,
            "executed_families": [fam for fam, _ in family_results],
            "verdicts": verdict_objects,
            "families": families_map,
        }
        if "width" in det_res.evidence and "height" in det_res.evidence:
            evidence["resolution_verified"] = f"{det_res.evidence['width']}x{det_res.evidence['height']}"
        if "format" in det_res.evidence:
            evidence["format"] = str(det_res.evidence["format"]).lower()

        return _finalize(
            verdict,
            composite_score,
            all_reason_codes,
            evidence,
            family_results,
        )

    @classmethod
    def compute_quality_score(
        cls,
        dimensions_dict: Optional[Dict[str, Optional[float]]] = None,
        evaluator_name: str = "khf.multimodal_evaluator",
        *,
        harness_result: Optional[HarnessResult] = None,
    ) -> QualityScore:
        """
        Construct a structured `QualityScore` from actually measured dimensions or a
        `HarnessResult` — with ZERO hardcoded `0.85`/`0.90` default score fallbacks.
        """
        raw: Dict[str, Optional[float]] = dict(dimensions_dict or {})

        # Populate measured dimensions from a real HarnessResult if provided
        if harness_result is not None:
            families = harness_result.evidence.get("families") or {}
            det_v = families.get("deterministic")
            if isinstance(det_v, dict) and raw.get("technical_quality") is None:
                raw["technical_quality"] = float(det_v.get("score", 0.0))
            vlm_v = families.get("vlm_critique")
            if isinstance(vlm_v, dict):
                vlm_ev = vlm_v.get("evidence") or {}
                if raw.get("prompt_adherence") is None and vlm_ev.get("prompt_adherence") is not None:
                    raw["prompt_adherence"] = float(vlm_ev["prompt_adherence"])
                if raw.get("composition") is None and vlm_ev.get("composition_score") is not None:
                    raw["composition"] = float(vlm_ev["composition_score"])
                if raw.get("technical_quality") is None and vlm_ev.get("craft_score") is not None:
                    raw["technical_quality"] = float(vlm_ev["craft_score"])
            ocr_v = families.get("ocr")
            if isinstance(ocr_v, dict) and raw.get("prompt_adherence") is None:
                raw["prompt_adherence"] = float(ocr_v.get("score", 0.0))
            temp_v = families.get("temporal")
            if isinstance(temp_v, dict) and raw.get("temporal_consistency") is None:
                raw["temporal_consistency"] = float(temp_v.get("score", 0.0))
            id_v = families.get("identity")
            if isinstance(id_v, dict) and raw.get("identity_consistency") is None:
                raw["identity_consistency"] = float(id_v.get("score", 0.0))

        def _opt_float(key: str) -> Optional[float]:
            val = raw.get(key)
            if val is None:
                return None
            return max(0.0, min(1.0, float(val)))

        dimensions = QualityDimensions(
            prompt_adherence=_opt_float("prompt_adherence"),
            technical_quality=_opt_float("technical_quality"),
            composition=_opt_float("composition"),
            visual_consistency=_opt_float("visual_consistency"),
            identity_consistency=_opt_float("identity_consistency"),
            temporal_consistency=_opt_float("temporal_consistency"),
            artifact_score=_opt_float("artifact_score"),
            user_satisfaction=_opt_float("user_satisfaction"),
        )

        measured_positive: List[float] = [
            v
            for v in (
                dimensions.prompt_adherence,
                dimensions.technical_quality,
                dimensions.composition,
                dimensions.visual_consistency,
                dimensions.identity_consistency,
                dimensions.temporal_consistency,
                dimensions.user_satisfaction,
            )
            if v is not None
        ]
        if dimensions.artifact_score is not None:
            measured_positive.append(max(0.0, min(1.0, 1.0 - dimensions.artifact_score)))

        if measured_positive:
            overall = round(sum(measured_positive) / float(len(measured_positive)), 3)
            confidence = round(min(0.95, 0.55 + 0.05 * len(measured_positive)), 2)
        elif harness_result is not None and harness_result.score is not None:
            overall = round(max(0.0, min(1.0, float(harness_result.score))), 3)
            confidence = 0.80
        else:
            overall = 0.0
            confidence = 0.0

        strengths: List[str] = []
        weaknesses: List[str] = []
        recommendations: List[str] = []

        if dimensions.prompt_adherence is not None and dimensions.prompt_adherence >= 0.80:
            strengths.append("High adherence to key prompt directives")
        if dimensions.technical_quality is not None and dimensions.technical_quality >= 0.80:
            strengths.append("Crisp texture rendering and low compression noise")
        if dimensions.identity_consistency is not None and dimensions.identity_consistency >= DEFAULT_IDENTITY_THRESHOLD:
            strengths.append("Persona identity continuity verified against reference assets")
        if dimensions.temporal_consistency is not None and dimensions.temporal_consistency >= DEFAULT_TEMPORAL_THRESHOLD:
            strengths.append("Smooth temporal frame consistency and optical flow stability")

        if dimensions.artifact_score is not None and dimensions.artifact_score > 0.25:
            weaknesses.append("Visual artifacts or edge noise detected")
            recommendations.append("Consider applying neural ESRGAN upscale with clarity restoration")
        if dimensions.identity_consistency is not None and dimensions.identity_consistency < DEFAULT_IDENTITY_THRESHOLD:
            weaknesses.append(f"Persona identity drift detected ({PERSONA_IDENTITY_DRIFT})")
            recommendations.append("Increase identity conditioning weight or retry with canonical reference set")
        if not measured_positive and harness_result is None:
            weaknesses.append("No measured quality dimensions supplied")

        return QualityScore(
            evaluator=evaluator_name,
            evaluator_version=cls.VERSION,
            dimensions=dimensions,
            overall=overall,
            confidence=confidence,
            evidence={
                "measured_dimension_count": len(measured_positive),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "recommendations": recommendations,
            },
        )


__all__ = [
    "KHFQualityHarness",
    "SERVICE_TIER_VLM_BUDGET_DEFAULTS",
    "resolve_vlm_budget_pct",
    "should_run_vlm_critique",
]
