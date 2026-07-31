# 构造第一组对话消息

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

先跑通再重构：在 app.py 中直接调用 ChatOpenAI 模型、看到 AI 回复后，再把消息构造逻辑提取为 build_chat_messages(system_prompt, user_input) 函数并添加输入校验。返回两个字典组成的列表（role=system 和 role=user），content 为清理空白后的文本；非法输入抛出 ValueError；不得修改传入值。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
