# RAG工程实战：文档切块策略与嵌入向量化

## 一、文档切块（Chunking）：RAG质量的"第一道关口"

在RAG系统中，文档切块看似是一个简单的工程步骤，但实际上它是决定检索质量和最终答案准确性的核心环节。一个不恰当的切块策略，会让后续所有的优化努力事倍功半。

### 1.1 为什么切块如此关键？

文档切块位于RAG管道的上游位置，其影响会层层放大：

```
切块质量 → 检索精度 → 上下文完整性 → 生成答案质量
  (上游)      (中游)        (下游)         (最终输出)
```

如果切块不合理：
- 检索阶段：即使检索算法完美，返回的也是"错误的正确文档块"
- 生成阶段：LLM拿到了碎片化的信息，无法形成完整理解
- 评估阶段：所有评估指标都会收到负面影响

### 1.2 切块的两个核心参数：Size 和 Overlap

**Chunk Size（块大小）** 决定每个文档块包含多少内容：

```
小Chunk (100-300 tokens):  高精度，低召回，适合精确的事实型问答
中Chunk (500-1000 tokens): 平衡方案，大多数场景的首选
大Chunk (1500-3000 tokens): 高召回，低精度，适合总结和主题理解
```

**Chunk Overlap（重叠量）** 决定相邻块之间的重叠程度：

```
无重叠 (0 overlap):
  [Chunk A: ...text ending here.] [Chunk B: Starting fresh...]
  风险：关键信息恰好在边界处被切断

有重叠 (10-20% overlap):
  [Chunk A: ...text ending with important context.] 
           [Chunk B: ...important context. Starting fresh...]
  优点：边界信息不会丢失
  代价：存储和索引的轻微冗余
```

**Size 和 Overlap 的定量关系**：

| Chunk Size | 推荐 Overlap | Overlap/Size 比例 | 适用场景 |
|------------|-------------|-------------------|---------|
| 256 tokens | 25-50 tokens | 10-20% | FAQ问答，短文本 |
| 512 tokens | 50-100 tokens | 10-20% | 通用文档问答 |
| 1024 tokens | 100-200 tokens | 10-20% | 技术文档，学术论文 |
| 2048 tokens | 200-400 tokens | 10-20% | 长篇报告，法律文书 |

**Image-Prompt(英文绘图词):** Flat-design 2D vector illustration showing the critical role of chunking in RAG quality as a pipeline with amplification effect. At the top "Chunking Quality" as the first domino/gear, cascading down to affect "Retrieval Precision" → "Context Completeness" → "Answer Quality". Three chunk size examples shown side by side: "Small Chunk (100-300 tokens)" as tiny puzzle pieces (high precision, low recall), "Medium Chunk (500-1000 tokens)" as balanced puzzle pieces (optimal), "Large Chunk (1500-3000 tokens)" as oversized pieces (high recall, low precision). Overlap visualization showing two adjacent chunks with a highlighted shared region. Tech blue #409EFF primary, white background.

## 二、主流切块策略深度对比

### 2.1 固定大小切块（Fixed-size Chunking）

最直观的方式：按固定字符数或Token数切分，是大多数RAG入门项目的起点。

```python
"""
固定大小切块 — 多种实现方式
"""

# 方式1：按字符数切分（最简单）
def char_fixed_chunk(text: str, chunk_size: int = 500, overlap: int = 50):
    """按字符数切分，带重叠"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks

# 方式2：按Token数切分（更精准，适配模型上下文窗口）
import tiktoken

def token_fixed_chunk(text: str, chunk_size: int = 500, overlap: int = 50,
                       model: str = "gpt-3.5-turbo"):
    """按Token数切分，使用tiktoken精确计数"""
    encoder = tiktoken.encoding_for_model(model)
    tokens = encoder.encode(text)
    
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoder.decode(chunk_tokens)
        chunks.append(chunk_text)
        if end == len(tokens):
            break
        start = end - overlap
    return chunks

# 方式3：使用LangChain的CharacterTextSplitter
from langchain.text_splitter import CharacterTextSplitter

splitter = CharacterTextSplitter(
    separator="\n",       # 在此分隔符处尽量切割
    chunk_size=500,        # 每块最多500字符
    chunk_overlap=50,      # 块间重叠50字符
    length_function=len,   # 长度计算函数
    is_separator_regex=False,
)

chunks = splitter.split_text(long_text)
```

**优缺点分析**：

| 方面 | 评价 |
|------|------|
| 实现难度 | 极低，几行代码 |
| 语义完整性 | 差，可能在词中间或句中切断 |
| 检索效果 | 中等，依赖overlap弥补信息断裂 |
| 计算效率 | 高，O(N)时间复杂度 |
| 适用场景 | 快速原型、英文文本（空格分词天然有边界） |

### 2.2 递归字符切块（Recursive Character Splitting）

这是LangChain的RecursiveCharacterTextSplitter所使用的策略，也是目前生产环境中最通用的方案。

**核心思想**：定义一组分隔符的"层级"，优先使用高层级分隔符（如段落），如果不满足大小要求则降到下一级（如句子），直到字符级。

```
分隔符层级（从大到小）：
"\n\n"  →  段落分隔
"\n"    →  行分隔
"。 "   →  句子分隔（中文）
". "    →  句子分隔（英文）
"；"    →  分句分隔（中文）
";"     →  分句分隔（英文）
" "     →  单词分隔
""      →  无分隔符（强制按字符切割）
```

