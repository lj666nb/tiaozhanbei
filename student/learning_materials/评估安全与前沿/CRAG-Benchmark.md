# CRAG Benchmark：RAG系统评估基准

## 引言

检索增强生成（RAG, Retrieval-Augmented Generation）已经成为AI Agent最核心的能力之一。无论是知识问答、文档分析还是实时信息检索，RAG都是Agent获取外部知识的主要手段。但一个关键问题随之而来：**如何客观地评估一个RAG系统的好坏？**

**CRAG（Comprehensive RAG Benchmark）** 正是为此而生——它是一个专门用于评估RAG系统综合性能的基准测试。与传统QA数据集不同，CRAG不仅评测最终答案的正确性，还深入评测检索质量、生成质量和端到端性能三个核心维度。本文将从CRAG的设计理念、评测维度和实践应用三个层面进行深入解析。



**Image-Prompt(CRAG-RAG-System-Evaluation-Overview):** A flat-design illustration of a RAG system being evaluated. Center shows a document icon feeding into a magnifying glass (retrieval) then into a brain-shaped processor (generation), with a scoring checklist overlay on the right side displaying checkmarks and score bars. Primary blue #409EFF for the evaluation flow arrows and scoring elements, deep blue #1a1a2e outlines, white background. Rounded rectangular panels, thin-line icons, centered symmetrical composition. Academic benchmark testing atmosphere.

---

## RAG评估的挑战

### 为什么评估RAG比评估纯LLM更难

```
纯LLM评估：
  输入问题 → LLM → 输出答案 → 对比参考答案 → 评分

RAG系统评估：
  输入问题 → 检索模块 → 相关文档 → 生成模块 → 输出答案
              ↓                        ↓
         检索质量评估             生成质量评估
              ↓                        ↓
              端到端质量评估（综合考虑）
```

| 评估维度 | 纯LLM | RAG系统 |
|---------|-------|---------|
| 评估对象 | 1个（生成模型） | 2个（检索器 + 生成器） |
| 失败模式 | 生成错误 | 检索失败 / 利用错误文档 / 忽略检索结果 / 幻觉 |
| 评估粒度 | 粗（只看最终答案） | 细（需检查中间步骤） |
| 数据需求 | 标准QA对 | 需知识库 + QA对 + 检索标注 |

### RAG系统常见的失败模式

```
失败模式1：检索失败 (Retrieval Failure)
  问题："2024年诺贝尔物理学奖得主是谁？"
  检索到的文档：[2023年物理奖, 2024年化学奖, 物理学史]
  → 没有检索到相关文档，生成模型只能靠记忆（可能过时或编造）

失败模式2：上下文忽略 (Context Ignorance)
  问题："什么是Transformer？"
  检索到的文档：[详细的Transformer架构解释]
  生成回答："Transformer是一种..." [没有利用检索到的文档]

失败模式3：上下文误解 (Context Misinterpretation)
  问题："Python中如何实现单例模式？"
  检索到的文档：[Python单例模式实现]
  生成回答："使用__new__方法..." [正确利用了文档]

失败模式4：幻觉 (Hallucination)
  问题："珠穆朗玛峰的高度是多少？"
  检索到的文档：无相关文档
  生成回答："珠穆朗玛峰高8849.68米" [实际为8848.86米，微小的数字偏差]
```

**Image-Prompt(RAG-vs-Pure-LLM-Evaluation-Comparison):** A flat-design split comparison diagram. Top half shows pure LLM evaluation as a simple single-arrow pipeline: "Question -> LLM -> Answer -> Compare -> Score" in muted gray. Bottom half shows RAG evaluation as a more complex branched pipeline: "Question -> Retrieval Module -> Relevant Docs -> Generation Module -> Answer", with two additional evaluation checkpoints at Retrieval and Generation stages highlighted in primary blue #409EFF. Deep blue #1a1a2e outlines, white background, rounded rectangular process nodes connected by thin-line arrows. Academic comparative analysis style.

---

## CRAG评测维度

### 三维度框架

