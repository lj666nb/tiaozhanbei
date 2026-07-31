# 毕业项目：端到端智能客服 Agent

## 一、我们走到了哪里

回顾过去 11 节，你掌握了：

| 章节 | 学到的能力 | 在本项目中的角色 |
|------|-----------|----------------|
| 1 | LLM 调用 + 消息协议 + 工程重构 | 与模型交互的基础 |
| 2 | 多轮对话 + 上下文裁剪 | 维护对话状态 |
| 3 | 流式输出 + 健壮错误处理 | 用户体验与稳定性 |
| 4 | 提示模板 + LCEL 管道 | 可复用的业务规则 |
| 5 | 工具调用 + 校验边界 | 连接外部业务系统 |
| 6 | Agent 循环 + 执行轨迹 | 自主决策与可审计性 |
| 7 | StateGraph + 状态管理 | 显式的控制流 |
| 8 | 条件路由 + 规则优先级 | 多分支决策 |
| 9 | 检查点 + 线程隔离 | 跨调用状态与故障恢复 |
| 10 | RAG 检索 + Top-K 排序 | 从知识库中查找证据 |
| 11 | 有依据回答 + 降级 | 可追溯答案与安全兜底 |

现在，我们要把这些全部整合到一个项目中。

### 什么是「端到端」？

> 🧠 **端到端（End-to-End）** 意味着从用户输入到系统输出，整个链路都由你的代码完成——不需要人工在中间插手（除非降级到人工节点）。对于一个客服 Agent，端到端链路是：
>
> ```text
> 请求校验 → 意图识别 → 风险路由 → 业务处理 → 结果整合 → 返回用户
>    ↑                                                    ↓
>    └── 全过程写入 trace（可审计）──────────────────────────┘
> ```
>
> 每一层都可能失败（校验不通过、检索无结果、工具超时……），而好的端到端设计能**在任何一层优雅降级**，不让整个系统崩溃。

### 本节目标

1. **先回顾**：前 11 节的技术如何在本项目中组合
2. **再设计**：统一状态结构、统一返回契约、统一错误处理
3. **后实现**：`handle_support_turn`——单函数实现完整的客服处理链路
4. **最终验收**：8 条测试场景 + 三层能力验证（代码测试、原理答辩、故障修复）

---

## 二、开始前：搭建毕业项目工作区

创建 `requirements.txt`、`.env.example`、`solution.py`、`app.py`。依赖为：

```text
langchain
langgraph
python-dotenv
```

<!-- lab-check:structure -->

```bash
python -m venv .venv
pip install -r requirements.txt
```

<!-- lab-check:environment -->
<!-- lab-check:dependencies -->

---

## 三、先设计架构——想清楚再写代码

### 3.1 推荐目录结构

代码多了以后，把所有逻辑塞进一个文件会很难维护。推荐按**关注点分离**的原则组织：

```text
support-agent/
├── app.py              ← 主入口：搭图、编译、运行
├── graph.py            ← 图结构定义（节点和边的连接）
├── state.py            ← 状态 Schema 定义
├── nodes/
│   ├── validate.py     ← 请求校验节点
│   ├── classify.py     ← 意图识别节点
│   ├── order.py        ← 订单查询节点
│   ├── knowledge.py    ← 知识检索节点
│   └── human.py        ← 人工降级节点
├── tools/
│   └── order.py        ← 订单业务函数（纯业务逻辑，不依赖 AI 框架）
├── retrieval/
│   └── store.py        ← 知识库和检索函数
└── tests/
    ├── test_routes.py      ← 路由函数单元测试
    ├── test_tools.py       ← 工具函数单元测试
    └── test_end_to_end.py  ← 端到端集成测试
```

> 🧠 **为什么要把 nodes、tools、retrieval 分开？** 这是「关注点分离」原则——每个模块只做一件事。`tools/order.py` 只关心如何查订单，不关心模型是怎么调用它的。`nodes/validate.py` 只关心输入校验，不关心校验通过后去哪。以后换一个模型、换一个数据库、换一个检索方式，只需要替换对应的模块。