```python
"""
递归切块 — 手写实现 + LangChain实现
"""

# ===== 手写实现（理解原理）=====
def recursive_chunk_manual(text: str, chunk_size: int = 500) -> list:
    """
    递归切块的手写实现
    演示核心递归逻辑
    """
    separators = ["\n\n", "\n", "。 ", ". ", " ", ""]
    
    def _split_recursive(text_to_split: str, seps: list) -> list:
        # 如果文本本身就不超过chunk_size，直接返回
        if len(text_to_split) <= chunk_size:
            return [text_to_split] if text_to_split else []
        
        # 尝试当前分隔符
        current_sep = seps[0]
        remaining_seps = seps[1:]
        
        if current_sep == "":
            # 最终手段：强制按字符切分
            return [text_to_split[i:i+chunk_size] 
                    for i in range(0, len(text_to_split), chunk_size)]
        
        # 用当前分隔符切分
        parts = text_to_split.split(current_sep)
        
        result = []
        current_chunk = ""
        
        for part in parts:
            # 如果加上当前片段仍在chunk_size内，合并到chunk中
            if len(current_chunk) + len(part) + len(current_sep) <= chunk_size:
                if current_chunk:
                    current_chunk += current_sep
                current_chunk += part
            else:
                # 当前chunk已满，保存它
                if current_chunk:
                    result.append(current_chunk)
                
                # 如果part本身大于chunk_size，需要递归用更小的分隔符
                if len(part) > chunk_size:
                    result.extend(_split_recursive(part, remaining_seps))
                else:
                    current_chunk = part
        
        if current_chunk:
            result.append(current_chunk)
        
        return result
    
    return _split_recursive(text, separators)


# ===== LangChain实现（生产使用）=====
from langchain.text_splitter import RecursiveCharacterTextSplitter

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,              # 每块最多800字符
    chunk_overlap=80,            # 块间重叠80字符
    separators=[
        "\n\n",                  # 第一优先级：段落
        "\n",                    # 第二优先级：换行
        "。",                    # 第三优先级：中文句号
        ". ",                    # 第四优先级：英文句号
        "！",                    # 第五优先级：感叹号
        "？",                    # 第六优先级：问号
        "；",                    # 第七优先级：分号
        "，",                    # 第八优先级：逗号
        " ",                     # 第九优先级：空格
        "",                      # 最终：字符
    ],
    length_function=len,
    is_separator_regex=False,
    add_start_index=True,        # 记录每个chunk在原文档中的起始位置
)

# 不仅切分文本，还保留元数据
from langchain.schema import Document

original_doc = Document(
    page_content=long_text,
    metadata={"source": "report_2024.pdf", "page": 1}
)

split_docs = recursive_splitter.split_documents([original_doc])
print(f"切分为 {len(split_docs)} 个文档块")
for i, doc in enumerate(split_docs[:3]):
    print(f"Chunk {i}: 长度={len(doc.page_content)}, "
          f"起始位置={doc.metadata.get('start_index')}, "
          f"来源={doc.metadata.get('source')}")
```

**使用建议**：RecursiveCharacterTextSplitter是90%场景下最合理的选择。它的设计哲学是"尽量在好的地方切，不行再降级"，在简洁性和效果之间取得了良好的平衡。

### 2.3 语义切块（Semantic Chunking）

语义切块的思路是：通过计算相邻句子之间的语义相似度，在相似度发生"断崖式下降"的地方进行切分。

```python
"""
语义切块 — 基于嵌入相似度的智能切分
"""
import numpy as np
from sentence_transformers import SentenceTransformer

class SemanticChunker:
    """
    语义切块器：在语义边界处切分文档
    
    工作原理：
    1. 将文档按句子拆分
    2. 计算相邻句子的embedding
    3. 计算相邻句子对的余弦相似度
    4. 在相似度低于阈值的"断点"处切分
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        similarity_threshold: float = 0.5,
        min_chunk_size: int = 100,
        max_chunk_size: int = 2000,
    ):
        self.model = SentenceTransformer(model_name)
        self.threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    def _split_sentences(self, text: str) -> list:
        """简单的句子分割（生产环境建议使用spaCy或jieba）"""
        # 中文和英文的句子分隔符
        import re
        return re.split(r'(?<=[。！？\.!\?])\s*', text)
    
    def _compute_similarities(self, sentences: list) -> list:
        """计算相邻句子的余弦相似度"""
        embeddings = self.model.encode(sentences, normalize_embeddings=True)
        
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i + 1])
            similarities.append(sim)
        
        return similarities
    
    def chunk(self, text: str) -> list:
        """执行语义切块"""
        sentences = self._split_sentences(text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            return [text] if text else []
        
        # 计算相邻句子相似度
        similarities = self._compute_similarities(sentences)
        
        # 在低相似度点切分
        chunks = []
        current_chunk = sentences[0]
        
        for i in range(1, len(sentences)):
            sim = similarities[i - 1]
            
            potential_size = len(current_chunk) + len(sentences[i])
            
            # 切分条件：相似度低于阈值 且 不小于最小chunk大小
            # 或者 加上当前句子会超过最大chunk大小
            if (sim < self.threshold and len(current_chunk) >= self.min_chunk_size) \
               or potential_size > self.max_chunk_size:
                chunks.append(current_chunk)
                current_chunk = sentences[i]
            else:
                if current_chunk:
                    current_chunk += " " + sentences[i]
                else:
                    current_chunk = sentences[i]
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks


# 使用示例
semantic_chunker = SemanticChunker(
    similarity_threshold=0.4,
    min_chunk_size=200,
    max_chunk_size=1500,
)

# 假设有一段包含多个主题的长文本
sample_text = """
人工智能在医疗领域的应用日益广泛。深度学习算法可以辅助医生进行影像诊断。
卷积神经网络在CT和MRI图像分析中表现出色。

Python是一种广泛应用于数据科学的编程语言。它拥有丰富的机器学习和深度学习库。
许多数据科学家使用Python进行数据分析和模型训练。

区块链技术最初是作为比特币的底层技术被提出的。它的去中心化特性提供了高度的安全性。
智能合约是区块链技术的重要应用之一。
"""

chunks = semantic_chunker.chunk(sample_text)
print(f"语义切块结果: {len(chunks)} 个块")
for i, chunk in enumerate(chunks):
    print(f"\n--- Chunk {i+1} ({len(chunk)} 字符) ---")
    print(chunk[:100] + "...")
```

