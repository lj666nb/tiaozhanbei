# 项目 8：让图学会「分叉」——条件路由与规则优先级

## 一、从「一条直线」到「多分支」

上一节的图是一条直线：`START → normalize → answer → END`。但真实业务需要根据输入内容走不同的分支：

```text
用户咨询
  ├─ 订单查询（"我的订单到哪了？"） → 查订单工具
  ├─ FAQ 问题（"退款政策是什么？"） → 知识库检索
  ├─ 普通闲聊（"你好！"）           → 直接回答
  └─ 紧急/低置信度                  → 转人工
```

这就要求图能「分叉」——根据当前状态选择不同的下一个节点。LangGraph 中这叫**条件边（Conditional Edge）**。

### 什么是条件路由？

> 🧠 **关键概念：条件路由（Conditional Routing）** 是根据当前状态决定「下一步去哪个节点」的机制。它由两部分组成：
> 1. **路由函数**——接收状态，返回下一个节点名（纯函数，不调用模型或外部服务）
> 2. **路由映射**——把函数返回值映射到实际节点名（显式声明，防拼写错误）
>
> **类比**：就像铁路道岔——火车（状态）到达道岔（条件边），扳道工（路由函数）根据目的地（状态中的字段）把铁轨扳向不同方向（返回节点名）。

### 本节目标

1. **先理解**：为什么路由函数应该是确定性代码而不是模型调用
2. **再实现**：`route_support_request` 路由函数 + `add_conditional_edges` 连接
3. **后验证**：覆盖紧急、边界置信度、未知意图、非法类型全部场景
4. **最终验收**：四条分支全部能正确路由

---

## 二、开始前：搭建本节项目

创建 `requirements.txt`、`.env.example`、`solution.py`、`app.py`，依赖 `langgraph` 和 `langchain`。

<!-- lab-check:structure -->

```bash
python -m venv .venv
pip install -r requirements.txt
```

<!-- lab-check:environment -->
<!-- lab-check:dependencies -->

---

## 三、设计路由前的思考：什么应该用代码，什么应该用模型？

> 🧠 **关键设计决策**：不是所有决策都应该交给模型。以下规则应该用**确定性代码**实现（而不是写在 prompt 里等模型判断）：
>
> | 规则类型 | 用什么实现 | 原因 |
> |---------|-----------|------|
> | 紧急请求 → 转人工 | 确定性路由函数 | 这是安全规则，不能依赖模型「自觉」遵守 |
> | 置信度 < 0.6 → 转人工 | 确定性路由函数 | 数值比较——代码比模型更可靠 |
> | 意图为 order → 订单节点 | 确定性路由函数 | 意图字段是上游节点产生的，代码直接判断即可 |
> | 「这个问题属于订单还是FAQ？」 | 模型分类 | 理解自然语言语义是模型擅长的事 |
>
> **原则**：把高风险、高确定性、数值型和枚举型的判断写成代码；把语义理解、模糊分类留给模型。

---

## 四、实现路由函数

### 4.1 原则：快速、确定、无副作用

```python
def route_support_request(state: dict) -> str:
    """根据状态中的意图、置信度和紧急标志，返回下一个节点名。
    
    路由优先级（从高到低）：
        1. 紧急请求 → 无条件转人工
        2. 置信度 < 0.6 → 转人工（模型不确定时宁可人工介入）
        3. 按意图映射 → order / faq / chat 各自对应不同节点
    
    返回：
        "human" | "order_tool" | "knowledge" | "respond"
    
    异常：
        ValueError: 缺少必填字段、置信度越界、未知意图
    """
    # 1. 校验状态完整性
    intent = state.get("intent")
    confidence = state.get("confidence")
    urgent = state.get("urgent")
    
    if not isinstance(intent, str) or not intent:
        raise ValueError("intent 必须是非空字符串")
    if not isinstance(confidence, (int, float)):
        raise ValueError("confidence 必须是数字")
    if isinstance(confidence, bool):
        raise ValueError("confidence 不能是布尔值")  # bool 是 int 的子类，必须单独排除
    if not (0 <= confidence <= 1):
        raise ValueError(f"confidence 必须在 0~1 之间，当前值: {confidence}")
    if not isinstance(urgent, bool):
        raise ValueError("urgent 必须是布尔值")
    
    # 2. 规则优先级：紧急 > 低置信度 > 意图映射
    if urgent or confidence < 0.6:
        return "human"
    
    # 3. 意图映射
    routes = {
        "order": "order_tool",
        "faq": "knowledge",
        "chat": "respond",
    }
    
    if intent not in routes:
        raise ValueError(f"未知意图: {intent}，支持: {list(routes.keys())}")
    
    return routes[intent]
```

