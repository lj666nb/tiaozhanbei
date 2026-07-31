# LangChain 核心组件深度解析

## 0. 概述：LangChain 组件生态全景

LangChain 是一套用于构建 LLM 驱动应用的框架，其核心设计哲学是**可组合性（Composability）**——将不同的能力封装为独立组件，通过标准接口将它们"链"在一起。本文将深入解析五大核心组件：

```
                        LangChain 核心组件架构

   ┌──────────────────────────────────────────────────────────────────┐
   │                         Agent（决策层）                           │
   │   AgentExecutor: 接收任务 → 思考 → 选工具 → 执行 → 观察 → 循环   │
   └──────────────────────────┬───────────────────────────────────────┘
                              │ 调用
          ┌───────────────────┼───────────────────┐
          v                   v                   v
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Chain       │  │  Tool        │  │  Retriever   │
   │  可组合的    │  │  工具/能力   │  │  检索器      │
   │  执行单元    │  │  封装        │  │  从外部获取  │
   └──────┬───────┘  └──────┬───────┘  │  上下文      │
          │                 │          └──────┬───────┘
          v                 v                 v
   ┌─────────────────────────────────────────────────┐
   │                  Memory（记忆层）                 │
   │  存储对话历史、中间状态，提供跨轮次上下文        │
   └─────────────────────────────────────────────────┘
```

阅读本文前，建议已了解 LangChain 的基本概念（Prompt Template、LLM 封装等），本文聚焦于**中层和高层组件的深入用法**，与入门教程互补。

Image-Prompt(英文绘图词): A flat-design ecosystem panorama showing the five core LangChain components as interconnected modules orbiting around a central "LLM Brain" icon: Chain (linked pipeline arrows), Retriever (magnifying glass over documents), Memory (layered storage cylinders), Tool (wrench and gear), Agent (decision-making robot head), all connected by tech-blue #409EFF circuit lines on white background, layered architecture rings from inner core to outer boundary, 2D vector academic style.

---

## 1. Chain 组件

### 1.1 概念与设计思想

Chain 是 LangChain 最基础的可组合单元。它将多个"可运行对象"（Runnable）串联成一个执行流水线。所有 Chain 都实现 `Runnable` 接口，这意味着它们共享统一的调用方式：`.invoke()`、`.stream()`、`.batch()`。

### 1.2 LLMChain —— 最基础的链

`LLMChain` 将 PromptTemplate + LLM + (可选)OutputParser 串联。虽然是"最基础"的链，但理解它的内部机制是理解所有复杂链的前提。

```python
"""
LLMChain 核心用法演示
展示从基础到高级的所有使用方式
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================================
# 方式 1：使用 LCEL（LangChain Expression Language）—— 推荐
# ============================================================

llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个{role}，擅长{skill}。请用不超过{max_words}字回答。"),
    ("human", "{question}"),
])

# LCEL 用 | 管道符串联组件
chain = prompt | llm | StrOutputParser()

result = chain.invoke({
    "role": "Python 技术专家",
    "skill": "代码优化",
    "max_words": "100",
    "question": "Python 中如何高效合并两个大字典？",
})
print(f"LLMChain 结果: {result}")

# ============================================================
# 方式 2：RunnableLambda 插入自定义逻辑
# ============================================================

from langchain_core.runnables import RunnableLambda, RunnablePassthrough

def count_words(text: str) -> dict:
    """在管道中插入自定义逻辑：统计输出字数"""
    return {"response": text, "word_count": len(text)}

chain_with_logic = (
    prompt
    | llm
    | StrOutputParser()
    | RunnableLambda(count_words)
)

result2 = chain_with_logic.invoke({
    "role": "数据分析师",
    "skill": "数据可视化",
    "max_words": "80",
    "question": "matplotlib 中 subplots 和 subplot 的区别？",
})
print(f"\n带自定义逻辑: {result2}")
```

### 1.3 SequentialChain —— 串联多个步骤

当任务需要**分步骤执行、上一步的输出是下一步的输入**时使用。

```python
"""
SequentialChain: 将多个步骤串联，前一步输出作为后一步输入

适用场景:
  - 翻译 + 润色
  - 大纲生成 + 逐段展开
  - 代码生成 + 代码审查 + 修复
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# ---- 步骤 1: 生成故事大纲 ----
outline_prompt = ChatPromptTemplate.from_template(
    "为一个关于'{topic}'的短篇故事生成一个 5 点大纲。只输出大纲，不要写具体内容。"
)
outline_chain = outline_prompt | llm | StrOutputParser()

# ---- 步骤 2: 根据大纲写正文 ----
write_prompt = ChatPromptTemplate.from_template(
    """根据以下大纲，写一篇约 200 字的短篇故事。

大纲:
{outline}

故事:"""
)
write_chain = write_prompt | llm | StrOutputParser()

# ---- 步骤 3: 起标题 ----
title_prompt = ChatPromptTemplate.from_template(
    "为以下故事起 3 个吸引人的标题（每个标题一行）:\n\n{story}"
)
title_chain = title_prompt | llm | StrOutputParser()

# ---- 组合：使用 RunnablePassthrough 传递中间结果 ----
# 技巧：用 dict 分发不同步骤需要的数据
full_chain = (
    # 第一步：生成大纲
    {"outline": outline_chain, "topic": RunnablePassthrough()}
    # 第二步：写正文（保留大纲以便引用）
    | RunnablePassthrough.assign(story=write_chain)
    # 第三步：起标题
    | RunnablePassthrough.assign(titles=title_chain)
)

# 执行
final = full_chain.invoke("AI 觉醒")
print("=" * 50)
print(f"【大纲】\n{final['outline']}\n")
print(f"【正文】\n{final['story']}\n")
print(f"【标题】\n{final['titles']}")
```

### 1.4 RouterChain —— 条件路由

当输入需要**根据不同条件走不同处理分支**时使用。

```python
"""
RouterChain: 根据输入内容自动选择处理分支

适用场景:
  - 客服系统：根据问题类型路由到不同专家链
  - 多语言翻译：自动识别语言并选择对应翻译链
  - 代码助手：区分"写代码"/"解释代码"/"审查代码"
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# ---- 定义各分支的处理链 ----
# 分支 A: 技术问题
tech_chain = (
    ChatPromptTemplate.from_template(
        "你是一个资深软件工程师。请用专业但易懂的方式回答:\n{question}"
    )
    | llm | StrOutputParser()
)

# 分支 B: 生活建议
life_chain = (
    ChatPromptTemplate.from_template(
        "你是一个温暖的生活顾问。请用亲切的口吻回答:\n{question}"
    )
    | llm | StrOutputParser()
)

# 分支 C: 数学问题
math_chain = (
    ChatPromptTemplate.from_template(
        "你是一个数学老师。请分步骤解答，最后给出答案:\n{question}"
    )
    | llm | StrOutputParser()
)

# ---- 路由分类器 ----
router_prompt = ChatPromptTemplate.from_template(
    """判断以下问题的类型，只回答一个词: tech / life / math

问题: {question}

类型:"""
)
classifier_chain = router_prompt | llm | StrOutputParser()

# ---- RunnableBranch: 类似于 if/elif/else ----
branch_chain = RunnableBranch(
    (lambda x: "tech" in x["category"].lower(), tech_chain),
    (lambda x: "life" in x["category"].lower(), life_chain),
    (lambda x: "math" in x["category"].lower(), math_chain),
    tech_chain,  # 默认分支
)

# ---- 组合：先分类再路由 ----
router_chain = (
    {"category": classifier_chain, "question": lambda x: x["question"]}
    | branch_chain
)

# 测试不同问题
test_questions = [
    "Python 中的 GIL 是什么？对多线程有什么影响？",
    "最近工作压力大，怎么调节心态？",
    "计算 1 到 100 所有质数的和",
]

for q in test_questions:
    # 先看分类结果
    cat = classifier_chain.invoke({"question": q})
    print(f"\n[问题] {q[:40]}...")
    print(f"[分类] {cat.strip()}")
    answer = router_chain.invoke({"question": q})
    print(f"[回答] {answer[:150]}...")
```

