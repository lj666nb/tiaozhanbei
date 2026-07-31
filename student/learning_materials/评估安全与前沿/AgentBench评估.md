# AgentBench：综合智能体评估环境

## 引言

评估AI智能体的能力远比评估传统NLP模型复杂。一个聊天模型只需评估文本生成质量，但一个Agent需要评估它在真实环境中的感知、推理、决策和行动能力——就像评估一个员工不能只看他的笔试成绩，还要看他在实际工作中的表现。

**AgentBench** 是由清华大学、智谱AI等机构联合提出的首个系统性智能体评估基准。它设计了8个不同维度的交互式评测环境，覆盖从操作系统操作到数据库查询、从知识图谱推理到代码编程的多种场景，全面衡量一个Agent在实际任务中的综合能力。



**Image-Prompt(AgentBench-8-Scene-Radar-Dashboard):** A flat-design 2D vector illustration of a radar chart with eight axes radiating from a center labeled "AgentBench". Each axis represents an evaluation environment: OS, DB, KG, Web, DCG, LTP, Code, NLP. Color-coded filled areas in primary blue #409EFF at varying opacity. Clean white background, deep blue #1a1a2e labels, rounded corner dashboard panels with thin-line icons for each scene. Academic learning atmosphere, centered symmetrical layout, minimal flat vector style.

---

## 为什么需要AgentBench

### 传统评测的局限

| 传统评测方式 | 局限 |
|-------------|------|
| 选择题/填空题（MMLU, C-Eval） | 只测知识记忆，不测行动能力 |
| 生成质量评测（BLEU, ROUGE） | 只测文本质量，不测交互能力 |
| 单轮问答（QA数据集） | 只测单步推理，不测多步规划 |
| 固定工具调用测试 | 不测真实环境中的适应性 |

Agent的能力需要在一个**交互式、多步骤、需要工具使用和策略规划**的环境中来评估。这正是AgentBench的设计目标。

### AgentBench的核心创新

1. **真实交互**：Agent需要在真实环境中执行操作（如写Shell命令、写SQL、操作网页）
2. **多步推理**：任务通常需要多个步骤才能完成
3. **工具使用**：Agent需要自主选择和使用合适的工具
4. **标准化评估**：每个环境有明确的评估指标

**Image-Prompt(Traditional-vs-Agent-Evaluation-Comparison):** A flat-design side-by-side comparison illustration. Left side shows traditional evaluation methods (multiple-choice card, BLEU score gauge) in muted gray tones with a subtle X symbol overlay. Right side shows AgentBench interactive evaluation in primary blue #409EFF, featuring interconnected nodes of perception, planning, tool-use, and action in a circular flow. White background, rounded rectangular container cards, thin-line arrows connecting the stages, deep blue #1a1a2e accents. Academic minimal style with clean typography.

---

## 8大评测场景

### 场景总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      AgentBench 8大场景                          │
├───────────────┬──────────────┬──────────────┬──────────────────┤
│    OS交互     │   数据库操作  │  知识图谱推理 │   网页浏览       │
│  (OS)         │  (DB)        │  (KG)        │  (Web)           │
├───────────────┼──────────────┼──────────────┼──────────────────┤
│    数字卡牌   │   横向思维   │  代码编程    │   常规NLP        │
│  (DCG)        │  (LTP)       │  (Code)      │  (NLP)           │
└───────────────┴──────────────┴──────────────┴──────────────────┘
```

### 1. 操作系统交互（OS）

**场景描述**：Agent在一个真实的Linux Shell环境中操作，需要完成文件管理、进程控制、文本处理等任务。

**典型任务示例**：
```bash
# 任务：统计所有Python文件中包含"TODO"的行数
# Agent需要执行：
grep -r "TODO" *.py | wc -l

