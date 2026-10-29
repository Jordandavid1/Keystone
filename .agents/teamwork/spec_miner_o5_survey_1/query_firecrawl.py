import urllib.request
import urllib.parse
import json
import ssl

def search_firecrawl_developer(query, limit=5, types=None):
    url = "https://api.firecrawl.dev/v2/search/developer"
    payload = {"query": query, "limit": limit}
    if types:
        payload["types"] = types
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Keystone-SpecMiner/1.0"}
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error querying {query}: {e}")
        return None

queries = [
    "OpenAI Videos API POST /v1/videos GET /v1/videos content",
    "OpenAI video generation API /v1/videos status completed queued",
    "ComfyUI API /prompt /history WebSocket client execution",
    "Comfy-Org/MiniMax-H3 PinkCherry ComfyUI workflow"
]

results = {}
for q in queries:
    print(f"Querying: {q}...")
    res = search_firecrawl_developer(q, limit=3)
    results[q] = res
    if res and "data" in res:
        print(f"  Got {len(res['data'])} hits")
        for hit in res['data'][:2]:
            print(f"    - ID: {hit.get('id')}")
            print(f"      URL: {hit.get('url')}")
            passages = hit.get('passages', [])
            if passages:
                print(f"      Passage preview: {passages[0][:150]}...")
    elif res:
        print(f"  Keys returned: {list(res.keys())}")
        print(f"  Raw: {str(res)[:300]}")

with open(r"c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_o5_survey_1\firecrawl_dev_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\nSaved to firecrawl_dev_results.json")
