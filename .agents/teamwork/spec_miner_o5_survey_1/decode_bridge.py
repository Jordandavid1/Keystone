import base64
import re

output_path = r"C:\Users\Lesia Eden\.gemini\antigravity\brain\f317caa6-a195-4fed-821e-2128aa1dc4c7\.system_generated\steps\234\output.txt"
content = open(output_path, "r", encoding="utf-8").read()

# Find base64.b64decode('...')
match = re.search(r"base64\.b64decode\('([^']+)'\)", content)
if match:
    b64_str = match.group(1)
    print(f"Found base64 string with length: {len(b64_str)}")
    decoded = base64.b64decode(b64_str).decode('utf-8', errors='ignore')
    print("Decoded length:", len(decoded))
    with open(r"c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_o5_survey_1\extracted_comfy_bridge.py", "w", encoding="utf-8") as f:
        f.write(decoded)
    print("Saved to extracted_comfy_bridge.py")
else:
    print("Pattern not matched directly, searching for b64 parts...")
    # let's look for write_bytes(base64.b64decode
    idx = content.find("write_bytes(base64.b64decode")
    print(content[idx:idx+500])