### 1.5 TransformChain —— 数据处理管道

当需要对数据进行**不涉及 LLM 的纯转换处理**时使用。

```python
"""
TransformChain: 纯数据处理管道

适用场景:
  - 文本预处理（清理、标准化、分句）
  - 数据格式转换（JSON → Markdown 表格）
  - 后处理（从 LLM 输出中提取结构化数据）
  - 敏感信息脱敏
"""
from langchain_core.runnables import RunnableLambda, RunnableParallel
import json, re


# ---- 预处理函数 ----
def clean_text(data: dict) -> dict:
    """清理输入文本：去除多余空白、统一标点"""
    text = data.get("text", "")
    text = re.sub(r'\s+', ' ', text)         # 合并空白
    text = re.sub(r'[“”]', '"', text)        # 统一引号
    text = text.strip()
    return {"text": text, "char_count": len(text)}


def extract_entities(data: dict) -> dict:
    """简单实体提取（演示用，实际应使用 NER 模型）"""
    text = data.get("text", "")
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    phones = re.findall(r'1[3-9]\d{9}', text)
    urls = re.findall(r'https?://[^\s]+', text)
    return {
        "text": text,
        "char_count": data.get("char_count", 0),
        "entities": {"emails": emails, "phones": phones, "urls": urls}
    }


def mask_sensitive(data: dict) -> dict:
    """脱敏处理"""
    text = data.get("text", "")
    for email in data.get("entities", {}).get("emails", []):
        local, domain = email.split("@")
        masked = local[0] + "***" + "@" + domain
        text = text.replace(email, masked)
    for phone in data.get("entities", {}).get("phones", []):
        text = text.replace(phone, phone[:3] + "****" + phone[-4:])
    return {"text": text, "entities": data.get("entities", {}), "original_length": data.get("char_count", 0)}


# ---- 组合成 TransformChain ----
transform_chain = (
    RunnableLambda(clean_text)
    | RunnableLambda(extract_entities)
    | RunnableLambda(mask_sensitive)
)

# 测试
sample = """
请联系  张三，邮箱是 zhangsan@company.com，
电话 13812345678，或者访问 https://internal.company.com/docs 查看详情。
"""
result = transform_chain.invoke({"text": sample})
print(f"处理后文本: {result['text']}")
print(f"检测到实体: {json.dumps(result['entities'], ensure_ascii=False)}")
print(f"原始长度: {result['original_length']}, 脱敏后长度: {len(result['text'])}")
```

### 1.6 Chain 类型对比总结

| Chain 类型 | 核心 API | 适用场景 | 输入输出 | 复杂度 |
|-----------|---------|---------|---------|-------|
| **LLMChain** | `prompt \| llm \| parser` | 单步 LLM 调用 | 单进单出 | 低 |
| **SequentialChain** | `chain1 \| chain2 \| ...` | 多步骤流水线 | 顺序传递 | 中 |
| **RouterChain** | `RunnableBranch` | 条件分支处理 | 单进多分支 | 中 |
| **TransformChain** | `RunnableLambda` | 纯数据转换 | 单进单出（无 LLM） | 低 |
| **ParallelChain** | `RunnableParallel` | 并行处理 | 单进多出（并发） | 中 |

Image-Prompt(英文绘图词): A flat-design pipeline comparison diagram showing five Chain types as horizontal flow lanes: LLMChain (single arrow: Prompt → LLM → Parser), SequentialChain (three linked arrows in series), RouterChain (a branching tree with four labeled leaf nodes for tech/life/math/default), TransformChain (three processing blocks: Clean → Extract → Mask), and ParallelChain (three parallel arrows merging into one output), all styled in tech-blue #409EFF on white background, 2D vector academic style with lane labels and input-output markers.

---

## 2. Retriever 组件

### 2.1 什么是 Retriever

Retriever（检索器）是 LangChain 中负责**从外部数据源获取相关上下文**的组件。它的核心接口极其简洁：`get_relevant_documents(query) -> List[Document]`。

Retriever 是 RAG（检索增强生成）架构的核心环节。

### 2.2 VectorStoreRetriever —— 基础向量检索

```python
"""
VectorStoreRetriever: 基于向量相似度的语义检索

工作原理:
  1. 将 query 向量化
  2. 在向量数据库中找到最相似的 k 个文档
  3. 返回文档列表
"""
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS  # 本地向量库，无需外部服务

# ---- 准备示例文档 ----
docs = [
    Document(page_content="Python 3.12 引入了更友好的错误提示信息，帮助开发者快速定位问题。", metadata={"topic": "python", "version": "3.12"}),
    Document(page_content="FastAPI 是一个现代高性能 Python Web 框架，基于 Starlette 和 Pydantic。", metadata={"topic": "web", "framework": "fastapi"}),
    Document(page_content="Docker 容器化技术允许将应用及其依赖打包到一个轻量级容器中。", metadata={"topic": "devops", "tool": "docker"}),
    Document(page_content="Redis 是一个开源的内存数据结构存储，用作数据库、缓存和消息代理。", metadata={"topic": "database", "type": "cache"}),
    Document(page_content="PyTorch 提供了动态计算图，使得调试和开发深度学习模型更加灵活。", metadata={"topic": "ml", "framework": "pytorch"}),
    Document(page_content="Kubernetes 是一个容器编排平台，用于自动化部署、扩展和管理容器化应用。", metadata={"topic": "devops", "tool": "k8s"}),
]

# ---- 构建向量库 ----
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = FAISS.from_documents(docs, embeddings)

# ---- 创建 Retriever ----
# search_type="similarity": 标准相似度检索
# search_kwargs={"k": 3}: 返回 top-3
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 3}
)

# ---- 检索 ----
query = "Python Web 开发框架"
results = retriever.invoke(query)

print(f"查询: {query}")
for i, doc in enumerate(results, 1):
    print(f"\n  {i}. [{doc.metadata.get('topic', 'unknown')}] {doc.page_content}")
```

### 2.3 MultiQueryRetriever —— 多角度查询

单个 query 可能无法很好覆盖相关信息。MultiQueryRetriever 用 LLM 从不同角度生成多个查询变体，合并检索结果。

```python
"""
MultiQueryRetriever: 自动生成查询变体，提升召回率

原理:
  原始 query: "如何提升 Python 代码性能"
  LLM 生成变体:
    1. "Python 性能优化技巧"
    2. "Python 代码 profiling 和调优方法"
    3. "提高 Python 执行速度的最佳实践"
  对每个变体独立检索 -> 去重合并 -> 返回

适用场景: query 表述不精确、多义词、需要广泛覆盖
"""
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

llm = ChatOpenAI(model="gpt-4o", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 准备更丰富的文档
tech_docs = [
    Document(page_content="使用 cProfile 模块可以分析 Python 程序的性能瓶颈，找到耗时最多的函数。"),
    Document(page_content="列表推导式比 map+lambda 更快，因为它在 C 层面执行循环。"),
    Document(page_content="使用 PyPy JIT 编译器可以显著提升纯 Python 代码的运行速度。"),
    Document(page_content="numpy 的向量化操作将循环从 Python 层移到 C 层，大幅提升数值计算性能。"),
    Document(page_content="Python 的 asyncio 库提供了异步 I/O 支持，适合高并发网络应用。"),
    Document(page_content="使用 functools.lru_cache 装饰器可以为函数调用结果添加缓存，避免重复计算。"),
]

vectorstore = FAISS.from_documents(tech_docs, embeddings)

# ---- MultiQueryRetriever ----
mq_retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 2}),
    llm=llm,
)

# 查看 LLM 生成了哪些查询变体
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)

results = mq_retriever.invoke("怎么让 Python 跑得更快")
print(f"\n检索到 {len(results)} 条文档:")
for i, doc in enumerate(results, 1):
    print(f"  {i}. {doc.page_content}")
```

