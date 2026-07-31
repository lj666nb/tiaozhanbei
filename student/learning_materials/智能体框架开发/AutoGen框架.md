# AutoGen多智能体对话与协作系统

## 1. 框架概述

AutoGen 是由微软研究院（Microsoft Research）开源的**多智能体对话框架**，核心理念是将 LLM 应用建模为多个可对话的 Agent 之间的消息传递与协作。与传统的"单 Agent + 工具链"模式不同，AutoGen 强调**智能体之间的对话即程序流** —— 多个 Agent 通过发送/接收消息来交换信息、协商决策、分工执行，从而完成复杂任务。

### 1.1 核心设计理念

| 设计维度 | AutoGen 的理念 |
|---------|---------------|
| 编程范式 | 对话驱动（Conversation-Driven） |
| 消息模型 | Agent 之间通过 send/receive/reply 通信 |
| 角色定位 | 每个 Agent 是对话中的一个参与者，拥有明确的角色和权限 |
| 人机协作 | 人类作为对话中的特殊参与者，可在任意节点介入 |
| 代码执行 | 支持在沙箱中自动生成、执行和验证代码 |
| 编排模式 | 通过 GroupChat 实现多对多自由对话，通过 GroupChatManager 控制发言顺序 |

### 1.2 与主流框架的定位对比

| 特性 | AutoGen | LangChain | CrewAI |
|------|---------|-----------|--------|
| 核心抽象 | 可对话Agent | Chain / Runnable | Crew / Task |
| 通信模型 | 多Agent消息传递 | 顺序流水线 | 任务委派 |
| 开源方 | 微软 | LangChain团队 | CrewAI |
| 最大优势 | 灵活对话+代码执行 | 生态丰富 | 简单易用 |

**Image-Prompt(multi-agent conversation framework):** A flat-design minimalist 2D vector illustration of the AutoGen multi-agent framework architecture. Center of composition shows three rounded rectangular agent nodes (AssistantAgent, UserProxyAgent, GroupChatManager) connected by bidirectional message arrows in tech light blue #409EFF. White background with dark blue #1a1a2e labels. Below the agents, a horizontal pipeline shows the conversation-driven programming paradigm: Message Send → Receive → Generate Reply → Send, each step as a rounded pill shape. Thin-line icons for speech bubbles and gears. Academic learning atmosphere with moderate whitespace and symmetric layout.

---

## 2. ConversableAgent：核心对话智能体

`ConversableAgent` 是 AutoGen 中所有 Agent 的基类，定义了消息的发送（send）、接收（receive）和回复（reply）机制。所有专用 Agent 类型（如 AssistantAgent、UserProxyAgent）均继承自它。

### 2.1 核心消息机制

```
┌─────────────────────────────────────────────────────┐
│                ConversableAgent                      │
│                                                     │
│   send(message, recipient)    ────►  接收方.receive()│
│                                                     │
│   receive(message, sender)    ◄────  发送方.send()   │
│                                                     │
│   generate_reply(messages)    ────►  调用LLM生成回复 │
│                                                     │
│   initiate_chat(recipient, message)  开启一轮对话    │
└─────────────────────────────────────────────────────┘
```

消息流向示意图（文字描述）：

```
Agent_A.initiate_chat(Agent_B, "请分析这段代码")
    │
    ▼
Agent_B.receive() → generate_reply() → send(reply, Agent_A)
    │
    ▼
Agent_A.receive() → generate_reply() → send(reply, Agent_B)
    │
    ▼
... 多轮对话 ...
```

### 2.2 代码示例：基础双Agent对话

```python
"""
AutoGen 双Agent对话示例
演示：让一个Agent出题，另一个Agent解答
"""
import os
from autogen import ConversableAgent, AssistantAgent

# ============================================================
# 配置LLM（示例使用OpenAI兼容接口）
# ============================================================
config_list = [
    {
        "model": "gpt-4",
        "api_key": os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY"),
        "base_url": os.environ.get("OPENAI_BASE_URL", None),
    }
]
llm_config = {"config_list": config_list, "temperature": 0.7}

# ============================================================
# 创建出题Agent（Teacher）
# ============================================================
teacher = AssistantAgent(
    name="Teacher",
    system_message="你是一位数学老师。每次给出一个中等难度的数学问题，"
                   "然后评估学生给出的答案是否正确。如果错误，请纠正。",
    llm_config=llm_config,
)

# ============================================================
# 创建解答Agent（Student）
# ============================================================
student = AssistantAgent(
    name="Student",
    system_message="你是一位勤奋的数学学生。你会尽力解答老师提出的每一个数学问题，"
                   "给出详细的解题步骤和最终答案。",
    llm_config=llm_config,
)

# ============================================================
# 开启对话：Teacher先出题，Student回答，Teacher评估
# max_turns=4 表示最多4轮对话
# ============================================================
result = student.initiate_chat(
    recipient=teacher,
    message="老师你好！请给我出一到数学题吧，我想测试一下自己的数学水平。",
    max_turns=4,
)

# 查看对话历史
for msg in student.chat_messages[teacher]:
    print(f"[{msg['name']}]: {msg['content'][:100]}...")
```

