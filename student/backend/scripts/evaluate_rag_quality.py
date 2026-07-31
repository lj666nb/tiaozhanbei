"""构建前后都可运行的 RAG 质量门禁。

默认只检查 PDF 分块；传入 --retrieve 可用 SiliconFlow 做真实 Top-K 检索。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from services.document_loader import chunk_quality_score, load_all_documents  # noqa: E402


def is_broken(text: str) -> bool:
    value = (text or "").strip()
    first_line = value.splitlines()[0].strip() if value else ""
    has_section_heading = "\n" in value and len(first_line) <= 80
    return (
        not value
        or chunk_quality_score(value) < 0.45
        or (
            not has_section_heading
            and bool(re.match(r"^(?:了|的|和|与|及|并|而|或|但|者|其)", value))
        )
        or (
            len(value) < 180
            and value.endswith(("，", "、", "：", "（", "(", "的"))
        )
    )


def evaluate_chunks(chunks: list) -> dict:
    parents = {}
    for chunk in chunks:
        parents.setdefault(chunk.metadata.get("parent_id") or chunk.doc_id, chunk)
    values = list(parents.values())
    toc = [
        chunk
        for chunk in values
        if re.search(r"AI Agent 实现篇", chunk.text)
        and len(re.findall(r"[。！？；]", chunk.text)) <= 2
    ]
    broken = [chunk for chunk in values if is_broken(chunk.text)]
    return {
        "children": len(chunks),
        "parents": len(values),
        "toc_fragments": len(toc),
        "broken_parents": len(broken),
        "broken_rate": round(len(broken) / max(1, len(values)), 4),
        "broken_examples": [
            {
                "source": chunk.title,
                "page": chunk.page,
                "section": chunk.section,
                "preview": chunk.text[:260],
            }
            for chunk in broken[:12]
        ],
    }


def evaluate_retrieval(questions: list[dict], top_k: int, provider: str) -> dict:
    from services.rag_service import get_rag_service

    if provider == "siliconflow":
        api_key = os.getenv("SILICONFLOW_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("使用 SiliconFlow 评测时必须设置 SILICONFLOW_API_KEY")
        rag = get_rag_service(
            provider="siliconflow",
            api_key=api_key,
            model="BAAI/bge-large-zh-v1.5",
            force_reload=True,
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}，请使用 siliconflow")
    details = []
    passed = 0
    for item in questions:
        results = rag.retrieve(item["question"], top_k=top_k)
        joined = "\n".join(result.get("text", "") for result in results)
        expected = [word for word in item.get("expected_any", []) if word in joined]
        broken_count = sum(is_broken(result.get("text", "")) for result in results)
        ok = bool(expected) and broken_count == 0 and len(results) >= min(3, top_k)
        passed += int(ok)
        details.append(
            {
                "question": item["question"],
                "returned": len(results),
                "matched": expected,
                "broken": broken_count,
                "passed": ok,
                "top_sections": [
                    (result.get("metadata") or {}).get("section", "")
                    for result in results[:3]
                ],
                "top_previews": [
                    (result.get("text") or "")[:360]
                    for result in results[:3]
                ],
                "broken_previews": [
                    (result.get("text") or "")[:420]
                    for result in results
                    if is_broken(result.get("text", ""))
                ],
            }
        )
    return {
        "passed": passed,
        "total": len(questions),
        "pass_rate": round(passed / max(1, len(questions)), 4),
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieve", action="store_true")
    parser.add_argument("--provider", choices=["siliconflow"], default="siliconflow")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--json-output", default="")
    parser.add_argument("--skip-chunking", action="store_true")
    args = parser.parse_args()

    questions = json.loads(
        (BACKEND / "data" / "rag_eval_questions.json").read_text(encoding="utf-8")
    )
    report = {}
    if not args.skip_chunking:
        chunks = load_all_documents(
            pdf_dir=str(ROOT / "pdf"),
            materials_dir=str(ROOT / "learning_materials"),
            dataset_dir=str(BACKEND / "data" / "dataset"),
            index_path=str(ROOT / "learning_materials" / "index.json"),
        )
        report["chunking"] = evaluate_chunks(chunks)
        examples = [
            chunk
            for chunk in chunks
            if "多模态" in chunk.text and "Mobile-Agent" in chunk.text
        ]
        report["multimodal_examples"] = [
            {
                "page": chunk.page,
                "end_page": chunk.metadata.get("end_page"),
                "section": chunk.section,
                "quality": chunk.metadata.get("quality_score"),
                "preview": chunk.text[:500],
            }
            for chunk in examples[:3]
        ]
    if args.retrieve:
        report["retrieval"] = evaluate_retrieval(questions, args.top_k, args.provider)

    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.json_output:
        Path(args.json_output).write_text(serialized, encoding="utf-8")
    chunking = report.get("chunking")
    if chunking and (chunking["toc_fragments"] or chunking["broken_rate"] > 0.05):
        return 1
    if args.retrieve and report["retrieval"]["pass_rate"] < 0.75:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
