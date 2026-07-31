"""面向教材的文档加载与语义分块。

PDF 不是普通纯文本：视觉换行不等于段落，页边界也不等于语义边界。
本模块先清理页眉页脚和目录页，再按章节/句子构造父块，最后为父块生成
较小的检索子块。向量检索命中子块后，RAG 返回完整父块，避免把半句话
或只有目录的片段交给模型。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PARENT_MAX_CHARS = 1500
PARENT_MIN_CHARS = 260
CHILD_MAX_CHARS = 520
CHILD_MIN_CHARS = 140

_SENTENCE_RE = re.compile(r".+?(?:[。！？!?；;]|(?=\n)|$)", re.S)
_HEADING_RE = re.compile(
    r"^(?:第\s*[一二三四五六七八九十百\d]+\s*[章节篇部]|"
    r"\d+(?:\.\d+){1,3}|[（(]\s*\d+\s*[)）]|"
    r"\d+[.、])\s*.{1,80}$"
)
_PAGE_DECORATION_RE = re.compile(
    r"^(?:\s*\d+\s*[|∣]\s*.+|.+[|∣]\s*\d+\s*|"
    r"第\s*\d+\s*章.{0,50}\d+\s*|"
    r"\d+\s*[|∣]\s*AI\s*Agent.+|"
    r"AI\s*Agent.+[|∣]\s*\d+)\s*$",
    re.I,
)
_TOC_LINE_RE = re.compile(
    r"^(?:[❍●•▪■◆◇★☆]\s*)?第?\s*\d+\s*[章节篇部]?.{0,60}(?:\s+\d+)?$"
)


@dataclass
class DocumentChunk:
    """一个检索子块及其可返回的完整父块。"""

    text: str
    source_type: str
    source_path: str
    title: str = ""
    module: str = ""
    page: Optional[int] = None
    section: str = ""
    chunk_index: int = 0
    knowledge_point: str = ""
    difficulty: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        child_index = self.metadata.get("child_index", 0)
        parent_id = self.metadata.get("parent_id", "")
        content = (
            f"v2:{self.source_path}:{self.page}:{self.chunk_index}:"
            f"{child_index}:{parent_id}:{self.section}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:20]

    @property
    def source_label(self) -> str:
        if self.source_type == "pdf":
            end_page = int(self.metadata.get("end_page") or self.page or 0)
            if self.page and end_page and end_page != self.page:
                page_info = f"（第{self.page}-{end_page}页）"
            else:
                page_info = f"（第{self.page}页）" if self.page else ""
            return f"📖 {self.title}{page_info}"
        if self.source_type == "markdown":
            return f"📝 {self.title} — {self.section}"
        if self.source_type == "qa_pair":
            return f"📋 {self.module} — {self.knowledge_point}"
        return self.source_path


def _clean_line(line: str) -> str:
    line = re.sub(r"[\u00a0\u2002-\u200b\ufeff]", " ", line)
    # \u79fb\u9664 PDF \u76ee\u5f55\u4e2d\u7684 dot leaders\uff08\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7 \u6216 .............\uff09\u53ca\u8ddf\u968f\u7684\u9875\u7801
    line = re.sub(r"[\u00b7\u2022.]{4,}\s*\d*\s*$", "", line)
    line = re.sub(r"[ \t]+", " ", line).strip()
    return line


def _is_heading(line: str) -> bool:
    value = _clean_line(line)
    if not value or len(value) > 90:
        return False
    if _HEADING_RE.match(value):
        return True
    return bool(
        len(value) <= 35
        and not re.match(r"^(?:了|的|和|与|及|并|而|或|但|者|其|这|该)", value)
        and re.search(r"(概述|小结|实现|原理|架构|应用|流程|准备|模块|案例)$", value)
        and not re.search(r"[。！？；]$", value)
    )


def _looks_like_code(lines: list[str]) -> bool:
    if not lines:
        return False
    ascii_ratio = sum(ord(ch) < 128 for ch in "".join(lines)) / max(
        1, len("".join(lines))
    )
    code_markers = sum(
        bool(re.search(r"^(?:def |class |import |from |pip |# |@|\w+\s*=)", line))
        for line in lines
    )
    syntax_lines = sum(
        bool(re.search(r"[{}[\]=]|\b(?:return|raise|print|await|yield)\b", line))
        for line in lines
    )
    return (
        ascii_ratio > 0.72
        and code_markers >= 2
        and syntax_lines >= 2
        and code_markers >= max(2, len(lines) // 5)
    )


def _join_visual_lines(raw: str) -> list[str]:
    """把 PDF 视觉换行恢复为段落，同时保留标题、列表和代码边界。"""
    raw_lines = [_clean_line(line) for line in raw.splitlines()]
    lines = [
        line
        for line in raw_lines
        if line
        and not re.fullmatch(r"[-—_=·•\s]{2,}", line)
        and not _PAGE_DECORATION_RE.match(line)
        and not re.fullmatch(r"\d{1,4}", line)
    ]
    if not lines:
        return []
    if _looks_like_code(lines):
        return ["\n".join(lines)]

    paragraphs: list[str] = []
    current = ""
    for line in lines:
        boundary = _is_heading(line) or bool(
            re.match(r"^(?:[❍●•▪■◆◇★☆]|[（(]\d+[)）]|[一二三四五六七八九十]+、)", line)
        )
        if boundary:
            if current:
                paragraphs.append(current)
                current = ""
            paragraphs.append(line)
            continue
        if current:
            if re.search(r"[A-Za-z0-9]$", current) and re.match(r"^[A-Za-z0-9]", line):
                current += " " + line
            else:
                current += line
        else:
            current = line
        if re.search(r"[。！？!?；;：:]$", current):
            paragraphs.append(current)
            current = ""
    if current:
        paragraphs.append(current)
    return [p.strip() for p in paragraphs if p.strip()]


def _is_toc_page(paragraphs: list[str]) -> bool:
    """识别只承载目录/篇章导航而没有解释性正文的页面。"""
    if not paragraphs:
        return True
    text = "\n".join(paragraphs)
    toc_hits = sum(
        bool(
            _TOC_LINE_RE.match(p)
            or re.match(r"^[❍●•▪■◆◇★☆]?\s*第\s*\d+\s*章", p)
        )
        for p in paragraphs
    )
    explanatory = len(re.findall(r"[。！？；]", text))
    return (
        ("目录" in text and explanatory <= 2)
        or (
            "AI Agent 实现篇" in text
            and len(re.findall(r"第\s*\d+\s*章", text)) >= 2
        )
        or (toc_hits >= 3 and explanatory <= 2)
        or (len(paragraphs) <= 6 and toc_hits >= max(2, len(paragraphs) - 1))
    )


def _sentences(text: str) -> list[str]:
    """句子级切分；极长代码/句子只在换行或标点处切，不从任意字符处硬砍。"""
    result = []
    for paragraph in [p.strip() for p in text.split("\n") if p.strip()]:
        if _is_heading(paragraph):
            result.append(paragraph)
            continue
        parts = [m.group(0).strip() for m in _SENTENCE_RE.finditer(paragraph)]
        result.extend(part for part in parts if part)
    return result


def _unit_is_complete(text: str) -> bool:
    return bool(re.search(r"[。！？!?；;：:）)】\]”’」』]$", text.strip()))


def _append_unit(units: list[tuple[str, int]], sentence: str, page: int) -> None:
    """跨视觉块/跨页续接残句，列表与标题保持独立。"""
    sentence = sentence.strip()
    if not sentence:
        return
    is_list = bool(
        _is_heading(sentence)
        or re.match(r"^(?:[❍●•▪■◆◇★☆]|[（(]\d+[)）]|[一二三四五六七八九十]+、)", sentence)
    )
    if (
        units
        and not _unit_is_complete(units[-1][0])
        and not is_list
        and len(units[-1][0]) < 700
    ):
        previous, previous_page = units[-1]
        spacer = " " if re.search(r"[A-Za-z0-9]$", previous) and re.match(r"^[A-Za-z0-9]", sentence) else ""
        units[-1] = (previous + spacer + sentence, previous_page)
    else:
        units.append((sentence, page))


def _pack_units(
    units: list[tuple[str, int]],
    *,
    max_chars: int,
    min_chars: int,
    overlap_units: int = 1,
) -> list[tuple[str, int, int]]:
    expanded_units: list[tuple[str, int]] = []
    for unit, page in units:
        if len(unit) <= max_chars:
            expanded_units.append((unit, page))
            continue
        # 代码块或超长公式不丢弃任何内容：优先在换行、标点和空格处分成
        # 多个检索单元。只有完全没有安全边界时才按长度拆开，但不会截断。
        remaining = unit
        while len(remaining) > max_chars:
            window = remaining[: max_chars + 1]
            lower_bound = max(1, int(max_chars * 0.58))
            safe_positions = [
                window.rfind(token, lower_bound)
                for token in ("\n", "。", "；", ";", "，", ",", " ", ")", "}")
            ]
            cut = max(safe_positions)
            if cut < lower_bound:
                cut = max_chars
            else:
                cut += 1
            expanded_units.append((remaining[:cut].rstrip(), page))
            remaining = remaining[cut:].lstrip()
        if remaining:
            expanded_units.append((remaining, page))

    packed: list[tuple[str, int, int]] = []
    current: list[tuple[str, int]] = []
    size = 0
    for unit, page in expanded_units:
        if current and size + len(unit) + 1 > max_chars and size >= min_chars:
            packed.append(("\n".join(x[0] for x in current), current[0][1], current[-1][1]))
            current = current[-overlap_units:] if overlap_units else []
            size = sum(len(x[0]) + 1 for x in current)
        current.append((unit, page))
        size += len(unit) + 1
    if current:
        tail = ("\n".join(x[0] for x in current), current[0][1], current[-1][1])
        if packed and len(tail[0]) < min_chars:
            previous_text, previous_start, _ = packed[-1]
            packed[-1] = (
                previous_text + "\n" + tail[0],
                previous_start,
                tail[2],
            )
        else:
            packed.append(tail)
    return packed


def _make_parent_child_chunks(
    *,
    section: str,
    units: list[tuple[str, int]],
    source_path: str,
    title: str,
    module: str,
    parent_offset: int,
    source_type: str = "pdf",
) -> list[DocumentChunk]:
    result: list[DocumentChunk] = []
    parent_units = _pack_units(
        units,
        max_chars=PARENT_MAX_CHARS,
        min_chars=PARENT_MIN_CHARS,
        overlap_units=1,
    )
    for parent_index, (parent_text, start_page, end_page) in enumerate(parent_units):
        if section and not parent_text.startswith(section):
            parent_text = f"{section}\n{parent_text}"
        quality = chunk_quality_score(parent_text)
        if quality < 0.45:
            continue
        parent_id = hashlib.sha256(
            f"{source_path}:{section}:{parent_offset + parent_index}:{parent_text}".encode("utf-8")
        ).hexdigest()[:20]
        sentence_units = [(sentence, start_page) for sentence in _sentences(parent_text)]
        child_units = _pack_units(
            sentence_units,
            max_chars=CHILD_MAX_CHARS,
            min_chars=CHILD_MIN_CHARS,
            overlap_units=1,
        )
        for child_index, (child_text, _, _) in enumerate(child_units):
            # 检索文本：领域标签 + 短标题 + 章节 + 内容正文
            # 把最多空间留给实际内容（child_text），而非元数据
            short_title = title[:30] if len(title) > 30 else title
            domain_tag = "数据分析与挖掘" if any(
                kw in title for kw in ("数据", "数据分析", "数据挖掘", "数据仓库")
            ) else "AI智能体"
            retrieval_text = f"【{domain_tag}】{short_title} | {section}\n{child_text}".strip()
            result.append(
                DocumentChunk(
                    text=parent_text,
                    source_type=source_type,
                    source_path=source_path,
                    title=title,
                    module=module,
                    page=start_page or None,
                    section=section or f"第{start_page}页",
                    chunk_index=parent_offset + parent_index,
                    metadata={
                        "parent_id": parent_id,
                        "child_index": child_index,
                        "end_page": end_page,
                        "embedding_text": retrieval_text,
                        "quality_score": round(quality, 3),
                        "chunk_version": "semantic-parent-child-v2",
                    },
                )
            )
    return result


def chunk_quality_score(text: str) -> float:
    """对目录、纯代码块、残句和信息密度低的块降权；0~1。"""
    value = text.strip()
    if not value:
        return 0.0
    score = 1.0
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if _is_toc_page(lines):
        score -= 0.65
    if len(value) < 180:
        score -= 0.25
    # 中文字符占比：概念查询依赖中文语义，低中文比例块几乎无检索价值
    chinese_chars = len(re.findall(r"[一-鿿]", value))
    total_chars = max(1, len(value))
    cn_ratio = chinese_chars / total_chars
    if cn_ratio < 0.25:
        score -= 0.55  # 几乎是纯代码/纯ASCII，对中文概念查询毫无价值
    elif cn_ratio < 0.50:
        score -= 0.30  # 以代码为主，中文概念检索价值低
    # 惩罚包含大量 dot leaders 的块
    dot_leader_chars = len(re.findall(r"[·•.]", value))
    if dot_leader_chars > 20:
        score -= 0.30
    if len(re.findall(r"[。！？；:：]", value)) < 2:
        score -= 0.15
    if re.match(r"^(?:了|的|和|与|及|并|而|或|但|者|其|这|该|从而)", value):
        score -= 0.12
    if value.endswith(("，", "、", "：", "（", "(", "的", "了")):
        score -= 0.15
    return max(0.0, min(1.0, score))


def load_pdf_documents(pdf_dir: str) -> list[DocumentChunk]:
    import fitz

    chunks: list[DocumentChunk] = []
    pdf_path = Path(pdf_dir)
    if not pdf_path.exists():
        logger.warning("PDF 目录不存在: %s", pdf_dir)
        return chunks

    pdf_files = sorted(pdf_path.rglob("*.pdf"))
    logger.info("发现 %s 个 PDF 文件", len(pdf_files))
    for pdf_file in pdf_files:
        try:
            doc = fitz.open(str(pdf_file))
            title = _clean_book_title(pdf_file.stem)
            module = _infer_module_from_title(title)
            sections: list[tuple[str, list[tuple[str, int]], str]] = []  # (section, units, parent_heading)
            current_title = ""
            current_units: list[tuple[str, int]] = []
            _parent_heading = ""  # 跟踪最近的父级章节标题（如 5.2.2 k均值聚类算法）

            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1], 1), b[0]))
                page_paragraphs: list[str] = []
                page_height = max(1.0, float(page.rect.height))
                for block in blocks:
                    y0, y1 = float(block[1]), float(block[3])
                    if y0 < page_height * 0.055 or y1 > page_height * 0.95:
                        continue
                    page_paragraphs.extend(_join_visual_lines(str(block[4] or "")))

                if _is_toc_page(page_paragraphs):
                    continue
                for paragraph in page_paragraphs:
                    if _is_heading(paragraph):
                        if current_units:
                            if current_units and not _unit_is_complete(current_units[-1][0]) and len(current_units[-1][0]) < 90:
                                current_units.pop()
                            sections.append((current_title, current_units, _parent_heading))
                        # 检测多级编号标题（如 5.2 或 5.2.2），更新父级标题
                        if re.match(r"\d+(?:\.\d+){1,}\s", paragraph):
                            _parent_heading = paragraph
                        current_title = paragraph
                        current_units = []
                    else:
                        for sentence in _sentences(paragraph):
                            _append_unit(current_units, sentence, page_num + 1)
            if current_units:
                sections.append((current_title, current_units, _parent_heading))
            doc.close()

            parent_offset = 0
            for section, units, parent_heading in sections:
                # 子章节继承父标题上下文，防止 "1.算法过程" 丢失 "k均值聚类算法" 语义
                enriched_section = section
                if parent_heading and parent_heading != section and not section.startswith(parent_heading):
                    enriched_section = f"{parent_heading} > {section}"
                section_chunks = _make_parent_child_chunks(
                    section=enriched_section,
                    units=units,
                    source_path=str(pdf_file),
                    title=title,
                    module=module,
                    parent_offset=parent_offset,
                )
                chunks.extend(section_chunks)
                parent_offset += max(1, len({c.metadata["parent_id"] for c in section_chunks}))
            logger.info("  [%s 子块] %s", len(chunks), title)
        except Exception as exc:
            logger.exception("PDF 解析失败: %s — %s", pdf_file, exc)
    return chunks


def _split_by_headings(text: str, level: int = 2) -> list[tuple[str, str]]:
    pattern = re.compile(rf"^{'#' * level}\s+(.+)$")
    sections: list[tuple[str, str]] = []
    title = ""
    content: list[str] = []
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            if content:
                sections.append((title, "\n".join(content)))
            title, content = match.group(1).strip(), []
        elif content or line.strip():
            content.append(line)
    if content:
        sections.append((title, "\n".join(content)))
    return sections or [("", text)]


def _split_paragraphs(text: str, max_chars: int = 800, min_chars: int = 200) -> list[str]:
    units = [(unit, 0) for unit in _sentences(text)]
    return [item[0] for item in _pack_units(units, max_chars=max_chars, min_chars=min_chars)]


def load_markdown_documents(
    materials_dir: str,
    index_path: Optional[str] = None,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    base = Path(materials_dir)
    if not base.exists():
        return chunks
    index: dict = {}
    if index_path and Path(index_path).exists():
        data = json.loads(Path(index_path).read_text(encoding="utf-8"))
        for module_name, topics in data.get("modules", {}).items():
            for topic_name, rel_path in topics.items():
                index[rel_path] = {"module": module_name, "topic": topic_name}
    for md_file in sorted(base.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        rel_path = str(md_file.relative_to(base))
        entry = index.get(rel_path, {})
        title = entry.get("topic", md_file.stem)
        module = entry.get("module", "")
        offset = 0
        for section, section_text in _split_by_headings(content):
            units = [(unit, 0) for unit in _sentences(section_text)]
            created = _make_parent_child_chunks(
                section=section or title,
                units=units,
                source_path=rel_path,
                title=title,
                module=module,
                parent_offset=offset,
                source_type="markdown",
            )
            chunks.extend(created)
            offset += max(1, len({c.metadata["parent_id"] for c in created}))
    return chunks


def load_qa_documents(dataset_dir: str) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    base = Path(dataset_dir)
    if not base.exists():
        return chunks
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            questions = (
                data
                if isinstance(data, list)
                else data.get("qa_pairs", data.get("questions", []))
            )
            for index, item in enumerate(questions):
                text = "\n".join(
                    part
                    for part in (
                        f"问题：{item.get('question', '')}" if item.get("question") else "",
                        f"答案：{item.get('answer', '')}" if item.get("answer") else "",
                        f"解析：{item.get('analysis', '')}" if item.get("analysis") else "",
                    )
                    if part
                )
                if len(text) < 40:
                    continue
                parent_id = hashlib.sha256(f"{path}:{index}:{text}".encode("utf-8")).hexdigest()[:20]
                chunks.append(
                    DocumentChunk(
                        text=text,
                        source_type="qa_pair",
                        source_path=path.name,
                        title=item.get("knowledge_point", item.get("section", "")),
                        module=item.get("module", ""),
                        section=item.get("section", ""),
                        knowledge_point=item.get("knowledge_point", ""),
                        difficulty=item.get("difficulty", ""),
                        chunk_index=index,
                        metadata={
                            "parent_id": parent_id,
                            "child_index": 0,
                            "embedding_text": text,
                            "quality_score": round(chunk_quality_score(text), 3),
                            "chunk_version": "semantic-parent-child-v2",
                        },
                    )
                )
        except Exception as exc:
            logger.warning("题库解析失败 %s: %s", path, exc)
    return chunks


def load_all_documents(
    pdf_dir: str = "pdf",
    materials_dir: str = "learning_materials",
    dataset_dir: str = "backend/data/dataset",
    index_path: str = "learning_materials/index.json",
) -> list[DocumentChunk]:
    chunks = load_pdf_documents(pdf_dir)
    chunks.extend(load_markdown_documents(materials_dir, index_path))
    chunks.extend(load_qa_documents(dataset_dir))
    logger.info("总计: %s 个检索子块", len(chunks))
    return chunks


def _clean_book_title(raw: str) -> str:
    """清理 PDF 文件名中的平台后缀和冗长作者列表，保留有意义的书名。"""
    title = raw.strip()
    # 去掉方括号标注 [转换版] 等
    title = re.sub(r"\s*\[[^\]]*\]", "", title)
    # 去掉末尾的括号内容：作者列表（含逗号/分号/著）、出版社、平台标识
    # 反复执行直到没有更多匹配，处理嵌套括号
    for _ in range(3):
        before = title
        title = re.sub(
            r"\s*\([^)]*(?:[；;，,、]|著|编著|主编|出版社|z-library|z-lib|1lib|sk\.|it-ebooks|Publisher)[^)]*\)\s*$",
            "", title, flags=re.I,
        )
        title = re.sub(
            r"\s*（[^）]*(?:[；;，,、]|著|编著|主编|出版社|z-library|z-lib|1lib|sk\.)[^）]*）\s*$",
            "", title, flags=re.I,
        )
        if title == before:
            break
    title = re.sub(r"\s+", " ", title).strip()
    return title if len(title) >= 4 else raw.strip()


def _infer_module_from_title(title: str) -> str:
    module_keywords = {
        "多智能体": "模块五：多智能体系统",
        "数据挖掘": "数据分析与挖掘",
        "数据分析": "数据分析与挖掘",
        "数据仓库": "数据分析与挖掘",
        "框架": "模块四：开发框架与工程实践",
        "实战": "模块四：开发框架与工程实践",
        "企业": "模块四：开发框架与工程实践",
        "开发": "模块三：智能体核心能力",
        "应用": "模块三：智能体核心能力",
    }
    for keyword, module in module_keywords.items():
        if keyword in title:
            return module
    return "模块一：智能体基础通识"
