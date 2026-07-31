"""
编程实验室 — 6 套知识分类对应的编程任务模板
每个模板内根据具体知识点生成不同变体，确保每个学习任务的编程练习各不相同。
"""
from services.question_bank_service import _infer_knowledge_category


def _variation(knowledge: str, n: int = 3) -> int:
    """根据知识点文本生成确定性变体编号 (0 ~ n-1)"""
    return sum(ord(c) for c in knowledge) % n


def get_template(category: str, topic: str, knowledge: str, index: int = 0) -> dict:
    """根据知识分类返回对应的编程任务模板。
    每个任务根据其knowledge文本生成完全不同的练习（类名、场景、测试均不同）。"""
    v = _variation(knowledge)

    # 每个分类有3种练习结构，按 index 轮换
    types = [
        _template_ooda_agent, _template_state_agent, _template_reflex_agent,
    ]
    if category == "智能体基础概念":
        return types[index % 3](topic, knowledge, v)

    types = [
        _template_llm_request, _template_token_counter, _template_param_tuner,
    ]
    if category == "大模型基座原理":
        return types[index % 3](topic, knowledge, v)

    types = [
        _template_cot_engine, _template_prompt_scorer, _template_template_builder,
    ]
    if category == "提示词工程":
        return types[index % 3](topic, knowledge, v)

    types = [
        _template_tool_agent, _template_memory_system, _template_pipeline_builder,
    ]
    if category == "智能体框架开发":
        return types[index % 3](topic, knowledge, v)

    types = [
        _template_rag_system, _template_decision_tree, _template_similarity_calc,
    ]
    if category == "智能体算法逻辑":
        return types[index % 3](topic, knowledge, v)

    types = [
        _template_multi_agent, _template_voting_system, _template_task_delegator,
    ]
    if category == "多智能体应用":
        return types[index % 3](topic, knowledge, v)

    return _template_fallback(topic, knowledge)


def build_code_task(topic: str, knowledge: str, action: str = "", depth: str = "标准", index: int = 0) -> dict:
    """根据知识点分类匹配对应的编程任务模板（backward-compatible wrapper）"""
    category = _infer_knowledge_category(knowledge)
    return get_template(category, topic, knowledge, index)


# ================================================================
# 模板 1: OODA 循环 Agent
# ================================================================
def _template_ooda_agent(topic: str, knowledge: str, v: int = 0) -> dict:
    # 根据知识点文本动态生成唯一场景
    kw = knowledge.strip()
    bot_name = kw[:4] + "Bot" if len(kw) >= 4 else "AgentBot"
    # 从知识点中提取角色描述
    role = kw[:8] if len(kw) >= 4 else "通用场景"
    msg_ok = f"{kw[:6]}运行正常" if len(kw) >= 4 else "一切正常"
    msg_alert = f"紧急！{kw[:6]}出现异常" if len(kw) >= 4 else "警报！系统故障"
    s = {"agent_name": bot_name, "role": role, "msg_ok": msg_ok, "msg_alert": msg_alert}
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"实现一个 **{s['role']}智能体**，基于 **OODA 循环**（观察→判断→决策→行动）处理{s['role']}场景。\n\n"
            f"Agent 接收到{s['role']}相关信息后，按照 OODA 四个阶段依次处理，最终输出行动指令。\n\n"
            f"## 📖 背景知识\n"
            f"OODA 循环是智能体决策的经典模型：\n"
            f"- **Observe（观察）**：从环境收集信息\n"
            f"- **Orient（判断）**：分析信息、评估形势\n"
            f"- **Decide（决策）**：选择最优行动方案\n"
            f"- **Act（行动）**：执行决策并输出结果\n\n"
            f"## 💡 你将学到\n"
            f"- Agent 的核心闭环逻辑\n"
            f"- 状态驱动的决策机制\n"
            f"- 如何用代码建模{s['role']}智能体行为"
        ),
        "requirements": [
            "创建 OODAAgent 类，实现 observe(msg)、orient()、decide()、act() 四个方法",
            "observe：将环境消息存入 self.observations 列表，根据关键词更新 self.state",
            "orient：根据 self.state 判断当前形势（'紧急' / '正常' / '未知'）",
            "decide：根据形势返回行动方案（紧急→'立即响应'，正常→'按计划执行'，未知→'请求更多信息'）",
            "act：执行决策，打印行动日志，返回行动结果字符串",
            "run(msg)：串联 OODA 四个阶段，接收消息→返回行动结果",
        ],
        "test_cases": [
            {"name": "Agent 创建", "description": "验证 Agent 实例化正确且初始状态为'就绪'",
             "setup_code": f"agent = OODAAgent('{s['agent_name']}')\nprint(agent.state)",
             "expected_output": "就绪", "check_type": "output_contains"},
            {"name": "OODA 循环-正常", "description": "发送正常消息，验证OODA完整流程",
             "setup_code": f"agent = OODAAgent('Bot')\nresult = agent.run('{s['msg_ok']}')\nprint(result)",
             "expected_output": "按计划执行", "check_type": "output_contains"},
            {"name": "OODA 循环-紧急", "description": "发送紧急消息，验证决策切换",
             "setup_code": f"agent = OODAAgent('Bot')\nresult = agent.run('{s['msg_alert']}')\nprint(result)",
             "expected_output": "立即响应", "check_type": "output_contains"},
            {"name": "观察记录", "description": "验证 observe 正确记录输入",
             "setup_code": f"agent = OODAAgent('Bot')\nagent.run('{s['msg_ok']}')\nagent.run('{s['msg_alert']}')\nprint(len(agent.observations))",
             "expected_output": "2", "check_type": "output_contains"},
        ],
        "starter_code": _OODA_STARTER.format(topic=topic, knowledge=knowledge, agent_name=s['agent_name'], role=s['role'], msg_ok=s['msg_ok'], msg_alert=s['msg_alert']),
        "answer_code": _OODA_ANSWER,
        "hints": [
            ("💡 第1步：实现 observe()",
             "1. self.observations.append(msg)\n2. 用 any(k in msg for k in ['警报','紧急','故障']) 判断消息类型\n3. 根据判断结果设置 self.state = '紧急' / '正常' / '未知'\n4. return f'Agent {self.name} 观察到: {msg}'"),
            ("🔑 第2步：实现 decide()",
             "if self.state == '紧急': return '立即响应'\nelif self.state == '正常': return '按计划执行'\nelse: return '请求更多信息'"),
            ("📖 第3步：检查 run()",
             "run() 已串联好 observe→orient→decide→act，无需修改。act() 中需 print 日志并 return decision。"),
        ],
    }


_OODA_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现 {role}智能体 ({agent_name}) — 在 START/END 标记之间编写你的代码
"""


class OODAAgent:
    """基于 OODA 循环的智能体 — {role}场景"""

    def __init__(self, name: str):
        self.name = name
        self.observations = []
        self.state = "就绪"
        # ========== START ==========
        pass
        # ========== END ==========

    def observe(self, msg: str) -> str:
        """观察阶段：接收环境信息并更新内部状态"""
        # ========== START ==========
        # 1. 将 msg 存入 self.observations 列表
        # 2. 根据 msg 内容设置 self.state：
        #    - 包含"警报"、"紧急"、"故障" → "紧急"
        #    - 包含"正常"、"完成"、"稳定" → "正常"
        #    - 其他 → "未知"
        # 3. 返回 f"Agent {{self.name}} 观察到: {{msg}}"
        pass
        # ========== END ==========

    def orient(self) -> str:
        """判断阶段：分析当前形势"""
        # ========== START ==========
        # 返回 self.state 对应的形势描述
        pass
        # ========== END ==========

    def decide(self) -> str:
        """决策阶段：根据形势选择行动方案"""
        # ========== START ==========
        # "紧急" → "立即响应"
        # "正常" → "按计划执行"
        # 其他 → "请求更多信息"
        pass
        # ========== END ==========

    def act(self, decision: str) -> str:
        """行动阶段：执行决策并返回结果"""
        # ========== START ==========
        # 打印: f"[{{self.name}}] 执行行动: {{decision}}"
        # 返回 decision
        pass
        # ========== END ==========

    def run(self, msg: str) -> str:
        """执行完整的 OODA 循环"""
        self.observe(msg)
        self.orient()
        decision = self.decide()
        return self.act(decision)


# ===== 测试代码（不要修改）=====
if __name__ == "__main__":
    agent = OODAAgent("{agent_name}")
    print(f"Agent {agent_name} 初始化完成")
    print(agent.state)
    print("--- 测试正常消息 ---")
    r1 = agent.run("{msg_ok}")
    print(r1)
    print("--- 测试紧急消息 ---")
    r2 = agent.run("{msg_alert}")
    print(r2)
    print("--- 观察记录 ---")
    print(f"共记录 {{len(agent.observations)}} 条观察")
'''

_OODA_ANSWER = '''class OODAAgent:
    def __init__(self, name: str):
        self.name = name
        self.observations = []
        self.state = "就绪"

    def observe(self, msg: str) -> str:
        self.observations.append(msg)
        if any(k in msg for k in ["警报", "紧急", "故障"]):
            self.state = "紧急"
        elif any(k in msg for k in ["正常", "完成"]):
            self.state = "正常"
        else:
            self.state = "未知"
        return f"Agent {self.name} 观察到: {msg}"

    def orient(self) -> str:
        return f"当前形势: {self.state}"

    def decide(self) -> str:
        if self.state == "紧急":
            return "立即响应"
        elif self.state == "正常":
            return "按计划执行"
        else:
            return "请求更多信息"

    def act(self, decision: str) -> str:
        print(f"[{self.name}] 执行行动: {decision}")
        return decision

    def run(self, msg: str) -> str:
        self.observe(msg)
        self.orient()
        decision = self.decide()
        return self.act(decision)
'''


# ================================================================
# 模板 2: LLM 请求构造器
# ================================================================
def _template_llm_request(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:10]
    r = (kw + "专家", kw + "应用", 0.3 + (v * 0.2))
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"实现一个 **LLM 请求构造器**，为「{r[0]}」角色拼装标准的 Messages 格式请求。\n\n"
            f"理解大模型 API 调用的核心：System Prompt / User Prompt / Messages / Temperature。\n\n"
            f"## 📖 背景知识\n"
            f"调用大模型 API 时需要构造标准格式的消息列表：\n"
            f"- System Message：设定 AI 的身份和行为规则\n"
            f"- User Message：用户的具体问题和上下文\n"
            f"- Temperature：控制生成文本的随机性（0=确定性，1=创造性）\n\n"
            f"## 💡 你将学到\n"
            f"- LLM API 的请求格式\n"
            f"- System Prompt 设计方法\n"
            f"- 参数（temperature、max_tokens）的作用"
        ),
        "requirements": [
            "创建 LLMRequest 类，包含 role、task、temperature 属性",
            "build_system_prompt() → 返回 '你是一位专业的{role}，擅长{task}'",
            "build_user_prompt(context, question) → 拼装背景+问题的格式化文本",
            "build_messages(context, question) → 返回 [{'role':'system','content':...}, {'role':'user','content':...}]",
            "describe() → 打印当前请求的完整配置信息",
        ],
        "test_cases": [
            {"name": "System Prompt", "description": "验证系统提示格式",
             "setup_code": f"req = LLMRequest('{r[0]}', '{r[1]}', {r[2]})\nprint(req.build_system_prompt())",
             "expected_output": f"你是一位专业的{r[0]}，擅长{r[1]}", "check_type": "output_contains"},
            {"name": "Messages 格式", "description": "验证消息列表结构",
             "setup_code": "req = LLMRequest('助手', '答疑', 0.3)\nmsgs = req.build_messages('今天下雨', '需要带伞吗')\nprint('system' in msgs[0].get('role',''))",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "Temperature 存储", "description": "验证参数保存",
             "setup_code": f"req = LLMRequest('{r[0]}', '{r[1]}', {r[2]})\nprint(req.temperature)",
             "expected_output": str(r[2]), "check_type": "output_contains"},
        ],
        "starter_code": _LLM_STARTER.format(topic=topic, knowledge=knowledge, role=r[0], task=r[1], temp=r[2]),
        "answer_code": _LLM_ANSWER,
        "hints": [
            ("💡 第1步：完成 __init__()",
             "self.role = role\nself.task = task\nself.temperature = temperature\n这三个属性是所有方法的输入基础。"),
            ("🔑 第2步：实现 build 系列方法",
             "build_system_prompt():\n  return f'你是一位专业的{self.role}，擅长{self.task}'\n\nbuild_user_prompt(context, question):\n  return f'背景信息：{context}\\n\\n问题：{question}'\n\nbuild_messages(context, question):\n  return [\n    {'role':'system','content':self.build_system_prompt()},\n    {'role':'user','content':self.build_user_prompt(context,question)}\n  ]"),
            ("📖 第3步：实现 describe()",
             "return f'角色:{self.role} 任务:{self.task} 温度:{self.temperature}'\n运行代码，观察完整的 LLM API 请求结构。"),
        ],
    }


_LLM_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
为 {role} 角色实现 LLM 请求构造器 — 在 START/END 标记之间编写你的代码
"""


