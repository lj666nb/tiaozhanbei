# 项目 4：把客服规则做成可复用的提示模板

## 一、我们要解决什么问题

到目前为止，我们的 system prompt 是直接写在代码里的：

```python
messages = [
    {"role": "system", "content": "你是电商客服。规则：1. 不猜测订单状态；2. ……"},
    {"role": "user", "content": f"用户编号：{user_id}\n问题：{question}"},
]
```

这有一个问题：**业务规则和用户数据混在了一起**。如果客服规则需要调整（比如增加「退款政策」），你得在代码中翻找字符串，容易改漏。更关键的是——同一个模板要给不同用户使用，每次都手工拼字符串，既容易出错又难以测试。

### 什么是提示模板？

> 🧠 **关键概念：Prompt Template（提示模板）** 是把「不变的结构」和「变化的数据」分离的设计模式。模板定义消息的骨架和角色，变量（`{user_id}`、`{question}`）是调用时填入的动态数据。
>
> **类比**：就像 Mad Libs（填空游戏）——模板是「__(人名)__ 去 __(地点)__ 买 __(物品)__」，每次填入不同的人名、地点、物品就得到不同的句子。

```
模板: "用户{user_id}咨询：{question}"
       ↓ 传入 {"user_id": "U-100", "question": "如何退款？"}
结果: "用户U-100咨询：如何退款？"
```

### LangChain 的提示模板与 LCEL 管道

> 🧠 **LCEL（LangChain Expression Language）** 是 LangChain 的组合式 API。它最核心的符号是 `|`（管道符）——把两个组件连接起来：**左边组件的输出自动成为右边组件的输入**。
>
> ```python
> chain = prompt_template | model
> #        ↑ 渲染变量→消息列表  ↑ 消息列表→调用模型→AIMessage
> ```
>
> `|` 不是 Python 的位运算符（虽然借用了同一个符号），而是在 LangChain Runnable 协议下**组合两个可执行组件**。以后你还可以继续往后接：`prompt | model | output_parser`，形成处理流水线。

### 本节目标

1. **先理解**：提示模板的「契约」概念——调用时必须提供哪些变量
2. **再使用**：用 `ChatPromptTemplate.from_messages()` 创建可复用模板，通过 `|` 组成链
3. **后实现**：独立写出 `render_support_prompt` 函数，理解模板渲染的内部逻辑
4. **最终验收**：同一模板处理三种不同的用户输入

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

## 三、用 LangChain 创建客服提示模板

### 3.1 定义模板

```python
from langchain_core.prompts import ChatPromptTemplate

# 模板只定义结构和角色，不包含具体用户数据
support_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是电商客服。
规则：
1. 不猜测订单状态——没有查到就是没有查到；
2. 信息不足时先追问，不要凭经验补全；
3. 回答末尾给出明确的下一步操作。"""),
    ("user", "用户编号：{user_id}\n问题：{question}"),
])
```

> 🧠 **`ChatPromptTemplate.from_messages()` 做了什么？** 它接收一组 `(role, template_string)` 元组，编译成一个**带变量契约的模板对象**。花括号 `{user_id}` 和 `{question}` 成为调用时必须提供的变量——漏传会直接报错，不会等到模型调用才发现。

### 3.2 用管道符组成一条链

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0.2,
)

# | 是 LCEL 管道符：模板输出 → 模型输入
chain = support_prompt | model

# 调用时只需传入变量字典
result = chain.invoke({
    "user_id": "U-100",
    "question": "退款一般需要多久？",
})

print(result.content)
```

> 🧠 **管道符 `|` 的工程含义**：在 LangChain 中，每个组件都是 `Runnable`（可执行对象）。`a | b` 创建一个新的 Runnable，执行时先把输入传给 `a`，把 `a` 的输出作为 `b` 的输入。它类似 Unix 管道的思想（`cat file | grep keyword`），但连接的是 Python 对象。

### 3.3 理解每个组件在做什么

| 框架代码 | 输入 | 输出 | 在链条中的角色 |
|---------|------|------|--------------|
| `ChatPromptTemplate.from_messages(...)` | `(role, template)` 元组列表 | 编译后的模板对象（含变量契约） | 定义消息的**结构和角色**，声明需要的变量 |
| `support_prompt \| model` | 左侧 Runnable + 右侧 Runnable | 新的 Runnable 链 | **连接**两个组件，让数据自动流转 |
| `chain.invoke({...})` | 与模板变量对应的字典 | `AIMessage`（模型回复） | **触发**执行：渲染模板 → 调用模型 → 返回结果 |

---

## 四、先在边界校验输入——不要浪费 API 调用

### 4.1 为什么要在调用模型之前校验？

> 🧠 **工程思维：每一次失败的 API 调用都是真金白银。** 如果 `user_id` 是空字符串，与其让模型收到一条残缺消息然后胡言乱语（或报错），不如在代码入口就拦截。这不仅是节省费用，更是让错误信息**对开发者有意义**（「user_id 不能为空」比「模型返回了奇怪的东西」有用得多）。

```python
def ask_support(chain, user_id, question):
    """安全调用客服链：先校验，再请求模型。"""
    # 1. 统一转为字符串（防御：调用方可能传了数字）
    user_id = str(user_id).strip()
    question = str(question).strip()
    
    # 2. 门禁校验：在调用模型之前拦截非法输入
    if not user_id or not question:
        raise ValueError("user_id 和 question 不能为空")
    
    # 3. 通过校验后才发起模型调用
    return chain.invoke({
        "user_id": user_id,
        "question": question,
    }).content
