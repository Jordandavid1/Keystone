import base64

lines = open(r'C:\Users\Lesia Eden\.gemini\antigravity\brain\f317caa6-a195-4fed-821e-2128aa1dc4c7\.system_generated\steps\234\output.txt', encoding='utf-8').readlines()
for l in lines:
    if 'f1e327' in l:
        print('Found line with len:', len(l))
        s_marker = "base64.b64decode('"
        start = l.find(s_marker) + len(s_marker)
        end = l.rfind("')")
        b64_content = l[start:end]
        print('b64 length:', len(b64_content))
        decoded = base64.b64decode(b64_content).decode('utf-8', errors='ignore')
        print(f'Decoded {len(decoded.splitlines())} lines')
        with open(r'c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_o5_survey_1\comfy_openai_bridge.py', 'w', encoding='utf-8') as f:
            f.write(decoded)
        print('Wrote comfy_openai_bridge.py successfully!')
