"""Persistent, project-shaped workspaces for the guided Agent labs.

The lab terminal behaves like a normal project terminal.  Its working directory
and virtual-environment state are persisted between requests so the browser UI
can offer the same workflow as a desktop IDE.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePosixPath

from config import BASE_DIR
from services.agent_lab_specs import SPECS
from services.judge_service import get_flagship_exercise, judge_submission


WORKSPACE_ROOT = Path(BASE_DIR) / "data" / "lab_workspaces"
MAX_FILE_SIZE = 300_000
SKIP_PARTS = {".venv", "__pycache__", ".git", ".pytest_cache", ".cache"}
TUTOR_HISTORY_LIMIT = 12
logger = logging.getLogger(__name__)
TRACK_CONFIG = {
    "1": {
        "framework": "LangChain",
        "packages": ["langchain", "langchain-openai", "python-dotenv"],
        "imports": ["langchain", "langchain_openai"],
    },
    "2": {
        "framework": "LangChain + SQLAlchemy",
        "packages": ["langchain", "langchain-openai", "python-dotenv", "sqlalchemy"],
        "imports": ["langchain", "langchain_openai", "sqlalchemy"],
    },
    "3": {
        "framework": "LangGraph",
        "packages": ["langgraph", "langchain"],
        "imports": ["langgraph"],
    },
    "4": {
        "framework": "LangChain + LangGraph",
        "packages": ["langchain", "langgraph", "python-dotenv"],
        "imports": ["langchain", "langgraph"],
    },
}

TRACK_PREREQUISITES = {
    "1": ["Python 函数", "列表与字典", "异常处理基础"],
    "2": ["消息列表", "函数参数校验", "异常隔离"],
    "3": ["字典状态", "条件分支", "不可变数据"],
    "4": ["Agent 路由", "工具调用", "列表排序与过滤"],
}


def _stage_hints(stage_id: str, exercise: dict, targets: list[str], track: dict) -> list[dict]:
    """Build a small, progressive hint ladder without exposing the full answer."""
    target_label = "、".join(targets) or "核心函数"
    steps = [str(item).strip() for item in exercise.get("steps", []) if str(item).strip()]
    acceptance = [str(item).strip() for item in exercise.get("acceptance", []) if str(item).strip()]
    if stage_id == "structure":
        texts = [
            "先区分每个文件的职责：依赖、密钥、可测试逻辑和可运行入口不应混在同一个文件里。",
            "从 requirements.txt 开始，再创建 .env、solution.py 和 app.py；注意文件名大小写必须完全一致。",
            "如果不确定缺少什么，运行 tree，再对照本阶段列出的四个文件逐项检查。",
        ]
    elif stage_id == "environment":
        texts = [
            "虚拟环境的目标是让本项目的依赖版本与系统 Python、其他实验互不影响。",
            "在项目根目录创建名为 .venv 的环境；创建成功后提示符会显示当前环境名称。",
            "仍未通过时，先确认终端所在目录，再运行 python --version 检查解释器是否可用。",
        ]
    elif stage_id == "dependencies":
        texts = [
            f"先问自己：运行这个 {track['framework']} 项目最少需要哪些包？密钥不属于依赖。",
            f"requirements.txt 每行声明一个包，本关需要：{'、'.join(track['packages'])}。",
            "修改 requirements.txt 后必须重新安装；仅写入文件并不代表依赖已经进入 .venv。",
        ]
    elif stage_id == "first_llm_call":
        texts = [
            "先写出最简单的版本：加载配置 → 创建模型 → 构造消息 → 调用 → 打印 response.content",
            "先确认 .env 文件在项目根目录且 LLM_API_KEY 已填写，再用 python app.py 运行",
            "如果报 401 错误请检查 Key 和 Base URL 是否属于同一服务；超时则检查网络/代理",
            "如果输出是 AIMessage 对象而非文字，试试 print(response.content) 而不是 print(response)",
        ]
    elif stage_id == "implementation":
        ordered = " → ".join(steps) if steps else f"先完成 {target_label} 的正常路径，再补输入边界"
        done_when = "；".join(acceptance) if acceptance else "正常路径、边界输入和不可变性都满足题目契约"
        texts = [
            f"回顾 app.py 中的内联消息构造逻辑，把它移到 {target_label} 函数中。",
            f"建议按最小步骤推进：{ordered}。每完成一步就用一个最小输入手动验证。",
            f"用验收标准反查遗漏：{done_when}。",
            "如果仍然卡住，可以插入函数骨架；只补当前失败分支，不要同时重写整个函数。",
        ]
    elif stage_id == "integration":
        texts = [
            "先画出最短调用链：读取配置 → 构造输入 → 调用模型或图 → 读取结果。",
            f"app.py 应从 solution 导入 {target_label}，核心逻辑仍留在 solution.py，避免复制两份实现。",
            "先检查导入和环境变量，再检查框架调用参数；最后才排查真实模型连接。",
        ]
    else:
        texts = [
            "验收失败时先看第一个未通过阶段，不要同时修改多个文件。",
            "先修复公开阶段检查，再运行私有业务场景；私有测试用于确认你没有只适配示例。",
            "全部通过后，请准备解释关键设计选择，而不只是复述代码执行过程。",
        ]
    return [
        {"level": index, "title": ["思考问题", "方向提示", "检查清单", "骨架提示"][min(index - 1, 3)], "content": text}
        for index, text in enumerate(texts, 1)
    ]


def _feedback_guidance(label: str, detail: str) -> tuple[str, str]:
    text = f"{label} {detail}"
    if any(term in text for term in ("语法", "解析", "compile", "Syntax")):
        return "语法与运行", "先定位报错行，修正语法后再判断业务逻辑"
    if any(term in text for term in ("空", "非法", "拒绝", "边界", "类型")):
        return "输入边界", "检查参数类型、空值和临界值的处理顺序"
    if any(term in text for term in ("顺序", "结构", "字段", "返回")):
        return "输出契约", "用最小示例逐字段比较实际返回值与题目契约"
    if any(term in text for term in ("修改", "独立", "共享", "不可变", "污染")):
        return "数据不可变性", "确认是否创建了新容器，并避免复用可变的子对象"
    return "业务逻辑", "只聚焦这个失败场景，构造一个最小输入后逐步跟踪分支"


def _safe_part(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "-", str(value or ""))
    if not value:
        raise ValueError("工作区标识不能为空")
    return value[:80]


def _root(user_id: int, exercise_id: str) -> Path:
    if exercise_id not in SPECS:
        raise ValueError("未找到该实验项目")
    path = WORKSPACE_ROOT / f"user-{int(user_id)}" / _safe_part(exercise_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_path(root: Path, relative_path: str, *, allow_hidden: bool = True) -> Path:
    raw = str(relative_path or "").replace("\\", "/").strip("/")
    pure = PurePosixPath(raw)
    if not raw or pure.is_absolute() or ".." in pure.parts:
        raise ValueError("文件路径不合法")
    if len(pure.parts) > 64 or any(len(part) > 255 for part in pure.parts):
        raise ValueError("文件路径过深或名称过长")
    if not allow_hidden and any(part.startswith(".") for part in pure.parts):
        raise ValueError("该隐藏目录不可操作")
    resolved = (root / Path(*pure.parts)).resolve()
    if root.resolve() not in resolved.parents:
        raise ValueError("文件必须位于当前项目内")
    return resolved


def _course(exercise_id: str) -> dict:
    exercise = get_flagship_exercise(exercise_id) or {}
    track = TRACK_CONFIG[exercise_id.split("-", 1)[0]]
    spec = SPECS[exercise_id]
    targets = [spec.get("target")] if spec.get("target") else []
    if spec.get("mode") == "checkpoint":
        targets = ["save_checkpoint", "load_checkpoint"]

    implementation_steps = [str(item).strip() for item in exercise.get("steps", []) if str(item).strip()]
    implementation_hint = (
        f" 建议按这个顺序完成：{' → '.join(implementation_steps)}。"
        if implementation_steps else ""
    )
    test_count = max(len(spec.get("cases", [])) + int(spec.get("extra_cases", 0)), 4)
    integration_hint = ""
    if exercise_id == "1-1":
        integration_hint = " 用 build_chat_messages() 调用替换 app.py 中原有的内联消息列表，确保函数返回值直接传入 model.invoke()。"
    elif exercise_id == "1-2":
        integration_hint = " 在 app.py 中维护一个 messages 列表（初始含 system），每次用户输入追加 user → invoke → 追加 assistant，并用 append_turn_and_trim 控制长度。"
    elif exercise_id == "1-3":
        integration_hint = " 必须遍历 model.stream()，并在循环内使用 flush=True 逐片段输出；不能等所有片段结束后一次性打印。"

    # ── 实验专属实现指引（补充步骤卡片中太简略的描述） ──
    _IMPL_NOTES = {
        "1-1": (
            "接收 system_prompt 和 user_input 两个参数，先分别校验类型和非空（含 .strip() 检查），"
            "再按 system → user 顺序返回独立的消息列表。每轮调用都必须创建新列表，不能缓存或原地修改。"
        ),
        "1-2": (
            "接收 history、user_text、assistant_text、max_messages 四个参数。先深拷贝 history，"
            "追加 user → assistant 消息对；保留开头的 system 消息（如果存在），从尾部截取最近 max_messages 条。"
            "返回新列表，原 history 不变。max_messages 必须 ≥ 2。"
        ),
        "1-3": (
            "遍历可迭代 chunks，识别字符串、None、消息字典 {content: ...}、带 content 属性的 AIMessageChunk 对象，"
            "以及 content 为 [{type:'text', text:'...'}] 的内容块。忽略 None/空字符串/非 text 类型块，"
            "无法识别时抛出 ValueError。返回拼接后的完整字符串。"
        ),
        "2-1": (
            "先定义 Base = declarative_base()，再继承 Base 定义 Order 类，声明 __tablename__ 和全部11列"
            "（id, order_id, customer_name, customer_phone, product, category, amount, status, carrier, eta, created_at）。"
            "setup_order_db 用 create_engine(f'sqlite:///{db_path}') 创建引擎，用 Base.metadata.create_all(engine) 建表，"
            "再用 sessionmaker(bind=engine) 返回 Session 类。\n\n"
            "query_orders 接收 session 和 **filters，构建 query = session.query(Order)，"
            "按 filters 中的 order_id / customer_name(LIKE模糊) / category / status / carrier / min_amount / max_amount 逐项叠加 .filter()，"
            "最后遍历 query.all() 将每行转成字典返回（包含全部11列）。无匹配时返回空列表。"
        ),
    }
    impl_notes = _IMPL_NOTES.get(exercise_id, "")

    # ── 实验专属「先跑通再提取」阶段（仅 Track 1 实验有此阶段）──
    _FIRST_RUN_STAGES = {
        "1-1": {
            "id": "first_llm_call", "title": "跑通第一段 AI 对话", "icon": "ChatDotSquare",
            "instruction": (
                "在 app.py 中写下你的第一段 LangChain 代码（先不创建 solution.py）：\n"
                "1. 用 load_dotenv() 加载 .env 中的密钥\n"
                "2. 创建 ChatOpenAI 模型客户端（temperature=0.2, timeout=30）\n"
                "3. 构造内联的 system/user 消息列表\n"
                "4. 调用 model.invoke(messages)\n"
                "5. 用 print(response.content) 查看 AI 回复\n\n"
                "先把整个调用链跑通，看到模型返回的非空字符串。提取函数是下一步的事。"
            ),
            "command": "python app.py",
            "checks": ["Python 语法正确", "LLM 调用链完整", "密钥已安全配置"],
            "check_mode": "llm_call",
        },
        "1-2": {
            "id": "first_llm_call", "title": "跑通多轮对话循环", "icon": "ChatDotSquare",
            "instruction": (
                "在 app.py 中搭建多轮对话循环（先不创建 solution.py）：\n"
                "1. 用 load_dotenv() 加载 .env 中的密钥\n"
                "2. 创建 ChatOpenAI 模型客户端\n"
                "3. 用列表 messages 维护对话历史，第一条是 system 消息\n"
                "4. 用 while 循环 + input() 接收用户输入\n"
                "5. 每轮：追加 user 消息 → model.invoke() → 追加 assistant 消息 → 打印回复\n\n"
                "观察：多轮后 messages 越来越长，超出上下文窗口怎么办？下一阶段实现裁剪函数解决这个问题。"
            ),
            "command": "python app.py",
            "checks": ["Python 语法正确", "多轮对话循环完整", "密钥已安全配置"],
            "check_mode": "multi_turn",
        },
        "1-3": {
            "id": "first_llm_call", "title": "观察流式输出片段", "icon": "ChatDotSquare",
            "instruction": (
                "在 app.py 中用流式调用观察模型输出片段（先不创建 solution.py）：\n"
                "1. 用 load_dotenv() 加载 .env 中的密钥\n"
                "2. 创建 ChatOpenAI 模型客户端\n"
                "3. 用 model.stream() 替代 model.invoke()\n"
                "4. 用 for 循环遍历 stream 返回的 chunks\n"
                "5. 打印每个 chunk 的 type() 和具体内容\n\n"
                "观察：chunk 的格式不统一——有的是字符串、有的是 AIMessageChunk 对象、有的是 None。"
                "下一阶段实现 normalize_stream_chunks 把这些统一成规整的文本。"
            ),
            "command": "python app.py",
            "checks": ["Python 语法正确", "流式循环完整", "密钥已安全配置"],
            "check_mode": "stream",
        },
    }

    # ── 实现阶段标题按实验定制 ──
    _IMPL_TITLES = {
        "1-1": "提取消息构造函数",
        "1-2": "实现多轮对话裁剪函数",
        "1-3": "实现流式片段规范化函数",
        "2-1": "实现订单数据库与查询函数",
        "2-2": "实现提示模板渲染函数",
        "2-3": "实现工具调用校验函数",
        "2-4": "实现多步工具执行循环",
        "3-1": "实现状态合并函数",
        "3-2": "实现客服路由函数",
        "3-3": "实现检查点存取函数",
        "4-1": "实现 Top-K 检索函数",
        "4-2": "实现有依据回答函数",
        "4-3": "实现端到端客服入口",
    }
    impl_title = _IMPL_TITLES.get(exercise_id, f"实现 {', '.join(targets)} 函数")

    packages_example = "、".join(track["packages"])
    project_files = ["requirements.txt", ".env", "solution.py", "app.py"]
    stages = [
        {
            "id": "structure", "title": "搭好项目骨架", "icon": "FolderOpened",
            "instruction": (
                f"在项目中创建 {', '.join(project_files)}，文件名必须完全一致。"
                f".env 存放 DEEPSEEK_API_KEY（不要提交到 Git）；requirements.txt 声明框架依赖；"
                f"solution.py 实现核心函数；app.py 负责导入并运行完整对话流程。"
            ),
            "command": "tree", "checks": ["必需文件存在", "文件名大小写一致"],
            "target_file": "README.md",
        },
        {
            "id": "environment", "title": "创建虚拟环境", "icon": "Cpu",
            "instruction": (
                "在终端执行 python -m venv .venv，让项目依赖与系统 Python 隔离。"
                "创建后终端提示符会自动显示 (.venv)，后续 pip install 的包只会安装到这个隔离环境。"
            ),
            "command": "python -m venv .venv", "checks": [".venv 已创建", "Python 版本可读取"],
            "target_file": "",
        },
        {
            "id": "dependencies", "title": f"声明 {track['framework']} 依赖", "icon": "Box",
            "instruction": (
                f"在 requirements.txt 中写入以下框架包（每行一个）：\n"
                f"{packages_example}\n\n"
                f"然后在终端执行 pip install -r requirements.txt 安装全部依赖。"
                f"不要将 DEEPSEEK_API_KEY 或其他密钥写入 requirements.txt。"
            ),
            "command": "pip install -r requirements.txt", "checks": [f"包含 {', '.join(track['packages'])}", "依赖已安装到当前虚拟环境"],
            "target_file": "requirements.txt",
        },
    ]

    # 条件性加入「先跑通再提取」阶段（仅 Track 1 有此阶段）
    first_run = _FIRST_RUN_STAGES.get(exercise_id)
    if first_run is not None:
        first_run["hints"] = _stage_hints("first_llm_call", exercise, targets, track)
        first_run["target_file"] = "app.py"
        stages.append(first_run)

    stages.append({
        "id": "implementation", "title": impl_title, "icon": "EditPen",
        "instruction": (
            f"创建 solution.py，实现 {', '.join(targets)} 函数。"
            f"{implementation_hint}"
            f"{chr(10) + chr(10) + impl_notes if impl_notes else ''}"
        ),
        "command": "", "test_count": test_count,
        "checks": ["Python 语法正确", "目标函数已定义", f"{test_count} 个业务测试点通过"],
        "target_file": "solution.py",
        "micro_steps": [
            {
                "id": f"implementation-{index}",
                "title": step,
                "description": "先完成这一小步并用一个最小输入自测，再继续下一步。",
            }
            for index, step in enumerate(implementation_steps, 1)
        ],
    })
    stages.append({
        "id": "integration", "title": "接入可运行应用", "icon": "Connection",
        "instruction": (
            f"现在重构 app.py：从 solution 导入 {', '.join(targets[:1]) if targets else 'solution'}，"
            f"用函数调用替换原来内联的逻辑。其余部分保持不变。"
            f"环境变量通过 python-dotenv 的 load_dotenv() 从 .env 读取，"
            f"禁止把真实 Key 硬编码在代码中。{integration_hint}\n\n"
            f"验证：运行 python app.py，输出应与重构前完全一致。"
        ),
        "command": "python app.py", "checks": ["核心业务测试仍通过", "app.py 可解析", "框架调用方式正确", "没有疑似硬编码密钥"],
        "target_file": "app.py",
    })
    stages.append({
        "id": "acceptance", "title": "AI 工程验收", "icon": "CircleCheck",
        "instruction": (
            "AI 助教将检查项目结构、环境、依赖、代码契约和服务端私有业务场景；"
            "全部通过后再进入能力答辩。你可以多次重试，直到所有检查点通过。"
        ),
        "command": "", "checks": ["前置阶段全部通过", "私有业务场景通过"],
        "target_file": "solution.py",
    })
    for stage in stages:
        stage["hints"] = _stage_hints(stage["id"], exercise, targets, track)
    return {
        "exercise_id": exercise_id,
        "title": exercise.get("title", exercise_id),
        "module": exercise.get("module", "Agent 工程实战"),
        "description": exercise.get("description", ""),
        "framework": track["framework"],
        "packages": track["packages"],
        "framework_imports": track["imports"],
        "targets": targets,
        "project_files": project_files,
        "starter_code": exercise.get("starter_code", ""),
        "input_output": exercise.get("input_output", ""),
        "acceptance": exercise.get("acceptance", []),
        "skills": exercise.get("skills", []),
        "prerequisites": exercise.get(
            "prerequisites",
            TRACK_PREREQUISITES.get(exercise_id.split("-", 1)[0], ["Python 基础"]),
        ),
        "reflection_prompts": [
            f"不用看代码，你能解释 {', '.join(targets) or '核心模块'} 的输入、输出与失败条件吗？",
            "如果业务规则发生一个小变化，你会先修改实现、测试还是调用方？为什么？",
        ],
        "stages": stages,
    }


def _read_files(root: Path) -> list[dict]:
    items = []
    env_names = set(_virtual_envs(root))
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts) or (relative.parts and relative.parts[0] in env_names):
            continue
        if path.is_file() and path.name != ".lab-state.json":
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            items.append({"path": relative.as_posix(), "content": content[:MAX_FILE_SIZE]})
    return items[:100]


def _passed_project_snapshot(root: Path) -> dict[str, str]:
    """Capture the passed project without persisting secrets or virtual envs."""
    snapshot: dict[str, str] = {}
    for item in _read_files(root):
        path = str(item.get("path", ""))
        parts = PurePosixPath(path).parts
        if (
            not path
            or path == "VARIANT_TASK.md"
            or any(part == ".env" or part.startswith(".env.") for part in parts)
            or any(part.lower().endswith((".pem", ".key", ".p12", ".pfx")) for part in parts)
        ):
            continue
        snapshot[path] = str(item.get("content", ""))
    return snapshot


def _restore_passed_project_snapshot(root: Path, snapshot: dict[str, str]) -> None:
    """恢复通关快照中的项目文件，不删除快照之外的本地文件。"""
    if not snapshot:
        return
    for relative, content in snapshot.items():
        target = _safe_path(root, relative, allow_hidden=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        # “全部测试通过”状态必须展示可信快照，而不是当前可能已改坏的同名文件。
        # .env 和密钥类文件不会进入 snapshot，因此不会被这里覆盖。
        target.write_text(str(content), encoding="utf-8")


def _persistable_stage_result(result: dict) -> dict:
    checks = []
    for item in result.get("checks", []):
        saved = {
            key: item[key]
            for key in ("label", "passed", "detail", "category", "next_action")
            if key in item
        }
        if item.get("cases"):
            saved["cases"] = [
                {
                    key: case[key]
                    for key in (
                        "label", "passed", "detail", "category", "next_action",
                        "duration_ms", "input_args", "expected_value", "actual_value",
                    )
                    if key in case
                }
                for case in item["cases"]
            ]
        checks.append(saved)
    return {
        "title": result.get("title", ""),
        "passed": bool(result.get("passed")),
        "summary": result.get("summary", ""),
        "checks": checks,
    }


def _legacy_passed_stage_results(course: dict) -> dict[str, dict]:
    """Make old trusted pass records visible after upgrading snapshot support."""
    return {
        stage["id"]: {
            "title": stage["title"],
            "passed": True,
            "summary": "已恢复此前全部测试通过时的记录",
            "checks": [
                {
                    "label": label,
                    "passed": True,
                    "detail": "该测试点已在此前实验推进中通过",
                }
                for label in stage.get("checks", [])
            ],
        }
        for stage in course["stages"]
    }


def _canonical_passed_project_files(course: dict, solution_code: str) -> dict[str, str]:
    """Build missing support files for pass records created before full snapshots."""
    exercise_id = str(course.get("exercise_id", ""))
    target = str((course.get("targets") or ["solve"])[0])
    requirements = "\n".join(course.get("packages", [])) + "\n"

    if exercise_id == "1-1":
        app_code = f'''import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from solution import {target}

load_dotenv()
model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or None,
)
messages = {target}("你是严谨的学习助手", "请解释什么是 Agent")
response = model.invoke(messages)
print(response.content)
'''
    elif exercise_id == "1-3":
        app_code = f'''import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from solution import {target}

load_dotenv()
model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") or None,
)
parts = []
for chunk in model.stream([{{"role": "user", "content": "你好"}}]):
    text = {target}([chunk])
    print(text, end="", flush=True)
    parts.append(text)
answer = "".join(parts)
'''
    else:
        imports = []
        if "langchain" in course.get("framework_imports", []):
            imports.append("import langchain")
        if "langgraph" in course.get("framework_imports", []):
            imports.append("import langgraph")
        app_code = (
            "\n".join(imports)
            + ("\n" if imports else "")
            + f"from solution import {target}\n\n"
            + 'if __name__ == "__main__":\n'
            + f'    print("已接入 {target}，请根据 README.md 填写运行参数。")\n'
        )

    return {
        "solution.py": solution_code,
        "requirements.txt": requirements,
        "app.py": app_code,
    }


def _enrich_passed_stage_results(
    root: Path,
    course: dict,
    stage_results: dict[str, dict],
) -> dict[str, dict]:
    """Attach every real private case to restored pass records."""
    enriched = json.loads(json.dumps(stage_results, ensure_ascii=False))
    solution = root / "solution.py"
    if not solution.is_file():
        return enriched
    judged = judge_submission(
        str(course.get("exercise_id", "")),
        solution.read_text(encoding="utf-8"),
    )
    cases = _judge_case_feedback(judged)
    if not judged.get("passed") or not cases:
        return enriched

    label_hints = {
        "implementation": ("业务测试点", "核心函数行为"),
        "integration": ("核心业务测试", "核心模块业务测试"),
        "acceptance": ("私有业务场景",),
    }
    for stage_id, hints in label_hints.items():
        stage = enriched.get(stage_id)
        if not isinstance(stage, dict):
            continue
        checks = stage.setdefault("checks", [])
        target_check = next(
            (
                item
                for item in checks
                if any(hint in str(item.get("label", "")) for hint in hints)
            ),
            None,
        )
        if target_check is None:
            target_check = {
                "label": "全部私有业务测试点",
                "passed": True,
            }
            checks.append(target_check)
        target_check.update({
            "passed": True,
            "detail": f"通过 {judged['passed_count']}/{judged['total']} 个真实业务测试点",
            "cases": cases,
        })
    return enriched


def _read_directories(root: Path) -> list[str]:
    directories = []
    env_names = set(_virtual_envs(root))
    for path in sorted(root.rglob("*")):
        if not path.is_dir():
            continue
        relative = path.relative_to(root)
        if (any(part in SKIP_PARTS or part.startswith(".") for part in relative.parts)
                or (relative.parts and relative.parts[0] in env_names)):
            continue
        directories.append(relative.as_posix())
    return directories[:100]


def _virtual_envs(root: Path) -> list[str]:
    result = []
    for cfg in root.glob("*/pyvenv.cfg"):
        if cfg.is_file():
            result.append(cfg.parent.name)
    return sorted(result)


def _remove_extra_virtual_envs(root: Path, state: dict | None = None) -> list[str]:
    """Keep one predictable environment per exercise: ``.venv``."""
    removed = []
    for name in _virtual_envs(root):
        if name == ".venv":
            continue
        shutil.rmtree(root / name)
        removed.append(name)
    if state is not None and str(state.get("active_env", "")) in removed:
        state["active_env"] = ""
    return removed


def _read_state(root: Path) -> dict:
    path = root / ".lab-state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"completed_stages": [], "commands": [], "terminal_cwd": "", "active_env": ""}


def _write_state(root: Path, state: dict) -> None:
    (root / ".lab-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _assistant_runtime(user_id: int) -> dict:
    """Return safe model availability metadata without exposing credentials."""
    if os.getenv("LOCAL_GPU_MODEL_AUTO", "0") == "1":
        return {
            "status": "ready",
            "available": True,
            "model": os.getenv("LOCAL_GPU_MODEL_NAME", "tiaozhanbei-qwen3-1.7b-local"),
            "provider": "project_local_gpu",
        }
    try:
        from database import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT provider, model_name, api_key FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
    except Exception:
        # Some isolated service tests intentionally do not initialize the user tables.
        # Treat that state like an unconfigured model instead of polluting logs.
        return {"status": "setup_required", "available": False, "model": "", "provider": ""}
    configured = bool(row and str(row["api_key"] or "").strip())
    return {
        "status": "ready" if configured else "setup_required",
        "available": configured,
        "model": str(row["model_name"] or "") if row else "",
        "provider": str(row["provider"] or "") if row else "",
    }


def _tutor_history(state: dict) -> list[dict]:
    history = []
    for item in state.get("tutor_history", []):
        role = str(item.get("role", ""))
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content[:6000]})
    return history[-TUTOR_HISTORY_LIMIT:]


def _append_tutor_turn(state: dict, question: str, answer: str) -> None:
    history = _tutor_history(state)
    history.extend([
        {"role": "user", "content": question[:4000]},
        {"role": "assistant", "content": answer[:6000]},
    ])
    state["tutor_history"] = history[-TUTOR_HISTORY_LIMIT:]


def _next_course_stage(course: dict, completed_stages: list[str]) -> dict:
    completed = set(completed_stages)
    return next(
        (stage for stage in course["stages"] if stage["id"] not in completed),
        course["stages"][-1],
    )


def _assistant_welcome(course: dict, stage: dict, runtime: dict) -> str:
    if runtime["available"]:
        return (
            f"我已连接 {runtime['model'] or '你配置的模型'}，并会读取项目、阶段检查和最近对话。"
            f"当前先聚焦“{stage['title']}”；你可以让我诊断、给分级提示，或用问题检查你的理解。"
        )
    return (
        f"当前处于静态项目引导，“{stage['title']}”是下一步。"
        "配置大模型后才会启用能读取项目状态、记住对话并动态追问的 Agent 导师。"
    )


def reset_assistant(user_id: int, exercise_id: str) -> dict:
    root = _root(user_id, exercise_id)
    course = _course(exercise_id)
    state = _read_state(root)
    state["tutor_history"] = []
    state["tutor_hint_levels"] = {}
    _write_state(root, state)
    runtime = _assistant_runtime(user_id)
    stage = _next_course_stage(course, state.get("completed_stages", []))
    return {
        **runtime,
        "history": [],
        "welcome": _assistant_welcome(course, stage, runtime),
    }


def _seed(root: Path, course: dict, preserved_state: dict | None = None) -> None:
    readme = f"""# {course['title']}

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

