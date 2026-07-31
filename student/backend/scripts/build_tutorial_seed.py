"""扫描 learning_materials/ 目录，生成 tutorial_seed.json 种子数据文件。

用法：
    python backend/build_tutorial_seed.py

输出：
    backend/data/tutorial_seed.json
"""
import json
import os
import sys

# 项目根目录（backend/ 的上一级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATERIALS_DIR = os.path.join(PROJECT_ROOT, "learning_materials")
INDEX_PATH = os.path.join(MATERIALS_DIR, "index.json")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tutorial_seed.json")


def extract_title_from_md(content: str, fallback: str) -> str:
    """从 Markdown 内容第一行提取标题（# 开头），否则用 fallback"""
    first_line = content.strip().split("\n")[0].strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return fallback


def build_seed() -> list[dict]:
    """扫描 index.json 和 .md 文件，生成种子数据列表"""
    if not os.path.exists(INDEX_PATH):
        print(f"[WARN] learning_materials/index.json not found at {INDEX_PATH}")
        return []

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    modules = index_data.get("modules", {})
    seed_docs = []
    seen_tags = set()

    for module_name, items in modules.items():
        if not isinstance(items, dict):
            continue
        for knowledge_tag, rel_path in items.items():
            if knowledge_tag in seen_tags:
                continue
            seen_tags.add(knowledge_tag)

            full_path = os.path.join(MATERIALS_DIR, rel_path)
            if not os.path.exists(full_path):
                print(f"  [SKIP] File not found: {rel_path}")
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"  [SKIP] Read error {rel_path}: {e}")
                continue

            title = extract_title_from_md(content, knowledge_tag)
            seed_docs.append({
                "knowledge_tag": knowledge_tag,
                "title": title,
                "content": content,
                "module": module_name,
                "source_type": "seed",
                "curriculum_version": "agent-project-path-v1",
            })

    return seed_docs


def main():
    print(f"Scanning: {MATERIALS_DIR}")
    docs = build_seed()
    if not docs:
        print("[WARN] No seed documents found. Check learning_materials/ and index.json.")
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    total_chars = sum(len(d["content"]) for d in docs)
    print(f"[OK] Generated {OUTPUT_PATH}")
    print(f"     {len(docs)} documents, {total_chars:,} chars total")


if __name__ == "__main__":
    main()
