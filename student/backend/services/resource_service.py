"""资源推荐服务"""
import json
import os
import re as _re_mermaid
from database import get_db
from services.diagnosis_service import get_user_knowledge_profile


# ================================================================
# Mermaid 提取工具 — 将正文与流程图代码分离
# ================================================================

def _wrap_naked_mermaid(content: str) -> str:
    """
    用正则匹配完整的 flowchart/graph 块（单行或多行），包裹为 ```mermaid 围栏。
    关键：只收集真正的 mermaid 续行（节点ID/classDef/style/subgraph/箭头），
    遇到普通正文行立即停止，避免把后续文章内容一起吞进代码块。
    """
    def _is_mermaid_continuation(s):
        """判断一行是否为 mermaid 代码的续行"""
        if not s:
            return True  # 空行可能是块内空行
        if s.startswith('```'):
            return False  # 围栏标记
        # flowchart 续行特征
        if _re_mermaid.match(r'^(classDef|style|subgraph|end\b|direction\b)', s, _re_mermaid.IGNORECASE):
            return True
        if _re_mermaid.match(r'^[a-zA-Z_]\w*\s*[\[(>]', s):  # 节点定义或箭头
            return True
        if _re_mermaid.match(r'^[a-zA-Z_]\w*\s*-->|---|==>', s):  # 箭头语句
            return True
        if _re_mermaid.match(r'^(flowchart|graph)\s+(TD|LR|BT|RL)\b', s, _re_mermaid.IGNORECASE):
            return True
        return False

    def replacer(m):
        block = m.group(0).strip()
        lines = block.split('\n')
        clean = []
        for i, line in enumerate(lines):
            s = line.strip()
            if i == 0:
                clean.append(line)
                continue
            if _is_mermaid_continuation(s):
                clean.append(line)
            else:
                break  # 遇到正文，停止
        code = '\n'.join(clean).strip()
        if len(code) > 50 and ('-->' in code or 'subgraph' in code or 'classDef' in code):
            return '\n\n```mermaid\n' + code + '\n```\n\n'
        return m.group(0)  # 不够特征，原样保留

    # 匹配 flowchart/graph 开头的块（前面是空行或文本开头）
    return _re_mermaid.sub(
        r'(?:^|\n\n)((?:flowchart|graph)\s+(?:TD|LR|BT|RL)\b[\s\S]*?)(?=\n\n[^\n]|\n#{1,4}\s|$)',
        replacer,
        content,
        flags=_re_mermaid.IGNORECASE | _re_mermaid.MULTILINE
    )


def extract_mermaid_blocks(content: str) -> dict:
    """
    从文章内容中提取所有 mermaid 代码块，返回分离后的结构。

    Args:
        content: 包含 ```mermaid ... ``` 代码块的原始文本

    Returns:
        {
            "article_text": str,       # 正文（mermaid 代码块替换为占位标记）
            "mermaid_list": [str, ...] # 提取出的 mermaid 代码（已去除围栏标记）
        }
    占位标记格式: <!--MERMAID_0--> <!--MERMAID_1--> ...
    前端收到后替换为 <div class="mermaid"> 即可渲染。
    """
    mermaid_list = []
    counter = [0]  # 用列表实现闭包引用

    def replacer(m):
        code = m.group(1).strip()
        mermaid_list.append(code)
        placeholder = f'<!--MERMAID_{counter[0]}-->'
        counter[0] += 1
        return placeholder

    # 匹配 ```mermaid ... ``` 代码块
    article_text = _re_mermaid.sub(
        r'```mermaid\s*\n(.*?)```',
        replacer,
        content,
        flags=_re_mermaid.DOTALL
    )

    return {
        "article_text": article_text,
        "mermaid_list": mermaid_list,
    }


def inject_mermaid_placeholders(article_text: str, mermaid_list: list) -> str:
    """
    将 mermaid 代码列表注入回正文中的占位标记位置。
    用于前端渲染前重组内容。
    返回完整的 HTML（占位标记替换为 <div class=\"mermaid\">）。
    """
    result = article_text
    for i, code in enumerate(mermaid_list):
        placeholder = f'<!--MERMAID_{i}-->'
        # 包裹为 mermaid 可渲染的 div
        # 前端 mermaid-js 会自动渲染 .mermaid 类的 div
        result = result.replace(placeholder, f'<div class="mermaid">\n{code}\n</div>')
    return result