### 2.4 ContextualCompressionRetriever —— 上下文压缩

检索到的文档可能包含大量无关内容。ContextualCompressionRetriever 对检索结果进行"二次压缩"，只保留与 query 真正相关的片段。

```python
"""
ContextualCompressionRetriever: 压缩检索结果，提升信息密度

工作流程:
  query → 基础 Retriever（召回宽泛） → Compressor（压缩/过滤） → 精简结果

常用 Compressor:
  - LLMChainExtractor: 用 LLM 从每个文档中提取仅相关的内容
  - LLMChainFilter: 用 LLM 判断文档是否相关，不相关的直接丢弃
  - EmbeddingsFilter: 用嵌入相似度过滤
"""
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

llm = ChatOpenAI(model="gpt-4o", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 包含大量冗余信息的文档
verbose_docs = [
    Document(page_content="""
    Python 是一门非常流行的编程语言。它由 Guido van Rossum 在 1991 年创建。
    Python 的设计哲学强调代码可读性和简洁的语法。
    关于性能优化，Python 提供了 cProfile 模块用于性能分析。
    此外，使用 NumPy 的向量化操作可以显著提升数值计算的效率。
    同时，functools.lru_cache 可以缓存函数结果以避免重复计算。
    Python 社区非常活跃，有大量的第三方库可供使用。
    """),
    Document(page_content="""
    Web 开发是 Python 的一个重要应用领域。Django 和 Flask 是最流行的两个框架。
    Django 是一个全栈框架，提供了 ORM、模板引擎、认证系统等开箱即用的功能。
    Flask 则是一个微框架，更加灵活，开发者可以自由选择组件。
    在部署方面，通常使用 Gunicorn 或 uWSGI 作为 WSGI 服务器，配合 Nginx 作为反向代理。
    关于服务器配置，建议使用至少 2 核 CPU 和 4GB 内存。
    """),
]

vectorstore = FAISS.from_documents(verbose_docs, embeddings)
base_retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# ---- LLMChainExtractor: 从文档中提取与 query 相关的部分 ----
compressor = LLMChainExtractor.from_llm(llm)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever,
)

query = "Python 性能优化方法"
raw = base_retriever.invoke(query)
compressed = compression_retriever.invoke(query)

print(f"查询: {query}\n")
print(f"原始检索（{len(raw)} 条）:")
for d in raw:
    print(f"  [{len(d.page_content)} 字符] {d.page_content[:100]}...")
print(f"\n压缩后（{len(compressed)} 条）:")
for d in compressed:
    print(f"  [{len(d.page_content)} 字符] {d.page_content}")
```

### 2.5 SelfQueryRetriever —— 结构化自查询

当文档有丰富的 metadata，且用户查询包含筛选条件时，SelfQueryRetriever 能将自然语言中的条件自动转换为结构化过滤。

```python
"""
SelfQueryRetriever: 将自然语言查询转换为"语义查询 + 元数据过滤"

示例:
  用户: "2024 年发表的关于 Python 的论文"
  → 语义查询: "Python"
  → 元数据过滤: year == 2024 AND category == "paper"
"""
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

llm = ChatOpenAI(model="gpt-4o", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 结构化文档（带丰富元数据）
papers = [
    Document(page_content="Transformer 架构在 NLP 任务中取得了突破性成果，通过自注意力机制解决了长距离依赖问题。",
             metadata={"year": 2017, "category": "paper", "author": "Vaswani", "citations": 50000}),
    Document(page_content="GPT-4 技术报告展示了大规模语言模型在多模态任务上的强大能力。",
             metadata={"year": 2023, "category": "paper", "author": "OpenAI", "citations": 8000}),
    Document(page_content="LangChain 框架提供了构建 LLM 应用的统一接口，支持 Chain、Agent、Memory 等组件。",
             metadata={"year": 2023, "category": "software", "author": "Harrison Chase", "citations": 3000}),
    Document(page_content="RAG（检索增强生成）通过将外部知识与 LLM 结合，有效减少了幻觉问题。",
             metadata={"year": 2020, "category": "paper", "author": "Lewis", "citations": 12000}),
    Document(page_content="LoRA 微调方法通过低秩矩阵分解，大幅降低了 LLM 微调的参数量和计算开销。",
             metadata={"year": 2021, "category": "paper", "author": "Hu", "citations": 15000}),
    Document(page_content="Chroma 是一个开源的向量数据库，专为 LLM 应用设计，支持高效的相似度搜索。",
             metadata={"year": 2024, "category": "software", "author": "Chroma Team", "citations": 500}),
]

vectorstore = FAISS.from_documents(papers, embeddings)

# ---- 定义元数据字段信息 ----
metadata_field_info = [
    AttributeInfo(name="year", description="发表年份", type="integer"),
    AttributeInfo(name="category", description="类型: paper（论文）或 software（软件工具）", type="string"),
    AttributeInfo(name="author", description="作者或组织", type="string"),
    AttributeInfo(name="citations", description="引用次数", type="integer"),
]

# ---- 文档内容描述 ----
document_content_description = "论文或软件工具的简要介绍"

# ---- 构建 SelfQueryRetriever ----
sq_retriever = SelfQueryRetriever.from_llm(
    llm=llm,
    vectorstore=vectorstore,
    document_contents=document_content_description,
    metadata_field_info=metadata_field_info,
    verbose=True,
)

# 测试：自然语言中包含筛选条件
queries = [
    "2023 年发表的论文",
    "引用次数超过 10000 的研究",
    "关于大语言模型的软件工具",
]

for q in queries:
    print(f"\n{'='*60}")
    print(f"查询: {q}")
    results = sq_retriever.invoke(q)
    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        print(f"  {i}. [{meta.get('year')}] [{meta.get('category')}] "
              f"by {meta.get('author')} | {doc.page_content[:60]}...")
```

### 2.6 Retriever 选型决策表

| 需求场景 | 推荐 Retriever | 关键优势 | 额外开销 |
|---------|---------------|---------|---------|
| 简单语义搜索 | `VectorStoreRetriever` | 零配置，速度快 | 无 |
| 查询表述模糊 | `MultiQueryRetriever` | 自动生成多角度查询 | +N 次 LLM 调用 |
| 文档冗长、信息密度低 | `ContextualCompressionRetriever` | 压缩无关内容 | +1 次 LLM 调用/文档 |
| 需要元数据过滤 | `SelfQueryRetriever` | NL→结构化过滤 | +1 次 LLM 调用 |
| 混合检索（语义+关键词） | `EnsembleRetriever` | 融合多路召回 | 取决于组合的检索器 |
| 大规模文档库 | `ParentDocumentRetriever` | 索引小片段，返回大文档 | 存储两份文档 |
| 时间加权 | `TimeWeightedVectorStoreRetriever` | 优先返回新文档 | 需维护时间戳 |

Image-Prompt(英文绘图词): A flat-design retrieval architecture diagram showing the Retriever workflow: a query entering from the left, splitting into five retrieval strategies shown as parallel cards — VectorStoreRetriever (embedding vector icon), MultiQueryRetriever (multiple branching arrows), ContextualCompressionRetriever (filter funnel squeezing documents), SelfQueryRetriever (structured metadata filter grid), and EnsembleRetriever (multiple inputs merging), all flowing to a final results box, tech-blue #409EFF on white background, 2D vector academic style.

---

## 3. Memory 组件

### 3.1 Memory 的作用与分类

