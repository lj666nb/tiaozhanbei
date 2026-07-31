"""伴随式学习路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from schemas import APIResponse, LearningPathGenerateRequest, PathProgressUpdateRequest, TaskUpdate, TaskQuizRequest, CodeExecuteRequest, CodeStepGuideRequest, CodeStepCheckRequest, DiagnosticTestRequest, TutorialSaveRequest, TutorialGenerateRequest
from services import learning_service, resource_service
from database import get_db
import os

router = APIRouter()


@router.post("/visit", response_model=APIResponse)
async def record_visit(current_user: dict = Depends(get_current_user)):
    """记录学习访问（用于统计学习天数）"""
    from database import get_db
    from datetime import datetime
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO learning_records (user_id, knowledge_tag, action_type, result_json) VALUES (?, '综合', 'page_visit', ?)",
        (current_user["id"], f'{{"date":"{today}"}}')
    )
    conn.commit()
    conn.close()
    return APIResponse(data={"recorded": today})


@router.post("/path/generate", response_model=APIResponse)
async def generate_path(req: LearningPathGenerateRequest, current_user: dict = Depends(get_current_user)):
    """生成个性化学习路径（可选携带诊断测试结果）"""
    try:
        result = await learning_service.generate_learning_path(
            user_id=current_user["id"],
            goal=req.goal,
            timeline=req.timeline,
            learning_depth=req.learning_depth,
            diagnostic_session_id=req.diagnostic_session_id,
            modules=req.modules
        )
        return APIResponse(data=result)
    except ValueError as e:
        return APIResponse(code=400, message=str(e), data=None)
    except Exception as e:
        return APIResponse(code=500, message=f"生成学习路径失败: {str(e)}", data=None)

@router.delete("/path", response_model=APIResponse)
async def delete_path(current_user: dict = Depends(get_current_user)):
    """删除当前学习路径"""
    try:
        result = await learning_service.delete_learning_path(current_user["id"])
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"删除学习路径失败: {str(e)}", data=None)

@router.post("/path/diagnostic-test", response_model=APIResponse)
async def create_diagnostic_test(req: DiagnosticTestRequest, current_user: dict = Depends(get_current_user)):
    """根据学习目标生成诊断测试卷"""
    try:
        result = await learning_service.generate_diagnostic_test(
            user_id=current_user["id"],
            goal=req.goal,
            count=req.count
        )
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"生成诊断测试失败: {str(e)}", data=None)

@router.get("/resource", response_model=APIResponse)
async def get_learning_resource(knowledge: str = "", current_user: dict = Depends(get_current_user)):
    """根据知识点获取本地学习资料（Markdown格式）"""
    try:
        result = resource_service.get_local_material(knowledge, user_id=current_user["id"])
        if result and result.get("found"):
            return APIResponse(data=result)
        # 如果没找到本地资料，返回fallback内容
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"获取学习资源失败: {str(e)}", data=None)

@router.get("/path", response_model=APIResponse)
async def get_path(current_user: dict = Depends(get_current_user)):
    """获取当前学习路径"""
    result = await learning_service.get_learning_path(current_user["id"])
    return APIResponse(data=result)

@router.put("/path/progress", response_model=APIResponse)
async def update_progress(req: PathProgressUpdateRequest, current_user: dict = Depends(get_current_user)):
    """更新路径进度（sub_action: learn/quiz/code，不传则全标记）"""
    result = await learning_service.update_path_progress(
        current_user["id"], req.task_key, req.completed, req.sub_action
    )
    return APIResponse(data=result)

@router.get("/tasks", response_model=APIResponse)
async def get_tasks(date: str = None, current_user: dict = Depends(get_current_user)):
    """获取每日任务"""
    result = await learning_service.get_daily_tasks(current_user["id"], date)
    return APIResponse(data=result)

@router.put("/tasks/complete", response_model=APIResponse)
async def complete_task(req: TaskUpdate, date: str = "", current_user: dict = Depends(get_current_user)):
    """完成每日任务"""
    if not date:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    result = await learning_service.update_daily_task(current_user["id"], date, req.completed)
    return APIResponse(data=result)

@router.post("/task-quiz", response_model=APIResponse)
async def generate_task_quiz(req: TaskQuizRequest, current_user: dict = Depends(get_current_user)):
    """为学习路径中指定天数的任务生成专项练习题"""
    try:
        result = await learning_service.generate_task_quiz(
            user_id=current_user["id"],
            task_day=req.task_day,
            count=req.count
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return APIResponse(data=result)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(code=500, message=f"生成任务练习失败: {str(e)}", data=None)

@router.get("/code-task/{task_day}", response_model=APIResponse)
async def get_code_task(task_day: int, current_user: dict = Depends(get_current_user)):
    """获取指定天数的编程任务"""
    try:
        result = await learning_service.get_code_task(current_user["id"], task_day)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return APIResponse(data=result)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(code=500, message=f"获取编程任务失败: {str(e)}", data=None)

@router.post("/code-execute", response_model=APIResponse)
async def execute_code(req: CodeExecuteRequest, current_user: dict = Depends(get_current_user)):
    """执行用户代码并运行测试"""
    try:
        result = await learning_service.execute_code(current_user["id"], req.task_day, req.code)
        # 记录代码完成
        if not result.get("error"):
            try:
                await learning_service.record_code_completion(current_user["id"], req.task_day)
            except Exception:
                pass
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"代码执行失败: {str(e)}", data=None)

class CodeRunRequest(BaseModel):
    code: str
    language: str = "python"  # python, cpp, java
    problem_title: str = ""      # 题目标题（用于AI提示分析）
    problem_description: str = ""  # 题目描述（用于AI提示分析）
    failure_count: int = 0       # 当前连续失败次数（用于渐进式提示）

@router.post("/code-run", response_model=APIResponse)
async def run_code(req: CodeRunRequest, current_user: dict = Depends(get_current_user)):
    """在线运行代码（沙箱执行 + AI 错误解析 + 渐进式提示）"""
    try:
        import subprocess, tempfile, os as _os, shutil
        code = req.code
        language = req.language.lower()
        output = ""
        error = ""
        ai_analysis = ""
        hint = ""

        # 检查编译器/解释器
        runners = {
            "python": ["python", "-c", code],
            "cpp": None,  # 需要编译后运行
            "java": None,
        }
        exe_name = {"python": "python", "cpp": "g++", "java": "javac"}

        executable = shutil.which(exe_name.get(language, "python"))
        if not executable:
            return APIResponse(data={"output": "", "error": f"未找到 {exe_name.get(language, language)} 运行环境，请先安装", "ai_analysis": "", "hint": ""})

        if language == "python":
            proc = subprocess.run(
                ["python", "-c", code],
                capture_output=True, text=True, timeout=30,
                cwd=_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            )
            output = proc.stdout
            error = proc.stderr
        elif language == "cpp":
            with tempfile.TemporaryDirectory() as tmp:
                src = _os.path.join(tmp, "main.cpp")
                exe = _os.path.join(tmp, "main.exe")
                with open(src, "w", encoding="utf-8") as f:
                    f.write(code)
                compile_proc = subprocess.run(
                    ["g++", src, "-o", exe, "-std=c++17", "-Wall"],
                    capture_output=True, text=True, timeout=20
                )
                if compile_proc.returncode != 0:
                    error = compile_proc.stderr
                else:
                    run_proc = subprocess.run(
                        [exe], capture_output=True, text=True, timeout=10,
                        input="\n"
                    )
                    output = run_proc.stdout
                    error = run_proc.stderr
        elif language == "java":
            with tempfile.TemporaryDirectory() as tmp:
                src = _os.path.join(tmp, "Main.java")
                with open(src, "w", encoding="utf-8") as f:
                    f.write(code)
                compile_proc = subprocess.run(
                    ["javac", src], capture_output=True, text=True, timeout=20
                )
                if compile_proc.returncode != 0:
                    error = compile_proc.stderr
                else:
                    run_proc = subprocess.run(
                        ["java", "-cp", tmp, "Main"],
                        capture_output=True, text=True, timeout=10,
                        input="\n"
                    )
                    output = run_proc.stdout
                    error = run_proc.stderr
        else:
            return APIResponse(data={"output": "", "error": f"不支持的语言: {language}", "ai_analysis": "", "hint": ""})

        # AI 错误解析（有错误时生成提示）
        has_problem_context = bool(req.problem_title or req.problem_description)
        if error:
            try:
                from services.ai_service import call_llm

                # 根据失败次数调整提示策略
                failure_count = max(0, req.failure_count)
                if failure_count == 0:
                    hint_strategy = "给出简洁的错误原因和通用修复方向，控制在100字以内。不要直接给出完整答案代码。"
                elif failure_count == 1:
                    hint_strategy = "给出更具体的错误定位和修复思路，可以提示关键代码片段，但不要给出完整答案。控制在150字以内。"
                elif failure_count == 2:
                    hint_strategy = "给出详细的修复步骤和关键代码示例，接近完整答案但不完全给出。控制在200字以内。"
                else:
                    hint_strategy = "给出完整的分析和修复方案，可以包含代码示例。控制在250字以内。"

                if has_problem_context:
                    analysis_prompt = f"""你是一位编程导师。学生正在做一道编程题，提交的 {language.upper()} 代码运行时出现了错误。