### 3.2 统一状态结构——全图共享的数据契约

```python
# state.py
from typing import TypedDict

class SupportState(TypedDict, total=False):
    # 请求信息
    request_id: str          # 请求唯一标识（用于日志关联）
    text: str                # 用户原始输入
    intent: str              # 意图分类结果
    confidence: float        # 分类置信度
    urgent: bool             # 是否紧急
    
    # 业务数据
    order_id: str            # 订单编号
    query_terms: list[str]   # 检索查询词
    evidence: list[dict]     # 检索结果
    
    # 输出
    answer: str              # 最终回答
    citations: list[str]     # 引用来源 ID
    needs_human: bool        # 是否需要转人工
    
    # 审计
    trace: list[str]         # 执行轨迹（经过的节点名）
```

### 3.3 统一返回契约——所有分支返回相同结构

> 🧠 **为什么必须统一返回结构？** 图中有 4 条分支（订单、FAQ、闲聊、人工），但最终都要输出给用户。如果各分支返回的字段不同——比如订单分支有 `order_status` 而 FAQ 分支有 `doc_id`——调用方需要写 4 套不同的解析逻辑。统一返回 `{answer, citations, needs_human, trace}` 后，调用方只需要处理一种结构。

---

## 四、实现 `handle_support_turn`——端到端入口

在实验室中，`handle_support_turn` 是你要独立实现的端到端函数。它不依赖 LangGraph（先理解业务逻辑，再用图来组织）：

```python
# solution.py —— 端到端客服处理
def handle_support_turn(request, order_db, documents):
    """处理一轮客服请求，返回可审计的完整结果。
    
    参数：
        request (dict): 用户请求，含 id、text、intent、confidence、urgent
        order_db (dict): 订单数据库 {order_id: {status, ...}}
        documents (list[dict]): 知识库文档列表
    
    返回：
        dict: {
            "request_id": str,     # 请求 ID（来自 request）
            "route": str,          # 实际走的分支（human/order/knowledge/respond）
            "answer": str,         # 回答正文
            "citations": list[str],# 引用来源（仅 knowledge 分支有值）
            "trace": list[str],    # 执行轨迹（始终包含 validate、route，再追加业务节点）
        }
    
    业务规则：
        1. 紧急或低置信度 → 转人工（最高优先级）
        2. intent=order → 查订单数据库
        3. intent=faq → 检索知识库文档
        4. intent=chat → 固定欢迎语
        5. 所有分支都不能修改输入的 request、order_db、documents
    """
    # === 阶段1：校验（validate） ===
    request_id = request.get("id")
    text = request.get("text")
    intent = request.get("intent")
    confidence = request.get("confidence")
    urgent = request.get("urgent")
    
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request.id 必须是非空字符串")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("request.text 必须是非空字符串")
    if not isinstance(intent, str) or not intent:
        raise ValueError("request.intent 必须是非空字符串")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("request.confidence 必须是数字（非布尔）")
    if not (0 <= confidence <= 1):
        raise ValueError("request.confidence 必须在 0~1 之间")
    if not isinstance(urgent, bool):
        raise ValueError("request.urgent 必须是布尔值")
    
    trace = ["validate", "route"]
    
    # === 阶段2：路由（route） ===
    # 优先级：紧急 > 低置信度 > 意图
    if urgent or confidence < 0.6:
        return {
            "request_id": request_id,
            "route": "human",
            "answer": "您的请求已转接人工客服，请稍候。",
            "citations": [],
            "trace": trace + ["human"],
        }
    
    # === 阶段3：业务处理 ===
    if intent == "order":
        # 订单分支：查数据库
        order_id = text  # 简化：假设用户输入就是订单号
        if order_id in order_db:
            status = order_db[order_id].get("status", "未知状态")
            return {
                "request_id": request_id,
                "route": "order",
                "answer": f"订单 {order_id} 的状态：{status}。",
                "citations": [],
                "trace": trace + ["order"],
            }
        else:
            # 无此订单 → 转人工
            return {
                "request_id": request_id,
                "route": "order",
                "answer": f"未找到订单 {order_id}，已为您转接人工。",
                "citations": [],
                "trace": trace + ["order", "human"],
            }
    
    elif intent == "faq":
        # FAQ 分支：检索知识库
        # 简化检索：查找 text 中是否包含文档的任一关键词
        matched = []
        for doc in documents:
            terms = doc.get("terms", [])
            if any(term in text for term in terms):
                matched.append(doc)
        
        if matched:
            top = matched[:3]
            return {
                "request_id": request_id,
                "route": "knowledge",
                "answer": f"根据资料：{'；'.join(d['text'] for d in top)}",
                "citations": [d["id"] for d in top],
                "trace": trace + ["knowledge"],
            }
        else:
            # 无匹配 → 转人工
            return {
                "request_id": request_id,
                "route": "knowledge",
                "answer": "暂未找到可靠依据，已为您转接人工客服。",
                "citations": [],
                "trace": trace + ["knowledge", "human"],
            }
    
    elif intent == "chat":
        # 闲聊分支：固定欢迎语
        return {
            "request_id": request_id,
            "route": "respond",
            "answer": "您好！我是智能客服，可以帮您查询订单、解答退款政策。请问有什么可以帮您？",
            "citations": [],
            "trace": trace + ["respond"],
        }
    
    else:
        raise ValueError(f"未知意图: {intent}")
```

