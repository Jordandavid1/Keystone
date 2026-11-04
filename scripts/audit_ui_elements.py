import re
from pathlib import Path

html_text = Path("apps/web/index.html").read_text(encoding="utf-8")
js_text = Path("apps/web/app.js").read_text(encoding="utf-8")

# Find all buttons and links with ids or data attributes
button_tags = re.findall(r'<button[^>]*>', html_text)
a_tags = re.findall(r'<a[^>]*>', html_text)

print(f"Total buttons found: {len(button_tags)}")
print(f"Total <a> tags found: {len(a_tags)}")

ids_in_html = set(re.findall(r'id=["\']([^"\']+)["\']', html_text))
classes_in_html = set(re.findall(r'class=["\']([^"\']+)["\']', html_text))
data_attrs = set(re.findall(r'data-([a-zA-Z0-9_\-]+)=["\']([^"\']+)["\']', html_text))

print(f"Total IDs in HTML: {len(ids_in_html)}")

# Check for each ID on buttons/links whether it appears in JS
unhandled_elements = []
for tag in button_tags + a_tags:
    m_id = re.search(r'id=["\']([^"\']+)["\']', tag)
    m_act = re.search(r'data-activity=["\']([^"\']+)["\']', tag)
    m_nav = re.search(r'data-nav=["\']([^"\']+)["\']', tag)
    m_mode = re.search(r'data-mode=["\']([^"\']+)["\']', tag)
    m_cmd = re.search(r'data-cmd=["\']([^"\']+)["\']', tag)
    m_href = re.search(r'href=["\']([^"\']+)["\']', tag)

    tag_id = m_id.group(1) if m_id else None
    act = m_act.group(1) if m_act else None
    nav = m_nav.group(1) if m_nav else None
    mode = m_mode.group(1) if m_mode else None
    cmd = m_cmd.group(1) if m_cmd else None
    href = m_href.group(1) if m_href else None

    # Check if wired in JS
    wired = False
    if tag_id and (f"'{tag_id}'" in js_text or f'"{tag_id}"' in js_text or f"`{tag_id}`" in js_text):
        wired = True
    if act and (f"'{act}'" in js_text or f'"{act}' in js_text):
        wired = True
    if nav and (f"'{nav}'" in js_text or f'"{nav}' in js_text):
        wired = True
    if mode and (f"'{mode}'" in js_text or f'"{mode}' in js_text):
        wired = True
    if cmd and (f"'{cmd}'" in js_text or f'"{cmd}' in js_text):
        wired = True
    if href and href != "#":
        wired = True

    # Also check generic class listeners:
    class_match = re.search(r'class=["\']([^"\']+)["\']', tag)
    if class_match:
        classes = class_match.group(1).split()
        for c in classes:
            if f".{c}" in js_text:
                wired = True

    if not wired:
        unhandled_elements.append(tag)

print(f"\nPotential unhandled button/link tags ({len(unhandled_elements)}):")
for u in unhandled_elements:
    print(" -", u)
