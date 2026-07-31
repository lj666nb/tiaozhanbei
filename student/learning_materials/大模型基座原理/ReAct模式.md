# ReAct模式

## 引言

假设你对一个AI助手提问："2025年诺贝尔物理学奖得主是谁？"

一个纯语言模型会怎么做？它可能：
- 根据训练数据（截止到某个时间点）直接猜测 → 但它的训练数据可能不包含2025年的信息
- 基于"模式匹配"生成一个看似合理的名字 → 这恰恰是幻觉的来源
- 即使不确定，也给出一个自信的错误答案

一个使用ReAct模式的AI会怎么做？

```
Thought: 我需要知道2025年诺贝尔物理学奖得主是谁。
        我的训练数据截止到2024年，无法直接回答。
        我应该搜索最新信息。

Action: search("2025年诺贝尔物理学奖得主")

Observation: 搜索结果显示，2025年诺贝尔物理学奖授予了...

Thought: 我现在有了确切的信息。可以整理并回答用户。

Action: Finish("2025年诺贝尔物理学奖授予了...")
```

这就是ReAct模式——**Reasoning（推理）**与**Acting（行动）**的交替协同。本文将深入讲解ReAct的原理、实现和应用。

**Image-Prompt(ReAct Agent Loop):**
```
A flat-design minimalist 2D vector illustration showing the ReAct cycle. Center: a rounded robot/AI icon surrounded by three circular nodes connected by clockwise arrows forming a loop. The three nodes contain simplified icons: a brain (Thought), a gear/wrench (Action), and an eye (Observation). Primary blue #409EFF for the arrows and node borders, white background, deep blue #1a1a2e for labels. Clean academic style with generous whitespace, centered symmetrical layout.
```

## ReAct的诞生背景

### 论文起源

ReAct（Reasoning + Acting）由Google Research和普林斯顿大学在2022年10月的论文《ReAct: Synergizing Reasoning and Acting in Language Models》中首次提出。这篇论文的核心发现是：**将推理和行动结合，比单独使用其中任何一个都要好得多**。

论文通过实验证明：
- 纯推理（CoT）：容易产生幻觉，因为缺乏外部事实校验
- 纯行动（Tool-Use）：缺乏规划，可能盲目调用工具
- ReAct（推理+行动）：既保持推理的规划性，又通过行动获取事实基础

```
实验结果（HotpotQA准确率）：
  纯CoT:      33.4%
  纯行动:      25.7%
  ReAct:      35.1%  ← 两者结合优于任一个单独使用
```

### 为什么两者需要交替

让我们用一个类比来理解。想象你是一个正在修理一辆不熟悉的汽车引擎的机械师：

**纯推理模式**（CoT）：你在脑海中想象引擎的结构，推理"这里可能有个螺丝，松开它应该能取下面板……"。你的推理可能很严谨，但如果实际的引擎结构与你想象的不同（你的知识有盲区），整个推理链就会崩塌。

**纯行动模式**（Tool-Use）：你直接伸手去摸索，摸到什么就拆什么，没有计划。你可能会拆掉很多不需要拆的零件，甚至损坏引擎。

**ReAct模式**：你先观察引擎（Observation），思考"这个面板似乎被三个卡扣固定"（Thought），然后尝试撬开第一个卡扣（Action），看到结果后再决定下一步（Observation → Thought → Action → ...）。

这就是ReAct的精妙之处——**推理为行动提供方向，行动为推理提供事实依据**。

**Image-Prompt(Reasoning vs Acting Comparison):**
```
A flat-design minimalist 2D vector illustration comparing three modes side by side. Left panel: a single chain of thought bubbles connected by arrows (labeled "CoT Only"). Center panel: scattered tool icons with no connecting logic (labeled "Action Only"). Right panel (highlighted with #409EFF glow): thought bubbles alternating with tool icons in a connected cycle (labeled "ReAct"). White background, deep blue #1a1a2e text labels, clean rounded rectangular panels arranged symmetrically.
```

## ReAct核心循环

### 基本循环结构

```
Thought → Action → Observation → Thought → Action → Observation → ... → Final Answer
```

每个步骤的职责：

