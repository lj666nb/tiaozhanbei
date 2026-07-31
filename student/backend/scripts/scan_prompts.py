"""扫描所有学习材料中的 Image-Prompt 块，统计缓存状态"""
import os, re, hashlib, sqlite3, sys

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning_materials")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "learning_platform.db")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "generated_images")

all_prompts = []
for root, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith('.md'):
            continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8') as fp:
            content = fp.read()

        # Match Image-Prompt(name):
        pattern = (r'(?:\*\*)?Image-Prompt\([^)]+\):(?:\*\*)?\s*'
                   r'(.+?)(?=\n\n(?:#|\*\*Image-Prompt|Image-Prompt)'
                   r'|\n(?:#|\*\*Image-Prompt|Image-Prompt)|$)')
        for match in re.finditer(pattern, content, re.DOTALL):
            body = match.group(1).strip()
            # Strip optional ``` markers
            if body.startswith('```'):
                body = body[3:]
            if body.endswith('```'):
                body = body[:-3]
            body = body.strip()
            if len(body) < 10:
                continue
            h = hashlib.sha256(body.encode()).hexdigest()
            m0 = match.group(0)[:100]
            name = m0.split(')')[0].split('(')[-1] if '(' in m0 else '?'
            all_prompts.append({
                'file': os.path.relpath(path, BASE),
                'name': name,
                'hash': h,
                'body_len': len(body),
                'body': body
            })

print(f"Total Image-Prompt blocks: {len(all_prompts)}")
unique = {p['hash']: p for p in all_prompts}
print(f"Unique prompts (by hash): {len(unique)}")

# Check cache
cached = set()
if os.path.exists(DB):
    conn = sqlite3.connect(DB)
    try:
        rows = conn.execute(
            "SELECT prompt_hash FROM generated_images WHERE svg_content IS NOT NULL"
        ).fetchall()
        cached = set(r[0] for r in rows)
    except Exception as e:
        print(f"DB error: {e}")
    conn.close()

cached_files = set()
if os.path.exists(IMG_DIR):
    for fn in os.listdir(IMG_DIR):
        if fn.endswith('.svg'):
            cached_files.add(fn.replace('.svg', ''))

all_cached = cached | cached_files
uncached = {h: p for h, p in unique.items() if h not in all_cached}
cached_count = len(unique) - len(uncached)

print(f"Cached (DB): {len(cached)}, (files): {len(cached_files)}, combined: {len(all_cached)}")
print(f"Already cached: {cached_count}")
print(f"Need to generate: {len(uncached)}")

# Print the list
print("\n--- Prompts needing generation ---")
for h, p in sorted(uncached.items(), key=lambda x: x[1]['file']):
    print(f"  [{p['name']}] {p['file']} (len={p['body_len']})")

# Export for runner script
export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uncached_prompts.txt")
with open(export_path, 'w', encoding='utf-8') as f:
    for h, p in uncached.items():
        f.write(f"{h}\t{p['name']}\t{p['file']}\t{p['body_len']}\n")
print(f"\nExported uncached list to: {export_path}")
print(f"Total to generate: {len(uncached)}")
