# CrewAI多智能体协作框架

## 引言：当单个Agent不够用的时候

在AI应用开发的进程中，我们经历了清晰的发展阶段：最初是用单个LLM回答问题，然后是让LLM调用工具完成任务（单Agent），现在则进入了一个新阶段——**让多个AI智能体像一个团队一样协作**。

想象一个真实的市场调研项目：需要有人搜索行业数据（研究员）、有人分析数据趋势（分析师）、有人将分析结果写成专业报告（撰写者）。在传统的单Agent架构中，你需要编写复杂的状态机来模拟这个流程。而**CrewAI**的设计理念是：直接创建一个虚拟的"团队"，每个成员各司其职，在同一个Crew中有序协作。

CrewAI由Joao Moura于2023年创建，是一款专注于**多Agent协作编排**的Python框架。它的设计哲学非常直观：**像管理人类团队一样管理AI Agent团队**。

**Image-Prompt(multi-agent team collaboration concept):** A flat-design minimalist 2D vector illustration introducing CrewAI multi-agent collaboration. A horizontal evolution showing three stages: "Single LLM" (one person icon answering questions) → "Single Agent" (one robot with tool icons) → "Multi-Agent Team" (three specialized avatar icons - Researcher with magnifying glass, Analyst with chart, Writer with pen - collaborating around a shared project). The multi-agent stage highlighted with tech light blue #409EFF glow. White background with dark blue #1a1a2e labels. Academic evolution of AI systems visualization.

---

## CrewAI的核心设计理念

### "角色-任务-团队"三层模型

CrewAI将多Agent协作抽象为三个核心概念，层层嵌套：

```
Crew（团队）
├── Agent 1（角色：市场分析师）
│   ├── Task A（搜集行业数据）
│   └── Task B（分析竞争格局）
├── Agent 2（角色：数据科学家）
│   ├── Task C（处理原始数据）
│   └── Task D（构建预测模型）
└── Agent 3（角色：报告撰写者）
    └── Task E（撰写最终报告）
```

这个模型的优势在于：
- **Agent = 角色**：定义"谁来做"，包括专业知识、性格特点和目标
- **Task = 任务**：定义"做什么"，包括具体输入、期望输出和完成标准
- **Crew = 团队**：定义"怎么做"，包括协作流程和执行顺序

### 与单Agent架构的区别

| 维度 | 单Agent（LangChain Agent等） | 多Agent（CrewAI） |
|------|---------------------------|-------------------|
| 任务处理 | 一个Agent处理所有事情 | 多个Agent分工协作 |
| 专业深度 | 通才型，每个领域都不够深 | 每个Agent是特定领域的专家 |
| 复杂任务 | 容易遗漏细节或产生幻觉 | 多视角交叉验证 |
| 调试难度 | 相对简单 | 需要追踪Agent间的信息流 |
| Token消耗 | 一次任务可能反复调用工具 | 多个Agent各自消耗Token |
| 适用场景 | 明确步骤的单一任务 | 需要多角色协作的复杂项目 |

---

## Agent角色定义详解

在CrewAI中，Agent是团队的基本成员。一个Agent的定义决定了它的"职业身份"和"行为模式"。

### 核心属性：role、goal、backstory

这三个属性是Agent的灵魂，它们共同决定了Agent在团队中的行为表现。

