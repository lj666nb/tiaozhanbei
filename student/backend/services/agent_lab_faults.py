"""Exercise-aware fault injection for the flagship programming labs.

The public prompt intentionally describes observable symptoms rather than the
line to edit.  Private metadata is kept in the capability session so the
explanation scorer can verify that a learner identified the actual mechanism.
"""

from __future__ import annotations

import re
from typing import Any


FAULT_PROFILES: dict[str, dict[str, Any]] = {
    "1-1": {
        "focus": "消息角色协议与可信/不可信内容边界",
        "root_cause": "用户消息的 role 被改成 assistant，导致模型把新输入误判为历史回复。",
        "root_terms": ["role", "user", "assistant", "角色", "消息协议"],
    },
    "1-2": {
        "focus": "上下文裁剪时保留系统规则和完整对话轮次",
        "root_cause": "裁剪前错误移除了 system 消息，导致全局规则在长对话中丢失。",
        "root_terms": ["system", "系统消息", "裁剪", "上下文", "完整轮次"],
    },
    "1-3": {
        "focus": "流式片段类型识别、空值处理与终止边界",
        "root_cause": "流式片段的空值或文本类型判断被反转，合法文本被跳过或非法片段被处理。",
        "root_terms": ["None", "空值", "chunk", "content", "流式", "类型判断"],
    },
    "2-1": {
        "focus": "ORM 动态查询条件与数据库过滤语义",
        "root_cause": "状态过滤条件在构造查询前被丢弃，查询返回了不属于目标状态的订单。",
        "root_terms": ["status", "状态", "filter", "过滤", "query", "查询条件"],
    },
    "2-2": {
        "focus": "模板变量完整性校验与重复占位符渲染",
        "root_cause": "渲染前错误丢弃了一个模板变量，导致占位符缺失或无法完整替换。",
        "root_terms": ["占位符", "变量", "values", "template", "format", "字段"],
    },
    "2-3": {
        "focus": "工具异常边界与统一结果协议",
        "root_cause": "异常捕获范围被缩窄，工具运行时错误越过统一工具消息边界向外泄漏。",
        "root_terms": ["异常", "Exception", "RuntimeError", "捕获", "工具消息", "error"],
    },
    "2-4": {
        "focus": "多步执行的失败即停、步数上限与审计轨迹",
        "root_cause": "步骤失败后仍继续执行后续工具，破坏了失败即停和副作用隔离规则。",
        "root_terms": ["失败", "停止", "break", "continue", "后续步骤", "副作用"],
    },
    "3-1": {
        "focus": "状态增量的 reducer 语义与不可变更新",
        "root_cause": "append reducer 被误判为 replace，历史列表被新值覆盖。",
        "root_terms": ["append", "replace", "reducer", "追加", "覆盖", "状态"],
    },
    "3-2": {
        "focus": "条件路由优先级与置信度边界",
        "root_cause": "0.70 的边界被错误纳入低置信度分支，路由发生 off-by-one 式偏移。",
        "root_terms": ["0.7", "边界", "置信度", "小于", "小于等于", "路由"],
    },
    "3-3": {
        "focus": "检查点隔离、深拷贝与恢复一致性",
        "root_cause": "检查点只进行了浅拷贝，嵌套状态仍与调用方共享引用。",
        "root_terms": ["深拷贝", "浅拷贝", "deepcopy", "copy", "嵌套", "引用"],
    },
    "4-1": {
        "focus": "Top-K 阈值边界、稳定排序与结果截断",
        "root_cause": "最低分过滤由大于等于变成严格大于，恰好达到阈值的文档被错误丢弃。",
        "root_terms": ["min_score", "阈值", "大于等于", ">=", "过滤", "边界"],
    },
    "4-2": {
        "focus": "回答结论与引用证据的一一对应",
        "root_cause": "生成回答时丢失了 citations，正文存在但无法追溯到证据。",
        "root_terms": ["citations", "引用", "证据", "来源", "id", "可追溯"],
    },
    "4-3": {
        "focus": "端到端 Agent 的紧急优先级与安全降级",
        "root_cause": "紧急分支被跳过，高风险请求错误进入普通业务路由。",
        "root_terms": ["urgent", "紧急", "优先级", "human", "升级", "路由"],
    },
}


