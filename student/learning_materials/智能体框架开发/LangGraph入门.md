# LangGraph图结构Agent开发

## 引言

LangChain已经成为许多AI开发者构建智能体的首选框架，它将大语言模型、工具和记忆串联成链式的工作流。然而，当你的智能体需要循环思考、条件判断和多路分支时，链式结构的局限性就暴露出来了。这就是**LangGraph**诞生的原因——它将智能体的工作流建模为**有向图**，让开发者能够构建更加灵活、强大、可控的智能体系统。

本文将带你从零开始了解LangGraph，理解它与LangChain的区别，掌握图结构开发的核心概念，并通过实践示例构建你的第一个LangGraph智能体。

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration showing a contrast between two approaches: on the left a rigid linear chain of connected rectangles (labeled "Step 1→Step 2→Step 3") cracking and breaking apart, on the right a flexible directed graph with circular nodes and branching edges labeled with decision points, a glowing state object flowing through the graph, clean white background, light blue #409EFF for graph nodes and edges, dark blue #1a1a2e labels, rounded shapes, academic learning atmosphere.

---

## 什么是LangGraph

LangGraph是LangChain团队推出的图结构智能体开发框架。它的核心理念是：**将智能体的行为流程建模为一个状态图（State Graph）**。在这个图中：

- **节点（Node）** 代表处理步骤——可能是调用LLM、执行工具、或者任何自定义逻辑
- **边（Edge）** 代表数据流和控制流——决定从当前步骤接下来要去哪里
- **状态（State）** 在整个图中流转，记录智能体的"记忆"和当前进度

### 现实类比

如果把LangChain比作一条流水线（原料→加工→包装→成品），那么LangGraph就像是棋类游戏——你需要根据当前局面（状态）做出决策，每一步的选择会影响后续的走向，而且你可能需要反复回到之前的步骤进行调整。

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a directed state graph with three rounded rectangular nodes labeled "LLM Call" (brain icon), "Tool Execution" (wrench icon), and "Decision Router" (diamond with question mark), connected by light blue #409EFF directional arrows, a glowing "State" object represented as a document card flowing along the edges, node circles with thin-line icons, clean white background, dark blue #1a1a2e text labels, centered symmetric layout, educational diagram style.

---

## LangGraph与LangChain的区别

理解两者的差异，有助于你在正确的场景中选择正确的工具。

| 维度 | LangChain | LangGraph |
|------|-----------|-----------|
| 工作流模型 | 线性链（Chain） | 有向图（Graph） |
| 循环支持 | 不支持 | 天然支持 |
| 条件分支 | 有限的RouterChain | 灵活的条件边 |
| 状态管理 | 无内置机制，需要自行实现 | 内置State，贯穿全流程 |
| 持久化 | 无内置 | 内置Checkpointing |
| 适用场景 | 简单的数据流水线 | 复杂的智能体决策流程 |
| 学习曲线 | 低 | 中等 |

**一句话总结**：LangChain适合"做菜"（按食谱一步步来）类的任务，LangGraph适合"下棋"（需要根据局势反复思考决策）类的任务。

值得注意的是，LangGraph与LangChain并非互斥关系——它们可以很好地协同工作。你可以在LangGraph的节点中使用LangChain的Chain和Tool，将两者的优势结合起来。

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a split comparison scene: left side shows a cooking assembly line (LangChain metaphor) with ingredient icons flowing through linear processing stations labeled "Load→Split→Embed→Store", right side shows a chess board (LangGraph metaphor) with branching move arrows and a decision tree overlay, center-bottom a Venn diagram showing overlapping "Chain" and "Graph" circles with "Tools" in the intersection, clean white background, light blue #409EFF accents, dark blue #1a1a2e labels.

---

## 核心概念详解

### 1. State（状态）

State是LangGraph的灵魂。它定义了在整个图执行过程中流转和积累的数据结构。

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    # messages会在每次节点返回时追加，而不是覆盖
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # 普通字段会被覆盖
    next_step: str
    task_result: str
    iteration_count: int