```python
# pip install crewai crewai-tools

from crewai import Agent
from crewai import LLM

# 配置LLM（CrewAI支持多种LLM提供商）
llm = LLM(
    model="gpt-4",
    temperature=0.7,
)

# === 1. 基本信息属性 ===
market_analyst = Agent(
    # --- role（角色）：定义Agent的专业身份 ---
    # 这个字段直接影响Agent在系统提示中的定位
    # 应该简洁、具体，包含明确的领域关键词
    role="资深市场分析师",

    # --- goal（目标）：定义Agent的核心任务目标 ---
    # 这是Agent行为的"北极星"，所有决策都应该服务于这个目标
    # 好的goal应该：具体、可衡量、与最终产出直接相关
    goal="深入分析目标市场，识别关键趋势、机会和竞争威胁，"
         "提供数据驱动的市场洞见",

    # --- backstory（背景故事）：赋予Agent"人格"和"专业知识" ---
    # 这是最容易被低估但最关键的属性
    # 一个生动的backstory让Agent像真人一样思考和决策
    backstory=(
        "你是一位拥有15年经验的市场研究专家，曾在麦肯锡和BCG工作过。"
        "你擅长从碎片化的信息中提炼出清晰的趋势图景，"
        "习惯于用SWOT框架和波特五力模型分析市场。"
        "你的分析风格：数据驱动、结构清晰、注重可操作性建议。"
        "你相信一个好的市场分析不仅描述现状，更要预见未来。"
    ),

    # --- 其他可选属性 ---
    llm=llm,                 # 指定Agent使用的LLM
    verbose=True,            # 打印详细的执行日志
    allow_delegation=True,   # 是否允许将任务委派给其他Agent
    max_iter=15,             # 最大推理迭代次数（防止无限循环）
    max_rpm=10,              # 每分钟最大API请求数（限流控制）

    # 可以使用自定义工具
    # tools=[search_tool, browser_tool],
)

# === 2. 设计Agent属性的最佳实践 ===

# 不良示例：过于模糊
bad_agent = Agent(
    role="助手",
    goal="帮助用户",
    backstory="你是一个AI助手",
    # → 问题：太宽泛，Agent的行为难以预测
)

# 良好示例：高度具体
good_agent = Agent(
    role="Python代码审查专家",
    goal="识别代码中的安全漏洞、性能瓶颈和可维护性问题，"
         "提供具体的改进建议和重构方案",
    backstory=(
        "你是一位资深的后端开发工程师和代码审查者，拥有10年的Python开发经验。"
        "你曾在多家科技公司担任技术负责人，审查过数千个PR。"
        "你的审查风格注重实际：不仅指出问题，更关注解决问题的方案是否经济可行。"
        "你擅长在代码优雅性和工程实用性之间找到平衡。"
        "你的座右铭：'好的代码评审不是挑剔，而是赋能。'"
    ),
    llm=llm,
)
```

### backstory如何影响Agent行为

backstory通过以下机制影响Agent的行为：

1. **知识范围边界**：背书中提到的专业知识领域，Agent会更深入处理；未提及的领域，Agent会意识到自己的局限
2. **表达风格**：背书中的"分析风格"等描述会影响Agent的输出语气和格式
3. **决策倾向**：背书中隐含的价值观和优先级会影响Agent在多选项之间的选择
4. **协作态度**：背书中有关团队角色的描述会影响Agent与其他成员的互动方式

**实验对比**：同样的任务，给Agent设置不同的backstory，产出的分析报告在深度、角度和表达方式上会有显著差异。这证明了backstory不是装饰品，而是Agent能力的核心组成部分。

### Agent属性设计检查清单

```
在设计Agent时，问自己以下问题：

role:
□ 是否包含专业领域关键词？（如"市场分析师"而非"助手"）
□ 是否在8个词以内？
□ 是否能让同领域的真人也认同这个头衔？

goal:
□ 是否与团队总目标高度对齐？
□ 是否包含了产出标准？（如"提供数据驱动的洞见"）
□ 是否用1-2句话就能清晰表达？

backstory:
□ 是否包含了专业经验年限或级别？（如"15年经验"）
□ 是否提到了工作方法或分析框架？（如"SWOT框架"）
□ 是否描述了工作风格或偏好？
□ 是否有"人格化"的细节？（如座右铭、特殊经历）
□ 读起来是否像一个真人的LinkedIn简介？
```

---

## 任务（Task）定义与委派机制

Task是CrewAI的工作单元，定义了团队成员需要完成的具体工作。

### Task核心属性详解

```python
from crewai import Task

# === 完整的Task定义示例 ===

# 创建一个数据收集任务
data_collection_task = Task(
    # --- description（任务描述）：说明要做什么 ---
    # 应该包含：具体行动、输入数据、分析维度
    description=(
        "收集目标市场（北美SaaS市场）的关键数据："
        "1. 使用SearchTools搜索以下维度的信息："
        "   - 市场规模和增长率（2020-2024）"
        "   - 主要竞争对手及其市场份额"
        "   - 技术发展趋势（AI、云计算相关）"
        "   - 客户需求和痛点"
        "2. 将收集到的数据按维度分类整理"
        "3. 标注每个数据点的来源和可信度"
        "4. 识别数据中呈现的关键模式和异常点"
    ),

    # --- expected_output（期望输出）：明确产出标准 ---
    # 越具体越好，便于后续Agent使用该输出
    expected_output=(
        "一份结构化的市场数据报告（Markdown格式），包含：\n"
        "- 执行摘要（100字以内）\n"
        "- 市场概况：规模、增长率、关键指标\n"
        "- 竞争格局：Top 5竞争对手详细分析表\n"
        "- 技术趋势：影响市场的核心技术清单\n"
        "- 数据来源附录：每个数据的原始来源链接"
    ),

    # --- agent（绑定执行者） ---
    # 必须是之前创建的Agent实例
    agent=market_analyst,

    # --- 可选属性 ---
    context=None,            # 前置任务列表，这些任务的输出作为本任务的输入
    async_execution=False,   # 是否异步执行（不等待完成就继续）
    output_file="market_data_report.md",  # 将输出保存到文件
    human_input=False,       # 是否在执行前需要人工确认
    expected_output_format=None, # 输出格式约束（Pydantic模型）
)
```

