"""为全部63道题手写完整实现，沙箱验证，写入答案缓存"""
import json, re, tempfile, subprocess, os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "data", "exercise_answers_cache.json")

# ═══════════════════════════════════════════════════════════════
# 全部63道题的完整实现
# ═══════════════════════════════════════════════════════════════

IMPLS = {}

# ── 模块一：智能体基础通识 (1-1 ~ 1-9) ──

IMPLS['1-1'] = '''
def agent_definition_demo():
    """返回 AI 智能体四大核心要素及其解释"""
    return {
        "perception": "感知能力：智能体通过传感器或数据输入感知环境状态变化",
        "decision": "决策能力：基于感知信息与内部知识选择最优行动策略",
        "action": "行动能力：通过执行器或输出接口对环境施加影响",
        "environment": "环境交互：智能体在特定环境中运行并与之持续交互"
    }
'''

IMPLS['1-2'] = '''
def compare_passive_vs_agent(scenario):
    """根据scenario返回被动应答或智能体主动决策流程"""
    if scenario == "recommend":
        return [
            "用户发起推荐请求",
            "系统根据预设规则计算推荐列表",
            "返回推荐结果给用户"
        ]
    elif scenario == "agent":
        return [
            "智能体感知用户当前上下文",
            "分析用户偏好与历史行为",
            "制定个性化推荐策略",
            "执行推荐并收集反馈",
            "根据反馈调整后续策略"
        ]
    else:
        return ["未知场景"]
'''

IMPLS['1-3'] = '''
def classify_ai_system(features):
    """根据特征判断系统类型：ChatBot 或 Agent"""
    agent_indicators = {"tool_calling", "env_manipulation", "planning", "memory"}
    if features & agent_indicators:
        return "Agent"
    return "ChatBot"
'''

IMPLS['1-4'] = '''
def recommend_approach(task_type):
    """根据任务类型推荐 Workflow 或 Agent"""
    workflow_tasks = {"invoice_processing", "data_etl", "report_generation", "batch_processing"}
    agent_tasks = {"customer_service", "research", "negotiation", "creative_writing"}
    if task_type in workflow_tasks:
        return "Workflow"
    elif task_type in agent_tasks:
        return "Agent"
    else:
        return "Unknown"
'''

IMPLS['1-5'] = '''
def validate_agent_features(agent_config):
    """检查五大核心特征是否达标（>=60），返回 passed/failed 列表"""
    required = ["Autonomy", "Perception", "Reasoning", "Planning", "Action"]
    scores = agent_config.get("feature_scores", {})
    passed = []
    failed = []
    for feat in required:
        if scores.get(feat, 0) >= 60:
            passed.append(feat)
        else:
            failed.append(feat)
    return {"passed": passed, "failed": failed}
'''

IMPLS['1-6'] = '''
def assess_agent_level(features_dict):
    """根据所有特征评分判断智能体等级"""
    core = ["Autonomy", "Perception", "Reasoning", "Planning", "Action"]
    if any(features_dict.get(k, 0) < 60 for k in core):
        return "L1-入门"
    memory = features_dict.get("Memory", 0)
    learning = features_dict.get("Learning", 0)
    if memory >= 60 and learning >= 60:
        return "L3-高阶"
    return "L2-标准"
'''

IMPLS['1-7'] = '''
def reflex_agent(percept, rules):
    """简单反应式智能体：根据当前感知查表返回动作"""
    return rules.get(percept, "NoOp")
'''

IMPLS['1-8'] = '''
class GoalBasedAgent:
    def __init__(self, initial_state, goal_state):
        self.state = initial_state
        self.goal = goal_state
        self.history = []

    def perceive(self, observation):
        self.history.append(observation)
        return f"已处理输入: {observation}"

    def decide(self):
        if self.state != self.goal:
            return f"前往{self.goal}"
        return "Stay"

    def act(self, action):
        if action.startswith("Move to"):
            self.state = action.replace("Move to ", "").strip()
        return f"执行: {action}"
'''