【题目】
标题：{req.problem_title}
描述：{req.problem_description[:1000]}

【学生代码】
{code[:2000]}

【错误信息】
{error[:1500]}

{hint_strategy}

注意：
- 用中文回答，语气鼓励、有耐心
- 先指出学生的思路是否正确，再给出具体的修改方向
- 不要把"题目要求做X，而你的代码做了Y"当作模板套话——只在确实存在这种偏差时才说
- 不要输出"方案一/方案二"这种多选项"""
                else:
                    analysis_prompt = f"""你是一位编程导师。学生提交了以下 {language.upper()} 代码，运行时出现了错误。

【代码】
{code[:2000]}

【错误信息】
{error[:1500]}

{hint_strategy}

请直接给出分析和建议，不要啰嗦开头。用中文回答。"""

                ai_resp = await call_llm(
                    current_user["id"],
                    [{"role": "user", "content": analysis_prompt}],
                    temperature=0.3, max_tokens=600
                )
                ai_analysis = ai_resp if not ai_resp.startswith("LLM调用异常") else ""

                # 生成简短 hint（用于终端区域快速查看）
                if ai_analysis:
                    hint = _extract_short_hint(ai_analysis, error)
            except Exception:
                pass
        elif not output and not error:
            # 代码成功运行但没有输出：逻辑缺漏 或 缺少调用入口
            has_code_body = _has_code_body(code)
            if has_problem_context and not has_code_body:
                # 场景A：代码全是 pass 占位，学生还没开始写
                ai_analysis = "你的代码中大部分函数体还是 pass 占位符，尚未实现实际逻辑。请逐个完成每个方法的功能实现后再运行。"
                hint = "📝 请将代码中的 pass 替换为实际逻辑"
            elif has_problem_context:
                # 场景B：代码有逻辑但没输出（缺少测试代码 或 定义了但未调用）
                try:
                    from services.ai_service import call_llm
                    analysis_prompt = f"""你是一位编程导师。学生的代码成功运行但没有产生任何输出，说明代码没有语法错误。

【题目】
标题：{req.problem_title}
描述：{req.problem_description[:1000]}

【学生代码】
{code[:2000]}

请做两件事：
1. 判断：学生是已经实现了题目要求的类/函数，只是缺少调用它们的测试代码？还是函数体本身就有逻辑缺陷？
2. 给出改进建议：
   - 如果缺少测试代码：告诉学生"你的类/函数定义看起来没问题，但缺少调用代码。请在代码末尾添加 if __name__ == '__main__': 块来创建实例并调用方法，用 print 输出结果来验证功能"
   - 如果函数体有缺陷：用一句话指出问题所在和修改方向

