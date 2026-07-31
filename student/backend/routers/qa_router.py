"""智能答疑路由"""
import asyncio
import json
import os
import time
import tempfile
import subprocess
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from auth import get_current_user
from schemas import APIResponse, QARequest, QASaveRequest, QAFeedbackRequest, CodeRunRequest
from services import qa_service
from services.ai_service import stream_llm, call_llm, _get_user_llm_config, DEEP_THINKING_INSTRUCTION
from services.agent_tool_service import plan_and_execute_tools
from services.conversation_export_service import iter_conversation_jsonl
from services.file_parser import parse_file
from services.evolution_service import extract_pattern, find_similar_patterns, evolve
from services.student_model import get_student_profile, record_qa_activity
from services.personalization_service import (
    build_personalized_system_prompt,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_or_create_current_conversation,
    get_conversation_history,
    get_knowledge_point_detail,
    get_memory_overview,
    create_memory_fact,
    update_memory_fact,
    delete_memory_fact,
    list_conversations,
    save_user_message,
    save_assistant_message,
    identify_knowledge_tags_standalone,
)
from database import get_db
from services.guidance_context_service import build_learning_context, public_learning_context
from services.mind_map_service import get_mind_map

router = APIRouter()

MEMORY_VISIBILITY_PHRASES = (
    "你对我有什么认识", "你了解我什么", "你记得我什么", "你还记得我吗",
    "我的画像", "我的长期记忆", "查看我的记忆", "关于我的信息",
)


def _is_memory_visibility_query(question: str) -> bool:
    compact = "".join(str(question or "").lower().split())
    return any("".join(phrase.lower().split()) in compact for phrase in MEMORY_VISIBILITY_PHRASES)

