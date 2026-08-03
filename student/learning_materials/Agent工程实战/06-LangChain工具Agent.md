# 项目 6：组装第一个工具 Agent——让模型自主决定「下一步做什么」

## 一、从「手动编排」到「自主循环」

上一节我们手动处理了工具调用：判断有没有 `tool_calls` → 逐个执行 → 写回结果 → 再次调用模型。这个过程用代码写出来大概是这样的：

```python
# 上一节：手动编排（你需要控制每一步）
response = model.invoke(messages)
if response.tool_calls:
    for tc in response.tool_calls:
        result = execute_tool(tc)
        messages.append(result)
    response = model.invoke(messages)  # 再次调用模型
    # 如果模型又返回 tool_calls……还得再来一轮
```

这是可行的，但很繁琐。LangChain 提供了 `create_agent`——它把这个循环**自动化**了。

### 什么是 Agent？

> 🧠 **关键概念：在 LangChain 中，Agent 不是一个人或一个机器人。它是一个「自动循环」——模型思考 → 决定是否调用工具 → 执行工具 → 观察结果 → 再思考……直到模型认为可以给出最终回答。**
>
> ```
> 用户问题 → [模型思考] → 需要工具? → 执行工具 → [模型再思考] → 可以回答了 → 输出答案
>              ↑                                    |
>              └────────── 观察结果 ←───────────────┘
> ```
>
> 这个循环被称为 **Agent Loop（智能体循环）**，有时也叫 **ReAct 模式**（Reasoning + Acting，推理 + 行动）。`create_agent` 就是把这个循环封装好的工厂函数。

| | 手动编排（上一节） | `create_agent`（本节） |
|---|---|---|
| 循环控制 | 你写 while/for | 框架自动循环 |
| 工具调用 | 你逐个判断、执行 | 框架自动执行 |
| 停止条件 | 你手动判断 | 框架根据模型输出自动停止 |
| 执行轨迹 | 你需要自己记录 | 框架在 `result["messages"]` 中保留完整轨迹 |
| 适用场景 | 1-2 个工具的简单场景 | 多工具、需要反复调用、需要审计轨迹 |

### 本节目标

1. **先理解**：Agent 循环的四个阶段——思考、决策、执行、观察
2. **再使用**：`create_agent` 组装一个能自主查订单的客服 Agent
3. **后模拟**：实现 `run_tool_plan` 用确定性步骤模拟 Agent 循环
4. **最终验收**：多工具协作 + 完整执行轨迹

---

## 二、开始前：搭建本节项目

创建 `requirements.txt`、`.env.example`、`solution.py`、`app.py`，依赖声明同前。

<!-- lab-check:structure -->

```bash
python -m venv .venv
pip install -r requirements.txt
```

<!-- lab-check:environment -->
<!-- lab-check:dependencies -->

---

## 三、最小 Agent——不到 15 行代码

> 🧠 **前提**：你已完成项目 4（用 SQLAlchemy 构建订单数据库），`../2-1/orders.db` 已存在且包含 10 条真实订单数据。本节将直接查询这份持久化数据库，让 Agent 获取真实业务数据。

```python
from langchain.agents import create_agent
from langchain.tools import tool
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# ── 对接项目4的持久化订单数据库（orders.db） ──
Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_id = Column(String(20), unique=True, nullable=False)
    customer_name = Column(String(50), nullable=False)
    customer_phone = Column(String(20))
    product = Column(String(100), nullable=False)
    category = Column(String(30), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    carrier = Column(String(30))
    eta = Column(String(20))
    created_at = Column(String(20), nullable=False)

# 1. 定义工具：用 SQLAlchemy 查询 ../2-1/orders.db
@tool
def query_order_tool(order_id: str) -> str:
    """根据订单编号查询物流状态。订单编号形如 ORD-20260730-0001。"""
    engine = create_engine('sqlite:///../2-1/orders.db')  # ← 项目4的持久化数据库
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if order is None:
            return f"订单 {order_id} 不存在，请核对编号。"
        return (
            f"订单{order_id}：{order.status}"
            + (f"（{order.carrier}，预计{order.eta}送达）" if order.carrier else "")
        )
    finally:
        session.close()

# 2. 创建 Agent
agent = create_agent(
    model=model,
    tools=[query_order_tool],
    system_prompt="""你是订单客服。
- 涉及订单状态时必须调用 query_order_tool 查询，不要凭记忆回答；
- 工具返回 not_found 时告知用户该订单不存在，不要编造状态；
- 回答末尾给出明确的下一步建议。""",
)

# 3. 运行 Agent
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "订单 ORD-20260730-0001 到哪了？"}
    ]
})

# 4. 获取最终回答
print(result["messages"][-1].content)
```

