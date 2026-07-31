# 项目 10：让 Agent 能「查资料」——RAG 检索与 Top-K 排序

## 一、知识从哪里来？

到目前为止，模型回答问题的知识来源只有两个：
1. **训练数据中记住的**——可能过时、可能不准确、可能不包含你公司的信息
2. **system prompt 中写死的**——维护成本高，改一个退款政策得改代码

现实中的知识（公司制度、产品手册、FAQ 文档）散落在 PDF、网页、数据库中。我们需要一种机制让 Agent **先检索相关知识，再基于检索结果回答**——这就是 RAG。

### 什么是 RAG？

> 🧠 **关键概念：RAG（Retrieval-Augmented Generation，检索增强生成）** 是一种给大模型「开卷考试」的技术。它不是让模型凭记忆回答，而是：
>
> ```text
> 用户提问 → 从知识库中检索相关文档 → 把文档和问题一起发给模型 → 模型根据文档生成回答
> ```
>
> **类比**：如果模型是参加开卷考试的学生，那知识库就是课本，检索器就是翻书找答案的过程。模型不能瞎编（闭卷），必须引用课本内容（开卷）。
>
> **为什么需要 RAG？**
> - 知识可以随时更新（改文档就行，不用重新训练模型）
> - 答案有来源可追溯（每句话都引用了哪篇文档）
> - 减少幻觉（模型被约束在给定文档中回答）
> - 企业专有知识（模型训练数据里不包含你公司的内部制度）

### 本节目标

1. **先理解**：RAG 的两阶段——检索（Retrieval）和生成（Generation）
2. **先不接向量库**：用确定性相关度（词项交集）理解检索逻辑
3. **再实现**：`retrieve_top_k`——过滤、稳定排序、Top-K 截断
4. **最终验收**：高相关、同分稳定、低分过滤、空文档、非法输入全覆盖

---

## 二、开始前：搭建本节项目

创建 `requirements.txt`、`.env.example`、`solution.py`、`app.py`。本工程阶段需要 `langchain`、`langgraph`、`python-dotenv`。

<!-- lab-check:structure -->

```bash
python -m venv .venv
pip install -r requirements.txt
```

<!-- lab-check:environment -->
<!-- lab-check:dependencies -->

---

## 三、先准备一个小型知识库

> 🧠 **为什么要先做一个确定性版本？** 真实的向量检索依赖嵌入模型（embedding）和向量数据库，这些概念的学习曲线很陡。先用词项交集模拟「相关度计算」，把过滤、排序、截断的控制逻辑吃透——之后把 `score()` 换成余弦相似度、把 `documents` 换成向量数据库时，核心逻辑完全不变。

```python
# 模拟知识库：每篇文档有 id、正文、关键词
documents = [
    {"id": "refund-1", "text": "实体商品签收后7天内可申请退款，需保持商品完好。", "terms": ["实体", "退款", "7天"]},
    {"id": "refund-2", "text": "退款审核通常需要1个工作日完成。", "terms": ["退款", "审核", "时效"]},
    {"id": "refund-3", "text": "数字商品（软件、课程等）激活后不支持退款。", "terms": ["数字商品", "退款", "激活"]},
    {"id": "invoice-1", "text": "电子发票可在订单详情页下载，支持抬头修改。", "terms": ["发票", "订单", "下载"]},
    {"id": "invoice-2", "text": "纸质发票在发货后3个工作日内寄出。", "terms": ["发票", "纸质", "寄出"]},
]
```

---

## 四、从最简相关度开始

### 4.1 计算词项交集

```python
def score(query_terms, document):
    """计算查询词与文档关键词的交集大小。"""
    return len(set(query_terms) & set(document["terms"]))

# 示例
print(score(["退款"], documents[0]))  # 1（"退款" 匹配）
print(score(["退款", "实体"], documents[0]))  # 2（"退款" + "实体" 都匹配）
print(score(["发票"], documents[0]))  # 0（"发票" 不在 refund-1 的关键词中）
```

> 🧠 **去重原则**：`set(query_terms)` 会把重复的查询词去重。如果用户输入 `["退款", "退款", "退款"]`，score 应该是 1 而不是 3——**重复查询词不应重复计分**。

### 4.2 过滤、排序、截断

```python
def retrieve_top_k(query_terms, documents, k, min_score):
    """从文档集中检索 Top-K 个最相关的文档。
    
    参数：
        query_terms (list[str]): 查询词列表（非空）
        documents (list[dict]): 文档列表，每项含 id、text、terms
        k (int): 最多返回几条结果
        min_score (int): 最低相关度阈值（score < min_score 的文档被过滤）
    
    返回：
        list[dict]: 每项含 {"id": str, "text": str, "score": int}
                   按 score 降序排列，同分按 id 字典序排列
    """
    # 1. 输入校验
    if not isinstance(query_terms, list) or not query_terms:
        raise ValueError("query_terms 必须是非空列表")
    if not all(isinstance(t, str) for t in query_terms):
        raise ValueError("query_terms 中的每个元素必须是字符串")
    if not isinstance(documents, list):
        raise ValueError("documents 必须是列表")
    if not isinstance(k, int) or k < 1:
        raise ValueError("k 必须是正整数")
    if not isinstance(min_score, int) or min_score < 0:
        raise ValueError("min_score 必须是非负整数")
    
    # 2. 去重查询词
    unique_terms = set(query_terms)
    
    # 3. 计算每篇文档的相关度
    scored = []
    for doc in documents:
        s = len(unique_terms & set(doc.get("terms", [])))
        if s >= min_score:
            scored.append({
                "id": doc["id"],
                "text": doc["text"],
                "score": s,
            })
    
    # 4. 稳定排序：按 (-score, id) 排序
    #    先按 score 降序（分数高的在前），同分按 id 字典序
    scored.sort(key=lambda item: (-item["score"], item["id"]))
    
    # 5. 截断到 Top-K
    return scored[:k]
```

