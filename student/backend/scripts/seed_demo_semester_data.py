"""为演示学生补一学期可解释、可重复执行的学习证据。

所有记录都带 semester_demo_v1 标记。脚本再次运行会直接跳过，不污染真实数据。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database import get_db  # noqa: E402

SOURCE = "semester_demo_v1"
TAGS = [
    "智能体基础概念",
    "提示词工程",
    "Function Calling",
    "智能体记忆",
    "RAG 文档切分",
    "向量检索与重排",
    "PDF 结构解析",
    "Vue 前端实践",
]


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def at(day: date, hour: int = 20) -> str:
    return datetime.combine(day, time(hour, 0)).isoformat()


def seed(username: str) -> dict:
    rng = random.Random(20260726)
    conn = get_db()
    user = conn.execute(
        "SELECT id, username FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not user:
        conn.close()
        raise RuntimeError(f"用户 {username!r} 不存在")
    user_id = int(user["id"])
    marker = conn.execute(
        """SELECT COUNT(*) AS count FROM learning_records
           WHERE user_id = ? AND CAST(result_json AS TEXT) LIKE ?""",
        (user_id, f"%{SOURCE}%"),
    ).fetchone()
    if int(marker["count"] or 0):
        conn.close()
        return {"status": "skipped", "user_id": user_id, "reason": "本学期演示数据已存在"}

    today = date.today()
    semester_start = today - timedelta(weeks=22)
    semester_start -= timedelta(days=semester_start.weekday())
    inserted = {
        "learning_stats": 0,
        "learning_records": 0,
        "quiz_sessions": 0,
        "error_questions": 0,
        "daily_tasks": 0,
        "knowledge_mastery": 0,
        "code_submissions": 0,
        "capability_sessions": 0,
    }
    quiz_ids = []

    for week in range(16):
        week_accuracy = min(0.91, 0.57 + week * 0.021 + rng.uniform(-0.025, 0.025))
        mastery = {}
        for index, tag in enumerate(TAGS):
            mastery[tag] = round(
                max(0.35, min(0.95, week_accuracy - 0.12 + index * 0.012)),
                3,
            )
        for weekday in (0, 1, 3, 5):
            day = semester_start + timedelta(weeks=week, days=weekday)
            duration = rng.randint(32, 78)
            questions = rng.randint(4, 12)
            rate = round(max(0.45, min(0.96, week_accuracy + rng.uniform(-0.07, 0.06))), 3)
            conn.execute(
                """INSERT INTO learning_stats
                   (user_id, date, study_duration, questions_done, correct_rate,
                    knowledge_mastery_json, mastery_detail_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    day.isoformat(),
                    duration,
                    questions,
                    rate,
                    dump({"source": SOURCE, "overall": round(sum(mastery.values()) / len(mastery), 3)}),
                    dump(mastery),
                    at(day),
                ),
            )
            inserted["learning_stats"] += 1
            for action_index in range(rng.randint(2, 4)):
                tag = TAGS[(week + weekday + action_index) % len(TAGS)]
                action_type = ("qa", "practice", "review_error", "code_lab")[
                    (week + action_index) % 4
                ]
                conn.execute(
                    """INSERT INTO learning_records
                       (user_id, knowledge_tag, action_type, duration_seconds, result_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        tag,
                        action_type,
                        rng.randint(480, 1500),
                        dump(
                            {
                                "source": SOURCE,
                                "week": week + 1,
                                "completed": True,
                                "score": round(rate * 100),
                            }
                        ),
                        at(day, 19 + action_index),
                    ),
                )
                inserted["learning_records"] += 1

        if week % 2 == 1:
            day = semester_start + timedelta(weeks=week, days=6)
            percentage = round(max(52, min(94, 59 + week * 1.85 + rng.uniform(-4, 4))), 1)
            total = 20
            correct = round(percentage / 100 * total)
            weak = TAGS[(week + 3) % len(TAGS)]
            strong = TAGS[(week - 1) % len(TAGS)]
            cursor = conn.execute(
                """INSERT INTO quiz_sessions
                   (user_id, stage, questions_json, answers_json, score, total,
                    report_json, status, created_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)""",
                (
                    user_id,
                    "进阶",
                    dump([{"id": i + 1, "source": SOURCE} for i in range(total)]),
                    dump([{"id": i + 1, "correct": i < correct} for i in range(total)]),
                    percentage,
                    total,
                    dump(
                        {
                            "source": SOURCE,
                            "week": week + 1,
                            "correct": correct,
                            "weak_points": [weak],
                            "strong_points": [strong],
                        }
                    ),
                    at(day, 15),
                    at(day, 16),
                ),
            )
            quiz_id = cursor.lastrowid
            if not quiz_id:
                row = conn.execute(
                    """SELECT id FROM quiz_sessions
                       WHERE user_id = ? AND CAST(report_json AS TEXT) LIKE ?
                       ORDER BY id DESC LIMIT 1""",
                    (user_id, f"%\"week\": {week + 1}%"),
                ).fetchone()
                quiz_id = int(row["id"])
            quiz_ids.append(quiz_id)
            inserted["quiz_sessions"] += 1
            for error_index in range(max(1, min(4, total - correct))):
                tag = TAGS[(week + error_index + 3) % len(TAGS)]
                conn.execute(
                    """INSERT INTO error_questions
                       (user_id, session_id, question_data, user_answer, correct_answer,
                        error_type, knowledge_tag, reviewed, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        quiz_id,
                        dump(
                            {
                                "source": SOURCE,
                                "stem": f"第{week + 1}周 {tag} 场景分析题",
                                "adaptive_hint": f"回到 {tag} 的业务边界再判断",
                            }
                        ),
                        "概念判断不完整",
                        "结合场景约束给出完整推理",
                        "迁移应用不足" if error_index % 2 else "概念边界混淆",
                        tag,
                        1 if week < 8 else 0,
                        at(day, 16),
                    ),
                )
                inserted["error_questions"] += 1

    mastery_targets = {
        "智能体基础概念": (0.89, 92, 87, 88, 12, 1),
        "提示词工程": (0.84, 88, 84, 81, 11, 2),
        "Function Calling": (0.81, 86, 80, 78, 10, 2),
        "智能体记忆": (0.76, 83, 75, 71, 9, 3),
        "RAG 文档切分": (0.61, 76, 59, 52, 12, 6),
        "向量检索与重排": (0.66, 78, 65, 57, 10, 5),
        "PDF 结构解析": (0.58, 72, 55, 49, 13, 7),
        "Vue 前端实践": (0.63, 75, 62, 55, 8, 4),
    }
    for tag, values in mastery_targets.items():
        mastery_score, basic, explanation, transfer, attempts, incorrect = values
        existing = conn.execute(
            "SELECT id FROM knowledge_mastery WHERE user_id = ? AND knowledge_tag = ?",
            (user_id, tag),
        ).fetchone()
        params = (
            SOURCE,
            mastery_score,
            basic,
            explanation,
            transfer,
            attempts,
            incorrect,
            at(today - timedelta(days=2)),
            at(today + timedelta(days=2)),
            datetime.now().isoformat(),
        )
        if existing:
            conn.execute(
                """UPDATE knowledge_mastery SET source_exercise_id = ?, mastery_score = ?,
                   basic_score = ?, explanation_score = ?, transfer_score = ?,
                   attempt_count = ?, incorrect_count = ?, last_activity_at = ?,
                   next_review_at = ?, updated_at = ? WHERE id = ?""",
                (*params, int(existing["id"])),
            )
        else:
            conn.execute(
                """INSERT INTO knowledge_mastery
                   (user_id, knowledge_tag, source_exercise_id, mastery_score, basic_score,
                    explanation_score, transfer_score, attempt_count, incorrect_count,
                    last_activity_at, next_review_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, tag, *params),
            )
        inserted["knowledge_mastery"] += 1

    for index, tag in enumerate(TAGS[:6]):
        submitted = today - timedelta(days=72 - index * 10)
        score = 61 + index * 5
        conn.execute(
            """INSERT INTO code_submissions
               (user_id, exercise_id, code, passed, total, score, verified, results_json, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                f"{SOURCE}-{index + 1}",
                f"# {SOURCE}\n# {tag} 业务练习\nresult = 'completed'",
                4 + index % 2,
                5,
                score,
                1 if index < 3 else 0,
                dump([{"source": SOURCE, "status": "passed" if score >= 70 else "partial"}]),
                at(submitted),
            ),
        )
        inserted["code_submissions"] += 1

    for index, tag in enumerate(TAGS[:4]):
        completed = today - timedelta(days=58 - index * 14)
        verified = 1 if index < 3 else 0
        conn.execute(
            """INSERT INTO capability_sessions
               (user_id, exercise_id, exercise_title, knowledge_tag, status, original_code,
                ai_usage, code_score, defense_score, repair_score, process_score, total_score,
                verified, report_json, started_at, code_passed_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                f"{SOURCE}-cap-{index + 1}",
                f"{tag}真实业务能力验证",
                tag,
                "verified" if verified else "repair_pending",
                f"# {SOURCE}\nresult = 'business-scenario'",
                "仅用于查阅文档",
                82 + index * 2,
                76 + index * 3,
                72 + index * 2,
                80,
                78 + index * 2,
                verified,
                dump({"source": SOURCE, "evidence": "代码+答辩+故障修复"}),
                at(completed - timedelta(days=1)),
                at(completed - timedelta(hours=12)),
                at(completed) if verified else None,
            ),
        )
        inserted["capability_sessions"] += 1

    for index in range(14):
        day = today - timedelta(days=13 - index)
        tag = TAGS[(index + 4) % len(TAGS)]
        conn.execute(
            """INSERT INTO daily_tasks
               (user_id, task_data_json, completed, date, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                dump(
                    {
                        "source": SOURCE,
                        "title": f"{tag} 自适应强化",
                        "reason": "根据本学期迁移得分和错题频次安排",
                    }
                ),
                1 if index < 11 else 0,
                day.isoformat(),
                at(day, 8),
            ),
        )
        inserted["daily_tasks"] += 1

    conn.commit()
    conn.close()
    return {
        "status": "inserted",
        "source": SOURCE,
        "user_id": user_id,
        "semester_start": semester_start.isoformat(),
        "semester_end": (semester_start + timedelta(weeks=16) - timedelta(days=1)).isoformat(),
        "inserted": inserted,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="demo")
    args = parser.parse_args()
    print(json.dumps(seed(args.username), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