class LLMRequest:
    """大模型 API 请求构造器"""

    def __init__(self, role: str, task: str, temperature: float = 0.7):
        # ========== START ==========
        # 保存 role, task, temperature 为实例属性
        pass
        # ========== END ==========

    def build_system_prompt(self) -> str:
        """构建系统提示词"""
        # ========== START ==========
        # 返回格式: "你是一位专业的{{role}}，擅长{{task}}"
        pass
        # ========== END ==========

    def build_user_prompt(self, context: str, question: str) -> str:
        """构建用户消息"""
        # ========== START ==========
        # 返回格式: "背景信息：{{context}}\\n\\n问题：{{question}}"
        pass
        # ========== END ==========

    def build_messages(self, context: str, question: str) -> list:
        """构建完整的 messages 列表"""
        # ========== START ==========
        # 返回包含 system 和 user 两个消息的列表
        pass
        # ========== END ==========

    def describe(self) -> str:
        """描述当前请求配置"""
        # ========== START ==========
        # 返回: f"角色:{{self.role}} 任务:{{self.task}} 温度:{{self.temperature}}"
        pass
        # ========== END ==========


# ===== 测试代码（不要修改）=====
if __name__ == "__main__":
    req = LLMRequest("{role}", "{task}", {temp})
    print(req.build_system_prompt())
    print(req.build_user_prompt("AI发展迅速", "如何学习"))
    msgs = req.build_messages("AI发展迅速", "如何学习")
    print(f"消息数: {{len(msgs)}}")
    print(req.describe())
'''

_LLM_ANSWER = '''class LLMRequest:
    def __init__(self, role: str, task: str, temperature: float = 0.7):
        self.role = role
        self.task = task
        self.temperature = temperature

    def build_system_prompt(self) -> str:
        return f"你是一位专业的{self.role}，擅长{self.task}"

    def build_user_prompt(self, context: str, question: str) -> str:
        return f"背景信息：{context}\\n\\n问题：{question}"

    def build_messages(self, context: str, question: str) -> list:
        return [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": self.build_user_prompt(context, question)}
        ]

    def describe(self) -> str:
        return f"角色:{self.role} 任务:{self.task} 温度:{self.temperature}"
'''


# ================================================================
# 模板 3: 思维链 Prompt 引擎
# ================================================================
def _template_cot_engine(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:12]
    q = (f"什么是{kw}", "JSON" if v % 2 == 0 else "markdown")
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"实现一个 **思维链 Prompt 引擎**，为「{q[0]}」这类问题自动生成带分步推理的链式提示。\n\n"
            f"## 📖 背景知识\n"
            f"Chain-of-Thought (CoT) 是提示词工程的核心技术：\n"
            f"- Zero-shot CoT：在 prompt 中添加「让我们一步步思考」\n"
            f"- Few-shot CoT：提供带推理过程的示例\n"
            f"- 结构化输出：要求模型按指定格式输出\n\n"
            f"## 💡 你将学到\n"
            f"- CoT 提示词的构造方法\n"
            f"- 如何设计结构化的 Prompt 模板\n"
            f"- 不同提示策略的效果差异"
        ),
        "requirements": [
            "创建 CoTEngine 类，支持多种提示策略",
            "zero_shot_cot(question) → 添加'让我们逐步分析'引导语",
            "few_shot_cot(question, examples) → 拼接示例+问题",
            "structured_prompt(question, output_format) → 要求按格式输出",
            "compare(question) → 返回三种策略的完整 prompt 对比",
        ],
        "test_cases": [
            {"name": "Zero-shot CoT", "description": "验证基础思维链生成",
             "setup_code": f"engine = CoTEngine()\np = engine.zero_shot_cot('{q[0]}')\nprint('逐步' in p)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "Few-shot CoT", "description": "验证带示例的提示",
             "setup_code": "engine = CoTEngine()\nexamples = ['Q:1+1=? A:思考:1+1=2 答案:2']\np = engine.few_shot_cot('2+2=?', examples)\nprint('示例' in p)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "结构化输出", "description": "验证格式要求",
             "setup_code": f"engine = CoTEngine()\np = engine.structured_prompt('分析天气', '{q[1]}')\nprint('{q[1]}' in p)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _COT_STARTER.format(topic=topic, knowledge=knowledge, question=q[0], fmt=q[1]),
        "answer_code": _COT_ANSWER,
        "hints": [
            ("💡 第1步：实现 zero_shot_cot()",
             "return f'{question}\\n\\n让我们逐步分析这个问题：\\n第一步：'\n只需在问题后拼接引导语，触发模型的分步推理。"),
            ("🔑 第2步：实现 few_shot_cot()",
             "prefix = '以下是一些问答示例：\\n'\nfor ex in examples:\n    prefix += f'- 示例：{ex}\\n'\nreturn prefix + f'\\n现在请回答：{question}\\n请仿照示例逐步推理'"),
            ("📖 第3步：实现 compare()",
             "return {\n  'zero_shot': self.zero_shot_cot(question),\n  'few_shot': self.few_shot_cot(question, []),\n  'structured': self.structured_prompt(question, 'markdown')\n}\n运行观察三种策略生成的不同 prompt。"),
        ],
    }


_COT_STARTER = '''"""
编程实验: {topic}
实现思维链 Prompt 引擎 — 在 START/END 标记之间编写你的代码
"""


class CoTEngine:
    """Chain-of-Thought 提示词引擎"""

    def zero_shot_cot(self, question: str) -> str:
        """零样本思维链：在问题后添加引导语句"""
        # ========== START ==========
        # 返回: f"{{question}}\\n\\n让我们逐步分析这个问题：\\n第一步："
        pass
        # ========== END ==========

    def few_shot_cot(self, question: str, examples: list) -> str:
        """小样本思维链：拼接示例和问题"""
        # ========== START ==========
        # 1. 构建 "以下是一些问答示例：\\n" + 每个示例用换行连接
        # 2. 添加 "\\n现在请回答：{{question}}\\n请仿照示例逐步推理"
        pass
        # ========== END ==========

    def structured_prompt(self, question: str, output_format: str) -> str:
        """结构化输出提示"""
        # ========== START ==========
        # 返回: f"{{question}}\\n\\n请严格按照{{output_format}}格式输出你的答案。"
        pass
        # ========== END ==========

    def compare(self, question: str) -> dict:
        """对比三种策略的 Prompt"""
        # ========== START ==========
        # 返回包含三种策略结果的字典
        pass
        # ========== END ==========


# ===== 测试代码 =====
if __name__ == "__main__":
    engine = CoTEngine()
    q = "什么是机器学习"
    print("--- Zero-shot CoT ---")
    p1 = engine.zero_shot_cot(q)
    print(p1[:100])
    print("--- Few-shot CoT ---")
    p2 = engine.few_shot_cot("2+2=?", ["Q:1+1=? 思考:1+1=2 A:2"])
    print(p2[:100])
    print("--- 对比 ---")
    r = engine.compare(q)
    print(f"三种策略: {{list(r.keys())}}")
'''

_COT_ANSWER = '''class CoTEngine:
    def zero_shot_cot(self, question: str) -> str:
        return f"{question}\\n\\n让我们逐步分析这个问题：\\n第一步："

    def few_shot_cot(self, question: str, examples: list) -> str:
        prefix = "以下是一些问答示例：\\n"
        for ex in examples:
            prefix += f"- 示例：{ex}\\n"
        return prefix + f"\\n现在请回答：{question}\\n请仿照示例逐步推理"

    def structured_prompt(self, question: str, output_format: str) -> str:
        return f"{question}\\n\\n请严格按照{output_format}格式输出你的答案，不要输出其他内容。"

    def compare(self, question: str) -> dict:
        return {
            "zero_shot": self.zero_shot_cot(question),
            "few_shot": self.few_shot_cot(question, []),
            "structured": self.structured_prompt(question, "markdown")
        }
