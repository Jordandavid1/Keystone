# Cognition Service

Adapter boundary for the fixed KEYSTONE cognitive checkpoint and vLLM runtime.

Bootstrap profile:

- two NVIDIA T4 GPUs
- tensor parallel size 2
- BF16 checkpoint
- measured CPU weight offload
- runtime hardware discovery
- short initial context
- one sequence initially
- no silent checkpoint substitution