{course['description']}

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 {course['framework']} 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
"""
    (root / "README.md").write_text(readme, encoding="utf-8")
    (root / ".gitignore").write_text(".venv/\n.env\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    preserved_state = preserved_state or {}
    state = {
        "completed_stages": [],
        "commands": [],
        "project_state": "initial",
    }
    # “初始化项目”只重置工作区，不抹掉用户曾经通过实验推进的事实。
    # 通过快照只保存 solution.py，不复制 .env 等可能含密钥的文件。
    for key in (
        "acceptance_ever_passed",
        "passed_solution_code",
        "passed_project_files",
        "passed_stage_results",
    ):
        if key in preserved_state:
            state[key] = preserved_state[key]
    _write_state(root, state)


def get_workspace(user_id: int, exercise_id: str, reset: bool = False) -> dict:
    root = _root(user_id, exercise_id)
    course = _course(exercise_id)
    preserved_state = _read_state(root) if reset else {}
    if reset:
        for child in list(root.iterdir()):
            if (
                child.name == ".venv"
                or child.name == ".env"
                or child.name.startswith(".env.")
            ):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        _seed(root, course, preserved_state)
    elif not any(root.iterdir()):
        _seed(root, course, preserved_state)
    state = _read_state(root)
    if "acceptance" in state.get("completed_stages", []):
        state["acceptance_ever_passed"] = True
        solution = root / "solution.py"
        if solution.is_file() and not state.get("passed_solution_code"):
            state["passed_solution_code"] = solution.read_text(encoding="utf-8")
        _write_state(root, state)
    removed_virtual_envs = _remove_extra_virtual_envs(root, state)
    if removed_virtual_envs:
        _write_state(root, state)
    runtime = _assistant_runtime(user_id)
    next_stage = _next_course_stage(course, state.get("completed_stages", []))
    return {
        "project_name": f"agent-lab-{exercise_id}",
        "files": _read_files(root),
        "directories": _read_directories(root),
        "virtual_env": (root / ".venv" / "pyvenv.cfg").is_file(),
        "virtual_envs": _virtual_envs(root),
        "removed_virtual_envs": removed_virtual_envs,
        "terminal_cwd": state.get("terminal_cwd", ""),
        "active_env": state.get("active_env", ""),
        "course": course,
        "completed_stages": state.get("completed_stages", []),
        "stage_results": state.get("stage_results", {}),
        "project_state": state.get("project_state", "initial"),
        "state_options": {
            "can_switch_to_passed": bool(
                state.get("acceptance_ever_passed")
                and str(state.get("passed_solution_code", "")).strip()
            ),
            "acceptance_ever_passed": bool(state.get("acceptance_ever_passed")),
        },
        "assistant": {
            **runtime,
            "history": _tutor_history(state),
            "welcome": _assistant_welcome(course, next_stage, runtime),
        },
    }


def get_progress_overview(user_id: int) -> dict:
    """Return lightweight stage progress for course trees and document badges,
    including scores from capability sessions."""
    user_root = WORKSPACE_ROOT / f"user-{int(user_id)}"
    # ── 查询能力验证分数 ──
    try:
        from services.capability_service import get_exercise_scores
        scores = get_exercise_scores(user_id)
    except Exception:
        scores = {}
    overview = {}
    for exercise_id in sorted(SPECS):
        root = user_root / _safe_part(exercise_id)
        state = _read_state(root) if root.is_dir() else {"completed_stages": []}
        score_info = scores.get(exercise_id, {})
        overview[exercise_id] = {
            "session_id": score_info.get("session_id"),
            "completed_stages": state.get("completed_stages", []),
            "virtual_env": (root / ".venv" / "pyvenv.cfg").is_file(),
            "total_stages": len(_course(exercise_id)["stages"]),
            "acceptance_passed": "acceptance" in state.get("completed_stages", []),
            "score": score_info.get("score"),
            "test_score": score_info.get("test_score"),
            "defense_score": score_info.get("defense_score"),
            "repair_score": score_info.get("repair_score"),
            "variant_score": score_info.get("variant_score"),
            "verified": score_info.get("verified", False),
            "skipped": score_info.get("skipped", False),
            "status": score_info.get("status", ""),
            "dimensions": score_info.get("dimensions", {}),
            "defense_feedback": score_info.get("defense_feedback", []),
        }
    return overview


def save_file(user_id: int, exercise_id: str, path: str, content: str) -> dict:
    root = _root(user_id, exercise_id)
    target = _safe_path(root, path, allow_hidden=True)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        raise ValueError("单个文件不能超过 300KB")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    return {"path": target.relative_to(root).as_posix(), "saved": True}


def create_directory(user_id: int, exercise_id: str, path: str) -> dict:
    root = _root(user_id, exercise_id)
    target = _safe_path(root, path, allow_hidden=True)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": target.relative_to(root).as_posix(), "created": True}


def delete_file(user_id: int, exercise_id: str, path: str) -> dict:
    root = _root(user_id, exercise_id)
    target = _safe_path(root, path, allow_hidden=True)
    if not target.is_file():
        raise ValueError("文件不存在")
    target.unlink()
    return {"path": path, "deleted": True}


def move_entry(user_id: int, exercise_id: str, path: str, destination: str) -> dict:
    root = _root(user_id, exercise_id)
    source = _safe_path(root, path, allow_hidden=True)
    target = _safe_path(root, destination, allow_hidden=True)
    if not source.exists():
        raise ValueError("文件或文件夹不存在")
    if source == root / ".venv":
        raise ValueError(".venv 是本题唯一虚拟环境，不能重命名")
    if target.exists():
        raise ValueError("目标名称已经存在")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return {"path": path, "destination": target.relative_to(root).as_posix(), "moved": True}


def duplicate_entry(user_id: int, exercise_id: str, path: str, destination: str) -> dict:
    root = _root(user_id, exercise_id)
    source = _safe_path(root, path, allow_hidden=True)
    target = _safe_path(root, destination, allow_hidden=True)
    if not source.exists():
        raise ValueError("文件或文件夹不存在")
    if source == root / ".venv":
        raise ValueError("虚拟环境不需要复制")
    if target.exists():
        raise ValueError("目标名称已经存在")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    return {"path": target.relative_to(root).as_posix(), "duplicated": True}


def delete_entry(user_id: int, exercise_id: str, path: str) -> dict:
    root = _root(user_id, exercise_id)
    target = _safe_path(root, path, allow_hidden=True)
    if not target.exists():
        raise ValueError("文件或文件夹不存在")
    if target == root / ".venv":
        raise ValueError("请使用“新建项目”重置虚拟环境")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"path": path, "deleted": True}


def list_entries(user_id: int, exercise_id: str, path: str = "") -> dict:
    """List one project directory, including hidden and virtual-env entries."""
    root = _root(user_id, exercise_id)
    directory = root if not str(path or "").strip("/\\") else _safe_path(root, path, allow_hidden=True)
    if not directory.is_dir():
        raise ValueError("目录不存在")
    entries = []
    for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if child.name == ".lab-state.json":
            continue
        relative = child.relative_to(root).as_posix()
        try:
            size = child.stat().st_size if child.is_file() else 0
        except OSError:
            size = 0
        entries.append({
            "name": child.name,
            "path": relative,
            "is_directory": child.is_dir(),
            "size": size,
            "virtual": child.is_dir() and (child / "pyvenv.cfg").is_file(),
        })
    return {"path": "" if directory == root else directory.relative_to(root).as_posix(), "entries": entries}


def read_file(user_id: int, exercise_id: str, path: str) -> dict:
    """Read a project file on demand so large environments do not block loading."""
    root = _root(user_id, exercise_id)
    target = _safe_path(root, path, allow_hidden=True)
    if not target.is_file():
        raise ValueError("文件不存在")
    size = target.stat().st_size
    if size > 2_000_000:
        return {"path": path, "content": "", "binary": True, "size": size, "message": "文件过大，无法在编辑器中预览"}
    raw = target.read_bytes()
    if b"\x00" in raw:
        return {"path": path, "content": "", "binary": True, "size": size, "message": "二进制文件无法作为文本预览"}
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = raw.decode("gb18030")
        except UnicodeDecodeError:
            return {"path": path, "content": "", "binary": True, "size": size, "message": "该文件不是可识别的文本格式"}
    return {"path": path, "content": content, "binary": False, "size": size}


def _clean_output(value: str, limit: int = 12_000) -> str:
    return (value or "").replace(str(WORKSPACE_ROOT), "<workspace>")[-limit:]


def _redact_tutor_context(value: str, limit: int = 3_000) -> str:
    """Keep useful diagnostics while removing common credential shapes."""
    text = _clean_output(value, limit=limit)
    text = re.sub(
        r"(?i)((?:api[_-]?key|authorization|token|secret|password)\s*[:=]\s*)[^\s]+",
        r"\1<redacted>",
        text,
    )
    text = re.sub(r"\b(?:sk|key)-[A-Za-z0-9_-]{12,}\b", "<redacted>", text)
    return text


def _terminal_directory(root: Path, state: dict) -> Path:
    relative = str(state.get("terminal_cwd", "") or "").replace("\\", "/").strip("/")
    try:
        candidate = root if not relative else _safe_path(root, relative, allow_hidden=True)
    except ValueError:
        candidate = root
    return candidate if candidate.is_dir() else root


def _activation_env(root: Path, command: str) -> Path | None:
    normalized = command.strip().replace("\\", "/")
    patterns = [
        # source .venv/bin/activate  /  . .venv/bin/activate  /  source .venv/Scripts/activate.bat
        r"^(?:source|\.)\s+['\"]?(.+?)/(?:bin/activate|Scripts/(?:activate(?:\.bat)?|Activate\.ps1))['\"]?$",
        # Bare Windows: .venv\Scripts\activate.bat  /  & .venv/Scripts/Activate.ps1
        r"^(?:&\s*)?['\"]?(.+?)/Scripts/(?:activate(?:\.bat)?|Activate\.ps1)['\"]?$",
        # Bare Unix path (without source/.) — user typed path directly: .venv/bin/activate
        r"^['\"]?(.+?)/bin/activate['\"]?$",
        # bash/sh wrapper: bash .venv/bin/activate  /  sh .venv/bin/activate
        r"^(?:bash|sh|zsh)\s+['\"]?(.+?)/(?:bin/activate|Scripts/(?:activate(?:\.bat)?|Activate\.ps1))['\"]?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).strip("'\"")
        try:
            target = _safe_path(root, raw, allow_hidden=True)
        except ValueError:
            return None
        if (target / "pyvenv.cfg").is_file():
            return target
    return None


def _ensure_activate_executable(venv_root: Path) -> None:
    """确保虚拟环境的激活脚本有执行权限（python -m venv 在 Linux 上创建的文件默认为 0644）"""
    try:
        for script in ["bin/activate", "Scripts/activate.bat", "Scripts/Activate.ps1"]:
            sp = venv_root / script
            if sp.is_file():
                sp.chmod(sp.stat().st_mode | 0o111)  # 添加执行权限
    except OSError:
        pass  # 权限修改失败不阻塞主流程


def _execution_environment() -> dict:
    """Build an allowlisted process environment without backend credentials."""
    allowed = (
        "PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
        "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "TZ",
    )
    return {key: os.environ[key] for key in allowed if os.environ.get(key)}


def _project_env_values(root: Path) -> dict[str, str]:
    """Read the current project .env without mutating the backend process env."""
    path = root / ".env"
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _project_api_config(root: Path) -> dict[str, str]:
    values = _project_env_values(root)
    # 找不到精确匹配时，模糊匹配包含 "api" 或 "key" 的变量名
    key_names = (
        "DEEPSEEK_API_KEY", "DEEP_SEEK_API", "OPENAI_API_KEY",
        "LLM_API_KEY", "API_KEY", "DEEPSEEK_KEY",
    )
    api_key = ""
    for name in key_names:
        v = values.get(name, "").strip()
        if v:
            api_key = v
            break
    if not api_key:
        for k, v in values.items():
            v = v.strip()
            if v and any(term in k.upper() for term in ("API_KEY", "APIKEY", "DEEPSEEK", "DEEP_SEEK", "LLM_KEY", "OPENAI_KEY")):
                api_key = v
                break
    placeholders = {
        "your-api-key", "your_api_key", "replace-me", "replace_me",
        "changeme", "test", "demo", "sk-xxx",
    }
    if api_key.lower() in placeholders or api_key.startswith(("<", "${")):
        api_key = ""
    return {
        "api_key": api_key,
        "base_url": (
            values.get("LLM_BASE_URL")
            or values.get("OPENAI_BASE_URL")
            or values.get("DEEPSEEK_BASE_URL")
            or ""
        ).strip(),
        "model_name": (
            values.get("LLM_MODEL")
            or values.get("OPENAI_MODEL")
            or values.get("DEEPSEEK_MODEL")
            or values.get("MODEL_NAME")
            or ""
        ).strip(),
    }


def apply_project_state(
    user_id: int,
    exercise_id: str,
    target_state: str,
    *,
    solution_code: str = "",
    variant_scenario: str = "",
    variant_target: str = "",
) -> dict:
    """Switch the visible project to a deliberate learning-stage snapshot."""
    if target_state not in {"initial", "passed", "repair", "variant"}:
        raise ValueError("不支持的项目状态")

    if target_state == "initial":
        return get_workspace(user_id, exercise_id, reset=True)

    root = _root(user_id, exercise_id)
    course = _course(exercise_id)
    if not any(root.iterdir()):
        _seed(root, course)
    state = _read_state(root)

    if target_state == "passed":
        # original_code 只会在服务端确认全部测试通过后写入能力会话，
        # 可作为旧工作区缺少本地通关标记时的可信迁移依据。
        if not state.get("acceptance_ever_passed") and str(solution_code).strip():
            state["acceptance_ever_passed"] = True
            state["passed_solution_code"] = solution_code
        if not state.get("acceptance_ever_passed"):
            raise ValueError("只有曾经通过实验推进后，才能跳转到全部测试通过状态")
        solution_code = str(state.get("passed_solution_code") or solution_code)
        if not solution_code.strip():
            raise ValueError("没有找到已通过全部测试点的项目快照")
        snapshot = state.get("passed_project_files")
        if not isinstance(snapshot, dict):
            snapshot = {}
        # 兼容升级前只保存 solution.py 或不完整文件集的通关记录：优先保留
        # 用户仍在的文件，再补齐可运行入口和依赖清单。
        current_files = _passed_project_snapshot(root)
        snapshot = dict(snapshot)
        support_paths = {
            "README.md",
            ".gitignore",
            "app.py",
            "requirements.txt",
            *[str(path) for path in course.get("project_files", [])],
        }
        for path in support_paths:
            if path in current_files:
                snapshot.setdefault(path, current_files[path])
        for path, content in _canonical_passed_project_files(course, solution_code).items():
            snapshot.setdefault(path, content)
        snapshot["solution.py"] = solution_code
        state["passed_project_files"] = snapshot
        _restore_passed_project_snapshot(root, snapshot)
    elif not str(solution_code).strip():
        raise ValueError("目标阶段没有可用的项目代码快照")

    # ── 写入目标文件 ──
    if target_state == "repair":
        # 故障修复：将含错代码写入独立文件 repair_target.py
        # solution.py 和其他文件一概不动，保证用户写的代码不会被覆盖
        (root / "repair_target.py").write_text(solution_code, encoding="utf-8")
    elif target_state == "passed":
        # 通关后不动 solution.py——上面的 _restore_passed_project_snapshot 已补齐支持文件
        pass
    else:
        (root / "solution.py").write_text(solution_code, encoding="utf-8")
    variant_task = root / "VARIANT_TASK.md"
    if target_state == "variant":
        task_body = (
            "# 变式迁移任务\n\n"
            f"{variant_scenario.strip()}\n\n"
            "## 当前工作区\n\n"
            f"`solution.py` 已切换为 `{variant_target or '变式目标函数'}` 的独立实现骨架。"
            "请按新场景重新完成，不要在原题答案上直接追加补丁。\n"
        )
        variant_task.write_text(task_body, encoding="utf-8")
    elif variant_task.exists():
        variant_task.unlink()

    state["project_state"] = target_state
    if target_state == "passed":
        state["completed_stages"] = [item["id"] for item in course["stages"]]
        saved_results = state.get("passed_stage_results")
        state["stage_results"] = (
            saved_results
            if isinstance(saved_results, dict) and saved_results
            else _legacy_passed_stage_results(course)
        )
        state["stage_results"] = _enrich_passed_stage_results(
            root,
            course,
            state["stage_results"],
        )
        state["passed_stage_results"] = state["stage_results"]
    elif target_state in {"repair", "variant"}:
        state["completed_stages"] = [item["id"] for item in course["stages"]]
    _write_state(root, state)
    return get_workspace(user_id, exercise_id, reset=False)


def _add_project_api_key_check(root: Path, add) -> dict[str, str]:
    config = _project_api_config(root)
    available = bool(config["api_key"])
    add(
        "项目 API Key",
        available,
        (
            "当前项目 .env 中已配置 API Key（仅校验存在性，不会显示或保存密钥）"
            if available
            else "当前项目 .env 中没有可用的 API Key。请填写 DEEPSEEK_API_KEY、OPENAI_API_KEY、LLM_API_KEY 或 API_KEY 后重新测试"
        ),
    )
    return config


def _terminal_environment(root: Path, state: dict) -> tuple[dict, str]:
    env = _execution_environment()
    env.update({"HOME": str(root), "PYTHONIOENCODING": "utf-8", "LAB_MODE": "1",
                "PIP_INDEX_URL": "https://pypi.tuna.tsinghua.edu.cn/simple"})
    active = str(state.get("active_env", "") or "")
    if active:
        try:
            target = _safe_path(root, active, allow_hidden=True)
        except ValueError:
            target = root / "__missing_environment__"
        executable_dir = target / ("Scripts" if os.name == "nt" else "bin")
        if (target / "pyvenv.cfg").is_file() and executable_dir.is_dir():
            env["VIRTUAL_ENV"] = str(target)
            env["PATH"] = str(executable_dir) + os.pathsep + env.get("PATH", "")
        else:
            active = ""
            state["active_env"] = ""
    return env, active


def _terminal_result(command: str, state: dict, exit_code: int, output: str = "") -> dict:
    return {
        "command": command,
        "output": output,
        "exit_code": exit_code,
        "cwd": state.get("terminal_cwd", ""),
        "active_env": state.get("active_env", ""),
    }


def _canonical_venv_command(command: str) -> tuple[str, str]:
    """Redirect the common venv creation form to the exercise's only environment."""
    match = re.fullmatch(
        r"((?:python(?:3(?:\.\d+)?)?|py(?:\s+-\d+(?:\.\d+)?)?)\s+-m\s+venv(?:\s+--[\w-]+)*)\s+([^\s;&|]+)",
        command.strip(),
        re.IGNORECASE,
    )
    if not match:
        return command, ""
    requested = match.group(2).strip("'\"").replace("\\", "/").strip("/")
    if requested == ".venv":
        return command, ""
    return f"{match.group(1)} .venv", f"每道题只使用一个虚拟环境，已将 {requested} 统一为 .venv。\n"


