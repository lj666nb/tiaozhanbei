"""智能答疑服务"""
import json
import re
from services.ai_service import (
    call_llm, extract_json_object,
    QA_BEGINNER_PROMPT, QA_STANDARD_PROMPT, QA_ADVANCED_PROMPT, CODE_DEBUG_PROMPT
)
from database import get_db, json_load
from services.personalization_service import build_personalized_system_prompt, record_conversation_turn
from services.guidance_context_service import build_learning_context, public_learning_context


def _filter_code_response(raw: str) -> str:
    """后处理：从LLM回复中只提取三个代码分析段落，丢弃其余内容"""
    import re as _re
    sections = []
    for key in ['代码结构与功能分析', '是否存在错误', '如何修改']:
        pat = _re.search(rf'#+\s*{key}\s*\n?(.*?)(?=#+\s|\Z)', raw, _re.DOTALL | _re.IGNORECASE)
        if pat:
            sections.append(f"## {key}\n{pat.group(1).strip()}")
    if sections:
        return '\n\n'.join(sections)
    # 降级：取前600字符
    return raw[:600]


def is_code_input(text: str) -> bool:
    """检测用户输入是否为代码"""
    # 强特征：编程语言关键字/语法结构
    code_patterns = [
        # Python
        r'\bdef\s+\w+\s*\(', r'\bclass\s+\w+', r'\bimport\s+\w+',
        r'\bfrom\s+\w+\s+import\b', r'\bprint\s*\(', r'\breturn\b',
        r'\bif\s+__name__\s*==', r'\b(lambda|yield|with|async|await)\b',
        r'\.(append|pop|keys|items|values|split|join|strip)\s*\(',
        # JavaScript / TypeScript
        r'\bfunction\s+\w+\s*\(', r'\bconst\s+\w+\s*=', r'\blet\s+\w+\s*=',
        r'\bvar\s+\w+\s*=', r'\bconsole\.log\b', r'\bexport\s+(default\s+)?',
        r'=>\s*\{', r'\bdocument\.', r'\bwindow\.', r'\brequire\s*\(',
        # Java / C# / C++
        r'\bpublic\s+(static\s+)?(void|int|String|class)\b',
        r'\bSystem\.out\.print', r'\b#include\s*[<"]', r'\bint\s+main\s*\(',
        r'\bstd::', r'\busing\s+namespace\b',
        # SQL
        r'\bSELECT\s+.+\s+FROM\b', r'\bCREATE\s+TABLE\b',
        r'\bINSERT\s+INTO\b', r'\bUPDATE\s+.+\s+SET\b',
        # Shell
        r'^#!/.+', r'\b(chmod|grep|awk|sed|curl|wget)\b',
        # HTML / CSS
        r'</?\w+[^>]*>', r'\{[^}]*:[^}]*;\s*\}',
        # 通用
        r'```', r'^\s*#include', r'^\s*package\s+\w+',
    ]
    for pattern in code_patterns:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return True
    # 辅助：多行 + 代码符号密度
    code_symbols = ['{', '}', ';', '=>', '===', '!==', '+=', '-=', '*=', '/=']
    symbol_count = sum(text.count(s) for s in code_symbols)
    lines = [l for l in text.strip().split('\n') if l.strip()]
    if len(lines) >= 3 and symbol_count >= 2:
        return True
    # 辅助：明显的缩进块（Python风格）
    if len(lines) >= 3:
        indented = sum(1 for l in lines if l.startswith('    ') or l.startswith('\t'))
        if indented >= 2:
            return True
    return False