'''


# ================================================================
# 模板 4: 工具调用 Agent
# ================================================================
def _template_tool_agent(topic: str, knowledge: str, v: int = 0) -> dict:
    tool_sets = [
        ("智能家居", [("灯光控制", "开灯 关灯 灯光 亮度"), ("空调控制", "空调 温度 制冷 制热"), ("窗帘控制", "窗帘 打开 关闭")]),
        ("数据分析", [("数据查询", "查询 搜索 数据 统计"), ("图表生成", "图表 可视化 柱状图"), ("报告导出", "导出 报告 PDF")]),
        ("客服系统", [("订单查询", "订单 物流 查询"), ("退款处理", "退款 退货 取消"), ("优惠查询", "优惠 折扣 促销")]),
    ]
    ts = tool_sets[v % 3]
    tools_desc = "\n".join([f"- **{t[0]}**：{t[1]}" for t in ts[1]])
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"为 **{ts[0]}场景**实现一个带工具调用能力的 ToolAgent。\n\n"
            f"可用工具：\n{tools_desc}\n\n"
            f"## 📖 背景知识\n"
            f"Tool Use（工具调用）是 AI Agent 区别于 ChatBot 的关键能力：\n"
            f"- Agent 理解用户意图 → 选择工具 → 填充参数 → 执行 → 返回结果\n"
            f"- 每个工具需要定义：名称、描述、参数、执行函数\n\n"
            f"## 💡 你将学到\n"
            f"- 工具注册和描述机制\n"
            f"- 基于关键词的意图→工具匹配"
        ),
        "requirements": [
            "Tool 类已提供（name, description, func）",
            "创建 ToolAgent 类，维护 tools 字典和 history 列表",
            "register_tool(tool)：注册工具到 Agent 的 tools 字典",
            "list_tools()：返回所有可用工具的 [(名称, 描述), ...] 列表",
            "_match_tool(user_input)：根据输入关键词匹配最合适的工具",
            "execute(user_input)：匹配工具 → 执行 → 返回结果",
        ],
        "test_cases": [
            {"name": "工具注册", "description": "验证工具注册和列表",
             "setup_code": "agent = ToolAgent('Helper')\nagent.register_tool(Tool('计算器','进行数学计算', lambda x: str(eval(x))))\nprint(len(agent.list_tools()))",
             "expected_output": "1", "check_type": "output_contains"},
            {"name": "工具匹配-计算", "description": "输入含'计算'关键词应匹配计算器",
             "setup_code": "agent = ToolAgent('Helper')\nagent.register_tool(Tool('计算器','数学计算', lambda x: str(eval(x))))\nr = agent.execute('帮我计算 3+5')\nprint('8' in r)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "未匹配提示", "description": "无匹配工具时返回提示",
             "setup_code": "agent = ToolAgent('Helper')\nr = agent.execute('今天星期几')\nprint('没有找到' in r or '无法' in r)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _TOOL_STARTER.format(topic=topic, knowledge=knowledge),
        "answer_code": _TOOL_ANSWER,
        "hints": [
            ("💡 第1步：实现 register_tool() 和 list_tools()",
             "register_tool: self.tools[tool.name] = tool\nlist_tools: return [(t.name, t.description) for t in self.tools.values()]"),
            ("🔑 第2步：实现 _match_tool()",
             "for tool in self.tools.values():\n    keywords = tool.description.split() + [tool.name]\n    for kw in keywords:\n        if len(kw) >= 2 and kw in user_input:\n            return tool\nreturn None"),
            ("📖 第3步：实现 execute()",
             "self.history.append(user_input)\ntool = self._match_tool(user_input)\nif tool:\n    return f'[{tool.name}] ' + tool.func(user_input)\nreturn '抱歉，没有找到可以处理该请求的工具'"),
        ],
    }


_TOOL_STARTER = '''"""
编程实验: {topic}
实现带工具调用能力的 Agent — 在 START/END 标记之间编写你的代码
"""


class Tool:
    """单个工具"""
    def __init__(self, name: str, description: str, func):
        self.name = name
        self.description = description
        self.func = func


class ToolAgent:
    """带工具调用能力的智能体"""

    def __init__(self, name: str):
        self.name = name
        self.tools = {{}}
        self.history = []
        # ========== START ==========
        pass
        # ========== END ==========

    def register_tool(self, tool: Tool):
        """注册工具到Agent"""
        # ========== START ==========
        # 将 tool 存入 self.tools[tool.name]
        pass
        # ========== END ==========

    def list_tools(self) -> list:
        """列出所有可用工具"""
        # ========== START ==========
        # 返回 [(name, description), ...] 列表
        pass
        # ========== END ==========

    def _match_tool(self, user_input: str):
        """根据用户输入匹配工具（关键词匹配）"""
        # ========== START ==========
        # 遍历 self.tools.values()，如果 tool.name 或 tool.description
        # 中的词出现在 user_input 中，则返回该 tool；没有则返回 None
        pass
        # ========== END ==========

    def execute(self, user_input: str) -> str:
        """执行用户指令"""
        # ========== START ==========
        # 1. 记录输入到 self.history
        # 2. 匹配工具
        # 3. 如果找到工具，调用 tool.func(user_input) 并返回结果
        # 4. 如果没找到，返回提示信息
        pass
        # ========== END ==========


# ===== 内置工具（已实现）=====
def calculator(expr: str) -> str:
    """安全的数学计算器"""
    try:
        import re
        cleaned = re.sub(r"[^0-9+\\-*/(). ]", "", expr)
        return str(eval(cleaned))
    except:
        return "计算错误"


def weather_sim(city: str) -> str:
    """模拟天气查询"""
    return f"{{city}}今天晴天，温度22-28°C"


