# 人机协作 - Human-in-the-Loop

## 1. 概念与动机

### 1.1 什么是 Human-in-the-Loop（HITL）

Human-in-the-Loop（人机协作 / 人在回路）是指**在智能体（Agent）的自主决策和执行链路中，有策略地嵌入人工判断、确认或干预节点**的设计范式。它不是"AI 做不了才找人"，而是一种**主动的架构设计**：把人的判断力视为系统不可或缺的组成部分。

### 1.2 为什么需要 HITL

LLM 驱动的智能体具备强大的推理和工具调用能力，但存在固有的不可靠性：

| 风险类型 | 典型场景 | 纯自动模式的后果 |
|---------|---------|----------------|
| **幻觉（Hallucination）** | 捏造不存在的 API 参数、虚构数据 | 下游系统收到无效指令 |
| **目标误对齐（Goal Misalignment）** | 对模糊指令做出极端解读 | 执行违背用户意图的操作 |
| **权限滥用** | 获得了删除/写权限后过度操作 | 数据丢失、配置破坏 |
| **级联错误** | 前一步错误输出成为下一步输入 | 小错放大为系统级故障 |
| **合规风险** | 在受监管领域自主决策 | 法律与合规问题 |

HITL 的核心思想是：**把自动化程度控制在"恰到好处"的水平，在效率与安全之间找到平衡**。

**Image-Prompt(human in the loop concept overview):** A flat-design minimalist 2D vector illustration introducing Human-in-the-Loop concept. Central composition shows a continuous loop diagram: AI Agent (rounded robot icon) → Decision Point (diamond shape with question mark) → Human Reviewer (human silhouette icon) → Approved Action (checkmark circle). Tech light blue #409EFF flow arrows connect nodes. Five risk type icons arranged around the loop: Hallucination (ghost icon), Goal Misalignment (crossed arrows), Permission Abuse (lock broken), Cascade Error (domino falling), Compliance Risk (gavel). White background with dark blue #1a1a2e labels. Academic atmosphere.

---

## 2. HITL 的三种设计模式

### 2.1 审批节点模式（Approval Node Pattern）

**思想**：在关键决策点插入"审批门"，智能体流程到达此处后挂起，等待人工确认后继续。

```
[LLM推理] --> [工具选择] --> [审批节点] --[通过]--> [执行工具] --> [LLM推理] --> ...
                                |
                               [拒绝] --> [返回修改/重新推理]
```

**适用场景**：
- 数据库写操作前的最终确认
- 发送邮件/消息给外部用户前
- 金额/资源分配决策
- 代码部署到生产环境前

### 2.2 异常上报模式（Exception Escalation Pattern）

**思想**：智能体在置信度低、遇到未知情况、或触发预设边界条件时，**主动将决策权上交给人类**。

```
[LLM推理] --> [置信度评估] --[高置信度]--> [自动执行]
                              |
                             [低置信度/异常] --> [上报人工] --> [人工决策] --> [注入结果继续]
```

**适用场景**：
- 客服对话中遇到超出知识库范围的问题
- 代码审查中检测到潜在安全漏洞
- 数据异常检测中发现的离群值
- 模型输出不符合预期格式时

### 2.3 定期汇报模式（Periodic Reporting Pattern）

**思想**：智能体在长时间运行的任务中，定期生成进度摘要并提交人工审阅。人类可以在任意汇报点介入（调整方向、暂停或终止）。

```
[子任务1] --> [汇报点1] --> [子任务2] --> [汇报点2] --> [子任务3] --> [汇报点3] --> [完成]
   |                         |                         |
   v                         v                         v
[进度摘要]                [进度摘要]                [进度摘要]
   |                         |                         |
   v                         v                         v
[人工审阅]                [人工审阅]                [人工审阅]
```

**适用场景**：
- 批量数据处理任务（如迁移 10 万条记录，每 1000 条汇报一次）
- 长时间运行的调研 Agent
- 自动化测试套件的阶段性结果
- 爬虫/数据采集任务

### 2.4 三种模式对比

| 维度 | 审批节点模式 | 异常上报模式 | 定期汇报模式 |
|------|------------|------------|------------|
| **触发方式** | 流程固定节点（主动） | 条件触发（被动） | 时间/进度触发（主动） |
| **人的角色** | 审批者 / 把关人 | 救火员 / 专家决策者 | 监督者 / 方向盘 |
| **延迟影响** | 每个审批点引入等待 | 仅在异常时引入等待 | 非阻塞（可异步审阅） |
| **自动化覆盖率** | 中（关键节点需要人） | 高（大部分自动） | 高（人可在事后介入） |
| **实现复杂度** | 低-中 | 中（需置信度评估） | 中（需进度追踪） |
| **典型实现** | `interrupt()` + 状态恢复 | 条件路由 + 通知 | 定时回调 + 摘要生成 |

