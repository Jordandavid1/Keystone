import re
import os

exe_path = r"C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe"
print(f"Scanning {exe_path} ({os.path.getsize(exe_path)} bytes)...")

with open(exe_path, "rb") as f:
    content = f.read()

# Look for routes like /atomic/v1/...
routes = set(re.findall(rb'/atomic/v1/[a-zA-Z0-9_\-/]+', content))
print(f"Found {len(routes)} control routes:")
for r in sorted(routes):
    print(" ", r.decode('latin1'))

# Look for /v1/ routes
v1_routes = set(re.findall(rb'/v1/[a-zA-Z0-9_\-/]+', content))
print(f"\nFound {len(v1_routes)} v1 routes:")
for r in sorted(v1_routes):
    if b'videos' in r or b'models' in r or b'chat' in r:
        print(" ", r.decode('latin1'))
