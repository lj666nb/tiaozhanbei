"""学情分析服务"""
import json
from datetime import datetime, timedelta
from database import get_db


def _date_prefix(val):
    """从 str 或 datetime 中提取 'YYYY-MM-DD' 前缀（兼容 SQLite TEXT / PG TIMESTAMP）"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10]

def get_user_stats(user_id: int) -> dict:
    """获取用户学习统计数据（从真实数据源查询）"""
    conn = get_db()

    # 学习天数：从 quiz_sessions、learning_records、qa_history 中统计有过活动的日期
    study_dates = set()
    # 测评日期
    for row in conn.execute(
        "SELECT DISTINCT COALESCE(completed_at, created_at) as d FROM quiz_sessions WHERE user_id = ? AND status = 'completed'",
        (user_id,)
    ).fetchall():
        if row["d"]:
            study_dates.add(_date_prefix(row["d"]))
    # 学习记录日期
    for row in conn.execute(
        "SELECT DISTINCT created_at FROM learning_records WHERE user_id = ?", (user_id,)
    ).fetchall():
        if row["created_at"]:
            study_dates.add(_date_prefix(row["created_at"]))
    # 问答日期
    for row in conn.execute(
        "SELECT DISTINCT created_at FROM qa_history WHERE user_id = ?", (user_id,)
    ).fetchall():
        if row["created_at"]:
            study_dates.add(_date_prefix(row["created_at"]))
    study_days = len(study_dates)

    # 做题总数：所有已完成测评的题目数之和
    total_questions = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM quiz_sessions WHERE user_id = ? AND status = 'completed'",
        (user_id,)
    ).fetchone()[0]

    # 平均正确率：所有已完成且非0分的测评
    avg_rate_row = conn.execute(
        "SELECT COALESCE(AVG(score * 100.0 / NULLIF(total, 0)), 0) FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND total > 0",
        (user_id,)
    ).fetchone()
    avg_correct_rate = round(avg_rate_row[0], 1)

    # 测评统计
    quiz_stats = conn.execute(
        "SELECT COUNT(*) as total, COALESCE(AVG(score * 100.0 / NULLIF(total, 0)), 0) as avg FROM quiz_sessions WHERE user_id = ? AND status = 'completed'",
        (user_id,)
    ).fetchone()

    # 错题数
    error_count = conn.execute(
        "SELECT COUNT(*) FROM error_questions WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    # 问答数
    qa_count = conn.execute(
        "SELECT COUNT(*) FROM qa_history WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    # 本周统计（最近7天每天的做题数+正确率）
    week_stats = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_row = conn.execute(
            "SELECT COUNT(*) as exam_set_count, COALESCE(SUM(total), 0) as questions, COALESCE(AVG(score * 100.0 / NULLIF(total, 0)), 0) as rate FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) = ?",
            (user_id, date)
        ).fetchone()
        week_stats.append({
            "date": date,
            "exam_set_count": day_row["exam_set_count"],   # 当天完成测评套数
            "questions": day_row["questions"],              # 当天做题总数量
            "correct_rate": round(day_row["rate"], 1)       # 当天平均正确率
        })

    # 知识点掌握度
    knowledge_mastery = {}
    from services.diagnosis_service import get_user_knowledge_profile
    profile = get_user_knowledge_profile(user_id)
    knowledge_mastery = {k: v for k, v in list(profile.get("mastery", {}).items())[:12]}

    conn.close()

    return {
        "study_days": study_days,
        "total_questions": total_questions,
        "avg_correct_rate": avg_correct_rate,
        "quiz_count": quiz_stats["total"],
        "quiz_avg_score": round(quiz_stats["avg"], 1) if quiz_stats["avg"] else 0,
        "error_count": error_count,
        "qa_count": qa_count,
        "knowledge_mastery": knowledge_mastery,
        "weekly_stats": week_stats,
    }

def get_weekly_report(user_id: int) -> dict:
    """生成周报告"""
    stats = get_user_stats(user_id)
    week_dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    conn = get_db()
    # 本周学习天数：从 quiz_sessions 统计有测评的日期
    study_days = conn.execute(
        "SELECT COUNT(DISTINCT date(COALESCE(completed_at, created_at))) FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) >= ?",
        (user_id, week_dates[0])
    ).fetchone()[0]

    # 本周做题数
    week_questions = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) >= ?",
        (user_id, week_dates[0])
    ).fetchone()[0]

    # 本周错题
    week_errors = conn.execute(
        "SELECT COUNT(*) FROM error_questions WHERE user_id = ? AND created_at >= ?",
        (user_id, week_dates[0])
    ).fetchone()[0]

    # 本周正确率
    week_rate = conn.execute(
        "SELECT COALESCE(AVG(score * 100.0 / NULLIF(total, 0)), 0) FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) >= ? AND total > 0",
        (user_id, week_dates[0])
    ).fetchone()
    conn.close()

    # 趋势判断
    weekly_rates = [d["correct_rate"] for d in stats["weekly_stats"] if d["questions"] > 0]
    trend = "稳定"
    if len(weekly_rates) >= 3:
        recent_avg = sum(weekly_rates[-3:]) / 3
        earlier_avg = sum(weekly_rates[:3]) / 3 if len(weekly_rates) > 3 else recent_avg
        if recent_avg > earlier_avg + 5:
            trend = "上升"
        elif recent_avg < earlier_avg - 5:
            trend = "下降"

    suggestions = []
    if week_questions == 0:
        suggestions.append("本周还没有做题记录，去学习路径做一套练习题吧")
    else:
        suggestions.append(f"本周共完成 {week_questions} 道题，{'表现不错，继续加油！' if (week_rate[0] or 0) >= 60 else '建议重点复习错题本中的薄弱知识点'}")
    suggestions.append("每天安排45-60分钟的专注学习时间效果最佳")
    suggestions.append("定期复习错题本中的题目能有效提高正确率")

    return {
        "period": f"{week_dates[0]} ~ {week_dates[-1]}",
        "study_days": study_days,
        "total_questions": week_questions,
        "avg_correct_rate": round(week_rate[0], 1) if week_rate[0] else 0,
        "new_errors": week_errors,
        "trend": trend,
        "suggestions": suggestions
    }

def get_monthly_report(user_id: int) -> dict:
    """生成月报告"""
    conn = get_db()
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")

    # 本月测评统计
    month_quizzes = conn.execute(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(total), 0) as questions, COALESCE(AVG(score * 100.0 / NULLIF(total, 0)), 0) as avg_rate FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) >= ?",
        (user_id, month_start)
    ).fetchone()

    # 本月学习天数
    month_study_days = conn.execute(
        "SELECT COUNT(DISTINCT date(COALESCE(completed_at, created_at))) FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) >= ?",
        (user_id, month_start)
    ).fetchone()[0]

    # 上月正确率
    last_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
    last_month_rate = conn.execute(
        "SELECT COALESCE(AVG(score * 100.0 / NULLIF(total, 0)), 0) FROM quiz_sessions WHERE user_id = ? AND status = 'completed' AND date(COALESCE(completed_at, created_at)) >= ? AND date(COALESCE(completed_at, created_at)) < ? AND total > 0",
        (user_id, last_month_start, month_start)
    ).fetchone()
    conn.close()

    current_rate = round(month_quizzes["avg_rate"], 1) if month_quizzes["avg_rate"] else 0
    last_rate = round(last_month_rate[0], 1) if last_month_rate[0] else 0
    growth = round(current_rate - last_rate, 1)

    return {
        "period": f"{month_start} ~ {datetime.now().strftime('%Y-%m-%d')}",
        "study_days": month_study_days,
        "total_questions": month_quizzes["questions"] or 0,
        "avg_correct_rate": current_rate,
        "quiz_count": month_quizzes["cnt"] or 0,
        "quiz_avg_score": current_rate,
        "growth": growth,
        "growth_direction": "up" if growth > 0 else "down" if growth < 0 else "stable"
    }

def get_recent_activity(user_id: int, limit: int = 20) -> list:
    """获取用户最近学习动态（跨设备一致，来源于数据库）

    合并三类数据源:
      - quiz_sessions (完成测评) → type: 'exam'
      - qa_history (AI答疑)     → type: 'chat'
      - error_questions (错题复习) → type: 'wrong'
    按时间倒序排列，截取前 limit 条
    """
    conn = get_db()

    activities = []

    # 1. 完成的测评
    for row in conn.execute(
        "SELECT 'exam' as type, "
        "'完成了测评练习' as content, "
        "COALESCE(completed_at, created_at) as create_time "
        "FROM quiz_sessions WHERE user_id = ? AND status = 'completed' "
        "ORDER BY COALESCE(completed_at, created_at) DESC LIMIT ?",
        (user_id, limit)
    ).fetchall():
        activities.append({
            "type": row["type"],
            "content": row["content"],
            "createTime": row["create_time"]
        })

    # 2. AI 答疑历史
    for row in conn.execute(
        "SELECT 'chat' as type, "
        "('进行了AI答疑：' || SUBSTR(question, 1, 30) || CASE WHEN LENGTH(question) > 30 THEN '...' ELSE '' END) as content, "
        "created_at as create_time "
        "FROM qa_history WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall():
        activities.append({
            "type": row["type"],
            "content": row["content"],
            "createTime": row["create_time"]
        })

    # 3. 错题复习
    for row in conn.execute(
        "SELECT 'wrong' as type, "
        "('复习了错题：' || COALESCE(knowledge_tag, '综合') || '') as content, "
        "created_at as create_time "
        "FROM error_questions WHERE user_id = ? AND reviewed = 1 "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall():
        activities.append({
            "type": row["type"],
            "content": row["content"],
            "createTime": row["create_time"]
        })

    conn.close()

    # 按时间倒序，截取前 limit 条
    activities.sort(key=lambda x: x["createTime"] or "", reverse=True)
    return activities[:limit]


def record_learning_activity(user_id: int, knowledge_tag: str, action_type: str,
                             duration: int = 0, result: dict = None):
    """记录学习活动"""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    conn.execute(
        "INSERT INTO learning_records (user_id, knowledge_tag, action_type, duration_seconds, result_json) VALUES (?, ?, ?, ?, ?)",
        (user_id, knowledge_tag, action_type, duration, json.dumps(result or {}, ensure_ascii=False))
    )

    # 更新/插入今日统计
    existing = conn.execute(
        "SELECT * FROM learning_stats WHERE user_id = ? AND date = ?",
        (user_id, today)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE learning_stats SET study_duration = study_duration + ?, questions_done = questions_done + 1 WHERE user_id = ? AND date = ?",
            (duration, user_id, today)
        )
    else:
        conn.execute(
            "INSERT INTO learning_stats (user_id, date, study_duration, questions_done, correct_rate) VALUES (?, ?, ?, ?, ?)",
            (user_id, today, duration, action_type == 'quiz' and 1 or 0, 0)
        )

    conn.commit()
    conn.close()

def get_growth_data(user_id: int) -> dict:
    """获取能力成长轨迹"""
    conn = get_db()
    quizzes = conn.execute(
        "SELECT score, total, completed_at, report_json FROM quiz_sessions WHERE user_id = ? AND status = 'completed' ORDER BY completed_at ASC LIMIT 20",
        (user_id,)
    ).fetchall()
    conn.close()

    growth_points = []
    for q in quizzes:
        rate = q["score"] / q["total"] if q["total"] > 0 else 0
        growth_points.append({
            "date": _date_prefix(q["completed_at"]) or "",
            "score": q["score"],
            "total": q["total"],
            "rate": round(rate * 100, 1)
        })

    return {
        "growth_points": growth_points,
        "trend": "up" if len(growth_points) >= 2 and growth_points[-1]["rate"] > growth_points[0]["rate"] else "stable"
    }