| 步骤 | 英文 | 职责 | 示例 |
|------|------|------|------|
| Thought | 思考 | 分析当前状态，决定下一步做什么 | "我需要搜索最新的GDP数据" |
| Action | 行动 | 执行具体的操作（调用工具） | search("中国2025年GDP") |
| Observation | 观察 | 记录行动的结果/返回信息 | "搜索结果显示：中国2025年GDP..." |
| ... | ... | 循环往复，直到问题解决 | |
| Final Answer | 最终答案 | 基于所有观察给出的结论 | "根据最新数据，中国2025年..." |

### 一个完整的ReAct循环示例

```
用户问题："巴黎和柏林哪个城市人口更多？多多少？"

Thought: 我需要比较巴黎和柏林的人口数据。
        先搜索巴黎的人口。

Action: search("巴黎人口 2025")

Observation: 巴黎市区人口约为216万人（2025年估计），
             大巴黎都会区人口约为1230万人。

Thought: 好的，巴黎市区人口约216万。接下来搜索柏林的人口。

Action: search("柏林人口 2025")

Observation: 柏林人口约为385万人（2025年估计）。

Thought: 现在我有两个城市的人口数据：
        - 巴黎市区：216万
        - 柏林：385万
        柏林人口更多。
        385 - 216 = 169万
        
        我可以给出最终答案了。

Action: Finish("柏林人口更多。柏林约385万人，巴黎市区约216万人，
        柏林比巴黎多约169万人。")
```

注意几个关键点：
- 每次Thought都基于之前的Observation，体现了"推理-行动"的交替性质
- 当信息不足时，模型会主动搜索而不是猜测
- 最终答案包含了完整的计算过程，具有可验证性

**Image-Prompt(Thought-Action-Observation Cycle Diagram):**
```
A flat-design minimalist 2D vector illustration of the ReAct core loop as a horizontal flowchart. Three rounded rectangular boxes labeled "Thought", "Action", "Observation" connected by right-pointing arrows in #409EFF. Each box contains a minimal icon: a lightbulb for Thought, a play-button triangle for Action, and a document with checkmark for Observation. A feedback arrow loops from Observation back to Thought, forming a cycle. White background, deep blue #1a1a2e labels, thin-line icons.
```

## 详细代码实现

### 基础ReAct Agent框架

