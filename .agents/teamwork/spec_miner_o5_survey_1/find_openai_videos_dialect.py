exe_path = r"C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe"
content = open(exe_path, "rb").read().decode("latin1")

idx = 0
while True:
    idx = content.find("openai-videos", idx)
    if idx == -1:
        break
    print(f"Match at {idx}:")
    print(content[max(0, idx - 200):min(len(content), idx + 800)])
    print("-" * 50)
    idx += len("openai-videos")