> 🧠 **为什么排序规则是 `(-score, id)` 而不是只按 `-score`？** 如果两篇文档的 score 都是 3，只按 `-score` 排序会依赖 Python 的内部排序稳定性——不同 Python 版本或不同运行环境可能给出不同的顺序。加入 `id` 作为第二排序键后，任何环境下同分文档的顺序都是固定的——这对**缓存**和**测试断言**至关重要。

<!-- lab-check:implementation -->

---

## 五、阈值不是越低越好——「宁缺毋滥」

```text
查询: ["退款", "政策"]
文档1: score=2 ✓ 保留（高度相关）
文档2: score=1 ✓ 保留（部分相关）
文档3: score=0 ✗ 过滤（完全无关——"退款"和"政策"都不在它的关键词里）
```

> 🧠 **如果 `min_score=0`，所有文档都会通过——包括完全无关的。** 这会导致模型收到一堆不相关的上下文，可能被误导而编造答案。`min_score` 就像一个质量门槛：低于它的文档宁可不要，让下游节点做「没有证据」的判断，而不是硬塞垃圾信息给模型。

---

## 六、保持契约——为后续升级预留接口

当前用词项交集计算相关度，但返回结构是统一的：

```python
{"id": "refund-1", "text": "实体商品签收后7天内...", "score": 2}
```

后续替换为向量检索时：
- 把 `score()` 函数替换为 cosine_similarity
- 把 `documents` 列表替换为向量数据库查询
- 返回结构**完全相同**——下游节点不需要任何修改

> 🧠 **接口契约的力量**：这就是「抽象」的工程价值。只要检索结果的 `{id, text, score}` 结构不变，回答生成、引用追踪、日志系统都不需要改动。

---

## 七、在 `app.py` 中接入 LangGraph 检索节点

```python
# app.py —— 带检索的 LangGraph 图
from langgraph.graph import StateGraph, START, END
from solution import retrieve_top_k

documents = [
    {"id": "refund-1", "text": "实体商品签收后7天内可申请退款", "terms": ["实体", "退款", "7天"]},
    {"id": "refund-2", "text": "退款审核通常需要1个工作日", "terms": ["退款", "审核", "时效"]},
    {"id": "invoice-1", "text": "电子发票可在订单页下载", "terms": ["发票", "订单"]},
]

def retrieve_node(state):
    """检索节点：根据查询词检索相关文档。"""
    query_terms = state.get("query_terms", [])
    evidence = retrieve_top_k(
        query_terms=query_terms,
        documents=documents,
        k=3,
        min_score=1,
    )
    return {"evidence": evidence, "trace": ["retrieve"]}

def answer_node(state):
    """回答节点：基于检索结果生成回答。"""
    evidence = state.get("evidence", [])
    if not evidence:
        return {"answer": "未找到相关信息，建议联系人工客服。"}
    # 拼接证据（最多3条）
    context = "；".join(item["text"] for item in evidence)
    return {"answer": f"根据资料：{context}", "trace": ["answer"]}

# 搭图
builder = StateGraph(dict)
builder.add_node("retrieve", retrieve_node)
builder.add_node("answer", answer_node)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "answer")
builder.add_edge("answer", END)

graph = builder.compile()

# 测试
result = graph.invoke({"query_terms": ["退款", "时效"]})
print("回答:", result["answer"])
print("证据:", result["evidence"])
```

<!-- lab-check:integration -->

---

## 八、验收——覆盖六类关键场景

| 场景 | 输入 | 预期结果 |
|------|------|---------|
| 高相关 | `["退款"]` | 返回 3 篇，score 降序 |
| 同分稳定 | 两篇文档 score 相同 | 按 id 字典序 |
| 全部低分 | `["xyz"]`（不匹配任何文档） | 返回空列表 |
| 空文档集 | `documents=[]` | 返回空列表 |
| 重复查询词 | `["退款", "退款"]` | 不会重复计分 |
| 非法输入 | `k=0`、`min_score=-1`、`query_terms=[]` | 抛出 ValueError |

---

## 九、常见错误速查

| 现象 | 可能原因 | 排查方法 |
|------|---------|---------|
| 同分文档每次运行顺序不同 | 只按 `-score` 排序，无第二排序键 | 增加 `id` 作为 tiebreaker |
| 重复查询词导致分数虚高 | 没有对 `query_terms` 做 `set()` 去重 | 使用 `set(query_terms)` |
| 过滤后返回了 score=0 的文档 | `min_score=0` 或条件写成了 `s > min_score`（应该是 `>=`） | 检查阈值比较的边界 |
| 返回结果数超过 k | 忘记截断，或截断在排序之前 | 确保 `[:k]` 在排序之后 |

---

## 十、下一步

检索只是找到材料。下一节确保生成答案**只引用实际使用的证据**，并在没有证据时**安全降级**——不让模型凭常识胡编。

<!-- lab-check:acceptance -->
