"""伴随式学习服务"""
import json
from datetime import datetime, timedelta
from services.ai_service import call_llm, extract_json_object, LEARNING_PATH_PROMPT
from services.diagnosis_service import get_user_knowledge_profile, get_all_tags_flat, generate_quiz
from services.question_bank_service import KNOWLEDGE_CATEGORY_MAP
from database import get_db, json_load

async def generate_learning_path(user_id: int, goal: str = "", timeline: str = "", learning_depth: str = "标准", diagnostic_session_id: int = None, modules: list = None) -> dict:
    """生成个性化学习路径
    Args:
        diagnostic_session_id: 可选，诊断测试的 session ID。
        modules: 可选，用户选中的模块名列表（如 ["智能体基础通识", "大模型与提示词工程"]）。
                 当提供时，从对应模块知识中直接构建路径，不调用LLM。
    """
    # ===== 模块选择模式：直接从知识结构构建学习路径 =====
    if modules and len(modules) > 0:
        from services.agent_course import TRACK_NAMES, build_course_path

        # 新版项目制课程使用固定依赖顺序与显式实验绑定，不再从知识标签中随机拼装。
        if any(module in TRACK_NAMES for module in modules):
            selected = [name for name in TRACK_NAMES if name in modules]
            if not selected:
                raise ValueError("请选择至少一个 Agent 实战阶段")
            return await _save_learning_path(
                user_id,
                build_course_path(selected, learning_depth),
            )

        import os as _os
        # 模块名 → 分类名映射
        MODULE_CATEGORY_MAP = {
            "智能体基础通识": "智能体基础概念",
            "大模型与提示词工程": ["大模型基座原理", "提示词工程"],
            "智能体四大核心能力模块": ["智能体框架开发", "智能体算法逻辑"],
            "开发框架与工程实践": "智能体框架开发",
            "多智能体系统": "多智能体应用",
            "评估安全与前沿拓展": "智能体算法逻辑",
        }

        from config import KNOWLEDGE_TAGS_PATH
        with open(KNOWLEDGE_TAGS_PATH, 'r', encoding='utf-8') as f:
            all_categories = json.load(f)

        # 收集选中模块对应的分类名
        target_categories = set()
        for mod in modules:
            cats = MODULE_CATEGORY_MAP.get(mod, [])
            if isinstance(cats, str):
                cats = [cats]
            target_categories.update(cats)

        # 从 knowledge_tags.json 中提取对应分类的知识点
        # 预加载学习资料索引，过滤掉无资料的标签
        materials_flat = {}
        materials_index_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
            "learning_materials", "index.json"
        )
        if _os.path.exists(materials_index_path):
            with open(materials_index_path, 'r', encoding='utf-8') as f:
                materials_index = json.load(f)
            for mod_name, items in materials_index.get("modules", {}).items():
                for tag_name, rel_path in items.items():
                    full = _os.path.join(
                        _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                        "learning_materials", rel_path
                    )
                    if _os.path.exists(full):
                        materials_flat[tag_name] = rel_path

        phases = []
        day = 1
        for cat_data in all_categories:
            cat_name = cat_data["category"]
            if cat_name not in target_categories:
                continue
            tags = cat_data.get("tags", [])
            tasks = []
            for tag in tags[:12]:  # 每个分类最多12个任务
                knowledge = tag["name"]
                # 跳过没有对应学习资料的标签
                if knowledge not in materials_flat:
                    continue
                difficulty = tag.get("difficulty", "Lv2中等")
                # 根据难度推荐资源类型
                resource = "学习资源页面" if difficulty == "Lv1入门" else "动手实践" if difficulty == "Lv3高阶" else "理论+习题"
                tasks.append({
                    "day": day,
                    "topic": knowledge,
                    "knowledge": knowledge,
                    "action": f"学习「{knowledge}」核心概念与原理，完成相关练习",
                    "resource": resource,
                    "check": "理解核心定义并能用自己的话复述" if "入门" in difficulty else
                            "能独立解决相关练习题，准确率>70%" if "中等" in difficulty else
                            "能完成综合实践项目，解释底层原理"
                })
                day += 1

            if tasks:
                phases.append({
                    "name": cat_name,
                    "description": f"学习{cat_name}相关的核心知识点",
                    "tasks": tasks
                })

        # 构建完整路径数据
        path_data = {
            "phases": phases,
            "estimated_total_days": day - 1,
            "learning_depth": learning_depth,
            "weekly_goals": [
                "每天投入 45-60 分钟专注学习",
                "学完每个知识点后做 2-3 道练习巩固",
                "每周末花 30 分钟复习本周所学"
            ],
            "key_milestones": [p["name"] for p in phases],
            "tips": "按顺序学习效果最佳。遇到难理解的概念可使用「智能答疑」寻求帮助。",
            "modules_selected": modules
        }

        # 保存学习路径
        return await _save_learning_path(user_id, path_data)

    # ===== LLM生成模式（保留兼容，无模块选择时使用）=====
    profile = get_user_knowledge_profile(user_id)
    all_tags = get_all_tags_flat()

    # 获取用户信息
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    student_profile = {
        "learning_stage": user["learning_stage"] if user else "入门",
        "weak_points": profile["weak_points"],
        "strong_points": profile["strong_points"],
        "mastery": {k: round(v, 2) for k, v in list(profile["mastery"].items())[:10]}
    }

    # 如果有诊断测试结果，计算掌握等级并注入到学生画像中
    diagnostic_info = {}
    if diagnostic_session_id:
        diagnostic_info = _get_diagnostic_result(user_id, diagnostic_session_id)
        student_profile["diagnostic_mastery_level"] = diagnostic_info.get("mastery_level", "有一定基础")
        student_profile["diagnostic_correct_rate"] = diagnostic_info.get("correct_rate", 0)
        student_profile["diagnostic_note"] = diagnostic_info.get("note", "")

    # 构建知识体系描述和依赖链（精简版：只传必要数据）
    import os
    from config import KNOWLEDGE_TAGS_PATH
    with open(KNOWLEDGE_TAGS_PATH, 'r', encoding='utf-8') as f:
        categories = json.load(f)

    # 知识体系：只保留分类名和标签名，去掉冗余字段
    knowledge_system = [
        {"category": c["category"], "tags": [t["name"] for t in c["tags"]]}
        for c in categories
    ]

    # 前置依赖链：精简为一行表达式，去掉冗余文字
    prereq_parts = []
    for c in categories:
        if c.get("prerequisites"):
            for p in c["prerequisites"]:
                prereq_parts.append(f"{p}→{c['category']}")
        for t in c["tags"]:
            if t.get("prerequisites"):
                for p in t["prerequisites"]:
                    prereq_parts.append(f"{p}→{t['name']}")
    prerequisite_chain = "、".join(prereq_parts) if prereq_parts else "无特殊依赖"

    # 转义花括号
    def _escape(s):
        return s.replace('{', '{{').replace('}', '}}')

    student_profile_str = _escape(json.dumps(student_profile, ensure_ascii=False))
    knowledge_system_str = _escape(json.dumps(knowledge_system, ensure_ascii=False))
    prereq_escaped = _escape(prerequisite_chain)

    prompt = LEARNING_PATH_PROMPT.format(
        student_profile=student_profile_str,
        goal=goal or (user["learning_goal"] if user and user["learning_goal"] else "系统掌握AI智能体学科知识"),
        timeline=timeline or "2周",
        learning_depth=learning_depth,
        knowledge_system=knowledge_system_str,
        prerequisite_chain=prereq_escaped
    )

    # 学习路径生成使用更长超时（180s）和更大 max_tokens（容纳长JSON）
    response = await call_llm(user_id, [
        {"role": "system", "content": "你是AI智能体学科的学习规划师，只输出JSON。"},
        {"role": "user", "content": prompt}
    ], temperature=0.7, max_tokens=4096)

    # 检查 LLM 调用是否返回了错误
    if response.startswith("LLM调用异常:") or response.startswith("LLM调用异常："):
        error_detail = response.replace("LLM调用异常:", "").replace("LLM调用异常：", "").strip()
        raise ValueError(f"AI模型调用失败: {error_detail}")

    path_data = extract_json_object(response)

    # 验证 path_data 必须包含 phases，否则说明 LLM 返回了无效内容
    if not path_data.get("phases"):
        raise ValueError(
            "AI模型未能生成有效的学习路径（缺少phases结构）。"
            "请检查：\n"
            "1. API Key 和 Base URL 是否匹配（如 DeepSeek 模型需搭配 DeepSeek 的 API 地址）\n"
            "2. 模型是否可用，API 账户余额是否充足\n"
            "3. 可前往「个人中心 → AI大模型配置」重新配置后重试"
        )

    # 保存学习深度到路径数据
    path_data["learning_depth"] = learning_depth

    # 【修复】后处理：重新分配连续的天数编号，确保LLM生成的任务天数顺序正确
    day_counter = 0
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            day_counter += 1
            task["day"] = day_counter
    # 更新预计总天数
    path_data["estimated_total_days"] = day_counter

    # 保存学习路径
    return await _save_learning_path(user_id, path_data)


