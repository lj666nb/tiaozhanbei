"""LangChain AI服务封装 — 支持用户自行配置API Key/Base URL/模型"""
import json
import re
from typing import AsyncGenerator, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from database import get_db
import httpx
import logging
# LLM配置完全由用户在数据库中自行设置，无系统默认值


def _get_user_llm_config(user_id: int) -> Optional[dict]:
    """从数据库读取用户的LLM配置"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM user_llm_config WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def _build_llm(user_id: int, temperature: float = 0.7, max_tokens: int = 4096,
               request_timeout = (10.0, 300.0), deep_thinking: bool = False,
               extra_body: dict = None) -> ChatOpenAI:
    """
    构建LangChain ChatOpenAI实例。
    用户必须先在个人中心配置API Key/Base URL/Model，否则抛出错误。
    deep_thinking: 对 DeepSeek 模型启用原生 reasoning（reasoning_content）

    request_timeout: float | tuple[float, float] | None
        - float: 所有阶段超时秒数（connect + read + write + pool）
        - tuple (connect, read): 分别设置连接超时和读取超时
        - None: 使用 OpenAI SDK 默认值（connect=5s, read=600s）
        - 默认 (10, 300): 连接 10s，读取 300s（5分钟）
    """
    user_config = _get_user_llm_config(user_id)

    if not user_config or not user_config.get("api_key"):
        raise ValueError("请先在「个人中心 → AI大模型配置」中设置您的API Key、接口地址和模型名称，否则无法使用AI答疑功能")

    model_name = user_config.get("model_name", "gpt-4o")
    base_url = user_config.get("base_url", "https://api.openai.com")

    # DeepSeek 原生 reasoning：仅 deepseek-reasoner 支持
    # deepseek-v4-pro 等思考模型默认开启 thinking，可能返回 reasoning_content
    # 调用方可传入 extra_body={"thinking": {"type": "disabled"}} 关闭
    _extra_body = extra_body  # use caller-provided extra_body if given
    if _extra_body is None and deep_thinking and "deepseek" in str(base_url).lower() and "reasoner" in model_name.lower():
        _extra_body = {}  # reasoner 原生返回 reasoning_content，无需额外配置

    return ChatOpenAI(
        model=model_name,
        openai_api_key=user_config["api_key"],
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=request_timeout,
        extra_body=_extra_body,
    )


def _convert_message(msg: dict) -> BaseMessage:
    """将 {'role': 'system'|'user'|'assistant', 'content': str} 转为LangChain消息"""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    if role == "system":
        return SystemMessage(content=content)
    elif role == "assistant":
        return AIMessage(content=content)
    else:
        return HumanMessage(content=content)


async def call_llm(user_id: int, messages: list, temperature: float = 0.7,
                   max_tokens: int = 4096, request_timeout = (10.0, 300.0)) -> str:
    """
    通过LangChain调用LLM，返回完整文本响应。

    Args:
        user_id: 用户ID，用于读取该用户的LLM配置
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        temperature: 温度参数
        max_tokens: 最大token数
        request_timeout: 请求超时（默认连接10s + 读取300s）
    Returns:
        LLM返回的文本内容
    """
    llm = _build_llm(user_id, temperature=temperature, max_tokens=max_tokens,
                     request_timeout=request_timeout)
    lc_messages = [_convert_message(m) for m in messages]
    try:
        response = await llm.ainvoke(lc_messages)
        return response.content
    except Exception as e:
        return f"LLM调用异常: {str(e)}"


async def stream_llm(user_id: int, messages: list, temperature: float = 0.7,
                     max_tokens: int = 4096, deep_thinking: bool = False) -> AsyncGenerator[str, None]:
    """
    通过LangChain流式调用LLM，产出SSE格式数据。

    Args:
        user_id: 用户ID
        messages: 消息列表
        temperature: 温度参数
        max_tokens: 最大token数
        deep_thinking: 是否启用深度思考模式（DeepSeek原生reasoning或prompt-based）
    Yields:
        SSE格式字符串: "data: {...}\n\n" 或 "data: [DONE]\n\n"
    """
    user_config = _get_user_llm_config(user_id)
    is_deepseek = user_config and "deepseek" in str(user_config.get("base_url", "")).lower()

    # DeepSeek 原生 reasoning：模型自动分离 reasoning_content 和 content，不需要 prompt 标记
    # 非 DeepSeek 模型：使用 prompt 标记 【思考过程】/【回答】
    use_native_reasoning = deep_thinking and is_deepseek

    # 深度思考模式参数调整
    if deep_thinking:
        actual_temperature = temperature * 0.6
        actual_max_tokens = max(max_tokens, 8192)
    else:
        actual_temperature = temperature
        actual_max_tokens = max_tokens

    llm = _build_llm(user_id, temperature=actual_temperature, max_tokens=actual_max_tokens,
                     deep_thinking=deep_thinking)
    lc_messages = [_convert_message(m) for m in messages]
    try:
        async for chunk in llm.astream(lc_messages):
            chunk_data = {}

            # DeepSeek 原生 reasoning_content（内部推理过程，独立于正文）
            reasoning = None
            try:
                if hasattr(chunk, 'additional_kwargs') and chunk.additional_kwargs:
                    reasoning = chunk.additional_kwargs.get('reasoning_content')
            except Exception:
                reasoning = None
            if reasoning:
                chunk_data['reasoning'] = reasoning

            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if content:
                chunk_data['content'] = content

            if chunk_data:
                yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    finally:
        yield "data: [DONE]\n\n"


def extract_json(text: str) -> list:
    """从AI返回文本中提取JSON数组"""
    # 尝试直接解析
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except:
        pass
    # 尝试提取```json```代码块
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except:
            pass
    # 尝试提取第一个[到最后一个]
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return []


def extract_json_object(text: str) -> dict:
    """从AI返回文本中提取JSON对象"""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except:
        pass
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return result
        except:
            pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    return {}


# ===== 联网搜索（兼容旧调用；新 QA 使用 Function Calling 工具注册表）=====
async def web_search(query: str, max_results: int = 5, api_key: str = "") -> List[dict]:
    """兼容旧代码的 Tavily advanced 搜索入口，不再回退到 Bing。"""
    import os
    from services.search_service import TAVILY_SEARCH_ENDPOINT, filter_search_results, rewrite_search_query

    key = str(api_key or os.getenv("TAVILY_API_KEY", "")).strip()
    if not key:
        return []
    rewritten = rewrite_search_query(query)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TAVILY_SEARCH_ENDPOINT,
                json={
                    "api_key": key,
                    "query": rewritten,
                    "topic": "general",
                    "search_depth": "advanced",
                    "max_results": min(max(max_results * 2, 6), 10),
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        return filter_search_results(rewritten, data.get("results") or [], max_results=max_results)
    except Exception:
        return []


# ===== 深度思考指令 =====
# 注意：仅用于非 DeepSeek 模型；DeepSeek 模型用原生 reasoning_content
DEEP_THINKING_INSTRUCTION = """
深度思考模式已激活。请严格按以下格式输出：

