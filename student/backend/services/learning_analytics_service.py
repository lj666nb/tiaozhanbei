"""面向学生个人数据的只读 NL2SQL 与稀疏数据兜底分析。"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from database import get_db
from services.ai_service import call_llm, extract_json_object


ALLOWED_SCHEMAS = {
    "quiz_sessions": "id, user_id, stage, score, total, status, created_at, completed_at",
    "error_questions": "id, user_id, error_type, knowledge_tag, reviewed, created_at",
    "qa_history": "id, user_id, question_type, knowledge_tags, explanation_level, created_at",
    "daily_tasks": "id, user_id, completed, date, created_at",
    "learning_records": "id, user_id, knowledge_tag, action_type, duration_seconds, created_at",
    "learning_stats": "id, user_id, date, study_duration, questions_done, correct_rate, created_at",
    "conversation_sessions": "id, user_id, title, turn_count, created_at, last_active_at",
    "conversation_messages": "id, session_id, user_id, role, knowledge_tags, created_at",
    "knowledge_mastery": (
        "id, user_id, knowledge_tag, mastery_score, basic_score, explanation_score, "
        "transfer_score, attempt_count, incorrect_count, last_activity_at, next_review_at"
    ),
    "code_submissions": "id, user_id, exercise_id, passed, score, verified, submitted_at",
    "capability_sessions": (
        "id, user_id, exercise_id, status, code_score, defense_score, repair_score, "
        "started_at, completed_at, verified"
    ),
}

BLOCKED_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|call|do|"
    r"pragma|attach|detach|vacuum|analyze|execute|prepare|merge)\b",
    re.IGNORECASE,
)


class UnsafeSQL(ValueError):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    if isinstance(value, str):
        return value[:2000]
    return value


def validate_student_sql(sql: str) -> str:
    """把模型 SQL 收窄到单表、单用户、只读 SELECT。"""
    cleaned = re.sub(r"^```(?:sql)?\s*|\s*```$", "", str(sql or "").strip(), flags=re.IGNORECASE)
    cleaned = cleaned.rstrip(";").strip()
    if not cleaned or len(cleaned) > 4000:
        raise UnsafeSQL("SQL 为空或过长")
    if ";" in cleaned or "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise UnsafeSQL("SQL 只能包含一条无注释查询")
    if not re.match(r"^select\b", cleaned, re.IGNORECASE):
        raise UnsafeSQL("只允许 SELECT")
    if BLOCKED_SQL.search(cleaned):
        raise UnsafeSQL("检测到非只读关键字")
    if re.search(r"\b(join|union|intersect|except)\b", cleaned, re.IGNORECASE):
        raise UnsafeSQL("学生分析查询仅允许单表，跨表由服务端聚合")
    if len(re.findall(r"\bfrom\b", cleaned, re.IGNORECASE)) != 1:
        raise UnsafeSQL("仅允许一个数据源")

    table_match = re.search(r"\bfrom\s+([a-zA-Z_][\w]*)", cleaned, re.IGNORECASE)
    if not table_match or table_match.group(1).lower() not in ALLOWED_SCHEMAS:
        raise UnsafeSQL("查询表不在学情分析白名单")
    if re.search(r"\b(pg_|sqlite_|information_schema)", cleaned, re.IGNORECASE):
        raise UnsafeSQL("禁止访问系统表")
    if cleaned.count("?") != 1:
        raise UnsafeSQL("查询必须且只能使用一个当前用户占位符")
    if not re.search(r"\b(?:\w+\.)?user_id\s*=\s*\?", cleaned, re.IGNORECASE):
        raise UnsafeSQL("查询必须按当前 user_id 隔离")
    if re.search(r"\bor\b", cleaned, re.IGNORECASE):
        raise UnsafeSQL("用户隔离条件不允许 OR")

    limit_match = re.search(r"\blimit\s+(\d+)\s*$", cleaned, re.IGNORECASE)
    if limit_match:
        if int(limit_match.group(1)) > 50:
            cleaned = re.sub(r"\blimit\s+\d+\s*$", "LIMIT 50", cleaned, flags=re.IGNORECASE)
    else:
        cleaned += " LIMIT 50"
    return cleaned


async def generate_student_sql(user_id: int, question: str) -> dict[str, str]:
    schema_text = "\n".join(f"- {table}({columns})" for table, columns in ALLOWED_SCHEMAS.items())
    prompt = f"""把学生的自然语言问题转换为一条 SQLite/PostgreSQL 都可执行的只读 SQL。

