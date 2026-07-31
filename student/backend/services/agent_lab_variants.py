"""旗舰编程实验的变式迁移规格。

这里的任务刻意改变业务场景、输入输出契约和边界条件，但仍复用原实验
训练的核心能力。测试用例只在服务端执行，前端仅展示场景说明。
"""

ADDITIONAL_VARIANT_SPECS = {
    "2-3": {
        "target": "authorize_campus_tool_call",
        "scenario": (
            "### 变式迁移：校园设备操作权限网关\n\n"
            "原项目执行客服工具调用。新场景中，Agent 要操作校园设备，误调用的风险更高。"
            "请实现 `authorize_campus_tool_call(call, allowed_tools, high_risk_tools)`。\n\n"
            "`call` 格式为 `{\"name\": 工具名, \"args\": 参数字典, \"confirmed\": 布尔值}`，"
            "返回统一决策：\n\n"
            "```python\n"
            '{"tool": "工具名", "args": {...}, "decision": "allow|confirm|deny"}\n'
            "```\n\n"
            "- 不在 `allowed_tools` 中：`deny`\n"
            "- 属于高风险工具且未确认：`confirm`\n"
            "- 其他允许工具：`allow`\n"
            "- 工具名为空、args 不是字典、confirmed 不是布尔值时抛出 `ValueError`\n"
            "- 不得修改输入对象\n\n"
            "**迁移重点**：从“能调用工具”升级为“在真实权限边界内安全调用工具”。"
        ),
        "cases": [
            {
                "description": "允许读取设备状态",
                "args": [
                    {"name": "read_sensor", "args": {"room": "A101"}, "confirmed": False},
                    ["read_sensor", "unlock_door"],
                    ["unlock_door"],
                ],
                "expected": {
                    "tool": "read_sensor",
                    "args": {"room": "A101"},
                    "decision": "allow",
                },
                "immutable": True,
            },
            {
                "description": "高风险开门操作需要确认",
                "args": [
                    {"name": "unlock_door", "args": {"door": "D-7"}, "confirmed": False},
                    ["read_sensor", "unlock_door"],
                    ["unlock_door"],
                ],
                "expected": {
                    "tool": "unlock_door",
                    "args": {"door": "D-7"},
                    "decision": "confirm",
                },
            },
            {
                "description": "确认后允许高风险操作",
                "args": [
                    {"name": "unlock_door", "args": {"door": "D-7"}, "confirmed": True},
                    ["unlock_door"],
                    ["unlock_door"],
                ],
                "expected": {
                    "tool": "unlock_door",
                    "args": {"door": "D-7"},
                    "decision": "allow",
                },
            },
            {
                "description": "拒绝未授权工具",
                "args": [
                    {"name": "shutdown_grid", "args": {}, "confirmed": True},
                    ["read_sensor"],
                    ["shutdown_grid"],
                ],
                "expected": {"tool": "shutdown_grid", "args": {}, "decision": "deny"},
            },
        ],
    },
    "2-4": {
        "target": "run_incident_response_plan",
        "scenario": (
            "### 变式迁移：生产故障处置计划\n\n"
            "原项目按计划执行多个工具。现在请把这一能力迁移到生产故障处置："
            "每一步都可能成功或失败，失败后必须停止，不能继续执行有副作用的后续步骤。\n\n"
            "实现 `run_incident_response_plan(plan, tool_results)`：\n\n"
            "- `plan` 是步骤名列表；`tool_results` 将步骤名映射到布尔执行结果\n"
            "- 按顺序执行并把已尝试步骤写入 `executed`\n"
            "- 首次失败立即停止，返回 `status='failed'` 和 `failed_step`\n"
            "- 全部成功返回 `status='completed'`，`failed_step=None`\n"
            "- 计划为空或缺少某一步结果时抛出 `ValueError`\n"
            "- 不得修改输入列表和字典\n\n"
            "返回：`{\"executed\": [...], \"status\": ..., \"failed_step\": ...}`。"
        ),
        "cases": [
            {
                "description": "完整执行故障恢复步骤",
                "args": [
                    ["isolate", "restart", "health_check"],
                    {"isolate": True, "restart": True, "health_check": True},
                ],
                "expected": {
                    "executed": ["isolate", "restart", "health_check"],
                    "status": "completed",
                    "failed_step": None,
                },
                "immutable": True,
            },
            {
                "description": "失败后停止危险操作",
                "args": [
                    ["isolate", "restart", "release_traffic"],
                    {"isolate": True, "restart": False, "release_traffic": True},
                ],
                "expected": {
                    "executed": ["isolate", "restart"],
                    "status": "failed",
                    "failed_step": "restart",
                },
            },
            {
                "description": "缺失执行结果时拒绝运行",
                "args": [["isolate", "restart"], {"isolate": True}],
                "exception": "ValueError",
            },
        ],
    },
    "3-1": {
        "target": "merge_telemetry_state",
        "scenario": (
            "### 变式迁移：物联网遥测状态合并\n\n"
            "原项目合并 LangGraph 节点状态。新场景是实验楼的传感器网关："
            "温度等字段覆盖，告警列表追加，计数器累加。\n\n"
            "实现 `merge_telemetry_state(current, update, policies)`：\n\n"
            "- 默认策略为 `replace`\n"
            "- `append`：新旧值都必须是列表并拼接\n"
            "- `sum`：新旧值都必须是非布尔数字并相加\n"
            "- 未出现过的字段直接使用更新值\n"
            "- 未知策略或类型不匹配时抛出 `ValueError`\n"
            "- 返回新字典，不得修改输入\n\n"
            "**迁移重点**：同样是状态增量，但合并规则由图节点语义变为设备遥测语义。"
        ),
        "cases": [
            {
                "description": "追加告警并覆盖温度",
                "args": [
                    {"alerts": ["door"], "temperature": 25},
                    {"alerts": ["smoke"], "temperature": 28},
                    {"alerts": "append"},
                ],
                "expected": {"alerts": ["door", "smoke"], "temperature": 28},
                "immutable": True,
            },
            {
                "description": "累加事件计数",
                "args": [{"events": 3}, {"events": 2, "online": True}, {"events": "sum"}],
                "expected": {"events": 5, "online": True},
            },
            {
                "description": "追加策略拒绝非列表",
                "args": [{"alerts": []}, {"alerts": "smoke"}, {"alerts": "append"}],
                "exception": "ValueError",
            },
        ],
    },
    "3-2": {
        "target": "route_facility_incident",
        "scenario": (
            "### 变式迁移：校园设施事件分流\n\n"
            "原项目根据意图、置信度和紧急程度路由客服请求。现在请处理校园设施事件，"
            "路由规则发生变化。\n\n"
            "实现 `route_facility_incident(incident)`，返回路由字符串：\n\n"
            "- `life_safety=True` 或严重度 `critical`：`emergency`\n"
            "- 置信度小于 `0.70`：`manual_review`\n"
            "- `network` → `network_team`\n"
            "- `power` / `water` → `facility_team`\n"
            "- `access` → `security_team`\n"
            "- 置信度必须是 0~1 的非布尔数字，未知类别抛出 `ValueError`\n\n"
            "**迁移重点**：保留条件路由思想，但优先级、阈值和目标节点都已改变。"
        ),
        "cases": [
            {
                "description": "生命安全事件最高优先级",
                "args": [{"category": "water", "confidence": 0.99, "severity": "medium", "life_safety": True}],
                "expected": "emergency",
            },
            {
                "description": "低置信度进入人工复核",
                "args": [{"category": "network", "confidence": 0.69, "severity": "low", "life_safety": False}],
                "expected": "manual_review",
            },
            {
                "description": "网络故障路由到网络组",
                "args": [{"category": "network", "confidence": 0.7, "severity": "high", "life_safety": False}],
                "expected": "network_team",
            },
            {
                "description": "严重事件覆盖普通分类",
                "args": [{"category": "access", "confidence": 0.9, "severity": "critical", "life_safety": False}],
                "expected": "emergency",
            },
            {
                "description": "拒绝布尔置信度",
                "args": [{"category": "power", "confidence": True, "severity": "low", "life_safety": False}],
                "exception": "ValueError",
            },
        ],
    },
    "3-3": {
        "target": "create_delivery_checkpoint",
        "scenario": (
            "### 变式迁移：无人配送流程检查点\n\n"
            "原项目保存客服线程检查点。新场景是校园无人配送车：断电恢复后必须知道"
            "任务版本、最后位置和下一动作，且不得把密钥等临时字段写入检查点。\n\n"
            "实现 `create_delivery_checkpoint(task_id, state, version)`：\n\n"
            "- `task_id` 必须是非空字符串，`version` 必须是大于 0 的非布尔整数\n"
            "- `state` 必须含 `location` 与 `next_action`\n"
            "- 只保存 `location`、`next_action`、可选的 `cargo`，忽略其他字段\n"
            "- 返回 `task_id`、`version`、过滤后的 `state` 和"
            " `resume_token`（格式为 `任务ID:版本号`）\n"
            "- 不得修改输入状态\n\n"
            "返回结果需要可序列化，以便在另一台设备上恢复。"
        ),
        "cases": [
            {
                "description": "创建可恢复配送检查点",
                "args": [
                    "DEL-7",
                    {"location": "A楼", "next_action": "前往B楼", "cargo": "图书", "api_key": "secret"},
                    2,
                ],
                "expected": {
                    "task_id": "DEL-7",
                    "version": 2,
                    "state": {"location": "A楼", "next_action": "前往B楼", "cargo": "图书"},
                    "resume_token": "DEL-7:2",
                },
                "immutable": True,
            },
            {
                "description": "可选货物字段缺失",
                "args": ["DEL-8", {"location": "仓库", "next_action": "充电", "debug": True}, 1],
                "expected": {
                    "task_id": "DEL-8",
                    "version": 1,
                    "state": {"location": "仓库", "next_action": "充电"},
                    "resume_token": "DEL-8:1",
                },
            },
            {
                "description": "缺少恢复所需状态时拒绝保存",
                "args": ["DEL-9", {"location": "A楼"}, 1],
                "exception": "ValueError",
            },
        ],
    },
    "4-1": {
        "target": "retrieve_library_resources",
        "scenario": (
            "### 变式迁移：跨院系图书馆资源检索\n\n"
            "原项目按关键词检索客服知识。现在需要检索图书馆学习资源，并加入院系偏好。"
            "实现 `retrieve_library_resources(query_terms, resources, top_k, min_score, department)`。\n\n"
            "- 每个命中的查询词计 1 分（重复查询词只计一次）\n"
            "- 资源 `department` 与用户院系相同，额外加 1 分\n"
            "- 过滤低于 `min_score` 的资源\n"
            "- 按分数降序、资源 id 升序稳定排序，最多返回 `top_k` 条\n"
            "- 返回项仅含 `id`、`title`、`score`\n"
            "- `top_k <= 0` 或 `min_score < 0` 时抛出 `ValueError`\n"
            "- 不得修改输入资源\n\n"
            "**迁移重点**：检索主干不变，但排序信号从纯文本相关度扩展为场景偏好。"
        ),
        "cases": [
            {
                "description": "相关度与院系偏好联合排序",
                "args": [
                    ["agent", "python", "agent"],
                    [
                        {"id": "B", "title": "Python实践", "terms": ["python"], "department": "计算机"},
                        {"id": "A", "title": "Agent导论", "terms": ["agent"], "department": "自动化"},
                        {"id": "C", "title": "Agent工程", "terms": ["agent", "python"], "department": "计算机"},
                    ],
                    2,
                    1,
                    "计算机",
                ],
                "expected": [
                    {"id": "C", "title": "Agent工程", "score": 3},
                    {"id": "B", "title": "Python实践", "score": 2},
                ],
                "immutable": True,
            },
            {
                "description": "过滤无关资源",
                "args": [
                    ["robot"],
                    [{"id": "A", "title": "文学", "terms": ["novel"], "department": "中文"}],
                    3,
                    1,
                    "计算机",
                ],
                "expected": [],
            },
            {
                "description": "拒绝非法返回数量",
                "args": [[], [], 0, 0, "计算机"],
                "exception": "ValueError",
            },
        ],
    },
    "4-2": {
        "target": "build_auditable_policy_answer",
        "scenario": (
            "### 变式迁移：可审计的校园政策回答\n\n"
            "原项目生成带引用的客服回答。现在校务 Agent 回答奖学金政策，"
            "每条结论都必须可追溯，并明确资料是否过期。\n\n"
            "实现 `build_auditable_policy_answer(question, evidence, current_year)`：\n\n"
            "- 无证据：返回无法确认并转人工，`citations=[]`\n"
            "- 只采用 `year >= current_year - 1` 的证据，最多三条\n"
            "- 有有效证据：按输入顺序用中文分号连接正文，并返回对应 id\n"
            "- 全部证据过期：明确提示资料已过期并转人工\n"
            "- 空问题、非法年份或证据缺少 id/text/year 时抛出 `ValueError`\n\n"
            "返回键固定为 `answer`、`citations`、`needs_human`、`stale_sources`。"
        ),
        "cases": [
            {
                "description": "使用近两年政策证据",
                "args": [
                    "奖学金何时申请",
                    [
                        {"id": "P1", "text": "每年九月开放申请", "year": 2026},
                        {"id": "P2", "text": "需提交成绩单", "year": 2025},
                        {"id": "OLD", "text": "旧流程", "year": 2023},
                    ],
                    2026,
                ],
                "expected": {
                    "answer": "根据现行政策：每年九月开放申请；需提交成绩单",
                    "citations": ["P1", "P2"],
                    "needs_human": False,
                    "stale_sources": 1,
                },
            },
            {
                "description": "全部资料过期时转人工",
                "args": [
                    "住宿补贴",
                    [{"id": "P1", "text": "旧补贴标准", "year": 2022}],
                    2026,
                ],
                "expected": {
                    "answer": "现有资料已过期，无法可靠回答，已为你转接人工老师。",
                    "citations": [],
                    "needs_human": True,
                    "stale_sources": 1,
                },
            },
            {
                "description": "无证据时安全降级",
                "args": ["如何申请", [], 2026],
                "expected": {
                    "answer": "暂未找到可靠政策依据，已为你转接人工老师。",
                    "citations": [],
                    "needs_human": True,
                    "stale_sources": 0,
                },
            },
        ],
    },
    "4-3": {
        "target": "handle_campus_it_ticket",
        "scenario": (
            "### 变式迁移：端到端校园 IT 服务台\n\n"
            "原项目编排客服 Agent。现在把同一套检索、路由、降级和轨迹能力迁移到"
            "校园 IT 服务台。实现 `handle_campus_it_ticket(ticket, device_status, knowledge)`。\n\n"
            "规则：\n\n"
            "- 轨迹始终从 `validate`、`route` 开始\n"
            "- `urgent=True`：直接 `onsite`，安排现场工程师\n"
            "- `category='device'`：按 `device_id` 查询状态；找不到则转 `onsite`\n"
            "- `category='account'`：从知识中选择 tags 含 `account` 且 priority 最高的条目；"
            "找不到则转 `human`\n"
            "- `category='chat'`：直接返回服务范围说明\n"
            "- 置信度低于 0.65：转 `human`\n"
            "- 返回 `ticket_id`、`route`、`answer`、`citations`、`trace`\n"
            "- 非法类别、空 id 或非法置信度抛出 `ValueError`\n\n"
            "**迁移重点**：需要在不同业务约束下重新组合校验、路由、工具查询、"
            "知识引用、安全降级和可观察轨迹。"
        ),
        "cases": [
            {
                "description": "紧急工单直接安排现场支持",
                "args": [
                    {"id": "T1", "category": "account", "confidence": 0.99, "urgent": True},
                    {},
                    [],
                ],
                "expected": {
                    "ticket_id": "T1",
                    "route": "onsite",
                    "answer": "已安排现场工程师优先处理。",
                    "citations": [],
                    "trace": ["validate", "route", "onsite"],
                },
                "immutable": True,
            },
            {
                "description": "查询设备在线状态",
                "args": [
                    {"id": "T2", "category": "device", "confidence": 0.9, "urgent": False, "device_id": "PC-7"},
                    {"PC-7": "离线"},
                    [],
                ],
                "expected": {
                    "ticket_id": "T2",
                    "route": "device",
                    "answer": "设备PC-7当前状态：离线",
                    "citations": [],
                    "trace": ["validate", "route", "device"],
                },
            },
            {
                "description": "账号问题引用最高优先级知识",
                "args": [
                    {"id": "T3", "category": "account", "confidence": 0.8, "urgent": False},
                    {},
                    [
                        {"id": "K1", "text": "通过统一身份平台重置密码", "tags": ["account"], "priority": 3},
                        {"id": "K2", "text": "联系学院管理员", "tags": ["account"], "priority": 1},
                    ],
                ],
                "expected": {
                    "ticket_id": "T3",
                    "route": "knowledge",
                    "answer": "通过统一身份平台重置密码",
                    "citations": ["K1"],
                    "trace": ["validate", "route", "knowledge"],
                },
            },
            {
                "description": "低置信度安全转人工",
                "args": [
                    {"id": "T4", "category": "device", "confidence": 0.5, "urgent": False, "device_id": "PC-1"},
                    {"PC-1": "在线"},
                    [],
                ],
                "expected": {
                    "ticket_id": "T4",
                    "route": "human",
                    "answer": "信息不足，已转交人工服务台核实。",
                    "citations": [],
                    "trace": ["validate", "route", "human"],
                },
            },
        ],
    },
}
