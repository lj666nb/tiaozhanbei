"""将现有的 generated_images/*.svg 文件导入 SQLite DB"""
import os, sqlite3

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "generated_images")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "learning_platform.db")

conn = sqlite3.connect(DB)
conn.execute(
    "CREATE TABLE IF NOT EXISTS generated_images ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
    "prompt_hash TEXT NOT NULL, prompt_text TEXT NOT NULL, "
    "svg_content TEXT, file_path TEXT, provider TEXT DEFAULT 'llm-svg', "
    "created_at TEXT)"
)
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_img_h ON generated_images(prompt_hash)"
)

# Get existing DB hashes
existing_db = set(r[0] for r in conn.execute(
    "SELECT prompt_hash FROM generated_images WHERE svg_content IS NOT NULL").fetchall())

imported = 0
for fn in sorted(os.listdir(IMG_DIR)):
    if not fn.endswith('.svg'):
        continue
    h = fn.replace('.svg', '')
    if h in existing_db:
        continue
    fpath = os.path.join(IMG_DIR, fn)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            svg = f.read()
        conn.execute(
            "INSERT OR REPLACE INTO generated_images "
            "(user_id, prompt_hash, prompt_text, svg_content, file_path, provider, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pre-generated', datetime('now'))",
            (1, h, f"pre-generated {h[:16]}", svg, fpath)
        )
        imported += 1
    except Exception as e:
        print(f"FAIL: {fn}: {e}")

conn.commit()
conn.close()

print(f"Imported {imported} new SVG files into DB")
total = len(existing_db) + imported
print(f"Total cached in DB: {total}")