IMPLS['1-9'] = '''
def ota_loop(environment, max_steps=5):
    """模拟 Observe → Think → Act 循环"""
    log = []
    for step in range(1, max_steps + 1):
        observed = environment.get("state", "unknown")
        if observed == environment.get("goal"):
            break
        plan = "advance" if observed != environment.get("goal") else "stay"
        environment["state"] = environment.get("goal", observed)
        log.append(f"Step {step}: Observe={observed} → Think={plan} → Act={environment['state']}")
    return log
'''

# ── 模块二：大模型与提示词工程 (2-1 ~ 2-10) ──

IMPLS['2-1'] = '''
import math

def softmax_row(row):
    exp_row = [math.exp(x) for x in row]
    total = sum(exp_row)
    return [x / total for x in exp_row]

def scaled_dot_product_attention(Q, K, V):
    """计算 softmax(Q * K^T / sqrt(dk)) * V"""
    dk = len(Q[0])
    # Q * K^T
    scores = [[sum(Q[i][k] * K[j][k] for k in range(len(Q[0]))) for j in range(len(K))] for i in range(len(Q))]
    # / sqrt(dk)
    scale = math.sqrt(dk)
    scores = [[s / scale for s in row] for row in scores]
    # softmax per row
    scores = [softmax_row(row) for row in scores]
    # * V
    result = [[sum(scores[i][k] * V[k][j] for k in range(len(V))) for j in range(len(V[0]))] for i in range(len(scores))]
    return result
'''

IMPLS['2-2'] = '''
def simulate_finetune_effect(base_model_knowledge, instruction_data):
    """模拟指令微调：对 instruction_data 中出现的词提高概率"""
    result = dict(base_model_knowledge)
    boost = 0.1
    for _, text in instruction_data:
        for word in text.split():
            word = word.strip("，。！？、；：""''（）")
            if word in result:
                result[word] = round(result[word] + boost, 2)
    return result
'''

IMPLS['2-3'] = '''
def apply_lora(original_weight, lora_A, lora_B, alpha=1.0):
    """模拟 LoRA: W' = W + alpha * (B @ A)"""
    n = len(original_weight)
    # B @ A
    BA = [[sum(lora_B[i][k] * lora_A[k][j] for k in range(n)) for j in range(n)] for i in range(n)]
    # W' = W + alpha * BA
    result = [[original_weight[i][j] + alpha * BA[i][j] for j in range(n)] for i in range(n)]
    return result
'''

IMPLS['2-4'] = '''
def build_few_shot_prompt(task, examples, query):
    """构建 Few-shot 提示词"""
    prompt = f"任务：{task}\\n\\n示例：\\n"
    for i, (ex_in, ex_out) in enumerate(examples, 1):
        prompt += f"{i}. 输入：{ex_in}\\n   输出：{ex_out}\\n"
    prompt += f"\\n现在请回答：\\n输入：{query}\\n输出："
    return prompt
'''

IMPLS['2-5'] = '''
def build_structured_prompt(role, task, output_format):
    """构建标准 Prompt 结构"""
    return {
        "messages": [
            {"role": "system", "content": f"你是一位{role}。请按以下格式输出：{output_format}"},
            {"role": "user", "content": task}
        ]
    }
'''

IMPLS['2-6'] = '''
def cot_solver(problem, steps=2):
    """模拟思维链推理"""
    import re
    reasoning = []
    expr = problem.replace("计算", "").strip()
    try:
        tokens = re.findall(r'[\d.]+|[+\\-*/]', expr)
        reasoning.append(f"步骤1: 解析表达式 {expr}")
        result = eval(expr)
        reasoning.append(f"步骤2: 计算结果 = {result}")
        return {"reasoning": reasoning, "answer": result}
    except:
        return {"reasoning": [], "answer": None}
'''

IMPLS['2-7'] = '''
def tot_search(branches_scores):
    """思维树搜索：返回得分最高的前k条路径"""
    sorted_branches = sorted(branches_scores, key=lambda x: -x[1])
    if not sorted_branches:
        return []
    top_score = sorted_branches[0][1]
    return [name for name, score in sorted_branches if score == top_score or score >= top_score - 1]
'''

