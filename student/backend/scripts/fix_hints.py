"""批量替换所有泛泛的提示为具体的代码引导"""
import re

PATH = 'D:/education/11/backend/services/code_lab_templates.py'
with open(PATH, encoding='utf-8') as f:
    content = f.read()

count = 0

def replace(old, new, label):
    global content, count
    if re.search(old, content, re.DOTALL):
        content = re.sub(old, new, content, flags=re.DOTALL)
        count += 1
        print(f'OK: {label}')
    else:
        print(f'MISS: {label}')

# 1. Param Tuner
replace(
    r'\(\"方向提示\", \"analyze_task: 用关键词判断任务类型（代码/创意/分析）\"\),\s*\n\s*\(\"关键代码\", \"if.*temperature.*\"\),\s*\n\s*\(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 analyze_task()",\n'
    '             "creative = any(w in text for w in [\'创意\',\'诗歌\',\'故事\'])\\ncode = any(w in text for w in [\'代码\',\'编程\',\'函数\'])\\nreturn {\'creative\': creative, \'code\': code, \'length\': len(text)}"),\n'
    '            ("🔑 第2步：实现 recommend()",\n'
    '             "analysis = self.analyze_task(text)\\nif analysis[\'code\']: return {\'temperature\': 0.2, \'max_tokens\': 2048, \'top_p\': 0.9}\\nelif analysis[\'creative\']: return {\'temperature\': 0.9, \'max_tokens\': 4096, \'top_p\': 0.95}\\nreturn {\'temperature\': 0.5, \'max_tokens\': 2048, \'top_p\': 0.9}"),\n'
    '            ("📖 第3步：实现 explain()",\n'
    '             "return f\'Temperature={params[\\\'temperature\\\']}, max_tokens={params[\\\'max_tokens\\\']}\'\\n运行后观察不同任务类型的参数推荐差异。")',
    'Param Tuner')

# 2. Template Builder
replace(
    r'\(\"方向提示\", \"用 re.sub.*替换模板变量\"\), \(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 compile() 和 render()",\n'
    '             "compile: self.template = template_str\\nrender: result = self.template\\nfor key, value in variables.items(): result = result.replace(\'{{\' + key + \'}}\', str(value))\\nreturn result"),\n'
    '            ("🔑 第2步：实现 batch_render()",\n'
    '             "return [self.render(vars) for vars in data_list]\\n一行列表推导式即可，对每组数据调用 render()。"),\n'
    '            ("📖 第3步：验证",\n'
    '             "运行代码，看看 {{role}} {{lang}} {{task}} 三个变量是如何被替换成实际值的。")',
    'Template Builder')

# 3. Pipeline Builder
replace(
    r'\(\"方向提示\", \"run: for step in steps: data = step.func\(data\)\"\), \(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 add_step() 和 run()",\n'
    '             "add_step: self.steps.append((name, func))\\nrun: for name, func in self.steps: data = func(data); log.append(f\'{name}: OK\')\\nreturn {\'result\': data, \'log\': log}"),\n'
    '            ("🔑 第2步：实现 run_safe()",\n'
    '             "在 run() 基础上加 try/except:\\nfor name, func in self.steps:\\n    try: data = func(data)\\n    except Exception as e: log.append(f\'{name}: ERROR - {e}\')\\nreturn {\'result\': data, \'log\': log}"),\n'
    '            ("📖 第3步：理解 Pipeline",\n'
    '             "Pipeline 的核心：前一步的输出是后一步的输入。观察 double->add10 的链式处理结果。")',
    'Pipeline Builder')

# 4. Similarity Calc
replace(
    r'\(\"方向提示\", \"jaccard: len\(intersection\)/len\(union\)\"\), \(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 tokenize()",\n'
    '             "import re\\nreturn set(re.findall(r\'\\\\w+\', text.lower()))\\n提取所有英文单词和数字，转为小写集合。"),\n'
    '            ("🔑 第2步：实现 jaccard_sim() 和 cosine_sim()",\n'
    '             "s1, s2 = self.tokenize(text1), self.tokenize(text2)\\nif not s1 and not s2: return 1.0\\njaccard = len(s1 & s2) / len(s1 | s2)\\ncosine = len(s1 & s2) / (len(s1)**0.5 * len(s2)**0.5) if s1 and s2 else 0.0"),\n'
    '            ("📖 第3步：实现 compare()",\n'
    '             "return {\'jaccard\': round(self.jaccard_sim(text1,text2), 3), \'cosine\': round(self.cosine_sim(text1,text2), 3)}\\n运行代码比较两段文本的相似度。")',
    'Similarity Calc')