```

### 4.2 实现 `render_support_prompt`——理解模板的底层逻辑

实验室中的核心函数叫 `render_support_prompt`。它不依赖 LangChain——你要独立实现模板渲染，这能帮你理解 `ChatPromptTemplate` 内部到底做了什么：

```python
# solution.py —— 安全模板渲染器
import re

def render_support_prompt(template, values):
    """安全渲染客服提示模板，不使用 eval。
    
    参数：
        template (str): 含 {field} 占位符的模板字符串
        values (dict): 字段名 → 字段值的映射
    
    返回：
        str: 所有占位符被替换后的字符串
    
    异常：
        ValueError: 模板不是非空字符串、values 不是字典、
                   缺少字段、包含非法占位符等
    
    设计要点：
        - 禁止使用 eval / exec —— 模板来自配置文件，不可执行任意代码
        - 重复占位符全部替换（如 "用户{id}咨询{id}" 中 {id} 出现两次）
        - values 中的额外字段不影响结果（只替换模板中出现的字段）
        - 所有值统一转为字符串（str(value)）
    """
    # 1. 输入校验
    if not isinstance(template, str) or not template.strip():
        raise ValueError("template 必须是非空字符串")
    if not isinstance(values, dict):
        raise ValueError("values 必须是字典")
    
    # 2. 扫描模板中的所有占位符
    placeholders = re.findall(r'\{(\w+)\}', template)
    
    # 3. 检查每个占位符是否都有对应的值
    for field in placeholders:
        if field not in values:
            raise ValueError(f"缺少必填字段: {field}")
    
    # 4. 安全替换（不使用 eval，直接用 str.replace）
    result = template
    for field in placeholders:
        # 用占位符的完整形式做替换，避免部分匹配
        result = result.replace(f'{{{field}}}', str(values[field]))
    
    return result
```

> 🧠 **为什么禁止使用 `eval`？** `eval()` 可以执行任意 Python 代码。如果模板来自用户输入或配置文件，攻击者可以注入 `{__import__('os').system('rm -rf /')}` 这样的恶意代码。`str.replace()` 只做文本替换，不执行代码。

<!-- lab-check:implementation -->

---

## 五、小项目改造——让模板更灵活

为模板增加两个维度的可配置性：渠道（网页/电话）和语气（简洁/详细）。

### 5.1 升级模板

```python
support_prompt_v2 = ChatPromptTemplate.from_messages([
    ("system", """你是{channel}客服。回答风格：{tone}。
规则：
1. 不猜测订单状态；
2. 信息不足时先追问；
3. 回答末尾给出下一步操作。"""),
    ("user", "用户编号：{user_id}\n问题：{question}"),
])
```

### 5.2 运行对比测试

```python
# 场景1：网页渠道 + 简洁风格
print(chain.invoke({
    "channel": "网页",
    "tone": "简洁",
    "user_id": "U-100",
    "question": "退款需要多久？",
}).content)

# 场景2：电话渠道 + 详细风格
print(chain.invoke({
    "channel": "电话",
    "tone": "详细",
    "user_id": "U-200",
    "question": "怎么申请退款？",
}).content)
```

> 🧠 **注意**：不要通过字符串拼接来创建整个提示——这样会把模板变量和模板结构混在一起。始终用 `ChatPromptTemplate.from_messages()` 定义结构，用 `chain.invoke({...})` 传入数据。

<!-- lab-check:integration -->

---

## 六、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| `KeyError: 'user_id'` | 调用 `chain.invoke()` 时漏传了模板中声明的变量 | 对比模板的 `{...}` 和 `invoke` 字典的 key |
| 模板渲染后出现字面 `{user_id}` | 占位符未被替换——变量名拼写不一致（如模板写 `{userId}`，字典 key 是 `user_id`） | 确认大小写和下划线完全一致 |
| 业务规则只在某些调用中生效 | 把规则写在了 user 消息中而非 system 消息中 | system 放稳定规则，user 放动态数据 |
| 费用异常高 | 缺字段校验在模型调用之后才报错——每次失败都消耗了一次 API 调用 | 在调用模型前先做字段完整性检查 |
| `eval()` 安全警告 | 用了 `eval(f'f"{template}"')` 来渲染 | 改为 `str.replace()` 或 `re.sub()` |

---

## 七、动手改造

1. 为 `render_support_prompt` 增加一个功能：检测到模板中有未闭合的花括号（如 `{user_id` 少了一个 `}`）时抛出 `ValueError`
2. 试着在一个模板中使用同一个变量 3 次，确认所有出现都被替换
3. 对比 `render_support_prompt(template, values)` 和 `ChatPromptTemplate.from_messages(...).invoke(values)` 的输出——它们应该完全一致

---

## 八、下一步

提示模板让 AI「会说」。下一节给客服接入**订单查询工具**，让 AI「能做」——不只是回答问题，还能实际查询业务系统。

[LangChain 官方 Prompt Template 文档](https://docs.langchain.com/oss/python/langchain/prompts)

<!-- lab-check:acceptance -->