```
                    ┌─────────────┐
                    │  CRAG综合   │
                    │   评测框架   │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
  ┌─────▼─────┐    ┌──────▼──────┐    ┌─────▼─────┐
  │ 检索质量   │    │  生成质量   │    │ 端到端性能 │
  │ Retrieval │    │ Generation │    │ End-to-End│
  └─────┬─────┘    └──────┬──────┘    └─────┬─────┘
        │                  │                  │
  ┌─────▼─────┐    ┌──────▼──────┐    ┌─────▼─────┐
  │ • Recall  │    │ • Faithful.│    │ • Accuracy│
  │ • Precision│   │ • Relevant │    │ • F1 Score│
  │ • MRR     │    │ • Fluency  │    │ • Latency │
  │ • NDCG    │    │ • Coverage │    │ • Cost    │
  └───────────┘    └────────────┘    └───────────┘
```

### 1. 检索质量（Retrieval Quality）

检索是RAG系统的第一步，也是最关键的一步——"垃圾进，垃圾出"。如果检索不到相关文档，生成模块再强也无法给出正确答案。

#### 核心指标

```python
import numpy as np
from typing import List, Set


class RetrievalMetrics:
    """检索质量评估指标"""

    @staticmethod
    def recall_at_k(retrieved: List[str],
                    relevant: Set[str],
                    k: int) -> float:
        """
        Recall@K：前K个检索结果中包含了多少相关文档。

        定义：|Retrieved_k ∩ Relevant| / |Relevant|

        意义：衡量检索系统"找全了没有"。
        高Recall = 不遗漏重要文档
        """
        retrieved_k = set(retrieved[:k])
        if len(relevant) == 0:
            return 0.0
        return len(retrieved_k & relevant) / len(relevant)

    @staticmethod
    def precision_at_k(retrieved: List[str],
                       relevant: Set[str],
                       k: int) -> float:
        """
        Precision@K：前K个检索结果中有多少是真正相关的。

        定义：|Retrieved_k ∩ Relevant| / k

        意义：衡量检索系统"找得准不准"。
        高Precision = 少噪音
        """
        retrieved_k = set(retrieved[:k])
        return len(retrieved_k & relevant) / k if k > 0 else 0.0

    @staticmethod
    def mrr(retrieved: List[str],
            relevant: Set[str]) -> float:
        """
        MRR (Mean Reciprocal Rank)：第一个相关文档的排名的倒数。

        定义：1 / rank_of_first_relevant

        意义：衡量检索系统是否能快速找到相关文档。
        MRR越接近1，相关文档排名越靠前。
        """
        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def ndcg_at_k(retrieved: List[str],
                  relevance_scores: dict,
                  k: int) -> float:
        """
        NDCG@K (Normalized Discounted Cumulative Gain)：

        考虑排序位置和相关性的综合指标。
        排名靠前的文档贡献更大的分数。

        DCG_k = Σ_{i=1}^{k} (2^{rel_i} - 1) / log2(i+1)
        NDCG_k = DCG_k / IDCG_k

        其中IDCG是理想排序下的DCG。
        """
        def dcg(scores):
            return sum(
                (2**s - 1) / np.log2(i + 2)
                for i, s in enumerate(scores)
            )

        retrieved_scores = [
            relevance_scores.get(d, 0) for d in retrieved[:k]
        ]
        ideal_scores = sorted(
            relevance_scores.values(), reverse=True
        )[:k]

        actual_dcg = dcg(retrieved_scores)
        ideal_dcg = dcg(ideal_scores)

        return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


# ============ 使用示例 ============
retrieved_docs = ["doc_3", "doc_1", "doc_5", "doc_2", "doc_8"]
relevant_docs = {"doc_1", "doc_2", "doc_4"}
relevance_scores = {"doc_1": 3, "doc_2": 2, "doc_3": 0,
                    "doc_4": 3, "doc_5": 1}

print(f"Recall@5: {RetrievalMetrics.recall_at_k(retrieved_docs, relevant_docs, 5):.2%}")
# Recall@5 = 2/3 = 66.7% (找到了doc_1和doc_2，漏了doc_4)

print(f"Precision@3: {RetrievalMetrics.precision_at_k(retrieved_docs, relevant_docs, 3):.2%}")
# Precision@3 = 1/3 = 33.3% (前3个中只有doc_1相关)

print(f"MRR: {RetrievalMetrics.mrr(retrieved_docs, relevant_docs):.4f}")
# MRR = 1/2 = 0.5 (第一个相关文档doc_1排第2)

print(f"NDCG@5: {RetrievalMetrics.ndcg_at_k(retrieved_docs, relevance_scores, 5):.4f}")
```