### 2.3 send / receive / reply 消息机制详解

`ConversableAgent` 的核心方法：

```python
"""
ConversableAgent 消息机制源码级解析
"""

# 1. send() — 将一个消息发送给接收者
#    sender.send(message, recipient)
#    内部调用 recipient.receive(message, sender)

# 2. receive() — 接收消息并触发处理流程
#    def receive(self, message, sender, request_reply=None, silent=False):
#        self.process_message_before_send(message, sender)
#        # 将消息存入聊天历史
#        self.append_chat_message(message, sender)
#        # 如果需要回复，则自动调用 generate_reply
#        if request_reply is not False:
#            reply = self.generate_reply(messages=self.chat_messages[sender], sender=sender)
#            if reply is not None:
#                self.send(reply, sender)

# 3. generate_reply() — 生成回复的核心逻辑
#    可以注册自定义的 reply_func 来拦截和自定义回复逻辑
#    def register_reply(self, trigger, reply_func, position=0, config=None):
#        支持的 trigger 包括：
#        - autogen.ConversableAgent.TRIGGER_ALWAYS: 每次收到消息都触发
#        - autogen.ConversableAgent.TRIGGER_NOT_TERMINATE: 只要未终止就触发
#        - 自定义 trigger 函数返回 True/False

# 4. 自定义回复逻辑示例
from autogen import ConversableAgent

def custom_reply_func(recipient, messages, sender, config):
    """自定义回复函数：在每段回复前添加emoji标记"""
    last_message = messages[-1]["content"]
    # 可以在这里添加任意的业务逻辑
    return True, f"🤖 [自定义处理]: {last_message} 已收到，正在处理..."

agent = ConversableAgent(name="CustomAgent", llm_config=llm_config)
agent.register_reply(
    trigger=ConversableAgent.TRIGGER_ALWAYS,  # 总是触发
    reply_func=custom_reply_func,
    position=0,  # 优先级：0为最高
)
```

**Image-Prompt(conversable agent message mechanism):** A flat-design minimalist 2D vector illustration showing the ConversableAgent core message mechanism. A central rounded rectangular agent node labeled "ConversableAgent" with four internal method blocks arranged symmetrically: send(), receive(), generate_reply(), initiate_chat(). Arrows in tech light blue #409EFF show message flow between two agent instances on left and right. White background, dark blue #1a1a2e text labels. Thin-line envelope and arrow icons. Clean academic educational style with centered composition.

---

## 3. GroupChat：多Agent群聊模式

当需要三个以上Agent协作时，AutoGen提供了`GroupChat`模式，允许多个Agent在一个共享的对话空间中自由交流。由一个`GroupChatManager`负责调度发言顺序。

### 3.1 架构图（文字描述）

```
┌──────────────────────────────────────────────────────────┐
│                     GroupChat                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐   │
│  │ Agent_A  │  │ Agent_B  │  │ Agent_C  │  │ Agent_D  │   │
│  │ 代码专家  │  │ 架构师   │  │ 测试专家  │  │ 产品经理  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │        │
│       └──────────────┴──────────────┴──────────────┘        │
│                          │                                  │
│                   ┌──────┴──────┐                           │
│                   │GroupChatManager│   ← 决定谁来发言       │
│                   │  (调度器)      │                         │
│                   │  speaker_selection_method              │
│                   │  = "auto" / "round_robin" / "random"  │
│                   └──────────────┘                          │
└──────────────────────────────────────────────────────────┘
```

### 3.2 GroupChatManager 调度机制

GroupChatManager 的核心职责是**选择下一个发言者**（speaker selection）。AutoGen 提供了三种选择策略：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `"auto"`（默认） | 由 LLM 分析对话上下文自动选择最合适的发言人 | 灵活协作，角色分工明确 |
| `"round_robin"` | 按固定顺序轮询发言 | 需要每一轮都发表意见 |
| `"random"` | 随机选择发言人 | 探索性讨论、头脑风暴 |

