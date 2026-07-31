# 合并节点产生的状态增量

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

LangGraph 节点通常只返回自己负责更新的状态字段。实现 merge_state(current, update, reducers)：返回新状态。普通字段直接覆盖；reducers 中声明为 'append' 的字段需要把旧列表与新列表拼接。禁止修改 current/update；append 字段两侧都必须是列表，否则抛出 ValueError。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangGraph 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
