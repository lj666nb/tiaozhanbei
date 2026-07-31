"""
编程实验室终端测试运行器 — 学生可在终端中运行 python -m lab_test 直接测试代码。

用法（在项目终端中）:
    python lab_test_runner.py <solution.py路径>

输出会以彩色终端格式展示每个测试点的通过/失败情况，
让学生无需点击"AI检查"按钮就能快速验证代码。

设计意图（对齐 EduCoder / 头歌模式）:
    - 实际执行代码（黑盒判题），不是字符串匹配
    - 每个测试点独立运行，即时反馈
    - 失败时显示预期值 vs 实际值
    - 通过时显示 ✓，失败时显示 ✗
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from services.agent_lab_specs import SPECS, FLAGSHIP_IDS
from services.judge_service import RUNNER


def run_tests(exercise_id: str, code: str, timeout: int = 8) -> dict:
    """运行测试并返回结构化结果。"""
    if exercise_id not in SPECS:
        return {
            "passed": False,
            "total": 0,
            "passed_count": 0,
            "compile_error": f"未找到实验 {exercise_id} 的判题配置",
            "results": [],
            "execution_time": 0,
        }

    started = time.perf_counter()

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            solution_path = Path(temp_dir) / "submission.py"
            spec_path = Path(temp_dir) / "spec.json"
            runner_path = Path(temp_dir) / "runner.py"
            solution_path.write_text(code, encoding="utf-8")
            spec_path.write_text(json.dumps(SPECS[exercise_id], ensure_ascii=False), encoding="utf-8")
            runner_path.write_text(RUNNER, encoding="utf-8")

            proc = subprocess.run(
                [
                    os.environ.get("PYTHON_PATH", sys.executable),
                    "-I", "-X", "utf8",
                    str(runner_path), str(solution_path), str(spec_path),
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )

        exec_time = round(time.perf_counter() - started, 3)

        marker_lines = [
            line for line in (proc.stdout or "").splitlines()
            if line.startswith("__JUDGE_RESULT__")
        ]
        if proc.returncode != 0 or not marker_lines:
            error_lines = (proc.stderr or proc.stdout or "提交代码未能完成执行").strip().splitlines()
            error = error_lines[-1][:300] if error_lines else "提交代码未能完成执行"
            return {
                "passed": False,
                "total": 0,
                "passed_count": 0,
                "compile_error": error,
                "results": [],
                "execution_time": exec_time,
            }

        raw_results = json.loads(marker_lines[-1].removeprefix("__JUDGE_RESULT__"))
        results = [
            {"case_index": index, **item}
            for index, item in enumerate(raw_results, 1)
        ]
        passed_count = sum(1 for r in results if r["passed"])
        return {
            "passed": passed_count == len(results),
            "total": len(results),
            "passed_count": passed_count,
            "compile_error": None,
            "results": results,
            "execution_time": exec_time,
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "total": 0,
            "passed_count": 0,
            "compile_error": f"执行超时（>{timeout} 秒）",
            "results": [],
            "execution_time": round(time.perf_counter() - started, 3),
        }


def print_terminal_results(result: dict) -> str:
    """将测试结果格式化为终端友好的彩色文本。"""
    lines = []
    sep = "─" * 60
    lines.append(f"\n{sep}")
    lines.append("  🧪 Agent Lab 测试结果")
    lines.append(sep)

    if result.get("compile_error"):
        lines.append(f"  ❌ 执行失败: {result['compile_error']}")
        lines.append(sep)
        return "\n".join(lines)

    passed = result["passed_count"]
    total = result["total"]
    symbol = "✅" if result["passed"] else "❌"
    lines.append(f"  {symbol} {passed}/{total} 通过  ({result['execution_time']}s)")

    for case in result.get("results", []):
        idx = case["case_index"]
        desc = case.get("description", f"测试点 {idx}")
        if case["passed"]:
            lines.append(f"  ✓ [{idx}] {desc} ({case.get('duration_ms', 0)}ms)")
        else:
            error = case.get("error", "未满足预期")
            lines.append(f"  ✗ [{idx}] {desc}")
            lines.append(f"       → {error}")

    lines.append(sep)
    if result["passed"]:
        lines.append("  🎉 全部通过！可以进入下一阶段。")
    else:
        remaining = total - passed
        lines.append(f"  💡 还有 {remaining} 个测试点未通过，请修改后重试。")
    lines.append(sep)
    return "\n".join(lines)


def run_integration_with_real_api(
    exercise_id: str,
    working_dir: str | Path,
    solution_code: str,
    app_code: str | None = None,
    api_key: str = "",
    base_url: str = "https://api.deepseek.com",
    model_name: str = "deepseek-v4-pro",
    timeout: int = 30,
) -> dict:
    """使用用户真实 API Key 运行集成测试。

    Returns:
        {
            "passed": bool,
            "exit_code": int,
            "output": str,
            "checks": [{"label": str, "passed": bool, "detail": str}, ...]
        }
    """
    working_dir = Path(working_dir)
    checks: list[dict] = []
    output = ""
    exit_code = -1

    if not api_key:
        return {
            "passed": False, "exit_code": -1, "output": "",
            "checks": [{"label": "API 配置", "passed": False,
                        "detail": "请先在「个人中心 → AI大模型配置」中配置 API Key"}],
        }

    # 写入 solution.py
    sol_path = working_dir / "solution.py"
    sol_path.write_text(solution_code, encoding="utf-8")

    # 写入 app.py
    app_path = working_dir / "app.py"
    _app_code = app_code or ""
    if _app_code.strip():
        app_path.write_text(_app_code, encoding="utf-8")

    # 先测试 solution.py 的核心函数
    from services.judge_service import judge_submission
    judged = judge_submission(exercise_id, solution_code)
    checks.append({
        "label": "核心函数业务测试",
        "passed": judged.get("passed", False),
        "detail": (
            f"通过 {judged.get('passed_count', 0)}/{judged.get('total', 0)} 个业务场景"
            if not judged.get("compile_error")
            else judged["compile_error"]
        ),
    })

    # 测试 app.py 能否运行
    if _app_code.strip():
        env = os.environ.copy()
        env.update({
            "DEEPSEEK_API_KEY": api_key,
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model_name,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        })
        try:
            proc = subprocess.run(
                [sys.executable, "-X", "utf8", str(app_path)],
                cwd=working_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout, env=env,
            )
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            exit_code = proc.returncode

            if exit_code == 0:
                checks.append({
                    "label": "真实 API 调用",
                    "passed": True,
                    "detail": f"app.py 成功运行，使用模型: {model_name}",
                })
                if len(output.strip()) > 20:
                    checks.append({
                        "label": "模型响应提取",
                        "passed": True,
                        "detail": f"输出 {len(output.strip())} 字符，响应内容正确提取",
                    })
                else:
                    checks.append({
                        "label": "模型响应提取",
                        "passed": False,
                        "detail": "输出内容过短，可能未正确提取模型响应",
                    })
            else:
                error_hint = _analyze_app_error(output, exit_code)
                checks.append({
                    "label": "真实 API 调用",
                    "passed": False,
                    "detail": f"exit_code={exit_code} — {error_hint}",
                })
        except subprocess.TimeoutExpired:
            checks.append({
                "label": "真实 API 调用",
                "passed": False,
                "detail": f"执行超时（>{timeout}秒），检查是否有死循环或阻塞调用",
            })
    else:
        checks.append({
            "label": "应用运行",
            "passed": False,
            "detail": "app.py 为空或不存在",
        })

    all_passed = all(c["passed"] for c in checks)
    return {
        "passed": all_passed, "exit_code": exit_code,
        "output": output[:3000], "checks": checks,
    }


def _analyze_app_error(output: str, exit_code: int) -> str:
    """分析 app.py 运行失败的可能原因。"""
    combined = output.lower()
    if "401" in combined or "unauthorized" in combined or "invalid api key" in combined:
        return "API Key 无效或已过期，请检查「个人中心 → AI大模型配置」"
    if "modulenotfounderror" in combined or "no module named" in combined:
        return "缺少依赖包，请检查 requirements.txt 是否正确安装"
    if "importerror" in combined or "cannot import" in combined:
        return "导入失败，请检查 solution 模块中的函数名是否正确"
    if "attributeerror" in combined:
        return "对象属性访问错误，请检查调用的方法或属性是否存在"
    if "keyerror" in combined:
        return "字典键不存在，请检查消息字典的 key 是否正确（role/content）"
    if "valueerror" in combined:
        return "输入值不符合要求，请检查参数校验逻辑"
    if "connection" in combined or "refused" in combined or "timeout" in combined:
        return "网络连接失败，请检查 LLM_BASE_URL 是否正确配置"
    if exit_code == 1 and not combined.strip():
        return "程序无输出就退出了，可能是缺少 print 语句或主逻辑未执行"
    return f"运行失败，检查终端输出中的 Traceback"


# ── 命令行入口 ───────────────────────────────────────────────

def main():
    """作为命令行工具运行测试。"""
    import argparse

    parser = argparse.ArgumentParser(description="Agent Lab 测试运行器")
    parser.add_argument(
        "file", nargs="?", default="solution.py",
        help="要测试的 Python 文件（默认: solution.py）",
    )
    parser.add_argument(
        "--exercise", "-e", default="",
        help="实验编号（如 1-1）。默认从当前目录自动检测。",
    )
    parser.add_argument(
        "--integration", "-i", action="store_true",
        help="运行集成测试（需要 app.py 和 Mock LLM 服务器）",
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="以 JSON 格式输出结果",
    )
    args = parser.parse_args()

    solution_path = Path(args.file)
    if not solution_path.is_absolute():
        solution_path = Path.cwd() / args.file

    if not solution_path.is_file():
        print(f"错误：找不到文件 {solution_path}")
        sys.exit(1)

    exercise_id = args.exercise
    if not exercise_id:
        # 尝试从目录名或环境变量中检测
        cwd_name = Path.cwd().name
        # agent-lab-1-1 → 1-1
        parts = cwd_name.replace("agent-lab-", "").split("-")
        if len(parts) >= 2:
            exercise_id = f"{parts[0]}-{parts[1]}"
        # 环境变量
        exercise_id = os.environ.get("LAB_EXERCISE_ID", exercise_id)

    if not exercise_id or exercise_id not in SPECS:
        available = ", ".join(sorted(SPECS.keys()))
        print(f"错误：未找到有效的实验编号。可用实验: {available}")
        print(f"提示：通过 --exercise 参数指定，如 --exercise 1-1")
        sys.exit(1)

    code = solution_path.read_text(encoding="utf-8")

    if args.integration:
        app_path = Path.cwd() / "app.py"
        app_code = app_path.read_text(encoding="utf-8") if app_path.is_file() else ""
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("LLM_MODEL", "deepseek-v4-pro")
        result = run_integration_with_real_api(exercise_id, Path.cwd(), code, app_code, api_key, base_url, model)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n🔗 集成测试结果 — 实验 {exercise_id}")
            print("─" * 60)
            for check in result["checks"]:
                symbol = "✓" if check["passed"] else "✗"
                print(f"  {symbol} {check['label']}: {check['detail']}")
            print("─" * 60)
            if result["passed"]:
                print("  🎉 集成测试全部通过！")
            else:
                print("  💡 还有检查项未通过")
                if result["output"].strip():
                    print(f"\n  程序输出:\n  {'─' * 40}")
                    for line in result["output"].strip().splitlines()[-20:]:
                        print(f"  │ {line}")
                    print(f"  {'─' * 40}")
            print()
    else:
        result = run_tests(exercise_id, code)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(print_terminal_results(result))

    sys.exit(0 if result.get("passed") else 1)


if __name__ == "__main__":
    main()
