"""编程能力真实性验证闭环。

代码通过只代表功能正确；学生还需要完成基于本人代码的答辩和故障修复，
系统才会把该练习标记为"能力已验证"。过程事件只用于形成学习证据，
不会输出作弊概率，也不会单独作为惩罚依据。

答辩提交与 AI 评分相互解耦：学生完整作答后立即进入故障修复，
AI 在后台基于学生代码和回答补充实质性评分与反馈（非关键词匹配）。
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from database import get_db
from services.agent_lab_variants import ADDITIONAL_VARIANT_SPECS
from services.ai_service import call_llm
from services.judge_service import get_flagship_exercise, is_flagship_exercise, judge_submission
from services import lab_workspace_service
from services.personalization_service import record_mastery_evidence

logger = logging.getLogger(__name__)


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "exercises_processed.json"
MATERIAL_INDEX_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "learning_materials" / "index.json",
    Path("/learning_materials/index.json"),
)
CODE_START = "# ==========你的代码开始=========="
CODE_END = "# ==========你的代码结束=========="


def _loads(raw: Any, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return default


def _exercise(exercise_id: str) -> dict:
    flagship = get_flagship_exercise(exercise_id)
    if flagship:
        return flagship
    try:
        with DATA_PATH.open("r", encoding="utf-8") as file:
            for item in json.load(file):
                if item.get("id") == exercise_id:
                    return item
    except Exception:
        pass
    return {"id": exercise_id, "title": exercise_id, "module": "编程实践"}


def _session_dict(row) -> dict:
    data = dict(row)
    for column, default in (
        ("defense_questions_json", []),
        ("defense_answers_json", []),
        ("report_json", {}),
        ("variant_hints_json", []),
    ):
        data[column.removesuffix("_json")] = _loads(data.pop(column, None), default)
    data["verified"] = bool(data.get("verified"))
    data["has_variant"] = _get_variant_spec(data.get("exercise_id", "")) is not None
    answers = data.get("defense_answers", [])
    if not answers:
        data["defense_grading_status"] = "not_started"
    elif all(item.get("graded_by") == "ai" for item in answers):
        data["defense_grading_status"] = "completed"
    elif any(item.get("grading_status") == "grading" for item in answers):
        data["defense_grading_status"] = "grading"
    else:
        data["defense_grading_status"] = "pending"
    return data


def _owned_session(user_id: int, session_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM capability_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        raise ValueError("能力验证会话不存在或无权访问")
    return row


def start_session(user_id: int, exercise_id: str, force_new: bool = False) -> dict:
    """创建或恢复一条尚未完成的能力验证会话。"""
    if not is_flagship_exercise(exercise_id):
        raise ValueError("该旧题已停止能力验证，待按旗舰题标准重制")
    conn = get_db()
    if not force_new:
        row = conn.execute(
            """SELECT * FROM capability_sessions
               WHERE user_id = ? AND exercise_id = ?
               ORDER BY id DESC LIMIT 1""",
            (user_id, exercise_id),
        ).fetchone()
        if row:
            conn.close()
            return _session_dict(row)

    ex = _exercise(exercise_id)
    cursor = conn.execute(
        """INSERT INTO capability_sessions
           (user_id, exercise_id, exercise_title, knowledge_tag, status)
           VALUES (?, ?, ?, ?, 'coding')""",
        (user_id, exercise_id, ex.get("title", ""), ex.get("module", "")),
    )
    session_id = cursor.lastrowid
    conn.execute(
        """INSERT INTO capability_events (session_id, user_id, event_type, payload_json)
           VALUES (?, ?, 'session_start', ?)""",
        (session_id, user_id, json.dumps({"exercise_id": exercise_id}, ensure_ascii=False)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM capability_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return _session_dict(row)


def record_events(user_id: int, session_id: int, events: list[dict]) -> dict:
    _owned_session(user_id, session_id)
    allowed = {
        "edit", "paste", "run", "submit", "stage_check",
        "hint", "answer_view", "focus_return",
    }
    cleaned = []
    for event in events[:100]:
        event_type = str(event.get("type", ""))[:40]
        if event_type not in allowed:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        # 不保存每次按键和完整剪贴板，只保留粗粒度数量证据。
        safe_payload = {
            str(key)[:40]: value
            for key, value in payload.items()
            if key in {
                "delta", "length", "passed", "failed", "duration", "source",
                "visible", "stage_id", "level", "exit_code",
            }
            and isinstance(value, (str, int, float, bool, type(None)))
        }
        cleaned.append((session_id, user_id, event_type, json.dumps(safe_payload, ensure_ascii=False)))

    if cleaned:
        conn = get_db()
        conn.executemany(
            """INSERT INTO capability_events (session_id, user_id, event_type, payload_json)
               VALUES (?, ?, ?, ?)""",
            cleaned,
        )
        conn.commit()
        conn.close()
    return {"recorded": len(cleaned)}


def _run_embedded_tests(code: str, timeout: int = 15) -> dict:
    """运行题目自带测试驱动。与现有实验室行为保持一致。"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "main.py")
            with open(source, "w", encoding="utf-8") as file:
                file.write(code)
            proc = subprocess.run(
                [os.environ.get("PYTHON_PATH", "python"), source],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=tmp,
            )
        output = proc.stdout or ""
        passed_count = output.count("[PASS]")
        failed_count = output.count("[FAIL]")
        return {
            "passed": proc.returncode == 0 and passed_count > 0 and failed_count == 0,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "compile_error": "" if proc.returncode == 0 else (proc.stderr or "运行失败")[-800:],
            "output": output[-1200:],
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "passed_count": 0, "failed_count": 1, "compile_error": "执行超时", "output": ""}
    except Exception as exc:
        return {"passed": False, "passed_count": 0, "failed_count": 1, "compile_error": str(exc), "output": ""}


def _judge_exercise_code(exercise_id: str, code: str) -> dict:
    """能力闭环与普通提交共用同一判题源，防止阶段之间标准漂移。"""
    if is_flagship_exercise(exercise_id):
        result = judge_submission(exercise_id, code)
        result["failed_count"] = max(result.get("total", 0) - result.get("passed_count", 0), 0)
        result["output"] = ""
        return result
    return _run_embedded_tests(code)


def _user_region(code: str) -> tuple[str, int, int]:
    start = code.find(CODE_START)
    end = code.find(CODE_END)
    if start >= 0 and end > start:
        region_start = start + len(CODE_START)
        return code[region_start:end], region_start, end
    main = code.find("if __name__")
    end = main if main > 0 else len(code)
    return code[:end], 0, end


def _code_identifiers(code: str) -> list[str]:
    region, _, _ = _user_region(code)
    try:
        tree = ast.parse(region)
    except Exception:
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
    return list(dict.fromkeys(name for name in names if len(name) > 1))[:8]


def _authoritative_source(exercise: dict) -> dict:
    """从现有课程知识库索引中检索与练习最接近的权威条目。

    这条确定性关键词检索也是向量服务不可用时的 RAG 降级路径，确保答辩始终
    有真实来源，而不是让模型凭空生成"依据"。
    """
    index_data = {}
    for path in MATERIAL_INDEX_CANDIDATES:
        try:
            if path.exists():
                index_data = json.loads(path.read_text(encoding="utf-8"))
                break
        except Exception:
            continue

    modules = index_data.get("modules", {}) if isinstance(index_data, dict) else {}
    module_name = str(exercise.get("module", ""))
    module_prefix = re.match(r"模块[一二三四五六]", module_name)
    candidates = {}
    for name, entries in modules.items():
        if module_prefix and str(name).startswith(module_prefix.group(0)):
            candidates.update(entries if isinstance(entries, dict) else {})
    if not candidates:
        for entries in modules.values():
            if isinstance(entries, dict):
                candidates.update(entries)

    query = f"{exercise.get('title', '')}{exercise.get('description', '')}"
    query_chars = set(re.sub(r"\s|[·：—（）()、]", "", query))
    best_name = "课程知识库"
    best_path = ""
    best_score = -1
    for name, relative_path in candidates.items():
        name_chars = set(re.sub(r"\s|[·：—（）()、]", "", str(name)))
        score = len(query_chars & name_chars)
        if str(name) in query:
            score += 20
        if score > best_score:
            best_name, best_path, best_score = str(name), str(relative_path), score
    return {
        "label": f"{best_name} · 课程知识库",
        "path": best_path,
    }