**Image-Prompt(three HITL design patterns):** A flat-design minimalist 2D vector illustration showing three Human-in-the-Loop design patterns in a horizontal triptych layout. Panel 1 "审批节点模式": linear flow with a gate/checkpoint node where human approval interrupts the pipeline. Panel 2 "异常上报模式": flow with a branching confidence evaluator sending low-confidence cases upward to a human icon. Panel 3 "定期汇报模式": timeline with periodic report checkpoints and human review icons. All using tech light blue #409EFF for active elements, white background, dark blue #1a1a2e labels. Thin-line icons. Academic pattern comparison layout.

---

## 3. 权限分级体系

### 3.1 操作风险分级

一个严谨的 HITL 系统应对所有操作进行风险定级，并据此决定人工参与的程度：

| 权限级别 | 操作类型 | 典型操作 | HITL 策略 | 审批要求 |
|---------|---------|---------|----------|---------|
| **L0 - 只读** | 查询、检索、读取 | `SELECT`、`GET`、文件读取、日志查看 | 自动通过，记录日志 | 无 |
| **L1 - 低风险写入** | 创建草稿、缓存写入 | 创建临时文件、Redis 写入、草稿保存 | 自动执行，可撤回 | 无（事后可审计） |
| **L2 - 中等风险修改** | 数据更新、配置修改 | `UPDATE`、`PUT`、修改配置文件 | 单次人工确认 | 单人审批 |
| **L3 - 高风险操作** | 删除、权限变更 | `DELETE`、`DROP`、修改 IAM 策略、发送外部消息 | 需人工确认 + 二次确认 | 单人审批 + 确认弹窗 |
| **L4 - 危险操作** | 生产部署、财务操作 | 生产发布、转账、批量删除用户数据 | 多级审批 | 至少两人审批 |
| **L5 - 关键操作** | 系统级变更、合规决策 | 数据库迁移、安全策略变更、法律决策 | 强制人工执行 | 多人会签 |

### 3.2 权限检查中间件

```python
"""
权限分级检查中间件
演示如何在工具调用前自动检查操作风险级别，并触发相应的 HITL 流程
"""
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import functools
import logging

logger = logging.getLogger(__name__)


class RiskLevel(IntEnum):
    """操作风险级别"""
    READ_ONLY = 0       # 只读：自动通过
    LOW_WRITE = 1       # 低风险写入：自动执行，可撤回
    MEDIUM_MUTATE = 2   # 中等风险修改：单次人工确认
    HIGH_RISK = 3       # 高风险操作：需确认 + 二次确认
    DANGEROUS = 4       # 危险操作：多级审批
    CRITICAL = 5        # 关键操作：强制多人会签


@dataclass
class OperationContext:
    """操作上下文，用于审批决策"""
    operation_name: str
    risk_level: RiskLevel
    target_resource: str
    estimated_impact: str
    requested_by: str
    metadata: dict = field(default_factory=dict)


class ApprovalRequired(Exception):
    """需要审批时抛出的异常"""
    def __init__(self, context: OperationContext, approval_id: str):
        self.context = context
        self.approval_id = approval_id
        super().__init__(f"操作 '{context.operation_name}' 需要审批 (ID: {approval_id})")


class ApprovalResult:
    """审批结果"""
    def __init__(self, approved: bool, approver: str, comment: str = ""):
        self.approved = approved
        self.approver = approver
        self.comment = comment


# ============================================================
# 风险级别门控装饰器
# ============================================================

def require_approval(risk_level: RiskLevel):
    """
    装饰器：为函数添加风险级别检查。
    调用工具时，若风险级别 >= MEDIUM_MUTATE，则触发审批流程。
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 构建操作上下文
            ctx = OperationContext(
                operation_name=func.__name__,
                risk_level=risk_level,
                target_resource=kwargs.get("resource", "unknown"),
                estimated_impact=f"执行 {func.__name__} 操作",
                requested_by="agent",
            )

            # L0-L1：自动通过
            if risk_level <= RiskLevel.LOW_WRITE:
                logger.info(f"[AUTO] {func.__name__} (L{risk_level}) 自动通过")
                result = func(*args, **kwargs)
                logger.info(f"[AUDIT] 已执行: {func.__name__}, 结果: {result}")
                return result

            # L2+：需要审批
            elif risk_level <= RiskLevel.HIGH_RISK:
                logger.warning(f"[PENDING] {func.__name__} (L{risk_level}) 等待单人审批")
                # 在实际系统中，这里会挂起并等待审批
                # 演示中使用异常机制通知上层
                raise ApprovalRequired(ctx, approval_id=f"APR-{func.__name__}-{id(ctx)}")

            # L4+：多级审批
            else:
                logger.error(f"[PENDING] {func.__name__} (L{risk_level}) 等待多级审批")
                raise ApprovalRequired(ctx, approval_id=f"APR-MULTI-{func.__name__}-{id(ctx)}")

        # 将元数据附加到函数上，方便框架识别
        wrapper._risk_level = risk_level
        return wrapper
    return decorator


# ============================================================
# 工具定义：使用风险级别装饰器
# ============================================================

@require_approval(RiskLevel.READ_ONLY)
def read_logs(service: str, lines: int = 100) -> str:
    """读取服务日志（L0 - 只读）"""
    return f"[模拟] 已读取 {service} 最近 {lines} 行日志"


@require_approval(RiskLevel.LOW_WRITE)
def save_draft(content: str, resource: str = "draft") -> str:
    """保存草稿（L1 - 低风险写入）"""
    return f"[模拟] 草稿已保存到 {resource}: {content[:50]}..."


@require_approval(RiskLevel.MEDIUM_MUTATE)
def update_config(key: str, value: str, resource: str = "config") -> str:
    """更新配置（L2 - 需单人确认）"""
    return f"[模拟] 配置 {key}={value} 已更新"


@require_approval(RiskLevel.HIGH_RISK)
def delete_record(table: str, record_id: int, resource: str = "database") -> str:
    """删除数据库记录（L3 - 需确认 + 二次确认）"""
    return f"[模拟] 已从 {table} 删除记录 ID={record_id}"


@require_approval(RiskLevel.DANGEROUS)
def deploy_production(version: str, resource: str = "production") -> str:
    """部署到生产环境（L4 - 多级审批）"""
    return f"[模拟] 版本 {version} 已部署到生产环境"


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("权限分级 HITL 演示")
    print("=" * 60)

    # L0 操作 - 自动通过
    print("\n1. L0 只读操作：")
    result = read_logs("api-gateway", lines=50)
    print(f"   结果: {result}")

    # L1 操作 - 自动通过
    print("\n2. L1 低风险写入：")
    result = save_draft("这是一份草稿内容...")
    print(f"   结果: {result}")

    # L2 操作 - 触发审批
    print("\n3. L2 中等风险修改（会触发审批需求）：")
    try:
        update_config("max_connections", "500")
    except ApprovalRequired as e:
        print(f"   [审批请求] 操作: {e.context.operation_name}")
        print(f"   [审批请求] 风险级别: L{e.context.risk_level}")
        print(f"   [审批请求] 审批ID: {e.approval_id}")
        print(f"   [审批请求] 需要单人审批，已通知审批人")

    # L4 操作 - 触发多级审批
    print("\n4. L4 危险操作（会触发多级审批需求）：")
    try:
        deploy_production("v2.3.1")
    except ApprovalRequired as e:
        print(f"   [审批请求] 操作: {e.context.operation_name}")
        print(f"   [审批请求] 风险级别: L{e.context.risk_level}")
        print(f"   [审批请求] 审批ID: {e.approval_id}")
        print(f"   [审批请求] 需要至少 2 人审批")
```

