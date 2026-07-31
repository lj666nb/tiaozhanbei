# 项目 1：用 LangChain 发出第一条 AI 消息

## 一、我们要做什么

> 你已经掌握了 Python 基础（函数、列表、字典、if/else）。现在我们要做一件很酷的事：**让 AI 模型回答你的问题**。

### LangChain 是什么？

**LangChain = Language + Chain（语言链）**。它是一个把大语言模型（LLM）相关的各种组件像链条一样串联起来的 Python 框架。这些组件包括：

| 组件 | 干什么用 |
|------|---------|
| 提示词模板 | 把用户输入 + 系统指令组装成模型能理解的格式 |
| 聊天模型 | 封装 HTTP 请求，统一调用 DeepSeek / OpenAI / 本地模型 |
| 工具调用 | 让模型能查数据库、调 API、执行代码 |
| 记忆存储 | 记住之前的对话，实现多轮聊天 |
| 嵌入模型 + 向量检索 | 从知识库中搜索相关内容（RAG） |
| Agent 循环 | 让模型自主决定「下一步该调哪个工具」 |

**如果没有 LangChain**，你需要自己写 HTTP 请求、处理流式响应、管理对话历史、实现工具调用协议……LangChain 帮你把底层细节封装好，让你专注于**组合组件**而非重复造轮子。

> 💡 这个名字本身就揭示了它的核心设计理念：**用 Chain（链）把 Language（语言）相关的组件编排起来**。

### 本节目标

在编程中，和 AI 模型对话就像寄信——你不能随便写一段话发过去，而要按照约定的**消息格式**（role + content）来组织内容。本节的目标就是：

1. **先跑通**：写一个能直接运行的 `app.py`，调用 AI 模型并看到回复
2. **再整理**：把消息构造逻辑提取为可测试的 `build_chat_messages` 函数
3. **后重构**：让 `app.py` 调用提取出的函数，保持行为不变

完整的调用链只有 5 步：

```text
你的输入 → 构造消息列表 → ChatOpenAI 模型 → model.invoke() → AIMessage.content（AI 的回复）
```

---

## 二、准备工作：搭好项目骨架

### 2.1 创建项目文件

在编程实验室左侧「引导教程」面板中，跟随阶段指引完成任务。先创建 4 个文件：

```text
first-agent/
├── requirements.txt   ← 声明项目需要哪些包
├── .env               ← 存放真实密钥（不提交到 Git）
├── .env.example       ← 密钥模板（提交到 Git，方便队友知道需要哪些变量）
├── solution.py        ← 可测试的核心函数（稍后创建）
└── app.py             ← 可运行的主程序
```

在你的项目区中按这个名称创建文件。

<!-- lab-check:structure -->

### 2.2 创建虚拟环境

虚拟环境让本项目的依赖包与系统 Python 隔离开，互不影响。在终端依次执行：

```bash
python -m venv .venv
```

创建成功后，终端提示符前面会出现 `(.venv)` 标记，表示当前在这个隔离环境中工作。

> 💡 **为什么需要虚拟环境？** 假设项目 A 需要 `langchain==1.0`，项目 B 需要 `langchain==0.3`。如果都装在系统 Python 里就会冲突。虚拟环境给每个项目一个独立的「小 Python」，互不干扰。

<!-- lab-check:environment -->

### 2.3 安装 LangChain 依赖

在 `requirements.txt` 中写入以下内容（每行一个包名）：

```text
langchain>=1.0
langchain-openai>=1.0
python-dotenv>=1.0
```

然后在终端安装：

```bash
pip install -r requirements.txt
```

> 💡 **这三个包各自干什么？**
>
> | 包名 | 职责 | 一句话理解 |
> |------|------|-----------|
> | `langchain` | 核心框架 | 提供统一的消息格式、Chain 编排、Prompt 模板——所有 LangChain 应用的基石 |
> | `langchain-openai` | 模型适配器 | 把 DeepSeek / OpenAI 等模型的 HTTP API 封装成统一的 Python 对象，让你用 `model.invoke()` 一行代码发起调用 |
> | `python-dotenv` | 密钥加载器 | 从 `.env` 文件读取 `LLM_API_KEY=sk-xxx` 并注入到 `os.getenv()`，这样代码里永远不出现真实 Key |

