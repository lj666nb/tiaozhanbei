"""重写所有编程模板的提示为具体的代码引导"""
import re

PATH = 'services/code_lab_templates.py'
with open(PATH, encoding='utf-8') as f:
    content = f.read()

hints_map = {
    '_template_ooda_agent': [
        ('💡 第1步：实现 observe()',
         '1. self.observations.append(msg)\\n'
         '2. 用 any(k in msg for k in ["警报","紧急","故障"]) 判断是否为紧急消息\\n'
         '3. 根据判断结果设置 self.state = "紧急" / "正常" / "未知"\\n'
         '4. return f"Agent {self.name} 观察到: {msg}"'),
        ('🔑 第2步：实现 decide()',
         'if self.state == "紧急": return "立即响应"\\n'
         'elif self.state == "正常": return "按计划执行"\\n'
         'else: return "请求更多信息"'),
        ('📖 第3步：检查 run() 方法',
         'run() 已经串联好 observe -> orient -> decide -> act，无需修改。\\n'
         'act() 中需要 print(f"[{self.name}] 执行行动: {decision}") 并 return decision。'),
    ],
    '_template_llm_request': [
        ('💡 第1步：完成 __init__()',
         'self.role = role\\nself.task = task\\nself.temperature = temperature'),
        ('🔑 第2步：实现 build 系列方法',
         'build_system_prompt: return f"你是一位专业的{self.role}，擅长{self.task}"\\n'
         'build_user_prompt: return f"背景信息：{context}\\n\\n问题：{question}"\\n'
         'build_messages: return [{"role":"system","content":self.build_system_prompt()},\\n'
         '                       {"role":"user","content":self.build_user_prompt(context,question)}]'),
        ('📖 第3步：实现 describe()',
         'return f"角色:{self.role} 任务:{self.task} 温度:{self.temperature}"\\n运行代码验证 LLM API 请求的完整结构。'),
    ],
    '_template_cot_engine': [
        ('💡 第1步：实现 zero_shot_cot()',
         'return f"{question}\\n\\n让我们逐步分析这个问题：\\n第一步："'),
        ('🔑 第2步：实现 few_shot_cot()',
         'prefix = "以下是一些问答示例：\\n"\\n'
         'for ex in examples: prefix += f"- 示例：{ex}\\n"\\n'
         'return prefix + f"\\n现在请回答：{question}\\n请仿照示例逐步推理"'),
        ('📖 第3步：实现 compare()',
         'return {"zero_shot": self.zero_shot_cot(question),\\n'
         '        "few_shot": self.few_shot_cot(question, []),\\n'
         '        "structured": self.structured_prompt(question, "markdown")}\\n'
         '运行后观察三种策略生成的不同 prompt。'),
    ],
    '_template_tool_agent': [
        ('💡 第1步：实现 register_tool() 和 list_tools()',
         'register_tool: self.tools[tool.name] = tool\\n'
         'list_tools: return [(t.name, t.description) for t in self.tools.values()]'),
        ('🔑 第2步：实现 _match_tool()',
         'for tool in self.tools.values():\\n'
         '    keywords = tool.description.split() + [tool.name]\\n'
         '    for kw in keywords:\\n'
         '        if len(kw) >= 2 and kw in user_input: return tool\\n'
         'return None'),
        ('📖 第3步：实现 execute()',
         'self.history.append(user_input)\\n'
         'tool = self._match_tool(user_input)\\n'
         'if tool: return f"[{tool.name}] " + tool.func(user_input)\\n'
         'return "抱歉，没有找到可以处理该请求的工具"'),
    ],
    '_template_rag_system': [
        ('💡 第1步：实现 add_document() 和 chunk_text()',
         'add_document:\\n'
         '  self.documents.append(text)\\n'
         '  chunks = self.chunk_text(text)\\n'
         '  self.chunks.extend(chunks)\\n'
         'chunk_text:\\n'
         '  text = text.replace("\\n", "。")\\n'
         '  sentences = text.split("。")\\n'
         '  return [s.strip() for s in sentences if s.strip()]'),
        ('🔑 第2步：实现 search()',
         'scored = []\\n'
         'for chunk in self.chunks:\\n'
         '    count = chunk.lower().count(query.lower())\\n'
         '    if count > 0: scored.append((count, chunk))\\n'
         'scored.sort(key=lambda x: -x[0])\\n'
         'return [chunk for _, chunk in scored[:top_k]]'),
        ('📖 第3步：实现 ask()',
         'results = self.search(query)\\n'
         'if results: return f"根据知识库中的{len(results)}条相关信息：{";".join(results)}"\\n'
         'return f"未在知识库中找到与{query}相关的信息"'),
    ],
    '_template_multi_agent': [
        ('💡 第1步：实现 MessageBus',
         'register: self.agents[name] = agent\\n'
         'send:\\n'
         '  self.log.append(f"{from_name} -> {to_name}: {msg[:50]}")\\n'
         '  if to_name in self.agents: self.agents[to_name].receive(from_name, msg)'),
        ('🔑 第2步：实现 Agent.receive()',
         'self.inbox.append(f"[来自{from_name}] {msg}")\\n'
         'if msg.startswith("CODE:"):\\n'
         '    code = msg[5:].strip()\\n'
         '    review = "审查通过" if len(code) > 10 else "建议改进: 代码太短"\\n'
         '    self.bus.send(self.name, from_name, review)'),
        ('📖 第3步：验证协作流程',
         '运行代码观察：Coder 发送 CODE 消息 -> Reviewer 收到并审查 -> Reviewer 回复 -> Coder 收到回复。'),
    ],
    '_template_state_agent': [
        ('💡 第1步：实现 add_state() 和 set_state()',
         'add_state: self.states[name] = transitions\\n'
         'set_state: self.current_state = name'),
        ('🔑 第2步：实现 handle()',
         'rules = self.states.get(self.current_state, {})\\n'
         'if event in rules:\\n'
         '    action, next_state = rules[event]\\n'
         '    self.current_state = next_state\\n'
         '    return action\\n'
         'return f"无法处理事件: {event}"'),
        ('📖 第3步：理解状态转移',
         '每个状态存储 {"event": ("action", "next_state")} 规则。\\n'
         'handle() 收到事件后查当前状态的规则，执行 action 并切换到 next_state。'),
    ],
    '_template_token_counter': [
        ('💡 第1步：实现 count_tokens()',
         'import re\\n'
         'chinese = len(re.findall(r"[\\u4e00-\\u9fff]", text))\\n'
         'english = len([w for w in re.findall(r"[a-zA-Z]+", text)])\\n'
         'return chinese + english'),
        ('🔑 第2步：实现 split_chunks()',
         'return [text[i:i+max_tokens] for i in range(0, len(text), max_tokens)]'),
        ('📖 第3步：实现 truncate()',
         'if strategy == "head": return text[:max_tokens]\\n'
         'return text[-max_tokens:]  # tail 模式取末尾'),
    ],
    '_template_prompt_scorer': [
        ('💡 第1步：实现 score_clarity()',
         'score = min(5, len(prompt) // 10)\\n'
         'keywords = ["解释","分析","描述","列出","比较","实现"]\\n'
         'score += sum(1 for k in keywords if k in prompt)\\n'
         'return min(10, score)'),
        ('🔑 第2步：实现 score_structure()',
         'score = 0\\n'
         'if any(c in prompt for c in ["1.","2.","步骤","首先"]): score += 4\\n'
         'if any(c in prompt for c in ["markdown","json","表格"]): score += 3\\n'
         'if len(prompt.split("。")) >= 2: score += 3\\n'
         'return min(10, score)'),
        ('📖 第3步：实现 score_completeness() 和 evaluate()',
         'score = 0\\n'
         'if any(w in prompt for w in ["你是","作为","充当"]): score += 4  # 角色\\n'
         'if any(w in prompt for w in ["请","帮我","完成"]): score += 3  # 任务\\n'
         'if any(w in prompt for w in ["输出","格式","返回"]): score += 3  # 格式\\n'
         'evaluate: return {"clarity":c,"structure":s,"completeness":comp,"total":c+s+comp}'),
    ],
    '_template_memory_system': [
        ('💡 第1步：实现 remember()',
         'store = {"short_term": self.short_term, "long_term": self.long_term, "working": self.working}\\n'
         'if category in store: store[category][key] = value\\n'
         'if category == "short_term": self.forget_old()'),
        ('🔑 第2步：实现 recall() 和 recall_recent()',
         'recall:\\n'
         '  store = {"short_term":self.short_term, "long_term":self.long_term, "working":self.working}\\n'
         '  return store.get(category, {}).get(key)\\n'
         'recall_recent: return list(self.short_term.values())[-n:]'),
        ('📖 第3步：实现 forget_old()',
         'while len(self.short_term) > self.max_short:\\n'
         '    self.short_term.popitem(last=False)  # FIFO 淘汰最早项'),
    ],
    '_template_decision_tree': [
        ('💡 第1步：实现 add_rule()',
         'self.rules.append((condition, action))\\n将条件函数和行动字符串组成的元组存入 rules 列表。'),
        ('🔑 第2步：实现 decide()',
         'for condition, action in self.rules:\\n'
         '    try:\\n'
         '        if condition(context): return action\\n'
         '    except: continue\\n'
         'return self.default_action'),
        ('📖 第3步：理解决策链',
         '规则按添加顺序依次判断，第一个匹配的规则返回其结果。无匹配时返回 default_action。'),
    ],
    '_template_voting_system': [
        ('💡 第1步：实现 simple_majority()',
         'tally = {}\\n'
         'for v in self.voters:\\n'
         '    ans, _ = v.vote(question)\\n'
         '    tally[ans] = tally.get(ans, 0) + 1\\n'
         'return max(tally, key=tally.get)'),
        ('🔑 第2步：实现 weighted_vote()',
         'scores = {}\\n'
         'for v in self.voters:\\n'
         '    ans, weight = v.vote(question)\\n'
         '    scores[ans] = scores.get(ans, 0) + weight\\n'
         'return max(scores, key=scores.get)'),
        ('📖 第3步：对比两种投票',
         '简单多数：每人一票。加权：Expert(weight=3) 一票抵三票。\\n运行代码对比两种方式的结果。'),
    ],
    '_template_reflex_agent': [
        ('💡 第1步：实现 add_rule()',
         'self.rules[pattern] = response\\n把规则存为字典，pattern 是匹配关键词，response 是回复内容。'),
        ('🔑 第2步：实现 respond()',
         'for pattern, response in self.rules.items():\\n'
         '    if pattern in msg: return response\\n'
         'return "抱歉，我不理解您的请求"'),
        ('📖 第3步：实现 match_count()',
         'return sum(1 for p in self.rules if p in msg)\\n统计有多少条规则匹配。运行代码测试不同输入。'),
    ],
    '_template_param_tuner': [
        ('💡 第1步：实现 analyze_task()',
         'creative = any(w in text for w in ["创意","诗歌","故事"])\\n'
         'code = any(w in text for w in ["代码","编程","函数","算法"])\\n'
         'return {"creative": creative, "code": code, "length": len(text)}'),
        ('🔑 第2步：实现 recommend()',
         'analysis = self.analyze_task(text)\\n'
         'if analysis["code"]: return {"temperature":0.2, "max_tokens":2048, "top_p":0.9}\\n'
         'elif analysis["creative"]: return {"temperature":0.9, "max_tokens":4096, "top_p":0.95}\\n'
         'return {"temperature":0.5, "max_tokens":2048, "top_p":0.9}'),
        ('📖 第3步：实现 explain()',
         'return f"Temperature={params[\'temperature\']}, max_tokens={params[\'max_tokens\']}"'),
    ],
    '_template_template_builder': [
        ('💡 第1步：实现 compile() 和 render()',
         'compile: self.template = template_str\\n'
         'render:\\n'
         '  result = self.template\\n'
         '  for key, value in variables.items():\\n'
         '      result = result.replace("{{" + key + "}}", str(value))\\n'
         '  return result'),
        ('🔑 第2步：实现 batch_render()',
         'return [self.render(vars) for vars in data_list]\\n一行列表推导式即可。'),
        ('📖 第3步：验证',
         '运行代码，观察 {{role}} {{lang}} {{task}} 三个变量如何被替换为实际值。'),
    ],
    '_template_pipeline_builder': [
        ('💡 第1步：实现 add_step() 和 run()',
         'add_step: self.steps.append((name, func))\\n'
         'run:\\n'
         '  log = []\\n'
         '  for name, func in self.steps: data = func(data); log.append(f"{name}: OK")\\n'
         '  return {"result": data, "log": log}'),
        ('🔑 第2步：实现 run_safe()',
         '在 run() 基础上加 try/except:\\n'
         'try: data = func(data); log.append(f"{name}: OK")\\n'
         'except Exception as e: log.append(f"{name}: ERROR - {e}")'),
        ('📖 第3步：理解 Pipeline',
         'Pipeline 核心：前一步输出是后一步输入。观察 double->add10 的链式处理。'),
    ],
    '_template_similarity_calc': [
        ('💡 第1步：实现 tokenize()',
         'import re\\nreturn set(re.findall(r"\\\\w+", text.lower()))\\n提取所有英文单词和数字，转为小写集合。'),
        ('🔑 第2步：实现 jaccard_sim() 和 cosine_sim()',
         's1, s2 = self.tokenize(text1), self.tokenize(text2)\\n'
         'if not s1 and not s2: return 1.0\\n'
         'jaccard = len(s1 & s2) / len(s1 | s2)\\n'
         'cosine = len(s1 & s2) / (len(s1)**0.5 * len(s2)**0.5) if s1 and s2 else 0.0'),
        ('📖 第3步：实现 compare()',
         'return {"jaccard": round(self.jaccard_sim(t1,t2),3), "cosine": round(self.cosine_sim(t1,t2),3)}'),
    ],
    '_template_task_delegator': [
        ('💡 第1步：实现 register()',
         'self.workers.append(worker)\\n把 Worker 实例添加到 workers 列表。'),
        ('🔑 第2步：实现 delegate()',
         'for w in self.workers:\\n    if task_type in w.skills:\\n        return w.execute(task_data)\\n'
         'return f"未找到能处理 {task_type} 的Worker"'),
        ('📖 第3步：实现 list_capabilities()',
         'return {w.name: w.skills for w in self.workers}\\n运行后观察 Coder 和 Designer 的分工结果。'),
    ],
}

count = 0
for tname, new_hints in hints_map.items():
    # Find the template function and its hints array
    func_start = content.index(f'def {tname}(')
    # Find the hints array within this function (before the return)
    func_end = content.index('\n    }', content.index('return {', func_start))
    section = content[func_start:func_end]

    if '"hints"' not in section:
        print(f'SKIP {tname}: no hints found')
        continue

    # Build the replacement hints string
    hint_lines = ['        "hints": [']
    for i, (title, body) in enumerate(new_hints):
        hint_lines.append(f'            ("{title}",')
        hint_lines.append(f'             "{body}"),')
    hint_lines.append('        ],')

    new_hints_str = '\n'.join(hint_lines)

    # Find the old hints array and replace it
    old_pattern = r'"hints":\s*\[.*?\]\s*,?\s*\n'
    match = re.search(old_pattern, section, re.DOTALL)
    if match:
        old_hints = match.group(0)
        content = content.replace(old_hints, new_hints_str + '\n', 1)
        count += 1
        print(f'OK: {tname}')
    else:
        print(f'MISS: {tname}')

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nTotal fixed: {count}')