def current_time(dummy: str = "") -> str:
    """获取当前时间"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ===== 测试代码 =====
if __name__ == "__main__":
    agent = ToolAgent("Helper")
    agent.register_tool(Tool("计算器", "数学计算 算数 加法 减法", calculator))
    agent.register_tool(Tool("天气查询", "天气 温度 下雨 晴天", weather_sim))
    agent.register_tool(Tool("时间查询", "时间 几点 日期 现在", current_time))

    print(f"已注册 {{len(agent.list_tools())}} 个工具")
    print(agent.execute("帮我计算 3+5*2"))
    print(agent.execute("北京今天天气怎么样"))
    print(agent.execute("现在几点了"))
    print(agent.execute("帮我订一张机票"))
'''

_TOOL_ANSWER = '''class ToolAgent:
    def __init__(self, name: str):
        self.name = name
        self.tools = {}
        self.history = []

    def register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def list_tools(self) -> list:
        return [(t.name, t.description) for t in self.tools.values()]

    def _match_tool(self, user_input: str):
        for tool in self.tools.values():
            keywords = tool.description.split() + [tool.name]
            for kw in keywords:
                if len(kw) >= 2 and kw in user_input:
                    return tool
        return None

    def execute(self, user_input: str) -> str:
        self.history.append(user_input)
        tool = self._match_tool(user_input)
        if tool:
            result = tool.func(user_input)
            return f"[{tool.name}] {result}"
        return "抱歉，没有找到可以处理该请求的工具"
'''


# ================================================================
# 模板 5: RAG 检索问答系统
# ================================================================
def _template_rag_system(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:15]
    docs = [
        f"{kw}是AI智能体学科中的重要概念，涉及自主感知、决策和执行等方面。",
        f"理解{kw}需要掌握其核心定义、工作原理和典型应用场景。",
        f"在实际工程中，{kw}常用于构建更智能、更自主的软件系统。",
    ]
    corpus = (f"{kw}知识库", docs)
    docs_str = "\n".join([f"- {d}" for d in corpus[1]])
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"为 **{corpus[0]}** 从零实现一个 RAG 检索增强生成系统。\n\n"
            f"知识库文档：\n{docs_str}\n\n"
            f"## 📖 背景知识\n"
            f"RAG (Retrieval-Augmented Generation) 流程：\n"
            f"1. 文档加载与分块（chunking）\n"
            f"2. 用户查询 → 检索相关文档块\n"
            f"3. 将检索结果组合 → 生成增强答案\n\n"
            f"## 💡 你将学到\n"
            f"- RAG 的核心流程、文档切块、关键词检索与相关性排序"
        ),
        "requirements": [
            "创建 SimpleRAG 类，管理文档库和检索",
            "add_document(text)：添加文档到知识库并自动分块",
            "chunk_text(text)：将文本按句号/换行分割成句子块",
            "search(query, top_k)：在所有文档块中查找包含 query 的块，按相关性排序",
            "ask(query)：检索 → 组合增强回答 → 返回",
        ],
        "test_cases": [
            {"name": "文档分块", "description": "验证文本切分功能",
             "setup_code": "rag = SimpleRAG()\nchunks = rag.chunk_text('第一句。第二句。第三句。')\nprint(len(chunks))",
             "expected_output": "3", "check_type": "output_contains"},
            {"name": "关键词检索", "description": "验证检索返回正确结果",
             "setup_code": "rag = SimpleRAG()\nrag.add_document('AI Agent可以自主决策和执行任务')\nrag.add_document('Python是一种流行的编程语言')\nresults = rag.search('Agent', 3)\nprint(len(results))",
             "expected_output": "1", "check_type": "output_contains"},
            {"name": "增强回答", "description": "验证 RAG 完整流程",
             "setup_code": "rag = SimpleRAG()\nrag.add_document('Transformer架构基于自注意力机制，由Vaswani等人在2017年提出')\nrag.add_document('RNN循环神经网络适合处理序列数据')\nanswer = rag.ask('Transformer是什么')\nprint('自注意力' in answer)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "相关性排序", "description": "验证多结果时按相关性排序",
             "setup_code": "rag = SimpleRAG()\nrag.add_document('Python非常适合数据分析和机器学习')\nrag.add_document('Python也可用于Web开发')\nrag.add_document('机器学习需要大量数据')\nresults = rag.search('机器学习', 5)\nprint(len(results))",
             "expected_output": "2", "check_type": "output_contains"},
        ],
        "starter_code": _RAG_STARTER.format(topic=topic, knowledge=knowledge),
        "answer_code": _RAG_ANSWER,
        "hints": [
            ("💡 第1步：实现 add_document() 和 chunk_text()",
             "add_document:\n  self.documents.append(text)\n  chunks = self.chunk_text(text)\n  self.chunks.extend(chunks)\n\nchunk_text:\n  text = text.replace('\\n', '。')\n  sentences = text.split('。')\n  return [s.strip() for s in sentences if s.strip()]"),
            ("🔑 第2步：实现 search()",
             "scored = []\nfor chunk in self.chunks:\n    count = chunk.lower().count(query.lower())\n    if count > 0:\n        scored.append((count, chunk))\nscored.sort(key=lambda x: -x[0])\nreturn [chunk for _, chunk in scored[:top_k]]"),
            ("📖 第3步：实现 ask()",
             "results = self.search(query)\nif results:\n    return f'根据知识库中的{len(results)}条相关信息：{';'.join(results)}'\nreturn f'未在知识库中找到与{query}相关的信息'"),
        ],
    }


_RAG_STARTER = '''"""
编程实验: {topic}
从零实现 RAG 检索增强生成系统 — 在 START/END 标记之间编写你的代码
"""


class SimpleRAG:
    """简化版 RAG 检索增强生成系统"""

    def __init__(self):
        self.documents = []
        self.chunks = []
        # ========== START ==========
        pass
        # ========== END ==========

    def add_document(self, text: str):
        """添加文档到知识库并自动分块"""
        # ========== START ==========
        # 1. 将 text 存入 self.documents
        # 2. 调用 self.chunk_text(text) 分块
        # 3. 将分块结果扩展到 self.chunks
        pass
        # ========== END ==========

    def chunk_text(self, text: str) -> list:
        """将文本切分为句子块"""
        # ========== START ==========
        # 1. 用 "。" 和 "\\n" 分割文本
        # 2. 过滤掉空字符串
        # 3. 返回句子列表
        # 提示: text.replace("\\n", "。").split("。")
        pass
        # ========== END ==========

    def search(self, query: str, top_k: int = 3) -> list:
        """检索相关文档块"""
        # ========== START ==========
        # 1. 遍历 self.chunks，找出所有包含 query 的块
        # 2. 按 query 出现次数降序排列（相关性排序）
        # 3. 返回前 top_k 个结果
        pass
        # ========== END ==========

    def ask(self, query: str) -> str:
        """检索增强问答"""
        # ========== START ==========
        # 1. 调用 self.search(query) 检索
        # 2. 如果有结果: "根据知识库中的{{len(results)}}条相关信息：..."
        # 3. 如果无结果: "未在知识库中找到相关信息"
        pass
        # ========== END ==========


# ===== 测试代码 =====
if __name__ == "__main__":
    rag = SimpleRAG()
    rag.add_document("AI智能体是一种能自主感知环境、做出决策并执行行动的软件系统。")
    rag.add_document("Python是数据科学和机器学习领域最流行的编程语言之一。")
    rag.add_document("Transformer架构基于自注意力机制，彻底改变了NLP领域。")

    print(f"知识库共 {{len(rag.chunks)}} 个文档块")
    print("--- 检索测试 ---")
    results = rag.search("Agent", 3)
    print(f"找到 {{len(results)}} 条结果")
    print("--- RAG问答 ---")
    print(rag.ask("什么是AI智能体"))
    print(rag.ask("Transformer是什么"))
    print(rag.ask("今天天气怎么样"))
'''

_RAG_ANSWER = '''class SimpleRAG:
    def __init__(self):
        self.documents = []
        self.chunks = []

    def add_document(self, text: str):
        self.documents.append(text)
        chunks = self.chunk_text(text)
        self.chunks.extend(chunks)

    def chunk_text(self, text: str) -> list:
        text = text.replace("\\n", "。")
        sentences = text.split("。")
        return [s.strip() for s in sentences if s.strip()]

    def search(self, query: str, top_k: int = 3) -> list:
        scored = []
        for chunk in self.chunks:
            count = chunk.lower().count(query.lower())
            if count > 0:
                scored.append((count, chunk))
        scored.sort(key=lambda x: -x[0])
        return [chunk for _, chunk in scored[:top_k]]

    def ask(self, query: str) -> str:
        results = self.search(query)
        if results:
            return f"根据知识库中的{len(results)}条相关信息：{'；'.join(results)}"
        return f"未在知识库中找到与'{query}'相关的信息"
'''


# ================================================================
# 模板 6: 双 Agent 协作
# ================================================================
def _template_multi_agent(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:6]
    prefixes = ["CODE:", "DRAFT:", "CHECK:", "REVIEW:", "TEST:", "TASK:"]
    s = (f"{kw}协作", f"{kw}A", f"{kw}B", prefixes[v % 6])
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"实现一个 **{s[0]}双 Agent 协作系统**，{s[1]} 和 {s[2]} 通过 MessageBus 互相通信完成任务。\n\n"
            f"## 📖 背景知识\n"
            f"多智能体协作的核心要素：\n"
            f"- 消息传递：Agent 之间通过消息总线通信\n"
            f"- 角色分工：每个 Agent 有明确的职责\n"
            f"- 任务编排：定义协作流程\n\n"
            f"## 💡 你将学到\n"
            f"- Agent 间通信机制、消息总线设计模式、协作任务编排"
        ),
        "requirements": [
            "创建 Agent 类(name, role, bus)，具有 receive(from_name, msg) 方法",
            "创建 MessageBus 类，管理 Agent 注册和消息路由",
            "MessageBus.register(name, agent)：注册 Agent",
            "MessageBus.send(from_name, to_name, msg)：路由消息到目标 Agent",
            f"Agent.receive：接收消息、存入 inbox；若消息以 {s[3]} 开头则执行审查并回复",
        ],
        "test_cases": [
            {"name": "Agent 注册", "description": "验证 Agent 注册到总线",
             "setup_code": "bus = MessageBus()\na = Agent('Coder', '编写代码', bus)\nbus.register('Coder', a)\nprint(len(bus.agents))",
             "expected_output": "1", "check_type": "output_contains"},
            {"name": "消息传递", "description": "验证 Agent 间消息路由",
             "setup_code": "bus = MessageBus()\na = Agent('Alice', '发送者', bus)\nb = Agent('Bob', '接收者', bus)\nbus.register('Alice', a)\nbus.register('Bob', b)\nbus.send('Alice', 'Bob', 'Hello')\nprint(len(b.inbox))",
             "expected_output": "1", "check_type": "output_contains"},
            {"name": "代码审查协作", "description": "验证完整的审查流程",
             "setup_code": "bus = MessageBus()\ncoder = Agent('Coder', '编写代码', bus)\nreviewer = Agent('Reviewer', '代码审查', bus)\nbus.register('Coder', coder)\nbus.register('Reviewer', reviewer)\nbus.send('Coder', 'Reviewer', 'CODE:def add(a,b):return a+b')\nprint(len(reviewer.inbox))",
             "expected_output": "1", "check_type": "output_contains"},
        ],
        "starter_code": _MULTI_STARTER.format(topic=topic, knowledge=knowledge),
        "answer_code": _MULTI_ANSWER,
        "hints": [
            ("💡 第1步：实现 MessageBus",
             "register: self.agents[name] = agent\nsend:\n  self.log.append(f'{from_name} -> {to_name}: {msg[:50]}')\n  if to_name in self.agents:\n      self.agents[to_name].receive(from_name, msg)"),
            ("🔑 第2步：实现 Agent.receive()",
             "self.inbox.append(f'[来自{from_name}] {msg}')\nif msg.startswith('CODE:'):\n    code = msg[5:].strip()\n    review = '审查通过' if len(code) > 10 else '建议改进: 代码太短'\n    self.bus.send(self.name, from_name, review)"),
            ("📖 第3步：验证协作流程",
             "Coder 发送 CODE 消息 → Reviewer 收到并审查 → 回复审查结果 → Coder 收到回复。\n检查 inbox 和 log 输出验证消息流转。"),
        ],
    }


_MULTI_STARTER = '''"""
编程实验: {topic}
双 Agent 协作系统 — 在 START/END 标记之间编写你的代码
"""


class Agent:
    """协作智能体"""

    def __init__(self, name: str, role: str, bus):
        self.name = name
        self.role = role
        self.bus = bus
        self.inbox = []
        # ========== START ==========
        pass
        # ========== END ==========

    def receive(self, from_name: str, msg: str):
        """接收消息并处理"""
        # ========== START ==========
        # 1. 将消息存入 self.inbox: f"[来自{{from_name}}] {{msg}}"
        # 2. 如果 msg 以 "CODE:" 开头，执行代码审查：
        #    - 提取代码: code = msg[5:].strip()
        #    - 审查: 如果 len(code) > 10 → "审查通过" 否则 "建议改进"
        # 3. 回复发送者: self.bus.send(self.name, from_name, 审查结果)
        pass
        # ========== END ==========


class MessageBus:
    """消息总线"""

    def __init__(self):
        self.agents = {{}}
        self.log = []

    def register(self, name: str, agent):
        """注册 Agent 到总线"""
        # ========== START ==========
        pass
        # ========== END ==========

    def send(self, from_name: str, to_name: str, msg: str):
        """发送消息给目标 Agent"""
        # ========== START ==========
        # 1. 记录消息到 self.log: f"{{from_name}} -> {{to_name}}: {{msg[:50]}}"
        # 2. 如果目标存在，调用 agent.receive(from_name, msg)
        # 3. 如果目标不存在，打印提示
        pass
        # ========== END ==========


# ===== 测试代码 =====
if __name__ == "__main__":
    bus = MessageBus()
    coder = Agent("Coder", "编写代码", bus)
    reviewer = Agent("Reviewer", "代码审查", bus)
    bus.register("Coder", coder)
    bus.register("Reviewer", reviewer)

    print(f"已注册 {{len(bus.agents)}} 个Agent")
    print("--- 提交代码审查 ---")
    bus.send("Coder", "Reviewer", "CODE:def add(a,b):return a+b")
    print(f"Coder收件箱: {{len(coder.inbox)}} 条")
    print(f"Reviewer收件箱: {{len(reviewer.inbox)}} 条")
    print(f"总线日志: {{len(bus.log)}} 条")
'''

_MULTI_ANSWER = '''class Agent:
    def __init__(self, name: str, role: str, bus):
        self.name = name
        self.role = role
        self.bus = bus
        self.inbox = []

    def receive(self, from_name: str, msg: str):
        self.inbox.append(f"[来自{from_name}] {msg}")
        if msg.startswith("CODE:"):
            code = msg[5:].strip()
            if len(code) > 10:
                review = f"审查通过: {code} — 代码结构清晰"
            else:
                review = f"建议改进: {code} — 代码太短，请添加更多逻辑"
            self.bus.send(self.name, from_name, review)


class MessageBus:
    def __init__(self):
        self.agents = {}
        self.log = []

    def register(self, name: str, agent):
        self.agents[name] = agent

    def send(self, from_name: str, to_name: str, msg: str):
        self.log.append(f"{from_name} -> {to_name}: {msg[:50]}")
        if to_name in self.agents:
            self.agents[to_name].receive(from_name, msg)
        else:
            print(f"消息无法送达: {to_name} 不存在")
'''


# ================================================================
# Type-C 模板：反射式 Agent（智能体基础概念 — 第3种练习）
# ================================================================
def _template_reflex_agent(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    cls_name = kw[:4] + "Reflex"
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n实现一个**条件反射式 Agent**，用 if-else 规则匹配输入并返回预设响应。\n\n"
            f"## 📖 背景知识\n反射式 Agent 是最简单的智能体：根据当前感知直接选择行动，无内部状态、无历史记忆。\n"
            f"适用场景：规则明确、输入有限的简单自动化任务。\n\n## 💡 你将学到\n- 规则引擎的实现\n- 模式匹配策略\n- 简单 Agent 的适用边界"
        ),
        "requirements": [
            f"创建 {cls_name} 类，维护 rules 字典",
            "add_rule(pattern, response)：注册匹配规则",
            "respond(msg)：遍历规则，返回第一个匹配的响应",
            "match_count(msg)：返回有多少条规则匹配该消息",
            "未匹配时返回默认响应",
        ],
        "test_cases": [
            {"name": "规则匹配", "description": "验证规则引擎",
             "setup_code": f"agent = {cls_name}()\nagent.add_rule('你好', '你好！')\nr = agent.respond('你好')\nprint(r)",
             "expected_output": "你好！", "check_type": "output_contains"},
            {"name": "匹配计数", "description": "验证多条规则匹配计数",
             "setup_code": f"agent = {cls_name}()\nagent.add_rule('天气', '晴天')\nagent.add_rule('气', '模糊匹配')\nn = agent.match_count('天气不错')\nprint(n)",
             "expected_output": "2", "check_type": "output_contains"},
            {"name": "默认响应", "description": "无匹配时返回默认",
             "setup_code": f"agent = {cls_name}()\nr = agent.respond('xyz')\nprint(len(r)>0)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _REFLEX_STARTER.replace('{cls_name}', cls_name).replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _REFLEX_ANSWER.replace('{cls_name}', cls_name),
        "hints": [
            ("方向提示", "respond: for pattern, response in self.rules.items(): if pattern in msg: return response"),
            ("关键代码", "match_count: sum(1 for p in self.rules if p in msg)"),
            ("完整答案", "查看 answer_code"),
        ],
    }

_REFLEX_STARTER = '''"""
编程实验: {topic} | 知识点: {knowledge}
实现条件反射式 Agent ({cls_name}) — 在 START/END 之间编写代码
"""

class {cls_name}:
    def __init__(self):
        self.rules = {{}}
        # ========== START ==========
        pass
        # ========== END ==========

    def add_rule(self, pattern: str, response: str):
        # ========== START ==========
        pass
        # ========== END ==========

    def respond(self, msg: str) -> str:
        # ========== START ==========
        pass
        # ========== END ==========

    def match_count(self, msg: str) -> int:
        # ========== START ==========
        pass
        # ========== END ==========

if __name__ == "__main__":
    agent = {cls_name}()
    agent.add_rule("你好", "你好！有什么可以帮您？")
    agent.add_rule("天气", "今日晴转多云")
    agent.add_rule("帮助", "可用命令: 你好、天气、帮助")
    print(agent.respond("你好"))
    print(agent.respond("今天天气如何"))
    print(f"匹配规则数: {{agent.match_count('你好天气')}}")
'''.replace('{{', '{').replace('}}', '}')

_REFLEX_ANSWER = '''class {cls_name}:
    def __init__(self):
        self.rules = {{}}

    def add_rule(self, pattern: str, response: str):
        self.rules[pattern] = response

    def respond(self, msg: str) -> str:
        for pattern, response in self.rules.items():
            if pattern in msg:
                return response
        return "抱歉，我不理解您的请求"

    def match_count(self, msg: str) -> int:
        return sum(1 for p in self.rules if p in msg)
'''.replace('{{', '{').replace('}}', '}')


# ================================================================
# Type-C 模板：参数调节器（大模型基座原理 — 第3种练习）
# ================================================================
def _template_param_tuner(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n实现一个**模型参数调节器**，根据输入内容自动推荐最佳的 temperature、max_tokens 等参数。\n\n"
            f"## 📖 背景知识\n大模型的关键参数：temperature(0=确定性,1=创造性)、max_tokens(输出长度)、top_p(核采样)。\n"
            f"不同任务需要不同参数配置。\n\n## 💡 你将学到\n- 参数对生成结果的影响\n- 根据任务类型推荐参数"
        ),
        "requirements": [
            "创建 ParamTuner 类",
            "analyze_task(text)：分析文本的复杂度（长文本→高分）和创造性需求（含'创意/头脑风暴'→高分）",
            "recommend(text)：返回推荐的参数字典 {'temperature':..., 'max_tokens':..., 'top_p':...}",
            "explain(params)：返回人类可读的参数说明",
        ],
        "test_cases": [
            {"name": "代码任务低温度", "description": "代码生成应推荐低temperature",
             "setup_code": "pt = ParamTuner()\np = pt.recommend('编写一个Python排序函数')\nprint(p['temperature'] <= 0.4)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "创意任务高温度", "description": "创意写作应推荐高temperature",
             "setup_code": "pt = ParamTuner()\np = pt.recommend('写一首关于未来的创意诗歌')\nprint(p['temperature'] >= 0.7)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _TUNER_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _TUNER_ANSWER,
        "hints": [
            ("方向提示", "analyze_task: 用关键词判断任务类型（代码/创意/分析）"),
            ("关键代码", "if '代码' in text or '编程' in text: return {'temperature':0.2,...}"),
            ("完整答案", "查看 answer_code"),
        ],
    }

_TUNER_STARTER = '''"""
编程实验: {topic} | 知识点: {knowledge}
实现模型参数调节器 — 在 START/END 之间编写代码
"""

class ParamTuner:
    def analyze_task(self, text: str) -> dict:
        # ========== START ==========
        pass
        # ========== END ==========

    def recommend(self, text: str) -> dict:
        # ========== START ==========
        pass
        # ========== END ==========

    def explain(self, params: dict) -> str:
        # ========== START ==========
        pass
        # ========== END ==========

if __name__ == "__main__":
    pt = ParamTuner()
    for task in ["写代码", "写创意诗歌", "分析数据报告"]:
        p = pt.recommend(task)
        print(f"{{task}}: T={{p['temperature']}} max={{p['max_tokens']}}")
'''

_TUNER_ANSWER = '''class ParamTuner:
    def analyze_task(self, text: str) -> dict:
        creative = any(w in text for w in ["创意", "诗歌", "故事", "头脑风暴"])
        code = any(w in text for w in ["代码", "编程", "函数", "算法"])
        return {"creative": creative, "code": code, "length": len(text)}

    def recommend(self, text: str) -> dict:
        analysis = self.analyze_task(text)
        if analysis["code"]:
            return {"temperature": 0.2, "max_tokens": 2048, "top_p": 0.9}
        elif analysis["creative"]:
            return {"temperature": 0.9, "max_tokens": 4096, "top_p": 0.95}
        return {"temperature": 0.5, "max_tokens": 2048, "top_p": 0.9}

    def explain(self, params: dict) -> str:
        return f"Temperature={params['temperature']}, max_tokens={params['max_tokens']}"
'''


# ================================================================
# Type-C 模板：模板构造器（提示词工程 — 第3种练习）
# ================================================================
def _template_template_builder(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n实现一个**Prompt 模板引擎**，支持变量替换和条件渲染，批量生成 Prompt。\n\n"
            f"## 📖 背景知识\n生产环境中常用模板来批量生成 Prompt：\n- 模板变量：用 {{variable}} 表示\n"
            f"- 条件块：根据变量值决定是否包含某段内容\n- 批量填充：一个模板+多组数据=多个 Prompt\n\n## 💡 你将学到\n- 模板引擎原理\n- 变量替换实现\n- 批量生成模式"
        ),
        "requirements": [
            "创建 PromptTemplate 类",
            "compile(template_str)：解析模板字符串",
            "render(variables)：替换模板中的 {{var}} 为实际值",
            "batch_render(data_list)：对多组数据批量渲染",
        ],
        "test_cases": [
            {"name": "变量替换", "description": "验证 {{var}} 替换",
             "setup_code": "pt = PromptTemplate()\npt.compile('你好{{name}}，请帮我{{task}}')\nr = pt.render({{'name':'Alice','task':'写代码'}})\nprint('Alice' in r and '写代码' in r)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "批量渲染", "description": "验证多组数据",
             "setup_code": "pt = PromptTemplate()\npt.compile('{{greeting}}，{{name}}')\nr = pt.batch_render([{{'greeting':'Hi','name':'A'}},{{'greeting':'Hello','name':'B'}}])\nprint(len(r))",
             "expected_output": "2", "check_type": "output_contains"},
        ],
        "starter_code": _TMPL_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _TMPL_ANSWER,
        "hints": [("方向提示", "用 re.sub(r'{{(\\w+)}}', ...) 替换模板变量"), ("完整答案", "查看 answer_code")],
    }

_TMPL_STARTER = '''"""
编程实验: {topic} | 知识点: {knowledge}
实现 Prompt 模板引擎 — 在 START/END 之间编写代码
"""
import re

class PromptTemplate:
    def compile(self, template_str: str):
        # ========== START ==========
        pass
        # ========== END ==========

    def render(self, variables: dict) -> str:
        # ========== START ==========
        pass
        # ========== END ==========

    def batch_render(self, data_list: list) -> list:
        # ========== START ==========
        pass
        # ========== END ==========

if __name__ == "__main__":
    pt = PromptTemplate()
    pt.compile("你是{{role}}，请用{{lang}}编写{{task}}")
    r = pt.render({{"role":"教师","lang":"Python","task":"排序算法"}})
    print(r)
    batch = pt.batch_render([{{"role":"A","lang":"Py","task":"X"}},{{"role":"B","lang":"JS","task":"Y"}}])
    print(f"Batch: {{len(batch)}} prompts")
'''

_TMPL_ANSWER = '''import re

class PromptTemplate:
    def compile(self, template_str: str):
        self.template = template_str

    def render(self, variables: dict) -> str:
        result = self.template
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    def batch_render(self, data_list: list) -> list:
        return [self.render(vars) for vars in data_list]
'''


# ================================================================
# Type-C 模板：流水线构造器（智能体框架开发 — 第3种练习）
# ================================================================
def _template_pipeline_builder(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n实现一个**数据处理流水线**，将多个处理步骤串联执行，模拟 Agent 的任务编排。\n\n"
            f"## 📖 背景知识\nAgent 框架中常用 Pipeline 模式编排多个处理步骤：\n- 每个步骤是一个函数，接收输入返回输出\n"
            f"- 步骤串联：前一步的输出是后一步的输入\n- 错误处理：某步失败时可跳过或中止\n\n## 💡 你将学到\n- Pipeline 设计模式\n- 函数式编程思想\n- 错误处理策略"
        ),
        "requirements": [
            "创建 Pipeline 类",
            "add_step(name, func)：添加处理步骤",
            "run(data)：按顺序执行所有步骤，返回最终结果和步骤日志",
            "run_safe(data)：执行步骤，某步出错时跳过并记录错误",
        ],
        "test_cases": [
            {"name": "流水线执行", "description": "验证顺序执行",
             "setup_code": "p = Pipeline()\np.add_step('double', lambda x: x*2)\np.add_step('add10', lambda x: x+10)\nr = p.run(5)\nprint(r['result'])",
             "expected_output": "20", "check_type": "output_contains"},
            {"name": "安全模式", "description": "验证错误跳过",
             "setup_code": "p = Pipeline()\np.add_step('ok', lambda x: x+1)\np.add_step('fail', lambda x: 1/0)\np.add_step('final', lambda x: x*3)\nr = p.run_safe(2)\nprint(r['result'])",
             "expected_output": "9", "check_type": "output_contains"},
        ],
        "starter_code": _PIPE_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _PIPE_ANSWER,
        "hints": [("方向提示", "run: for step in steps: data = step.func(data)"), ("完整答案", "查看 answer_code")],
    }

_PIPE_STARTER = '''"""
编程实验: {topic} | 知识点: {knowledge}
实现数据处理流水线 — 在 START/END 之间编写代码
"""

class Pipeline:
    def __init__(self):
        self.steps = []
        # ========== START ==========
        pass
        # ========== END ==========

    def add_step(self, name: str, func):
        # ========== START ==========
        pass
        # ========== END ==========

    def run(self, data):
        # ========== START ==========
        pass
        # ========== END ==========

    def run_safe(self, data):
        # ========== START ==========
        pass
        # ========== END ==========

if __name__ == "__main__":
    p = Pipeline()
    p.add_step("double", lambda x: x * 2)
    p.add_step("add10", lambda x: x + 10)
    r = p.run(5)
    print(f"Result: {{r['result']}}, Steps: {{len(r['log'])}}")
'''

_PIPE_ANSWER = '''class Pipeline:
    def __init__(self):
        self.steps = []

    def add_step(self, name: str, func):
        self.steps.append((name, func))

    def run(self, data):
        log = []
        for name, func in self.steps:
            data = func(data)
            log.append(f"{{name}}: OK")
        return {{"result": data, "log": log}}

    def run_safe(self, data):
        log = []
        for name, func in self.steps:
            try:
                data = func(data)
                log.append(f"{{name}}: OK")
            except Exception as e:
                log.append(f"{{name}}: ERROR - {{e}}")
        return {{"result": data, "log": log}}
'''


# ================================================================
# Type-C 模板：文本相似度计算器（智能体算法逻辑 — 第3种练习）
# ================================================================
def _template_similarity_calc(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n实现一个**文本相似度计算器**，用多种算法计算两段文本的相似度。\n\n"
            f"## 📖 背景知识\n向量检索是 RAG 和 Agent 记忆系统的基础：\n- Jaccard 相似度：交集/并集\n"
            f"- 余弦相似度（简化）：共同词数/sqrt(len1*len2)\n- 应用：文档去重、语义检索、推荐\n\n## 💡 你将学到\n- 文本相似度算法\n- 特征提取方法\n- 在 Agent 检索中的应用"
        ),
        "requirements": [
            "创建 TextSimilarity 类",
            "tokenize(text)：分词（按空格和标点）",
            "jaccard_sim(text1, text2)：计算 Jaccard 相似度",
            "cosine_sim(text1, text2)：计算简化版余弦相似度",
            "compare(text1, text2)：返回两种相似度分数的字典",
        ],
        "test_cases": [
            {"name": "相同文本", "description": "相同文本相似度应为1.0",
             "setup_code": "ts = TextSimilarity()\nr = ts.compare('hello world', 'hello world')\nprint(r['jaccard'])",
             "expected_output": "1.0", "check_type": "output_contains"},
            {"name": "部分相似", "description": "部分重叠应有0~1之间的分数",
             "setup_code": "ts = TextSimilarity()\nr = ts.compare('AI Agent 智能体', 'AI 智能体 学习')\nprint(0 < r['jaccard'] < 1)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _SIM_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _SIM_ANSWER,
        "hints": [("方向提示", "jaccard: len(intersection)/len(union)"), ("完整答案", "查看 answer_code")],
    }

_SIM_STARTER = '''"""
编程实验: {topic} | 知识点: {knowledge}
实现文本相似度计算器 — 在 START/END 之间编写代码
"""
import re

class TextSimilarity:
    def tokenize(self, text: str) -> set:
        # ========== START ==========
        pass
        # ========== END ==========

    def jaccard_sim(self, text1: str, text2: str) -> float:
        # ========== START ==========
        pass
        # ========== END ==========

    def cosine_sim(self, text1: str, text2: str) -> float:
        # ========== START ==========
        pass
        # ========== END ==========

    def compare(self, text1: str, text2: str) -> dict:
        # ========== START ==========
        pass
        # ========== END ==========

if __name__ == "__main__":
    ts = TextSimilarity()
    r = ts.compare("AI Agent 智能体", "AI 智能体 学习")
    print(r)
'''

_SIM_ANSWER = '''import re, math

class TextSimilarity:
    def tokenize(self, text: str) -> set:
        return set(re.findall(r'\\w+', text.lower()))

    def jaccard_sim(self, text1: str, text2: str) -> float:
        s1, s2 = self.tokenize(text1), self.tokenize(text2)
        if not s1 and not s2: return 1.0
        return len(s1 & s2) / len(s1 | s2)

    def cosine_sim(self, text1: str, text2: str) -> float:
        s1, s2 = self.tokenize(text1), self.tokenize(text2)
        common = len(s1 & s2)
        if not s1 or not s2: return 0.0
        return common / math.sqrt(len(s1) * len(s2))

    def compare(self, text1: str, text2: str) -> dict:
        return {{"jaccard": round(self.jaccard_sim(text1, text2), 3),
                "cosine": round(self.cosine_sim(text1, text2), 3)}}
'''


# ================================================================
# Type-C 模板：任务委派器（多智能体应用 — 第3种练习）
# ================================================================
def _template_task_delegator(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n实现一个**任务委派系统**，根据任务类型自动分配给最合适的 Agent。\n\n"
            f"## 📖 背景知识\nManager-Worker 模式中，Manager 负责任务分配：\n- 每个 Worker 注册自己能处理的任务类型\n"
            f"- Manager 接收任务 → 匹配 Worker → 委派 → 收集结果\n- 无人能处理时返回错误\n\n## 💡 你将学到\n- 任务委派模式\n- Worker 能力注册\n- 负载均衡基础"
        ),
        "requirements": [
            "创建 Worker 类(name, skills)，具有 execute(task) 方法",
            "创建 Delegator 类，管理 Worker 池",
            "register(worker)：注册 Worker",
            "delegate(task_type, task_data)：按任务类型匹配 Worker 并执行",
            "list_capabilities()：列出所有 Worker 的能力",
        ],
        "test_cases": [
            {"name": "任务委派", "description": "验证任务分配给正确Worker",
             "setup_code": "d = Delegator()\nd.register(Worker('Coder', ['python','java']))\nr = d.delegate('python', 'print(1)')\nprint('Coder' in r)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "无匹配", "description": "验证无人能处理时返回错误",
             "setup_code": "d = Delegator()\nd.register(Worker('Coder', ['python']))\nr = d.delegate('design', 'task')\nprint('无法' in r or '未找到' in r)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _DELEG_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _DELEG_ANSWER,
        "hints": [("方向提示", "delegate: 找到 skills 含 task_type 的 Worker"), ("完整答案", "查看 answer_code")],
    }

_DELEG_STARTER = '''"""
编程实验: {topic} | 知识点: {knowledge}
实现任务委派系统 — 在 START/END 之间编写代码
"""

class Worker:
    def __init__(self, name: str, skills: list):
        self.name = name
        self.skills = skills
    def execute(self, task: str) -> str:
        return f"[{{self.name}}] 完成: {{task}}"

class Delegator:
    def __init__(self):
        self.workers = []
        # ========== START ==========
        pass
        # ========== END ==========

    def register(self, worker: Worker):
        # ========== START ==========
        pass
        # ========== END ==========

    def delegate(self, task_type: str, task_data: str) -> str:
        # ========== START ==========
        pass
        # ========== END ==========

    def list_capabilities(self) -> dict:
        # ========== START ==========
        pass
        # ========== END ==========

if __name__ == "__main__":
    d = Delegator()
    d.register(Worker("Coder", ["python", "java"]))
    d.register(Worker("Designer", ["ui", "ux"]))
    print(d.delegate("python", "写排序算法"))
    print(d.delegate("ui", "设计登录页"))
    print(d.delegate("database", "建表"))
    print(d.list_capabilities())
'''

_DELEG_ANSWER = '''class Delegator:
    def __init__(self):
        self.workers = []

    def register(self, worker: Worker):
        self.workers.append(worker)

    def delegate(self, task_type: str, task_data: str) -> str:
        for w in self.workers:
            if task_type in w.skills:
                return w.execute(task_data)
        return f"未找到能处理 {{task_type}} 的Worker"

    def list_capabilities(self) -> dict:
        return {{w.name: w.skills for w in self.workers}}
'''


# ================================================================
# 兜底模板
# ================================================================
def _template_fallback(topic: str, knowledge: str) -> dict:
    return {
        "title": f"编程练习: {topic}",
        "knowledge": knowledge,
        "description": f"## 编程练习\n\n请根据以下知识点完成编程练习：{knowledge}",
        "requirements": ["创建至少一个类或函数", "包含测试代码", "代码能正常运行"],
        "test_cases": [{"name": "代码可运行", "description": "验证代码能执行",
                        "setup_code": "", "expected_output": "", "check_type": "output_exists"}],
        "starter_code": f"# 编程练习: {knowledge}\n\n",
        "answer_code": "# 参考答案\n",
        "hints": [],
    }


# ================================================================
# Type-B 模板：状态机 Agent（智能体基础概念 — 第2种练习）
# ================================================================
def _template_state_agent(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:8]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"实现一个 **状态机驱动的智能体**，根据当前状态和输入在不同行为模式间切换。\n\n"
            f"与 OODA 循环不同，状态机 Agent 的决策取决于**当前所处状态**而非单次判断。\n\n"
            f"## 📖 背景知识\n"
            f"有限状态机是 Agent 行为建模的基础工具：\n"
            f"- 每个状态定义了一组行为规则\n"
            f"- 输入事件触发状态转移\n"
            f"- Agent 的行为 = 当前状态 + 输入 → 行动 + 新状态\n\n"
            f"## 💡 你将学到\n"
            f"- 状态机的建模方法\n"
            f"- 状态转移表的设计\n"
            f"- 事件驱动的 Agent 行为模式"
        ),
        "requirements": [
            "创建 StateAgent 类，维护 states 字典和 current_state",
            "add_state(name, transitions)：注册一个状态及其转移规则",
            "set_state(name)：切换当前状态",
            "handle(event)：根据当前状态和事件执行动作并可能转移状态",
            "状态转移规则格式：{'event_name': ('action', 'next_state')}",
        ],
        "test_cases": [
            {"name": "状态注册", "description": "验证状态添加功能",
             "setup_code": f"agent = StateAgent('{kw}Bot')\nagent.add_state('idle', {{'start': ('初始化完成', 'ready')}})\nprint(len(agent.states))",
             "expected_output": "1", "check_type": "output_contains"},
            {"name": "状态转移", "description": "验证事件触发状态切换",
             "setup_code": f"agent = StateAgent('Bot')\nagent.add_state('idle', {{'go': ('moving', 'active')}})\nagent.set_state('idle')\nresult = agent.handle('go')\nprint(result, agent.current_state)",
             "expected_output": "moving active", "check_type": "output_contains"},
            {"name": "未知事件", "description": "验证未定义事件的处理",
             "setup_code": f"agent = StateAgent('Bot')\nagent.add_state('idle', {{}})\nagent.set_state('idle')\nr = agent.handle('unknown')\nprint('无法处理' in r or '未知' in r)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _STATE_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge).replace('{bot_name}', kw+'Bot').replace('{event}', f'start_{kw[:4]}'),
        "answer_code": _STATE_ANSWER,
        "hints": [
            ("方向提示", "handle方法: if event in self.states[self.current_state]: action, next_state = ..."),
            ("关键代码", "states[name] = transitions; 转移规则用字典存储 event→(action, next_state)"),
            ("完整答案", "查看 answer_code"),
        ],
    }


_STATE_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现状态机 Agent ({bot_name}) — 在 START/END 之间编写代码
"""


