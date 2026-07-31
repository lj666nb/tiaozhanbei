# 思维树ToT

## 引言

请思考以下问题：

> "用数字1、2、3、4和基本运算符号（+、-、×、÷），能否得到24？每个数字恰好用一次。"

大多数人解决这道"24点"游戏的策略是进行**试探性搜索**：尝试"(1+2+3)×4=24"——不对，1+2+3=6，6×4=24！找到了一个解。但如果不是刚好试探到这条路径呢？可能试了"(1×2)×(3×4)"、"4×3×2×1"……这种沿着多条路径探索、遇到死胡同就回溯的思维方式，正是**思维树（Tree of Thoughts, ToT）**的核心。

传统的思维链（Chain of Thought, CoT）像是沿着一条路一直走——先想A，再想B，再想C，最终到达答案。但很多复杂问题的一条路可能根本走不通。ToT则允许模型在推理过程中**分叉、比较、回溯**——这正是人类解决真正难题时的思维方式。

**Image-Prompt(Tree of Thoughts Concept Introduction):**
```
A flat-design minimalist 2D vector illustration contrasting two thinking approaches. Left side: a single straight path with arrows labeled "CoT" showing a linear chain (A→B→C→Answer) in gray. Right side: a branching tree structure with multiple paths diverging from a root node, some branches ending with X marks (dead ends) and one leading to a highlighted star (solution), labeled "ToT" in #409EFF. A small 24-point game card (showing numbers 1,2,3,4) at the top as the problem example. White background, deep blue #1a1a2e text.
```

## 从CoT到ToT：单链推理的局限性

### CoT的单链困境

CoT的核心假设是：**存在一条从问题到答案的连续推理链**。这在数学文字题等结构化问题中通常成立，但在开放式复杂问题上会暴露根本局限。

考虑这个问题：

> "设计一个为期3天的巴黎旅行计划，预算500欧元，必须包括卢浮宫、埃菲尔铁塔和至少一家米其林推荐餐厅。"

CoT的处理方式：

```
思考：第一天去埃菲尔铁塔（门票20欧）→ 第二天去卢浮宫（门票17欧）
→ 嗯，那餐厅应该安排在...等等，预算不够了？
→ 也许应该重新安排，但已经生成的内容无法"撤销"。
```

CoT的三个致命局限在此暴露：
1. **无回溯能力**：生成的错误步骤无法撤销
2. **无全局搜索**：无法比较方案A和方案B哪个更好
3. **无探索广度**：被困在一条路径上，即使这条路越来越糟

### ToT的应对思路

ToT将推理过程建模为**在思维空间中的搜索**。每一步生成多个"思维候选"（多个可能的推理分支），评估它们的质量，决定深入探索还是回溯。

```
问题："设计巴黎3日游，500欧预算"

第1步：生成多种思路
  思路A: "按地理区域安排行程"  (评分: 8/10)
  思路B: "按时间顺序安排行程"  (评分: 7/10)
  思路C: "先确定大支出再填空"  (评分: 9/10) ← 最优
  
第2步：基于思路C展开
  子思路C1: "住宿预定青旅30欧/晚"    (评分: 8/10)
  子思路C2: "住宿选择airbnb 50欧/晚"  (评分: 6/10)
  
第3步：进一步探索C1...
  C1→门票→交通→餐饮→ 预算剩余检查
  发现超支 → 回溯到第2步，尝试不同的住宿策略
```

**Image-Prompt(CoT Linear Chain Limitations):**
```
A flat-design minimalist 2D vector illustration showing the three fatal limitations of linear Chain-of-Thought reasoning. Three horizontally arranged cards, each with a red X icon and a conceptual graphic: Card 1 shows a one-way arrow hitting a wall (no backtracking), Card 2 shows a single path vs multiple question marks (no global search), Card 3 shows a narrowing path getting dimmer (no exploration breadth). Each card has a brief label in deep blue #1a1a2e. White background, clean rounded card design.
```

## ToT的核心架构

### 四大组件

