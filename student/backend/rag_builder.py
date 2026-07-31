#!/usr/bin/env python3
"""RAG 知识库构建脚本 — 一键构建向量知识库

用法:
    # 使用 DashScope 云端嵌入
    python backend/rag_builder.py --api-key sk-xxx

    # 使用 SiliconFlow 云端嵌入
    python backend/rag_builder.py --provider siliconflow --api-key sk-xxx

    # 增量模式（只处理新增文档）
    python backend/rag_builder.py --api-key sk-xxx --incremental
"""

import os
import sys
import time
import argparse
from pathlib import Path

# 修复 Windows GBK 编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 确保项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services.embedding_service import get_embedding_backend
from services.rag_service import RAGService
from services.document_loader import load_all_documents


def main():
    parser = argparse.ArgumentParser(description="RAG 知识库构建工具")
    parser.add_argument("--provider", default="dashscope", choices=["dashscope", "siliconflow"],
                        help="嵌入后端（默认: dashscope）")
    parser.add_argument("--api-key", default="", help="DashScope API Key")
    parser.add_argument("--model", default="text-embedding-v3", help="嵌入模型名")
    parser.add_argument("--incremental", action="store_true", help="增量模式（仅处理新文档）")
    parser.add_argument("--pdf-dir", default="pdf", help="PDF 教材目录")
    parser.add_argument("--materials-dir", default="learning_materials", help="学习材料目录")
    parser.add_argument("--dataset-dir", default="backend/data/dataset", help="题库目录")
    parser.add_argument("--index-path", default="learning_materials/index.json", help="学习材料索引")
    parser.add_argument("--batch-size", type=int, default=50, help="入库批大小")
    parser.add_argument("--chroma-path", default="backend/data/chroma_db", help="ChromaDB 存储路径")
    args = parser.parse_args()

    # 获取 API Key
    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if args.provider == "dashscope" and not api_key:
        print("❌ DashScope 需要 API Key。请通过 --api-key 或环境变量 DASHSCOPE_API_KEY 提供。")
        sys.exit(1)

    print("=" * 60)
    print("  RAG 知识库构建工具")
    print(f"  嵌入后端: {args.provider}")
    print(f"  模式: {'增量' if args.incremental else '全量'}")
    print("=" * 60)

    # 加载文档
    print("\n[1/3] 加载文档...")
    t0 = time.time()
    chunks = load_all_documents(
        pdf_dir=args.pdf_dir,
        materials_dir=args.materials_dir,
        dataset_dir=args.dataset_dir,
        index_path=args.index_path,
    )
    load_time = time.time() - t0
    print(f"  ✅ 加载完成: {len(chunks)} 个文档块（耗时 {load_time:.1f}s）")

    if not chunks:
        print("  ⚠️  未找到任何文档，请检查数据路径。")
        return

    # 按类型统计
    from collections import Counter
    type_counts = Counter(c.source_type for c in chunks)
    for t, cnt in type_counts.most_common():
        print(f"     {t}: {cnt}")

    # 初始化嵌入后端
    print("\n[2/3] 初始化嵌入后端...")
    t0 = time.time()
    backend = get_embedding_backend(
        provider=args.provider,
        api_key=api_key,
        model=args.model,
        force_reload=True,
    )
    init_time = time.time() - t0
    print(f"  ✅ {backend.NAME} 初始化完成（耗时 {init_time:.1f}s）")

    # 入库
    print(f"\n[3/3] 文档向量化与入库...")
    rag = RAGService(backend=backend, chroma_path=args.chroma_path)

    if args.incremental:
        result = rag.ingest(chunks, batch_size=args.batch_size)
    else:
        result = rag.rebuild(chunks)

    total_time = time.time() - t0 + init_time + load_time

    # 输出结果
    print(f"\n{'=' * 60}")
    print(f"  构建完成！")
    print(f"  总文档块:  {result['total']}")
    print(f"  新增入库:  {result['new']}")
    print(f"  跳过（已存在）: {result['skipped']}")
    print(f"  错误:     {result['errors']}")
    print(f"  知识库:   {rag.collection_name}")
    print(f"  存储路径: {rag.chroma_path}")
    print(f"  总耗时:   {total_time:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