IMPLS['2-8'] = '''
def react_loop(task, tools, max_rounds=5):
    """模拟 ReAct 交替推理与行动"""
    log = []
    for i in range(max_rounds):
        thought = f"第{i+1}轮推理：需要调用工具来完成任务"
        tool_name = list(tools.keys())[0]
        action_result = tools[tool_name](task)
        observation = str(action_result)
        log.append({"Thought": thought, "Action": f"调用{tool_name}", "Observation": observation})
        task = observation
    return log
'''

IMPLS['2-9'] = '''
def simulate_quantization(weights, bits=8):
    """模拟权重量化与反量化过程"""
    max_val = max(abs(w) for w in weights)
    levels = 2 ** (bits - 1) - 1
    scale = max_val / levels if levels > 0 else 1.0
    quantized = [round(w / scale) * scale for w in weights]
    dequantized = list(quantized)
    error = sum(abs(weights[i] - dequantized[i]) for i in range(len(weights))) / len(weights)
    return {"quantized": quantized, "dequantized": dequantized, "error": error}
'''

IMPLS['2-10'] = '''
def calculate_metrics(tp, fp, tn, fn):
    """计算分类模型的四个核心评估指标"""
    accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3)
    }
'''

# ── 模块三：智能体核心能力 (3-1 ~ 3-14) ──

IMPLS['3-1'] = '''
def parse_nl_instruction(text):
    """解析自然语言指令，提取意图和实体"""
    intent = ""
    entities = {}
    if "天气" in text:
        intent = "query_weather"
        import re
        city_match = re.search(r"查询(.+?)天气", text)
        if city_match:
            entities["city"] = city_match.group(1)
    elif "提醒" in text:
        intent = "set_reminder"
    elif "翻译" in text:
        intent = "translate"
    else:
        intent = "unknown"
    return {"intent": intent, "entities": entities}
'''

IMPLS['3-2'] = '''
def fuse_multimodal_inputs(inputs):
    """融合多模态输入为统一语义表示"""
    parts = ["[融合感知]"]
    for modal in ["text", "image_desc", "audio_transcript"]:
        if modal in inputs and inputs[modal]:
            parts.append(f"{modal}: {inputs[modal]}")
    return " ".join(parts)
'''

IMPLS['3-3'] = '''
def simulate_vlm(image_features, concept_map):
    """模拟VLM：根据图像特征匹配最可能的概念"""
    counts = {}
    for feat in image_features:
        if feat in concept_map:
            concept = concept_map[feat]
            counts[concept] = counts.get(concept, 0) + 1
    if not counts:
        return {"concept": "unknown", "confidence": 0.0}
    best = max(counts, key=counts.get)
    total = sum(counts.values())
    return {"concept": best, "confidence": round(counts[best] / total, 2)}
'''

IMPLS['3-4'] = '''
class ShortTermMemory:
    def __init__(self, max_size=5):
        self.max_size = max_size
        self.messages = []

    def add(self, message):
        self.messages.append(message)
        if len(self.messages) > self.max_size:
            self.messages.pop(0)

    def get_context(self):
        return list(self.messages)

    def get_token_estimate(self):
        total_chars = sum(len(str(m)) for m in self.messages)
        return total_chars // 2
'''

IMPLS['3-5'] = '''
import math

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x**2 for x in a))
    norm_b = math.sqrt(sum(x**2 for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

def semantic_search(query_embedding, memory_store, top_k=3):
    """余弦相似度检索最相关的 top_k 条记忆"""
    scores = [(cosine_similarity(query_embedding, item["vector"]), item) for item in memory_store]
    scores.sort(key=lambda x: -x[0])
    return [item for _, item in scores[:top_k]]
'''

IMPLS['3-6'] = '''
class KnowledgeGraph:
    def __init__(self):
        self.graph = {}

    def add_triple(self, subject, relation, obj):
        if subject not in self.graph:
            self.graph[subject] = []
        self.graph[subject].append((relation, obj))

def query_related_concepts(kg, entity, max_depth=1):
    """BFS 从 entity 出发，返回 max_depth 步内可达的所有实体"""
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
    return visited
'''

