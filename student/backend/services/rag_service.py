"""RAG 编排服务 — ChromaDB 向量存储 + 混合检索 + 上下文格式化

核心流程:
1. 文档块 → Embedding → ChromaDB 存储
2. Query → Embedding → 语义检索 + 关键词匹配 → RRF 融合 → 上下文注入
"""

import os
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from .embedding_service import EmbeddingBackend, get_embedding_backend, reset_embedding_backend
from .document_loader import DocumentChunk, load_all_documents
from config import CHROMA_DB_PATH

logger = logging.getLogger(__name__)

# ============================================================
# 配置常量
# ============================================================

DEFAULT_CHROMA_PATH = CHROMA_DB_PATH
from config import RAG_TOP_K as DEFAULT_TOP_K
CANDIDATE_MULTIPLIER = 5  # 父子块会产生同父候选，多取一些再做父块去重
DOMAIN_TERMS = (
    "多模态", "智能体", "数据采集", "模态处理", "模态融合", "架构", "规划",
    "工具执行", "工具调用", "短期记忆", "长期记忆", "记忆", "ReAct",
    "推理", "行动", "观察", "Function Calling", "Tool Calling", "RAG",
    "文档切分", "向量检索", "重排序", "多智能体", "任务分解", "协同通信",
)

# 查询扩展：英文术语 → 中文同义词，提升跨语言概念匹配
QUERY_EXPANSION_MAP = {
    "k-means": "K-means K均值 K-均值 k均值 聚类算法",
    "kmeans": "K-means K均值 K-均值 k均值 聚类算法",
    "react": "ReAct 推理行动 思考行动",
    "function calling": "函数调用 工具调用 Function Calling",
    "tool calling": "工具调用 函数调用 Tool Calling",
    "fine-tuning": "微调 Fine-tuning 模型微调",
    "fine tuning": "微调 Fine-tuning 模型微调",
    "chain of thought": "思维链 Chain of Thought CoT 逐步推理",
    "cot": "思维链 Chain of Thought CoT 逐步推理",
    "rag": "检索增强生成 RAG 知识库检索",
    "prompt": "提示词 Prompt 提示工程",
    "embedding": "嵌入 Embedding 向量化 向量表征",
    "agent": "智能体 Agent 代理",
    "langchain": "LangChain 开发框架",
    "langgraph": "LangGraph 图编排",
    "auto-gpt": "AutoGPT 自主智能体",
    "autogpt": "AutoGPT 自主智能体",
}

# RAG Prompt 模板
RAG_CONTEXT_TEMPLATE = """【知识库参考资料】
以下是平台知识库中与本问题最相关的内容，请基于这些资料回答用户问题。
{chunks}

【回答要求】
1. 优先使用知识库中的权威内容，用自己的话重新组织表述
2. 在引用知识库内容时，标注来源编号（如 [1]、[2]）
3. 如果知识库内容不足以完全回答问题，结合你自己的知识补充说明
4. 保持回答结构清晰、语言通俗，适合大学生阅读"""

RAG_SYSTEM_SUPPLEMENT = """你正在使用平台知识库的权威资料辅助回答。请以知识库内容为准，如知识库不完整再结合你的知识补充。"""


# ============================================================
# RAG 服务
# ============================================================

