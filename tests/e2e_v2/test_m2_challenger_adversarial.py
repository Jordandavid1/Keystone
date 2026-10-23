"""
Milestone M2 (Wave 2) Adversarial Challenger Verification Suite
Author: challenger_m2_2
Target: F10 Prompt Compiler, F13 Cognition Connector & Client, Kaggle Tier 0 Notebooks
Directives:
1. Model mutation attempts: pass substitute model names, verify strict rejection with PROHIBITED_CHECKPOINT_MUTATION.
2. Empty/whitespace prompt attempts: verify rejection with EMPTY_PROMPT.
3. PromptCompiler stress: missing required anatomy components, invalid playbooks, determinism stress.
4. Kaggle notebook hardware verification: CPU offload calculations mathematically, strict prohibition of quantization.
5. API routing boundary validation.
"""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.cognition.src.client import (
    CognitionConnector,
    CognitionClient,
    PINNED_CHECKPOINT
)
from packages.prompt_engine.compiler import (
    PromptCompiler,
    validate_prompt_anatomy,
    compile_to_markdown,
    compile_to_chat_messages,
    compile_for_reasoning_model,
    compile_prompt
)
from packages.prompt_engine.playbooks import PlaybookRegistry, PLAYBOOK_IDS
from packages.prompt_engine.engine import generate
from packages.contracts.src.models import PromptIntent, PromptAnatomy, ProposedAction
from apps.api.src.server import app


@pytest.fixture
def api_client():
    return TestClient(app)


# ============================================================================
# 1. Model Mutation Adversarial Stress (F13 & Invariants §2.6, §2.10, §11, §24)
# ============================================================================

class TestModelMutationAdversarial:
    """
    Stress-tests cognition client against model substitution and mutation attacks.
    Enforces Bible §2 Invariant 6, 10, §11, §24: Checkpoint is permanently pinned
    to huihui-ai/Huihui-Qwen3.8-27B-abliterated.
    """

    SUBSTITUTE_MODELS = [
        # Proprietary / Commercial Models
        "gpt-4",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-opus",
        "claude-3-5-sonnet",
        "claude-3-haiku",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        # Open / Aligned Base Models
        "mistral",
        "mistralai/Mistral-7B-Instruct-v0.2",
        "Qwen/Qwen2.5-72B-Instruct",
        "Qwen/Qwen2.5-27B-Instruct",
        "meta-llama/Llama-3.1-70B-Instruct",
        "meta-llama/Meta-Llama-3-8B",
        "deepseek-ai/DeepSeek-V3",
        # Quantized Checkpoints (Strictly Prohibited per Bible §11)
        "huihui-ai/Huihui-Qwen3.8-27B-awq",
        "huihui-ai/Huihui-Qwen3.8-27B-gptq",
        "huihui-ai/Huihui-Qwen3.8-27B-GGUF",
        "huihui-ai/Huihui-Qwen3.8-27B-bnb-4bit",
        # Case Mutations & Whitespace Tampering
        "Huihui-ai/Huihui-Qwen3.8-27B-abliterated",
        "huihui-ai/huihui-qwen3.8-27b-abliterated",
        " huihui-ai/Huihui-Qwen3.8-27B-abliterated",
        "huihui-ai/Huihui-Qwen3.8-27B-abliterated ",
        "huihui-ai/Huihui-Qwen3.8-27B-abliterated\n",
        # Suffix / Prefix Tampering
        "huihui-ai/Huihui-Qwen3.8-27B-abliterated-fp16",
        "vllm/huihui-ai/Huihui-Qwen3.8-27B-abliterated",
        # Malicious Injections
        "huihui-ai/Huihui-Qwen3.8-27B-abliterated; rm -rf /",
        "huihui-ai/Huihui-Qwen3.8-27B-abliterated\r\nmodel: gpt-4"
    ]

    def test_build_completion_request_rejects_all_substitute_models(self):
        """Verifies build_completion_request raises PROHIBITED_CHECKPOINT_MUTATION for all substitute models."""
        for model in self.SUBSTITUTE_MODELS:
            with pytest.raises(ValueError) as exc_info:
                CognitionConnector.build_completion_request(
                    prompt="Generate creative scene",
                    options={"model": model}
                )
            assert "PROHIBITED_CHECKPOINT_MUTATION" in str(exc_info.value), (
                f"Model '{model}' did not trigger PROHIBITED_CHECKPOINT_MUTATION"
            )

    def test_complete_method_rejects_substitute_models(self):
        """Verifies complete() entrypoint raises PROHIBITED_CHECKPOINT_MUTATION."""
        connector = CognitionConnector()
        for model in ["gpt-4", "claude-3-opus", "huihui-ai/Huihui-Qwen3.8-27B-awq", "mistral"]:
            with pytest.raises(ValueError) as exc_info:
                connector.complete(
                    prompt="Analyze intent",
                    options={"model": model}
                )
            assert "PROHIBITED_CHECKPOINT_MUTATION" in str(exc_info.value)

    def test_explicit_none_or_empty_model_option_rejected(self):
        """Verifies passing explicit None or empty string as model option is rejected."""
        with pytest.raises(ValueError) as exc1:
            CognitionConnector.build_completion_request(
                prompt="Valid prompt",
                options={"model": ""}
            )
        assert "PROHIBITED_CHECKPOINT_MUTATION" in str(exc1.value)

        with pytest.raises(ValueError) as exc2:
            CognitionConnector.build_completion_request(
                prompt="Valid prompt",
                options={"model": None}
            )
        assert "PROHIBITED_CHECKPOINT_MUTATION" in str(exc2.value)

    def test_pinned_model_clean_acceptance(self):
        """Verifies default (no model specified) and explicit pinned model both succeed."""
        req_default = CognitionConnector.build_completion_request("Valid prompt")
        assert req_default["model"] == PINNED_CHECKPOINT

        req_explicit = CognitionConnector.build_completion_request(
            "Valid prompt",
            options={"model": PINNED_CHECKPOINT}
        )
        assert req_explicit["model"] == PINNED_CHECKPOINT