控制在180字以内。用中文，语气鼓励。不要直接给出完整答案代码。"""
                    ai_resp = await call_llm(
                        current_user["id"],
                        [{"role": "user", "content": analysis_prompt}],
                        temperature=0.3, max_tokens=500
                    )
                    ai_analysis = ai_resp if not ai_resp.startswith("LLM调用异常") else ""
                    if ai_analysis:
                        hint = ai_analysis[:120]
                except Exception:
                    pass
            # 场景C：无题目上下文且无输出 — 给通用提示
            if not ai_analysis:
                ai_analysis = "代码成功运行但没有任何输出。如果你定义了函数或类，请在代码末尾添加测试代码来调用它们，并用 print() 输出结果。"
                hint = "💡 添加 print() 或测试代码来验证你的实现"

        return APIResponse(data={
            "output": output,
            "error": error,
            "ai_analysis": ai_analysis,
            "hint": hint
        })
    except subprocess.TimeoutExpired:
        return APIResponse(data={"output": "", "error": "代码执行超时（30秒）", "ai_analysis": "代码执行超时，请检查是否存在死循环或无限递归。尝试添加打印语句来定位卡住的位置。", "hint": "⚠️ 超时：检查循环条件或递归终止条件"})
    except Exception as e:
        return APIResponse(data={"output": "", "error": f"执行异常: {str(e)}", "ai_analysis": "", "hint": ""})


def _extract_short_hint(ai_analysis: str, error: str) -> str:
    """从AI分析中提取简短的一句话提示（显示在终端区）"""
    # 尝试取第一句有意义的话
    import re
    # 移除常见前缀
    cleaned = re.sub(r'^(好的[，,]?|同学[，,]?|你的代码|这段代码)', '', ai_analysis.strip())
    # 取第一句（以句号、分号、换行分隔）
    first_sentence = re.split(r'[。；\n]', cleaned)[0].strip()
    if len(first_sentence) > 10:
        return first_sentence[:120]
    # fallback: 取前120字符
    return ai_analysis.strip()[:120]


def _has_code_body(code: str) -> bool:
    """检查代码是否包含实际逻辑（而非全部 pass 占位）"""
    import re
    # 去除注释和空行
    lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
    if not lines:
        return False
    # 检查非 pass 的实质性代码行比例
    non_pass_lines = [l for l in lines if l.strip() != 'pass' and not re.match(r'^\s*pass\s*$', l)]
    # 如果超过 30% 的行不是 pass，认为有代码体
    # 同时排除只有类/函数定义头（以冒号结尾）的情况
    body_lines = [l for l in non_pass_lines if not re.match(r'^\s*(def |class ).*:\s*$', l)]
    return len(body_lines) >= max(2, len(lines) * 0.2)


def _load_exercise_by_id(exercise_id: str) -> dict | None:
    """从习题文件中加载指定ID的习题数据"""
    # 项目制实验优先，确保参考答案也使用当前课程契约。
    try:
        from services.judge_service import get_flagship_exercise
        flagship = get_flagship_exercise(exercise_id)
        if flagship:
            return flagship
    except Exception:
        pass

    import os as _os, glob as _glob
    exercises_dir = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "data", "exercises"
    )
    for fpath in sorted(_glob.glob(_os.path.join(exercises_dir, "module_*.txt"))):
        content = open(fpath, "r", encoding="utf-8").read()
        # 解析单个习题块
        import re as _re
        parts = _re.split(r'\n(?=关卡 \d+-\d+：)', content)
        for part in parts:
            m = _re.match(r'关卡\s*(\d+-\d+)', part.strip())
            if not m or m.group(1) != exercise_id:
                continue

            ex = {"id": exercise_id}
            # 标题
            tm = _re.search(r'：(.+?)$', part.split('\n')[0])
            if tm:
                ex["title"] = tm.group(1).strip()
            # 模块
            mm = _re.search(r'所属模块[：:]\s*(.+?)$', part, _re.MULTILINE)
            if mm:
                ex["module"] = mm.group(1).strip()
            # 描述
            desc_m = _re.search(r'【任务描述】\s*\n(.*?)(?=【[输初评]|$)', part, _re.DOTALL)
            if desc_m:
                ex["description"] = desc_m.group(1).strip()
            # starter code
            sc_m = _re.search(r'```python\s*\n(.*?)```', part, _re.DOTALL)
            if sc_m:
                ex["starter_code"] = sc_m.group(1).strip()
            # eval code (from the second code block)
            all_code_blocks = list(_re.finditer(r'```python\s*\n(.*?)```', part, _re.DOTALL))
            if len(all_code_blocks) >= 2:
                ex["eval_code"] = all_code_blocks[1].group(1).strip()
            return ex
    return None


def _extract_eval_hints(eval_code: str) -> str:
    """从评测代码中提取关键的输入/输出格式提示"""
    import re as _re
    hints = []
    # 提取 assert 语句
    asserts = _re.findall(r'assert\s+(.+?)(?:\s*,\s*["\'].*?["\'])?\s*$', eval_code, _re.MULTILINE)
    for a in asserts[:8]:
        a = a.strip()
        if len(a) < 120:
            hints.append(f"  - 评测断言: assert {a}")
    # 提取返回值检查模式
    returns = _re.findall(r'(\w+)\[["\'](\w+)["\']\]', eval_code)
    if returns:
        for var, key in returns[:5]:
            hints.append(f"  - 预计返回值包含键: {var}['{key}']")
    if hints:
        return "以下是从评测代码中提取的约束，你的代码必须满足：\n" + "\n".join(hints[:8])
    return ""


async def _validate_code_in_sandbox(code: str, language: str = "python",
                                     exercise_id: str = "") -> tuple[bool, str]:
    """在沙箱中运行代码并验证，返回 (是否通过, 错误信息)。

    当提供 exercise_id 时，会注入该题目的测试驱动并用实际评测验证。
    """
    import subprocess, tempfile, os as _os
    try:
        if language.lower() not in ("python", "py", "python3"):
            return True, ""  # 非 Python 暂不验证

        # 当前项目制实验统一走服务端私有场景，避免生成答案只凭“能运行”被误判通过。
        if exercise_id:
            try:
                from services.judge_service import is_flagship_exercise, judge_submission
                if is_flagship_exercise(exercise_id):
                    result = judge_submission(exercise_id, code)
                    if result.get("passed"):
                        return True, ""
                    failed = [
                        item.get("description", "私有场景")
                        for item in result.get("results", []) if not item.get("passed")
                    ]
                    detail = "、".join(failed[:4]) or result.get("compile_error") or "私有场景未通过"
                    return False, f"服务端私有场景验证失败：{detail}"
            except Exception as exc:
                return False, f"服务端私有场景验证异常：{str(exc)[:240]}"

        # 如果代码没有 __main__ 测试入口，尝试注入测试驱动
        test_code = code
        has_test_driver = 'if __name__' in code or '__main__' in code

        if not has_test_driver and exercise_id:
            injected = _inject_test_driver(code, exercise_id)
            if injected:
                test_code = injected
                has_test_driver = True

        with tempfile.TemporaryDirectory() as tmp:
            src = _os.path.join(tmp, "main.py")
            with open(src, "w", encoding="utf-8") as f:
                f.write(test_code)
            proc = subprocess.run(
                ["python", src],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=15, cwd=tmp
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()

            if proc.returncode != 0:
                return False, f"退出码={proc.returncode}\nstderr:\n{stderr[:600]}\nstdout:\n{stdout[:300]}"

            # 如果有测试驱动，检查 [PASS]/[FAIL] 标记
            if has_test_driver:
                pass_count = stdout.count('[PASS]')
                fail_count = stdout.count('[FAIL]')
                total = pass_count + fail_count
                if total == 0 and not stdout:
                    return False, "代码运行成功但没有产生任何输出（缺少 print 或测试代码未调用）。"
                if fail_count > 0 or (total == 0 and not stdout):
                    if fail_count > 0:
                        return False, f"测试未全部通过：{pass_count}/{total} 通过，{fail_count} 失败"
                    if not stdout:
                        return False, "代码运行成功但没有产生任何输出。"
                return True, ""
            else:
                # 没有测试驱动，只检查是否有输出
                if not stdout:
                    return False, "代码运行成功但没有产生任何输出（缺少 print 或测试代码未调用）。"
                return True, ""
    except subprocess.TimeoutExpired:
        return False, "代码执行超时（>15秒），可能存在死循环。"
    except Exception as e:
        return False, f"沙箱验证异常: {str(e)}"


class CodeAnswerByProblemRequest(BaseModel):
    title: str = ""
    description: str = ""
    knowledge: str = ""
    language: str = "python"
    code: str = ""          # 学生当前代码，用于上下文
    exercise_id: str = ""   # 习题ID（如 "5-6"），用于加载starter代码和评测代码
    starter_code: str = ""  # 题目的初始代码模板（前端可直接传入）

@router.post("/code-answer", response_model=APIResponse)
async def get_code_answer_by_problem(req: CodeAnswerByProblemRequest, current_user: dict = Depends(get_current_user)):
    """根据题目描述生成参考答案（含逐行解释 + 沙箱自验）

    工作流程：
    1. 如果提供了 exercise_id，加载习题的 starter 代码和评测代码作为上下文
    2. 调用 LLM 生成答案
    3. 在沙箱中运行答案代码验证
    4. 如果验证失败，用错误信息修复并重试（最多2次）
    """
    import subprocess, tempfile, os as _os, shutil

    try:
        # ===== 0. 检查参考答案缓存 =====
        CACHE_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                    "data", "exercise_answers_cache.json")
        if req.exercise_id and _os.path.exists(CACHE_PATH):
            try:
                import json as _json
                with open(CACHE_PATH, "r", encoding="utf-8") as _f:
                    cache = _json.load(_f)
                if req.exercise_id in cache and cache[req.exercise_id].get("_validated"):
                    cached = dict(cache[req.exercise_id])
                    cached["_from_cache"] = True
                    return APIResponse(data=cached)
            except Exception:
                pass

        # ===== 1. 加载习题信息 =====
        starter_code = req.starter_code
        eval_code = ""
        if req.exercise_id and not starter_code:
            # 从后端习题文件加载
            exercise = _load_exercise_by_id(req.exercise_id)
            if exercise:
                if not req.title:
                    req.title = exercise.get("title", "")
                if not req.description:
                    req.description = exercise.get("description", "")
                starter_code = starter_code or exercise.get("starter_code", "")
                eval_code = exercise.get("eval_code", "")
                if not req.knowledge:
                    req.knowledge = exercise.get("module", "")

        # ===== 2. 构建 prompt =====
        from services.ai_service import call_llm

        # 项目制实验由服务端私有场景判题，答案只能包含函数/类定义；旧题保留自带测试入口。
        try:
            from services.judge_service import is_flagship_exercise
            is_project_lab = bool(req.exercise_id and is_flagship_exercise(req.exercise_id))
        except Exception:
            is_project_lab = False
        has_test_code = ('if __name__' in req.code and '__main__' in req.code) if req.code else False
        if is_project_lab:
            test_reminder = "\n\n【重要】本题使用服务端私有场景判题。答案只保留题目要求的函数或类定义，不要添加 import、print 或模块顶层测试代码。"
            answer_runtime_requirement = "- 只输出函数/类实现，不要包含 import、print 或 if __name__ 测试入口"
        else:
            test_reminder = ""
            if not has_test_code and req.code:
                test_reminder = "\n\n【重要】学生的代码缺少 if __name__ == '__main__': 测试入口，参考答案务必在末尾包含测试代码，让学生复制后直接运行就能看到输出。"
            answer_runtime_requirement = "- 必须包含 if __name__ == '__main__': 测试入口，末尾创建实例、调用方法、用 print() 输出结果"

        # starter 代码上下文：告诉 AI 必须遵循的接口
        starter_context = ""
        if starter_code:
            starter_context = f"""