**语义切块的适用场景**：
- 文档包含多个不同主题时（如综合报告）
- 需要高质量的检索结果（每个chunk内主题一致）
- 文档长度适中（计算embedding的成本可接受）

**语义切块的局限性**：
- 计算成本高：需要对每个句子生成embedding
- 阈值调优困难：不同文档的"语义断点"不同
- 短文本场景效果不佳：句子太少时难以找到好的切分点

### 2.4 按文档结构切块（Structural Chunking）

利用文档自身的结构（标题、列表、表格）作为切分边界。

```python
"""
按文档结构切块 — Markdown 和 HTML
"""
from langchain.text_splitter import MarkdownHeaderTextSplitter, HTMLHeaderTextSplitter

# ===== Markdown结构切块 =====
markdown_text = """
# 第一章：系统架构

## 1.1 整体设计
系统采用微服务架构，各服务独立部署和扩展。

## 1.2 技术栈
后端使用Spring Boot，前端使用React。

# 第二章：API设计

## 2.1 RESTful接口
所有API遵循RESTful设计规范，使用JSON格式传输数据。

## 2.2 认证机制
使用JWT进行身份认证和授权管理。
"""

# 定义切分所用的标题层级
headers_to_split_on = [
    ("#", "h1"),      # 在 # 处切分，元数据记作 h1
    ("##", "h2"),     # 在 ## 处切分，元数据记作 h2
    ("###", "h3"),    # 在 ### 处切分，元数据记作 h3
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False,  # 保留标题文字在chunk中
)

md_chunks = markdown_splitter.split_text(markdown_text)

for chunk in md_chunks:
    print(f"Chunk元数据: {chunk.metadata}")
    print(f"Chunk内容: {chunk.page_content[:80]}...")
    print()

# ===== HTML结构切块 =====
html_splitter = HTMLHeaderTextSplitter(
    headers_to_split_on=[
        ("h1", "Header 1"),
        ("h2", "Header 2"),
    ]
)

# html_chunks = html_splitter.split_text_from_url("https://example.com/docs")
```

**按结构切块的优势**：
- 保持文档原有的逻辑结构
- 每个chunk天然带有层级元数据（这对检索后的上下文还原非常有用）
- 适合技术文档、API手册、知识库等有良好结构的内容

### 2.5 特定文档类型的切块策略

#### PDF文档

PDF是RAG中最常见也最棘手的文档格式。它的文本布局是视觉导向的，而非语义导向的。

```python
"""
PDF文档的切块最佳实践
"""
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def process_pdf_for_rag(pdf_path: str, chunk_size: int = 1000):
    """
    PDF文档的RAG处理流程
    """
    # Step 1: 加载并预检查
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    
    print(f"PDF共有 {len(pages)} 页")
    
    # Step 2: 页面级处理
    # 对每页进行清洗：去除页眉页脚、多余空白
    cleaned_pages = []
    for page in pages:
        text = page.page_content
        # 简单的页眉页脚过滤（生产环境中可能需要更复杂的规则）
        lines = text.split('\n')
        # 移除可能的页码行
        cleaned_lines = [
            line for line in lines 
            if not line.strip().isdigit()  # 过滤纯数字行（可能是页码）
            and len(line.strip()) > 3       # 过滤过短的行
        ]
        page.page_content = '\n'.join(cleaned_lines)
        cleaned_pages.append(page)
    
    # Step 3: 切分 — 组合使用多种策略
    # 对于PDF，推荐使用递归切分+较大的chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,      # PDF内容密度高，使用较大块
        chunk_overlap=150,          # 较大重叠确保跨页信息不丢失
        separators=[
            "\n\n",   # PDF中的段落（空行）
            "\n",     # PDF中的换行
            "。",     # 中文句号
            ". ",     # 英文句号
            " ",      # 空格
            "",       # 字符
        ],
        length_function=len,
    )
    
    chunks = splitter.split_documents(cleaned_pages)
    
    # Step 4: 增强元数据
    for chunk in chunks:
        # 保留页码信息
        chunk.metadata['file_type'] = 'pdf'
        # 添加chunk在原文档中的近似位置
        if 'page' in chunk.metadata:
            chunk.metadata['location_hint'] = f"第{chunk.metadata['page']}页"
    
    return chunks
```

**PDF切块的特殊注意事项**：
- PDF中的表格内容需要特殊处理（先用Camelot/Tabula提取）
- 多栏布局的PDF文本顺序可能是乱的（从左栏跳到右栏再回到左栏下一段）
- 图片中的文字需要通过OCR提取
- PDF的"页"是天然的分界点，但不一定是语义分界点

#### 代码文档

代码的语义单元与传统文本完全不同。

```python
"""
代码文档的切块策略
"""
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    Language,
)

# LangChain 内置支持多种编程语言的切分器
code_text = """
def calculate_rag_score(metrics: dict) -> float:
    \"\"\"
    计算RAG系统的综合得分
    \"\"\"
    weights = {
        "faithfulness": 0.3,
        "relevance": 0.3,
        "precision": 0.2,
        "recall": 0.2,
    }
    score = sum(metrics.get(k, 0) * v for k, v in weights.items())
    return round(score, 4)


class RAGEvaluator:
    \"\"\"RAG系统评估器\"\"\"
    
    def __init__(self, llm, threshold=0.7):
        self.llm = llm
        self.threshold = threshold
    
    def evaluate(self, question: str, answer: str, context: list):
        \"\"\"执行评估\"\"\"
        results = {}
        results["faithfulness"] = self._check_faithfulness(answer, context)
        results["relevance"] = self._check_relevance(question, answer)
        return results
    
    def _check_faithfulness(self, answer, context):
        # 检查答案是否忠实于上下文
        pass
    
    def _check_relevance(self, question, answer):
        # 检查答案是否相关
        pass
"""

# 使用Python专用的切分器
python_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=500,
    chunk_overlap=0,  # 代码通常不需要overlap
)

python_chunks = python_splitter.split_text(code_text)

for i, chunk in enumerate(python_chunks):
    print(f"--- Python Chunk {i+1} ---")
    print(chunk.strip())
    print()

# 也支持其他语言
# Language.JS, Language.TS, Language.GO, Language.RUST, Language.JAVA 等
```

