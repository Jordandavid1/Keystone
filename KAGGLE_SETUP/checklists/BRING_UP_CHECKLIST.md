# Kaggle Bring-Up Checklist

## Account preparation

- [ ] Kaggle account has phone verification if required for accelerator access
- [ ] Notebook accelerator set to GPU T4 x2
- [ ] Internet access enabled only for dependency/model retrieval
- [ ] Persistent dataset or approved external object storage selected for caches
- [ ] Required secrets entered through Kaggle Secrets, not notebook cells

## Cognition runtime

- [ ] Both T4 GPUs detected
- [ ] Available host RAM measured
- [ ] CUDA and driver reported
- [ ] Exact Qwen checkpoint confirmed
- [ ] Model files downloaded successfully
- [ ] Tensor parallel size set to 2
- [ ] CPU offload calculated from measured memory
- [ ] Conservative context configured
- [ ] vLLM health endpoint passes
- [ ] Plain text generation passes
- [ ] Structured ProposedAction output validates
- [ ] Vision input test passes
- [ ] Peak GPU and host RAM recorded
- [ ] Restart test passes without redownloading avoidable assets

## Creative runtime

- [ ] ComfyUI starts
- [ ] API endpoint responds
- [ ] Required custom nodes are pinned and installed
- [ ] Workflow JSON files are present
- [ ] Image generation smoke test passes
- [ ] Image-to-video smoke test passes
- [ ] Outputs are written to persistent/object storage
- [ ] Failure and cancellation behavior recorded

## KEYSTONE integration

- [ ] KEYSTONE local brain test passes
- [ ] `plan.v1` compatibility test passes
- [ ] Capability registry loads
- [ ] Authority decision validates
- [ ] ExecutionEnvelope is required by worker
- [ ] Job event stream works
- [ ] Generated asset returns to project/session
- [ ] Prompt provenance is stored
- [ ] End-to-end customer flow passes