### 任务依赖与上下文传递

Task之间可以通过`context`参数建立依赖关系。后续Task可以直接访问前置Task的输出。

```python
# === 任务链示例：市场调研的完整任务流 ===

# Task 1: 收集原始数据
collect_data = Task(
    description="收集目标市场的原始数据，包括行业报告、新闻、财报等...",
    expected_output="一份包含所有原始数据及其来源的结构化文档",
    agent=market_analyst,
)

# Task 2: 数据分析（依赖Task 1的输出）
analyze_data = Task(
    description=(
        "基于收集到的原始数据，进行深度分析："
        "1. 识别市场增长的主要驱动力和阻碍因素"
        "2. 绘制竞争定位图（基于价格和功能两个维度）"
        "3. 计算市场集中度（CR4和HHI指数）"
        "4. 预测未来12-18个月的市场变化趋势"
    ),
    expected_output=(
        "一份深度市场分析报告，包含：\n"
        "- SWOT分析矩阵\n"
        "- 竞争定位图描述\n"
        "- 趋势预测及置信度评估\n"
        "- 战略建议（进军策略、差异化方向）"
    ),
    agent=data_scientist,
    context=[collect_data],  # ← 使用Task 1的输出作为上下文
)

# Task 3: 撰写最终报告（依赖于前两个任务）
write_report = Task(
    description=(
        "基于市场调研数据和分析结论，撰写一份面向高管层的战略建议报告。"
        "报告要求：逻辑清晰、数据支撑、建议具体可操作。"
        "目标读者：CEO、COO（非技术背景）"
    ),
    expected_output=(
        "一份专业的战略建议报告，包含：\n"
        "1. 执行摘要（Executive Summary）\n"
        "2. 市场全景图\n"
        "3. 竞争对手深度剖析\n"
        "4. 机会与风险评估\n"
        "5. 战略建议（短期+中期+长期）\n"
        "6. 下一步行动计划"
    ),
    agent=report_writer,
    context=[collect_data, analyze_data],  # ← 同时使用前两个任务的输出
    output_file="final_strategy_report.md",
)

# context的工作原理：
# Task执行前，context中所有前置Task的输出会被拼接并注入到当前Task的提示中
# 这让后续Agent能够"看到"前面Agent的工作成果，实现信息传递
```

### 异步任务执行

当多个任务相互独立时，可以使用`async_execution=True`让它们并行执行，大幅提升效率。

```python
# === 独立任务的并行执行 ===

# 这三个任务互不依赖，可以同时执行
competitor_research = Task(
    description="搜索并分析Top 5竞争对手的产品、定价和营销策略",
    expected_output="竞争对手分析表（含产品、定价、营销策略对比）",
    agent=market_analyst,
    async_execution=True,  # ← 异步执行
)

customer_research = Task(
    description="搜索目标市场中目标客户群的规模、画像和核心需求",
    expected_output="目标客户画像报告",
    agent=market_analyst,
    async_execution=True,  # ← 异步执行
)

tech_trend_research = Task(
    description="搜索当前行业的最新技术趋势和创新方向",
    expected_output="技术趋势概览报告",
    agent=market_analyst,
    async_execution=True,  # ← 异步执行
)

# 这三个任务将同时启动，全部完成后才继续执行后续任务

# 汇总任务（等待上面三个异步任务完成后再执行）
synthesis_task = Task(
    description="整合竞争对手分析、客户画像和技术趋势三份报告，形成综合市场洞察",
    expected_output="综合市场洞察报告",
    agent=market_analyst,
    context=[competitor_research, customer_research, tech_trend_research],
    # 没有async_execution，默认同步执行
)
```

---

## Crew组建和执行流程

Crew是团队的"管理者"，负责协调Agent完成所有Task。

### Sequential Process（顺序执行）

任务按添加顺序依次执行，每个任务的输出作为下一个任务的上下文。这是最直观的执行模式。