def stream_terminal(user_id: int, exercise_id: str, command: str):
    """Yield terminal events while a command is running."""
    root = _root(user_id, exercise_id)
    command = str(command or "").strip()
    state = _read_state(root)
    removed = _remove_extra_virtual_envs(root, state)
    cwd = _terminal_directory(root, state)
    output_already_streamed = False
    if not command:
        yield {"type": "done", **_terminal_result("", state, 0)}
        return
    if len(command) > 2_000:
        raise ValueError("单条命令不能超过 2000 个字符")

    yield {
        "type": "start", "command": command,
        "cwd": state.get("terminal_cwd", ""), "active_env": state.get("active_env", ""),
    }
    if removed:
        yield {"type": "output", "data": f"每道题仅保留 .venv，已清理重复环境：{', '.join(removed)}\n"}

    if command.lower() in {"clear", "cls"}:
        yield {"type": "clear"}
        yield {"type": "done", **_terminal_result(command, state, 0, "__CLEAR__")}
        return

    # ── lab-test 终端命令：在终端中运行实际判题测试 ──
    if re.match(r"^(?:python(?:3(?:\.\d+)?)?\s+(?:-m\s+)?)?lab[-_]?test\b", command.strip(), re.IGNORECASE):
        output = _handle_lab_test_command(root, exercise_id, state)
        exit_code = 0 if "全部通过" in output else 1
        state.setdefault("commands", []).append({"command": command, "exit_code": exit_code})
        state["commands"] = state["commands"][-80:]
        state["last_terminal"] = {
            "exit_code": exit_code,
            "output": _redact_tutor_context(output),
        }
        _write_state(root, state)
        output_already_streamed = True
        yield {"type": "output", "data": output}
        yield {"type": "done", **_terminal_result(command, state, exit_code, output)}
        return

    activated = _activation_env(root, command)
    if activated:
        active_env = activated.relative_to(root).as_posix()
        state["active_env"] = active_env
        # 确保 activate 脚本有执行权限（python -m venv 创建的文件可能没有）
        _ensure_activate_executable(activated)
        output, exit_code = f"已激活虚拟环境 {active_env}\n", 0
    elif command.lower() == "deactivate":
        state["active_env"] = ""
        output, exit_code = "已退出虚拟环境\n", 0
    else:
        shell_command, venv_notice = _canonical_venv_command(command)
        if venv_notice:
            yield {"type": "output", "data": venv_notice}
        try:
            parts = shlex.split(shell_command, posix=os.name != "nt")
        except ValueError as exc:
            raise ValueError(f"命令格式不完整：{exc}") from exc
        if parts and parts[0].lower() == "cd":
            requested = parts[1] if len(parts) > 1 else ""
            if len(parts) > 2:
                raise ValueError("cd 命令一次只能进入一个目录")
            try:
                target = root if not requested else (cwd / requested).resolve()
                if target != root.resolve() and root.resolve() not in target.parents:
                    raise ValueError
            except (OSError, ValueError):
                output, exit_code = "cd: 只能进入当前项目中的目录\n", 1
            else:
                if not target.is_dir():
                    output, exit_code = f"cd: 目录不存在：{requested}\n", 1
                else:
                    cwd = target
                    state["terminal_cwd"] = "" if target == root.resolve() else target.relative_to(root.resolve()).as_posix()
                    output, exit_code = "", 0
        else:
            env, _ = _terminal_environment(root, state)
            if parts == ["tree"] and shutil.which("tree", path=env.get("PATH")) is None:
                lines = ["."]
                for index, path in enumerate(sorted(cwd.rglob("*"))):
                    if index >= 5_000:
                        lines.append("… 项目内容较多，已显示前 5000 项")
                        break
                    relative = path.relative_to(cwd)
                    lines.append(f"{'    ' * (len(relative.parts) - 1)}└── {path.name}{'/' if path.is_dir() else ''}")
                output, exit_code = "\n".join(lines) + "\n", 0
            else:
                if os.name == "nt" and parts and parts[0].lower() in {"mkdir", "md"}:
                    shell_command = shell_command.replace("/", "\\")
                env["PYTHONUNBUFFERED"] = "1"
                chunks: queue.Queue[str | None] = queue.Queue()
                proc = None
                started = time.monotonic()
                try:
                    proc = subprocess.Popen(
                        shell_command, cwd=cwd, shell=True, executable=None if os.name == "nt" else "/bin/sh",
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding="utf-8", errors="replace", bufsize=1, env=env,
                    )
                    def read_process_output() -> None:
                        assert proc is not None and proc.stdout is not None
                        try:
                            for line in iter(proc.stdout.readline, ""):
                                # 将 \r 替换为 \n，防止 pip 进度条等原地刷新内容在终端中互相覆盖
                                clean_line = line.replace('\r\n', '\n').replace('\r', '\n')
                                chunks.put(clean_line)
                        finally:
                            chunks.put(None)

                    threading.Thread(target=read_process_output, daemon=True).start()
                    output_parts = []
                    stream_finished = False
                    while not stream_finished:
                        if time.monotonic() - started > 600:
                            proc.terminate()
                            notice = "\n命令运行超过 600 秒（10分钟），已停止。\n"
                            output_parts.append(notice)
                            yield {"type": "output", "data": notice}
                            exit_code = 124
                            break
                        try:
                            chunk = chunks.get(timeout=0.1)
                        except queue.Empty:
                            if proc.poll() is not None:
                                continue
                            continue
                        if chunk is None:
                            stream_finished = True
                        else:
                            clean = chunk.replace(str(WORKSPACE_ROOT), "<workspace>")
                            output_parts.append(clean)
                            yield {"type": "output", "data": clean}
                    if proc.poll() is None:
                        proc.wait(timeout=3)
                    if 'exit_code' not in locals() or exit_code != 124:
                        exit_code = proc.returncode
                    output = "".join(output_parts)
                    output_already_streamed = True
                finally:
                    if proc is not None and proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                    if proc is not None and proc.stdout is not None:
                        proc.stdout.close()

    if output and not output_already_streamed:
        yield {"type": "output", "data": output}

    if exit_code == 0 and re.search(r"(?:^|[;&|]\s*)(?:python\s+-m\s+pip|pip)\s+install\s+-r\s+requirements\.txt(?:\s|$)", command, re.IGNORECASE):
        state["installed_requirements_hash"] = _requirements_hash(root)
    state.setdefault("commands", []).append({"command": command, "exit_code": exit_code})
    state["commands"] = state["commands"][-80:]
    state["last_terminal"] = {
        "exit_code": exit_code,
        "output": _redact_tutor_context(output),
    }
    _write_state(root, state)
    yield {"type": "done", **_terminal_result(command, state, exit_code)}


