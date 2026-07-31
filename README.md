# Edu-TA 智教星 — 师生协同学习平台

```
edu-platform/
├── portal/           # 🌐 统一入口页 (双击 index.html)
├── teacher/          # 👨‍🏫 教师端 (Edu-TA 智教星)
│   ├── frontend/     #    React + Ant Design (端口 5173)
│   ├── backend/      #    Python FastAPI (端口 8000)
│   └── ...
├── student/          # 🎓 学生端 (智学引擎)
│   ├── frontend/     #    Vue 3 + Element Plus (端口 5174)
│   ├── backend/      #    Python FastAPI
│   └── ...
└── README.md
```

## 快速开始

### 入口
双击 `portal/index.html` 选择教师端或学生端。

### 启动
```bash
# 1. 教师端后端 (端口 8000，含师生通信 API)
cd teacher/backend
uvicorn app.main:app --port 8000 --reload

# 2. 教师端前端 (端口 5173)
cd teacher/frontend && npm run dev

# 3. 学生端后端
cd student/backend
uvicorn main:app --port 8001 --reload

# 4. 学生端前端 (端口 5174)
cd student/frontend && npm run dev -- --port 5174
```

## 师生通信

- **教师端**: 侧边栏「师生通信」→ 新建会话 → 发送消息
- **学生端**: 侧边栏「师生通信」→ 新建会话 → 发送消息
- **实时推送**: SSE，新消息即时送达
- **数据库**: 共享 PostgreSQL `tiaozhanbei`
