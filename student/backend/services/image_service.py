"""AI 配图生成服务"""
import os, re, hashlib
from database import get_db
from datetime import datetime
from services.ai_service import call_llm

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "generated_images")
os.makedirs(IMAGES_DIR, exist_ok=True)

def _init_table():
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS generated_images (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, prompt_hash TEXT NOT NULL, prompt_text TEXT NOT NULL, svg_content TEXT, file_path TEXT, provider TEXT DEFAULT 'llm-svg', created_at TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_img_h ON generated_images(prompt_hash)")
    conn.commit()
    conn.close()
_init_table()

async def generate_image(user_id, prompt, style="educational"):
    h = hashlib.sha256(prompt.encode()).hexdigest()
    conn = get_db()
    row = conn.execute("SELECT svg_content FROM generated_images WHERE prompt_hash=? AND svg_content IS NOT NULL LIMIT 1", (h,)).fetchone()
    conn.close()
    if row and row["svg_content"]:
        return {"success": True, "svg": row["svg_content"], "cached": True}

    svg_prompt = f"""你是一位教育插画师。请为教科书创建一张清晰的中文 SVG 插图。

知识点：\"{prompt}\"

关键规则：
- ViewBox 0 0 800 500
- 扁平化 2D 矢量图，科技蓝 #409EFF + 白色 + 深蓝 #1a1a2e
- 浅蓝渐变背景
- 所有文字标签必须使用中文，字号 14px 以上
- 元素间距 >=40px 垂直、>=30px 水平
- 最多 6-8 个标注，每个 3-6 个字
- 充分留白，禁止重叠
- 只输出 ```svg ... ``` 包裹的代码"""

    try:
        resp = await call_llm(user_id=user_id, messages=[{"role":"user","content":svg_prompt}], temperature=0.5, max_tokens=4096)
        if not resp or resp.startswith("LLM"):
            return {"success": False, "error": str(resp)}
        m = re.search(r'```svg\s*(.*?)\s*```', resp, re.DOTALL)
        if not m: m = re.search(r'<svg[\s\S]*?</svg>', resp)
        svg = (m.group(1) if m and '```' in resp else m.group(0)) if m else None
        if not svg: return {"success": False, "error": "No SVG found"}
        svg = svg.strip()
        if 'viewBox=' not in svg[:200]: svg = svg.replace('<svg', '<svg viewBox="0 0 800 500"')
        if not svg.endswith('</svg>'): return {"success": False, "error": "SVG incomplete"}

        fp = os.path.join(IMAGES_DIR, f"{h}.svg")
        with open(fp, 'w', encoding='utf-8') as f: f.write(svg)
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO generated_images (user_id, prompt_hash, prompt_text, svg_content, file_path, provider, created_at) VALUES (?,?,?,?,?,'llm-svg',?)", (user_id, h, prompt, svg, fp, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return {"success": True, "svg": svg, "cached": False}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_cached_images(user_id):
    conn = get_db()
    rows = conn.execute("SELECT prompt_hash, file_path FROM generated_images WHERE user_id=? AND file_path IS NOT NULL ORDER BY created_at DESC LIMIT 500", (user_id,)).fetchall()
    conn.close()
    return [{"prompt_hash": r["prompt_hash"], "url": "/api/images/"+os.path.basename(r["file_path"])} for r in rows if os.path.exists(r["file_path"])]
