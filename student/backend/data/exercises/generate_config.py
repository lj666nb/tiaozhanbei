import re, glob, json

lines = []
lines.append('// AI智能体编程习题配置（63关，6大模块）')
lines.append('// 新增关卡只需在此文件中添加即可')
lines.append('')
lines.append('export const MODULES = [')

module_names = [
    ('模块一：智能体基础通识', '🤖', '掌握AI智能体的核心定义、分类、核心特征与运行闭环', 9),
    ('模块二：大模型（LLM）与提示词工程', '🧠', '理解Transformer架构、微调技术、提示词工程核心方法', 10),
    ('模块三：智能体四大核心能力模块', '⚙️', '深入感知、记忆、规划、行动四大模块', 14),
    ('模块四：开发框架与工程实践', '🔧', '学习LangChain/LangGraph/LlamaIndex等主流框架', 13),
    ('模块五：多智能体系统', '🤝', '理解多Agent协作架构、通信协议、博弈论', 7),
    ('模块六：评估、安全与前沿拓展', '🛡️', '掌握评估基准、安全治理、MCP协议、前沿技术', 10),
]

exercises = {}
for fpath in sorted(glob.glob('backend/data/exercises/module_*.txt')):
    content = open(fpath, 'r', encoding='utf-8').read()
    parts = re.split(r'\n(?=关卡 \d+-\d+)', content)
    for part in parts:
        m_id = re.search(r'关卡 (\d+-\d+)', part)
        m_title = re.search(r'关卡 \d+-\d+[：:]\s*(.+)', part)
        m_mod = re.search(r'所属模块[：:]\s*(.+)', part)
        m_code = re.findall(r'```python\s*\n(.*?)```', part, re.DOTALL)
        if m_id and m_mod:
            mod_key = m_mod.group(1).strip()
            if mod_key not in exercises:
                exercises[mod_key] = []
            starter = m_code[0].strip() if m_code else '# TODO'
            exercises[mod_key].append({
                'id': m_id.group(1),
                'title': m_title.group(1).strip() if m_title else '',
                'starter': starter
            })

# 模块名映射：从文件中的模块名 → 配置中的标准名
def get_module_key(mod_name):
    if '模块一' in mod_name or '基础通识' in mod_name: return '模块一：智能体基础通识'
    if '模块二' in mod_name or '提示词' in mod_name: return '模块二：大模型（LLM）与提示词工程'
    if '模块三' in mod_name or '四大核心' in mod_name: return '模块三：智能体四大核心能力模块'
    if '模块四' in mod_name or '工程实践' in mod_name: return '模块四：开发框架与工程实践'
    if '模块五' in mod_name or '多智能体' in mod_name: return '模块五：多智能体系统'
    if '模块六' in mod_name or '评估' in mod_name or '安全' in mod_name: return '模块六：评估、安全与前沿拓展'
    return mod_name

merged = {}
for mod_name, tasks in exercises.items():
    key = get_module_key(mod_name)
    if key not in merged:
        merged[key] = []
    merged[key].extend(tasks)

for i, (mod_name, icon, desc, count) in enumerate(module_names):
    tasks = merged.get(mod_name, [])
    lines.append('  {')
    lines.append(f'    id: {i+1},')
    lines.append(f'    name: "{mod_name}",')
    lines.append(f'    icon: "{icon}",')
    lines.append(f'    description: "{desc}",')
    lines.append(f'    taskCount: {len(tasks)},')
    lines.append('    tasks: [')
    for t in tasks:
        safe_starter = t['starter'].replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
        lines.append('      {')
        lines.append(f'        id: "{t["id"]}",')
        lines.append(f'        title: "{t["title"]}",')
        lines.append(f'        starter: `{safe_starter}`')
        lines.append('      },')
    lines.append('    ]')
    lines.append('  },')
lines.append(']')
lines.append('')
lines.append('// 模拟进度（后续对接后端API）：{ "moduleId": completedCount }')
lines.append('export const MOCK_PROGRESS = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 }')

with open('frontend/src/config/exercises.js', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

total = sum(len(v) for v in exercises.values())
print(f'Config generated: {total} exercises across {len(exercises)} modules')
for mod_name, tasks in exercises.items():
    print(f'  {mod_name}: {len(tasks)} tasks')