```python
import re
import json
from typing import Dict, List, Tuple, Callable, Any
from dataclasses import dataclass

@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, str]  # 参数名 → 描述

class ReActAgent:
    """ReAct模式的Agent实现"""

    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        self.tools: Dict[str, Tool] = {}
        self.history: List[Dict[str, str]] = []
        self.max_iterations = 10

    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool

    def _build_tool_descriptions(self) -> str:
        """构建工具描述文本"""
        descriptions = []
        for tool in self.tools.values():
            params = ", ".join(
                f"{k}: {v}" for k, v in tool.parameters.items()
            )
            descriptions.append(
                f"- {tool.name}({params}): {tool.description}"
            )
        return "\n".join(descriptions)

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        tool_desc = self._build_tool_descriptions()

        return f"""你是一个具备行动能力的AI助手。你可以使用以下工具：

{tool_desc}

你必须严格遵循以下格式进行每一步的思考和行动：

Thought: 你的思考过程——分析当前需要什么信息，下一步应该做什么
Action: 工具名称[参数]
Observation: 工具返回的结果（由系统自动填入）

当你有足够的信息回答用户时，使用：
Action: Finish[你的最终答案]

重要规则：
1. 每一步必须先写Thought，再写Action
2. 一次只能执行一个Action
3. 如果搜索结果不理想，尝试不同的搜索关键词
4. 不要猜测事实——如果不知道，请使用工具搜索
5. 在Finish之前，确保你的答案基于Observations中的真实数据
"""

    def _parse_action(self, text: str) -> Tuple[str, str]:
        """解析Action文本，提取工具名和参数"""
        # 匹配: Action: tool_name[arguments]
        pattern = r"Action:\s*(\w+)\[(.*?)\]"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1), match.group(2).strip()
        return None, None

    def _execute_action(self, action_name: str, action_input: str) -> str:
        """执行工具调用"""
        if action_name == "Finish":
            return action_input

        if action_name not in self.tools:
            return f"错误：未知工具 '{action_name}'。可用的工具有：{list(self.tools.keys())}"

        try:
            tool = self.tools[action_name]
            result = tool.func(action_input)
            return str(result)
        except Exception as e:
            return f"工具执行错误：{str(e)}"

    def _call_llm(self, messages: List[Dict]) -> str:
        """调用LLM（此处为简化示例，实际应调用API）"""
        # 实际使用时替换为真正的API调用
        # response = openai.ChatCompletion.create(
        #     model=self.model_name,
        #     messages=messages,
        #     temperature=0,
        # )
        # return response.choices[0].message.content
        pass  # 占位

    def run(self, user_query: str) -> str:
        """运行ReAct循环"""
        # 初始化对话
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": user_query},
        ]

        self.history = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # 调用LLM获取下一步思考+行动
            response = self._call_llm(messages)

            # 解析Thought和Action
            thought_match = re.search(
                r"Thought:\s*(.+?)(?=\nAction:|\Z)",
                response, re.DOTALL
            )
            thought = thought_match.group(1).strip() if thought_match else ""

            action_name, action_input = self._parse_action(response)

            if not action_name:
                messages.append({
                    "role": "assistant",
                    "content": response
                })
                messages.append({
                    "role": "user",
                    "content": "请按照指定格式输出：\nThought: ...\nAction: tool_name[arguments]"
                })
                continue

            # 记录本轮信息
            step_record = {
                "iteration": iteration,
                "thought": thought,
                "action": f"{action_name}[{action_input}]",
            }

            # 执行Action
            if action_name == "Finish":
                step_record["final_answer"] = action_input
                self.history.append(step_record)
                return action_input

            observation = self._execute_action(action_name, action_input)
            step_record["observation"] = observation
            self.history.append(step_record)

            # 构建Observation反馈
            observation_text = f"Observation: {observation}"

            # 将结果加入对话历史
            messages.append({
                "role": "assistant",
                "content": f"Thought: {thought}\nAction: {action_name}[{action_input}]"
            })
            messages.append({
                "role": "user",
                "content": observation_text
            })

        return "抱歉，经过多次尝试仍无法找到满意的答案。我已有的信息不足以给出可信的回答。"

    def get_reasoning_trace(self) -> str:
        """获取完整的推理轨迹"""
        trace = []
        for step in self.history:
            trace.append(f"\n=== 第{step['iteration']}步 ===")
            trace.append(f"Thought: {step['thought']}")
            trace.append(f"Action: {step['action']}")
            if 'observation' in step:
                trace.append(f"Observation: {step['observation']}")
            if 'final_answer' in step:
                trace.append(f"\n>>> Final Answer: {step['final_answer']}")
        return "\n".join(trace)
```

### 注册和使用工具

```python
# 创建Agent实例
agent = ReActAgent(model_name="gpt-4")

# 定义搜索工具（模拟）
def search_web(query: str) -> str:
    """模拟网络搜索"""
    # 实际项目中这里会调用搜索API
    # 此处用模拟数据演示
    knowledge_base = {
        "诺贝尔物理学奖 2025": "2025年诺贝尔物理学奖授予...",
        "巴黎人口": "巴黎市区人口约216万（2025年）",
        "柏林人口": "柏林人口约385万（2025年）",
    }
    for key in knowledge_base:
        if all(word in query for word in key.split()):
            return knowledge_base[key]
    return f"未找到关于'{query}'的搜索结果。"

# 定义计算器工具
def calculator(expression: str) -> str:
    """安全地计算数学表达式"""
    try:
        # 只允许数字和基本运算符
        if re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', expression):
            result = eval(expression)
            return str(result)
        return "表达式包含不允许的字符"
    except Exception as e:
        return f"计算错误：{str(e)}"

# 注册工具
agent.register_tool(Tool(
    name="search",
    description="搜索互联网获取最新信息。输入搜索关键词。",
    func=search_web,
    parameters={"query": "搜索关键词"}
))

agent.register_tool(Tool(
    name="calculate",
    description="执行数学计算。输入合法的数学表达式。",
    func=calculator,
    parameters={"expression": "数学表达式，如 3850000 - 2160000"}
))

# 运行
question = "巴黎和柏林哪个城市人口更多？多多少？"
answer = agent.run(question)
print("=== 最终答案 ===")
print(answer)
print("\n=== 推理轨迹 ===")
print(agent.get_reasoning_trace())
```

### ReAct Prompt模板（用于直接调用LLM API）

如果你不使用框架，直接通过API实现ReAct，可以使用以下Prompt模板：

