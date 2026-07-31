# 教程文档种子数据系统 — 设计文档

## 背景

项目制学习路径（`agent_course.py` → `COURSE_TRACKS`）包含 4 个模块 12 个任务，每个任务通过 `knowledge` 字段绑定一篇教程 Markdown 文档。目前这些教程以 `.md` 文件形式存放在 `learning_materials/` 目录中，虽然版本控制保证了跨部署的一致性，但缺乏显式的种子数据管理机制，且无法支持用户在路径中创建自定义教程。

## 目标

1. 系统预置教程文档作为"种子数据"，多用户共享、跨电脑（Git）分发
2. 用户可对种子文档做私有修改（不影响他人）
3. 用户可通过 AI 生成自定义教程（遵循种子文档格式）
4. 清晰区分三种数据来源：种子、用户修改、AI 生成

## 数据库变更

### 新增表：`tutorial_documents`

```sql
CREATE TABLE tutorial_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_tag TEXT NOT NULL,          -- 知识点标识，如 "01-第一段LangChain对话"
    title TEXT DEFAULT '',
    content TEXT NOT NULL,                -- Markdown 正文
    source_type TEXT DEFAULT 'seed',      -- 'seed' | 'user_modified' | 'ai_generated'
    user_id INTEGER,                      -- NULL=种子数据（共享）, 有值=用户私有
    parent_id INTEGER,                    -- 用户修改种子文档时指向原始种子记录
    curriculum_version TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tutorial_knowledge ON tutorial_documents(knowledge_tag, user_id);
CREATE INDEX idx_tutorial_user ON tutorial_documents(user_id, source_type);
```

### 字段说明

| 字段 | 种子文档 | 用户修改种子 | AI 生成文档 |
|------|:---:|:---:|:---:|
| `source_type` | `seed` | `user_modified` | `ai_generated` |
| `user_id` | NULL | 当前用户 ID | 当前用户 ID |
| `parent_id` | NULL | 种子文档 ID | NULL |

## 种子数据分发

### 构建脚本

新增 `backend/build_tutorial_seed.py`：

- 扫描 `learning_materials/` 目录下所有 `.md` 文件
- 结合 `learning_materials/index.json` 提取 knowledge_tag → 文件路径映射
- 读取每个 .md 文件内容
- 生成 `backend/data/tutorial_seed.json`（结构化 JSON，包含 knowledge_tag、title、content）

### 导入时机

`database.py` → `init_db()` 在创建 `tutorial_documents` 表后执行：

1. 读取 `backend/data/tutorial_seed.json`
2. 按 `knowledge_tag` 逐个检查是否存在 `source_type='seed' AND user_id IS NULL` 的记录
3. 不存在则 INSERT，存在则跳过（不覆盖，避免擦除用户修改无需动种子）
4. 不删除已有种子记录（种子数据只增不减，新版本种子通过 knowledge_tag 去重）

### Git 管理

- `backend/data/tutorial_seed.json` 纳入版本控制（Git LFS 不需要，预估 <2MB）
- 每次修改/新增 `learning_materials/` 下的教程后，运行构建脚本重新生成
- CI/CD 或 Docker 构建时自动执行

## API 设计

### 读取教程（修改现有端点）

**`GET /api/learning/resource?knowledge=xxx`**

读取逻辑变更（`resource_service.py` → `get_local_material()`）：

```
1. 查询 tutorial_documents WHERE knowledge_tag=xxx AND user_id=当前用户
2. 如果找到 → 返回用户私有版本（source_type + title 一并返回给前端）
3. 如果未找到 → 查询 tutorial_documents WHERE knowledge_tag=xxx AND user_id IS NULL
4. 如果找到 → 返回种子版本
5. 如果仍未找到 → 返回 fallback 内容
```

返回结构新增字段：
```json
{
  "found": true,
  "content": "...",
  "source_type": "seed",
  "parent_id": null,
  "tutorial_id": 123,
  ...
}
```

### 保存/更新用户教程（新增端点）

**`PUT /api/learning/tutorial/{knowledge_tag}`**

```json
// Request
{
  "title": "教程标题",
  "content": "Markdown 正文内容",
  "source_type": "ai_generated"  // 或首次修改种子时自动设为 "user_modified"
}

// Response
{
  "tutorial_id": 456,
  "knowledge_tag": "01-第一段LangChain对话",
  "source_type": "ai_generated",
  "message": "教程已保存"
}
```

处理逻辑：
- 如 `source_type` 为 `ai_generated`：直接 INSERT，user_id=当前用户
- 如已有种子记录但无用户记录 → 创建用户私有副本，source_type=`user_modified`，parent_id=种子记录 ID
- 如已有用户记录 → UPDATE

### AI 生成教程（新增端点）

**`POST /api/learning/tutorial/generate`**

```json
// Request
{
  "knowledge_tag": "custom-topic",
  "topic": "用户输入的主题",
  "goal": "想达成的学习目标"
}

// Response
{
  "tutorial_id": 789,
  "knowledge_tag": "custom-topic",
  "title": "生成的标题",
  "content": "AI 生成的 Markdown 正文（遵循种子文档格式）",
  "source_type": "ai_generated"
}
```

生成格式要求（LLM prompt 约束）：
- `# 标题` → `## 概述` → `## 核心知识` → `## 应用场景` → `## 易混淆概念` → `## 学习建议` → `## 延伸阅读`
- 与种子文档结构一致

### 删除用户教程（新增端点）

**`DELETE /api/learning/tutorial/{knowledge_tag}`**

- 仅删除当前用户的私有记录
- 不影响种子数据
- 删除后，用户再次访问该 knowledge_tag 会回退到种子版本

### 重置为种子版本（新增端点）

**`DELETE /api/learning/tutorial/{knowledge_tag}/reset`**

- 删除当前用户的私有记录
- 语义明确告知前端：此操作是"放弃我的修改，恢复原始版本"

## 前端变更

### LearningPath.vue 教程阅读区

- 学习教程页面顶部增加来源标识标签：
  - 🟢 `系统预置`（种子文档）
  - 🟡 `我的修改`（修改过的种子文档）
  - 🔵 `AI 生成`（用户 AI 生成的文档）

- 种子文档被用户修改后，增加"恢复原始版本"按钮

### 新增：AI 生成教程入口

- 学习路径页面 → "AI 生成教程"按钮
- 弹窗：输入主题 + 学习目标 → 调用 LLM 生成
- 生成后跳转到教程编辑/预览页

### 新增：教程编辑器（Markdown）

- 左侧编辑区（textarea / Monaco 编辑器）
- 右侧实时预览（渲染 Markdown）
- 保存按钮 → 调用 PUT API

## 构建与部署

### Docker 构建变更

`Dockerfile` 或 `docker-compose.yml` 不需要额外变更，因为：
- `build_tutorial_seed.py` 在 `init_db()` 执行前运行
- `tutorial_seed.json` 随代码复制到镜像中

### 开发环境

```bash
source backend/.venv/Scripts/activate
python backend/build_tutorial_seed.py  # 生成 seed JSON
python backend/main.py                  # 启动时 init_db() 自动导入
```

## 迁移策略

- 旧版仍从 `learning_materials/` 文件直接读取的逻辑保留作为 fallback
- `get_local_material()` 优先查数据库，无数据时回退到文件读取
- 首次运行 `init_db()` 导入种子数据后，数据库优先路径生效
- 用户无感知切换
