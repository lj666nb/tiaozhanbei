# 项目 7：把代码变成图——LangGraph 状态图入门

## 一、为什么需要「图」？

到目前为止，我们的程序逻辑是「一条直线」：

```text
用户输入 → 构造消息 → 调用模型 → 输出结果
```

但真实业务不是直线。客服系统可能有多个分支：

```text
用户输入 → 意图识别 → 订单查询 → 查询结果 → 生成回答
                    → FAQ     → 知识检索 → 生成回答
                    → 闲聊    → 直接回答
                    → 紧急    → 转人工
```

用 `if/elif/else` 当然可以实现，但随着分支增多，代码会变成「意大利面条」——难以测试、难以观察、难以修改。

### 什么是状态图？

> 🧠 **关键概念：StateGraph（状态图）** 是一种**显式**的程序控制流描述方式。相比把逻辑藏在 `if/else` 和函数调用栈中，状态图把「有哪些步骤（节点）」「步骤之间怎么跳转（边）」「共享什么数据（状态）」都声明为可见的结构。
>
> **类比**：就像地铁线路图——每个站是节点，轨道是边，列车的位置是状态。你一眼就能看到所有可能的路线和当前在哪一站。而 `if/else` 版本就像文字导航——「第一个路口左转，第二个红绿灯右转……」——你需要逐行追踪才知道发生了什么。

```
普通代码:                      状态图:
def process(x):                 START → validate → classify → order → END
    x = validate(x)                                      ↘ faq ↗
    if x.type == "order":                                  ↘ chat ↗
        return handle_order(x)                             ↘ human ↗
    elif x.type == "faq":
        return handle_faq(x)
    ...
```

### `create_agent` vs 手写 `if/else` vs `StateGraph`

| 方式 | 控制力 | 可见性 | 适用场景 |
|------|:---:|:---:|------|
| `create_agent` | 低——模型自主决定 | 低——内部黑盒 | 简单工具循环，不需要精确分支控制 |
| 手写 `if/else` | 高——每步都控制 | 低——逻辑藏在代码中 | 简单流程，3 个以内分支 |
| `StateGraph` | 高——每步都控制 | **高——图结构可视化** | 多分支、需要审计、需要故障恢复的复杂流程 |

### 本节目标

1. **先理解**：图的三个核心概念——节点（Node）、边（Edge）、状态（State）
2. **再搭建**：用 `StateGraph` 搭建一个「规范化 → 生成回答」的两节点图
3. **后实现**：`merge_state` 函数——理解节点增量如何合并到全局状态
4. **最终验收**：图运行后返回包含 `trace` 的完整最终状态

---

## 二、开始前：搭建本节项目

创建 `requirements.txt`、`.env.example`、`solution.py`、`app.py`。本节依赖新增 `langgraph`：

```text
langgraph
langchain
langchain-openai
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

## 三、图的三个核心概念

### 3.1 状态（State）——节点之间共享的数据契约

```python
from typing import TypedDict

class SupportState(TypedDict, total=False):
    question: str              # 用户原始问题
    normalized_question: str   # 规范化后的问题
    answer: str                # 模型生成的回答
    trace: list[str]           # 执行轨迹（经过哪些节点）
```

> 🧠 **什么是 `TypedDict`？** 它是 Python 的类型提示机制——告诉类型检查器「这个字典应该有哪些 key、每个 key 是什么类型」。LangGraph 用它来定义状态的 Schema。`total=False` 表示字段都是可选的（不是每个节点都要填写所有字段）。
>
> ⚠️ **状态中不要放不可序列化的对象**——数据库连接、文件句柄、模型客户端等应通过闭包或全局变量访问，而不是塞进状态字典。

### 3.2 节点（Node）——执行具体工作的函数

```python
def normalize_node(state: SupportState):
    """规范化节点：清理输入，记录轨迹。"""
    question = state["question"].strip()
    if not question:
        raise ValueError("question 不能为空")
    # 返回「增量」——只返回本节点负责更新的字段
    return {
        "normalized_question": question,
        "trace": [*state.get("trace", []), "normalize"],
    }

def answer_node(state: SupportState):
    """回答节点：调用模型生成回答。"""
    response = model.invoke(state["normalized_question"])
    return {
        "answer": str(response.content),
        "trace": [*state.get("trace", []), "answer"],
    }
```

> 🧠 **节点返回的是「增量」（delta），不是完整状态。** 每个节点只返回自己负责更新的字段，LangGraph 负责把这些增量合并到全局状态中。这样做的好处是：你不需要在 `answer_node` 中记住 `normalized_question` 的值——它已经在状态里了，框架会保留它。

### 3.3 边（Edge）——节点之间的流向

```python
from langgraph.graph import StateGraph, START, END

# 创建图构建器
builder = StateGraph(SupportState)

# 注册节点
builder.add_node("normalize", normalize_node)
builder.add_node("answer", answer_node)

# 连接边——定义流向
builder.add_edge(START, "normalize")   # 图启动 → 规范化节点
builder.add_edge("normalize", "answer")  # 规范化 → 回答
builder.add_edge("answer", END)         # 回答 → 图结束

# 编译（校验 + 生成可运行图）
graph = builder.compile()
```

> 🧠 **`START` 和 `END` 是什么？** 它们是 LangGraph 提供的特殊标记——不是你定义的业务节点。`START` 表示图的入口（第一个执行的节点从它出发），`END` 表示图的出口（到达它的节点执行完后图就停止）。它们帮助 LangGraph 校验图的完整性——如果某个节点后面没有边连接，编译时就会报错。

---

## 四、运行这张图

```python
# 用初始状态调用图
result = graph.invoke({
    "question": "  如何退款？ ",
    "trace": [],
})