# 任务：找到最近修改的3个文件，打包为archive.tar.gz
# Agent需要执行：
ls -t | head -3 | xargs tar -czf archive.tar.gz
```

**评估维度**：
- 命令正确性：生成的Shell命令是否正确
- 任务完成率：是否成功达成任务目标
- 效率：使用的命令步骤是否最优
- 安全性：是否执行了危险操作（rm -rf等）

**对Agent的挑战**：
- 需要理解Linux文件系统和命令行工具
- 需要在多步操作中保持目标一致性
- 需要处理命令执行的错误和异常

### 2. 数据库操作（DB）

**场景描述**：Agent在一个SQL数据库环境中，需要通过编写SQL查询来回答问题和完成数据操作。

**典型任务示例**：
```sql
-- 任务：找出2023年销售额最高的5个产品类别及其增长率
-- Agent需要：
WITH yearly_sales AS (
    SELECT category, SUM(amount) as total
    FROM sales
    WHERE year = 2023
    GROUP BY category
),
prev_sales AS (
    SELECT category, SUM(amount) as total
    FROM sales
    WHERE year = 2022
    GROUP BY category
)
SELECT y.category, y.total,
       (y.total - p.total) / p.total * 100 as growth_rate
FROM yearly_sales y
JOIN prev_sales p ON y.category = p.category
ORDER BY y.total DESC
LIMIT 5;
```

**评估维度**：
- SQL语法正确性
- 查询结果准确性
- 查询效率（是否使用索引、避免全表扫描）
- 复杂查询能力（JOIN、子查询、窗口函数、CTE）

### 3. 知识图谱推理（KG）

**场景描述**：Agent需要在知识图谱上进行多跳推理，通过实体和关系链回答复杂查询。

**典型任务示例**：
```
知识图谱结构：
  [北京] --(位于)--> [中国]
  [中国] --(首都)--> [北京]
  [北京] --(人口)--> [2189万]

任务：北京的人口是多少？它所在国家的首都是什么？
Agent需要：
1. 查找北京的人口 → 2189万
2. 查找北京所在的国家 → 中国
3. 查找中国的首都 → 北京
```

**评估维度**：
- 多跳推理准确性
- 路径选择效率
- 缺失信息的处理
- 复杂查询的分解能力

### 4. 网页浏览（Web）

**场景描述**：Agent在模拟的网页浏览器环境中，需要通过点击、输入、滚动等操作来完成信息检索和交互任务。

**典型任务示例**：
```
任务：在电商网站上找到价格最低的蓝牙耳机，并加入购物车

Agent操作序列：
1. 在搜索框输入"蓝牙耳机"
2. 点击搜索按钮
3. 点击"按价格排序"
4. 查看第一个商品的价格和评价
5. 如果评价 >= 4星，点击"加入购物车"
```

**评估维度**：
- 页面元素识别和定位
- 操作序列规划
- 条件判断（if-then逻辑）
- 异常处理（页面加载失败、元素未找到）

### 5. 数字卡牌游戏（DCG）

**场景描述**：Agent在《炉石传说》风格的卡牌游戏环境中，需要进行策略规划和出牌决策。

**典型任务示例**：
```
当前状态：我方生命30，对方生命15
手牌：[火球术(6伤), 寒冰箭(3伤+冻结), 奥术飞弹(随机3伤)]
法力水晶：8/8

任务：在本回合内击败对手
Agent需要计算：
- 火球术(6) + 寒冰箭(3) + 奥术飞弹(3x随机) = 至少12伤
- 但奥术飞弹可能打偏 → 需要更大的伤害余量
- 最优方案：火球术 + 寒冰箭 + 英雄技能(1伤) = 10伤...
```

**评估维度**：
- 状态空间搜索
- 概率计算（随机效果）
- 资源管理（法力水晶）
- 胜率最大化策略

### 6. 横向思维谜题（LTP）

**场景描述**：Agent需要解决需要创造性思维和"跳出框架"能力的横向思维谜题。

**典型任务示例**：
```
谜题：一个男人住在十楼。每天他乘电梯到一楼去上班。
但回家时，他只乘到七楼，然后走楼梯到十楼，除非下雨天
或电梯里有其他人。为什么？

答案：这个男人是个侏儒，够不到十楼按钮，最多够到七楼。
下雨天他用伞按按钮，有人时可以请人帮忙。
```

**评估维度**：
- 非常规推理能力
- 假设探索
- 排除法使用
- 创造性问题解决

### 7. 代码编程（Code）

**场景描述**：Agent需要根据需求编写、调试和优化代码。

**典型任务示例**：
```python
# 任务：实现一个LRU缓存，支持get和put操作，O(1)时间复杂度
# Agent需要：

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> node
        # 双向链表：head <-> ... <-> tail
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node):
        prev = node.prev
        nxt = node.next
        prev.next = nxt
        nxt.prev = prev

    def _add(self, node):
        # 添加到head后面（最近使用）
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self._remove(node)
            self._add(node)
            return node.value
        return -1

    def put(self, key: int, value: int):
        if key in self.cache:
            self._remove(self.cache[key])
        node = Node(key, value)
        self._add(node)
        self.cache[key] = node
        if len(self.cache) > self.capacity:
            # 移除最久未使用（tail前面）
            lru = self.tail.prev
            self._remove(lru)
            del self.cache[lru.key]