> 🧠 **五个工程规则在本函数中的体现**：
> 1. **门禁校验**：所有参数在阶段 1 就检查完毕——非法输入不消耗任何业务逻辑
> 2. **规则优先级**：紧急和低置信度在路由的最前面——不会被后续分支绕过
> 3. **安全降级**：查不到订单、搜不到文档 → 转人工，不编造
> 4. **审计轨迹**：每条分支都完整记录 trace——出问题时能精确知道走了哪条路径
> 5. **不可变数据**：`request`、`order_db`、`documents` 都只读取不修改

<!-- lab-check:implementation -->

---

## 五、在 LangGraph 中编排图

```python
# app.py —— 端到端客服 Agent 图
from langgraph.graph import StateGraph, START, END
from solution import handle_support_turn, route_support_request

# 定义各节点（每个节点只做一件事）
def validate_node(state):
    request = {
        "id": state["request_id"],
        "text": state["text"],
        "intent": state["intent"],
        "confidence": state["confidence"],
        "urgent": state["urgent"],
    }
    # 校验在节点内部完成——非法输入直接抛异常
    return {"trace": ["validate"]}

def classify_node(state):
    # 生产环境：调用模型做意图分类
    # 简化版：直接使用 request 中的 intent
    return {}

def order_node(state):
    result = handle_support_turn(
        request={"id": state["request_id"], "text": state["text"],
                 "intent": "order", "confidence": state["confidence"], "urgent": state["urgent"]},
        order_db=ORDER_DB,
        documents=DOCUMENTS,
    )
    return result

# ... 其他节点类似

# 搭图
builder = StateGraph(SupportState)
builder.add_node("validate", validate_node)
builder.add_node("classify", classify_node)
builder.add_node("order", order_node)
builder.add_node("knowledge", knowledge_node)
builder.add_node("respond", respond_node)
builder.add_node("human", human_node)
builder.add_node("finalize", finalize_node)

builder.add_edge(START, "validate")
builder.add_edge("validate", "classify")
builder.add_conditional_edges("classify", route_support_request, {
    "human": "human", "order_tool": "order",
    "knowledge": "knowledge", "respond": "respond",
})
for node in ("order", "knowledge", "respond", "human"):
    builder.add_edge(node, "finalize")
builder.add_edge("finalize", END)

# 编译时加入 checkpointer（支持多轮对话）
from langgraph.checkpoint.memory import InMemorySaver
graph = builder.compile(checkpointer=InMemorySaver())
```

<!-- lab-check:integration -->

---

## 六、端到端测试清单——8 条场景全覆盖