```python
from crewai import Crew, Process

# === 顺序执行 ===
# 适用场景：任务之间有明确的前后依赖关系
# 工作流：Task 1 → Task 2 → Task 3 → Task 4

sequential_crew = Crew(
    agents=[analyst, researcher, writer],
    tasks=[task1, task2, task3, task4],
    process=Process.sequential,  # 顺序执行模式
    verbose=True,
    memory=True,                 # 启用团队记忆（跨任务共享上下文）
    cache=True,                  # 启用结果缓存（相同输入不重复调用LLM）
    max_rpm=10,                  # 每分钟最大API请求数
)

# 启动Crew
result = sequential_crew.kickoff()

# 执行过程日志示例：
# [Crew] Starting sequential execution...
# [Task 1] Analyst working on "Data Collection"...
# [Task 1] Completed. Output: <analysis result>
# [Task 2] Researcher working on "Competitor Analysis"...
# [Task 2] Using context from Task 1...
# [Task 2] Completed. Output: <research result>
# ...
```

### Hierarchical Process（层级执行）

指定一个Manager Agent，由它来分析和分配任务，而不是按固定顺序执行。Manager Agent像一个项目经理，动态决定任务的执行顺序和Agent安排。

```python
# === 层级执行 ===
# 适用场景：复杂项目，任务之间存在动态依赖
# 工作流：Manager Agent分析所有任务 → 动态分配 → 监控执行 → 整合结果

# 创建Manager Agent
manager = Agent(
    role="市场研究项目经理",
    goal="高效管理市场研究项目，确保每个任务由最合适的专家完成，"
         "按时产出高质量的综合分析报告",
    backstory=(
        "你是一位经验丰富的项目经理，拥有PMP认证和10年管理咨询项目经验。"
        "你擅长评估任务优先级、匹配合适的人才、识别项目风险。"
        "你的管理风格：目标导向、数据驱动、注重沟通协调。"
        "你相信一个好的管理者不是在上面发号施令，而是为团队清除障碍。"
    ),
    llm=llm,
    allow_delegation=True,   # 允许将子任务委派给其他Agent
    verbose=True,
)

hierarchical_crew = Crew(
    agents=[market_analyst, data_scientist, report_writer],  # 执行团队
    tasks=[task1, task2, task3, task4],  # 所有任务
    manager_agent=manager,               # 指定管理者
    process=Process.hierarchical,        # 层级执行模式
    verbose=True,
    memory=True,
    planning=True,  # 启用计划模式：在执行前让Manager制定执行计划
)

# 启动Crew
result = hierarchical_crew.kickoff()

# 层级执行的优势：
# 1. Manager可以根据上下文动态调整任务分配
# 2. 遇到问题时Manager可以重新规划
# 3. 适合任务间关系复杂、需要灵活调度的场景
```

### Sequential vs Hierarchical 对比

| 维度 | Sequential（顺序） | Hierarchical（层级） |
|------|-------------------|---------------------|
| **执行方式** | 按添加顺序固定执行 | Manager动态分配调度 |
| **适用场景** | 步骤明确、依赖关系固定的项目 | 复杂多变、需要灵活调度的项目 |
| **可控性** | 高（开发者精确控制执行顺序） | 中（受Manager的LLM决策影响） |
| **Token消耗** | 较低 | 较高（Manager的调度决策消耗Token） |
| **执行效率** | 固定，可能不够优化 | 可能更高效（动态调度） |
| **调试难度** | 低（执行路径可预测） | 较高（执行路径取决于LLM决策） |
| **推荐使用** | 新手项目、标准化流程 | 复杂项目、创新性任务 |

---

## 多Agent协作实战案例：市场调研团队

下面构建一个完整的市场调研Crew，包含三个专业Agent协作完成一份综合市场分析报告。