可用表：
{schema_text}

强制规则：
1. 只查询一个表，不使用 JOIN、UNION、子查询或 CTE。
2. 必须包含 WHERE user_id = ?，问号代表当前登录学生，不能写具体用户编号。
3. 只允许 SELECT；最多返回 50 行；优先用 COUNT/AVG/SUM/GROUP BY 做统计。
4. 数据少时如实返回，不推测不存在的数据。
5. 只输出 JSON：{{"sql":"...","purpose":"这条查询在回答什么"}}。

学生问题：{str(question or "")[:500]}"""
    response = await call_llm(
        user_id,
        [
            {"role": "system", "content": "你是严格的只读 NL2SQL 规划器，只返回 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=700,
    )
    parsed = extract_json_object(response)
    sql = validate_student_sql(parsed.get("sql", ""))
    return {"sql": sql, "purpose": str(parsed.get("purpose") or "")[:300]}


def execute_student_sql(user_id: int, sql: str) -> list[dict[str, Any]]:
    safe_sql = validate_student_sql(sql)
    conn = get_db()
    try:
        rows = conn.execute(safe_sql, (user_id,)).fetchall()
        return [
            {key: _json_value(value) for key, value in dict(row).items()}
            for row in rows[:50]
        ]
    finally:
        conn.close()


def build_learning_snapshot(user_id: int) -> dict[str, Any]:
    """跨表固定聚合。即使测评表为空，也能用学习轨迹和对话数据形成证据。"""
    conn = get_db()
    try:
        counts: dict[str, int] = {}
        for table in ALLOWED_SCHEMAS:
            row = conn.execute(
                f"SELECT COUNT(*) AS count FROM {table} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            counts[table] = int(row["count"] or 0)

        activity = conn.execute(
            """SELECT COUNT(*) AS actions,
                      COALESCE(SUM(duration_seconds), 0) AS duration_seconds,
                      COUNT(DISTINCT knowledge_tag) AS knowledge_areas
               FROM learning_records WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        stats = conn.execute(
            """SELECT COUNT(*) AS active_days,
                      COALESCE(SUM(questions_done), 0) AS questions_done,
                      COALESCE(AVG(correct_rate), 0) AS avg_correct_rate
               FROM learning_stats WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        top_areas = conn.execute(
            """SELECT knowledge_tag, COUNT(*) AS actions,
                      COALESCE(SUM(duration_seconds), 0) AS duration_seconds
               FROM learning_records
               WHERE user_id = ? AND knowledge_tag <> ''
               GROUP BY knowledge_tag
               ORDER BY actions DESC LIMIT 8""",
            (user_id,),
        ).fetchall()
        mastery = conn.execute(
            """SELECT knowledge_tag, mastery_score, basic_score,
                      explanation_score, transfer_score, attempt_count, incorrect_count
               FROM knowledge_mastery
               WHERE user_id = ?
               ORDER BY mastery_score ASC LIMIT 10""",
            (user_id,),
        ).fetchall()
        capability = conn.execute(
            """SELECT exercise_id, status, code_score, defense_score, repair_score,
                      verified, completed_at
               FROM capability_sessions
               WHERE user_id = ?
               ORDER BY started_at DESC LIMIT 10""",
            (user_id,),
        ).fetchall()
        semester_stats = conn.execute(
            """SELECT date, study_duration, questions_done, correct_rate
               FROM learning_stats WHERE user_id = ?
               ORDER BY date ASC LIMIT 200""",
            (user_id,),
        ).fetchall()
        quiz_trend = conn.execute(
            """SELECT score, total, completed_at, report_json
               FROM quiz_sessions
               WHERE user_id = ? AND status = 'completed'
               ORDER BY completed_at ASC LIMIT 30""",
            (user_id,),
        ).fetchall()
        error_areas = conn.execute(
            """SELECT COALESCE(NULLIF(knowledge_tag, ''), '综合') AS knowledge_tag,
                      COUNT(*) AS error_count,
                      SUM(CASE WHEN reviewed = 0 THEN 1 ELSE 0 END) AS unreviewed
               FROM error_questions WHERE user_id = ?
               GROUP BY COALESCE(NULLIF(knowledge_tag, ''), '综合')
               ORDER BY error_count DESC LIMIT 8""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    evidence_count = sum(counts.values())
    if counts["quiz_sessions"] == 0 and counts["knowledge_mastery"] <= 1:
        coverage = "limited"
        coverage_note = "正式测评和掌握度样本偏少；当前结论主要依据学习行为、对话与能力验证，只能作为阶段性观察。"
    elif evidence_count < 30:
        coverage = "partial"
        coverage_note = "已有部分学习证据，但样本仍少，建议继续完成测评和编程能力验证。"
    else:
        coverage = "sufficient"
        coverage_note = "已积累多来源学习证据，可用于趋势分析；仍应避免把相关性解释为因果。"

    stat_rows = [dict(row) for row in semester_stats]
    first_window = stat_rows[: min(12, len(stat_rows))]
    last_window = stat_rows[-min(12, len(stat_rows)) :] if stat_rows else []

    def avg(rows: list[dict], key: str) -> float:
        return round(sum(float(row.get(key) or 0) for row in rows) / max(1, len(rows)), 3)

    accuracy_start = avg(first_window, "correct_rate")
    accuracy_latest = avg(last_window, "correct_rate")
    study_minutes = sum(int(row.get("study_duration") or 0) for row in stat_rows)
    weak = [
        dict(row)
        for row in mastery
        if float(row["mastery_score"] or 0) < 0.7
    ][:4]
    strong = sorted(
        [dict(row) for row in mastery],
        key=lambda row: float(row.get("mastery_score") or 0),
        reverse=True,
    )[:3]
    adaptive_plan = [
        {
            "knowledge_tag": row["knowledge_tag"],
            "priority": "高" if float(row["mastery_score"] or 0) < 0.62 else "中",
            "reason": (
                f"综合掌握度 {round(float(row['mastery_score']) * 100)}%，"
                f"迁移得分 {round(float(row['transfer_score'] or 0))}，"
                f"累计错误 {int(row['incorrect_count'] or 0)} 次"
            ),
            "next_action": (
                "先用一个真实业务案例复述边界，再完成一题变式迁移和一次故障修复"
            ),
        }
        for row in weak
    ]

    return {
        "coverage": coverage,
        "coverage_note": coverage_note,
        "table_counts": counts,
        "activity": {key: _json_value(value) for key, value in dict(activity).items()},
        "learning_stats": {key: _json_value(value) for key, value in dict(stats).items()},
        "top_knowledge_areas": [
            {key: _json_value(value) for key, value in dict(row).items()} for row in top_areas
        ],
        "mastery_evidence": [
            {key: _json_value(value) for key, value in dict(row).items()} for row in mastery
        ],
        "capability_evidence": [
            {key: _json_value(value) for key, value in dict(row).items()} for row in capability
        ],
        "semester_summary": {
            "period": {
                "start": _json_value(stat_rows[0]["date"]) if stat_rows else None,
                "end": _json_value(stat_rows[-1]["date"]) if stat_rows else None,
            },
            "active_days": len(stat_rows),
            "study_minutes": study_minutes,
            "questions_done": sum(int(row.get("questions_done") or 0) for row in stat_rows),
            "accuracy_start": accuracy_start,
            "accuracy_latest": accuracy_latest,
            "accuracy_change_points": round((accuracy_latest - accuracy_start) * 100, 1),
            "quiz_trend": [
                {
                    "score": float(row["score"] or 0),
                    "total": int(row["total"] or 0),
                    "completed_at": _json_value(row["completed_at"]),
                }
                for row in quiz_trend
            ],
            "strong_areas": strong,
            "weak_areas": weak,
            "error_areas": [
                {key: _json_value(value) for key, value in dict(row).items()}
                for row in error_areas
            ],
            "adaptive_plan": adaptive_plan,
        },
    }


async def analyze_learning_data(user_id: int, question: str) -> dict[str, Any]:
    snapshot = build_learning_snapshot(user_id)
    nl2sql: dict[str, Any] = {"status": "fallback", "purpose": "", "rows": []}
    try:
        generated = await generate_student_sql(user_id, question)
        nl2sql = {
            "status": "ok",
            "purpose": generated["purpose"],
            "sql": generated["sql"],
            "rows": execute_student_sql(user_id, generated["sql"]),
        }
    except Exception as exc:
        nl2sql["reason"] = str(exc)[:200]
    return {
        "question": str(question or "")[:500],
        "nl2sql": nl2sql,
        "snapshot": snapshot,
        "guardrails": ["只读查询", "当前用户隔离", "单表白名单", "最多50行", "稀疏数据显式标注"],
    }
