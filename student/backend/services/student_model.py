"""学生知识模型服务 — 动态追踪学生知识点掌握度"""
import json
from database import get_db


def update_mastery(user_id: int, knowledge_tag: str, delta: float):
    """
    更新学生对某知识点的掌握度。
    delta: 正数=掌握度上升, 负数=下降, 范围建议 [-0.2, 0.2]
    """
    today = _today()
    conn = get_db()
    row = conn.execute(
        "SELECT id, mastery_detail_json FROM learning_stats WHERE user_id = ? AND date = ?",
        (user_id, today)
    ).fetchone()

    if row:
        mastery = _load_json(row["mastery_detail_json"])
    else:
        mastery = {}
        conn.execute(
            "INSERT INTO learning_stats (user_id, date, mastery_detail_json) VALUES (?, ?, '{}')",
            (user_id, today)
        )

    current = mastery.get(knowledge_tag, 0.5)  # 默认掌握度 0.5
    new_val = max(0.0, min(1.0, current + delta))
    mastery[knowledge_tag] = round(new_val, 3)

    conn.execute(
        "UPDATE learning_stats SET mastery_detail_json = ? WHERE user_id = ? AND date = ?",
        (json.dumps(mastery, ensure_ascii=False), user_id, today)
    )
    conn.commit()
    conn.close()


def get_student_profile(user_id: int) -> dict:
    """
    获取学生完整画像：强项、弱项、学习阶段、总体进度。
    """
    conn = get_db()
    # 最近30天掌握度变化
    rows = conn.execute("""
        SELECT mastery_detail_json FROM learning_stats
        WHERE user_id = ? AND date >= date('now', '-30 days')
        ORDER BY date DESC LIMIT 30
    """, (user_id,)).fetchall()

    user = conn.execute(
        "SELECT nickname, grade, learning_stage FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    # 合并所有掌握度数据
    merged = {}
    for r in rows:
        m = _load_json(r["mastery_detail_json"])
        for tag, val in m.items():
            if tag not in merged:
                merged[tag] = []
            merged[tag].append(val)

    # 计算每个知识点的最新掌握度和趋势
    strengths = []
    weaknesses = []
    for tag, vals in merged.items():
        latest = vals[0] if vals else 0.5
        trend = "上升" if len(vals) >= 2 and vals[0] > vals[-1] else ("下降" if len(vals) >= 2 and vals[0] < vals[-1] else "稳定")
        entry = {"tag": tag, "mastery": round(latest, 2), "trend": trend}
        if latest >= 0.7:
            strengths.append(entry)
        elif latest <= 0.4:
            weaknesses.append(entry)

    strengths.sort(key=lambda x: x["mastery"], reverse=True)
    weaknesses.sort(key=lambda x: x["mastery"])

    return {
        "nickname": user["nickname"] if user else "",
        "grade": user["grade"] if user else "",
        "stage": user["learning_stage"] if user else "入门",
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "total_tags_tracked": len(merged),
    }


def record_qa_activity(user_id: int, knowledge_tags: list[str]):
    """记录问答活动，轻微提升相关知识点掌握度"""
    for tag in (knowledge_tags or []):
        if tag and tag != "综合":
            update_mastery(user_id, tag, 0.02)


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def _load_json(raw) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {}
