"""
KEYSTONE Prompt Engine Package
"""

from packages.prompt_engine.playbooks import (
    Playbook,
    CriticalSlot,
    PathStep,
    PlaybookRegistry,
    CANONICAL_PLAYBOOKS,
    PLAYBOOKS_BY_ID,
    PLAYBOOK_IDS
)
from packages.prompt_engine.compiler import (
    PromptCompiler,
    validate_prompt_anatomy,
    compile_to_markdown,
    compile_to_chat_messages,
    compile_for_reasoning_model,
    compile_prompt
)
from packages.prompt_engine.engine import (
    generate,
    normalize_goal,
    classify_domain,
    extract_signals,
    build_step_prompt_anatomy
)

__all__ = [
    "Playbook",
    "CriticalSlot",
    "PathStep",
    "PlaybookRegistry",
    "CANONICAL_PLAYBOOKS",
    "PLAYBOOKS_BY_ID",
    "PLAYBOOK_IDS",
    "PromptCompiler",
    "validate_prompt_anatomy",
    "compile_to_markdown",
    "compile_to_chat_messages",
    "compile_for_reasoning_model",
    "compile_prompt",
    "generate",
    "normalize_goal",
    "classify_domain",
    "extract_signals",
    "build_step_prompt_anatomy"
]