Memory 组件管理对话历史和中间状态，使 LLM 应用具备"记忆"能力。LangChain 提供了多种 Memory 实现，核心区别在于**存储内容**和**存储方式**。

### 3.2 常用 Memory 深入对比

```python
"""
Memory 组件全对比: 从基础到高级的所有 Memory 类型

核心抽象: BaseChatMemory
  - load_memory_variables: 从 Memory 加载上下文
  - save_context: 保存一轮对话
  - clear: 清空 Memory
"""
from langchain.memory import (
    ConversationBufferMemory,
    ConversationBufferWindowMemory,
    ConversationSummaryMemory,
    ConversationSummaryBufferMemory,
    ConversationTokenBufferMemory,
    ConversationKGMemory,
)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# ============================================================
# 1. ConversationBufferMemory — 全量存储
# 最简单: 记住所有对话，不做任何处理
# ============================================================
print("=" * 60)
print("1. ConversationBufferMemory（全量存储）")
buffer_memory = ConversationBufferMemory(return_messages=True)
buffer_memory.save_context(
    {"input": "我叫张三，是一名后端工程师"},
    {"output": "你好张三！有什么可以帮助你的？"}
)
buffer_memory.save_context(
    {"input": "Python 的异步编程怎么做？"},
    {"output": "Python 使用 asyncio 库实现异步编程..."}
)
print(f"  存储的消息数: {len(buffer_memory.chat_memory.messages)}")
print(f"  内存占用: 完整保留所有历史")

# ============================================================
# 2. ConversationBufferWindowMemory — 滑动窗口
# 只保留最近 K 轮对话，控制 token 消耗
# ============================================================
print("\n" + "=" * 60)
print("2. ConversationBufferWindowMemory（滑动窗口, K=2）")
window_memory = ConversationBufferWindowMemory(k=2, return_messages=True)

# 模拟多轮对话
conversations = [
    ("你好！", "你好！有什么可以帮你的？"),
    ("我想了解 Python", "Python 是一门通用编程语言..."),
    ("那 Java 呢？", "Java 也是一门流行的语言..."),
    ("两者有什么区别？", "Python 更简洁，Java 更严谨..."),
]
for user, ai in conversations:
    window_memory.save_context({"input": user}, {"output": ai})

loaded = window_memory.load_memory_variables({})
msgs = loaded.get("history", [])
print(f"  总轮次: {len(conversations)}, 保留轮次: {len(msgs)//2}")
print(f"  最早保留的消息: {msgs[0].content[:40] if msgs else '无'}...")
print(f"  内存占用: 固定窗口，低")

# ============================================================
# 3. ConversationSummaryMemory — 摘要存储
# 用 LLM 对历史对话进行渐进式摘要，只存摘要不存原文
# ============================================================
print("\n" + "=" * 60)
print("3. ConversationSummaryMemory（摘要存储）")
summary_memory = ConversationSummaryMemory(llm=llm, return_messages=True)

# 模拟长对话
long_conversations = [
    ("帮我设计一个用户系统的数据库表结构", "好的，用户表应包含 id, username, email, password_hash, created_at 等字段..."),
    ("需要支持手机号登录吗？", "建议添加 phone 和 phone_verified 字段，并创建 user_auth_methods 关联表..."),
    ("那权限系统呢？", "推荐使用 RBAC 模型，需要 roles 表、permissions 表和 user_roles 关联表..."),
    ("缓存策略应该怎么设计？", "可以使用 Redis 缓存用户 session 和常用查询，设置合理的 TTL..."),
]
for user, ai in long_conversations:
    summary_memory.save_context({"input": user}, {"output": ai})

vars = summary_memory.load_memory_variables({})
print(f"  摘要内容（压缩了 {len(long_conversations)} 轮对话）:")
print(f"  {str(vars.get('history', ''))[:300]}...")
print(f"  内存占用: 极低，只存摘要文本")

# ============================================================
# 4. ConversationTokenBufferMemory — Token 限制
# 保留不超过 N 个 token 的最近对话
# ============================================================
print("\n" + "=" * 60)
print("4. ConversationTokenBufferMemory（Token 限制, max=200）")
token_memory = ConversationTokenBufferMemory(
    llm=llm, max_token_limit=200, return_messages=True
)

for user, ai in long_conversations:
    token_memory.save_context({"input": user}, {"output": ai})

loaded = token_memory.load_memory_variables({})
msgs = loaded.get("history", [])
print(f"  总轮次: {len(long_conversations)}, 保留消息: {len(msgs)} 条")
print(f"  超出限制的早期对话已被丢弃")
print(f"  内存占用: 可控的上限")

# ============================================================
# 5. ConversationSummaryBufferMemory — 摘要 + 窗口
# 超过窗口的部分做摘要，窗口内的保留原文
# 结合了 Summary 的低成本和 Window 的精确性
# ============================================================
print("\n" + "=" * 60)
print("5. ConversationSummaryBufferMemory（摘要 + 窗口）")
hybrid_memory = ConversationSummaryBufferMemory(
    llm=llm, max_token_limit=300, return_messages=True
)

for user, ai in long_conversations:
    hybrid_memory.save_context({"input": user}, {"output": ai})

vars = hybrid_memory.load_memory_variables({})
print(f"  Memory 内容（前 300 字）: {str(vars.get('history', ''))[:300]}...")
print(f"  内存占用: 中等，结合了两种策略的优点")
```

### 3.3 自定义 Memory 实现

```python
"""
自定义 Memory: 实现带过期时间和重要性评分的记忆

实际业务中，标准 Memory 往往不够用，需要定制:
  - 某些记忆需要过期（如一次性验证码上下文）
  - 某些记忆需要评分（用户偏好应该比闲聊更"重要"）
  - 需要混合多种存储后端（Redis + PostgreSQL）
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from langchain.memory import BaseMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
import json


class MemoryEntry(BaseModel):
    """单条记忆条目"""
    content: str
    role: str                              # "human" | "ai"
    timestamp: datetime = Field(default_factory=datetime.now)
    importance: float = 1.0                # 重要性评分 (1.0 = 普通)
    ttl_seconds: Optional[int] = None      # 存活时间（秒），None = 永不过期


class SmartMemory(BaseMemory, BaseModel):
    """
    智能记忆组件:
      - 带 TTL（过期时间）
      - 带重要性评分（检索时加权）
      - 支持关键词检索（而非返回所有历史）
    """
    entries: List[MemoryEntry] = Field(default_factory=list)
    return_messages: bool = True
    memory_key: str = "history"
    input_key: Optional[str] = None
    output_key: Optional[str] = None

    # ---- 核心属性 ----
    @property
    def memory_variables(self) -> List[str]:
        return [self.memory_key]

    # ---- 加载记忆（带过期检查 + 重要性排序）----
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now()

        # 1. 过滤过期条目
        active = []
        for entry in self.entries:
            if entry.ttl_seconds is not None:
                age = (now - entry.timestamp).total_seconds()
                if age > entry.ttl_seconds:
                    continue  # 已过期，丢弃
            active.append(entry)

        # 2. 按重要性降序排序（重要内容优先出现在上下文中）
        active.sort(key=lambda e: e.importance, reverse=True)

        # 3. 构建输出
        if self.return_messages:
            messages = [
                HumanMessage(content=e.content) if e.role == "human" else AIMessage(content=e.content)
                for e in active
            ]
            return {self.memory_key: messages}
        else:
            text = "\n".join(f"{'User' if e.role=='human' else 'AI'}: {e.content}" for e in active)
            return {self.memory_key: text}

    # ---- 保存上下文 ----
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        input_str = inputs.get(self.input_key or "input", "")
        output_str = outputs.get(self.output_key or "output", "")

        # 启发式重要性评分: 包含关键词的对话更"重要"
        important_keywords = ["配置", "偏好", "密码", "任务", "bug", "错误", "规则"]
        importance = 1.0
        combined = input_str + output_str
        for kw in important_keywords:
            if kw in combined:
                importance = min(2.5, importance + 0.3)

        now = datetime.now()
        self.entries.append(MemoryEntry(
            content=input_str, role="human",
            timestamp=now, importance=importance, ttl_seconds=None
        ))
        self.entries.append(MemoryEntry(
            content=output_str, role="ai",
            timestamp=now, importance=importance, ttl_seconds=None
        ))

    # ---- 添加带 TTL 的记忆（如一次性信息）----
    def add_temporary(self, content: str, ttl_seconds: int = 300, role: str = "ai") -> None:
        """添加临时记忆，过期后自动消失"""
        self.entries.append(MemoryEntry(
            content=content, role=role,
            timestamp=datetime.now(), importance=1.0,
            ttl_seconds=ttl_seconds
        ))

    # ---- 清空 ----
    def clear(self) -> None:
        self.entries.clear()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    memory = SmartMemory()

    # 普通对话
    memory.save_context({"input": "今天天气真好"}, {"output": "是啊，适合出去走走"})
    # 重要对话（含关键词"配置"）
    memory.save_context(
        {"input": "记住我的配置：主题用暗色模式"},
        {"output": "好的，已记住你的偏好配置：暗色模式"}
    )

    # 临时记忆（5 秒后过期）
    memory.add_temporary("验证码 884321 已发送到你的手机", ttl_seconds=5)
    print("验证码 884321 已发送到你的手机", ttl_seconds=5)

    vars1 = memory.load_memory_variables({})
    print(f"当前记忆（{len(vars1.get('history', []))} 条）:")
    for m in vars1.get("history", []):
        print(f"  [{type(m).__name__}] importance={m.additional_kwargs.get('importance', 1.0)}: {m.content[:50]}...")
```

