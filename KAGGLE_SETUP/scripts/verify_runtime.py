import json
import os
import sys
import urllib.request

ENDPOINTS = {
    "vllm": os.getenv("VLLM_HEALTH_URL", "http://127.0.0.1:8001/health"),
    "comfyui": os.getenv("COMFYUI_HEALTH_URL", "http://127.0.0.1:8188/system_stats"),
    "keystone": os.getenv("KEYSTONE_HEALTH_URL", "http://127.0.0.1:8000/v1/health"),
}

failed = []
for name, url in ENDPOINTS.items():
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            print(json.dumps({"service": name, "status": response.status, "url": url}))
    except Exception as exc:
        failed.append({"service": name, "url": url, "error": str(exc)})

if failed:
    print(json.dumps({"failed": failed}, indent=2))
    sys.exit(1)
print("All KEYSTONE runtime health checks passed.")