【思考过程】
1. 先拆解问题的核心要素和潜在难点
2. 从多个角度分析，标注推理依据
3. 给出你的推理链条

【回答】
给出结构清晰、有深度的完整回答。
"""


# ===== 出题Prompt模板 =====
QUIZ_GENERATION_PROMPT = """你是AI智能体课程专属出题引擎，严格按照以下约束生成题目，仅针对AI智能体学科，禁止超纲。

1. 出题知识点范围：{target_knowledge}
2. 题目难度：{level}
3. 题目数量：{count}道
4. 题目题型：{question_type}
5. 规避知识点：{avoid_knowledge}（已掌握内容少出，规避历史重复错题）

输出要求：
严格返回JSON数组格式，禁止多余文字、禁止markdown、禁止解释。
每道题目必须包含以下字段：
- question_id（字符串）
- question（题目内容）
- options（选项数组，单选题和多选题为4个选项，判断题固定为["正确","错误"]，简答/填空/代码实操用空数组[]）
- question_type（题型：单选/多选/判断/简答/填空/代码实操）
- answer（正确答案）
- analysis（详细解析，必须包含：①本题考察的知识点 ②正确思路的推导过程 ③常见错误和避免方法 ④学习建议）
- option_analysis（选项分析对象，仅选择题/判断题需要，其他题型用空对象{{}}。格式：{{"A":"选项A为什么对/错","B":"选项B为什么对/错",...}}。对每个选项逐一说明其正确或错误的具体原因，学生对错题复习时非常依赖此信息。）
- knowledge_tag（所属知识点名称）
- difficulty（难度：Lv1入门/Lv2中等/Lv3高阶）