### 3.3 完整代码示例：软件开发团队群聊

```python
"""
AutoGen GroupChat 完整示例
模拟一个软件开发团队的多角色协作
需求：设计并实现一个简单的REST API用户认证模块
"""
import os
from autogen import (
    AssistantAgent,
    UserProxyAgent,
    GroupChat,
    GroupChatManager,
)

# ============================================================
# LLM配置
# ============================================================
config_list = [{"model": "gpt-4", "api_key": os.environ.get("OPENAI_API_KEY")}]
llm_config = {"config_list": config_list, "temperature": 0.7}

# ============================================================
# 创建团队成员Agent
# ============================================================

# 1. 架构师 — 负责系统设计
architect = AssistantAgent(
    name="Architect",
    system_message="""你是一位资深软件架构师。
    - 负责设计系统架构、技术选型、模块划分
    - 输出清晰的架构描述，包括组件关系和接口定义
    - 当被问到时，给出具体的技术方案
    请用中文回答。""",
    llm_config=llm_config,
)

# 2. 后端开发工程师 — 负责实现
developer = AssistantAgent(
    name="Developer",
    system_message="""你是一位Python后端开发工程师。
    - 负责将架构设计转化为可执行的Python代码
    - 使用FastAPI框架编写REST API
    - 注重代码质量、错误处理和安全性
    - 输出完整可运行的代码
    请用中文回答。""",
    llm_config=llm_config,
)

# 3. 代码审查员 — 负责质量把关
reviewer = AssistantAgent(
    name="Reviewer",
    system_message="""你是一位资深代码审查员。
    - 审查别人提供的代码，检查潜在问题
    - 关注：安全漏洞、性能问题、代码规范、边界情况
    - 给出具体的改进建议，而不是泛泛而谈
    请用中文回答。""",
    llm_config=llm_config,
)

# 4. 用户代理 — 代表用户提出问题，并执行代码
user_proxy = UserProxyAgent(
    name="UserProxy",
    human_input_mode="NEVER",  # 不需要人工介入
    max_consecutive_auto_reply=0,
    code_execution_config={
        "work_dir": "coding_workspace",
        "use_docker": False,  # 本地执行，不使用Docker
    },
    system_message="你是用户代表，负责提出需求并最终确认方案是否满足需求。",
)

# ============================================================
# 定义发言顺序规则（自定义函数）
# ============================================================
def custom_speaker_selection(last_speaker, groupchat):
    """
    自定义发言顺序：
    UserProxy → Architect → Developer → Reviewer → UserProxy（循环）
    这样的顺序确保"需求 → 设计 → 实现 → 审查 → 确认"的流水线
    """
    messages = groupchat.messages
    if len(messages) <= 1:
        return architect  # 第一轮：架构师先设计
    elif last_speaker is architect:
        return developer  # 架构师说完，开发开始
    elif last_speaker is developer:
        return reviewer  # 开发写完，审查员审查
    elif last_speaker is reviewer:
        return user_proxy  # 审查通过，回到用户确认
    elif last_speaker is user_proxy:
        return architect  # 用户确认后，如果需要修改则回到架构师
    return "auto"  # 其他情况让LLM自动决定

# ============================================================
# 创建GroupChat和Manager
# ============================================================
groupchat = GroupChat(
    agents=[user_proxy, architect, developer, reviewer],
    messages=[],
    max_round=10,  # 最多10轮对话
    speaker_selection_method=custom_speaker_selection,
    allow_repeat_speaker=True,  # 允许同一个Agent连续发言
)

manager = GroupChatManager(
    name="Manager",
    groupchat=groupchat,
    llm_config=llm_config,
)

# ============================================================
# 启动群聊
# ============================================================
if __name__ == "__main__":
    user_proxy.initiate_chat(
        recipient=manager,
        message="""
请团队协作完成以下任务：
设计并实现一个用户认证模块的REST API，需要包含：
1. 用户注册接口（用户名+密码）
2. 用户登录接口（返回JWT Token）
3. Token刷新接口
4. 密码使用bcrypt加密存储

请架构师先给出设计方案，然后由开发实现，审查员审查代码质量。
        """.strip(),
    )

    # 打印对话概要
    print("\n" + "=" * 60)
    print("对话完成！共 {} 轮讨论".format(len(groupchat.messages)))
    print("=" * 60)
```