#### 检索质量评估矩阵

| 指标 | 考察维度 | 最优值 | 适用场景 |
|------|---------|--------|---------|
| Recall@K | 完整性（查全） | 1.0 | 不允许遗漏的场景（医疗/法律） |
| Precision@K | 准确性（查准） | 1.0 | 对噪音敏感的场景（精确问答） |
| MRR | 排序质量 | 1.0 | 用户只看前几个结果的场景 |
| NDCG@K | 综合排序 | 1.0 | 文档相关度有等级区分的场景 |

### 2. 生成质量（Generation Quality）

检索到文档后，生成模块需要基于文档进行正确的回答。CRAG从多个角度评估生成质量。

```python
class GenerationMetrics:
    """生成质量评估指标"""

    @staticmethod
    def faithfulness(generated_answer: str,
                     retrieved_context: str) -> float:
        """
        忠实度 (Faithfulness)：生成的答案是否忠实于检索到的上下文。

        检查：答案中的每个声明是否都能在上下文中找到依据。

        这是RAG系统最关键的质量指标——如果答案不忠于检索结果，
        RAG就失去了意义。
        """
        # 实现：提取答案中的原子声明
        claims = GenerationMetrics._extract_claims(generated_answer)
        context_sentences = GenerationMetrics._split_sentences(
            retrieved_context
        )

        supported_count = 0
        for claim in claims:
            # 用NLI（自然语言推理）检查每个声明是否能从上下文中推出
            if GenerationMetrics._is_supported(claim, context_sentences):
                supported_count += 1

        return supported_count / len(claims) if claims else 0.0

    @staticmethod
    def answer_relevance(generated_answer: str,
                          question: str) -> float:
        """
        答案相关性 (Answer Relevance)：答案是否切题。

        衡量生成答案与原始问题之间的语义相关性。
        通过计算答案的embedding与问题的embedding的余弦相似度。
        """
        answer_embedding = GenerationMetrics._get_embedding(
            generated_answer
        )
        question_embedding = GenerationMetrics._get_embedding(question)
        return np.dot(answer_embedding, question_embedding) / (
            np.linalg.norm(answer_embedding) *
            np.linalg.norm(question_embedding)
        )

    @staticmethod
    def context_recall(generated_answer: str,
                       retrieved_context: str,
                       reference_context: str) -> float:
        """
        上下文召回 (Context Recall)：

        回复中使用的信息覆盖了参考上下文中多少关键点。

        高上下文召回 = 生成模块充分挖掘了检索结果中的信息。
        """
        # 提取回复和参考上下文中的关键信息点
        answer_points = GenerationMetrics._extract_key_points(
            generated_answer
        )
        reference_points = GenerationMetrics._extract_key_points(
            reference_context
        )

        covered = sum(
            1 for rp in reference_points
            if any(GenerationMetrics._semantic_match(rp, ap)
                  for ap in answer_points)
        )
        return covered / len(reference_points) if reference_points else 0.0

    @staticmethod
    def hallucination_rate(generated_answer: str,
                           retrieved_contexts: List[str]) -> float:
        """
        幻觉率 (Hallucination Rate)：

        生成答案中无法在检索上下文中找到依据的声明比例。

        目标：让这个值尽可能接近0。
        """
        claims = GenerationMetrics._extract_claims(generated_answer)
        all_context = " ".join(retrieved_contexts)

        hallucinated = 0
        for claim in claims:
            if not GenerationMetrics._is_supported(claim, all_context):
                hallucinated += 1

        return hallucinated / len(claims) if claims else 0.0

    # ============ 辅助方法（简化示意） ============

    @staticmethod
    def _extract_claims(text: str) -> List[str]:
        """从文本中提取原子声明"""
        # 实际使用LLM/Parser提取
        sentences = text.replace("。", ".").split(".")
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def _is_supported(claim: str,
                      context: str) -> bool:
        """使用NLI判断声明是否被上下文支撑"""
        # 实际使用NLI模型
        # 返回 entailment / contradiction / neutral
        return "entailment" in claim  # 简化

    @staticmethod
    def _get_embedding(text: str) -> np.ndarray:
        """获取文本的embedding向量"""
        # 实际使用embedding模型
        return np.random.randn(768)

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        return text.replace("。", ".").split(".")
```

