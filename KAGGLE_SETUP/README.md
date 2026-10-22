# KEYSTONE Kaggle Full Bring-Up Workspace

This folder is dedicated to bringing the complete KEYSTONE runtime online through Kaggle while preserving KEYSTONE as the sole prompting authority.

## Execution order

1. `notebooks/01_keystone_cognition_bootstrap.ipynb`
   - Hardware and CUDA probe
   - RAM/VRAM discovery
   - Qwen checkpoint configuration
   - Initial BF16 plus CPU-offload calculation
2. `notebooks/02_keystone_comfyui_runtime.ipynb`
   - ComfyUI installation and persistence layout
   - Workflow directories
   - API health validation
3. `notebooks/03_keystone_integrated_gateway.ipynb`
   - KEYSTONE API bridge
   - Cognition and creative-runtime health checks
   - Tunnel configuration placeholders
4. `checklists/BRING_UP_CHECKLIST.md`
   - Manual setup and verification gates
5. `configs/kaggle-secrets.example.env`
   - Names of required secrets only. Never commit real credentials.

## Rules

- Do not place GitHub tokens, Kaggle tokens, Cloudflare credentials, passwords, or model-provider keys in notebooks.
- Put credentials in Kaggle Secrets and read them from environment variables.
- Do not silently substitute the configured cognitive checkpoint.
- Keep context, concurrency, and GPU allocation conservative until the memory harness passes.
- A notebook is not complete until its health check and restart check pass.