【初始代码模板 — 必须兼容此接口】
```python
{starter_code[:2000]}
```
⚠️ 你的答案必须基于此模板实现。类名、方法签名必须与模板一致，不要自己重新设计接口。只需把 pass / TODO 替换为实际逻辑。"""

        # eval 代码上下文：告诉 AI 输出格式
        eval_context = ""
        if eval_code:
            # 从评测代码中提取关键断言来提示 AI
            eval_hints = _extract_eval_hints(eval_code)
            if eval_hints:
                eval_context = f"\n\n【输出格式要求 — 从评测代码推断】\n{eval_hints}"

        max_retries = 2
        last_error = ""
        result = None

        for attempt in range(max_retries + 1):
            retry_context = ""
            if attempt > 0 and last_error:
                retry_context = f"""
【上一版答案的验证错误 — 务必修复】
{last_error[:800]}
请根据以上错误修正代码，确保代码能正常运行。"""

            prompt = f"""你是一位编程导师。请为以下编程题生成正确答案。

【题目信息】
标题：{req.title}
知识点：{req.knowledge}
描述：{req.description[:2000]}
编程语言：{req.language.upper()}
{starter_context}
{eval_context}
【学生当前代码（供参考其进度）】
{req.code[:1500] if req.code else "（学生尚未编写代码）"}
{test_reminder}
{retry_context}
请完成以下三项任务：

