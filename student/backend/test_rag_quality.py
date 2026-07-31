#!/usr/bin/env python3
"""RAG 召回质量测试 — 针对 6 类问题进行全面测试"""
import os, sys, json, io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from services.embedding_service import get_embedding_backend
from services.rag_service import RAGService

api_key = os.getenv("SILICONFLOW_API_KEY", "")
if not api_key:
    print("请设置 SILICONFLOW_API_KEY 环境变量")
    sys.exit(1)

backend = get_embedding_backend(provider="siliconflow", api_key=api_key, force_reload=True)
rag = RAGService(backend=backend)

# ============================================================
# 测试用例：6 大类
# ============================================================
TEST_QUERIES = {
    "1-基础概念": [
        "什么是AI Agent？它和传统程序有什么区别？",
        "智能体的规划能力指的是什么？请解释ReAct模式",
        "大语言模型在AI Agent中扮演什么角色？",
        "什么是思维链（Chain of Thought）？",
        "什么是工具调用（Function Calling）？",
    ],
    "2-代码编程": [
        "如何用Python实现一个简单的ReAct Agent？",
        "如何使用LangChain框架构建一个工具调用Agent？",
        "如何实现智能体的记忆模块？给出代码示例",
        "如何用Python调用大模型API实现对话？",
        "AutoGPT的核心架构是什么？如何搭建？",
    ],
    "3-综合辨析": [
        "单智能体和多智能体系统有什么区别？各有什么优劣？",
        "RAG和微调（Fine-tuning）的区别是什么？什么场景用哪个？",
        "短期记忆和长期记忆在AI Agent中各自的实现方式？",
        "扣子（Coze）平台和LangChain框架各适合什么场景？",
        "嵌入式模型和生成式模型的区别？在RAG中各自的作用？",
    ],
    "4-表格数据": [
        "数据挖掘中常用的分类算法有哪些？各自的评价指标是什么？",
        "数据预处理包括哪些步骤？每个步骤的作用是什么？",
        "Python数据分析常用的库有哪些？各自的功能对比",
        "K-means聚类的原理和步骤是什么？",
    ],
    "5-跨篇章/跨书籍": [
        "从AI Agent的基础理论到企业级落地，需要经过哪些阶段？",
        "比较不同书籍中对Agent架构的定义有什么异同？",
        "数据分析挖掘和AI Agent如何结合应用？",
    ],
    "6-边界情况": [
        "Agent的安全性问题如何解决？",
        "智能体如何进行自我反思和纠错？",
        "多模态Agent是什么？如何处理图像和文本？",
        "Agent的评估指标体系有哪些？",
    ],
}


def evaluate_retrieval(query: str, category: str) -> dict:
    """检索并评估返回结果的质量"""
    results = rag.retrieve(query, top_k=5)

    chunks_info = []
    total_score = 0.0
    empty_count = 0

    for i, r in enumerate(results):
        meta = r.get("metadata", {})
        text = r.get("text", "")
        score = r.get("score", 0)
        rerank = r.get("rerank_score", 0)

        if not text or len(text.strip()) < 50:
            empty_count += 1
            continue

        # 计算文本质量指标
        text_len = len(text)
        sentence_count = text.count("。") + text.count("！") + text.count("？")
        has_code = int("def " in text or "import " in text or "class " in text)
        has_table = int("|" in text and text.count("|") >= 3)

        chunks_info.append({
            "rank": i + 1,
            "source": meta.get("source_label", meta.get("title", "?")),
            "section": meta.get("section", "")[:80],
            "page": meta.get("page", 0),
            "score": round(score, 4),
            "rerank_score": round(rerank, 4),
            "text_len": text_len,
            "sentences": sentence_count,
            "has_code": bool(has_code),
            "has_table": bool(has_table),
            "text_preview": text[:200].replace("\n", " "),
        })
        total_score += score

    return {
        "query": query,
        "category": category,
        "total_hits": len(results),
        "quality_hits": len(chunks_info),
        "empty_or_short": empty_count,
        "avg_score": round(total_score / max(1, len(results)), 4),
        "chunks": chunks_info,
    }


def main():
    print("=" * 70)
    print("  RAG 召回质量测试 — 12524 chunks (SiliconFlow)")
    print("=" * 70)

    all_results = {}
    total_queries = 0
    total_quality_hits = 0
    all_scores = []

    for category, queries in TEST_QUERIES.items():
        print(f"\n{'─' * 70}")
        print(f"  📂 {category}")
        print(f"{'─' * 70}")
        cat_results = []

        for query in queries:
            result = evaluate_retrieval(query, category)
            cat_results.append(result)
            total_queries += 1
            total_quality_hits += result["quality_hits"]
            all_scores.append(result["avg_score"])

            # 打印每条查询的结果
            status = "✅" if result["quality_hits"] >= 3 else ("⚠️" if result["quality_hits"] >= 1 else "❌")
            print(f"\n  {status} [{result['quality_hits']}/{result['total_hits']}] {query}")
            print(f"     avg_score={result['avg_score']:.4f}")

            for chunk in result["chunks"][:3]:  # 展示前3个结果
                code_icon = "💻" if chunk["has_code"] else ""
                table_icon = "📊" if chunk["has_table"] else ""
                print(f"     #{chunk['rank']} [{chunk['score']:.4f}] {chunk['source']}")
                print(f"         section: {chunk['section']}")
                print(f"         preview: {chunk['text_preview'][:150]}...")
                if code_icon or table_icon:
                    print(f"         {code_icon}{table_icon}")

        all_results[category] = cat_results

    # 汇总统计
    print(f"\n{'=' * 70}")
    print(f"  📊 汇总统计")
    print(f"{'=' * 70}")
    print(f"  总查询数:      {total_queries}")
    print(f"  平均返回数:    {total_quality_hits / max(1, total_queries):.1f}")
    print(f"  平均分:        {sum(all_scores) / max(1, len(all_scores)):.4f}")
    print(f"  最高分:        {max(all_scores):.4f}")
    print(f"  最低分:        {min(all_scores):.4f}")

    # 按类别统计
    print(f"\n  各类别平均分:")
    for category, results in all_results.items():
        avg = sum(r["avg_score"] for r in results) / max(1, len(results))
        good = sum(1 for r in results if r["quality_hits"] >= 3)
        total = len(results)
        bar = "█" * int(avg * 20) + "░" * (10 - int(avg * 20))
        print(f"    {category:<20s} {avg:.4f} {bar} ({good}/{total} 高质量)")

    # 返回详细结果供后续分析
    return all_results


if __name__ == "__main__":
    main()