**Image-Prompt(group chat multi-agent orchestration):** A flat-design minimalist 2D vector illustration of AutoGen GroupChat architecture. Four rounded agent avatar icons (Architect, Developer, Reviewer, UserProxy) arranged in a circle around a central "GroupChatManager" hub node in tech light blue #409EFF. Dashed selection arrows show the manager choosing the next speaker. Speaker selection methods displayed as three small pill badges: auto, round_robin, random. White background with dark blue #1a1a2e text. Thin-line chat bubble icons connect agents. Academic atmosphere with symmetric radial layout.

---

## 4. 代码执行集成

AutoGen 的一个独特优势是**内置的代码执行能力**。`UserProxyAgent` 在执行代码时可以自动触发代码执行环境。

### 4.1 UserProxyAgent 与代码执行

```python
"""
UserProxyAgent 代码执行示例
演示：让Agent生成代码并在沙箱中执行
"""
from autogen import AssistantAgent, UserProxyAgent
import os

llm_config = {
    "config_list": [{"model": "gpt-4", "api_key": os.environ.get("OPENAI_API_KEY")}]
}

# ============================================================
# 创建代码生成Agent
# ============================================================
coder = AssistantAgent(
    name="Coder",
    system_message="""你是一位Python开发者。用户会提出数据分析需求。
    请编写Python代码完成分析任务，代码应包含必要的print语句输出结果。
    代码应该是完整可独立运行的。每次只输出一个代码块。""",
    llm_config=llm_config,
)

# ============================================================
# 创建用户代理（启用代码执行）
# ============================================================
user_proxy = UserProxyAgent(
    name="UserProxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=0,
    code_execution_config={
        "work_dir": "coding",
        "use_docker": False,  # 关闭Docker（本地开发环境）
        # 当 use_docker=True 时，代码将在Docker容器中执行，提供安全沙箱
        # "docker_image": "python:3.11",  # 指定Docker镜像
        "timeout": 60,  # 代码执行超时时间（秒）
    },
)

# ============================================================
# 发起对话：让Agent分析数据
# ============================================================
if __name__ == "__main__":
    user_proxy.initiate_chat(
        coder,
        message="""
请帮我分析以下销售数据，计算每个季度的总销售额和同比增长率：

数据（格式：季度,销售额（万元））：
2023Q1,120  2023Q2,135  2023Q3,158  2023Q4,200
2024Q1,145  2024Q2,160  2024Q3,182  2024Q4,230

请用Python代码完成分析，并将结果用print输出。
        """.strip(),
    )
```

### 4.2 Docker 代码执行沙箱

```python
"""
Docker沙箱代码执行配置
生产环境推荐使用Docker沙箱隔离
"""
code_execution_config = {
    "work_dir": "workspace",
    "use_docker": True,
    # 指定Docker镜像（可自定义）
    "docker_image": "python:3.11-slim",
    # 超时设置
    "timeout": 120,
    # 执行前自动安装依赖
    "last_n_messages": 3,  # 将最后N条消息作为上下文提供
}

# 注意：使用Docker需要满足以下前提条件：
# 1. 系统已安装Docker
# 2. Docker daemon正在运行
# 3. 当前用户有Docker操作权限
```

### 4.3 两Agent代码生成与执行模式

```python
"""
经典模式：Coder + Executor 双Agent协作
Coder: 负责编写代码
Executor: 负责执行代码并反馈错误给Coder修正
"""
from autogen import AssistantAgent, UserProxyAgent

config_list = [{"model": "gpt-4", "api_key": "YOUR_API_KEY"}]

# Coder Agent
assistant = AssistantAgent(
    name="assistant",
    llm_config={"config_list": config_list},
    system_message="你是Python专家。编写代码解决问题，根据执行反馈修正错误。",
)

# Executor Agent（自动执行代码）
user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    code_execution_config={"work_dir": "coding", "use_docker": False},
)

# 开始自动协作
user_proxy.initiate_chat(
    assistant,
    message="用Python编写一个函数，找出1000以内的所有质数并打印。",
)
# 如果Coder的代码执行出错，Executor会自动反馈错误信息，
# Coder会据此修正代码，直到代码正确运行为止
```

**Image-Prompt(code execution sandbox pipeline):** A flat-design minimalist 2D vector illustration of the AutoGen code execution integration. A horizontal flow diagram showing: Coder Agent (rounded rectangle with code icon) → generates Python code → UserProxy Agent (rounded rectangle with gear icon) → executes in Docker Sandbox (cube icon with shield) → returns results/errors back as feedback loop. The sandbox cube has a protective glow border in tech light blue #409EFF. White background, dark blue #1a1a2e labels. Thin-line terminal and container icons. Academic learning atmosphere.

---

