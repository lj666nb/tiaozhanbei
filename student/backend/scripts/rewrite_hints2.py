"""用精确文本匹配替换所有提示数组"""
import re

PATH = 'services/code_lab_templates.py'
with open(PATH, encoding='utf-8') as f:
    content = f.read()

# Map of template name -> (old hints text fragment, new hints array string)
# Use a unique fragment that identifies the old hints
replacements = []

# Helper: find hints array by searching for start marker, then find end marker (]),
# then replace the whole thing

def replace_hints(tname, new_hints_list):
    """Replace the hints array in template function tname with new content"""
    global content
    # Find function start
    pattern = rf'def {tname}\('
    match = re.search(pattern, content)
    if not match:
        print(f'MISS: {tname} (function not found)')
        return
    pos = match.start()
    # Find hints array within next 300 lines
    section = content[pos:pos+5000]
    hints_match = re.search(r'"hints":\s*\[(.*?)\]\s*,?\s*\n\s*\}', section, re.DOTALL)
    if not hints_match:
        print(f'MISS: {tname} (hints not found)')
        return
    old = hints_match.group(0)
    # Build new hints
    lines = ['"hints": [']
    for title, body in new_hints_list:
        lines.append(f'            ("{title}",')
        lines.append(f'             "{body}"),')
    lines.append('        ],\n    }')
    new = '\n'.join(lines)
    content = content.replace(old, new, 1)
    print(f'OK: {tname}')

# Now define new hints for all 18 templates
replace_hints('_template_ooda_agent', [
    ('💡 第1步：实现 observe()',
     '1. self.observations.append(msg)\\n2. 用 any(k in msg for k in ["警报","紧急","故障"]) 判断消息类型\\n3. 根据结果设置 self.state = "紧急" / "正常" / "未知"\\n4. return f"Agent {self.name} 观察到: {msg}"'),
    ('🔑 第2步：实现 decide()',
     'if self.state == "紧急": return "立即响应"\\nelif self.state == "正常": return "按计划执行"\\nelse: return "请求更多信息"'),
    ('📖 第3步：检查 run() 方法',
     'run() 已串联好 observe->orient->decide->act，无需修改。\\nact() 中需 print 日志并 return decision。\\n运行后观察紧急和正常消息的不同输出。'),
])

replace_hints('_template_llm_request', [
    ('💡 第1步：完成 __init__()',
     'self.role = role\\nself.task = task\\nself.temperature = temperature'),
    ('🔑 第2步：实现 build 系列方法',
     'build_system_prompt: f"你是一位专业的{self.role}，擅长{self.task}"\\nbuild_user_prompt: f"背景信息：{context}\\n\\n问题：{question}"\\nbuild_messages: return [{"role":"system","content":self.build_system_prompt()}, {"role":"user","content":self.build_user_prompt(context,question)}]'),
    ('📖 第3步：实现 describe()',
     'return f"角色:{self.role} 任务:{self.task} 温度:{self.temperature}"\\n运行代码验证 LLM API 请求结构。'),
])

replace_hints('_template_cot_engine', [
    ('💡 第1步：实现 zero_shot_cot()',
     'return f"{question}\\n\\n让我们逐步分析这个问题：\\n第一步："'),
    ('🔑 第2步：实现 few_shot_cot()',
     'prefix = "以下是一些问答示例：\\n"\\nfor ex in examples: prefix += f"- 示例：{ex}\\n"\\nreturn prefix + f"\\n现在请回答：{question}\\n请仿照示例逐步推理"'),
    ('📖 第3步：实现 compare()',
     'return {"zero_shot":self.zero_shot_cot(q),"few_shot":self.few_shot_cot(q,[]),"structured":self.structured_prompt(q,"markdown")}\\n运行观察三种策略的不同 prompt。'),
])

replace_hints('_template_tool_agent', [
    ('💡 第1步：实现 register_tool() 和 list_tools()',
     'register_tool: self.tools[tool.name] = tool\\nlist_tools: return [(t.name, t.description) for t in self.tools.values()]'),
    ('🔑 第2步：实现 _match_tool()',
     'for tool in self.tools.values():\\n    keywords = tool.description.split() + [tool.name]\\n    for kw in keywords:\\n        if len(kw) >= 2 and kw in user_input: return tool\\nreturn None'),
    ('📖 第3步：实现 execute()',
     'self.history.append(user_input)\\ntool = self._match_tool(user_input)\\nif tool: return f"[{tool.name}] " + tool.func(user_input)\\nreturn "抱歉，没有找到可以处理该请求的工具"'),
])