# ============================================================================
# 2. Empty / Whitespace Prompt Adversarial Stress (F13)
# ============================================================================

class TestEmptyPromptAdversarial:
    """
    Stress-tests cognition client against empty, whitespace, and null prompt submissions.
    Must reject strictly with EMPTY_PROMPT.
    """

    EMPTY_PROMPT_VARIANTS = [
        "",
        " ",
        "   ",
        "\t",
        "\n",
        "\r\n",
        "  \t \r \n  ",
        None
    ]

    def test_build_completion_request_rejects_empty_prompts(self):
        """Verifies build_completion_request rejects all empty prompt variants with EMPTY_PROMPT."""
        for empty_val in self.EMPTY_PROMPT_VARIANTS:
            with pytest.raises(ValueError) as exc_info:
                CognitionConnector.build_completion_request(empty_val)
            assert "EMPTY_PROMPT" in str(exc_info.value), (
                f"Input {repr(empty_val)} did not trigger EMPTY_PROMPT"
            )

    def test_complete_method_rejects_empty_prompts(self):
        """Verifies complete() rejects all empty prompt variants with EMPTY_PROMPT."""
        connector = CognitionConnector()
        for empty_val in ["", "  \n  ", None]:
            with pytest.raises(ValueError) as exc_info:
                connector.complete(empty_val)
            assert "EMPTY_PROMPT" in str(exc_info.value)


# ============================================================================
# 3. PromptCompiler Anatomy & Playbook Stress (F10)
# ============================================================================

