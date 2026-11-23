"""
KEYSTONE Prompt Compiler (Python Implementation)
Implements six-part PromptAnatomy validation, multi-profile compilation (standard, chat, reasoning),
deterministic SHA-256 prompt hashing, and provenance generation per Bible §2 Invariant 13, §6, §7, §9.
"""

from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from packages.contracts.src.models import PromptAnatomy, PromptIntent, CompiledPrompt
from packages.prompt_engine.playbooks import PlaybookRegistry, PLAYBOOK_IDS


REQUIRED_ANATOMY_FIELDS = ["role", "task", "context", "constraints", "outputFormat", "reasoning"]


def validate_prompt_anatomy(prompt: Union[Dict[str, Any], PromptAnatomy]) -> bool:
    """Validates that all six parts of PromptAnatomy are present and correctly typed."""
    if prompt is None or not (isinstance(prompt, dict) or isinstance(prompt, PromptAnatomy)):
        raise TypeError("Prompt must be an object")

    data = prompt.model_dump() if isinstance(prompt, PromptAnatomy) else prompt

    for field_name in REQUIRED_ANATOMY_FIELDS:
        val = data.get(field_name)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ValueError(f'Prompt missing required field: "{field_name}"')

    if not isinstance(data.get("context"), list):
        raise TypeError("Prompt context must be an array")
    if not isinstance(data.get("constraints"), list):
        raise TypeError("Prompt constraints must be an array")

    return True


def compile_to_markdown(prompt: Union[Dict[str, Any], PromptAnatomy]) -> str:
    """Compiles PromptAnatomy into structured Markdown."""
    validate_prompt_anatomy(prompt)
    data = prompt.model_dump() if isinstance(prompt, PromptAnatomy) else prompt
    context_lines = "\n".join(str(c) for c in data.get("context", []) if c)
    constraints_lines = "\n".join(f"- {c}" for c in data.get("constraints", []) if c)

    parts = [
        f"## ROLE\n{data['role']}",
        f"## TASK\n{data['task']}",
        f"## CONTEXT\n{context_lines}",
        f"## CONSTRAINTS\n{constraints_lines}",
        f"## OUTPUT FORMAT\n{data['outputFormat']}",
        f"## REASONING\n{data['reasoning']}"
    ]
    return "\n\n".join(parts)


def compile_to_chat_messages(prompt: Union[Dict[str, Any], PromptAnatomy]) -> List[Dict[str, str]]:
    """Compiles PromptAnatomy into OpenAI-compatible chat messages."""
    validate_prompt_anatomy(prompt)
    data = prompt.model_dump() if isinstance(prompt, PromptAnatomy) else prompt
    constraints_lines = "\n".join(f"- {c}" for c in data.get("constraints", []) if c)
    context_lines = "\n".join(str(c) for c in data.get("context", []) if c)

    return [
        {
            "role": "system",
            "content": f"Identity & Role:\n{data['role']}\n\nOperational Constraints:\n{constraints_lines}"
        },
        {
            "role": "user",
            "content": (
                f"## TASK\n{data['task']}\n\n"
                f"## CONTEXT\n{context_lines}\n\n"
                f"## OUTPUT FORMAT\n{data['outputFormat']}\n\n"
                f"## REASONING OBJECTIVE\n{data['reasoning']}"
            )
        }
    ]


def compile_for_reasoning_model(prompt: Union[Dict[str, Any], PromptAnatomy]) -> str:
    """Compiles PromptAnatomy for deep reasoning models (e.g. Qwen / o1)."""
    validate_prompt_anatomy(prompt)
    data = prompt.model_dump() if isinstance(prompt, PromptAnatomy) else prompt
    context_lines = "\n".join(str(c) for c in data.get("context", []) if c)
    constraints_lines = "\n".join(f"- {c}" for c in data.get("constraints", []) if c)

    parts = [
        f"## ROLE & PERSPECTIVE\n{data['role']}",
        f"## OBJECTIVE\n{data['task']}",
        f"## CONTEXT & DEPENDENCIES\n{context_lines}",
        f"## CONSTRAINTS\n{constraints_lines}",
        f"## DELIVERABLE CONTRACT\n{data['outputFormat']}",
        "## REASONING OBJECTIVE\nAnalyze requirements holistically and verify edge cases before producing the deliverable."
    ]
    return "\n\n".join(parts)


