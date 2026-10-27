"""
KEYSTONE Creative Tool Fabric Adapters (Bible §8, §23).
Provides standardized adapters for ComfyUI, Flux Schnell/Dev, Image Edit,
Wan 2.1 I2V, Wan 2.1 T2V, FaceFusion 3.x, and Clarity/Upscale.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from packages.contracts.src.models import CapabilityManifest, ParameterSpec, ExecutionEnvelope


# Registry of supported creative adapters
SUPPORTED_ADAPTERS = [
    "comfyui",
    "image_gen",
    "image_edit",
    "wan_i2v",
    "wan_t2v",
    "facefusion",
    "upscale"
]


class CreativeAdapterBase:
    """Base interface for all creative tool fabric adapters."""

    def __init__(self, adapter_name: str, capability_id: str, provider_id: str, version: str = "1.0.0"):
        self.adapter_name = adapter_name
        self.capability_id = capability_id
        self.provider_id = provider_id
        self.version = version

    def get_manifest(self) -> CapabilityManifest:
        raise NotImplementedError

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        raise NotImplementedError

    def execute(self, params: Dict[str, Any], envelope: Optional[ExecutionEnvelope] = None) -> Dict[str, Any]:
        validated = self.validate_parameters(params)
        prompt = validated.get("prompt", "")
        graph = self.build_workflow_graph(validated, prompt)
        return {
            "adapter": self.adapter_name,
            "capability_id": self.capability_id,
            "status": "READY",
            "workflow_id": f"wf_{self.adapter_name}_v1",
            "graph": graph,
            "parameters": validated,
            "estimated_runtime_seconds": 45
        }


class ComfyUIAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("comfyui", "creative.comfyui", "comfy.core")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="creative.comfyui",
            provider_id="comfy.core",
            provider_version="1.0.0",
            capability_type="generation",
            description="ComfyUI modular graph generation engine",
            accepts=["application/json"],
            produces=["image/png", "video/mp4"],
            parameters={
                "workflow_graph": ParameterSpec(type="object", required=True, description="ComfyUI node graph JSON")
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if "workflow_graph" not in params and "prompt" not in params:
            raise ValueError("MISSING_GRAPH_OR_PROMPT: workflow_graph or prompt required for ComfyUI adapter")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return params.get("workflow_graph", {"3": {"inputs": {"text": prompt}, "class_type": "CLIPTextEncode"}})


class ImageGenAdapter(CreativeAdapterBase):
    """Flux Schnell / Dev text-to-image adapter."""

    def __init__(self):
        super().__init__("image_gen", "image.generation", "comfy.flux_schnell")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="image.generation",
            provider_id="comfy.flux_schnell",
            provider_version="1.0.0",
            capability_type="generation",
            description="High-fidelity text-to-image generation powered by Flux",
            accepts=["text/plain"],
            produces=["image/png", "image/webp"],
            parameters={
                "prompt": ParameterSpec(type="string", required=True, description="Compiled generation prompt"),
                "width": ParameterSpec(type="integer", required=False, default=1024, minimum=256, maximum=2048),
                "height": ParameterSpec(type="integer", required=False, default=1024, minimum=256, maximum=2048),
                "steps": ParameterSpec(type="integer", required=False, default=20, minimum=1, maximum=50),
                "guidance": ParameterSpec(type="number", required=False, default=3.5, minimum=1.0, maximum=20.0),
                "seed": ParameterSpec(type="integer", required=False, default=42)
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if "prompt" not in params or not str(params["prompt"]).strip():
            raise ValueError("MISSING_PROMPT: prompt string is required for image_gen")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-schnell.sft", "weight_dtype": "fp8_e4m3fn"}},
            "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
            "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": params.get("width", 1024), "height": params.get("height", 1024), "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["3", 0], "latent_image": ["4", 0], "seed": params.get("seed", 42), "steps": params.get("steps", 20), "cfg": params.get("guidance", 3.5), "sampler_name": "euler", "scheduler": "simple"}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["7", 0]}},
            "7": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.sft"}},
            "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "keystone_flux", "images": ["6", 0]}}
        }


class ImageEditAdapter(CreativeAdapterBase):
    """Image-to-image and inpainting creative adapter."""

    def __init__(self):
        super().__init__("image_edit", "image.editing", "comfy.image_edit")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="image.editing",
            provider_id="comfy.image_edit",
            provider_version="1.0.0",
            capability_type="transformation",
            description="Targeted image modification and inpainting",
            accepts=["image/png", "text/plain"],
            produces=["image/png"],
            parameters={
                "source_image_asset_id": ParameterSpec(type="string", required=True, description="Source image asset ID"),
                "prompt": ParameterSpec(type="string", required=True, description="Instruction prompt"),
                "denoise": ParameterSpec(type="number", required=False, default=0.75, minimum=0.05, maximum=1.0)
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("source_image_asset_id"):
            raise ValueError("MISSING_ASSET: image_edit requires source_image_asset_id")
        if not params.get("prompt"):
            raise ValueError("MISSING_PROMPT: image_edit requires prompt")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": params["source_image_asset_id"]}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt}},
            "3": {"class_type": "KSampler", "inputs": {"denoise": params.get("denoise", 0.75)}}
        }


class WanI2VAdapter(CreativeAdapterBase):
    """Wan 2.1 Image-to-Video generation adapter."""

    def __init__(self):
        super().__init__("wan_i2v", "video.i2v", "comfy.wan_2_1_i2v")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="video.i2v",
            provider_id="comfy.wan_2_1_i2v",
            provider_version="1.0.0",
            capability_type="generation",
            description="Wan 2.1 Image-to-Video generative motion model",
            accepts=["image/png", "text/plain"],
            produces=["video/mp4"],
            parameters={
                "source_image_asset_id": ParameterSpec(type="string", required=True, description="Anchor image asset ID"),
                "prompt": ParameterSpec(type="string", required=False, description="Motion guidance prompt"),
                "duration_seconds": ParameterSpec(type="integer", required=False, default=5, minimum=1, maximum=10),
                "resolution": ParameterSpec(type="string", required=False, default="720p", enum=["480p", "720p", "1080p"])
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("source_image_asset_id"):
            raise ValueError("MISSING_ASSET: wan_i2v requires source_image_asset_id")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": params["source_image_asset_id"]}},
            "2": {"class_type": "WanVideoModelLoader", "inputs": {"model_name": "wan2.1_i2v_720p_14B.safetensors"}},
            "3": {"class_type": "WanMotionPrompt", "inputs": {"motion_text": prompt or "subtle realistic motion"}},
            "4": {"class_type": "WanVideoSampler", "inputs": {"duration": params.get("duration_seconds", 5), "resolution": params.get("resolution", "720p")}}
        }


class WanT2VAdapter(CreativeAdapterBase):
    """Wan 2.1 Text-to-Video generation adapter."""

    def __init__(self):
        super().__init__("wan_t2v", "video.t2v", "comfy.wan_2_1_t2v")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="video.t2v",
            provider_id="comfy.wan_2_1_t2v",
            provider_version="1.0.0",
            capability_type="generation",
            description="Wan 2.1 Text-to-Video camera and scene generation",
            accepts=["text/plain"],
            produces=["video/mp4"],
            parameters={
                "prompt": ParameterSpec(type="string", required=True, description="Video prompt"),
                "duration_seconds": ParameterSpec(type="integer", required=False, default=5, minimum=1, maximum=10),
                "resolution": ParameterSpec(type="string", required=False, default="720p", enum=["480p", "720p", "1080p"])
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if "prompt" not in params or not str(params["prompt"]).strip():
            raise ValueError("MISSING_PROMPT: wan_t2v requires prompt string")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "WanVideoModelLoader", "inputs": {"model_name": "wan2.1_t2v_720p_14B.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt}},
            "3": {"class_type": "WanVideoSampler", "inputs": {"duration": params.get("duration_seconds", 5), "resolution": params.get("resolution", "720p")}}
        }


class FaceFusionAdapter(CreativeAdapterBase):
    """FaceFusion 3.x identity consistency adapter."""

    def __init__(self):
        super().__init__("facefusion", "identity.facefusion", "facefusion.v3")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="identity.facefusion",
            provider_id="facefusion.v3",
            provider_version="3.0.0",
            capability_type="transformation",
            description="Identity preservation and facial feature fusion",
            accepts=["image/png", "video/mp4"],
            produces=["image/png", "video/mp4"],
            parameters={
                "source_face_asset_id": ParameterSpec(type="string", required=True, description="Reference face asset ID"),
                "target_asset_id": ParameterSpec(type="string", required=True, description="Target image or video asset ID")
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("source_face_asset_id") or not params.get("target_asset_id"):
            raise ValueError("MISSING_ASSETS: facefusion requires source_face_asset_id and target_asset_id")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": params["source_face_asset_id"]}},
            "2": {"class_type": "LoadTargetMedia", "inputs": {"media": params["target_asset_id"]}},
            "3": {"class_type": "FaceFusionSwap", "inputs": {"source": ["1", 0], "target": ["2", 0], "similarity_threshold": 0.85}}
        }


class UpscaleAdapter(CreativeAdapterBase):
    """Clarity / RealESRGAN resolution upscaler."""

    def __init__(self):
        super().__init__("upscale", "upscale.clarity", "comfy.upscale_clarity")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="upscale.clarity",
            provider_id="comfy.upscale_clarity",
            provider_version="1.0.0",
            capability_type="transformation",
            description="Super-resolution detail restoration and upscaling",
            accepts=["image/png"],
            produces=["image/png"],
            parameters={
                "source_image_asset_id": ParameterSpec(type="string", required=True, description="Asset to upscale"),
                "upscale_factor": ParameterSpec(type="integer", required=False, default=2, enum=[2, 4])
            }
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("source_image_asset_id"):
            raise ValueError("MISSING_ASSET: upscale requires source_image_asset_id")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": params["source_image_asset_id"]}},
            "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "4x-UltraSharp.pth"}},
            "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}}
        }


ADAPTER_REGISTRY: Dict[str, CreativeAdapterBase] = {
    "comfyui": ComfyUIAdapter(),
    "image_gen": ImageGenAdapter(),
    "image_edit": ImageEditAdapter(),
    "wan_i2v": WanI2VAdapter(),
    "wan_t2v": WanT2VAdapter(),
    "facefusion": FaceFusionAdapter(),
    "upscale": UpscaleAdapter()
}


def get_adapter(adapter_name: str) -> CreativeAdapterBase:
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(f"UNKNOWN_ADAPTER: {adapter_name}")
    return ADAPTER_REGISTRY[adapter_name]


def list_capabilities() -> List[CapabilityManifest]:
    return [adapter.get_manifest() for adapter in ADAPTER_REGISTRY.values()]


def validate_adapter_request(adapter: str, params: Dict[str, Any]) -> Dict[str, Any]:
    ad = get_adapter(adapter)
    return ad.execute(params)
