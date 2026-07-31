"""学情诊断路由"""
import json
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
from schemas import APIResponse, QuizGenerateRequest, QuizSubmitRequest
from services import diagnosis_service

router = APIRouter()

@router.post("/quiz/generate", response_model=APIResponse)
async def generate_quiz(req: QuizGenerateRequest, current_user: dict = Depends(get_current_user)):
    """生成个性化测评题目（从题库中抽题）"""
    result = await diagnosis_service.generate_quiz(
        user_id=current_user["id"],
        stage=req.stage,
        count=req.count,
        focus_knowledge=req.focus_knowledge,
        use_timer=req.use_timer,
        timer_minutes=req.timer_minutes
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return APIResponse(data=result)

@router.post("/quiz/submit", response_model=APIResponse)
async def submit_quiz(req: QuizSubmitRequest, current_user: dict = Depends(get_current_user)):
    """提交测评答案"""
    answers = [{"question_id": a.question_id, "user_answer": a.user_answer} for a in req.answers]
    result = await diagnosis_service.submit_quiz(
        session_id=req.session_id,
        user_id=current_user["id"],
        answers=answers
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # 如果这个session是学习路径的任务练习，记录结果
    _record_task_quiz_result(current_user["id"], req.session_id, result)

    return APIResponse(data=result)


def _record_task_quiz_result(user_id: int, session_id: int, quiz_result: dict) -> None:
    """提交测评后更新学习路径进度。

    兼容 task_quiz_map 两种格式：旧格式存 int(day号)，新格式存 str(task_key)。
    始终遍历 path_data 找到当天所有非复习任务，标记 quiz=True。
    """
    try:
        from services.learning_service import _normalize_progress, _get_task_key, _check_and_advance_day
        from database import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        if not row:
            conn.close()
            print(f"[_record_task_quiz_result] session={session_id} NO_ACTIVE_PATH")
            return

        progress = json.loads(row["progress_json"]) if row["progress_json"] else {}
        progress = _normalize_progress(progress)

        task_quiz_map = progress.get("task_quiz_map", {})
        print(f"[_record_task_quiz_result] session={session_id} task_quiz_map={dict(task_quiz_map)}")
        task_map_value = task_quiz_map.get(str(session_id))
        if task_map_value is None:
            conn.close()
            print(f"[_record_task_quiz_result] session={session_id} NO_TASK_MAP_ENTRY (keys={list(task_quiz_map.keys())})")
            return

        # 从 task_quiz_map 的值中提取 day 号（兼容新旧格式）
        if isinstance(task_map_value, int):
            task_day = task_map_value
        else:
            # 新格式：字符串 "5-某topic"
            parts = str(task_map_value).split("-", 1)
            task_day = int(parts[0]) if parts[0].isdigit() else None

        if task_day is None:
            conn.close()
            return

        # 遍历 path_data 找到当天所有非复习任务，标记 quiz=True
        path_data = json.loads(row["path_data_json"]) if row["path_data_json"] else {}
        completed_tasks = progress["completed_tasks"]
        matched = 0

        for phase in path_data.get("phases", []):
            for task in phase.get("tasks", []):
                if task.get("day") == task_day and not task.get("remedial"):
                    task_key = _get_task_key(task_day, task["topic"])
                    if task_key not in completed_tasks:
                        completed_tasks[task_key] = {"learn": False, "quiz": False, "code": False}
                    completed_tasks[task_key]["quiz"] = True
                    matched += 1

        # 如果上面的循环没匹配到任何任务（path_data 里没有对应 day 的任务），
        # 且 task_map_value 是新格式的字符串，直接用 task_key 兜底
        if matched == 0 and isinstance(task_map_value, str):
            task_key = task_map_value
            if task_key not in completed_tasks:
                completed_tasks[task_key] = {"learn": False, "quiz": False, "code": False}
            completed_tasks[task_key]["quiz"] = True

        # 重新计算整体进度
        total_tasks = sum(len(phase.get("tasks", [])) for phase in path_data.get("phases", []))
        fully_completed = sum(
            1 for k, v in completed_tasks.items()
            if isinstance(v, dict) and v.get("learn") and v.get("quiz") and v.get("code")
        )
        progress["overall_progress"] = round(fully_completed / total_tasks * 100) if total_tasks > 0 else 0
        progress["completed_tasks"] = completed_tasks

        # 正确率<60% → 生成复习任务
        correct_rate = (quiz_result.get("correct_rate", 0) or 0) / 100.0
        error_tags = list(set(
            e.get("knowledge_tag", "") for e in quiz_result.get("error_questions", [])
        ))
        print(f"[_record_task_quiz_result] session={session_id} task_day={task_day} correct_rate={correct_rate} error_tags_count={len(error_tags)}")
        if correct_rate < 0.6 and error_tags:
            # 找到原始任务的知识点（学习资料索引中保证存在）
            original_knowledge = ""
            for phase in path_data.get("phases", []):
                for t in phase.get("tasks", []):
                    if t.get("day") == task_day and not t.get("remedial"):
                        original_knowledge = t.get("knowledge", "")
                        break
                if original_knowledge:
                    break
            # 如果没有找到原始知识点，回退到第一个error tag
            review_knowledge = original_knowledge or error_tags[0]

            print(f"[_record_task_quiz_result] session={session_id} CREATING remedial tasks for day {task_day+1} knowledge={review_knowledge}")
            next_day = task_day + 1
            remedial = progress.get("remedial_tasks", {})
            next_key = str(next_day)
            if next_key not in remedial:
                remedial[next_key] = []
            # 只创建一个复习任务，使用原始任务的知识点（确保学习资料匹配）
            remedial[next_key].append({
                "day": next_day,
                "topic": f"复习：{review_knowledge}",
                "knowledge": review_knowledge,
                "action": f"针对性复习「{review_knowledge}」相关知识点，重做错题并理解错误原因",
                "resource": "错题本 + 学习资料",
                "check": "能独立正确解答该知识点的题目",
                "remedial": True,
                "source_day": task_day,
                "correct_rate": round(correct_rate * 100)
            })
            progress["remedial_tasks"] = remedial

        # 检查是否当天所有任务全部完成，推进 current_day
        _check_and_advance_day(progress, path_data)

        # 清除已处理的 task_quiz_map 映射
        task_quiz_map.pop(str(session_id), None)
        progress["task_quiz_map"] = task_quiz_map

        # 一次性写入所有更新
        conn.execute(
            "UPDATE learning_paths SET progress_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(progress, ensure_ascii=False), __import__('datetime').datetime.now().isoformat(), row["id"])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[_record_task_quiz_result] ERROR: {e}")
        import traceback
        traceback.print_exc()

@router.get("/quiz/history", response_model=APIResponse)
async def get_history(current_user: dict = Depends(get_current_user)):
    """获取测评历史"""
    history = await diagnosis_service.get_diagnosis_history(current_user["id"])
    return APIResponse(data=history)

@router.get("/quiz/report/{session_id}", response_model=APIResponse)
async def get_report(session_id: int, current_user: dict = Depends(get_current_user)):
    """获取测评报告"""
    report = await diagnosis_service.get_report(session_id, current_user["id"])
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return APIResponse(data=report)

@router.get("/bank-stats", response_model=APIResponse)
async def get_bank_stats():
    """获取题库统计信息"""
    from services.question_bank_service import get_bank_stats
    stats = get_bank_stats()
    return APIResponse(data=stats)


@router.get("/profile", response_model=APIResponse)
async def get_knowledge_profile(current_user: dict = Depends(get_current_user)):
    """获取学情画像"""
    profile = diagnosis_service.get_user_knowledge_profile(current_user["id"])
    return APIResponse(data=profile)