## 5. 人机交互模式

AutoGen 的一个重要设计理念是**人类作为对话的参与者**，而非旁观者。通过 `UserProxyAgent` 的 `human_input_mode` 参数，可以灵活控制人工介入的时机。

### 5.1 human_input_mode 三种模式

| 模式 | 值 | 行为 |
|------|-----|------|
| 始终询问 | `"ALWAYS"` | 每次需要Agent回复时，都等待人工输入 |
| 条件询问 | `"TERMINATE"` | 仅在对话即将终止时询问人工是否继续 |
| 从不询问 | `"NEVER"` | 完全不等待人工输入，全自动运行 |

### 5.2 人工介入模式示例

```python
"""
人机交互示例：代码审查场景
人类审查员在关键节点介入审查代码
"""
from autogen import AssistantAgent, UserProxyAgent

config_list = [{"model": "gpt-4", "api_key": "YOUR_API_KEY"}]

# ============================================================
# 代码编写Agent
# ============================================================
developer = AssistantAgent(
    name="DeveloperAgent",
    system_message="你是一位Python开发者。编写高质量、安全的代码。",
    llm_config={"config_list": config_list},
)

# ============================================================
# 人工审查Agent（TERMINATE模式）
# ============================================================
human_reviewer = UserProxyAgent(
    name="HumanReviewer",
    human_input_mode="TERMINATE",
    # TERMINATE模式：当对话即将结束时，弹窗询问：
    # "Please give feedback to the sender. Press enter to skip and terminate,
    #  or type 'exit' to end the conversation."
    code_execution_config=False,  # 不执行代码，仅做审查
)

# ============================================================
# 启动带人工审查的对话流程
# ============================================================
if __name__ == "__main__":
    human_reviewer.initiate_chat(
        developer,
        message="""
请编写一个Python函数用于处理用户上传的文件：
1. 接收文件路径作为参数
2. 检查文件大小（不超过10MB）和类型（仅允许.txt, .csv, .json）
3. 读取文件内容并返回
4. 包含完善的异常处理
        """.strip(),
    )
    # 工作流程：
    # 1. Developer 编写代码
    # 2. 代码完成后，HumanReviewer弹出TERMINATE确认
    # 3. 人工审查员检查代码质量和安全性
    # 4. 可以选择继续对话让Developer修改，或输入'exit'结束
```

### 5.3 自定义人工介入条件

```python
"""
高级用法：自定义人工介入触发条件
"""
from autogen import UserProxyAgent

def custom_termination_condition(messages):
    """
    自定义终止条件：当消息中包含特定关键词时触发人工介入
    """
    last_message = messages[-1]["content"] if messages else ""
    # 当代码中包含敏感操作时，需要人工确认
    sensitive_keywords = [
        "DELETE", "DROP", "rm -rf", "os.remove",
        "subprocess", "eval(", "exec(", "password"
    ]
    for keyword in sensitive_keywords:
        if keyword.lower() in last_message.lower():
            return True  # 触发人工介入
    return False

# 创建带自定义终止条件的人工Agent
supervisor = UserProxyAgent(
    name="Supervisor",
    human_input_mode="ALWAYS",  # 始终等待人工输入
    # 可以结合max_consecutive_auto_reply控制自动化程度
    max_consecutive_auto_reply=10,  # 连续自动回复最多10次
    system_message="你是安全审查员，确认所有操作都是安全的。",
)
```

**Image-Prompt(human input modes comparison):** A flat-design minimalist 2D vector illustration showing three human-in-the-loop interaction modes. Three columns side by side: "ALWAYS" mode (human silhouette with solid connecting line to agent), "TERMINATE" mode (human silhouette with dashed conditional line), "NEVER" mode (agent standalone with automated gear). Each column uses tech light blue #409EFF for active elements. White background, dark blue #1a1a2e for labels. Thin-line human and robot icons. Academic comparison layout with moderate spacing.

---

## 6. AutoGen vs CrewAI：详细对比分析

### 6.1 架构理念对比

| 维度 | AutoGen | CrewAI |
|------|---------|--------|
| **核心范式** | 对话驱动（Conversation-Driven） | 任务委派驱动（Task-Delegation） |
| **灵感来源** | 微软研究院的多Agent对话研究 | 层级化团队协作理论 |
| **编程模型** | Agent之间通过消息通信，类似聊天室 | 管理者分配Task给Worker，类似公司层级 |
| **控制流** | 显式的消息发送/接收 | 隐式的任务分配和执行 |
| **编排方式** | GroupChat + GroupChatManager | Crew + Process(sequential/hierarchical) |