#### 生成质量评估框架

```python
class RAGQualityEvaluator:
    """RAG系统生成质量的综合评估器"""

    def __init__(self):
        self.metrics = GenerationMetrics()

    def evaluate_single(self, question: str,
                        generated_answer: str,
                        retrieved_contexts: List[str],
                        reference_answer: str = None) -> dict:
        """
        评估单个RAG回答的质量。

        返回包括多个维度的评分和综合质量判断。
        """
        context_str = "\n".join(retrieved_contexts)

        results = {
            "faithfulness": self.metrics.faithfulness(
                generated_answer, context_str
            ),
            "answer_relevance": self.metrics.answer_relevance(
                generated_answer, question
            ),
            "hallucination_rate": self.metrics.hallucination_rate(
                generated_answer, retrieved_contexts
            ),
        }

        if reference_answer:
            results["context_recall"] = self.metrics.context_recall(
                generated_answer, context_str, reference_answer
            )

        # 综合质量分类
        results["quality_level"] = self._classify_quality(results)

        return results

    def _classify_quality(self, results: dict) -> str:
        """根据多维度分数分类回答质量"""
        faithfulness = results.get("faithfulness", 0)
        relevance = results.get("answer_relevance", 0)
        hallucination = results.get("hallucination_rate", 1.0)

        if faithfulness > 0.9 and relevance > 0.8 and hallucination < 0.05:
            return "excellent"
        elif faithfulness > 0.7 and relevance > 0.6 and hallucination < 0.15:
            return "good"
        elif faithfulness > 0.5 and hallucination < 0.3:
            return "acceptable"
        else:
            return "poor"
```

### 3. 端到端性能（End-to-End Performance）

端到端评估关注整个RAG系统作为一个黑盒的表现。

```python
class EndToEndMetrics:
    """端到端性能评估"""

    @staticmethod
    def exact_match(predicted: str,
                    reference: str) -> bool:
        """
        精确匹配 (Exact Match, EM)

        最严格的指标：答案必须与参考答案完全一致。
        适用于事实性问答（如"北京的首都是什么？"）。
        """
        return predicted.strip().lower() == reference.strip().lower()

    @staticmethod
    def f1_score(predicted: str,
                 reference: str) -> float:
        """
        F1分数：基于token重叠的软匹配。

        更适用于长答案，不要求完全一致，
        而是看预测答案覆盖了多少参考答案的内容。
        """
        pred_tokens = set(predicted.lower().split())
        ref_tokens = set(reference.lower().split())

        if not pred_tokens or not ref_tokens:
            return 0.0

        overlap = pred_tokens & ref_tokens
        precision = len(overlap) / len(pred_tokens)
        recall = len(overlap) / len(ref_tokens)

        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @staticmethod
    def rouge_l(predicted: str,
                reference: str) -> float:
        """
        ROUGE-L：基于最长公共子序列(LCS)的匹配。

        更关注回答的结构和顺序。
        """
        # 简化实现
        def lcs(s1, s2):
            m, n = len(s1), len(s2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if s1[i-1] == s2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                    else:
                        dp[i][j] = max(dp[i-1][j], dp[i][j-1])
            return dp[m][n]

        pred_words = predicted.split()
        ref_words = reference.split()
        lcs_len = lcs(pred_words, ref_words)

        if not pred_words or not ref_words:
            return 0.0

        precision = lcs_len / len(pred_words)
        recall = lcs_len / len(ref_words)

        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @staticmethod
    def bert_score(predicted: str,
                   reference: str) -> float:
        """
        BERTScore：基于BERT embedding的语义相似度。

        相比token级别的匹配，BERTScore能捕获语义等价。
        例如"今天很热"和"气温很高"在token级别不匹配，
        但在BERTScore中会获得高分。
        """
        # 实际使用bert-score库
        pred_embed = np.random.randn(768)
        ref_embed = np.random.randn(768)
        return float(np.dot(pred_embed, ref_embed) /
                    (np.linalg.norm(pred_embed) *
                     np.linalg.norm(ref_embed)))

    @staticmethod
    def latency_metrics(timestamps: List[float]) -> dict:
        """
        延迟指标：
        - P50延迟（中位数）：典型用户体验
        - P95延迟：最差5%用户体验
        - P99延迟：长尾延迟
        """
        latencies = np.diff(timestamps)
        return {
            "mean": float(np.mean(latencies)),
            "median": float(np.median(latencies)),
            "p95": float(np.percentile(latencies, 95)),
            "p99": float(np.percentile(latencies, 99)),
            "min": float(np.min(latencies)),
            "max": float(np.max(latencies)),
        }
```