## 任务1：解题思路
用1-2段话简要说明这道题的解题思路和核心逻辑。

## 任务2：参考答案代码
给出完整的、可直接运行的参考答案代码。要求：
- 基于初始代码模板实现，类名和方法签名保持一致
- 核心逻辑加注释
{answer_runtime_requirement}
- 代码风格规范、可直接复制运行

## 任务3：关键代码解释
选择代码中3-5个关键部分，用通俗的语言解释其作用。

请用以下JSON格式返回：
```json
{{
  "approach": "解题思路说明（1-2段话）",
  "answer_code": "完整参考答案代码（含测试入口）",
  "explanations": [
    {{"code": "关键代码片段1", "explanation": "这段代码的作用解释"}},
    {{"code": "关键代码片段2", "explanation": "这段代码的作用解释"}}
  ]
}}
```

注意：
- 用中文回答
- answer_code 中的代码必须完整，并遵循本题的判题入口要求
- answer_code 里不要用转义字符（\\n、\\t 等），就是正常的代码文本
- 解释要通俗易懂，适合初学者"""

            response = await call_llm(
                current_user["id"],
                [{"role": "system", "content": "你是编程教学专家，请严格按JSON格式返回，不要输出其他内容。"},
                 {"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=2048
            )

            from services.ai_service import extract_json_object
            try:
                result = extract_json_object(response)
            except Exception:
                result = {
                    "approach": "以下是参考答案：",
                    "answer_code": response,
                    "explanations": []
                }

            # ===== 3. 沙箱验证 =====
            answer_code = result.get("answer_code", "")
            if not answer_code:
                break  # 没有代码可验证

            is_valid, validation_error = await _validate_code_in_sandbox(
                answer_code, req.language, exercise_id=req.exercise_id)
            if is_valid:
                result["_validated"] = True
                break
            else:
                last_error = validation_error
                result["_validated"] = False
                if attempt < max_retries:
                    continue  # 重试
                else:
                    # 最后一次仍失败，标记并返回
                    result["_validation_error"] = validation_error[:300]

        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"生成参考答案失败: {str(e)}", data=None)


# ── 真实沙箱评测端点 ──────────────────────────────────────────
class CodeEvaluateRequest(BaseModel):
    exercise_id: str = ""      # 习题ID (如 "5-6")
    code: str = ""             # 用户编写的代码
    language: str = "python"


@router.post("/code-evaluate", response_model=APIResponse)
async def evaluate_code_submission(req: CodeEvaluateRequest, current_user: dict = Depends(get_current_user)):
    """真实沙箱评测：语法校验 + 动态函数调用 + 多用例判题"""
    try:
        from database import get_db
        from services.judge_service import is_flagship_exercise, judge_submission

        if not is_flagship_exercise(req.exercise_id):
            return APIResponse(
                code=410,
                message="该旧题已停止判题，待按真实业务场景和服务端私有测试标准重制",
                data=None,
            )

        # 私有业务场景完全由服务端掌握，浏览器输出不能伪造通过结果。
        result = judge_submission(req.exercise_id, req.code)

        # 3. 保存提交记录
        try:
            import json as _json
            conn = get_db()
            conn.execute(
                "INSERT INTO code_submissions (user_id, exercise_id, code, passed, total, score, verified, results_json) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (current_user["id"], req.exercise_id, req.code,
                 1 if result.get('passed') else 0, result['total'],
                 round(result['passed_count'] / max(result['total'], 1) * 100),
                 _json.dumps(result['results'], ensure_ascii=False))
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

        return APIResponse(data=result)

    except Exception as e:
        return APIResponse(code=500, message=f"评测异常: {str(e)}", data=None)


def _evaluate_with_embedded_tests(code: str) -> dict:
    """运行用户代码中已有的 if __name__ == '__main__' 测试驱动，解析结果"""
    import subprocess, tempfile, os as _os, re, time as _time
    start = _time.time()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = _os.path.join(tmp, 'main.py')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(code)
            proc = subprocess.run(
                [_os.environ.get('PYTHON_PATH', 'python'), src],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=15, cwd=tmp
            )
            stdout = proc.stdout or ''
            stderr = proc.stderr or ''

            if proc.returncode != 0:
                # Extract meaningful error
                err_lines = [l for l in stderr.split('\n') if l.strip()]
                error_msg = '\n'.join(err_lines[-3:]) if err_lines else stderr[:500]
                return {
                    'passed': False, 'total': 0, 'passed_count': 0,
                    'compile_error': error_msg,
                    'results': [], 'execution_time': round(_time.time() - start, 3)
                }

            # Parse [PASS] and [FAIL] from output
            pass_count = stdout.count('[PASS]')
            fail_count = stdout.count('[FAIL]')
            total = pass_count + fail_count

            results = []
            for line in stdout.split('\n'):
                if '[PASS]' in line or '[FAIL]' in line:
                    results.append({
                        'case_index': len(results) + 1,
                        'description': line.strip()[:100],
                        'passed': '[PASS]' in line,
                        'error': None if '[PASS]' in line else line.strip()[:200]
                    })

            if total == 0:
                total = 1  # ran without error

            return {
                'passed': fail_count == 0 and total > 0,
                'total': total,
                'passed_count': pass_count,
                'compile_error': None,
                'results': results,
                'execution_time': round(_time.time() - start, 3)
            }
    except subprocess.TimeoutExpired:
        return {
            'passed': False, 'total': 0, 'passed_count': 0,
            'compile_error': '执行超时 (>15秒)',
            'results': [], 'execution_time': round(_time.time() - start, 3)
        }
    except Exception as e:
        return {
            'passed': False, 'total': 0, 'passed_count': 0,
            'compile_error': f'评测异常: {str(e)}',
            'results': [], 'execution_time': round(_time.time() - start, 3)
        }


def _inject_test_driver(user_code: str, exercise_id: str) -> str | None:
    """当用户代码缺少 __main__ 测试入口时，从题库骨架代码中提取测试驱动并注入。

    返回组合后的完整代码，如果找不到该题目的骨架代码则返回 None。
    """
    import json as _json, os as _os, re as _re

    # 加载题库数据
    processed_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "data", "exercises_processed.json"
    )
    if not _os.path.exists(processed_path):
        return None

    try:
        with open(processed_path, 'r', encoding='utf-8') as f:
            exercises = _json.load(f)
    except Exception:
        return None

    # 查找目标题目的骨架代码
    skeleton_code = ""
    for ex in exercises:
        if ex.get('id') == exercise_id:
            skeleton_code = ex.get('skeleton_code', '')
            break

    if not skeleton_code:
        return None

    # 从骨架代码中提取 __main__ 测试块
    main_idx = skeleton_code.find("if __name__")
    if main_idx < 0:
        # 尝试匹配 "if __name__" 的各种变体
        import re as _re2
        m = _re2.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', skeleton_code)
        if m:
            main_idx = m.start()

    if main_idx < 0:
        return None

    test_block = skeleton_code[main_idx:]

    # ----- 清洗用户代码 -----
    cleaned = user_code

    # 移除 CODE_START/CODE_END 标记及其外部框架代码，只保留用户编写部分
    start_marker = "# ==========你的代码开始=========="
    end_marker = "# ==========你的代码结束=========="

    if start_marker in cleaned:
        start_idx = cleaned.find(start_marker) + len(start_marker)
        end_idx = cleaned.find(end_marker)
        if end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx].strip()
        else:
            # 结束标记缺失，取开始标记之后的所有内容
            cleaned = cleaned[start_idx:].strip()

    # 如果用户代码中已有 __main__ 块，移除它（避免重复定义）
    # 使用同样的检测逻辑
    existing_main_idx = cleaned.find("if __name__")
    if existing_main_idx < 0:
        import re as _re3
        m = _re3.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', cleaned)
        if m:
            existing_main_idx = m.start()

    if existing_main_idx >= 0:
        # 确保 __main__ 不在字符串或注释中（简单检测：前面没有未闭合的引号）
        before = cleaned[:existing_main_idx]
        if before.count("'''") % 2 == 0 and before.count('"""') % 2 == 0:
            cleaned = cleaned[:existing_main_idx].strip()

    # 组合：用户代码 + 测试驱动
    combined = cleaned + "\n\n" + test_block
    return combined


