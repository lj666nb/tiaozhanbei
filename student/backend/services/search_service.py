"""Tavily 高级搜索与轻量质量控制。

这不是 Deep Research 流水线：每次最多取少量结果，在进入模型上下文前完成
查询规范化、语言过滤、URL/内容去重、相关度与来源可信度重排。
"""
from __future__ import annotations

import hashlib
import os
import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

import httpx

from database import get_db


TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
MIN_TAVILY_SCORE = 0.35

HIGH_TRUST_SUFFIXES = (
    ".gov", ".edu", ".ac.cn", ".org",
    "arxiv.org", "acm.org", "ieee.org", "nature.com", "science.org",
    "docs.python.org", "openai.com", "microsoft.com", "github.com",
    "huggingface.co", "langchain.com", "tavily.com",
)


class TavilyUnavailableError(RuntimeError):
    """Tavily 未配置或暂时不可用。"""


def get_tavily_api_key(user_id: int) -> str:
    """优先读取用户私有配置，其次读取服务端环境变量。"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT search_api_key FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row and row["search_api_key"]:
        return str(row["search_api_key"]).strip()
    return os.getenv("TAVILY_API_KEY", "").strip()


def tavily_is_configured(user_id: int) -> bool:
    return bool(get_tavily_api_key(user_id))


def rewrite_search_query(question: str) -> str:
    """确定性轻量改写，避免为了改写再消耗一次模型调用。"""
    query = re.sub(
        r"(请|麻烦|能不能|可以不可以|帮我|给我|我想|有没有|查一下|搜一下|搜索一下)",
        " ",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s+", " ", query).strip(" ，。！？?；;")

    # 教学平台中的歧义词固定到 AI 语境，防止 memory/agent 被搜到语言学等领域。
    lowered = query.lower()
    if ("智能体" in query or "agent" in lowered) and ("记忆" in query or "memory" in lowered):
        if not any(token in lowered for token in ("short-term", "long-term", "短期", "长期")):
            query += " AI Agent 短期记忆 长期记忆 memory architecture"
    elif query in {"记忆", "memory"}:
        query = "AI Agent 短期记忆 长期记忆 memory architecture"
    return query[:300] or str(question or "")[:300]


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def _domain_trust(url: str) -> float:
    domain = _domain(url)
    if any(domain == suffix or domain.endswith(suffix) for suffix in HIGH_TRUST_SUFFIXES):
        return 0.95
    if url.lower().startswith("https://"):
        return 0.62
    return 0.45


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _looks_japanese(text: str) -> bool:
    text = text or ""
    kana = len(re.findall(r"[\u3040-\u30ff]", text))
    visible = len(re.sub(r"\s+", "", text))
    return kana >= 3 and kana / max(visible, 1) > 0.025


def _tokens(text: str) -> set[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", (text or "").lower())
    words = {word for word in normalized.split() if len(word) >= 2}
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    words.update(chinese[i:i + 2] for i in range(max(0, len(chinese) - 1)))
    return words


def _lexical_relevance(query: str, result: dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    result_tokens = _tokens(
        f"{result.get('title', '')} {result.get('content', '')} {result.get('raw_content', '')}"
    )
    return len(query_tokens & result_tokens) / max(1, min(len(query_tokens), 12))


def _content_fingerprint(result: dict[str, Any]) -> str:
    text = re.sub(
        r"\s+", " ",
        f"{result.get('title', '')} {result.get('content', '')}".lower(),
    ).strip()
    return hashlib.sha256(text[:1200].encode("utf-8")).hexdigest()


def _is_near_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_text = re.sub(r"\s+", " ", f"{left.get('title', '')} {left.get('content', '')}".lower())
    right_text = re.sub(r"\s+", " ", f"{right.get('title', '')} {right.get('content', '')}".lower())
    if not left_text or not right_text:
        return False
    return SequenceMatcher(None, left_text[:1200], right_text[:1200]).ratio() >= 0.82


def filter_search_results(
    query: str,
    raw_results: list[dict[str, Any]],
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """对 Tavily 结果做小规模、低延迟的质量过滤与重排。"""
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    chinese_query = _contains_chinese(query)

    for raw in raw_results:
        url = str(raw.get("url") or "").strip()
        title = str(raw.get("title") or "").strip()
        content = str(raw.get("content") or raw.get("snippet") or "").strip()
        if not url or not title or url in seen_urls:
            continue
        if chinese_query and _looks_japanese(f"{title} {content}"):
            continue

        candidate = {
            "title": title[:300],
            "url": url,
            "snippet": content[:1200],
            "score": round(float(raw.get("score") or 0.0), 4),
            "source": _domain(url),
        }
        fingerprint = _content_fingerprint(candidate)
        if fingerprint in seen_fingerprints:
            continue
        if any(_is_near_duplicate(candidate, kept) for kept in candidates):
            continue

        lexical = _lexical_relevance(query, raw)
        tavily_score = float(raw.get("score") or 0.0)
        trust = _domain_trust(url)
        if tavily_score < MIN_TAVILY_SCORE and lexical < 0.12:
            continue

        candidate["quality"] = {
            "relevance": round(tavily_score, 4),
            "lexical_match": round(lexical, 4),
            "source_trust": round(trust, 4),
        }
        candidate["_rank"] = tavily_score * 0.72 + min(lexical, 1.0) * 0.12 + trust * 0.16
        candidates.append(candidate)
        seen_urls.add(url)
        seen_fingerprints.add(fingerprint)

    candidates.sort(key=lambda item: item["_rank"], reverse=True)
    for item in candidates:
        item.pop("_rank", None)
    return candidates[:max(1, min(max_results, 8))]


async def tavily_advanced_search(
    user_id: int,
    question: str,
    *,
    max_results: int = 5,
) -> dict[str, Any]:
    api_key = get_tavily_api_key(user_id)
    if not api_key:
        raise TavilyUnavailableError("Tavily 高级搜索暂不可用")

    query = rewrite_search_query(question)
    payload = {
        "api_key": api_key,
        "query": query,
        "topic": "general",
        "search_depth": "advanced",
        "max_results": min(max(max_results * 2, 6), 10),
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(TAVILY_SEARCH_ENDPOINT, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise TavilyUnavailableError("Tavily 高级搜索暂不可用") from exc

    results = filter_search_results(query, data.get("results") or [], max_results=max_results)
    return {
        "provider": "tavily",
        "search_depth": "advanced",
        "query": query,
        "results": results,
    }
