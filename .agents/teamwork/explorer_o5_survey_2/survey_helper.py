import os
import sys
import json
import re
import urllib.request
import urllib.error

ROAMING_PATH = r"C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat"
LOCAL_PATH = r"C:\Users\Lesia Eden\AppData\Local\Atomic Chat"
CONTROL_TOKEN_FILE = os.path.join(ROAMING_PATH, "data", "atomic-core", "control-token")
PUBLIC_TOKEN = "sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay"

def mask_secret(s):
    if not s or len(s) < 8:
        return "***"
    return f"{s[:6]}...{s[-4:]} (length {len(s)})"

def inspect_files():
    print("=== FILESYSTEM INSPECTION ===")
    print(f"Control token file exists: {os.path.exists(CONTROL_TOKEN_FILE)}")
    control_token = ""
    if os.path.exists(CONTROL_TOKEN_FILE):
        with open(CONTROL_TOKEN_FILE, "r", encoding="utf-8") as f:
            control_token = f.read().strip()
        print(f"Control token loaded: {mask_secret(control_token)}")

    # Check local-api-server.json
    local_api_files = [
        os.path.join(ROAMING_PATH, "data", "local-api-server.json"),
        os.path.join(ROAMING_PATH, "data", "atomic-core", "local-api-server.json")
    ]
    for lap in local_api_files:
        print(f"Checking {lap} (exists: {os.path.exists(lap)})")
        if os.path.exists(lap):
            try:
                with open(lap, "r", encoding="utf-8") as f:
                    data = json.load(f)
                safe_data = {}
                for k, v in data.items():
                    if any(x in k.lower() for x in ["key", "token", "secret"]):
                        safe_data[k] = mask_secret(str(v))
                    else:
                        safe_data[k] = v
                print(f"Content: {json.dumps(safe_data, indent=2)}")
            except Exception as e:
                print(f"Error reading {lap}: {e}")

    # Check videos folder
    videos_dir = os.path.join(ROAMING_PATH, "data", "videos")
    print(f"\nVideos directory: {videos_dir} (exists: {os.path.exists(videos_dir)})")
    if os.path.exists(videos_dir):
        files = os.listdir(videos_dir)
        print(f"Videos count: {len(files)}")
        for f in files[:20]:
            fp = os.path.join(videos_dir, f)
            sz = os.path.getsize(fp) if os.path.isfile(fp) else "<dir>"
            print(f"  {f} ({sz} bytes)")
    
    # Check diffusion gallery or other folders
    diffusion_dir = os.path.join(ROAMING_PATH, "data", "diffusion")
    print(f"\nDiffusion directory exists: {os.path.exists(diffusion_dir)}")

    return control_token

def search_cloudflare_url():
    print("\n=== SEARCHING CLOUDFLARE TUNNEL URL ===")
    found_urls = set()
    log_dirs = [
        os.path.join(ROAMING_PATH, "data", "logs"),
        os.path.join(ROAMING_PATH, "data", "atomic-core", "logs"),
        os.path.join(ROAMING_PATH, "data", "atomic-core"),
        LOCAL_PATH
    ]
    cf_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", re.IGNORECASE)

    for ld in log_dirs:
        if not os.path.exists(ld):
            continue
        for root, _, files in os.walk(ld):
            for fname in files:
                if fname.endswith((".log", ".txt", ".json")):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                            matches = cf_pattern.findall(text)
                            for m in matches:
                                found_urls.add((m, fpath))
                    except Exception as e:
                        pass
    if found_urls:
        for u, src in found_urls:
            print(f"Found Cloudflare URL: {u} (in {src})")
    else:
        print("No trycloudflare.com URL found in standard log files.")
    return [u for u, _ in found_urls]

def test_http_endpoint(url, headers=None, method="GET", body=None):
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
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            try:
                decoded = raw.decode("utf-8")
                try:
                    js = json.loads(decoded)
                    return status, js
                except:
                    return status, decoded[:500]
            except:
                return status, f"<binary: {len(raw)} bytes>"
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="ignore")[:500]
        except:
            pass
        return e.code, err_body
    except Exception as e:
        return None, str(e)

def test_control_api(control_token):
    print("\n=== TESTING ATOMIC CHAT CONTROL API (127.0.0.1:56603) ===")
    base_url = "http://127.0.0.1:56603/atomic/v1"
    endpoints = [
        "/cloud/providers",
        "/server/selection",
        "/diffusion/video/gallery"
    ]

    header_variants = [
        {"Authorization": f"Bearer {control_token}"},
        {"X-Atomic-Control-Token": control_token},
        {"X-Control-Token": control_token},
        {"Authorization": control_token},
        {}
    ]

    for ep in endpoints:
        full_url = f"{base_url}{ep}"
        print(f"\n--- Testing Endpoint: {full_url} ---")
        success = False
        for i, hdrs in enumerate(header_variants):
            h_desc = list(hdrs.keys())[0] if hdrs else "No auth header"
            status, res = test_http_endpoint(full_url, headers=hdrs)
            print(f"Header: {h_desc} -> Status: {status}")
            if status == 200:
                print(f"Response (summary): {json.dumps(res, indent=2)[:400] if isinstance(res, (dict, list)) else str(res)[:400]}")
                success = True
                break
            else:
                print(f"Response: {res}")
        if not success:
            print(f"Failed to authenticate or fetch {ep}")

def test_public_api():
    print("\n=== TESTING ATOMIC CHAT PUBLIC API (127.0.0.1:1337/v1) ===")
    base_url = "http://127.0.0.1:1337/v1"
    endpoints = [
        "/models",
        "/videos"
    ]
    headers = {
        "Authorization": f"Bearer {PUBLIC_TOKEN}"
    }
    for ep in endpoints:
        full_url = f"{base_url}{ep}"
        print(f"\n--- Testing Endpoint: {full_url} ---")
        status, res = test_http_endpoint(full_url, headers=headers)
        print(f"Status: {status}")
        if status == 200:
            print(f"Response (summary): {json.dumps(res, indent=2)[:500] if isinstance(res, (dict, list)) else str(res)[:500]}")
        else:
            print(f"Response: {res}")

if __name__ == "__main__":
    token = inspect_files()
    search_cloudflare_url()
    test_control_api(token)
    test_public_api()
