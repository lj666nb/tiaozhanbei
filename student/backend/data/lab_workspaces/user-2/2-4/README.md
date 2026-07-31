# 用 SQLAlchemy 构建订单数据库

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

工具 Agent 需要真实数据源。实现 setup_order_db(db_path) 和 query_orders(session, **filters)。用 SQLAlchemy ORM 定义 Order 模型（id, customer_name, product, amount, status），创建 SQLite 引擎和 Session，支持按 status / customer_name / min_amount 组合过滤，返回字段完整的字典列表。非法参数抛出 ValueError。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain + SQLAlchemy 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
