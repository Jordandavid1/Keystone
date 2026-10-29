import urllib.request
import urllib.error

for path in ['/', '/docs', '/openapi.json', '/v1/models', '/v1/videos', '/v1/videos/models']:
    url = f'http://127.0.0.1:1337{path}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.68.0'})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type")
            print(f"{path} -> {resp.status} ({ct}) bytes={len(data)}")
            if "json" in str(ct).lower() and len(data) < 2000:
                print("   ", data.decode('utf-8', errors='ignore'))
    except urllib.error.HTTPError as e:
        print(f"{path} -> HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}")
    except Exception as e:
        print(f"{path} -> Error: {e}")
