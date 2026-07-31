"""分析每个资源需要生成的图片数量（最多5张/资源）"""
import json, os, re, hashlib

RESOURCES = json.load(open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "resources.json"),
    encoding='utf-8'))

INDEX = json.load(open(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "learning_materials", "index.json"), encoding='utf-8'))

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning_materials")

# Build flat index: tag -> file path
flat = {}
for mod, items in INDEX.get("modules", {}).items():
    for tag, rel_path in items.items():
        flat[tag] = rel_path

def extract_prompts_from_file(rel_path):
    """Extract all Image-Prompt bodies from a markdown file"""
    full = os.path.join(BASE, rel_path)
    if not os.path.exists(full):
        return []
    with open(full, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = (r'(?:\*\*)?Image-Prompt\([^)]+\):(?:\*\*)?\s*'
               r'(.+?)(?=\n\n(?:#|\*\*Image-Prompt|Image-Prompt)'
               r'|\n(?:#|\*\*Image-Prompt|Image-Prompt)|$)')
    results = []
    for m in re.finditer(pattern, content, re.DOTALL):
        body = m.group(1).strip()
        if body.startswith('```'): body = body[3:]
        if body.endswith('```'): body = body[:-3]
        body = body.strip()
        if len(body) >= 10:
            h = hashlib.sha256(body.encode()).hexdigest()
            results.append({'hash': h, 'body': body})
    return results

for res in RESOURCES:
    rid = res['id']
    title = res['title']
    tags = res.get('tags', [])

    # Find markdown files for this resource
    seen_files = set()
    all_prompts = []
    for tag in tags:
        rel = flat.get(tag)
        if rel and rel not in seen_files:
            seen_files.add(rel)
            prompts = extract_prompts_from_file(rel)
            all_prompts.extend(prompts)

    # Deduplicate by hash
    seen_hashes = set()
    unique_prompts = []
    for p in all_prompts:
        if p['hash'] not in seen_hashes:
            seen_hashes.add(p['hash'])
            unique_prompts.append(p)

    first5 = unique_prompts[:5]
    extra = unique_prompts[5:] if len(unique_prompts) > 5 else []

    print(f"[{rid}] {title}")
    print(f"    Tags: {len(tags)}, Files: {len(seen_files)}, Total prompts: {len(unique_prompts)}")
    print(f"    First 5 to generate: {len(first5)}, Extra (to hide): {len(extra)}")