class StateAgent:
    """状态机驱动的智能体"""

    def __init__(self, name: str):
        self.name = name
        self.states = {{}}
        self.current_state = "idle"
        # ========== START ==========
        self.add_state("idle", {{}})
        # ========== END ==========

    def add_state(self, name: str, transitions: dict):
        """注册一个状态及其转移规则
        transitions 格式: {{'event': ('action', 'next_state'), ...}}"""
        # ========== START ==========
        pass
        # ========== END ==========

    def set_state(self, name: str):
        """切换到指定状态"""
        # ========== START ==========
        pass
        # ========== END ==========

    def handle(self, event: str) -> str:
        """处理事件：在当前状态下查找匹配的转移规则并执行"""
        # ========== START ==========
        # 1. 获取当前状态的转移规则
        # 2. 如果 event 在规则中，执行 action，更新 current_state
        # 3. 返回 action 字符串；若事件未定义，返回提示
        pass
        # ========== END ==========


if __name__ == "__main__":
    agent = StateAgent("{bot_name}")
    agent.add_state("idle", {{"start": ("初始化完成", "ready")}})
    agent.add_state("ready", {{"process": ("处理数据中", "busy"), "stop": ("关闭中", "idle")}})
    agent.add_state("busy", {{"done": ("任务完成", "ready")}})
    agent.set_state("idle")
    print(f"当前状态: {{agent.current_state}}")
    r = agent.handle("{event}")
    print(f"执行: {{r}}, 新状态: {{agent.current_state}}")