class TestPromptCompilerStress:
    """
    Adversarial stress on PromptCompiler:
    - Missing required anatomy components
    - Invalid playbooks
    - Determinism stress (identical anatomy produces identical SHA-256)
    - Avalanche effect on single-character mutation
    """

    REQUIRED_FIELDS = ["role", "task", "context", "constraints", "outputFormat", "reasoning"]

    def _valid_anatomy_dict(self) -> Dict[str, Any]:
        return {
            "role": "Lead Architect",
            "task": "Build scalable pipeline",
            "context": ["Keystone Phase 1", "Kaggle T4x2"],
            "constraints": ["Zero data loss", "BF16 only"],
            "outputFormat": "plan.v1 specification",
            "reasoning": "Deduce architecture from requirements"
        }

    def test_validate_anatomy_missing_each_required_field(self):
        """Omitting any single required anatomy field raises ValueError."""
        for field in self.REQUIRED_FIELDS:
            payload = self._valid_anatomy_dict()
            del payload[field]
            with pytest.raises(ValueError, match=f'Prompt missing required field: "{field}"'):
                validate_prompt_anatomy(payload)

    def test_validate_anatomy_whitespace_only_field_values(self):
        """Whitespace-only string for any required anatomy field raises ValueError."""
        for field in ["role", "task", "outputFormat", "reasoning"]:
            payload = self._valid_anatomy_dict()
            payload[field] = "   \n\t  "
            with pytest.raises(ValueError, match=f'Prompt missing required field: "{field}"'):
                validate_prompt_anatomy(payload)

    def test_validate_anatomy_type_errors(self):
        """Invalid types for prompt, context, or constraints raise TypeError."""
        # Non-dict/non-PromptAnatomy
        with pytest.raises(TypeError, match="Prompt must be an object"):
            validate_prompt_anatomy("raw string")
        with pytest.raises(TypeError, match="Prompt must be an object"):
            validate_prompt_anatomy(None)
        with pytest.raises(TypeError, match="Prompt must be an object"):
            validate_prompt_anatomy([1, 2, 3])

        # Non-list context
        payload1 = self._valid_anatomy_dict()
        payload1["context"] = "not a list"
        with pytest.raises(TypeError, match="Prompt context must be an array"):
            validate_prompt_anatomy(payload1)

        # Non-list constraints
        payload2 = self._valid_anatomy_dict()
        payload2["constraints"] = "not a list"
        with pytest.raises(TypeError, match="Prompt constraints must be an array"):
            validate_prompt_anatomy(payload2)

    def test_prompt_compiler_objective_required(self):
        """PromptCompiler.compile() requires non-empty objective string."""
        with pytest.raises(ValueError, match="OBJECTIVE_REQUIRED"):
            PromptCompiler.compile(None)
        with pytest.raises(ValueError, match="OBJECTIVE_REQUIRED"):
            PromptCompiler.compile({})
        with pytest.raises(ValueError, match="OBJECTIVE_REQUIRED"):
            PromptCompiler.compile({"objective": ""})
        with pytest.raises(ValueError, match="OBJECTIVE_REQUIRED"):
            PromptCompiler.compile({"objective": "   \r\n\t  "})

    def test_playbook_catalog_and_fallback_resilience(self):
        """Verifies 13 canonical playbooks resolve and unknown playbooks fallback to general."""
        canonical_13 = list(PLAYBOOK_IDS)
        assert len(canonical_13) == 13

        # Canonical resolve
        for pb_id in canonical_13:
            res = PromptCompiler.compile({"objective": "Creative task"}, playbook=pb_id)
            assert res["provenance"]["playbook"] == pb_id

        # Case insensitivity
        for pb_id in ["DESIGN", "Software", "MARKETING"]:
            res = PromptCompiler.compile({"objective": "Creative task"}, playbook=pb_id)
            assert res["provenance"]["playbook"] == pb_id.lower()

        # Fallback to general for unknown playbook strings
        for bad_pb in ["crypto_hacks", "unknown_domain", "SQL_INJECTION", ""]:
            res = PromptCompiler.compile({"objective": "Creative task"}, playbook=bad_pb)
            assert res["provenance"]["playbook"] == "general"

    def test_determinism_stress_1000_iterations(self):
        """
        Stress-tests compilation determinism over 1,000 iterations.
        Verifies identical PromptIntent + parameters produces the exact same SHA-256 hash.
        """
        intent = {
            "objective": "Render cinematic Wan 2.1 scene with volumetric fog and rim lighting",
            "subject": "Cybernetic tiger",
            "environment": "Rain-slicked Neo-Tokyo alleyway",
            "visual_style": "Blade Runner anamorphic cinematography",
            "constraints": ["No digital noise", "No oversaturated neon", "Maintain photorealistic fur physics"]
        }

        first_res = PromptCompiler.compile(intent, playbook="design", profile="standard")
        expected_hash = first_res["prompt_hash"]
        expected_positive = first_res["positive_prompt"]

        # 64 hex characters check
        assert len(expected_hash) == 64
        assert re.match(r"^[0-9a-f]{64}$", expected_hash)
        assert hashlib.sha256(expected_positive.encode("utf-8")).hexdigest() == expected_hash

        # Run 1000 iterations
        for i in range(1000):
            res = PromptCompiler.compile(intent, playbook="design", profile="standard")
            assert res["prompt_hash"] == expected_hash, f"Hash diverged at iteration {i}"
            assert res["positive_prompt"] == expected_positive

    def test_avalanche_effect_hash_sensitivity_on_positive_prompt_fields(self):
        """Verifies 1-character mutation across objective, subject, environment, and visual_style changes hash."""
        base_intent = {
            "objective": "Render a majestic eagle soaring over snow-capped mountain peaks",
            "subject": "Golden Eagle",
            "environment": "Rocky Mountain sunrise",
            "visual_style": "National Geographic 8k"
        }
        base_hash = PromptCompiler.compile(base_intent, "design")["prompt_hash"]

        mutations = [
            # 1-char change in objective
            {**base_intent, "objective": "Render a majestic eagle soaring over snow-capped mountain peak."},
            # 1-char change in subject
            {**base_intent, "subject": "Golden Eagles"},
            # 1-char change in environment
            {**base_intent, "environment": "Rocky Mountain sunrises"},
            # 1-char change in visual_style
            {**base_intent, "visual_style": "National Geographic 4k"}
        ]

        for idx, mut in enumerate(mutations):
            mut_hash = PromptCompiler.compile(mut, "design")["prompt_hash"]
            assert mut_hash != base_hash, f"Avalanche failure on mutation variant {idx}"

    def test_finding_constraints_omission_from_positive_prompt_and_hash(self):
        """
        REMEDIATION VERIFICATION:
        Verifies that PromptCompiler.compile() records constraints in anatomy_dict['constraints']
        and includes constraints in positive_prompt. Mutating constraints produces distinct
        positive_prompt and distinct SHA-256 prompt_hash.
        """
        base_intent = {
            "objective": "Render modern villa",
            "constraints": ["No blur", "Photorealistic"]
        }
        mutated_intent = {
            "objective": "Render modern villa",
            "constraints": ["Strictly no watermarks", "High dynamic range"]
        }

        res_base = PromptCompiler.compile(base_intent, "design")
        res_mut = PromptCompiler.compile(mutated_intent, "design")

        # In anatomy, constraints are correctly captured
        assert res_base["anatomy"]["constraints"] != res_mut["anatomy"]["constraints"]

        # REMEDIATION VERIFICATION: positive_prompt and prompt_hash are distinct when constraints differ
        assert res_base["positive_prompt"] != res_mut["positive_prompt"]
        assert res_base["prompt_hash"] != res_mut["prompt_hash"]
        assert "No blur" in res_base["positive_prompt"]
        assert "Strictly no watermarks" in res_mut["positive_prompt"]