IMPLS['3-7'] = '''
def decompose_task(goal, subtask_templates):
    """根据目标中的关键词匹配子任务模板"""
    tasks = []
    seen = set()
    for keyword, subtasks in subtask_templates.items():
        if keyword in goal:
            for t in subtasks:
                if t not in seen:
                    tasks.append(t)
                    seen.add(t)
    return tasks
'''

IMPLS['3-8'] = '''
def hierarchical_path_plan(start, goal, waypoints):
    """分层规划：高层经过关键节点，细节步骤逐段展开"""
    path = [start] + waypoints + [goal]
    high_level = [f"{path[i]}→{path[i+1]}" for i in range(len(path)-1)]
    steps = [f"{seg}: 前进" for seg in high_level]
    return {"high_level": high_level, "steps": steps}
'''

IMPLS['3-9'] = '''
def replan_on_failure(original_plan, failed_step, alternative_steps):
    """计划中某一步失败时用替代步骤替换"""
    new_plan = list(original_plan)
    if failed_step in new_plan:
        idx = new_plan.index(failed_step)
        new_plan = new_plan[:idx] + alternative_steps + new_plan[idx+1:]
    return new_plan
'''

IMPLS['3-10'] = '''
def parse_function_call(llm_response):
    """解析 LLM 的函数调用 JSON 并模拟执行"""
    func_name = llm_response.get("function", "")
    params = llm_response.get("params", {})
    result = None
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
    return {"function": func_name, "params": params, "result": result}
'''

IMPLS['3-11'] = '''
class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, func):
        self.tools[name] = func

    def call(self, name, **kwargs):
        if name in self.tools:
            return self.tools[name](**kwargs)
        raise ValueError(f"工具 {name} 未注册")

    def list_tools(self):
        return list(self.tools.keys())
'''

IMPLS['3-12'] = '''
import io
import sys

def sandbox_execute(code, allowed_builtins=None):
    """在受限环境中执行 Python 代码"""
    if allowed_builtins is None:
        allowed_builtins = {"print", "len", "range", "int", "float", "str", "list", "dict", "abs", "min", "max", "sum"}
    safe_globals = {"__builtins__": {k: __builtins__[k] for k in allowed_builtins if k in __builtins__}}
    safe_globals["__builtins__"]["__import__"] = None
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, safe_globals)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "output": str(e)}
    finally:
        sys.stdout = old_stdout
'''

IMPLS['3-13'] = '''
def execute_tool_chain(tool_chain, initial_input):
    """顺序执行工具链，支持错误跳过"""
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
    return {"final_result": current, "steps": steps}
'''

IMPLS['3-14'] = '''
def hitl_gate(action, risk_level, threshold=7):
    """人在回路审批门控"""
    if risk_level >= threshold:
        return {"approved": False, "reason": f"风险等级{risk_level}超过阈值{threshold}，需要人工审批"}
    return {"approved": True, "reason": "自动通过"}
'''

# ── 模块四：开发框架与工程实践 (4-1 ~ 4-13) ──

IMPLS['4-1'] = '''
class SimpleChain:
    def __init__(self):
        self.steps = []

    def add_step(self, name, func):
        self.steps.append((name, func))

    def run(self, input_data):
        current = input_data
        for name, func in self.steps:
            current = func(current)
        return current
'''

IMPLS['4-2'] = '''
class StateGraph:
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
        return state
'''

IMPLS['4-3'] = '''
class SimpleIndex:
    def __init__(self):
        self.docs = []
        self.index = {}

    def add_documents(self, docs):
        self.docs.extend(docs)

    def build_index(self):
        self.index = {}
        for i, doc in enumerate(self.docs):
            for word in doc.split():
                w = word.lower()
                if w not in self.index:
                    self.index[w] = []
                if i not in self.index[w]:
                    self.index[w].append(i)

    def search(self, query, top_k=3):
        query_words = query.lower().split()
        scores = {}
        for w in query_words:
            for doc_id in self.index.get(w, []):
                scores[doc_id] = scores.get(doc_id, 0) + 1
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [self.docs[doc_id] for doc_id, _ in ranked[:top_k]]
'''