```

关键知识点：
- 使用`Annotated` + `operator.add`可以让字段在更新时**追加**而非覆盖，这对于保存对话历史非常有用
- 普通字段在每次节点返回时会被**覆盖更新**
- State的类型定义是图编译时的契约，确保所有节点都遵守相同的数据结构

### 2. Node（节点）

节点是图的计算单元。每个节点是一个函数，接收当前State，返回State的更新部分。

```python
def agent_node(state: AgentState) -> dict:
    """调用LLM进行决策的节点"""
    # 从状态中获取消息历史
    messages = state["messages"]
    
    # 调用LLM
    response = llm.invoke(messages)
    
    # 返回状态更新
    return {
        "messages": [response],  # 追加到消息列表
        "next_step": "check_if_done",
        "iteration_count": state.get("iteration_count", 0) + 1
    }

def tool_node(state: AgentState) -> dict:
    """执行工具调用的节点"""
    last_message = state["messages"][-1]
    
    # 执行工具
    tool_result = execute_tool(last_message.tool_calls[0])
    
    # 将工具结果作为新消息返回
    return {
        "messages": [ToolMessage(content=tool_result)],
        "next_step": "agent"
    }
```

### 3. Edge（边）

边定义了节点之间的流转关系。LangGraph支持两种边：

**普通边（Normal Edge）**：无条件地从节点A转到节点B。

```python
workflow.add_edge("tools", "agent")  # tools执行完总是回到agent
```

**条件边（Conditional Edge）**：根据State的内容动态决定下一个节点。

```python
def router(state: AgentState) -> str:
    """根据状态决定下一步去哪个节点"""
    last_message = state["messages"][-1]
    
    # 如果LLM决定调用工具
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # 如果已经达到最大迭代次数
    if state["iteration_count"] >= 5:
        return "finalize"
    
    # 如果LLM给出了最终回答
    if "FINAL ANSWER" in last_message.content:
        return "end"
    
    # 否则继续思考
    return "agent"

# 添加条件边
workflow.add_conditional_edges(
    "agent",      # 从agent节点出发
    router,        # 使用router函数决定
    {              # 映射router返回值到目标节点
        "tools": "tools",
        "agent": "agent",
        "finalize": "finalize",
        "end": END
    }
)
```

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of three concept panels arranged horizontally: left panel "State" showing a layered data card with fields (messages list with append icon, next_step string, iteration_count number), center panel "Node" showing a rounded function box with State input arrow entering and updated State output arrow exiting, right panel "Edge" showing two types — a straight normal edge arrow and a branching conditional edge with diamond router sending to different target nodes, all in light blue #409EFF outlines, dark blue #1a1a2e labels, clean white background, educational software UI style.

---

## 构建你的第一个LangGraph智能体

让我们通过一个完整的搜索智能体示例来实践LangGraph的使用。

### 场景设计

我们要构建一个智能体，让它能够：接收用户问题 → 思考是否需要搜索 → 搜索信息 → 整合信息回答 → 评估回答是否充分 → 如果不充分则继续搜索和改进。

### 完整代码

```python
from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# 第一步：定义State
class SearchAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    search_results: Annotated[list, operator.add]
    next_action: str
    iteration: int