> 🧠 **为什么 `langchain-openai` 的类名叫 `ChatOpenAI` 却能接入 DeepSeek？** 因为 OpenAI 定义了一套 HTTP API 协议（请求格式、响应格式、认证方式），DeepSeek 等厂商按同样的协议实现了自己的服务——这叫 **「协议兼容」**。`ChatOpenAI` 适配的是这套**协议**，不是 OpenAI 这家**公司**。只要服务端遵守同一套协议，改一下 `base_url` 就能切换模型提供商。

<!-- lab-check:dependencies -->

---

## 三、写出第一版能跑的代码

### 3.1 安全配置密钥（`.env` 文件）

API Key 就像你的银行卡密码——泄露了别人就能以你的名义调用模型，产生费用。

**正确做法**：

**① 创建 `.env.example`（提交到 Git）**——告诉队友这个项目需要哪些环境变量：

```properties
# .env.example —— 项目所需环境变量模板（可安全提交到 Git）
LLM_API_KEY=你的Key填在这里
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

**② 复制一份为 `.env`（不提交到 Git）**——填入你的真实值：

```properties
# .env —— 你的真实配置（已在 .gitignore 中，不会被提交）
LLM_API_KEY=sk-abc123你的真实Key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

**③ 确保 `.gitignore` 中包含 `.env`**：

```text
.env
.venv/
__pycache__/
```

> ⚠️ **绝对禁止**把真实 Key 写进 `app.py` 或 `solution.py`。Git 会永久记录每一次提交，即便你后来删掉，别人仍能从历史中翻出你的 Key。**`.env.example` + `.gitignore` 是业界标准做法。**

### 3.2 写下第一段 LangChain 代码（`app.py`）

现在，在 `app.py` 中写下以下代码。**先不创建 `solution.py`**——我们先把整个调用链跑通再说。

```python
# app.py —— 你的第一段 AI 对话程序
import os
from dotenv import load_dotenv          # 从 .env 读取配置
from langchain_openai import ChatOpenAI  # OpenAI 兼容协议的聊天模型适配器

# 1. 加载 .env 中的密钥和配置
load_dotenv()

api_key = os.getenv("LLM_API_KEY")
if not api_key:
    raise RuntimeError("缺少 LLM_API_KEY，请先在 .env 中填写你的 API Key")

# 2. 创建模型客户端（此时只是保存配置，还不会发起网络请求）
model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=api_key,
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0.2,   # 控制回答的随机程度，0=确定、1=发散（见下文详解）
    timeout=30,        # 单次请求最长等待 30 秒
    max_retries=2,     # 网络瞬时故障时自动重试 2 次（不能修复错误的 Key）
)

# 3. 构造消息列表
#    ChatGPT 出现后，业界统一了多轮对话的消息格式：
#    - system:  系统指令，定义 AI 的角色、语气、边界（「你是谁」「怎么回答」）
#    - user:    用户说的话（本轮问题）
#    - assistant: AI 的回答（多轮对话时把历史回复放在这里）
#    这种三段式角色协议让模型能区分「规则」「问题」和「历史回复」
messages = [
    {"role": "system", "content": "你是一位耐心的 Python 助教，回答控制在 120 字以内。"},
    {"role": "user", "content": "请用一个生活例子解释 AI Agent。"},
]

# 4. 发起调用（这里才真正联网请求模型）
#    invoke() 是「同步调用」——发请求，等回复，拿到结果后才继续执行下一行
#    与之对应的是 stream()（流式调用），后续关卡会用到
response = model.invoke(messages)

# 5. 打印 AI 的回复正文
#    invoke() 返回的是一个 AIMessage 对象，不是普通字符串
#    正文在 .content 属性中，对象还包含 token 用量、结束原因等元数据
print(response.content)
```

**`temperature` 到底是什么？** 模型生成每个词时，实际上是从一个概率分布中采样——比如在「你好」后面，模型认为下一个词是「！ 」的概率为 60%，「。」的概率为 30%，「啊」的概率为 2%。`temperature` 控制这个分布的「平滑程度」：

| temperature | 效果 | 适合场景 |
|:--:|------|------|
| 0.0~0.2 | 几乎总是选概率最高的词，回答稳定、可预测 | 代码生成、事实问答、客服 |
| 0.5~0.7 | 中等随机性，有一定多样性但不离谱 | 日常对话、翻译 |
| 0.8~1.0 | 低概率词也有机会被选中，回答更「有创意」但也可能跑偏 | 创意写作、头脑风暴 |

在终端运行：

```bash
python app.py
```

如果一切正常，你会看到 AI 用中文回复了一段关于 AI Agent 的生活化解释。