def run_terminal(user_id: int, exercise_id: str, command: str) -> dict:
    """Compatibility wrapper for tests and non-streaming clients."""
    output_parts = []
    result = None
    for event in stream_terminal(user_id, exercise_id, command):
        if event["type"] == "output":
            output_parts.append(event.get("data", ""))
        elif event["type"] == "clear":
            output_parts = ["__CLEAR__"]
        elif event["type"] == "done":
            result = event
    result = result or {"command": command, "exit_code": 1, "cwd": "", "active_env": ""}
    result.pop("type", None)
    result["output"] = _clean_output("".join(output_parts))
    return result


def _requirements(root: Path) -> list[str]:
    path = root / "requirements.txt"
    if not path.is_file():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            result.append(re.split(r"[<>=!~\[]", line, 1)[0].strip().replace("_", "-"))
    return result


def _requirements_hash(root: Path) -> str:
    path = root / "requirements.txt"
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_secret(root: Path) -> bool:
    pattern = re.compile(r"(?i)(api[_-]?key|secret)\s*=\s*['\"][a-z0-9_-]{16,}['\"]")
    for name in ["solution.py", "app.py"]:
        path = root / name
        if path.is_file() and pattern.search(path.read_text(encoding="utf-8")):
            return True
    return False


def _stage_result(stage: dict, checks: list[dict]) -> dict:
    passed = all(item["passed"] for item in checks)
    return {**stage, "passed": passed, "checks": checks, "summary": "检查通过，可以进入下一步" if passed else "还有项目项需要完善"}


