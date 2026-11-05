from __future__ import annotations

import asyncio
import sqlite3
import unittest
from apps.api.src.creative import h3, h3_manifest
from apps.api.src.keystone import cognition, prompting
from apps.api.src.keystone.models import PromptCompilationRequest, PromptIntent


def compile_text(text: str, references: int, hint: str = "animate"):
    return asyncio.run(prompting.compile_for_generation("job-test", text, hint, references))


def decisions_of(compiled):
    return {item["id"]: item["decision"] for item in compiled.provenance["tool_suggestions"]}


class SeatedModel:
    """Test double for the embedded model: it proposes structure and tries to rewrite the request."""

    async def reason(self, request):
        return cognition.CognitiveResult(
            reasoning_id="reasoning-1",
            confidence=0.9,
            intent=PromptIntent(
                objective="REWRITTEN BY THE MODEL",
                camera="slow dolly in",
                mood="tense",
                references=["subject identity", "background style"],
                constraints=["no text overlays"],
            ),
        )


class BrokenModel:
    async def reason(self, request):
        raise RuntimeError("model unreachable")


class CompileTests(unittest.TestCase):
    def tearDown(self):
        cognition.unregister()

    def test_the_users_words_survive_and_references_are_tagged(self):
        compiled = compile_text("slow push-in on her face", 2)
        self.assertIn("slow push-in on her face", compiled.positive_prompt)
        self.assertIn("<Picture 1>", compiled.positive_prompt)
        self.assertIn("<Picture 2>", compiled.positive_prompt)
        self.assertIsNone(compiled.negative_prompt)
        self.assertEqual(compiled.parameters["reference_images"], 2)
        self.assertEqual(compiled.provenance["cognition"], {"status": "not_connected"})
        self.assertEqual(decisions_of(compiled), {"reference_tags": "applied", "reference_roles": "declined"})

    def test_explicit_tags_are_left_alone(self):
        text = "<Picture 1> walks left while <Picture 2> watches"
        compiled = compile_text(text, 2)
        self.assertEqual(compiled.positive_prompt, text)
        self.assertEqual(decisions_of(compiled), {"reference_tags": "satisfied", "reference_roles": "satisfied"})

    def test_no_references_means_nothing_is_added(self):
        compiled = compile_text("a quiet street at dawn", 0)
        self.assertEqual(compiled.positive_prompt, "a quiet street at dawn")
        self.assertEqual(decisions_of(compiled), {"reference_tags": "declined", "reference_roles": "declined"})

    def test_references_beyond_the_tools_limit_are_not_tagged(self):
        compiled = compile_text("x", 5)
        self.assertNotIn("<Picture 3>", compiled.positive_prompt)
        self.assertEqual(compiled.parameters["reference_images"], 2)

    def test_a_tool_that_suggests_nothing_changes_nothing(self):
        manifest = h3_manifest.manifest()
        manifest.metadata["prompt_suggestions"] = []
        request = PromptCompilationRequest(
            request_id="job-test",
            target_capability=manifest.capability_id,
            target_provider=manifest.provider_id,
            intent=PromptIntent(objective="walk"),
            user_context={"reference_count": 2},
            capability=manifest,
        )
        compiled = asyncio.run(prompting.H3PromptCompiler().compile(request))
        self.assertEqual(compiled.positive_prompt, "walk")
        self.assertEqual(compiled.provenance["tool_suggestions"], [])

    def test_a_disabled_or_foreign_capability_is_refused(self):
        manifest = h3_manifest.manifest()
        request = PromptCompilationRequest(
            request_id="job-test",
            target_capability=manifest.capability_id,
            target_provider=manifest.provider_id,
            intent=PromptIntent(objective="walk"),
            capability=manifest,
        )
        manifest.enabled = False
        with self.assertRaises(prompting.CompilationError):
            asyncio.run(prompting.H3PromptCompiler().compile(request))
        manifest.enabled = True
        request.target_provider = "some-other-provider"
        with self.assertRaises(prompting.CompilationError):
            asyncio.run(prompting.H3PromptCompiler().compile(request))

    def test_an_empty_request_is_refused(self):
        with self.assertRaises(prompting.CompilationError):
            compile_text("   ", 1)

    def test_hash_is_stable_and_detects_tampering(self):
        first = compile_text("same words", 1)
        again = compile_text("same words", 1)
        other = compile_text("other words", 1)
        self.assertEqual(first.prompt_hash, again.prompt_hash)
        self.assertNotEqual(first.prompt_hash, other.prompt_hash)
        self.assertEqual(first.prompt_hash, prompting.compute_hash(first))

        conn = sqlite3.connect(":memory:")
        prompting.ensure_schema(conn)
        first.positive_prompt += " tampered"
        with self.assertRaises(prompting.CompilationError):
            prompting.record(conn, "job-test", first)

    def test_a_seated_model_adds_structure_but_never_rewrites_the_request(self):
        cognition.register(SeatedModel())
        compiled = compile_text("she turns to the window", 2)
        text = compiled.positive_prompt
        self.assertIn("she turns to the window", text)
        self.assertNotIn("REWRITTEN", text)
        self.assertIn("<Picture 1>: subject identity.", text)
        self.assertIn("<Picture 2>: background style.", text)
        self.assertIn("Camera: slow dolly in", text)
        self.assertIn("Mood: tense", text)
        self.assertIn("Constraints: no text overlays", text)

        record = compiled.provenance["cognition"]
        self.assertEqual(record["status"], "used")
        self.assertEqual(record["reasoning_id"], "reasoning-1")
        self.assertEqual(record["proposed_objective"], "REWRITTEN BY THE MODEL")
        self.assertEqual(set(decisions_of(compiled).values()), {"applied"})

    def test_a_seated_model_that_fails_stops_the_job(self):
        cognition.register(BrokenModel())
        with self.assertRaises(prompting.CompilationError) as raised:
            compile_text("anything", 1)
        self.assertIn("KEYSTONE_COGNITION_FAILED", str(raised.exception))

    def test_two_way_digest_and_compile_prompt(self):
        cognition.register(SeatedModel())
        digested = asyncio.run(
            prompting.digest_and_compile_prompt(
                user_text="Cyberpunk detective walking in neon rain",
                reference_count=1,
                intent_hint="animate",
            )
        )
        self.assertIn("Cyberpunk detective walking in neon rain", digested.positive_prompt)
        self.assertIn("<Picture 1>", digested.positive_prompt)
        self.assertEqual(len(digested.prompt_hash), 64)
        self.assertEqual(digested.provenance["cognition"]["status"], "used")

    def test_h3_workflow_compiles_from_manifest(self):
        import json
        wf_path = h3.workflow_path()
        self.assertIsNotNone(wf_path)
        template = json.loads(wf_path.read_text(encoding="utf-8"))
        prepared = h3._prepare(template, "<Picture 1> walks forward in neon rain", ["anchor.png"])
        api_graph = h3._to_api_prompt(prepared)
        self.assertIn("138", api_graph)
        self.assertIn("148", api_graph)


if __name__ == "__main__":
    unittest.main()