> 🎉 **恭喜！你刚刚完成了人生中第一次程序化 AI 调用。** 虽然代码不多，但这 5 步——加载配置、创建客户端、构造消息、发起调用、读取结果——是所有 AI 应用的基础骨架，后续无论多复杂的 Agent 系统都离不开它。

<!-- lab-check:first_llm_call -->

---

## 四、理解刚才的代码做了什么

先不急着重写。我们停下来搞清楚每一行框架代码的**工程含义**——以后你会反复用到它们。

| 框架代码 | 它在做什么 | 为什么这样设计 |
|---|---|---|
| `load_dotenv()` | 读取 `.env` 文件，把 `KEY=VALUE` 注入到当前进程的环境变量中 | 把**敏感配置从代码中分离**——代码是公开的（可提交 Git），配置是私有的（每人一份 `.env`） |
| `ChatOpenAI(...)` | 创建一个模型客户端对象，保存模型名、地址、超时等配置 | **只是保存配置，不发起网络请求**——真正调用发生在 `invoke()` 那一刻。这让你可以创建一次、多次复用 |
| `model.invoke(messages)` | 把消息列表序列化为 HTTP 请求体，发给模型服务器，等待完整响应 | **同步阻塞调用**：代码会停在这里直到模型返回完整结果。这是最简单但最直观的调用方式 |
| `response.content` | 从返回的 `AIMessage` 对象中提取纯文本正文 | `response` 对象除了正文还包含 `response_metadata`（token 用量、模型名、finish_reason 等），直接 `print(response)` 会输出一大串 |

### `invoke()` vs `stream()` —— 两种调用方式的本质区别

| | `invoke()` | `stream()` |
|---|---|---|
| 等待方式 | 等模型生成**全部**内容后一次性返回 | 模型每生成一个词就立即返回一个片段 |
| 用户体验 | 用户盯着空白屏幕等，然后一下子看到完整回答 | 用户看到文字逐字「打出来」，像 ChatGPT 那样 |
| 代码复杂度 | 简单，一行完事 | 需要 `for chunk in model.stream(...)` 循环处理 |
| 本节用哪个 | ✅ 本节用 `invoke()` | 下一节和 1-3 关卡会用到 |

---

## 五、提取消息构造函数——从「能用」走向「可测试」

### 5.1 为什么要提取？

目前 `app.py` 中的消息列表是写死的：`"你是一位耐心的 Python 助教..."`。真实应用中：
- 每个用户问的问题不同 → `user_input` 每次都变
- 不同场景需要不同的系统指令 → `system_prompt` 也需要灵活配置

**更关键的是**：如果消息构造逻辑混在 `app.py` 里，我们没法**单独测试**它——每次验证都得真的调用一次模型（又慢又花钱）。把纯数据处理的逻辑提取为独立函数后，测试不需要联网，毫秒级跑完全部用例。

> 🧠 **工程思维**：把「和外部系统交互的代码」（I/O）与「纯数据变换的代码」（业务逻辑）分开。前者难以自动测试，后者可以。`build_chat_messages` 是纯数据变换——给定输入、返回输出，不涉及网络——所以非常适合独立测试。

### 5.2 实现 `build_chat_messages`

创建 `solution.py`，写入以下代码：

```python
# solution.py —— 消息构造函数（可独立测试，无需联网）
def build_chat_messages(system_prompt, user_input):
    """生成可直接交给 LangChain ChatModel 的消息列表。

    参数：
        system_prompt (str): 系统指令，定义 AI 的角色和边界
        user_input (str): 用户本轮的问题

    返回：
        list[dict]: 两个字典组成的列表，按 system → user 顺序排列。
        每项包含 role 和 content 字段，content 已清理首尾空白。

    异常：
        ValueError: 任一参数不是非空字符串（含仅由空白组成的情况）
    """
    # 1. 校验：两个参数都必须是 str 类型
    #    这是「输入门禁」——在数据进入处理逻辑之前先过滤掉非法值
    if not isinstance(system_prompt, str):
        raise ValueError("system_prompt 必须是字符串")
    if not isinstance(user_input, str):
        raise ValueError("user_input 必须是字符串")

    # 2. 清理首尾空白（空格、换行、制表符等）
    #    .strip() 返回新字符串，不改变调用方传入的原变量
    system_clean = system_prompt.strip()
    user_clean = user_input.strip()

    # 3. 校验：清理后不能是空字符串
    #    必须放在 .strip() 之后——"   " 看起来有内容，实际是空的
    if not system_clean:
        raise ValueError("system_prompt 不能为空（仅含空白字符也不行）")
    if not user_clean:
        raise ValueError("user_input 不能为空（仅含空白字符也不行）")

    # 4. 返回全新的消息列表
    #    每次调用都创建新列表——如果用缓存或全局变量，
    #    第二次调用会混入上一次的数据（这是 Python 新手最常见的坑之一）
    return [
        {"role": "system", "content": system_clean},
        {"role": "user", "content": user_clean},
    ]
```