**Image-Prompt(risk level permission hierarchy):** A flat-design minimalist 2D vector illustration of the L0-L5 risk level permission system. A vertical pyramid/gradient from bottom (L0 green "只读 - 自动通过") to top (L5 red "关键操作 - 多人会签"). Each level shown as a horizontal bar with operation icon (eye for L0, pencil for L1-L2, trash for L3, rocket for L4, shield for L5) and approval requirement badge. Tech light blue #409EFF accents. White background with dark blue #1a1a2e labels. Thin-line permission icons. Academic security framework visualization.

---

## 4. 中断与恢复机制

### 4.1 核心挑战

HITL 的核心技术挑战在于：**如何在 LLM 调用链的任意位置插入暂停点，保存完整状态，并在人工决策后无缝恢复执行**。

这涉及三个子问题：
1. **暂停点插入**：在哪里停下？如何让 Agent 安全停下来？
2. **状态保存**：保存哪些信息？保存到什么粒度？
3. **状态恢复**：如何从暂停点原样恢复？恢复后如何注入人工决策结果？

### 4.2 基于 LangGraph 的 HITL 实现

LangGraph 提供了 `interrupt()` 机制，天然支持在图中插入暂停点。下面的代码演示一个完整的 HITL Agent：

```python
"""
基于 LangGraph 的 Human-in-the-Loop 完整实现
演示：审批节点模式 + 中断恢复机制

安装依赖：
    pip install langgraph langchain langchain-openai grandalf
"""
from typing import TypedDict, Literal, Annotated, Optional
from dataclasses import dataclass, field
import operator
import json
import uuid
from datetime import datetime

# LangGraph 核心
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

# LangChain
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# ============================================================
# 1. 定义状态结构
# ============================================================

@dataclass
class PendingApproval:
    """审批挂起信息的结构化存储"""
    approval_id: str
    action_description: str
    risk_level: str
    tool_name: str
    tool_args: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentState(TypedDict):
    """
    Agent 状态定义。
    LangGraph 使用 TypedDict 定义图中节点间流转的数据结构。
    使用 Annotated + operator.add 实现消息的累加（而非替换）。
    """
    messages: Annotated[list, operator.add]
    pending_approval: Optional[PendingApproval]   # 当前挂起的审批（若有）
    approval_history: list[PendingApproval]        # 审批历史记录
    execution_stage: str                           # 当前执行阶段标识
    final_result: Optional[str]                    # 最终执行结果


# ============================================================
# 2. 模拟工具集
# ============================================================

# 模拟数据库
_fake_db = {
    "users": [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ],
    "config": {"max_retries": "3", "timeout": "30s"}
}


def search_users(query: str) -> str:
    """L0 - 只读：搜索用户"""
    results = [u for u in _fake_db["users"] if query.lower() in u["name"].lower()]
    return json.dumps(results, ensure_ascii=False)


def read_config(key: str) -> str:
    """L0 - 只读：读取配置"""
    value = _fake_db["config"].get(key, "未找到")
    return f"配置 {key} = {value}"


def update_user_email(user_id: int, new_email: str) -> str:
    """L2 - 修改操作：更新用户邮箱（需要审批）"""
    for u in _fake_db["users"]:
        if u["id"] == user_id:
            old_email = u["email"]
            u["email"] = new_email
            return f"用户 {u['name']} 邮箱已从 {old_email} 更新为 {new_email}"
    return f"未找到用户 ID={user_id}"


def delete_user(user_id: int) -> str:
    """L3 - 高风险操作：删除用户（需要审批 + 二次确认）"""
    for i, u in enumerate(_fake_db["users"]):
        if u["id"] == user_id:
            deleted = _fake_db["users"].pop(i)
            return f"用户 {deleted['name']} (ID={user_id}) 已被永久删除"
    return f"未找到用户 ID={user_id}"


# ============================================================
# 3. 工具风险级别映射表
# ============================================================

TOOL_RISK_MAP = {
    "search_users":       {"level": "L0", "require_approval": False},
    "read_config":        {"level": "L0", "require_approval": False},
    "update_user_email":  {"level": "L2", "require_approval": True},
    "delete_user":        {"level": "L3", "require_approval": True},
}

TOOLS_BY_NAME = {
    "search_users":       search_users,
    "read_config":        read_config,
    "update_user_email":  update_user_email,
    "delete_user":        delete_user,
}


# ============================================================
# 4. 图节点定义
# ============================================================

# 初始化 LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# System Prompt
SYSTEM_PROMPT = """你是一个需要人类审批才能执行修改操作的 AI 助手。

规则：
1. 只读操作（search_users, read_config）可以直接执行，无需审批。
2. 修改操作（update_user_email）需要向人类请求审批。
3. 删除操作（delete_user）是高风险操作，必须请求审批并说明风险。

当你需要执行修改/删除操作时，请先向用户说明你想做什么，
不要直接调用工具。等待用户批准后再执行。

始终使用中文回复用户。"""


def agent_node(state: AgentState) -> AgentState:
    """
    Agent 推理节点：决定下一步做什么。
    这是整个图的"大脑"。
    """
    messages = state["messages"]

    # 如果有待处理的审批，说明刚从中断恢复 —— 此时 LLM
    # 应该根据审批结果（批准/拒绝）决定后续动作
    if state.get("pending_approval"):
        approval = state["pending_approval"]
        # 检查最近的用户消息是否包含审批决定
        last_human = None
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                last_human = m.content
                break

        if last_human and ("批准" in last_human or "approve" in last_human.lower()):
            # 审批通过，告知 LLM 可以执行
            messages.append(
                SystemMessage(content=f"审批已通过！你现在可以执行 {approval.tool_name} 操作了。")
            )

    # 调用 LLM
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm.invoke(full_messages)

    return {
        "messages": [response],
        "execution_stage": "agent_reasoning",
    }


def tool_execution_node(state: AgentState) -> AgentState:
    """
    工具执行节点：根据审批状态决定是否执行工具。

    流程：
    1. 检查待执行的操作风险级别
    2. L0 操作：直接执行
    3. L2+ 操作：触发 interrupt()，挂起等待人工审批
    4. 审批通过后恢复执行
    """
    # 从最后一条 AI 消息中解析工具调用意图
    # 简化实现：通过关键词匹配检测工具调用意图
    last_ai = None
    for m in reversed(state["messages"]):
        if isinstance(m, AIMessage):
            last_ai = m.content
            break

    if not last_ai:
        return {"execution_stage": "no_action"}

    # 检测需要执行的操作
    pending_approval = state.get("pending_approval")

    # 场景1：刚从中断恢复，审批已通过 —— 执行挂起的操作
    if pending_approval:
        approval = pending_approval
        tool_name = approval.tool_name
        tool_args = approval.tool_args

        if tool_name in TOOLS_BY_NAME:
            tool_func = TOOLS_BY_NAME[tool_name]
            result = tool_func(**tool_args)
            return {
                "messages": [AIMessage(content=f"[工具执行结果] {result}")],
                "pending_approval": None,  # 清除待审批状态
                "approval_history": [approval],  # 记录到历史
                "execution_stage": "tool_executed",
            }

    # 场景2：检测是否有需要审批的操作意图
    for tool_name, risk_info in TOOL_RISK_MAP.items():
        if tool_name in last_ai and risk_info["require_approval"]:
            # 解析工具参数（简化实现）
            tool_args = _parse_tool_args(last_ai, tool_name)

            # --- 核心：interrupt() 挂起 ---
            # 这是 LangGraph HITL 的关键 API。
            # 调用 interrupt() 后，图执行暂停，状态被序列化保存到 Checkpointer。
            # 外部通过 update_state + Command 恢复执行时，
            # interrupt() 的返回值就是外部传入的值。
            approval_decision = interrupt(
                PendingApproval(
                    approval_id=f"APR-{uuid.uuid4().hex[:8]}",
                    action_description=f"执行 {tool_name} 操作: {tool_args}",
                    risk_level=risk_info["level"],
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
            )

            # --- 恢复后：根据审批决定继续 ---
            # approval_decision 是外部通过 Command(resume=...) 传入的值
            if isinstance(approval_decision, dict) and approval_decision.get("approved"):
                tool_func = TOOLS_BY_NAME[tool_name]
                result = tool_func(**tool_args)
                return {
                    "messages": [AIMessage(content=f"[已批准执行] {result}")],
                    "approval_history": [pending_approval],
                    "pending_approval": None,
                    "execution_stage": "tool_executed_after_approval",
                }
            else:
                return {
                    "messages": [
                        AIMessage(content=f"[审批被拒绝] {tool_name} 操作未执行，用户拒绝")
                    ],
                    "pending_approval": None,
                    "execution_stage": "tool_rejected",
                }

    # 场景3：无特殊操作，正常返回
    return {"execution_stage": "idle"}


def _parse_tool_args(content: str, tool_name: str) -> dict:
    """简易参数解析（实际项目应使用 tool_calls 结构化解析）"""
    if tool_name == "update_user_email":
        return {"user_id": 1, "new_email": "new_email@example.com"}
    elif tool_name == "delete_user":
        return {"user_id": 2}
    return {}


# ============================================================
# 5. 路由函数：决定图中的分支走向
# ============================================================

def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """根据状态决定是去执行工具还是结束"""
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message and isinstance(last_message, AIMessage):
        content = last_message.content
        # 如果 AI 消息中包含工具调用意图，走向工具节点
        if any(tool_name in content for tool_name in TOOLS_BY_NAME):
            return "tools"
    return "end"


# ============================================================
# 6. 构建图
# ============================================================

def build_hitl_graph():
    """
    构建带有 HITL 中断机制的 LangGraph 图。

    图结构：
        START --> agent_node --> [should_continue]
                                   |-- "tools" --> tool_execution_node --> agent_node
                                   |-- "end"   --> END

    其中 tool_execution_node 在需要审批时调用 interrupt()，
    这会暂停整个图的执行，等待外部人工审批。
    """
    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_execution_node)

    # 注册边
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    workflow.add_edge("tools", "agent")

    # 使用 MemorySaver 作为 Checkpointer
    # Checkpointer 负责在 interrupt() 时保存状态快照
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# ============================================================
# 7. 完整的 HITL 交互演示
# ============================================================

def run_hitl_demo():
    """
    完整演示 HITL 的流程：
    1. 用户发起请求
    2. Agent 推理后决定执行需要审批的操作
    3. 系统调用 interrupt() 挂起
    4. 人工审批
    5. 系统恢复执行
    """
    graph = build_hitl_graph()

    # 生成唯一的 thread_id，用于定位同一个会话的状态
    config = {"configurable": {"thread_id": "demo-session-001"}}

    print("=" * 70)
    print("  LangGraph Human-in-the-Loop 完整交互演示")
    print("=" * 70)

    # ======== 步骤 1：用户发起请求 ========
    user_input = "请帮我把用户 ID=1 的邮箱更新为 alice_new@company.com"
    print(f"\n{'='*50}")
    print(f"[用户] {user_input}")
    print(f"{'='*50}")

    # 第一次执行：运行到 interrupt() 处会暂停
    print("\n[系统] Agent 开始推理...")
    try:
        # stream 会逐个节点输出，直到遇到 interrupt()
        events = list(graph.stream(
            {"messages": [HumanMessage(content=user_input)],
             "execution_stage": "start"},
            config,
            stream_mode="values",
        ))
        for event in events:
            if "messages" in event:
                last_msg = event["messages"][-1]
                role = "AI" if isinstance(last_msg, AIMessage) else "System"
                print(f"  [{role}] {last_msg.content[:200]}")
    except Exception as e:
        print(f"  [注意] 图执行遇到了中断点: {type(e).__name__}")

    # ======== 步骤 2：检查是否有挂起的审批 ========
    print("\n" + "-" * 50)
    print("[系统] 检查挂起状态...")

    current_state = graph.get_state(config)
    print(f"  当前执行阶段: {current_state.values.get('execution_stage', 'unknown')}")
    print(f"  是否有中断: {current_state.next}")

    # 在实际 UI 中，这里应该展示审批信息给用户
    # 从状态中取出 pending_approval 展示
    if current_state.values.get("pending_approval"):
        pa = current_state.values["pending_approval"]
        print(f"\n  ====== 审批请求 ======")
        print(f"  审批 ID: {pa.approval_id}")
        print(f"  操作描述: {pa.action_description}")
        print(f"  风险级别: {pa.risk_level}")
        print(f"  操作时间: {pa.timestamp}")
        print(f"  =======================")

    # ======== 步骤 3：人工审批并恢复执行 ========
    print("\n" + "-" * 50)
    print("[审批] 人工审批中...")
    import time
    time.sleep(0.5)  # 模拟审批耗时

    # 构建审批结果
    approval_result = {
        "approved": True,
        "approver": "admin_zhang",
        "comment": "邮箱更新合理，批准执行",
        "timestamp": datetime.now().isoformat(),
    }

    print(f"[审批] 审批人: {approval_result['approver']}")
    print(f"[审批] 决定: {'批准' if approval_result['approved'] else '拒绝'}")
    print(f"[审批] 备注: {approval_result['comment']}")

    # ======== 步骤 4：恢复图执行 ========
    print("\n" + "-" * 50)
    print("[系统] 恢复图执行...")

    # 关键 API：使用 Command(resume=...) 恢复中断的执行
    # resume 中的值会作为 interrupt() 的返回值
    resume_events = list(graph.stream(
        Command(resume=approval_result),
        config,
        stream_mode="values",
    ))

    for event in resume_events:
        if "messages" in event:
            last_msg = event["messages"][-1]
            if isinstance(last_msg, AIMessage):
                print(f"  [AI] {last_msg.content}")

    # ======== 步骤 5：查看最终结果 ========
    print("\n" + "=" * 50)
    print("[结果] 数据库当前状态:")
    print(f"  Users: {json.dumps(_fake_db['users'], ensure_ascii=False, indent=2)}")
    print("=" * 50)


if __name__ == "__main__":
    run_hitl_demo()
```

