# 项目 5：让模型学会「查资料」——工具调用入门

## 一、我们要解决什么问题

前几节中，模型只能凭它训练时学到的知识来回答问题。但现实中有大量信息模型不知道：

- 「订单 ORD-20260730-0001 的物流状态是什么？」——模型不可能知道你们公司的订单系统
- 「今天北京天气怎么样？」——模型的知识截止到训练日期
- 「把这份数据写入数据库」——模型不能直接操作外部系统

**工具调用（Tool Calling，也叫 Function Calling）** 就是解决这个问题的：让模型知道自己可以「请求」哪些外部工具，并在需要时生成结构化的调用请求。

### 工具调用的本质——模型并不「执行」任何东西

> 🧠 **关键概念（非常重要！）：模型本身不会调用任何函数。** 它的数据库、网络、文件系统都不在你的服务器上。工具调用的实际流程是：
>
> ```text
> 1. 你告诉模型：「我有一个 query_order 工具，参数是 order_id」
> 2. 模型判断这个问题需要查订单 → 生成 {"name": "query_order", "args": {"order_id": "ORD-20260730-0001"}}
> 3. 你的代码收到这个 JSON → 校验 → 真的调用 query_order("ORD-20260730-0001") → 把结果发回给模型
> 4. 模型读取结果 → 生成最终回答
> ```
>
> **模型只是生成了一个「调用建议」（一段结构化 JSON），你的代码才是真正执行的人。** 这意味着你必须校验模型生成的内容——它可能编造工具名、漏掉参数、或传入非法值。

### 本节目标

1. **先理解**：工具调用的完整链路——模型提议 → 代码校验 → 执行 → 结果返回
2. **再实现**：用 `@tool` 装饰器注册工具，用 `bind_tools()` 绑定到模型
3. **后提取**：实现 `execute_tool_call` 函数，统一处理校验和错误转换
4. **最终验收**：跑通「模型提议 → 服务端校验 → 执行业务函数」的完整链路

---

## 二、开始前：搭建本节项目

创建 `requirements.txt`、`.env.example`、`solution.py`、`app.py`。依赖声明 `langchain`、`langchain-openai`、`python-dotenv`。

<!-- lab-check:structure -->

```bash
python -m venv .venv
pip install -r requirements.txt
```

<!-- lab-check:environment -->
<!-- lab-check:dependencies -->

---

## 三、先写普通业务函数——业务逻辑不绑定框架

> 🧠 **工程原则**：业务逻辑（查数据库、算价格、调 API）应该写成**普通 Python 函数**。不要一开始就和 LangChain 耦合——这样你的业务代码可以在任何框架中使用，也更容易单独测试。

这里我们**对接项目 4 创建的持久化订单数据库**——它包含 10 条真实电商订单，后续所有项目共用这一份数据。

```python
# 对接项目4的持久化订单数据库（orders.db）
# 路径 ../2-1/orders.db：从当前项目目录向上一级，进入项目4的工作区
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

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
    """根据订单编号查询订单状态、快递公司和预计送达时间。"""
    order_id = order_id.strip()
    if not order_id:
        raise ValueError("order_id 不能为空")
    engine = create_engine('sqlite:///../2-1/orders.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if order is None:
            return {"status": "not_found", "message": f"订单 {order_id} 不存在"}
        return {
            "status": order.status,
            "carrier": order.carrier or "暂无",
            "eta": order.eta or "暂无",
            "customer_name": order.customer_name,
            "product": order.product,
        }
    finally:
        session.close()
```

---

## 四、把函数暴露给模型——`@tool` 装饰器

### 4.1 `@tool` 做了什么？

```python
from langchain.tools import tool

@tool
def query_order_tool(order_id: str) -> dict:
    """根据订单编号查询当前状态和物流信息。订单编号形如 ORD-20260730-0001。"""
    return query_order(order_id)
```

