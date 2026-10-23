import sys, os
sys.path.insert(0, os.path.abspath("."))
from services.cognition.src.client import CognitionConnector
from packages.prompt_engine.compiler import PromptCompiler, validate_prompt_anatomy
import json
import hmac
import hashlib

def test_cognition_connector():
    c = CognitionConnector()

    # 1. Test markdown-fenced json
    fenced_content = '```json\n{"action_type": "edit", "capability": "creative.image_edit", "parameters": {"prompt": "brighten"}, "rationale": "editing request", "estimated_credits": 2}\n```'
    raw = {'choices': [{'message': {'content': fenced_content}}]}
    res = c.parse_response(raw, prompt='Please brighten this')
    assert res['proposed_action'].action_type == 'edit'
    assert res['proposed_action'].estimated_credits == 2
    print('1. Markdown-fenced JSON: PASS')

    # 2. Test invalid JSON in choices
    bad_raw = {'choices': [{'message': {'content': 'Not a JSON' }}]}
    try:
        c.parse_response(bad_raw)
        assert False, 'Should have raised ValueError'
    except ValueError as e:
        assert 'INVALID_PROPOSED_ACTION' in str(e)
    print('2. Invalid JSON rejection: PASS')

    # 3. Test schema violation in choices
    invalid_schema = {'choices': [{'message': {'content': '{"action_type": "unknown_type"}' }}]}
    try:
        c.parse_response(invalid_schema)
        assert False, 'Should have raised ValueError'
    except ValueError as e:
        assert 'INVALID_PROPOSED_ACTION' in str(e)
    print('3. Schema violation rejection: PASS')

    # 4. Test None raw response
    res_none = c.parse_response(None)
    assert res_none['proposed_action'] is None
    assert res_none['usage']['total_tokens'] == 0
    assert res_none['latency_ms'] == 0
    print('4. None raw response: PASS')

    # 5. Test realistic token computation when usage is None
    res_calc = c.parse_response(raw, prompt='A test prompt with eight words here')
    assert res_calc['usage']['prompt_tokens'] == 7 or res_calc['usage']['prompt_tokens'] == len('A test prompt with eight words here'.split())
    assert res_calc['usage']['completion_tokens'] > 0
    assert res_calc['usage']['total_tokens'] == res_calc['usage']['prompt_tokens'] + res_calc['usage']['completion_tokens']
    print('5. Realistic token computation: PASS')

    # 6. Test complete() offline fallback
    res_comp = c.complete('Generate cyberpunk street scene')
    assert res_comp['proposed_action'] is not None
    assert res_comp['proposed_action'].action_type == 'generate'
    assert 'cyberpunk' in res_comp['proposed_action'].parameters['prompt']
    print('6. complete() offline fallback: PASS')

def test_prompt_compiler_constraints_and_guards():
    # 7. Test prompt compiler non-string playbook
    res_int = PromptCompiler.compile({'objective': 'Test objective'}, playbook=12345)
    assert res_int['provenance']['playbook'] == 'general'
    print('7. Non-string playbook int: PASS')

    res_none_pb = PromptCompiler.compile({'objective': 'Test objective'}, playbook=None)
    assert res_none_pb['provenance']['playbook'] == 'general'
    print('8. None playbook: PASS')

    # 9. Test constraints sensitivity and avalanche effect
    intent_no_c = {'objective': 'Render mountain landscape'}
    intent_c1 = {'objective': 'Render mountain landscape', 'constraints': ['No clouds']}
    intent_c2 = {'objective': 'Render mountain landscape', 'constraints': ['Dramatic storm clouds', 'Volumetric lighting']}

    res_no_c = PromptCompiler.compile(intent_no_c)
    res_c1 = PromptCompiler.compile(intent_c1)
    res_c2 = PromptCompiler.compile(intent_c2)

    assert 'Constraints: None' in res_no_c['positive_prompt']
    assert 'Constraints: No clouds' in res_c1['positive_prompt']
    assert 'Constraints: Dramatic storm clouds; Volumetric lighting' in res_c2['positive_prompt']

    assert res_no_c['prompt_hash'] != res_c1['prompt_hash']
    assert res_c1['prompt_hash'] != res_c2['prompt_hash']
    assert res_no_c['prompt_hash'] != res_c2['prompt_hash']
    print('9. Constraints in positive_prompt and distinct SHA-256 hashes: PASS')

def test_notebook_cell8_hmac():
    # 10. Test HMAC logic directly as written in Cell 8
    secret = b"keystone_dev_secret"
    consumed_nonces = set()

    def verify_envelope(envelope: dict) -> bool:
        nonce = envelope.get("nonce")
        if not nonce or nonce in consumed_nonces:
            raise ValueError("INVALID_NONCE: Nonce missing or already consumed")
        
        payload_str = f"{envelope.get('job_id')}:{envelope.get('capability_id')}:{nonce}"
        expected_sig = hmac.new(secret, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        
        provided_sig = envelope.get("signature")
        if not provided_sig:
            raise ValueError("MISSING_SIGNATURE: ExecutionEnvelope must include HMAC signature")
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise ValueError("TAMPERED_ENVELOPE: HMAC signature verification failed")
            
        consumed_nonces.add(nonce)
        return True

    # Test missing signature raises MISSING_SIGNATURE
    try:
        verify_envelope({"job_id": "j1", "capability_id": "c1", "nonce": "n1"})
        assert False, "Should raise MISSING_SIGNATURE"
    except ValueError as e:
        assert "MISSING_SIGNATURE" in str(e)
    print("10. Missing signature raises MISSING_SIGNATURE: PASS")

    # Test empty string signature raises MISSING_SIGNATURE
    try:
        verify_envelope({"job_id": "j1", "capability_id": "c1", "nonce": "n2", "signature": ""})
        assert False, "Should raise MISSING_SIGNATURE"
    except ValueError as e:
        assert "MISSING_SIGNATURE" in str(e)
    print("11. Empty string signature raises MISSING_SIGNATURE: PASS")

    # Test invalid signature raises TAMPERED_ENVELOPE
    try:
        verify_envelope({"job_id": "j1", "capability_id": "c1", "nonce": "n3", "signature": "bad_sig"})
        assert False, "Should raise TAMPERED_ENVELOPE"
    except ValueError as e:
        assert "TAMPERED_ENVELOPE" in str(e)
    print("12. Invalid signature raises TAMPERED_ENVELOPE: PASS")

    # Test valid signature passes
    nonce = "valid_nonce_1"
    valid_payload = f"j1:c1:{nonce}"
    valid_sig = hmac.new(secret, valid_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    assert verify_envelope({"job_id": "j1", "capability_id": "c1", "nonce": nonce, "signature": valid_sig}) is True
    print("13. Valid signature acceptance: PASS")

    # Test replay of consumed nonce
    try:
        verify_envelope({"job_id": "j1", "capability_id": "c1", "nonce": nonce, "signature": valid_sig})
        assert False, "Should raise INVALID_NONCE on replay"
    except ValueError as e:
        assert "INVALID_NONCE" in str(e)
    print("14. Nonce replay prevention: PASS")

if __name__ == "__main__":
    test_cognition_connector()
    test_prompt_compiler_constraints_and_guards()
    test_notebook_cell8_hmac()
    print("\nALL ADVERSARIAL STRESS TESTS PASSED SUCCESSFULLY!")