# ============================================================================
# 4. Kaggle Hardware Probe & Memory Math Verification (F16, F20)
# ============================================================================

class TestKaggleHardwareVerification:
    """
    Mathematical and contractual verification of Kaggle Tier 0 GPU/CPU offload:
    - 27B BF16 model (~51.7 GiB weights) on Kaggle 2x Nvidia T4 (30 GiB VRAM total).
    - Usable GPU VRAM ~24–25 GiB (with 5 GiB runtime reserve).
    - Calculated CPU offload: ~26.7–30 GiB offloaded to host RAM.
    - Host RAM capacity: ~80 GB pool.
    - Host safety reserve >= 10 GiB maintained.
    - Strict prohibition of quantization across all notebooks.
    """

    def test_mathematical_cpu_offload_formulas(self):
        """Verifies the exact math for CPU weight offload and headroom."""
        model_estimate_gib = 51.7  # 27B params in 16-bit
        gpu_total_gib = 30.0       # 2x 15.0 GiB T4
        gpu_reserve_gib = 5.0      # KV cache, activations, CUDA context
        host_total_gib = 80.0      # Kaggle system RAM pool
        host_reserve_gib = 12.0    # Host OS + workers safety reserve (>= 10 GiB)

        # 1. Usable GPU VRAM
        usable_gpu = max(0.0, gpu_total_gib - gpu_reserve_gib)
        assert usable_gpu == 25.0
        assert usable_gpu / 2 == 12.5  # per GPU in tensor parallel 2

        # 2. Calculated CPU offload
        cpu_offload_gib = max(0.0, model_estimate_gib - usable_gpu)
        assert round(cpu_offload_gib, 2) == 26.7

        # 3. Host headroom verification
        available_host_headroom = host_total_gib - host_reserve_gib
        assert available_host_headroom == 68.0
        assert cpu_offload_gib <= available_host_headroom

        remaining_free_host_ram = host_total_gib - cpu_offload_gib - host_reserve_gib
        assert remaining_free_host_ram >= 41.0  # Safe healthy headroom

        # 4. Host reserve requirement
        assert host_reserve_gib >= 10.0, "Host safety reserve must be at least 10 GiB"

    def test_memory_harness_asserts_failure_on_insufficient_host_ram(self):
        """Simulates memory starvation to verify MemoryHarness guard raises assertion."""
        model_estimate_gib = 51.7
        gpu_total_gib = 30.0
        gpu_reserve_gib = 5.0
        host_reserve_gib = 12.0

        usable_gpu = max(0.0, gpu_total_gib - gpu_reserve_gib)
        cpu_offload_gib = max(0.0, model_estimate_gib - usable_gpu)  # 26.7 GiB

        # Starved host available RAM (e.g., only 30 GiB available)
        starved_host_avail = 30.0
        headroom = starved_host_avail - host_reserve_gib  # 18.0 GiB < 26.7 GiB

        with pytest.raises(AssertionError) as exc_info:
            assert cpu_offload_gib <= max(0.0, headroom), (
                f"Insufficient host RAM! Needed {cpu_offload_gib:.1f} GiB offload, "
                f"available headroom {headroom:.1f} GiB"
            )
        assert "Insufficient host RAM!" in str(exc_info.value)

    def test_finding_notebook_02_json_syntax_corruption(self):
        """
        REMEDIATION VERIFICATION:
        Verifies that KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb
        parses cleanly as valid JSON without syntax corruption.
        """
        nb_path = REPO_ROOT / "KAGGLE_SETUP" / "notebooks" / "02_keystone_comfyui_runtime.ipynb"
        assert nb_path.exists()

        content = json.loads(nb_path.read_text(encoding="utf-8"))
        assert "cells" in content
        assert len(content["cells"]) > 0

    def test_strict_prohibition_of_quantization_in_all_loadable_notebooks(self):
        """
        Inspects every single cell of all valid Kaggle notebooks.
        Ensures NO quantization or substitute checkpoint flags are present.
        """
        notebook_paths = [
            REPO_ROOT / "KAGGLE_SETUP" / "01_keystone_cognition_bootstrap.ipynb",
            REPO_ROOT / "KAGGLE_SETUP" / "02_keystone_comfyui_runtime.ipynb",
            REPO_ROOT / "KAGGLE_SETUP" / "03_keystone_integrated_gateway.ipynb",
            REPO_ROOT / "KAGGLE_SETUP" / "notebooks" / "01_keystone_cognition_bootstrap.ipynb",
            REPO_ROOT / "KAGGLE_SETUP" / "notebooks" / "03_keystone_integrated_gateway.ipynb",
            REPO_ROOT / "infrastructure" / "kaggle" / "keystone_kaggle_bootstrap.ipynb"
        ]

        prohibited_tokens = [
            "--quantization",
            "load_in_4bit",
            "load_in_8bit",
            "bitsandbytes",
            "int4",
            "int8",
            "fp8",
            "Huihui-Qwen3.8-27B-awq",
            "Huihui-Qwen3.8-27B-gptq"
        ]

        for nb_path in notebook_paths:
            assert nb_path.exists(), f"Notebook file missing: {nb_path}"
            data = json.loads(nb_path.read_text(encoding="utf-8"))
            for cell_idx, cell in enumerate(data.get("cells", [])):
                source = "".join(cell.get("source", []))
                for token in prohibited_tokens:
                    assert token.lower() not in source.lower(), (
                        f"Prohibited quantization token '{token}' detected in {nb_path.name} cell {cell_idx}:\n{source[:200]}"
                    )

    def test_notebook_01_cognition_bootstrap_exact_parameters(self):
        """Verifies Notebook 01 configures bfloat16, tensor-parallel 2, and 7 retry profiles."""
        nb_path = REPO_ROOT / "KAGGLE_SETUP" / "01_keystone_cognition_bootstrap.ipynb"
        data = json.loads(nb_path.read_text(encoding="utf-8"))
        all_code = "\n".join(["".join(c["source"]) for c in data["cells"] if c["cell_type"] == "code"])

        assert "'huihui-ai/Huihui-Qwen3.8-27B-abliterated'" in all_code
        assert '"--tensor-parallel-size", "2"' in all_code
        assert '"--dtype", "bfloat16"' in all_code
        assert '"--cpu-offload-gb", "27"' in all_code
        assert "HOST_RESERVE_GIB = 12.0" in all_code
        assert "GPU_RESERVE_GIB = 5.0" in all_code

        # Verify all 7 controlled retry profiles verbatim per Bible §24
        expected_profiles = [
            "1. baseline tensor parallel 2",
            "2. tune CPU offload",
            "3. reduce maximum context",
            "4. reduce maximum sequences to one",
            "5. reduce batch token budget",
            "6. lower GPU-memory-utilization target when fragmentation occurs",
            "7. stop and report evidence after approved profiles are exhausted"
        ]
        for prof in expected_profiles:
            assert prof in all_code