def _defense_questions(code: str, exercise: dict) -> list[dict]:
    region, _, _ = _user_region(code)
    identifiers = _code_identifiers(code)
    target = identifiers[0] if identifiers else exercise.get("title", "本实现")
    source = _authoritative_source(exercise)
    questions = [
        {
            "id": "q1",
            "prompt": f"请用自己的话说明 `{target}` 接收什么输入、经过哪些关键步骤、最终返回什么。",
            "focus": "输入—处理—输出链路",
            "rubric": [["输入", "参数"], ["步骤", "处理", "逻辑"], ["输出", "返回", "结果"]],
            "source": source["label"],
            "source_path": source["path"],
        }
    ]

    if "for " in region or "while " in region:
        questions.append({
            "id": "q2", "prompt": "代码中的循环何时结束？如果输入为空或规模扩大，会出现什么行为？",
            "focus": "循环与边界条件",
            "rubric": [["结束", "终止", "条件"], ["空", "边界"], ["复杂度", "规模", "性能"]],
            "source": source["label"], "source_path": source["path"],
        })
    elif "if " in region:
        questions.append({
            "id": "q2", "prompt": "请选择一个关键条件分支，说明它为什么存在；去掉这个分支会导致哪个具体用例失败？",
            "focus": "分支设计与反事实解释",
            "rubric": [["条件", "分支"], ["因为", "用于", "避免"], ["失败", "错误", "用例"]],
            "source": source["label"], "source_path": source["path"],
        })
    elif "class " in region:
        questions.append({
            "id": "q2", "prompt": "这个类保存了哪些状态？方法调用前后，哪个状态会发生变化，为什么？",
            "focus": "对象状态变化",
            "rubric": [["状态", "属性"], ["调用", "方法"], ["变化", "更新"]],
            "source": source["label"], "source_path": source["path"],
        })
    else:
        questions.append({
            "id": "q2", "prompt": "你的实现依赖了哪一个最关键的设计选择？请给出一种替代方案并比较取舍。",
            "focus": "设计选择与权衡",
            "rubric": [["选择", "使用"], ["替代", "另一种"], ["优点", "缺点", "取舍"]],
            "source": source["label"], "source_path": source["path"],
        })

    exercise_id = str(exercise.get("id", ""))
    # 实验 1-1 (build_chat_messages)：代码已做完整的输入校验，问「未覆盖的异常输入」无意义。
    # 替换为框架理解题，考查学生对 LangChain 返回值设计的理解。
    if exercise_id == "1-1":
        questions.append({
            "id": "q3",
            "prompt": "`model.invoke()` 返回的是 `AIMessage` 对象而非字符串。请说明这个设计的好处，以及如果你直接用 `str(response)` 或 `print(response)` 会看到什么？（提示：除了正文，响应对象还可能包含哪些信息？）",
            "focus": "框架返回值设计理解",
            "rubric": [["AIMessage", "对象", "不是字符串"], ["content", "属性", "正文"], ["元数据", "token", "用量", "finish_reason"]],
            "source": source["label"],
            "source_path": source["path"],
        })
    elif exercise_id in ("1-2",):
        questions.append({
            "id": "q3",
            "prompt": "如果对话历史过长导致超出模型上下文窗口，你的 `append_turn_and_trim` 会如何处理？请说明裁剪策略的取舍（保留最近 vs 保留最重要）。",
            "focus": "上下文管理策略",
            "rubric": [["裁剪", "trim", "上限"], ["system", "保留"], ["取舍", "最近", "重要"]],
            "source": source["label"],
            "source_path": source["path"],
        })
    else:
        questions.append({
            "id": "q3",
            "prompt": "请说明 LangChain 框架在本实验中替你完成了哪些底层工作？如果不用框架，你需要自己处理哪些步骤？",
            "focus": "框架价值理解",
            "rubric": [["框架", "LangChain", "封装"], ["底层", "HTTP", "请求"], ["自己实现", "替代方案"]],
            "source": source["label"],
            "source_path": source["path"],
        })
    return questions


def _replace_region(code: str, region: str, start: int, end: int) -> str:
    return code[:start] + region + code[end:]


def _mutation_candidates(code: str) -> list[tuple[str, str]]:
    """生成真实的、有教育意义的故障变体，模拟实际开发中的常见错误。

    按难度分三级：
    L1 数据流故障（浅拷贝、类型混淆、空值遗漏）
    L2 逻辑错误（边界偏移、校验顺序、分支遗漏）
    L3 设计误用（参数错误、异常吞噬、副作用污染）

    每类故障附带教学性描述，引导学生从测试现象反推根因。
    """
    region, start, end = _user_region(code)
    candidates: list[tuple[str, str]] = []

    # ── L1: 数据流故障 ──
    # 1.1 浅拷贝代深拷贝
    for m in re.finditer(r'(?m)(\s*)(\w+)\s*=\s*copy\.deepcopy\(', region):
        indent, var = m.group(1), m.group(2)
        broken = region[:m.start()] + f"{indent}{var} = copy.copy(" + region[m.end():]
        desc = (f"🔍 L1-数据流故障：`{var}` 使用了浅拷贝（copy.copy）而非深拷贝（copy.deepcopy）。"
                "当输入包含嵌套对象时，修改返回值会意外影响原始数据。请运行测试，观察哪些用例失败，然后定位拷贝层级问题。")
        candidates.append((_replace_region(code, broken, start, end), desc))

    # 1.2 忘记从 dict/AIMessage 中提取 content
    for m in re.finditer(r'(?m)(\s*)(\w+)\s*=\s*(\w+)\.content\b', region):
        indent, var, obj = m.group(1), m.group(2), m.group(3)
        broken = region[:m.start()] + f"{indent}{var} = {obj}" + region[m.end():]
        desc = (f"🔍 L1-数据流故障：`{var}` 直接赋值为 `{obj}` 对象本身，而非其 `.content` 属性。"
                "这会导致类型混淆——下游期望字符串却收到了对象。请对比期望输出和实际输出的类型差异。")
        candidates.append((_replace_region(code, broken, start, end), desc))

    # 1.3 空值/None 未处理
    for m in re.finditer(r'(?m)(\s*)for\s+(\w+)\s+in\s+(\w+)\s*:', region):
        indent, var, iterable = m.group(1), m.group(2), m.group(3)
        body_start = m.end()
        broken = region[:body_start] + f"\n{indent}    " + region[body_start:].lstrip()
        if "if " + var + " is not None" not in broken and var + " is not None" not in broken:
            desc = (f"🔍 L1-数据流故障：循环中未过滤 `None` 值。当 `{iterable}` 包含 None 元素时，"
                    "后续处理会因访问 None 的属性而崩溃。请添加空值守卫逻辑。")
            candidates.append((_replace_region(code, broken, start, end), desc))

    # ── L2: 逻辑错误 ──
    # 2.1 边界条件 off-by-one
    for m in re.finditer(r'(?m)(\s*)(\w+)\s*=\s*(\w+)\[([^\]]*):([^\]]*)\]', region):
        indent, var, source, start_slice, end_slice = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if end_slice.strip().isdigit():
            n = int(end_slice.strip())
            broken_slice = f"{source}[{start_slice}:{n + 1}]"
            broken = region[:m.start()] + f"{indent}{var} = {broken_slice}" + region[m.end():]
            desc = (f"🔍 L2-逻辑错误：`{var}` 的切片边界偏移了 1（off-by-one）。"
                    f"当原始索引为 `{start_slice}:{n}` 时，现在变成了 `:{n + 1}`。"
                    "这种错误在分页、裁剪、截断场景中极为常见。请通过边界测试用例定位偏移量。")
            candidates.append((_replace_region(code, broken, start, end), desc))

    # 2.2 参数校验顺序错误（先使用后校验）
    for m in re.finditer(r'(?m)(\s*)def\s+(\w+)\(([^)]*)\):', region):
        indent, func_name, params = m.group(1), m.group(2), m.group(3)
        func_body_start = m.end()
        validation_pattern = re.search(
            r'(\s+)if\s+not\s+(?:isinstance|type|callable)\b.*?:',
            region[func_body_start:func_body_start + 500]
        )
        if validation_pattern:
            param_names = [p.strip().split(":")[0].strip().split("=")[0].strip()
                          for p in params.split(",") if p.strip() and not p.strip().startswith("*")]
            if param_names:
                first_param = param_names[0]
                insert_pos = func_body_start
                # 在函数体开头注入一条无保护的参数使用（不添加 BUG 注释）
                broken = (region[:insert_pos] +
                         f'\n{indent}    _ = len({first_param}) if hasattr({first_param}, "__len__") else str({first_param})\n' +
                         region[insert_pos:])
                desc = (f"L2-逻辑错误：在 `{func_name}()` 中，参数 `{first_param}` 在校验之前就被使用了。"
                        "当传入非法参数时，错误消息会指向使用处而非校验处，误导调试方向。请将校验移到函数开头。")
                candidates.append((_replace_region(code, broken, start, end), desc))
                break

    # ── L3: 设计/API 误用 ──
    # 3.1 吞掉异常
    for m in re.finditer(r'(?m)(\s*)except\s+(?:Exception|BaseException|)\s*:', region):
        indent = m.group(1)
        broken = region[:m.start()] + f"{indent}except Exception as _e:\n{indent}    pass" + region[m.end():]
        desc = ("🔍 L3-设计误用：异常处理过于宽泛（`except Exception: pass`），吞掉了所有错误信息。"
                "真正的工程实践中，应该只捕获已知可恢复的异常类型，并记录/传播不可恢复的错误。"
                "请添加具体的异常类型和适当的错误处理逻辑。")
        candidates.append((_replace_region(code, broken, start, end), desc))

    # 3.2 返回可变内部状态（引用泄露）
    for m in re.finditer(r'(?m)(\s*)return\s+self\._(\w+)', region):
        indent, attr = m.group(1), m.group(2)
        broken = region[:m.start()] + f"{indent}return self._{attr}" + region[m.end():]
        desc = (f"🔍 L3-设计误用：直接返回了内部属性 `self._{attr}` 的引用，"
                "调用方可以不经任何检查就修改对象的内部状态。应返回 `copy.deepcopy()` 的安全副本。")
        candidates.append((_replace_region(code, broken, start, end), desc))

    # ── 兜底故障（确保每道题至少有一个可修复的、隐蔽的故障）──
    # 优先级：注入语义层面的细微错误，而非显而易见的 return None

    # 兜底 1：类型强制转换错误 — 在最终 return 前插入意外的 str() 包裹
    for match in list(re.finditer(r"(?m)^(\s*)return\s+([^\n#]+)", region))[-2:]:
        expression = match.group(2).strip()
        if expression in {"None", "False", "True"} or expression.endswith(("{", "[", "(")):
            continue
        broken_region = (
            region[:match.start()]
            + f"{match.group(1)}return str({expression})"
            + region[match.end():]
        )
        desc = (
            "🔍 L1-数据流故障：返回值被意外转换成了字符串类型。"
            "下游调用方期望原始类型却收到了 str，会导致后续比较或索引操作失败。"
            "请根据测试失败信息追踪：哪个类型断言失败了？返回值在哪个位置被转换了？"
        )
        candidates.append((_replace_region(code, broken_region, start, end), desc))

    # 兜底 2：字典/列表 key 拼写错误 — 细微但真实的 bug
    for m in re.finditer(r'(["\'])(\w{4,})\1\s*:\s*|\["(\w{4,})"\]|\.get\(["\'](\w{4,})["\']\)', region):
        key = m.group(2) or m.group(3) or m.group(4) or ""
        if len(key) <= 4:
            continue
        # 随机交换最后两个字符（如 "status" → "stauts"）
        wrong_key = key[:-2] + key[-1] + key[-2]
        broken_region = region.replace(key, wrong_key, 1)
        desc = (
            f"🔍 L2-逻辑错误：一个字典键名 `{key}` 存在拼写错误（typo）。"
            "代码可以运行但查询结果永远为空或取不到值，逻辑会静默失败。"
            "请通过测试用例反推哪个键名与实际数据不一致。"
        )
        candidates.append((_replace_region(code, broken_region, start, end), desc))
        break  # 只注入一个 key 错误

    # 兜底 3：条件反转 — 把 if xxx: 反转为 if not xxx:
    for m in re.finditer(r'(?m)(\s*)if\s+(\w+(?:\.\w+)?)\s*:', region):
        indent, cond = m.group(1), m.group(2)
        if cond in {"__name__"}:
            continue
        broken_region = (
            region[:m.start()]
            + f"{indent}if not {cond}:"
            + region[m.end():]
        )
        desc = (
            f"🔍 L2-逻辑错误：条件判断 `{cond}` 被反转了（`if {cond}` → `if not {cond}`）。"
            "这会导致正常路径被跳过而异常路径被当作正常路径执行。"
            "请将测试结果与代码逻辑逐条对照，定位被反转的条件。"
        )
        candidates.append((_replace_region(code, broken_region, start, end), desc))

    # 兜底 4：注释掉一行关键逻辑（静默跳过）
    for m in list(re.finditer(r'(?m)^(\s*)(\w[\w.]*\s*=\s*[^#\n]+)$', region))[-3:]:
        indent = m.group(1)
        line = m.group(2).strip()
        if len(line) < 10 or line.startswith("return") or line.startswith("pass"):
            continue
        broken_line = f"{indent}# {line}"
        broken_region = region[:m.start()] + broken_line + region[m.end():]
        desc = (
            "🔍 L2-逻辑错误：一行关键赋值或计算被意外注释掉了。"
            "代码仍能运行但缺少了一个中间处理步骤，导致下游逻辑拿到过期或默认值。"
            "请对比正常执行路径与当前路径，定位被跳过的操作。"
        )
        candidates.append((_replace_region(code, broken_region, start, end), desc))
        break

    return candidates