'''.replace('{{', '{').replace('}}', '}')

_STATE_ANSWER = '''class StateAgent:
    def __init__(self, name: str):
        self.name = name
        self.states = {}
        self.current_state = "idle"
        self.add_state("idle", {})

    def add_state(self, name: str, transitions: dict):
        self.states[name] = transitions

    def set_state(self, name: str):
        self.current_state = name

    def handle(self, event: str) -> str:
        if self.current_state in self.states:
            rules = self.states[self.current_state]
            if event in rules:
                action, next_state = rules[event]
                self.current_state = next_state
                return action
        return f"无法处理事件: {event}"
'''


# ================================================================
# Type-B 模板：Token 计数器（大模型基座原理 — 第2种练习）
# ================================================================
def _template_token_counter(topic: str, knowledge: str, v: int = 0) -> dict:
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            "## 🎯 实验目标\n"
            "实现一个简易的 **Token 计数器和文本分块器**，模拟大模型处理文本前的预处理流程。\n\n"
            "## 📖 背景知识\n"
            "大模型处理文本前需要：\n"
            "- Tokenization：将文本切分为 token（词或子词）\n"
            "- Context Window：模型能处理的最大 token 数\n"
            "- Truncation：超长文本的截断策略\n\n"
            "## 💡 你将学到\n"
            "- Token 的基本概念和估算方法\n"
            "- 上下文窗口的工作原理\n"
            "- 文本预处理流程"
        ),
        "requirements": [
            "创建 TokenProcessor 类，实现 token 计数和文本处理",
            "count_tokens(text)：按中文字数+英文单词数估算 token 数",
            "split_chunks(text, max_tokens)：将文本按 max_tokens 切块",
            "truncate(text, max_tokens, strategy)：按策略截断（'head'取开头/'tail'取结尾）",
            "stats(text)：返回 {'chars': 字符数, 'tokens': 估算token数, 'chunks': 需多少块}",
        ],
        "test_cases": [
            {"name": "Token 计数", "description": "验证中英文token估算",
             "setup_code": "tp = TokenProcessor()\ncount = tp.count_tokens('Hello World 你好世界')\nprint(count)",
             "expected_output": "4", "check_type": "output_contains"},
            {"name": "文本分块", "description": "验证长文本切分",
             "setup_code": "tp = TokenProcessor()\nchunks = tp.split_chunks('一二三四五六七八九十', 3)\nprint(len(chunks))",
             "expected_output": "4", "check_type": "output_contains"},
            {"name": "截断策略", "description": "验证head截断",
             "setup_code": "tp = TokenProcessor()\nr = tp.truncate('ABCDEFGHIJ', 5, 'head')\nprint(len(r))",
             "expected_output": "5", "check_type": "output_contains"},
        ],
        "starter_code": _TOKEN_STARTER.format(topic=topic, knowledge=knowledge),
        "answer_code": _TOKEN_ANSWER,
        "hints": [
            ("方向提示", "count_tokens: 中文按字符数，英文按空格分词数"),
            ("关键代码", "split_chunks: 用循环每次取 max_tokens 个字符，text[i:i+max_tokens]"),
            ("完整答案", "查看 answer_code"),
        ],
    }


_TOKEN_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现 Token 计数器和文本分块器 — 在 START/END 之间编写代码
"""


class TokenProcessor:
    """文本 Token 处理器"""

    def count_tokens(self, text: str) -> int:
        """估算 token 数量（中文按字符，英文按单词）"""
        # ========== START ==========
        # import re
        # 中文字符数 + 英文单词数
        pass
        # ========== END ==========

    def split_chunks(self, text: str, max_tokens: int) -> list:
        """将文本按 max_tokens 切分为多个块"""
        # ========== START ==========
        pass
        # ========== END ==========

    def truncate(self, text: str, max_tokens: int, strategy: str = "head") -> str:
        """截断文本：'head'取前 max_tokens 个字符, 'tail'取后 max_tokens 个"""
        # ========== START ==========
        pass
        # ========== END ==========

    def stats(self, text: str) -> dict:
        """返回文本统计信息"""
        # ========== START ==========
        pass
        # ========== END ==========


if __name__ == "__main__":
    tp = TokenProcessor()
    text = "Hello World 你好世界 AI Agent 智能体"
    print(f"Tokens: {{tp.count_tokens(text)}}")
    chunks = tp.split_chunks("一二三四五六七八九十", 3)
    print(f"Chunks: {{len(chunks)}}")
    print(f"Trunc: {{tp.truncate('ABCDEFGHIJ', 5, 'head')}}")
    print(tp.stats(text))
'''

