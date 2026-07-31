"""Shared learning-path context for course guidance and programming assistants."""

from __future__ import annotations

import json
import re
from pathlib import Path

from config import BASE_DIR
from database import get_db, json_load
from services.agent_course import COURSE_TRACKS


MATERIALS_ROOT = Path(BASE_DIR).parent / "learning_materials"
MAX_MATERIAL_CHARS = 6500
MAX_PROJECT_CHARS = 7000


def _course_tasks() -> list[dict]:
    tasks = []
    for track in COURSE_TRACKS:
        for task in track.get("tasks", []):
            tasks.append({"phase": track.get("name", ""), **task})
    return tasks


def _path_snapshot(user_id: int) -> tuple[dict, dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT path_data_json, progress_json FROM learning_paths "
        "WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {}, {}
    try:
        path_data = json_load(row["path_data_json"] or "{}")
        progress = json_load(row["progress_json"] or "{}")
        return path_data if isinstance(path_data, dict) else {}, progress if isinstance(progress, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}, {}


def _path_tasks(path_data: dict) -> list[dict]:
    tasks = []
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            tasks.append({"phase": phase.get("name", ""), **task})
    return tasks


def _select_task(user_id: int, exercise_id: str | None = None) -> tuple[dict | None, dict]:
    path_data, progress = _path_snapshot(user_id)
    path_tasks = _path_tasks(path_data)
    catalog = _course_tasks()

    if exercise_id:
        task = next((item for item in path_tasks if item.get("lab_id") == exercise_id), None)
        task = task or next((item for item in catalog if item.get("lab_id") == exercise_id), None)
        return task, progress

    current_day = int(progress.get("current_day") or 1)
    task = next(
        (item for item in path_tasks if int(item.get("day") or 0) == current_day and not item.get("personalized_review")),
        None,
    )
    task = task or next((item for item in path_tasks if int(item.get("day") or 0) == current_day), None)
    task = task or (path_tasks[0] if path_tasks else None)
    return task, progress


def _material_path(knowledge: str) -> Path | None:
    if not knowledge:
        return None
    index_path = MATERIALS_ROOT / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        relative = index.get("materials", {}).get(knowledge) or index.get(knowledge)
        if relative:
            candidate = (MATERIALS_ROOT / relative).resolve()
            if MATERIALS_ROOT.resolve() in candidate.parents and candidate.is_file():
                return candidate
    except (OSError, TypeError, json.JSONDecodeError):
        pass
    candidate = MATERIALS_ROOT / "Agent工程实战" / f"{knowledge}.md"
    return candidate if candidate.is_file() else None


def _material_excerpt(knowledge: str, question: str) -> tuple[str, str]:
    path = _material_path(knowledge)
    if not path:
        return "", ""
    try:
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S).strip()
    except OSError:
        return "", ""
    if len(text) <= MAX_MATERIAL_CHARS:
        return text, path.stem

    sections = re.split(r"(?=^#{1,3}\s+)", text, flags=re.M)
    terms = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,8}", question.lower()))
    ranked = []
    for index, section in enumerate(sections):
        lower = section.lower()
        score = sum(2 for term in terms if term in lower)
        if any(key in lower for key in ("项目目标", "本节做完", "常见错误", "验收", "动手")):
            score += 3
        ranked.append((score, -index, section))
    chosen = [sections[0]]
    for _, _, section in sorted(ranked, reverse=True):
        if section not in chosen:
            chosen.append(section)
        if sum(len(item) for item in chosen) >= MAX_MATERIAL_CHARS:
            break
    return "\n\n".join(chosen)[:MAX_MATERIAL_CHARS], path.stem


def _task_status(task: dict, progress: dict) -> dict:
    key = f"{task.get('day')}-{task.get('topic')}"
    value = progress.get("completed_tasks", {}).get(key, {})
    return value if isinstance(value, dict) else {}


def _project_snapshot(user_id: int, lab_id: str) -> tuple[str, list[str]]:
    try:
        from services import lab_workspace_service

        root = lab_workspace_service._root(user_id, lab_id)
        files = lab_workspace_service._read_files(root)
    except Exception:
        return "", []
    parts = []
    names = []
    for item in files:
        path = str(item.get("path", ""))
        if not path or not path.endswith((".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml")):
            continue
        names.append(path)
        content = str(item.get("content", ""))[:2200]
        parts.append(f"--- {path} ---\n{content}")
        if sum(len(part) for part in parts) >= MAX_PROJECT_CHARS:
            break
    return "\n\n".join(parts)[:MAX_PROJECT_CHARS], names


def build_learning_context(user_id: int, question: str, exercise_id: str | None = None) -> dict:
    """Build one authoritative context shared by the QA page and lab assistant."""
    task, progress = _select_task(user_id, exercise_id)
    if not task:
        return {
            "available": False,
            "prompt": "当前没有可用的学习路径任务。回答时应说明这一点，并提供通用但准确的建议。",
        }

    lab_id = str(task.get("lab_id") or exercise_id or "")
    material, material_title = _material_excerpt(str(task.get("knowledge") or ""), question)
    project, project_files = _project_snapshot(user_id, lab_id) if lab_id else ("", [])
    status = _task_status(task, progress)
    completed = [label for key, label in (("learn", "教程"), ("quiz", "练习"), ("code", "编程实验")) if status.get(key)]
    pending = [label for label in ("教程", "练习", "编程实验") if label not in completed]

    prompt = f"""【当前学习路径与项目上下文（优先级高于通用建议）】
当前阶段：{task.get('phase') or '项目制 Agent 工程'}
当前任务：第 {task.get('day', '?')} 项 · {task.get('topic', '')}
对应实验：{lab_id or '无'}
课程框架：{task.get('framework', '')}
本节知识：{task.get('knowledge', '')}
本节行动：{task.get('action', '')}
本节交付物：{task.get('deliverable', '')}
本节验收标准：{task.get('check', '')}
完成情况：已完成 {', '.join(completed) or '暂无'}；待完成 {', '.join(pending) or '无'}
项目文件：{', '.join(project_files) or '尚无可读取的文本文件'}

【回答约束】
1. 先直接解决用户问题，再明确它与“当前任务/交付物/验收标准”的关系。
2. 课程资料和实验契约是当前项目的权威依据；不得建议改做与本节目标不同的项目，也不得把后续章节内容冒充当前必做项。
3. 可以补充其他正确方案，但必须标为“扩展方案”，并先给出符合当前课程路线的做法。
4. 涉及代码时优先检查当前项目文件；信息不足要明确说明，不得假装已经看到不存在的文件。
5. 以引导式方式给下一步和验证方法；除非用户明确索要完整答案，否则不要一次替学生完成整个实验。
6. 不得把课程示例中的文件名、函数名、依赖、环境变量或验收标准擅自替换成另一套方案。
"""
    if material:
        prompt += f"\n【当前课程资料：{material_title}】\n{material}\n"
    if project:
        prompt += f"\n【当前实验项目快照】\n{project}\n"

    return {
        "available": True,
        "lab_id": lab_id,
        "day": task.get("day"),
        "phase": task.get("phase", ""),
        "topic": task.get("topic", ""),
        "knowledge": task.get("knowledge", ""),
        "deliverable": task.get("deliverable", ""),
        "check": task.get("check", ""),
        "material": material_title,
        "project_files": project_files,
        "prompt": prompt,
    }


def public_learning_context(context: dict) -> dict:
    """Remove prompt/file contents before sending context metadata to the browser."""
    return {key: value for key, value in context.items() if key != "prompt"}