**代码切块的特殊考虑**：
- 以函数/类/方法为基本单元，而非固定长度
- 通常不需要overlap（代码的上下文通过import/include获取）
- 保留代码结构（缩进、注释）
- AST（抽象语法树）切分是最理想的方式，但实现复杂

#### 对话记录

对话记录的语义结构特殊：有角色区分、时序依赖、话题漂移。

```python
"""
对话记录的切块策略
"""
def chunk_conversation(conversation: list, max_turns: int = 8):
    """
    按对话轮次切块
    
    conversation: [{"role": "user/assistant", "content": "..."}, ...]
    """
    chunks = []
    
    for start in range(0, len(conversation), max_turns // 2):
        end = min(start + max_turns, len(conversation))
        chunk_turns = conversation[start:end]
        
        # 格式化为自然文本
        chunk_text = ""
        for turn in chunk_turns:
            role_label = "用户" if turn["role"] == "user" else "助手"
            chunk_text += f"{role_label}: {turn['content']}\n"
        
        chunks.append({
            "text": chunk_text,
            "turn_range": (start, end - 1),
            "turn_count": len(chunk_turns),
        })
        
        if end == len(conversation):
            break
    
    return chunks
```

**Image-Prompt(英文绘图词):** Flat-design 2D vector illustration comparing five chunking strategies as horizontal panels. Panel 1 "Fixed-Size": document cut by character count with scissors, showing uneven breaks. Panel 2 "Recursive": separator hierarchy pyramid on the left (paragraph→sentence→word→character), document progressively split on the right. Panel 3 "Semantic": adjacent sentences with similarity scores between them, a "cliff" drop indicating the split point. Panel 4 "Structural": Markdown/HTML document with H1/H2/H3 headers highlighted as natural split boundaries. Panel 5 "Code": Python function/class blocks as natural chunks. Tech blue #409EFF primary, white background, clean comparison.

## 三、嵌入模型选择：从通用到专用

### 3.1 嵌入模型的评估维度

选择嵌入模型时，需要从以下维度综合评估：

```
质量维度：
├─ MTEB排行榜排名 — 通用质量参考
├─ 领域适配度 — 是否在你的领域上表现好
├─ 最大序列长度 — 能否处理你的chunk大小
└─ 语言支持 — 多语言/特定语言的性能

工程维度：
├─ 向量维度 — 影响存储成本和检索速度
├─ 推理速度 — 影响索引构建和查询时延
├─ 部署方式 — API vs 本地部署
└─ 是否有Matryoshka（可变维度）支持
```

### 3.2 主流嵌入模型对比

| 模型 | 维度 | 最大Token | 语言 | 部署 | MTEB排名 | 推荐场景 |
|------|------|----------|------|------|---------|---------|
| OpenAI text-embedding-3-large | 3072(可调) | 8191 | 多语言 | API | 64.6 | 追求最高质量 |
| OpenAI text-embedding-3-small | 1536(可调) | 8191 | 多语言 | API | 62.3 | 性价比之选 |
| BGE-large-zh-v1.5 | 1024 | 512 | 中文优化 | 本地 | C-MTEB第1 | 中文首选 |
| BGE-M3 | 1024 | 8192 | 多语言 | 本地 | 综合强 | 多语言+长文本 |
| E5-mistral-7b-instruct | 4096 | 32768 | 多语言 | 本地(大) | 66.6 | 高质量但需大算力 |
| Jina-embeddings-v3 | 1024(可调) | 8192 | 多语言 | API/本地 | 65.2 | 长文本+多语言 |
| multilingual-e5-large | 1024 | 512 | 多语言 | 本地 | 60+ | 多语言开源方案 |

### 3.3 实战：不同模型的embedding对比

```python
"""
嵌入模型对比实战
"""
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np
import time

# ===== 本地模型：BGE =====
print("加载 BGE 模型...")
bge_model = SentenceTransformer(
    "BAAI/bge-large-zh-v1.5",
    device="cuda"
)

# BGE需要特殊的前缀来提升效果
def bge_embed(texts: list, is_query: bool = False):
    if is_query:
        texts = [f"为这个句子生成表示以用于检索相关文章：{t}" for t in texts]
    return bge_model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

# ===== API模型：OpenAI =====
openai_client = OpenAI()  # 需要设置 OPENAI_API_KEY

def openai_embed(texts: list, model: str = "text-embedding-3-small",
                 dimensions: int = None):
    kwargs = {"model": model, "input": texts}
    if dimensions:
        kwargs["dimensions"] = dimensions
    
    response = openai_client.embeddings.create(**kwargs)
    embeddings = [item.embedding for item in response.data]
    return np.array(embeddings)

# ===== 对比测试 =====
test_texts = [
    "Python是一种广泛使用的编程语言",
    "JavaScript主要用于前端Web开发",
    "机器学习是人工智能的一个子领域",
    "深度学习使用多层神经网络进行特征提取",
    "今天天气非常晴朗适合出游",
]

test_query = "我该怎么学习Python编程？"

print("\n===== 模型相似度对比 =====")

# 测试BGE
bge_doc_embeddings = bge_embed(test_texts, is_query=False)
bge_query_embedding = bge_embed([test_query], is_query=True)[0]

bge_similarities = np.dot(bge_doc_embeddings, bge_query_embedding)
print("\nBGE-large-zh 相似度排名:")
for idx in np.argsort(bge_similarities)[::-1]:
    print(f"  {bge_similarities[idx]:.4f} - {test_texts[idx]}")

# 测试OpenAI
oa_doc_embeddings = openai_embed(test_texts, "text-embedding-3-small")
oa_query_embedding = openai_embed([test_query], "text-embedding-3-small")[0]

# 归一化后计算余弦相似度
oa_doc_norm = oa_doc_embeddings / np.linalg.norm(oa_doc_embeddings, axis=1, keepdims=True)
oa_query_norm = oa_query_embedding / np.linalg.norm(oa_query_embedding)
oa_similarities = np.dot(oa_doc_norm, oa_query_norm)

print("\nOpenAI text-embedding-3-small 相似度排名:")
for idx in np.argsort(oa_similarities)[::-1]:
    print(f"  {oa_similarities[idx]:.4f} - {test_texts[idx]}")
```

