# CLAUDE.md

## 项目概述
AI智能体学科学习平台 — 专注于AI智能体单一学科的个性化、伴随式、智能化学习平台。

## 技术栈
- 前端：Vue3 + Vite + Element Plus + ECharts（端口 80 via Docker / 5173 本地开发）
- 后端：Python FastAPI + PostgreSQL（远程服务器）（端口 8000 via Docker / 8000 本地开发）
- AI：DeepSeek API
- 容器化：Docker Compose

## ⚡ 代码修改后自动部署（必须执行）

**每次修改代码后，必须自动执行以下命令让用户看到效果：**
```bash
docker compose up -d --build
```
- 原因：Docker 前端是 `npm run build` → nginx 静态构建，后端是 Python 源码复制。源码修改必须重建镜像才能生效。
- 用户访问 `http://localhost:80` 看到的是 Docker 版本的代码，不是本地 dev server。

## 🧪 代码修改后自动测试（必须执行）

**每次代码修改并部署后，必须自动使用 Playwright MCP 进行端到端测试，无需用户反复要求。**
- 使用 Playwright MCP 浏览器工具（`mcp__playwright__*`）进行测试
- 测试范围应覆盖本次修改涉及的所有功能点
- 测试流程：
  1. `docker compose up -d --build` 部署完成后等待 ~15s 让容器初始化
  2. 导航到 `http://localhost:80`，使用 demo 账号登录（demo / demo123）
  3. 针对本次修改的功能逐一验证
  4. 检查浏览器控制台是否有 JavaScript 错误
  5. 报告测试结果（通过/失败/控制台错误）

## 启动方式（必须优先使用 Docker）

### 方式一：Docker 一键启动（推荐，始终优先使用）
```bash
docker compose up -d --build
```
- 前端: http://localhost:80
- 后端: http://localhost:8001 （注意 Docker 映射到 8001）
- API 文档: http://localhost:8001/docs

### 方式二：本地开发（仅在 Docker 不可用时使用）

**激活虚拟环境（必须）：**
```bash
# Windows Git Bash:
source backend/.venv/Scripts/activate
# 或 Windows CMD:
backend\.venv\Scripts\activate.bat

# 安装依赖：
pip install -r backend/requirements.txt

# 启动后端：
cd backend && python main.py
```
前端：
```bash
cd frontend && npm install && npm run dev
```

## RAG 知识库引擎

### 嵌入模型（云端 API）

| 后端 | 模型 | 维度 | 使用场景 |
|------|------|:---:|------|
| SiliconFlow | `BAAI/bge-large-zh-v1.5` | 1024 | 生产环境（推荐） |
| 阿里云 DashScope | `text-embedding-v3` | 1024 | 备用（需用户配置 API Key） |

- 所有嵌入均通过云端 API 调用，无需本地 GPU
- Docker 默认使用 SiliconFlow（`EMBEDDING_RUNTIME_MODE=siliconflow`）
- 用户可在「个人中心 → AI大模型配置」中配置嵌入 API Key

### 当前向量库状态
- 集合：`rag_docs_cached-bge-large-zh-v1.5`（SiliconFlow）/ `rag_docs_cached-dashscope-text-embedding-v3`（DashScope 历史）
- 存储：`backend/data/chroma_db/`
- 总计 4887 个文档块：PDF 2402 + Markdown 1885 + Q&A 600

### 虚拟环境
- 路径：`backend/.venv/`（Python 3.11.6）
- 核心 RAG 依赖：`chromadb`, `dashscope`, `openai`
- 所有 Python 操作必须在激活虚拟环境后执行

### RAG 一键构建
```bash
# 激活 venv
source backend/.venv/Scripts/activate

# DashScope 云端模式（需用户自行申请 API Key）
python backend/rag_builder.py --api-key <你的DashScope_API_Key>

# SiliconFlow 云端模式（推荐）
python backend/rag_builder.py --provider siliconflow --api-key <你的SiliconFlow_API_Key>
```
构建后：
- QA 页面提问自动触发 RAG 检索（前提：用户已在个人中心配置嵌入 API Key）
- 未配置时 QA 正常回答，但无知识库增强，并提示用户配置 text-embedding-v3 API Key
- 回答下方展示 📚 参考来源（PDF 页码 / Markdown 章节 / 题库知识点）
- API: `GET /api/rag/status`, `POST /api/rag/search?q=xxx`

### ⚠️ API Key 使用规则（极其重要 — 违反将导致 Key 泄露和账单损失）

**🚫 禁止事项：**
- **绝对禁止将任何真实 API Key 直接写入代码文件**（包括 .py / .js / .vue / .json / .yml / .env）
- 绝不使用硬编码的默认 Key 来兜底——未配置 = 不可用，清晰提示即可
- 测试用的 Key 只能通过浏览器 UI 输入（Playwright），不能写入任何源代码

**✅ 正确做法：**
- 所有 API Key 必须由用户通过前端界面自行输入配置
- 未配置 → 功能不可用 → 显示明确指引（如「请在个人中心配置 xxx API Key」）
- LLM 对话 Key：`个人中心 → DeepSeek 快速配置` 中填写
- 嵌入 Key：`个人中心 → 知识库嵌入 API Key 快速配置` 中填写 DashScope text-embedding-v3
- 本地测试：通过 Playwright 在浏览器中输入 Key，或使用环境变量（不提交）

### RAG 数据源
| 数据源 | 数量 | 路径 |
|--------|:---:|------|
| AI Agent 中文教材 PDF | 7 本 | `pdf/` |
| Markdown 学习材料 | 81 篇 | `learning_materials/` |
| Q&A 题库 | ~600 条 | `backend/data/dataset/` |

### 参考项目
- SuperMew（agentic RAG）：`F:/code/MyPython/SuperMew-main/`
  - 三层分块 + 自动合并、混合检索 + RRF 融合、LangGraph agentic RAG pipeline
  - 查询扩展（Step-back + HyDE）、Jina Reranker 精排

## 数据库

### 生产环境：PostgreSQL（远程服务器）
- **Docker 容器内自动使用远程 PostgreSQL**，通过 `DATABASE_URL` 环境变量配置
- 连接地址：通过本机 `.env` 的 `DATABASE_URL` 注入，文档和源码中不得保存真实凭据。
- 本地 SQLite 仅在不设置 `DATABASE_URL` 时作为回退（`backend/db.py` 自动检测）
- **本地 SQLite 已被弃用**，所有数据操作应针对 PostgreSQL

### 数据库运维
- 查询/修改数据：通过 Docker 容器执行 Python 脚本连接 PostgreSQL
  ```bash
  docker exec ai-learning-backend python -c "
  import psycopg2, os
  conn = psycopg2.connect(os.environ['DATABASE_URL'])
  # 执行 SQL ...
  conn.close()
  "
  ```
- `docker compose down` 不会影响远程 PostgreSQL 数据
- 本地 volume `backend_data` 仅用于临时缓存文件

## 重要注意事项
- `backend/docker-entrypoint.sh` 必须是 **LF** 行尾符（不是 CRLF），否则容器启动报 `Illegal option -`
- Demo 账号：`demo` / `demo123`
- Docker Compose 将后端端口映射为 `127.0.0.1:8001:8000`
- Docker 构建镜像体积大（含 Python 依赖），修改代码后必须 rebuild
- **修改数据库配置（如模型名称）必须操作远程 PostgreSQL，不能改本地 SQLite**