```
System Prompt:
你是一位ReAct智能体。你需要通过 思考(Thought) → 行动(Action) → 观察(Observation)
的循环来解决问题。

可用工具：
- search[query]: 搜索网络信息
- calculate[expression]: 执行数学计算
- lookup[entity]: 查询知识库中的实体信息

格式要求（严格遵循）：
Thought: [你的思考过程]
Action: [工具名称[参数]]
Observation: [工具返回结果]

当你准备回答时：
Thought: 我已收集到足够信息
Action: Finish[你的最终答案]

---

User: 2025年诺贝尔物理学奖得主是谁？

Assistant:
Thought: 用户询问2025年诺贝尔物理学奖得主。这是一个近期事件，
可能不在我的训练数据中。我应该搜索最新信息。
Action: search[2025年诺贝尔物理学奖得主]

[系统自动填入Observation]

User:
Observation: 2025年诺贝尔物理学奖授予了Pierre Agostini、
Ferenc Krausz和Anne L'Huillier，以表彰他们在阿秒物理学领域的贡献。

Assistant:
Thought: 我已获得2025年诺贝尔物理学奖得主的完整信息。
可以整理并回答用户的问题。
Action: Finish[2025年诺贝尔物理学奖授予了三位科学家：
1. Pierre Agostini（皮埃尔·阿戈斯蒂尼）
2. Ferenc Krausz（费伦茨·克劳斯）
3. Anne L'Huillier（安妮·吕利耶）
他们的获奖原因是"为研究物质中的电子动力学而产生阿秒光脉冲的实验方法"。]
```

## ReAct在主流框架中的实现

### LangChain中的ReAct

LangChain提供了开箱即用的ReAct Agent：

```python
from langchain.agents import initialize_agent, AgentType
from langchain.agents import Tool
from langchain.chat_models import ChatOpenAI
from langchain.tools import DuckDuckGoSearchRun

# 定义工具
search = DuckDuckGoSearchRun()
tools = [
    Tool(
        name="Search",
        func=search.run,
        description="搜索互联网获取最新信息。输入搜索查询。"
    ),
]

# 初始化LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# 创建ReAct Agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # ReAct模式
    verbose=True,  # 显示每一步的Thought, Action, Observation
    max_iterations=5,
    handle_parsing_errors=True,
)

# 运行
result = agent.run("2025年诺贝尔物理学奖得主是谁？")
print(result)
```

LangChain的ReAct Agent在内部使用了以下默认Prompt（简化版）：

```
Answer the following questions as best you can.
You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}
```

### AutoGPT/BabyAGI中的ReAct

AutoGPT和BabyAGI虽然更复杂，但其核心循环也是ReAct的变体：

```
AutoGPT的核心循环（简化）：

1. Thought: "我需要完成用户的目标：'帮我研究电动汽车市场并撰写报告'"
2. Action: 生成任务列表
   - 搜索电动汽车市场数据
   - 分析主要品牌市场份额
   - 撰写总结报告
3. Thought: "先执行第一个任务：搜索市场数据"
4. Action: google_search("2025电动车全球销量")
5. Observation: [搜索结果显示...]
6. Thought: "数据收集完毕，开始分析..."
   ...（循环继续）
```

核心区别在于AutoGPT增加了：
- 任务管理器：将大目标拆解为子任务队列
- 记忆系统：将中间结果持久化存储
- 自我提示：在每次循环开始时回顾总体目标和进度

**Image-Prompt(ReAct Frameworks Integration):**
```
A flat-design minimalist 2D vector illustration showing the ReAct pattern implemented across popular frameworks. Three horizontally arranged rounded panels, each containing a simplified framework icon: a chain link for LangChain, a gear for AutoGPT, and a baby bottle for BabyAGI. Below each icon, the same Thought-Action-Observation mini-cycle is drawn in thin blue #409EFF lines. White background, deep blue #1a1a2e labels, centered symmetrical composition.
```

## 经典案例深度走读

### 案例：用ReAct回答"2025年诺贝尔物理学奖得主是谁？"

让我们逐帧分析一个完整的ReAct执行过程：

