import urllib.request
import urllib.error
import json

req = urllib.request.Request(
    'https://api.firecrawl.dev/v2/search/developer',
    data=json.dumps({'query': 'OpenAI Videos API'}).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'User-Agent': 'curl/7.68.0'}
)
try:
    with urllib.request.urlopen(req) as resp:
        print('Status:', resp.status)
        print('Resp:', resp.read().decode('utf-8')[:500])
except urllib.error.HTTPError as e:
    print('HTTP Code:', e.code)
    print('Error Body:', e.read().decode('utf-8'))
except Exception as e:
    print('Other error:', e)