ToT框架由四个核心组件构成：

```
┌─────────────────────────────────────────────┐
│              Tree of Thoughts                │
│                                              │
│  ┌──────────┐    ┌──────────┐               │
│  │ 思维生成器 │───→│ 思维评估器 │               │
│  │ Generator │    │ Evaluator │              │
│  └──────────┘    └──────────┘               │
│       ↑               │                      │
│       │               ↓                      │
│  ┌──────────┐    ┌──────────┐               │
│  │ 搜索策略   │←───│ 状态管理  │               │
│  │ Strategy  │    │  State   │               │
│  └──────────┘    └──────────┘               │
└─────────────────────────────────────────────┘
```

**1. 思维生成器（Thought Generator）**

给定当前状态（已推理到哪一步），生成k个可能的下一步思维。实现方式有两种：

- **独立采样（Independent Sampling）**：用较高的温度，让LLM对同一个Prompt多次生成，获得不同的思维分支。适用于思维空间广阔的问题。
- **顺序提议（Sequential Proposal）**：在Prompt中要求LLM生成多个不同的下一步选项。适用于思维空间有明确结构的问题。

```
独立采样Prompt示例：
"当前状态：我们已知A和B。请提出下一步推理。"
→ 运行3次（temperature=0.7），得到3个不同的思维分支

顺序提议Prompt示例：
"当前状态：我们已知A和B。请提出3种不同的下一步推理方案：
方案1:
方案2:
方案3:"
→ 运行1次，LLM一次性给出3个选项
```

**2. 思维评估器（Thought Evaluator）**

评估每个思维分支的质量，给出分数或分类（好/中/差）。这是ToT最关键也最难设计的组件。

评估方式有两种：

- **值评估（Value）**：给每个思维一个标量分数，如0-10。适合需要精确定量比较的场景。
- **投票评估（Vote）**：在多个思维中投票选出最好的。适合难以量化评估的场景。

```
值评估Prompt示例：
"请评估以下推理步骤的质量（1-10分），考虑其逻辑严谨性、
与前文的一致性和对解决问题的贡献：
推理步骤：{thought}
评分："

投票评估Prompt示例：
"以下是5个可能的下一步推理。请选出最好的1个，并说明理由：
选项1: {thought_1}
选项2: {thought_2}
...
最佳选项：[编号]，理由："
```

**3. 搜索策略（Search Strategy）**

决定探索和回溯的规则。两种主要策略：

**BFS（广度优先搜索）**：

```
BFS伪代码：
1. 从根节点开始
2. 对于当前层的每个节点，生成k个子思维
3. 评估所有子思维，保留最好的b个（beam width = b）
4. 对于保留的b个节点，重复步骤2-3
5. 到达终止条件时，选择评分最高的完整路径

可视化（k=3, b=2）：
         ┌─A1─ ... 
     ┌─A─├─A2─ ...
     │   └─A3  (被剪枝)
Root─┤   ┌─B1─ ...
     └─B─├─B2─ ...
         └─B3  (被剪枝)
```

**DFS（深度优先搜索）**：

```
DFS伪代码：
1. 从根节点开始
2. 选择一个最有希望的分支深入探索
3. 到达叶节点（最终状态）后，评估完整方案
4. 如果评分低于阈值，回溯到最近的未探索分支
5. 重复直到找到足够好的方案或用尽搜索预算

可视化：
Root → A → A1 → A1.1 → [回溯] → A1.2 → [回溯] → A2 → ...
```

**4. 状态管理（State Manager）**

维护当前搜索树的状态，包括已探索的节点、各节点的评分、可用搜索预算等。

### 如何选择BFS还是DFS

| 特性 | BFS | DFS |
|------|-----|-----|
| 适用于 | 思维分枝有限、深度较浅 | 思维深度大、需要深入探索 |
| 优势 | 不会错过浅层的优质方案 | 能在搜索预算内深入到底 |
| 劣势 | 宽度×深度组合爆炸 | 可能困在不好的分支浪费预算 |
| 典型场景 | 创意写作、方案比选 | 数学证明、代码调试 |
| 类比 | 广撒网，同步推进多种可能 | 一条路走到黑，不行再换 |