```

**评估维度**：
- 代码正确性（通过测试用例）
- 算法效率（时间/空间复杂度）
- 代码可读性和最佳实践
- 错误处理和边界情况

### 8. 常规NLP任务（NLP）

**场景描述**：Agent完成文本分类、情感分析、命名实体识别等经典NLP任务。

**评估维度**：
- 与标准NLP模型的结果对比
- 多任务泛化能力
- 少样本学习能力
- 解释和推理能力

**Image-Prompt(Eight-Evaluation-Environments-Grid-Dashboard):** A flat-design 2x4 grid layout of eight rounded rectangular cards, each representing one AgentBench evaluation environment. Each card features a thin-line minimal icon (terminal for OS, database cylinder for DB, network nodes for KG, browser window for Web, playing cards for DCG, lightbulb puzzle for LTP, code brackets for Code, document text for NLP). Primary blue #409EFF accents on card headers, white card backgrounds, deep blue #1a1a2e icon strokes. Clean white overall background, centered symmetrical grid composition. Academic educational software dashboard style.

---

## 评估指标体系

### 核心指标

```python
class AgentBenchMetrics:
    """AgentBench核心评估指标"""

    @staticmethod
    def task_success_rate(completed: int,
                          total: int) -> float:
        """
        任务成功率 (Task Success Rate, TSR)

        定义：成功完成的任务数 / 总任务数

        这是最核心的指标。任务"成功"的定义因环境而异。
        """
        return completed / total if total > 0 else 0.0

    @staticmethod
    def step_efficiency(min_steps: int,
                        actual_steps: int) -> float:
        """
        步骤效率 (Step Efficiency)

        定义：最少所需步骤 / 实际使用步骤数

        值为1.0表示最优效率，值越低表示冗余操作越多。
        """
        return min_steps / actual_steps if actual_steps > 0 else 0.0

    @staticmethod
    def action_accuracy(correct_actions: int,
                        total_actions: int) -> float:
        """
        动作准确率 (Action Accuracy)

        定义：正确动作数 / 总动作数

        衡量Agent执行的具体操作（命令、SQL、点击等）的正确率。
        """
        return correct_actions / total_actions if total_actions > 0 else 0.0

    @staticmethod
    def tool_selection_accuracy(
            correct_tool_selections: int,
            total_tool_invocations: int) -> float:
        """
        工具选择准确率

        定义：正确选择和使用的工具 / 总工具调用次数

        衡量Agent是否在正确的时机选择了正确的工具。
        """
        return (correct_tool_selections / total_tool_invocations
                if total_tool_invocations > 0 else 0.0)

    @staticmethod
    def cost_efficiency(task_success_rate: float,
                        total_api_calls: int,
                        total_tokens: int) -> float:
        """
        成本效率

        定义：成功率 / (API调用成本 + Token消耗成本)

        在性能相近的情况下，成本更低的Agent更优。
        """
        normalized_cost = (total_api_calls * 0.01 +
                          total_tokens * 0.000001)
        return task_success_rate / (normalized_cost + 1e-6)

    @staticmethod
    def overall_score(metrics: dict) -> float:
        """
        综合评分

        加权平均各维度得分。
        权重可根据应用场景调整。
        """
        weights = {
            "task_success_rate": 0.50,
            "step_efficiency": 0.15,
            "action_accuracy": 0.15,
            "tool_selection_accuracy": 0.10,
            "cost_efficiency": 0.10
        }
        return sum(metrics.get(k, 0) * w
                  for k, w in weights.items())