```
═══════════════════════════════════════════
第1步：初始化
═══════════════════════════════════════════

Question: 2025年诺贝尔物理学奖得主是谁？

═══════════════════════════════════════════
第2步：第一次推理
═══════════════════════════════════════════

Thought: 用户询问的是2025年的诺贝尔物理学奖得主。
        我的训练数据截止于2024年初，不包含2025年的信息。
        如果直接生成答案，很可能是错误的（幻觉）。
        正确做法：使用搜索工具获取最新信息。

Action: search[2025 诺贝尔 物理学奖 得主]

Observation: 搜索结果(1-3):
1. 2025年诺贝尔物理学奖揭晓 - 诺贝尔奖官网
   2025年10月7日...2025年诺贝尔物理学奖授予...
2. Wikipedia: 诺贝尔物理学奖得主列表
   2025年 - ...
3. 2025诺贝尔物理学奖解读 - 知乎专栏
   ...

═══════════════════════════════════════════
第3步：分析搜索结果
═══════════════════════════════════════════

Thought: 搜索结果返回了多条相关信息。第一条来自诺贝尔奖官网，
        可信度最高。我需要获取详细信息。

Action: search[2025诺贝尔物理学奖 阿秒物理]

Observation: 详细搜索结果：
2025年诺贝尔物理学奖授予Pierre Agostini、Ferenc Krausz
和Anne L'Huillier，以表彰他们在阿秒物理学领域的开创性工作。

═══════════════════════════════════════════
第4步：验证信息
═══════════════════════════════════════════

Thought: 我需要进一步确认获奖者的具体贡献和基本信息。
        Anne L'Huillier是第五位获得诺贝尔物理学奖的女性，
        这一点也值得在回答中提及。

Action: search[Anne L'Huillier 阿秒物理 贡献]

Observation: Anne L'Huillier（1958年出生，法国/瑞典物理学家），
她在1987年发现激光与气体原子相互作用产生高次谐波的现象...

═══════════════════════════════════════════
第5步：给出最终答案
═══════════════════════════════════════════

Thought: 我已获得足够的信息：
        - 获奖者：Pierre Agostini、Ferenc Krausz、Anne L'Huillier
        - 获奖原因：阿秒物理学实验方法
        - 额外背景：Anne L'Huillier是第五位女性物理奖得主
        
        可以组织语言给出清晰、准确的回答了。

Action: Finish[2025年诺贝尔物理学奖授予了三位科学家：
        
1. **Pierre Agostini（皮埃尔·阿戈斯蒂尼）** - 法国物理学家
2. **Ferenc Krausz（费伦茨·克劳斯）** - 匈牙利-奥地利物理学家  
3. **Anne L'Huillier（安妮·吕利耶）** - 法国/瑞典物理学家

获奖原因：表彰他们"为研究物质中的电子动力学而产生
阿秒光脉冲的实验方法"。这项技术使人类首次能够以阿秒
（10^-18秒）的时间分辨率观测电子运动，开创了阿秒物理学
这一全新研究领域。Anne L'Huillier也成为历史上第五位
获得诺贝尔物理学奖的女性。]
```

### 关键观察：ReAct的两个核心价值

从这个案例中可以清晰地看到ReAct的两个核心价值：

**1. 事实接地（Factual Grounding）**

纯CoT可能生成"2025年诺贝尔物理学奖得主是..."然后基于模型内部的统计模式猜测一个名字。但ReAct通过搜索获取了真实信息，避免了幻觉。推理的每一步都有外部事实作为支撑。

**2. 推理可追溯（Interpretability）**

每一步的Thought/Action/Observation都是透明的。如果最终答案有误，你可以精确定位是哪一步出了问题——是搜索词选择不当？是信息解读错误？还是推理逻辑有漏洞？纯CoT的"黑盒推理"无法提供这种粒度的可审计性。

**Image-Prompt(ReAct Case Study Step-by-Step):**
```
A flat-design minimalist 2D vector illustration of the ReAct step-by-step execution trace. Five vertically stacked rounded rectangular cards, each representing one iteration step, numbered 1-5 on the left side. Each card shows a mini Thought-Action-Observation triplet with thin icons (brain, search magnifier, document). The cards are connected by downward arrows in #409EFF. The last card is highlighted with a light blue glow indicating the final answer. White background, deep blue #1a1a2e for numbering and labels.
```

## ReAct vs CoT vs Tool-Use 深度对比

### 三种模式的形式化描述

```
纯CoT模式：
  [思考1] → [思考2] → [思考3] → ... → [答案]
  
  特点：所有推理基于模型内部知识，无外部信息获取

纯Tool-Use模式：
  [工具调用1] → [结果1] → [工具调用2] → [结果2] → [答案]
  
  特点：直接调用工具，但缺乏明确的推理规划

ReAct模式：
  [思考] → [工具调用] → [观察] → [思考] → [工具调用] → [观察] → ... → [答案]
  
  特点：推理引导行动，行动反馈修正推理
```