### 6.2 角色定义方式对比

**AutoGen 角色定义：**
```python
# AutoGen：通过 system_message 定义角色行为
agent = AssistantAgent(
    name="Researcher",
    system_message="你是一位研究员，擅长搜索和分析信息...",
    llm_config=llm_config,
)
# 角色通过 对话中的位置 自然体现
# 角色转换通过 GroupChatManager 的发言调度实现
```

**CrewAI 角色定义：**
```python
# CrewAI：通过明确的 role/goal/backstory 定义角色
agent = Agent(
    role="资深研究员",
    goal="发现关于{topic}的最新信息",
    backstory="你在一家顶级智库工作了10年...",
    tools=[search_tool],
)
# 角色是 预设属性，行为由 Task 进一步约束
```

### 6.3 消息传递机制对比

| 机制 | AutoGen | CrewAI |
|------|---------|--------|
| **通信方式** | `send()/receive()/reply()` 显式消息 | 任务上下文自动传递 |
| **对话历史** | 每个Agent维护 `chat_messages` 字典 | 通过 Crew 的共享上下文 |
| **发言人调度** | GroupChatManager 选择下一个发言者 | Process 定义执行顺序 |
| **消息路由** | 点对点直接发送 | 通过 Manager/Task 间接路由 |
| **消息可见性** | 所有GroupChat成员可见 | 按Process配置决定 |

### 6.4 适用场景差异

| 场景类型 | 推荐框架 | 原因 |
|---------|---------|------|
| 多领域专家辩论/研讨 | **AutoGen** | 自由对话模式天然支持多方讨论 |
| 代码生成+执行+调试循环 | **AutoGen** | 内置代码执行沙箱，自动反馈修复 |
| 人机协作工作流 | **AutoGen** | human_input_mode 灵活控制 |
| 垂直领域任务流水线 | **CrewAI** | Task 定义清晰，Crew 组织直观 |
| 固定流程的业务自动化 | **CrewAI** | Sequential/Hierarchical Process 简单可靠 |
| 快速原型验证（3-5 agents） | **CrewAI** | API 简洁，学习曲线平缓 |
| 复杂动态交互（5+ agents） | **AutoGen** | GroupChat 管理多个智能体更自然 |
| 需要灵活人工介入的场景 | **AutoGen** | 细粒度控制人工参与 |

### 6.5 选型建议总结表格

| 条件 | 选择 |
|------|------|
| 需要Agent间自由对话和辩论 | **AutoGen** |
| 需要执行和验证代码 | **AutoGen** |
| 需要人类在任意节点介入 | **AutoGen** |
| 任务流程固定且可预测 | **CrewAI** |
| 团队协作建模为公司层级 | **CrewAI** |
| 追求极简API和快速上手 | **CrewAI** |
| 微软技术栈/生态 | **AutoGen** |
| 需要生产级Docker沙箱 | **AutoGen** |

**Image-Prompt(framework comparison AutoGen vs CrewAI):** A flat-design minimalist 2D vector illustration comparing AutoGen and CrewAI frameworks side by side. Left side: AutoGen shown as a conversation web with agents connected by bidirectional chat arrows. Right side: CrewAI shown as a hierarchical pyramid with Manager at top delegating tasks downward. A central divider with comparison labels in tech light blue #409EFF. White background, dark blue #1a1a2e text. Thin-line icons representing different architectural patterns. Academic educational comparison chart style.

---

## 7. 完整示例：多Agent辩论系统

以下是一个完整的多Agent辩论系统，模拟三位专家就一个命题进行辩论，由一位裁判Agent做最终裁决。