async def _save_learning_path(user_id: int, path_data: dict) -> dict:
    """保存学习路径到数据库（公共方法，模块模式和LLM模式共用）"""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM learning_paths WHERE user_id = ? AND status = 'active'",
        (user_id,)
    ).fetchone()

    path_json = json.dumps(path_data, ensure_ascii=False)
    progress_json = json.dumps({"completed_tasks": {}, "overall_progress": 0, "current_day": 1}, ensure_ascii=False)

    if existing:
        conn.execute(
            "UPDATE learning_paths SET path_data_json = ?, updated_at = ? WHERE id = ?",
            (path_json, datetime.now().isoformat(), existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO learning_paths (user_id, path_data_json, progress_json) VALUES (?, ?, ?)",
            (user_id, path_json, progress_json)
        )

    conn.commit()
    conn.close()
    return path_data


def map_goal_to_knowledge_categories(goal: str) -> list:
    """从用户输入的学习目标中提取关键词，映射到知识分类

    Examples:
        "2周学会RAG" → ["智能体框架开发"]
        "掌握多Agent协作" → ["多智能体应用"]
        "学习Transformer和大模型" → ["大模型基座原理"]
    """
    if not goal:
        return []

    # 按优先级排序的关键词（长的优先匹配，避免"大模型"误匹配"模型"）
    keywords_sorted = sorted(KNOWLEDGE_CATEGORY_MAP.keys(), key=len, reverse=True)

    matched_categories = []
    seen_categories = set()

    for keyword in keywords_sorted:
        if keyword.lower() in goal.lower():
            category = KNOWLEDGE_CATEGORY_MAP[keyword]
            if category not in seen_categories:
                matched_categories.append(category)
                seen_categories.add(category)

    # 如果没匹配到任何分类，返回所有分类（让诊断覆盖全面）
    if not matched_categories:
        matched_categories = list(set(KNOWLEDGE_CATEGORY_MAP.values()))

    return matched_categories


def _get_diagnostic_result(user_id: int, session_id: int) -> dict:
    """从诊断测试 session 中计算用户掌握等级

    Returns:
        {"mastery_level": "基础薄弱"|"有一定基础"|"较为熟练",
         "correct_rate": "67%",
         "correct_count": 6, "total_count": 10,
         "note": "..."}
    """
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM quiz_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id)
    ).fetchone()

    if not session:
        conn.close()
        return {"mastery_level": "有一定基础", "correct_rate": "N/A", "note": "未找到诊断记录，使用默认等级"}

    # 解析答题记录
    answers_json = session["answers_json"] if session["answers_json"] else "[]"
    try:
        answers = json_load(answers_json)
    except (json.JSONDecodeError, TypeError):
        answers = []

    total = len(answers)
    if total == 0:
        conn.close()
        return {"mastery_level": "有一定基础", "correct_rate": "N/A", "note": "诊断测试无答题记录"}

    correct = sum(1 for a in answers if a.get("is_correct", False))
    correct_rate = correct / total

    if correct_rate < 0.4:
        mastery_level = "基础薄弱"
        note = "诊断测试正确率较低，该学生对目标知识领域的基础概念掌握不够扎实，建议从基础概念和入门实践开始学习"
    elif correct_rate <= 0.7:
        mastery_level = "有一定基础"
        note = "诊断测试正确率中等，该学生对目标知识领域有一定了解但存在知识盲区，建议理论+实践并重进行系统学习"
    else:
        mastery_level = "较为熟练"
        note = "诊断测试正确率较高，该学生对目标知识领域已有较好的掌握，建议侧重进阶内容、源码分析和实战项目"

    conn.close()

    return {
        "mastery_level": mastery_level,
        "correct_rate": f"{int(correct_rate * 100)}%",
        "correct_count": correct,
        "total_count": total,
        "note": note
    }


async def generate_diagnostic_test(user_id: int, goal: str = "", count: int = 10) -> dict:
    """根据用户的学习目标生成诊断测试卷

    1. 从 goal 中提取知识分类
    2. 从题库中选取相关题目
    3. 创建 quiz session 并返回
    """
    # 映射目标到知识分类
    focus_knowledge = map_goal_to_knowledge_categories(goal)

    # 根据用户掌握程度选择合适难度阶段
    profile = get_user_knowledge_profile(user_id)
    weak_count = len(profile.get("weak_points", []))
    if weak_count >= 3:
        stage = "入门"
    elif weak_count >= 1:
        stage = "进阶"
    else:
        stage = "进阶"  # 默认进阶，有一定区分度

    # 调用 diagnosis_service 生成题目
    result = await generate_quiz(
        user_id=user_id,
        stage=stage,
        count=count,
        focus_knowledge=focus_knowledge if focus_knowledge else None,
        use_timer=False
    )

    # 添加诊断元信息
    result["diagnostic_goal"] = goal
    result["diagnostic_categories"] = focus_knowledge

    return result


async def delete_learning_path(user_id: int) -> dict:
    """删除用户当前的活跃学习路径"""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM learning_paths WHERE user_id = ? AND status = 'active'",
        (user_id,)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return {"deleted": deleted, "message": "学习路径已删除" if deleted else "没有可删除的学习路径"}