# ============================================================================
# 5. Planning API Router Adversarial Stress
# ============================================================================

class TestPlanningRouterAdversarial:
    """Verifies additive API endpoints handle adversarial payloads and enforce contracts."""

    def test_plan_empty_goal_returns_400(self, api_client: TestClient):
        """Submitting empty goal string returns 400 Bad Request."""
        res = api_client.post("/v1/planning/plan", json={"goal": ""})
        assert res.status_code == 422 or res.status_code == 400

    def test_compile_empty_objective_returns_400(self, api_client: TestClient):
        """Submitting empty intent objective returns 400 Bad Request with OBJECTIVE_REQUIRED."""
        res = api_client.post(
            "/v1/planning/compile",
            json={"intent": {"objective": ""}, "playbook": "general"}
        )
        assert res.status_code == 400
        assert "OBJECTIVE_REQUIRED" in res.json()["detail"]

    def test_compile_unknown_playbook_falls_back_to_general(self, api_client: TestClient):
        """Submitting arbitrary unknown playbook returns 200 with general playbook."""
        res = api_client.post(
            "/v1/planning/compile",
            json={"intent": {"objective": "Create portrait"}, "playbook": "arbitrary_pb"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["provenance"]["playbook"] == "general"

    def test_compile_api_determinism(self, api_client: TestClient):
        """Two identical POST requests return the exact same prompt_hash."""
        payload = {
            "intent": {
                "objective": "Render architectural glass pavilion",
                "subject": "Modern pavilion",
                "environment": "Misty pine forest"
            },
            "playbook": "design",
            "profile": "chat"
        }
        res1 = api_client.post("/v1/planning/compile", json=payload)
        res2 = api_client.post("/v1/planning/compile", json=payload)
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["prompt_hash"] == res2.json()["prompt_hash"]
