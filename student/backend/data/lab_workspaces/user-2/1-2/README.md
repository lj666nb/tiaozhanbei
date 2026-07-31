# 维护并裁剪多轮上下文

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

多轮聊天要把本轮 user/assistant 消息追加到历史中，但不能无限增长。实现 append_turn_and_trim(history, user_text, assistant_text, max_messages)：返回新列表，绝不能修改 history；始终保留开头的 system 消息（如果存在），并从旧到新保留最多 max_messages 条消息。max_messages 必须是大于等于 2 的整数。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