题目要求：
- 入门题考概念辨析，中等题考原理理解，高阶题考代码实操、Prompt优化、架构分析
- analysis字段必须包含错误原因、知识点溯源、学习提升建议
- option_analysis必须逐项解释，不能为空或敷衍
- 贴合大学生AI智能体课程学习难度，不幼稚、不超纲
- 单选题的options必须是4个选项的数组，多选题options也是4个选项的数组
- 判断题的options为["正确","错误"]"""

# ===== 答疑Prompt模板 =====
QA_BEGINNER_PROMPT = """你是一位耐心细致的AI智能体学科辅导老师。学生是零基础入门水平，正在学习人工智能和AI Agent相关知识。

【关键规则】
- 学生问的所有问题都是关于AI/人工智能/计算机科学的。永远不要给出词语定义、词典释义、词源解释。
- 当学生问"什么是X"，直接讲X在AI领域的概念和原理，用生活类比帮助零基础学生理解。
- 禁止从心理学、教育学、管理学等其他领域回答。
- 以下词汇默认AI含义：skill=AI智能体的工具/能力模块，agent=AI智能体，prompt=给大模型的指令，token=文本切分单元，tool=Agent可调用的外部功能

要求：
1. 从最基础的概念讲起，用日常生活中的类比帮助理解
2. 避免使用过多专业术语，如果必须使用，请给出简单解释
3. 用具体例子说明抽象概念
4. 分步骤讲解，最后给出核心要点总结
5. 鼓励学生继续提问
6. 直接回答问题，不要用开场白，不要描述你正在做什么

学生问题：{question}
问题类型：{question_type}
额外上下文：{context}"""

QA_STANDARD_PROMPT = """你是一位知识渊博的AI智能体学科导师。学生正在学习人工智能和AI Agent相关知识，有一定基础但需要系统理解。

【关键规则】
- 学生问的所有问题都是关于AI/人工智能/计算机科学的。永远不要给出词语定义、词典释义、词源解释。
- 当学生问"什么是X"，直接讲X在AI领域的概念、原理、机制。禁止先绕到"这个词本意是..."之类的废话。
- 禁止从心理学、教育学、管理学等其他领域回答。
- 以下词汇默认AI含义：skill=AI智能体的工具/能力模块，agent=AI智能体，prompt=给大模型的指令，token=文本切分单元，tool=Agent可调用的外部功能，memory=Agent的记忆机制

要求：
1. 分步骤详细讲解，每一步标注依据和知识点
2. 标注常见易错点和理解误区
3. 提供典型例题或应用场景辅助理解
4. 给出知识框架关联，帮助学生建立知识体系
5. 最后给出核心要点总结和延伸学习建议
6. 直接回答问题，不要用开场白，不要描述你正在做什么

学生问题：{question}
问题类型：{question_type}
额外上下文：{context}"""

QA_ADVANCED_PROMPT = """你是一位资深AI智能体学科专家导师。学生正在学习人工智能和AI Agent相关知识，学有余力需要拔高拓展。

【关键规则】
- 学生问的所有问题都是关于AI/人工智能/计算机科学的。永远不要给出词语定义、词典释义、词源解释。
- 当学生问"什么是X"，直接深入讲X在AI领域的底层原理和前沿发展。禁止从"这个词的意思是..."开始。
- 禁止从心理学、教育学、管理学等其他领域回答。
- 以下词汇默认AI含义：skill=AI智能体的工具/能力模块（如OpenAI Agents SDK的Skill机制），agent=AI智能体系统，prompt=大模型输入工程，token=文本切分与计费单元，tool=Agent外部功能调用，memory=Agent上下文与持久化存储

要求：
1. 深入剖析核心原理和底层逻辑
2. 提供延伸考点、变式分析、前沿技术关联
3. 给出考研/竞赛/工业界的拓展视野
4. 批判性分析不同方案的优缺点
5. 推荐高阶学习资源和研究方向
6. 最后给出拔高总结
7. 直接回答问题，不要用开场白，不要描述你正在做什么

