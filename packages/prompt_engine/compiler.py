"""
KEYSTONE Prompt Compiler (Python Implementation)
Implements six-part PromptAnatomy validation, multi-profile compilation (standard, chat, reasoning),
deterministic SHA-256 prompt hashing, and provenance generation per Bible §2 Invariant 13, §6, §7, §9.
"""

from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

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

    @classmethod
    def compile(
        cls,
        intent: Union[Dict[str, Any], PromptIntent, None],
        playbook: str = "general",
        profile: Literal["standard", "chat", "reasoning"] = "standard"
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

        # Resolve playbook and its preloaded domain context & skills
        selected_playbook = PlaybookRegistry.resolve_id(playbook)
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

        constraints_list = list(constraints) if isinstance(constraints, (list, tuple)) else []
        if not constraints_list and domain_ctx.get("default_constraints"):
            constraints_list = list(domain_ctx["default_constraints"])

        anatomy_dict: Dict[str, Any] = {
            "role": f"Authoritative creative agent specialized in {selected_playbook} ({pb.label})",
            "task": str(objective),
            "context": context_items,
            "constraints": constraints_list,
            "outputFormat": "High-fidelity multimodal asset descriptor conforming to plan.v1",
            "reasoning": f"Selected {selected_playbook} playbook with profile {profile} and {len(pb.skills)} bound skills for objective"
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
                "profile": profile,
                "hash": prompt_hash,
                "skills": [s.get("id") for s in (pb.skills or [])],
                "use_case_count": len(pb.use_cases or []),
                "compiled_at": datetime.now(timezone.utc).isoformat()
            },
            "playbook_context": domain_ctx,
            "use_cases": pb.use_cases,
            "skills": pb.skills,
            "prompt_hash": prompt_hash,
            "anatomy": anatomy_dict
        }