_TOKEN_ANSWER = '''import re

class TokenProcessor:
    def count_tokens(self, text: str) -> int:
        chinese = len(re.findall(r'[\\u4e00-\\u9fff]', text))
        english = len([w for w in re.findall(r'[a-zA-Z]+', text)])
        return chinese + english

    def split_chunks(self, text: str, max_tokens: int) -> list:
        return [text[i:i+max_tokens] for i in range(0, len(text), max_tokens)]

    def truncate(self, text: str, max_tokens: int, strategy: str = "head") -> str:
        if strategy == "head":
            return text[:max_tokens]
        return text[-max_tokens:]

    def stats(self, text: str) -> dict:
        tokens = self.count_tokens(text)
        return {"chars": len(text), "tokens": tokens, "chunks": (tokens + 99) // 100}
'''


# ================================================================
# Type-B 模板：Prompt 评分器（提示词工程 — 第2种练习）
# ================================================================
def _template_prompt_scorer(topic: str, knowledge: str, v: int = 0) -> dict:
    kw = knowledge.strip()[:10]
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            f"## 🎯 实验目标\n"
            f"实现一个 **Prompt 质量评分器**，根据多个维度自动评估提示词的质量。\n\n"
            f"## 📖 背景知识\n"
            f"好的 Prompt 通常具备以下特征：\n"
            f"- 明确性：清晰描述任务和期望输出\n"
            f"- 完整性：包含必要的上下文和约束\n"
            f"- 结构化：有清晰的格式和步骤指引\n\n"
            f"## 💡 你将学到\n"
            f"- Prompt 质量评估的维度\n"
            f"- 如何编写评分规则\n"
            f"- 自动化的 Prompt 优化思路"
        ),
        "requirements": [
            "创建 PromptScorer 类，实现多维度评分",
            "score_clarity(prompt)：根据长度和关键词评估明确性(0-10)",
            "score_structure(prompt)：检查是否有编号/列表/分段等结构(0-10)",
            "score_completeness(prompt)：检查是否包含角色/任务/格式三要素(0-10)",
            "evaluate(prompt)：返回总分和分项评分字典",
        ],
        "test_cases": [
            {"name": "高分提示词", "description": "完整提示词应得高分",
             "setup_code": "ps = PromptScorer()\ngood = '你是一位教师。请分三步解释：1.概念 2.原理 3.示例。用markdown格式输出。'\nr = ps.evaluate(good)\nprint(r['total'] >= 15)",
             "expected_output": "True", "check_type": "output_contains"},
            {"name": "低分提示词", "description": "模糊提示词应得低分",
             "setup_code": "ps = PromptScorer()\nbad = '解释一下'\nr = ps.evaluate(bad)\nprint(r['total'] < 10)",
             "expected_output": "True", "check_type": "output_contains"},
        ],
        "starter_code": _SCORER_STARTER.format(topic=topic, knowledge=knowledge),
        "answer_code": _SCORER_ANSWER,
        "hints": [
            ("方向提示", "score_clarity: len(prompt)>20得5分基础分，含具体关键词加分"),
            ("关键代码", "用 if '步骤' in prompt or '1.' in prompt 检测结构化程度"),
            ("完整答案", "查看 answer_code"),
        ],
    }


_SCORER_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现 Prompt 质量评分器 — 在 START/END 之间编写代码
"""


class PromptScorer:
    """Prompt 质量评分器"""

    def score_clarity(self, prompt: str) -> int:
        """评估明确性：长度+关键词(0-10)"""
        # ========== START ==========
        pass
        # ========== END ==========

    def score_structure(self, prompt: str) -> int:
        """评估结构化程度(0-10)"""
        # ========== START ==========
        pass
        # ========== END ==========

    def score_completeness(self, prompt: str) -> int:
        """检查角色/任务/格式三要素(0-10)"""
        # ========== START ==========
        pass
        # ========== END ==========

    def evaluate(self, prompt: str) -> dict:
        """综合评估，返回总分和分项分"""
        # ========== START ==========
        pass
        # ========== END ==========


if __name__ == "__main__":
    ps = PromptScorer()
    good = "你是一位Python教师。请分三步讲解：1.变量 2.循环 3.函数。用markdown格式输出。"
    bad = "解释一下"
    print(f"Good prompt: {{ps.evaluate(good)}}")
    print(f"Bad prompt: {{ps.evaluate(bad)}}")
'''

_SCORER_ANSWER = '''class PromptScorer:
    def score_clarity(self, prompt: str) -> int:
        score = min(5, len(prompt) // 10)
        keywords = ["解释", "分析", "描述", "列出", "比较", "实现"]
        score += sum(1 for k in keywords if k in prompt)
        return min(10, score)

    def score_structure(self, prompt: str) -> int:
        score = 0
        if any(c in prompt for c in ["1.", "2.", "3.", "步骤", "首先", "然后"]):
            score += 4
        if any(c in prompt for c in ["\\n", "markdown", "json", "表格"]):
            score += 3
        if len(prompt.split("。")) >= 2:
            score += 3
        return min(10, score)

    def score_completeness(self, prompt: str) -> int:
        score = 0
        if any(w in prompt for w in ["你是", "作为", "充当", "角色"]):
            score += 4
        if any(w in prompt for w in ["请", "帮我", "完成", "任务"]):
            score += 3
        if any(w in prompt for w in ["输出", "格式", "返回", "结果"]):
            score += 3
        return min(10, score)

    def evaluate(self, prompt: str) -> dict:
        c = self.score_clarity(prompt)
        s = self.score_structure(prompt)
        comp = self.score_completeness(prompt)
        return {"clarity": c, "structure": s, "completeness": comp, "total": c + s + comp}
'''


# ================================================================
# Type-B 模板：记忆系统（智能体框架开发 — 第2种练习）
# ================================================================
def _template_memory_system(topic: str, knowledge: str, v: int = 0) -> dict:
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            "## 🎯 实验目标\n"
            "实现 Agent 的 **三层记忆系统**：短期记忆（会话上下文）+ 长期记忆（持久存储）+ 工作记忆（当前任务）。\n\n"
            "## 📖 背景知识\n"
            "AI Agent 的记忆系统是区分简单 ChatBot 的关键能力：\n"
            "- 短期记忆：保存最近 N 轮对话\n"
            "- 长期记忆：跨会话持久化的知识和经验\n"
            "- 工作记忆：当前任务相关的临时状态\n\n"
            "## 💡 你将学到\n"
            "- 三层记忆架构的设计模式\n"
            "- 记忆的存储和检索策略\n"
            "- 记忆淘汰和优先级机制"
        ),
        "requirements": [
            "创建 MemorySystem 类，包含 short_term、long_term、working 三种存储",
            "remember(category, key, value)：存入指定记忆类型",
            "recall(category, key)：检索指定记忆",
            "recall_recent(n)：返回短期记忆中最近 n 条记录",
            "forget_old(max_size)：淘汰超出容量的旧记忆",
        ],
        "test_cases": [
            {"name": "记忆存储", "description": "验证三种记忆存储",
             "setup_code": "mem = MemorySystem()\nmem.remember('short_term', 'msg1', '你好')\nmem.remember('long_term', 'user_name', 'Alice')\nmem.remember('working', 'task', '写代码')\nprint(len(mem.short_term), len(mem.long_term), len(mem.working))",
             "expected_output": "1 1 1", "check_type": "output_contains"},
            {"name": "记忆检索", "description": "验证记忆读取",
             "setup_code": "mem = MemorySystem()\nmem.remember('long_term', 'lang', 'Python')\nprint(mem.recall('long_term', 'lang'))",
             "expected_output": "Python", "check_type": "output_contains"},
            {"name": "记忆淘汰", "description": "验证旧记忆清理",
             "setup_code": "mem = MemorySystem(max_short=3)\nfor i in range(5):\n    mem.remember('short_term', f'k{{i}}', f'v{{i}}')\nprint(len(mem.short_term))",
             "expected_output": "3", "check_type": "output_contains"},
        ],
        "starter_code": _MEM_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _MEM_ANSWER,
        "hints": [
            ("方向提示", "三种记忆都用 OrderedDict 实现，支持快速检索和淘汰"),
            ("关键代码", "forget_old: while len(self.short_term)>max_short: self.short_term.popitem(last=False)"),
            ("完整答案", "查看 answer_code"),
        ],
    }


_MEM_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现 Agent 三层记忆系统 — 在 START/END 之间编写代码
"""
from collections import OrderedDict


