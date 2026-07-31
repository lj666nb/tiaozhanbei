# 智能体 vs 工作流

## 概述

在AI应用的设计中，有一个比"ChatBot还是Agent"更根本的工程决策：**这个任务的执行方式应该是确定性的还是非确定性的？** 换句话说，应该用工作流（Workflow）还是智能体（Agent）？

这两个概念分别代表了两种截然不同的任务编排哲学：
- **工作流**：我们提前知道所有可能的路径，画好地图，系统按图索骥。
- **智能体**：我们只知道目的地，系统自己找路，路况不好就换一条。

误判这个决策的代价很高：对确定性任务使用Agent，会引入不必要的延迟、成本和不确定性；对非确定性任务使用Workflow，则根本无法覆盖所有可能的情况。

本章将深入对比这两种范式，从定义、执行机制、适用场景等多个维度展开分析，并提供一套实用的决策框架，帮助你在实际开发中做出正确的选择。

Image-Prompt(workflow-vs-agent-overview):
```
A flat-design 2D vector illustration showing a split-scene comparison of two task execution philosophies. Left side (Workflow): a pre-drawn map with all routes clearly marked, a delivery truck following a highlighted path along fixed roads — labeled "Map Navigation: Follow the Known Path". Right side (Agent): a compass pointing toward a destination star on the horizon, a robot hiker dynamically choosing routes through varied terrain, adapting to obstacles — labeled "Compass Navigation: Find Your Own Way". The dividing line shows a cost comparison: "Deterministic tasks with Agent = unnecessary cost & delay". Tech blue (#409EFF) for Agent/compass side, muted blue-gray for Workflow/map side. Deep blue (#1a1a2e) labels, clean white background, split symmetrical layout.
```

## 工作流（Workflow）的定义

### 什么是工作流

工作流是一种**预先定义的、确定的、结构化的**任务执行方式。它的核心特征是：任务执行的路径在运行前就已经完全确定。

用图论的语言来描述：**工作流是一个有向无环图（DAG, Directed Acyclic Graph）**。每个节点是一个任务步骤，每条边定义了步骤之间的执行顺序和条件。从起点到终点的每条路径都是可以提前枚举的。

### 工作流的技术本质

```
工作流 = DAG（有向无环图）

┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐
│  A  │────▶│  B  │────▶│  D  │────▶│  F  │
└─────┘     └─────┘     └─────┘     └─────┘
               │           ▲
               │           │
               ▼           │
            ┌─────┐        │
            │  C  │────────┘
            └─────┘

在这个DAG中：
- 节点 = 任务步骤（数据处理，API调用，人工审批...）
- 边 = 执行顺序和条件
- 所有可能的执行路径都可以提前枚举
- 不存在循环（无环 = 不会形成死循环）
```

### 工作流的关键特征

```
工作流的四大特征：

1. 预定义性（Predefined）
   → 所有步骤在执行前就已定义好
   → 步骤之间的转换条件明确
   → 不存在"未知的下一步"

2. 确定性（Deterministic）
   → 同样的输入一定会触发同样的执行路径
   → 结果可复现、可审计、可调试
   → 这是企业级应用最看重的特性

3. 结构化（Structured）
   → 有明确的开始节点和结束节点
   → 支持分支（if/else）、并行（fork/join）、合并
   → 可以用BPMN或类似工具可视化建模

4. 可预测性（Predictable）
   → 执行时间可估算
   → 资源消耗可预估
   → 异常情况有预定义的处理路径
```

### 工作流的核心元素与技术实现

一个完整的工作流系统通常包含以下基础元素：

```
工作流的构成要素：

┌─────────────────────────────────────────────────────┐
│                   工作流引擎                          │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │ 触发器    │   │ 任务节点  │   │ 路由规则  │         │
│  │ Trigger   │   │ Task     │   │ Router   │         │
│  │           │   │          │   │          │         │
│  │ · 定时触发 │   │ · 脚本   │   │ · 条件分支 │         │
│  │ · 事件触发 │   │ · API调用│   │ · 并行分支 │         │
│  │ · 手动触发 │   │ · 人工节点│   │ · 合并等待 │         │
│  │ · Webhook │   │ · LLM节点│   │ · 默认路由 │         │
│  └──────────┘   └──────────┘   └──────────┘         │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │ 状态管理  │   │ 错误处理  │   │ 可观测性  │         │
│  │ State    │   │ Error    │   │ Observe  │         │
│  │          │   │          │   │          │         │
│  │ · 变量传递 │   │ · 重试策略 │   │ · 执行日志 │         │
│  │ · 上下文  │   │ · 降级方案 │   │ · 节点耗时 │         │
│  │ · 检查点  │   │ · 人工介入 │   │ · 告警通知 │         │
│  └──────────┘   └──────────┘   └──────────┘         │
└─────────────────────────────────────────────────────┘
```

### 工作流的典型实现示例

以下是一个订单处理工作流的实际代码示例（以LangGraph为例）：

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

# 定义工作流的状态
class OrderState(TypedDict):
    order_id: str
    amount: float
    payment_status: str
    inventory_status: str
    fraud_score: float
    final_status: str

