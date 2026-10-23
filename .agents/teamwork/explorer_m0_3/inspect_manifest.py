import json

with open('.agents/teamwork/explorer_m0_3/prebuilt_manifest.json') as f:
    m = json.load(f)

prebuilt = {k: v for k, v in m.items() if not k.startswith('tests/e2e_v2') and k != 'KEYSTONE_BIBLE.md'}
print(f"Total files: {len(prebuilt)}")
for idx, k in enumerate(sorted(prebuilt.keys()), 1):
    print(f"{idx:2d}. {k:58s} | {prebuilt[k]['size']:6d} B | {prebuilt[k]['sha256']}")
