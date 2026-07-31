"""QA 工具注册表与一次式 Function Calling 调度。"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import RAG_TOP_K
from database import get_db
from services.ai_service import _build_llm, call_llm, extract_json_object
from services.learning_analytics_service import analyze_learning_data
from services.search_service import TavilyUnavailableError, tavily_advanced_search


TOOL_PLANNER_PROMPT = """你是 AI 智能体学习平台的工具路由器。可用工具只是权限，不代表必须调用。

决策规则：
1. 普通知识解释、代码分析、上下文已经足够时，直接不调用工具。
2. 只有问题明确需要最新信息、外部网页、论文动态或事实核实时，才调用 web_search。
3. AI 智能体或数据挖掘课程知识，且内部教材能提高准确性时，调用 knowledge_search。
4. 只有用户询问“我的”学习情况、成绩、薄弱点、学习趋势时，调用 analyze_learning_data。
5. 只有用户明确要求思维导图、知识树、框架图，或回答确实需要结构化全景时，调用 generate_mind_map。
6. 工具参数必须是精确、无歧义的查询；“记忆”默认指 AI Agent memory，不是语言学或心理学。
7. 可以一次调用多个互补工具，但不要调用内容重叠的工具，也不要为了展示能力而调用。

你只负责决定是否调用工具。不要在这一步输出长篇答案。"""


def _tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def build_tool_schemas(
    *,
    allow_web: bool,
    allow_knowledge: bool,
    allow_analytics: bool,
    allow_mind_map: bool,
) -> list[dict]:
    tools: list[dict] = []
    if allow_web:
        tools.append(_tool_schema(
            "web_search",
            "使用 Tavily advanced 搜索少量高相关网页。仅用于最新/外部/需核实的信息，不用于稳定概念。",
            {
                "query": {
                    "type": "string",
                    "description": "精确搜索词，保留 AI Agent 等领域限定和必要的中英文术语",
                }
            },
            ["query"],
        ))
    if allow_knowledge:
        tools.append(_tool_schema(
            "knowledge_search",
            "检索平台内部教材。知识库仅覆盖 AI 智能体与数据挖掘课程。",
            {
                "query": {"type": "string", "description": "要在课程知识库中检索的完整问题"},
                "top_k": {"type": "integer", "minimum": 2, "maximum": 6, "default": 4},
            },
            ["query"],
        ))
    if allow_analytics:
        tools.append(_tool_schema(
            "analyze_learning_data",
            "通过只读 NL2SQL 和固定聚合分析当前学生自己的学习数据。仅用于个性化学情问题。",
            {
                "question": {
                    "type": "string",
                    "description": "需要用当前学生数据回答的具体分析问题",
                }
            },
            ["question"],
        ))
    if allow_mind_map:
        tools.append(_tool_schema(
            "generate_mind_map",
            "生成可视化思维导图结构。只在用户要求导图/知识树或结构化全景时使用。",
            {
                "topic": {"type": "string", "description": "思维导图中心主题"},
                "depth": {"type": "integer", "minimum": 2, "maximum": 3, "default": 3},
            },
            ["topic"],
        ))
    return tools


def _knowledge_search_sync(user_id: int, query: str, top_k: int) -> dict[str, Any]:
    from services.rag_service import get_runtime_rag_service

    try:
        rag = get_runtime_rag_service(user_id)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    chunks = rag.retrieve(query, top_k=max(2, min(int(top_k or RAG_TOP_K), 6)))
    return {
        "query": query,
        "context": rag.format_context(chunks) if chunks else "",
        "sources": rag.get_sources(chunks) if chunks else [],
    }


def _clean_mind_map_node(node: Any, *, depth: int = 0, budget: list[int] | None = None) -> dict | None:
    if budget is None:
        budget = [30]
    if budget[0] <= 0 or depth > 3 or not isinstance(node, dict):
        return None
    label = str(node.get("label") or node.get("name") or "").strip()[:80]
    if not label:
        return None
    budget[0] -= 1
    children = []
    for child in node.get("children") or []:
        cleaned = _clean_mind_map_node(child, depth=depth + 1, budget=budget)
        if cleaned:
            children.append(cleaned)
    return {"label": label, "children": children}


async def _generate_mind_map(user_id: int, topic: str, depth: int) -> dict[str, Any]:
    response = await call_llm(
        user_id,
        [
            {
                "role": "system",
                "content": (
                    "你是课程知识结构设计器。只输出 JSON 对象，节点字段为 label 和 children；"
                    "总节点不超过30，每层2-5个子节点，不写空泛套话。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"为“{str(topic)[:120]}”生成深度为{max(2, min(int(depth or 3), 3))}的"
                    "AI课程思维导图。格式："
                    '{"title":"主题","root":{"label":"主题","children":[...]}}'
                ),
            },
        ],
        temperature=0.2,
        max_tokens=1800,
    )
    parsed = extract_json_object(response)
    root = _clean_mind_map_node(parsed.get("root") or parsed)
    if not root:
        root = {"label": str(topic)[:80] or "知识导图", "children": []}
    from services.mind_map_service import persist_mind_map

    return await asyncio.to_thread(
        persist_mind_map,
        user_id,
        str(parsed.get("title") or topic)[:100],
        root,
    )


async def _execute_tool(user_id: int, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "web_search":
        return await tavily_advanced_search(user_id, str(args.get("query") or ""), max_results=5)
    if name == "knowledge_search":
        return await asyncio.to_thread(
            _knowledge_search_sync,
            user_id,
            str(args.get("query") or ""),
            int(args.get("top_k") or RAG_TOP_K),
        )
    if name == "analyze_learning_data":
        return await analyze_learning_data(user_id, str(args.get("question") or "分析我的学习情况"))
    if name == "generate_mind_map":
        return await _generate_mind_map(
            user_id,
            str(args.get("topic") or "AI 智能体"),
            int(args.get("depth") or 3),
        )
    raise ValueError("未注册工具")


async def plan_and_execute_tools(
    user_id: int,
    question: str,
    history: list[dict] | None = None,
    *,
    allow_web: bool = True,
    allow_knowledge: bool = True,
    allow_analytics: bool = True,
    allow_mind_map: bool = True,
) -> dict[str, Any]:
    schemas = build_tool_schemas(
        allow_web=allow_web,
        allow_knowledge=allow_knowledge,
        allow_analytics=allow_analytics,
        allow_mind_map=allow_mind_map,
    )
    result: dict[str, Any] = {
        "tool_events": [],
        "search_results": [],
        "search_query": "",
        "rag_sources": [],
        "mind_map": None,
        "learning_analysis": None,
        "context": "",
    }
    if not schemas:
        return result

    llm = _build_llm(user_id, temperature=0.0, max_tokens=700, request_timeout=60.0)
    planner = llm.bind_tools(schemas, tool_choice="auto")
    messages = [SystemMessage(content=TOOL_PLANNER_PROMPT)]
    for item in (history or [])[-6:]:
        role = item.get("role")
        content = str(item.get("content") or "")[:2000]
        if role == "user":
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=str(question)[:4000]))

    try:
        decision = await planner.ainvoke(messages)
        calls = list(getattr(decision, "tool_calls", None) or [])[:4]
    except Exception:
        return result
    if not calls:
        return result

    async def run(call: dict) -> tuple[dict, dict | None]:
        name = str(call.get("name") or "")
        args = call.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        started = time.perf_counter()
        event = {
            "tool_call_id": str(call.get("id") or ""),
            "name": name,
            "arguments": args,
            "status": "ok",
        }
        try:
            payload = await _execute_tool(user_id, name, args)
            event["duration_ms"] = int((time.perf_counter() - started) * 1000)
            event["result_count"] = len(payload.get("results") or payload.get("sources") or [])
            return event, payload
        except TavilyUnavailableError:
            event.update({
                "status": "unavailable",
                "message": "Tavily 高级搜索暂不可用",
                "duration_ms": int((time.perf_counter() - started) * 1000),
            })
            return event, None
        except Exception as exc:
            event.update({
                "status": "error",
                "message": str(exc)[:160],
                "duration_ms": int((time.perf_counter() - started) * 1000),
            })
            return event, None

    executed = await asyncio.gather(*(run(call) for call in calls))
    context_blocks: list[str] = []
    for event, payload in executed:
        result["tool_events"].append(event)
        if not payload:
            continue
        if event["name"] == "web_search":
            result["search_results"] = payload.get("results") or []
            result["search_query"] = payload.get("query") or ""
            context_blocks.append("【Tavily 高级搜索证据】\n" + json.dumps(
                result["search_results"], ensure_ascii=False,
            ))
        elif event["name"] == "knowledge_search":
            result["rag_sources"] = payload.get("sources") or []
            if payload.get("context"):
                context_blocks.append("【课程知识库证据】\n" + payload["context"])
        elif event["name"] == "analyze_learning_data":
            result["learning_analysis"] = payload
            context_blocks.append("【当前学生只读学情数据】\n" + json.dumps(
                payload, ensure_ascii=False, default=str,
            ))
        elif event["name"] == "generate_mind_map":
            result["mind_map"] = payload
            context_blocks.append(
                "【已生成思维导图】回答正文不要重复整张导图，只需解释关键结构。\n"
                + json.dumps(payload, ensure_ascii=False)
            )
    result["context"] = "\n\n".join(block[:16000] for block in context_blocks)
    return result
