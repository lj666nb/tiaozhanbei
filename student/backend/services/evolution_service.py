"""智能体自进化服务 — 成功模式提取、检索、进化"""
import json
import re
from datetime import datetime, timedelta
from database import get_db


def extract_pattern(qa_history_id: int) -> int | None:
    """
    从高评分问答中提取成功模式，存入 qa_patterns。
    触发条件：该问答获得 ≥2 个好评。
    返回 pattern_id 或 None。
    """
    conn = get_db()
    # 统计好评数
    good = conn.execute(
        "SELECT COUNT(*) FROM qa_feedback WHERE qa_history_id = ? AND rating = 1",
        (qa_history_id,)
    ).fetchone()[0]
    if good < 2:
        conn.close()
        return None

    # 读取原问答
    qa = conn.execute(
        "SELECT question, answer, knowledge_tags FROM qa_history WHERE id = ?",
        (qa_history_id,)
    ).fetchone()
    if not qa:
        conn.close()
        return None

    question = qa["question"]
    answer = qa["answer"]
    tags = qa["knowledge_tags"]

    # 去重：相似问题已存在则更新
    existing = conn.execute(
        "SELECT id, success_count FROM qa_patterns WHERE question_text = ?",
        (question,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE qa_patterns SET success_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (existing["success_count"] + 1, existing["id"])
        )
        conn.commit()
        conn.close()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO qa_patterns (question_text, answer_text, knowledge_tags, success_count)
           VALUES (?, ?, ?, 1)""",
        (question, answer, tags)
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return pid


def find_similar_patterns(question: str, top_k: int = 3) -> list[dict]:
    """
    基于关键词匹配找到最相似的成功模式。
    返回 [{"question": str, "answer": str, "score": float}, ...]
    """
    conn = get_db()
    all_patterns = conn.execute(
        "SELECT id, question_text, answer_text, knowledge_tags, success_count, usage_count FROM qa_patterns ORDER BY success_count DESC"
    ).fetchall()
    conn.close()

    if not all_patterns:
        return []

    # 将问题分词
    q_words = set(_tokenize(question))

    scored = []
    for p in all_patterns:
        p_words = set(_tokenize(p["question_text"]))
        if not p_words:
            continue
        # Jaccard 相似度
        intersection = q_words & p_words
        union = q_words | p_words
        score = len(intersection) / len(union) if union else 0
        # 加分：知识点标签匹配
        p_tags = set(_parse_tags(p["knowledge_tags"]))
        q_tag_hits = sum(1 for t in q_words if t in str(p_tags))
        score += q_tag_hits * 0.1
        if score > 0.15:
            scored.append({"question": p["question_text"], "answer": p["answer_text"], "score": score, "id": p["id"]})

    scored.sort(key=lambda x: x["score"], reverse=True)

    # 更新使用计数
    if scored:
        conn = get_db()
        for s in scored[:top_k]:
            conn.execute("UPDATE qa_patterns SET usage_count = usage_count + 1 WHERE id = ?", (s["id"],))
        conn.commit()
        conn.close()

    return scored[:top_k]


def evolve() -> dict:
    """
    定期进化：扫描近期高分问答，聚类生成新模式，淘汰过期模式。
    返回进化报告。
    """
    conn = get_db()
    now = datetime.utcnow()
    week_ago = (now - timedelta(days=7)).isoformat()

    # 1. 扫描近期高分问答
    rows = conn.execute("""
        SELECT qh.id, qh.question, qh.answer, qh.knowledge_tags,
               (SELECT COUNT(*) FROM qa_feedback WHERE qa_history_id = qh.id AND rating = 1) as goods
        FROM qa_history qh
        WHERE qh.created_at >= ?
        ORDER BY goods DESC LIMIT 50
    """, (week_ago,)).fetchall()

    new_patterns = 0
    for r in rows:
        if r["goods"] >= 2:
            pid = extract_pattern(r["id"])
            if pid:
                new_patterns += 1

    # 2. 淘汰 30 天未使用且成功率低的旧模式
    month_ago = (now - timedelta(days=30)).isoformat()
    deleted = conn.execute("""
        DELETE FROM qa_patterns
        WHERE updated_at < ? AND usage_count = 0 AND success_count <= 1
    """, (month_ago,)).rowcount

    # 3. 统计总模式数
    total = conn.execute("SELECT COUNT(*) FROM qa_patterns").fetchone()[0]

    conn.commit()
    conn.close()

    return {
        "new_patterns": new_patterns,
        "deleted_patterns": deleted,
        "total_patterns": total,
        "scanned_qa": len(rows),
        "evolved_at": now.isoformat()
    }


def _tokenize(text: str) -> list[str]:
    """简单中文+英文分词"""
    # 提取中文词组（2-4字）
    tokens = []
    # 英文单词
    tokens.extend(re.findall(r'[a-zA-Z_]\w*', text.lower()))
    # 中文词组
    cleaned = re.sub(r'[^一-鿿]', ' ', text)
    for word in cleaned.split():
        if len(word) >= 2:
            tokens.append(word)
            # 2-gram
            for i in range(len(word) - 1):
                tokens.append(word[i:i + 2])
    return tokens


def _parse_tags(tags_str: str) -> list[str]:
    try:
        return json.loads(tags_str) if isinstance(tags_str, str) else tags_str
    except Exception:
        return []