def _judge_check_detail(judged: dict) -> str:
    """Turn private judge output into concise, actionable learner feedback."""
    passed_count = judged.get("passed_count", 0)
    total = judged.get("total", 0)
    if judged.get("passed"):
        return f"通过 {passed_count}/{total} 个业务场景，函数已有可运行的真实行为"
    if judged.get("compile_error"):
        return f"业务测试无法运行：{judged['compile_error']}"
    failed = [
        str(item.get("description", "")).strip()
        for item in judged.get("results", [])
        if not item.get("passed") and str(item.get("description", "")).strip()
    ]
    suffix = f"；请先修正：{'、'.join(failed[:3])}" if failed else ""
    return f"仅通过 {passed_count}/{total} 个业务场景{suffix}"


def _judge_case_feedback(judged: dict) -> list[dict]:
    if judged.get("compile_error"):
        return []
    feedback = []
    for item in judged.get("results", []):
        label = str(item.get("description") or f"测试点 {item.get('case_index', '?')}")[:80]
        passed = bool(item.get("passed"))
        error_raw = str(item.get("error") or "")
        # 解析错误消息中的输入/期望/实际值
        input_args = ""
        expected_val = ""
        actual_val = ""
        if not passed and error_raw:
            for line in error_raw.split("\n"):
                stripped = line.strip()
                if stripped.startswith("输入:"):
                    input_args = stripped[3:].strip()
                elif stripped.startswith("期望:"):
                    expected_val = stripped[3:].strip()
                elif stripped.startswith("实际:"):
                    actual_val = stripped[3:].strip()
            # 取纯错误描述（第一行）
            detail = error_raw.split("\n")[0].strip()[:240]
        else:
            detail = "通过"
        category, next_action = _feedback_guidance(label, detail)
        case_feedback = {
            "label": label,
            "passed": passed,
            "detail": detail,
            "category": category,
            "next_action": "" if passed else next_action,
        }
        # 失败时附带调试信息
        if not passed and (input_args or expected_val or actual_val):
            case_feedback["input_args"] = input_args
            case_feedback["expected_value"] = expected_val
            case_feedback["actual_value"] = actual_val
            case_feedback["duration_ms"] = item.get("duration_ms", 0)
        elif passed:
            case_feedback["duration_ms"] = item.get("duration_ms", 0)
        feedback.append(case_feedback)
    return feedback


def _is_named_call(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == name)
        or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
    )


def _integration_contract_checks(exercise_id: str, tree: ast.AST) -> list[tuple[str, bool, str]]:
    """Check observable framework wiring without making a real paid model request."""
    if exercise_id == "1-1":
        builder_vars = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in ((node.targets if isinstance(node, ast.Assign) else [node.target]))
            if isinstance(target, ast.Name) and _is_named_call(node.value, "build_chat_messages")
        }
        invoke_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "invoke"
        ]
        uses_messages = any(
            any(
                _is_named_call(arg, "build_chat_messages")
                or (isinstance(arg, ast.Name) and arg.id in builder_vars)
                for arg in [*call.args, *(keyword.value for keyword in call.keywords)]
            )
            for call in invoke_calls
        )
        return [
            ("聊天模型调用", bool(invoke_calls), "已调用 model.invoke()" if invoke_calls else "需要调用 model.invoke(messages)"),
            (
                "个性化消息接入", uses_messages,
                "build_chat_messages 的结果已传入模型" if uses_messages
                else "请把 build_chat_messages(...) 的返回值传给 model.invoke()",
            ),
        ]

    if exercise_id == "1-3":
        stream_vars = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in ((node.targets if isinstance(node, ast.Assign) else [node.target]))
            if isinstance(target, ast.Name) and _is_named_call(node.value, "stream")
        }
        loops = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.For, ast.AsyncFor))
            and (_is_named_call(node.iter, "stream") or (isinstance(node.iter, ast.Name) and node.iter.id in stream_vars))
        ]
        immediate = False
        accumulates = False
        for loop in loops:
            loop_calls = [node for node in ast.walk(loop) if isinstance(node, ast.Call)]
            immediate = immediate or any(
                isinstance(call.func, ast.Name) and call.func.id == "print"
                and any(keyword.arg == "flush" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in call.keywords)
                for call in loop_calls
            ) or (
                any(isinstance(call.func, ast.Attribute) and call.func.attr == "write" for call in loop_calls)
                and any(isinstance(call.func, ast.Attribute) and call.func.attr == "flush" for call in loop_calls)
            )
            accumulates = accumulates or any(
                isinstance(call.func, ast.Attribute) and call.func.attr == "append" for call in loop_calls
            )
        normalizes = any(_is_named_call(node, "normalize_stream_chunks") for node in ast.walk(tree))
        return [
            ("真实流式调用", bool(loops), "已逐个遍历 model.stream() 片段" if loops else "需要使用 for chunk in model.stream(messages)"),
            (
                "逐片段即时输出", immediate,
                "检测到循环内刷新输出" if immediate else "请在流式循环内输出片段，并设置 flush=True",
            ),
            (
                "完整回答累积", accumulates,
                "流式片段会被累积为完整回答" if accumulates else "请在输出片段的同时 append 到结果列表",
            ),
            (
                "片段规范化接入", normalizes,
                "已调用 normalize_stream_chunks" if normalizes else "请使用 normalize_stream_chunks 处理模型片段",
            ),
        ]
    return []


