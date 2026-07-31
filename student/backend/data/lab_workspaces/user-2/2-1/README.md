# 渲染可复用客服提示模板

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

提示模板应把稳定业务规则与动态输入分开。实现 render_support_prompt(template, values)：template 使用 {name} 占位符；values 必须提供全部字段，额外字段允许存在；值统一转为字符串。缺字段、模板不是非空字符串或 values 不是字典时抛出 ValueError。禁止使用 eval。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