def _load_exercise_test_meta(exercise_id: str) -> dict | None:
    """从数据库加载习题评测元数据"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM exercise_test_metadata WHERE exercise_id = ?", (exercise_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    import json as _json
    return {
        'exercise_type': row['exercise_type'],
        'target_function': row['target_function'],
        'test_cases': _json.loads(row['test_cases_json'] or '[]'),
        'locked_code': row['locked_code'] or '',
        'guide_comment': row['guide_comment'] or '# 请在此处实现代码',
    }


def _load_exercise_test_meta_from_processed(exercise_id: str) -> dict | None:
    """从 exercises_processed.json 中提取评测元数据"""
    import json as _json
    processed_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "data", "exercises_processed.json")
    if not os.path.exists(processed_path):
        return None
    try:
        with open(processed_path, 'r', encoding='utf-8') as f:
            exercises = _json.load(f)
        for ex in exercises:
            if ex['id'] == exercise_id:
                return _build_meta_from_exercise(ex)
    except Exception:
        pass
    return None


def _build_meta_from_exercise(ex: dict) -> dict:
    """从习题数据构建评测元数据"""
    import re
    raw_code = ex.get('raw_starter_code', '') or ex.get('skeleton_code', '')
    eval_code = ex.get('eval_code', '')

    # 提取目标函数名（第一个 def 后面的名字）
    func_match = re.search(r'def\s+(\w+)\s*\(', raw_code)
    target = func_match.group(1) if func_match else ''

    # 确定类型: 有 eval_code 且没有 module_dict 则为函数型
    ex_type = 'function'
    if 'module_dict' in eval_code:
        ex_type = 'function'  # 类方法也是 function 型（返回 dict）

    # 从 eval_code 中提取测试用例
    test_cases = _extract_test_cases_from_eval(eval_code, raw_code)

    # 提取锁定代码（imports, 类声明等）
    locked_code = _extract_locked_code(raw_code, target)

    return {
        'exercise_type': ex_type,
        'target_function': target,
        'test_cases': test_cases,
        'locked_code': locked_code,
        'guide_comment': f'# 请在此处实现 {target}() 函数功能' if target else '# 请在此处编写代码',
    }


def _extract_test_cases_from_eval(eval_code: str, raw_code: str) -> list:
    """从评测代码中提取测试用例 [{args, expected, description}]"""
    import re as _re
    cases = []
    if not eval_code:
        return cases

    # 提取 func(args) 调用 + assert
    calls = _re.findall(r'(\w+)\s*=\s*\w+\((.*?)\)', eval_code)
    asserts = _re.findall(r'assert\s+(.+?)(?:\s*,\s*["\'](.+?)["\'])?\s*$', eval_code, _re.MULTILINE)

    for i, call_match in enumerate(_re.finditer(r'(\w+)\s*=\s*\w+\((.*?)\)', eval_code)):
        result_var = call_match.group(1)
        args_str = call_match.group(2)
        # 解析参数为 Python 字面量
        try:
            args = _parse_args(args_str)
        except Exception:
            args = [args_str]

        # 查找对应的 assert
        expected = None
        desc = f'用例{i+1}'
        for assert_cond, assert_msg in asserts:
            if result_var in assert_cond:
                desc = assert_msg.strip('\'"') if assert_msg else desc
                # 尝试从 assert 中提取期望值
                eq_match = _re.search(r'==\s*(.+?)(?:\s+and|\s*$)', assert_cond)
                if eq_match:
                    try:
                        expected = eval(eq_match.group(1).strip())
                    except Exception:
                        expected = eq_match.group(1).strip()
                break

        if args:
            cases.append({
                'args': args,
                'expected': expected,
                'description': desc
            })

    return cases[:10]


def _parse_args(args_str: str) -> list:
    """安全解析参数字符串为 Python 对象列表"""
    if not args_str.strip():
        return []
    # 使用 ast.literal_eval 安全解析
    import ast
    try:
        # 包装为元组
        result = ast.literal_eval(f'({args_str})')
        if isinstance(result, tuple):
            return list(result)
        return [result]
    except Exception:
        # 降级: 当作单个字符串参数
        return [args_str.strip()]


def _extract_locked_code(raw_code: str, target_func: str) -> str:
    """提取锁定代码: 类声明 + __init__ + 非目标函数的已完成方法"""
    import re as _re
    if not raw_code:
        return ''

    lines = raw_code.split('\n')
    locked_lines = []
    in_target = False
    in_method = False
    method_indent = 0

    for line in lines:
        stripped = line.strip()

        # class 声明 → 锁定
        if stripped.startswith('class ') and stripped.endswith(':'):
            locked_lines.append(line)
            continue

        # import 语句 → 锁定
        if stripped.startswith('import ') or stripped.startswith('from '):
            locked_lines.append(line)
            continue

        # def 声明
        m = _re.match(r'def\s+(\w+)', stripped)
        if m:
            func_name = m.group(1)
            in_target = (func_name == target_func)
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            if not in_target:
                locked_lines.append(line)
            continue

        # 方法体
        if in_method and (not stripped or (len(line) - len(line.lstrip()) > method_indent)):
            if not in_target:
                locked_lines.append(line)
            continue

        # 回到类级别
        if in_method and stripped and (len(line) - len(line.lstrip()) <= method_indent):
            in_method = False
            locked_lines.append(line)
            continue

        # 顶层代码
        if not in_method:
            locked_lines.append(line)

    return '\n'.join(locked_lines)


@router.get("/code-answer/{task_day}", response_model=APIResponse)
async def get_code_answer(task_day: int, current_user: dict = Depends(get_current_user)):
    """获取编程任务参考答案及逐行解释"""
    try:
        result = await learning_service.get_code_answer(current_user["id"], task_day)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return APIResponse(data=result)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(code=500, message=f"获取参考答案失败: {str(e)}", data=None)

@router.post("/code-step-guide", response_model=APIResponse)
async def generate_step_guide(req: CodeStepGuideRequest, current_user: dict = Depends(get_current_user)):
    """AI 将编程任务分解为手把手教学步骤"""
    try:
        result = await learning_service.generate_code_step_guide(current_user["id"], req.task_day)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return APIResponse(data=result)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(code=500, message=f"生成教学步骤失败: {str(e)}", data=None)

@router.post("/code-step-check", response_model=APIResponse)
async def check_code_step(req: CodeStepCheckRequest, current_user: dict = Depends(get_current_user)):
    """AI 检查当前步骤代码是否正确"""
    try:
        result = await learning_service.check_code_step(
            current_user["id"], req.task_day, req.step_index, req.code,
            req.step_title, req.step_instruction
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return APIResponse(data=result)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(code=500, message=f"检查代码步骤失败: {str(e)}", data=None)

@router.get("/error-book", response_model=APIResponse)
async def get_error_book(page: int = 1, page_size: int = 20, current_user: dict = Depends(get_current_user)):
    """获取错题本"""
    result = await learning_service.get_error_book(current_user["id"], page, page_size)
    return APIResponse(data=result)

@router.put("/error-book/{error_id}/review", response_model=APIResponse)
async def review_error(error_id: int, current_user: dict = Depends(get_current_user)):
    """标记错题已复习"""
    result = await learning_service.review_error(current_user["id"], error_id)
    return APIResponse(data=result)

@router.put("/error-book/session/{session_id}/review-all", response_model=APIResponse)
async def review_session_errors(session_id: int, current_user: dict = Depends(get_current_user)):
    """将该组错题全部标记为已复习"""
    result = await learning_service.review_session_errors(current_user["id"], session_id)
    return APIResponse(data=result)

class BatchDeleteRequest(BaseModel):
    ids: list[int]

@router.get("/error-book/sessions", response_model=APIResponse)
async def get_error_sessions(current_user: dict = Depends(get_current_user)):
    """获取错题按测评分组"""
    result = await learning_service.get_error_sessions(current_user["id"])
    return APIResponse(data=result)

@router.get("/error-book/session/{session_id}", response_model=APIResponse)
async def get_errors_by_session(session_id: int, page: int = 1, current_user: dict = Depends(get_current_user)):
    """获取指定会话的错题"""
    result = await learning_service.get_errors_by_session(current_user["id"], session_id, page)
    return APIResponse(data=result)

@router.get("/error-book/orphan", response_model=APIResponse)
async def get_orphan_errors(page: int = 1, current_user: dict = Depends(get_current_user)):
    """获取无会话的历史错题"""
    result = await learning_service.get_errors_by_session(current_user["id"], None, page)
    return APIResponse(data=result)

@router.delete("/error-book/session/{session_id}", response_model=APIResponse)
async def delete_session_errors(session_id: int, current_user: dict = Depends(get_current_user)):
    """删除某次测评的全部错题"""
    result = await learning_service.delete_errors_by_session(current_user["id"], session_id)
    return APIResponse(data=result)

@router.delete("/error-book/orphan", response_model=APIResponse)
async def delete_orphan_errors(current_user: dict = Depends(get_current_user)):
    """删除历史错题"""
    result = await learning_service.delete_errors_by_session(current_user["id"], None)
    return APIResponse(data=result)

@router.post("/error-book/batch-delete", response_model=APIResponse)
async def batch_delete_errors(req: BatchDeleteRequest, current_user: dict = Depends(get_current_user)):
    """批量删除错题（保留兼容）"""
    result = await learning_service.batch_delete_errors(current_user["id"], req.ids)
    return APIResponse(data=result)


@router.get("/code-completions", response_model=APIResponse)
async def get_code_completions(current_user: dict = Depends(get_current_user)):
    """获取用户已通过的编程习题ID列表（跨设备同步通关状态）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT exercise_id FROM code_submissions WHERE user_id = ? AND passed = 1 AND verified = 1",
        (current_user["id"],)
    ).fetchall()
    conn.close()
    return APIResponse(data=[r["exercise_id"] for r in rows])