```python
# 测试数据
ORDER_DB = {
    "O-100": {"status": "已发货"},
    "O-200": {"status": "退款审核中"},
}
DOCUMENTS = [
    {"id": "refund-1", "text": "实体商品签收后7天内可申请退款", "terms": ["退款", "实体"]},
    {"id": "refund-2", "text": "退款审核需1个工作日", "terms": ["退款", "审核"]},
]

# 测试1：紧急请求转人工
result = handle_support_turn(
    {"id": "r1", "text": "账号被盗", "intent": "chat", "confidence": 0.95, "urgent": True},
    ORDER_DB, DOCUMENTS)
assert result["route"] == "human"

# 测试2：边界置信度 0.59 vs 0.60
r_low = handle_support_turn(
    {"id": "r2", "text": "退款", "intent": "faq", "confidence": 0.59, "urgent": False},
    ORDER_DB, DOCUMENTS)
r_ok = handle_support_turn(
    {"id": "r3", "text": "退款", "intent": "faq", "confidence": 0.60, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert r_low["route"] == "human"
assert r_ok["route"] == "knowledge"

# 测试3：存在的订单
result = handle_support_turn(
    {"id": "r4", "text": "O-100", "intent": "order", "confidence": 0.9, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert result["route"] == "order"
assert "已发货" in result["answer"]

# 测试4：不存在的订单
result = handle_support_turn(
    {"id": "r5", "text": "O-999", "intent": "order", "confidence": 0.9, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert "未找到" in result["answer"]

# 测试5：FAQ 有证据
result = handle_support_turn(
    {"id": "r6", "text": "退款政策", "intent": "faq", "confidence": 0.9, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert len(result["citations"]) > 0

# 测试6：FAQ 无证据
result = handle_support_turn(
    {"id": "r7", "text": "天气", "intent": "faq", "confidence": 0.9, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert result["citations"] == []
assert "转接人工" in result["answer"]

# 测试7：闲聊
result = handle_support_turn(
    {"id": "r8", "text": "你好", "intent": "chat", "confidence": 0.9, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert result["route"] == "respond"

# 测试8：输入不可变
original_db = dict(ORDER_DB)
handle_support_turn(
    {"id": "r9", "text": "O-100", "intent": "order", "confidence": 0.9, "urgent": False},
    ORDER_DB, DOCUMENTS)
assert ORDER_DB == original_db  # 数据库未被修改
```

---

## 七、编程实验 4-3——三层能力验证

平台对毕业项目的验收分为三层：

| 层次 | 验证内容 | 通过标准 |
|------|---------|---------|
| **1. 代码测试** | 服务端用私有业务场景运行你的 `handle_support_turn` | 8 类场景全部通过 |
| **2. 原理答辩** | AI 针对你的代码提问（如「为什么紧急检查放在最前面？」） | 正确解释设计决策 |
| **3. 故障修复** | 系统向你的代码注入一个真实 Bug（如裁剪逻辑错误） | 定位并修复，重新通过测试 |

> 🧠 **代码测试通过只是入场券。能够解释规则优先级、发现被改坏的边界并修复，才表示具备了复杂工程场景的能力。**

---

## 八、完成后的扩展方向

毕业项目不是终点。以下方向可以让这个 Agent 更接近生产级：

1. **真实 API 替换**：把内存 `ORDER_DB` 替换为真实的 HTTP API 调用，增加超时和重试
2. **向量检索升级**：把词项匹配替换为 embedding + 向量数据库（ChromaDB / Milvus）
3. **持久化检查点**：把 `InMemorySaver` 替换为 `SqliteSaver` 或 `PostgresSaver`
4. **权限与安全**：在 validate 节点加入用户鉴权，根据权限限制可查询的订单范围
5. **观测与监控**：用 LangSmith 或自定义日志记录每次调用的延迟、成功率和降级率
6. **评估集**：建立一组标准问答对，每次修改后自动运行评估，防止行为退化

**每次只替换一层，并保持输入输出契约不变**——这就是工程化迭代的核心方法论。

<!-- lab-check:acceptance -->