replace_hints('_template_rag_system', [
    ('💡 第1步：实现 add_document() 和 chunk_text()',
     'add_document: self.documents.append(text); chunks = self.chunk_text(text); self.chunks.extend(chunks)\\nchunk_text: text=text.replace("\\n","。"); sentences=text.split("。"); return [s.strip() for s in sentences if s.strip()]'),
    ('🔑 第2步：实现 search()',
     'scored=[]\\nfor chunk in self.chunks:\\n    count=chunk.lower().count(query.lower())\\n    if count>0: scored.append((count,chunk))\\nscored.sort(key=lambda x:-x[0])\\nreturn [chunk for _,chunk in scored[:top_k]]'),
    ('📖 第3步：实现 ask()',
     'results=self.search(query)\\nif results: return f"根据知识库中的{len(results)}条相关信息：{";".join(results)}"\\nreturn f"未在知识库中找到与{query}相关的信息"'),
])

replace_hints('_template_multi_agent', [
    ('💡 第1步：实现 MessageBus',
     'register: self.agents[name]=agent\\nsend: self.log.append(f"{from_name} -> {to_name}: {msg[:50]}"); if to_name in self.agents: self.agents[to_name].receive(from_name,msg)'),
    ('🔑 第2步：实现 Agent.receive()',
     'self.inbox.append(f"[来自{from_name}] {msg}")\\nif msg.startswith("CODE:"):\\n    code=msg[5:].strip()\\n    review="审查通过" if len(code)>10 else "建议改进: 代码太短"\\n    self.bus.send(self.name,from_name,review)'),
    ('📖 第3步：验证协作',
     '运行代码观察：Coder 发送 CODE -> Reviewer 审查 -> 回复 -> Coder 收到回复。'),
])

replace_hints('_template_state_agent', [
    ('💡 第1步：实现 add_state() 和 set_state()',
     'add_state: self.states[name]=transitions\\nset_state: self.current_state=name'),
    ('🔑 第2步：实现 handle()',
     'rules=self.states.get(self.current_state,{})\\nif event in rules:\\n    action,next_state=rules[event]\\n    self.current_state=next_state\\n    return action\\nreturn f"无法处理事件: {event}"'),
    ('📖 第3步：理解状态转移',
     '每个状态存 {"event":("action","next_state")} 规则。handle() 查当前状态规则，执行 action 并切换状态。'),
])

replace_hints('_template_token_counter', [
    ('💡 第1步：实现 count_tokens()',
     'import re\\nchinese=len(re.findall(r"[\\u4e00-\\u9fff]",text))\\nenglish=len([w for w in re.findall(r"[a-zA-Z]+",text)])\\nreturn chinese+english'),
    ('🔑 第2步：实现 split_chunks()',
     'return [text[i:i+max_tokens] for i in range(0,len(text),max_tokens)]'),
    ('📖 第3步：实现 truncate()',
     'if strategy=="head": return text[:max_tokens]\\nreturn text[-max_tokens:]  # tail 取末尾'),
])

replace_hints('_template_prompt_scorer', [
    ('💡 第1步：实现 score_clarity()',
     'score=min(5,len(prompt)//10)\\nkeywords=["解释","分析","描述","列出","比较","实现"]\\nscore+=sum(1 for k in keywords if k in prompt)\\nreturn min(10,score)'),
    ('🔑 第2步：实现 score_structure()',
     'score=0\\nif any(c in prompt for c in ["1.","2.","步骤","首先"]): score+=4\\nif any(c in prompt for c in ["markdown","json","表格"]): score+=3\\nif len(prompt.split("。"))>=2: score+=3\\nreturn min(10,score)'),
    ('📖 第3步：实现 score_completeness()',
     'score=0\\nif any(w in prompt for w in ["你是","作为","充当"]): score+=4\\nif any(w in prompt for w in ["请","帮我","完成"]): score+=3\\nif any(w in prompt for w in ["输出","格式","返回"]): score+=3\\nreturn min(10,score)'),
])

replace_hints('_template_memory_system', [
    ('💡 第1步：实现 remember()',
     'store={"short_term":self.short_term,"long_term":self.long_term,"working":self.working}\\nif category in store: store[category][key]=value\\nif category=="short_term": self.forget_old()'),
    ('🔑 第2步：实现 recall()',
     'store={"short_term":self.short_term,"long_term":self.long_term,"working":self.working}\\nreturn store.get(category,{}).get(key)'),
    ('📖 第3步：实现 forget_old()',
     'while len(self.short_term)>self.max_short: self.short_term.popitem(last=False)  # FIFO淘汰'),
])

replace_hints('_template_decision_tree', [
    ('💡 第1步：实现 add_rule()',
     'self.rules.append((condition,action))\\n条件函数+行动字符串 组成元组存入 rules 列表。'),
    ('🔑 第2步：实现 decide()',
     'for condition,action in self.rules:\\n    try:\\n        if condition(context): return action\\n    except: continue\\nreturn self.default_action'),
    ('📖 第3步：理解决策链',
     '规则按添加顺序判断，首个匹配返回其结果。无匹配时返回 default_action。'),
])