### `create_agent` 的每个参数做什么？

| 参数 | 作用 | 工程注意点 |
|------|------|-----------|
| `model=` | 负责推理和决策的聊天模型 | 模型必须支持 tool calling；DeepSeek 和 OpenAI 都支持 |
| `tools=` | 本次 Agent 可调用的工具列表 | **最小权限原则**：不要为了方便把所有工具都暴露给一个 Agent |
| `system_prompt=` | 约束角色、工具使用条件、失败策略 | 应写清三件事：何时必须调用、何时不得猜测、失败后如何降级 |

### `result["messages"]` 里有什么？

> 🧠 **`agent.invoke()` 返回的不是一句话，而是完整的执行轨迹。** `result["messages"]` 是一个消息列表，里面可能包含：
> - `HumanMessage`（用户输入）
> - `AIMessage`（模型思考或回答，可能带 `tool_calls`）
> - `ToolMessage`（工具执行结果）
> - `AIMessage`（模型读取结果后的最终回答）
>
> 只取 `result["messages"][-1].content` 适合展示给用户，但**排障和审计时应保留完整轨迹**——它能告诉你模型在第几步调了什么工具、返回了什么结果、为什么最终这样回答。

---

## 四、Agent 循环的四个阶段

用上一节的订单查询为例，Agent 内部发生了什么：

```text
阶段1 → 模型收到用户消息 "订单 ORD-20260730-0001 到哪了？"
阶段2 → 模型判断：这需要真实订单数据，我用不了……但我有 query_order_tool！
         生成 tool_call: {"name": "query_order_tool", "args": {"order_id": "ORD-20260730-0001"}}
阶段3 → 框架自动执行 query_order_tool("ORD-20260730-0001")，返回 "已发货（顺丰，预计7月30日送达）"
         框架自动把工具结果作为 ToolMessage 追加到消息历史
阶段4 → 模型看到工具结果，生成最终回答："您的订单 ORD-20260730-0001 已通过顺丰发货，预计7月30日送达。
         如需进一步帮助，请随时联系我。"
```

> 🧠 **停止条件**：Agent 什么时候停止？当模型决定不再调用工具，而是直接生成文本回答时——这就表示循环结束了。为了防止死循环（模型反复调用工具），`create_agent` 有默认的最大迭代限制。

---

## 五、增加第二个工具——观察 Agent 如何选择

```python
@tool
def refund_policy(product_type: str) -> str:
    """查询指定商品类型的退款政策。product_type 可以是 'digital'（数字商品）或 'physical'（实体商品）。"""
    policies = {
        "digital": "数字商品（软件、课程等）激活后不支持退款。",
        "physical": "实体商品签收后7天内可申请退款，需保持商品完好。",
    }
    return policies.get(product_type, "未找到该商品类型的退款政策，需要人工确认。")

# 把两个工具都传给 Agent
agent = create_agent(
    model=model,
    tools=[query_order_tool, refund_policy],  # ← 两个工具
    system_prompt="你是订单客服。涉及订单状态用 query_order_tool，涉及退款政策用 refund_policy。",
)
```

测试 Agent 的工具选择能力：