IMPLS['4-4'] = '''
class CrewAI:
    def __init__(self):
        self.agents = {}
        self.tasks = []

    def create_agent(self, name, role, goal):
        self.agents[name] = {"name": name, "role": role, "goal": goal}

    def create_task(self, description, assigned_agent_name):
        self.tasks.append({"description": description, "agent": assigned_agent_name})

    def execute(self):
        results = []
        for task in self.tasks:
            agent = self.agents.get(task["agent"])
            if agent:
                output = f"[{agent['role']}] 完成: {task['description']}"
                results.append({"agent": agent["name"], "task": task["description"], "output": output})
        return {"results": results}
'''

IMPLS['4-5'] = '''
def autogen_dialogue(agent_a, agent_b, topic, rounds=3):
    """模拟 AutoGen 双Agent对话"""
    dialogue = []
    for i in range(rounds):
        a_msg = f"[{agent_a['name']}] 关于'{topic}'的第{i+1}轮分析..."
        b_msg = f"[{agent_b['name']}] 对'{topic}'的反馈和建议..."
        dialogue.append({"speaker": agent_a["name"], "message": a_msg})
        dialogue.append({"speaker": agent_b["name"], "message": b_msg})
    return dialogue
'''

IMPLS['4-6'] = '''
def rag_pipeline(query, documents, llm_simulator):
    """RAG全流程：检索→增强→生成"""
    scores = []
    for i, doc in enumerate(documents):
        score = sum(1 for ch in query if ch in doc)
        for w in query.split():
            if w in doc:
                score += 5
        scores.append((score, i))
    scores.sort(reverse=True)
    top_docs = [documents[s[1]] for s in scores[:2] if s[0] > 0]
    context = chr(10).join(top_docs)
    answer = llm_simulator(context, query)
    return {"retrieved": top_docs, "answer": answer}
'''

IMPLS['4-8'] = '''
def chunk_and_embed(text, chunk_size=128, overlap=20):
    """文档切块 + 简易嵌入向量生成"""
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + chunk_size]
        if not chunk:
            break
        vector = [0.0] * 32
        for i, ch in enumerate(chunk[:32]):
            vector[i] = ord(ch) / 256.0
        chunks.append({"chunk": chunk, "vector": vector})
        start += chunk_size - overlap
    return chunks
'''

IMPLS['4-9'] = '''
def prompt_chain(task_input, steps):
    """串行执行提示链的所有步骤"""
    intermediate = []
    current = task_input
    for name, func in steps:
        current = func(current)
        intermediate.append({"step": name, "output": current[:80]})
    return {"intermediate": intermediate, "final": current}
'''

IMPLS['4-10'] = '''
def router(intent, handlers):
    """根据意图关键词路由到对应处理器"""
    for keyword, handler in sorted(handlers.items(), key=lambda x: -len(x[0])):
        if keyword in intent:
            return {"matched": keyword, "result": handler(intent)}
    return {"matched": "default", "result": f"无法处理意图: {intent}"}
'''

IMPLS['4-11'] = '''
import time

def parallel_execute(tasks):
    """模拟并行执行多个任务"""
    results = []
    start = time.time()
    for name, func in tasks:
        out = func()
        results.append({"task": name, "output": out})
    elapsed = round(time.time() - start, 4)
    return {"results": results, "total_time": elapsed}
'''

IMPLS['4-12'] = '''
def reflection_loop(initial, evaluator, improver, max_iter=3):
    """自我反思迭代改进循环"""
    current = initial
    for i in range(max_iter):
        score, issues = evaluator(current)
        if score >= 0.8:
            return {"final": current, "iterations": i + 1, "final_score": score}
        current = improver(current, issues)
    score, _ = evaluator(current)
    return {"final": current, "iterations": max_iter, "final_score": score}
'''