print(result["answer"])   # 模型的回答
print(result["trace"])    # ['normalize', 'answer'] —— 经过的节点
```

### `StateGraph` API 逐项拆解

| 框架代码 | 作用 | 返回 / 后续 |
|---------|------|------------|
| `StateGraph(SupportState)` | 创建以 `SupportState` 为状态契约的图构建器 | 此时只是描述框架，还不能运行 |
| `builder.add_node("name", func)` | 注册节点——名字 + 可调用函数 | 节点接收当前状态，返回增量字典 |
| `builder.add_edge(a, b)` | 声明固定流向：a 完成后一定去 b | 只负责连线，不负责合并状态 |
| `builder.compile()` | **校验**图结构（无孤立节点、有起止点），生成可运行图 | 返回的 `graph` 对象有 `invoke()`、`stream()` 等方法 |
| `graph.invoke(input)` | 用初始状态运行整张图，直到抵达 `END` | 返回合并后的**完整**最终状态（不只是最后一个节点的返回） |

---

## 五、实现 `merge_state`——理解状态合并

在实验室中，`merge_state` 是你需要独立实现的核心函数。LangGraph 在后台做状态合并，理解它的逻辑对后续复杂图的调试至关重要。

```python
# solution.py —— 状态合并器
def merge_state(current, update, reducers=None):
    """模拟 LangGraph 将节点增量合并进当前状态。
    
    参数：
        current (dict): 当前全局状态
        update (dict): 节点的返回增量
        reducers (dict, optional): 字段合并策略，如 {"messages": "append"}
    
    返回：
        dict: 合并后的新状态（不修改 current 和 update）
    
    合并规则：
        - reducers 中声明为 "append" 的字段：将旧列表与新列表拼接
        - 其他字段：直接覆盖（update 中的值覆盖 current 中的值）
        - 始终返回新字典——输入对象不受影响
    """
    if reducers is None:
        reducers = {}
    
    # 1. 创建 current 的浅拷贝
    result = dict(current)
    
    # 2. 逐字段应用合并规则
    for key, value in update.items():
        if key in reducers and reducers[key] == "append":
            # append 语义：拼接列表
            old_list = current.get(key, [])
            if not isinstance(old_list, list) or not isinstance(value, list):
                raise ValueError(f"append reducer 要求字段 '{key}' 的值必须是列表")
            result[key] = old_list + value  # 创建新列表（不修改原列表）
        else:
            # 覆盖语义：直接覆盖
            result[key] = value
    
    return result
```

> 🧠 **为什么需要 reducer？** 考虑 `trace` 字段——节点 A 返回 `trace: ["validate"]`，节点 B 返回 `trace: ["answer"]`。如果直接覆盖，最终 trace 只剩 `["answer"]`。使用 `append` reducer 后，最终 trace 是 `["validate", "answer"]`——完整保留了执行轨迹。

<!-- lab-check:implementation -->

---

## 六、在 `app.py` 中搭建最小图

```python
# app.py —— 你的第一张 LangGraph 状态图
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from solution import merge_state

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0.2,
)

class SupportState(dict):
    """简化版状态——使用普通 dict 而非 TypedDict，便于理解。"""
    pass

def normalize_node(state):
    question = state.get("question", "").strip()
    if not question:
        return {"error": "question 不能为空"}
    return {"normalized_question": question, "trace": ["normalize"]}

def answer_node(state):
    response = model.invoke(state["normalized_question"])
    return {"answer": str(response.content), "trace": ["answer"]}

# 搭图
builder = StateGraph(SupportState)
builder.add_node("normalize", normalize_node)
builder.add_node("answer", answer_node)
builder.add_edge(START, "normalize")
builder.add_edge("normalize", "answer")
builder.add_edge("answer", END)

graph = builder.compile()

# 运行
result = graph.invoke({"question": "什么是 LangGraph？用一句话解释。"})
print("回答:", result.get("answer"))
print("轨迹:", result.get("trace"))
```

<!-- lab-check:integration -->

---

## 七、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| `KeyError: 'normalized_question'` | `answer_node` 依赖了前一个节点的输出，但前节点未返回该字段 | 检查每个节点的返回字典是否包含后续节点需要的 key |
| `InvalidGraphError` | 图中存在孤立节点（没有边连接），或缺少 `START`/`END` | 确认每个节点都有入边和出边（除非是起止点） |
| 最终状态中 trace 不完整 | 后一个节点覆盖了前一个节点的 trace | 使用 `{"trace": [*state["trace"], "new_node"]}` 而非 `{"trace": ["new_node"]}` |
| 状态字段互相覆盖 | 两个节点都返回了同名但不同含义的字段 | 为不同阶段使用不同字段名（如 `raw_question` vs `normalized_question`） |
| `compile()` 报错但不知道哪里 | 图结构存在循环但无 `END` 条件 | 使用条件边（下一节）或在循环中加入终止逻辑 |

---

## 八、动手改造

1. 在 `normalize_node` 和 `answer_node` 之间插入一个 `classify_node`，根据关键词（如包含「退款」→ 标记为 refund 类）给状态增加 `category` 字段
2. 修改 `merge_state` 支持一个新的 reducer 类型：`"merge"` —— 将两个字典深度合并（而非简单覆盖）
3. 把 `trace` 改为 `append` reducer，用 `merge_state` 合并两次节点返回

---

## 九、下一步

当前图只有一条直线。下一节用**条件边（Conditional Edges）** 把咨询分流到订单、知识库或人工节点——让图真正「分叉」。

[LangGraph 官方 Graph API 文档](https://docs.langchain.com/oss/python/langgraph/graph-api)

<!-- lab-check:acceptance -->