**Image-Prompt(CRAG-Three-Dimension-Evaluation-Framework):** A flat-design three-panel dashboard layout. Top center reads "CRAG Comprehensive Evaluation Framework" in deep blue #1a1a2e. Three rounded rectangular panels below, side by side: left panel "Retrieval Quality" with metrics icons (Recall, Precision, MRR, NDCG), middle panel "Generation Quality" with icons (Faithfulness, Relevance, Fluency, Coverage), right panel "End-to-End Performance" with icons (Accuracy, F1, Latency, Cost). Each panel in primary blue #409EFF accent borders, white card backgrounds, thin-line minimal icons. Clean white overall background, centered symmetrical composition. Academic benchmark evaluation style.

---

## 完整的CRAG评估流程

```python
class CRAGEvaluator:
    """
    CRAG完整评估流程。

    整合检索质量、生成质量和端到端性能三个维度。
    """

    def __init__(self):
        self.retrieval_metrics = RetrievalMetrics()
        self.generation_metrics = GenerationMetrics()
        self.e2e_metrics = EndToEndMetrics()

    def evaluate_system(self,
                        rag_system,
                        test_queries: List[dict]) -> dict:
        """
        对一个RAG系统进行完整评估。

        test_queries格式：
        [
            {
                "query": "什么是AgentBench？",
                "relevant_docs": ["doc_1", "doc_5"],
                "relevance_scores": {"doc_1": 3, "doc_2": 1, ...},
                "reference_answer": "AgentBench是..."
            },
            ...
        ]
        """
        retrieval_results = []
        generation_results = []
        e2e_results = []
        latencies = []

        for tq in test_queries:
            # 1. 运行RAG系统
            start_time = time.time()
            retrieved_docs, answer = rag_system.query(tq["query"])
            end_time = time.time()
            latencies.append(end_time - start_time)

            # 2. 评估检索质量
            retrieval_results.append({
                "recall@5": self.retrieval_metrics.recall_at_k(
                    retrieved_docs, set(tq["relevant_docs"]), 5
                ),
                "precision@5": self.retrieval_metrics.precision_at_k(
                    retrieved_docs, set(tq["relevant_docs"]), 5
                ),
                "mrr": self.retrieval_metrics.mrr(
                    retrieved_docs, set(tq["relevant_docs"])
                )
            })

            # 3. 评估生成质量
            context = self._load_context(retrieved_docs)
            generation_results.append({
                "faithfulness": self.generation_metrics.faithfulness(
                    answer, context
                ),
                "hallucination_rate": self.generation_metrics.hallucination_rate(
                    answer, [context]
                )
            })

            # 4. 评估端到端
            e2e_results.append({
                "f1": self.e2e_metrics.f1_score(
                    answer, tq["reference_answer"]
                ),
                "rouge_l": self.e2e_metrics.rouge_l(
                    answer, tq["reference_answer"]
                )
            })

        # 5. 汇总
        return self._aggregate_results(
            retrieval_results, generation_results,
            e2e_results, latencies
        )

    def _aggregate_results(self, retrieval, generation,
                            e2e, latencies) -> dict:
        """汇总所有评估结果"""
        def mean(vals): return sum(vals) / len(vals) if vals else 0

        return {
            # 检索质量
            "retrieval": {
                "recall@5": mean([r["recall@5"] for r in retrieval]),
                "precision@5": mean([r["precision@5"] for r in retrieval]),
                "mrr": mean([r["mrr"] for r in retrieval]),
            },
            # 生成质量
            "generation": {
                "faithfulness": mean(
                    [g["faithfulness"] for g in generation]
                ),
                "hallucination_rate": mean(
                    [g["hallucination_rate"] for g in generation]
                ),
            },
            # 端到端
            "end_to_end": {
                "f1_score": mean([e["f1"] for e in e2e]),
                "rouge_l": mean([e["rouge_l"] for e in e2e]),
            },
            # 性能
            "performance": {
                "avg_latency_ms": mean(latencies) * 1000,
                "p95_latency_ms": np.percentile(latencies, 95) * 1000,
            }
        }
```