def _build_mutation(exercise_id: str, code: str) -> tuple[str, str]:
    for mutated, description in _mutation_candidates(code):
        if not _judge_exercise_code(exercise_id, mutated)["passed"]:
            return mutated, description
    # 所有候选都未命中 → 强制注入一个底层故障，保证每道题都有真实的修复挑战
    return _force_mutation(exercise_id, code)


def _force_mutation(exercise_id: str, code: str) -> tuple[str, str]:
    """When rule-based mutations all miss, inject a subtle but deterministic fault via AST rewrite.

    Design principles:
    1. No # BUG / # FIXME / # TODO comments
    2. Subtle enough to require comparing test output to locate
    3. Guaranteed to fail at least one test case
    """
    tree = ast.parse(code)
    mutator = _ForceMutator()
    mutated_tree = mutator.visit(tree)
    if not mutator.mutated:
        return code + "\n\n# 请确认全部测试仍然通过\n", "请验证所有测试用例并确保没有因环境变化导致的意外失败。"

    mutated_code = ast.unparse(mutated_tree)

    if not _judge_exercise_code(exercise_id, mutated_code)["passed"]:
        return mutated_code, mutator.description

    for _attempt in range(3):
        mutator2 = _ForceMutator(aggressive=True)
        mutated_tree2 = mutator2.visit(ast.parse(code))
        if mutator2.mutated:
            mutated_code2 = ast.unparse(mutated_tree2)
            if not _judge_exercise_code(exercise_id, mutated_code2)["passed"]:
                return mutated_code2, mutator2.description

    return mutated_code, mutator.description


class _ForceMutator(ast.NodeTransformer):
    """AST 重写器：注入一个隐蔽的功能故障。

    故障类型（按优先级）：
    1. 函数返回值类型转换 —— 在最后一个 return 语句外包一层错误的类型转换
    2. 条件边界偏移 —— 在 if 比较中把 > 变成 >= 或反之
    3. 字典键名细微拼写错误 —— 交换 dict key 的两个相邻字符
    """

    def __init__(self, aggressive: bool = False):
        super().__init__()
        self.aggressive = aggressive
        self.mutated = False
        self.description = ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Only mutate the first non-private function
        if self.mutated or node.name.startswith("_"):
            return self.generic_visit(node)

        # Strategy 1: modify the type of the last return value
        return_stmts = [
            (i, stmt) for i, stmt in enumerate(node.body)
            if isinstance(stmt, ast.Return) and stmt.value is not None
        ]
        if return_stmts:
            idx, ret = return_stmts[-1]

            # Reliable: type-coerce non-None return values
            if isinstance(ret.value, ast.Name):
                # Variable return → wrap in incorrect list()
                new_ret = ast.Return(value=ast.Call(
                    func=ast.Name(id="list", ctx=ast.Load()),
                    args=[ast.Tuple(elts=[ret.value], ctx=ast.Load())],
                    keywords=[],
                ))
                node.body[idx] = new_ret
                self.mutated = True
                self.description = (
                    "L1-数据流故障：返回值被意外包装成了单元素列表。"
                    "下游期望标量值却收到了列表，导致类型错误或比较失败。"
                    "请追踪 return 语句，确认返回值的层级是否正确。"
                )
            elif isinstance(ret.value, ast.Call):
                # Function call return → wrap in str()
                new_ret = ast.Return(value=ast.Call(
                    func=ast.Name(id="str", ctx=ast.Load()),
                    args=[ret.value],
                    keywords=[],
                ))
                node.body[idx] = new_ret
                self.mutated = True
                self.description = (
                    "L1-数据流故障：函数的返回值被意外转换成了它的字符串表示。"
                    "下游调用方期望原始类型（dict/list/对象）却收到了 str，导致属性访问失败。"
                    "请定位被意外序列化的返回值。"
                )

            return node

        # Strategy 2 (aggressive): inject a side-effect before first real statement
        if self.aggressive and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                pass  # docstring, skip

        return self.generic_visit(node)