**Image-Prompt(interrupt and resume state machine):** A flat-design minimalist 2D vector illustration of the LangGraph interrupt/resume mechanism. A state machine diagram showing: Normal Execution → interrupt() call (pause icon) → State saved to Checkpointer (database cylinder) → Human approval received → Command(resume=...) → Execution continues. Each state as a rounded rectangle connected by tech light blue #409EFF arrows. A MemorySaver icon shown as a disk with state snapshot. White background with dark blue #1a1a2e labels. Thin-line pause/play icons. Academic workflow visualization.

---

## 5. 交互流程图

### 5.1 审批节点模式的完整时序

```
用户            Agent (LangGraph)         工具执行器         审批系统          人类审批者
 |                    |                      |                 |                 |
 |--[发送请求]------->|                      |                 |                 |
 |                    |--[LLM推理]----------->|                 |                 |
 |                    |                      |--[风险检查]---->|                 |
 |                    |                      |                 |                 |
 |                    |                      |  [L2: 需要审批] |                 |
 |                    |                      |                 |--[推送审批]---->|
 |                    |                      |                 |                 |
 |                    |  interrupt() 挂起    |                 |                 |
 |                    |<-------X-------------|                 |                 |
 |                    |                      |                 |                 |
 |                    |  状态已保存到 Checkpointer              |                 |
 |                    |                      |                 |                 |
 |                    |                      |                 |   [审阅操作]    |
 |                    |                      |                 |<--[批准/拒绝]---|
 |                    |                      |                 |                 |
 |<--[通知结果]--------|                      |                 |                 |
 |                    |                      |                 |                 |
 |  Command(resume=...) 恢复执行              |                 |                 |
 |-------------------->|                      |                 |                 |
 |                    |--[继续执行]---------->|                 |                 |
 |                    |                      |--[执行工具]----->|                 |
 |                    |<--[执行结果]----------|                 |                 |
 |                    |                      |                 |                 |
 |<--[最终回复]--------|                      |                 |                 |
```

