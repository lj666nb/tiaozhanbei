# 设计客服请求条件路由

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

条件边必须稳定、可测试。实现 route_support_request(state)：若 urgent=True 或 confidence<0.6，路由到 human；否则 intent=order 路由 order_tool，intent=faq 路由 knowledge，intent=chat 路由 respond。缺少字段、置信度越界、intent 未知时抛出 ValueError。注意 bool 不能被当作合法数字置信度。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangGraph 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