class RAGService:
    """RAG 编排服务"""

    def __init__(self, backend: EmbeddingBackend, chroma_path: str = DEFAULT_CHROMA_PATH):
        self.backend = backend
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)

        # 延迟初始化 ChromaDB（避免启动时的导入开销）
        self._client = None
        self._collection = None
        self.collection_name = f"rag_docs_{backend.NAME}_semantic_v2"

    @property
    def client(self):
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # ============================================================
    # 文档入库
    # ============================================================

    def ingest(
        self,
        chunks: List[DocumentChunk],
        batch_size: int = 50,
        progress_callback=None,
    ) -> dict:
        """批量向量化并写入 ChromaDB

        Args:
            chunks: 文档块列表
            batch_size: 批大小
            progress_callback: 进度回调 (current, total) -> None

        Returns:
            {"total": int, "new": int, "skipped": int, "errors": int}
        """
        total = len(chunks)
        new_count = 0
        skip_count = 0
        error_count = 0

        # 获取已有文档 ID 集合（去重）
        existing_ids = set()
        try:
            existing = self.collection.get()
            if existing and existing.get("ids"):
                existing_ids = set(existing["ids"])
        except Exception:
            pass  # 空集合

        logger.info(f"开始入库 {total} 个文档块（已有 {len(existing_ids)} 个）...")

        batch_seen = set()  # 批内去重

        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            new_batch = []
            new_texts = []

            for chunk in batch:
                doc_id = f"{chunk.source_type}:{chunk.doc_id}"
                if doc_id in existing_ids or doc_id in batch_seen:
                    skip_count += 1
                    continue
                batch_seen.add(doc_id)
                new_batch.append(chunk)
                # 命中较小的检索子块，返回完整父块。这样既提高定位精度，
                # 又不会把句子从 500/600/800 字处硬截断。
                new_texts.append(chunk.metadata.get("embedding_text") or chunk.text)

            if not new_texts:
                if progress_callback:
                    progress_callback(min(i + batch_size, total), total)
                continue

            try:
                # 嵌入
                embeddings = self.backend.embed(new_texts)
                ids = [f"{c.source_type}:{c.doc_id}" for c in new_batch]
                metadatas = [
                    {
                        "source_type": c.source_type,
                        "source_path": c.source_path,
                        "title": c.title or "",
                        "module": c.module or "",
                        "page": c.page or 0,
                        "section": c.section or "",
                        "source_label": c.source_label,
                        "parent_id": str(c.metadata.get("parent_id") or c.doc_id),
                        "child_index": int(c.metadata.get("child_index") or 0),
                        "end_page": int(c.metadata.get("end_page") or c.page or 0),
                        "quality_score": float(c.metadata.get("quality_score") or 0.5),
                        "chunk_version": str(c.metadata.get("chunk_version") or "legacy"),
                        "parent_text": c.text,
                    }
                    for c in new_batch
                ]

                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=new_texts,
                    metadatas=metadatas,
                )
                new_count += len(new_batch)

            except Exception as e:
                logger.error(f"入库批次 [{i}:{i+batch_size}] 失败: {e}")
                error_count += len(new_batch)

            if progress_callback:
                progress_callback(min(i + batch_size, total), total)

        logger.info(f"入库完成: 新增 {new_count}, 跳过 {skip_count}, 错误 {error_count}")
        return {"total": total, "new": new_count, "skipped": skip_count, "errors": error_count}

    # ============================================================
    # 检索
    # ============================================================

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> List[dict]:
        """混合检索主入口

        Returns:
            [{text, metadata, score}, ...]  按相关度降序
        """
        # 查询扩展：将英文术语映射到中文同义词，提升跨语言检索
        expanded_query = self._expand_query(query)

        # 1. 语义检索（dense）
        dense_results = self._dense_retrieve(expanded_query, top_k * CANDIDATE_MULTIPLIER)

        # 2. 关键词匹配（keyword）
        keyword_results = self._keyword_retrieve(expanded_query, top_k * CANDIDATE_MULTIPLIER)

        # 3. RRF 融合
        merged = self._rrf_fusion(
            dense_results,
            keyword_results,
            top_k * CANDIDATE_MULTIPLIER,
        )
        return self._rerank_and_deduplicate(query, merged, top_k)

    def _expand_query(self, query: str) -> str:
        """查询扩展：将英文技术术语映射到中文同义词"""
        result = query
        query_lower = query.lower()
        for en_term, cn_expansion in QUERY_EXPANSION_MAP.items():
            if en_term in query_lower:
                result = f"{result} {cn_expansion}"
        return result

    def _dense_retrieve(self, query: str, top_k: int) -> List[dict]:
        """语义向量检索"""
        try:
            query_emb = self.backend.embed_single(query)
            results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=top_k,
                where={
                    "$and": [
                        {"source_type": {"$ne": "qa_pair"}},
                        {"quality_score": {"$gte": 0.55}},
                    ]
                },
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            if results and results.get("ids") and results["ids"][0]:
                ids = results["ids"][0]
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                dists = results.get("distances", [[]])[0]

                for i, doc_id in enumerate(ids):
                    # cosine distance → similarity score
                    distance = dists[i] if i < len(dists) else 0
                    score = max(0.0, 1.0 - distance)
                    metadata = metas[i] if i < len(metas) else {}
                    parent_text = (
                        (metadata or {}).get("parent_text")
                        or (docs[i] if i < len(docs) else "")
                    )
                    if len(parent_text.strip()) < 150:
                        continue

                    chunks.append({
                        "id": doc_id,
                        "text": parent_text,
                        "retrieval_text": docs[i] if i < len(docs) else "",
                        "metadata": metadata,
                        "score": round(score, 4),
                        "source": "dense",
                    })

            return sorted(chunks, key=lambda x: x["score"], reverse=True)

        except Exception as e:
            logger.warning(f"Dense retrieval failed: {e}")
            return []

    def _keyword_retrieve(self, query: str, top_k: int) -> List[dict]:
        """关键词匹配检索（Jaccard 相似度 + 知识标签匹配）

        复用现有 evolution_service 的 Jaccard 模式，不依赖额外库
        """
        try:
            # 对查询做 2-gram 分词
            query_tokens = set(self._tokenize(query))

            # 从 ChromaDB 获取所有文档（可缓存优化）
            all_docs = self.collection.get(include=["documents", "metadatas"])

            if not all_docs or not all_docs.get("ids"):
                return []

            scored = []
            for i, doc_id in enumerate(all_docs["ids"]):
                doc_text = all_docs["documents"][i] if i < len(all_docs["documents"]) else ""
                doc_meta = all_docs["metadatas"][i] if i < len(all_docs["metadatas"]) else {}

                if not doc_text:
                    continue
                if doc_meta.get("source_type") == "qa_pair":
                    continue
                if float(doc_meta.get("quality_score") or 0) < 0.55:
                    continue
                if len(doc_meta.get("parent_text") or doc_text) < 150:
                    continue

                doc_tokens = set(self._tokenize(doc_text))

                # Jaccard 相似度
                intersection = query_tokens & doc_tokens
                union = query_tokens | doc_tokens
                jaccard = len(intersection) / max(1, len(union))

                # 知识标签命中加成
                tag_bonus = 0.0
                if doc_meta.get("module") and _keyword_in_text(doc_meta["module"], query):
                    tag_bonus += 0.15
                if doc_meta.get("title") and _keyword_in_text(doc_meta["title"], query):
                    tag_bonus += 0.10

                score = min(1.0, jaccard + tag_bonus)
                if score > 0.05:  # 最低阈值
                    scored.append({
                        "id": doc_id,
                        "text": doc_meta.get("parent_text") or doc_text,
                        "retrieval_text": doc_text,
                        "metadata": doc_meta,
                        "score": round(score, 4),
                        "source": "keyword",
                    })

            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:top_k]

        except Exception as e:
            logger.warning(f"Keyword retrieval failed: {e}")
            return []

    def _rrf_fusion(
        self,
        dense_results: List[dict],
        keyword_results: List[dict],
        top_k: int,
        k: int = 60,
    ) -> List[dict]:
        """Reciprocal Rank Fusion 融合排序"""
        # 构建 id → chunk 映射
        chunk_map = {}
        for r in dense_results:
            chunk_map[r["id"]] = r
        for r in keyword_results:
            if r["id"] not in chunk_map:
                chunk_map[r["id"]] = r

        # RRF 打分
        rrf_scores = {}
        for rank, r in enumerate(dense_results):
            rrf_scores[r["id"]] = rrf_scores.get(r["id"], 0) + 1.0 / (k + rank + 1)
        for rank, r in enumerate(keyword_results):
            rrf_scores[r["id"]] = rrf_scores.get(r["id"], 0) + 1.0 / (k + rank + 1)

        # 排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids[:top_k]:
            chunk = chunk_map.get(doc_id, {})
            results.append({
                "id": doc_id,
                "text": chunk.get("text", ""),
                "metadata": chunk.get("metadata", {}),
                "score": round(rrf_scores[doc_id], 4),
                "source": chunk.get("source", "unknown"),
            })

        return results

    def _rerank_and_deduplicate(
        self,
        query: str,
        candidates: List[dict],
        top_k: int,
    ) -> List[dict]:
        """按父块合并子块，并用质量/查询覆盖率做轻量重排。"""
        query_tokens = set(self._tokenize(query))
        query_terms = {
            term.upper()
            for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,20}", query)
        }
        required_terms = [term for term in DOMAIN_TERMS if term.lower() in query.lower()]
        implementation_intent = any(
            marker in query
            for marker in ("如何实现", "怎么实现", "怎样实现", "如何构建", "怎么构建", "搭建")
        )
        best_by_parent: dict[str, dict] = {}
        for candidate in candidates:
            metadata = candidate.get("metadata") or {}
            text = candidate.get("text") or ""
            parent_id = str(metadata.get("parent_id") or candidate.get("id") or "")
            retrieval_text = candidate.get("retrieval_text") or text
            document_tokens = set(self._tokenize(retrieval_text))
            coverage = len(query_tokens & document_tokens) / max(1, len(query_tokens))
            quality = float(metadata.get("quality_score") or 0.5)
            score = float(candidate.get("score") or 0)
            retrieval_upper = retrieval_text.upper()
            term_hits = sum(term in retrieval_upper for term in query_terms)
            exact_term_bonus = (
                0.07 * term_hits / max(1, len(query_terms))
                if query_terms
                else 0.0
            )
            source_bonus = 0.026 if metadata.get("source_type") == "pdf" else 0.016
            domain_hits = sum(
                term.lower() in retrieval_text.lower()
                for term in required_terms
            )
            domain_coverage = domain_hits / max(1, len(required_terms))
            domain_bonus = 0.11 * domain_coverage if required_terms else 0.0
            if required_terms and domain_hits == 0:
                domain_bonus -= 0.06
            low_value_penalty = 0.0
            section = str(metadata.get("section") or "")
            if any(marker in section for marker in ("未来展望", "本章小结", "内容简介", "前言")):
                low_value_penalty += 0.10
            if implementation_intent and "注意事项" in section:
                low_value_penalty += 0.04
            if (
                metadata.get("source_type") == "pdf"
                and int(metadata.get("page") or 0) <= 10
                and any(
                    marker in retrieval_text
                    for marker in ("内容简介", "图书在版编目", "版权所有，侵权必究")
                )
            ):
                low_value_penalty += 0.24
            implementation_bonus = 0.0
            if implementation_intent:
                implementation_markers = ("架构", "实现", "构建", "流程", "步骤", "组件")
                if any(marker in section for marker in implementation_markers):
                    implementation_bonus += 0.15
                if any(marker in retrieval_text[:320] for marker in implementation_markers):
                    implementation_bonus += 0.045
            candidate["rerank_score"] = (
                score
                + coverage * 0.11
                + quality * 0.025
                + exact_term_bonus
                + source_bonus
                + domain_bonus
                + implementation_bonus
                - low_value_penalty
            )
            existing = best_by_parent.get(parent_id)
            if not existing or candidate["rerank_score"] > existing["rerank_score"]:
                best_by_parent[parent_id] = candidate

        ordered = sorted(
            best_by_parent.values(),
            key=lambda item: item.get("rerank_score", 0),
            reverse=True,
        )
        return ordered[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """中文 2-gram 分词"""
        cleaned = text.replace('\n', ' ').replace('\r', ' ')
        tokens = []
        for i in range(len(cleaned) - 1):
            bigram = cleaned[i:i + 2].strip()
            if bigram and ' ' not in bigram:
                tokens.append(bigram)
        return tokens

    # ============================================================
    # 上下文格式化
    # ============================================================

    def format_context(self, chunks: List[dict]) -> str:
        """将检索结果格式化为 Prompt 上下文"""
        if not chunks:
            return ""

        parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            source_label = meta.get("source_label", meta.get("title", "未知来源"))
            text = chunk.get("text", "")
            parts.append(f"[{i}] ({source_label})\n{text}")

        return RAG_CONTEXT_TEMPLATE.format(chunks="\n\n".join(parts))

    def get_sources(self, chunks: List[dict]) -> List[dict]:
        """提取来源信息（供前端展示）"""
        sources = []
        seen = set()
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            # 同一本书可以贡献多个不同章节；只合并同一个父块，不能按文件去重。
            source_key = meta.get("parent_id") or chunk.get("id") or ""
            if source_key in seen:
                continue
            seen.add(source_key)
            chunk_text = chunk.get("text", "") or ""
            sources.append({
                "title": meta.get("title", "未知来源"),
                "source_path": meta.get("source_path", ""),
                "source_type": meta.get("source_type", ""),
                "section": meta.get("section", ""),
                "page": meta.get("page"),
                "end_page": meta.get("end_page") or meta.get("page"),
                "parent_id": meta.get("parent_id", ""),
                "quality_score": meta.get("quality_score", 0),
                "score": chunk.get("score", 0),
                "content": chunk_text,
            })
        return sources

    # ============================================================
    # 管理方法
    # ============================================================

    def get_status(self) -> dict:
        """获取知识库状态"""
        try:
            count = self.collection.count()
        except Exception:
            count = 0

        return {
            "collection_name": self.collection_name,
            "backend": self.backend.NAME,
            "embedding_runtime": self.backend.runtime_info(),
            "total_chunks": count,
            "chroma_path": str(self.chroma_path),
        }

    def clear(self):
        """清空知识库"""
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None
            logger.info(f"已清空知识库: {self.collection_name}")
        except Exception as e:
            logger.warning(f"清空知识库失败: {e}")

    def rebuild(self, chunks: List[DocumentChunk], progress_callback=None) -> dict:
        """清空并重建知识库"""
        self.clear()
        return self.ingest(chunks, progress_callback=progress_callback)


# ============================================================
# 全局单例
# ============================================================

_rag_service_instances: dict[tuple[str, str, str], RAGService] = {}


def get_rag_service(
    provider: str = "dashscope",
    api_key: str = "",
    model: str = "text-embedding-v3",
    chroma_path: str = DEFAULT_CHROMA_PATH,
    force_reload: bool = False,
) -> RAGService:
    """获取 RAG 服务实例（单例）"""
    service_key = (
        f"{str(provider).lower()}:{model}",
        str(chroma_path),
        str(api_key)[:8],
    )
    if service_key in _rag_service_instances and not force_reload:
        return _rag_service_instances[service_key]

    backend = get_embedding_backend(
        provider=provider,
        api_key=api_key,
        model=model,
        force_reload=force_reload,
    )
    _rag_service_instances[service_key] = RAGService(backend=backend, chroma_path=chroma_path)
    logger.info(f"RAG service initialized: backend={backend.NAME}")
    return _rag_service_instances[service_key]


def reset_rag_service():
    """重置 RAG 服务（切换 embedding provider 时调用）"""
    _rag_service_instances.clear()
    reset_embedding_backend()


def get_runtime_rag_service(user_id: int) -> RAGService:
    """获取运行时 RAG 服务（始终使用 SiliconFlow 云端嵌入）。"""
    from database import get_db

    api_key = os.getenv("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        conn = get_db()
        try:
            row = conn.execute(
                """SELECT embedding_provider, embedding_api_key, embedding_model
                   FROM user_llm_config WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if row and str(row["embedding_provider"] or "").lower() in {"siliconflow", "bge-api"}:
            api_key = str(row["embedding_api_key"] or "").strip()

    if not api_key:
        raise ValueError(
            "SiliconFlow BGE 查询嵌入暂不可用。请在个人中心配置 SiliconFlow API Key。"
        )
    return get_rag_service(
        provider="siliconflow",
        api_key=api_key,
        model="BAAI/bge-large-zh-v1.5",
    )


# ============================================================
# 工具函数
# ============================================================

def _keyword_in_text(keyword: str, text: str) -> bool:
    """检查关键词是否在文本中（子串匹配）"""
    if not keyword or not text:
        return False
    return keyword.lower() in text.lower()