from config import RESOURCES_PATH

def load_resources():
    """加载资源库"""
    if not os.path.exists(RESOURCES_PATH):
        return []
    with open(RESOURCES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def recommend_resources(user_id: int, limit: int = 10) -> list:
    """基于学情推荐资源"""
    profile = get_user_knowledge_profile(user_id)
    all_resources = load_resources()
    weak_points = set(profile.get("weak_points", []))

    # 获取用户学习阶段
    conn = get_db()
    user = conn.execute("SELECT learning_stage FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    stage = user["learning_stage"] if user else "入门"

    # 评分推荐
    scored = []
    for res in all_resources:
        score = 0
        # 知识点匹配
        for tag in res.get("tags", []):
            if tag in weak_points:
                score += 30
        # 难度匹配
        if stage == "入门" and res["difficulty"] == "Lv1入门":
            score += 20
        elif stage == "进阶" and res["difficulty"] in ["Lv1入门", "Lv2中等"]:
            score += 20
        elif stage == "高阶":
            score += 10
        # 类别多样性
        score += 5
        scored.append({"resource": res, "score": score, "reason": generate_reason(res, weak_points)})

    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]

def generate_reason(resource: dict, weak_points: set) -> str:
    """生成推荐理由"""
    matched = [t for t in resource.get("tags", []) if t in weak_points]
    if matched:
        return f"针对性加强「{'、'.join(matched)}」"
    if resource["difficulty"] == "Lv1入门":
        return "适合入门打基础"
    if resource["difficulty"] == "Lv2中等":
        return "巩固提升，拓展知识面"
    return "拔高学习，挑战进阶内容"

def get_resources_by_category(category: str = None, difficulty: str = None, page: int = 1, page_size: int = 12) -> dict:
    """按分类获取资源"""
    all_resources = load_resources()
    filtered = all_resources

    if category:
        filtered = [r for r in filtered if r["category"] == category]
    if difficulty:
        filtered = [r for r in filtered if r["difficulty"] == difficulty]

    total = len(filtered)
    offset = (page - 1) * page_size
    items = filtered[offset:offset + page_size]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "categories": list(set(r["category"] for r in all_resources)),
        "difficulties": ["Lv1入门", "Lv2中等", "Lv3高阶"]
    }

def toggle_collect_resource(user_id: int, resource_id: str) -> dict:
    """收藏/取消收藏资源"""
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM user_resources WHERE user_id = ? AND resource_id = ?",
        (user_id, resource_id)
    ).fetchone()

    if existing:
        new_status = 0 if existing["collected"] else 1
        conn.execute(
            "UPDATE user_resources SET collected = ? WHERE user_id = ? AND resource_id = ?",
            (new_status, user_id, resource_id)
        )
    else:
        new_status = 1
        conn.execute(
            "INSERT INTO user_resources (user_id, resource_id, collected) VALUES (?, ?, ?)",
            (user_id, resource_id, 1)
        )

    conn.commit()
    conn.close()

    return {"resource_id": resource_id, "collected": bool(new_status)}