### 3.4 Memory 选型对比

| Memory 类型 | 存储形式 | Token 增长 | 信息丢失 | 适用场景 |
|-----------|---------|-----------|---------|---------|
| `BufferMemory` | 全量原文 | 线性增长 | 无丢失 | 短对话（<10 轮） |
| `BufferWindowMemory` | 最近 K 轮原文 | 固定上限 | 早期对话丢失 | 中等对话，只关注近期 |
| `SummaryMemory` | 渐进式摘要 | 缓慢增长 | 细节丢失 | 长对话，关注主题 |
| `TokenBufferMemory` | Token 限制内原文 | 固定上限 | 早期对话丢失 | Token 敏感的 API 调用 |
| `SummaryBufferMemory` | 摘要 + 近期原文 | 可控增长 | 早期细节丢失 | 长对话 + 需近期精确性 |
| `KGMemory` | 知识图谱 | 稳定 | 只保留结构化事实 | 需要关系推理 |
| **自定义 Memory** | 任意 | 可控 | 可控 | 有特殊业务需求 |

Image-Prompt(英文绘图词): A flat-design comparison of six Memory types as labeled storage icons in a grid layout: BufferMemory (full database cylinder labeled "All History"), BufferWindowMemory (sliding window frame showing only recent items), SummaryMemory (compressed document with sparkle icon), TokenBufferMemory (fuel-gauge meter with token limit marker), SummaryBufferMemory (hybrid icon combining document and window frame), and a custom gear-icon for Custom Memory, all styled in tech-blue #409EFF on white background, 2D vector academic style with memory-capacity bar indicators.

---

## 4. Tool 组件

### 4.1 @tool 装饰器 —— 最简工具定义

```python
"""
@tool 装饰器: 将 Python 函数一键转换为 LangChain Tool

Tool 的核心接口:
  - name: 工具名称（LLM 用它来选择和调用）
  - description: 工具描述（LLM 靠它理解工具的功能和使用方式）
  - args_schema: 参数定义（指导 LLM 如何传参）
"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Optional
import requests
import json


# ---- 方式 1: 基础 @tool 装饰器 ----
@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """获取指定城市的当前天气信息。

    Args:
        city: 城市名称，支持中文（如"北京"）和英文（如"Beijing"）
        unit: 温度单位，celsius（摄氏度）或 fahrenheit（华氏度），默认 celsius
    """
    # 模拟天气 API（实际应替换为真实 API 调用）
    weather_data = {
        "北京": {"temp": 28, "humidity": 65, "condition": "晴"},
        "上海": {"temp": 32, "humidity": 80, "condition": "多云"},
        "深圳": {"temp": 30, "humidity": 75, "condition": "阵雨"},
    }
    data = weather_data.get(city, {"temp": 25, "humidity": 60, "condition": "未知"})
    temp = data["temp"] if unit == "celsius" else data["temp"] * 9/5 + 32
    unit_str = "°C" if unit == "celsius" else "°F"
    return f"{city}: {data['condition']}, 温度 {temp:.1f}{unit_str}, 湿度 {data['humidity']}%"


# ---- 方式 2: 结构化参数定义（Pydantic）----
class CalculatorInput(BaseModel):
    """计算器输入参数"""
    expression: str = Field(
        description="要计算的数学表达式，例如 '2 + 3 * 4' 或 'sqrt(16)'"
    )


@tool(args_schema=CalculatorInput)
def calculator(expression: str) -> str:
    """安全地计算数学表达式。支持 +, -, *, /, **, sqrt(), abs() 等。

    注意: 使用受限的 eval 环境，不接受任何导入或函数调用。
    """
    # 安全检查：白名单允许的函数
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sqrt": __import__("math").sqrt,
        "pow": pow, "int": int, "float": float,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"计算结果: {expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# ---- 方式 3: 异步工具 ----
@tool
async def search_documentation(query: str, version: str = "latest") -> str:
    """搜索 Python 官方文档。

    Args:
        query: 搜索关键词，如 "asyncio" 或 "list comprehension"
        version: Python 版本，如 "3.12" 或 "latest"
    """
    # 模拟文档搜索（实际应调用文档 API 或网页抓取）
    mock_docs = {
        "asyncio": "asyncio 是 Python 的异步 I/O 库，提供事件循环、协程、任务等...",
        "list comprehension": "列表推导式 [expr for item in iterable if condition] 是...",
    }
    result = mock_docs.get(query.lower(), f"未找到关于 '{query}' 的文档。")
    return f"[Python {version} 文档] {result}"


# 查看工具信息
print("已注册工具:")
for t in [get_weather, calculator, search_documentation]:
    print(f"  - {t.name}: {t.description[:50]}...")
    if hasattr(t, 'args_schema') and t.args_schema:
        print(f"    参数: {t.args_schema.schema().get('properties', {}).keys()}")
```

### 4.2 StructuredTool —— 复杂参数处理