### 5.2 异常上报模式流程

```
[Agent 推理] --> {置信度评估}
                    |
        +-----------+-----------+
        |                       |
   [高置信度]             [低置信度 / 未知]
        |                       |
   [自动执行]             [构建上报数据包]
        |                       |
   [记录日志]              [通知 + 挂起]
        |                       |
   [继续下一轮]           [等待人工决策]
                                |
                    +-----------+-----------+
                    |                       |
               [人工介入]              [人工忽略]
                    |                       |
              [注入决策]              [降级处理/
              [恢复执行]               标记为待处理]


流程说明：
  - 置信度评估可以基于：模型输出格式规范性、
    检索结果相关性分数、工具执行成功率等指标
  - 上报数据包含：上下文摘要、置信度分数、
    不确定点标注、Agent 的建议方案（供人参考）
  - 降级策略：标记任务为"需人工处理"并跳过
```

**Image-Prompt(HITL approval sequence diagram):** A flat-design minimalist 2D vector illustration of the HITL approval node sequence flow. Five vertical swim lanes labeled: User, Agent (LangGraph), Tool Executor, Approval System, Human Approver. Timeline arrows showing: User sends request → Agent reasons → Tool detects L2 risk → interrupt() pauses → Approval pushed to human → Human approves → Command(resume) → execution continues → result returned. Tech light blue #409EFF for active flow lines. White background with dark blue #1a1a2e labels. Academic sequence diagram style.