```

**Image-Prompt(Agent-Evaluation-Metrics-Dashboard):** A flat-design dashboard panel showing five circular gauge meters arranged in a row. Each gauge represents a core metric: Task Success Rate (50% weight), Step Efficiency (15%), Action Accuracy (15%), Tool Selection Accuracy (10%), Cost Efficiency (10%). Primary blue #409EFF fill arcs indicating performance levels, deep blue #1a1a2e labels and tick marks, white gauge backgrounds. Clean white overall canvas, centered horizontal layout, rounded rectangular dashboard frame with subtle shadow. Academic assessment tool interface style.

---

## 评测结果解读

### 主流模型在AgentBench上的表现

| 模型 | OS | DB | KG | Web | DCG | LTP | Code | 综合 |
|------|----|----|----|-----|-----|-----|------|------|
| GPT-4 | 68.3 | 72.1 | 54.2 | 45.8 | 81.5 | 38.2 | 74.6 | 62.1 |
| GPT-3.5 | 42.7 | 55.3 | 32.1 | 28.5 | 55.2 | 22.5 | 52.3 | 41.2 |
| Claude-2 | 55.2 | 61.0 | 48.3 | 35.2 | 70.1 | 30.5 | 65.8 | 52.3 |
| Llama-2-70B | 25.3 | 35.8 | 22.5 | 15.6 | 35.2 | 18.0 | 32.5 | 26.4 |
| ChatGLM3-6B | 18.5 | 28.2 | 15.8 | 10.2 | 25.3 | 12.0 | 22.0 | 18.9 |

### 关键发现

**1. Agent能力与模型规模强相关**

```
Agent能力 ≈ 基础语言能力 × 推理能力 × 工具使用能力 × 规划能力

其中，基础语言能力（由模型规模决定）是所有能力的基础。
小模型(<10B)在Agent任务上的表现普遍较差。
```

**2. 不同场景的能力分布不均**

同一模型在不同场景的表现差异巨大：
- GPT-4在DCG（游戏策略）上表现最好（81.5），说明其策略规划能力强
- 在LTP（横向思维）上表现最差（38.2），说明创造性推理仍是大模型的薄弱环节
- Web任务普遍偏低，因为需要处理复杂的HTML结构和动态交互

**3. 代码环境表现出特殊性**

代码任务中，模型的代差特别明显：
- GPT-4（74.6）远超GPT-3.5（52.3），差距达22.3分
- 说明代码能力是新模型优于旧模型最显著的维度之一

**4. 工具使用是Agent的核心瓶颈**

即使是最强的GPT-4，在多工具协同使用的场景中也经常出现问题：
- 选择了错误的工具
- 工具调用参数格式错误
- 不会根据工具输出调整后续策略

**Image-Prompt(Model-Performance-Comparison-Bar-Chart):** A flat-design horizontal bar chart comparing five AI models (GPT-4, GPT-3.5, Claude-2, Llama-2-70B, ChatGLM3-6B) across eight evaluation environments. Bars colored in gradient from primary blue #409EFF (high score) to light gray (low score). Each model on the Y-axis, scores on X-axis. Clean white background, thin-line grid, deep blue #1a1a2e axis labels. Rounded bar caps for a soft academic look. Centered layout with legend at bottom. Suitable for educational software dashboards.

---

## AgentBench的使用

### 评估流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  1. 部署  │ -> │ 2. 运行  │ -> │ 3. 收集  │ -> │ 4. 分析  │
│  环境     │    │  任务    │    │  数据    │    │  结果    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Python SDK接入示例

```python
from agentbench import AgentBench, Task, Environment

# 1. 配置评估环境
bench = AgentBench(
    environments=[
        Environment.OS,      # 操作系统交互
        Environment.DB,      # 数据库操作
        Environment.Code,    # 代码编程
    ],
    difficulty="mixed",      # easy / medium / hard / mixed
    num_tasks_per_env=50,    # 每个环境的任务数
    max_steps_per_task=30,   # 每个任务最大步数
    timeout_per_task=300,    # 每个任务超时（秒）
)

# 2. 定义被评估的Agent
class MyAgent:
    def __init__(self, model_name: str):
        self.model = load_model(model_name)

    def act(self, observation: str,
            available_actions: list[str]) -> str:
        """
        Agent在一个回合中的决策函数。

        observation: 环境返回的当前观察（文本描述）
        available_actions: 当前可用的动作列表

        返回：Agent选择执行的动作
        """
        prompt = self._build_prompt(observation,
                                     available_actions)
        response = self.model.generate(prompt)
        return self._parse_action(response)

    def _build_prompt(self, observation, actions):
        """构建发送给LLM的提示"""
        return f"""
你是一个AI Agent，当前在{observation['environment']}环境中。

当前状态：
{observation['state']}

历史操作：
{observation['history']}

可用操作：
{chr(10).join(f'- {a}' for a in actions)}

请选择下一步操作（直接输出操作内容）：
"""

