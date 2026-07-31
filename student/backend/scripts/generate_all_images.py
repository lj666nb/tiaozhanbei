"""批量预生成 + 质量验证"""
import os, re, hashlib, asyncio, sys, time
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Fix Windows console encoding
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
from services.image_service import _init_image_table
from services.ai_service import call_llm
from database import get_db

_init_image_table()
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning_materials")
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "generated_images")
os.makedirs(IMAGES_DIR, exist_ok=True)
USER_ID = 1

def validate_svg(svg_text):
    issues = []
    if not svg_text or len(svg_text) < 200:
        return False, ["SVG too short"]
    if "</svg>" not in svg_text[-50:]:
        return False, ["SVG not closed"]
    try:
        from xml.etree import ElementTree as ET2
        ET2.fromstring(svg_text)
    except Exception as e:
        return False, [f"XML parse error: {e}"]
    return True, []

async def generate_single(prompt, max_retries=2):
    """生成并验证一张配图，失败则重试"""
    svg_prompt = f"""你是一位教育插画师。创建一张中文教育配图。

主题："{prompt}"

必须遵守：
- viewBox="0 0 800 500"
- 扁平化 2D，主色 #409EFF，白底，深蓝 #1a1a2e 文字
- 浅蓝渐变背景
- 所有文字 14px 以上
- 元素间距 ≥40px 垂直、≥30px 水平
- 最多 6 个标注，每个 3-6 个字
- 充分留白，禁止重叠
- 只输出 ```svg ... ``` 包裹的代码"""

    for attempt in range(max_retries + 1):
        try:
            resp = await call_llm(user_id=USER_ID, messages=[{"role": "user", "content": svg_prompt}], temperature=0.5, max_tokens=4096)
            if not resp or resp.startswith("LLM调用异常"):
                if attempt < max_retries:
                    await asyncio.sleep(3)
                    continue
                return None

            m = re.search(r'```svg\s*(.*?)\s*```', resp, re.DOTALL)
            if not m:
                m = re.search(r'<svg[\s\S]*?</svg>', resp)
            svg = (m.group(1) if '```' in resp else m.group(0)) if m else None
            if not svg:
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return None

            svg = svg.strip()
            if 'viewBox=' not in svg[:200]:
                svg = svg.replace('<svg', '<svg viewBox="0 0 800 500"')

            valid, issues = validate_svg(svg)
            if valid:
                return svg
            # 失败则用更详细的提示重试
            if attempt < max_retries:
                issue_str = "; ".join(issues[:3])
                svg_prompt = f"""你是一位教育插画师。之前的 SVG 有问题：{issue_str}。请修正后重新生成。

主题："{prompt}"

必须遵守：viewBox="0 0 800 500"，所有文字 ≥14px，间距 ≥40px，最多 6 个标注，中文，不重叠，充分留白。
只输出 ```svg ... ``` 包裹的代码。"""
                await asyncio.sleep(3)
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(3)
            else:
                return None
    return None


def extract_prompts(content, max_per_file=2):
    """提取每文件最多 max_per_file 个代表性提示词（跳过已生成的）"""
    all_prompts = []
    pattern = r'(?:\*\*)?Image-Prompt\(([^)]+)\):(?:\*\*)?\s*(.+?)(?=\n\n(?:#|\*\*Image-Prompt|Image-Prompt)|\n(?:#|\*\*Image-Prompt|Image-Prompt)|$)'
    for m in re.finditer(pattern, content, re.DOTALL):
        body = m.group(2).strip()
        if body and len(body) > 10:
            h = hashlib.md5(body.encode()).hexdigest()
            conn = get_db()
            exists = conn.execute("SELECT id FROM generated_images WHERE prompt_hash=?", (h,)).fetchone()
            conn.close()
            if not exists:
                all_prompts.append((h, body))
    # 选取代表：首尾各1个 + 中间均匀取
    n = len(all_prompts)
    if n <= max_per_file:
        return all_prompts
    selected = [all_prompts[0]]
    if max_per_file >= 2:
        selected.append(all_prompts[-1])
    if max_per_file >= 3:
        step = max(1, (n - 2) // (max_per_file - 2))
        for i in range(1, n - 1, step):
            if len(selected) >= max_per_file:
                break
            selected.append(all_prompts[i])
    return selected[:max_per_file]


async def main():
    all_files = []
    for root, dirs, files in os.walk(BASE):
        for f in sorted(files):
            if f.endswith('.md'):
                all_files.append(os.path.join(root, f))

    total = 0
    for fp in all_files:
        with open(fp, 'r', encoding='utf-8') as fh:
            total += len(extract_prompts(fh.read()))

    print(f"Need to generate: {total} images in {len(all_files)} files")
    if total == 0:
        print("All done!")
        return

    ok, fail, skip = 0, 0, 0
    for fp in all_files:
        fname = os.path.relpath(fp, BASE)
        with open(fp, 'r', encoding='utf-8') as fh:
            prompts = extract_prompts(fh.read())
        for h, body in prompts:
            print(f"[{ok+1}/{total}] {fname}: {body[:60]}...", end=" ", flush=True)
            svg = await generate_single(body)
            if svg:
                file_path = os.path.join(IMAGES_DIR, f"{h}.svg")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(svg)
                conn = get_db()
                conn.execute(
                    "INSERT INTO generated_images (user_id, prompt_hash, prompt_text, svg_content, file_path, provider) VALUES (?,?,?,?,?,'llm-svg')",
                    (USER_ID, h, body, svg, file_path)
                )
                conn.commit()
                conn.close()
                ok += 1
                print("OK [OK]")
            else:
                fail += 1
                print("FAIL [FAIL]")
            await asyncio.sleep(1.5)

    print(f"\nDone! OK={ok}, Failed={fail}")

if __name__ == "__main__":
    asyncio.run(main())