# 定义工作流节点
def validate_payment(state: OrderState) -> OrderState:
    """验证支付"""
    # 调用支付网关API
    payment_result = payment_gateway.verify(state["order_id"])
    state["payment_status"] = payment_result.status
    return state

def check_inventory(state: OrderState) -> OrderState:
    """检查库存"""
    inventory = warehouse_api.check_stock(state["order_id"])
    state["inventory_status"] = "available" if inventory > 0 else "out_of_stock"
    return state

def fraud_detection(state: OrderState) -> OrderState:
    """风控检测"""
    state["fraud_score"] = risk_engine.evaluate(state["order_id"])
    return state

def approve_order(state: OrderState) -> OrderState:
    """确认订单"""
    state["final_status"] = "approved"
    return state

def manual_review(state: OrderState) -> OrderState:
    """人工审核"""
    review_api.create_task(state["order_id"], state["fraud_score"])
    state["final_status"] = "pending_review"
    return state

def reject_order(state: OrderState) -> OrderState:
    """拒绝订单"""
    state["final_status"] = "rejected"
    return state

# 定义路由逻辑
def route_after_fraud(state: OrderState) -> str:
    if state["fraud_score"] < 30:
        return "approve"
    elif state["fraud_score"] < 70:
        return "manual_review"
    else:
        return "reject"

def route_after_inventory(state: OrderState) -> str:
    if state["inventory_status"] == "available":
        return "continue"
    else:
        return "reject"

# 构建工作流（DAG）
workflow = StateGraph(OrderState)

# 添加节点
workflow.add_node("validate_payment", validate_payment)
workflow.add_node("check_inventory", check_inventory)
workflow.add_node("fraud_detection", fraud_detection)
workflow.add_node("approve_order", approve_order)
workflow.add_node("manual_review", manual_review)
workflow.add_node("reject_order", reject_order)

# 添加边：定义执行顺序
workflow.set_entry_point("validate_payment")
workflow.add_edge("validate_payment", "check_inventory")

# 添加条件边：分支逻辑
workflow.add_conditional_edges(
    "check_inventory",
    route_after_inventory,
    {
        "continue": "fraud_detection",
        "reject": "reject_order",
    }
)

workflow.add_conditional_edges(
    "fraud_detection",
    route_after_fraud,
    {
        "approve": "approve_order",
        "manual_review": "manual_review",
        "reject": "reject_order",
    }
)

# 所有终端节点连接至END
workflow.add_edge("approve_order", END)
workflow.add_edge("manual_review", END)
workflow.add_edge("reject_order", END)

# 编译执行
app = workflow.compile()
```

这个工作流的可视化结构：

```
                ┌─────────────────┐
                │ validate_payment │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ check_inventory  │
                └────────┬────────┘
                         │
              ┌──────────┼──────────┐
              │ 有库存    │          │ 无库存
              ▼           │          ▼
    ┌─────────────┐      │   ┌─────────────┐
    │fraud_detection│     │   │ reject_order │
    └──────┬──────┘      │   └─────────────┘
           │             │
    ┌──────┼──────┐      │
    │      │      │      │
   低风险  中风险  高风险  │
    │      │      │      │
    ▼      ▼      ▼      │