> 🧠 **为什么 `bool` 要单独排除？** 在 Python 中，`bool` 是 `int` 的子类——`True == 1`，`False == 0`。如果调用方误传了 `confidence=True`，`isinstance(True, int)` 返回 `True`，会被当成「置信度 1.0」通过校验。这会导致路由行为异常。**防御性编程要求在类型检查时排除布尔值。**

### 4.2 规则优先级为什么重要？

```text
✅ 正确顺序（高风险优先）：
   1. 紧急或低置信度 → 人工（最高优先级）
   2. 意图映射 → 订单 / 知识库 / 闲聊

❌ 错误顺序（如果反过来）：
   1. 意图映射 → 订单
   2. 紧急或低置信度 → 人工
   → 结果：一个紧急的订单请求会先被路由到订单节点，绕过人工升级规则！
```

---

## 五、连接条件边

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(SupportState)

# 注册所有节点
builder.add_node("classify", classify_node)   # 意图识别（可调用模型）
builder.add_node("human", human_node)          # 转人工
builder.add_node("order_tool", order_node)     # 订单查询
builder.add_node("knowledge", knowledge_node)  # 知识库检索
builder.add_node("respond", respond_node)      # 直接回答

# 条件边：classify 完成后根据路由函数选择下一站
builder.add_conditional_edges(
    "classify",           # 从哪个节点之后触发路由
    route_support_request, # 路由函数（state → 节点名）
    {
        "human": "human",              # 返回值 "human" → 节点 "human"
        "order_tool": "order_tool",    # 返回值 "order_tool" → 节点 "order_tool"
        "knowledge": "knowledge",      # 返回值 "knowledge" → 节点 "knowledge"
        "respond": "respond",          # 返回值 "respond" → 节点 "respond"
    },
)

# 所有分支最终都要抵达 END
for node in ("human", "order_tool", "knowledge", "respond"):
    builder.add_edge(node, END)

builder.add_edge(START, "classify")
graph = builder.compile()
```

> 🧠 **`add_conditional_edges` 的第三个参数是路由映射表。** 它的作用是解耦路由函数的返回值与实际的节点名——路由函数返回 `"human"`（语义化的标识），映射表把它转为 `"human"`（实际注册的节点名）。这让你可以重命名节点而不必修改路由函数。

<!-- lab-check:implementation -->

---

## 六、验证用例——覆盖所有边界

好的路由函数应该能通过以下全部测试：

```python
# 正常路由
assert route_support_request({"intent": "faq", "confidence": 0.8, "urgent": False}) == "knowledge"
assert route_support_request({"intent": "order", "confidence": 0.9, "urgent": False}) == "order_tool"
assert route_support_request({"intent": "chat", "confidence": 0.7, "urgent": False}) == "respond"

# 紧急优先（即使置信度高、意图明确）
assert route_support_request({"intent": "order", "confidence": 0.99, "urgent": True}) == "human"

# 低置信度转人工
assert route_support_request({"intent": "faq", "confidence": 0.59, "urgent": False}) == "human"