实际应用中，经常使用两者的混合策略——先用BFS生成几个有潜力的方向，再对每个方向用DFS深入探索。

**Image-Prompt(ToT Four Core Components Architecture):**
```
A flat-design minimalist 2D vector illustration of the Tree of Thoughts four-component architecture. A central rounded rectangular hub labeled "Tree of Thoughts" in #409EFF, with four satellite nodes connected by thin lines: top-left "Thought Generator" with a branching tree icon, top-right "Thought Evaluator" with a star rating icon, bottom-left "Search Strategy" with BFS/DFS path icons, bottom-right "State Manager" with a data tree icon. Each node is a rounded square in light blue. White background, deep blue #1a1a2e labels, symmetrical centered layout.
```

## 完整代码实现

### ToT核心框架

```python
import re
import itertools
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
import openai

@dataclass
class ThoughtNode:
    """思维树的一个节点"""
    content: str                          # 思维内容
    parent: Optional["ThoughtNode"] = None # 父节点
    children: List["ThoughtNode"] = field(default_factory=list)
    score: float = 0.0                    # 评估分数
    depth: int = 0                        # 深度
    visits: int = 0                       # 被访问次数

    def get_path(self) -> List[str]:
        """获取从根节点到当前节点的完整思维路径"""
        path = []
        node = self
        while node is not None:
            path.append(node.content)
            node = node.parent
        return list(reversed(path))

class TreeOfThoughts:
    """ToT核心引擎"""

    def __init__(
        self,
        model: str = "gpt-4",
        max_depth: int = 5,
        num_thoughts_per_step: int = 3,   # k值
        beam_width: int = 2,              # b值（BFS保留数）
        temperature: float = 0.7,
    ):
        self.model = model
        self.max_depth = max_depth
        self.k = num_thoughts_per_step
        self.beam_width = beam_width
        self.temperature = temperature
        self.root = None

    def call_llm(self, prompt: str, n: int = 1) -> List[str]:
        """调用LLM API"""
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            n=n,
        )
        return [choice.message.content for choice in response.choices]

    def generate_thoughts(
        self, current_state: str, problem: str, n: int
    ) -> List[str]:
        """生成n个可能的下一步思维"""
        prompt = f"""你正在解决以下问题：
{problem}

当前的推理状态：
{current_state}

请提出{n}种不同的下一步推理。每一种应该从不同的角度切入，
探索不同的可能性。用数字1-{n}标记每个方案。

方案："""
        response = self.call_llm(prompt, n=1)[0]

        # 解析LLM返回的多个方案
        thoughts = []
        for i in range(1, n + 1):
            pattern = rf"{i}[\.\)]\s*(.+?)(?=\n?\d+[\.\)]|\Z)"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                thoughts.append(match.group(1).strip())

        # 如果解析失败，使用独立采样
        if len(thoughts) < n:
            individual_responses = self.call_llm(
                f"问题：{problem}\n当前状态：{current_state}\n请提出下一步推理：",
                n=n
            )
            thoughts = individual_responses

        return thoughts[:n]

    def evaluate_thought(
        self, thought_path: List[str], problem: str
    ) -> float:
        """评估一个思维分支的质量，返回0-10的分数"""
        path_text = "\n→ ".join(thought_path)

        prompt = f"""你是一位严格的评估专家。请评估以下推理路径在解决给定问题时的质量。

问题：{problem}

推理路径：
→ {path_text}

请从以下维度评估（每项0-10分）：
1. 逻辑严密性：推理步骤之间是否有清晰的逻辑联系
2. 对目标的贡献：这一步是否有效地向最终答案推进
3. 独创性：是否有新颖的视角或解决方案
4. 可行性：提出的方案是否实际可行

最后给出一个综合分数（0-10分）。

综合评分："""
        response = self.call_llm(prompt, n=1)[0]

        # 提取综合评分
        match = re.search(r"(\d+(?:\.\d+)?)", response)
        if match:
            return min(10.0, max(0.0, float(match.group(1))))
        return 5.0  # 默认中等分数

    def is_terminal(self, thought_path: List[str]) -> bool:
        """判断是否已达到终止状态（得出了最终答案）"""
        if len(thought_path) >= self.max_depth:
            return True

        # 用LLM判断是否已解决问题
        path_text = "\n→ ".join(thought_path)
        prompt = f"""推理路径：
→ {path_text}

请判断：以上推理是否已经得出了问题的最终答案？
仅回答"是"或"否"。"""
        response = self.call_llm(prompt, n=1)[0]
        return "是" in response

    def search_bfs(self, problem: str) -> str:
        """BFS策略搜索"""
        # 初始化根节点（包含问题本身）
        root_prompt = f"你正在解决一个问题：{problem}\n让我们开始分析。"
        initial_thoughts = self.call_llm(root_prompt, n=1)
        self.root = ThoughtNode(
            content=f"问题：{problem}",
            depth=0,
            score=10.0,
        )

        current_layer = [self.root]

        for depth in range(1, self.max_depth + 1):
            next_layer_candidates = []

            for node in current_layer:
                # 为当前节点生成k个子思维
                child_thoughts = self.generate_thoughts(
                    current_state="\n→ ".join(node.get_path()),
                    problem=problem,
                    n=self.k,
                )

                for thought_text in child_thoughts:
                    child = ThoughtNode(
                        content=thought_text,
                        parent=node,
                        depth=depth,
                    )
                    # 评估子思维
                    child.score = self.evaluate_thought(
                        child.get_path(), problem
                    )
                    node.children.append(child)
                    next_layer_candidates.append(child)

            # 检查是否有终止节点
            for candidate in next_layer_candidates:
                if self.is_terminal(candidate.get_path()):
                    return "\n→ ".join(candidate.get_path())

            # 保留评分最高的b个节点
            next_layer_candidates.sort(key=lambda n: n.score, reverse=True)
            current_layer = next_layer_candidates[:self.beam_width]

            if not current_layer:
                break

        # 返回评分最高的完整路径
        if current_layer:
            best = max(current_layer, key=lambda n: n.score)
            return "\n→ ".join(best.get_path())
        return "搜索未能找到有效方案"

    def search_dfs(self, problem: str, threshold: float = 6.0) -> str:
        """DFS策略搜索（带剪枝）"""
        self.root = ThoughtNode(
            content=f"问题：{problem}",
            depth=0,
            score=10.0,
        )

        def dfs_recursive(node: ThoughtNode) -> Optional[str]:
            current_path = node.get_path()

            # 终止条件
            if self.is_terminal(current_path):
                return "\n→ ".join(current_path)

            # 达到最大深度
            if node.depth >= self.max_depth:
                return None

            # 生成子节点
            child_thoughts = self.generate_thoughts(
                current_state="\n→ ".join(current_path),
                problem=problem,
                n=self.k,
            )

            # 评估并排序
            scored_children = []
            for thought_text in child_thoughts:
                child = ThoughtNode(
                    content=thought_text,
                    parent=node,
                    depth=node.depth + 1,
                )
                child.score = self.evaluate_thought(
                    child.get_path(), problem
                )
                node.children.append(child)
                scored_children.append((child.score, child))

            # 按评分降序排列，优先探索高分分支
            scored_children.sort(key=lambda x: x[0], reverse=True)

            for _, child in scored_children:
                # 剪枝：评分太低则跳过
                if child.score < threshold:
                    continue

                result = dfs_recursive(child)
                if result is not None:
                    return result

            return None  # 所有分支都走不通，回溯

        result = dfs_recursive(self.root)
        if result:
            return result
        return "DFS搜索未能找到有效方案（所有分支被剪枝或已探索完毕）"

    def solve(self, problem: str, strategy: str = "bfs") -> str:
        """主入口"""
        if strategy == "bfs":
            return self.search_bfs(problem)
        elif strategy == "dfs":
            return self.search_dfs(problem)
        else:
            raise ValueError(f"未知搜索策略: {strategy}")
```