def find_resource_by_knowledge(knowledge: str) -> dict:
    """根据知识点文本匹配最合适的学习资源

    Args:
        knowledge: 知识点文本，如 "AI智能体定义"、"框架基础"、"Transformer架构"

    Returns:
        匹配到的资源字典（含url, title等），或 None
    """
    if not knowledge:
        return None

    all_resources = load_resources()
    if not all_resources:
        return None

    knowledge_lower = knowledge.lower().strip()

    # 提取关键词：去除常见的分隔符和虚词
    import re
    keywords = re.split(r'[，,、\s]+', knowledge)
    # 过滤掉太短的词
    keywords = [k.strip() for k in keywords if len(k.strip()) >= 2]

    best_match = None
    best_score = 0

    for res in all_resources:
        score = 0
        # 1. 标签精确匹配（最高权重）
        for tag in res.get("tags", []):
            tag_lower = tag.lower()
            if tag_lower == knowledge_lower:
                score += 100
            elif tag_lower in knowledge_lower or knowledge_lower in tag_lower:
                score += 50
            # 关键词匹配
            for kw in keywords:
                if len(kw) >= 2 and kw.lower() in tag_lower:
                    score += 20

        # 2. 标题匹配
        title_lower = res.get("title", "").lower()
        for kw in keywords:
            if len(kw) >= 2 and kw.lower() in title_lower:
                score += 15

        # 3. 分类名匹配
        category_lower = res.get("category", "").lower()
        if category_lower in knowledge_lower or knowledge_lower in category_lower:
            score += 10

        # 4. 摘要匹配（低权重）
        summary_lower = res.get("summary", "").lower()
        for kw in keywords:
            if len(kw) >= 2 and kw.lower() in summary_lower:
                score += 5

        if score > best_score:
            best_score = score
            best_match = res

    # 如果没有任何匹配（得分为0），返回该知识分类下的第一个资源作为兜底
    if best_score == 0:
        for res in all_resources:
            for kw in keywords:
                if len(kw) >= 2:
                    # 尝试模糊匹配分类
                    cat = res.get("category", "")
                    if any(c in cat for c in ["智能体", "模型", "提示", "框架", "算法", "应用"]):
                        if any(c in knowledge for c in ["智能体", "模型", "提示", "框架", "算法"]):
                            if cat[0:2] == knowledge[0:2] if len(knowledge) >= 2 else False:
                                best_match = res
                                break
                if best_match:
                    break
            if best_match:
                break

    if best_match and best_score > 0:
        return {
            "url": best_match.get("url", ""),
            "title": best_match.get("title", ""),
            "summary": best_match.get("summary", ""),
            "type": best_match.get("type", ""),
            "duration": best_match.get("duration", ""),
            "match_score": best_score
        }

    return None


# 本地学习资料
import os as _os
# 支持通过环境变量 LEARNING_MATERIALS_DIR 覆盖（Docker 部署时自动挂载到 /learning_materials）
_MATERIALS_ROOT = _os.getenv(
    "LEARNING_MATERIALS_DIR",
    _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "learning_materials")
)
MATERIALS_INDEX_PATH = _os.path.join(_MATERIALS_ROOT, "index.json")
MATERIALS_BASE_DIR = _MATERIALS_ROOT
RESOURCE_IMAGE_CONFIG_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "data", "resource_image_config.json")

