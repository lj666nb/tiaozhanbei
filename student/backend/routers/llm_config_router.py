"""用户LLM配置路由 — 支持用户自行配置API Key/Base URL/模型"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth import get_current_user
from schemas import APIResponse, LLMConfigRequest, LLMConfigResponse
from database import get_db
from datetime import datetime

router = APIRouter()


class EmbeddingConfigRequest(BaseModel):
    embedding_api_key: str = ""
    embedding_provider: str = "siliconflow"
    embedding_model: str = "BAAI/bge-large-zh-v1.5"


def _mask_api_key(key: str) -> str:
    """对API Key做脱敏处理，仅显示前4位和后4位"""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


@router.get("", response_model=APIResponse)
async def get_llm_config(current_user: dict = Depends(get_current_user)):
    """获取当前用户的LLM配置（API Key脱敏）"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM user_llm_config WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()
    conn.close()

    if row:
        r = dict(row)
        return APIResponse(data=LLMConfigResponse(
            provider=r.get("provider", "openai"),
            api_key=_mask_api_key(r.get("api_key", "")),
            base_url=r.get("base_url", "https://api.openai.com"),
            model_name=r.get("model_name", "gpt-4o"),
            temperature=r.get("temperature", 0.7),
            max_tokens=r.get("max_tokens", 4096),
            is_configured=bool(r.get("api_key")),
            image_api_key=_mask_api_key(r.get("image_api_key", "")),
            embedding_api_key=_mask_api_key(r.get("embedding_api_key", "")),
            embedding_provider=r.get("embedding_provider", "siliconflow"),
            embedding_model=r.get("embedding_model", "BAAI/bge-large-zh-v1.5"),
            search_api_key=_mask_api_key(r.get("search_api_key", "")),
        ).model_dump())
    else:
        return APIResponse(data=LLMConfigResponse(is_configured=False).model_dump())


@router.put("", response_model=APIResponse)
async def save_llm_config(req: LLMConfigRequest, current_user: dict = Depends(get_current_user)):
    """保存/更新用户的LLM配置"""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM user_llm_config WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()

    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            """UPDATE user_llm_config
               SET provider=?, api_key=?, base_url=?, model_name=?,
                   temperature=?, max_tokens=?, image_api_key=?,
                   embedding_api_key=?, embedding_provider=?, embedding_model=?,
                   search_api_key=?, updated_at=?
               WHERE user_id=?""",
            (req.provider, req.api_key, req.base_url, req.model_name,
             req.temperature, req.max_tokens, req.image_api_key or "",
             req.embedding_api_key or "", req.embedding_provider or "siliconflow",
             req.embedding_model or "BAAI/bge-large-zh-v1.5",
             req.search_api_key or "", now, current_user["id"])
        )
    else:
        conn.execute(
            """INSERT INTO user_llm_config
               (user_id, provider, api_key, base_url, model_name, temperature, max_tokens, image_api_key,
                embedding_api_key, embedding_provider, embedding_model, search_api_key, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (current_user["id"], req.provider, req.api_key, req.base_url,
             req.model_name, req.temperature, req.max_tokens, req.image_api_key or "",
             req.embedding_api_key or "", req.embedding_provider or "siliconflow",
             req.embedding_model or "BAAI/bge-large-zh-v1.5",
             req.search_api_key or "", now)
        )
    conn.commit()
    conn.close()

    return APIResponse(data={
        "message": "LLM配置已保存",
        "model_name": req.model_name,
        "base_url": req.base_url,
        "is_configured": bool(req.api_key)
    })


@router.put("/embedding", response_model=APIResponse)
async def save_embedding_config(req: EmbeddingConfigRequest, current_user: dict = Depends(get_current_user)):
    """仅更新嵌入（Embedding）配置，不影响 LLM 对话配置"""
    embedding_key = req.embedding_api_key.strip()
    if embedding_key and not embedding_key.startswith("sk-"):
        return APIResponse(code=400, message="SiliconFlow API Key 应以 sk- 开头", data=None)
    if req.embedding_provider != "siliconflow" or req.embedding_model != "BAAI/bge-large-zh-v1.5":
        return APIResponse(
            code=400,
            message="当前知识库固定使用 SiliconFlow 的 BAAI/bge-large-zh-v1.5，不能切换向量模型",
            data=None,
        )

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM user_llm_config WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()

    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            """UPDATE user_llm_config
               SET embedding_api_key=?, embedding_provider=?, embedding_model=?, updated_at=?
               WHERE user_id=?""",
            (embedding_key, req.embedding_provider, req.embedding_model, now, current_user["id"])
        )
    else:
        conn.execute(
            """INSERT INTO user_llm_config
               (user_id, embedding_api_key, embedding_provider, embedding_model, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (current_user["id"], embedding_key, req.embedding_provider, req.embedding_model, now)
        )
    conn.commit()
    conn.close()

    return APIResponse(data={
        "message": "SiliconFlow BGE API Key 已保存" if embedding_key else "嵌入配置已清除",
        "embedding_provider": req.embedding_provider,
        "embedding_model": req.embedding_model,
        "is_configured": bool(embedding_key),
    })


class SearchConfigRequest(BaseModel):
    search_api_key: str = ""


@router.put("/search", response_model=APIResponse)
async def save_search_config(req: SearchConfigRequest, current_user: dict = Depends(get_current_user)):
    """仅更新 Tavily 配置；空值表示清除，不影响 LLM 对话配置。"""
    search_key = req.search_api_key.strip()
    if search_key and not search_key.startswith("tvly-"):
        return APIResponse(code=400, message="请输入有效的 Tavily API Key（应以 tvly- 开头）", data=None)

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM user_llm_config WHERE user_id = ?",
        (current_user["id"],)
    ).fetchone()

    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            """UPDATE user_llm_config
               SET search_api_key=?, updated_at=?
               WHERE user_id=?""",
            (search_key, now, current_user["id"])
        )
    elif search_key:
        conn.execute(
            """INSERT INTO user_llm_config
               (user_id, search_api_key, updated_at)
               VALUES (?, ?, ?)""",
            (current_user["id"], search_key, now)
        )
    conn.commit()
    conn.close()

    return APIResponse(data={
        "message": "Tavily API Key 已保存" if search_key else "Tavily 配置已清除",
        "provider": "tavily",
        "search_depth": "advanced",
        "is_configured": bool(search_key),
    })


@router.delete("", response_model=APIResponse)
async def reset_llm_config(current_user: dict = Depends(get_current_user)):
    """重置用户的LLM配置为系统默认"""
    conn = get_db()
    conn.execute(
        "DELETE FROM user_llm_config WHERE user_id = ?",
        (current_user["id"],)
    )
    conn.commit()
    conn.close()
    return APIResponse(data={"message": "已重置为系统默认配置"})