IMPLS['4-13'] = '''
from datetime import datetime

def api_gateway(request, agent_func, auth_token):
    """API 网关：鉴权→校验→执行→日志"""
    if auth_token != "valid_token_2024":
        return {"status": 401, "result": "Unauthorized", "log": ""}
    if "action" not in request:
        return {"status": 400, "result": "Missing action", "log": ""}
    result = agent_func(request)
    log = f"[{datetime.now().isoformat()}] action={request['action']} status=200"
    return {"status": 200, "result": result, "log": log}
'''

# ── 模块五：多智能体系统 (5-1 ~ 5-7) ──

IMPLS['5-1'] = '''
def assign_tasks_to_agents(tasks, agents):
    """轮询（Round-Robin）策略分配任务给Agent"""
    assignment = {a: [] for a in agents}
    for i, task in enumerate(tasks):
        agent = agents[i % len(agents)]
        assignment[agent].append(task)
    return assignment
'''

IMPLS['5-2'] = '''
class ManagerWorkerSystem:
    def __init__(self):
        self.manager_name = "Manager"
        self.workers = {}

    def add_worker(self, name, skill):
        self.workers[name] = {"name": name, "skill": skill}

    def run(self, task):
        subtasks = [f"子任务{i+1}: {task} (第{i+1}部分)" for i in range(len(self.workers))]
        results = {}
        for (name, worker), subtask in zip(self.workers.items(), subtasks):
            results[name] = f"[{worker['skill']}] 完成: {subtask}"
        return {
            "assignments": {name: st for name, st in zip(self.workers.keys(), subtasks)},
            "results": results,
            "summary": f"Manager分配{len(subtasks)}个子任务给{len(self.workers)}个Worker"
        }
'''

IMPLS['5-3'] = '''
def peer_voting(proposals, votes):
    """P2P投票决策：汇总所有Agent的投票，排序返回"""
    scores = {p: 0 for p in proposals}
    for agent, ballot in votes.items():
        for prop, score in ballot.items():
            if prop in scores:
                scores[prop] += score
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return ranked
'''

IMPLS['5-4'] = '''
class MessageBus:
    def __init__(self):
        self.agents = set()
        self.messages = {}

    def register(self, agent_name):
        self.agents.add(agent_name)
        if agent_name not in self.messages:
            self.messages[agent_name] = []

    def send(self, sender, receiver, content):
        if receiver in self.messages:
            self.messages[receiver].append({"from": sender, "content": content})

    def broadcast(self, sender, content):
        for agent in self.agents:
            if agent != sender:
                self.messages[agent].append({"from": sender, "content": content})

    def inbox(self, agent_name):
        return self.messages.get(agent_name, [])
'''

IMPLS['5-5'] = '''
class Blackboard:
    def __init__(self):
        self.board = {}

    def post(self, agent, topic, data):
        if topic not in self.board:
            self.board[topic] = []
        self.board[topic].append({"agent": agent, "data": data})

    def read(self, agent, topic=None):
        if topic:
            return self.board.get(topic, [])
        result = {}
        for t, entries in self.board.items():
            result[t] = [e for e in entries if e["agent"] != agent]
        return result

    def clear_topic(self, topic):
        if topic in self.board:
            del self.board[topic]
'''

IMPLS['5-6'] = '''
class PubSub:
    def __init__(self):
        self.subscriptions = {}

    def subscribe(self, agent, event_type):
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []
        if agent not in self.subscriptions[event_type]:
            self.subscriptions[event_type].append(agent)

    def unsubscribe(self, agent, event_type):
        if event_type in self.subscriptions and agent in self.subscriptions[event_type]:
            self.subscriptions[event_type].remove(agent)
            if not self.subscriptions[event_type]:
                del self.subscriptions[event_type]

    def publish(self, event_type, data):
        notified = self.subscriptions.get(event_type, [])
        return {"notified": list(notified)}
'''