┌──────┐ ┌────┐ ┌──────┐ │
│approve│ │人工│ │reject│ │
└──────┘ └────┘ └──────┘ │
```

**关键观察**：这个工作流虽然包含了分支和条件判断，但所有的路径——从开始到结束的每一种可能性——都是在设计时就已经确定的。风控分数小于30一定走approve，大于70一定走reject，没有任何"意外"的空间。

Image-Prompt(workflow-definition-dag):
```
A flat-design 2D vector illustration showing a Workflow as a Directed Acyclic Graph (DAG). The main visual is a clean directed graph with labeled nodes (A, B, C, D, E, F) connected by directional arrows, forming a clear flow from Entry to End. Each node is a rounded rectangle with a task icon (validation, payment, inventory, fraud check, approve, reject). Branching paths show conditional logic (if/else) at node splits. A legend explains: "Node = Task Step", "Edge = Execution Order". The four key features are displayed as badges around the graph: "Predefined", "Deterministic", "Structured", "Predictable". Tech blue (#409EFF) for nodes and arrows, deep blue (#1a1a2e) for labels, clean white background, centered layout.
```

## AI智能体（AI Agent）的定义

### 什么是Agent式执行

与工作流的确定性相反，Agent式的执行是**动态的、自适应的、非确定性的**。Agent在执行前并不知道完整的执行路径——它在每一步根据当前的状态和观察，动态决定下一步做什么。

用图论的语言来描述：**Agent不是在遍历一个预定义的DAG，而是在实时构建一个有向图**。这个图的拓扑结构在执行前是不确定的。

### Agent执行的技术本质

```
Agent执行 ≠ 预定义DAG遍历
Agent执行 = 实时图构建 + 动态路径选择

时间步1：Agent在节点A，面临选择{B, C, D}
时间步2：Agent选择C，到达后新发现可以选择{E, F}
时间步3：Agent选择E，发现任务已完成，决定终止

          A
         /|\
        / | \
       B  C  D    ← 时间步1：从A可以到B/C/D
           |
          / \
         E   F    ← 时间步2：从C可以到E/F（这个关系在A时未知）
         |
        END       ← 时间步3：Agent决定结束

整个过程不是遍历预定义图，而是"摸着石头过河"
```

### Agent执行的关键特征

```
Agent式执行的四大特征：

1. 动态性（Dynamic）
   → 执行路径在执行过程中实时确定
   → 下一步的选择取决于当前步骤的实际输出
   → 可能出现设计者未曾预料到的执行路径

2. 自适应（Adaptive）
   → 遇到障碍时自动调整策略
   → 发现新信息时可能完全改变计划
   → 具备"此路不通走彼路"的灵活性

3. 非确定性（Non-deterministic）
   → 同样的输入可能产生不同的执行路径
   → 因为Agent的决策依赖LLM的推理输出
   → 这既是优势（灵活性）也是劣势（不可预测）

4. 目标驱动（Goal-driven）
   → Agent不关心"按什么路径完成"
   → 只关心"目标是否达成"
   → "条条大路通罗马"是Agent的默认心态
```

### Agent执行的代码示例

以下对比展示：同一个"处理客户退款"的任务，工作流和Agent的实现差异。

```python
# ============================================
# 方式一：工作流实现 —— 所有路径预定义
# ============================================
class RefundWorkflow:
    """退款工作流：所有分支在设计时已确定"""

    def process(self, refund_request):
        # Step 1: 验证订单
        order = self.db.get_order(refund_request.order_id)
        if not order:
            return {"status": "rejected", "reason": "订单不存在"}

        # Step 2: 检查退款时效
        if order.days_since_purchase > 30:
            return {"status": "rejected", "reason": "超过30天退款期限"}

        # Step 3: 检查商品状态
        if refund_request.reason == "质量问题":
            return self._quality_refund(order)  # 走质量退款流程
        elif refund_request.reason == "不想要了":
            if order.amount > 500:
                return {"status": "pending", "reason": "大额退款需人工审核"}
            return self._standard_refund(order)  # 走标准退款流程
        else:
            return {"status": "pending", "reason": "未知退款原因，转人工"}


# ============================================
# 方式二：Agent实现 —— 路径由LLM动态决定
# ============================================
class RefundAgent:
    """退款Agent：每步由LLM根据当前状态动态决策"""

    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = {
            "get_order": self.db.get_order,
            "check_return_policy": self.policy_engine.check,
            "inspect_item_photo": self.vision_ai.analyze,  # 看用户上传的图片
            "check_inventory": self.warehouse.check_stock,
            "calculate_refund_amount": self.finance.calculate,
            "process_refund": self.payment.process,
            "send_email": self.email.send,
            "escalate_to_human": self.ticket_system.create,
        }

    def process(self, refund_request):
        context = {"request": refund_request, "history": []}

        for step in range(10):  # 最多10步
            # LLM观察当前状态，决定下一步
            decision = self.llm.decide(
                goal=f"处理退款请求: {refund_request}",
                context=context,
                available_tools=self.tools,
            )

            if decision.action == "FINISH":
                return decision.final_result

            # Agent的自主行为示例（工作流不可能做到）：
            if decision.action == "inspect_item_photo":
                # Agent自主决定：用户上传了商品照片，先看看有没有损坏
                result = self.tools["inspect_item_photo"](
                    refund_request.photos
                )
                if result.damage_detected:
                    # 发现损坏 → Agent自主改变策略
                    context["insight"] = "商品确实有损坏，应走质量退款"
                    # 接下来Agent会走向质量退款路径
                    # 这个决策是运行时做出的，不在预定义分支中

            elif decision.action == "check_inventory":
                # Agent自主决定：如果商品缺货，退款金额应该加补偿
                stock = self.tools["check_inventory"](
                    refund_request.product_id
                )
                if stock < 10:
                    context["note"] = "商品接近售罄，建议提供补偿券"
                    # 这个推理没有写在if-else里

            # 执行决定的工具调用
            result = self.tools[decision.action](**decision.params)
            context["history"].append({
                "step": step,
                "action": decision.action,
                "result": result,
            })

        return {"status": "max_steps_reached"}
```

**关键差异**：工作流的所有分支（质量问题、不想要了、大额审核...）在编写代码时就已经硬编码了。Agent的分支（看图判断是否损坏、查库存决定是否补偿）是运行时由LLM推理产生的，在设计代码时并没有对应的if-else语句。

Image-Prompt(agent-definition-dynamic-graph):
```
A flat-design 2D vector illustration showing Agent execution as real-time graph building. Unlike the fixed DAG, this shows a dynamic process: at Time 1, Agent is at node A facing three unknowns (B, C, D) with lightning bolt decision lines. At Time 2, Agent chose C and discovered new options (E, F) that weren't visible before. At Time 3, Agent reached the goal. The visual shows a "fog of war" effect — unexplored paths are grayed out, explored paths are tech blue (#409EFF). The four key features are displayed as badges: "Dynamic", "Adaptive", "Non-deterministic", "Goal-driven". A small comparison inset shows: "Workflow = traversing a known map" vs "Agent = building the map as you go". Deep blue (#1a1a2e) labels, clean white background.
```

## 核心区别深度解析

### 确定性 vs 非确定性

这是最根本的哲学差异：

```
工作流的世界观：
  世界是可建模的 → 所有情况都可以提前枚举 → 写好规则就够了

Agent的世界观：
  世界是复杂的 → 总有意外情况 → 需要动态推理和适应
```

**一个思想实验**：假设你要设计一个"处理客户投诉"的系统。

- 工作流思路：枚举所有投诉类型（产品质量、物流延迟、客服态度、账单错误...），每种类型写一个处理流程。
- Agent思路：给Agent一个目标（"让客户满意并解决问题"），一套工具（退款、补偿、道歉信、升级处理...），让它自己判断怎么做。

哪种好？取决于你的领域：
- 如果投诉类型确实有限且稳定（比如只有5种标准投诉类型），工作流更可靠。
- 如果投诉五花八门且不断变化（用户可能投诉任何东西），Agent是唯一可行的方案。

### 预定义路径 vs 动态决策

```
┌────────────────────────────────────────────────────────────┐
│                     工作流的路径空间                         │
│                                                            │
│  所有可能的执行路径在设计时就已确定：                          │
│                                                            │
│  ●───●───●───●    路径1: A→B→D→F                          │
│  │    \   /                                                │
│  ●     \ /     路径2: A→C→E→F（或A→C→D→F）                │
│  │      ●                                                   │
│  ●─────●       路径3: A→C→G→H                              │
│  │                                                         │
│  ●                 总共只有这N条路径                          │
│                                                            │
│  优点：每条路径都可测试、可审计、可优化                        │
│  缺点：出现第N+1种情况时束手无策                             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                     Agent的路径空间                          │
│                                                            │
│  Agent的决策空间是一个动态拓展的树：                          │
│                                                            │
│                ● 起点                                       │
│               /|\                                          │
│              / | \        第1次决策：有N个可能选项            │
│             /  |  \                                        │
│            ●   ●   ●     第2次决策：每个选项下又有M个可能     │
│           /|\  /|\  /|\                                     │
│          ...  ...  ...   持续分叉，指数级可能路径              │
│                                                            │
│  优点：几乎可以处理任何情况                                  │
│  缺点：不可完全预测，不可完全测试，可能走出"坏路径"            │
└────────────────────────────────────────────────────────────┘
```

### 多维度对比表

| 对比维度 | 工作流（Workflow） | 智能体（Agent） |
|----------|-----------------|----------------|
| **执行路径** | 预定义，执行前已知 | 动态产生，执行中方知 |
| **决策者** | 规则引擎 / 条件判断 | LLM推理引擎 |
| **确定性** | 确定：相同输入→相同输出 | 非确定：相同输入可能不同输出 |
| **适应性** | 低：只处理设计时考虑的情况 | 高：可处理未见过的情境 |
| **可预测性** | 高：执行时间、资源可预估 | 低：可能快速完成也可能绕远路 |
| **可调试性** | 高：路径可追踪、可复现 | 中低：需看推理日志才能理解 |
| **可审计性** | 高：每一步都有明确的合规依据 | 中：LLM的推理过程可解释但不完全确定 |
| **开发成本** | 中：需要梳理清楚所有业务流程 | 低中：定义工具和约束即可 |
| **运行成本** | 低：不需要LLM推理每步决策 | 高：每步决策消耗LLM tokens |
| **响应速度** | 快：毫秒~秒 | 慢：秒~十秒（需多轮LLM推理） |
| **容错能力** | 弱：未定义的情况直接失败 | 强：可自主尝试替代方案 |
| **业务逻辑变更** | 重：需要修改流程定义并重新测试 | 轻：调整提示词或工具即可 |
| **适合的团队** | 业务分析师 + 工程师 | AI工程师 + 提示词工程师 |
| **典型框架** | Temporal, Airflow, LangGraph, Camunda | LangChain Agent, OpenAI Agent SDK, CrewAI |

Image-Prompt(workflow-vs-agent-path-comparison):
```
A flat-design 2D vector illustration showing two path-space visualizations side by side. Left: "Workflow Path Space" — a finite, clearly bounded decision tree with all paths visible and enumerated (Path 1: A→B→D→F, Path 2: A→C→E→F, etc.), each path numbered like a subway map. Labels: "All N paths predefined", "Testable, auditable, optimizable". Right: "Agent Path Space" — an infinite-expanding tree with a root node at center, branching exponentially outward with dotted "possible but unexplored" branches radiating into a star shape. Labels: "Exponential possible paths", "Cannot fully predict, cannot fully test". Tech blue (#409EFF) for Agent side, structured gray-blue for Workflow side. Deep blue (#1a1a2e) labels, clean white background, comparison layout.
```

## 决策树：什么场景用工作流？什么场景用Agent？

### 决策框架

这是一个系统性的决策框架，通过5个关键问题帮助你做出选择。

```
决策起点：我要自动化一个业务流程
                │
                ▼
┌─────────────────────────────────────┐
│ 问题1：任务的步骤是否可以提前完全     │
│        枚举？（≤30步，且覆盖所有情况） │
└──────────────┬──────────────────────┘
               │
          ┌────┴────┐
          │ 是      │ 否 → Agent（步骤太多或不确定，必须动态决策）
          ▼         │
┌─────────────────────────────────────┐
│ 问题2：每种情况下"下一步做什么"的    │
│        规则是否明确且稳定？          │
└──────────────┬──────────────────────┘
               │
          ┌────┴────┐
          │ 是      │ 否 → Agent（规则模糊或频繁变化，需要LLM推理）
          ▼         │
┌─────────────────────────────────────┐
│ 问题3：任务的容错率如何？错了能不能   │
│        承担后果？                    │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       │ 低容错         │ 高容错
       │ （不能出错）    │ （错了可以重来）
       ▼               ▼
┌────────────┐   ┌─────────────────────┐
│ 问题4：     │   │ 问题5：任务是否经常   │
│ 是否有合规  │   │ 出现设计者没想到的   │
│ /审计要求？ │   │ 新情况？             │
└──┬─────┬───┘   └──────┬──────────────┘
   │     │               │
  是    否          ┌────┴────┐
   │     │          │ 是      │ 否
   ▼     ▼          ▼         ▼
 ✅    考虑      ✅ Agent   ✅ 工作流
工作流  混合      必需      就够
必须   模式
```

### 快速判断口诀

```
四看原则：

1. 看边界：任务边界清晰吗？
   → 清晰 = 工作流  模糊 = Agent

2. 看变化：会出现意料之外的情况吗？
   → 不会 = 工作流  会 = Agent

3. 看后果：出了错严重吗？
   → 严重 = 工作流（至少核心部分）  不严重 = Agent可尝试

4. 看频率：业务流程变化频繁吗？
   → 不频繁 = 工作流（一次投入，长期受益）
   → 频繁 = Agent（改提示词比改代码快）
```

### 具体场景选择表

| 业务场景 | 推荐方案 | 理由 |
|----------|---------|------|
| 员工入职流程（IT开通+HR归档+培训安排） | ✅ 工作流 | 步骤完全标准化，无意外情况 |
| 贷款审批（征信→收入验证→风控评分→审批） | ✅ 工作流 | 合规要求，必须可审计 |
| 订单履约（下单→支付→拣货→发货→签收） | ✅ 工作流 | 流程确定，每次一样 |
| 数据ETL管道（提取→清洗→转换→加载） | ✅ 工作流 | 确定性数据处理 |
| 客户投诉处理 | ⚠️ 混合 | 标准投诉流程用工作流，复杂投诉转Agent |
| 智能客服（含退款/改单等操作） | ⚠️ 混合 | FAQ走工作流快速路由，复杂操作走Agent |
| 内容审核（机审→高风险转人审→复审） | ⚠️ 混合 | 确定规则用工作流，边缘判断用Agent |
| 竞品分析 | ✅ Agent | 搜索→分析→对比→报告，路径差异大 |
| 代码Bug诊断和修复 | ✅ Agent | 每个Bug都不一样，需要动态推理 |
| 旅行行程规划 | ✅ Agent | 每个用户偏好不同，方案千差万别 |
| 个人日程管理 | ✅ Agent | 动态冲突解决，灵活调整 |

Image-Prompt(workflow-vs-agent-decision-tree):
```
A flat-design 2D vector illustration showing a decision tree flowchart. Starting from the top: "Automate a Business Process" → five diamond-shaped decision nodes branching downward: Q1 "Can all steps be fully enumerated?" → Q2 "Are transition rules clear and stable?" → Q3 "Error tolerance?" → Q4 "Compliance/audit required?" → Q5 "New unexpected situations frequent?". Each "Yes" and "No" branch leads to a recommendation badge: green for "Workflow", tech blue (#409EFF) for "Agent", and a gradient badge for "Hybrid Mode". The "Four-Principle Quick Guide" appears as a small sidebar: "1. Look at boundaries, 2. Look at changes, 3. Look at consequences, 4. Look at frequency". Deep blue (#1a1a2e) labels, clean white background, centered tree layout.
```

## 混合模式：工作流中嵌入智能体节点（Agentic Workflow）

### 为什么需要混合模式

纯粹的工作流太死板，纯粹的Agent不可靠。混合模式取两者之长：

```
工作流的优势：
  ✅ 确定性 → 关键环节不能出错
  ✅ 可审计 → 满足合规要求
  ✅ 高效 → 不需要LLM的地方就别用

Agent的优势：
  ✅ 灵活 → 处理意外和边缘情况
  ✅ 智能 → 需要推理和判断的地方
  ✅ 自适应 → 根据结果动态调整
```

### 混合架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    混合式 Agentic Workflow                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   工作流引擎（骨架）                    │   │
│  │                                                       │   │
│  │  ┌──────┐   ┌──────┐   ┌──────────┐   ┌──────┐      │   │
│  │  │ 入口  │──▶│ 校验 │──▶│ Agent节点 │──▶│ 审核  │      │   │
│  │  │      │   │ (规则)│   │ (动态推理)│   │(规则) │      │   │
│  │  └──────┘   └──────┘   └─────┬────┘   └──┬───┘      │   │
│  │                              │            │          │   │
│  │                        ┌─────┴────┐       │          │   │
│  │                        │ Agent内部 │       │          │   │
│  │                        │ ○→○→○→○  │       │          │   │
│  │                        │ 自由探索  │       │          │   │
│  │                        └──────────┘       │          │   │
│  │                              │            │          │   │
│  │                              ▼            ▼          │   │
│  │                         ┌──────┐    ┌──────────┐    │   │
│  │                         │ 执行 │───▶│  结束    │    │   │
│  │                         │(规则)│    └──────────┘    │   │
│  │                         └──────┘                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  特点：                                                      │
│  · 外围由工作流控制 → 保证整体流程可控、可审计                │
│  · 核心推理交给Agent → 获得灵活性和智能性                    │
│  · Agent节点有明确的输入输出契约 → 作为工作流的一部分运行      │
└─────────────────────────────────────────────────────────────┘
```

### 混合模式的代码实现

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Any

class CustomerServiceState(TypedDict):
    user_input: str
    user_profile: dict
    intent: str
    agent_result: Any
    final_response: str

# ============================================
# 工作流节点（确定性）
# ============================================

def classify_intent(state: CustomerServiceState) -> CustomerServiceState:
    """意图分类 —— 用规则做，不用LLM，快速且免费"""
    text = state["user_input"]

    # 规则快速路由（毫秒级，零成本）
    keywords_map = {
        "greeting": ["你好", "hi", "hello", "在吗"],
        "order_query": ["订单", "物流", "发货", "到哪了"],
        "faq": ["退货政策", "保修", "多久到", "怎么退"],
        "account": ["密码", "登录", "注册", "绑定"],
        "complex": [],  # 匹配不到走这个
    }

    for intent, keywords in keywords_map.items():
        for kw in keywords:
            if kw in text:
                state["intent"] = intent
                return state

    # 没有匹配到关键词 → 标记为复杂问题，交给Agent
    state["intent"] = "complex"
    return state


def route_by_intent(state: CustomerServiceState) -> str:
    """路由决策 —— 完全确定性"""
    if state["intent"] in ["greeting", "faq"]:
        return "simple_reply"     # 简单回复，模板即可
    elif state["intent"] in ["order_query", "account"]:
        return "structured_flow"  # 结构化处理流程
    else:
        return "agent_node"       # 复杂问题交给Agent


# ============================================
# Agent节点（非确定性）
# ============================================

class CustomerServiceAgent:
    """Agent节点：处理需要动态推理的复杂问题"""

    def __init__(self, llm):
        self.llm = llm
        self.tools = {
            "search_knowledge_base": kb.search,
            "query_order_system": order_api.query,
            "process_refund": payment_api.refund,
            "check_policy": policy_engine.lookup,
            "create_ticket": ticket_system.create,
        }

    def __call__(self, state: CustomerServiceState) -> CustomerServiceState:
        """Agent自由执行循环"""
        context = {
            "user_input": state["user_input"],
            "user_profile": state["user_profile"],
        }

        for step in range(8):
            decision = self.llm.decide(
                goal="解决用户问题",
                context=context,
                tools=self.tools,
            )
            if decision.action == "FINISH":
                state["agent_result"] = decision.response
                return state

            context = self._execute_tool(decision, context)

        state["agent_result"] = "复杂问题超时，已转人工处理"
        return state


# ============================================
# 组装混合工作流
# ============================================

def simple_reply(state: CustomerServiceState) -> CustomerServiceState:
    """简单回复 —— 模板，不调用LLM"""
    templates = {
        "greeting": "您好！我是AI客服助手，有什么可以帮您的？",
        "faq": "关于这个问题，请参考我们的帮助中心：help.example.com",
    }
    state["final_response"] = templates.get(state["intent"], "请详述您的问题。")
    return state

def structured_flow(state: CustomerServiceState) -> CustomerServiceState:
    """结构化处理 —— 确定性的多步骤流程"""
    # 调用固定的业务流程
    result = standard_service_flow(state["intent"], state["user_input"])
    state["final_response"] = result
    return state

def human_review_node(state: CustomerServiceState) -> CustomerServiceState:
    """人工审核节点 —— 高风险操作前的人工确认"""
    agent_output = state["agent_result"]
    if agent_output.get("risk_level") == "high":
        # 高风险操作：创建工单等待人工审核
        ticket_system.create(agent_output)
        state["final_response"] = "您的问题已转接高级客服，将在2小时内回复。"
    else:
        # 低风险操作：直接执行
        state["final_response"] = agent_output["response"]
    return state

# 构建混合工作流
hybrid_workflow = StateGraph(CustomerServiceState)

hybrid_workflow.add_node("classify_intent", classify_intent)
hybrid_workflow.add_node("simple_reply", simple_reply)
hybrid_workflow.add_node("structured_flow", structured_flow)
hybrid_workflow.add_node("agent_node", CustomerServiceAgent(llm))
hybrid_workflow.add_node("human_review", human_review_node)

hybrid_workflow.set_entry_point("classify_intent")

hybrid_workflow.add_conditional_edges(
    "classify_intent",
    route_by_intent,
    {
        "simple_reply": "simple_reply",
        "structured_flow": "structured_flow",
        "agent_node": "agent_node",
    }
)

hybrid_workflow.add_edge("simple_reply", END)
hybrid_workflow.add_edge("structured_flow", END)
hybrid_workflow.add_edge("agent_node", "human_review")  # Agent输出必须经过审核
hybrid_workflow.add_edge("human_review", END)

hybrid_app = hybrid_workflow.compile()
```

### 混合模式的设计原则

```
混合模式设计的四条黄金法则：

1. 工作流是骨架，Agent是肌肉
   → 用工作流定义"必须经过哪些环节"
   → 在需要判断的环节嵌入Agent

2. Agent的输出不能直接落地
   → Agent的输出应该经过一个验证/审核环节
   → 高风险操作（退款、发邮件）必须有人工确认

3. 能确定的事不要交给不确定的系统
   → 规则能解决的问题就不用LLM
   → 省成本、省时间、更可靠

4. 保留降级路径
   → Agent超时/失败时自动降级为工作流兜底策略
   → "Agent不行就按规则来"
```

Image-Prompt(hybrid-agentic-workflow):
```
A flat-design 2D vector illustration showing a hybrid architecture diagram. The outer structure is a Workflow Engine (labeled "Skeleton") drawn as a solid rounded rectangle with deterministic nodes: Entry → Validation (rule) → Agent Node (dynamic) → Review (rule) → End. The Agent Node is a highlighted tech blue (#409EFF) inner box containing a freeform exploration pattern (labeled "Muscle") with a mini robot navigating between sub-nodes. Bubbles annotate the four design principles: "1. Workflow is skeleton, Agent is muscle", "2. Agent output must be verified", "3. Certain things don't need LLM", "4. Keep fallback path". A small cost comparison table at bottom: Cost, Reliability, Flexibility for Pure Workflow vs Hybrid vs Pure Agent. Deep blue (#1a1a2e) labels, clean white background.
```

## 实际案例：客服系统的混合架构

### 背景

一个电商平台的智能客服系统，每天处理10万+次用户咨询。涵盖：订单查询、物流追踪、退款申请、投诉处理、产品咨询、账户问题等。

### 架构设计

```
                       用户消息
                          │
                          ▼
              ┌───────────────────────┐
              │  第1层：快速路由层       │  完全确定性（工作流）
              │  关键词+正则匹配        │
              │  响应时间：<10ms        │
              │  覆盖：60%的请求        │
              │  成本：几乎为零          │
              └───────────┬───────────┘
                          │
              ┌───────────┴───────────┐
              │ 快速命中？              │
              └───────────┬───────────┘
                    ┌─────┴─────┐
                   是            否
                    │             │
                    ▼             ▼
          ┌─────────────┐  ┌───────────────────────┐
          │ 模板回复     │  │  第2层：意图分类层       │
          │ （工作流）    │  │  轻量NLU模型           │
          └─────────────┘  │  响应时间：<50ms        │
                           │  覆盖：+25%的请求       │
                           │  成本：极低              │
                           └───────────┬───────────┘
                                       │
                           ┌───────────┴───────────┐
                           │ 意图明确且有标准流程？    │
                           └───────────┬───────────┘
                                 ┌─────┴─────┐
                                是            否
                                 │             │
                                 ▼             ▼
                       ┌──────────────┐  ┌───────────────────────┐
                       │ 第3层：标准   │  │  第4层：Agent深度处理   │
                       │ 流程处理      │  │  （非确定性）           │
                       │ （工作流）     │  │  LLM推理 + 工具调用     │
                       │              │  │  响应时间：2-15秒       │
                       │ 流程包括：    │  │  覆盖：最后的15%       │
                       │ · 订单查询   │  │  成本：较高             │
                       │ · 物流追踪   │  └───────────┬───────────┘
                       │ · 简单退款   │              │
                       │ · 账户操作   │    ┌─────────┴─────────┐
                       └──────────────┘    │ 需要人工确认？      │
                                           └─────────┬─────────┘
                                               ┌─────┴─────┐
                                              是            否
                                               │             │
                                               ▼             ▼
                                     ┌──────────────┐  ┌──────────┐
                                     │ 第5层：人工   │  │ 自动执行  │
                                     │ 审核（HITL）  │  │ 并回复   │
                                     └──────────────┘  └──────────┘
```

### 各级分工明细

| 层级 | 类型 | 处理内容 | 占比 | 响应时间 | 每千次成本 |
|------|------|---------|------|---------|-----------|
| 第1层 | 工作流 | "你好"、"在吗"、"谢谢"、简单FAQ | 60% | <10ms | ~0元 |
| 第2层 | 工作流 | "我的订单到哪了"、"怎么退货" | 25% | <50ms | ~0.1元 |
| 第3层 | 工作流 | 订单查询、物流追踪、标准退款 | 10% | <500ms | ~1元 |
| 第4层 | Agent | "为什么扣了我两次钱"、"我收到的和图片不一样"、"帮我比较A和B哪个好" | 4% | 2-15s | ~50元 |
| 第5层 | HITL | 第4层中Agent判断需要人工介入的案件 | 1% | 分钟~小时 | ~500元 |

### 关键数据指标

```
架构效果量化：

┌──────────────────────────────────────────────────────┐
│  指标                  纯工作流方案    混合方案       │
├──────────────────────────────────────────────────────┤
│  问题解决率             72%            94%           │
│  平均响应时间           200ms          1.2s          │
│  日均LLM调用量           0              ~5000次       │
│  日均运营成本            ¥30            ¥280         │
│  人工介入比例           28%            6%            │
│  用户满意度             3.8/5          4.5/5         │
│  新问题类型适应时间     2周（改代码）   1天（改提示词） │
└──────────────────────────────────────────────────────┘
```

关键洞察：混合方案用280元/天的增量成本，换来了人工介入率从28%降至6%。按每个客服日薪400元计算，相当于节省了约4.5个客服的人力。

Image-Prompt(customer-service-hybrid-architecture):
```
A flat-design 2D vector illustration showing a five-layer funnel architecture for a customer service system. Layer 1 (top, widest, light gray): "Quick Router — Keyword + Regex, <10ms, 60% traffic, Near zero cost" with template reply icon. Layer 2: "Intent Classifier — Light NLU, <50ms, +25% traffic" with NLU chip icon. Layer 3: "Standard Workflow — Order/Logistics/Refund, <500ms, +10%" with structured flow icon. Layer 4 (narrower, tech blue #409EFF): "Agent Deep Processing — LLM + Tools, 2-15s, final 4%" with robot brain and tools icon. Layer 5 (narrowest, with a human figure): "Human Review (HITL) — 1%, minutes-hours" with checkbox icon. A performance dashboard card at the bottom shows key metrics: "Resolution Rate: 94%", "Avg Response: 1.2s", "Daily LLM Calls: ~5000", "Human Intervention: 6%". Deep blue (#1a1a2e) labels, clean white background.
```

## 总结

工作流和Agent代表了两种任务编排的哲学，没有绝对的优劣之分。

**工作流是"地图导航"**——你提前知道所有路口、所有可能的路径，画好一张精确的地图，然后严格按照地图走。它精确、可靠、高效，但遇到地图上没有标注的新路口就束手无策。

**Agent是"指南针导航"**——你只知道目的地在哪个方向，然后根据实际地形和障碍动态选择路径。它灵活、自适应、能处理意外，但可能绕远路，可能迷路，需要时不时确认方向。

**混合模式（Agentic Workflow）是"地图+指南针"**——主干道用地图（工作流），遇到地图上没有标注的岔路口时用指南针（Agent），过了复杂地带再回到地图。这是目前生产环境中最实用、最主流的架构选择。

记住这个决策公式：

```
如果你的业务流程可以被完整地写成一本标准操作手册（SOP），用工作流。
如果你发现自己在写SOP时总是遇到"视情况而定"的环节，在那个环节嵌入Agent。
如果整个任务从头到尾都是"视情况而定"，那就全用Agent——但要设好护栏。
```

在下一章中，我们将深入探讨智能体的辅助特征——记忆与学习能力，这是Agent区别于一次性工具调用的关键维度之一。

---

**关键记忆点：**

```
工作流 = 预定义的、确定性的任务执行 → 适合标准化流程
Agent  = 动态的、自适应的任务执行 → 适合需要判断和推理的任务
混合   = 工作流骨架 + Agent节点 → 生产环境的最佳实践

决策原则：能确定的就别让AI猜，AI猜的要设好护栏。
```

Image-Prompt(workflow-vs-agent-summary):
```
A flat-design 2D vector illustration showing a unified summary metaphor. Center: a character holding both a map (Workflow) in one hand and a compass (Agent) in the other, walking forward confidently. Three labeled zones: left zone — "Workflow = Map Navigation" showing a bus on a clearly marked road with street signs (standardized processes); center zone — "Hybrid = Map + Compass" showing main roads with the character consulting a compass at intersections (the practical gold standard); right zone — "Agent = Compass Navigation" showing open terrain with the character following the compass toward a goal star on the horizon (creative problem-solving). The decision formula at the bottom: "SOP exists → Workflow | Case-by-case → Embed Agent | All case-by-case → Full Agent with guardrails". Tech blue (#409EFF) for Agent elements, structured gray for Workflow elements, deep blue (#1a1a2e) labels, clean white background, centered layout.
```