### 使用示例：24点游戏

```python
# 初始化ToT引擎
tot = TreeOfThoughts(
    model="gpt-4",
    max_depth=5,
    num_thoughts_per_step=4,   # 每步生成4个候选
    beam_width=2,              # BFS保留2个最优
    temperature=0.8,
)

# 解决24点问题
problem = "用数字 4, 5, 6, 7 和基本运算（+、-、×、÷），得到24。每个数字只能用一次。"

solution = tot.solve(problem, strategy="bfs")
print(solution)
```

这个例子中，ToT会生成多条推理路径。例如：

```
路径A: 4×6=24, 但剩下5和7无法处理 → 回溯
路径B: 7-5=2, 6×4=24, 24×2?...每个数字只用一次 → 回溯
路径C: 7-6=1, 5-1=4, 4×6=24...等等6已经用过 → 回溯  
路径D: (7-5)×(6+4)...不对
路径E: 4×6=24, 7-5=2, 但还需要组合 → 各种尝试
...
最终: 4 × (7 + 5 - 6) = 4 × 6 = 24 ✓
```

**Image-Prompt(ToT 24-Game Search Tree Visualization):**
```
A flat-design minimalist 2D vector illustration of the Tree of Thoughts solving the 24-point game with numbers 4,5,6,7. A tree diagram with a root node at the top showing "4,5,6,7→24". Below, four branching paths (A, B, C, D) with calculation attempts in rounded nodes. Paths A, B, C end with red X marks (dead ends), while Path D descends through sub-nodes and ends with a green checkmark and "4×(7+5-6)=24" highlighted in #409EFF. White background, deep blue #1a1a2e labels, thin connecting lines.
```