```python
"""
多Agent市场调研团队 - 完整实战案例

Crew结构：
┌─────────────────────────────────────────────────┐
│                  Manager Agent                   │
│           (项目协调和质量控制)                     │
├────────────────┬────────────────┬───────────────┤
│  市场分析师      │  数据科学家      │  报告撰写者     │
│  (信息收集+      │  (数据分析+      │  (报告撰写+     │
│   竞品分析)      │   趋势建模)      │   可视化建议)   │
└────────────────┴────────────────┴───────────────┘
         │                 │                │
         ▼                 ▼                ▼
    市场数据结构化    数据建模与预测    最终综合报告

安装依赖:
pip install crewai crewai-tools langchain-openai
"""

import os
from datetime import datetime
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool, FileReadTool


# ===== 环境配置 =====
# 设置API密钥（实际使用时应从环境变量读取）
# os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
# os.environ["SERPER_API_KEY"] = "your-serper-api-key"

# 初始化LLM
# CrewAI支持各种LLM提供商，统一通过LLM类配置
llm = LLM(
    model="gpt-4",
    temperature=0.7,
    # 也可以使用其他模型:
    # model="anthropic/claude-3-opus-20240229",
    # model="gemini/gemini-pro",
)

# 初始化工具
search_tool = SerperDevTool()            # 搜索引擎工具
scrape_tool = ScrapeWebsiteTool()        # 网页抓取工具

print("=" * 70)
print(f"  市场调研Crew启动 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 70)


# ===== 第一步：定义Agent角色 =====

# Agent 1: 市场分析师 —— 负责信息收集和竞争分析
market_analyst = Agent(
    role="资深市场分析师",
    goal=(
        "全面收集和分析目标市场数据，识别市场结构、竞争格局和增长机会，"
        "提供数据支撑的市场进入策略建议"
    ),
    backstory=(
        "你是一位拥有15年经验的顶级市场分析师，曾在高盛和麦肯锡任职。"
        "你的专长是TMT（科技、媒体、电信）行业分析。"
        "你开发了一套独特的分析框架'MARKET-7'，涵盖市场规模(Market Size)、"
        "竞争强度(Activity)、监管环境(Regulation)、关键玩家(Key Players)、"
        "经济指标(Economics)、技术趋势(Technology)七个维度。"
        "你的每一份分析报告都会引用至少5个可靠数据源。"
        "你善于从不完整的信息中推断出合理的结论，并清晰地标注确定性级别。"
    ),
    tools=[search_tool, scrape_tool],
    llm=llm,
    verbose=True,
    allow_delegation=True,
    max_iter=20,
)

# Agent 2: 数据科学家 —— 负责数据分析、建模和预测
data_scientist = Agent(
    role="数据科学家",
    goal=(
        "对收集到的市场数据进行定量分析，构建趋势预测模型，"
        "将原始数据转化为可指导决策的洞察"
    ),
    backstory=(
        "你是一位数据科学家，拥有MIT统计学博士学位和8年的业界经验。"
        "你曾在Netflix担任增长数据科学家，用数据驱动过多个关键商业决策。"
        "你精通时间序列分析、回归建模和市场预测。"
        "你的工作哲学：'没有数据的观点只是猜测，数据不说话，但能让观点更有力。'"
        "你习惯用置信区间而非单点估计来表达预测结果。"
        "你特别擅长发现数据中的反直觉模式——那些表面看是噪音、"
        "实际上隐藏重要信号的数据特征。"
    ),
    tools=[search_tool],
    llm=llm,
    verbose=True,
    allow_delegation=True,
    max_iter=20,
)

# Agent 3: 报告撰写者 —— 负责将分析结果整合为专业报告
report_writer = Agent(
    role="战略报告撰写专家",
    goal=(
        "将市场分析数据和研究结论整合为一份面向高管层的、"
        "逻辑清晰、论据充分、建议可操作的综合战略报告"
    ),
    backstory=(
        "你是一位曾服务于多家Fortune 500企业的战略咨询顾问和商业作家。"
        "你的报告曾被《哈佛商业评论》和《经济学人》引用。"
        "你拥有将复杂分析转化为简洁有力叙述的独特天赋。"
        "你深谙'金字塔原理'——结论先行，以上统下，归类分组，逻辑递进。"
        "你的写作风格：每段不超过4句话，每句话承载一个观点，"
        "每个观点都有数据或事实支撑。"
        "你相信一份好的战略报告应该让读者在5分钟内掌握核心结论，"
        "30分钟内理解完整论证过程。"
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,  # 报告撰写者不需要委派任务
    max_iter=15,
)


# ===== 第二步：定义任务 =====

# Task 1: 市场规模与结构分析
market_sizing_task = Task(
    description=(
        "【目标市场】: 2024年北美企业AI Agent市场\n\n"
        "请完成以下调研：\n"
        "1. 搜索并汇总市场规模数据：总市场规模(TAM)、可服务市场(SAM)、"
        "   可获得市场(SOM)，涵盖2020-2027年的历史数据和预测\n"
        "2. 识别市场细分维度：按行业(金融、医疗、制造)、按企业规模(大/中/小型)、"
        "   按部署模式(云端/本地/混合)\n"
        "3. 计算各细分市场的增长率和占比\n"
        "4. 识别3-5个关键市场驱动力和2-3个市场阻碍因素\n"
        "5. 用Porter五力模型分析行业竞争结构\n\n"
        "数据要求：每个数据点标注来源和可信度评级(高/中/低)"
    ),
    expected_output=(
        "【市场结构与规模分析】\n\n"
        "一、市场规模概览\n"
        "  - TAM/SAM/SOM估算及增长率(GAGR)表格\n"
        "  - 2020-2027年市场规模趋势描述\n\n"
        "二、市场细分分析\n"
        "  - 按行业/企业规模/部署模式三个维度的细分数据表\n"
        "  - 最具增长潜力的细分市场Top 3\n\n"
        "三、市场驱动力与阻碍\n"
        "  - 驱动力分析(每个驱动力的影响程度评级)\n"
        "  - 阻碍因素分析(含应对策略建议)\n\n"
        "四、竞争结构分析\n"
        "  - Porter五力模型分析\n"
        "  - 行业集中度指标\n\n"
        "五、数据来源附录"
    ),
    agent=market_analyst,
    async_execution=True,  # 与其他市场分析任务并行执行
)

# Task 2: 竞争对手深度分析
competitor_analysis_task = Task(
    description=(
        "【分析目标】: 北美企业AI Agent市场Top 8竞争对手\n\n"
        "请完成以下分析：\n"
        "1. 识别并列出Top 8竞争对手（包括市场份额排名）\n"
        "2. 对每个竞争对手收集以下信息：\n"
        "   - 公司概况(成立时间、总部、融资情况、团队规模)\n"
        "   - 产品定位和核心功能\n"
        "   - 定价策略和商业模式\n"
        "   - 目标客户群体\n"
        "   - 技术优势和差异化特点\n"
        "3. 构建竞争定位矩阵：定价(横轴) × 功能完整度(纵轴)\n"
        "4. 识别市场空白和差异化机会\n"
        "5. SWOT分析：针对Top 3竞争对手各做简要SWOT"
    ),
    expected_output=(
        "【竞争对手深度分析报告】\n\n"
        "一、竞争全景图\n"
        "  - Top 8竞争对手概览表（名称、成立年份、融资总额、市场份额估算）\n\n"
        "二、竞争对手详细档案\n"
        "  - 每家公司的详细分析（按模板格式）\n\n"
        "三、竞争定位矩阵\n"
        "  - 基于定价和功能的竞争定位图文字描述\n"
        "  - 四个象限的典型代表和策略含义\n\n"
        "四、差异化机会识别\n"
        "  - 市场空白区域描述\n"
        "  - 潜在的蓝海策略方向\n\n"
        "五、Top 3 SWOT分析"
    ),
    agent=market_analyst,
    async_execution=True,  # 与市场规模任务并行执行
)

# Task 3: 数据建模与趋势预测
data_modeling_task = Task(
    description=(
        "【输入数据】: 前序任务产生的市场规模数据、竞争对手数据和行业趋势数据\n\n"
        "请完成以下分析：\n"
        "1. 基于历史数据(2020-2024)，构建市场增长的时间序列模型\n"
        "   - 计算CAGR(复合年增长率)\n"
        "   - 识别季节性模式和异常波动点\n"
        "2. 基于竞争数据，进行市场份额集中度分析：\n"
        "   - 计算CR4(前4大企业集中度)和HHI(赫芬达尔指数)\n"
        "   - 判断市场是分散型、寡头型还是垄断型\n"
        "3. 基于市场驱动力和阻碍因素，构建2025-2027年市场预测：\n"
        "   - 乐观、基准、悲观三种情景\n"
        "   - 每种情景对应的市场条件假设\n"
        "4. 识别3-5个先行指标(leading indicators)，用于监控市场变化"
    ),
    expected_output=(
        "【数据建模与预测分析】\n\n"
        "一、历史增长分析\n"
        "  - 2020-2024年市场规模变化曲线和增长率\n"
        "  - CAGR计算(整体及各细分市场)\n"
        "  - 关键转折点识别和归因分析\n\n"
        "二、竞争结构量化分析\n"
        "  - CR4和HHI指数计算结果\n"
        "  - 市场结构判断和演变趋势\n\n"
        "三、市场预测模型(2025-2027)\n"
        "  - 三种情景的预测数值和假设条件\n"
        "  - 敏感性分析：关键变量的影响权重\n\n"
        "四、先行指标体系\n"
        "  - 推荐的监控指标和阈值\n"
        "  - 基于先行指标的市场预警机制建议"
    ),
    agent=data_scientist,
    context=[market_sizing_task, competitor_analysis_task],
    # 等待前两个异步任务完成后再执行
)

# Task 4: 撰写综合战略报告
final_report_task = Task(
    description=(
        "【任务】: 整合所有前序分析，撰写一份面向CEO的高质量战略建议报告\n\n"
        "报告要求：\n"
        "1. 受众：公司CEO和董事会成员（非技术背景，关注战略和回报）\n"
        "2. 结构要求（严格遵循）：\n"
        "   - Executive Summary（1页，必须包含核心结论）\n"
        "   - 市场机遇（市场规模、增长率、关键趋势）\n"
        "   - 竞争格局（主要玩家、市场地图、差异化空间）\n"
        "   - 战略建议（进入策略、产品定位、定价策略）\n"
        "   - 财务预测（投入估算、预期回报、盈亏平衡时间线）\n"
        "   - 风险与缓解（Top 5风险及应对方案）\n"
        "   - 下一步行动（未来90天的具体行动计划）\n"
        "3. 质量标准：\n"
        "   - 每个断言都有数据支撑\n"
        "   - 使用图表描述（非实际图表，用结构化文字描述）\n"
        "   - 建议必须是可执行的，不是泛泛而谈\n"
        "   - 语言简洁有力，避免行业黑话"
    ),
    expected_output=(
        "一份完整的市场进入战略建议报告（Markdown格式），"
        "包含所有指定章节，长度约3000-5000字。"
    ),
    agent=report_writer,
    context=[market_sizing_task, competitor_analysis_task, data_modeling_task],
    output_file="market_entry_strategy_report.md",
)


# ===== 第三步：组建Crew并执行 =====

# 方案A：使用层级执行模式（推荐用于复杂项目）
market_research_crew = Crew(
    agents=[market_analyst, data_scientist, report_writer],
    tasks=[
        market_sizing_task,
        competitor_analysis_task,
        data_modeling_task,
        final_report_task,
    ],
    process=Process.hierarchical,  # 层级执行：由Manager动态调度
    manager_llm=llm,               # 使用LLM作为manager的决策引擎
    verbose=True,
    memory=True,                   # 启用团队记忆
    planning=True,                 # 在执行前先制定计划
    max_rpm=10,                    # 限制每分钟请求数
)

# 方案B：顺序执行（适合步骤明确的项目）
# market_research_crew = Crew(
#     agents=[market_analyst, data_scientist, report_writer],
#     tasks=[
#         market_sizing_task,
#         competitor_analysis_task,
#         data_modeling_task,
#         final_report_task,
#     ],
#     process=Process.sequential,  # 按顺序执行
#     verbose=True,
# )


# ===== 启动Crew =====
print("\n" + "=" * 70)
print("  开始执行市场调研任务...")
print("=" * 70 + "\n")

# kickoff启动整个Crew的执行
result = market_research_crew.kickoff()

# ===== 查看结果 =====
print("\n" + "=" * 70)
print("  市场调研任务完成！")
print("=" * 70)
print(f"\n最终报告预览:\n{str(result)[:500]}...")

# 完整的最终报告保存在 market_entry_strategy_report.md 文件中
print(f"\n完整报告已保存至: market_entry_strategy_report.md")

# ===== 可选的：查看执行指标 =====
print("\n" + "=" * 70)
print("  执行摘要")
print("=" * 70)
print(f"  总Token消耗: {market_research_crew.usage_metrics}")

# 关于每个任务的详细执行过程（含中间输出），可以在verbose=True时从控制台看到
```

