import re

exe_path = r"C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe"
content = open(exe_path, "rb").read().decode("latin1")

# Find occurrences of router.get, router.put, router.post, router.delete
pattern = re.compile(r'router\.(get|put|post|delete)\(p2\("([^"]+)"\)', re.IGNORECASE)
matches = pattern.findall(content)
print(f"Total control routes registered with p2: {len(matches)}")
routes_found = set()
for method, route in matches:
    routes_found.add((method.upper(), route))

for method, route in sorted(routes_found):
    print(f"{method:6} /atomic/v1{route}")

# Let's inspect the exact code for server/selection and cloud/providers and diffusion/video
for target in ["server/selection", "cloud/providers", "diffusion/video/"]:
    idx = content.find(target)
    if idx != -1:
        start = max(0, idx - 300)
        end = min(len(content), idx + 1000)
        print(f"\n=================== CONTEXT FOR {target} ===================")
        print(content[start:end])