def _load_resource_image_config() -> dict:
    """加载资源配置：resource_id -> [allowed_prompt_hashes]"""
    cfg_path = _os.path.normpath(RESOURCE_IMAGE_CONFIG_PATH)
    if not _os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _load_materials_index() -> dict:
    """加载学习资料索引（兼容新旧两种格式）"""
    if not _os.path.exists(MATERIALS_INDEX_PATH):
        return {}
    with open(MATERIALS_INDEX_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 新格式：modules -> {模块名: {知识点: 路径, ...}}
    if "modules" in data:
        flat = {}
        for module_name, module_items in data["modules"].items():
            if isinstance(module_items, dict):
                for knowledge_name, rel_path in module_items.items():
                    flat[knowledge_name] = rel_path
        return flat

    # 旧格式：materials -> {知识点: 路径}
    return data.get("materials", {})


def _get_tutorial_from_db(knowledge: str, user_id: int = None) -> dict | None:
    """从 tutorial_documents 表查询教程内容（用户私有优先，否则种子数据）"""
    conn = None
    try:
        from database import get_db as _get_db
        conn = _get_db()

        # 1. 优先查用户私有版本
        if user_id:
            row = conn.execute(
                "SELECT id, knowledge_tag, title, content, source_type, parent_id "
                "FROM tutorial_documents "
                "WHERE knowledge_tag = ? AND user_id = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (knowledge, user_id)
            ).fetchone()
            if row:
                return {
                    "found": True,
                    "content": row["content"],
                    "file_path": None,
                    "matched_tag": knowledge,
                    "format": "markdown",
                    "source_type": row["source_type"],
                    "tutorial_id": row["id"],
                    "parent_id": row["parent_id"],
                    "from_db": True,
                }

        # 2. 查种子数据
        row = conn.execute(
            "SELECT id, knowledge_tag, title, content, source_type, parent_id "
            "FROM tutorial_documents "
            "WHERE knowledge_tag = ? AND source_type = 'seed' AND user_id IS NULL "
            "LIMIT 1",
            (knowledge,)
        ).fetchone()
        if row:
            return {
                "found": True,
                "content": row["content"],
                "file_path": None,
                "matched_tag": knowledge,
                "format": "markdown",
                "source_type": row["source_type"],
                "tutorial_id": row["id"],
                "parent_id": row["parent_id"],
                "from_db": True,
            }
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
    return None


def get_local_material(knowledge: str, allowed_hashes: set = None, user_id: int = None) -> dict:
    """根据知识点名称获取本地学习资料内容（Markdown格式）

    Args:
        knowledge: 知识点文本
        allowed_hashes: 允许显示的图片hash集合（用于控制每个资源最多5张图）
        user_id: 当前用户ID（用于查询私有教程版本）

    Returns:
        {"found": True/False, "content": ..., "source_type": ..., "tutorial_id": ..., ...}
    """
    if not knowledge:
        return _fallback_material(knowledge)

    # === 优先从数据库读取（种子数据 / 用户私有版本） ===
    if user_id:
        db_result = _get_tutorial_from_db(knowledge, user_id)
    else:
        db_result = _get_tutorial_from_db(knowledge)  # 仅查种子数据
    if db_result:
        # 注入图片和 mermaid 处理
        content = db_result["content"]
        content = _wrap_naked_mermaid(content)
        content = _inject_cached_images(content, allowed_hashes=allowed_hashes)
        extracted = extract_mermaid_blocks(content)
        db_result["content"] = content
        db_result["article_text"] = extracted["article_text"]
        db_result["mermaid_code_list"] = extracted["mermaid_list"]
        return db_result

    # === Fallback: 从文件系统读取（旧逻辑保持不变） ===
    materials_index = _load_materials_index()
    if not materials_index:
        return _fallback_material(knowledge)

    knowledge_lower = knowledge.lower().strip()

    # 1. 精确匹配标签名
    for tag, rel_path in materials_index.items():
        if tag.lower() == knowledge_lower:
            return _read_material_file(rel_path, tag, allowed_hashes=allowed_hashes)

    # 2. 包含匹配
    for tag, rel_path in materials_index.items():
        tag_lower = tag.lower()
        if tag_lower in knowledge_lower or knowledge_lower in tag_lower:
            return _read_material_file(rel_path, tag, allowed_hashes=allowed_hashes)

    # 3. 关键词匹配
    import re
    keywords = re.split(r'[，,、\s]+', knowledge)
    keywords = [k.strip().lower() for k in keywords if len(k.strip()) >= 2]

    for tag, rel_path in materials_index.items():
        tag_lower = tag.lower()
        for kw in keywords:
            if kw in tag_lower:
                return _read_material_file(rel_path, tag, allowed_hashes=allowed_hashes)

    # 4. 无匹配，返回默认材料
    return _fallback_material(knowledge)


def _inject_cached_images(content: str, allowed_hashes: set = None) -> str:
    """注入已缓存 SVG 为 base64 图片。

    Args:
        content: markdown 文本
        allowed_hashes: 如果提供，只注入列表中存在的hash；不在列表中的Image-Prompt块会被隐藏。
                       如果为None（默认），保留所有Image-Prompt块（兼容旧行为）。"""
    import hashlib, re as _re, base64
    from database import get_db as _gdb

    conn = _gdb()
    rows = conn.execute("SELECT prompt_hash, svg_content FROM generated_images WHERE svg_content IS NOT NULL").fetchall()
    conn.close()
    cache = {r["prompt_hash"]: r["svg_content"] for r in rows if r["svg_content"]}

    def _repl(m):
        body = m.group(1).strip()
        # Strip optional ``` markers
        if body.startswith('```'): body = body[3:]
        if body.endswith('```'): body = body[:-3]
        body = body.strip()
        if len(body) < 10:
            return ''  # 提示词过短或为空，直接隐藏
        h = hashlib.sha256(body.encode()).hexdigest()

        # With allowed_hashes: only show if hash is in the list
        if allowed_hashes is not None:
            if h not in allowed_hashes:
                return ''  # Hide this Image-Prompt block entirely
            # Allow — inject cached image if available
            svg = cache.get(h)
            if svg:
                b64 = base64.b64encode(svg.encode()).decode()
                return f'<div style="margin:20px 0;text-align:center"><img src="data:image/svg+xml;base64,{b64}" style="max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08)" /></div>'
            # Even if cached image missing, still hide the prompt text (keep image placeholder area)
            return f'<div style="margin:20px 0;text-align:center;padding:40px;background:#f5f7fa;border-radius:8px;color:#999;font-size:13px">�� 配图生成中，请稍后刷新页面...</div>'

        # Legacy mode (no allowed_hashes filter): inject cached images, hide uncached prompts
        svg = cache.get(h)
        if svg:
            b64 = base64.b64encode(svg.encode()).decode()
            return f'<div style="margin:20px 0;text-align:center"><img src="data:image/svg+xml;base64,{b64}" style="max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08)" /></div>'
        return ''  # 隐藏未缓存的Image-Prompt块，不显示原始提示词

    pattern = r'(?:\*\*)?Image-Prompt\([^)]+\):(?:\*\*)?\s*(.+?)(?=\n\n(?:#|\*\*Image-Prompt|Image-Prompt)|\n(?:#|\*\*Image-Prompt|Image-Prompt)|$)'
    return _re.sub(pattern, _repl, content, flags=_re.DOTALL)


def _read_material_file(rel_path: str, tag: str, allowed_hashes: set = None) -> dict:
    """读取Markdown文件内容，自动注入已缓存的配图，并提取Mermaid代码"""
    full_path = _os.path.join(MATERIALS_BASE_DIR, rel_path)
    if _os.path.exists(full_path):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = _wrap_naked_mermaid(content)  # 后端统一包裹裸露的 flowchart
            content = _inject_cached_images(content, allowed_hashes=allowed_hashes)
            # 提取 mermaid 代码块（正文分离 + 独立列表）
            extracted = extract_mermaid_blocks(content)
            return {
                "found": True,
                "content": content,  # 保留原始完整内容（兼容旧版前端）
                "article_text": extracted["article_text"],
                "mermaid_code_list": extracted["mermaid_list"],
                "file_path": rel_path,
                "matched_tag": tag,
                "format": "markdown"
            }
        except Exception:
            pass
    return _fallback_material(tag)


def _fallback_material(knowledge: str = "") -> dict:
    """当找不到匹配资料时返回通用引导内容"""
    topic = knowledge or "AI智能体"
    content = f"""# {topic}

## 学习指引

当前知识点「{topic}」的详细学习资料正在编写中。

## 建议学习路径

1. 先理解基础概念：了解「{topic}」在AI智能体学科中的位置和重要性
2. 查阅相关资源：访问「学习资源」页面获取相关的在线教程和文档
3. 动手实践：理论结合实际，通过编写代码和运行示例加深理解
4. 提问交流：使用「智能答疑」功能向AI助教提出具体问题

## 相关知识点

建议同时复习与该知识点相关的前置知识，确保基础扎实。可查看学习路径了解完整的知识依赖关系。

---
> 提示：完整学习资料正在持续完善中，敬请期待。
"""
    return {
        "found": False,
        "content": content,
        "file_path": None,
        "matched_tag": knowledge,
        "format": "markdown"
    }


import asyncio
import html as _html_lib


async def search_and_curate_material(user_id: int, knowledge: str) -> dict:
    """根据知识点，联网搜索并利用AI整理学习资料（Markdown格式）

    工作流程：
    1. 使用Bing搜索知识点相关内容
    2. 抓取前2-3个有实质内容的网页全文
    3. 由AI整合、组织、去重、提取核心内容，生成结构化Markdown学习资料

    Args:
        user_id: 用户ID（用于获取LLM配置）
        knowledge: 知识点文本

    Returns:
        {"found": True/False, "content": "markdown内容", "matched_tag": "标签名", "sources": [...来源URL...]}
    """
    if not knowledge:
        return _fallback_material(knowledge)

    from services.ai_service import web_search, call_llm

    # 1. 联网搜索
    search_query = f"{knowledge} 教程 AI智能体"
    search_results = await web_search(search_query, max_results=5)

    if not search_results:
        search_query_cn = f"{knowledge} 人工智能 学习资料"
        search_results = await web_search(search_query_cn, max_results=5)

    # 2. 抓取搜索结果中的网页正文
    web_contents = []
    sources = []

    async def fetch_page(url: str, title: str) -> tuple:
        """抓取单个网页的文本内容"""
        try:
            import httpx
            import re as _re
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    },
                )
                if resp.status_code != 200:
                    return (title, url, "")
                # 简单提取网页正文：去除script/style标签，提取纯文本
                text = resp.text
                text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.DOTALL | _re.IGNORECASE)
                text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL | _re.IGNORECASE)
                text = _re.sub(r'<[^>]+>', ' ', text)
                text = _re.sub(r'\s+', ' ', text).strip()
                # 截取前8000字符，避免超出token限制
                if len(text) > 8000:
                    text = text[:8000] + "..."
                return (title, url, text)
        except Exception:
            return (title, url, "")

    # 抓取前3个搜索结果
    fetch_tasks = []
    for sr in search_results[:3]:
        if sr.get("url") and sr.get("title"):
            fetch_tasks.append(fetch_page(sr["url"], sr["title"]))

    if fetch_tasks:
        results = await asyncio.gather(*fetch_tasks)
        for title, url, content in results:
            if content and len(content) > 200:  # 过滤掉无实质内容的页面
                web_contents.append({"title": title, "url": url, "content": content})
                sources.append({"title": title, "url": url})

    # 如果没有任何网页内容，回退到只用搜索摘要
    if not web_contents:
        snippets_text = "\n\n".join([
            f"### {sr.get('title', '')}\n> {sr.get('snippet', '')}"
            for sr in search_results[:5] if sr.get("snippet")
        ])
        if not snippets_text:
            return _fallback_material(knowledge)
    else:
        snippets_text = "\n\n---\n\n".join([
            f"### [{item['title']}]({item['url']})\n{item['content']}"
            for item in web_contents
        ])

    # 3. AI整理与生成
    curation_prompt = f"""你是一位资深的AI智能体学科导师，请根据以下从网上搜集到的资料，为知识点「{knowledge}」整理一份结构完整、内容详实的学习资料。

## 原始资料
{snippets_text}

## 整理要求

请生成一份Markdown格式的学习资料，结构如下：

### 1. 概述
简要介绍「{knowledge}」的核心概念和背景（3-5句话）。

### 2. 核心知识
详细阐述该知识点的核心内容，包括：
- 关键概念和定义
- 工作原理/底层逻辑
- 重要特性/属性

### 3. 应用场景
列举该知识点在AI智能体系统中的实际应用场景，并解释为什么重要。

### 4. 易混淆概念
如果存在容易混淆的相关概念，请对比区分。

### 5. 学习建议
给出学习该知识点的具体建议、推荐学习顺序、实践方法。

### 6. 延伸阅读
简短提及该知识点的前沿发展或进阶方向。

## 格式要求
- 通篇使用Markdown格式，h2标题、列表、代码块、引用等
- 语言通俗易懂，适合大学生阅读
- 核心概念用**加粗**突出
- 代码示例使用```代码块```
- 总字数控制在1500-3000字
- 不要提及"从网上搜集"、"根据资料"等字样，让内容读起来像是一份原创学习笔记
- 直接以"# {knowledge}"作为文档标题开始"""

    try:
        curated_content = await call_llm(
            user_id=user_id,
            messages=[
                {"role": "system", "content": "你是一位专业的AI智能体学科导师，擅长将零散的资料整理成结构清晰、内容详实的学习笔记。请严格按照要求输出Markdown格式内容。"},
                {"role": "user", "content": curation_prompt}
            ],
            temperature=0.6,
            max_tokens=4096
        )

        if curated_content and not curated_content.startswith("LLM调用异常"):
            curated_content = _wrap_naked_mermaid(curated_content)
            return {
                "found": True,
                "content": curated_content,
                "file_path": None,
                "matched_tag": knowledge,
                "format": "markdown",
                "sources": sources,
                "source": "web_ai_curated"
            }
    except Exception:
        pass

    # AI整理失败，回退到用搜索摘要生成简单内容
    fallback = f"""# {knowledge}

## 概述
以下内容基于网络搜索结果整理，建议通过更多渠道深入学习。

{snippets_text}

---
> 提示：AI整理功能暂不可用，以上为搜索原始结果。请确保已在个人中心配置AI大模型API Key。
"""
    return {
        "found": False,
        "content": fallback,
        "file_path": None,
        "matched_tag": knowledge,
        "format": "markdown",
        "sources": sources,
        "source": "search_raw"
    }


