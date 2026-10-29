import os
import sys
import json
import re
import urllib.request
import urllib.error

ROAMING_PATH = r"C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat"
CONTROL_TOKEN_FILE = os.path.join(ROAMING_PATH, "data", "atomic-core", "control-token")
PUBLIC_TOKEN = "sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay"
CF_URL = "https://likewise-transmission-violations-investigations.trycloudflare.com"

def mask_secret(s):
    if not s or len(s) < 8:
        return "***"
    return f"{s[:6]}...{s[-4:]} (length {len(s)})"

def test_http_endpoint(url, headers=None, method="GET", body=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    if body is not None:
        if isinstance(body, (dict, list)):
            req.data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        elif isinstance(body, bytes):
            req.data = body
        else:
            req.data = str(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read()
            try:
                decoded = raw.decode("utf-8")
                try:
                    js = json.loads(decoded)
                    return status, js
                except:
                    return status, decoded[:1000]
            except:
                return status, f"<binary: {len(raw)} bytes>"
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="ignore")[:1000]
        except:
            pass
        return e.code, err_body
    except Exception as e:
        return None, str(e)

def run_deep_survey():
    with open(CONTROL_TOKEN_FILE, "r", encoding="utf-8") as f:
        control_token = f.read().strip()
    
    control_headers = {"Authorization": f"Bearer {control_token}"}
    public_headers = {"Authorization": f"Bearer {PUBLIC_TOKEN}"}

    print("=== 1. CONTROL API DETAILED RESULTS ===")
    
    # 1a. /cloud/providers
    st, res = test_http_endpoint("http://127.0.0.1:56603/atomic/v1/cloud/providers", headers=control_headers)
    print(f"\nGET /cloud/providers -> Status {st}")
    if isinstance(res, dict) and "providers" in res:
        print(f"Total providers: {len(res['providers'])}")
        for p in res["providers"]:
            models = p.get("models", [])
            print(f"- Provider: {p.get('provider')} | Base URL: {p.get('base_url')} | Models ({len(models)}): {models[:5]}")

    # 1b. /server/selection
    st, res = test_http_endpoint("http://127.0.0.1:56603/atomic/v1/server/selection", headers=control_headers)
    print(f"\nGET /server/selection -> Status {st}")
    print(json.dumps(res, indent=2))

    # 1c. /diffusion/video/gallery with offset=0
    for q in ["?offset=0", "?offset=0&limit=10"]:
        url = f"http://127.0.0.1:56603/atomic/v1/diffusion/video/gallery{q}"
        st, res = test_http_endpoint(url, headers=control_headers)
        print(f"\nGET /diffusion/video/gallery{q} -> Status {st}")
        print(json.dumps(res, indent=2) if isinstance(res, (dict, list)) else res)

    print("\n=== 2. PUBLIC API DETAILED RESULTS ===")
    # 2a. Local 127.0.0.1:1337/v1/models
    st, res = test_http_endpoint("http://127.0.0.1:1337/v1/models", headers=public_headers)
    print(f"\nGET http://127.0.0.1:1337/v1/models -> Status {st}")
    if isinstance(res, dict) and "data" in res:
        model_ids = [m.get("id") for m in res["data"]]
        print(f"Total models: {len(model_ids)}")
        print(f"Sample models: {model_ids[:10]}")
        print(f"PinkCherry in models: {'PinkCherry-MiniMax-H3' in model_ids}")

    # 2b. Local 127.0.0.1:1337/v1/videos
    st, res = test_http_endpoint("http://127.0.0.1:1337/v1/videos", headers=public_headers)
    print(f"\nGET http://127.0.0.1:1337/v1/videos -> Status {st}")
    print(json.dumps(res, indent=2) if isinstance(res, (dict, list)) else res)

    print("\n=== 3. CLOUDFLARE TUNNEL LIVE CONNECTIVITY ===")
    print(f"Testing public tunnel URL: {CF_URL}")
    st, res = test_http_endpoint(f"{CF_URL}/v1/models", headers=public_headers, timeout=10)
    print(f"GET {CF_URL}/v1/models -> Status {st}")
    if isinstance(res, dict) and "data" in res:
        model_ids = [m.get("id") for m in res["data"]]
        print(f"Tunnel models count: {len(model_ids)}")
    else:
        print(f"Response: {res}")

    st, res = test_http_endpoint(f"{CF_URL}/v1/videos", headers=public_headers, timeout=10)
    print(f"GET {CF_URL}/v1/videos -> Status {st}")
    print(json.dumps(res, indent=2) if isinstance(res, (dict, list)) else res)

    print("\n=== 4. SETTINGS & REMOTE ACCESS CONFIGURATION ===")
    settings_file = os.path.join(ROAMING_PATH, "data", "atomic-core", "settings.json")
    if os.path.exists(settings_file):
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)
        # mask any keys
        def sanitize(obj):
            if isinstance(obj, dict):
                return {k: ("[MASKED]" if any(x in k.lower() for x in ["key", "token", "secret"]) else sanitize(v)) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize(elem) for elem in obj]
            return obj
        print(f"Settings (relevant sections):")
        remote_access = settings.get("remote_access", {})
        print(f"remote_access: {json.dumps(sanitize(remote_access), indent=2)}")

if __name__ == "__main__":
    run_deep_survey()