### 3.4 Matryoshka Embedding（俄罗斯套娃嵌入）

OpenAI text-embedding-3 和 Jina-embeddings-v3 支持 Matryoshka Representation Learning，可以在不损失太多质量的情况下缩短向量维度，从而大幅减少存储成本和检索延迟。

```python
"""
Matryoshka Embedding 效果对比
"""
def test_matryoshka_embedding(texts: list):
    """
    对比不同维度的embedding保留率
    """
    # 生成全维度embedding
    full_embeddings = openai_embed(texts, "text-embedding-3-large", dimensions=3072)
    
    dims_to_test = [256, 512, 1024, 1536, 3072]
    reference_ranking = None
    
    print(f"\n{'维度':<8} {'存储(MB)':<12} {'检索速度':<12} {'Top-3一致率':<14}")
    print("-" * 48)
    
    for dim in dims_to_test:
        # 用指定维度重新生成（或从全维度截取的前dim维）
        embeddings = openai_embed(texts, "text-embedding-3-large", dimensions=dim)
        
        # 模拟查询
        query_emb = openai_embed(["Python编程入门"], "text-embedding-3-large", dimensions=dim)
        query_norm = query_emb / np.linalg.norm(query_emb, axis=1, keepdims=True)
        doc_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        similarities = np.dot(doc_norm, query_norm.T).flatten()
        ranking = np.argsort(similarities)[::-1][:3]
        
        if reference_ranking is None:
            reference_ranking = ranking
            agreement = "Reference"
        else:
            agreement = f"{len(set(ranking) & set(reference_ranking)) / 3 * 100:.0f}%"
        
        # 估算存储
        n_vectors = len(texts)
        storage_mb = n_vectors * dim * 4 / 1024 / 1024
        # 估算速度（线性与维度相关）
        speed_factor = 3072 / dim
        
        print(f"{dim:<8} {storage_mb:<12.2f} {speed_factor:<12.1f}x {agreement:<14}")

# test_matryoshka_embedding(test_texts * 1000)
```

**Matryoshka维度选择建议**：
- 256维：移动端、边缘设备、超大规模（减少74%存储，精度损失约3-5%）
- 512维：高吞吐量API服务（减少50%存储，精度损失约1-2%）
- 1024维：大多数生产场景的理想平衡点

### 3.5 针对不同语言和领域的embedding选择

```python
"""
场景化的embedding模型选择指南
"""

def select_embedding_model(language: str, domain: str, 
                           deployment: str, budget: str):
    """
    根据场景推荐embedding模型
    
    参数:
        language: "zh" | "en" | "multilingual"
        domain: "general" | "code" | "medical" | "legal" | "finance"
        deployment: "api" | "local"
        budget: "low" | "medium" | "high"
    """
    
    recommendations = {
        ("zh", "general", "local", "medium"): {
            "model": "BAAI/bge-large-zh-v1.5",
            "reason": "中文MTEB排名第一，本地部署，中等算力需求"
        },
        ("zh", "general", "api", "low"): {
            "model": "text-embedding-3-small",
            "reason": "性价比高，1536维（可降到512维），中文效果好"
        },
        ("zh", "general", "api", "high"): {
            "model": "text-embedding-3-large",
            "reason": "质量最高，3072维，场景自适应"
        },
        ("multilingual", "general", "local", "medium"): {
            "model": "BAAI/bge-m3",
            "reason": "多语言+长文本(8192 tokens)，综合能力强"
        },
        ("multilingual", "general", "api", "medium"): {
            "model": "jina-embeddings-v3",
            "reason": "8192 tokens，多语言，支持Matryoshka"
        },
        ("en", "code", "local", "medium"): {
            "model": "jina-embeddings-v2-base-code",
            "reason": "代码专用embedding，支持多种编程语言"
        },
        ("en", "general", "local", "high"): {
            "model": "intfloat/e5-mistral-7b-instruct",
            "reason": "基于Mistral-7B，MTEB最高分，需GPU"
        },
    }
    
    key = (language, domain, deployment, budget)
    if key in recommendations:
        return recommendations[key]
    
    # 默认回退
    return {
        "model": "BAAI/bge-small-zh-v1.5" if language == "zh" 
                 else "sentence-transformers/all-MiniLM-L6-v2",
        "reason": "通用回退方案，轻量级，适合大多数场景"
    }

# 使用示例
result = select_embedding_model("zh", "general", "local", "medium")
print(f"推荐模型: {result['model']}")
print(f"推荐理由: {result['reason']}")
```

**Image-Prompt(英文绘图词):** Flat-design 2D vector illustration of embedding model selection as a funnel/filter process. Incoming text at the top passes through evaluation dimensions arranged as filter layers: "Quality" layer (MTEB ranking badge, domain fit gauge), "Engineering" layer (dimension size slider, speed gauge, deployment toggle API vs Local), "Language" layer (language flags: ZH, EN, multilingual). At the bottom, a comparison grid showing popular models (OpenAI text-embedding-3, BGE, E5, Jina) with their key specs. A Matryoshka doll icon representing Matryoshka embeddings with dimension layers (256, 512, 1024, 3072). Tech blue #409EFF primary, white background.

## 四、嵌入质量评估

### 4.1 内部评估 vs 外部评估

**内部评估**（Intrinsic Evaluation）：直接评估embedding本身的质量，不依赖下游任务。
- 语义相似度基准测试（STS Benchmark）
- 分类任务（情感分类、主题分类）
- 聚类质量（同一类文本的embedding是否聚集）

