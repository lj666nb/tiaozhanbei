"""
为6个模块题库中的每道题用AI生成严谨详细的解析，存入题库JSON文件。
用法: cd backend && python generate_analysis.py
"""
import json, os, asyncio, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.ai_service import call_llm

DATASET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dataset", "dataset"
)

MODULE_FILES = [
    "module_01_智能体基础通识.json",
    "module_02_大模型与提示词工程.json",
    "module_03_智能体四大核心能力模块.json",
    "module_04_开发框架与工程实践.json",
    "module_05_多智能体系统.json",
    "module_06_评估安全与前沿拓展.json",
]

USER_ID = 1
CONCURRENCY = 8


def build_prompt(q):
    """构建生成解析的prompt"""
    qtype = q.get("type", "简答")
    question = q.get("question", "")
    answer = q.get("answer", "")
    options = q.get("options", [])
    module = q.get("module", "")
    knowledge = q.get("knowledge_point", q.get("section", ""))

    opt_text = ""
    if options:
        labels = "ABCDEFGH"
        opt_lines = []
        for i, opt in enumerate(options):
            mark = " ✓（正确答案）" if opt.strip() == answer.strip() else ""
            opt_lines.append(f"  {labels[i] if i < len(labels) else i}. {opt}{mark}")
        opt_text = "\n".join(opt_lines)

    prompt = f"""你是一位AI智能体学科的资深导师，请为下面这道题目撰写一份严谨、详细的解析。

【所属模块】{module}
【知识点】{knowledge}
【题型】{qtype}
【题目】{question}"""

    if opt_text:
        prompt += f"""
【选项】
{opt_text}"""

    prompt += f"""
【正确答案】{answer}

【解析要求】
1. 先点明本题考察的核心知识点和考察意图
2. 对于选择题：逐一分析每个选项（为什么对/为什么错），重点讲解易混淆选项的区分点
3. 对于填空题：解释正确答案的含义和来源，说明常见错误填法及原因
4. 对于简答题：给出完整的答题要点框架，说明每个要点的给分权重
5. 最后给出「学习建议」：如何巩固该知识点、推荐记忆方法或关联知识
6. 语言严谨、专业但不晦涩，适合大学生阅读
7. 控制在200-400字
8. 用中文撰写"""

    return prompt


async def generate_one(q, sem, idx, total):
    """为单道题生成解析"""
    async with sem:
        try:
            prompt = build_prompt(q)
            resp = await call_llm(
                user_id=USER_ID,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,  # 低温度，追求准确性
                max_tokens=1024
            )
            if resp and not resp.startswith("LLM调用异常"):
                return (idx, resp.strip(), None)
            return (idx, None, resp)
        except Exception as e:
            return (idx, None, str(e))


async def process_module(mod_file):
    """处理单个模块文件"""
    mod_path = os.path.join(DATASET_DIR, mod_file)
    with open(mod_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pairs = data["qa_pairs"]
    total = len(pairs)

    # Filter: only process questions without analysis or with placeholder analysis
    to_process = []
    for i, q in enumerate(pairs):
        existing = q.get("analysis", "").strip()
        # Skip if already has a genuine analysis (not the template placeholder)
        if existing and len(existing) > 60 and not existing.startswith("【知识点】"):
            continue
        to_process.append(i)

    if not to_process:
        print(f"  {mod_file}: all {total} already have analysis, skipping")
        return 0

    print(f"  {mod_file}: {len(to_process)}/{total} need analysis generation")

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [generate_one(pairs[i], sem, i, len(to_process)) for i in to_process]

    done = 0
    failed = 0
    for future in asyncio.as_completed(tasks):
        i, analysis, err = await future
        done += 1
        if analysis:
            pairs[i]["analysis"] = analysis
            if done % 20 == 0:
                print(f"    [{done}/{len(to_process)}]  {mod_file}")
        else:
            failed += 1
            if failed <= 3:
                print(f"    FAIL #{i}: {err[:80] if err else 'empty'}")

    # Save
    with open(mod_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  {mod_file}: saved! {len(to_process) - failed} generated, {failed} failed")
    return len(to_process) - failed


async def main():
    global CONCURRENCY
    print("=" * 50)
    print("  题库解析批量生成")
    print("=" * 50)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", "-m", type=str, default="", help="Only process specific module (e.g. module_01)")
    parser.add_argument("--limit", "-n", type=int, default=0, help="Max questions per module (0=all)")
    parser.add_argument("--concurrency", "-c", type=int, default=CONCURRENCY)
    args = parser.parse_args()

    CONCURRENCY = args.concurrency

    files = MODULE_FILES
    if args.module:
        files = [f for f in files if args.module in f]
        if not files:
            print(f"No module matching '{args.module}'")
            return

    total_generated = 0
    start = time.time()

    for mod_file in files:
        mod_path = os.path.join(DATASET_DIR, mod_file)
        if not os.path.exists(mod_path):
            print(f"  SKIP: {mod_file} not found")
            continue

        if args.limit > 0:
            with open(mod_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Only process first N that need analysis
            need = 0
            for q in data["qa_pairs"]:
                existing = q.get("analysis", "").strip()
                if not existing or len(existing) <= 60 or existing.startswith("【知识点】"):
                    need += 1
            if need > args.limit:
                print(f"  {mod_file}: limiting to {args.limit} (need {need})")

        generated = await process_module(mod_file)
        total_generated += generated

    elapsed = time.time() - start
    print(f"\nDone! {total_generated} analyses generated in {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    asyncio.run(main())
