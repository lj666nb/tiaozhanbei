"""嵌入服务 — SiliconFlow / DashScope 云端嵌入。

生产环境：SiliconFlow BAAI/bge-large-zh-v1.5 API（1024维）
备用环境：阿里云 DashScope text-embedding-v3（1024维）
"""

import os
import hashlib
import logging
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional

# 文本截断保护：BGE max_seq_length=512 tokens ≈ 1000-1500 中文字符
MAX_TEXT_CHARS = 2400

logger = logging.getLogger(__name__)


# ============================================================
# 嵌入后端抽象
# ============================================================

class EmbeddingBackend:
    """嵌入后端基类"""
    DIMENSION = 1024
    NAME = "base"

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_single(self, text: str) -> List[float]:
        results = self.embed([text])
        return results[0]

    def runtime_info(self) -> dict:
        return {"backend": self.NAME}


# ============================================================
# 阿里云 DashScope 后端（生产环境）
# ============================================================

class DashScopeBackend(EmbeddingBackend):
    """阿里云 text-embedding-v3 云端嵌入"""
    NAME = "dashscope-text-embedding-v3"
    BATCH_SIZE = 25  # DashScope 单次最大 25 条

    def __init__(self, api_key: str, model: str = "text-embedding-v3"):
        import dashscope
        dashscope.api_key = api_key
        self.model = model
        self._dashscope = dashscope

    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入，自动分批"""
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i:i + self.BATCH_SIZE]
            for text in batch:
                resp = self._dashscope.TextEmbedding.call(
                    model=self.model,
                    input=text
                )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"DashScope embedding failed: code={resp.status_code}, "
                        f"message={getattr(resp, 'message', 'unknown')}"
                    )
                emb = resp.output['embeddings'][0]['embedding']
                all_embeddings.append(emb)

        return all_embeddings


class SiliconFlowBGEBackend(EmbeddingBackend):
    """SiliconFlow 上与本地知识库完全同模型的 BGE 查询嵌入。"""

    NAME = "bge-large-zh-v1.5"
    MODEL = "BAAI/bge-large-zh-v1.5"
    BATCH_SIZE = 32

    def __init__(
        self,
        api_key: str,
        model: str = MODEL,
        base_url: str = "https://api.siliconflow.cn/v1",
    ):
        from openai import OpenAI

        if not api_key:
            raise ValueError("SiliconFlow BGE 嵌入需要 API Key")
        if model != self.MODEL:
            raise ValueError(
                f"知识库由 {self.MODEL} 构建，查询端禁止切换为 {model}，否则向量空间不一致。"
            )
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = OpenAI(base_url=self.base_url, api_key=api_key)

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings: List[List[float]] = []
        for index in range(0, len(texts), self.BATCH_SIZE):
            batch = [_truncate_text(text, MAX_TEXT_CHARS) for text in texts[index:index + self.BATCH_SIZE]]
            response = self.client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            batch_embeddings = [item.embedding for item in ordered]
            if any(len(vector) != self.DIMENSION for vector in batch_embeddings):
                raise RuntimeError(
                    f"SiliconFlow {self.model} 返回了非 {self.DIMENSION} 维向量，已拒绝写入或查询。"
                )
            embeddings.extend(batch_embeddings)
        return embeddings

    def runtime_info(self) -> dict:
        return {
            "backend": self.NAME,
            "provider": "siliconflow",
            "model": self.model,
            "base_url": self.base_url,
            "execution": "remote_api",
        }


# ============================================================
# 嵌入缓存层（避免重复调用 API）
# ============================================================

class CachedEmbeddingBackend(EmbeddingBackend):
    """嵌入缓存装饰器 — 对相同文本避免重复调用 API"""

    def __init__(self, backend: EmbeddingBackend):
        self._backend = backend
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._max_cache_entries = max(
            0,
            int(os.getenv("EMBEDDING_MEMORY_CACHE_SIZE", "256")),
        )
        self.NAME = f"cached-{backend.NAME}"
        self.DIMENSION = backend.DIMENSION

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def embed(self, texts: List[str]) -> List[List[float]]:
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            key = self._hash(text)
            if key in self._cache:
                cached = self._cache.pop(key)
                self._cache[key] = cached
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                results.append((i, None))  # placeholder

        if uncached_texts:
            new_embs = self._backend.embed(uncached_texts)
            for idx, text, emb in zip(uncached_indices, uncached_texts, new_embs):
                key = self._hash(text)
                if self._max_cache_entries:
                    self._cache[key] = emb
                    self._cache.move_to_end(key)
                    while len(self._cache) > self._max_cache_entries:
                        self._cache.popitem(last=False)
                results[idx] = (idx, emb)

        # 按原始顺序返回
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def clear_cache(self):
        self._cache.clear()

    def runtime_info(self) -> dict:
        return {
            **self._backend.runtime_info(),
            "memory_cache_entries": len(self._cache),
            "memory_cache_limit": self._max_cache_entries,
        }


# ============================================================
# 工厂函数
# ============================================================

# 按后端隔离单例，避免先初始化 DashScope 后所有 BGE 查询误用云端向量空间。
_backend_instances: dict[tuple[str, str], EmbeddingBackend] = {}


def get_embedding_backend(
    provider: str = "siliconflow",
    api_key: str = "",
    model: str = "text-embedding-v3",
    force_reload: bool = False,
) -> EmbeddingBackend:
    """获取嵌入后端实例（单例模式）

    Args:
        provider: "dashscope" | "siliconflow"
        api_key: API Key
        model: 模型名
        force_reload: 强制重新创建实例

    Returns:
        EmbeddingBackend 实例（带缓存层）
    """
    cache_key = (str(provider).lower(), str(model))
    if cache_key in _backend_instances and not force_reload:
        return _backend_instances[cache_key]

    provider = str(provider).lower()
    if provider == "dashscope":
        if not api_key:
            raise ValueError(
                "DashScope 嵌入需要 API Key。请在「个人中心 → Embedding 配置」中设置你的阿里云 API Key。"
            )
        backend = DashScopeBackend(api_key=api_key, model=model)
    elif provider in {"siliconflow", "bge-api"}:
        api_model = model if model != "text-embedding-v3" else SiliconFlowBGEBackend.MODEL
        backend = SiliconFlowBGEBackend(
            api_key=api_key,
            model=api_model,
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        )
    else:
        raise ValueError(
            f"不支持的嵌入提供商: {provider}。可选: siliconflow, dashscope"
        )

    _backend_instances[cache_key] = CachedEmbeddingBackend(backend)
    logger.info("Embedding backend: %s", _backend_instances[cache_key].NAME)
    return _backend_instances[cache_key]


def reset_embedding_backend():
    """重置嵌入后端（切换 provider 时调用）"""
    _backend_instances.clear()


def _truncate_text(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    """截断文本到安全长度，防止单个文本块过大导致 GPU OOM

    BGE max_seq_length=512 tokens ≈ 1000-1500 中文字符（中文约 1.5-2 char/token）。
    在字符层面截断而非 tokenizer 层面，避免加载 tokenizer 的开销。
    """
    if len(text) <= max_chars:
        return text
    logger.warning(f"文本过长（{len(text)} chars），已截断至 {max_chars} chars")
    return text[:max_chars]


def test_dashscope_connection(api_key: str, model: str = "text-embedding-v3") -> dict:
    """测试 DashScope API 连通性

    Returns:
        {"ok": True/False, "dimension": int, "latency_ms": float, "error": str}
    """
    import time
    try:
        backend = DashScopeBackend(api_key=api_key, model=model)
        t0 = time.time()
        emb = backend.embed_single("连通性测试")
        latency = (time.time() - t0) * 1000
        return {
            "ok": True,
            "dimension": len(emb),
            "latency_ms": round(latency, 1),
            "model": model,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def test_siliconflow_connection(
    api_key: str,
    model: str = SiliconFlowBGEBackend.MODEL,
) -> dict:
    """用一条短 Query 验证 SiliconFlow BGE 模型、维度和延迟。"""
    import time

    try:
        backend = SiliconFlowBGEBackend(api_key=api_key, model=model)
        started = time.perf_counter()
        embedding = backend.embed_single("智能体记忆如何实现")
        return {
            "ok": True,
            "provider": "siliconflow",
            "model": model,
            "dimension": len(embedding),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except Exception as exc:
        return {"ok": False, "provider": "siliconflow", "error": str(exc)[:300]}
