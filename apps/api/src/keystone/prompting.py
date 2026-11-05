"""KEYSTONE's prompting authority for generation and chat (Bible sections 5 and 9).

Every prompt a worker receives is assembled here. The user's words stay in the prompt as
written, the embedded cognition contributes structured intent when it is seated, and a
tool's suggestions are weighed by KEYSTONE's own rules with each decision recorded. The
result is versioned, hashed and stored before anything is dispatched.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from apps.api.src.creative import h3_manifest
from apps.api.src.keystone import cognition
from apps.api.src.keystone.models import (
    CompiledPrompt,
    PromptCompilationRequest,
    PromptCompiler,
    PromptIntent,
    ToolSuggestion,
    dump,
)

COMPILER_ID = "keystone.h3-ref2va"
COMPILER_VERSION = "1.0.0"

# Intent fields the embedded cognition may fill, in the order they are written.
_INTENT_LINES = (
    ("Subject", "subject"),
    ("Environment", "environment"),
    ("Style", "visual_style"),
    ("Composition", "composition"),
    ("Camera", "camera"),
    ("Lighting", "lighting"),
    ("Mood", "mood"),
    ("Motion", "motion"),
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS compiled_prompts (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    compiler_id TEXT NOT NULL,
    compiler_version TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    positive_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    parameters TEXT NOT NULL,
    provenance TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""
_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS compiled_prompts_job ON compiled_prompts(job_id)"


class CompilationError(RuntimeError):
    """KEYSTONE could not produce a prompt, so nothing is dispatched to a worker."""


# ------------------------------------------------------------------------ hash

def _hash(
    compiler_version: str,
    capability: str,
    provider: str,
    positive: str,
    negative: Optional[str],
    parameters: Dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "compiler_version": compiler_version,
            "target_capability": capability,
            "target_provider": provider,
            "positive_prompt": positive,
            "negative_prompt": negative,
            "parameters": parameters,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_hash(compiled: CompiledPrompt) -> str:
    return _hash(
        compiled.compiler_version,
        compiled.target_capability,
        compiled.target_provider,
        compiled.positive_prompt,
        compiled.negative_prompt,
        compiled.parameters,
    )


# -------------------------------------------------------------------- compiler

def _plan_references(
    user_text: str, count: int, roles: List[str]
) -> Tuple[Optional[str], Dict[str, Tuple[str, str]]]:
    """Decide how the references are bound into the prompt.

    Returns the line to add (or None) and, per reference suggestion, a (decision, detail) pair.
    """
    if count == 0:
        nothing = ("declined", "no_references")
        return None, {"reference_tags": nothing, "reference_roles": nothing}

    tags = [f"<Picture {index}>" for index in range(1, count + 1)]

    if all(tag in user_text for tag in tags):
        return None, {
            "reference_tags": ("satisfied", "the request already carries every tag"),
            "reference_roles": ("satisfied", "the request is explicit"),
        }

    if len(roles) == count and all(role.strip() for role in roles):
        lines = [f"{tag}: {role.strip().rstrip('.')}." for tag, role in zip(tags, roles)]
        return " ".join(lines), {
            "reference_tags": ("applied", "tags carried by the role lines"),
            "reference_roles": ("applied", "roles proposed by the embedded cognition"),
        }

    missing = [tag for tag in tags if tag not in user_text]
    if len(missing) == 1:
        binding = f"Using {missing[0]} as a visual reference."
    else:
        binding = f"Using {', '.join(missing[:-1])} and {missing[-1]} as visual references."
    return binding, {
        "reference_tags": ("applied", "added " + ", ".join(missing)),
        "reference_roles": ("declined", "roles_not_provided"),
    }


class H3PromptCompiler(PromptCompiler):
    provider_id = h3_manifest.PROVIDER_ID

    async def compile(self, request: PromptCompilationRequest) -> CompiledPrompt:
        manifest = request.capability
        if not manifest.enabled:
            raise CompilationError(f"KEYSTONE_CAPABILITY_DISABLED: {manifest.capability_id}")
        if request.target_provider != self.provider_id or manifest.provider_id != self.provider_id:
            raise CompilationError(
                f"KEYSTONE_PROVIDER_MISMATCH: {request.target_provider} is not {self.provider_id}"
            )

        intent = request.intent
        user_text = intent.objective.strip()
        if not user_text:
            raise CompilationError("KEYSTONE_EMPTY_OBJECTIVE: there is no request text to compile")

        limit = int(manifest.metadata.get("max_reference_images", 0))
        count = max(0, min(int(request.user_context.get("reference_count", 0)), limit))

        # The tool suggests; KEYSTONE's rules decide, and every decision is recorded.
        suggestions = [ToolSuggestion(**raw) for raw in manifest.metadata.get("prompt_suggestions", [])]
        suggested = {item.suggestion_id for item in suggestions}
        if "reference_tags" in suggested:
            roles = intent.references if "reference_roles" in suggested else []
            binding, outcomes = _plan_references(user_text, count, roles)
        else:
            binding, outcomes = None, {}

        decisions = []
        for item in suggestions:
            decision, detail = outcomes.get(item.suggestion_id, ("declined", "no_compiler_rule"))
            decisions.append(
                {"id": item.suggestion_id, "source": item.source, "decision": decision, "detail": detail}
            )

        blocks = [binding] if binding else []
        blocks.append(user_text)
        extras = []
        for label, field in _INTENT_LINES:
            value = (getattr(intent, field) or "").strip()
            if value:
                extras.append(f"{label}: {value}")
        constraints = [item.strip() for item in intent.constraints if item.strip()]
        if constraints:
            extras.append("Constraints: " + "; ".join(constraints))
        if extras:
            blocks.append("\n".join(extras))
        positive = "\n\n".join(blocks)

        parameters = {name: spec.default for name, spec in manifest.parameters.items()}
        parameters["reference_images"] = count

        provenance = {
            "compiler_id": COMPILER_ID,
            "compiler_version": COMPILER_VERSION,
            "request_id": request.request_id,
            "manifest": {
                "schema_version": manifest.schema_version,
                "capability_id": manifest.capability_id,
                "provider_id": manifest.provider_id,
                "provider_version": manifest.provider_version,
                "prompt_profile": manifest.prompt_profile,
                "workflow_id": manifest.workflow_id,
            },
            "intent_hint": intent.metadata.get("intent_hint"),
            "user_text": intent.objective,
            "reference_count": count,
            "cognition": intent.metadata.get("cognition", {"status": "not_connected"}),
            "tool_suggestions": decisions,
        }

        # The H3 ref2va graph has no negative conditioning, so none is compiled.
        return CompiledPrompt(
            compiler_version=COMPILER_VERSION,
            target_capability=manifest.capability_id,
            target_provider=manifest.provider_id,
            positive_prompt=positive,
            negative_prompt=None,
            parameters=parameters,
            provenance=provenance,
            prompt_hash=_hash(
                COMPILER_VERSION, manifest.capability_id, manifest.provider_id, positive, None, parameters
            ),
        )


# ---------------------------------------------------------------------- entry

async def compile_for_generation(
    job_id: str,
    user_text: str,
    intent_hint: Optional[str],
    reference_count: int,
) -> CompiledPrompt:
    """Compile the prompt the H3 worker will receive for one job."""
    manifest = h3_manifest.manifest()
    intent = PromptIntent(
        objective=user_text,
        metadata={"intent_hint": intent_hint, "cognition": {"status": "not_connected"}},
    )

    provider = cognition.current()
    if provider is not None:
        try:
            result = await provider.reason(
                cognition.CognitiveRequest(
                    request_id=job_id,
                    user_text=user_text,
                    intent_hint=intent_hint,
                    reference_count=reference_count,
                    capability=manifest,
                )
            )
            proposed = result.intent
            intent = PromptIntent(
                **{
                    **dump(proposed),
                    "objective": user_text,  # the user's words are not the model's to rewrite
                    "metadata": {
                        "intent_hint": intent_hint,
                        "cognition": {
                            "status": "used",
                            "reasoning_id": result.reasoning_id,
                            "confidence": result.confidence,
                            "observations": result.observations,
                            "proposed_objective": proposed.objective,
                        },
                    },
                }
            )
        except Exception as exc:
            raise CompilationError(f"KEYSTONE_COGNITION_FAILED: {exc}") from exc

    request = PromptCompilationRequest(
        request_id=job_id,
        target_capability=manifest.capability_id,
        target_provider=manifest.provider_id,
        intent=intent,
        user_context={"reference_count": reference_count},
        capability=manifest,
    )
    return await H3PromptCompiler().compile(request)


async def digest_and_compile_prompt(
    user_text: str,
    reference_count: int = 0,
    intent_hint: Optional[str] = "generate",
    job_id: Optional[str] = None,
) -> CompiledPrompt:
    """
    Two-way KEYSTONE Prompt Engine + Embedded Cognition digest helper:
    1. If a test or custom CognitiveProvider is registered via `cognition.register(...)`,
       runs strict `compile_for_generation`.
    2. Otherwise attempts to consult the live embedded Qwen model (`LiveQwenCognitiveProvider`)
       at `OPENAI_BASE_URL` / `COGNITION_BASE_URL` to populate structured PromptIntent fields,
       falling back cleanly to KEYSTONE's deterministic `H3PromptCompiler` if the remote
       cognition tunnel is currently unreachable.
    """
    req_id = job_id or f"job-{uuid.uuid4().hex[:8]}"
    if cognition.current() is not None:
        return await compile_for_generation(req_id, user_text, intent_hint, reference_count)

    manifest = h3_manifest.manifest()
    intent = PromptIntent(
        objective=user_text,
        metadata={"intent_hint": intent_hint, "cognition": {"status": "not_connected"}},
    )

    try:
        live_provider = cognition.LiveQwenCognitiveProvider()
        result = await live_provider.reason(
            cognition.CognitiveRequest(
                request_id=req_id,
                user_text=user_text,
                intent_hint=intent_hint,
                reference_count=reference_count,
                capability=manifest,
            )
        )
        proposed = result.intent
        intent = PromptIntent(
            **{
                **dump(proposed),
                "objective": user_text,
                "metadata": {
                    "intent_hint": intent_hint,
                    "cognition": {
                        "status": "used",
                        "reasoning_id": result.reasoning_id,
                        "confidence": result.confidence,
                        "observations": result.observations,
                        "proposed_objective": proposed.objective,
                    },
                },
            }
        )
    except Exception:
        pass

    request = PromptCompilationRequest(
        request_id=req_id,
        target_capability=manifest.capability_id,
        target_provider=manifest.provider_id,
        intent=intent,
        user_context={"reference_count": reference_count},
        capability=manifest,
    )
    return await H3PromptCompiler().compile(request)


# ---------------------------------------------------------------------- record

def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(_CREATE_TABLE)
    db.execute(_CREATE_INDEX)


def record(db: sqlite3.Connection, job_id: str, compiled: CompiledPrompt) -> str:
    """Store the compiled prompt before dispatch; refuses a prompt that no longer matches its hash."""
    if compiled.prompt_hash != compute_hash(compiled):
        raise CompilationError("KEYSTONE_HASH_MISMATCH: the prompt changed after it was compiled")
    ensure_schema(db)
    record_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO compiled_prompts (id, job_id, compiler_id, compiler_version, capability_id, "
        "provider_id, positive_prompt, negative_prompt, parameters, provenance, prompt_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            record_id,
            job_id,
            compiled.provenance.get("compiler_id", COMPILER_ID),
            compiled.compiler_version,
            compiled.target_capability,
            compiled.target_provider,
            compiled.positive_prompt,
            compiled.negative_prompt,
            json.dumps(compiled.parameters, ensure_ascii=False, default=str),
            json.dumps(compiled.provenance, ensure_ascii=False, default=str),
            compiled.prompt_hash,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return record_id