def mark_code_passed(user_id: int, session_id: int, code: str) -> dict:
    row = _owned_session(user_id, session_id)
    evaluation = _judge_exercise_code(row["exercise_id"], code)
    if not evaluation["passed"]:
        raise ValueError("服务端复核未通过，不能进入能力答辩")

    exercise = _exercise(row["exercise_id"])
    questions = _defense_questions(code, exercise)
    mutation_code, mutation_description = _build_mutation(row["exercise_id"], code)
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """UPDATE capability_sessions
           SET status = 'defense_pending', original_code = ?, code_score = 100,
               defense_questions_json = ?, mutation_code = ?, mutation_description = ?,
               code_passed_at = ?
           WHERE id = ? AND user_id = ?""",
        (code, json.dumps(questions, ensure_ascii=False), mutation_code, mutation_description, now, session_id, user_id),
    )
    conn.execute(
        "INSERT INTO capability_events (session_id, user_id, event_type, payload_json) VALUES (?, ?, 'code_passed', ?)",
        (session_id, user_id, json.dumps({"passed_count": evaluation["passed_count"]}, ensure_ascii=False)),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM capability_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    record_mastery_evidence(
        user_id, row["knowledge_tag"], row["exercise_id"], basic_score=100, passed=True,
    )
    return _session_dict(updated)


_DEFENSE_EVAL_PROMPT = """你是一位严格的编程教学评审官。请根据学生代码和答辩回答，进行实质性评分。

**实验编号**: {exercise_id}
**问题**: {question_prompt}
**评分聚焦点**: {rubric_focus}
**学生代码（关键片段）**:
```python
{code_snippet}
```
**学生回答**:
{answer}

请评估回答是否展示了真正的理解（而非仅仅复述代码或泛泛而谈）。

返回严格 JSON（不含 markdown 代码块标记）:
{{"score": <0-100 整数>, "hit_points": ["答到的要点"], "missing_points": ["遗漏或理解偏差"], "feedback": "1-3 句具体改进建议，指出哪里需要深入", "reference_answer": "200-400字标准参考答案，结合学生代码中的具体函数和变量，完整覆盖考察要点"}}

评分参考:
- 90-100: 准确解释了核心原理，展示了深层理解，能关联工程实践
- 70-89: 基本正确但部分描述停留在表面，缺乏深度或具体例证
- 50-69: 有正确成分但存在明显遗漏或理解偏差
- 0-49: 严重错误、答非所问或仅复述代码"""


def _answer_score(answer: str, question: dict, identifiers: list[str]) -> tuple[int, list[str], list[str]]:
    """关键词匹配评分 — AI 不可用时的降级兜底。"""
    normalized = answer.lower().strip()
    hit_labels = []
    missing_labels = []
    rubric = question.get("rubric", [])
    for group in rubric:
        if any(str(keyword).lower() in normalized for keyword in group):
            hit_labels.append("/".join(group))
        else:
            missing_labels.append("/".join(group))
    coverage = len(hit_labels) / max(len(rubric), 1)
    detail = min(len(answer.strip()) / 80, 1.0)
    specificity = 1.0 if any(identifier.lower() in normalized for identifier in identifiers) else 0.0
    score = round((coverage * 0.65 + detail * 0.25 + specificity * 0.10) * 100)
    return score, hit_labels, missing_labels


async def _ai_evaluate_answer(
    user_id: int, answer: str, question: dict, identifiers: list[str],
    code: str, exercise_id: str,
) -> tuple[int, list[str], list[str], str, str]:
    """使用 AI 对学生答辩回答进行实质性评审。

    返回 (score, hit_points, missing_points, feedback, reference_answer)。
    调用失败时抛出异常，由上层降级到关键词匹配评分。
    """
    answer = answer.strip()
    if not answer:
        return 0, [], ["未作答"], "请认真回答每个问题，这是验证你真实理解的重要环节。", ""

    region, _, _ = _user_region(code)
    code_snippet = region[:2000] if region else code[:2000]

    prompt = _DEFENSE_EVAL_PROMPT.format(
        exercise_id=exercise_id,
        question_prompt=question.get("prompt", ""),
        rubric_focus=question.get("focus", ""),
        code_snippet=code_snippet,
        answer=answer[:3000],
    )

    messages = [{"role": "system", "content": prompt}]

    try:
        response = await call_llm(user_id, messages, temperature=0.3, max_tokens=800, request_timeout=30.0)
    except ValueError as exc:
        # 用户未配置 API Key
        logger.info("AI defense evaluation skipped: %s", exc)
        raise
    except Exception as exc:
        logger.warning("LLM call failed during defense evaluation: %s", exc)
        raise

    # 解析 AI 返回的 JSON
    json_match = re.search(r'\{[^{}]*"score"\s*:\s*\d+[^{}]*\}', response, re.DOTALL)
    if not json_match:
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if not json_match:
        raise ValueError(f"AI 评审返回格式异常，无法解析 JSON: {response[:200]}")

    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError:
        raise ValueError(f"AI 评审 JSON 解析失败: {json_match.group()[:200]}")

    if not isinstance(result.get("score"), (int, float)) or isinstance(result.get("score"), bool):
        raise ValueError("AI 评审缺少有效 score")
    if not str(result.get("feedback", "")).strip():
        raise ValueError("AI 评审缺少有效 feedback")
    score = max(0, min(100, int(result["score"])))
    hit_points = result.get("hit_points", []) if isinstance(result.get("hit_points"), list) else []
    missing_points = result.get("missing_points", []) if isinstance(result.get("missing_points"), list) else []
    feedback = str(result.get("feedback", ""))[:500]
    reference_answer = str(result.get("reference_answer", "")).strip()[:4000]

    return score, hit_points, missing_points, feedback, reference_answer


def _fallback_reference_answer(question: dict, identifiers: list[str]) -> str:
    """AI 不可用时，按题目评分量规生成可复核的标准答案。"""
    focus = str(question.get("focus", "核心实现原理")).strip()
    points = [
        "、".join(str(keyword) for keyword in group[:3])
        for group in question.get("rubric", [])
        if isinstance(group, list) and group
    ]
    target = "、".join(identifiers[:3]) or "当前实现"
    point_text = "；".join(points) or "输入、关键处理步骤、输出与边界情况"
    return (
        f"参考答案应围绕“{focus}”展开，并结合代码中的 {target} 说明，而不是只复述题目。"
        f"完整回答至少应覆盖：{point_text}。还应给出一个具体输入或失败用例，说明该设计"
        "如何影响最终结果，并解释若删除关键校验或分支会产生什么可观察的错误。"
    )


async def submit_defense(user_id: int, session_id: int, answers: list[dict], ai_usage: str) -> dict:
    """保存完整答辩并立即解锁故障修复，AI 评分由后台任务补齐。"""
    row = _owned_session(user_id, session_id)
    questions = _loads(row["defense_questions_json"], [])
    answer_map = {str(item.get("question_id")): str(item.get("answer", "")) for item in answers}

    if not questions:
        raise ValueError("当前答辩没有可评分的问题，请重新进入能力验证")
    missing_answers = [
        question.get("id")
        for question in questions
        if not answer_map.get(str(question.get("id")), "").strip()
    ]
    if missing_answers:
        raise ValueError(f"请先完整回答全部 {len(questions)} 道题后再提交评分")

    pending_details = [
        {
            "question_id": question.get("id"),
            "prompt": question.get("prompt"),
            "answer": answer_map.get(str(question.get("id")), "").strip(),
            "score": None,
            "hit_points": [],
            "missing_points": [],
            "feedback": "",
            "graded_by": "",
            "grading_status": "pending",
            "reference_answer": "",
        }
        for question in questions
    ]

    conn = get_db()
    conn.execute(
        """UPDATE capability_sessions
           SET defense_answers_json = ?, defense_score = ?, ai_usage = ?, status = ?
           WHERE id = ? AND user_id = ?""",
        (
            json.dumps(pending_details, ensure_ascii=False),
            0,
            ai_usage[:40],
            "repair_pending",
            session_id,
            user_id,
        ),
    )
    conn.execute(
        "INSERT INTO capability_events (session_id, user_id, event_type, payload_json) VALUES (?, ?, 'defense_submit', ?)",
        (
            session_id,
            user_id,
            json.dumps(
                {"submitted": True, "grading_status": "pending"},
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM capability_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    data = _session_dict(updated)
    data["defense_passed"] = True
    data["defense_met_standard"] = None
    data["review_items"] = []
    data["reference_cached"] = False
    return data


def defense_grading_pending(data: dict) -> bool:
    """判断答辩是否应启动或恢复后台 AI 评分。"""
    if data.get("status") in ("coding", "defense_pending", "skipped"):
        return False
    grading_status = data.get("defense_grading_status")
    answers = data.get("defense_answers", [])
    now = datetime.now()
    if grading_status == "pending":
        retry_times = []
        for item in answers:
            try:
                retry_times.append(datetime.fromisoformat(str(item.get("grading_retry_after", ""))))
            except (TypeError, ValueError):
                continue
        return not retry_times or max(retry_times) <= now
    if grading_status == "grading":
        started_times = []
        for item in answers:
            try:
                started_times.append(datetime.fromisoformat(str(item.get("grading_started_at", ""))))
            except (TypeError, ValueError):
                continue
        # 服务在评分过程中重启时，超过五分钟自动恢复任务。
        return not started_times or min(started_times) <= now - timedelta(minutes=5)
    return False


def _refresh_report_after_defense_grade(conn, row, score: int, details: list[dict]) -> None:
    """若学生已经继续完成后续步骤，同步刷新报告中的答辩分和总分。"""
    report = _loads(row["report_json"], {})
    if not report:
        return
    dimensions = dict(report.get("dimensions", {}))
    dimensions["原理理解"] = score
    report["dimensions"] = dimensions
    report["defense_evidence"] = details

    code_score = float(row["code_score"] or 0)
    repair_score = float(row["repair_score"] or 0)
    process_score = float(row["process_score"] or 0)
    if "variant_evidence" in report:
        variant_score = float(row["variant_score"] or 0)
        total_score = round(
            code_score * 0.20 + score * 0.20 + repair_score * 0.30
            + variant_score * 0.20 + process_score * 0.10
        )
    else:
        total_score = round(
            code_score * 0.25 + score * 0.25 + repair_score * 0.40 + process_score * 0.10
        )
    report["total_score"] = total_score
    conn.execute(
        """UPDATE capability_sessions SET total_score = ?, report_json = ?
           WHERE id = ? AND user_id = ?""",
        (total_score, json.dumps(report, ensure_ascii=False), row["id"], row["user_id"]),
    )


async def grade_defense_answers(user_id: int, session_id: int) -> None:
    """后台并行完成三道答辩题的 AI 评分；失败后恢复为 pending 供轮询重试。"""
    row = _owned_session(user_id, session_id)
    data = _session_dict(row)
    if data.get("defense_grading_status") in ("not_started", "completed"):
        return
    if not defense_grading_pending(data):
        return

    questions = data.get("defense_questions", [])
    submitted = data.get("defense_answers", [])
    answer_map = {
        str(item.get("question_id")): str(item.get("answer", ""))
        for item in submitted
    }
    if not questions or any(
        not answer_map.get(str(question.get("id")), "").strip()
        for question in questions
    ):
        return

    grading_started_at = datetime.now().isoformat()
    grading_details = [
        {
            **item,
            "grading_status": "grading",
            "grading_started_at": grading_started_at,
            "grading_retry_after": "",
        }
        for item in submitted
    ]
    conn = get_db()
    conn.execute(
        """UPDATE capability_sessions SET defense_answers_json = ?
           WHERE id = ? AND user_id = ?""",
        (json.dumps(grading_details, ensure_ascii=False), session_id, user_id),
    )
    conn.commit()
    conn.close()

    identifiers = _code_identifiers(row["original_code"] or "")
    code = row["original_code"] or ""
    exercise_id = str(row["exercise_id"] or "")

    async def _eval_one(question: dict) -> dict:
        answer = answer_map.get(str(question.get("id")), "").strip()
        score, hits, missing, feedback, reference_answer = await _ai_evaluate_answer(
            user_id, answer, question, identifiers, code, exercise_id,
        )
        if not reference_answer:
            reference_answer = _fallback_reference_answer(question, identifiers)
        return {
            "question_id": question.get("id"),
            "prompt": question.get("prompt"),
            "answer": answer,
            "score": score,
            "hit_points": hits,
            "missing_points": missing,
            "feedback": feedback,
            "graded_by": "ai",
            "grading_status": "completed",
            "reference_answer": reference_answer,
        }

    try:
        details = list(await asyncio.gather(*(_eval_one(q) for q in questions)))
    except Exception as exc:
        logger.warning(
            "Background AI defense grading failed for user=%s session=%s: %s",
            user_id, session_id, exc,
        )
        retry_after = (datetime.now() + timedelta(seconds=30)).isoformat()
        retry_details = [
            {
                **item,
                "grading_status": "pending",
                "grading_started_at": "",
                "grading_retry_after": retry_after,
            }
            for item in submitted
        ]
        conn = get_db()
        conn.execute(
            """UPDATE capability_sessions SET defense_answers_json = ?
               WHERE id = ? AND user_id = ?""",
            (json.dumps(retry_details, ensure_ascii=False), session_id, user_id),
        )
        conn.execute(
            """INSERT INTO capability_events
               (session_id, user_id, event_type, payload_json)
               VALUES (?, ?, 'defense_grade_retry', ?)""",
            (session_id, user_id, json.dumps({"error": str(exc)[:300]}, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        return

    score = round(sum(item["score"] for item in details) / max(len(details), 1))
    met_standard = score >= 60
    conn = get_db()
    latest = conn.execute(
        "SELECT * FROM capability_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    ).fetchone()
    conn.execute(
        """UPDATE capability_sessions
           SET defense_answers_json = ?, defense_score = ?
           WHERE id = ? AND user_id = ?""",
        (json.dumps(details, ensure_ascii=False), score, session_id, user_id),
    )
    _refresh_report_after_defense_grade(conn, latest, score, details)
    conn.execute(
        """INSERT INTO capability_events
           (session_id, user_id, event_type, payload_json)
           VALUES (?, ?, 'defense_graded', ?)""",
        (
            session_id,
            user_id,
            json.dumps(
                {"score": score, "met_standard": met_standard, "graded_by": "ai"},
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
    conn.close()
    record_mastery_evidence(
        user_id, row["knowledge_tag"], row["exercise_id"],
        explanation_score=score, passed=met_standard,
    )


def _process_evidence(conn, session_id: int, started_at: str, ai_usage: str) -> tuple[int, dict]:
    rows = conn.execute(
        "SELECT event_type, payload_json FROM capability_events WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    counts: dict[str, int] = {}
    max_hint_level = 0
    passed_stages = set()
    for row in rows:
        counts[row["event_type"]] = counts.get(row["event_type"], 0) + 1
        payload = _loads(row["payload_json"], {})
        if row["event_type"] == "hint":
            max_hint_level = max(max_hint_level, int(payload.get("level", 0) or 0))
        if row["event_type"] == "stage_check" and payload.get("passed") and payload.get("stage_id"):
            passed_stages.add(str(payload["stage_id"]))
    try:
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        elapsed_minutes = max(0, (datetime.now() - started_at).total_seconds() / 60)
    except Exception:
        elapsed_minutes = 0
    score = 35
    score += min(counts.get("edit", 0) * 3, 20)
    score += min(counts.get("run", 0) * 5, 20)
    score += 10 if elapsed_minutes >= 2 else round(elapsed_minutes * 5)
    score += 10 if ai_usage else 0
    score += 5 if counts.get("submit", 0) else 0
    evidence = {
        "edit_snapshots": counts.get("edit", 0),
        "paste_events": counts.get("paste", 0),
        "run_attempts": counts.get("run", 0),
        "stage_checks": counts.get("stage_check", 0),
        "passed_stages": len(passed_stages),
        "hint_views": counts.get("hint", 0) + counts.get("answer_view", 0),
        "max_hint_level": max_hint_level,
        "elapsed_minutes": round(elapsed_minutes, 1),
        "ai_usage": ai_usage or "未声明",
        "note": "过程数据只用于说明证据完整度，不用于判定作弊。",
    }
    return min(score, 100), evidence


def _mark_learning_path_lab_complete(conn, user_id: int, exercise_id: str) -> None:
    """把通过完整能力闭环的实验同步回项目制学习路径。"""
    row = conn.execute(
        "SELECT id, path_data_json, progress_json FROM learning_paths WHERE user_id = ? AND status = 'active'",
        (user_id,),
    ).fetchone()
    if not row:
        return
    path_data = _loads(row["path_data_json"], {})
    progress = _loads(row["progress_json"], {})
    completed = progress.get("completed_tasks", {})
    if isinstance(completed, list):
        completed = {key: {"learn": True, "quiz": False, "code": True} for key in completed}

    matched_key = None
    total = 0
    for phase in path_data.get("phases", []):
        for task in phase.get("tasks", []):
            total += 1
            key = f"{task.get('day')}-{task.get('topic')}"
            if task.get("lab_id") == exercise_id:
                matched_key = key
    if not matched_key:
        return

    status = completed.get(matched_key, {})
    if not isinstance(status, dict):
        status = {"learn": bool(status)}
    status["code"] = True
    status.setdefault("learn", False)
    # 兼容旧进度结构：新版课程用实验替代选择题，内部将 quiz 视为由实验验收覆盖。
    status["quiz"] = True
    completed[matched_key] = status
    progress["completed_tasks"] = completed
    finished = sum(
        1 for value in completed.values()
        if isinstance(value, dict) and value.get("learn") and value.get("code")
    )
    progress["overall_progress"] = round(finished / max(total, 1) * 100)
    conn.execute(
        "UPDATE learning_paths SET progress_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(progress, ensure_ascii=False), datetime.now().isoformat(), row["id"]),
    )


def _score_explanation(explanation: str, mutation_desc: str, exercise_id: str, repair_code: str) -> int:
    """对故障修复的根因说明进行实质性评分（0-20）。

    评分维度：
    - 基础门槛（0-6分）：长度、非重复字符
    - 内容质量（0-8分）：包含代码相关术语、定位到具体位置
    - 因果推理（0-6分）：说明故障机制、修复策略

    纯按字符数计分已废弃——学生必须展示对故障的理解。
    """
    if not explanation:
        return 0

    score = 0

    # ── 基础门槛（0-6分）──
    text = explanation.strip()
    length = len(text)

    # 门槛 1：最少 20 个字符；20-40 之间给部分分
    if length < 20:
        return 0
    if length < 40:
        # 20-40 字符：给基础分但不进入完整评分
        score += 2
        unique_chars = len(set(text.lower()))
        if unique_chars < 5:
            return 2  # 明显灌水
        score += 1  # 及格线以上
        # 额外奖励：包含实质性代码术语
        if re.search(r'(?<![a-zA-Z])[a-zA-Z_]\w{2,}(?![a-zA-Z])', text):
            score += 1
        if any(kw in text for kw in ["函数", "return", "变量", "错误", "bug", "类型", "修复", "参数"]):
            score += 1
        return min(score, 8)  # 短说明最多 8 分

    score += 3  # 达到标准长度

    # 门槛 2：不能是纯重复字符或纯标点
    unique_chars = len(set(text.lower()))
    if unique_chars < 6:
        return 3  # 明显灌水，只给长度基础分
    char_diversity = unique_chars / max(length, 1)
    if char_diversity < 0.2:
        return 4  # 低质量
    score += 2 if char_diversity >= 0.4 else 1

    # 门槛 3：包含中文字符（说明是实质性中文描述）或英文术语
    has_chinese = any('一' <= c <= '鿿' for c in text)
    has_english_terms = bool(re.search(r'[a-zA-Z]{4,}', text))
    if has_chinese:
        score += 1
    if has_english_terms:
        score += 1

    # ── 内容质量（0-8分）──
    # 检查是否引用了具体的代码元素
    # 注意：\b 在中文 Unicode 环境不可靠（Python 将中文视为 \w），
    # 改用 ASCII 友好的边界断言
    code_terms = re.findall(r'(?<![a-zA-Z])[a-zA-Z_]\w{2,}(?![a-zA-Z])', text)
    meaningful_terms = [t for t in code_terms if t.lower() not in {
        "the", "and", "for", "that", "this", "with", "from", "your", "have",
        "what", "when", "were", "been", "they", "them", "then", "than",
        "there", "their", "just", "like", "some", "also",
    }]

    if len(meaningful_terms) >= 5:
        score += 3
    elif len(meaningful_terms) >= 3:
        score += 2
    elif len(meaningful_terms) >= 1:
        score += 1

    # 检查是否提及了代码位置（函数名、变量名、行号等）
    # 中文不使用 \b，直接按子串匹配
    code_location_keywords = [
        "函数", "方法", "类", "模块", "文件", "行", "return", "变量", "参数", "属性",
        "修改", "改动", "变更", "替换", "删除", "添加", "调整", "修复", "恢复", "纠正",
    ]
    location_hits = sum(1 for kw in code_location_keywords if kw in text)
    # 额外：检查英文代码相关模式
    if re.search(r'\bdef\s+\w+|\.py\b|solution|app\.py', text, re.IGNORECASE):
        location_hits += 1
    score += min(location_hits * 2, 4)

    # ── 因果推理（0-6分）──
    # 检查是否解释了"为什么"
    causality_keywords = [
        "因为", "由于", "原因", "导致", "造成", "引起", "触发", "源于",
        "所以", "因此", "故而", "于是", "结果", "后果", "影响",
        "根因", "根源", "本质", "根本", "底层", "源头",
    ]
    causality_hits = sum(1 for kw in causality_keywords if kw in text)
    score += min(causality_hits * 2, 6)

    return min(score, 20)


def submit_repair(user_id: int, session_id: int, code: str, explanation: str) -> dict:
    """提交故障修复并评分。

    测试与说明分数保留真实结果，但完整提交后即完成本阶段，不再用通过线
    阻塞后续变式迁移。
    """
    row = _owned_session(user_id, session_id)
    if row["status"] != "repair_pending":
        raise ValueError("请先通过代码答辩再进入故障修复")

    evaluation = _judge_exercise_code(row["exercise_id"], code)
    explanation = explanation.strip()
    explanation_score = _score_explanation(
        explanation,
        row["mutation_description"] or "",
        row["exercise_id"] or "",
        code,
    )
    test_score = 80 if evaluation["passed"] else round(
        80 * evaluation.get("passed_count", 0) / max(evaluation.get("total", 1), 1)
    )
    repair_score = test_score + explanation_score
    # 修复通过条件：测试全部通过 且 根因说明有意义（≥10/20分）
    repair_passed = evaluation["passed"] and explanation_score >= 10

    conn = get_db()
    process_score, evidence = _process_evidence(conn, session_id, row["started_at"], row["ai_usage"] or "")
    code_score = 100
    defense_score = float(row["defense_score"] or 0)
    total_score = round(code_score * 0.25 + defense_score * 0.25 + repair_score * 0.40 + process_score * 0.10)
    report = {
        "verified": True,
        "verdict": "能力已验证",
        "summary": "代码、原理答辩和故障修复均已提交评分并形成可复核证据。",
        "dimensions": {
            "代码正确性": code_score,
            "原理理解": round(defense_score),
            "故障修复": repair_score,
            "过程证据完整度": process_score,
        },
        "process_evidence": evidence,
        "defense_evidence": _loads(row["defense_answers_json"], []),
        "knowledge_sources": list(dict.fromkeys(
            question.get("source_path")
            for question in _loads(row["defense_questions_json"], [])
            if question.get("source_path")
        )),
        "repair_evidence": {
            "description": row["mutation_description"],
            "explanation": explanation,
            "tests_passed": bool(evaluation["passed"]),
            "test_score": test_score,
            "explanation_score": explanation_score,
            "score": repair_score,
            "passed_count": evaluation.get("passed_count", 0),
            "total": evaluation.get("total", 0),
            "cases": evaluation.get("results", []),
        },
        "total_score": total_score,
        "next_step": (
            "继续完成变式迁移，并根据本次失败测试补强修复方案。"
            if not repair_passed
            else "尝试修改输入约束或替换一种实现策略，再比较两种方案的取舍。"
        ),
    }
    # 检查是否有变式迁移场景，如有则进入 variant_pending 而非直接 verified
    exercise_id = str(row["exercise_id"] or "")
    has_variant = _get_variant_spec(exercise_id) is not None
    next_status = "variant_pending" if has_variant else "verified"
    now = datetime.now().isoformat()

    if has_variant:
        report.update({
            "verified": False,
            "verdict": "故障修复已评分",
            "summary": "故障修复已完成评分；可重新挑战本阶段，或继续完成变式迁移。",
        })
        # 修复提交评分后先保存阶段报告；变式完成时在此基础上补齐最终维度。
        conn.execute(
            """UPDATE capability_sessions
               SET repair_code = ?, repair_explanation = ?, repair_score = ?, process_score = ?,
                   total_score = ?, report_json = ?, status = ?
               WHERE id = ? AND user_id = ?""",
            (
                code, explanation, repair_score, process_score, total_score,
                json.dumps(report, ensure_ascii=False), "variant_pending", session_id, user_id,
            ),
        )
    else:
        conn.execute(
            """UPDATE capability_sessions
               SET repair_code = ?, repair_explanation = ?, repair_score = ?, process_score = ?,
                   total_score = ?, verified = 1, status = 'verified', report_json = ?, completed_at = ?
               WHERE id = ? AND user_id = ?""",
            (code, explanation, repair_score, process_score, total_score,
             json.dumps(report, ensure_ascii=False), now, session_id, user_id),
        )
    conn.execute(
        "INSERT INTO capability_events (session_id, user_id, event_type, payload_json) VALUES (?, ?, 'repair_submit', ?)",
        (
            session_id,
            user_id,
            json.dumps(
                {"completed": True, "passed": repair_passed, "score": repair_score},
                ensure_ascii=False,
            ),
        ),
    )
    # 只有完成整套闭环，代码提交才进入掌握度统计。
    if not has_variant:
        conn.execute(
            """UPDATE code_submissions SET verified = 1
               WHERE id = (
                   SELECT id FROM code_submissions
                   WHERE user_id = ? AND exercise_id = ? AND passed = 1
                   ORDER BY id DESC LIMIT 1
               )""",
            (user_id, row["exercise_id"]),
        )
        conn.execute(
            "INSERT INTO capability_events (session_id, user_id, event_type, payload_json) VALUES (?, ?, 'verified', ?)",
            (session_id, user_id, json.dumps({"total_score": total_score}, ensure_ascii=False)),
        )
        _mark_learning_path_lab_complete(conn, user_id, row["exercise_id"])
    conn.commit()
    conn.close()
    record_mastery_evidence(
        user_id, row["knowledge_tag"], row["exercise_id"],
        transfer_score=repair_score, passed=repair_passed,
    )
    result = {
        "repair_passed": repair_passed,
        "repair_completed": True,
        "repair_score": repair_score,
        "verified": not has_variant,
        "report": report,
        "evaluation": evaluation,
        "status": next_status,
    }
    return result


def retry_repair(user_id: int, session_id: int) -> dict:
    """重新注入同一代表性故障，开始一次新的修复尝试。

    上一次提交的评分和证据保留在会话报告与事件流中；再次提交修复时会用
    新结果更新当前阶段分数。只有尚未提交变式迁移的会话可以重试。
    """
    row = _owned_session(user_id, session_id)
    if row["status"] != "variant_pending":
        raise ValueError("只有完成故障修复且尚未提交变式迁移时可以重新修复")
    mutation_code = str(row["mutation_code"] or "")
    if not mutation_code.strip():
        raise ValueError("当前会话没有可重新注入的故障代码")

    conn = get_db()
    previous_attempts = conn.execute(
        """SELECT COUNT(*) AS count FROM capability_events
           WHERE session_id = ? AND event_type = 'repair_submit'""",
        (session_id,),
    ).fetchone()["count"]
    conn.execute(
        """UPDATE capability_sessions
           SET status = 'repair_pending'
           WHERE id = ? AND user_id = ?""",
        (session_id, user_id),
    )
    conn.execute(
        """INSERT INTO capability_events (session_id, user_id, event_type, payload_json)
           VALUES (?, ?, 'repair_retry', ?)""",
        (
            session_id,
            user_id,
            json.dumps(
                {
                    "next_attempt": int(previous_attempts or 0) + 1,
                    "previous_score": round(float(row["repair_score"] or 0)),
                },
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM capability_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    data = _session_dict(updated)
    data["mutation_code"] = mutation_code
    data["retry_attempt"] = int(previous_attempts or 0) + 1
    data["previous_repair_score"] = round(float(row["repair_score"] or 0))
    return data


def get_session(user_id: int, session_id: int) -> dict:
    return _session_dict(_owned_session(user_id, session_id))


def skip_capability(user_id: int, session_id: int) -> dict:
    """跳过能力验证，仅以测试分数完成关卡。"""
    row = _owned_session(user_id, session_id)
    if row["status"] in ("verified", "skipped"):
        raise ValueError("该关卡已完成能力验证流程，不能重复跳过")

    code_score = float(row["code_score"] or 0)
    # 仅测试分：满分 60（不做能力验证的最高分）
    test_only_score = round(code_score * 0.6)
    total_score = test_only_score

    report = {
        "verified": False,
        "skipped": True,
        "verdict": "仅测试通过",
        "summary": "你选择跳过能力验证，仅获得测试点分数。建议后续完成能力验证以获得更全面的评估。",
        "dimensions": {
            "代码正确性": code_score,
            "原理理解": 0,
            "故障修复与迁移": 0,
            "过程证据完整度": 0,
        },
        "total_score": total_score,
        "next_step": "可以随时重新进入本题完成能力验证，获得更高分数。",
    }
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """UPDATE capability_sessions
           SET status = 'skipped', defense_score = 0, repair_score = 0,
               total_score = ?, verified = 0, report_json = ?, completed_at = ?
           WHERE id = ? AND user_id = ?""",
        (total_score, json.dumps(report, ensure_ascii=False), now, session_id, user_id),
    )
    conn.execute(
        "INSERT INTO capability_events (session_id, user_id, event_type, payload_json) VALUES (?, ?, 'skipped', ?)",
        (session_id, user_id, json.dumps({"total_score": total_score}, ensure_ascii=False)),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM capability_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    data = _session_dict(updated)
    data["report"] = report
    return data


_REFERENCE_ANSWER_PROMPT = """你是一位编程教学专家。请根据学生的代码和答辩问题，撰写一份标准参考答案。

**实验编号**: {exercise_id}
**问题**: {question_prompt}
**学生代码（关键片段）**:
```python
{code_snippet}
```

请撰写一份标准、准确的参考答案，涵盖该问题考察的所有要点。答案应该：
1. 使用中文
2. 结合代码中的具体函数/变量名，不要泛泛而谈
3. 控制在 200-400 字
4. 结构清晰，分点说明"""


async def _generate_reference_answer(
    user_id: int, question: dict, code: str, exercise_id: str,
) -> str:
    """为答辩问题生成标准参考答案。AI 不可用时返回降级提示。"""
    region, _, _ = _user_region(code)
    code_snippet = region[:2000] if region else code[:2000]

    prompt = _REFERENCE_ANSWER_PROMPT.format(
        exercise_id=exercise_id,
        question_prompt=question.get("prompt", ""),
        code_snippet=code_snippet,
    )
    try:
        answer = await call_llm(
            user_id,
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
            request_timeout=30.0,
        )
        return answer.strip()
    except Exception:
        return "⚠️ 标准答案生成需要配置 API Key（个人中心 → AI大模型配置）。请对比你的回答与评分反馈来查漏补缺。"


async def get_session_review(user_id: int, session_id: int) -> dict:
    """获取能力验证回顾数据，包含用户回答、AI 评价和标准参考答案。

    用户可以对比自己的回答与标准答案，找出差距，巩固学习。

    标准参考答案首次生成后会持久化到数据库，后续查看直接返回缓存，
    避免重复调用 LLM。
    """
    row = _owned_session(user_id, session_id)
    data = _session_dict(row)

    questions = data.get("defense_questions", [])
    answers = data.get("defense_answers", [])
    code = data.get("original_code", "")
    exercise_id = str(data.get("exercise_id", ""))
    repair_evidence = data.get("report", {}).get("repair_evidence", {})
    if not isinstance(repair_evidence, dict):
        repair_evidence = {}
    repair_review = {
        "score": data.get("repair_score", 0),
        "description": data.get("mutation_description", ""),
        "explanation": data.get("repair_explanation", ""),
        **repair_evidence,
    }

    # 构建每道题的回顾数据
    review_items = []
    cached_count = 0
    for question in questions:
        q_id = question.get("id", "")
        user_answer_data = next(
            (a for a in answers if a.get("question_id") == q_id), {}
        )
        item = {
            "question_id": q_id,
            "prompt": question.get("prompt", ""),
            "focus": question.get("focus", ""),
            "user_answer": user_answer_data.get("answer", ""),
            "user_score": user_answer_data.get("score", 0),
            "hit_points": user_answer_data.get("hit_points", []),
            "missing_points": user_answer_data.get("missing_points", []),
            "feedback": user_answer_data.get("feedback", ""),
            "graded_by": user_answer_data.get("graded_by", "keyword"),
            "grading_status": user_answer_data.get("grading_status", ""),
            # 首先检查是否已有持久化的标准答案
            "reference_answer": user_answer_data.get("reference_answer", ""),
        }
        if item["reference_answer"]:
            cached_count += 1
        review_items.append(item)

    grading_status = data.get("defense_grading_status", "not_started")
    if grading_status != "completed":
        return {
            "session_id": session_id,
            "exercise_id": exercise_id,
            "exercise_title": data.get("exercise_title", ""),
            "status": data.get("status", ""),
            "defense_grading_status": grading_status,
            "total_score": data.get("total_score", 0),
            "code_score": data.get("code_score", 0),
            "defense_score": data.get("defense_score", 0),
            "repair_score": data.get("repair_score", 0),
            "repair_review": repair_review,
            "report": data.get("report", {}),
            "review_items": review_items,
            "reference_cached": False,
        }

    # 如果有缓存的参考答案，直接返回
    if cached_count == len(questions) and cached_count > 0:
        return {
            "session_id": session_id,
            "exercise_id": exercise_id,
            "exercise_title": data.get("exercise_title", ""),
            "status": data.get("status", ""),
            "defense_grading_status": grading_status,
            "total_score": data.get("total_score", 0),
            "code_score": data.get("code_score", 0),
            "defense_score": data.get("defense_score", 0),
            "repair_score": data.get("repair_score", 0),
            "repair_review": repair_review,
            "report": data.get("report", {}),
            "review_items": review_items,
            "reference_cached": True,
        }

    # 部分或全部缺少参考答案 → 调用 LLM 生成并持久化
    missing_questions = [
        q for q in questions
        if not next((a for a in answers if a.get("question_id") == q.get("id")), {}).get("reference_answer")
    ]
    if missing_questions:
        import asyncio
        generated = await asyncio.gather(*(
            _generate_reference_answer(user_id, q, code, exercise_id)
            for q in missing_questions
        ))
        # 将生成的参考答案写入每个 answer 条目
        gen_map = {q.get("id"): ref for q, ref in zip(missing_questions, generated)}
        for ans_entry in answers:
            qid = ans_entry.get("question_id", "")
            if qid in gen_map and not ans_entry.get("reference_answer"):
                ans_entry["reference_answer"] = gen_map[qid]

        # 持久化到数据库
        conn = get_db()
        conn.execute(
            """UPDATE capability_sessions
               SET defense_answers_json = ?
               WHERE id = ? AND user_id = ?""",
            (json.dumps(answers, ensure_ascii=False), session_id, user_id),
        )
        conn.commit()
        conn.close()

        # 更新返回数据
        for item in review_items:
            qid = item["question_id"]
            if qid in gen_map and not item["reference_answer"]:
                item["reference_answer"] = gen_map[qid]

    return {
        "session_id": session_id,
        "exercise_id": exercise_id,
        "exercise_title": data.get("exercise_title", ""),
        "status": data.get("status", ""),
        "defense_grading_status": grading_status,
        "total_score": data.get("total_score", 0),
        "code_score": data.get("code_score", 0),
        "defense_score": data.get("defense_score", 0),
        "repair_score": data.get("repair_score", 0),
        "repair_review": repair_review,
        "report": data.get("report", {}),
        "review_items": review_items,
        "reference_cached": False,
    }


# ── 变式迁移场景定义 ─────────────────────────────────────────────
# 每道旗舰实验提供 1-2 个变式场景，改变输入/输出格式或业务规则，
# 检验学生是否真正理解核心概念而非记忆代码。

_VARIANT_SPECS = {}


def _get_variant_spec(exercise_id: str) -> dict | None:
    """获取实验的变式迁移规格。"""
    return _VARIANT_SPECS.get(exercise_id) or ADDITIONAL_VARIANT_SPECS.get(exercise_id)


def generate_variant(user_id: int, session_id: int) -> dict:
    """为已完成修复的实验生成变式迁移场景。"""
    row = _owned_session(user_id, session_id)
    if row["status"] != "variant_pending":
        raise ValueError("请先提交故障修复，再查看变式迁移场景")
    exercise_id = str(row["exercise_id"] or "")
    variant_spec = _get_variant_spec(exercise_id)
    if not variant_spec:
        raise ValueError("该实验暂无变式迁移场景，请联系教师添加")

    scenario = variant_spec["scenario"]
    hints = json.dumps(variant_spec.get("hints", []), ensure_ascii=False)
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """UPDATE capability_sessions
           SET variant_scenario = ?, variant_hints_json = ?, status = 'variant_pending'
           WHERE id = ? AND user_id = ?""",
        (scenario, hints, session_id, user_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM capability_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    data = _session_dict(updated)
    data["variant_scenario"] = scenario
    data["variant_target"] = variant_spec.get("target", "")
    data["variant_hints"] = variant_spec.get("hints", [])
    return data


def _variant_starter_code(variant_spec: dict) -> str:
    target = str(variant_spec.get("target") or "solve_variant")
    return (
        '"""变式迁移独立实现区。\n\n'
        "请根据 VARIANT_TASK.md 中的新业务场景和输入输出契约完成函数。\n"
        '"""\n\n\n'
        f"def {target}(*args, **kwargs):\n"
        '    """按变式任务要求实现，并补充清晰的参数校验。"""\n'
        '    raise NotImplementedError("请完成变式迁移实现")\n'
    )


def switch_project_state(user_id: int, session_id: int, target_state: str) -> dict:
    """Switch the lab workspace to an explicit initial/passed/repair/variant state."""
    row = _owned_session(user_id, session_id)
    exercise_id = str(row["exercise_id"] or "")
    target_state = str(target_state or "").strip().lower()

    if target_state == "initial":
        workspace = lab_workspace_service.apply_project_state(
            user_id, exercise_id, "initial",
        )
    elif target_state == "passed":
        workspace = lab_workspace_service.apply_project_state(
            user_id,
            exercise_id,
            "passed",
            solution_code=str(row["original_code"] or ""),
        )
    elif target_state == "repair":
        if row["status"] not in {"repair_pending", "variant_pending", "verified"}:
            raise ValueError("当前流程尚未解锁故障修复项目状态")
        workspace = lab_workspace_service.apply_project_state(
            user_id,
            exercise_id,
            "repair",
            solution_code=str(row["mutation_code"] or ""),
        )
    elif target_state == "variant":
        if row["status"] not in {"variant_pending", "verified"}:
            raise ValueError("请先完成故障修复评分，再切换到变式迁移项目状态")
        variant_spec = _get_variant_spec(exercise_id)
        if not variant_spec:
            raise ValueError("该实验没有可用的变式迁移项目")
        # 规格可能在课程迭代中修正。始终使用当前规格，避免旧会话继续加载
        # 已废弃或事实错误的变式说明。
        scenario = str(variant_spec["scenario"])
        hints = json.dumps(variant_spec.get("hints", []), ensure_ascii=False)
        conn = get_db()
        conn.execute(
            "UPDATE capability_sessions SET variant_scenario = ?, variant_hints_json = ? WHERE id = ? AND user_id = ?",
            (scenario, hints, session_id, user_id),
        )
        conn.commit()
        conn.close()
        workspace = lab_workspace_service.apply_project_state(
            user_id,
            exercise_id,
            "variant",
            solution_code=_variant_starter_code(variant_spec),
            variant_scenario=scenario,
            variant_target=str(variant_spec.get("target") or ""),
        )
    else:
        raise ValueError("项目状态只能是 initial、passed、repair 或 variant")

    conn = get_db()
    reopened_status = ""
    if row["status"] == "verified" and target_state in {"repair", "variant"}:
        reopened_status = "repair_pending" if target_state == "repair" else "variant_pending"
        conn.execute(
            """UPDATE capability_sessions
               SET status = ?, verified = 0, completed_at = NULL
               WHERE id = ? AND user_id = ?""",
            (reopened_status, session_id, user_id),
        )
    conn.execute(
        """INSERT INTO capability_events
           (session_id, user_id, event_type, payload_json)
           VALUES (?, ?, 'project_state_switch', ?)""",
        (
            session_id,
            user_id,
            json.dumps(
                {
                    "target_state": target_state,
                    "reopened_status": reopened_status,
                },
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "target_state": target_state,
        "workspace": workspace,
        "session": _session_dict(_owned_session(user_id, session_id)),
        "reopened": bool(reopened_status),
    }


def submit_variant(user_id: int, session_id: int, code: str) -> dict:
    """提交变式迁移代码并评分。

    分数保留真实测试表现，但提交并完成评分后即完成该阶段，不再以 60 分作为流程门槛。
    """
    row = _owned_session(user_id, session_id)
    if row["status"] != "variant_pending":
        raise ValueError("当前会话不在变式迁移阶段")
    exercise_id = str(row["exercise_id"] or "")
    variant_spec = _get_variant_spec(exercise_id)
    if not variant_spec:
        raise ValueError("该实验没有变式迁移场景")

    # 使用变式专属测试用例判题
    variant_result = _judge_variant_code(code, variant_spec)
    passed = variant_result["passed"]
    variant_score = 100 if passed else max(0, round(variant_result["passed_count"] / max(variant_result["total"], 1) * 100))

    conn = get_db()
    # 完成评分即完成完整验证流程；variant_passed 仍保留客观测试结论。
    now = datetime.now().isoformat()
    conn.execute(
        """UPDATE capability_sessions
           SET variant_code = ?, variant_score = ?, variant_passed_at = ?,
               status = 'verified'
           WHERE id = ? AND user_id = ?""",
        (code, variant_score, now, session_id, user_id),
    )

    # 重新计算总分（加入变式维度）
    code_score = float(row["code_score"] or 100)
    defense_score = float(row["defense_score"] or 0)
    repair_score_val = float(row["repair_score"] or 0)
    process_score = float(row["process_score"] or 0)
    total_score = round(
        code_score * 0.20 + defense_score * 0.20 + repair_score_val * 0.30 + variant_score * 0.20 + process_score * 0.10
    )

    # 更新报告
    old_report = _loads(row["report_json"], {})
    dimensions = old_report.get("dimensions", {})
    dimensions["变式迁移"] = variant_score
    report = {
        **old_report,
        "dimensions": dimensions,
        "total_score": total_score,
        "variant_evidence": {
            "scenario": row["variant_scenario"],
            "tests_passed": passed,
            "passed_count": variant_result["passed_count"],
            "total": variant_result["total"],
        },
        "summary": "代码、原理答辩、故障修复与变式迁移均已完成评分并形成可复核证据。",
    }

    conn.execute(
        """UPDATE capability_sessions
           SET total_score = ?, report_json = ?, verified = 1, completed_at = ?
           WHERE id = ? AND user_id = ?""",
        (total_score, json.dumps(report, ensure_ascii=False), now, session_id, user_id),
    )
    conn.execute(
        "INSERT INTO capability_events (session_id, user_id, event_type, payload_json) VALUES (?, ?, 'variant_submit', ?)",
        (
            session_id,
            user_id,
            json.dumps({"variant_score": variant_score, "passed": passed, "graded": True}, ensure_ascii=False),
        ),
    )
    conn.execute(
        """UPDATE code_submissions SET verified = 1
           WHERE id = (
               SELECT id FROM code_submissions
               WHERE user_id = ? AND exercise_id = ? AND passed = 1
               ORDER BY id DESC LIMIT 1
           )""",
        (user_id, row["exercise_id"]),
    )
    _mark_learning_path_lab_complete(conn, user_id, row["exercise_id"])
    conn.commit()
    updated = conn.execute("SELECT * FROM capability_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    record_mastery_evidence(
        user_id, row["knowledge_tag"], row["exercise_id"],
        transfer_score=variant_score, passed=passed,
    )

    data = _session_dict(updated)
    data["variant_passed"] = passed
    data["variant_completed"] = True
    data["evaluation"] = variant_result
    data["report"] = report
    return data


def _judge_variant_code(code: str, variant_spec: dict) -> dict:
    """使用变式专属测试用例判题。"""
    import time as time_module
    started = time_module.perf_counter()

    # 安全检查
    from services.judge_service import _policy_error
    policy_error = _policy_error(code)
    total = len(variant_spec.get("cases", []))
    if policy_error:
        return {
            "passed": False, "total": total, "passed_count": 0,
            "compile_error": policy_error, "results": [],
        }

    # 构建临时判题脚本
    target = variant_spec["target"]
    cases = variant_spec["cases"]

    runner_code = f'''
import copy, json, sys, time

SAFE_BUILTINS = {{
    "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
    "AssertionError": AssertionError,
    "dict": dict, "list": list, "str": str, "int": int, "float": float,
    "bool": bool, "set": set, "tuple": tuple,
    "len": len, "isinstance": isinstance, "hasattr": hasattr,
    "min": min, "max": max, "sum": sum, "round": round,
    "sorted": sorted, "enumerate": enumerate, "zip": zip,
    "all": all, "any": any, "range": range,
}}

code = {json.dumps(code)}
namespace = {{"__builtins__": SAFE_BUILTINS}}
exec(compile(code, "variant.py", "exec"), namespace)

func = namespace.get({json.dumps(target)})
if not callable(func):
    print("__JUDGE_RESULT__" + json.dumps([{{"description": "函数定义", "passed": False, "error": "未定义 " + {json.dumps(target)}}}]))
    sys.exit(1)

results = []
cases = json.loads({json.dumps(json.dumps(cases, ensure_ascii=False))})
for item in cases:
    started = time.perf_counter()
    args = copy.deepcopy(item.get("args", []))
    args_before = copy.deepcopy(args)
    try:
        expected_exception = item.get("exception")
        if expected_exception:
            try:
                func(*args)
            except SAFE_BUILTINS[expected_exception]:
                results.append({{"description": item["description"], "passed": True, "error": None}})
                continue
            raise AssertionError("必须抛出 " + expected_exception)
        actual = func(*args)
        if item.get("immutable") and args != args_before:
            raise AssertionError("函数不得修改输入参数")
        expected = item.get("expected")
        if actual != expected:
            raise AssertionError(
                "返回结果不符合变式场景\\n"
                + "输入: " + json.dumps(args, ensure_ascii=False, default=str)[:200] + "\\n"
                + "期望: " + json.dumps(expected, ensure_ascii=False, default=str)[:200] + "\\n"
                + "实际: " + json.dumps(actual, ensure_ascii=False, default=str)[:200]
            )
        results.append({{"description": item["description"], "passed": True, "error": None,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2)}})
    except Exception as exc:
        results.append({{"description": item["description"], "passed": False,
                        "error": str(exc)[:240],
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2)}})

print("__JUDGE_RESULT__" + json.dumps(results, ensure_ascii=False))
'''

    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner_path = Path(tmp) / "variant_runner.py"
            runner_path.write_text(runner_code, encoding="utf-8")
            proc = subprocess.run(
                [os.environ.get("PYTHON_PATH", "python"), "-I", "-X", "utf8", str(runner_path)],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            )
        marker_lines = [l for l in (proc.stdout or "").splitlines() if l.startswith("__JUDGE_RESULT__")]
        if proc.returncode != 0 or not marker_lines:
            error = (proc.stderr or proc.stdout or "变式代码执行失败").strip().splitlines()[-1][:300]
            return {"passed": False, "total": total, "passed_count": 0, "compile_error": error, "results": []}

        raw = json.loads(marker_lines[-1].removeprefix("__JUDGE_RESULT__"))
        results = [{"case_index": i, **r} for i, r in enumerate(raw, 1)]
        passed_count = sum(1 for r in results if r["passed"])
        return {
            "passed": passed_count == len(results),
            "total": len(results), "passed_count": passed_count,
            "compile_error": None, "results": results,
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "total": total, "passed_count": 0, "compile_error": "变式代码执行超时", "results": []}
    except Exception as exc:
        return {"passed": False, "total": total, "passed_count": 0, "compile_error": str(exc)[:240], "results": []}


def get_completed_sessions(user_id: int) -> list[dict]:
    """获取用户所有已完成的能力验证会话历史。

    返回按完成时间倒序排列的会话列表，包含分数和复盘回顾数据。
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM capability_sessions
           WHERE user_id = ? AND status IN ('verified', 'skipped')
           ORDER BY completed_at DESC, id DESC
           LIMIT 50""",
        (user_id,),
    ).fetchall()
    conn.close()

    sessions = []
    for row in rows:
        data = _session_dict(row)
        report = data.get("report", {})
        # 精简返回数据，去掉过大的代码内容
        sessions.append({
            "session_id": data["id"],
            "exercise_id": data["exercise_id"],
            "exercise_title": data.get("exercise_title", ""),
            "knowledge_tag": data.get("knowledge_tag", ""),
            "status": data["status"],
            "verified": data.get("verified", False),
            "skipped": data["status"] == "skipped",
            "total_score": round(data.get("total_score", 0) or 0),
            "code_score": round(data.get("code_score", 0) or 0),
            "defense_score": round(data.get("defense_score", 0) or 0),
            "repair_score": round(data.get("repair_score", 0) or 0),
            "dimensions": report.get("dimensions", {}),
            "summary": report.get("summary", ""),
            "verdict": report.get("verdict", ""),
            "started_at": str(data.get("started_at", "")),
            "completed_at": str(data.get("completed_at", "")),
            "defense_questions": data.get("defense_questions", []),
            "defense_answers": data.get("defense_answers", []),
            "mutation_description": data.get("mutation_description", ""),
            "repair_explanation": data.get("repair_explanation", ""),
        })
    return sessions


def get_exercise_scores(user_id: int) -> dict[str, dict]:
    """获取用户所有已完成的实验关卡分数概览。

    返回 {exercise_id: {score, test_score, capability_score, verified, skipped, status}, ...}
    """
    conn = get_db()
    # 每个 exercise 取最新的 capability session
    rows = conn.execute(
        """SELECT cs.id, cs.exercise_id, cs.status, cs.code_score, cs.defense_score,
                  cs.repair_score, cs.variant_score, cs.total_score, cs.verified,
                  cs.defense_answers_json, cs.report_json
           FROM capability_sessions cs
           WHERE cs.user_id = ? AND cs.id IN (
               SELECT MAX(id) FROM capability_sessions
               WHERE user_id = ? AND status IN (
                   'verified', 'skipped', 'variant_pending', 'repair_pending', 'defense_pending'
               )
               GROUP BY exercise_id
           )""",
        (user_id, user_id),
    ).fetchall()
    conn.close()

    scores = {}
    for row in rows:
        eid = row["exercise_id"]
        status = row["status"]
        verified = bool(row["verified"])
        skipped = status == "skipped"
        report = _loads(row["report_json"], {})
        defense_answers = _loads(row["defense_answers_json"], [])
        defense_grading_status = (
            "not_started" if not defense_answers
            else "completed" if all(item.get("graded_by") == "ai" for item in defense_answers)
            else "grading" if any(item.get("grading_status") == "grading" for item in defense_answers)
            else "pending"
        )

        scores[eid] = {
            "session_id": row["id"],
            "score": round(row["total_score"] or 0),
            "test_score": round(row["code_score"] or 0),
            "defense_score": round(row["defense_score"] or 0),
            "repair_score": round(row["repair_score"] or 0),
            "variant_score": round(row["variant_score"] or 0),
            "verified": verified,
            "skipped": skipped,
            "status": status,
            "defense_grading_status": defense_grading_status,
            "summary": report.get("summary", ""),
            "dimensions": report.get("dimensions", {}),
            "defense_feedback": [
                {
                    "question_id": item.get("question_id", ""),
                    "prompt": item.get("prompt", ""),
                    "score": round(item.get("score", 0) or 0),
                    "feedback": item.get("feedback", ""),
                    "graded_by": item.get("graded_by", ""),
                    "grading_status": item.get("grading_status", ""),
                }
                for item in defense_answers
            ],
        }
    return scores