@router.put("/tutorial/{knowledge_tag:path}", response_model=APIResponse)
async def save_tutorial(knowledge_tag: str, req: TutorialSaveRequest, current_user: dict = Depends(get_current_user)):
    """保存或更新用户的教程文档（私有版本）"""
    from datetime import datetime
    conn = get_db()

    try:
        # 判断该 knowledge_tag 是否有种子记录
        seed = conn.execute(
            "SELECT id FROM tutorial_documents WHERE knowledge_tag = ? AND source_type = 'seed' AND user_id IS NULL",
            (knowledge_tag,)
        ).fetchone()

        # 查询用户是否已有私有记录
        existing = conn.execute(
            "SELECT id FROM tutorial_documents WHERE knowledge_tag = ? AND user_id = ?",
            (knowledge_tag, current_user["id"])
        ).fetchone()

        source_type = req.source_type
        parent_id = None

        if seed and not existing:
            # 用户修改种子文档 → 自动标记为 user_modified
            if source_type == "ai_generated":
                parent_id = None  # 明确选择 AI 生成则不算修改种子
            else:
                source_type = "user_modified"
                parent_id = seed["id"]

        if existing:
            # Preserve original source_type if backend auto-assigned it
            existing_row = conn.execute(
                "SELECT source_type, parent_id FROM tutorial_documents WHERE id = ?",
                (existing["id"],)
            ).fetchone()
            if existing_row:
                if existing_row["source_type"] == "user_modified" and req.source_type == "ai_generated":
                    source_type = "user_modified"
                if existing_row["parent_id"] is not None:
                    parent_id = existing_row["parent_id"]
            conn.execute(
                "UPDATE tutorial_documents SET title = ?, content = ?, source_type = ?, updated_at = ? WHERE id = ?",
                (req.title, req.content, source_type, datetime.now().isoformat(), existing["id"])
            )
            tutorial_id = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO tutorial_documents (knowledge_tag, title, content, source_type, user_id, parent_id) VALUES (?, ?, ?, ?, ?, ?)",
                (knowledge_tag, req.title, req.content, source_type, current_user["id"], parent_id)
            )
            tutorial_id = cursor.lastrowid

        conn.commit()

        return APIResponse(data={
            "tutorial_id": tutorial_id,
            "knowledge_tag": knowledge_tag,
            "source_type": source_type,
            "message": "教程已保存"
        })
    except Exception as e:
        return APIResponse(code=500, message=f"保存教程失败: {str(e)}", data=None)
    finally:
        conn.close()


