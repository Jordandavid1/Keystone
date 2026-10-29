output_path = r"C:\Users\Lesia Eden\.gemini\antigravity\brain\f317caa6-a195-4fed-821e-2128aa1dc4c7\.system_generated\steps\224\output.txt"
lines = open(output_path, "r", encoding="utf-8").readlines()
print(f"Total lines: {len(lines)}")

current_cell = []
in_textbox = False

for i, line in enumerate(lines):
    if "textbox" in line or "generic \"Code Cell" in line or "generic \"Markdown Cell" in line:
        if current_cell:
            print("\n" + "="*40)
            print("".join(current_cell[:20]))
            current_cell = []
    if "generic [ref=" in line and "- generic [ref=" in line:
        text = line.split(":", 1)[-1].strip() if ":" in line else line.strip()
        current_cell.append(text + "\n")

if current_cell:
    print("\n" + "="*40)
    print("".join(current_cell[:20]))