```python
# 场景1：只涉及订单
result = agent.invoke({"messages": [{"role": "user", "content": "订单 ORD-20260730-0001 到哪了？"}]})
# Agent 应该只调用 query_order_tool

# 场景2：涉及退款政策
result = agent.invoke({"messages": [{"role": "user", "content": "我买的软件可以退款吗？"}]})
# Agent 应该只调用 refund_policy

# 场景3：同时涉及两个工具
result = agent.invoke({"messages": [{"role": "user", "content": "订单 ORD-20260730-0004 是实体商品，状态和退款规则分别是什么？"}]})
# Agent 可能依次调用两个工具（取决于模型判断）
```

---

## 六、实现 `run_tool_plan`——用确定性步骤理解 Agent 循环

在实验室中，`run_tool_plan` 是一个**确定性模拟**：不依赖模型，用预先定义的步骤计划来模拟 Agent 循环。这让你先理解循环的控制逻辑，再回看 `create_agent` 替你做了什么。

```python
# solution.py —— 确定性工具计划执行器
def run_tool_plan(plan, registry, max_steps=5):
    """按确定性计划执行多步工具调用，记录完整轨迹。
    
    参数：
        plan (list): 按顺序执行的步骤，每项为 {"name": str, "args": dict}
        registry (dict): 工具注册表 {"name": callable}
        max_steps (int): 最大执行步数（防止无限执行）
    
    返回：
        dict: {"status": "completed"|"failed"|"stopped",
               "trace": [{"step": 1, "name": ..., "status": ..., "observation": ...}, ...],
               "final_observation": 最后一次有效观察或 None}
    
    设计要点：
        - 步号从 1 开始
        - 未知工具或执行异常 → status="error" 并立即停止
        - 超过 max_steps 的剩余步骤不执行，追加 status="stopped" 的轨迹
        - 每步都写入 trace，不吞掉任何信息
    """
    # 1. 参数校验
    if not isinstance(plan, list):
        raise ValueError("plan 必须是列表")
    if not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("max_steps 必须是正整数")
    
    trace = []
    final_observation = None
    
    for i, step in enumerate(plan):
        step_num = i + 1
        
        # 2. 检查步数上限
        if step_num > max_steps:
            trace.append({
                "step": step_num,
                "name": step.get("name", "unknown"),
                "status": "stopped",
                "observation": f"达到最大步数限制 ({max_steps})，剩余步骤不执行",
            })
            return {"status": "stopped", "trace": trace, "final_observation": final_observation}
        
        name = step.get("name")
        args = step.get("args", {})
        
        # 3. 查找工具
        if name not in registry:
            trace.append({
                "step": step_num,
                "name": name,
                "status": "error",
                "observation": f"未知工具: {name}",
            })
            return {"status": "failed", "trace": trace, "final_observation": final_observation}
        
        # 4. 执行工具
        try:
            result = registry[name](**args)
            observation = str(result)
            trace.append({
                "step": step_num,
                "name": name,
                "status": "success",
                "observation": observation,
            })
            final_observation = observation
        except Exception as exc:
            trace.append({
                "step": step_num,
                "name": name,
                "status": "error",
                "observation": f"工具执行异常: {exc}",
            })
            return {"status": "failed", "trace": trace, "final_observation": final_observation}
    
    return {"status": "completed", "trace": trace, "final_observation": final_observation}
```

> 🧠 **为什么 trace 从 1 开始计数？** 这是为了和人类的思维方式一致——「第一步做什么、第二步做什么」。程序内部可以用 `trace[0]`，但日志、报告和调试时 `step: 1` 比 `step: 0` 更直观。

<!-- lab-check:implementation -->

---

## 七、重构 `app.py`——从手动编排到 Agent

