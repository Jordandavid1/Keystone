"""What the H3 tool contributes to KEYSTONE's prompting (Bible sections 5 and 8).

The manifest describes the capability and carries the tool's own prompting recommendations,
taken from the workflow note inside PinkCherry_Ref2V.json / workflows/h3-ref2va.json.
KEYSTONE weighs them; nothing here decides.
"""

from __future__ import annotations

from apps.api.src.keystone.models import CapabilityManifest, ParameterSpec, ToolSuggestion, dump

CAPABILITY_ID = "video.reference_to_video"
PROVIDER_ID = "minimax-h3-pinkcherry-1.8"
PROVIDER_VERSION = "1.8"
WORKFLOW_ID = "h3-ref2va"
SUGGESTION_SOURCE = "h3-ref2va workflow note"

COMFY_DURATION = 5.0
COMFY_STEPS = 4
COMFY_MEGAPIXELS = 5.6
COMFY_ASPECT = "16:9 (Widescreen)"
REFERENCE_NODES = ("181", "187")

SUGGESTIONS = (
    ToolSuggestion(
        suggestion_id="reference_tags",
        source=SUGGESTION_SOURCE,
        text="Refer to each reference by its tag, in the order the references are connected: "
             "<Picture 1>, <Picture 2>.",
    ),
    ToolSuggestion(
        suggestion_id="reference_roles",
        source=SUGGESTION_SOURCE,
        text="Say which reference drives which part of the shot; ref2va output is very "
             "sensitive to prompt wording.",
    ),
)


def manifest() -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=CAPABILITY_ID,
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        capability_type="video_generation",
        description="Reference-to-video with native audio: MiniMax H3 (PinkCherry 1.8 ref2va) through ComfyUI.",
        accepts=["image", "video", "audio", "text"],
        produces=["video"],
        parameters={
            "duration": ParameterSpec(type="number", default=COMFY_DURATION, description="Seconds of video."),
            "steps": ParameterSpec(type="integer", default=COMFY_STEPS, description="Turbo sampler steps."),
            "megapixels": ParameterSpec(type="number", default=COMFY_MEGAPIXELS, description="Resolution budget."),
            "aspect": ParameterSpec(type="string", default=COMFY_ASPECT, description="Aspect ratio preset."),
        },
        prompt_profile=WORKFLOW_ID,
        workflow_id=WORKFLOW_ID,
        metadata={
            "max_reference_images": len(REFERENCE_NODES),
            "prompt_suggestions": [dump(item) for item in SUGGESTIONS],
        },
    )
