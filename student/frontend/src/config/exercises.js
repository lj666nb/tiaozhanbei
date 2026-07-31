// AI智能体编程习题配置（63关，6大模块）
// 新增关卡只需在此文件中添加即可

export const MODULES = [
  {
    id: 1,
    name: "模块一：智能体基础通识",
    icon: "🤖",
    description: "掌握AI智能体的核心定义、分类、核心特征与运行闭环",
    taskCount: 9,
    tasks: [
      {
        id: "1-1",
        title: "理解 AI 智能体的官方学术定义",
        starter: `def agent_definition_demo():
    """
    返回 AI 智能体四大核心要素及其解释。
    """
    # TODO: 构建并返回字典
    pass`
      },
      {
        id: "1-2",
        title: "智能体 vs 传统 AI 应用的被动应答",
        starter: `def compare_passive_vs_agent(scenario):
    """
    scenario="recommend": 返回被动应答流程
    scenario="agent":    返回智能体主动决策流程
    """
    # TODO: 根据 scenario 返回对应的流程步骤列表
    pass`
      },
      {
        id: "1-3",
        title: "智能体 vs 聊天机器人的核心分界线",
        starter: `def classify_ai_system(features):
    """
    features: set[str] 包含系统的能力特征
    返回: "ChatBot" 或 "Agent"
    """
    # TODO: 根据特征判断系统类型
    pass`
      },
      {
        id: "1-4",
        title: "智能体 vs 工作流的适用场景",
        starter: `def recommend_approach(task_type):
    """
    根据任务类型推荐 Workflow 或 Agent。
    """
    # TODO: 实现映射逻辑
    pass`
      },
      {
        id: "1-5",
        title: "智能体的五大核心特征",
        starter: `def validate_agent_features(agent_config):
    """
    检查五大核心特征是否达标（>=60）。
    返回 {"passed": [...], "failed": [...]}
    """
    required = ["Autonomy", "Perception", "Reasoning", "Planning", "Action"]
    # TODO: 遍历检查并分类
    pass`
      },
      {
        id: "1-6",
        title: "智能体的辅助特征：记忆能力与学习能力",
        starter: `def assess_agent_level(features_dict):
    """
    根据所有特征评分判断智能体等级。
    """
    core = ["Autonomy", "Perception", "Reasoning", "Planning", "Action"]
    # TODO: 实现等级判断逻辑
    pass`
      },
      {
        id: "1-7",
        title: "反应式智能体的工作原理",
        starter: `def reflex_agent(percept, rules):
    """
    简单反应式智能体：根据当前感知查表返回动作。
    percept: 当前感知（str）
    rules:   条件-动作规则（dict）
    返回:    对应的动作（str），无匹配则返回 "NoOp"
    """
    # TODO: 实现条件-动作映射
    pass`
      },
      {
        id: "1-8",
        title: "基于记忆与目标导向智能体的工作原理",
        starter: `class GoalBasedAgent:
    def __init__(self, initial_state, goal_state):
        self.state = initial_state
        self.goal = goal_state
        self.history = []

    def perceive(self, observation):
        """将观察加入历史"""
        # TODO: 追加到 history
        pass

    def decide(self):
        """根据当前状态和目标决定行动"""
        # TODO: 如果 state != goal，返回行动描述
        pass

    def act(self, action):
        """执行行动，更新状态"""
        # TODO: 更新 self.state
        pass`
      },
      {
        id: "1-9",
        title: "智能体的基本运行闭环 Observe→Think→Act",
        starter: `def ota_loop(environment, max_steps=5):
    """
    模拟 Observe → Think → Act 循环。
    environment: {"state": ..., "goal": ...}
    返回日志列表
    """
    log = []
    for step in range(1, max_steps + 1):
        # 1. Observe
        observed = environment.get("state", "unknown")
        # 2. Think: 根据观察和目标决定计划
        if observed == environment.get("goal"):
            break
        plan = "advance" if observed != environment.get("goal") else "stay"
        # 3. Act: 执行计划
        environment["state"] = environment.get("goal") if plan == "advance" else observed
        # TODO: 完善上述逻辑并生成日志字符串
        log.append(f"Step {step}: Observe={observed} → Think={plan} → Act={environment['state']}")
    return log`
      },
    ]
  },
  {
    id: 2,
    name: "模块二：大模型（LLM）与提示词工程",
    icon: "🧠",
    description: "理解Transformer架构、微调技术、提示词工程核心方法",
    taskCount: 10,
    tasks: [
      {
        id: "2-1",
        title: "Transformer 架构核心 — 自注意力机制与位置编码",
        starter: `import math

def softmax_row(row):
    """对一行做 softmax，返回新列表"""
    exp_row = [math.exp(x) for x in row]
    total = sum(exp_row)
    return [x / total for x in exp_row]

def scaled_dot_product_attention(Q, K, V):
    """
    Q, K, V: 2x2 列表
    计算 softmax(Q * K^T / sqrt(dk)) * V
    """
    dk = len(Q[0])  # key 维度
    # TODO: 1. 计算 Q * K^T; 2. 除以 sqrt(dk); 3. softmax; 4. 乘以 V
    pass`
      },
      {
        id: "2-2",
        title: "预训练与指令微调",
        starter: `def simulate_finetune_effect(base_model_knowledge, instruction_data):
    """
    模拟指令微调：对 instruction_data 中出现的词提高概率。
    """
    result = dict(base_model_knowledge)  # 复制
    # TODO: 遍历 instruction_data，提取词并提高概率
    pass`
      },
      {
        id: "2-3",
        title: "LoRA 低秩适配基本概念",
        starter: `def apply_lora(original_weight, lora_A, lora_B, alpha=1.0):
    """
    模拟 LoRA: W' = W + alpha * (B @ A)
    original_weight, lora_A, lora_B 均为 2x2 列表
    """
    # 矩阵乘法 B @ A: (2x2) x (2x2) = (2x2)
    n = len(original_weight)
    # TODO: 计算 BA = B * A，然后 W' = W + alpha * BA
    pass`
      },
      {
        id: "2-4",
        title: "上下文学习与少样本提示",
        starter: `def build_few_shot_prompt(task, examples, query):
    """
    构建 Few-shot 提示词。
    """
    # TODO: 按格式拼接 task, examples, query
    pass`
      },
      {
        id: "2-5",
        title: "Prompt 标准结构",
        starter: `def build_structured_prompt(role, task, output_format):
    """
    构建标准 Prompt 结构，返回包含 messages 的字典。
    """
    # TODO: 构建 system + user 消息列表
    pass`
      },
      {
        id: "2-6",
        title: "思维链 Chain of Thought",
        starter: `def cot_solver(problem, steps=2):
    """
    模拟思维链推理。problem 格式: "计算 a op b op c"
    支持 +-*/, 遵循运算优先级。
    """
    import re
    # TODO: 解析表达式，按步骤拆分计算，返回推理过程和答案
    reasoning = []
    # 简易实现：用 eval 计算，但分步展示
    try:
        answer = eval(problem.replace("计算", "").strip())
        reasoning.append(f"步骤1: 解析表达式")
        reasoning.append(f"步骤2: 计算结果 = {answer}")
        return {"reasoning": reasoning, "answer": answer}
    except:
        return {"reasoning": [], "answer": None}`
      },
      {
        id: "2-7",
        title: "思维树 Tree of Thoughts",
        starter: `def tot_search(branches_scores):
    """
    branches_scores: list of (branch_name, score) tuples
    返回得分最高的前k条路径的 branch_name 列表
    """
    # TODO: 按分数排序，取前 k=3，包括所有并列最高分
    pass`
      },
      {
        id: "2-8",
        title: "ReAct 模式 — 推理与行动交替",
        starter: `def react_loop(task, tools, max_rounds=5):
    """
    模拟 ReAct 交替推理与行动。
    """
    log = []
    # TODO: 实现 Thought → Action → Observation 循环
    for i in range(max_rounds):
        thought = f"第{i+1}轮推理：需要调用工具来完成任务"
        # 选择第一个可用工具
        tool_name = list(tools.keys())[0]
        action_result = tools[tool_name](task)
        observation = str(action_result)
        log.append({"Thought": thought, "Action": f"调用{tool_name}", "Observation": observation})
        task = observation  # 更新task为观察结果
    return log`
      },
      {
        id: "2-9",
        title: "模型量化与推理加速",
        starter: `def simulate_quantization(weights, bits=8):
    """
    模拟权重量化与反量化过程。
    """
    max_val = max(abs(w) for w in weights)
    levels = 2 ** (bits - 1) - 1  # 量化级别数
    scale = max_val / levels if levels > 0 else 1.0
    # TODO: 量化（round(w/scale)*scale），计算误差
    quantized = []
    dequantized = []
    for w in weights:
        q = round(w / scale) * scale
        quantized.append(q)
        dequantized.append(q)
    error = sum(abs(weights[i] - dequantized[i]) for i in range(len(weights))) / len(weights)
    return {"quantized": quantized, "dequantized": dequantized, "error": error}`
      },
      {
        id: "2-10",
        title: "模型评估基础",
        starter: `def calculate_metrics(tp, fp, tn, fn):
    """
    计算分类模型的四个核心评估指标。
    """
    # TODO: 实现 accuracy, precision, recall, f1 的计算
    pass`
      },
    ]
  },
  {
    id: 3,
    name: "模块三：智能体四大核心能力模块",
    icon: "⚙️",
    description: "深入感知、记忆、规划、行动四大模块",
    taskCount: 14,
    tasks: [
      {
        id: "3-1",
        title: "自然语言指令解析",
        starter: `def parse_nl_instruction(text):
    """
    解析自然语言指令，提取意图和实体。
    """
    # TODO: 关键词匹配提取 intent 和 entities
    pass`
      },
      {
        id: "3-2",
        title: "多模态感知模拟",
        starter: `def fuse_multimodal_inputs(inputs):
    """
    融合多模态输入为统一语义表示。
    """
    parts = ["[融合感知]"]
    # TODO: 遍历 inputs，拼接各模态信息
    for modal in ["text", "image_desc", "audio_transcript"]:
        if modal in inputs and inputs[modal]:
            parts.append(f"{modal}: {inputs[modal]}")
    return " ".join(parts)`
      },
      {
        id: "3-3",
        title: "视觉语言模型（VLM）的基本作用",
        starter: `def simulate_vlm(image_features, concept_map):
    """
    模拟VLM：根据图像特征匹配最可能的概念。
    """
    # TODO: 统计每个概念的出现次数，返回最高频概念和占比
    pass`
      },
      {
        id: "3-4",
        title: "短期记忆 — 上下文窗口管理",
        starter: `class ShortTermMemory:
    def __init__(self, max_size=5):
        self.max_size = max_size
        self.messages = []

    def add(self, message):
        """添加消息，超出容量时移除最早的消息"""
        # TODO: append + 检查长度
        pass

    def get_context(self):
        """返回当前上下文"""
        # TODO
        pass

    def get_token_estimate(self):
        """估算 token 数"""
        total_chars = sum(len(str(m)) for m in self.messages)
        return total_chars // 2`
      },
      {
        id: "3-5",
        title: "长期记忆 — 向量数据库语义检索模拟",
        starter: `import math

def cosine_similarity(a, b):
    """计算两个向量的余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x**2 for x in a))
    norm_b = math.sqrt(sum(x**2 for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

def semantic_search(query_embedding, memory_store, top_k=3):
    """
    余弦相似度检索最相关的 top_k 条记忆。
    """
    # TODO: 计算所有相似度，排序，返回 top_k
    pass`
      },
      {
        id: "3-6",
        title: "知识图谱作为记忆增强手段",
        starter: `class KnowledgeGraph:
    def __init__(self):
        self.graph = {}  # {entity: [(relation, target), ...]}

    def add_triple(self, subject, relation, obj):
        """添加 (subject, relation, object) 三元组"""
        if subject not in self.graph:
            self.graph[subject] = []
        self.graph[subject].append((relation, obj))

def query_related_concepts(kg, entity, max_depth=1):
    """
    BFS 从 entity 出发，返回 max_depth 步内可达的所有实体。
    """
    # TODO: BFS遍历
    visited = set()
    current = {entity}
    for _ in range(max_depth):
        next_level = set()
        for e in current:
            if e not in visited and e in kg.graph:
                visited.add(e)
                for rel, target in kg.graph[e]:
                    next_level.add(target)
        current = next_level
    visited.update(current)
    visited.discard(entity)
    return visited`
      },
      {
        id: "3-7",
        title: "复杂任务自动分解",
        starter: `def decompose_task(goal, subtask_templates):
    """
    根据目标中的关键词匹配子任务模板，返回分解结果。
    """
    # TODO: 关键词匹配收集子任务
    tasks = []
    seen = set()
    for keyword, subtasks in subtask_templates.items():
        if keyword in goal:
            for t in subtasks:
                if t not in seen:
                    tasks.append(t)
                    seen.add(t)
    return tasks`
      },
      {
        id: "3-8",
        title: "状态空间搜索与分层规划",
        starter: `def hierarchical_path_plan(start, goal, waypoints):
    """
    分层规划：高层经过关键节点，细节步骤逐段展开。
    """
    # TODO: 构建高层路径和细节步骤
    path = [start] + waypoints + [goal]
    high_level = [f"{path[i]}→{path[i+1]}" for i in range(len(path)-1)]
    steps = [f"{seg}: 前进" for seg in high_level]
    return {"high_level": high_level, "steps": steps}`
      },
      {
        id: "3-9",
        title: "根据反馈动态调整子目标",
        starter: `def replan_on_failure(original_plan, failed_step, alternative_steps):
    """
    计划中某一步失败时，用替代步骤替换并返回新计划。
    """
    # TODO: 查找失败步骤位置，替换
    pass`
      },
      {
        id: "3-10",
        title: "函数调用 Function Calling 机制",
        starter: `def parse_function_call(llm_response):
    """
    解析 LLM 的函数调用 JSON 并模拟执行。
    """
    func_name = llm_response.get("function", "")
    params = llm_response.get("params", {})
    result = None
    # TODO: 根据 func_name 调用对应模拟函数
    if func_name == "get_weather":
        result = f"{params.get('city','未知')}: 晴, 25°C"
    elif func_name == "calculate":
        try:
            result = eval(str(params.get("expr", "0")))
        except:
            result = "计算错误"
    elif func_name == "search":
        result = f"搜索结果: 关于'{params.get('query','')}'的3条信息"
    else:
        result = "未知函数"
    return {"function": func_name, "params": params, "result": result}`
      },
      {
        id: "3-11",
        title: "外部工具集成",
        starter: `class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, func):
        """注册一个工具"""
        # TODO
        pass

    def call(self, name, **kwargs):
        """调用工具"""
        # TODO
        pass

    def list_tools(self):
        """列出所有工具名"""
        # TODO
        pass`
      },
      {
        id: "3-12",
        title: "沙箱安全执行代码",
        starter: `import io
import sys

def sandbox_execute(code, allowed_builtins=None):
    """
    在受限环境中执行 Python 代码。
    """
    if allowed_builtins is None:
        allowed_builtins = {"print", "len", "range", "int", "float", "str", "list", "dict", "abs", "min", "max", "sum"}
    safe_globals = {"__builtins__": {k: __builtins__[k] for k in allowed_builtins if k in __builtins__}}
    safe_globals["__builtins__"]["__import__"] = None  # 禁止import
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, safe_globals)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "output": str(e)}
    finally:
        sys.stdout = old_stdout`
      },
      {
        id: "3-13",
        title: "工具链编排设计",
        starter: `def execute_tool_chain(tool_chain, initial_input):
    """
    顺序执行工具链，支持错误跳过。
    """
    current = initial_input
    steps = []
    for tc in tool_chain:
        try:
            current = tc["func"](current)
            steps.append({"tool": tc["name"], "ok": True, "output": str(current)})
        except Exception as e:
            if tc.get("error_handling") == "skip":
                steps.append({"tool": tc["name"], "ok": False, "output": str(e)})
            else:
                return {"final_result": None, "steps": steps, "error": str(e)}
    return {"final_result": current, "steps": steps}`
      },
      {
        id: "3-14",
        title: "人在回路 Human-in-the-Loop",
        starter: `def hitl_gate(action, risk_level, threshold=7):
    """
    人在回路审批门控。
    """
    # TODO: 根据风险等级判断是否需要人工审批
    pass`
      },
    ]
  },
  {
    id: 4,
    name: "模块四：开发框架与工程实践",
    icon: "🔧",
    description: "学习LangChain/LangGraph/LlamaIndex等主流框架",
    taskCount: 13,
    tasks: [
      {
        id: "4-1",
        title: "LangChain 核心组件模拟",
        starter: `class SimpleChain:
    """模拟 LangChain 的 Chain 组件"""
    def __init__(self):
        self.steps = []

    def add_step(self, name, func):
        """添加处理步骤"""
        # TODO
        pass

    def run(self, input_data):
        """顺序执行所有步骤"""
        # TODO
        pass`
      },
      {
        id: "4-2",
        title: "LangGraph 状态机编排",
        starter: `class StateGraph:
    """模拟 LangGraph 状态机"""
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.conditional_edges = {}

    def add_node(self, name, func):
        self.nodes[name] = func

    def add_edge(self, from_node, to_node):
        self.edges[from_node] = to_node

    def add_conditional_edge(self, from_node, condition_func, mapping):
        self.conditional_edges[from_node] = (condition_func, mapping)

    def run(self, start_node, initial_state):
        # TODO: 从起始节点遍历图，应用每个节点的转换
        current = start_node
        state = dict(initial_state)
        max_steps = 20
        for _ in range(max_steps):
            if current in self.nodes:
                state = self.nodes[current](state)
            if current in self.conditional_edges:
                cond_fn, mapping = self.conditional_edges[current]
                branch = cond_fn(state)
                current = mapping.get(branch, current)
            elif current in self.edges:
                current = self.edges[current]
            else:
                break
        return state`
      },
      {
        id: "4-3",
        title: "LlamaIndex RAG 框架模拟",
        starter: `class SimpleIndex:
    """模拟 LlamaIndex 文档索引与检索"""
    def __init__(self):
        self.docs = []
        self.index = {}

    def add_documents(self, docs):
        """docs: list[str]"""
        # TODO
        pass

    def build_index(self):
        """构建倒排索引"""
        # TODO: 对每个文档分词（按空白字符split），建立词→文档ID映射
        pass

    def search(self, query, top_k=3):
        """检索最相关文档"""
        # TODO: query分词，统计每个文档的命中次数，返回top_k
        pass`
      },
      {
        id: "4-4",
        title: "CrewAI 多智能体协作角色定义",
        starter: `class CrewAI:
    """模拟 CrewAI 多智能体协作"""
    def __init__(self):
        self.agents = {}
        self.tasks = []

    def create_agent(self, name, role, goal):
        self.agents[name] = {"name": name, "role": role, "goal": goal}

    def create_task(self, description, assigned_agent_name):
        self.tasks.append({"description": description, "agent": assigned_agent_name})

    def execute(self):
        # TODO: 每个Agent执行分配给它的任务
        results = []
        for task in self.tasks:
            agent = self.agents.get(task["agent"])
            if agent:
                output = f"[{agent['role']}] 完成: {task['description']}"
                results.append({"agent": agent["name"], "task": task["description"], "output": output})
        return {"results": results}`
      },
      {
        id: "4-5",
        title: "AutoGen 多智能体对话模拟",
        starter: `def autogen_dialogue(agent_a, agent_b, topic, rounds=3):
    """
    模拟 AutoGen 双Agent对话。
    """
    dialogue = []
    for i in range(rounds):
        # TODO: 模拟两个Agent交替发言
        a_msg = f"[{agent_a['name']}] 关于'{topic}'的第{i+1}轮分析..."
        b_msg = f"[{agent_b['name']}] 对'{topic}'的反馈和建议..."
        dialogue.append({"speaker": agent_a["name"], "message": a_msg})
        dialogue.append({"speaker": agent_b["name"], "message": b_msg})
    return dialogue`
      },
      {
        id: "4-6",
        title: "RAG 检索增强生成全流程",
        starter: `def rag_pipeline(query, documents, llm_simulator):
    """
    RAG全流程：检索→增强→生成。
    """
    # 简易TF-IDF检索
    query_words = set(query.lower().split())
    scores = []
    for i, doc in enumerate(documents):
        doc_words = set(doc.lower().split())
        score = len(query_words & doc_words)
        scores.append((score, i))
    scores.sort(reverse=True)
    top_docs = [documents[s[1]] for s in scores[:2] if s[0] > 0]

    # 拼接上下文
    context = "\\n".join(top_docs)
    answer = llm_simulator(context, query)
    return {"retrieved": top_docs, "answer": answer}`
      },
      {
        id: "4-7",
        title: "向量数据库选型与相似度检索",
        starter: `import math

class VectorStore:
    """模拟向量数据库"""
    def __init__(self):
        self.vectors = []  # [(id, vector, metadata)]

    def add(self, id, vector, metadata=None):
        # TODO
        pass

    def search(self, query_vector, top_k=3):
        # TODO: 计算欧氏距离，返回最近的top_k
        pass`
      },
      {
        id: "4-8",
        title: "文档切块策略与嵌入向量化",
        starter: `def chunk_and_embed(text, chunk_size=128, overlap=20):
    """
    文档切块 + 简易嵌入向量生成。
    """
    chunks = []
    # TODO: 滑动窗口切块
    start = 0
    while start < len(text):
        chunk = text[start:start + chunk_size]
        if not chunk:
            break
        # 简易嵌入：32维向量（字符统计归一化）
        vector = [0.0] * 32
        for i, ch in enumerate(chunk[:32]):
            vector[i] = ord(ch) / 256.0
        chunks.append({"chunk": chunk, "vector": vector})
        start += chunk_size - overlap
    return chunks`
      },
      {
        id: "4-9",
        title: "提示链 Prompt Chaining 模式",
        starter: `def prompt_chain(task_input, steps):
    """
    串行执行提示链的所有步骤。
    """
    intermediate = []
    current = task_input
    # TODO: 顺序执行每步
    for name, func in steps:
        current = func(current)
        intermediate.append({"step": name, "output": current[:80]})
    return {"intermediate": intermediate, "final": current}`
      },
      {
        id: "4-10",
        title: "路由 Routing 模式",
        starter: `def router(intent, handlers):
    """
    根据意图关键词路由到对应处理器。
    """
    # TODO: 关键词匹配，选最佳handler
    for keyword, handler in sorted(handlers.items(), key=lambda x: -len(x[0])):
        if keyword in intent:
            return {"matched": keyword, "result": handler(intent)}
    return {"matched": "default", "result": f"无法处理意图: {intent}"}`
      },
      {
        id: "4-11",
        title: "并行化 Parallelization 模式",
        starter: `import time

def parallel_execute(tasks):
    """
    模拟并行执行多个任务。
    """
    results = []
    start = time.time()
    # 串行模拟并行（Python不用threading简化）
    for name, func in tasks:
        out = func()
        results.append({"task": name, "output": out})
    elapsed = round(time.time() - start, 4)
    return {"results": results, "total_time": elapsed}`
      },
      {
        id: "4-12",
        title: "自我反思 Reflection 模式",
        starter: `def reflection_loop(initial, evaluator, improver, max_iter=3):
    """
    自我反思迭代改进循环。
    """
    current = initial
    for i in range(max_iter):
        score, issues = evaluator(current)
        if score >= 0.8:
            return {"final": current, "iterations": i + 1, "final_score": score}
        current = improver(current, issues)
    score, _ = evaluator(current)
    return {"final": current, "iterations": max_iter, "final_score": score}`
      },
      {
        id: "4-13",
        title: "Agent API 工程化部署",
        starter: `from datetime import datetime

def api_gateway(request, agent_func, auth_token):
    """
    API 网关：鉴权→校验→执行→日志。
    """
    # TODO: 实现完整流程
    if auth_token != "valid_token_2024":
        return {"status": 401, "result": "Unauthorized", "log": ""}
    if "action" not in request:
        return {"status": 400, "result": "Missing action", "log": ""}
    result = agent_func(request)
    log = f"[{datetime.now().isoformat()}] action={request['action']} status=200"
    return {"status": 200, "result": result, "log": log}`
      },
    ]
  },
  {
    id: 5,
    name: "模块五：多智能体系统",
    icon: "🤝",
    description: "理解多Agent协作架构、通信协议、博弈论",
    taskCount: 7,
    tasks: [
      {
        id: "5-1",
        title: "多智能体系统定义与适用场景",
        starter: `def assign_tasks_to_agents(tasks, agents):
    """
    轮询（Round-Robin）策略分配任务给Agent。
    """
    # TODO: 实现轮询分配
    assignment = {a: [] for a in agents}
    for i, task in enumerate(tasks):
        agent = agents[i % len(agents)]
        assignment[agent].append(task)
    return assignment`
      },
      {
        id: "5-2",
        title: "管理者-执行者 Manager-Worker 模式",
        starter: `class ManagerWorkerSystem:
    """Manager-Worker 多智能体架构"""
    def __init__(self):
        self.manager_name = "Manager"
        self.workers = {}

    def add_worker(self, name, skill):
        self.workers[name] = {"name": name, "skill": skill}

    def run(self, task):
        # Manager 分解任务
        subtasks = [f"子任务{i+1}: {task} (第{i+1}部分)" for i in range(len(self.workers))]
        # 分配并执行
        results = {}
        for (name, worker), subtask in zip(self.workers.items(), subtasks):
            results[name] = f"[{worker['skill']}] 完成: {subtask}"
        return {
            "assignments": {name: st for name, st in zip(self.workers.keys(), subtasks)},
            "results": results,
            "summary": f"Manager分配{len(subtasks)}个子任务给{len(self.workers)}个Worker"
        }`
      },
      {
        id: "5-3",
        title: "专家小组 Peer-to-Peer 模式",
        starter: `def peer_voting(proposals, votes):
    """
    P2P投票决策：汇总所有Agent的投票，排序返回。
    """
    # TODO: 计算每个提案的总分，排序
    scores = {p: 0 for p in proposals}
    for agent, ballot in votes.items():
        for prop, score in ballot.items():
            if prop in scores:
                scores[prop] += score
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return ranked`
      },
      {
        id: "5-4",
        title: "智能体间通信协议",
        starter: `class MessageBus:
    """多智能体消息总线"""
    def __init__(self):
        self.agents = set()
        self.messages = {}

    def register(self, agent_name):
        self.agents.add(agent_name)
        if agent_name not in self.messages:
            self.messages[agent_name] = []

    def send(self, sender, receiver, content):
        """点对点发送"""
        # TODO
        pass

    def broadcast(self, sender, content):
        """广播给所有其他Agent"""
        # TODO
        pass

    def inbox(self, agent_name):
        """返回未读消息列表"""
        # TODO
        pass`
      },
      {
        id: "5-5",
        title: "公告板协调模式",
        starter: `class Blackboard:
    """共享公告板"""
    def __init__(self):
        self.board = {}

    def post(self, agent, topic, data):
        # TODO
        pass

    def read(self, agent, topic=None):
        # TODO
        pass

    def clear_topic(self, topic):
        # TODO
        pass`
      },
      {
        id: "5-6",
        title: "订阅/发布事件驱动模式",
        starter: `class PubSub:
    """发布/订阅事件系统"""
    def __init__(self):
        self.subscriptions = {}

    def subscribe(self, agent, event_type):
        # TODO
        pass

    def unsubscribe(self, agent, event_type):
        # TODO
        pass

    def publish(self, event_type, data):
        # TODO: 通知所有订阅者
        pass`
      },
      {
        id: "5-7",
        title: "博弈论纳什均衡入门",
        starter: `def find_nash_equilibrium(payoff_matrix):
    """
    找到2x2博弈中的所有纯策略纳什均衡。
    payoff_matrix: {("A1","B1"): (payoffA, payoffB), ...}
    """
    strategies_A = list(set(k[0] for k in payoff_matrix.keys()))
    strategies_B = list(set(k[1] for k in payoff_matrix.keys()))
    ne_list = []
    # TODO: 对每个策略组合检查是否为纳什均衡
    for a in strategies_A:
        for b in strategies_B:
            current = payoff_matrix.get((a, b))
            if current is None:
                continue
            # A是否有动机偏离？
            a_ok = all(
                current[0] >= payoff_matrix.get((alt_a, b), (float('-inf'),))[0]
                for alt_a in strategies_A if alt_a != a
            )
            # B是否有动机偏离？
            b_ok = all(
                current[1] >= payoff_matrix.get((a, alt_b), (0, float('-inf')))[1]
                for alt_b in strategies_B if alt_b != b
            )
            if a_ok and b_ok:
                ne_list.append((a, b))
    return ne_list`
      },
    ]
  },
  {
    id: 6,
    name: "模块六：评估、安全与前沿拓展",
    icon: "🛡️",
    description: "掌握评估基准、安全治理、MCP协议、前沿技术",
    taskCount: 10,
    tasks: [
      {
        id: "6-1",
        title: "AgentBench 综合评估环境",
        starter: `def evaluate_agent_on_benchmark(agent_outputs, ground_truth):
    """
    评估Agent在基准测试上的表现。
    """
    total = len(ground_truth)
    passed = 0
    partial = 0.0
    # TODO: 计算 pass_rate 和 partial_score
    for pred, gt in zip(agent_outputs, ground_truth):
        if pred == gt:
            passed += 1
            partial += 1.0
        elif gt in pred or pred in gt:
            partial += 0.5
    return {
        "pass_rate": round(passed / total, 3) if total else 0,
        "partial_score": round(partial / total, 3) if total else 0,
        "total": total,
        "passed": passed
    }`
      },
      {
        id: "6-2",
        title: "CRAG Benchmark RAG 评估",
        starter: `def evaluate_rag_system(retrieved_docs, relevant_docs, answers, ground_truth):
    """
    评估RAG系统的检索和生成质量。
    """
    n = len(ground_truth)
    # Recall: 每个查询检索到的相关文档占比
    recalls = []
    for ret, rel in zip(retrieved_docs, relevant_docs):
        if rel:
            hits = len(set(ret) & rel)
            recalls.append(hits / len(rel))
        else:
            recalls.append(1.0)
    avg_recall = sum(recalls) / n if n else 0
    # Accuracy: 答案正确率
    correct = sum(1 for a, g in zip(answers, ground_truth) if a.strip() == g.strip())
    return {
        "recall": round(avg_recall, 3),
        "accuracy": round(correct / n, 3) if n else 0
    }`
      },
      {
        id: "6-3",
        title: "量化评估推理能力与工具使用",
        starter: `def multi_dimension_eval(results):
    """
    多维度评估智能体能力。
    """
    n = len(results)
    if n == 0:
        return {"avg_reasoning_depth": 0, "tool_accuracy": 0, "completion_rate": 0}
    # TODO: 计算三个维度
    avg_depth = sum(r.get("reasoning_steps", 0) for r in results) / n
    tool_ok = sum(r.get("tool_calls_correct", 0) for r in results)
    tool_total = max(sum(r.get("tool_calls_total", 0) for r in results), 1)
    tool_acc = tool_ok / tool_total
    done = sum(1 for r in results if r.get("task_done", False))
    return {
        "avg_reasoning_depth": round(avg_depth, 1),
        "tool_accuracy": round(tool_acc, 3),
        "completion_rate": round(done / n, 3)
    }`
      },
      {
        id: "6-4",
        title: "工具调用权限控制",
        starter: `def check_tool_permission(tool_name, user_role, permission_policy):
    """
    检查用户是否有权限调用指定工具。
    """
    # TODO: 查找策略，判断角色是否在允许列表中
    allowed_roles = permission_policy.get(tool_name, [])
    if user_role in allowed_roles:
        return {"allowed": True, "reason": "权限通过"}
    return {"allowed": False, "reason": f"角色{user_role}无权调用{tool_name}"}`
      },
      {
        id: "6-5",
        title: "幻觉抑制 — 检索增强与约束解码",
        starter: `def reduce_hallucination(query, knowledge_base, response):
    """
    检测并标记回答中的疑似幻觉内容。
    """
    kb_words = set(knowledge_base.lower().split())
    resp_words = response.lower().split()
    suspicious = []
    # TODO: 找出response中不在knowledge_base中的长词（>3字符）
    for word in set(resp_words):
        if len(word) > 3 and word not in kb_words and word not in query.lower():
            suspicious.append(word)
    return {
        "clean": len(suspicious) == 0,
        "suspicious": suspicious[:5],
        "verified_response": response if len(suspicious) == 0 else response + " [引用已核查]"
    }`
      },
      {
        id: "6-6",
        title: "数据隐私脱敏",
        starter: `import re

def mask_sensitive_info(text):
    """
    对手机号、身份证、邮箱进行脱敏处理。
    """
    # TODO: 正则替换
    # 手机号: 1[3-9]\\d{9} → 前3位+****+后4位
    text = re.sub(r'(1[3-9]\\d)\\d{4}(\\d{4})', r'\\1****\\2', text)
    # 身份证: \\d{17}[\\dXx] → 前1位+16星+末位
    text = re.sub(r'(\\d)\\d{16}(\\d[\\dXx])', r'\\1****************\\2', text)
    # 邮箱: 用户名部分只保留首字母
    text = re.sub(r'(\\w)[\\w.]*(@\\w+\\.\\w+)', r'\\1***\\2', text)
    return text`
      },
      {
        id: "6-7",
        title: "算法偏见检测与缓解",
        starter: `def detect_bias(predictions, threshold=0.15):
    """
    检测模型输出中的群体偏差。
    predictions: [{"score": 0.8, "group": "A"}, ...]
    """
    # TODO: 分组统计平均分，检查组间差异
    groups = {}
    for p in predictions:
        g = p["group"]
        if g not in groups:
            groups[g] = []
        groups[g].append(p["score"])
    avg_scores = {g: sum(s)/len(s) for g, s in groups.items()}
    scores_list = list(avg_scores.values())
    max_diff = max(scores_list) - min(scores_list) if scores_list else 0
    return {
        "has_bias": max_diff > threshold,
        "group_scores": avg_scores,
        "recommendation": "需要调整模型以消除偏差" if max_diff > threshold else "偏差在可接受范围"
    }`
      },
      {
        id: "6-8",
        title: "具身智能（Embodied AI）感知-操作循环",
        starter: `def embodied_agent_loop(environment, policy, max_steps=5):
    """
    具身智能体感知-规划-行动循环。
    """
    trajectory = []
    state = environment.get("initial_state", "start")
    for step in range(1, max_steps + 1):
        action = policy(state)
        trajectory.append({"step": step, "state": state, "action": action})
        # 执行动作，更新状态
        transitions = environment.get("transitions", {})
        state = transitions.get((state, action), state)
        if state == "goal":
            trajectory.append({"step": step + 1, "state": "goal", "action": "done"})
            break
    return trajectory`
      },
      {
        id: "6-9",
        title: "MCP 模型上下文协议模拟",
        starter: `class MCPServer:
    """MCP 协议服务端模拟"""
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, description, input_schema, handler):
        """注册工具: handler接收arguments字典返回结果"""
        # TODO
        pass

    def list_tools(self):
        """返回工具列表"""
        # TODO
        pass

    def call_tool(self, name, arguments):
        """调用指定工具"""
        # TODO
        pass`
      },
      {
        id: "6-10",
        title: "Skills 技能模块封装",
        starter: `class SkillRegistry:
    """技能注册中心"""
    def __init__(self):
        self.skills = {}

    def register_skill(self, name, description, keywords, handler):
        """注册技能及其关键词"""
        # TODO
        pass

    def find_skill(self, task_description):
        """关键词匹配最佳技能，返回skill_name或None"""
        # TODO
        pass

    def execute_skill(self, name, **kwargs):
        """执行已注册的技能"""
        # TODO
        pass`
      },
    ]
  },
]

// 模拟进度（后续对接后端API）：{ "moduleId": completedCount }
export const MOCK_PROGRESS = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 }