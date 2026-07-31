# 校验并执行工具调用

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

Agent 不能直接相信模型生成的工具调用。实现 execute_tool_call(tool_call, registry)：tool_call 必须包含字符串 name、字典 args 和字符串 id；registry 中每个工具用 {required:[...], handler: callable} 描述。拒绝未知工具与缺少参数；执行成功后返回统一 ToolMessage 风格字典。handler 的异常要转成 status=error 的结果，不能让整个 Agent 崩溃。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
