# 实现线程检查点与恢复

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

LangGraph checkpointer 用 thread_id 隔离会话。实现 save_checkpoint(store, thread_id, state) 和 load_checkpoint(store, thread_id)。store 是字典：每个线程保存按 version 递增的快照列表。保存时要复制 state，返回新版本号；读取返回最新快照的新副本；不存在返回 None。thread_id 必须是非空字符串，state 必须是字典，不得发生跨线程串话。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangGraph 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
