#!/usr/bin/env python3
"""
Test full end-to-end live flow against running server on http://127.0.0.1:8000.
"""

import json
import time
import urllib.request

__test__ = False


def run_live_workflow(base: str = "http://127.0.0.1:8000") -> None:
    # 1. Register test user
    user_payload = json.dumps({
        "email": f"live-operator-{int(time.time())}@keystone.local",
        "password": "LivePassword123!",
        "display_name": "Live Operator"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/auth/register",
        data=user_payload,
        headers={"Content-Type": "application/json"}
    )
    auth_resp = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    token = auth_resp["access_token"]
    print(f"[+] Auth token acquired for tenant {auth_resp.get('user', {}).get('id')}")

    # 2. Compile prompt intent
    compile_payload = json.dumps({
        "intent": {
            "objective": "Cinematic Neo-Tokyo night skyline in rain",
            "visual_style": "Blade Runner Studio"
        },
        "playbook": "design",
        "profile": "reasoning"
    }).encode("utf-8")
    req_c = urllib.request.Request(
        f"{base}/v1/planning/compile",
        data=compile_payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    compiled = json.loads(urllib.request.urlopen(req_c).read().decode("utf-8"))
    p_hash = compiled.get("prompt_hash", "")[:16]
    print(f"[+] Compiled prompt hash: {p_hash}...")

    # 3. Create job
    job_payload = json.dumps({
        "request_text": "Cinematic Neo-Tokyo night skyline in rain",
        "action": {
            "action_type": "generate",
            "capability": "image.generation",
            "parameters": {
                "prompt": compiled["positive_prompt"],
                "negative_prompt": compiled["negative_prompt"],
                "aspect_ratio": "16:9",
                "width": 1024,
                "height": 576,
                "steps": 25,
                "guidance": 6.0
            },
            "rationale": "Customer create request via design playbook"
        },
        "capability_id": "image.generation",
        "provider_id": "comfyui"
    }).encode("utf-8")
    req_j = urllib.request.Request(
        f"{base}/v1/jobs",
        data=job_payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    job_data = json.loads(urllib.request.urlopen(req_j).read().decode("utf-8"))
    job_id = job_data["id"]
    print(f"[+] Job created: {job_id} state={job_data['state']}")

    # 3.1 Transition job through deterministic states to RUNNING
    transitions = ["VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED", "RUNNING"]
    for st in transitions:
        trans_payload = json.dumps({"next_state": st, "reason": f"Transition to {st}"}).encode("utf-8")
        req_t = urllib.request.Request(
            f"{base}/v1/jobs/{job_id}/transition",
            data=trans_payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        )
        t_res = json.loads(urllib.request.urlopen(req_t).read().decode("utf-8"))
        print(f"[+] Job transitioned to: {t_res['current_state']}")

    # 4. Generate asset
    auth_args = job_data.get("authorized_arguments", {})
    asset_payload = json.dumps({
        "prompt": auth_args.get("prompt", compiled["positive_prompt"]),
        "negative_prompt": auth_args.get("negative_prompt"),
        "width": auth_args.get("width", 1024),
        "height": auth_args.get("height", 576),
        "steps": auth_args.get("steps", 25),
        "cfg": auth_args.get("guidance", 6.0),
        "job_id": job_data["id"]
    }).encode("utf-8")
    req_a = urllib.request.Request(
        f"{base}/v1/assets/generate",
        data=asset_payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    asset_data = json.loads(urllib.request.urlopen(req_a).read().decode("utf-8"))
    print(f"[+] Asset generated: {asset_data['id']} byte_size={asset_data['byte_size']} download_url={asset_data['download_url']}")

    # 5. Fetch asset content
    content_req = urllib.request.Request(f"{base}{asset_data['download_url']}")
    with urllib.request.urlopen(content_req) as resp:
        content_bytes = resp.read()
        print(f"[+] Asset content fetched: {len(content_bytes)} bytes, content-type={resp.headers.get('content-type')}")

    print("[SUCCESS] Complete end-to-end live flow verified successfully!")


if __name__ == "__main__":
    run_live_workflow()

