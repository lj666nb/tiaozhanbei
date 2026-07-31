"""Rebuild tutorial_seed.json from learning_materials/ directory."""
import json, os, re, hashlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATERIALS_DIR = os.path.join(PROJECT_ROOT, 'learning_materials')

documents = []
for root, dirs, files in os.walk(MATERIALS_DIR):
    for fname in files:
        if fname.endswith('.md'):
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, MATERIALS_DIR)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            title = fname.replace('.md', '')
            category = rel.replace('\\', '/').split('/')[0] if '/' in rel.replace('\\', '/') else ''
            doc_id = hashlib.md5(rel.encode()).hexdigest()[:12]
            documents.append({
                'id': doc_id,
                'title': title,
                'category': category,
                'path': rel,
                'content': content,
                'content_length': len(content),
            })

output_path = os.path.join(PROJECT_ROOT, 'backend', 'data', 'tutorial_seed.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(documents, f, ensure_ascii=False)

print(f'Generated {len(documents)} documents to {output_path}')
for d in documents:
    if d['category'] == 'Agent工程实战':
        print(f'  [{d["title"]}] {d["content_length"]} chars')