**设计要点**（这些是后续 17 个测试点会验证的）：

- ✅ **输入校验在前**：先检查类型和非空，再处理数据——防止「垃圾进、垃圾出」
- ✅ **每轮创建新列表**：不能用缓存或全局变量，否则第二次调用会混入上一次的数据
- ✅ **清理但不修改原值**：`.strip()` 返回新字符串，调用方传入的变量不受影响
- ✅ **仅含空白的字符串视为空**：`"   "` 经过 `.strip()` 后是 `""`，应当拒绝——这体现了「先清洗再判断」的防御性编程原则

在编程实验室中点击阶段检查，系统会运行 17 个测试点，覆盖正常输入、边界情况和各种非法输入。

<!-- lab-check:implementation -->

---

## 六、重构 app.py——接入提取好的函数

现在 `build_chat_messages` 已经通过全部测试了，我们来重构 `app.py`，把原来写死的消息列表替换为函数调用。

> 🧠 **什么是重构？** 重构 = **在不改变程序外部行为的前提下，改善内部结构**。重构前后，运行 `python app.py` 的输出应该完全一致。如果输出变了，说明重构过程中引入了 bug。

修改 `app.py`，在文件顶部增加一行 import，然后把 `messages = [...]` 替换为函数调用：

```python
# app.py —— 重构版：使用提取出的消息构造函数
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from solution import build_chat_messages   # ← 新增：导入我们提取的函数

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
if not api_key:
    raise RuntimeError("缺少 LLM_API_KEY，请先在 .env 中填写你的 API Key")

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=api_key,
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0.2,
    timeout=30,
    max_retries=2,
)

# ← 重构点：用函数调用替代原来写死的消息列表
#   原来：messages = [{"role": "system", "content": "..."}, {"role": "user", ...}]
#   现在：一行函数调用，system_prompt 和 user_input 作为参数传入
messages = build_chat_messages(
    "你是一位耐心的 Python 助教，回答控制在 120 字以内。",
    "请用一个生活例子解释 AI Agent。",
)

response = model.invoke(messages)
print(response.content)
```

在终端再次运行 `python app.py`，输出应该和重构前**完全一致**——这说明重构成功，外部行为没有退化。

<!-- lab-check:integration -->

---

## 七、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|---|---|---|
| `401 Unauthorized` | API Key 无效，或 Key 与 Base URL 不属于同一服务 | 确认 `.env` 中的 Key 是从对应平台的控制台复制的；检查 Base URL 是否匹配 |
| `model not found` | 模型名不存在或你的账户无权访问 | 检查 `LLM_MODEL` 是否是该平台支持的模型名（如 DeepSeek 用 `deepseek-chat`） |
| 一直超时 | 网络不通、代理问题、或模型响应太慢 | 先用最短问题测试（几个字）；检查是否需要配置代理；确认 `timeout=30` 不是设得太短 |
| 打印出来一大串复杂对象 | 打印了 `response`（整个对象）而非 `response.content`（仅正文） | 改成 `print(response.content)` |
| `ModuleNotFoundError` | 依赖未安装，或终端不在虚拟环境中 | 确认终端提示符有 `(.venv)` 前缀；重新执行 `pip install -r requirements.txt` |

---

## 八、动手改造

1. 把 `app.py` 中写死的问题改为 `input("你：")`，让用户每次可以输入不同的问题
2. 如果用户直接按回车（空输入），给出友好提示并重新询问——你已经在 `build_chat_messages` 中实现了空值校验，这里可以复用
3. 试试把 `temperature` 改成 `0.1` 再改成 `0.9`，用同一个问题分别运行，观察 AI 回答风格有什么不同

---

## 九、下一步

当前程序每次运行完就「失忆」了——下一次启动时记不住之前聊过什么。下一节我们将实现**多轮对话**：把用户和 AI 的每一轮问答保存为一个 `messages` 列表，让模型能「记住」上下文，实现真正的连续追问。

[LangChain 官方模型文档](https://docs.langchain.com/oss/python/langchain/models)

<!-- lab-check:acceptance -->