def _replace(code: str, pattern: str, replacement: str, *, flags: int = 0) -> str | None:
    updated, count = re.subn(pattern, replacement, code, count=1, flags=flags)
    return updated if count else None


def _inject_after_definition(code: str, function_name: str, statement: str) -> str | None:
    pattern = rf"(?m)^(?P<indent>[ \t]*)def\s+{re.escape(function_name)}\s*\([^\n]*\)\s*:\s*\n"
    match = re.search(pattern, code)
    if not match:
        return None
    body_indent = match.group("indent") + "    "
    inserted = "\n".join(body_indent + line if line else "" for line in statement.splitlines()) + "\n"
    return code[:match.end()] + inserted + code[match.end():]


def curated_mutation_candidates(exercise_id: str, code: str) -> list[tuple[str, dict[str, Any]]]:
    """Return deterministic, concept-aligned mutation candidates for one lab."""
    profile = FAULT_PROFILES.get(exercise_id)
    if not profile:
        return []

    candidates: list[str | None] = []
    if exercise_id == "1-1":
        candidates.append(_replace(code, r'(["\']role["\']\s*:\s*)["\']user["\']', r'\1"assistant"'))
    elif exercise_id == "1-2":
        candidates.append(_inject_after_definition(
            code,
            "append_turn_and_trim",
            'history = [item for item in history if not (isinstance(item, dict) and item.get("role") == "system")]',
        ))
    elif exercise_id == "1-3":
        candidates.extend([
            _replace(code, r"if\s+(\w+)\s+is\s+None\s*:", r"if \1 is not None:"),
            _replace(code, r'(\.get\(["\']type["\']\)\s*)==\s*(["\']text["\'])', r"\1!= \2"),
        ])
    elif exercise_id == "2-1":
        candidates.append(_inject_after_definition(
            code,
            "query_orders",
            'filters = {key: value for key, value in filters.items() if key != "status"}',
        ))
    elif exercise_id == "2-2":
        candidates.append(_inject_after_definition(
            code,
            "render_support_prompt",
            'values = {key: value for index, (key, value) in enumerate(values.items()) if index != 0}',
        ))
    elif exercise_id == "2-3":
        candidates.extend([
            _replace(code, r"except\s+Exception\s+as\s+(\w+)\s*:", r"except ValueError as \1:"),
            _replace(code, r"except\s+Exception\s*:", "except ValueError:"),
        ])
    elif exercise_id == "2-4":
        candidates.extend([
            _replace(code, r"(?m)^(\s*)break\s*$", r"\1continue"),
            _replace(code, r"(>=\s*max_steps)", r"> max_steps"),
        ])
    elif exercise_id == "3-1":
        candidates.extend([
            _replace(code, r"(==\s*)[\"']append[\"']", r'\1"replace"'),
            _replace(code, r"(reducer\s*==\s*)[\"']append[\"']", r'\1"replace"'),
        ])
    elif exercise_id == "3-2":
        candidates.append(_replace(code, r"<\s*0\.7(?!\d)", "<= 0.7"))
    elif exercise_id == "3-3":
        candidates.append(_replace(code, r"copy\.deepcopy\s*\(", "copy.copy("))
    elif exercise_id == "4-1":
        candidates.extend([
            _replace(code, r">=\s*min_score", "> min_score"),
            _replace(code, r"min_score\s*<=", "min_score <"),
        ])
    elif exercise_id == "4-2":
        candidates.extend([
            _replace(code, r'(["\']citations["\']\s*:\s*)\w+', r"\1[]"),
            _replace(code, r'(citations\s*=\s*)\[[^\n]*\]', r"\1[]"),
        ])
    elif exercise_id == "4-3":
        candidates.extend([
            _replace(code, r"if\s+request\.get\([\"']urgent[\"']\)\s*:", 'if False and request.get("urgent"):'),
            _replace(code, r"if\s+request\[[\"']urgent[\"']\]\s*:", 'if False and request["urgent"]:'),
        ])

    return [(candidate, dict(profile)) for candidate in candidates if candidate and candidate != code]