### 具体场景对比

**场景：查询一支股票的合理估值**

| 步骤 | 纯CoT | 纯Tool-Use | ReAct |
|------|-------|------------|-------|
| 1 | 思考："特斯拉的PE大约在..." | 调用stock_price("TSLA") | 思考："估值需要PE和行业对比" |
| 2 | 思考："对比行业平均..." | 调用industry_pe("汽车") | 行动：stock_price("TSLA") |
| 3 | 回答："特斯拉估值偏高" | 回答："股价240美元" | 观察："股价240，EPS 3.2" |
| 4 | （可能基于过时数据） | （没有推理过程） | 思考："PE=75，需要行业对比" |
| 5 | | | 行动：industry_pe("电动汽车") |
| 6 | | | 观察："行业PE中位数25" |
| 7 | | | 思考：对比结果 |
| 8 | | | 回答：整段估值分析 |

**场景：代码调试**

```python
# 纯CoT：
"这段代码的问题可能是循环中的变量未初始化...建议添加..."
# 可能分析了一个不存在的问题

# 纯Tool-Use：
# 直接运行代码 → 看到报错 → 不知道含义
run_code("buggy.py")
# "NameError: name 'x' is not defined"
# "好的，错误是变量未定义" ← 没有分析，只是复述

# ReAct：
Thought: 先运行代码看具体报什么错
Action: run_code("buggy.py")
Observation: "NameError on line 23: name 'data' is not defined"

Thought: Line 23使用了'data'但未定义。
        可能的原因：①拼写错误 ②变量作用域问题 ③赋值被跳过
        需要检查上下文。

Action: read_file("buggy.py", start_line=15, end_line=30)
Observation: [显示代码内容]

Thought: 啊，'data'在if分支中定义，但line 23在if外部访问。
        需要将'data'的声明移到if外部（初始化为None），
        或者在外部也定义它。

Action: Finish("问题在第23行，变量'data'在if分支内定义，
        但在分支外部被访问。修复方式：在if之前先初始化data = None。")
```

### 三种模式的综合对比表

```
+------------------+-----------+----------+------------+
| 维度             | CoT       | Tool-Use | ReAct      |
+------------------+-----------+----------+------------+
| 推理质量         | 高        | 低       | 高         |
| 事实准确性       | 低/不确定 | 高       | 高         |
| 外部知识获取     | 无        | 有       | 有         |
| 规划能力         | 有        | 无       | 有         |
| 可解释性         | 中        | 低       | 高         |
| 错误恢复能力     | 差        | 中       | 好         |
| 幻觉风险         | 高        | 低       | 低         |
| API调用成本      | 最低      | 中       | 最高       |
| 实现复杂度       | 低        | 中       | 较高       |
| 典型延迟         | 短        | 中       | 较长       |
+------------------+-----------+----------+------------+
```

### 何时选择ReAct

- 问题需要**超出训练数据范围的最新信息**（新闻、股价、天气等）
- 答案需要**精确数值计算**，不能靠模型"估计"
- 需要调用**特定API或数据库**获取私有数据
- 任务需要**多步交互**（如代码调试、数据查询分析）
- 答案需要**可审计、可验证**（合规场景、研究场景）

不需要ReAct的场景：
- 纯知识问答（"光的传播速度是多少"）
- 纯创意任务（"写一首诗"）
- 简单的格式转换（"把这段文字翻译成英文"）

**Image-Prompt(CoT vs ToolUse vs ReAct Three-Way Comparison):**
```
A flat-design minimalist 2D vector illustration showing a three-way comparison. Three vertical columns, each with a header label: "CoT" (left), "Tool-Use" (center), "ReAct" (right, highlighted with #409EFF border). Each column shows its reasoning pattern as a simplified diagram: CoT shows a straight chain of thought bubbles, Tool-Use shows isolated tool calls, ReAct shows interleaved thought bubbles and tool icons in a dynamic loop. A checkmark table below compares key dimensions (reasoning, accuracy, explainability) with blue checkmarks for ReAct. White background, deep blue #1a1a2e text.
```

## ReAct的局限与改进

### 局限1：工具调用错误

模型可能生成无效的工具调用格式或错误的参数，导致执行失败。处理方式：