## ToT的适用场景

### 场景1：数学证明与逻辑推理

```
问题："证明√2是无理数"

ToT搜索过程：
  思路A: 反证法 → 假设√2=p/q → 推导... → 得出矛盾 ✓
  思路B: 直接构造法 → 尝试构造有理数近似 → 无法证明 ✗
  思路C: 数论方法 → 使用唯一分解定理 → 可行但复杂

ToT会同时探索A、B、C，快速识别B是死胡同，在A和C之间选择更优雅的A。
```

### 场景2：创意写作

```
问题："写一个关于AI觉醒的短篇科幻故事"

ToT搜索过程：
  第1步：故事背景设定
    分支A: 近未来（2040年），医疗AI觉醒
    分支B: 远未来（2200年），星际飞船AI觉醒
    分支C: 当代，智能手机助手AI觉醒
  
  第2步：评估并选择最优设定 → B
    分支B1: AI从飞船日志中学习人类情感
    分支B2: AI在面对陨石危机时的道德抉择
  
  第3步：继续展开选中的分支...
```

### 场景3：策略规划

```python
# 旅行规划
problem = """
从北京出发，7天内游玩大理和丽江，预算5000元。
要求：包含交通、住宿、景点和餐饮方案。
"""

tot = TreeOfThoughts(
    model="gpt-4",
    max_depth=4,
    num_thoughts_per_step=3,
    beam_width=2,
)

solution = tot.solve(problem, strategy="bfs")
```

### 场景4：代码调试

```
问题："这段Python代码在处理大文件时内存溢出，请找出问题并修复"

ToT搜索过程：
  分支A: 检查是否一次性读取了整个文件
    → A1: 改为逐行读取 → 测试 → 部分解决，但仍慢
    → A2: 改为chunk读取 → 测试 → 解决内存问题
  分支B: 检查是否存在循环引用
    → B1: 使用gc模块检查 → 未发现
  分支C: 检查数据库连接是否关闭
    → 无需继续
```

