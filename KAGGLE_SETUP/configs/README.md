# KAGGLE_SETUP Configurations

Authoritative configurations for KEYSTONE Tier 0 GPU workers on Kaggle (Bible §24):
- `vllm_config.json`: Configuration for vLLM running `huihui-ai/Huihui-Qwen3.8-27B-abliterated` on 2x NVIDIA T4 GPUs with ~26.7–27 GiB CPU offload in bfloat16.
- `comfyui_config.json`: Configuration for headless ComfyUI (port 8188) and signed ExecutionHarness (port 8189) supporting Wan 2.1, FaceFusion, and RealESRGAN.