def compile_prompt(prompt: Union[Dict[str, Any], PromptAnatomy], options: Optional[Dict[str, Any]] = None) -> Union[str, List[Dict[str, str]]]:
    """Universal compiler interface selecting profile ('standard', 'chat', 'reasoning')."""
    opts = options or {}
    profile = opts.get("profile", "standard")
    if profile == "chat":
        return compile_to_chat_messages(prompt)
    if profile == "reasoning":
        return compile_for_reasoning_model(prompt)
    return compile_to_markdown(prompt)


class PromptCompiler:
    """
    Authoritative KEYSTONE Prompt Compiler.
    Transforms raw user intent (PromptIntent) into 6-part PromptAnatomy,
    determines domain playbook, formats positive/negative prompts, computes SHA-256 hash,
    and attaches immutable provenance metadata.
    """

    COMPILER_VERSION = "2.0.0"
    PLAYBOOKS = list(PLAYBOOK_IDS)
    SFW_PLAYBOOKS = list(PLAYBOOK_IDS[:13])
    UNRESTRICTED_PLAYBOOKS = list(PLAYBOOK_IDS)

    @classmethod
    def get_playbooks_for_mode(cls, mode: str = "sfw") -> List[str]:
        """Return mode-scoped playbook IDs (1-13 SFW, 1-16 UNRESTRICTED)."""
        if (mode or "sfw").lower() == "unrestricted":
            return list(cls.UNRESTRICTED_PLAYBOOKS)
        return list(cls.SFW_PLAYBOOKS)

    @classmethod
    def critique_rubric(cls, mode: str = "sfw") -> Dict[str, Any]:
        """Critique rubric stub ready for PR7."""
        normalized_mode = (mode or "sfw").lower()
        return {
            "mode": normalized_mode,
            "threshold": 0.70 if normalized_mode == "unrestricted" else 0.75,
            "criteria": [
                {"id": "anatomy_completeness", "weight": 0.30, "description": "All 6 PromptAnatomy parts are well-formed."},
                {"id": "objective_fidelity", "weight": 0.40, "description": "User objective is preserved without drift."},
                {"id": "policy_alignment", "weight": 0.30, "description": f"Output adheres to {normalized_mode} mode constraints."},
            ],
        }

    @classmethod
    def compile(
        cls,
        intent: Union[Dict[str, Any], PromptIntent, None],
        playbook: str = "general",
        profile: Literal["standard", "chat", "reasoning"] = "standard",
        mode: Literal["sfw", "unrestricted"] = "sfw",
        memory_context: Optional[Union[str, List[str]]] = None,
        persona_sheet: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compiles PromptIntent into standard CompiledPrompt dictionary format.
        Validates objective, generates deterministic SHA-256 hash, and attaches provenance.
        """
        if intent is None:
            raise ValueError("OBJECTIVE_REQUIRED")

        if isinstance(intent, dict):
            objective = intent.get("objective")
            subject = intent.get("subject")
            environment = intent.get("environment")
            visual_style = intent.get("visual_style")
            constraints = intent.get("constraints", [])
        elif isinstance(intent, PromptIntent):
            objective = intent.objective
            subject = intent.subject
            environment = intent.environment
            visual_style = intent.visual_style
            constraints = intent.constraints
        else:
            raise ValueError("OBJECTIVE_REQUIRED")

        if not objective or not str(objective).strip():
            raise ValueError("OBJECTIVE_REQUIRED")

        # Resolve mode-scoped playbook and its preloaded domain context & skills
        allowed_playbooks = cls.get_playbooks_for_mode(mode)
        selected_playbook = PlaybookRegistry.resolve_id(playbook)
        if selected_playbook not in allowed_playbooks:
            selected_playbook = "general"
        pb = PlaybookRegistry.get(selected_playbook)
        domain_ctx = pb.domain_context or {}
        skill_names = [s.get("name", s.get("id", "")) for s in (pb.skills or []) if s]

        # Build 6-part PromptAnatomy
        context_items: List[str] = []
        if subject:
            context_items.append(f"Subject: {subject}")
        if environment:
            context_items.append(f"Environment: {environment}")
        if visual_style:
            context_items.append(f"Style: {visual_style}")

        if not context_items and domain_ctx:
            if domain_ctx.get("domain_brief"):
                context_items.append(f"Domain Context: {domain_ctx['domain_brief']}")
            if domain_ctx.get("system_framing"):
                context_items.append(f"System Framing: {domain_ctx['system_framing']}")
            if skill_names:
                context_items.append(f"Active Skills: {', '.join(skill_names)}")

        if memory_context:
            mem_str = "; ".join(str(m) for m in memory_context) if isinstance(memory_context, (list, tuple)) else str(memory_context)
            if mem_str.strip():
                context_items.append(f"Memory Advisory: {mem_str.strip()}")

        persona_injected = False
        if persona_sheet:
            persona_str = json.dumps(persona_sheet, sort_keys=True) if isinstance(persona_sheet, dict) else str(persona_sheet)
            if persona_str.strip():
                context_items.append(f"Persona Sheet: {persona_str.strip()}")
                persona_injected = True

        constraints_list = list(constraints) if isinstance(constraints, (list, tuple)) else []
        if not constraints_list and domain_ctx.get("default_constraints"):
            constraints_list = list(domain_ctx["default_constraints"])

        anatomy_dict: Dict[str, Any] = {
            "role": f"Authoritative creative agent specialized in {selected_playbook} ({pb.label})",
            "task": str(objective),
            "context": context_items,
            "constraints": constraints_list,
            "outputFormat": "High-fidelity multimodal asset descriptor conforming to plan.v1",
            "reasoning": f"Selected {selected_playbook} playbook ({mode} mode) with profile {profile} and {len(pb.skills)} bound skills for objective"
        }

        # Build positive prompt string for hashing and delivery
        context_str = ", ".join(context_items)
        constraints_str = "; ".join(str(c) for c in constraints_list) if constraints_list else "None"
        positive_prompt = f"{anatomy_dict['role']}. Goal: {anatomy_dict['task']}. Context: {context_str}. Constraints: {constraints_str}."

        # Compute deterministic SHA-256 prompt hash
        prompt_hash = hashlib.sha256(positive_prompt.encode("utf-8")).hexdigest()

        return {
            "compiler_version": cls.COMPILER_VERSION,
            "target_capability": "keystone.creative.generation",
            "target_provider": "comfyui.wan",
            "positive_prompt": positive_prompt,
            "negative_prompt": "deformed, blurry, low quality, artifacts, watermark",
            "parameters": {
                "aspect_ratio": "16:9",
                "steps": 30,
                "guidance": 6.0
            },
            "provenance": {
                "playbook": selected_playbook,
                "domain_label": pb.label,
                "mode": (mode or "sfw").lower(),
                "profile": profile,
                "hash": prompt_hash,
                "skills": [s.get("id") for s in (pb.skills or [])],
                "use_case_count": len(pb.use_cases or []),
                "memory_context_used": bool(memory_context),
                "persona_injected": persona_injected,
                "compiled_at": datetime.now(timezone.utc).isoformat()
            },
            "playbook_context": domain_ctx,
            "use_cases": pb.use_cases,
            "skills": pb.skills,
            "prompt_hash": prompt_hash,
            "anatomy": anatomy_dict
        }


# ----------------------------------------------------------------------------
# Absorbed H3PromptCompiler & Generation Digest (PR4 Consolidation - ADR-005)
# ----------------------------------------------------------------------------

COMPILER_ID = "keystone.h3-ref2va"
H3_COMPILER_VERSION = "1.0.0"

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


class CompilationError(RuntimeError):
    """KEYSTONE could not produce a prompt, so nothing is dispatched to a worker."""


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


def compute_hash(compiled: Any) -> str:
    """Compute deterministic SHA-256 hash for a CompiledPrompt."""
    return _hash(
        compiled.compiler_version,
        compiled.target_capability,
        compiled.target_provider,
        compiled.positive_prompt,
        compiled.negative_prompt,
        compiled.parameters,
    )


def _plan_references(
    user_text: str, count: int, roles: List[str]
) -> Tuple[Optional[str], Dict[str, Tuple[str, str]]]:
    """Decide how the references are bound into the prompt."""
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


class H3PromptCompiler:
    """Prompt compiler for H3 ref2va generation requests."""

    provider_id = "minimax-h3-pinkcherry-1.8"

    async def compile(self, request: Any) -> Any:
        from apps.api.src.keystone.models import CompiledPrompt as KeystoneCompiledPrompt, ToolSuggestion

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
            "compiler_version": H3_COMPILER_VERSION,
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

        return KeystoneCompiledPrompt(
            compiler_version=H3_COMPILER_VERSION,
            target_capability=manifest.capability_id,
            target_provider=manifest.provider_id,
            positive_prompt=positive,
            negative_prompt=None,
            parameters=parameters,
            provenance=provenance,
            prompt_hash=_hash(
                H3_COMPILER_VERSION, manifest.capability_id, manifest.provider_id, positive, None, parameters
            ),
        )


async def compile_for_generation(
    job_id: str,
    user_text: str,
    intent_hint: Optional[str],
    reference_count: int,
) -> Any:
    """Compile the prompt the H3 worker will receive for one job."""
    from apps.api.src.creative import h3_manifest
    from apps.api.src.keystone import cognition
    from apps.api.src.keystone.models import PromptCompilationRequest, PromptIntent as KeystonePromptIntent, dump

    manifest = h3_manifest.manifest()
    intent = KeystonePromptIntent(
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
            intent = KeystonePromptIntent(
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
    memory_context: Optional[Union[str, List[str]]] = None,
    persona_sheet: Optional[Union[str, Dict[str, Any]]] = None,
) -> Any:
    """
    Two-way KEYSTONE Prompt Engine + Embedded Cognition digest helper.
    """
    from apps.api.src.creative import h3_manifest
    from apps.api.src.keystone import cognition
    from apps.api.src.keystone.models import PromptCompilationRequest, PromptIntent as KeystonePromptIntent, dump

    req_id = job_id or f"job-{uuid.uuid4().hex[:8]}"
    if cognition.current() is not None:
        return await compile_for_generation(req_id, user_text, intent_hint, reference_count)

    manifest = h3_manifest.manifest()
    intent = KeystonePromptIntent(
        objective=user_text,
        metadata={
            "intent_hint": intent_hint,
            "cognition": {"status": "not_connected"},
            "memory_context_used": bool(memory_context),
            "persona_injected": bool(persona_sheet),
        },
    )

    from services.cognition.src.client import CognitionConnector

    if CognitionConnector().resolve_active_endpoint():
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
            intent = KeystonePromptIntent(
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
                        "memory_context_used": bool(memory_context),
                        "persona_injected": bool(persona_sheet),
                    },
                }
            )
        except Exception as exc:
            intent = KeystonePromptIntent(
                objective=user_text,
                metadata={
                    "intent_hint": intent_hint,
                    "cognition": {
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    "memory_context_used": bool(memory_context),
                    "persona_injected": bool(persona_sheet),
                },
            )

    request = PromptCompilationRequest(
        request_id=req_id,
        target_capability=manifest.capability_id,
        target_provider=manifest.provider_id,
        intent=intent,
        user_context={"reference_count": reference_count},
        capability=manifest,
    )
    return await H3PromptCompiler().compile(request)