async def get_learning_path(user_id: int) -> dict:
    """获取当前学习路径"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()

    if not row:
        return {}

    path_data = json_load(row["path_data_json"]) if row["path_data_json"] else {}
    progress = json_load(row["progress_json"]) if row["progress_json"] else {}

    # 课程方向已从概念题库切换为项目制 Agent 工程。旧任务无法可靠映射到新实验，
    # 因此首次读取时执行一次显式版本迁移，保留路径记录但重置任务进度。
    if path_data.get("curriculum_version") != "agent-project-path-v1":
        from services.agent_course import TRACK_NAMES, build_course_path
        path_data = build_course_path(TRACK_NAMES, path_data.get("learning_depth", "标准"))
        path_data["migrated_from_legacy"] = True
        progress = {
            "completed_tasks": {},
            "overall_progress": 0,
            "current_day": 1,
            "remedial_tasks": {},
        }
        conn_migration = get_db()
        conn_migration.execute(
            "UPDATE learning_paths SET path_data_json = ?, progress_json = ?, updated_at = ? WHERE id = ?",
            (
                json.dumps(path_data, ensure_ascii=False),
                json.dumps(progress, ensure_ascii=False),
                datetime.now().isoformat(),
                row["id"],
            ),
        )
        conn_migration.commit()
        conn_migration.close()

    original_ct = progress.get("completed_tasks", [])
    progress = _normalize_progress(progress)

    # 如果发生了格式迁移（旧列表→新对象），持久化到DB
    if isinstance(original_ct, list) and original_ct:
        conn2 = get_db()
        conn2.execute(
            "UPDATE learning_paths SET progress_json = ? WHERE id = ?",
            (json.dumps(progress, ensure_ascii=False), row["id"])
        )
        conn2.commit()
        conn2.close()

    # 【迁移】修复旧路径中所有任务 day=1 的问题：重新分配连续天数
    # 同时重建 progress 中的 key，确保与新的 day 编号一致
    if path_data.get("phases"):
        all_days = []
        for phase in path_data["phases"]:
            for task in phase.get("tasks", []):
                all_days.append(task.get("day", 1))
        # 如果路径有多个任务且全部 day 都是 1，则需要修复
        if len(all_days) > 1 and all(d == 1 for d in all_days):
            # Step 1: 建立 topic → new_day 映射
            topic_to_new_day = {}
            day_counter = 0
            for phase in path_data["phases"]:
                for task in phase.get("tasks", []):
                    day_counter += 1
                    task["day"] = day_counter
                    topic_to_new_day[task["topic"]] = day_counter
            path_data["estimated_total_days"] = day_counter

            # Step 2: 重建 progress 中的 completed_tasks key
            # 旧 key 格式 "1-{topic}" → 新 key "{new_day}-{topic}"
            ct = progress.get("completed_tasks", {})
            if isinstance(ct, dict) and ct:
                new_ct = {}
                for old_key, val in ct.items():
                    # 旧 key 格式: "1-{topic}"，提取 topic 部分
                    parts = old_key.split("-", 1)
                    topic = parts[1] if len(parts) > 1 else old_key
                    new_day = topic_to_new_day.get(topic, 1)
                    new_key = _get_task_key(new_day, topic)
                    new_ct[new_key] = val
                progress["completed_tasks"] = new_ct

            # Step 3: 持久化修复后的路径数据和进度
            conn_mig = get_db()
            conn_mig.execute(
                "UPDATE learning_paths SET path_data_json = ?, progress_json = ? WHERE id = ?",
                (json.dumps(path_data, ensure_ascii=False),
                 json.dumps(progress, ensure_ascii=False),
                 row["id"])
            )
            conn_mig.commit()
            conn_mig.close()

    # 将复习任务注入到对应 day 的任务列表前面
    remedial = progress.get("remedial_tasks", {})
    remedial_modified = False
    if remedial and path_data.get("phases"):
        for phase in path_data["phases"]:
            for task in phase.get("tasks", []):
                day = task.get("day", 0)
                day_key = str(day)
                if day_key in remedial and remedial[day_key]:
                    # 在 phase 的 tasks 中，在该 day 原有任务前面插入复习任务
                    # 找到该 day 的第一个 task 位置
                    insert_positions = {}
                    for i, t in enumerate(phase["tasks"]):
                        d = t.get("day", 0)
                        if d not in insert_positions:
                            insert_positions[d] = i
                    if day in insert_positions:
                        insert_at = insert_positions[day]
                        for r_task in reversed(remedial[day_key]):
                            phase["tasks"].insert(insert_at, r_task)
                    del remedial[day_key]  # 已注入，清除
                    remedial_modified = True
        if remedial_modified:
            progress["remedial_tasks"] = remedial
            # 持久化：同时保存修改后的 path_data（含已注入的复习任务）和 progress，
            # 避免刷新页面后复习任务消失
            conn3 = get_db()
            conn3.execute(
                "UPDATE learning_paths SET path_data_json = ?, progress_json = ? WHERE id = ?",
                (json.dumps(path_data, ensure_ascii=False),
                 json.dumps(progress, ensure_ascii=False),
                 row["id"])
            )
            conn3.commit()
            conn3.close()

    # 第二天起，根据编程实验的基本测试/用户解释/变式迁移证据，虚拟追加第 5 阶段。
    # 该阶段每次读取时动态生成，不写回基础课程，避免重复插入。
    try:
        from services.personalization_service import get_due_review_recommendations

        recommendations = get_due_review_recommendations(user_id)
        if recommendations:
            task_by_lab = {}
            for phase in path_data.get("phases", []):
                for task in phase.get("tasks", []):
                    if task.get("lab_id"):
                        task_by_lab[task["lab_id"]] = task
            review_tasks = []
            review_notices = []
            for item in recommendations:
                source = task_by_lab.get(item.get("source_exercise_id"))
                if not source:
                    continue
                mastery_percent = round(float(item.get("mastery_score", 0)) * 100)
                review_task = dict(source)
                review_task.update({
                    "topic": f"个性化复习：{item['knowledge_tag']}",
                    "knowledge": source.get("knowledge") or item["knowledge_tag"],
                    "action": f"系统检测到你对「{item['knowledge_tag']}」的熟悉程度较低，建议返回编程实验重点复习。",
                    "check": "重新通过基本测试、用自己的话解释关键实现，并完成变式迁移",
                    "personalized_review": True,
                    "mastery_score": item["mastery_score"],
                    "basic_score": item["basic_score"],
                    "explanation_score": item["explanation_score"],
                    "transfer_score": item["transfer_score"],
                    "source_topic": source.get("topic"),
                })
                review_tasks.append(review_task)
                review_notices.append({
                    "knowledge_tag": item["knowledge_tag"],
                    "mastery_percent": mastery_percent,
                    "lab_id": source.get("lab_id"),
                    "module_id": source.get("module_id"),
                    "topic": source.get("topic"),
                })
            if review_tasks:
                path_data["phases"].append({
                    "name": "个性化复习路径",
                    "description": "根据昨天及更早的实验能力证据动态生成",
                    "personalized_review": True,
                    "tasks": review_tasks,
                })
                path_data["personalized_review"] = {
                    "title": f"检测到 {len(review_tasks)} 个知识点需要返工",
                    "message": f"系统检测到你对「{review_tasks[0]['knowledge']}」的熟悉程度较低，建议先复习昨天的编程部分。",
                    "items": review_notices,
                }
    except Exception:
        pass

    return {
        "id": row["id"],
        "path_data": path_data,
        "progress": progress,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

def _normalize_progress(progress: dict) -> dict:
    """将旧版 completed_tasks 列表格式迁移为新的对象格式"""
    ct = progress.get("completed_tasks", [])
    if isinstance(ct, list):
        # 旧格式是简单列表，迁移时只标记learn为True（旧系统中"完成"主要指已学习）
        # quiz和code默认False，避免误标记
        new_ct = {}
        for item in ct:
            new_ct[item] = {"learn": True, "quiz": False, "code": False}
        progress["completed_tasks"] = new_ct
    # 确保每个任务值都是完整的字典，缺失子项默认False
    for key, val in list(progress.get("completed_tasks", {}).items()):
        if not isinstance(val, dict):
            progress["completed_tasks"][key] = {"learn": False, "quiz": False, "code": False}
        else:
            for sub in ["learn", "quiz", "code"]:
                if sub not in val:
                    val[sub] = False
    # 确保其他字段存在
    if "overall_progress" not in progress:
        progress["overall_progress"] = 0
    if "current_day" not in progress:
        progress["current_day"] = 1
    if "remedial_tasks" not in progress:
        progress["remedial_tasks"] = {}
    return progress


def _get_task_key(day: int, topic: str) -> str:
    return f"{day}-{topic}"


def _is_task_fully_complete(task_status: dict) -> bool:
    """检查任务是否三个子项全部完成"""
    return task_status.get("learn", False) and task_status.get("quiz", False) and task_status.get("code", False)


def _count_completed_sub_tasks(task_status: dict) -> int:
    """统计已完成的子任务数"""
    return sum(1 for k in ["learn", "quiz", "code"] if task_status.get(k, False))


def _check_and_advance_day(progress: dict, path_data: dict) -> bool:
    """检查当前 day 的所有任务是否全部完成，若是则推进 current_day"""
    current_day = progress.get("current_day", 1)
    completed_tasks = progress.get("completed_tasks", {})

    day_task_keys = []
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == current_day:
                day_task_keys.append(_get_task_key(task["day"], task["topic"]))

    if day_task_keys and all(
        _is_task_fully_complete(completed_tasks.get(k, {})) for k in day_task_keys
    ):
        progress["current_day"] = current_day + 1
        return True
    return False


async def update_path_progress(user_id: int, task_key: str, completed: bool = True,
                                sub_action: str = None) -> dict:
    """更新学习路径进度

    Args:
        task_key: "{day}-{topic}"
        completed: True/False
        sub_action: "learn" | "quiz" | "code" | None (None=全标记)
    """
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return {"error": "没有活跃的学习路径"}

    progress = json_load(row["progress_json"]) if row["progress_json"] else {"completed_tasks": [], "overall_progress": 0, "current_day": 1, "remedial_tasks": {}}
    progress = _normalize_progress(progress)
    completed_tasks = progress["completed_tasks"]

    # 初始化任务状态
    if task_key not in completed_tasks:
        completed_tasks[task_key] = {"learn": False, "quiz": False, "code": False}

    task_status = completed_tasks[task_key]

    if sub_action:
        # 更新指定子动作
        task_status[sub_action] = completed
    else:
        # 兼容旧接口：全标记
        task_status["learn"] = completed
        task_status["quiz"] = completed
        task_status["code"] = completed

    # 计算整体进度
    path_data = json_load(row["path_data_json"]) if row["path_data_json"] else {}
    total_tasks = 0
    completed_count = 0
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            total_tasks += 1
            key = _get_task_key(task.get("day", 0), task.get("topic", ""))
            if _is_task_fully_complete(completed_tasks.get(key, {})):
                completed_count += 1

    progress["overall_progress"] = round(completed_count / total_tasks * 100) if total_tasks > 0 else 0
    progress["completed_tasks"] = completed_tasks

    # 检查是否当天所有任务全部完成，推进 current_day
    _check_and_advance_day(progress, path_data)

    conn.execute(
        "UPDATE learning_paths SET progress_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(progress, ensure_ascii=False), datetime.now().isoformat(), row["id"])
    )
    conn.commit()
    conn.close()

    return progress


async def record_quiz_result(user_id: int, task_day: int, correct_rate: float,
                              error_knowledge_tags: list = None) -> dict:
    """记录做题结果：正确率<60%时自动为下一天生成复习任务"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return {"error": "没有活跃的学习路径"}

    progress = json_load(row["progress_json"]) if row["progress_json"] else {}
    progress = _normalize_progress(progress)

    # 标记 quiz 子任务完成
    path_data = json_load(row["path_data_json"]) if row["path_data_json"] else {}
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == task_day:
                task_key = _get_task_key(task_day, task["topic"])
                if task_key not in progress["completed_tasks"]:
                    progress["completed_tasks"][task_key] = {"learn": False, "quiz": False, "code": False}
                progress["completed_tasks"][task_key]["quiz"] = True

    # 正确率<60% → 生成复习任务，插入到 day+1
    if correct_rate < 0.6 and error_knowledge_tags:
        # 找到原始任务的知识点（学习资料索引中保证存在）
        original_knowledge = ""
        for phase in path_data.get("phases", []):
            for t in phase.get("tasks", []):
                if t.get("day") == task_day and not t.get("remedial"):
                    original_knowledge = t.get("knowledge", "")
                    break
            if original_knowledge:
                break
        review_knowledge = original_knowledge or error_knowledge_tags[0]

        next_day = task_day + 1
        remedial = progress.get("remedial_tasks", {})
        next_key = str(next_day)
        if next_key not in remedial:
            remedial[next_key] = []
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

    conn.execute(
        "UPDATE learning_paths SET progress_json = ? WHERE id = ?",
        (json.dumps(progress, ensure_ascii=False), row["id"])
    )
    conn.commit()
    conn.close()

    return progress


