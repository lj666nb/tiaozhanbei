# 项目 9：让图记住「上次说到哪了」——检查点与故障恢复

## 一、图目前存在的问题

前两节的图每次调用 `graph.invoke()` 都是**从零开始**的：

```python
# 第一次调用
graph.invoke({"question": "我想查订单", "thread_id": "user-1"})

# 第二次调用——图不知道第一轮问了什么！
graph.invoke({"question": "编号是 O-100", "thread_id": "user-1"})
```

第二轮的 `"编号是 O-100"` 在没有人名或订单号的上下文中毫无意义——但图无法把第一轮的状态延续到第二轮。这个问题和第二章的「模型失忆」是同源的，只不过现在状态是图级别的而非 HTTP 请求级别的。

### 三种「记忆」概念——别搞混了

> 🧠 **LangGraph 中有三种不同层次的「记住」机制，初学者最容易混淆：**
>
> | 机制 | 记住什么 | 存活范围 | 实现方式 |
> |------|---------|---------|---------|
> | **messages 列表** | 当前会话的对话历史 | 单次图调用内 | 状态中的 `messages` 字段 |
> | **Checkpointer（检查点）** | 图在每个节点执行后的**完整状态快照** | 跨多次 `invoke()` 调用 | `InMemorySaver` / `SqliteSaver` 等 |
> | **Store（长期存储）** | 跨会话的**用户偏好和知识** | 跨线程、跨会话 | LangGraph Store API |
>
> 本节关注的是 **Checkpointer**——让同一 `thread_id` 的多次 `invoke()` 调用共享状态。

### 本节目标

1. **先理解**：Checkpointer 的工作原理——什么是快照、什么是 thread_id
2. **再实现**：用 `InMemorySaver` 让图跨调用记住状态
3. **后模拟**：实现 `save_checkpoint` 和 `load_checkpoint` 函数
4. **最终验收**：多线程隔离 + 防御性复制 + 故障恢复

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

## 三、接入检查点

### 3.1 最小改动：加两行代码

```python
from langgraph.checkpoint.memory import InMemorySaver

# 1. 创建检查点保存器
checkpointer = InMemorySaver()

# 2. 编译时传入 checkpointer
graph = builder.compile(checkpointer=checkpointer)
```

### 3.2 调用时必须指定 thread_id

```python
# 每个用户/会话一个唯一的 thread_id
config = {"configurable": {"thread_id": "user-U100-session-1"}}

# 第一轮：问订单
result1 = graph.invoke(
    {"messages": [{"role": "user", "content": "我想查订单"}]},
    config=config,
)
# 图执行完毕后，状态快照自动保存

# 第二轮：补充信息（同一 thread_id，图能读取上一轮的状态）
result2 = graph.invoke(
    {"messages": [{"role": "user", "content": "编号是 O-100"}]},
    config=config,
)
# 图从上次保存的快照恢复，messages 中已经包含第一轮的内容
```

> 🧠 **`thread_id` 是什么？** 它是状态的**隔离键**。可以理解为「这是谁的第几通会话」。不同的 `thread_id` 之间状态完全隔离——用户 A 的对话不会串到用户 B。你和家人共用一个 Netflix 账号，但各自有不同的「观看历史」——`thread_id` 就是你的「用户 profile」。

### 3.3 检查点 API 逐项拆解

| 框架代码 | 作用 | 工程边界 |
|---------|------|---------|
| `InMemorySaver()` | 创建**进程内**检查点保存器 | 进程退出后数据消失——只适合开发和学习 |
| `builder.compile(checkpointer=...)` | 把保存器接入图的运行时 | 只有传了 checkpointer 的图才会保存状态快照 |
| `configurable.thread_id` | 指定本次调用属于哪个会话 | 必须稳定、唯一，并在服务端校验所属用户 |
| `graph.invoke(input, config=config)` | 在指定线程中执行，自动保存检查点 | 同一线程后续调用可读取已有状态 |
| `graph.get_state(config)` | 读取线程的**最新**状态快照 | `values` 是当前状态，`next` 是待执行节点列表 |

---

## 四、查看状态与时间旅行

```python
# 查看当前状态
snapshot = graph.get_state(config)
print("当前状态:", snapshot.values)   # 所有字段的当前值
print("下一节点:", snapshot.next)     # () 表示图已完成，('order',) 表示等待执行

# 查看状态历史（时间旅行）
history = list(graph.get_state_history(config))
for h in history:
    print(f"步骤 {h.config['configurable']['checkpoint_id']}: {h.values}")
```

检查点支持四种关键能力：
- **对话记忆**：多轮调用延续上下文
- **人工中断**：暂停执行，等待人工审核后继续
- **时间旅行**：回退到历史某个检查点重新执行
- **故障恢复**：节点执行失败后从上一个成功检查点恢复

---

## 五、线程与长期记忆不是一回事

> 🧠 **重要区分**：
> - **Checkpointer** 保存的是**单个会话线程**的状态——会话结束后通常可以清理
> - **Store** 保存的是**跨会话的持久数据**——比如用户的偏好设置、历史订单偏好、常用地址
>
> 不要把用户偏好（如「用户偏好简洁回答」）放在 Checkpointer 里——会话结束后这些信息就丢了。这类信息应该用 LangGraph 的 Store API 存储。

---

## 六、实现 `save_checkpoint` 和 `load_checkpoint`——理解底层机制