**Image-Prompt(ToT Application Scenarios Quadrant):**
```
A flat-design minimalist 2D vector illustration showing four application scenarios of Tree of Thoughts as a 2x2 grid of rounded cards. Top-left: a math proof icon (square root symbol with checkmark) for "Math & Logic". Top-right: a lightbulb with a storybook for "Creative Writing". Bottom-left: a map pin with a calendar for "Strategic Planning". Bottom-right: a bug icon with a magnifying glass for "Code Debugging". Each card has a mini tree diagram inside. The grid uses #409EFF borders, white background, deep blue #1a1a2e labels.
```

## ToT vs CoT vs ReAct：三方对比

### 核心差异一览

```
CoT（思维链）:
  [思考1] → [思考2] → [思考3] → [答案]
  单链，不分支，不回溯

ReAct（推理+行动）:
  [思考] → [行动] → [观察] → [思考] → [行动] → [观察] → [答案]
  与外部环境交互，但思维仍是单链

ToT（思维树）:
        ┌→ [思考2a] ─→ [思考3a] → [答案A]
  [思考1]→ [思考2b] ─→ [思考3b] → [答案B]
        └→ [思考2c] ─→ [回溯]
  多分支并行探索，评估后选择或回溯
```

### 详细对比表

| 维度 | CoT | ToT | ReAct |
|------|-----|-----|-------|
| 推理结构 | 线性链 | 树状 | 链 + 外部调用 |
| 搜索能力 | 无 | BFS/DFS/束搜索 | 无（但可通过工具辅助） |
| 外部交互 | 无 | 无 | 有（工具、API、数据库） |
| 回溯能力 | 无 | 有 | 有限（通过重新行动） |
| 计算成本 | 低（1次生成） | 高（k×b×深度次生成） | 中（取决于行动次数） |
| 适用问题 | 有明确推理链的结构化问题 | 需要探索多方案的开放式问题 | 需要外部知识或行动的问题 |
| 代表应用 | 数学题、逻辑推理 | 24点、创意写作、规划 | 知识问答、Agent任务 |

### 三种方法的互补关系

在实际系统中，这三种方法并非互斥，而是可以组合使用：

```
ReAct + ToT:
  在ReAct的"思考"阶段使用ToT进行更深入的推理
  例如：Agent接到复杂任务 → ToT生成多种行动计划 → 选择最优 → ReAct执行

CoT + ToT:
  在ToT的每个思维节点内部使用CoT进行详细推理
  例如：评估分支时用CoT仔细分析

最佳实践：
  1. 简单问题（已知答案路径）→ CoT
  2. 需要探索的问题（方案不确定）→ ToT
  3. 需要操作外部世界 → ReAct
  4. 复杂Agent → ReAct（外层） + ToT（规划层） + CoT（推理层）
```

**Image-Prompt(ToT vs CoT vs ReAct Three-Mode Comparison):**
```
A flat-design minimalist 2D vector illustration comparing three reasoning modes. Three vertical columns with distinct visual patterns: Left "CoT" shows a straight horizontal arrow chain of circles. Center "ToT" (highlighted with #409EFF glow) shows a branching tree with multiple paths and a highlighted solution path. Right "ReAct" shows alternating brain and gear icons with feedback arrows. Below, a Venn diagram overlay shows the complementary relationship. White background, deep blue #1a1a2e labels, symmetrical three-column layout.
```

## ToT的局限性与挑战

### 1. 计算成本

ToT最大的实际挑战在于成本。对于每个问题：

```
API调用次数 ≈ 深度 × 保留宽度 × 每步生成数 × 2（生成+评估）

以k=3, b=2, depth=5为例：
  约 5 × 2 × 3 × 2 = 60 次API调用
  每次调用约几千Token，总成本可能是单次CoT的50-100倍
```

### 2. 评估器的可靠性

思维评估器本身是一个LLM，它可能给出不准确的评分。一个本应通向正确答案的思维分支可能被评估器错误地打了低分而被剪枝。这是ToT最脆弱的环节。

缓解策略：
- 多次评估取平均
- 结合规则评估（如代码是否可以运行）
- 在关键节点使用更强大的模型进行评估