async def record_code_completion(user_id: int, task_day: int) -> dict:
    """记录代码练习完成"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return {"error": "没有活跃的学习路径"}

    progress = json_load(row["progress_json"]) if row["progress_json"] else {}
    progress = _normalize_progress(progress)

    path_data = json_load(row["path_data_json"]) if row["path_data_json"] else {}
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == task_day:
                task_key = _get_task_key(task_day, task["topic"])
                if task_key not in progress["completed_tasks"]:
                    progress["completed_tasks"][task_key] = {"learn": False, "quiz": False, "code": False}
                progress["completed_tasks"][task_key]["code"] = True

    # 检查是否当天所有任务全部完成，推进 current_day
    _check_and_advance_day(progress, path_data)

    conn.execute(
        "UPDATE learning_paths SET progress_json = ? WHERE id = ?",
        (json.dumps(progress, ensure_ascii=False), row["id"])
    )
    conn.commit()
    conn.close()

    return progress

async def get_daily_tasks(user_id: int, date: str = None) -> dict:
    """获取每日任务"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM daily_tasks WHERE user_id = ? AND date = ?",
        (user_id, date)
    ).fetchone()

    if not row:
        # 自动生成每日任务
        path = await get_learning_path(user_id)
        task_data = await generate_daily_tasks(user_id, path, date)
        conn.close()
        return {
            "id": None,
            "date": date,
            "tasks": task_data.get("tasks", []),
            "study_tips": task_data.get("study_tips", ""),
            "completed": False
        }

    conn.close()
    task_data = json_load(row["task_data_json"]) if row["task_data_json"] else {}
    return {
        "id": row["id"],
        "date": date,
        "tasks": task_data.get("tasks", []),
        "study_tips": task_data.get("study_tips", ""),
        "completed": bool(row["completed"])
    }

async def generate_daily_tasks(user_id: int, path: dict, date: str) -> dict:
    """生成每日任务"""
    path_data = path.get("path_data", {})
    progress = path.get("progress", {})
    completed_tasks = progress.get("completed_tasks", [])
    current_day = progress.get("current_day", 1)

    # 寻找当前日期的任务
    daily_tasks_data = []
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == current_day:
                daily_tasks_data.append(task)

    if not daily_tasks_data:
        daily_tasks_data = [
            {"topic": "复习已学知识点", "knowledge": "综合复习", "action": "回顾本周错题和笔记", "resource": "错题本", "check": "完成错题回顾"},
            {"topic": "AI智能体概念巩固", "knowledge": "智能体基础概念", "action": "阅读教材相关内容，做好笔记", "resource": "教材/课件", "check": "能用自己的话解释核心概念"},
            {"topic": "每日一练", "knowledge": "综合练习", "action": "完成3-5道练习题", "resource": "在线题库", "check": "正确率>60%"}
        ]

    task_data = {
        "date": date,
        "tasks": daily_tasks_data,
        "study_tips": "每天保持专注学习30分钟以上，及时记录疑问便于答疑"
    }

    # 保存
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO daily_tasks (user_id, task_data_json, completed, date) VALUES (?, ?, 0, ?)",
        (user_id, json.dumps(task_data, ensure_ascii=False), date)
    )
    conn.commit()
    conn.close()

    return task_data