---

## 与其他RAG基准的对比

| 基准名称 | 覆盖维度 | 数据规模 | 开源 | 特点 |
|---------|---------|---------|------|------|
| **CRAG** | 检索 + 生成 + 端到端 | 中等 | 是 | 三维度综合，工业界友好 |
| **RGB** | 检索 + 生成 | 小 | 是 | 中英双语，专注于幻觉检测 |
| **RAGAS** | 检索 + 生成 | - | 是 | 无参考答案评测框架 |
| **TruLens** | 检索 + 生成 | - | 部分 | 可视化监控面板 |
| **KILT** | 知识密集型任务 | 大 | 是 | 5个任务统一框架 |
| **BEIR** | 纯检索 | 大 | 是 | 18个检索数据集 |

### CRAG的独特优势

1. **工业级**：由Meta AI等工业实验室设计，贴近实际应用场景
2. **三维度一体化**：检索、生成、端到端在一个框架中评估
3. **幻觉检测**：专门的幻觉率评估维度
4. **文档级标注**：提供了完整的文档-查询相关性标注

---

## 实践建议

### RAG系统优化checklist

```
□ 检索质量
  □ Recall@K是否达标？（目标 > 0.85）
  □ 是否存在检索盲区？（某些类型问题检索不到相关文档）
  □ 是否需要混合检索（向量 + 关键词）？
  □ 分块策略是否合理？（块太大/太小都影响检索）

□ 生成质量
  □ 忠实度是否达标？（目标 > 0.85）
  □ 幻觉率是否可接受？（目标 < 0.1）
  □ Prompt是否充分引导模型利用检索结果？
  □ 是否需要引用标注？

□ 端到端性能
  □ 延迟是否满足SLA？（目标：P95 < 3s）
  □ 成本是否可控？（每次查询的Token消耗）
  □ 是否正确处理"无法回答"的情况？
  □ 是否支持流式输出？
```

---

## 小结

CRAG Benchmark为RAG系统提供了一个标准化、多维度的评估框架。它将RAG评估从"看答案对不对"的粗放阶段推进到"检索够不够全、生成忠不忠实、幻觉多不多、延迟高不高"的精细化阶段。

**评估RAG系统的关键原则**：
1. **检索优先**：没有好的检索，生成再好也白搭
2. **忠实度 > 流畅度**：一个忠实但不流畅的回答，好过一个流畅但虚构的回答
3. **多维度不可偏废**：高召回低精确、高忠实高延迟都是有问题的
4. **持续评估**：知识库在更新、模型在升级，评估要持续进行
5. **结合业务**：不同场景对检索/生成/延迟的容忍度不同，评分权重应结合业务需求调整

记住：RAG系统的质量上限由检索决定，下限由生成决定，而用户体验由端到端延迟决定。

**Image-Prompt(CRAG-Benchmark-Summary-Key-Principles):** A flat-design summary infographic with five rounded rectangular cards arranged in a row. Cards labeled: "Retrieval First", "Faithfulness > Fluency", "Multi-Dimensional", "Continuous Evaluation", "Business-Aligned". Each card features a minimal thin-line icon in primary blue #409EFF, deep blue #1a1a2e text labels. White background, centered horizontal layout, soft rounded corners. Academic key-takeaways summary style for educational software.