# 第二步：定义节点函数
def think_node(state: SearchAgentState) -> dict:
    """智能体思考下一步行动"""
    prompt = f"""
    你是一个研究助手。当前是第{state.get('iteration', 0)}轮思考。
    
    已搜索到的信息：{state.get('search_results', [])}
    
    请决定下一步行动：
    - 如果需要更多信息，回复 SEARCH: <搜索关键词>
    - 如果信息足够，回复 ANSWER: <你的回答>
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {
        "messages": [response],
        "next_action": "search" if "SEARCH:" in response.content else "answer",
        "iteration": state.get("iteration", 0) + 1
    }

def search_node(state: SearchAgentState) -> dict:
    """执行搜索"""
    last_message = state["messages"][-1].content
    query = last_message.split("SEARCH:")[1].strip()
    
    results = search_tool.search(query)
    
    return {
        "search_results": results,
        "next_action": "think"
    }

def answer_node(state: SearchAgentState) -> dict:
    """生成最终回答"""
    last_message = state["messages"][-1].content
    answer = last_message.split("ANSWER:")[1].strip()
    
    return {
        "messages": [AIMessage(content=answer)],
        "next_action": "end"
    }

# 第三步：构建图
def build_search_agent():
    workflow = StateGraph(SearchAgentState)
    
    # 添加节点
    workflow.add_node("think", think_node)
    workflow.add_node("search", search_node)
    workflow.add_node("answer", answer_node)
    
    # 设置入口
    workflow.set_entry_point("think")
    
    # 添加条件边
    def route_after_think(state):
        if state["iteration"] >= 10:  # 最多10轮
            return "answer"
        return state["next_action"]
    
    workflow.add_conditional_edges("think", route_after_think, {
        "search": "search",
        "answer": "answer"
    })
    
    # 搜索后总是回到思考
    workflow.add_edge("search", "think")
    
    # answer后结束
    workflow.add_edge("answer", END)
    
    return workflow.compile()

# 第四步：运行
agent = build_search_agent()
result = agent.invoke({
    "messages": [HumanMessage(content="量子计算的最新进展是什么？")],
    "search_results": [],
    "iteration": 0
})

print(result["messages"][-1].content)
```

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a three-node agent workflow graph: left node "Think" (brain icon, entry point), center node "Search" (magnifying glass icon), right node "Answer" (speech bubble icon), with light blue #409EFF directional arrows showing the loop Think→Search→Think and the exit Think→Answer→END, a State card flowing along edges showing accumulating messages and search results, clean white background, dark blue #1a1a2e labels, rounded node shapes, academic diagram style.

---

## 条件路由与循环

LangGraph最强大的特性之一就是灵活的条件路由和循环机制。以下是几种常见的路由模式：

### 模式一：工具调用循环

这是最经典的ReAct模式实现：

```
Agent思考 → 需要工具？ → 执行工具 → Agent再思考 → 需要工具？ → ... → 给出最终回答 → 结束
```

### 模式二：质量控制循环

用于需要反复打磨输出的场景：

```
生成草稿 → 质量检查 → 不合格 → 修订 → 质量检查 → 合格 → 结束
```

### 模式三：多路分支

根据任务类型分派到不同的专业处理节点：

```
任务入口 → 路由判断 → 技术任务 → 技术处理节点
                    → 创作任务 → 创作处理节点
                    → 分析任务 → 分析处理节点
```

### 设置循环上限

循环是强大的，但也可能是危险的。始终设置循环上限：

```python
def safety_router(state):
    if state["iteration"] >= MAX_ITERATIONS:
        return "force_finish"  # 强制结束
    # 正常路由逻辑...
```

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of three routing pattern diagrams arranged vertically: top pattern "ReAct Loop" showing Agent and Tool nodes cycling with bidirectional arrows, middle pattern "Quality Control Loop" showing Generate→Review→Revise nodes in a cycle with a checkmark exit condition, bottom pattern "Multi-Branch Dispatch" showing a central diamond router splitting to three specialized nodes (Technical, Creative, Analytical) with icons, all in light blue #409EFF, clean white background, dark blue #1a1a2e labels, rounded shapes.

---

## 检查点与持久化

LangGraph内置的检查点（Checkpointing）机制是实现人机协作和故障恢复的关键。

### 基本用法

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# 使用SQLite存储检查点
memory = SqliteSaver.from_conn_string("checkpoints.db")
agent = workflow.compile(checkpointer=memory)

# 运行时会自动保存每步的状态
config = {"configurable": {"thread_id": "user_session_123"}}
result = agent.invoke(input_data, config)

# 可以随时恢复
saved_state = agent.get_state(config)
```

### 实际应用场景

1. **人机协作**：在关键决策点暂停，等待人类审批后继续
2. **故障恢复**：智能体执行到一半崩溃了，从检查点恢复而不是重来
3. **分支探索**：从某个检查点分出多个分支，探索不同的执行路径
4. **调试分析**：回溯查看智能体在每一步的完整状态

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a timeline-based checkpointing visualization: a horizontal agent execution path with numbered step markers (Step 1, Step 2, Step 3, Step 4) along it, save-point flag icons at each step connected to a database cylinder icon below representing SQLite storage, a pause icon between Step 2 and 3 showing "Human Approval" intervention, a branching fork from Step 2 exploring two alternate paths A and B, clean white background, light blue #409EFF timeline and save-point markers, dark blue #1a1a2e labels, rounded shapes.

---

## 何时使用LangGraph而非LangChain

选择LangGraph的明确信号：

1. **智能体需要多轮推理和行动**：不是一次性生成，而是需要反复思考和尝试
2. **工作流包含条件分支**：不同情况需要走不同的处理路径
3. **需要循环执行直到满足终止条件**：例如，搜索→阅读→搜索，直到收集到足够信息
4. **多个智能体需要协调调度**：需要一个"调度中心"根据不同情况将任务分派给不同智能体
5. **需要人机协作**：在流程中插入人工审核环节
6. **需要持久化和恢复**：长时间运行的任务需要断点续传能力

**LangChain更合适的场景**：
- 简单的线性数据处理流水线
- 一次性的文档处理（加载→分割→嵌入→存储）
- 不需要循环和分支的问答系统

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a decision flowchart: on the left side six scenario icons (multi-turn loop icon, branch fork icon, cycle refresh icon, multi-agent network icon, human-check icon, save-restore icon) feeding into a central diamond decision node labeled "Need Graph?", the diamond splits into two paths — right path "Use LangGraph" with a graph node icon and left path "Use LangChain" with a chain link icon, each path listing their ideal use cases below, clean white background, light blue #409EFF flow lines, dark blue #1a1a2e labels.

---

## 高级技巧

### 1. 并行节点执行

LangGraph支持并行节点，多个独立任务可以同时执行：

```python
# 添加并行节点
workflow.add_node("research_A", research_node_A)
workflow.add_node("research_B", research_node_B)

# 从router分叉
workflow.add_conditional_edges("router", fork, {
    "parallel": ["research_A", "research_B"]
})
```

### 2. 子图嵌套

可以将一个复杂的子流程封装为子图，在主图中作为单个节点使用：

```python
# 创建子图
subgraph = create_research_subgraph()

# 在主图中使用
workflow.add_node("deep_research", subgraph.compile())
```

### 3. 流式输出

LangGraph支持流式输出，让用户看到智能体的实时进展：

```python
for event in agent.stream(input_data, config):
    # 每个节点执行完触发一个事件
    node_name = event[0]
    node_output = event[1]
    print(f"[{node_name}] {node_output}")
```

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a triptych layout showing three advanced techniques: left panel "Parallel Nodes" with a router node forking into two simultaneous research nodes A and B then merging, center panel "Subgraph Nesting" with a magnified detail showing a mini-graph nested inside a larger graph node labeled "Deep Research", right panel "Streaming Output" with a vertical event pipeline showing node events flowing down with real-time labels "[think]→[search]→[answer]", clean white background, light blue #409EFF accents, dark blue #1a1a2e labels, rounded container shapes.

---

## 实践建议

1. **从简单图开始**：先用3-4个节点的小图验证想法，再逐步扩展
2. **始终设置循环上限**：防止智能体陷入无限循环消耗大量Token
3. **为每个节点添加日志**：记录节点的输入和输出，方便调试
4. **使用类型化的State**：清晰的State定义让图的行为更可预测
5. **测试每个节点独立运行**：确保每个节点函数都能正确处理各种输入
6. **渐进式增加复杂度**：先实现基本流程，再添加条件分支、循环、检查点

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of a numbered checklist card layout with six rounded tip cards in two rows of three, each card containing a thin-line icon and short label: "1 Start Simple" (seedling icon), "2 Set Loop Limit" (stopwatch icon), "3 Log Nodes" (notepad icon), "4 Typed State" (type tag icon), "5 Unit Test Nodes" (checkmark clipboard icon), "6 Iterate Gradually" (staircase arrow icon), clean white background, light blue #409EFF card borders, dark blue #1a1a2e text, academic learning atmosphere.

---

## 小结

LangGraph将智能体开发从"线性思维"提升到了"图思维"——让你能够用节点和边来描绘智能体的完整决策流程。通过State、Node和Edge三大核心概念的组合，你可以构建出从简单问答到复杂多智能体协作的各种应用。

随着A2A（Agent-to-Agent）等标准的推广，LangGraph的图结构思维将在构建大规模智能体系统中变得更加重要。掌握LangGraph，你就掌握了构建下一代智能体应用的核心工具。

开始你的LangGraph之旅吧：从一个简单的搜索智能体开始，逐步添加条件分支、循环和检查点，你会发现图结构带来的灵活性和控制力远超链式结构。

Image-Prompt(英文绘图词): A flat-design minimalist 2D vector illustration of an ascending staircase with five steps representing progressive complexity levels in LangGraph development: step 1 "Simple Chain" (single link icon), step 2 "Add Conditions" (branching diamond), step 3 "Add Loops" (circular arrow), step 4 "Add Checkpoints" (save-point flag), step 5 "Multi-Agent Graph" (network of interconnected nodes), a glowing star icon at the top, upward arrow on the side labeled "Graph Thinking", clean white background, light blue #409EFF staircase and accents, dark blue #1a1a2e labels, centered symmetric layout.
