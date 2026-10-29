exe_path = r"C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe"
content = open(exe_path, "rb").read().decode("latin1")

# Find serveCreate and MEDIA_DIALECTS
idx = content.find("serveCreate")
print(f"serveCreate found at {idx}")
if idx != -1:
    print("----- CODE AROUND serveCreate -----")
    print(content[max(0, idx - 4000):min(len(content), idx + 4000)])

idx2 = content.find("MEDIA_DIALECTS")
print(f"MEDIA_DIALECTS found at {idx2}")
if idx2 != -1:
    print("----- CODE AROUND MEDIA_DIALECTS -----")
    print(content[max(0, idx2 - 500):min(len(content), idx2 + 1000)])
