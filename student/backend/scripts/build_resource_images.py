"""
为每个学习资源选择5个均匀分布的Image-Prompt并生成图片
用法: cd backend && python build_resource_images.py
"""
import json, os, re, hashlib, asyncio, sqlite3, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.image_service import generate_image

RESOURCES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "resources.json")
INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning_materials", "index.json")
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "learning_materials")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "learning_platform.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "resource_image_config.json")

USER_ID = 1
CONCURRENCY = 6


def load_flat_index():
    """tag -> rel_path"""
    if not os.path.exists(INDEX_PATH):
        return {}
    data = json.load(open(INDEX_PATH, encoding='utf-8'))
    flat = {}
    for mod, items in data.get("modules", {}).items():
        for tag, rel in items.items():
            flat[tag] = rel
    return flat


def extract_prompts_in_order(resource_id, tags, flat_index):
    """按关联markdown文件顺序提取所有Image-Prompt，去重但保持顺序"""
    seen_files = []
    for tag in tags:
        rel = flat_index.get(tag)
        if rel and rel not in seen_files:
            seen_files.append(rel)

    prompts = []
    seen_hashes = set()
    for rel in seen_files:
        full = os.path.join(BASE, rel)
        if not os.path.exists(full):
            continue
        with open(full, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = (r'(?:\*\*)?Image-Prompt\([^)]+\):(?:\*\*)?\s*'
                   r'(.+?)(?=\n\n(?:#|\*\*Image-Prompt|Image-Prompt)'
                   r'|\n(?:#|\*\*Image-Prompt|Image-Prompt)|$)')
        for m in re.finditer(pattern, content, re.DOTALL):
            body = m.group(1).strip()
            if body.startswith('```'): body = body[3:]
            if body.endswith('```'): body = body[:-3]
            body = body.strip()
            if len(body) < 10:
                continue
            h = hashlib.sha256(body.encode()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                prompts.append({
                    'hash': h,
                    'body': body,
                    'file': rel
                })
    return prompts


def pick_evenly(prompts, n=5):
    """从列表中均匀选择n个元素"""
    if len(prompts) <= n:
        return prompts
    indices = [int(i * (len(prompts) - 1) / (n - 1)) for i in range(n)]
    selected = [prompts[idx] for idx in indices]
    return selected


def get_cached_hashes():
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


async def generate_batch(to_generate):
    """并发生成一批图片"""
    sem = asyncio.Semaphore(CONCURRENCY)
    total = len(to_generate)
    done = 0
    failed = 0
    import time
    start = time.time()

    async def gen_one(h, body):
        nonlocal done, failed
        async with sem:
            try:
                result = await generate_image(USER_ID, body)
                if result.get('success'):
                    return (h, True, None)
                return (h, False, result.get('error', 'unknown'))
            except Exception as e:
                return (h, False, str(e))

    tasks = [gen_one(h, body) for h, body in to_generate.items()]

    for i in range(0, len(tasks), CONCURRENCY):
        chunk = tasks[i:i+CONCURRENCY]
        results = await asyncio.gather(*chunk)
        for h, ok, err in results:
            done += 1
            pct = done * 100 // total
            elapsed = time.time() - start
            eta = (elapsed / done) * (total - done) if done > 0 else 0
            if ok:
                print(f"  [{done}/{total} {pct}%] OK  {h[:16]}...  ETA {eta:.0f}s")
            else:
                failed += 1
                print(f"  [{done}/{total} {pct}%] FAIL {h[:16]}... {err}")

    elapsed = time.time() - start
    print(f"  Done: {done} total, {failed} failed, {elapsed:.0f}s")
    return failed


def main():
    global CONCURRENCY
    print("=" * 60)
    print("  学习资源图片预生成 — 每资源5张均匀分布")
    print("=" * 60)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--concurrency", "-c", type=int, default=CONCURRENCY)
    parsed_args, _ = parser.parse_known_args()
    CONCURRENCY = parsed_args.concurrency

    resources = json.load(open(RESOURCES_PATH, encoding='utf-8'))
    flat = load_flat_index()
    cached = get_cached_hashes()

    # Step 1: Select 5 evenly distributed prompts per resource
    config = {}  # resource_id -> [hash1, hash2, ...]
    all_to_generate = {}  # hash -> body (unique across all resources)

    for res in resources:
        rid = res['id']
        tags = res.get('tags', [])
        prompts = extract_prompts_in_order(rid, tags, flat)

        if not prompts:
            config[rid] = []
            continue

        selected = pick_evenly(prompts, 5)
        config[rid] = [p['hash'] for p in selected]

        for p in selected:
            if p['hash'] not in cached and p['hash'] not in all_to_generate:
                all_to_generate[p['hash']] = p['body']

    # Step 2: Report
    total_prompts = sum(len(v) for v in config.values())
    resources_with_images = sum(1 for v in config.values() if v)
    print(f"\nResources: {len(resources)}")
    print(f"Resources with images: {resources_with_images}")
    print(f"Total selected prompts: {total_prompts}")
    print(f"Already cached: {total_prompts - len(all_to_generate)}")
    print(f"Need to generate: {len(all_to_generate)}")

    if not all_to_generate:
        print("\nAll images already cached!")
    else:
        # Show preview
        print("\nTo generate:")
        for i, (h, body) in enumerate(sorted(all_to_generate.items())):
            if i >= 5:
                break
            print(f"  {h[:16]}... {body[:60]}...")
        if len(all_to_generate) > 5:
            print(f"  ... and {len(all_to_generate) - 5} more")

        # Step 3: Generate
        if not parsed_args.yes:
            resp = input(f"\nGenerate {len(all_to_generate)} images? (y/N): ").strip().lower()
            if resp != 'y':
                print("Aborted. Config saved anyway.")
                json.dump(config, open(CONFIG_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                print(f"Config saved to {CONFIG_PATH}")
                return

        print(f"\nGenerating {len(all_to_generate)} images (concurrency={CONCURRENCY})...")
        asyncio.run(generate_batch(all_to_generate))

    # Step 4: Save config
    json.dump(config, open(CONFIG_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nConfig saved to {CONFIG_PATH}")

    # Final stats
    final_cached = get_cached_hashes()
    missing = sum(1 for v in config.values() for h in v if h not in final_cached)
    print(f"Cached: {len(final_cached)} total in DB")
    print(f"Missing from config: {missing}")
    if missing:
        print("WARNING: Some images still missing. Rerun the script to retry.")


if __name__ == "__main__":
    main()