---

## 6. 用户体验设计原则

### 6.1 四个核心原则

| 原则 | 说明 | 反模式 | 正例 |
|------|------|--------|------|
| **不打扰用户** | 审批请求应该有节制，合并同类请求 | 每个 UPDATE 都弹窗确认（通知轰炸） | 批量变更合并为一次审批 |
| **智能聚合通知** | 将相关的审批请求分组，提供统一的决策界面 | 10 条零散的审批逐一推送 | 一个"下午 3 点批次操作汇总"卡片 |
| **上下文保留** | 每次审批请求附带完整的上下文信息 | "是否执行 update_user_email？" 无任何上下文 | 附带用户详情、变更前后对比、影响范围 |
| **可逆性优先** | 优先支持可撤销的操作，降低审批成本 | 直接执行 DROP TABLE 后无法回滚 | 改为 RENAME（软删除），24 小时后真正清理 |

### 6.2 通知策略分级

```python
"""
HITL 通知策略 —— 避免"狼来了"效应

设计思路：
  不同风险级别的审批使用不同的通知渠道和紧急程度，
  让用户形成条件反射：手机震动 = 真正需要关注的事。
"""

NOTIFICATION_POLICY = {
    "L2": {
        "channel": "in_app_badge",        # 应用内红点
        "urgency": "low",
        "auto_expire": "24h",             # 24 小时自动过期
        "batch_window": "1h",             # 1 小时内同类请求合并
        "description": "静默收集，批量呈现"
    },
    "L3": {
        "channel": "desktop_notification", # 桌面通知
        "urgency": "medium",
        "auto_expire": "4h",
        "batch_window": "15min",
        "description": "适度提醒，允许延迟处理"
    },
    "L4": {
        "channel": "push_notification",   # 手机推送
        "urgency": "high",
        "auto_expire": "30min",
        "batch_window": "none",           # 不合并，逐条处理
        "require_ack": True,              # 需要确认收到
        "description": "即时推送，要求确认"
    },
    "L5": {
        "channel": "multi_channel",       # 短信 + 推送 + 电话
        "urgency": "critical",
        "auto_expire": "never",
        "batch_window": "none",
        "require_multi_approval": True,
        "description": "多渠道轰炸，必须多人会签"
    },
}
```