def get_resource_material(resource_id: str, user_id: int = 1) -> dict:
    """根据资源ID获取学习资料（优先本地，兜底AI联网整理）

    策略：
    1. 通过资源ID在 resources.json 中找到资源
    2. 用资源的 tags 逐条匹配本地 learning_materials
    3. 命中多条时合并所有匹配的资料
    4. 本地无匹配时，用第一个tag走AI联网搜索+整理
    """
    all_resources = load_resources()
    resource = next((r for r in all_resources if r.get("id") == resource_id), None)
    if not resource:
        return _fallback_material(resource_id)

    tags = resource.get("tags", [])
    title = resource.get("title", "")

    # 加载图片配置（每个资源最多5张均匀分布）
    img_config = _load_resource_image_config()
    allowed_hashes = set(img_config.get(resource_id, [])) if img_config else None

    # 1. 尝试从本地 learning_materials 匹配所有 tag
    matched_contents = []
    matched_tags = []
    seen_tags = set()

    for tag in tags:
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        local = get_local_material(tag, allowed_hashes=allowed_hashes)
        if local.get("found") and local.get("content"):
            # 避免重复添加相同内容
            content_preview = local["content"][:100]
            if content_preview not in [c[:100] for c in matched_contents]:
                matched_contents.append(local["content"])
                matched_tags.append(tag)

    if matched_contents:
        # 合并多份资料
        if len(matched_contents) == 1:
            merged = matched_contents[0]
        else:
            merged = "\n\n---\n\n".join(matched_contents)

        return {
            "found": True,
            "content": merged,
            "file_path": None,
            "matched_tag": "、".join(matched_tags),
            "format": "markdown",
            "source": "local",
            "resource_title": title,
            "resource_url": resource.get("url", ""),
        }

    # 2. 本地无匹配，用第一个 tag 走联网搜索+AI整理（异步需要在调用处处理）
    return {
        "found": False,
        "content": None,
        "matched_tag": tags[0] if tags else "",
        "format": "markdown",
        "source": "fallback",
        "resource_title": title,
        "resource_url": resource.get("url", ""),
    }


async def get_resource_material_async(resource_id: str, user_id: int = 1) -> dict:
    """异步版本：本地无匹配时自动走联网搜索+AI整理"""
    result = get_resource_material(resource_id, user_id)

    if result.get("found"):
        return result

    # 走联网搜索+AI整理
    tag = result.get("matched_tag", "")
    if tag:
        web_result = await search_and_curate_material(user_id, tag)
        if web_result.get("found"):
            web_result["resource_title"] = result.get("resource_title", "")
            web_result["resource_url"] = result.get("resource_url", "")
            return web_result

    # 完全兜底
    return _fallback_material(result.get("matched_tag", ""))


def get_collected_resources(user_id: int) -> list:
    """获取收藏的资源"""
    conn = get_db()
    rows = conn.execute(
        "SELECT resource_id FROM user_resources WHERE user_id = ? AND collected = 1",
        (user_id,)
    ).fetchall()
    conn.close()

    all_resources = load_resources()
    collected_ids = set(r["resource_id"] for r in rows)
    return [r for r in all_resources if r.get("id") in collected_ids]
 