---

## CrewAI的执行流程可视化

以上示例的完整执行流程可以用文字描述为：

```
┌──────────────────────────────────────────────────┐
│            Crew.kickoff() 启动                    │
└───────────────────┬──────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────┐
│  Manager Agent (Process.hierarchical模式下)       │
│  1. 审查所有Task的描述和依赖关系                   │
│  2. 制定执行计划(planning=True)                   │
│  3. 分配Task给相应的Agent                         │
└───────────────────┬──────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Task 1   │ │ Task 2   │ │          │
│ 市场规模  │ │ 竞争对手  │ │  (并行)  │
│ 分析     │ │ 分析     │ │          │
└────┬─────┘ └────┬─────┘ └──────────┘
     │            │
     └─────┬──────┘
           │ context传递
           ▼
     ┌──────────┐
     │ Task 3   │
     │ 数据建模  │
     │ 与预测   │
     └────┬─────┘
          │ context传递
          ▼
     ┌──────────┐
     │ Task 4   │
     │ 综合报告  │
     │ 撰写     │
     └────┬─────┘
          │
          ▼
     ┌────────────────┐
     │  最终产出:       │
     │  战略建议报告.md │
     └────────────────┘
```

---

## 与其他多Agent框架的对比

CrewAI并不是市场上唯一的多Agent框架，了解它与同类工具的差异有助于技术选型。

