# Kaggle Pre-Flight Checklist (Bible §24)

Prior to initiating any Kaggle worker session:

1. [ ] **Accelerator Selection**: Kaggle notebook settings -> Accelerator: **GPU T4 x 2** selected.
2. [ ] **Internet Access**: Kaggle notebook settings -> Internet: **Enabled (On)**.
3. [ ] **Secrets & Tokens**: Hugging Face token added to Kaggle Secrets (name: `HF_TOKEN`) if accessing gated assets.
4. [ ] **Hardware Probe**: Run Cell 1 in Notebook 01 and confirm available host RAM >= 70 GiB.
5. [ ] **Quantization Check**: Confirm `--quantization` flag is NOT passed to vLLM. Checkpoint is `huihui-ai/Huihui-Qwen3.8-27B-abliterated`.
6. [ ] **API Endpoint**: Confirm live Google Cloud Run API endpoint is operational and reachable.