```python
"""
StructuredTool: 当 @tool 装饰器不够用时的进阶选择
适用于参数校验复杂、需要自定义错误处理、或从已有类方法生成工具
"""
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, validator
from typing import List, Literal
from datetime import datetime


# ---- 复杂参数 Schema ----
class EmailInput(BaseModel):
    """发送邮件的参数定义"""
    to: List[str] = Field(description="收件人邮箱列表")
    subject: str = Field(description="邮件主题", min_length=1, max_length=200)
    body: str = Field(description="邮件正文（支持 Markdown）")
    priority: Literal["low", "normal", "high"] = Field(
        default="normal", description="优先级: low/normal/high"
    )
    cc: List[str] = Field(default_factory=list, description="抄送邮箱列表")
    schedule_time: Optional[str] = Field(
        default=None, description="定时发送时间，ISO 格式，如 2026-07-09T15:00:00"
    )

    @validator("to", "cc")
    def validate_emails(cls, v):
        """校验邮箱格式"""
        import re
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        for email in v:
            if not re.match(pattern, email):
                raise ValueError(f"无效邮箱格式: {email}")
        return v

    @validator("schedule_time")
    def validate_schedule(cls, v):
        """校验定时时间必须在未来"""
        if v:
            scheduled = datetime.fromisoformat(v)
            if scheduled <= datetime.now():
                raise ValueError("定时发送时间必须在未来")
        return v


def send_email(
    to: List[str],
    subject: str,
    body: str,
    priority: str = "normal",
    cc: List[str] = None,
    schedule_time: str = None,
) -> str:
    """通过公司邮件系统发送邮件。

    注意事项:
      - 单次最多发送给 50 个收件人
      - 邮件正文最大 100KB
      - 高优先级邮件会绕过低优先级队列
    """
    cc = cc or []
    schedule_info = f"，定时发送: {schedule_time}" if schedule_time else ""
    return (
        f"[邮件已{'排期' if schedule_time else '发送'}]\n"
        f"  收件人: {', '.join(to)}\n"
        f"  抄送: {', '.join(cc) if cc else '无'}\n"
        f"  主题: {subject}\n"
        f"  优先级: {priority}{schedule_info}\n"
        f"  正文预览: {body[:80]}..."
    )


# ---- 创建 StructuredTool ----
email_tool = StructuredTool.from_function(
    func=send_email,
    name="send_email",
    description="通过公司邮件系统发送邮件，支持定时发送和优先级设置",
    args_schema=EmailInput,
    # handle_tool_error: 自定义错误返回（而非抛出异常）
    handle_tool_error=True,
)

# 测试
print(email_tool.invoke({
    "to": ["zhang@company.com"],
    "subject": "项目周报",
    "body": "本周完成了用户模块的开发...",
    "priority": "normal",
}))

# 测试参数校验
try:
    email_tool.invoke({
        "to": ["invalid-email"],
        "subject": "Test",
        "body": "Test",
    })
except Exception as e:
    print(f"\n参数校验失败（预期行为）: {e}")
```

### 4.3 Toolkit —— 工具组合模式

```python
"""
Toolkit: 将相关工具打包为一个逻辑单元

常见场景:
  - 数据库工具包: query, insert, update, delete
  - 文件操作工具包: read_file, write_file, list_dir
  - GitHub 工具包: create_issue, search_code, create_pr
"""
from langchain_core.tools import BaseToolkit, BaseTool
from typing import List


class DatabaseToolkit(BaseToolkit):
    """
    数据库操作工具包: 将与数据库相关的所有工具打包在一起。

    使用 Toolkit 的好处:
      1. 共享连接/配置: 所有工具复用同一个数据库连接
      2. 统一管理: 一次性注册所有相关工具
      3. 更好的代码组织: 相关功能内聚在一起
    """

    # 共享配置（所有工具共享）
    connection_string: str
    max_retries: int = 3

    def get_tools(self) -> List[BaseTool]:
        """返回工具包中的所有工具"""
        # 将共享配置注入到每个工具中
        return [
            self._create_query_tool(),
            self._create_insert_tool(),
            self._create_describe_tool(),
        ]

    def _create_query_tool(self) -> BaseTool:
        """创建查询工具（L0 - 只读）"""
        conn_str = self.connection_string

        @tool
        def db_query(sql: str) -> str:
            """执行只读 SQL 查询。仅支持 SELECT 语句。

            Args:
                sql: 要执行的 SELECT 查询语句
            """
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith("SELECT"):
                return "错误: db_query 仅支持 SELECT 查询。修改操作请使用其他工具。"

            # 模拟数据库查询
            if "users" in sql.lower():
                return '[{"id": 1, "name": "Alice", "email": "alice@example.com"}, {"id": 2, "name": "Bob", "email": "bob@example.com"}]'
            return "[]"

        db_query.name = "db_query"
        return db_query

    def _create_insert_tool(self) -> BaseTool:
        """创建插入工具（L2 - 需审批）"""
        conn_str = self.connection_string

        @tool
        def db_insert(table: str, data_json: str) -> str:
            """向指定表插入数据。需要审批后才能执行。

            Args:
                table: 目标表名
                data_json: JSON 格式的插入数据
            """
            data = json.loads(data_json)
            # 模拟插入
            return f"已向 {table} 插入数据: {json.dumps(data, ensure_ascii=False)}"

        db_insert.name = "db_insert"
        return db_insert

    def _create_describe_tool(self) -> BaseTool:
        """创建描述表结构工具（L0 - 只读）"""
        conn_str = self.connection_string

        @tool
        def db_describe(table: str) -> str:
            """获取指定表的结构信息（字段名、类型、约束）。

            Args:
                table: 要查询的表名
            """
            schemas = {
                "users": "id INT PRIMARY KEY, name VARCHAR(100), email VARCHAR(255) UNIQUE, created_at TIMESTAMP",
                "orders": "id INT PRIMARY KEY, user_id INT FK, amount DECIMAL(10,2), status VARCHAR(20)",
            }
            return schemas.get(table, f"未找到表 '{table}'")

        db_describe.name = "db_describe"
        return db_describe


# 使用 Toolkit
db_toolkit = DatabaseToolkit(connection_string="postgresql://localhost/mydb")
tools = db_toolkit.get_tools()
print(f"数据库工具包包含 {len(tools)} 个工具:")
for t in tools:
    print(f"  - {t.name}: {t.description[:60]}...")
```

### 4.4 工具组合模式

| 模式 | 说明 | 适用场景 | 示例 |
|------|------|---------|------|
| **单一工具** | `@tool` 装饰单个函数 | 独立功能 | `get_weather`, `calculator` |
| **StructuredTool** | 复杂参数 + 自定义校验 | 参数规则复杂 | `send_email`（邮箱校验） |
| **Toolkit** | 打包一组相关工具 | 同领域多工具 | `DatabaseToolkit`, `GitHubToolkit` |
| **工具链** | 工具 A 的输出作为工具 B 的输入 | 多步骤操作 | `search_file → read_file → summarize` |
| **动态工具生成** | 运行时根据上下文动态创建工具 | API 动态发现 | 根据 OpenAPI spec 生成工具 |

Image-Prompt(英文绘图词): A flat-design tool ecosystem diagram showing three tool definition approaches: a @tool decorator wrapping a simple function block with a wand icon, a StructuredTool block with Pydantic schema overlay showing validated fields, and a Toolkit container box grouping three related tools (query, insert, describe) sharing a common database connection, arranged in a row with increasing complexity arrows, tech-blue #409EFF on white background, 2D vector academic style.

---

## 5. Agent 组件

### 5.1 AgentExecutor 工作流深入

Agent 是 LangChain 的最高层抽象：它使用 LLM 作为"大脑"，自主决定使用哪些工具、以什么顺序使用、何时停止。

```
AgentExecutor 内部循环:

    ┌──────────────────────────────────────────┐
    │              AgentExecutor                │
    │                                          │
    │  ┌─────────┐    ┌──────────────┐        │
    │  │ 输入    │───>│ Agent (LLM)  │        │
    │  │(任务)   │    │ 思考下一步   │        │
    │  └─────────┘    └──────┬───────┘        │
    │                        │                │
    │              ┌─────────┴─────────┐      │
    │              v                   v      │
    │        [AgentFinish]      [AgentAction] │
    │              │                   │      │
    │              v                   v      │
    │         ┌────────┐      ┌──────────┐    │
    │         │ 返回   │      │ 执行工具 │    │
    │         │ 结果   │      └────┬─────┘    │
    │         └────────┘           │          │
    │                              v          │
    │                     ┌──────────────┐    │
    │                     │ Observation  │    │
    │                     │ (工具结果)    │    │
    │                     └──────┬───────┘    │
    │                            │            │
    │                            v            │
    │                    回到 Agent (LLM) ──┘ 循环
    └──────────────────────────────────────────┘
```

### 5.2 Agent 类型对比与实战

