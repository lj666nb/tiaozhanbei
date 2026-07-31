"""
批量预生成所有学习材料中的 AI 配图。
用法: cd backend && python pre_generate_images.py
"""
import os, sys, asyncio, hashlib, re, time

# Ensure backend packages are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.image_service import generate_image
import sqlite3
import sqlite3 as _sqlite3_module

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning_materials")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "learning_platform.db")

USER_ID = 1  # Demo user
CONCURRENCY = 5  # Parallel API calls

# ---- Extract all unique prompts ----

def extract_prompts():
    """遍历所有md文件，提取所有唯一Image-Prompt块"""
    unique = {}  # hash -> {file, name, body}
    for root, dirs, files in os.walk(BASE):
        for f in files:
            if not f.endswith('.md'):
                continue
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fp:
                content = fp.read()

            pattern = (r'(?:\*\*)?Image-Prompt\([^)]+\):(?:\*\*)?\s*'
                       r'(.+?)(?=\n\n(?:#|\*\*Image-Prompt|Image-Prompt)'
                       r'|\n(?:#|\*\*Image-Prompt|Image-Prompt)|$)')
            for match in re.finditer(pattern, content, re.DOTALL):
                body = match.group(1).strip()
                if body.startswith('```'):
                    body = body[3:]
                if body.endswith('```'):
                    body = body[:-3]
                body = body.strip()
                if len(body) < 10:
                    continue
                h = hashlib.sha256(body.encode()).hexdigest()
                m0 = match.group(0)[:100]
                name = m0.split(')')[0].split('(')[-1] if '(' in m0 else '?'
                if h not in unique:
                    unique[h] = {
                        'file': os.path.relpath(path, BASE),
                        'name': name,
                        'body': body
                    }
    return unique


def get_cached_hashes():
    """获取已缓存的prompt_hash"""
    conn = sqlite3.connect(DB)
    try:
        rows = conn.execute(
            "SELECT prompt_hash FROM generated_images WHERE svg_content IS NOT NULL"
        ).fetchall()
        return set(r[0] for r in rows)
    except:
        return set()
    finally:
        conn.close()


async def generate_batch(prompts_to_generate, cached_set):
    """并发批量生成图片"""
    sem = asyncio.Semaphore(CONCURRENCY)
    total = len(prompts_to_generate)
    done = 0
    failed = 0
    start = time.time()

    async def generate_one(prompt_hash, info):
        nonlocal done, failed
        async with sem:
            try:
                result = await generate_image(USER_ID, info['body'])
                if result.get('success'):
                    return (prompt_hash, True, None)
                else:
                    return (prompt_hash, False, result.get('error', 'unknown'))
            except Exception as e:
                return (prompt_hash, False, str(e))

    tasks = [generate_one(h, info) for h, info in prompts_to_generate.items()]

    # Process in chunks to report progress
    chunk_size = 5
    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i:i+chunk_size]
        results = await asyncio.gather(*chunk)
        for h, ok, err in results:
            done += 1
            if ok:
                pct = done * 100 // total
                elapsed = time.time() - start
                eta = (elapsed / done) * (total - done) if done > 0 else 0
                print(f"[{done}/{total} {pct}%] OK  {h[:16]}... | ETA {eta:.0f}s")
            else:
                failed += 1
                print(f"[{done}/{total} {pct}%] FAIL {h[:16]}... | {err}")

    elapsed = time.time() - start
    print(f"\nDone! {done} total, {failed} failed, in {elapsed:.0f}s ({elapsed/60:.1f}min)")
    return failed


def main():
    global CONCURRENCY
    import argparse
    parser = argparse.ArgumentParser(description="Pre-generate all AI illustrations for learning materials")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--limit", "-n", type=int, default=0, help="Only generate N images (0=all)")
    parser.add_argument("--test", action="store_true", help="Generate just 1 image and exit")
    parser.add_argument("--concurrency", "-c", type=int, default=CONCURRENCY, help="Parallel API calls")
    args = parser.parse_args()

    CONCURRENCY = args.concurrency

    print("Extracting prompts from markdown files...")
    unique_prompts = extract_prompts()
    print(f"Unique prompts: {len(unique_prompts)}")

    cached = get_cached_hashes()
    print(f"Already cached: {len(cached)}")

    to_generate = {h: info for h, info in unique_prompts.items() if h not in cached}
    print(f"Need to generate: {len(to_generate)}")

    if args.test:
        to_generate = {h: to_generate[h] for h in list(to_generate.keys())[:1]}
        print("TEST MODE: will only generate 1 image")

    if args.limit > 0:
        to_generate = {h: to_generate[h] for h in list(to_generate.keys())[:args.limit]}
        print(f"LIMITED: generating {args.limit} images")

    if not to_generate:
        print("All images already cached! Nothing to do.")
        return

    # Preview
    print("\nFirst 10 to generate:")
    for i, (h, info) in enumerate(sorted(to_generate.items(), key=lambda x: x[1]['file'])):
        if i >= 10:
            break
        print(f"  [{info['name']}] {info['file']}: {info['body'][:80]}...")

    # Confirm
    if not args.yes and not args.test:
        print(f"\nAbout to generate {len(to_generate)} images using LLM API.")
        print(f"Concurrency: {CONCURRENCY}, User ID: {USER_ID}")
        resp = input("Proceed? (y/N): ").strip().lower()
        if resp != 'y':
            print("Aborted.")
            return

    failed = asyncio.run(generate_batch(to_generate, cached))

    # Final report
    final_cached = get_cached_hashes()
    print(f"\nFinal: {len(final_cached)} cached in DB, {failed} failures")


if __name__ == "__main__":
    main()
