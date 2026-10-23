# Kaggle Session Startup Checklist (Bible §24)

Execute the following sequential startup order for each Kaggle session:

1. [ ] **Session 1 (Cognition)**:
   - Launch `KAGGLE_SETUP/01_keystone_cognition_bootstrap.ipynb`.
   - Run Cells 1–5 to start vLLM on port 8000.
   - Verify Cell 6 returns a valid structured `ProposedAction` JSON response.
2. [ ] **Session 2 (Creative Tool Fabric)**:
   - Launch `KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb`.
   - Run Cells 1–7 to start headless ComfyUI on port 8188.
   - Run Cell 8 to mount the Signed Execution Harness on port 8189.
   - Verify Cell 10 confirms verification envelope pass.
3. [ ] **Session 3 (Gateway & Bridge)**:
   - Launch `KAGGLE_SETUP/03_keystone_integrated_gateway.ipynb`.
   - Verify tunnel URLs are active.
   - Confirm worker registration returns HTTP 200 from Keystone Cloud Run API.
   - Confirm background heartbeat daemon is streaming pulses every 30s.