def _require_llm_config(user_id: int):
    """检查用户是否已配置LLM，未配置则抛出400错误"""
    config = _get_user_llm_config(user_id)
    if not config or not config.get("api_key"):
        raise HTTPException(
            status_code=400,
            detail="请先在「个人中心 → AI大模型配置」中设置您的API Key、接口地址和模型名称"
        )

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """上传文件并提取文本内容"""
    _require_llm_config(current_user["id"])
    try:
        content = await file.read()
        result = parse_file(content, file.filename)
        return APIResponse(data={
            "text": result["text"],
            "file_type": result["file_type"],
            "filename": file.filename,
            "base64": result.get("base64"),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")


@router.post("/ask", response_model=APIResponse)
async def ask_question(req: QARequest, current_user: dict = Depends(get_current_user)):
    """提交问题获取AI答疑"""
    _require_llm_config(current_user["id"])
    result = await qa_service.answer_question(
        user_id=current_user["id"],
        question=req.question,
        question_type=req.question_type,
        explanation_level=req.explanation_level,
        context=req.context
    )
    return APIResponse(data=result)

def _is_pure_code(text: str) -> bool:
    """判断用户输入是否为纯代码（没有额外的自然语言指令）"""
    cleaned = text.strip()

    # 去掉代码块标记
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
    elif cleaned.startswith("```"):
        # 开头有代码块标记但结尾没有 → 可能有文字描述在代码块外
        cleaned = cleaned[3:].strip()

    # 快速判断：是否包含明显的自然语言指令关键词
    instruction_keywords = [
        '修改', '改成', '改为', '换成', '换一种', '改成', '优化', '重构',
        '解释', '分析', '说明', '注释', '注解',
        '这个代码', '这段代码', '帮我', '能否', '可以', '怎么', '如何', '为什么',
        '我不喜欢', '不好', '不对', '有问题', '错了', '换掉', '替换',
        '实现方式', '换种方式', '换一个方式', '改成用', '改成使用',
        '用for', '用while', '用递归', '用lambda', '用类',
        '帮我改', '帮忙改', '麻烦改', '帮我优化', '帮忙优化',
    ]
    for kw in instruction_keywords:
        if kw in cleaned:
            return False

    # 逐行分析
    lines = cleaned.split('\n')
    code_lines = 0
    natural_lines = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 注释行（# 或 // 开头）计入代码
        if stripped.startswith('#') or stripped.startswith('//'):
            code_lines += 1
            continue

        # 明显的自然语言行（以中文标点结尾的长句）
        if (len(stripped) > 10 and
            any(stripped.endswith(c) for c in ('。', '！', '？', '.', '!', '?'))):
            natural_lines += 1
            continue

        # 以自然语言开头的行
        natural_starters = (
            '请', '帮', '改', '换', '优化', '解释', '分析', '修改',
            '这个', '这段', '下面', '以下', '如上',
            '帮我', '能否', '可以', '怎么', '如何', '我想', '希望',
            '用', '按照', '根据', '麻烦', '代码', '问题', '需要',
            '如果', '但是', '不过', '另外', '还有', '注意',
        )
        if any(stripped.startswith(w) for w in natural_starters):
            natural_lines += 1
            continue

        # 明显的中文自然语言（包含较多中文字符，不是代码）
        import re
        chinese_chars = len(re.findall(r'[一-鿿]', stripped))
        if chinese_chars > 5:  # 超过5个中文字 → 自然语言
            natural_lines += 1
            continue

        # 代码特征检测
        has_code_features = (
            'def ' in stripped or 'class ' in stripped or
            'import ' in stripped or 'from ' in stripped or
            'return ' in stripped or 'print(' in stripped or
            stripped.endswith(':') and ('if ' in stripped or 'else' in stripped or
                                        'for ' in stripped or 'while ' in stripped or
                                        'try' in stripped or 'except' in stripped) or
            'self.' in stripped or 'lambda' in stripped or
            ' = ' in stripped or ' += ' in stripped or
            stripped.endswith('{') or stripped.endswith(';')
        )
        if has_code_features:
            code_lines += 1
        elif chinese_chars > 0:
            natural_lines += 1
        else:
            code_lines += 1  # 无中文字符且无自然语言特征 → 算代码

    total = code_lines + natural_lines
    if total == 0:
        return True

    # 任何自然语言行 → 不是纯代码
    if natural_lines > 0:
        return False
    return True


@router.post("/ask/stream")
async def ask_question_stream(req: QARequest, current_user: dict = Depends(get_current_user)):
    """流式AI答疑，返回SSE格式。支持深度思考和联网搜索。"""
    _require_llm_config(current_user["id"])

    # 过滤与学习无关的内容（有文件附件时跳过，文件内容可能是学习材料）
    # 多轮对话中跳过学习相关性检查（上下文已建立）
    persisted_history = get_conversation_history(current_user["id"], req.conversation_id, limit=20)
    has_history = bool(persisted_history or (req.history and len(req.history) > 0))
    if (not req.file_text and not has_history
            and not _is_memory_visibility_query(req.question)
            and not qa_service.is_learning_related(req.question)):
        async def _reject_stream():
            msg = "这是一个教学平台，我无法解答你的这个问题。请提出与学习、知识相关的问题。"
            yield f"data: {json.dumps({'content': msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_reject_stream(), media_type="text/event-stream")

    # 如果用户附带了文件内容，注入到上下文并添加提取要点指令
    if req.file_text:
        file_instruction = "\n\n【重要指令】用户上传了一个文件，请完成以下任务：\n1. 提取文件的核心内容和关键要点\n2. 用清晰的结构化格式呈现（如分点、标题）\n3. 只输出与文件内容直接相关的信息，禁止寒暄、禁止评价、禁止追问、禁止补充无关说明"
        req.context = (req.context or "无额外上下文") + f"\n\n【用户上传的文件内容】\n{req.file_text}" + file_instruction

    # 初始化变量（代码路径和非代码路径共用）
    search_results = []
    search_query_rewritten = ""
    rag_sources = None
    tool_bundle = {
        "tool_events": [],
        "search_results": [],
        "search_query": "",
        "rag_sources": [],
        "mind_map": None,
        "learning_analysis": None,
        "context": "",
    }
    messages = []
    temperature = 0.7
    max_tokens = 4096
    # 检测是否为 DeepSeek 模型（支持原生 reasoning_content）
    _user_cfg = _get_user_llm_config(current_user["id"])
    _is_deepseek = _user_cfg and "deepseek" in str(_user_cfg.get("base_url", "")).lower()
    learning_context = build_learning_context(current_user["id"], req.question)

    # 自动检测代码输入
    is_code = qa_service.is_code_input(req.question)
    print(f"[QA-STREAM] is_code={is_code}, question_len={len(req.question)}, question_preview={repr(req.question[:100])}")
    if is_code:
        # 判断是纯代码还是代码+描述
        code_only = _is_pure_code(req.question)

        if code_only:
            system_prompt = """你是一位资深代码审查专家。用户贴了一段代码给你，请做以下事情：

1. 用简短的话概括这段代码的功能
2. 给原代码添加详细的中文注释（直接在代码中以 # 注释形式标注），解释每一部分的作用
3. 如果代码有错误或隐患，指出问题并给出修正版本
4. 如果没有错误，不要输出"是否存在错误""不存在错误"这类自问自答，直接告诉用户代码没问题、可以怎么优化即可

注意：
- 风格自然流畅，像是在 Code Review 中给同事的反馈
- 注释要解释"为什么这样做"，而不只是"做了什么"
"""
        else:
            system_prompt = """你是一位资深代码专家。用户贴了一段代码并附带了对代码的修改要求。

【最重要】用户不是让你分析代码，而是让你按他的要求修改代码。你必须输出修改后的完整代码，而不是分析原代码。

规则：
- 用户说"换一种方式"→ 用不同的实现方式重写这段代码
- 用户说"修改"/"改成xxx"→ 按用户要求改代码，输出改后的完整代码
- 用户说"优化"→ 优化代码并输出优化后的版本
- 用户说"这个代码有问题"→ 指出问题并给出修正后的代码
- 用户问具体问题→ 针对性回答

输出格式：
1. 先简要说明你做了什么修改（1-2句话）
2. 然后给出完整的修改后代码（用 ``` 代码块包裹）
3. 最后简要解释关键改动点

不要只分析不修改。用户要的是修改后的代码！"""

        system_prompt = build_personalized_system_prompt(
            current_user["id"], req.question, system_prompt,
        )
        system_prompt += "\n\n" + learning_context["prompt"]

        # 深度思考：追加思考指令 + 调整参数
        if req.deep_thinking:
            system_prompt = DEEP_THINKING_INSTRUCTION + "\n\n" + system_prompt
            temperature = 0.2
            max_tokens = 8192
        else:
            temperature = 0.4
            max_tokens = 4096

        prompt = req.question
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        print(f"[QA-STREAM-CODE] code_only={code_only}, deep_thinking={req.deep_thinking}, question_len={len(req.question)}")
    else:
        # 构建system prompt
        system_prompt = """你是一位知识渊博、乐于助人的AI导师。请根据用户的问题内容自适应调整回答角色：
- 用户问编程/技术问题时，作为技术专家回答
- 用户问学术/学科问题时，作为学科导师回答
- 用户闲聊或问日常问题时，以友好助手身份回答
- 任何时候都不要说"作为XX导师/专家"之类的开场白，直接回答问题本身。"""

        # 深度思考模式：深度思考模式下将格式指令放在最前面以确保模型遵守
        # DeepSeek reasoner 原生返回 reasoning_content，但 deepseek-chat 不支持
        # 统一使用 【思考过程】...【回答】... 格式标记，前端解析
        if req.deep_thinking:
            system_prompt = DEEP_THINKING_INSTRUCTION + "\n\n" + system_prompt
        else:
            system_prompt += "\n\n注意：直接回答即可，不要输出你的思考过程、不要说你正在做什么、不要以角色自我介绍开头。"

        system_prompt = build_personalized_system_prompt(
            current_user["id"], req.question, system_prompt,
        )
        system_prompt += "\n\n" + learning_context["prompt"]

        # 开关表示“允许模型使用”，真正是否调用由 Function Calling 自主决定。
        if not _is_memory_visibility_query(req.question):
            tool_bundle = await plan_and_execute_tools(
                current_user["id"],
                req.question,
                persisted_history or (req.history or []),
                allow_web=req.enable_search,
                allow_knowledge=req.use_rag,
                allow_analytics=req.enable_learning_analytics,
                allow_mind_map=req.enable_mind_map,
            )
            search_results = tool_bundle["search_results"]
            search_query_rewritten = tool_bundle["search_query"]
            rag_sources = tool_bundle["rag_sources"]
        tool_context = tool_bundle.get("context") or ""

        # 选择Prompt模板
        if req.explanation_level == "beginner":
            from services.ai_service import QA_BEGINNER_PROMPT as prompt_template
        elif req.explanation_level == "advanced":
            from services.ai_service import QA_ADVANCED_PROMPT as prompt_template
        else:
            from services.ai_service import QA_STANDARD_PROMPT as prompt_template

        prompt = prompt_template.format(
            question=req.question,
            question_type=req.question_type,
            context=(req.context or "无额外上下文")
                    + ("\n\n" + tool_context if tool_context else "")
        )
        if tool_context:
            prompt += (
                "\n\n【证据使用规则】只采用与问题直接相关的工具证据；"
                "工具没有覆盖的事实不要编造。联网资料要保留可核查链接；"
                "学情样本不足时必须明确说明证据覆盖度。"
            )

        # 【自进化】注入成功模式 + 学生画像
        try:
            patterns = find_similar_patterns(req.question, top_k=2)
            if patterns:
                pattern_text = "\n\n【参考以下历史高质量回答模式】\n"
                for i, p in enumerate(patterns, 1):
                    pattern_text += f"模式{i}（相似度{p['score']:.2f}）：\n问：{p['question'][:300]}\n答：{p['answer'][:500]}\n\n"
                prompt += pattern_text

            profile = get_student_profile(current_user["id"])
            if profile["weaknesses"] or profile["strengths"]:
                profile_text = f"\n\n【当前学生画像】强项：{', '.join(s['tag'] for s in profile['strengths'][:3]) or '暂无'}；薄弱：{', '.join(w['tag'] for w in profile['weaknesses'][:3]) or '暂无'}。请针对薄弱点重点讲解。"
                prompt += profile_text
        except Exception:
            pass  # 进化注入失败不影响主流程

    # 非代码才构建messages和参数（代码已在上方设置）
    if not qa_service.is_code_input(req.question):
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        # 多轮对话：注入之前的对话历史（最近20条，即10轮）
        effective_history = persisted_history or (req.history or [])
        if effective_history:
            for h in effective_history[-20:]:  # 最多保留最近10轮对话
                role = h.get("role", "user")
                content = h.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        # 当前问题
        messages.append({"role": "user", "content": prompt})

        # 深度思考模式使用更低的temperature和更大的max_tokens
        temperature = 0.42 if req.deep_thinking else 0.7
        max_tokens = 8192 if req.deep_thinking else 4096

    async def _stream_with_search():
        """先发送 RAG 来源/不可用提示和搜索结果，再流式输出 LLM 回答（带心跳保活）"""
        if learning_context.get("available"):
            yield f"data: {json.dumps({'learning_context': public_learning_context(learning_context)}, ensure_ascii=False)}\n\n"
        if tool_bundle.get("tool_events"):
            yield f"data: {json.dumps({'tool_events': tool_bundle['tool_events']}, ensure_ascii=False)}\n\n"
        if rag_sources:
            yield f"data: {json.dumps({'rag_sources': rag_sources}, ensure_ascii=False)}\n\n"
        for event in tool_bundle.get("tool_events") or []:
            if event.get("name") == "knowledge_search" and event.get("status") != "ok":
                yield f"data: {json.dumps({'rag_unavailable': True, 'message': '知识库检索暂不可用，本次回答未使用知识库内容。'}, ensure_ascii=False)}\n\n"
            if event.get("name") == "web_search" and event.get("status") != "ok":
                yield f"data: {json.dumps({'search_unavailable': True, 'message': 'Tavily 高级搜索暂不可用'}, ensure_ascii=False)}\n\n"
        if search_results:
            search_msg = {"search_results": search_results}
            if search_query_rewritten:
                search_msg["search_query"] = search_query_rewritten
            yield f"data: {json.dumps(search_msg, ensure_ascii=False)}\n\n"
        if tool_bundle.get("mind_map"):
            yield f"data: {json.dumps({'mind_map': tool_bundle['mind_map']}, ensure_ascii=False)}\n\n"
        if tool_bundle.get("learning_analysis"):
            yield f"data: {json.dumps({'learning_analysis': tool_bundle['learning_analysis']}, ensure_ascii=False, default=str)}\n\n"

        # 使用队列 + 生产者任务实现心跳保活：
        # - 生产者从 stream_llm 读取 chunk 放入队列
        # - 消费者从队列读取，带 15s 超时 → 超时时发送 SSE 注释心跳
        queue: asyncio.Queue = asyncio.Queue()

        async def _produce():
            try:
                async for chunk in stream_llm(current_user["id"], messages, temperature=temperature,
                                               max_tokens=max_tokens, deep_thinking=req.deep_thinking):
                    await queue.put(('chunk', chunk))
            except Exception as e:
                await queue.put(('error', str(e)))
            finally:
                await queue.put(('done', None))

        producer_task = asyncio.create_task(_produce())
        try:
            while True:
                try:
                    kind, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if kind == 'chunk':
                        yield data
                    elif kind == 'error':
                        yield f"data: {json.dumps({'error': f'AI 响应中断: {data}'}, ensure_ascii=False)}\n\n"
                        break
                    elif kind == 'done':
                        break
                except asyncio.TimeoutError:
                    # 15 秒无 LLM 输出 → 发送心跳注释放防止代理/nginx 断连
                    yield ": heartbeat\n\n"
        finally:
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _stream_with_search(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/history", response_model=APIResponse)
async def get_history(page: int = 1, page_size: int = 20, current_user: dict = Depends(get_current_user)):
    """获取问答历史"""
    result = await qa_service.get_qa_history(current_user["id"], page, page_size)
    return APIResponse(data=result)


@router.get("/export")
async def export_conversations(
    anonymize: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """一键导出当前用户可训练对话；始终过滤 API Key 等秘密。"""
    filename = f"ai-learning-conversations-{current_user['id']}.jsonl"
    return StreamingResponse(
        iter_conversation_jsonl(current_user["id"], anonymize=anonymize),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/conversations", response_model=APIResponse)
async def start_conversation(current_user: dict = Depends(get_current_user)):
    """创建一个中期记忆会话。"""
    return APIResponse(data=create_conversation(current_user["id"]))


@router.get("/conversations", response_model=APIResponse)
async def conversations(current_user: dict = Depends(get_current_user)):
    """获取左侧会话历史。"""
    return APIResponse(data=list_conversations(current_user["id"]))


@router.get("/conversations/current", response_model=APIResponse)
async def current_conversation(current_user: dict = Depends(get_current_user)):
    """刷新页面时续接当前用户最近的中期记忆会话（同时返回对话列表，减少前端请求数）。"""
    conv = get_or_create_current_conversation(current_user["id"])
    conv["_conversations"] = list_conversations(current_user["id"])
    return APIResponse(data=conv)


@router.get("/conversations/{conversation_id}", response_model=APIResponse)
async def conversation_detail(conversation_id: int, current_user: dict = Depends(get_current_user),
                               msg_limit: int = 25, msg_offset: int = 0):
    conversation = get_conversation(current_user["id"], conversation_id, msg_limit, msg_offset)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return APIResponse(data=conversation)


@router.delete("/conversations/{conversation_id}", response_model=APIResponse)
async def remove_conversation(conversation_id: int, current_user: dict = Depends(get_current_user)):
    if not delete_conversation(current_user["id"], conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    return APIResponse(data={"deleted": True, "id": conversation_id})


@router.get("/memory", response_model=APIResponse)
async def memory_overview(current_user: dict = Depends(get_current_user)):
    """返回当前用户的分层记忆和三维掌握度概览。"""
    return APIResponse(data=get_memory_overview(current_user["id"]))


@router.post("/memory/knowledge-detail", response_model=APIResponse)
async def knowledge_point_detail(req: dict, current_user: dict = Depends(get_current_user)):
    """根据长期记忆中的知识点，从历史对话中总结详细讲解。

    Request body: { fact_key, fact_value, category }
    """
    fact_key = str(req.get("fact_key", "") or "").strip()
    fact_value = str(req.get("fact_value", "") or "").strip()
    if not fact_key:
        raise HTTPException(status_code=400, detail="缺少 fact_key")

    # 搜索相关对话
    detail = get_knowledge_point_detail(current_user["id"], fact_key, fact_value)
    if not detail.get("source_messages"):
        return APIResponse(data={
            "fact_key": fact_key,
            "fact_value": fact_value or fact_key,
            "summary": "暂无与此知识点相关的历史对话记录。去智能答疑页面提问吧！",
            "sources": [],
            "conversation_count": 0,
        })

    # 构建 LLM 提示词
    topic = fact_value or fact_key
    context_parts = []
    for msg in detail["source_messages"]:
        role_label = "用户问" if msg["role"] == "user" else "AI答"
        context_parts.append(f"[{msg['session']}] {role_label}: {msg['content']}")

    context_text = "\n\n---\n\n".join(context_parts)
    system_prompt = (
        "你是一位AI学习助教。请根据用户与AI的历史对话记录，针对「{topic}」这个知识点，"
        "撰写一份详细的讲解。要求：\n"
        "1. 从历史对话中提取关于该知识点的核心概念、关键见解和重要细节\n"
        "2. 整合成结构清晰的讲解（可分点、分段）\n"
        "3. 语言通俗易懂，适合学习回顾\n"
        "4. 控制在800字以内\n"
        "5. 使用Markdown格式\n"
        "6. 不要简单复制粘贴对话内容，而是提炼总结"
    ).format(topic=topic)

    user_prompt = f"以下是与「{topic}」相关的历史对话记录，请基于这些内容撰写详细讲解：\n\n{context_text[:8000]}"

    try:
        summary = await call_llm(
            user_id=current_user["id"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=2000,
        )
    except HTTPException:
        raise
    except Exception as e:
        summary = f"生成讲解时出错：{str(e)}"

    return APIResponse(data={
        "fact_key": fact_key,
        "fact_value": fact_value or fact_key,
        "summary": summary,
        "sources": detail.get("sessions", []),
        "conversation_count": detail.get("conversation_count", 0),
        "source_messages_count": len(detail.get("source_messages", [])),
    })


@router.delete("/history", response_model=APIResponse)
async def clear_history(current_user: dict = Depends(get_current_user)):
    """清空当前用户的所有问答历史"""
    count = await qa_service.clear_qa_history(current_user["id"])
    return APIResponse(data={"deleted_count": count, "message": f"已清空 {count} 条问答历史"})


@router.delete("/history/{qa_id}", response_model=APIResponse)
async def delete_history(qa_id: int, current_user: dict = Depends(get_current_user)):
    """删除单条问答历史"""
    ok = await qa_service.delete_qa_history(current_user["id"], qa_id)
    if not ok:
        return APIResponse(code=404, message="记录不存在或无权删除", data=None)
    return APIResponse(data={"deleted": True, "id": qa_id})


@router.post("/save", response_model=APIResponse)
async def save_qa(req: QASaveRequest, current_user: dict = Depends(get_current_user)):
    """保存流式问答记录（流式响应结束后由前端调用）"""
    qa_id = await qa_service.save_qa_history(
        user_id=current_user["id"],
        question=req.question,
        answer=req.answer,
        question_type=req.question_type,
        explanation_level=req.explanation_level,
        conversation_id=req.conversation_id,
        rag_sources=req.rag_sources,
        search_results=req.search_results,
        search_query=req.search_query,
        tool_events=req.tool_events,
        mind_map=req.mind_map,
        learning_analysis=req.learning_analysis,
    )
    # 获取实际使用的 conversation_id（可能在 save 过程中新建）
    actual_conversation_id = req.conversation_id
    if not actual_conversation_id:
        conn = get_db()
        row = conn.execute(
            "SELECT session_id FROM conversation_messages WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (current_user["id"],)
        ).fetchone()
        conn.close()
        if row:
            actual_conversation_id = row["session_id"]
    # 【自进化】记录学习活动
    try:
        tags = qa_service.identify_knowledge_tags(req.question)
        record_qa_activity(current_user["id"], tags)
    except Exception:
        pass
    return APIResponse(data={"id": qa_id, "conversation_id": actual_conversation_id, "message": "保存成功"})


@router.post("/save-user-message", response_model=APIResponse)
async def save_user_msg(req: QASaveRequest, current_user: dict = Depends(get_current_user)):
    """保存用户消息（在流式生成开始前调用，防止刷新丢失）"""
    tags = identify_knowledge_tags_standalone(req.question)
    result = save_user_message(
        user_id=current_user["id"],
        conversation_id=req.conversation_id,
        question=req.question,
        knowledge_tags=tags,
    )
    return APIResponse(data={
        "conversation_id": result["conversation_id"],
        "message_id": result["message_id"],
        "message": "用户消息已保存",
        "memory_updates": result.get("memory_updates") or [],
    })


@router.post("/save-assistant-message", response_model=APIResponse)
async def save_assistant_msg(req: QASaveRequest, current_user: dict = Depends(get_current_user)):
    """保存助手消息（流式生成完成后调用）"""
    if not req.conversation_id:
        raise HTTPException(status_code=400, detail="缺少 conversation_id")
    tags = qa_service.identify_knowledge_tags(req.question)
    result = save_assistant_message(
        user_id=current_user["id"],
        conversation_id=req.conversation_id,
        answer=req.answer,
        knowledge_tags=tags,
        rag_sources=req.rag_sources,
        search_results=req.search_results,
        search_query=req.search_query or "",
        tool_events=req.tool_events,
        mind_map=req.mind_map,
        learning_analysis=req.learning_analysis,
        memory_updates=req.memory_updates,
    )
    # 【自进化】记录学习活动
    try:
        record_qa_activity(current_user["id"], tags)
    except Exception:
        pass
    return APIResponse(data={
        "message_id": result["message_id"],
        "conversation_id": req.conversation_id,
        "message": "助手消息已保存",
    })


@router.post("/memory", response_model=APIResponse)
async def add_memory(req: dict, current_user: dict = Depends(get_current_user)):
    try:
        item = create_memory_fact(
            current_user["id"],
            str(req.get("category") or "profile"),
            str(req.get("fact_key") or ""),
            str(req.get("fact_value") or ""),
        )
        return APIResponse(data=item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/memory/{fact_id}", response_model=APIResponse)
async def edit_memory(
    fact_id: int,
    req: dict,
    current_user: dict = Depends(get_current_user),
):
    try:
        item = update_memory_fact(
            current_user["id"],
            fact_id,
            str(req.get("category") or ""),
            str(req.get("fact_key") or ""),
            str(req.get("fact_value") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return APIResponse(data=item)


@router.delete("/memory/{fact_id}", response_model=APIResponse)
async def remove_memory(fact_id: int, current_user: dict = Depends(get_current_user)):
    if not delete_memory_fact(current_user["id"], fact_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return APIResponse(data={"deleted": True, "id": fact_id})


@router.get("/mind-maps/{map_id}", response_model=APIResponse)
async def mind_map_detail(map_id: int, current_user: dict = Depends(get_current_user)):
    item = get_mind_map(current_user["id"], map_id)
    if not item:
        raise HTTPException(status_code=404, detail="思维导图不存在")
    return APIResponse(data=item)


@router.post("/feedback", response_model=APIResponse)
async def submit_feedback(req: QAFeedbackRequest, current_user: dict = Depends(get_current_user)):
    """提交问答反馈（👍/👎），触发自进化模式提取"""
    from database import get_db
    conn = get_db()
    conn.execute(
        "INSERT INTO qa_feedback (qa_history_id, user_id, rating, feedback_text) VALUES (?, ?, ?, ?)",
        (req.qa_history_id, current_user["id"], req.rating, req.feedback_text)
    )
    conn.commit()
    conn.close()
    # 触发模式提取
    pattern_id = extract_pattern(req.qa_history_id)
    return APIResponse(data={
        "message": "反馈已记录",
        "pattern_extracted": pattern_id is not None,
        "pattern_id": pattern_id
    })


@router.post("/code-run", response_model=APIResponse)
async def run_code(req: CodeRunRequest, current_user: dict = Depends(get_current_user)):
    """运行QA中的代码片段，支持 Python/JavaScript/C/C++/Java"""
    # 语言配置：{ 规范名: (文件后缀, [编译命令], [执行命令]) }
    LANG_CONFIG = {
        "python":     ("py",   None,                              ["python", "{src}"]),
        "py":         ("py",   None,                              ["python", "{src}"]),
        "python3":    ("py",   None,                              ["python", "{src}"]),
        "javascript": ("js",   None,                              ["node", "{src}"]),
        "js":         ("js",   None,                              ["node", "{src}"]),
        "node":       ("js",   None,                              ["node", "{src}"]),
        "c":          ("c",    ["gcc", "-o", "{exe}", "{src}"],  ["{exe}"]),
        "cpp":        ("cpp",  ["g++", "-o", "{exe}", "{src}"],  ["{exe}"]),
        "c++":        ("cpp",  ["g++", "-o", "{exe}", "{src}"],  ["{exe}"]),
        "cplusplus":  ("cpp",  ["g++", "-o", "{exe}", "{src}"],  ["{exe}"]),
        "java":       ("java", ["javac", "{src}"],                ["java", "-cp", "{dir}", "{classname}"]),
    }

    lang = req.language.strip().lower()
    cfg = LANG_CONFIG.get(lang)
    if not cfg:
        return APIResponse(data={
            "stdout": "",
            "stderr": f"不支持的语言: {req.language}。支持的类型: python, javascript, c, cpp, java",
            "exit_code": -1,
            "status": "error",
            "execution_time": 0
        })

    ext, compile_cmd, run_cmd = cfg

    # Java: 从源码中提取 public class 名用作文件名
    if lang in ("java",):
        import re
        class_match = re.search(r'public\s+class\s+(\w+)', req.code)
        java_classname = class_match.group(1) if class_match else "Main"

    start_time = time.time()
    src_path = None
    exe_path = None

    try:
        work_dir = tempfile.mkdtemp()

        # Java: 文件名必须与 public class 名一致
        if lang in ("java",):
            src_path = os.path.join(work_dir, f"{java_classname}.{ext}")
        else:
            src_path = os.path.join(work_dir, f"main.{ext}")

        # 写入源代码
        with open(src_path, 'w', encoding='utf-8') as f:
            f.write(req.code)

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'

        # 编译阶段（C/C++/Java）
        if compile_cmd:
            exe_path = os.path.join(work_dir, "program.exe")
            compile_args = [
                arg.format(src=src_path, exe=exe_path, dir=work_dir, classname="Main")
                for arg in compile_cmd
            ]
            comp_result = subprocess.run(
                compile_args,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=30, env=env, cwd=work_dir
            )
            if comp_result.returncode != 0:
                execution_time = round(time.time() - start_time, 3)
                return APIResponse(data={
                    "stdout": "",
                    "stderr": f"编译失败:\n{(comp_result.stderr or '').strip()}\n{(comp_result.stdout or '').strip()}",
                    "exit_code": comp_result.returncode,
                    "status": "error",
                    "execution_time": execution_time
                })

        # 执行阶段
        if lang in ("java",):
            run_args = ["java", "-cp", work_dir, java_classname]
        elif compile_cmd:
            run_args = [
                arg.format(src=src_path, exe=exe_path, dir=work_dir)
                for arg in run_cmd
            ]
        else:
            run_args = [
                arg.format(src=src_path, exe=exe_path, dir=work_dir)
                for arg in run_cmd
            ]

        result = subprocess.run(
            run_args,
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=15, env=env, cwd=work_dir
        )

        execution_time = round(time.time() - start_time, 3)
        status = "success" if result.returncode == 0 else "error"

        return APIResponse(data={
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
            "exit_code": result.returncode,
            "status": status,
            "execution_time": execution_time
        })

    except subprocess.TimeoutExpired:
        execution_time = round(time.time() - start_time, 3)
        return APIResponse(data={
            "stdout": "",
            "stderr": "代码执行超时（超过15秒），请检查是否存在死循环或耗时操作",
            "exit_code": -1,
            "status": "timeout",
            "execution_time": execution_time
        })
    except Exception as e:
        execution_time = round(time.time() - start_time, 3)
        return APIResponse(data={
            "stdout": "",
            "stderr": f"代码执行异常: {str(e)}",
            "exit_code": -1,
            "status": "error",
            "execution_time": execution_time
        })
    finally:
        # 清理临时文件
        import shutil
        if work_dir:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


@router.post("/evolve", response_model=APIResponse)
async def trigger_evolve(current_user: dict = Depends(get_current_user)):
    """手动触发自进化：扫描近期问答，聚类生成新模式，淘汰过期模式"""
    report = evolve()
    return APIResponse(data=report)