def _run_integration_runtime_test(root: Path, exercise_id: str, course: dict, add, user_id: int) -> None:
    """使用用户配置的真实 API Key 实际运行 app.py，验证端到端集成行为。

    与头歌/EduCoder 平台的关键区别：
    - 头歌：用预置测试用例匹配输出字符串（黑盒）
    - 本系统：实际调用用户配置的大模型 API，真正运行学生的 Agent 代码，
      验证模型调用是否成功、输出是否正确提取

    要求用户先在「个人中心 → AI大模型配置」中配置 API Key，
    未配置时明确提示，不允许"糊弄式"通过。
    """
    # 仅对有框架接入的关卡执行运行时测试
    if not course.get("framework_imports"):
        return
    if os.getenv("LAB_RUNTIME_EXECUTION_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    app_path = root / "app.py"
    if not app_path.is_file():
        return

    app_code = app_path.read_text(encoding="utf-8")
    if len(app_code.strip()) < 30:
        add("运行时集成测试", False, "app.py 内容过短，请完成代码后再测试")
        return

    # 项目测试必须以当前工作区的 .env 为准。不能从个人中心偷偷补入 Key，
    # 否则学生删除项目 Key 后，测试仍会错误地显示通过。
    project_config = _project_api_config(root)
    if not project_config["api_key"]:
        return

    # 个人中心只为缺省的接口地址和模型名提供便利，不再提供 API Key。
    try:
        from database import get_db
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM user_llm_config WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        user_config = dict(row) if row else None
    except Exception:
        user_config = None

    user_config = user_config or {}
    api_key = project_config["api_key"]
    base_url = project_config["base_url"] or user_config.get("base_url") or "https://api.deepseek.com"
    model_name = project_config["model_name"] or user_config.get("model_name") or "deepseek-chat"

    # ── 准备运行环境 ──
    env = _execution_environment()
    env.update({
        "DEEPSEEK_API_KEY": api_key,
        "LLM_BASE_URL": base_url,
        "LLM_MODEL": model_name,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "LAB_MODE": "1",
        "PIP_INDEX_URL": "https://pypi.tuna.tsinghua.edu.cn/simple",
    })

    python_cmd = os.environ.get("PYTHON_PATH", sys.executable)
    # 不使用工作区的 .venv Python（里面可能没有安装 langchain 等依赖）
    # 集成测试直接使用系统 Python（Docker 镜像中已预装所有依赖）
    has_venv = (root / ".venv" / "pyvenv.cfg").is_file()
    if has_venv:
        # 只把 .venv 加入 PATH，让 app.py 中可能的 subprocess 能找到它
        # 但实际运行用系统 Python
        executable_dir = root / (".venv/Scripts" if os.name == "nt" else ".venv/bin")
        if executable_dir.is_dir():
            env["PATH"] = str(executable_dir) + os.pathsep + env.get("PATH", "")

    try:
        proc = subprocess.run(
            [python_cmd, "-X", "utf8", str(app_path)],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, env=env,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        combined_output = (stdout + "\n" + stderr).strip()
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        add("运行时集成测试", False, "app.py 运行超时（>30秒），请检查是否有死循环或 API 调用未设置超时")
        return

    if exit_code != 0:
        error_lower = combined_output.lower()
        if "401" in error_lower or "unauthorized" in error_lower or "invalid api key" in error_lower:
            detail = "API Key 无效或已过期，请检查「个人中心 → AI大模型配置」中的 Key 是否正确"
        elif "modulenotfounderror" in error_lower or "no module named" in error_lower:
            detail = "缺少依赖包，请在终端执行 pip install -r requirements.txt"
        elif "importerror" in error_lower or "cannot import" in error_lower:
            detail = "导入失败，请检查 solution.py 中的函数名与 app.py 中的 import 语句是否一致"
        elif "connection" in error_lower or "timeout" in error_lower or "refused" in error_lower:
            detail = f"网络连接失败，请检查 Base URL ({base_url}) 是否可访问，以及网络/代理设置"
        elif "attributeerror" in error_lower:
            detail = "对象属性访问错误，请检查 response.content 等属性是否正确使用"
        else:
            last_lines = combined_output.splitlines()[-3:]
            detail = f"运行异常(exit={exit_code})：" + "；".join(line[:120] for line in last_lines)
        add("运行时集成测试", False, detail)
        return

    # ── 运行成功 ──
    output_len = len(combined_output)
    if output_len < 20:
        add("运行时集成测试", False, f"app.py 运行成功但输出仅 {output_len} 字符，请确保 print 了模型响应内容")
    else:
        detail = f"✓ 真实 API 调用成功（模型: {model_name}），app.py 输出 {output_len} 字符"
        add("运行时集成测试", True, detail)


def _handle_lab_test_command(root: Path, exercise_id: str, terminal_state: dict) -> str:
    """处理 `python -m lab_test` / `lab-test` 终端命令。

    在项目目录下运行实际判题测试并返回终端格式的结果。
    """
    solution = root / "solution.py"
    if not solution.is_file():
        return "错误: 当前目录下没有 solution.py，请先完成核心模块后再测试。\n"

    try:
        from services.lab_test_runner import run_tests, print_terminal_results
    except ImportError:
        return "错误: lab_test_runner 模块未加载，请通过UI检查阶段。\n"

    code = solution.read_text(encoding="utf-8")
    result = run_tests(exercise_id, code)
    return print_terminal_results(result) + "\n"


def check_stage(
    user_id: int,
    exercise_id: str,
    stage_id: str,
    *,
    persist: bool = True,
    allow_runtime: bool = True,
) -> dict:
    root = _root(user_id, exercise_id)
    course = _course(exercise_id)
    stage = next((item for item in course["stages"] if item["id"] == stage_id), None)
    if not stage:
        raise ValueError("未找到该阶段")
    checks: list[dict] = []
    invalidated_stage_ids: list[str] = []
    prior_stage_results: dict[str, dict] = {}

    def add(label: str, passed: bool, detail: str, cases: list[dict] | None = None) -> None:
        item = {"label": label, "passed": bool(passed), "detail": detail}
        if cases:
            item["cases"] = cases
        checks.append(item)

    if stage_id == "structure":
        for name in course["project_files"]:
            ok = (root / name).is_file()
            add(name, ok, "文件存在，名称完全一致" if ok else f"请在项目根目录创建 {name}")
        # 跨练习依赖：项目5/6/7和毕业项目需要项目4的持久化数据库
        if exercise_id in {"2-2", "2-3", "2-4", "4-3"}:
            db_path = root.parent / "2-1" / "orders.db"
            ok = db_path.is_file() and db_path.stat().st_size > 0
            add("项目4数据库", ok,
                "orders.db 已就绪——后续项目可复用项目4的订单数据" if ok else "请先完成项目4（2-1）：用 SQLAlchemy 构建订单数据库，生成 orders.db")
    elif stage_id == "environment":
        cfg = root / ".venv" / "pyvenv.cfg"
        add("虚拟环境目录", cfg.is_file(), "检测到 .venv/pyvenv.cfg" if cfg.is_file() else "请执行 python -m venv .venv")
        add("Python 版本", sys.version_info >= (3, 11), f"当前沙箱 Python {sys.version.split()[0]}")
    elif stage_id == "dependencies":
        declared = _requirements(root)
        for package in course["packages"]:
            ok = package.lower().replace("_", "-") in declared
            add(package, ok, "已在 requirements.txt 声明" if ok else f"请把 {package} 写入 requirements.txt")
        state = _read_state(root)
        installed = bool(_requirements_hash(root)) and state.get("installed_requirements_hash") == _requirements_hash(root)
        add("虚拟环境依赖", installed, "当前 requirements.txt 已成功安装" if installed else "请先创建 .venv，再执行 pip install -r requirements.txt；修改依赖文件后需要重新安装")
    elif stage_id == "first_llm_call":
        path = root / "app.py"
        check_mode = stage.get("check_mode", "llm_call")
        if not path.is_file():
            add("app.py", False, "请先创建 app.py，完成本阶段要求的运行时代码")
        else:
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
                add("app.py 语法", True, "AST 解析成功")
                all_calls = list(ast.walk(tree))
                has_load_dotenv = any(
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "load_dotenv"
                    for node in all_calls
                )
                has_chatopenai = any(
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "ChatOpenAI"
                    for node in all_calls
                )
                has_invoke = any(
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "invoke"
                    for node in all_calls
                )
                has_stream = any(
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "stream"
                    for node in all_calls
                )
                has_content_access = any(
                    isinstance(node, ast.Attribute) and node.attr == "content"
                    and isinstance(node.value, ast.Name)
                    for node in all_calls
                )
                has_print = any(
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                    for node in all_calls
                )
                # 检查 while/for 循环结构（用于多轮对话和流式模式）
                has_loop = any(
                    isinstance(node, (ast.While, ast.For))
                    for node in all_calls
                )
                # 检查列表 append 操作（多轮对话需要）
                has_append = any(
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append"
                    for node in all_calls
                )

                add("加载环境变量", has_load_dotenv,
                    "已调用 load_dotenv()" if has_load_dotenv
                    else "请在开头添加: from dotenv import load_dotenv; load_dotenv()")
                add("创建模型客户端", has_chatopenai,
                    "已创建 ChatOpenAI 实例" if has_chatopenai
                    else "需要 model = ChatOpenAI(model=..., api_key=..., base_url=...)")

                if check_mode == "stream":
                    add("流式调用", has_stream,
                        "已调用 model.stream()" if has_stream
                        else "需要 chunks = model.stream(messages)")
                    add("遍历流式片段", has_loop,
                        "已用 for 循环遍历 chunks" if has_loop
                        else "需要 for chunk in model.stream(messages): print(chunk)")
                    add("输出片段内容", has_print,
                        "已打印流式片段" if has_print
                        else "需要在循环内 print(chunk) 观察每个片段的格式")
                elif check_mode == "multi_turn":
                    add("模型调用", has_invoke,
                        "已调用 model.invoke()" if has_invoke
                        else "需要 response = model.invoke(messages)")
                    add("消息列表维护", has_append,
                        "已用 append 追加消息" if has_append
                        else "需要用 messages.append(...) 维护对话历史")
                    add("对话循环结构", has_loop,
                        "检测到循环结构" if has_loop
                        else "需要 while 循环持续读取用户输入")
                else:  # llm_call mode (1-1)
                    add("发起模型调用", has_invoke,
                        "已调用 model.invoke(messages)" if has_invoke
                        else "需要 response = model.invoke(messages)")
                    add("读取响应正文", has_content_access or has_print,
                        "已输出 AI 回复" if (has_content_access or has_print)
                        else "需要用 print(response.content) 输出模型回复")
            except SyntaxError as exc:
                add("app.py 语法", False, f"第 {exc.lineno or '?'} 行：{exc.msg}")
            add("密钥安全", not _contains_secret(root),
                "未发现硬编码密钥" if not _contains_secret(root)
                else "疑似把真实密钥写进了代码，请改用 .env 环境变量")
            _add_project_api_key_check(root, add)
            # 尝试运行 app.py（使用用户配置的 API Key）
            if allow_runtime:
                _run_integration_runtime_test(root, exercise_id, course, add, user_id)
    elif stage_id == "implementation":
        path = root / "solution.py"
        if not path.is_file():
            add("solution.py", False, "请先创建 solution.py")
        else:
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
                add("Python 语法", True, "AST 解析成功")
                names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
                for target in course["targets"]:
                    add(target, target in names, "目标函数已定义" if target in names else f"还没有定义 {target}")
                if all(target in names for target in course["targets"]):
                    judged = judge_submission(exercise_id, source)
                    add(
                        "核心函数行为", judged.get("passed", False), _judge_check_detail(judged),
                        _judge_case_feedback(judged),
                    )
            except SyntaxError as exc:
                add("Python 语法", False, f"第 {exc.lineno or '?'} 行：{exc.msg}")
    elif stage_id == "integration":
        solution = root / "solution.py"
        if solution.is_file():
            judged = judge_submission(exercise_id, solution.read_text(encoding="utf-8"))
            add(
                "核心模块业务测试", judged.get("passed", False), _judge_check_detail(judged),
                _judge_case_feedback(judged),
            )
        else:
            add("核心模块业务测试", False, "缺少 solution.py，不能接入空模块")
        path = root / "app.py"
        if not path.is_file():
            add("app.py", False, "请先创建 app.py")
        else:
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
                add("app.py 语法", True, "可正常解析")
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module)
                # 2-1 是纯 SQLAlchemy 数据库练习，app.py 不需要 LangChain 导入
                _required_imports = ["sqlalchemy"] if exercise_id == "2-1" else course["framework_imports"]
                has_framework = any(any(name == expected or name.startswith(expected + ".") for expected in _required_imports) for name in imported)
                _missing = [e for e in _required_imports if not any(name == e or name.startswith(e + ".") for name in imported)]
                add("框架接入", has_framework, f"检测到：{', '.join(sorted(imported)) or '无导入'}" if has_framework else f"需要在 app.py 中导入：{', '.join(_missing)}")
                has_solution = any(name == "solution" or name.startswith("solution.") for name in imported)
                add("核心模块接入", has_solution, "已导入 solution" if has_solution else "请从 solution 导入你实现的函数")
                for label, passed, detail in _integration_contract_checks(exercise_id, tree):
                    add(label, passed, detail)
            except SyntaxError as exc:
                add("app.py 语法", False, f"第 {exc.lineno or '?'} 行：{exc.msg}")
            add("密钥安全", not _contains_secret(root), "未发现硬编码密钥" if not _contains_secret(root) else "疑似把真实密钥写进了代码，请改用环境变量")
            _add_project_api_key_check(root, add)

            # ── 实际运行集成测试（使用项目 .env 中的真实 API Key）──
            if allow_runtime:
                _run_integration_runtime_test(root, exercise_id, course, add, user_id)
    elif stage_id == "acceptance":
        prior = [
            check_stage(
                user_id,
                exercise_id,
                item["id"],
                persist=False,
                allow_runtime=allow_runtime,
            )
            for item in course["stages"][:-1]
        ]
        prior_stage_results = {
            item["id"]: _persistable_stage_result(item)
            for item in prior
        }
        for item in prior:
            if not item["passed"]:
                invalidated_stage_ids.append(item["id"])
            failed_details = [
                str(check.get("detail", "")).strip()
                for check in item.get("checks", [])
                if not check.get("passed") and str(check.get("detail", "")).strip()
            ]
            detail = item["summary"]
            if failed_details:
                detail = "；".join(failed_details[:3])
            add(item["title"], item["passed"], detail)
        solution = root / "solution.py"
        if solution.is_file():
            judged = judge_submission(exercise_id, solution.read_text(encoding="utf-8"))
            add(
                "私有业务场景", judged.get("passed", False), _judge_check_detail(judged),
                _judge_case_feedback(judged),
            )
        else:
            add("私有业务场景", False, "缺少 solution.py")

        # 验收阶段也执行运行时集成测试（使用用户真实 API Key）
        if allow_runtime and solution.is_file() and (root / "app.py").is_file():
            _run_integration_runtime_test(root, exercise_id, course, add, user_id)

    result = _stage_result(stage, checks)
    state = _read_state(root)
    if persist:
        completed = set(state.get("completed_stages", []))
        if stage_id == "acceptance":
            completed.difference_update(invalidated_stage_ids)
        if result["passed"]:
            completed.add(stage_id)
            if stage_id == "acceptance":
                completed.update(item["id"] for item in course["stages"])
        else:
            completed.discard(stage_id)
        state["completed_stages"] = [item["id"] for item in course["stages"] if item["id"] in completed]
        if stage_id == "acceptance" and result["passed"]:
            state["acceptance_ever_passed"] = True
            solution = root / "solution.py"
            if solution.is_file():
                state["passed_solution_code"] = solution.read_text(encoding="utf-8")
            state["project_state"] = "passed"
        stage_results = state.setdefault("stage_results", {})
        if stage_id == "acceptance":
            stage_results.update(prior_stage_results)
        stage_results[stage_id] = _persistable_stage_result(result)
        if stage_id == "acceptance" and result["passed"]:
            state["passed_project_files"] = _passed_project_snapshot(root)
            state["passed_stage_results"] = {
                item["id"]: stage_results[item["id"]]
                for item in course["stages"]
                if item["id"] in stage_results
            }
        _write_state(root, state)
    result["completed_stages"] = state.get("completed_stages", [])
    return result


def _teaching_move(question: str, history: list[dict]) -> str:
    text = question.lower()
    if any(term in text for term in ("自测", "考考我", "提问我", "检查理解")):
        return "socratic_question"
    if any(term in text for term in ("为什么", "作用", "原理")):
        return "concept_link"
    if any(term in text for term in ("提示", "卡住", "不会", "下一步")):
        return "progressive_hint"
    if any(term in text for term in ("报错", "错误", "失败", "不通过", "异常")):
        return "diagnose"
    if history and history[-1]["role"] == "assistant" and "？" in history[-1]["content"]:
        return "evaluate_response"
    return "guided_next_step"


def _stage_observation(stage_result: dict) -> tuple[str, list[dict]]:
    checks = stage_result.get("checks", [])
    failed = [item for item in checks if not item.get("passed")]
    lines = [
        f"阶段：{stage_result.get('title', '')}",
        f"检查结论：{'通过' if stage_result.get('passed') else '未通过'}",
    ]
    for item in failed[:6]:
        lines.append(f"- {item.get('label', '检查项')}：{item.get('detail', '')}")
    events = [{
        "tool": "stage_inspector",
        "label": f"检查“{stage_result.get('title', '当前阶段')}”",
        "status": "passed" if stage_result.get("passed") else "attention",
        "detail": f"{len(checks) - len(failed)}/{len(checks)} 项通过",
    }]
    return "\n".join(lines), events


async def ask_assistant(
    user_id: int,
    exercise_id: str,
    question: str,
    active_file: str = "",
    mode: str = "agent",
    stage_id: str = "",
) -> dict:
    root = _root(user_id, exercise_id)
    course = _course(exercise_id)
    question = str(question or "").strip()
    if not question:
        raise ValueError("请先输入问题")
    mode = "chat" if mode == "chat" else "agent"
    from services.guidance_context_service import build_learning_context, public_learning_context
    learning_context = build_learning_context(user_id, question, exercise_id)
    state = _read_state(root)
    history = _tutor_history(state)
    current_stage = next(
        (item for item in course["stages"] if item["id"] == stage_id),
        _next_course_stage(course, state.get("completed_stages", [])),
    )
    snippets = []
    for item in _read_files(root):
        if item["path"].endswith((".py", ".txt", ".md")) and (mode == "agent" or item["path"] == active_file):
            snippets.append(f"--- {item['path']} ---\n{item['content'][:2500]}")
    observations = [{
        "tool": "workspace_reader",
        "label": "读取项目文件",
        "status": "completed",
        "detail": f"已读取 {len(snippets)} 个文本文件",
    }]
    stage_context = "Chat 模式未执行阶段检查"
    if mode == "agent":
        inspected = check_stage(
            user_id,
            exercise_id,
            current_stage["id"],
            persist=False,
            allow_runtime=False,
        )
        stage_context, stage_events = _stage_observation(inspected)
        observations.extend(stage_events)
        terminal = state.get("last_terminal") or {}
        if terminal:
            terminal_context = str(terminal.get("output", "")).strip()
            stage_context += (
                f"\n最近终端：退出状态 {int(terminal.get('exit_code', 0))}"
                + (f"\n{terminal_context}" if terminal_context else "")
            )
            observations.append({
                "tool": "terminal_observer",
                "label": "读取最近终端结果",
                "status": "completed" if int(terminal.get("exit_code", 0)) == 0 else "attention",
                "detail": f"退出状态 {int(terminal.get('exit_code', 0))}",
            })
    teaching_move = _teaching_move(question, history)
    hint_level = 0
    if teaching_move == "progressive_hint":
        levels = state.setdefault("tutor_hint_levels", {})
        hint_level = min(int(levels.get(current_stage["id"], 0)) + 1, 3)
    role_hint = (
        "你处于 Chat 问答模式：直接解释学生的问题，不规划或声称执行项目操作。"
        if mode == "chat" else
        "你处于 Agent 项目模式：先依据工具观察进行诊断，再选择一个最合适的教学动作。"
    )
    prompt = f"""当前实验：{course['title']}，框架：{course['framework']}。
{role_hint}
学生问题：{question}
当前文件：{active_file or '未选择'}
当前阶段：{current_stage['title']}（{current_stage['id']}）
教学动作：{teaching_move}
提示级别：{hint_level or '不适用'}

工具观察：
{stage_context}

项目内容：
{chr(10).join(snippets)[:9000]}

要求：
1. 必须依据“工具观察”和项目内容回答，不能声称执行了未列出的操作。
2. 一次只推进一个学习目标：先说判断依据，再给下一步和验证方法。
3. progressive_hint 只给当前级别提示；1级只提方向，2级定位结构，3级才给局部示例，禁止直接贴完整答案。
4. socratic_question 只问一个能暴露理解程度的问题，等待学生回答；evaluate_response 要先评价上一问的回答。
5. 重点解释 LangChain/LangGraph 的对象、参数、返回值和工程作用；基础语法仅在它是根因时解释。
6. 代码和命令必须放进带语言标识的 Markdown 围栏；用中文，控制在 500 字以内。"""
    runtime = _assistant_runtime(user_id)
    if not runtime["available"]:
        return {
            "answer": "",
            "available": False,
            "status": "setup_required",
            "error": "尚未配置可用的大模型。当前仅提供左侧静态课程引导。",
            "mode": mode,
            "observations": observations,
            "learning_context": public_learning_context(learning_context),
        }
    try:
        from services.ai_service import call_llm
        from services.personalization_service import build_personalized_system_prompt
        system_prompt = build_personalized_system_prompt(
            user_id,
            question,
            "你是 Agent 工程编程实验室中的结对导师。只提供与当前实验相关的分步诊断，不直接替学生完成整个项目。",
        )
        system_prompt += (
            "\n\n" + learning_context["prompt"]
            + "\n\n你是有状态的苏格拉底式导师。参考多轮对话判断学生是在提问、求提示，还是回答了你上一轮的问题。"
            "不得重复已经给过的固定话术。"
        )
        llm_messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": prompt},
        ]
        answer = await call_llm(
            user_id,
            llm_messages,
            temperature=0.2,
            max_tokens=900,
        )
        if answer.startswith("LLM调用异常:"):
            raise ValueError(answer)
        if hint_level:
            state.setdefault("tutor_hint_levels", {})[current_stage["id"]] = hint_level
        _append_tutor_turn(state, question, answer)
        _write_state(root, state)
        return {
            "answer": answer,
            "available": True,
            "status": "ready",
            "mode": mode,
            "notice": f"已观察项目与“{current_stage['title']}”阶段",
            "pedagogical_move": teaching_move,
            "hint_level": hint_level,
            "observations": observations,
            "learning_context": public_learning_context(learning_context),
        }
    except Exception as exc:
        error_msg = str(exc)
        if "Timeout" in error_msg or "APITimeoutError" in error_msg:
            logger.warning("Lab tutor timeout for user=%s exercise=%s model=%s: %s", user_id, exercise_id, runtime.get('model', 'unknown'), exc)
            return {
                "answer": "",
                "available": False,
                "status": "error",
                "error": (
                    f"模型 {runtime.get('model', '')} 响应超时（5分钟）。可能原因：\n"
                    "1. API 服务当前繁忙，请稍后重试\n"
                    "2. API 接口地址配置有误\n"
                    "3. 网络连接不稳定\n"
                    "建议：稍等片刻后重试，若持续超时请检查 API 配置。"
                ),
                "mode": mode,
                "observations": observations,
                "learning_context": public_learning_context(learning_context),
            }
        logger.warning("Lab tutor model call failed for user=%s exercise=%s: %s", user_id, exercise_id, exc)
        return {
            "answer": "",
            "available": False,
            "status": "error",
            "error": "模型连接失败，本次没有生成导师回答。请检查模型配置后重试。",
            "mode": mode,
            "observations": observations,
            "learning_context": public_learning_context(learning_context),
        }


