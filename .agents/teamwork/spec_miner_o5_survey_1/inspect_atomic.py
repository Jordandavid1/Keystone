import os
import json
import glob

data_dir = r"C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data"
print("Scanning:", data_dir)
for f in os.listdir(data_dir):
    full_path = os.path.join(data_dir, f)
    if os.path.isfile(full_path):
        print(f"File: {f} ({os.path.getsize(full_path)} bytes)")
    elif os.path.isdir(full_path):
        print(f"Dir: {f}/")

# Check local-api-server.json, store.json, etc.
for conf_file in ["local-api-server.json", "store.json"]:
    p = os.path.join(data_dir, conf_file)
    if os.path.exists(p):
        print(f"\n--- {conf_file} ---")
        try:
            with open(p, 'r', encoding='utf-8') as fh:
                d = json.load(fh)
                # Print keys or summary, don't leak secrets
                if isinstance(d, dict):
                    print("Keys:", list(d.keys()))
                    for k in d:
                        val = d[k]
                        if "token" in k.lower() or "key" in k.lower() or "secret" in k.lower():
                            print(f"  {k}: [REDACTED_SECRET len={len(str(val))}]")
                        elif isinstance(val, (dict, list)):
                            print(f"  {k}: {type(val)} len={len(val)}")
                        else:
                            print(f"  {k}: {val}")
        except Exception as e:
            print("Error reading:", e)

# Check atomic-core
core_dir = os.path.join(data_dir, "atomic-core")
if os.path.exists(core_dir):
    print("\n--- atomic-core dir ---")
    for f in os.listdir(core_dir):
        print("  ", f)