### 3. 思维空间的指数爆炸

即使有剪枝，搜索空间仍然随深度指数增长。对于非常开放的问题（如"如何实现世界和平"），思维空间几乎是无限的，ToT无法有效搜索。

### 4. 缺乏外部信息

ToT的"思维"完全基于模型内部知识。如果模型对某个事实不确定，生成的所有分支都可能是基于错误前提的。这是ToT相对于ReAct的根本劣势——ReAct可以通过工具调用获取外部信息来纠正错误。

**Image-Prompt(ToT Limitations Four Challenges):**
```
A flat-design minimalist 2D vector illustration showing four key limitations of Tree of Thoughts. Four rounded cards in a 2x2 grid: top-left "Compute Cost" with a dollar sign and multiple API call icons, top-right "Evaluator Reliability" with a shaking balance scale, bottom-left "Exponential Explosion" with a rapidly branching tree hitting a boundary, bottom-right "No External Info" with a locked book icon. Each card uses a caution orange accent alongside #409EFF. White background, deep blue #1a1a2e labels.
```

## 实践建议

1. **从CoT开始，只在必要时使用ToT**：大部分问题用CoT就够了。只有当CoT反复给出错误答案或推理过程明显单薄时，才考虑升级到ToT。

2. **控制搜索预算**：设置最大API调用次数、最大推理时间等硬性限制，防止搜索失控。

3. **结合领域知识优化评估器**：在特定领域（如数学），可以加入领域特定的评估规则（如代入验证），大幅提升评估准确性。

4. **渐进式加深**：对于非关键应用，可以使用"1层BFS + 其余DFS"的混合策略——第一步广泛探索，后续快速深入。

5. **缓存思维节点**：如果同一个思维状态被多次访问（在搜索中很常见），不必重复调用LLM生成和评估。

**Image-Prompt(ToT Best Practices Guide):**
```
A flat-design minimalist 2D vector illustration of five best practices for Tree of Thoughts. Five numbered items arranged vertically, each with a simple icon: (1) "Start with CoT" shown as a stepping stone, (2) "Control Search Budget" as a timer icon, (3) "Domain-Specific Evaluator" as a target with checkmark, (4) "Progressive Deepening" as layers building up, (5) "Cache Thought Nodes" as a recycle/cache icon. Each number is in a #409EFF circle. White background, deep blue #1a1a2e labels.
```

## 总结

思维树（ToT）将LLM的推理能力从"单链思维"提升到了"树状搜索"的新高度。它模仿了人类解决复杂问题时的核心策略——生成多种可能、评估优劣、深入探索或果断回溯。

ToT的三大支柱是：
- **多分支生成**：不只走一条路，而是同时探索多个方向
- **智能评估**：用LLM自身评判每个方向的质量，筛选最有希望的路径
- **策略性搜索**：BFS保证广度，DFS保证深度，束搜索取得平衡

ToT的最佳应用场景是那些"不能靠一条推理链直达答案"的问题——数学搜索题、复杂规划、创意方案设计。对于这些场景，ToT相比CoT的准确率提升可能是质的飞跃（在24点游戏上从4%提升到74%）。

但ToT的代价同样显著——API调用量是CoT的数十倍乃至上百倍。在实践中，关键是权衡"额外成本"和"准确率提升"的价值。对于关键决策、高价值内容创作等场景，ToT的投入是完全值得的。把ToT理解为AI推理的"深思熟虑模式"——慢，但更可靠。

**Image-Prompt(ToT Summary Three Pillars):**
```
A flat-design minimalist 2D vector illustration of the three pillars of Tree of Thoughts. A central triangular composition with three cornerstone icons: bottom-left "Multi-Branch Generation" with a branching tree icon, bottom-right "Intelligent Evaluation" with a star-rating scale icon, top "Strategic Search" with BFS/DFS path icons. The three elements are connected by #409EFF lines forming a triangle. At the center, a small trophy icon with "4%→74%" accuracy improvement annotation. White background, deep blue #1a1a2e labels.
```
