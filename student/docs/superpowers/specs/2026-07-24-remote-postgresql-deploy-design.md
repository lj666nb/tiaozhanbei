# 远程 PostgreSQL 部署 + 本地后端 设计方案

## 日期
2026-07-24

## 目标
将数据库迁移到服务器 `113.45.66.152` 上的 PostgreSQL，后端和前端在本地 Windows 运行。

## 架构

```
用户浏览器 (localhost:5173)
      │
      ▼
Vite Dev Server (端口 5173)
  └─ /api 代理 → localhost:8000
      │
      ▼
FastAPI 后端 (端口 8000, 本地 Python 直接运行)
  └─ DATABASE_URL → 113.45.66.152:5432
      │
      ▼ TCP 直连
PostgreSQL @ 113.45.66.152:5432
  数据库: tiaozhanbei
  用户: app_user
```

## 服务器端

### 1. 安装 PostgreSQL
- 通过 SSH 连接 `root@113.45.66.152`
- 安装 PostgreSQL（Ubuntu/Debian 系）
- 启动并启用服务

### 2. 配置远程访问
- `postgresql.conf`: `listen_addresses = '*'`
- `pg_hba.conf`: 添加远程密码认证规则
- 防火墙开放端口

### 3. 创建数据库和用户
- 用户: `app_user`，密码: `123456`
- 数据库: `tiaozhanbei`，owner 为 `app_user`

### 4. 建表和种子数据
- 上传 `docs/database/merged_schema.sql`
- 执行建表（37 张表）
- 种子数据（demo 账号等由 `_seed_pg_data` 函数处理）

## 本地端

### 1. 环境变量
```
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
```

### 2. 后端启动
- 激活 venv: `source backend/.venv/Scripts/activate`
- 启动: `cd backend && python main.py`
- 端口: 8000
- `db.py` 检测到 `DATABASE_URL` 后自动使用 PostgreSQL
- `database.py` 中的 `_seed_pg_data()` 自动运行种子数据

### 3. 前端启动
- `cd frontend && npm run dev`
- 端口: 5173
- Vite 自动代理 `/api` → `localhost:8000`
- 用户访问 `http://localhost:5173`

## 端口备选
- 首选 PostgreSQL 端口: 5432
- 如 5432 不通，改为 8080（安全组已确认开放）
- 修改 `postgresql.conf` 中的 `port` 配置即可切换

## 验证
- 后端健康检查: `http://localhost:8000/api/health`
- Demo 账号登录: `demo / demo123`
- Playwright E2E 测试