| 维度 | CrewAI | AutoGen (Microsoft) | LangGraph | ChatDev |
|------|--------|---------------------|-----------|---------|
| **设计哲学** | 角色-任务-团队，模仿人类团队 | Agent对话模式，灵活的消息传递 | 图结构状态机 | 软件开发团队仿真 |
| **协作方式** | Sequential / Hierarchical | 自定义对话模式 | 图定义的节点和边 | 瀑布式开发流程 |
| **学习曲线** | 低（直觉化设计） | 高（概念灵活但复杂） | 中（需理解图概念） | 中（专注软件开发） |
| **主要场景** | 通用多Agent协作 | 复杂多Agent对话系统 | 需要精细控制的工作流 | 自动化软件开发 |
| **任务分配** | 固定绑定 或 Manager动态分配 | 基于对话自主协商 | 图的拓扑结构决定 | 按软件开发生命周期分配 |
| **生态成熟度** | 快速增长，社区活跃 | 较成熟，微软支持 | 成熟，LangChain生态 | 较新，专注特定领域 |
| **中文支持** | 良好 | 中等 | 良好 | 良好（中国团队开发） |
| **生产就绪** | 基本可用 | 可用 | 成熟的生态 | 主要用于研究和原型 |

### 选型建议

```
你的场景是什么？

├─ 需要用户参与审批的流程 → AutoGen
├─ 软件开发自动化 → ChatDev
├─ 需要精确控制每个步骤 → LangGraph
└─ 希望快速上手、直觉化管理多Agent团队 → CrewAI ★推荐
```