**外部评估**（Extrinsic Evaluation）：在RAG系统中端到端评估。
- 检索召回率：对于已知答案的问题，embedding能否检索到正确的chunk
- 下游任务质量：使用该embedding的RAG系统最终生成的答案质量

### 4.2 自定义评估脚本

```python
"""
Embedding模型的自定义评估
"""
from sentence_transformers import SentenceTransformer, evaluation
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class EmbeddingEvaluator:
    """
    Embedding模型评估器
    """
    
    def __init__(self, model):
        self.model = model
    
    def evaluate_retrieval_quality(self, queries, relevant_docs, corpus):
        """
        评估检索质量
        
        queries: 查询列表
        relevant_docs: 每个查询对应的相关文档ID列表
        corpus: 全部文档列表
        """
        # 嵌入所有文档和查询
        corpus_embeddings = self.model.encode(corpus, normalize_embeddings=True)
        query_embeddings = self.model.encode(queries, normalize_embeddings=True)
        
        # 计算相似度矩阵
        similarity_matrix = np.dot(query_embeddings, corpus_embeddings.T)
        
        # 计算 Retrieval Metrics
        metrics = {}
        for k in [1, 3, 5, 10]:
            recall = self._calculate_recall_at_k(
                similarity_matrix, relevant_docs, k
            )
            metrics[f"Recall@{k}"] = recall
            
            mrr = self._calculate_mrr(
                similarity_matrix, relevant_docs, k
            )
            metrics[f"MRR@{k}"] = mrr
        
        return metrics
    
    def _calculate_recall_at_k(self, similarity_matrix, relevant_docs, k):
        """计算 Recall@K"""
        recalls = []
        for i, query_relevant in enumerate(relevant_docs):
            # 获取Top-K结果
            top_k_indices = np.argsort(similarity_matrix[i])[::-1][:k]
            # 计算召回率
            retrieved_relevant = set(top_k_indices) & set(query_relevant)
            recall = len(retrieved_relevant) / len(query_relevant) if query_relevant else 0
            recalls.append(recall)
        return np.mean(recalls)
    
    def _calculate_mrr(self, similarity_matrix, relevant_docs, k):
        """计算 MRR@K (Mean Reciprocal Rank)"""
        reciprocal_ranks = []
        for i, query_relevant in enumerate(relevant_docs):
            ranking = np.argsort(similarity_matrix[i])[::-1]
            for rank, idx in enumerate(ranking[:k], 1):
                if idx in query_relevant:
                    reciprocal_ranks.append(1.0 / rank)
                    break
            else:
                reciprocal_ranks.append(0.0)
        return np.mean(reciprocal_ranks)
    
    def evaluate_semantic_consistency(self, sentence_pairs, similarity_scores):
        """
        评估语义一致性（与人工标注的相似度分数的相关性）
        
        sentence_pairs: [(sent1, sent2), ...]
        similarity_scores: 人工标注的相似度分数 [0-5]
        """
        from scipy.stats import spearmanr, pearsonr
        
        # 计算模型给出的相似度
        predicted_scores = []
        for sent1, sent2 in sentence_pairs:
            emb1 = self.model.encode([sent1], normalize_embeddings=True)[0]
            emb2 = self.model.encode([sent2], normalize_embeddings=True)[0]
            sim = np.dot(emb1, emb2)
            predicted_scores.append(sim)
        
        # 计算与人工标注的相关性
        spearman_corr, _ = spearmanr(predicted_scores, similarity_scores)
        pearson_corr, _ = pearsonr(predicted_scores, similarity_scores)
        
        return {
            "spearman_correlation": spearman_corr,
            "pearson_correlation": pearson_corr,
        }

# 使用示例
evaluator = EmbeddingEvaluator(bge_model)

# 模拟评估数据
queries = ["Python编程入门", "机器学习基础"]
corpus = [
    "Python是一种解释型编程语言",
    "机器学习是AI的重要分支",
    "今天天气很好",
    "Python用于数据科学和机器学习",
]
relevant = [[0, 3], [1, 3]]  # 每个查询对应的相关文档索引

metrics = evaluator.evaluate_retrieval_quality(queries, relevant, corpus)
for metric, value in metrics.items():
    print(f"{metric}: {value:.4f}")
```

## 五、Chunking最佳实践与陷阱

### 5.1 最佳实践清单

| 序号 | 实践 | 说明 |
|------|------|------|
| 1 | 先分析文档特征 | 不同类型、不同领域的文档需要不同的切块策略 |
| 2 | 保留元数据 | 每个chunk应记录来源、页码、位置等元数据 |
| 3 | 从RecursiveChunking开始 | 它是大多数场景下的最优默认选择 |
| 4 | 进行A/B测试 | 不同chunk size的效果需要实验验证 |
| 5 | 考虑检索策略匹配 | chunk策略应与下游的检索策略协同设计 |
| 6 | 监控chunk质量 | 抽样检查切块后的文本是否语义完整 |
| 7 | 小chunk检索+大chunk返回 | 用100-200 token block检索，返回500-1000 token上下文 |

### 5.2 常见陷阱与解决方案

**陷阱1：盲目使用默认参数**

```python
# ❌ 错误：不加思考地使用默认值
splitter = RecursiveCharacterTextSplitter()  # 默认chunk_size=1000, overlap=200

# ✅ 正确：根据实际文档特征选择参数
# 先分析文档的平均段落长度、主题密度
avg_paragraph_length = analyze_document_stats(documents)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=avg_paragraph_length * 2,  # 大约2个段落
    chunk_overlap=max(50, avg_paragraph_length // 5),  # 约20%重叠
)
```

**陷阱2：忽略多模态内容**