def is_learning_related(text: str) -> bool:
    """检测用户输入是否与学习/知识相关，过滤无关闲聊"""
    # 明显的学习/知识相关关键词
    learning_patterns = [
        # 学习意图 — 中文（通用疑问词优先）
        r'(如何|怎么|怎样|怎么样|为什么|为何|什么是|是什么|啥是|啥)',
        r'(解释一下|讲讲|说明一下|介绍一下|简述|概述|总结一下)',
        r'(帮我|教我|教我一下|怎么学|好不好|对吗|对吧|行不行|可以吗)',
        r'(区别|对比|比较|优缺点|联系|关系|异同|不同|优缺点)',
        r'(原因|原理|机制|流程|步骤|方法|技巧|方案|策略)',
        # 知识领域
        r'(编程|代码|算法|数据结构|软件|开发|前端|后端|数据库|SQL|Python|Java|C\+\+|JavaScript|TypeScript|React|Vue|Node|API|HTTP)',
        r'(数学|物理|化学|生物|历史|地理|政治|哲学|经济|心理|社会|法律|文学|艺术|音乐)',
        r'(AI|人工智能|机器学习|深度学习|神经网络|NLP|CV|强化学习|大模型|LLM|GPT|Transformer|Agent|智能体)',
        r'(英语|日语|韩语|法语|德语|语法|词汇|口语|写作|翻译|阅读)',
        r'(考试|考研|高考|雅思|托福|四六级|备考|复习|真题|模拟)',
        r'(论文|毕业|开题|文献|综述|实验|数据分析|研究报告)',
        r'(操作系统|计算机|网络|协议|安全|加密|认证|架构|设计模式)',
        # 英文学习关键词
        r'\b(how|what|why|when|where|who|explain|describe|define|compare|analyze|evaluate)\b',
        r'\b(learn|study|tutorial|guide|example|concept|definition|principle|theory)\b',
        r'\b(python|java|javascript|typescript|react|vue|node|api|http|sql|docker|linux|git)\b',
        # 问号结尾 + 足够长度
        r'^.{10,}.*[？?]$',
    ]
    for pattern in learning_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # 短句闲聊过滤（< 8 字的单句通常不是学习问题）
    cleaned = text.strip()
    if len(cleaned) < 8 and not any(kw in cleaned for kw in ['?', '?', '什么', '怎么', '如何', '为什么']):
        return False

    # 纯闲聊特征
    chat_only = [
        r'^(你好|嗨|hi|hello|在吗|在不在|有人吗|哈哈|呵呵|嗯|哦|好的|谢谢|拜拜|再见|晚安|早安)\s*$',
        r'^(今天|明天|昨天).{0,5}(天气|心情|怎么)',
        r'^\s*(无聊|好累|困了|饿了|累了)\s*$',
    ]
    for pattern in chat_only:
        if re.search(pattern, text, re.IGNORECASE):
            return False

    # 默认放行（长度较长可能包含学习内容）
    if len(cleaned) >= 15:
        return True

    return False


def _rewrite_question(question: str) -> str:
    """将用户问题注入AI智能体学科领域上下文，避免LLM给出词典释义等无关回答"""
    # 需要强制AI上下文的歧义词汇
    ai_context_words = {
        "skill": "AI Agent的Skill（工具/能力模块）",
        "skills": "AI Agent的Skills（工具/能力模块）",
        "agent": "AI智能体（AI Agent）",
        "agents": "AI智能体（AI Agent）",
        "tool": "AI Agent的Tool（工具调用）",
        "tools": "AI Agent的Tools（工具调用）",
        "prompt": "大语言模型的Prompt（提示词）",
        "prompts": "大语言模型的Prompt（提示词）",
        "token": "大语言模型的Token（文本切分单元）",
        "tokens": "大语言模型的Tokens（文本切分单元）",
        "memory": "AI Agent的Memory（记忆机制）",
        "chain": "LLM的Chain（调用流水线）",
        "chains": "LLM的Chains（调用流水线）",
        "model": "大语言模型/机器学习模型",
        "models": "大语言模型/机器学习模型",
        "planner": "AI Agent的Planner（规划模块）",
        "planning": "AI Agent的Planning（规划能力）",
        "reasoning": "AI Agent的Reasoning（推理能力）",
        "embedding": "机器学习中的Embedding（向量嵌入）",
        "fine-tuning": "大模型的Fine-tuning（微调）",
        "hallucination": "大模型的Hallucination（幻觉问题）",
        "grounding": "AI的Grounding（知识锚定）",
        "orchestration": "多Agent的Orchestration（编排）",
        "guardrails": "AI系统的Guardrails（安全护栏）",
        "function calling": "LLM的Function Calling（函数调用）",
    }

    q_lower = question.lower().strip()
    # 检测是否为简短的"什么是X"类问题
    what_is_match = re.match(
        r'^(什么是|啥是|什么是|什么叫|啥叫|解释一下?|讲讲|说说|问一下?)\s*(.+?)$',
        question.strip()
    )
    if what_is_match:
        term = what_is_match.group(2).strip().rstrip("？?")
        term_lower = term.lower()
        if term_lower in ai_context_words:
            rewritten = f"在AI智能体（AI Agent）和人工智能领域中，{term}是什么？请讲解{ai_context_words[term_lower]}的概念、核心原理和实际应用。"
            return rewritten

    # 如果问题中包含歧义词汇但未被上述规则匹配，主动注入上下文
    for word, ai_meaning in ai_context_words.items():
        if word in q_lower and "AI" not in question and "人工智能" not in question and "智能体" not in question:
            return f"[本问题是AI智能体学科学习平台上的提问，请从AI/人工智能技术角度回答]\n\n{question}"
    return question