```python
"""
AutoGen 多Agent辩论系统
命题：「人工智能是否应该拥有自主决策权？」

参与者：
- Proponent（正方）：支持AI拥有自主决策权
- Opponent（反方）：反对AI拥有自主决策权
- Moderator（主持人）：控制辩论节奏，提出规则
- Judge（裁判）：根据双方论点做出最终裁决

架构：
  Moderator → Proponent → Opponent → Proponent → Opponent → ... → Judge
     │            │           │
     └────────────┴───────────┘
              GroupChat
"""
import os
from autogen import AssistantAgent, GroupChat, GroupChatManager

# ============================================================
# 配置
# ============================================================
config_list = [
    {
        "model": "gpt-4",
        "api_key": os.environ.get("OPENAI_API_KEY", "demo-key"),
    }
]
llm_config = {
    "config_list": config_list,
    "temperature": 0.8,  # 稍高温度增加观点多样性
}

# ============================================================
# 创建辩论参与者
# ============================================================

def create_agent(name, system_prompt):
    """工厂函数：统一创建Agent"""
    return AssistantAgent(
        name=name,
        system_message=system_prompt,
        llm_config=llm_config,
    )

moderator = create_agent(
    name="Moderator",
    system_message="""你是辩论主持人。
职责：
1. 宣布辩论开始的规则（每人发言不超过200字）
2. 确保双方交替发言，控制辩论节奏
3. 在3轮辩论后宣布辩论结束，请裁判做最终裁决
4. 你的发言必须以【规则】或【提醒】或【裁决】开头
请用中文。"""
)

proponent = create_agent(
    name="Proponent",
    system_message="""你是正方辩手，支持「AI应该拥有自主决策权」。
论据方向：
- AI在某些领域已经超越人类（棋类、蛋白质折叠）
- 自主决策是通往AGI的必经之路
- 在医疗诊断、自动驾驶等场景中，快速自主决策可以挽救生命
- 可以设置安全边界和人类监督机制
请用有力的论据支持你的立场。每次发言关注一个核心论点。
请用中文。"""
)

opponent = create_agent(
    name="Opponent",
    system_message="""你是反方辩手，反对「AI应该拥有自主决策权」。
论据方向：
- 当前AI缺乏真正的理解和道德判断能力
- 责任归属问题：如果AI做错决策，谁来负责？
- 历史上技术被滥用的教训（核武器、生物技术）
- AI的安全对齐问题尚未解决
请用有力的论据支持你的立场。每次反驳前先回应正方上一轮的论点。
请用中文。"""
)

judge = create_agent(
    name="Judge",
    system_message="""你是辩论裁判，负责最后的裁决。
在收到「请裁判裁决」的指令后，你需要：
1. 总结双方的核心论点（各列出2-3条）
2. 评估哪一方的论据更加有说服力
3. 给出最终裁决（正方胜/反方胜/平局）
4. 说明裁决理由（至少2条理由）
请用中文，裁判发言以【最终裁决】开头。"""
)

# ============================================================
# 自定义发言顺序
# ============================================================
def debate_speaker_selection(last_speaker, groupchat):
    """控制辩论的发言顺序"""
    messages = groupchat.messages
    if len(messages) <= 1:
        return proponent  # 辩论开始，正方先发言

    # 计算双方的发言次数
    pro_count = sum(1 for m in messages if m.get("name") == "Proponent")
    opp_count = sum(1 for m in messages if m.get("name") == "Opponent")

    if last_speaker is moderator:
        return proponent  # 主持人发言后，正方开始

    elif last_speaker is proponent:
        if opp_count < 3:
            return opponent  # 正方说完轮到反方
        else:
            return moderator  # 3轮后回到主持人

    elif last_speaker is opponent:
        if pro_count < 3:
            return proponent  # 反方说完轮到正方
        else:
            return moderator  # 3轮后回到主持人

    # 检查是否应该进入裁决阶段
    if pro_count >= 3 and opp_count >= 3 and last_speaker is moderator:
        return judge  # 辩论结束，裁判裁决

    return "auto"  # 其他情况由LLM决定

# ============================================================
# 创建GroupChat
# ============================================================
groupchat = GroupChat(
    agents=[moderator, proponent, opponent, judge],
    messages=[],
    max_round=12,
    speaker_selection_method=debate_speaker_selection,
    allow_repeat_speaker=False,
)

manager = GroupChatManager(
    name="DebateManager",
    groupchat=groupchat,
    llm_config=llm_config,
)

# ============================================================
# 开始辩论
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("辩论主题：人工智能是否应该拥有自主决策权？")
    print("=" * 60)

    # 由Moderator发起辩论
    moderator.initiate_chat(
        recipient=manager,
        message="""【规则】辩论现在开始！
主题：「人工智能是否应该拥有自主决策权？」
规则：
1. 正方（Proponent）和反方（Opponent）各进行3轮辩论
2. 每轮发言请控制在200字以内，关注一个核心论点
3. 反方发言时应先回应正方的上一轮论点
4. 3轮后由裁判（Judge）做出最终裁决

现在开始，请正方辩手Proponent先发言。""",
    )

    # 打印辩论记录
    print("\n" + "=" * 60)
    print("辩论记录总览")
    print("=" * 60)
    for i, msg in enumerate(groupchat.messages, 1):
        name = msg.get("name", "Unknown")
        content = msg.get("content", "")[:120]
        print(f"  [{i}] {name}: {content}...")
```