学生问题：{question}
问题类型：{question_type}
额外上下文：{context}"""

CODE_DEBUG_PROMPT = """{question}"""

# ===== 学情报告Prompt =====
REPORT_PROMPT = """你是AI智能体学科的学习分析师，请根据学生的测评数据生成学情诊断报告。

测评数据：{quiz_data}

请按以下格式返回JSON：
{
    "overall_assessment": "整体评价（200字以内）",
    "knowledge_analysis": {
        "知识点名称": {"mastery": 0.0-1.0, "level": "优秀/良好/一般/薄弱/盲区", "comment": "简短评语"}
    },
    "ability_analysis": {
        "概念理解": {"score": 0.0-1.0, "comment": ""},
        "原理辨析": {"score": 0.0-1.0, "comment": ""},
        "算法逻辑": {"score": 0.0-1.0, "comment": ""},
        "代码实操": {"score": 0.0-1.0, "comment": ""},
        "应用分析": {"score": 0.0-1.0, "comment": ""}
    },
    "weak_points": ["薄弱点1", "薄弱点2"],
    "strong_points": ["优势点1", "优势点2"],
    "error_summary": "错题归因分析（150字以内）",
    "study_suggestions": ["建议1", "建议2", "建议3"],
    "next_focus": "下一步重点学习方向"
}"""

# ===== 学习路径生成Prompt（精简版，减少token消耗加速生成） =====
LEARNING_PATH_PROMPT = """你是AI智能体学科的学习规划师。为学生生成个性化学习路径。

学生学情：{student_profile}
学习目标：{goal}
时间规划：{timeline}
学习深度：{learning_depth}
知识体系（含标签）：{knowledge_system}
知识依赖链：{prerequisite_chain}

学习深度：基础=概念理解+入门题 | 标准=理论实践+中等题 | 深入=源码分析+高阶题

【约束】
1. 严格遵守依赖链：B依赖A → A必须在B之前
2. 基础标签前1/3，高阶标签后1/3
3. 薄弱知识点优先安排

返回JSON（只返回JSON）：
{{"phases":[{{"name":"阶段名","duration":"耗时","tasks":[{{"day":1,"topic":"主题","knowledge":"知识点标签","action":"行动","resource":"资源","check":"验收标准"}}]}}],"weekly_goals":["周目标"],"key_milestones":["里程碑"],"estimated_total_days":30,"tips":"学习建议"}}"""

# ===== 编程任务生成Prompt =====
CODE_TASK_PROMPT = """你是AI智能体学科的编程教练。请根据以下任务信息，生成一个编程练习题。

任务主题：{topic}
知识点：{knowledge}
学习行动：{action}
学习深度：{learning_depth}

请生成一个Python编程练习题，要求：
1. 任务描述要详细说明程序应实现的具体功能
2. 给出2-3个具体测试用例，每个测试用例包含输入和期望输出
3. 提供起始代码框架，代码必须与任务需求严格对应
4. 测试用例的期望输出必须是确定性的（能通过字符串精确匹配验证）

返回JSON（不要markdown代码块）：
{{
    "title": "编程练习标题",
    "description": "详细的任务描述，说明代码应实现哪些功能（200字以内）",
    "requirements": ["具体要求1", "具体要求2", "具体要求3"],
    "test_cases": [
        {{
            "name": "测试用例1名称",
            "description": "该测试验证什么",
            "setup_code": "准备工作代码（可为空字符串）",
            "test_input": "通过stdin传入的测试输入（可为空字符串）",
            "expected_output": "期望的标准输出结果（必须精确）",
            "check_type": "exact_match"
        }}
    ],
    "starter_code": "Python起始代码，包含函数签名和TODO注释"
}}

注意：
- test_input 如果不需要输入则设为空字符串
- expected_output 必须是可精确匹配的字符串（去除首尾空白后比较）
- starter_code 应该是一个完整的Python脚本框架，用户在此基础上填充实现
- 如果知识点涉及"智能体"相关，代码框架应包含Agent类设计
- 如果知识点涉及"框架"相关，代码框架应包含框架调用示例"""