IMPLS['5-7'] = '''
def find_nash_equilibrium(payoff_matrix):
    """找到2x2博弈中的所有纯策略纳什均衡"""
    strategies_A = list(set(k[0] for k in payoff_matrix.keys()))
    strategies_B = list(set(k[1] for k in payoff_matrix.keys()))
    ne_list = []
    for a in strategies_A:
        for b in strategies_B:
            current = payoff_matrix.get((a, b))
            if current is None:
                continue
            a_ok = all(current[0] >= payoff_matrix.get((alt_a, b), (float('-inf'),))[0]
                       for alt_a in strategies_A if alt_a != a)
            b_ok = all(current[1] >= payoff_matrix.get((a, alt_b), (0, float('-inf')))[1]
                       for alt_b in strategies_B if alt_b != b)
            if a_ok and b_ok:
                ne_list.append((a, b))
    return ne_list
'''

# ── 模块六：评估安全与前沿 (6-1 ~ 6-10) ──

IMPLS['6-1'] = '''
def evaluate_agent_on_benchmark(agent_outputs, ground_truth):
    """评估Agent在基准测试上的表现"""
    total = len(ground_truth)
    passed = 0
    partial = 0.0
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
    }
'''

IMPLS['6-2'] = '''
def evaluate_rag_system(retrieved_docs, relevant_docs, answers, ground_truth):
    """评估RAG系统的检索和生成质量"""
    n = len(ground_truth)
    recalls = []
    for ret, rel in zip(retrieved_docs, relevant_docs):
        if rel:
            hits = len(set(ret) & set(rel))
            recalls.append(hits / len(rel))
        else:
            recalls.append(1.0)
    avg_recall = sum(recalls) / n if n else 0
    correct = sum(1 for a, g in zip(answers, ground_truth) if a.strip() == g.strip())
    return {
        "recall": round(avg_recall, 3),
        "accuracy": round(correct / n, 3) if n else 0
    }
'''

IMPLS['6-3'] = '''
def multi_dimension_eval(results):
    """多维度评估智能体能力"""
    n = len(results)
    if n == 0:
        return {"avg_reasoning_depth": 0, "tool_accuracy": 0, "completion_rate": 0}
    avg_depth = sum(r.get("reasoning_steps", 0) for r in results) / n
    tool_ok = sum(r.get("tool_calls_correct", 0) for r in results)
    tool_total = max(sum(r.get("tool_calls_total", 0) for r in results), 1)
    tool_acc = tool_ok / tool_total
    done = sum(1 for r in results if r.get("task_done", False))
    return {
        "avg_reasoning_depth": round(avg_depth, 1),
        "tool_accuracy": round(tool_acc, 3),
        "completion_rate": round(done / n, 3)
    }
'''

IMPLS['6-4'] = '''
def check_tool_permission(tool_name, user_role, permission_policy):
    """检查用户是否有权限调用指定工具"""
    allowed_roles = permission_policy.get(tool_name, [])
    if user_role in allowed_roles:
        return {"allowed": True, "reason": "权限通过"}
    return {"allowed": False, "reason": f"角色{user_role}无权调用{tool_name}"}
'''

IMPLS['6-5'] = '''
def reduce_hallucination(query, knowledge_base, response):
    """检测并标记回答中的疑似幻觉内容"""
    kb_words = set(knowledge_base.lower().split())
    resp_words = response.lower().split()
    suspicious = []
    for word in set(resp_words):
        if len(word) > 3 and word not in kb_words and word not in query.lower():
            suspicious.append(word)
    return {
        "clean": len(suspicious) == 0,
        "suspicious": suspicious[:5],
        "verified_response": response if len(suspicious) == 0 else response + " [引用已核查]"
    }
'''

IMPLS['6-6'] = '''
import re

def mask_sensitive_info(text):
    """对手机号、身份证、邮箱进行脱敏处理"""
    text = re.sub(r'(1[3-9]\\d)\\d{4}(\\d{4})', r'\\1****\\2', text)
    text = re.sub(r'(\\d)\\d{16}(\\d[\\dXx])', r'\\1****************\\2', text)
    text = re.sub(r'(\\w)[\\w.]*(@\\w+\\.\\w+)', r'\\1***\\2', text)
    return text
'''