> 🧠 **`@tool` 装饰器自动提取了三种元数据**：
>
> | 来源 | 提取内容 | 用途 |
> |------|---------|------|
> | 函数名 `query_order_tool` | 工具名称 → `"query_order_tool"` | 模型用这个名字来指定调用哪个工具 |
> | 类型标注 `order_id: str` | 参数 Schema → `{"order_id": {"type": "string"}}` | 告诉模型这个工具需要什么参数 |
> | docstring `"""根据订单编号..."""` | 工具描述 → 给模型看的说明文 | **模型据此判断「什么时候该用这个工具」** |
>
> ⚠️ **docstring 不是普通注释！** 模型的工具选择完全依赖你写的描述文字。如果描述不清——比如写了「查询信息」而非「根据订单编号查询物流状态」——模型可能在应该用这个工具时却不调用它。

### 4.2 绑定工具到模型

```python
# bind_tools() 把工具 Schema 注入到模型中
# 此后模型「知道」了这些工具的存在，可以在需要时生成调用请求
model_with_tools = model.bind_tools([query_order_tool])

# 发起请求
response = model_with_tools.invoke("帮我查一下订单 ORD-20260730-0001 的状态")
```

> 🧠 **`bind_tools()` 做了什么？** 它把工具的参数 Schema（名称、描述、参数类型）注入到模型的 system prompt 中。模型看到这些信息后，遇到相关问题就会生成一个 `tool_calls` 列表。**`bind_tools()` 不会执行任何函数**——它只是「告知」模型有哪些工具可用。

### 4.3 读取模型的调用建议

```python
# response.tool_calls 是模型建议的工具调用列表
print(response.tool_calls)
# 输出类似：
# [{'name': 'query_order_tool',
#   'args': {'order_id': 'ORD-20260730-0001'},
#   'id': 'call_abc123'}]
```

> 🧠 **`tool_call` 的三个字段**：
> - `id`：本次调用的唯一标识——后续把执行结果发回模型时需要这个 ID 来对应
> - `name`：工具名——你需要在注册表中查找对应的处理函数
> - `args`：模型生成的参数——**必须校验**，模型可能生成不存在的字段名或非法值

---

## 五、校验并执行——模型不可信

### 5.1 为什么必须校验？

模型是一个语言模型，不是一个编译器。它可能：
- 编造一个不存在的工具名（幻觉）
- 漏掉必填参数
- 传入错误类型（把字符串当作数字）
- 参数中包含恶意内容

> 🧠 **安全原则：永远不要按模型返回的字符串动态导入或执行任意函数。** 工具注册表（`registry`）是白名单——只有在注册表中明确声明的工具才能被执行。这是防止模型恶意注入代码的关键防线。

### 5.2 实现 `execute_tool_call`——统一校验边界

```python
# solution.py —— 工具调用执行器
def execute_tool_call(tool_call, registry):
    """校验并执行模型生成的工具调用，返回统一格式的结果。
    
    参数：
        tool_call (dict): 模型生成的调用请求，含 name、args、id
        registry (dict): 工具注册表，格式为 {name: {"required": [...], "handler": fn}}
    
    返回：
        dict: 统一格式的工具消息，可直接追加到消息历史
              {role: "tool", tool_call_id: id, name: name,
               status: "success"|"error", content: str}
    
    异常：
        ValueError: tool_call 契约非法（缺字段、类型错误等）
    
    设计原则：
        1. 未知工具绝不执行（白名单机制）
        2. 工具自身异常不向上传播（转换为 error 状态）
        3. 返回结构统一，调用方无需判断不同工具的返回格式
    """
    # 1. 校验 tool_call 契约
    if not isinstance(tool_call, dict):
        raise ValueError("tool_call 必须是字典")
    
    name = tool_call.get("name")
    args = tool_call.get("args")
    call_id = tool_call.get("id")
    
    if not isinstance(name, str) or not name:
        raise ValueError("tool_call.name 必须是非空字符串")
    if not isinstance(args, dict):
        raise ValueError("tool_call.args 必须是字典")
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("tool_call.id 必须是非空字符串")
    
    # 2. 白名单检查：工具必须在注册表中
    if name not in registry:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "status": "error",
            "content": f"工具执行失败：未知工具 '{name}'。可用工具：{list(registry.keys())}",
        }
    
    tool_spec = registry[name]
    handler = tool_spec.get("handler")
    required = tool_spec.get("required", [])
    
    # 3. 检查必填参数
    missing = [p for p in required if p not in args]
    if missing:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "status": "error",
            "content": f"工具执行失败：缺少必填参数 {missing}",
        }
    
    # 4. 执行工具——隔离工具异常
    try:
        result = handler(**args)
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "status": "success",
            "content": str(result),
        }
    except Exception as exc:
        # 工具异常转换为 error 消息，不向上传播
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "status": "error",
            "content": f"工具执行失败：{exc}",
        }
```