# 边界值：0.6 不转人工（>= 0.6 视为可靠）
assert route_support_request({"intent": "faq", "confidence": 0.6, "urgent": False}) == "knowledge"

# 边界值：0 和 1
assert route_support_request({"intent": "chat", "confidence": 0, "urgent": False}) == "human"
assert route_support_request({"intent": "chat", "confidence": 1.0, "urgent": False}) == "respond"

# 非法输入
import pytest
with pytest.raises(ValueError):
    route_support_request({"intent": "unknown", "confidence": 0.8, "urgent": False})
with pytest.raises(ValueError):
    route_support_request({"intent": "order", "confidence": True, "urgent": False})
with pytest.raises(ValueError):
    route_support_request({"intent": "order"})  # 缺字段
```

---

## 七、在 `app.py` 中搭建完整路由图

```python
# app.py —— 条件路由客服图
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from solution import route_support_request

load_dotenv()
model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0,
)

# 模拟意图分类节点（生产环境用模型分类）
def classify_node(state):
    text = state.get("text", "")
    # 简化版：用关键词做意图识别
    if "订单" in text or "物流" in text:
        intent = "order"
    elif "退款" in text or "政策" in text or "怎么" in text:
        intent = "faq"
    else:
        intent = "chat"
    return {"intent": intent, "confidence": 0.85, "urgent": "紧急" in text}

# 各分支节点
def order_node(state): return {"answer": "订单查询结果：已发货", "trace": ["order"]}
def knowledge_node(state): return {"answer": "根据知识库：7天内可退款", "trace": ["knowledge"]}
def respond_node(state): return {"answer": "您好！有什么可以帮您？", "trace": ["respond"]}
def human_node(state): return {"answer": "已转接人工客服，请稍候。", "trace": ["human"]}

# 搭图
builder = StateGraph(dict)
builder.add_node("classify", classify_node)
builder.add_node("order_tool", order_node)
builder.add_node("knowledge", knowledge_node)
builder.add_node("respond", respond_node)
builder.add_node("human", human_node)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_support_request, {
    "human": "human", "order_tool": "order_tool",
    "knowledge": "knowledge", "respond": "respond",
})
for n in ("human", "order_tool", "knowledge", "respond"):
    builder.add_edge(n, END)

graph = builder.compile()

# 测试四类输入
for text in ["查询订单 O-100", "退款政策是什么", "你好", "紧急！我的账号被盗了"]:
    result = graph.invoke({"text": text, "trace": []})
    print(f"[{text}] → {result['trace']} → {result['answer']}")
```

<!-- lab-check:integration -->

---

## 八、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| 紧急请求被路由到业务节点 | 路由优先级错误——先处理了意图映射 | 紧急和低置信度检查放在路由函数**最前面** |
| 条件边执行后图不停止 | 分支节点后面没有连接 `END` | 确认所有分支节点都有 `add_edge(node, END)` |
| `bool` 值被当作有效置信度 | 没有排除 `bool`（它是 `int` 的子类） | 在类型检查后增加 `if isinstance(confidence, bool): raise ValueError` |
| 未知意图导致 `KeyError` | `routes[intent]` 找不到键 | 先用 `if intent not in routes: raise ValueError` 检查 |

---

## 九、动手改造

1. 在路由函数中增加一个规则：如果 `intent == "order"` 且 `confidence >= 0.95`，跳过确认直接查询（增加一个 `order_direct` 节点）
2. 为置信度边界值 `0.60` 写一个测试——确认 `>= 0.6` 不转人工（需求文档说要排除边界）
3. 把 `classify_node` 改为调用真实模型来做意图识别，比较模型分类和关键词分类的准确率差异

---

## 十、下一步

图中途可能失败——比如订单接口在 `order_node` 中超时。下一节加入**检查点（Checkpoint）**，让图能从失败的位置恢复，而不是从头开始。

<!-- lab-check:acceptance -->