```python
# ❌ 错误：只处理文本，忽略表格和图片
loader = PyPDFLoader("report.pdf")
docs = loader.load()
chunks = splitter.split_documents(docs)

# ✅ 正确：多模态内容的综合处理
from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(
    "report.pdf",
    strategy="hi_res",
    extract_images_in_pdf=True,
    infer_table_structure=True,
    extract_image_block_types=["Image", "Table"],
)

# 分别处理不同类型的内容
text_elements = [e for e in elements if e.category == "NarrativeText"]
table_elements = [e for e in elements if e.category == "Table"]
image_elements = [e for e in elements if e.category == "Image"]

# 对文本、表格、图片分别使用不同的处理策略
```

**陷阱3：切块后丢失文档上下文**

```python
# ✅ 正确：保留chunk的层级关系和上下文
from typing import List, Optional

class ContextAwareChunk:
    """带有上下文信息的文档块"""
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata
        self.parent_title: Optional[str] = None
        self.section_path: List[str] = []  # 如 ["Chapter 1", "Section 1.1"]
        self.prev_chunk_summary: Optional[str] = None
        self.next_chunk_summary: Optional[str] = None
    
    def to_retrieval_text(self):
        """生成增强的检索文本（包含上下文）"""
        parts = []
        if self.parent_title:
            parts.append(f"[所属章节: {self.parent_title}]")
        if self.section_path:
            parts.append(f"[文档路径: {' > '.join(self.section_path)}]")
        parts.append(self.text)
        return "\n".join(parts)

# 在切分时填充上下文信息
def chunk_with_context(document, splitter):
    chunks = splitter.split_documents([document])
    
    context_chunks = []
    for i, chunk in enumerate(chunks):
        ctx = ContextAwareChunk(
            text=chunk.page_content,
            metadata=chunk.metadata,
        )
        # 添加上下文摘要（可以用轻量级LLM生成）
        if i > 0:
            ctx.prev_chunk_summary = summarize_chunk(chunks[i-1].page_content)
        if i < len(chunks) - 1:
            ctx.next_chunk_summary = summarize_chunk(chunks[i+1].page_content)
        
        context_chunks.append(ctx)
    
    return context_chunks
```

**陷阱4：不同文档类型使用相同的切块策略**

```python
# ✅ 正确：根据文档类型动态选择切块策略
class AdaptiveChunker:
    """
    自适应切块器：根据文档类型自动选择最佳切块策略
    """
    
    STRATEGIES = {
        "pdf": {
            "splitter": RecursiveCharacterTextSplitter,
            "chunk_size": 800,
            "chunk_overlap": 100,
            "separators": ["\n\n", "\n", "。", ". ", " ", ""],
        },
        "markdown": {
            "splitter": MarkdownHeaderTextSplitter,
            # Markdown结构切分的参数在初始化时指定
        },
        "code": {
            "splitter": RecursiveCharacterTextSplitter.from_language,
            "chunk_size": 500,
            "chunk_overlap": 0,
        },
        "conversation": {
            "chunk_size": 2000,  # 对话需要更大上下文
            "chunk_overlap": 400,
            "strategy": "turn_based",  # 按对话轮次切分
        },
    }
    
    def chunk(self, document, doc_type: str):
        if doc_type not in self.STRATEGIES:
            doc_type = "pdf"  # 默认回退
        
        strategy = self.STRATEGIES[doc_type]
        # 根据策略执行切分...
        return []


# 生产环境中的完整工作流
def production_chunking_pipeline(file_path: str) -> list:
    """
    生产级文档切分流水线
    """
    # 1. 识别文档类型
    ext = file_path.split('.')[-1].lower()
    
    doc_type_map = {
        'pdf': 'pdf',
        'md': 'markdown',
        'py': 'code',
        'js': 'code',
        'ts': 'code',
        'json': 'conversation',  # 对话记录的常见格式
        'txt': 'pdf',  # 文本文件用通用策略
    }
    
    doc_type = doc_type_map.get(ext, 'pdf')
    
    # 2. 加载文档
    loaders = {
        'pdf': PyPDFLoader,
        'markdown': TextLoader,
        'code': TextLoader,
        'conversation': TextLoader,
    }
    
    loader_cls = loaders.get(doc_type, PyPDFLoader)
    loader = loader_cls(file_path)
    documents = loader.load()
    
    # 3. 根据类型选择切分器
    adaptive_chunker = AdaptiveChunker()
    chunks = adaptive_chunker.chunk(documents[0], doc_type)
    
    # 4. 后处理：质量检查
    validated_chunks = []
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
        # 过滤空chunk
        if len(text.strip()) < 20:
            continue
        # 过滤纯数字/纯符号的chunk
        if text.strip().replace('\n', '').replace(' ', '').isascii() and \
           len(set(text.strip())) < 5:
            continue
        validated_chunks.append(chunk)
    
    print(f"文档类型: {doc_type}, 原始chunk数: {len(chunks)}, "
          f"有效chunk数: {len(validated_chunks)}")
    
    return validated_chunks
```

**Image-Prompt(英文绘图词):** Flat-design 2D vector illustration showing best practices and common pitfalls as a two-column comparison. Left column "Best Practices" with green checkmark icons: analyzing document features first (document analysis magnifying glass), preserving metadata (tag icon), starting with recursive chunking (recommended badge), A/B testing (split test icon), small chunk retrieval + large chunk return (two arrows of different sizes). Right column "Pitfalls" with red X icons: using default parameters blindly (warning triangle), ignoring multimodal content (image+table inside PDF), losing document context after chunking (broken chain icon), same strategy for all doc types (hammer hitting different shaped objects). Tech blue #409EFF primary, white background, clean educational layout.

## 六、完整实战：端到端的文档处理流水线