async def answer_question(user_id: int, question: str, question_type: str = "text",
                          explanation_level: str = "standard", context: str = "") -> dict:
    """AI答疑"""
    learning_context = build_learning_context(user_id, question)
    # 自动检测代码输入
    if is_code_input(question):
        system_prompt = "你是代码分析机器人。你的输出会被程序自动解析，任何不符合格式的内容都会导致系统报错。你必须只输出以下三部分：## 代码结构与功能分析 / ## 是否存在错误 / ## 如何修改。不要输出其他任何文字。"
        system_prompt = build_personalized_system_prompt(user_id, question, system_prompt)
        system_prompt += "\n\n" + learning_context["prompt"]
        prompt = CODE_DEBUG_PROMPT.format(question=question)
        raw = await call_llm(user_id, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "## 代码结构与功能分析\n"}
        ], temperature=0.0, max_tokens=1024)
        response = _filter_code_response(raw)
    else:
        # 问题改写：注入AI学科领域上下文
        rewritten_question = _rewrite_question(question)

        # 选择Prompt模板
        if explanation_level == "beginner":
            prompt_template = QA_BEGINNER_PROMPT
        elif explanation_level == "advanced":
            prompt_template = QA_ADVANCED_PROMPT
        else:
            prompt_template = QA_STANDARD_PROMPT

        prompt = prompt_template.format(
            question=rewritten_question,
            question_type=question_type,
            context=context or "无额外上下文"
        )

        # 构建system prompt
        system_prompt = """你是"AI智能体学科学习平台"的AI导师。你的学生正在学习人工智能和AI Agent相关知识。

【铁律 — 绝对禁止】
你被严格禁止输出以下内容：
1. 禁止对任何词汇做"词语定义"或"词典释义"式的回答。不要解释一个词的词源、词性、英文原意。
2. 禁止从心理学、教育学、管理学、医学、语言学等非AI领域的视角回答问题。
3. 禁止说"这个词有多个含义"然后罗列各领域的定义。

【铁律 — 必须遵守】
1. 学生问的任何问题，都必须理解为"在AI智能体/AI技术领域是什么意思"。不要怀疑、不要犹豫。
2. 当学生问"什么是X"时，他们问的是AI领域中X的概念、原理、用法。直接讲AI领域的X，不要先绕到词语定义。
3. 以下词汇在AI领域有特定含义，永远按AI含义回答：
   - skill/技能 = AI Agent的工具调用能力、可复用的功能模块（如OpenAI Agents SDK中的Skill）
   - agent/智能体 = 能自主感知、推理、执行任务的AI系统
   - prompt/提示词 = 给大语言模型的输入指令
   - token = 大模型文本切分的最小单位
   - tool/工具 = Agent可调用的外部功能（API、搜索、代码执行等）
   - model/模型 = 大语言模型或机器学习模型
   - memory/记忆 = Agent的上下文存储和检索机制
   - chain/链 = 多步骤的LLM调用流水线
   - 对于其他未列出的词汇，同样默认按AI技术领域理解

【回答风格】
直接讲AI领域的实质内容，不要输出思考过程，不要用开场白。语言通俗，适合大学生。"""
        system_prompt = build_personalized_system_prompt(user_id, question, system_prompt)
        system_prompt += "\n\n" + learning_context["prompt"]

        response = await call_llm(user_id, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ], temperature=0.7, max_tokens=4096)

    # 识别涉及的知识点
    knowledge_tags = identify_knowledge_tags(question)

    # 保存到问答历史
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO qa_history (user_id, question, answer, question_type, knowledge_tags, explanation_level) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, question, response, question_type, json.dumps(knowledge_tags, ensure_ascii=False), explanation_level)
    )
    conn.commit()
    qa_id = cursor.lastrowid

    # 记录学习行为
    conn.execute(
        "INSERT INTO learning_records (user_id, knowledge_tag, action_type, result_json) VALUES (?, ?, 'qa', ?)",
        (user_id, ",".join(knowledge_tags), json.dumps({"question": question[:100]}, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

    record_conversation_turn(user_id, None, question, response, knowledge_tags)

    return {
        "id": qa_id,
        "question": question,
        "answer": response,
        "knowledge_tags": knowledge_tags,
        "explanation_level": explanation_level,
        "learning_context": public_learning_context(learning_context),
    }

async def save_qa_history(user_id: int, question: str, answer: str,
                          question_type: str = "text",
                          explanation_level: str = "standard",
                          conversation_id: int = None,
                          rag_sources: list = None,
                          search_results: list = None,
                          search_query: str = "",
                          tool_events: list = None,
                          mind_map: dict = None,
                          learning_analysis: dict = None) -> int:
    """保存流式问答记录到数据库，返回记录ID"""
    knowledge_tags = identify_knowledge_tags(question)
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO qa_history (user_id, question, answer, question_type, knowledge_tags, explanation_level) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, question, answer, question_type, json.dumps(knowledge_tags, ensure_ascii=False), explanation_level)
    )
    conn.commit()
    qa_id = cursor.lastrowid

    # 记录学习行为
    conn.execute(
        "INSERT INTO learning_records (user_id, knowledge_tag, action_type, result_json) VALUES (?, ?, 'qa', ?)",
        (user_id, ",".join(knowledge_tags), json.dumps({"question": question[:100]}, ensure_ascii=False))
    )
    conn.commit()
    conn.close()
    record_conversation_turn(user_id, conversation_id, question, answer, knowledge_tags,
                             rag_sources=rag_sources, search_results=search_results, search_query=search_query,
                             tool_events=tool_events, mind_map=mind_map,
                             learning_analysis=learning_analysis)
    return qa_id


def identify_knowledge_tags(text: str) -> list:
    """根据问题文本识别涉及的知识点"""
    keyword_map = {
        "智能体": ["智能体基础概念"],
        "agent": ["智能体基础概念"],
        "大模型": ["大模型基座原理"],
        "LLM": ["大模型基座原理"],
        "上下文": ["大模型基座原理"],
        "参数": ["大模型基座原理"],
        "transformer": ["大模型基座原理"],
        "提示词": ["提示词工程"],
        "prompt": ["提示词工程"],
        "思维链": ["提示词工程"],
        "少样本": ["提示词工程"],
        "零样本": ["提示词工程"],
        "框架": ["智能体框架开发"],
        "工具调用": ["智能体框架开发"],
        "记忆": ["智能体框架开发"],
        "规划": ["智能体框架开发"],
        "算法": ["智能体算法逻辑"],
        "决策": ["智能体算法逻辑"],
        "推理": ["智能体算法逻辑"],
        "协作": ["多智能体应用"],
        "多智能体": ["多智能体应用"],
        "多agent": ["多智能体应用"],
        "冲突": ["多智能体应用"],
    }
    matched = set()
    text_lower = text.lower()
    for keyword, tags in keyword_map.items():
        if keyword.lower() in text_lower:
            for tag in tags:
                matched.add(tag)
    return list(matched) if matched else ["综合"]

async def delete_qa_history(user_id: int, qa_id: int) -> bool:
    """删除单条问答历史"""
    conn = get_db()
    # 验证该记录属于当前用户
    row = conn.execute(
        "SELECT id FROM qa_history WHERE id = ? AND user_id = ?",
        (qa_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return False
    # 删除关联的反馈记录
    conn.execute("DELETE FROM qa_feedback WHERE qa_history_id = ?", (qa_id,))
    # 删除问答记录
    conn.execute("DELETE FROM qa_history WHERE id = ?", (qa_id,))
    conn.commit()
    conn.close()
    return True


async def clear_qa_history(user_id: int) -> int:
    """清空用户的所有问答历史，返回删除条数"""
    conn = get_db()
    # 先删除所有关联的反馈记录
    conn.execute(
        "DELETE FROM qa_feedback WHERE qa_history_id IN (SELECT id FROM qa_history WHERE user_id = ?)",
        (user_id,)
    )
    # 删除所有问答记录
    cursor = conn.execute("DELETE FROM qa_history WHERE user_id = ?", (user_id,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count


async def get_qa_history(user_id: int, page: int = 1, page_size: int = 20) -> dict:
    """获取问答历史"""
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM qa_history WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        "SELECT id, question, answer, question_type, knowledge_tags, explanation_level, created_at FROM qa_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, page_size, offset)
    ).fetchall()
    conn.close()

    history = []
    for r in rows:
        d = dict(r)
        d["knowledge_tags"] = json_load(d["knowledge_tags"]) if d["knowledge_tags"] else []
        history.append(d)

    return {
        "items": history,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