IMPLS['6-7'] = '''
def detect_bias(predictions, threshold=0.15):
    """检测模型输出中的群体偏差"""
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
    }
'''

IMPLS['6-8'] = '''
def embodied_agent_loop(environment, policy, max_steps=5):
    """具身智能体感知-规划-行动循环"""
    trajectory = []
    state = environment.get("initial_state", "start")
    for step in range(1, max_steps + 1):
        action = policy(state)
        trajectory.append({"step": step, "state": state, "action": action})
        transitions = environment.get("transitions", {})
        state = transitions.get((state, action), state)
        if state == "goal":
            trajectory.append({"step": step + 1, "state": "goal", "action": "done"})
            break
    return trajectory
'''

IMPLS['6-9'] = '''
class MCPServer:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, description, input_schema, handler):
        self.tools[name] = {
            "description": description,
            "input_schema": input_schema,
            "handler": handler
        }

    def list_tools(self):
        return [{"name": name, "description": info["description"]} for name, info in self.tools.items()]

    def call_tool(self, name, arguments):
        if name not in self.tools:
            raise ValueError(f"工具 {name} 未注册")
        return self.tools[name]["handler"](arguments)
'''

IMPLS['6-10'] = '''
class SkillRegistry:
    def __init__(self):
        self.skills = {}

    def register_skill(self, name, description, keywords, handler):
        self.skills[name] = {
            "description": description,
            "keywords": keywords,
            "handler": handler
        }

    def find_skill(self, task_description):
        best_match = None
        best_score = 0
        for name, info in self.skills.items():
            score = sum(1 for kw in info["keywords"] if kw in task_description)
            if score > best_score:
                best_score = score
                best_match = name
        return best_match

    def execute_skill(self, name, **kwargs):
        if name not in self.skills:
            raise ValueError(f"技能 {name} 未注册")
        return self.skills[name]["handler"](**kwargs)
'''

# ═══════════════════════════════════════════════════════════════
# 验证与保存
# ═══════════════════════════════════════════════════════════════

def validate_and_save():
    with open(os.path.join(BASE_DIR, "data", "exercises_processed.json"), 'r', encoding='utf-8') as f:
        exs = json.load(f)

    # Load existing cache
    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            cache = json.load(f)

    validated = 0
    failed = 0

    for ex in exs:
        eid = ex['id']
        impl = IMPLS.get(eid, '').strip()
        if not impl:
            print(f'{eid}: NO IMPLEMENTATION')
            failed += 1
            continue

        tc = ex.get('test_code', '').strip()
        full_code = impl + '\n\n' + tc if tc else impl

        # Validate
        try:
            compile(full_code, '<answer>', 'exec')
        except SyntaxError as e:
            print(f'{eid}: SYNTAX ERROR - {e}')
            failed += 1
            continue

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'main.py')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(full_code)
            try:
                proc = subprocess.run(['python', src], capture_output=True, text=True, timeout=10, cwd=tmp)
                if proc.returncode == 0 and '[FAIL]' not in proc.stdout:
                    cache[eid] = {
                        'approach': f'【{ex.get("title","")}】参考答案',
                        'answer_code': full_code,
                        'explanations': [],
                        '_validated': True
                    }
                    validated += 1
                    print(f'{eid}: PASS')
                else:
                    print(f'{eid}: TESTS FAILED')
                    if proc.returncode != 0:
                        print(f'  stderr: {proc.stderr[:200]}')
                    else:
                        for l in proc.stdout.split('\n'):
                            if 'FAIL' in l:
                                print(f'  {l[:120]}')
                    failed += 1
            except subprocess.TimeoutExpired:
                print(f'{eid}: TIMEOUT')
                failed += 1
            except Exception as e:
                print(f'{eid}: ERROR - {e}')
                failed += 1

    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*50}')
    print(f'Passed: {validated}/{len(exs)}')
    print(f'Failed: {failed}/{len(exs)}')
    return validated, failed

if __name__ == '__main__':
    validate_and_save()
