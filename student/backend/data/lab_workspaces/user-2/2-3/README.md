# 实现多步工具执行循环

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

create_agent 的核心是模型与工具之间的循环。本关用确定性计划模拟该循环。实现 run_tool_plan(plan, registry, max_steps=5)：plan 是按顺序执行的 {name,args} 列表；每步执行 registry[name](**args)，把 {step,name,status,observation} 写入 trace。未知工具或异常记为 error 并立即停止；超过 max_steps 的剩余计划不执行，并追加 status=stopped 的轨迹。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