### 6.3 上下文保留的实现

```python
"""
构建审批上下文 —— 让审批者一目了然
"""

def build_approval_context(operation: dict, history: list) -> str:
    """
    为审批者生成结构化的决策上下文。

    一个好的审批界面应该让审批者在 5 秒内理解：
    1. 要做什么？（操作描述）
    2. 为什么要做？（上下文来源）
    3. 有什么影响？（变更前后对比）
    4. 有没有先例？（历史类似操作）
    """
    lines = []

    # 1. 操作摘要
    lines.append("## 操作摘要")
    lines.append(f"- **操作类型**: {operation.get('type', '未知')}")
    lines.append(f"- **目标资源**: {operation.get('target', '未知')}")
    lines.append(f"- **风险级别**: {operation.get('risk_level', '未知')}")
    lines.append(f"- **发起时间**: {operation.get('timestamp', '未知')}")

    # 2. 变更详情（Diff）
    lines.append("\n## 变更详情")
    lines.append("```diff")
    lines.append(f"- {operation.get('old_value', 'N/A')}")
    lines.append(f"+ {operation.get('new_value', 'N/A')}")
    lines.append("```")

    # 3. 上下文来源（用户原始请求 + Agent 推理链路）
    lines.append("\n## 决策链路")
    for i, step in enumerate(operation.get("reasoning_chain", []), 1):
        lines.append(f"{i}. {step}")

    # 4. 影响范围
    lines.append("\n## 影响范围")
    lines.append(f"- 直接影响: {operation.get('direct_impact', 0)} 条记录")
    lines.append(f"- 关联影响: {operation.get('cascade_impact', '无')}")

    # 5. 历史类似操作
    similar = [h for h in history
               if h.get("type") == operation.get("type")]
    if similar:
        lines.append("\n## 历史类似操作")
        for h in similar[-3:]:  # 最近 3 条
            lines.append(f"- {h['timestamp']}: {h['summary']} "
                         f"({h['approver']} / {'批准' if h['approved'] else '拒绝'})")

    return "\n".join(lines)


# 演示
if __name__ == "__main__":
    op = {
        "type": "update_user_email",
        "target": "users[1].email",
        "risk_level": "L2",
        "timestamp": "2026-07-09T14:30:00",
        "old_value": "alice@example.com",
        "new_value": "alice_new@company.com",
        "reasoning_chain": [
            "用户请求变更 Alice 的邮箱地址",
            "Agent 验证了新邮箱格式合法",
            "Agent 确认 Alice 是活跃用户（最近 7 天有登录）",
            "Agent 判断这是低风险的资料更新",
        ],
        "direct_impact": 1,
        "cascade_impact": "需同步更新 SSO 系统中的邮箱（关联系统）",
    }
    history = [
        {"type": "update_user_email", "timestamp": "2026-07-08", "summary": "Bob 邮箱更新",
         "approver": "admin_wang", "approved": True},
        {"type": "update_user_email", "timestamp": "2026-07-07", "summary": "Charlie 邮箱更新",
         "approver": "admin_wang", "approved": True},
    ]
    print(build_approval_context(op, history))