# ── Lab Assistant Tool Definitions ──

def _lab_tool_schemas(*, allow_writes: bool = False) -> list[dict]:
    """Build OpenAI Function Calling tool schemas for the lab assistant."""
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "read_project_file",
                "description": (
                    "读取学生项目工作区中的指定代码文件内容。"
                    "在需要查看学生代码、检查实现细节时调用此工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "文件路径，如 app.py, solution.py, requirements.txt"
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_project_files",
                "description": (
                    "列出学生项目工作区中的所有文件。"
                    "在需要了解项目结构、确认有哪些文件时调用此工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_stage_status",
                "description": (
                    "检查学生项目某个阶段的完成情况。返回测试通过/失败的详细信息。"
                    "在需要了解学生当前进度、哪些测试点未通过时调用此工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stage_id": {
                            "type": "string",
                            "description": "阶段标识符，如 structure, environment, dependencies, first_llm_call, implementation, integration, acceptance"
                        }
                    },
                    "required": ["stage_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_terminal_log",
                "description": (
                    "获取学生最近一次终端命令的输出内容。"
                    "在学生报告运行错误或需要诊断运行时问题时调用此工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_exercise_info",
                "description": (
                    "获取当前关卡的元数据信息，包括所有阶段的标题、完成状态、框架和技能标签。"
                    "在需要了解关卡整体结构、学生进度时调用此工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
    ]
    if allow_writes:
        schemas.extend([
            {
                "type": "function",
                "function": {
                    "name": "write_project_file",
                    "description": (
                        "创建或完整覆盖项目内的文本文件。用户要求创建文件、填写代码、"
                        "修改配置或修复实现时直接调用；路径只能位于当前项目内。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "项目内相对路径，如 solution.py、src/tools.py"},
                            "content": {"type": "string", "description": "要写入文件的完整文本内容"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_project_directory",
                    "description": "在当前项目内创建目录及所需父目录。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "项目内相对目录，如 src/tools"},
                        },
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_terminal_command",
                    "description": (
                        "在当前项目终端中执行命令并返回退出状态和输出。"
                        "可用于创建虚拟环境、安装依赖、运行 Python、测试和查看项目状态。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "要在当前项目目录执行的终端命令"},
                        },
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                },
            },
        ])
    return schemas


def _execute_lab_tool(tool_name: str, tool_args: dict, user_id: int, exercise_id: str) -> str:
    """Execute a lab assistant tool and return the result as a string."""
    root = _root(user_id, exercise_id)
    state = _read_state(root)

    if tool_name == "read_project_file":
        path = str(tool_args.get("path", "")).strip().lstrip("/")
        if not path:
            return "错误：未指定文件路径"
        file_path = root / path
        if not file_path.exists():
            return f"文件 {path} 不存在。可用文件：{', '.join(f['path'] for f in _read_files(root) if f['path'].endswith(('.py', '.txt', '.md', '.json', '.yml', '.yaml', '.env', '.toml')))}"
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return f"文件 {path} 无法以文本方式读取"
        if len(content) > 2000:
            return content[:2000] + f"\n\n... （文件共 {len(content)} 字符，已截断至前 2000 字符）"
        return content

    elif tool_name == "list_project_files":
        files = _read_files(root)
        if not files:
            return "项目工作区中没有文件"
        lines = []
        for f in files:
            lines.append(f"- {f['path']} ({len(f['content'])} 字符)")
        return "\n".join(lines)

    elif tool_name == "check_stage_status":
        stage_id = str(tool_args.get("stage_id", "")).strip()
        if not stage_id:
            return "错误：未指定阶段 ID"
        course = _course(exercise_id)
        stage = next((s for s in course["stages"] if s["id"] == stage_id), None)
        if not stage:
            valid = ", ".join(s["id"] for s in course["stages"])
            return f"未知阶段 {stage_id}。当前关卡的阶段：{valid}"
        try:
            result = check_stage(user_id, exercise_id, stage_id, persist=False, allow_runtime=False)
        except Exception as exc:
            return f"阶段检查失败：{exc}"
        checks = result.get("checks", [])
        failed = [c for c in checks if not c.get("passed")]
        lines = [
            f"阶段「{stage['title']}」({stage_id})",
            f"检查结论：{'✓ 通过' if result.get('passed') else '✗ 未通过'}",
            f"通过 {len(checks) - len(failed)}/{len(checks)} 项",
        ]
        if failed:
            lines.append("\n未通过的项目：")
            for c in failed[:8]:
                lines.append(f"- {c['label']}：{c.get('detail', '')}")
        return "\n".join(lines)

    elif tool_name == "get_terminal_log":
        terminal = state.get("last_terminal") or {}
        if not terminal:
            return "还没有终端执行记录"
        output = str(terminal.get("output", "")).strip()
        exit_code = int(terminal.get("exit_code", 0))
        result = f"退出状态码：{exit_code}"
        if output:
            result += f"\n\n终端输出：\n{output[:2000]}"
            if len(output) > 2000:
                result += f"\n... （共 {len(output)} 字符，已截断）"
        return result

    elif tool_name == "get_exercise_info":
        course = _course(exercise_id)
        completed = set(state.get("completed_stages", []))
        lines = [
            f"关卡：{course['title']}",
            f"框架：{course['framework']}",
            f"技能：{', '.join(course.get('skills', []))}",
            f"目标文件：{', '.join(course.get('targets', []) or [])}",
            "\n阶段列表：",
        ]
        for s in course["stages"]:
            status = "✓" if s["id"] in completed else "○"
            lines.append(f"  {status} {s['title']} ({s['id']})")
        return "\n".join(lines)

    elif tool_name == "write_project_file":
        path = str(tool_args.get("path", "")).strip()
        content = tool_args.get("content", "")
        if not isinstance(content, str):
            return "错误：文件内容必须是文本"
        saved = save_file(user_id, exercise_id, path, content)
        return f"已写入 {saved['path']}（{len(content.encode('utf-8'))} 字节）"

    elif tool_name == "create_project_directory":
        path = str(tool_args.get("path", "")).strip()
        created = create_directory(user_id, exercise_id, path)
        return f"已创建目录 {created['path']}"

    elif tool_name == "run_terminal_command":
        command = str(tool_args.get("command", "")).strip()
        if not command:
            return "错误：终端命令不能为空"
        result = run_terminal(user_id, exercise_id, command)
        output = _redact_tutor_context(result.get("output", ""), limit=3000).strip()
        summary = f"命令退出状态：{result.get('exit_code', 1)}"
        if output:
            summary += f"\n终端输出：\n{output}"
        return summary

    return f"未知工具：{tool_name}"


def _normalized_lab_tool_calls(message) -> list[dict]:
    """Return complete tool calls after LangChain has merged streamed chunks."""
    calls = []
    for index, raw_call in enumerate(getattr(message, "tool_calls", None) or []):
        if isinstance(raw_call, dict):
            name = str(raw_call.get("name") or "").strip()
            arguments = raw_call.get("args") or {}
            call_id = str(raw_call.get("id") or "").strip()
        else:
            name = str(getattr(raw_call, "name", "") or "").strip()
            arguments = getattr(raw_call, "args", {}) or {}
            call_id = str(getattr(raw_call, "id", "") or "").strip()

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (TypeError, ValueError):
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        if name:
            calls.append({
                "name": name,
                "args": arguments,
                "id": call_id or f"call_{index}",
            })
    return calls


async def ask_assistant_streaming(
    user_id: int,
    exercise_id: str,
    question: str,
    active_file: str = "",
    mode: str = "agent",
    stage_id: str = "",
):
    """Stream lab assistant response with Function Calling tool support via SSE.

    Yields SSE-formatted JSON lines: {"type":"text","content":"..."},
    {"type":"tool_call",...}, {"type":"tool_result",...}, {"type":"done",...}
    """
    import json as _json
    import uuid as _uuid
    from services.ai_service import _build_llm

    root = _root(user_id, exercise_id)
    course = _course(exercise_id)
    question = str(question or "").strip()
    if not question:
        yield _json.dumps({"type": "done", "status": "error", "error": "请先输入问题"}, ensure_ascii=False) + "\n"
        return
    mode = "chat" if mode == "chat" else "agent"

    state = _read_state(root)
    history = _tutor_history(state)
    current_stage = next(
        (item for item in course["stages"] if item["id"] == stage_id),
        _next_course_stage(course, state.get("completed_stages", [])),
    )
    completed = state.get("completed_stages", [])
    teaching_move = _teaching_move(question, history)
    hint_level = 0
    if teaching_move == "progressive_hint":
        levels = state.setdefault("tutor_hint_levels", {})
        hint_level = min(int(levels.get(current_stage["id"], 0)) + 1, 3)

    # Runtime check
    runtime = _assistant_runtime(user_id)
    if not runtime["available"]:
        yield _json.dumps({
            "type": "done", "status": "setup_required",
            "error": "尚未配置可用的大模型。当前仅提供左侧静态课程引导。",
        }, ensure_ascii=False) + "\n"
        return

    # Build lean system prompt (NOT injecting all project files)
    hints_instruction = ""
    if mode == "agent":
        hints_instruction = (
            f"教学动作：{teaching_move}。"
            + (f"提示级别：{hint_level}（1=方向, 2=结构, 3=局部示例）。" if hint_level else "")
        )

    system_prompt = f"""你是 Agent 工程编程实验室中的结对导师（苏格拉底式教学）。

【当前关卡】{course['title']}（框架：{course['framework']}）
【当前阶段】{current_stage['title']}（{current_stage['id']}，{len(completed)}/{len(course['stages'])} 已完成）
【学生问题】{question}
【当前打开文件】{active_file or '无'}
{hints_instruction}

【可用工具】使用工具按需查看代码和项目状态，不要猜测：
- read_project_file(path): 读取项目中的代码文件
- list_project_files(): 浏览项目文件列表
- check_stage_status(stage_id): 查看某阶段的测试通过情况
- get_terminal_log(): 查看最近终端输出
- get_exercise_info(): 获取关卡元数据和阶段列表
{'''- write_project_file(path, content): 创建文件或写入完整代码
- create_project_directory(path): 创建项目目录
- run_terminal_command(command): 在项目内运行终端命令并读取结果''' if mode == 'agent' else ''}

【教学规则】
1. 先诊断，再引导。用工具查看代码/测试结果后，再给建议
2. Agent 模式下，用户明确要求创建、修改、修复或运行时，直接使用工具完成，并根据终端结果继续修正；普通求助仍采用渐进提示
3. 苏格拉底式提问：一次只问一个能暴露理解程度的问题
4. 重点解释 LangChain/LangGraph 的对象、参数和工程作用；基础 Python 语法仅在它是根因时解释
5. 代码和命令放进 Markdown 围栏，中文回答控制在 500 字以内
6. progressive_hint 按要求给提示；socratic_question 只提问等待回答；evaluate_response 先评价再引导"""

    # Build messages with LangChain format for bind_tools
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
    from langchain_openai import ChatOpenAI

    def _to_lc(msg: dict):
        """Convert saved history dict to LangChain message, preserving tool metadata."""
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        # Ensure non-empty content for user/assistant; skip truly empty messages
        if not content and role != "system":
            content = " "  # single space avoids empty-content coercion issues
        if role == "system":
            return SystemMessage(content=content)
        elif role == "assistant":
            # Preserve tool_calls and additional_kwargs if they were saved
            extra_kwargs = {}
            tc_list = msg.get("tool_calls")
            if tc_list:
                extra_kwargs["tool_calls"] = tc_list
            if msg.get("additional_kwargs"):
                extra_kwargs.update(msg["additional_kwargs"])
            return AIMessage(content=content, additional_kwargs=extra_kwargs)
        elif role == "tool":
            return ToolMessage(content=content, tool_call_id=msg.get("tool_call_id", "unknown"))
        else:
            return HumanMessage(content=content)

    llm_messages = [SystemMessage(content=system_prompt)]
    for h in history:
        lc_msg = _to_lc(h)
        if lc_msg:
            llm_messages.append(lc_msg)
    llm_messages.append(HumanMessage(content=question))

    schemas = _lab_tool_schemas(allow_writes=mode == "agent")
    observations = []
    collected_answer = ""

    try:
        # Disable DeepSeek thinking mode — prevents reasoning_content which
        # requires round-trip preservation across all messages in conversation.
        # Without this, any AIMessage missing its reasoning_content causes
        # "The reasoning_content in the thinking mode must be passed back to the API."
        llm = _build_llm(user_id, temperature=0.2, max_tokens=900,
                         extra_body={"thinking": {"type": "disabled"}})
        llm_with_tools = llm.bind_tools(schemas, tool_choice="auto")

        # Tool calling loop (max 5 rounds to allow multi-step reasoning)
        for _round in range(5):
            full_content = ""
            full_reasoning = ""  # DeepSeek reasoning_content — must be passed back to API
            tool_calls_buffer: list[dict] = []
            merged_chunk = None

            try:
                async for chunk in llm_with_tools.astream(llm_messages):
                    # Tool names, IDs and JSON arguments commonly arrive in
                    # separate chunks. LangChain reconstructs the complete call
                    # when chunks are added together.
                    merged_chunk = chunk if merged_chunk is None else merged_chunk + chunk

                    # Text content
                    chunk_content = chunk.content if hasattr(chunk, 'content') and chunk.content else ""
                    if chunk_content:
                        full_content += chunk_content
                        yield _json.dumps({"type": "text", "content": chunk_content}, ensure_ascii=False) + "\n"

                    # Reasoning content (DeepSeek thinking mode) — must preserve for API
                    try:
                        if hasattr(chunk, 'additional_kwargs') and chunk.additional_kwargs:
                            reasoning = chunk.additional_kwargs.get('reasoning_content', '')
                            if reasoning:
                                full_reasoning += reasoning
                    except Exception:
                        pass  # additional_kwargs can be any type; ignore on access failure

                if merged_chunk is not None:
                    tool_calls_buffer = _normalized_lab_tool_calls(merged_chunk)
            except Exception as stream_err:
                logger.warning("Lab tutor stream error in round %s: %s", _round, stream_err)
                if merged_chunk is not None:
                    tool_calls_buffer = _normalized_lab_tool_calls(merged_chunk)
                # If we have tool calls accumulated, try to execute them and continue
                if not tool_calls_buffer or not tool_calls_buffer[0].get("name"):
                    raise  # No tool calls to salvage — re-raise

            # Check if LLM wants to call tools
            if tool_calls_buffer and tool_calls_buffer[0].get("name"):
                # Build AIMessage with tool_calls (ensure valid IDs)
                from langchain_core.messages import AIMessage as LCAIMessage
                lc_tool_calls = []
                for tc in tool_calls_buffer:
                    if tc.get("name"):
                        # Use `or` to properly fallback when id is "" (empty string)
                        valid_id = tc.get("id") or f"call_{_uuid.uuid4().hex[:12]}"
                        tool_args = tc.get("args", {})
                        if tc["name"] == "read_project_file" and not tool_args.get("path"):
                            fallback_path = active_file if active_file and (root / active_file).is_file() else ""
                            if not fallback_path and (root / "solution.py").is_file():
                                fallback_path = "solution.py"
                            if fallback_path:
                                tool_args = {**tool_args, "path": fallback_path}
                        lc_tool_calls.append({
                            "name": tc["name"],
                            "args": tool_args,
                            "id": valid_id,
                        })

                # Preserve reasoning_content for DeepSeek API compatibility
                ai_additional_kwargs = {}
                if full_reasoning:
                    ai_additional_kwargs["reasoning_content"] = full_reasoning

                ai_msg = LCAIMessage(
                    content=full_content or "",
                    tool_calls=lc_tool_calls,
                    additional_kwargs=ai_additional_kwargs,
                )
                llm_messages.append(ai_msg)

                # Execute tools
                for tc in lc_tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})
                    tool_call_id = tc["id"]  # Guaranteed non-empty

                    yield _json.dumps({
                        "type": "tool_call",
                        "tool": tool_name,
                        "args": tool_args,
                    }, ensure_ascii=False) + "\n"

                    try:
                        result = _execute_lab_tool(tool_name, tool_args, user_id, exercise_id)
                    except Exception as tool_err:
                        result = f"工具执行失败: {tool_err}"
                        logger.warning("Lab tool %s failed: %s", tool_name, tool_err)

                    mutating_tool = tool_name in {
                        "write_project_file", "create_project_directory", "run_terminal_command",
                    }
                    yield _json.dumps({
                        "type": "tool_result",
                        "tool": tool_name,
                        "status": "completed",
                        "detail": f"已执行 {tool_name}",
                        "preview": _redact_tutor_context(result[:500], limit=500),
                        "workspace_changed": mutating_tool,
                    }, ensure_ascii=False) + "\n"

                    observations.append({
                        "tool": tool_name,
                        "label": f"调用 {tool_name}",
                        "status": "completed",
                        "detail": f"已执行 {tool_name}",
                    })

                    # Use the same valid ID for ToolMessage
                    llm_messages.append(ToolMessage(content=result, tool_call_id=tool_call_id))

                continue  # Another round for LLM to process tool results

            # No tool calls — final text response
            collected_answer = full_content
            break

        else:
            # Max rounds exceeded — ask LLM to summarize
            collected_answer = full_content if full_content else ""
            if not collected_answer:
                try:
                    llm_messages.append(HumanMessage(content="请根据以上工具调用结果，给出简短总结和建议。"))
                    summary = await llm_with_tools.ainvoke(llm_messages)
                    collected_answer = summary.content or ""
                    if collected_answer:
                        yield _json.dumps({"type": "text", "content": collected_answer}, ensure_ascii=False) + "\n"
                except Exception:
                    collected_answer = "（工具调用完成，请根据结果继续提问）"

    except Exception as exc:
        error_msg = str(exc)
        logger.warning("Lab tutor streaming failed for user=%s exercise=%s: %s", user_id, exercise_id, exc)
        yield _json.dumps({
            "type": "done",
            "status": "error",
            "available": True,
            "error": error_msg,
            "observations": observations,
        }, ensure_ascii=False) + "\n"
        return

    # Persist conversation
    if collected_answer:
        if hint_level:
            state.setdefault("tutor_hint_levels", {})[current_stage["id"]] = hint_level
        _append_tutor_turn(state, question, collected_answer)
        _write_state(root, state)

    yield _json.dumps({
        "type": "done",
        "status": "ready",
        "available": True,
        "mode": mode,
        "notice": f"已观察项目与“{current_stage['title']}”阶段",
        "pedagogical_move": teaching_move,
        "hint_level": hint_level,
        "observations": observations,
    }, ensure_ascii=False) + "\n"