在实验室中，你需要独立实现一个简化版的 checkpointer：

```python
# solution.py —— 线程检查点系统
def save_checkpoint(store, thread_id, state):
    """保存线程状态快照，返回递增版本号。
    
    参数：
        store (dict): 全局存储，结构为 {thread_id: [snapshot1, snapshot2, ...]}
        thread_id (str): 线程标识，必须是非空字符串
        state (dict): 要保存的状态字典
    
    返回：
        int: 新快照的版本号（从 1 开始，按线程独立递增）
    
    设计要点：
        - 保存时必须对 state 做防御性复制（深拷贝列表和字典）
        - 每个线程的版本号独立递增
        - 同一线程多次保存不会覆盖之前的快照
    """
    import copy
    
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id 必须是非空字符串")
    if not isinstance(state, dict):
        raise ValueError("state 必须是字典")
    
    # 初始化线程的版本列表
    if thread_id not in store:
        store[thread_id] = []
    
    # 防御性复制：防止外部修改影响已保存的快照
    snapshot = copy.deepcopy(state)
    store[thread_id].append(snapshot)
    
    # 返回版本号（列表长度即为当前线程的版本数）
    return len(store[thread_id])


def load_checkpoint(store, thread_id):
    """读取线程的最新状态快照，返回防御性副本。
    
    参数：
        store (dict): 全局存储
        thread_id (str): 线程标识
    
    返回：
        dict or None: {"version": int, "state": dict}（最新快照的副本）
                     如果线程不存在或没有快照，返回 None
    
    设计要点：
        - 返回的是新副本——修改返回值不影响 store 中的原始快照
        - 不同线程之间的数据完全隔离（不能串话）
    """
    import copy
    
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id 必须是非空字符串")
    
    if thread_id not in store or not store[thread_id]:
        return None
    
    # 获取最新快照的版本号和内容
    latest = store[thread_id][-1]
    version = len(store[thread_id])
    
    # 返回防御性副本
    return {
        "version": version,
        "state": copy.deepcopy(latest),
    }
```

> 🧠 **为什么每次都做 `copy.deepcopy`？** 如果 `load_checkpoint` 直接返回 store 中的原始字典引用，调用方修改返回结果就会**悄悄污染已保存的检查点**。当故障恢复时，你拿到的「检查点」已经不是原始状态了——这会导致恢复不可信。**防御性复制是检查点系统的底线。**

<!-- lab-check:implementation -->

---

## 七、在 `app.py` 中验证线程隔离

```python
# app.py —— 检查点与线程隔离测试
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from solution import save_checkpoint, load_checkpoint

# 搭建简单图
def chat_node(state):
    messages = state.get("messages", [])
    last_msg = messages[-1]["content"] if messages else ""
    response = f"收到: {last_msg}"
    return {"messages": [{"role": "assistant", "content": response}]}

builder = StateGraph(dict)
builder.add_node("chat", chat_node)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)

graph = builder.compile(checkpointer=InMemorySaver())

# 两个不同用户的 thread_id
config_a = {"configurable": {"thread_id": "user-A"}}
config_b = {"configurable": {"thread_id": "user-B"}}

# 用户 A 对话
graph.invoke({"messages": [{"role": "user", "content": "我是小明"}]}, config=config_a)

# 用户 B 对话
graph.invoke({"messages": [{"role": "user", "content": "我是小红"}]}, config=config_b)

# 验证隔离：用户 A 的状态里应该只有小明的消息
state_a = graph.get_state(config_a)
state_b = graph.get_state(config_b)
print("用户A的最后消息:", state_a.values["messages"][-1]["content"])  # "收到: 我是小明"
print("用户B的最后消息:", state_b.values["messages"][-1]["content"])  # "收到: 我是小红"
# 两个用户互不干扰！
```

<!-- lab-check:integration -->

---

## 八、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| 第二轮调用看不到上一轮的消息 | 忘记传 `config` 参数，或 `thread_id` 变了 | 确认两次 `invoke()` 使用相同的 `thread_id` |
| 用户 A 的对话跑到用户 B 那里 | 所有请求共用了同一个 `thread_id`（如 `"default"`） | 为每个用户生成唯一 `thread_id`（如 `f"user-{user_id}-{session_id}"`） |
| 进程重启后检查点丢失 | 使用了 `InMemorySaver`（进程内存） | 生产环境切换到 `SqliteSaver` 或 `PostgresSaver` |
| 修改了 load 出的状态后保存被污染 | 没有做防御性复制 | 在 `load_checkpoint` 中使用 `copy.deepcopy()` |
| 状态中保存了不可序列化对象 | 把模型客户端、文件句柄放进了状态 | 状态中只放数据和简单类型 |

---

## 九、动手改造

1. 在 `save_checkpoint` 中加入最大版本数限制（如每个线程最多保留 10 个快照），超出时删除最旧的
2. 实现 `load_checkpoint_by_version(store, thread_id, version)` —— 支持读取指定版本而非仅最新
3. 把 `InMemorySaver` 替换为 `SqliteSaver`，观察进程重启后检查点是否仍然存在

---

## 十、下一步

图已经能记忆和恢复了。最后阶段加入**企业知识检索（RAG）**——让回答基于可追溯的证据，而不是模型的「记忆」。

[LangGraph 官方持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)

<!-- lab-check:acceptance -->