# 5. Task Delegator
replace(
    r'\(\"方向提示\", \"delegate: 找到 skills 含 task_type 的 Worker\"\), \(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 register()",\n'
    '             "self.workers.append(worker)\\n把 Worker 实例添加到 workers 列表中。"),\n'
    '            ("🔑 第2步：实现 delegate()",\n'
    '             "for w in self.workers:\\n    if task_type in w.skills:\\n        return w.execute(task_data)\\nreturn f\'未找到能处理 {task_type} 的Worker\'"),\n'
    '            ("📖 第3步：实现 list_capabilities()",\n'
    '             "return {w.name: w.skills for w in self.workers}\\n运行后观察 Coder 和 Designer 的分工。")',
    'Task Delegator')

# 6. Prompt Scorer
replace(
    r'\(\"方向提示\", \"score_clarity: len\(prompt\)>20.*?\"\),\s*\n\s*\(\"关键代码\", \"用 if.*?检测结构化程度\"\),\s*\n\s*\(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 score_clarity()",\n'
    '             "score = min(5, len(prompt) // 10)\\nkeywords = [\'解释\',\'分析\',\'描述\',\'列出\',\'比较\',\'实现\']\\nscore += sum(1 for k in keywords if k in prompt)\\nreturn min(10, score)"),\n'
    '            ("🔑 第2步：实现 score_structure()",\n'
    '             "score = 0\\nif any(c in prompt for c in [\'1.\',\'2.\',\'步骤\',\'首先\']): score += 4\\nif any(c in prompt for c in [\'markdown\',\'json\',\'表格\']): score += 3\\nif len(prompt.split(\'。\')) >= 2: score += 3\\nreturn min(10, score)"),\n'
    '            ("📖 第3步：实现 score_completeness()",\n'
    '             "score = 0\\nif any(w in prompt for w in [\'你是\',\'作为\',\'充当\']): score += 4\\nif any(w in prompt for w in [\'请\',\'帮我\',\'完成\']): score += 3\\nif any(w in prompt for w in [\'输出\',\'格式\',\'返回\']): score += 3\\nreturn min(10, score)")',
    'Prompt Scorer')

# 7. Memory System
replace(
    r'\(\"方向提示\", \"三种记忆都用 OrderedDict 实现.*?\"\),\s*\n\s*\(\"关键代码\", \"forget_old: while len.*?\"\),\s*\n\s*\(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 remember()",\n'
    '             "store = {\'short_term\': self.short_term, \'long_term\': self.long_term, \'working\': self.working}\\nif category in store: store[category][key] = value\\nif category == \'short_term\': self.forget_old()"),\n'
    '            ("🔑 第2步：实现 recall() 和 recall_recent()",\n'
    '             "recall: return self.short_term.get(key) if category==\'short_term\' else self.long_term.get(key) if category==\'long_term\' else self.working.get(key)\\nrecall_recent: return list(self.short_term.values())[-n:]"),\n'
    '            ("📖 第3步：实现 forget_old()",\n'
    '             "while len(self.short_term) > self.max_short: self.short_term.popitem(last=False)\\npopitem(last=False) 删除最早插入的项（FIFO淘汰）。")',
    'Memory System')

# 8. Decision Tree
replace(
    r'\(\"方向提示\", \"add_rule: 将\(condition, action\)元组存入 rules 列表\"\),\s*\n\s*\(\"关键代码\", \"decide: for cond, action in self.rules: if cond\(context\): return action\"\),\s*\n\s*\(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 add_rule()",\n'
    '             "self.rules.append((condition, action))\\n将条件函数和行动字符串组成的元组存入 rules 列表。"),\n'
    '            ("🔑 第2步：实现 decide()",\n'
    '             "for condition, action in self.rules:\\n    try:\\n        if condition(context): return action\\n    except: continue\\nreturn self.default_action"),\n'
    '            ("📖 第3步：理解决策链",\n'
    '             "规则按添加顺序依次判断，第一个匹配的规则返回其结果。无匹配时返回 default_action。")',
    'Decision Tree')

# 9. Voting System
replace(
    r'\(\"方向提示\", \"simple_majority: 用字典统计每个答案的出现次数\"\),\s*\n\s*\(\"关键代码\", \"weighted_vote: 累加每个投票者的 weight.*?\"\),\s*\n\s*\(\"完整答案\", \"查看 answer_code\"\)',
    '("💡 第1步：实现 simple_majority()",\n'
    '             "tally = {}\\nfor v in self.voters:\\n    ans, _ = v.vote(question)\\n    tally[ans] = tally.get(ans, 0) + 1\\nreturn max(tally, key=tally.get)"),\n'
    '            ("🔑 第2步：实现 weighted_vote()",\n'
    '             "scores = {}\\nfor v in self.voters:\\n    ans, weight = v.vote(question)\\n    scores[ans] = scores.get(ans, 0) + weight\\nreturn max(scores, key=scores.get)"),\n'
    '            ("📖 第3步：对比两种投票方式",\n'
    '             "简单多数：每人一票，票多者胜。加权投票：按权重累加，Expert(weight=3)的一票等于3票。")',
    'Voting System')

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nTotal fixed: {count}')