# 3. 运行评估
results = bench.evaluate(
    agent=MyAgent("claude-sonnet-4-20250514"),
    verbose=True
)

# 4. 查看结果
print(f"综合得分: {results.overall_score:.2f}")
print(f"任务成功率: {results.task_success_rate:.2%}")
print(f"各环境得分:")
for env, score in results.per_environment.items():
    print(f"  {env}: {score:.2f}")
```

**Image-Prompt(AgentBench-Evaluation-Pipeline-Flow):** A flat-design four-step horizontal pipeline diagram. Four rounded rectangular nodes connected by thin-line arrows: "1. Deploy Environment" (gear icon) -> "2. Run Tasks" (play icon) -> "3. Collect Data" (document icon) -> "4. Analyze Results" (chart icon). Each node in primary blue #409EFF with white icon, deep blue #1a1a2e step numbers and labels. Clean white background, centered symmetrical flow, subtle drop shadows on nodes. Academic evaluation workflow style for educational software.

---

## AgentBench的局限与未来

### 当前局限

1. **环境简化**：真实生产环境比模拟环境复杂得多，模拟评估可能高估Agent能力
2. **任务覆盖面**：8个场景虽然多样，但远未覆盖Agent的所有应用场景（如医疗、法律、金融等垂直领域）
3. **评估自动化**：某些任务的"成功"判断仍然需要人工标注
4. **缺乏长期任务**：目前主要是短期任务（<30步），不评估长期自主运行能力
5. **成本未充分考量**：不同Agent的API成本差异巨大，但在评分中权重较小

### 发展方向

```
AgentBench v1 (当前) → AgentBench v2 (规划中)
  ├── 更多垂直领域场景（医疗、法律、教育）
  ├── 长期自主任务（数小时到数天）
  ├── 多Agent协作评估
  ├── 安全性评估维度
  ├── 真实环境集成（非模拟）
  └── 动态任务生成（避免数据污染）
```

**Image-Prompt(AgentBench-Future-Roadmap-Evolution):** A flat-design horizontal timeline evolution diagram. Starting from "AgentBench v1" as a rounded rectangle in primary blue #409EFF, arrow pointing to "AgentBench v2" with six branching feature cards below: Medical/Legal, Long-term Autonomy, Multi-Agent Collaboration, Safety Evaluation, Real Environment, Dynamic Task Generation. Each feature card as a small rounded rectangle with thin-line icons and deep blue #1a1a2e text. Clean white background, centered layout, subtle light blue connecting lines. Academic technology roadmap style.

---

## 小结

AgentBench为Agent评估提供了一个标准化、多维度的框架。它的核心价值在于：**让Agent的能力在真实、交互式的环境中接受检验，而非仅仅在纸面上答题**。

**使用AgentBench的最佳实践**：
1. **选择相关场景**：不是所有Agent都需要在所有场景中评估。选择与你应用相关的2-3个场景即可
2. **多次运行取平均**：Agent行为有一定随机性，建议每个任务运行3-5次
3. **关注细节指标**：单纯的综合得分可能掩盖重要问题，关注步骤效率和工具使用准确率
4. **与竞品对比**：在相同条件下对比不同模型/Agent框架的表现
5. **持续跟踪**：模型和框架在快速迭代，定期重新评估以了解最新能力边界

记住：**评测只是手段，理解Agent的真实能力边界才是目的**。AgentBench提供的是一个"体检报告"，真正的健康需要在生产环境中验证。

**Image-Prompt(AgentBench-Summary-Key-Takeaways):** A flat-design summary infographic with four rounded rectangular cards arranged in a 2x2 grid. Cards labeled: "Multi-Dimensional Evaluation", "Interactive Environment", "Standardized Metrics", "Continuous Assessment". Each card features a minimal thin-line icon in primary blue #409EFF, with deep blue #1a1a2e title text and light gray description. White background, centered symmetrical layout, soft rounded corners. Academic educational summary slide style, suitable for teaching software interfaces.