```

**Image-Prompt(HITL UX design principles):** A flat-design minimalist 2D vector illustration of four UX design principles for HITL systems. Four rounded cards arranged in a 2x2 grid: "不打扰用户" (notification with do-not-disturb icon), "智能聚合通知" (grouped notification cards merging into one), "上下文保留" (approval dialog showing before/after diff comparison), "可逆性优先" (undo arrow with soft-delete concept). Tech light blue #409EFF card accents. White background with dark blue #1a1a2e labels. Thin-line UX icons. Academic design principles layout.

---

## 7. 实践建议

### 7.1 HITL 设计的 DO 和 DON'T

**DO（应该做的）**：
1. **从 L0 自动开始**，逐步增加自动化程度。先让只读操作全自动，积累信任后再扩大到 L1。
2. **提供"一键批准"**。对 L2 操作，提供一个批量批准按钮，而非逐个点击。
3. **记录所有审批决策**。审批日志本身就是宝贵的安全审计数据。
4. **设计降级路径**。如果审批人不在线，操作应该怎么处理？（排队等待 / 超时自动拒绝 / 临时提升审批人）
5. **在审批 UI 中展示"AI 建议"**。让 Agent 说明它为什么推荐批准/拒绝，帮审批人更快决策。

**DON'T（不应该做的）**：
1. **不要用 HITL 替代安全性设计**。HITL 是安全网，不是安全带。如果操作本身就危险，先改进操作的安全性。
2. **不要让人类做"橡皮图章"**。如果人类总是无脑批准，HITL 就是无效的——要么自动化程度不够，要么审批信息不足。
3. **不要在用户注意力高峰期轰炸**。考虑用户的注意力预算，把非紧急审批合并到固定时段。
4. **不要丢失上下文**。审批断点恢复后，确保 Agent 仍然知道"我是谁、我在哪、我要做什么"。

### 7.2 渐进式自动化路线图

```
阶段1: 全人工
   用户直接操作
        |
        v
阶段2: 影子模式
   AI 生成建议但不出手，所有操作人工
        |
        v
阶段3: L0 自动化
   只读操作全自动，修改操作仍需确认
        |
        v
阶段4: 条件自动化
   L1-L2 在有条件（白名单资源、工作时间）下自动
        |
        v
阶段5: 智能自动化
   AI 自主决策 L0-L2，L3+ 触发 HITL
   （到达目标状态）
```

### 7.3 技术选型参考

| 需求场景 | 推荐方案 | 关键能力 |
|---------|---------|---------|
| 简单审批流程 | LangGraph `interrupt()` + MemorySaver | 内置中断/恢复，状态持久化 |
| 多级审批工作流 | Temporal + LangGraph | 长时间运行的工作流引擎 |
| 低延迟交互式审批 | WebSocket + Redis Pub/Sub | 实时双向通信 |
| 离线审批 | 消息队列 + 外部任务系统 | 异步解耦，支持离线处理 |
| 企业级审批 | Camunda / Flowable + 自定义 TaskListener | BPMN 标准，完善的审批 UI |

**Image-Prompt(HITL progressive automation roadmap):** A flat-design minimalist 2D vector illustration of the five-stage progressive automation roadmap. Five ascending steps from left to right: Stage 1 "全人工" (full human silhouette), Stage 2 "影子模式" (human with AI shadow), Stage 3 "L0自动化" (AI handles read-only, human for writes), Stage 4 "条件自动化" (AI handles L1-L2 conditionally), Stage 5 "智能自动化" (AI autonomous L0-L2, HITL for L3+). Each step in gradient tech light blue #409EFF increasing intensity. White background with dark blue #1a1a2e labels. Academic progression visualization.

---

## 8. 小结

Human-in-the-Loop 不是 AI 能力不足的妥协，而是**智能系统设计的分内之事**。一个设计良好的 HITL 系统应该：

- **在正确的时间点**（审批节点模式、异常上报模式、定期汇报模式）引入人类判断
- **以正确的粒度**（L0-L5 的权限分级）决定人的参与程度
- **用正确的方式**（上下文保留、智能聚合、不打扰原则）呈现给人类
- **确保正确的恢复**（状态快照、中断点恢复、审批结果注入）

核心代码实现中，LangGraph 的 `interrupt()` + `Command(resume=...)` + `MemorySaver` 组合提供了开箱即用的 HITL 基础设施，配合合理的权限分级和 UX 设计，可以构建出既高效又安全的智能体系统。

**Image-Prompt(HITL summary key concepts):** A flat-design minimalist 2D vector illustration summarizing Human-in-the-Loop key concepts. Central hub labeled "HITL" with four radiating connected nodes: "正确的时间点" (clock icon with three pattern types), "正确的粒度" (L0-L5 pyramid icon), "正确的方式" (context card with UX principles), "正确的恢复" (state snapshot restore icon). Tech light blue #409EFF for hub and connections. White background with dark blue #1a1a2e labels. Thin-line concept icons. Academic summary mind-map style with centered radial layout.