@router.delete("/tutorial/{knowledge_tag:path}", response_model=APIResponse)
async def delete_tutorial(knowledge_tag: str, current_user: dict = Depends(get_current_user)):
    """删除用户的私有教程（回退到种子版本），不影响种子数据"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM tutorial_documents WHERE knowledge_tag = ? AND user_id = ?",
            (knowledge_tag, current_user["id"])
        )
        deleted = cursor.rowcount
        conn.commit()
        return APIResponse(data={
            "deleted": deleted,
            "knowledge_tag": knowledge_tag,
            "message": "已恢复为系统预置版本" if deleted else "没有需要删除的私有版本"
        })
    except Exception as e:
        return APIResponse(code=500, message=f"删除教程失败: {str(e)}", data=None)
    finally:
        conn.close()


@router.post("/tutorial/generate", response_model=APIResponse)
async def generate_tutorial(req: TutorialGenerateRequest, current_user: dict = Depends(get_current_user)):
    """AI 生成教程文档（遵循种子文档格式）"""
    from services.ai_service import call_llm

    # 构建格式参考：读取一篇种子文档作为格式样本
    fallback_format = "# 标题\n## 概述\n## 核心知识\n## 应用场景\n## 学习建议\n## 延伸阅读"
    format_sample = fallback_format
    seed_conn = None
    try:
        seed_conn = get_db()
        seed = seed_conn.execute(
            "SELECT content FROM tutorial_documents WHERE source_type = 'seed' AND user_id IS NULL LIMIT 1"
        ).fetchone()
        if seed:
            format_sample = seed["content"][:1500]
    except Exception:
        pass
    finally:
        if seed_conn:
            seed_conn.close()

    prompt = f"""你是一位资深的AI智能体学科导师，请为以下主题生成一份结构完整的学习教程。

【主题】{req.topic}
【学习目标】{req.goal or "系统掌握该知识点"}
【格式参考 — 请严格遵循此结构】
{format_sample}

【生成要求】
1. 结构必须与格式参考一致：以 # 标题开头，依次包含 ## 概述、## 核心知识、## 应用场景、## 学习建议、## 延伸阅读等章节
2. 核心概念用 **加粗** 突出
3. 代码示例使用 ```代码块```
4. 语言通俗易懂，适合大学生/初学者阅读
5. 总字数控制在 1500-3500 字
6. 直接以 "# {req.topic}" 作为文档标题开始

请直接输出完整的 Markdown 文档，不要有其他说明文字。"""

    try:
        response = await call_llm(
            current_user["id"],
            [{"role": "system", "content": "你是专业的AI智能体学科导师，擅长编写结构清晰的学习教程。只输出Markdown内容。"},
             {"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=4096
        )

        if response.startswith("LLM调用异常"):
            return APIResponse(code=500, message=f"AI 生成失败: {response}", data=None)

        # 保存生成的内容到数据库
        conn = get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO tutorial_documents (knowledge_tag, title, content, source_type, user_id, parent_id) VALUES (?, ?, ?, 'ai_generated', ?, NULL)",
                (req.knowledge_tag, req.topic, response, current_user["id"])
            )
            tutorial_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        return APIResponse(data={
            "tutorial_id": tutorial_id,
            "knowledge_tag": req.knowledge_tag,
            "title": req.topic,
            "content": response,
            "source_type": "ai_generated",
            "message": "AI 教程已生成并保存"
        })
    except Exception as e:
        return APIResponse(code=500, message=f"AI 生成教程失败: {str(e)}", data=None)