async def update_daily_task(user_id: int, date: str, completed: int = 1) -> dict:
    """更新每日任务完成状态，并同步到学习路径"""
    conn = get_db()
    conn.execute(
        "UPDATE daily_tasks SET completed = ? WHERE user_id = ? AND date = ?",
        (completed, user_id, date)
    )
    conn.commit()

    # 记录学习时长 + 推进学习天数
    if completed:
        existing = conn.execute(
            "SELECT * FROM learning_stats WHERE user_id = ? AND date = ?",
            (user_id, date)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE learning_stats SET study_duration = study_duration + 30 WHERE user_id = ? AND date = ?",
                (user_id, date)
            )
        else:
            conn.execute(
                "INSERT INTO learning_stats (user_id, date, study_duration, questions_done, correct_rate, knowledge_mastery_json) VALUES (?, ?, 30, 0, 0, '{}')",
                (user_id, date)
            )
        conn.commit()

        # 同步：将当前 day 的所有路径任务标记为完成
        path_row = conn.execute(
            "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        if path_row:
            progress = json_load(path_row["progress_json"]) if path_row["progress_json"] else {}
            progress = _normalize_progress(progress)
            completed_tasks = progress.get("completed_tasks", {})
            current_day = progress.get("current_day", 1)

            path_data = json_load(path_row["path_data_json"]) if path_row["path_data_json"] else {}
            total_tasks = 0
            for phase in path_data.get("phases", []):
                total_tasks += len(phase.get("tasks", []))

            # 将当前 day 的所有任务标记为完成（全部三个子任务）
            for phase in path_data.get("phases", []):
                for task in phase.get("tasks", []):
                    if task.get("day") == current_day:
                        task_key = f"{task['day']}-{task['topic']}"
                        if task_key not in completed_tasks:
                            completed_tasks[task_key] = {"learn": False, "quiz": False, "code": False}
                        completed_tasks[task_key] = {"learn": True, "quiz": True, "code": True}

            progress["completed_tasks"] = completed_tasks
            fully_completed = sum(1 for k in completed_tasks if _is_task_fully_complete(completed_tasks[k]))
            progress["overall_progress"] = round(fully_completed / total_tasks * 100) if total_tasks > 0 else 0

            conn.execute(
                "UPDATE learning_paths SET progress_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(progress, ensure_ascii=False), datetime.now().isoformat(), path_row["id"])
            )
            conn.commit()

    conn.close()

    if completed:
        advanced = await _advance_learning_day(user_id)
        if advanced:
            # 天数推进了才删除旧任务，下次获取重新生成
            conn = get_db()
            conn.execute("DELETE FROM daily_tasks WHERE user_id = ? AND date = ?", (user_id, date))
            conn.commit()
            conn.close()

    return {"message": "任务状态已更新"}


async def _advance_learning_day(user_id: int) -> bool:
    """完成今日任务后推进学习路径的 current_day，返回是否实际推进"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    progress = json_load(row["progress_json"]) if row["progress_json"] else {}
    progress = _normalize_progress(progress)
    current_day = progress.get("current_day", 1)

    path_data = json_load(row["path_data_json"]) if row["path_data_json"] else {}
    completed_tasks = progress.get("completed_tasks", {})
    day_tasks = []
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == current_day:
                day_tasks.append(_get_task_key(task["day"], task["topic"]))

    # 使用 _is_task_fully_complete 检查所有子任务是否完成（而非仅检查key存在）
    all_done = all(_is_task_fully_complete(completed_tasks.get(t, {})) for t in day_tasks) if day_tasks else True

    if all_done:
        progress["current_day"] = current_day + 1
        conn.execute(
            "UPDATE learning_paths SET progress_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(progress, ensure_ascii=False), datetime.now().isoformat(), row["id"])
        )
        conn.commit()
        conn.close()
        return True

    conn.commit()
    conn.close()
    return False

async def get_error_book(user_id: int, page: int = 1, page_size: int = 20) -> dict:
    """获取错题本"""
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM error_questions WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        "SELECT * FROM error_questions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, page_size, offset)
    ).fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        qd = d.get("question_data", "{}")
        if isinstance(qd, str):
            try:
                d["question_data"] = json_load(qd)
            except (json.JSONDecodeError, TypeError):
                d["question_data"] = {"question": qd[:200], "analysis": ""}
        elif isinstance(qd, dict):
            d["question_data"] = qd
        else:
            d["question_data"] = {}
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

async def get_error_sessions(user_id: int) -> list:
    """获取错题按测评会话分组"""
    conn = get_db()
    # 有 session_id 的按 session 分组
    rows = conn.execute("""
        SELECT e.session_id, COUNT(*) as error_count,
               SUM(CASE WHEN e.reviewed = 1 THEN 1 ELSE 0 END) as reviewed_count,
               qs.stage, qs.score, qs.total,
               COALESCE(qs.completed_at, qs.created_at) as quiz_time
        FROM error_questions e
        LEFT JOIN quiz_sessions qs ON e.session_id = qs.id
        WHERE e.user_id = ?
        GROUP BY e.session_id, qs.stage, qs.score, qs.total, qs.completed_at, qs.created_at
        ORDER BY quiz_time DESC
    """, (user_id,)).fetchall()

    sessions = []
    for r in rows:
        stage = r["stage"] or "未知"
        score = r["score"] or 0
        total = r["total"] or 0
        quiz_time = r["quiz_time"] or ""
        # 统一处理 datetime 对象（PG）和字符串（SQLite）两种格式
        if quiz_time:
            if isinstance(quiz_time, datetime):
                display_time = quiz_time.strftime("%Y-%m-%d %H:%M")
            else:
                # '2026-06-06 09:53:39' 或 '2026-06-06T17:54:31.951562'
                display_time = quiz_time.replace("T", " ")[:16]
        else:
            display_time = ""
        sessions.append({
            "session_id": r["session_id"],
            "label": f"{stage}测评 ({score}/{total}分)" if quiz_time else "历史错题",
            "error_count": r["error_count"],
            "reviewed_count": r["reviewed_count"] or 0,
            "quiz_time": display_time,
            "stage": stage,
            "score": score,
            "total": total,
        })

    conn.close()
    return sessions


async def get_errors_by_session(user_id: int, session_id: int = None, page: int = 1, page_size: int = 50) -> dict:
    """获取指定会话的错题"""
    conn = get_db()
    if session_id is not None:
        total = conn.execute(
            "SELECT COUNT(*) FROM error_questions WHERE user_id = ? AND session_id = ?",
            (user_id, session_id)
        ).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM error_questions WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, session_id, page_size, offset)
        ).fetchall()
    else:
        total = conn.execute(
            "SELECT COUNT(*) FROM error_questions WHERE user_id = ? AND session_id IS NULL",
            (user_id,)
        ).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM error_questions WHERE user_id = ? AND session_id IS NULL ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, page_size, offset)
        ).fetchall()

    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        qd = d.get("question_data", "{}")
        if isinstance(qd, str):
            try:
                d["question_data"] = json_load(qd)
            except (json.JSONDecodeError, TypeError):
                d["question_data"] = {"question": qd[:200], "analysis": ""}
        elif isinstance(qd, dict):
            d["question_data"] = qd
        else:
            d["question_data"] = {}
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size)
    }


async def delete_errors_by_session(user_id: int, session_id: int = None) -> dict:
    """删除指定会话的所有错题"""
    conn = get_db()
    if session_id is not None:
        count = conn.execute(
            "SELECT COUNT(*) FROM error_questions WHERE user_id = ? AND session_id = ?",
            (user_id, session_id)
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM error_questions WHERE user_id = ? AND session_id = ?",
            (user_id, session_id)
        )
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM error_questions WHERE user_id = ? AND session_id IS NULL",
            (user_id,)
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM error_questions WHERE user_id = ? AND session_id IS NULL",
            (user_id,)
        )
    conn.commit()
    conn.close()
    return {"deleted": count}


async def batch_delete_errors(user_id: int, error_ids: list[int]) -> dict:
    """批量删除错题（保留兼容）"""
    conn = get_db()
    deleted = 0
    for eid in error_ids:
        row = conn.execute(
            "SELECT id FROM error_questions WHERE id = ? AND user_id = ?",
            (eid, user_id)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM error_questions WHERE id = ?", (eid,))
            deleted += 1
    conn.commit()
    conn.close()
    return {"deleted": deleted, "total": len(error_ids)}

def map_task_knowledge_to_categories(knowledge_text: str) -> list:
    """将任务知识点文本映射到题库分类（长关键词优先匹配，精准聚焦）"""
    from services.question_bank_service import KNOWLEDGE_CATEGORY_MAP
    from collections import Counter

    if not knowledge_text:
        return ["智能体基础概念"]

    # 按关键词长度降序匹配（"多智能体应用" > "智能体"），累加权重
    sorted_keywords = sorted(KNOWLEDGE_CATEGORY_MAP.keys(), key=len, reverse=True)
    category_scores = Counter()
    for keyword in sorted_keywords:
        if keyword in knowledge_text:
            category_scores[KNOWLEDGE_CATEGORY_MAP[keyword]] += len(keyword)

    if category_scores:
        # 只返回得分最高的 1-2 个分类，保证精准
        top = category_scores.most_common(2)
        return [cat for cat, _ in top]

    # 完全无匹配时，返回最通用的分类（而非全部6个）
    return ["智能体基础概念"]


async def generate_task_quiz(user_id: int, task_day: int, count: int = 10) -> dict:
    """为学习路径中指定天数的任务生成专项练习题"""
    # 1. 获取用户的学习路径
    path = await get_learning_path(user_id)
    if not path or not path.get("path_data"):
        return {"error": "没有找到学习路径，请先生成学习路径"}

    path_data = path["path_data"]

    # 2. 查找指定天数的任务（跳过复习任务）
    target_task = None
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == task_day and not task.get("remedial"):
                target_task = task
                break
        if target_task:
            break

    if not target_task:
        return {"error": f"未找到第{task_day}天的任务"}

    # 3. 任务知识点 → 题库分类 + 所属模块
    import os as _os
    knowledge_text = target_task.get("knowledge", "")

    # 先通过 knowledge_tags.json 精确查找知识点所属的分类
    from config import KNOWLEDGE_TAGS_PATH as _KT_PATH
    CATEGORY_TO_MODULE = {
        "智能体基础概念": "智能体基础通识",
        "大模型基座原理": "大模型与提示词工程",
        "提示词工程": "大模型与提示词工程",
        "智能体框架开发": "智能体四大核心能力模块",
        "智能体算法逻辑": "智能体四大核心能力模块",
        "多智能体应用": "多智能体系统",
    }

    exact_category = None
    if _os.path.exists(_KT_PATH):
        with open(_KT_PATH, 'r', encoding='utf-8') as f:
            kt_data = json.load(f)
        for cat_data in kt_data:
            for tag in cat_data.get("tags", []):
                if tag["name"] == knowledge_text:
                    exact_category = cat_data["category"]
                    break
            if exact_category:
                break

    # 精确匹配到分类就用精确分类，否则回退到关键词匹配
    if exact_category:
        focus_categories = [exact_category]
        task_module = CATEGORY_TO_MODULE.get(exact_category)
    else:
        focus_categories = map_task_knowledge_to_categories(knowledge_text)
        task_module = None
        for cat in focus_categories:
            mod = CATEGORY_TO_MODULE.get(cat)
            if mod:
                task_module = mod
                break

    # focus_knowledge: 模块名（触发模块级过滤）+ 分类名（触发知识点级过滤）
    combined_focus = []
    if task_module:
        combined_focus.append(task_module)
    combined_focus.extend(focus_categories)

    # 4. 根据学习深度确定出题难度阶段
    depth = path_data.get("learning_depth", "标准")
    depth_stage_map = {"基础": "入门", "标准": "进阶", "深入": "高阶"}
    stage = depth_stage_map.get(depth, "进阶")

    # 5. 加载已出过的题目（跨任务去重）
    used_questions = set()
    conn0 = get_db()
    row0 = conn0.execute(
        "SELECT progress_json FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    if row0 and row0["progress_json"]:
        try:
            prog = json_load(row0["progress_json"])
            used_questions = set(prog.get("used_question_texts", []))
        except:
            pass
    conn0.close()

    # 6. 调用诊断服务生成题目（传入knowledge_filter + exclude_ids）
    from services.diagnosis_service import generate_quiz
    result = await generate_quiz(
        user_id=user_id,
        stage=stage,
        count=count,
        focus_knowledge=combined_focus,
        knowledge_filter=knowledge_text,
        exclude_ids=used_questions,
        use_timer=False,
        timer_minutes=0
    )

    # 7. 将新出的题目加入已用集合
    new_texts = [q.get("question", "") for q in result.get("questions", [])]
    used_questions.update(new_texts)
    # 限制集合大小（保留最近500道）
    if len(used_questions) > 500:
        used_questions = set(list(used_questions)[-500:])

    # 8. 保存 task_quiz_map + used_question_texts, 用于后续自动记录
    #    直接存 task_key（"{day}-{topic}"），避免 submit 时再到 path_data 里查找匹配
    session_id = result.get("session_id")
    if session_id:
        task_key = _get_task_key(task_day, target_task.get("topic", ""))
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM learning_paths WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if row:
            progress = json_load(row["progress_json"]) if row["progress_json"] else {}
            progress = _normalize_progress(progress)
            if "task_quiz_map" not in progress:
                progress["task_quiz_map"] = {}
            progress["task_quiz_map"][str(session_id)] = task_key
            progress["used_question_texts"] = list(used_questions)
            print(f"[generate_task_quiz] Saving task_quiz_map[{session_id}] = {task_key}")
            conn.execute(
                "UPDATE learning_paths SET progress_json = ? WHERE id = ?",
                (json.dumps(progress, ensure_ascii=False), row["id"])
            )
            conn.commit()
        conn.close()

    # 7. 附带任务上下文返回
    result["task_context"] = {
        "day": task_day,
        "topic": target_task.get("topic", ""),
        "knowledge": knowledge_text
    }

    return result


def _build_code_task_from_template(topic: str, knowledge: str, action: str, depth: str = "标准", index: int = 0) -> dict:
    """根据知识点分类匹配对应的编程任务模板"""
    from services.code_lab_templates import build_code_task
    return build_code_task(topic, knowledge, action, depth, index)

# ===== Legacy code removed — now using code_lab_templates.py =====
async def get_code_task(user_id: int, task_day: int) -> dict:
    """获取指定天数的编程任务"""
    path = await get_learning_path(user_id)
    if not path or not path.get("path_data"):
        return {"error": "没有找到学习路径，请先生成学习路径"}

    path_data = path["path_data"]

    target_task = None
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task.get("day") == task_day:
                target_task = task
                break
        if target_task:
            break

    if not target_task:
        return {"error": f"未找到第{task_day}天的任务"}

    topic = target_task.get("topic", "")
    knowledge = target_task.get("knowledge", "")
    action = target_task.get("action", "")
    depth = path_data.get("learning_depth", "标准")

    # 使用模板生成详细编程任务（task_day作为序号轮换不同练习类型）
    code_task = _build_code_task_from_template(topic, knowledge, action, depth, index=task_day)
    code_task["task_context"] = {"day": task_day, "topic": topic, "knowledge": knowledge, "action": action}
    return code_task


async def execute_code(user_id: int, task_day: int, code: str) -> dict:
    """在沙箱中执行用户代码并严格运行测试验证"""
    import subprocess
    import tempfile
    import os

    # 获取任务和测试用例
    task_info = await get_code_task(user_id, task_day)
    if "error" in task_info:
        return task_info

    test_cases = task_info.get("test_cases", [])

    # 为每个测试用例生成独立的测试脚本
    test_results = []
    all_outputs = []

    for tc in test_cases:
        check_type = tc.get("check_type", "output_exists")
        expected = tc.get("expected_output", "").strip()
        test_name = tc.get("name", "")
        test_desc = tc.get("description", "")

        # 去除用户代码中的 if __name__ == "__main__" 块，避免干扰测试输出
        idx = code.find('\nif __name__')
        if idx < 0:
            idx = code.find('\nif  __name__')
        clean_code = code[:idx] if idx > 0 else code

        # 构建测试执行脚本：用户类/函数定义 + 测试用例的setup
        test_script = f"""# -*- coding: utf-8 -*-
# === 用户代码（类/函数定义） ===
{clean_code}

# === 测试用例: {test_name} ===
{tc.get("setup_code", "")}
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(test_script)
            tmp_path = f.name

        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            result = subprocess.run(
                ["python", tmp_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=15,
                env=env,
                cwd=os.path.dirname(tmp_path)
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            all_outputs.append(stdout)

            if result.returncode != 0:
                test_results.append({
                    "name": test_name, "description": test_desc,
                    "status": "failed", "message": f"运行错误: {stderr[:300] if stderr else f'退出码 {result.returncode}'}",
                    "expected": expected, "actual": stdout
                })
                continue

            # 根据检查类型判断是否通过
            passed = False
            if check_type == "exact_match":
                passed = stdout == expected
            elif check_type == "output_contains":
                passed = expected in stdout if expected else bool(stdout)
            elif check_type == "output_exists":
                passed = bool(stdout)
            else:
                passed = bool(stdout)

            if passed:
                msg = f"测试通过"
                if expected:
                    msg += f" - 输出符合预期"
                test_results.append({
                    "name": test_name, "description": test_desc,
                    "status": "passed", "message": msg,
                    "expected": expected, "actual": stdout
                })
            else:
                test_results.append({
                    "name": test_name, "description": test_desc,
                    "status": "failed",
                    "message": f"输出不匹配",
                    "expected": expected, "actual": stdout
                })

        except subprocess.TimeoutExpired:
            test_results.append({
                "name": test_name, "description": test_desc,
                "status": "failed", "message": "执行超时（超过15秒）",
                "expected": expected, "actual": ""
            })
        except Exception as e:
            test_results.append({
                "name": test_name, "description": test_desc,
                "status": "failed", "message": f"执行异常: {str(e)}",
                "expected": expected, "actual": ""
            })
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

    # 综合判断
    all_passed = all(t["status"] == "passed" for t in test_results)
    compile_status = "success" if all_passed else "error"
    combined_stdout = "\n".join(all_outputs)

    return {
        "compile_status": compile_status,
        "stdout": combined_stdout,
        "stderr": "" if all_passed else "部分测试未通过，请检查输出",
        "exit_code": 0 if all_passed else 1,
        "test_results": test_results,
        "all_passed": all_passed,
        "passed_count": sum(1 for t in test_results if t["status"] == "passed"),
        "total_count": len(test_results)
    }


def _generate_answer_with_explanations(topic: str, knowledge: str) -> dict:
    """生成答案代码及逐行解释"""
    if "智能体" in knowledge or "Agent" in topic.lower():
        answer_code = '''class SimpleAgent:
    """AI智能体类 - 完整实现"""
    def __init__(self, name: str):
        """初始化智能体"""
        self.name = name
        self.memory = []
        print(f"Agent {name} 初始化成功")

    def perceive(self, input_text: str) -> str:
        """感知输入并存储到记忆"""
        self.memory.append(input_text)
        result = f"已处理输入: {input_text}"
        print(result)
        return result

    def respond(self) -> str:
        """返回最新响应"""
        return self.memory[-1] if self.memory else ""

    def get_memory(self) -> list:
        """获取所有记忆"""
        print(f"记忆数量: {len(self.memory)}")
        return self.memory


if __name__ == "__main__":
    agent = SimpleAgent("TestBot")
    agent.perceive("Hello")
    agent.perceive("第二条消息")
    print("记忆数量:", len(agent.get_memory()))'''
        explanations = [
            {"line": 1, "code": "class SimpleAgent:", "explanation": "定义一个名为 SimpleAgent 的类，表示一个简单的AI智能体。类是面向对象编程的核心概念，用于封装数据和行为。"},
            {"line": 2, "code": '    """AI智能体类 - 完整实现"""', "explanation": "文档字符串（docstring），用于描述类的用途。良好的文档字符串有助于代码可读性。"},
            {"line": 3, "code": "    def __init__(self, name: str):", "explanation": "构造函数，在创建实例时自动调用。self 指向实例本身，name 参数接收智能体的名称，类型注解 :str 表示期望字符串类型。"},
            {"line": 4, "code": '        """初始化智能体"""', "explanation": "方法的文档字符串，说明此方法的功能。"},
            {"line": 5, "code": "        self.name = name", "explanation": "将传入的 name 参数赋值给实例属性 self.name，这样其他方法可以通过 self.name 访问智能体名称。"},
            {"line": 6, "code": "        self.memory = []", "explanation": "初始化一个空列表作为记忆存储。列表是Python中最常用的数据结构之一，支持动态添加元素。"},
            {"line": 7, "code": '        print(f"Agent {name} 初始化成功")', "explanation": "使用 f-string 格式化输出初始化确认信息，f-string 是 Python 3.6+ 提供的简洁字符串格式化方式。"},
            {"line": 9, "code": "    def perceive(self, input_text: str) -> str:", "explanation": "定义感知方法，接收文本输入并返回处理确认。-> str 表示返回值为字符串类型。这是智能体与外界交互的主要入口。"},
            {"line": 10, "code": '        """感知输入并存储到记忆"""', "explanation": "方法说明文档。"},
            {"line": 11, "code": "        self.memory.append(input_text)", "explanation": "使用列表的 append 方法将输入文本添加到记忆列表末尾。这样智能体就能记住所有接收到的信息。"},
            {"line": 12, "code": '        return f"已处理输入: {input_text}"', "explanation": "返回处理确认信息，告知调用者输入已被接收和处理。"},
            {"line": 14, "code": "    def respond(self) -> str:", "explanation": "定义响应方法，返回智能体记忆中最新的信息。模拟智能体根据记忆做出响应的行为。"},
            {"line": 15, "code": '        """返回最新响应"""', "explanation": "方法说明文档。"},
            {"line": 16, "code": "        return self.memory[-1] if self.memory else \"\"", "explanation": "三元表达式：如果 memory 非空则返回最后一条（索引 -1 表示最后一个元素），否则返回空字符串。这是边界条件处理的重要示例。"},
            {"line": 18, "code": "    def get_memory(self) -> list:", "explanation": "定义获取记忆方法，返回完整的记忆列表。提供了访问内部数据的公开接口，体现了封装原则。"},
            {"line": 19, "code": '        """获取所有记忆"""', "explanation": "方法说明文档。"},
            {"line": 20, "code": "        return self.memory", "explanation": "直接返回记忆列表。在更复杂的实现中可能需要深拷贝以保护内部数据。"},
            {"line": 23, "code": 'if __name__ == "__main__":', "explanation": "Python 的标准入口检查。当脚本直接运行时 __name__ 为 '__main__'，当被导入时则为模块名。这种模式允许代码既可作为模块导入，也可独立运行。"},
            {"line": 24, "code": '    agent = SimpleAgent("TestBot")', "explanation": "创建 SimpleAgent 实例，传入名称参数 'TestBot'。这会触发 __init__ 方法并打印初始化信息。"},
            {"line": 25, "code": '    print(agent.perceive("Hello"))', "explanation": "调用 percepve 方法处理输入 'Hello'，并打印返回的确认信息。验证感知功能是否正常。"},
            {"line": 26, "code": '    agent.perceive("第二条消息")', "explanation": "再次调用 perceive 添加第二条消息，测试多次输入下的记忆累积功能。"},
            {"line": 27, "code": '    print("记忆数量:", len(agent.get_memory()))', "explanation": "调用 get_memory 获取完整记忆列表，用 len() 获取列表长度并打印。验证记忆存储和检索的正确性。"},
        ]
    elif "框架" in knowledge or "LangChain" in topic.lower():
        answer_code = '''class Step:
    """处理步骤"""
    def __init__(self, name: str, func):
        self.name = name
        self.func = func
        print(f"Step {name} 创建成功")

    def execute(self, data):
        """执行步骤处理"""
        return self.func(data)


class Pipeline:
    """处理流水线"""
    def __init__(self):
        self.steps = []

    def add_step(self, name: str, func) -> None:
        """添加处理步骤"""
        step = Step(name, func)
        self.steps.append(step)

    def run(self, data):
        """依次执行所有步骤并返回最终结果"""
        result = data
        for step in self.steps:
            result = step.execute(result)
        return result


if __name__ == "__main__":
    p = Pipeline()
    p.add_step("upper", lambda x: x.upper())
    p.add_step("reverse", lambda x: x[::-1])
    print("Pipeline结果:", p.run("hello"))'''
        explanations = [
            {"line": 1, "code": "class Step:", "explanation": "定义 Step 类，表示流水线中的一个处理步骤。每个步骤有名称和处理函数。"},
            {"line": 3, "code": "    def __init__(self, name: str, func):", "explanation": "构造函数，接收步骤名称 name 和处理函数 func。func 接受一个参数并返回处理结果。"},
            {"line": 4, "code": "        self.name = name", "explanation": "保存步骤名称到实例属性。"},
            {"line": 5, "code": "        self.func = func", "explanation": "保存处理函数到实例属性。函数是一等公民，可以作为参数传递和存储。"},
            {"line": 6, "code": '        print(f"Step {name} 创建成功")', "explanation": "输出确认信息，便于调试和追踪步骤创建。"},
            {"line": 8, "code": "    def execute(self, data):", "explanation": "执行步骤的处理逻辑。接收上一个步骤的输出作为输入。"},
            {"line": 10, "code": "        return self.func(data)", "explanation": "调用保存的处理函数并返回结果。这是责任链模式的核心——每个步骤处理并传递数据。"},
            {"line": 13, "code": "class Pipeline:", "explanation": "定义 Pipeline 类，管理多个处理步骤并按顺序执行。实现管道模式（Pipeline Pattern）。"},
            {"line": 15, "code": "    def __init__(self):", "explanation": "构造函数，初始化空的步骤列表。"},
            {"line": 16, "code": "        self.steps = []", "explanation": "用列表存储所有步骤，保持添加顺序。"},
            {"line": 18, "code": "    def add_step(self, name: str, func) -> None:", "explanation": "添加步骤方法。-> None 表示此方法没有返回值。将名称和处理函数组合成 Step 对象并加入流水线。"},
            {"line": 20, "code": "        step = Step(name, func)", "explanation": "创建 Step 实例，封装名称和函数。"},
            {"line": 21, "code": "        self.steps.append(step)", "explanation": "将步骤添加到流水线的步骤列表中。"},
            {"line": 23, "code": "    def run(self, data):", "explanation": "执行流水线核心方法。接收初始数据，依次通过每个步骤处理。"},
            {"line": 25, "code": "        result = data", "explanation": "初始化结果为输入数据。在流水线处理中，前一个步骤的输出是下一个步骤的输入。"},
            {"line": 26, "code": "        for step in self.steps:", "explanation": "遍历所有步骤，按添加顺序依次执行。"},
            {"line": 27, "code": "            result = step.execute(result)", "explanation": "调用当前步骤的 execute 方法处理数据，用返回值更新 result。"},
            {"line": 28, "code": "        return result", "explanation": "返回经过所有步骤处理后的最终结果。"},
            {"line": 31, "code": 'if __name__ == "__main__":', "explanation": "测试入口。当脚本直接运行时执行以下测试代码。"},
            {"line": 32, "code": "    p = Pipeline()", "explanation": "创建 Pipeline 实例。"},
            {"line": 33, "code": '    p.add_step("upper", lambda x: x.upper())', "explanation": "添加第一个步骤：使用 lambda 匿名函数将文本转为大写。lambda 是定义简单单行函数的快捷方式。"},
            {"line": 34, "code": '    p.add_step("reverse", lambda x: x[::-1])', "explanation": "添加第二个步骤：使用切片 [::-1] 反转字符串。这利用了 Python 切片的强大功能。"},
            {"line": 35, "code": '    print("Pipeline结果:", p.run("hello"))', "explanation": "运行流水线处理 'hello'，预期输出 'OLLEH'（先大写后反转）。验证整个流水线功能。"},
        ]
    else:
        answer_code = f'''# 编程练习: {topic}
# 知识点: {knowledge}

def solve_problem():
    """解决问题的核心函数"""
    # 根据任务要求实现具体逻辑
    result = "任务完成"
    return result


if __name__ == "__main__":
    result = solve_problem()
    print(f"结果: {{result}}")'''
        explanations = [
            {"line": 1, "code": answer_code.split(chr(10))[0], "explanation": "注释说明程序的目的和涉及的知识点。良好的注释帮助理解代码意图。"},
            {"line": 4, "code": "def solve_problem():", "explanation": "定义解决问题的核心函数。将主要逻辑封装在函数中是好习惯，便于测试和复用。"},
            {"line": 6, "code": '    result = "任务完成"', "explanation": "根据具体任务实现核心逻辑。此处为占位，实际开发中应根据需求编写具体处理代码。"},
            {"line": 7, "code": "    return result", "explanation": "返回处理结果。函数通过 return 将计算结果传递给调用者。"},
            {"line": 10, "code": 'if __name__ == "__main__":', "explanation": "Python 标准入口检查，使脚本既可独立运行也可作为模块导入。"},
            {"line": 11, "code": "    result = solve_problem()", "explanation": "调用核心函数获取结果。将函数调用与输出分离，提高代码清晰度。"},
            {"line": 12, "code": '    print(f"结果: {result}")', "explanation": "使用 f-string 格式化输出最终结果，方便查看程序执行效果。"},
        ]

    return {
        "answer_code": answer_code,
        "explanations": [e for e in explanations if not e["code"].strip().startswith(('#', '"""', "'''"))]
    }


async def get_code_answer(user_id: int, task_day: int) -> dict:
    """获取编程任务的参考答案及逐行解释"""
    task_info = await get_code_task(user_id, task_day)
    if "error" in task_info:
        return task_info

    topic = task_info.get("task_context", {}).get("topic", "")
    knowledge = task_info.get("task_context", {}).get("knowledge", "")
    result = _generate_answer_with_explanations(topic, knowledge)
    result["task_context"] = task_info.get("task_context", {})
    return result


async def review_error(user_id: int, error_id: int) -> dict:
    """标记错题已复习"""
    conn = get_db()
    conn.execute(
        "UPDATE error_questions SET reviewed = 1 WHERE id = ? AND user_id = ?",
        (error_id, user_id)
    )
    conn.commit()
    conn.close()

    # 更新学习记录
    conn = get_db()
    error = conn.execute("SELECT * FROM error_questions WHERE id = ?", (error_id,)).fetchone()
    if error:
        conn.execute(
            "INSERT INTO learning_records (user_id, knowledge_tag, action_type, result_json) VALUES (?, ?, 'review_error', ?)",
            (user_id, error["knowledge_tag"], json.dumps({"error_id": error_id}, ensure_ascii=False))
        )
    conn.commit()
    conn.close()

    return {"message": "已标记为已复习"}


async def review_session_errors(user_id: int, session_id: int) -> dict:
    """将该会话下所有未复习的错题批量标记为已复习"""
    conn = get_db()
    cur = conn.execute(
        "UPDATE error_questions SET reviewed = 1 WHERE user_id = ? AND session_id = ? AND reviewed = 0",
        (user_id, session_id)
    )
    updated = cur.rowcount
    conn.commit()
    conn.close()

    # 为每道题记录学习活动
    if updated > 0:
        conn = get_db()
        errors = conn.execute(
            "SELECT id, knowledge_tag FROM error_questions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id)
        ).fetchall()
        for e in errors:
            conn.execute(
                "INSERT INTO learning_records (user_id, knowledge_tag, action_type, result_json) VALUES (?, ?, 'review_error', ?)",
                (user_id, e["knowledge_tag"], json.dumps({"error_id": e["id"], "batch": True}, ensure_ascii=False))
            )
        conn.commit()
        conn.close()

    return {"reviewed_count": updated, "session_id": session_id}


# ===== AI 手把手编程教学 =====

CODE_STEP_GUIDE_PROMPT = """你是一位编程导师，正在手把手教零基础学生完成一道编程题。学生是初学者，需要看到完整的代码才能跟着写。

**题目信息：**
- 标题：{title}
- 知识点：{knowledge}
- 任务描述：{description}
- 任务要求：{requirements}
- 起始代码：{starter_code}

**起始代码中标记了 START 和 END 的区域是学生需要编写的部分。**

**核心原则：**
- 每个步骤给出该步骤的完整代码，学生照着你写的代码敲进去就能通过
- 步骤从易到难、逐步推进，最后一步完成后所有 START/END 区域都被填满
- 每一步只完成一小部分，让学生逐个方法/函数地实现

**返回格式（JSON）：**
```json
{{
  "steps": [
    {{
      "title": "步骤1：实现 __init__ 方法",
      "instruction": "这一步骤做什么、为什么这样做",
      "example_code": "    def __init__(self, name: str):\\n        self.name = name\\n        self.memory = []",
      "expected": "完成此步后运行代码，应该能看到 Agent 初始化成功的提示"
    }},
    ...
  ]
}}
```

**example_code 要求：**
- 必须是当前这一步的完整可运行代码，包含缩进
- 学生照着敲就能通过，不要省略、不要伪代码
- 如果这一步实现的是某个方法，给出该方法的完整代码
- 使用 \\n 表示换行

请直接返回 JSON，不要有其他文字。"""


CODE_STEP_CHECK_PROMPT = """你是一位编程导师，正在检查学生某个步骤的代码是否正确。

**完整题目：**
- 标题：{title}
- 知识点：{knowledge}
- 任务描述：{description}

**当前步骤（第 {step_index} 步）：**
- 标题：{step_title}
- 要求：{step_instruction}

**学生的代码：**
```python
{student_code}
```

**起始代码（供参考）：**
```python
{starter_code}
```

**请判断：**
1. 学生是否完成了当前步骤的要求？
2. 如果没有完成或者代码有问题，具体哪里有问题？应该怎么改？

用 JSON 格式返回：
```json
{{
  "passed": true/false,
  "feedback": "简短的评价（1-2句话）",
  "issue": "如果 passed=false，指出具体问题；如果 passed=true，可以为空字符串"
}}
```

请直接返回 JSON，不要有其他文字。"""


# 步骤指南缓存（key: "user_id:task_day"）
_step_guide_cache: dict = {}


async def generate_code_step_guide(user_id: int, task_day: int) -> dict:
    """用 AI 将编程任务分解为手把手教学步骤（结果缓存，不重复生成）"""
    cache_key = f"{user_id}:{task_day}"

    # 命中缓存直接返回
    if cache_key in _step_guide_cache:
        return _step_guide_cache[cache_key]

    task_info = await get_code_task(user_id, task_day)
    if "error" in task_info:
        return task_info

    prompt = CODE_STEP_GUIDE_PROMPT.format(
        title=task_info.get("title", ""),
        knowledge=task_info.get("knowledge", ""),
        description=task_info.get("description", ""),
        requirements="\n".join(task_info.get("requirements", [])),
        starter_code=task_info.get("starter_code", "")
    )

    response = await call_llm(user_id, [
        {"role": "system", "content": "你是编程教学专家，请严格按JSON格式返回，不要输出其他内容。"},
        {"role": "user", "content": prompt}
    ], temperature=0.3)

    try:
        steps_data = extract_json_object(response)
    except Exception:
        return {"error": "AI 生成教学步骤失败，请稍后重试"}

    steps_data["task_context"] = {
        "title": task_info.get("title", ""),
        "knowledge": task_info.get("knowledge", ""),
        "task_day": task_day
    }

    # 存入缓存
    _step_guide_cache[cache_key] = steps_data
    return steps_data


async def check_code_step(user_id: int, task_day: int, step_index: int,
                           code: str, step_title: str = "", step_instruction: str = "") -> dict:
    """用 AI 检查学生当前步骤的代码是否正确

    前端直接传入 step_title 和 step_instruction，避免后端再次调 LLM 生成步骤指南。
    """
    task_info = await get_code_task(user_id, task_day)
    if "error" in task_info:
        return task_info

    # 如果前端没传步骤信息，尝试从缓存拿
    if not step_title or not step_instruction:
        cache_key = f"{user_id}:{task_day}"
        cached = _step_guide_cache.get(cache_key, {})
        steps = cached.get("steps", [])
        if step_index < len(steps):
            step_title = steps[step_index].get("title", "")
            step_instruction = steps[step_index].get("instruction", "")

    prompt = CODE_STEP_CHECK_PROMPT.format(
        title=task_info.get("title", ""),
        knowledge=task_info.get("knowledge", ""),
        description=task_info.get("description", ""),
        step_index=step_index + 1,
        step_title=step_title,
        step_instruction=step_instruction,
        student_code=code,
        starter_code=task_info.get("starter_code", "")
    )

    response = await call_llm(user_id, [
        {"role": "system", "content": "你是编程教学专家，只输出JSON，不要输出其他内容。"},
        {"role": "user", "content": prompt}
    ], temperature=0.2)

    try:
        result = extract_json_object(response)
    except Exception:
        return {"passed": False, "feedback": "AI 评估超时，请重试", "issue": ""}

    result["step_title"] = step_title
    result["step_instruction"] = step_instruction
    result["step_index"] = step_index

    # AI 判定通过时，实际运行代码做双重验证
    if result.get("passed"):
        exec_result = await execute_code(user_id, task_day, code)
        result["exec_result"] = {
            "compile_status": exec_result.get("compile_status", ""),
            "all_passed": exec_result.get("all_passed", False),
            "passed_count": exec_result.get("passed_count", 0),
            "total_count": exec_result.get("total_count", 0)
        }

    return result
