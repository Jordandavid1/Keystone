"""KEYSTONE prompting contracts (Bible sections 7 to 9).

Names and field types follow the Bible. ToolSuggestion is the one addition: it carries a
tool's provider-specific recommendations (Bible section 5) to the compiler as data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def dump(model: Any) -> Dict[str, Any]:
    """Plain dict of a pydantic model, on either major version."""
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


class PromptIntent(BaseModel):
    objective: str
    subject: Optional[str] = None
    environment: Optional[str] = None
    visual_style: Optional[str] = None
    composition: Optional[str] = None
    camera: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    motion: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParameterSpec(BaseModel):
    type: str
    required: bool = False
    default: Optional[Any] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    enum: Optional[List[Any]] = None
    description: Optional[str] = None


class CapabilityManifest(BaseModel):
    schema_version: str = "1.0"
    capability_id: str
    provider_id: str
    provider_version: str
    capability_type: str
    description: str
    accepts: List[str]
    produces: List[str]
    parameters: Dict[str, ParameterSpec]
    prompt_profile: Optional[str] = None
    workflow_id: Optional[str] = None
    required_harnesses: List[str] = Field(default_factory=list)
    estimated_resource_class: Optional[str] = None
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolSuggestion(BaseModel):
    suggestion_id: str
    source: str
    text: str


class PromptCompilationRequest(BaseModel):
    request_id: str
    target_capability: str
    target_provider: str
    intent: PromptIntent
    user_context: Dict[str, Any] = Field(default_factory=dict)
    workflow_context: Dict[str, Any] = Field(default_factory=dict)
    capability: CapabilityManifest


class CompiledPrompt(BaseModel):
    compiler_version: str
    target_capability: str
    target_provider: str
    positive_prompt: str
    negative_prompt: Optional[str] = None
    parameters: Dict[str, Any]
    provenance: Dict[str, Any]
    prompt_hash: str


class PromptCompiler(ABC):
    provider_id: str

    @abstractmethod
    async def compile(self, request: PromptCompilationRequest) -> CompiledPrompt:
        ...