---

## 注意事项与最佳实践

### 成本控制

多Agent系统最大的挑战之一是**Token消耗**。每个Agent的每一次推理都会消耗Token，多个Agent协作时成本可能迅速攀升。

```python
# 成本控制策略

# 1. 为不同Agent选择不同级别的模型
analyst = Agent(
    role="数据收集员",
    llm=LLM(model="gpt-3.5-turbo"),  # 简单任务用便宜模型
    # ...
)

strategist = Agent(
    role="战略分析师",
    llm=LLM(model="gpt-4"),          # 复杂推理用高级模型
    # ...
)

# 2. 限制迭代次数
Agent(..., max_iter=10)  # 防止无限循环

# 3. 启用结果缓存
Crew(..., cache=True)  # 相同输入不重复调用LLM

# 4. 控制上下文大小
# 在Task中明确要求精炼的输出，减少传递给后续Agent的上下文长度
```

### 调试技巧

1. **始终开启verbose=True**：CrewAI的详细日志会显示每个Agent的完整思考过程，是调试的主要手段。
2. **从小规模开始**：先用2个Agent验证流程，再扩展到更多。
3. **任务描述要极度具体**：模糊的描述会导致Agent产出不可预测的结果。
4. **检查中间输出**：将关键Task的output_file设置为独立文件，方便检查每个Agent的工作质量。

### 设计原则

1. **单一职责**：每个Agent只负责一类任务，不要试图制作一个"万能Agent"
2. **明确的交接标准**：Task的expected_output需要具体到后续Agent可以直接使用
3. **质量把关**：如果有条件，设置一个专门的Review Agent做最终质量检查
4. **版本管理提示词**：Agent的role、goal、backstory对行为影响极大，应该像管理代码一样管理这些文本

---

## 小结

CrewAI通过"角色-任务-团队"三层模型，将复杂的多Agent协作问题转化为直观的团队管理问题。它的核心价值在于**降低多Agent系统的设计和实现门槛**——你不需要编写复杂的状态机或消息路由逻辑，只需要定义好每个Agent的角色背景和任务说明，框架会处理一切。

**快速上手指南**：
1. 先明确你的团队需要哪些角色（通常3-5个Agent足够）
2. 为每个角色编写清晰具体的backstory（这是最重要的步骤）
3. 将工作拆分为多个Task，明确每个Task的输入输出
4. 选择Sequential还是Hierarchical执行模式
5. 小规模测试验证 → 调整Agent定义 → 扩大规模

**CrewAI最适合的场景**：
- 内容创作团队（调研员→撰稿人→编辑→发布者）
- 代码开发团队（架构师→开发者→测试员→文档者）
- 商业分析团队（分析师→策略师→报告撰写者）
- 客户支持升级链（一线支持→技术专家→管理层）

多Agent协作是AI应用的下一个重要方向——不是因为单个模型不够强大，而是因为现实世界的问题本身就是多角色、多视角的。CrewAI让构建这样的系统变得前所未有的简单。