```python
"""
端到端文档处理流水线
从原始文件到可检索的向量化文档块
"""
from pathlib import Path
from typing import List, Dict, Any
import hashlib
import json
from datetime import datetime

class DocumentProcessingPipeline:
    """
    完整的文档处理流水线
    
    功能:
    - 多格式文档加载
    - 智能文档切块（自适应策略）
    - 批量嵌入向量化
    - 向量库写入
    - 处理状态追踪
    """
    
    def __init__(self, embedder, vectorstore, config: dict = None):
        self.embedder = embedder
        self.vectorstore = vectorstore
        self.config = config or self._default_config()
        self.processing_log = []
    
    @staticmethod
    def _default_config():
        return {
            "pdf": {"chunk_size": 800, "chunk_overlap": 100},
            "markdown": {"chunk_size": 1000, "chunk_overlap": 150},
            "code": {"chunk_size": 500, "chunk_overlap": 0},
            "text": {"chunk_size": 600, "chunk_overlap": 80},
            "batch_size": 50,           # 嵌入批处理大小
            "min_chunk_length": 30,     # 最小chunk长度
            "max_chunk_length": 3000,   # 最大chunk长度
        }
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """处理单个文件"""
        file_path = Path(file_path)
        start_time = datetime.now()
        
        result = {
            "file": str(file_path),
            "status": "pending",
            "chunks_created": 0,
            "chunks_indexed": 0,
            "errors": [],
        }
        
        try:
            # Step 1: 计算文件哈希（变更检测）
            file_hash = self._file_hash(file_path)
            
            # Step 2: 加载文档
            documents = self._load_document(file_path)
            result["pages"] = len(documents)
            
            # Step 3: 切分
            chunks = self._chunk_documents(documents, file_path.suffix)
            result["chunks_created"] = len(chunks)
            
            # Step 4: 质量过滤
            chunks = self._filter_chunks(chunks)
            result["chunks_after_filter"] = len(chunks)
            
            # Step 5: 嵌入并写入向量库
            indexed = self._index_chunks(chunks)
            result["chunks_indexed"] = indexed
            result["status"] = "success"
            
        except Exception as e:
            result["status"] = "failed"
            result["errors"].append(str(e))
        
        result["duration_sec"] = (datetime.now() - start_time).total_seconds()
        self.processing_log.append(result)
        
        return result
    
    def process_directory(self, dir_path: str, glob_pattern: str = "**/*") -> List[Dict]:
        """批量处理目录"""
        dir_path = Path(dir_path)
        results = []
        
        for file_path in dir_path.glob(glob_pattern):
            if file_path.is_file():
                result = self.process_file(str(file_path))
                results.append(result)
                print(f"[{result['status']}] {file_path.name}: "
                      f"{result['chunks_indexed']} chunks, "
                      f"{result['duration_sec']:.1f}s")
        
        # 汇总
        total_chunks = sum(r.get("chunks_indexed", 0) for r in results)
        success_count = sum(1 for r in results if r["status"] == "success")
        
        print(f"\n处理完成: {success_count}/{len(results)} 个文件成功, "
              f"共索引 {total_chunks} 个文档块")
        
        return results
    
    def _file_hash(self, file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def _load_document(self, file_path: Path):
        ext = file_path.suffix.lower()
        
        if ext == '.pdf':
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(str(file_path))
        elif ext in ['.md', '.txt', '.rst']:
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(str(file_path), encoding='utf-8')
        else:
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(str(file_path), encoding='utf-8')
        
        return loader.load()
    
    def _chunk_documents(self, documents, file_ext: str) -> list:
        ext = file_ext.lower().replace('.', '')
        config = self.config.get(ext, self.config["text"])
        
        if ext == 'md':
            from langchain.text_splitter import MarkdownHeaderTextSplitter
            headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
            splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
            all_chunks = []
            for doc in documents:
                chunks = splitter.split_text(doc.page_content)
                all_chunks.extend(chunks)
            return all_chunks
        else:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=config["chunk_size"],
                chunk_overlap=config["chunk_overlap"],
                separators=["\n\n", "\n", "。", ". ", " ", ""],
                length_function=len,
            )
            return splitter.split_documents(documents)
    
    def _filter_chunks(self, chunks: list) -> list:
        """质量过滤"""
        filtered = []
        for chunk in chunks:
            text = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
            length = len(text.strip())
            if self.config["min_chunk_length"] <= length <= self.config["max_chunk_length"]:
                filtered.append(chunk)
        return filtered
    
    def _index_chunks(self, chunks: list) -> int:
        """批量嵌入并写入向量库"""
        batch_size = self.config["batch_size"]
        total_indexed = 0
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            self.vectorstore.add_documents(batch)
            total_indexed += len(batch)
        
        return total_indexed


# ============ 使用 ============
if __name__ == "__main__":
    from langchain_community.embeddings import HuggingFaceBgeEmbeddings
    from langchain_community.vectorstores import Chroma
    
    # 初始化组件
    embedder = HuggingFaceBgeEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    vectorstore = Chroma(
        collection_name="knowledge_base",
        embedding_function=embedder,
        persist_directory="./chroma_db"
    )
    
    # 创建流水线
    pipeline = DocumentProcessingPipeline(
        embedder=embedder,
        vectorstore=vectorstore,
        config={
            "pdf": {"chunk_size": 800, "chunk_overlap": 100},
            "markdown": {"chunk_size": 1000, "chunk_overlap": 150},
            "code": {"chunk_size": 500, "chunk_overlap": 0},
            "batch_size": 32,
            "min_chunk_length": 30,
        }
    )
    
    # 处理文档目录
    # results = pipeline.process_directory("./documents/")
```

## 七、总结

文档切块和嵌入向量化是RAG系统中看似基础但至关重要的一环。几个核心原则：

1. **没有万能策略**：文档类型、内容特征、下游任务决定了最佳的切块方式和embedding选择
2. **从简到繁**：先用RecursiveCharacterTextSplitter + 通用embedding模型建立baseline，再逐步优化
3. **质量驱动**：定期抽样检查chunk质量和检索效果，不要凭感觉调参数
4. **保留元数据**：chunk的来源、位置、层级关系是检索后上下文还原的关键
5. **监控和迭代**：将切块和嵌入质量纳入系统监控，建立反馈循环

一个好的文档处理策略可以让RAG系统的事半功倍，反之则会让后续所有的优化努力大打折扣。
