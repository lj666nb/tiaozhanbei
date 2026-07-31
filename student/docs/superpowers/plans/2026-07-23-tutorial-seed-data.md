# 教程文档种子数据系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将系统预置教程文档纳入种子数据管理（数据库 + Git 分发），支持用户私有修改和 AI 生成自定义教程。

**Architecture:** 新增 `tutorial_documents` 表存储教程内容（seed/user_modified/ai_generated），构建脚本将 `learning_materials/*.md` 打包为 `tutorial_seed.json` 随 Git 分发。读取链路改为数据库优先 → 文件 fallback。

**Tech Stack:** Python FastAPI (backend), SQLite, Vue3 (frontend), DeepSeek API (AI 生成)

## Global Constraints

- 每次修改代码后必须执行 `docker compose up -d --build` 部署
- 部署后必须使用 Playwright MCP 进行端到端测试（demo/demo123）
- 禁止将真实 API Key 写入代码
- 种子数据按 `knowledge_tag` 去重，不覆盖已有数据

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/build_tutorial_seed.py` | 扫描 learning_materials 生成 seed JSON |
| Create | `backend/data/tutorial_seed.json` | 种子数据文件（构建脚本生成） |
| Modify | `backend/database.py` | 新增 tutorial_documents 表 + init_db 导入种子 |
| Modify | `backend/schemas.py` | 新增 Pydantic 请求/响应模型 |
| Modify | `backend/services/resource_service.py` | 读取逻辑改为 DB 优先 → 文件 fallback |
| Modify | `backend/routers/learning_router.py` | 新增 PUT/DELETE/POST 端点 |
| Modify | `frontend/src/api/learning.js` | 新增前端 API 调用 |
| Modify | `frontend/src/views/LearningPath.vue` | 来源标识 + AI 生成 + 编辑 + 恢复 |

---

### Task 1: 构建种子数据生成脚本

**Files:**
- Create: `backend/build_tutorial_seed.py`

**Interfaces:**
- Produces: `build_tutorial_seed.py` 脚本，运行时生成 `backend/data/tutorial_seed.json`

- [ ] **Step 1: 编写构建脚本**

```python
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
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATERIALS_DIR = os.path.join(PROJECT_ROOT, "learning_materials")
INDEX_PATH = os.path.join(MATERIALS_DIR, "index.json")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tutorial_seed.json")


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
```

- [ ] **Step 2: 运行脚本生成种子数据文件**

```bash
cd backend && source .venv/Scripts/activate && python build_tutorial_seed.py
```

Expected: 输出 `[OK]` 并生成 `backend/data/tutorial_seed.json`，约 80+ 篇文档。

- [ ] **Step 3: 验证生成的文件结构**

```bash
python -c "import json; d=json.load(open('backend/data/tutorial_seed.json','r',encoding='utf-8')); print(f'Docs: {len(d)}, First: {d[0][\"knowledge_tag\"]}')"
```

- [ ] **Step 4: 提交**

```bash
git add backend/build_tutorial_seed.py backend/data/tutorial_seed.json
git commit -m "feat: add tutorial seed data build script and generated seed JSON"
```

---

### Task 2: 数据库表与种子导入

**Files:**
- Modify: `backend/database.py` — 在 `init_db()` 中新增建表 + 种子导入逻辑

**Interfaces:**
- Consumes: `backend/data/tutorial_seed.json`（Task 1 生成）
- Produces: `tutorial_documents` 表（含 seed 记录），供 Task 3/4/5 查询

- [ ] **Step 1: 在 `init_db()` 中新增建表 SQL**

在 `database.py` 的 `init_db()` 函数中，找到现有建表语句区域（约 `conn.executescript(...)` 之后），在 `exercise_test_metadata` 建表之前插入：

```python
    # 教程文档表 — 种子数据 + 用户私有修改 + AI 生成
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tutorial_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_tag TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            source_type TEXT DEFAULT 'seed',
            user_id INTEGER,
            parent_id INTEGER,
            curriculum_version TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tutorial_knowledge ON tutorial_documents(knowledge_tag, user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tutorial_user ON tutorial_documents(user_id, source_type)")
    conn.commit()
```

- [ ] **Step 2: 在 `init_db()` 末尾新增种子导入逻辑**

在 `_import_svgs_to_db()` 调用之前插入：

```python
    # Seed tutorial_documents from tutorial_seed.json (only insert new knowledge_tags)
    try:
        _seed_path = os.path.join(os.path.dirname(__file__), "data", "tutorial_seed.json")
        if os.path.exists(_seed_path):
            import json as _json
            with open(_seed_path, "r", encoding="utf-8") as _f:
                _seed_docs = _json.load(_f)
            _imported = 0
            for _doc in _seed_docs:
                _existing = conn.execute(
                    "SELECT 1 FROM tutorial_documents WHERE knowledge_tag = ? AND source_type = 'seed' AND user_id IS NULL",
                    (_doc["knowledge_tag"],)
                ).fetchone()
                if _existing:
                    continue
                conn.execute(
                    "INSERT INTO tutorial_documents (knowledge_tag, title, content, source_type, user_id, parent_id, curriculum_version) "
                    "VALUES (?, ?, ?, 'seed', NULL, NULL, ?)",
                    (_doc["knowledge_tag"], _doc.get("title", ""), _doc["content"], _doc.get("curriculum_version", ""))
                )
                _imported += 1
            conn.commit()
            if _imported:
                print(f"[OK] Imported {_imported} tutorial seed documents into tutorial_documents table")
    except Exception as e:
        print(f"[WARN] Tutorial seed import failed: {e}")
```

- [ ] **Step 3: 构建并部署验证**

```bash
docker compose up -d --build
```

Wait ~15s, then check:

```bash
docker compose exec backend python -c "
from database import get_db
conn = get_db()
count = conn.execute(\"SELECT COUNT(*) FROM tutorial_documents WHERE source_type='seed'\").fetchone()[0]
conn.close()
print(f'Seed tutorial documents in DB: {count}')
"
```

Expected: `Seed tutorial documents in DB: 80+`

- [ ] **Step 4: 提交**

```bash
git add backend/database.py
git commit -m "feat: add tutorial_documents table and seed data import in init_db"
```

---

### Task 3: 新增 Pydantic 模型

**Files:**
- Modify: `backend/schemas.py` — 新增请求/响应模型

**Interfaces:**
- Produces: `TutorialSaveRequest`, `TutorialGenerateRequest`, `TutorialResponse`，供 Task 5 端点使用

- [ ] **Step 1: 在 schemas.py 末尾添加模型类**

```python
# ===== Tutorial Documents =====
class TutorialSaveRequest(BaseModel):
    title: str = ""
    content: str = Field(..., min_length=1)
    source_type: str = Field(default="ai_generated")  # "ai_generated" | "user_modified"

class TutorialGenerateRequest(BaseModel):
    knowledge_tag: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    goal: str = ""

class TutorialResponse(BaseModel):
    tutorial_id: int
    knowledge_tag: str
    title: str
    source_type: str
    message: str = ""
```

- [ ] **Step 2: 验证模块导入**

```bash
cd backend && source .venv/Scripts/activate && python -c "from schemas import TutorialSaveRequest, TutorialGenerateRequest, TutorialResponse; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add backend/schemas.py
git commit -m "feat: add tutorial document request/response schemas"
```

---

### Task 4: 修改资源读取逻辑（DB 优先 → 文件 fallback）

**Files:**
- Modify: `backend/services/resource_service.py` — 修改 `get_local_material()` 函数

**Interfaces:**
- Consumes: `tutorial_documents` 表（Task 2 创建）
- Produces: `get_local_material()` 返回新增 `source_type`、`tutorial_id`、`parent_id` 字段
- Consumed by: `GET /api/learning/resource` 端点、Task 5 前端

- [ ] **Step 1: 新增数据库查询辅助函数**

在 `resource_service.py` 的 `_load_materials_index()` 后面插入：

```python
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
```

- [ ] **Step 2: 修改 `get_local_material()` 函数**

在 `get_local_material()` 函数开头（`if not knowledge:` 之前）插入 DB 优先查询逻辑：

```python
def get_local_material(knowledge: str, allowed_hashes: set = None, user_id: int = None) -> dict:
    """根据知识点名称获取本地学习资料内容（Markdown格式）

    Args:
        knowledge: 知识点文本
        allowed_hashes: 允许显示的图片hash集合
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
    # ... existing code continues below ...
```

注意：需要保留原有的文件系统 fallback 逻辑（`materials_index = _load_materials_index()` 等），放在 `# === Fallback` 注释之后。

- [ ] **Step 3: 更新调用方传入 user_id**

在 `routers/learning_router.py` 中，更新 `get_learning_resource` 端点，将 `current_user["id"]` 传给 `get_local_material()`：

找到 `get_learning_resource` 函数（约 L69-79）：

```python
@router.get("/resource", response_model=APIResponse)
async def get_learning_resource(knowledge: str = "", current_user: dict = Depends(get_current_user)):
    """根据知识点获取本地学习资料（Markdown格式）"""
    try:
        result = resource_service.get_local_material(knowledge, user_id=current_user["id"])
        if result and result.get("found"):
            return APIResponse(data=result)
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"获取学习资源失败: {str(e)}", data=None)
```

- [ ] **Step 4: 构建部署验证**

```bash
docker compose up -d --build
```

Wait ~15s. Then use Playwright MCP to:
1. Navigate to `http://localhost:80` and login as demo/demo123
2. Generate a project-based learning path (select all 4 modules)
3. Click "去学习" on the first task
4. Verify tutorial content loads correctly

- [ ] **Step 5: 提交**

```bash
git add backend/services/resource_service.py backend/routers/learning_router.py
git commit -m "feat: prioritize tutorial_documents DB over file system for resource loading"
```

---

### Task 5: 新增教程管理 API 端点

**Files:**
- Modify: `backend/routers/learning_router.py` — 新增 PUT/DELETE/POST 端点

**Interfaces:**
- Consumes: `TutorialSaveRequest`, `TutorialGenerateRequest` (Task 3)
- Produces: `PUT /api/learning/tutorial/{knowledge_tag}`, `DELETE /api/learning/tutorial/{knowledge_tag}`, `POST /api/learning/tutorial/generate`
- Consumed by: 前端 API 调用 (Task 6)

- [ ] **Step 1: 新增保存教程端点**

在 `learning_router.py` 中，现有 `@router.get("/code-completions")` 之后添加：

```python
@router.put("/tutorial/{knowledge_tag:path}", response_model=APIResponse)
async def save_tutorial(knowledge_tag: str, req: TutorialSaveRequest, current_user: dict = Depends(get_current_user)):
    """保存或更新用户的教程文档（私有版本）"""
    import json as _json
    from datetime import datetime
    conn = get_db()

    try:
        # 判断该 knowledge_tag 是否有种子记录
        seed = conn.execute(
            "SELECT id FROM tutorial_documents WHERE knowledge_tag = ? AND source_type = 'seed' AND user_id IS NULL",
            (knowledge_tag,)
        ).fetchone()

        # 查询用户是否已有私有记录
        existing = conn.execute(
            "SELECT id FROM tutorial_documents WHERE knowledge_tag = ? AND user_id = ?",
            (knowledge_tag, current_user["id"])
        ).fetchone()

        source_type = req.source_type
        parent_id = None

        if seed and not existing:
            # 用户修改种子文档 → 自动标记为 user_modified
            if source_type == "ai_generated":
                parent_id = None  # 明确选择 AI 生成则不算修改种子
            else:
                source_type = "user_modified"
                parent_id = seed["id"]

        if existing:
            conn.execute(
                "UPDATE tutorial_documents SET title = ?, content = ?, source_type = ?, updated_at = ? WHERE id = ?",
                (req.title, req.content, source_type, datetime.now().isoformat(), existing["id"])
            )
            tutorial_id = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO tutorial_documents (knowledge_tag, title, content, source_type, user_id, parent_id) VALUES (?, ?, ?, ?, ?, ?)",
                (knowledge_tag, req.title, req.content, source_type, current_user["id"], parent_id)
            )
            tutorial_id = cursor.lastrowid

        conn.commit()

        return APIResponse(data={
            "tutorial_id": tutorial_id,
            "knowledge_tag": knowledge_tag,
            "source_type": source_type,
            "message": "教程已保存"
        })
    except Exception as e:
        return APIResponse(code=500, message=f"保存教程失败: {str(e)}", data=None)
    finally:
        conn.close()
```

- [ ] **Step 2: 新增删除用户教程端点**

```python
@router.delete("/tutorial/{knowledge_tag:path}", response_model=APIResponse)
async def delete_tutorial(knowledge_tag: str, current_user: dict = Depends(get_current_user)):
    """删除用户的私有教程（回退到种子版本），不影响种子数据"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM tutorial_documents WHERE knowledge_tag = ? AND user_id = ?",
            (knowledge_tag, current_user["id"])
        )
        deleted = cursor.rowcount
        conn.commit()
        return APIResponse(data={
            "deleted": deleted,
            "knowledge_tag": knowledge_tag,
            "message": "已恢复为系统预置版本" if deleted else "没有需要删除的私有版本"
        })
    except Exception as e:
        return APIResponse(code=500, message=f"删除教程失败: {str(e)}", data=None)
    finally:
        conn.close()
```

- [ ] **Step 3: 新增 AI 生成教程端点**

```python
@router.post("/tutorial/generate", response_model=APIResponse)
async def generate_tutorial(req: TutorialGenerateRequest, current_user: dict = Depends(get_current_user)):
    """AI 生成教程文档（遵循种子文档格式）"""
    from services.ai_service import call_llm, extract_json_object

    # 构建格式参考：读取一篇种子文档作为格式样本
    format_sample = ""
    try:
        seed = get_db().execute(
            "SELECT content FROM tutorial_documents WHERE source_type = 'seed' AND user_id IS NULL LIMIT 1"
        ).fetchone()
        if seed:
            format_sample = seed["content"][:1500]
    except Exception:
        pass

    prompt = f"""你是一位资深的AI智能体学科导师，请为以下主题生成一份结构完整的学习教程。

【主题】{req.topic}
【学习目标】{req.goal or "系统掌握该知识点"}
【格式参考 — 请严格遵循此结构】
{format_sample if format_sample else '# 标题\\n## 概述\\n## 核心知识\\n## 应用场景\\n## 学习建议\\n## 延伸阅读'}

【生成要求】
1. 结构必须与格式参考一致：以 # 标题开头，依次包含 ## 概述、## 核心知识、## 应用场景、## 学习建议、## 延伸阅读等章节
2. 核心概念用 **加粗** 突出
3. 代码示例使用 ```代码块```
4. 语言通俗易懂，适合大学生/初学者阅读
5. 总字数控制在 1500-3500 字
6. 直接以 "# {req.topic}" 作为文档标题开始

请直接输出完整的 Markdown 文档，不要有其他说明文字。"""

    try:
        response = await call_llm(
            current_user["id"],
            [{"role": "system", "content": "你是专业的AI智能体学科导师，擅长编写结构清晰的学习教程。只输出Markdown内容。"},
             {"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=4096
        )

        if response.startswith("LLM调用异常"):
            return APIResponse(code=500, message=f"AI 生成失败: {response}", data=None)

        # 保存生成的内容到数据库
        from database import get_db as _gdb
        conn = _gdb()
        cursor = conn.execute(
            "INSERT INTO tutorial_documents (knowledge_tag, title, content, source_type, user_id, parent_id) VALUES (?, ?, ?, 'ai_generated', ?, NULL)",
            (req.knowledge_tag, req.topic, response, current_user["id"])
        )
        tutorial_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return APIResponse(data={
            "tutorial_id": tutorial_id,
            "knowledge_tag": req.knowledge_tag,
            "title": req.topic,
            "content": response,
            "source_type": "ai_generated",
            "message": "AI 教程已生成并保存"
        })
    except Exception as e:
        return APIResponse(code=500, message=f"AI 生成教程失败: {str(e)}", data=None)
```

- [ ] **Step 4: 更新 import 语句**

在 `learning_router.py` 顶部确保导入了新的 schemas：

```python
from schemas import APIResponse, LearningPathGenerateRequest, PathProgressUpdateRequest, TaskUpdate, TaskQuizRequest, CodeExecuteRequest, CodeStepGuideRequest, CodeStepCheckRequest, DiagnosticTestRequest, TutorialSaveRequest, TutorialGenerateRequest
```

- [ ] **Step 5: 构建部署并测试 API**

```bash
docker compose up -d --build
```

Wait ~15s. Test via curl:

```bash
# Test save endpoint
curl -X PUT "http://localhost:8001/api/learning/tutorial/test-topic" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test", "content":"# Test\nContent here", "source_type":"ai_generated"}'

# Test delete endpoint
curl -X DELETE "http://localhost:8001/api/learning/tutorial/test-topic" \
  -H "Authorization: Bearer <token>"
```

- [ ] **Step 6: 提交**

```bash
git add backend/routers/learning_router.py
git commit -m "feat: add tutorial save/delete/AI-generate API endpoints"
```

---

### Task 6: 前端 API 层新增调用

**Files:**
- Modify: `frontend/src/api/learning.js` — 新增 API 调用函数

**Interfaces:**
- Consumes: Task 5 的 API 端点
- Produces: `saveTutorial()`, `deleteTutorial()`, `generateAITutorial()` 函数
- Consumed by: Task 7 (LearningPath.vue)

- [ ] **Step 1: 在 learning.js 末尾添加新 API 函数**

```javascript
// 教程文档管理
export const saveTutorial = (knowledgeTag, data) =>
  request.put(`/learning/tutorial/${encodeURIComponent(knowledgeTag)}`, data)

export const deleteTutorial = (knowledgeTag) =>
  request.delete(`/learning/tutorial/${encodeURIComponent(knowledgeTag)}`)

export const generateAITutorial = (data) =>
  request.post('/learning/tutorial/generate', data)
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/learning.js
git commit -m "feat: add frontend API calls for tutorial management"
```

---

### Task 7: 前端教程阅读区改造

**Files:**
- Modify: `frontend/src/views/LearningPath.vue` — 来源标识 + 编辑入口 + AI 生成 + 恢复按钮

**Interfaces:**
- Consumes: Task 6 的 API 函数 (`saveTutorial`, `deleteTutorial`, `generateAITutorial`)
- Consumes: Task 4 的 `source_type`/`tutorial_id` 响应字段

- [ ] **Step 1: 新增 import 和响应式状态**

在 `<script setup>` 区域，import 新 API：

```javascript
import { getLearningResource, recordStudyVisit, saveTutorial, deleteTutorial, generateAITutorial } from '../api/learning'
```

新增响应式变量（在 `learnDialogLoading` 之后）：

```javascript
const tutorialMeta = ref({ source_type: '', tutorial_id: null, parent_id: null })
const showAIDialog = ref(false)
const aiGenForm = reactive({ knowledge_tag: '', topic: '', goal: '' })
const aiGenLoading = ref(false)
const isEditing = ref(false)
const editContent = ref('')
const saveLoading = ref(false)
```

- [ ] **Step 2: 更新 loadLearningMaterial 保存元信息**

在 `loadLearningMaterial()` 函数中，`resource` 返回后保存元信息：

```javascript
// 在 learnDialogTitle.value = ... 之前添加
tutorialMeta.value = {
  source_type: resource.source_type || 'file',
  tutorial_id: resource.tutorial_id || null,
  parent_id: resource.parent_id || null
}
```

- [ ] **Step 3: 添加来源标识标签模板**

在教程内容区域（`.reader-page-nav` 内部、导航按钮之后）添加来源标识：

```html
<!-- 来源标识 -->
<div v-if="tutorialMeta.source_type" class="tutorial-source-badge" :class="'source-' + tutorialMeta.source_type">
  <el-tag v-if="tutorialMeta.source_type === 'seed'" type="success" size="small" effect="plain">📚 系统预置</el-tag>
  <el-tag v-else-if="tutorialMeta.source_type === 'user_modified'" type="warning" size="small" effect="plain">✏️ 我的修改</el-tag>
  <el-tag v-else-if="tutorialMeta.source_type === 'ai_generated'" type="primary" size="small" effect="plain">🤖 AI 生成</el-tag>
  <el-button v-if="tutorialMeta.source_type === 'user_modified'" type="danger" size="small" text @click="restoreSeedTutorial">恢复原始版本</el-button>
  <el-button v-if="tutorialMeta.source_type === 'ai_generated'" type="danger" size="small" text @click="deleteCustomTutorial">删除此教程</el-button>
</div>
```

- [ ] **Step 4: 添加 AI 生成弹窗模板**

在现有 `el-dialog`（模块选择）之后添加：

```html
<el-dialog v-model="showAIDialog" title="🤖 AI 生成教程" width="550px" :close-on-click-modal="false">
  <el-form :model="aiGenForm" label-position="top">
    <el-form-item label="知识点标识（英文/拼音，用于系统索引）">
      <el-input v-model="aiGenForm.knowledge_tag" placeholder="如: custom-rag-advanced" />
    </el-form-item>
    <el-form-item label="教程主题">
      <el-input v-model="aiGenForm.topic" placeholder="如: RAG高级检索技巧" />
    </el-form-item>
    <el-form-item label="学习目标（可选）">
      <el-input v-model="aiGenForm.goal" type="textarea" :rows="2" placeholder="想通过这篇教程达成什么学习目标？" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="showAIDialog = false">取消</el-button>
    <el-button type="primary" :loading="aiGenLoading" :disabled="!aiGenForm.knowledge_tag || !aiGenForm.topic" @click="doAIGenerate">开始生成</el-button>
  </template>
</el-dialog>
```

- [ ] **Step 5: 添加 AI 生成按钮到工具栏**

在 `.reader-page-nav` 中的操作区添加：

```html
<el-button size="small" text @click="openAIDialog">🤖 AI 生成教程</el-button>
```

- [ ] **Step 6: 添加编辑模式切换**

在教程内容上方添加编辑/预览切换：

```html
<div v-if="tutorialMeta.tutorial_id" class="tutorial-edit-bar">
  <el-button size="small" :type="isEditing ? '' : 'primary'" text @click="isEditing = !isEditing">
    {{ isEditing ? '👁 预览' : '✏️ 编辑' }}
  </el-button>
</div>
```

当 `isEditing` 为 true 时，用 `<el-input type="textarea">` 替换 `v-html` 内容区。

- [ ] **Step 7: 实现操作函数**

```javascript
function openAIDialog() {
  aiGenForm.knowledge_tag = ''
  aiGenForm.topic = ''
  aiGenForm.goal = ''
  showAIDialog.value = true
}

async function doAIGenerate() {
  aiGenLoading.value = true
  try {
    const result = await generateAITutorial({
      knowledge_tag: aiGenForm.knowledge_tag,
      topic: aiGenForm.topic,
      goal: aiGenForm.goal
    })
    showAIDialog.value = false
    ElMessage.success('AI 教程已生成！')
    // 模拟一个 task 来显示生成的教程
    tutorialMeta.value = {
      source_type: 'ai_generated',
      tutorial_id: result.tutorial_id,
      parent_id: null
    }
    learnDialogTitle.value = result.title
    learnDialogContent.value = renderMarkdown(result.content)
    await nextTick()
    if (materialRef.value) {
      materialRef.value.scrollTop = 0
      bindCodeBlockActions(materialRef.value)
      rebuildArticleOutline()
    }
  } catch (e) {
    ElMessage.error('AI 生成失败: ' + (e.response?.data?.message || e.message))
  } finally {
    aiGenLoading.value = false
  }
}

async function restoreSeedTutorial() {
  try {
    await ElMessageBox.confirm('将放弃你的修改，恢复为系统预置版本。确定？', '恢复原始版本', { type: 'warning' })
    await deleteTutorial(currentLearnTask.value.knowledge || currentLearnTask.value.topic)
    ElMessage.success('已恢复为系统预置版本')
    tutorialMeta.value = { source_type: 'seed', tutorial_id: null, parent_id: null }
    await loadLearningMaterial(currentLearnTask.value, false)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('恢复失败')
  }
}

async function deleteCustomTutorial() {
  try {
    await ElMessageBox.confirm('将删除此 AI 生成的教程。确定？', '删除教程', { type: 'warning' })
    await deleteTutorial(currentLearnTask.value.knowledge || currentLearnTask.value.topic)
    ElMessage.success('已删除')
    tutorialMeta.value = { source_type: 'seed', tutorial_id: null, parent_id: null }
    await loadLearningMaterial(currentLearnTask.value, false)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function saveEditedTutorial() {
  if (!editContent.value.trim()) return ElMessage.warning('内容不能为空')
  saveLoading.value = true
  try {
    const knowledgeTag = currentLearnTask.value.knowledge || currentLearnTask.value.topic
    await saveTutorial(knowledgeTag, {
      title: learnDialogTitle.value,
      content: editContent.value,
      source_type: tutorialMeta.value.source_type || 'ai_generated'
    })
    ElMessage.success('已保存')
    isEditing.value = false
    learnDialogContent.value = renderMarkdown(editContent.value)
    await nextTick()
    if (materialRef.value) {
      materialRef.value.scrollTop = 0
      bindCodeBlockActions(materialRef.value)
      rebuildArticleOutline()
    }
    if (tutorialMeta.value.source_type === 'seed') {
      tutorialMeta.value.source_type = 'user_modified'
    }
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}
```

- [ ] **Step 8: 添加 import 遗漏**

在 `<script setup>` 中确保 `ElMessageBox` 已被 import：

```javascript
import { ElMessage, ElMessageBox } from 'element-plus'
```

- [ ] **Step 9: 构建部署并 Playwright 测试**

```bash
docker compose up -d --build
```

Wait ~15s. Playwright MCP 测试：
1. Navigate to `http://localhost:80` → login demo/demo123
2. Generate project-based learning path (select all 4 modules)
3. Click "去学习" on task 1 → verify tutorial loads with "📚 系统预置" badge
4. Click "AI 生成教程" → verify dialog opens
5. Check browser console for JS errors

- [ ] **Step 10: 提交**

```bash
git add frontend/src/views/LearningPath.vue
git commit -m "feat: add tutorial source badges, AI generate, edit and restore in LearningPath"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 完整部署**

```bash
docker compose up -d --build
```

- [ ] **Step 2: Playwright MCP 全流程测试**

1. 登录 demo/demo123
2. 生成学习路径（全选 4 个模块）
3. 打开第一篇教程 → 验证 "📚 系统预置" 标签出现
4. 编辑教程内容并保存 → 验证标签变为 "✏️ 我的修改"
5. 点击 "恢复原始版本" → 验证恢复成功
6. 打开 AI 生成弹窗 → 填入主题 → 生成 → 验证内容展示
7. 检查浏览器 console 无 JS 错误

- [ ] **Step 3: 提交（如有遗漏修改）**

```bash
git status
git add <any-remaining-files>
git commit -m "chore: final cleanup for tutorial seed data system"
```