```python
# 错误处理与重试
max_retries = 3
for retry in range(max_retries):
    try:
        observation = execute_tool(action_name, action_input)
        break
    except ToolError as e:
        if retry == max_retries - 1:
            observation = f"工具多次执行失败：{e}"
        else:
            prompt = f"工具执行失败：{e}\n请修正后重试。"
            response = llm(prompt)  # 让LLM重新生成Action
```

### 局限2：无限循环

当模型陷入"搜索→无结果→换关键词搜索→仍无结果→再换..."的循环时：

```python
# 硬限制和智能检测
if iteration > max_iterations:
    return summary_from_collected_info()

# 检测重复Action
if action in recent_actions:
    prompt = ("你已经多次执行了相同的操作。"
              "请尝试不同的方法或基于已有信息给出回答。")
```

### 局限3：上下文窗口溢出

每次循环都向对话历史添加Thought、Action和Observation，长任务会超出上下文限制：

```python
# 摘要压缩策略
if token_count(messages) > threshold:
    # 将历史步骤压缩为摘要
    summary = summarize_steps(agent.history)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"之前的进展摘要：{summary}\n\n继续执行。"}
    ]
```

**Image-Prompt(ReAct Limitations and Solutions):**
```
A flat-design minimalist 2D vector illustration depicting three common ReAct limitations as warning cards. Left card: a broken wrench icon representing "Tool Errors" with a retry arrow. Center card: an infinity symbol crossed out representing "Infinite Loop" with a stop sign. Right card: an overflowing text box representing "Context Overflow" with a compression funnel. Each card has a small solution indicator below in #409EFF. White background, deep blue #1a1a2e labels, clean rounded cards in symmetrical layout.
```

## 实践建议

1. **精心设计工具描述**：模型完全依赖工具描述来理解工具的用途。描述应该清晰、具体，包含典型的输入/输出示例。

2. **从简化版开始**：先用search和calculator两个基础工具测试ReAct循环，确认基本流程正确后再增加更多工具。

3. **设置防御性限制**：max_iterations、超时、预算上限都是必要的安全措施。

4. **记录和审计推理轨迹**：将每一步的Thought/Action/Observation完整记录，这对于调试和优化至关重要。

5. **结合Few-Shot示例**：在System Prompt中给出2-3个完整的ReAct执行示例，显著降低格式错误率。

6. **分层设计工具**：不要把所有功能堆在一层。使用分层工具——基础层（search、calculate）、中间层（analyze、summarize）、应用层（generate_report）。

**Image-Prompt(ReAct Best Practices Checklist):**
```
A flat-design minimalist 2D vector illustration of a best practices guide. A centered clipboard or checklist icon with six checkmark items in #409EFF, each representing a practice: tool design (wrench), start simple (seedling), defensive limits (shield), audit trail (footprints), few-shot examples (document with star), layered tools (stacked blocks). Clean white background, deep blue #1a1a2e for numbering, rounded rectangular layout with comfortable spacing.
```

## 总结

ReAct模式将AI推理带入了"知行合一"的新范式。它不再是凭空想象，而是在思考与行动之间建立起持续的反馈循环——思考引导行动，行动产生的观察又反过来修正和充实思考。

ReAct的三个核心原则：
- **不知道就查**：承认知识边界，通过行动获取答案
- **想清楚再动**：每次行动前都有明确的推理和目标
- **根据结果调整**：观察行动结果后重新评估，动态调整策略

ReAct开启了Agent时代的大门。从LangChain到AutoGPT，从代码助手到智能客服，几乎所有现代AI Agent系统都以某种形式继承了ReAct的核心思想。理解ReAct，不仅是学习一种技术，更是理解AI如何从"静态回答者"进化为"动态行动者"的关键。

**Image-Prompt(ReAct Summary Core Principles):**
```
A flat-design minimalist 2D vector illustration summarizing the three core principles of ReAct. Three vertically arranged rounded cards, each with a prominent number (1, 2, 3) in #409EFF circle. Card 1: a question mark transitioning to a magnifying glass (icon: "Don't know? Search"). Card 2: a brain with a directional arrow (icon: "Think before acting"). Card 3: a looping feedback arrow with adjustment nodes (icon: "Adapt based on results"). A subtle graduation cap icon at the top reinforces the educational context. White background, deep blue #1a1a2e text.
```