class MemorySystem:
    """AI Agent 三层记忆系统"""

    def __init__(self, max_short: int = 10):
        self.short_term = OrderedDict()
        self.long_term = {{}}
        self.working = {{}}
        self.max_short = max_short
        # ========== START ==========
        pass
        # ========== END ==========

    def remember(self, category: str, key: str, value):
        """将信息存入指定记忆类型"""
        # ========== START ==========
        pass
        # ========== END ==========

    def recall(self, category: str, key: str):
        """检索指定记忆，不存在返回 None"""
        # ========== START ==========
        pass
        # ========== END ==========

    def recall_recent(self, n: int = 5) -> list:
        """返回短期记忆中最新的 n 条 (value 列表)"""
        # ========== START ==========
        pass
        # ========== END ==========

    def forget_old(self):
        """淘汰超出容量的旧短期记忆"""
        # ========== START ==========
        pass
        # ========== END ==========


if __name__ == "__main__":
    mem = MemorySystem(max_short=3)
    mem.remember("short_term", "m1", "你好")
    mem.remember("short_term", "m2", "今天天气不错")
    mem.remember("long_term", "user", "Bob")
    mem.remember("working", "goal", "学习Agent")
    print(f"短期: {{len(mem.short_term)}}, 长期: {{len(mem.long_term)}}, 工作: {{len(mem.working)}}")
    print(f"recall user: {{mem.recall('long_term', 'user')}}")
    mem.remember("short_term", "m3", "第三条")
    mem.remember("short_term", "m4", "第四条")
    print(f"淘汰后短期: {{len(mem.short_term)}}")
'''.replace('{{', '{').replace('}}', '}')

_MEM_ANSWER = '''from collections import OrderedDict

class MemorySystem:
    def __init__(self, max_short: int = 10):
        self.short_term = OrderedDict()
        self.long_term = {}
        self.working = {}
        self.max_short = max_short

    def remember(self, category: str, key: str, value):
        store = {"short_term": self.short_term, "long_term": self.long_term, "working": self.working}
        if category in store:
            store[category][key] = value
        if category == "short_term":
            self.forget_old()

    def recall(self, category: str, key: str):
        store = {"short_term": self.short_term, "long_term": self.long_term, "working": self.working}
        return store.get(category, {}).get(key)

    def recall_recent(self, n: int = 5) -> list:
        return list(self.short_term.values())[-n:]

    def forget_old(self):
        while len(self.short_term) > self.max_short:
            self.short_term.popitem(last=False)
'''


# ================================================================
# Type-B 模板：决策树规划器（智能体算法逻辑 — 第2种练习）
# ================================================================
def _template_decision_tree(topic: str, knowledge: str, v: int = 0) -> dict:
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            "## 🎯 实验目标\n"
            "实现一个基于 **决策树的任务规划器**，根据条件自动选择执行路径。\n\n"
            "## 📖 背景知识\n"
            "决策树是 Agent 规划中最直观的方法：\n"
            "- 每个节点是一个判断条件\n"
            "- 分支代表不同的结果路径\n"
            "- 叶子节点是最终行动\n\n"
            "## 💡 你将学到\n"
            "- 决策树的构建和遍历\n"
            "- 条件判断的链式组合\n"
            "- Agent 规划的规则驱动方法"
        ),
        "requirements": [
            "创建 DecisionNode 类，包含 condition(函数)、yes_child、no_child、action",
            "创建 DecisionTree 类，管理根节点和决策流程",
            "add_rule(condition, action)：添加决策规则",
            "decide(context)：根据 context 遍历决策树，返回最终 action",
            "支持链式规则：按添加顺序依次判断",
        ],
        "test_cases": [
            {"name": "决策链", "description": "验证基本的if-else决策",
             "setup_code": "tree = DecisionTree()\ntree.add_rule(lambda c: c.get('urgent'), '立即处理')\ntree.add_rule(lambda c: c.get('important'), '安排时间')\nr = tree.decide({{'urgent': True}})\nprint(r)",
             "expected_output": "立即处理", "check_type": "output_contains"},
            {"name": "默认行动", "description": "无规则匹配时返回默认",
             "setup_code": "tree = DecisionTree()\ntree.add_rule(lambda c: c.get('urgent'), '立即')\nr = tree.decide({{}})\nprint(r)",
             "expected_output": "搁置", "check_type": "output_contains"},
        ],
        "starter_code": _DT_STARTER.replace('{topic}', topic).replace('{knowledge}', knowledge),
        "answer_code": _DT_ANSWER,
        "hints": [
            ("方向提示", "add_rule: 将(condition, action)元组存入 rules 列表"),
            ("关键代码", "decide: for cond, action in self.rules: if cond(context): return action"),
            ("完整答案", "查看 answer_code"),
        ],
    }


_DT_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现决策树任务规划器 — 在 START/END 之间编写代码
"""


class DecisionTree:
    """决策树任务规划器"""

    def __init__(self, default_action: str = "搁置"):
        self.rules = []
        self.default_action = default_action
        # ========== START ==========
        pass
        # ========== END ==========

    def add_rule(self, condition, action: str):
        """添加决策规则: condition 是函数(context)->bool, action 是结果字符串"""
        # ========== START ==========
        pass
        # ========== END ==========

    def decide(self, context: dict) -> str:
        """根据 context 依次匹配规则，返回第一个匹配的 action"""
        # ========== START ==========
        pass
        # ========== END ==========


if __name__ == "__main__":
    tree = DecisionTree("保持观望")
    tree.add_rule(lambda c: c.get("risk") == "high", "立即撤离")
    tree.add_rule(lambda c: c.get("confidence", 0) > 0.8, "执行交易")
    tree.add_rule(lambda c: c.get("confidence", 0) > 0.5, "等待确认")
    print(tree.decide({{"risk": "high"}}))
    print(tree.decide({{"confidence": 0.9}}))
    print(tree.decide({{"confidence": 0.6}}))
    print(tree.decide({{}}))
'''

_DT_ANSWER = '''class DecisionTree:
    def __init__(self, default_action: str = "搁置"):
        self.rules = []
        self.default_action = default_action

    def add_rule(self, condition, action: str):
        self.rules.append((condition, action))

    def decide(self, context: dict) -> str:
        for condition, action in self.rules:
            try:
                if condition(context):
                    return action
            except:
                continue
        return self.default_action
'''


# ================================================================
# Type-B 模板：投票系统（多智能体应用 — 第2种练习）
# ================================================================
def _template_voting_system(topic: str, knowledge: str, v: int = 0) -> dict:
    return {
        "title": f"编程实验: {topic}",
        "knowledge": knowledge,
        "description": (
            "## 🎯 实验目标\n"
            "实现一个 **多 Agent 投票决策系统**，多个 Agent 独立评估后投票得出最终结论。\n\n"
            "## 📖 背景知识\n"
            "投票是多智能体系统中常用的决策机制：\n"
            "- 每个 Agent 独立给出评分或判断\n"
            "- 通过投票聚合（多数/加权/一致同意）得出最终决策\n"
            "- 用于提高系统鲁棒性和准确性\n\n"
            "## 💡 你将学到\n"
            "- 投票机制的实现\n"
            "- 多数决、加权决的区别\n"
            "- 投票结果的可信度评估"
        ),
        "requirements": [
            "创建 Voter 类(name, weight)，具有 vote(question) 方法返回 (answer, confidence)",
            "创建 VotingSystem 类，管理多个 Voter 并进行投票聚合",
            "add_voter(voter)：注册投票者",
            "simple_majority(question)：简单多数决，返回票数最多的答案",
            "weighted_vote(question)：加权投票，按 voter.weight 权重计算",
        ],
        "test_cases": [
            {"name": "简单多数", "description": "验证多数决",
             "setup_code": "vs = VotingSystem()\nvs.add_voter(Voter('A',1,lambda q:'yes'))\nvs.add_voter(Voter('B',1,lambda q:'yes'))\nvs.add_voter(Voter('C',1,lambda q:'no'))\nprint(vs.simple_majority('ok?'))",
             "expected_output": "yes", "check_type": "output_contains"},
            {"name": "加权投票", "description": "验证权重影响",
             "setup_code": "vs = VotingSystem()\nvs.add_voter(Voter('Expert',3,lambda q:'buy'))\nvs.add_voter(Voter('A',1,lambda q:'sell'))\nvs.add_voter(Voter('B',1,lambda q:'sell'))\nprint(vs.weighted_vote('stock?'))",
             "expected_output": "buy", "check_type": "output_contains"},
        ],
        "starter_code": _VOTE_STARTER.format(topic=topic, knowledge=knowledge),
        "answer_code": _VOTE_ANSWER,
        "hints": [
            ("方向提示", "simple_majority: 用字典统计每个答案的出现次数"),
            ("关键代码", "weighted_vote: 累加每个投票者的 weight 到其答案上，返回最高权重答案"),
            ("完整答案", "查看 answer_code"),
        ],
    }


_VOTE_STARTER = '''"""
编程实验: {topic}
知识点: {knowledge}
实现多 Agent 投票系统 — 在 START/END 之间编写代码
"""


class Voter:
    """投票者"""
    def __init__(self, name: str, weight: float, vote_func):
        self.name = name
        self.weight = weight
        self.vote_func = vote_func

    def vote(self, question: str) -> tuple:
        """返回 (answer, confidence)"""
        return self.vote_func(question), self.weight


class VotingSystem:
    """多 Agent 投票系统"""

    def __init__(self):
        self.voters = []
        # ========== START ==========
        pass
        # ========== END ==========

    def add_voter(self, voter: Voter):
        # ========== START ==========
        pass
        # ========== END ==========

    def simple_majority(self, question: str) -> str:
        """简单多数决"""
        # ========== START ==========
        pass
        # ========== END ==========

    def weighted_vote(self, question: str) -> str:
        """加权投票"""
        # ========== START ==========
        pass
        # ========== END ==========


if __name__ == "__main__":
    vs = VotingSystem()
    vs.add_voter(Voter("Analyst1", 1, lambda q: "buy"))
    vs.add_voter(Voter("Analyst2", 1, lambda q: "buy"))
    vs.add_voter(Voter("Analyst3", 2, lambda q: "sell"))
    print(f"简单多数: {{vs.simple_majority('投资?')}}")
    print(f"加权投票: {{vs.weighted_vote('投资?')}}")
'''

_VOTE_ANSWER = '''class VotingSystem:
    def __init__(self):
        self.voters = []

    def add_voter(self, voter: Voter):
        self.voters.append(voter)

    def simple_majority(self, question: str) -> str:
        tally = {}
        for v in self.voters:
            ans, _ = v.vote(question)
            tally[ans] = tally.get(ans, 0) + 1
        return max(tally, key=tally.get)

    def weighted_vote(self, question: str) -> str:
        scores = {}
        for v in self.voters:
            ans, weight = v.vote(question)
            scores[ans] = scores.get(ans, 0) + weight
        return max(scores, key=scores.get)
'''