```python
# app.py —— Agent 版：工具直接对接项目4的 orders.db
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from solution import run_tool_plan

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0,
)

# ── 对接项目4的持久化订单数据库 ──
Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_id = Column(String(20), unique=True, nullable=False)
    customer_name = Column(String(50), nullable=False)
    customer_phone = Column(String(20))
    product = Column(String(100), nullable=False)
    category = Column(String(30), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    carrier = Column(String(30))
    eta = Column(String(20))
    created_at = Column(String(20), nullable=False)

def query_order(order_id: str) -> dict:
    """从项目4的 orders.db 查询订单。"""
    engine = create_engine('sqlite:///../2-1/orders.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if order is None:
            return {"status": "not_found", "message": f"订单 {order_id} 不存在"}
        return {
            "status": order.status, "carrier": order.carrier or "暂无",
            "eta": order.eta or "暂无", "customer_name": order.customer_name,
            "product": order.product,
        }
    finally:
        session.close()

@tool
def query_order_tool(order_id: str) -> str:
    """根据订单编号查询物流状态。订单编号形如 ORD-20260730-0001。"""
    result = query_order(order_id)
    if result.get("status") == "not_found":
        return f"订单 {order_id} 不存在，请核对编号。"
    return f"{result['status']}（{result['carrier']}，预计{result['eta']}送达）"

@tool
def refund_policy(product_type: str) -> str:
    """查询退款政策。product_type 为 'digital' 或 'physical'。"""
    policies = {"digital": "数字商品（课程、软件等）激活后不支持退款。", "physical": "实体商品签收后7天内可申请退款，需保持商品完好。"}
    return policies.get(product_type, "未找到该商品类型的退款政策，需要人工确认。")

agent = create_agent(
    model=model,
    tools=[query_order_tool, refund_policy],
    system_prompt="你是电商客服。涉及真实订单数据时必须调用工具，不要编造。失败时告知用户并建议转人工。",
)

# 测试：需要工具的问题
result = agent.invoke({"messages": [{"role": "user", "content": "订单 ORD-20260730-0001 的状态？"}]})
print("需要工具:", result["messages"][-1].content)

# 测试：不需要工具的问题
result = agent.invoke({"messages": [{"role": "user", "content": "你好，请问你们几点下班？"}]})
print("不需要工具:", result["messages"][-1].content)
```

<!-- lab-check:integration -->

---

## 八、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| Agent 不调用工具直接回答 | system_prompt 没规定「何时必须调用工具」；或问题不需要工具就能回答 | 在 prompt 中明确写「涉及订单状态时必须调用 query_order_tool」 |
| Agent 反复调用同一个工具 | 工具返回的结果不够清晰，模型不确定是否已拿到答案 | 让工具返回确定性语句（如「查询结果：已发货」而非模糊表述） |
| Agent 调用后不再回答 | 工具结果没有正确写回 messages——模型收不到反馈 | 检查 `create_agent` 的 messages 轨迹中是否有 ToolMessage |
| 两个工具描述太相似，模型选错 | docstring 不够具体，模型无法区分使用场景 | 让每个工具的 docstring 包含典型使用场景和参数示例 |
| 循环超限（达到最大步数） | 模型在反复问同一个问题或工具返回了非确定性结果 | 增加 system_prompt 中的停止条件描述 |

---

## 九、动手改造

1. 新增一个 `check_inventory` 工具（查询库存），让 Agent 在三个工具中做选择
2. 在 system_prompt 中加入错误时降级规则：「如果工具连续失败 2 次，告知用户并建议转人工」
3. 用 `result["messages"]` 打印完整执行轨迹，追踪每一步的工具调用和结果

---

## 十、下一步

`create_agent` 适合简单的工具循环。但当业务需要**明确的分支逻辑**（如「紧急请求→人工」「FAQ→知识库」「订单→查工具」），我们需要自己设计图的拓扑结构。下一阶段将使用 LangGraph 的 `StateGraph` 来精确控制每一步的流向。

[LangChain 官方 Agent 文档](https://docs.langchain.com/oss/python/langchain/agents)

<!-- lab-check:acceptance -->
