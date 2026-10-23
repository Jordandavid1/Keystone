import os
import re

PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|password|bearer|private[_-]?key)\s*[:=]\s*[\'\"][a-zA-Z0-9_\-\.]{16,}[\'\"]'),
    re.compile(r'sk_live_[a-zA-Z0-9]{20,}'),
    re.compile(r'ghp_[a-zA-Z0-9]{20,}'),
    re.compile(r'xox[baprs]-[a-zA-Z0-9]{10,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
]

findings = []
for root, dirs, files in os.walk('.'):
    if any(p in root for p in ['.git', '.gemini', 'node_modules', '.venv', '.agents']):
        continue
    for f in files:
        if f.endswith(('.py', '.js', '.ts', '.json', '.sh', '.md', '.sql', '.ipynb')):
            p = os.path.join(root, f)
            try:
                content = open(p, 'r', encoding='utf-8', errors='ignore').read()
                for i, line in enumerate(content.splitlines()):
                    for pat in PATTERNS:
                        if pat.search(line):
                            line_lower = line.lower()
                            if 'placeholder' in line_lower or 'example' in line_lower or 'redacted' in line_lower:
                                continue
                            findings.append((p, i + 1, line.strip()))
            except Exception:
                pass

print(f"Total secret scan findings: {len(findings)}")
for f, l, s in findings[:20]:
    print(f"{f}:{l} -> {s[:100]}")