**Image-Prompt(multi-agent debate system):** A flat-design minimalist 2D vector illustration of a multi-agent debate system. Four rounded agent nodes arranged in a diamond pattern: Moderator (top), Proponent (left, green-tinted), Opponent (right, orange-tinted), Judge (bottom). Debate flow arrows in tech light blue #409EFF show alternating exchanges between Proponent and Opponent with Moderator controlling turns. A gavel icon near Judge node. White background with dark blue #1a1a2e labels. Academic debate atmosphere with symmetric diamond composition.

---

## 8. 高级特性速览

### 8.1 Teachability（可教育性）

```python
"""
Teachability：让Agent从过往对话中学习
"""
from autogen import ConversableAgent
from autogen.agentchat.contrib.capabilities.teachability import Teachability

agent = AssistantAgent(
    name="TeachableAgent",
    llm_config=llm_config,
)

# 启用可教育性 —— Agent会记住用户教给它的偏好和知识
teachability = Teachability(
    verbosity=0,
    reset_db=False,
    path_to_db_dir="./tmp/teachability_db",  # 记忆存储路径
    recall_threshold=1.5,  # 相似度阈值（越低越容易召回）
)
teachability.add_to_agent(agent)
```

### 8.2 多层嵌套聊天（Nested Chat）

```python
"""
嵌套聊天：一个Agent在处理消息时会触发子对话
"""
from autogen import AssistantAgent

# 主Agent在处理复杂问题时，自动启动子Agent进行专项分析
main_agent = AssistantAgent(
    name="MainAgent",
    llm_config=llm_config,
)

sub_agent = AssistantAgent(
    name="SubAgent",
    llm_config=llm_config,
)

# 注册嵌套聊天：当MainAgent收到消息中包含"分析"时，
# 自动触发与SubAgent的子对话来深度分析
# 注：此处为概念性代码，具体API请参考AutoGen文档
```

**Image-Prompt(teachability and nested chat features):** A flat-design minimalist 2D vector illustration showing two advanced AutoGen features. Left panel: Teachability shown as an agent with a brain icon storing memories to a database cylinder labeled "Teachability DB" with recall arrows. Right panel: Nested Chat shown as a main agent containing a smaller sub-agent dialog bubble inside it, representing recursive conversation nesting. Tech light blue #409EFF accents. White background, dark blue #1a1a2e text. Thin-line icons. Academic feature overview layout.

---

## 9. 小结与学习建议

### 核心要点回顾

1. **AutoGen的核心是"对话即计算"** —— 将多Agent协作建模为消息传递，而非任务链
2. **ConversableAgent** 是所有Agent的基类，掌握 send/receive/reply 机制是关键
3. **GroupChat + GroupChatManager** 是多Agent协作的核心模式，通过 speaker_selection 控制流程
4. **UserProxyAgent + 代码执行** 是AutoGen的独特优势，实现了"生成-执行-反馈-修正"闭环
5. **human_input_mode** 提供了灵活的人机协作粒度

### 实践建议

| 阶段 | 目标 | 建议练习 |
|------|------|---------|
| 入门 | 理解消息机制 | 实现双Agent对话（Q&A场景） |
| 进阶 | 掌握GroupChat | 实现3+Agent的代码审查工作流 |
| 高级 | 人机协作 | 添加人工审查节点到工作流中 |
| 专家 | 自定义扩展 | 注册自定义reply_func，实现复杂业务逻辑 |

### 与他人协作的最佳实践

- 明确定义每个Agent的 `system_message`，越具体越好
- 为GroupChat设置合理的 `max_round` 防止无限对话
- 生产环境使用 `use_docker=True` 隔离代码执行
- 利用 `register_reply` 机制添加日志、监控、审计等横切关注点
- 定期使用 Teachability 让Agent积累领域知识

**Image-Prompt(AutoGen learning roadmap summary):** A flat-design minimalist 2D vector illustration of the AutoGen learning pathway. A horizontal stepped roadmap with four ascending stages: "入门" (two-agent dialogue), "进阶" (GroupChat workflow), "高级" (human-AI collaboration), "专家" (custom reply functions). Each stage shown as an ascending rounded step in tech light blue #409EFF gradient intensity. White background with dark blue #1a1a2e labels. Thin-line milestone flag icons. Clean academic progression visualization with centered layout.

---

> **延伸阅读**：
> - AutoGen官方仓库：https://github.com/microsoft/autogen
> - AutoGen Studio：可视化构建多Agent工作流
> - AutoGen v0.4 架构升级：事件驱动 + 异步支持