```python
"""
Agent 类型全景对比: OpenAI Functions / ReAct / Structured Chat

核心区别:
  - OpenAI Functions: 使用 function calling API（最稳定）
  - ReAct: Reason + Act，不使用 function calling（最通用）
  - Structured Chat: 支持多参数工具的结构化对话（最灵活）
"""
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import (
    create_openai_functions_agent,
    create_react_agent,
    create_structured_chat_agent,
    AgentExecutor,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain import hub  # LangChain Hub: 社区共享的 prompt 模板

# ============================================================
# 准备 LLM 和工具（三种 Agent 共享）
# ============================================================
llm = ChatOpenAI(model="gpt-4o", temperature=0)

@tool
def search_info(topic: str) -> str:
    """搜索关于某个主题的信息。适用于事实查询。"""
    fake_db = {
        "python": "Python 由 Guido van Rossum 于 1991 年创建，最新稳定版为 3.12。",
        "rust": "Rust 是 Mozilla 开发的系统编程语言，以内存安全著称，最新版为 1.78。",
        "docker": "Docker 是一个容器化平台，使用 Go 语言编写，2013 年首次发布。",
    }
    return fake_db.get(topic.lower(), f"未找到关于 {topic} 的详细信息")

@tool
def text_tool(text: str, operation: str) -> str:
    """对文本执行操作。operation: reverse(反转), upper(大写), word_count(字数统计)"""
    if operation == "reverse":
        return text[::-1]
    elif operation == "upper":
        return text.upper()
    elif operation == "word_count":
        return f"字数: {len(text.split())}"
    return f"未知操作: {operation}"

tools = [search_info, text_tool]


# ============================================================
# 1. OpenAI Functions Agent（推荐 —— 最稳定）
# ============================================================
print("=" * 60)
print("1. OpenAI Functions Agent")
print("=" * 60)

functions_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有用的 AI 助手。使用工具来回答问题。如果无法获取信息，如实告知。"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

functions_agent = create_openai_functions_agent(llm, tools, functions_prompt)
functions_executor = AgentExecutor(
    agent=functions_agent,
    tools=tools,
    verbose=True,
    max_iterations=5,
    handle_parsing_errors=True,
    return_intermediate_steps=True,  # 返回中间步骤（调试用）
)

result = functions_executor.invoke({"input": "搜索 Python 的信息，然后告诉我反转'Hello World'是什么"})
print(f"\n最终结果: {result['output']}")
print(f"中间步骤数: {len(result.get('intermediate_steps', []))}")


# ============================================================
# 2. ReAct Agent（通用 —— 不依赖 function calling）
# ============================================================
print("\n" + "=" * 60)
print("2. ReAct Agent (Reason + Act)")
print("=" * 60)

# ReAct 使用独特的 prompt 格式
react_prompt = hub.pull("hwchase17/react")  # 从 Hub 拉取标准 ReAct prompt
# 也可以自定义:
# react_prompt = PromptTemplate.from_template("""
# You have access to the following tools:
# {tools}
# Use the format: Question: the input question
# Thought: what you should do
# Action: the tool name
# Action Input: the tool input
# Observation: the tool output
# ... (repeat Thought/Action/Action Input/Observation)
# Thought: I now know the final answer
# Final Answer: the final answer
# Question: {input}
# {agent_scratchpad}
# """)

react_agent = create_react_agent(llm, tools, react_prompt)
react_executor = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True,
    max_iterations=5,
    handle_parsing_errors=True,
)

result2 = react_executor.invoke({"input": "Docker 是什么时候发布的？"})
print(f"\n最终结果: {result2['output']}")


# ============================================================
# 3. Structured Chat Agent（最灵活 —— 支持复杂多参数工具）
# ============================================================
print("\n" + "=" * 60)
print("3. Structured Chat Agent")
print("=" * 60)

structured_prompt = ChatPromptTemplate.from_messages([
    ("system", """Respond to the human as helpfully and accurately as possible.
You have access to the following tools:
{tools}

Use a json blob to specify a tool, with an 'action' key (tool name)
and an 'action_input' key (tool input).
Valid 'action' values: "Final Answer" or {tool_names}

Provide only ONE action per $JSON_BLOB, as shown:
```
{
  "action": $TOOL_NAME,
  "action_input": $INPUT
}
```

Follow this format:
Question: input question
Thought: consider what to do
Action:
$JSON_BLOB
Observation: action result
... (repeat Thought/Action/Observation)
Thought: I now know the final answer
Action:
```
{
  "action": "Final Answer",
  "action_input": "Final response to human"
}
```
Begin!"""),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

structured_agent = create_structured_chat_agent(llm, tools, structured_prompt)
structured_executor = AgentExecutor(
    agent=structured_agent,
    tools=tools,
    verbose=True,
    max_iterations=5,
    handle_parsing_errors=True,
)

result3 = structured_executor.invoke(
    {"input": "把 'Hello World' 转为大写，然后统计有多少个词"}
)
print(f"\n最终结果: {result3['output']}")
```

### 5.3 Agent 类型决策表

| Agent 类型 | 底层机制 | 稳定性 | 多参数工具 | 模型要求 | 推荐场景 |
|-----------|---------|-------|-----------|---------|---------|
| **OpenAI Functions** | Function Calling API | 最高 | 原生支持 | OpenAI 模型 | 生产环境首选 |
| **OpenAI Tools** | Parallel Tool Calling | 最高 | 原生支持 | OpenAI 模型 | 需要并行调用多工具 |
| **ReAct** | 文本解析 (Thought/Action/Observation) | 中（解析错误） | 序列化传参 | 任意模型 | 非 OpenAI 模型 / 可解释性 |
| **Structured Chat** | JSON 解析 | 中-高 | 原生支持 | 任意模型 | 复杂多参数工具 |
| **XML Agent** | XML 解析 | 中 | 序列化传参 | Anthropic 模型 | Claude 模型的自然选择 |
| **JSON Chat** | JSON blob 解析 | 中-高 | 原生支持 | 任意模型 | 结构化输出偏好 |

### 5.4 自定义 AgentExecutor —— 高级控制