> 🧠 **为什么工具异常不能向上抛？** 如果工具执行抛异常，整个 Agent 进程就崩溃了——用户看到的是一个错误页面，而不是「抱歉，订单查询暂时不可用，已为您转接人工」。把工具异常转换为 `status: "error"` 的消息，模型可以据此决定**重试、换个问法、或告知用户**。

<!-- lab-check:implementation -->

---

## 六、接入完整流程

在 `app.py` 中使用 `@tool` 注册工具，用 `execute_tool_call` 作为执行边界：

```python
# app.py —— 工具调用完整流程
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from solution import execute_tool_call

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0,
)

# 用 @tool 装饰器把业务函数注册为模型可调用的工具
@tool
def query_order_tool(order_id: str) -> str:
    """根据订单编号查询物流状态和预计送达时间。订单编号形如 ORD-20260730-0001。"""
    return query_order(order_id)  # 调用上面已定义的真实数据库查询

# 构建工具注册表
TOOL_REGISTRY = {
    "query_order_tool": {
        "required": ["order_id"],
        "handler": query_order_tool,
    }
}

# 绑定工具
model_with_tools = model.bind_tools([query_order_tool])

# 发起请求
messages = [{"role": "user", "content": "帮我查订单 ORD-20260730-0001"}]
response = model_with_tools.invoke(messages)

# 处理工具调用
if response.tool_calls:
    for tc in response.tool_calls:
        result = execute_tool_call(tc, TOOL_REGISTRY)
        messages.append({"role": "assistant", "content": "", "tool_calls": [tc]})
        messages.append(result)  # 工具结果写回消息历史
    
    # 模型读取工具结果后生成最终回答
    final = model.invoke(messages)
    print(final.content)
```

<!-- lab-check:integration -->

---

## 七、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| 模型不调用工具，直接回答 | docstring 描述不清，或问题不需要查数据 | 让问题明确需要工具才能回答（如「查订单 ORD-20260730-0001」） |
| 模型调用了不存在的工具名 | 幻觉——模型编造了工具名 | 始终用工具注册表白名单校验 |
| 返回结果后模型不继续回答 | 忘记把工具结果追加到 messages 中 | 确认 `messages.append(result)` |
| `tool_call_id` 不对应 | 工具结果写回了错误的 `tool_call_id` | 用原始 `tool_call["id"]` 作为 `tool_call_id` |
| 工具异常导致程序崩溃 | 异常没有被 try-except 捕获 | 在 `execute_tool_call` 中包裹 handler 调用 |

---

## 八、动手改造

1. 新增一个 `query_refund_policy` 工具，注册到同一模型，测试模型能否在两个工具中正确选择
2. 故意在 registry 中漏掉一个必填参数，观察 `execute_tool_call` 如何返回 error 而非崩溃
3. 把 `temperature` 设成 `0.0` vs `1.0`，用同一个需要工具的问题测试，观察工具调用成功率变化

---

## 九、下一步

手动处理工具调用（判断有没有 `tool_calls`、逐个执行、写回结果）太繁琐。下一节使用 LangChain 的 `create_agent`，它会自动完成「模型判断 → 调用工具 → 读取结果 → 决定是否继续」的循环。

[LangChain 官方工具文档](https://docs.langchain.com/oss/python/langchain/tools)

<!-- lab-check:acceptance -->