replace_hints('_template_voting_system', [
    ('💡 第1步：实现 simple_majority()',
     'tally={}\\nfor v in self.voters: ans,_=v.vote(question); tally[ans]=tally.get(ans,0)+1\\nreturn max(tally,key=tally.get)'),
    ('🔑 第2步：实现 weighted_vote()',
     'scores={}\\nfor v in self.voters: ans,w=v.vote(question); scores[ans]=scores.get(ans,0)+w\\nreturn max(scores,key=scores.get)'),
    ('📖 第3步：对比两种投票',
     '简单多数：每人一票。加权：Expert(weight=3) 一票抵三票。运行代码对比两种结果。'),
])

replace_hints('_template_reflex_agent', [
    ('💡 第1步：实现 add_rule()',
     'self.rules[pattern]=response\\n把规则存为字典，pattern 是匹配关键词，response 是回复。'),
    ('🔑 第2步：实现 respond()',
     'for pattern,response in self.rules.items():\\n    if pattern in msg: return response\\nreturn "抱歉，我不理解您的请求"'),
    ('📖 第3步：实现 match_count()',
     'return sum(1 for p in self.rules if p in msg)\\n统计匹配的规则数。'),
])

replace_hints('_template_param_tuner', [
    ('💡 第1步：实现 analyze_task()',
     'creative=any(w in text for w in ["创意","诗歌","故事"])\\ncode=any(w in text for w in ["代码","编程","函数","算法"])\\nreturn {"creative":creative,"code":code,"length":len(text)}'),
    ('🔑 第2步：实现 recommend()',
     'a=self.analyze_task(text)\\nif a["code"]: return {"temperature":0.2,"max_tokens":2048,"top_p":0.9}\\nelif a["creative"]: return {"temperature":0.9,"max_tokens":4096,"top_p":0.95}\\nreturn {"temperature":0.5,"max_tokens":2048,"top_p":0.9}'),
    ('📖 第3步：实现 explain()',
     'return f"Temperature={params[\'temperature\']}, max_tokens={params[\'max_tokens\']}"'),
])

replace_hints('_template_template_builder', [
    ('💡 第1步：实现 compile() 和 render()',
     'compile: self.template=template_str\\nrender: result=self.template; for k,v in variables.items(): result=result.replace("{{"+k+"}}",str(v)); return result'),
    ('🔑 第2步：实现 batch_render()',
     'return [self.render(vars) for vars in data_list]'),
    ('📖 第3步：验证',
     '运行代码，观察 {{role}} {{lang}} {{task}} 三个变量被替换为实际值。'),
])

replace_hints('_template_pipeline_builder', [
    ('💡 第1步：实现 add_step() 和 run()',
     'add_step: self.steps.append((name,func))\\nrun: for name,func in self.steps: data=func(data); log.append(f"{name}: OK")\\nreturn {"result":data,"log":log}'),
    ('🔑 第2步：实现 run_safe()',
     '在 run() 中加 try/except:\\ntry: data=func(data); log.append(f"{name}: OK")\\nexcept Exception as e: log.append(f"{name}: ERROR - {e}")'),
    ('📖 第3步：理解 Pipeline',
     'Pipeline 核心：前一步输出是后一步输入。观察 double->add10 的链式处理。'),
])

replace_hints('_template_similarity_calc', [
    ('💡 第1步：实现 tokenize()',
     'import re\\nreturn set(re.findall(r"\\\\w+",text.lower()))\\n提取英文单词和数字，转为小写集合。'),
    ('🔑 第2步：实现 jaccard_sim() 和 cosine_sim()',
     's1,s2=self.tokenize(t1),self.tokenize(t2)\\nif not s1 and not s2: return 1.0\\njaccard=len(s1&s2)/len(s1|s2)\\ncosine=len(s1&s2)/(len(s1)**0.5*len(s2)**0.5) if s1 and s2 else 0.0'),
    ('📖 第3步：实现 compare()',
     'return {"jaccard":round(self.jaccard_sim(t1,t2),3),"cosine":round(self.cosine_sim(t1,t2),3)}'),
])

replace_hints('_template_task_delegator', [
    ('💡 第1步：实现 register()',
     'self.workers.append(worker)'),
    ('🔑 第2步：实现 delegate()',
     'for w in self.workers:\\n    if task_type in w.skills: return w.execute(task_data)\\nreturn f"未找到能处理 {task_type} 的Worker"'),
    ('📖 第3步：实现 list_capabilities()',
     'return {w.name:w.skills for w in self.workers}'),
])

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