```python
"""
自定义 AgentExecutor: 在标准循环中加入日志、重试、限流、提前终止

标准 AgentExecutor 提供了 .invoke() 和 .stream()，但有时我们需要
在 Agent 循环的每一步中插入自定义逻辑。
"""
from typing import Any, Dict, List, Tuple, Union
from langchain.agents import AgentExecutor
from langchain_core.agents import AgentAction, AgentFinish
from langchain.callbacks.base import BaseCallbackHandler
import time
from datetime import datetime


class ObservableAgentExecutor(AgentExecutor):
    """
    增强了可观测性和控制的 AgentExecutor:

    新增能力:
      - 步骤级时间追踪
      - 最大执行时间限制
      - 工具调用频率限制
      - 自动重试（解析错误时）
    """

    max_execution_time: int = 60        # 最大执行时间（秒）
    tool_call_limit: int = 20           # 工具调用最大次数
    retry_on_parse_error: bool = True   # 解析错误时是否重试
    start_time: float = 0.0

    def _take_next_step(
        self,
        name_to_tool_map: Dict,
        color_mapping: Dict,
        inputs: Dict,
        intermediate_steps: List[Tuple[AgentAction, str]],
        run_manager=None,
    ) -> Union[AgentFinish, List[Tuple[AgentAction, str]]]:
        """
        重写核心步骤方法，在每个 Agent 步骤前后插入自定义逻辑。
        """

        # ---- 检查1: 超时 ----
        if self.start_time == 0.0:
            self.start_time = time.time()
        elapsed = time.time() - self.start_time
        if elapsed > self.max_execution_time:
            return AgentFinish(
                return_values={"output": f"执行超时（已运行 {elapsed:.1f} 秒，超过 {self.max_execution_time} 秒限制）。任务部分完成。"},
                log=f"超时终止"
            )

        # ---- 检查2: 工具调用次数 ----
        if len(intermediate_steps) >= self.tool_call_limit:
            return AgentFinish(
                return_values={"output": f"已达到最大工具调用次数 ({self.tool_call_limit})。请根据已有信息给出最佳答案。"},
                log=f"达到工具调用上限"
            )

        # ---- 记录步骤信息 ----
        step_num = len(intermediate_steps) + 1
        print(f"\n[Step {step_num}] 已用时间: {elapsed:.1f}s, 已调用工具: {len(intermediate_steps)}")

        # ---- 执行原始逻辑 ----
        try:
            result = super()._take_next_step(
                name_to_tool_map, color_mapping, inputs, intermediate_steps, run_manager
            )
            return result
        except Exception as e:
            if self.retry_on_parse_error and "parsing" in str(e).lower():
                print(f"[警告] 解析错误，自动重试: {str(e)[:100]}")
                # 让 LLM 重新尝试（通过加一条错误观察）
                return super()._take_next_step(
                    name_to_tool_map, color_mapping, inputs, intermediate_steps, run_manager
                )
            raise


# 演示
llm = ChatOpenAI(model="gpt-4o", temperature=0)

@tool
def slow_tool(query: str) -> str:
    """模拟一个慢速工具"""
    time.sleep(0.5)  # 模拟网络延迟
    return f"查询 '{query}' 的结果: 一切正常"

enhanced_executor = ObservableAgentExecutor(
    agent=create_openai_functions_agent(
        llm, [slow_tool],
        ChatPromptTemplate.from_messages([
            ("system", "你是一个助手。"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
    ),
    tools=[slow_tool],
    max_execution_time=30,
    tool_call_limit=10,
    retry_on_parse_error=True,
    verbose=False,  # 使用我们自己的日志
    return_intermediate_steps=True,
)

result = enhanced_executor.invoke({"input": "查询三次天气，每次查询不同的城市"})
print(f"\n最终结果: {result['output']}")
```

Image-Prompt(英文绘图词): A flat-design AgentExecutor cycle diagram showing the core Agent loop as a circular flowchart: "Input Task" → "Agent (LLM) Thinks" → branching to either "AgentFinish" (output result) or "AgentAction" (select and execute a Tool) → "Observation" (tool result feeds back) → looping back to the Agent, with iteration counter and max_iterations limit shown as a progress bar, tech-blue #409EFF on white background, 2D vector academic style with directional arrows.

---

## 6. 组件选型决策树

```
需要构建 LLM 应用？
│
├── 简单的单步 LLM 调用？
│   └── 使用 LLMChain (prompt | llm | parser)
│
├── 需要多步骤流水线？
│   ├── 步骤顺序固定 → SequentialChain
│   ├── 步骤需根据条件路由 → RouterChain / RunnableBranch
│   └── 纯数据处理（无 LLM）→ TransformChain
│
├── 需要从外部数据源获取上下文？
│   ├── 简单语义搜索 → VectorStoreRetriever
│   ├── 查询表述不明确 → MultiQueryRetriever
│   ├── 检索结果太冗长 → ContextualCompressionRetriever
│   ├── 需要元数据过滤 → SelfQueryRetriever
│   └── 多路召回融合 → EnsembleRetriever
│
├── 需要跨轮次记忆？
│   ├── 对话短（<10 轮）→ BufferMemory
│   ├── 对话长但只关注近期 → BufferWindowMemory
│   ├── 对话长且关注主题 → SummaryMemory
│   ├── Token 预算严格 → TokenBufferMemory
│   └── 有特殊需求 → 自定义 Memory
│
├── 需要给 LLM 装备工具？
│   ├── 简单函数 → @tool 装饰器
│   ├── 复杂参数校验 → StructuredTool
│   ├── 一组相关工具 → Toolkit
│   └── 运行中发现 API → 动态工具生成
│
└── 需要 LLM 自主决策？
    ├── 使用 OpenAI 模型？
    │   ├── 简单任务 → OpenAI Functions Agent
    │   └── 需要并行调用多工具 → OpenAI Tools Agent
    ├── 使用其他模型？→ ReAct Agent
    └── 复杂多参数工具？→ Structured Chat Agent
```

Image-Prompt(英文绘图词): A flat-design decision tree flowchart starting from a root question box "Build LLM App?" with branching paths: simple single-step → LLMChain leaf; multi-step → splits into SequentialChain (fixed order), RouterChain (conditional), TransformChain (no LLM); needs external data → Retriever subtree with five leaf strategies; needs memory → Memory subtree with five storage types; needs LLM autonomy → Agent subtree splitting into OpenAI Functions, ReAct, and Structured Chat leaves, all branches in tech-blue #409EFF on white background, 2D vector academic style.

---

## 7. 实践建议

### 7.1 组件组合最佳实践

1. **从最简单的链开始**。不要一上来就构建复杂 Agent。先用 `LLMChain` 验证 prompt 效果，再逐步增加 Retriever，最后才引入 Agent。
2. **LCEL 是首选**。`prompt | llm | parser` 的管道语法比旧的 `LLMChain(llm=..., prompt=...)` 更灵活，更利于组合和调试。
3. **Memory 是双刃剑**。过多的历史会让 LLM 混淆，过少则丢失上下文。建议从 `BufferWindowMemory(k=5)` 开始调优。
4. **Agent 的 max_iterations 要设上限**。无限循环是 Agent 最常见的失败模式。5-10 轮是一个合理的默认值。
5. **工具描述是 Agent 的"说明书"**。花时间写好 `description` 和 `args_schema` 中的 `Field(description=...)`，这直接影响 Agent 的工具选择准确度。

### 7.2 调试技巧

| 问题 | 排查方法 |
|------|---------|
| Agent 不调用工具 | 检查工具 description 是否清晰，是否与任务相关 |
| Agent 反复调用同一工具 | 工具返回的结果可能不够明确，LLM 认为需要更多信息 |
| Memory 信息丢失 | 检查 Memory 的 k/max_token_limit 设置 |
| 检索结果不相关 | 尝试 MultiQueryRetriever 或调整 embedding 模型 |
| Chain 输出格式不稳定 | 在 prompt 中给出明确的输出格式示例（Few-shot） |

Image-Prompt(英文绘图词): A flat-design best practices illustration with five numbered tip cards arranged in a row: Card 1 "Start Simple" (single block icon), Card 2 "Use LCEL" (pipe operator symbol), Card 3 "Tune Memory" (window slider control), Card 4 "Set max_iterations" (counter with upper limit), Card 5 "Write Good Descriptions" (pencil over document), all cards connected to a central gear icon, tech-blue #409EFF on white background, 2D vector academic style with clean card shadows.

---

## 8. 小结

LangChain 的五大核心组件构成了一个从简单到复杂的完整光谱：

- **Chain**：执行单元，决定"做什么"
- **Retriever**：信息入口，决定"基于什么信息"
- **Memory**：状态管理，决定"记住什么"
- **Tool**：能力边界，决定"能做什么"
- **Agent**：决策中枢，决定"怎么做"

掌握这些组件的用法和适用场景后，你可以像搭积木一样，根据具体需求灵活组合，构建出从简单的问答机器人到复杂多步推理 Agent 的各种 LLM 应用。关键是**从简单开始，渐进式增加复杂度**，在每一步验证效果后再进入下一步。

Image-Prompt(英文绘图词): A flat-design layered capability pyramid showing the five LangChain components stacked from base to apex: Chain (foundation layer, widest), Retriever (second layer), Memory (third layer), Tool (fourth layer), and Agent (apex, narrowest), with upward arrows indicating increasing abstraction and autonomy, each layer labeled with its role ("What to do", "Based on what info", "What to remember", "What can do", "How to decide"), tech-blue #409EFF gradient from bottom to top on white background, 2D vector academic style.
