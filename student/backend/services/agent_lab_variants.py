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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "判断顺序很重要",
                        "content": "权限检查有固定的优先级——先排除非法输入，再检查是否在允许范围内，最后判断是否需要额外确认。想想：如果工具根本不在允许列表中，还需要检查它是否高风险吗？"
                },
                {
                        "level": 2,
                        "title": "三层决策模型",
                        "content": "函数需要按顺序做三件事：(1) 验证 call 中各字段的类型是否合法 (2) 检查工具名是否在 allowed_tools 中，不在则拒绝 (3) 检查是否在高风险列表中且用户未确认，是则要求确认，否则放行。注意：输入验证要放在最前面，尽早抛出 ValueError。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：检查 call['name'] 是否为非空字符串、call['args'] 是否为 dict、call['confirmed'] 是否为 bool，任一不满足则 raise ValueError。\n第二步：若 call['name'] 不在 allowed_tools 中，返回 decision='deny'。\n第三步：若 call['name'] 在 high_risk_tools 中且 call['confirmed'] 为 False，返回 decision='confirm'。\n第四步：其余情况返回 decision='allow'。\n注意使用 dict(call) 或 copy 创建新字典，不要修改原始输入。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "安全第一的设计",
                        "content": "这个场景的核心是「失败即停止」——想象你在执行故障恢复脚本，如果重启失败就继续释放流量，会造成更严重的后果。关键点：如何在遍历过程中检测到失败并立即返回？"
                },
                {
                        "level": 2,
                        "title": "遍历与提前退出",
                        "content": "先验证 plan 非空且 tool_results 包含所有步骤的结果——缺失任何一步都应拒绝执行。然后用 for 循环遍历 plan，每步检查 tool_results[step]：True 则追加到 executed 列表继续，False 则立即返回失败状态并标记 failed_step。循环正常结束说明全部成功。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：if not plan or any(step not in tool_results for step in plan): raise ValueError。\n第二步：创建 executed = []，遍历 plan 中的每个 step。\n第三步：executed.append(step)，若 tool_results[step] 为 False，返回 {'executed': executed, 'status': 'failed', 'failed_step': step}。\n第四步：循环结束后返回 {'executed': executed, 'status': 'completed', 'failed_step': None}。\n注意用 plan.copy() 避免修改输入列表，返回新字典。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "策略驱动的合并",
                        "content": "不是简单覆盖——不同字段有不同的合并规则。温度要覆盖（取最新值），告警要追加（保留历史），计数器要累加。关键是：从哪里读取每个字段该用什么策略？"
                },
                {
                        "level": 2,
                        "title": "遍历 + 查表模式",
                        "content": "先复制 current 避免修改输入。然后遍历 update 的每个字段，用 policies.get(field, 'replace') 查策略。append 时需要确保新旧值都是列表再拼接；sum 时需要确保都是非布尔数字再相加；默认直接覆盖。类型不匹配时抛出 ValueError。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：result = dict(current) 创建副本。\n第二步：for key, new_val in update.items(): 获取 policy = policies.get(key, 'replace')。\n第三步：若 policy == 'append'，验证 isinstance(result.get(key), list) and isinstance(new_val, list) 后 result[key] = result.get(key, []) + new_val。\n第四步：若 policy == 'sum'，验证两者都是 (int|float) 且非 bool 后 result[key] = result.get(key, 0) + new_val。\n第五步：若 policy == 'replace' 直接 result[key] = new_val；否则 raise ValueError。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "优先级分层的判断",
                        "content": "不是简单的 if-elif 链——有些条件（如生命安全）必须优先于其他所有规则。想想：如果一个事件既涉及生命安全又属于 network 类别，应该路由到哪里？哪个条件应该写在最前面？"
                },
                {
                        "level": 2,
                        "title": "先验证，再按优先级判断",
                        "content": "首先验证 confidence 是 0~1 之间的非布尔数字，不是则抛 ValueError。然后按优先级从高到低判断：(1) life_safety 或 severity=='critical' → emergency (2) confidence < 0.7 → manual_review (3) 按 category 路由到对应团队。未知类别抛 ValueError。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：验证 isinstance(incident['confidence'], (int, float)) and not isinstance(incident['confidence'], bool) and 0 <= incident['confidence'] <= 1，不满足则 raise ValueError。\n第二步：if incident.get('life_safety') or incident.get('severity') == 'critical': return 'emergency'。\n第三步：if incident['confidence'] < 0.7: return 'manual_review'。\n第四步：用 if-elif 按 category 返回对应团队：network→network_team, power/water→facility_team, access→security_team，else raise ValueError。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "白名单过滤",
                        "content": "配送车断电恢复时不应保留 api_key 等敏感信息。关键思路：不是保存所有字段，而是只允许白名单中的字段（location、next_action、cargo）进入检查点。想想如何从 state 字典中只提取这些字段？"
                },
                {
                        "level": 2,
                        "title": "验证 + 过滤 + 组装",
                        "content": "函数分三步：(1) 验证 task_id 非空字符串、version 为正整数、state 包含必需字段 (2) 从 state 中只提取 location、next_action 和可选的 cargo，忽略其他键 (3) 组装返回字典，resume_token 格式为 f'{task_id}:{version}'。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：验证 isinstance(task_id, str) and task_id.strip() 非空；验证 isinstance(version, int) and not isinstance(version, bool) and version > 0；验证 'location' in state and 'next_action' in state。\n第二步：filtered = {'location': state['location'], 'next_action': state['next_action']}，若 'cargo' in state 则 filtered['cargo'] = state['cargo']。\n第三步：return {'task_id': task_id, 'version': version, 'state': filtered, 'resume_token': f'{task_id}:{version}'}。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "双维度打分",
                        "content": "每个资源的得分由两部分组成：查询词匹配分 + 院系偏好加分。先想想如何去掉 query_terms 中的重复词，然后在资源的 terms 列表中逐一检查命中。"
                },
                {
                        "level": 2,
                        "title": "计算 → 过滤 → 排序 → 截断",
                        "content": "流程分四步：(1) 对 query_terms 去重得到 terms_set (2) 遍历 resources，计算 score = 命中数 + 院系加分 (3) 过滤 score < min_score 的项 (4) 按 score 降序、id 升序稳定排序后取前 top_k 条。返回时只保留 id、title、score 三个字段。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：if top_k <= 0 or min_score < 0: raise ValueError；terms_set = list(set(query_terms))。\n第二步：for r in resources: score = sum(1 for t in terms_set if t in r.get('terms', []))；if r.get('department') == department: score += 1。\n第三步：if score >= min_score: 收集 {'id': r['id'], 'title': r['title'], 'score': score}。\n第四步：sorted(results, key=lambda x: (-x['score'], x['id']))[:top_k]。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "可靠性与时效性",
                        "content": "校务回答必须有据可查。关键约束有两个：证据必须足够新（近两年内），且过期证据要明确告知用户。想想：空问题、非法年份、不完整的证据条目——这些边界情况应该怎么处理？"
                },
                {
                        "level": 2,
                        "title": "三步处理流水线",
                        "content": "(1) 验证输入合法性：question 非空、current_year 是正整数、每条 evidence 含 id/text/year (2) 筛选有效证据 year >= current_year-1，最多取前三条 (3) 无证据→无法确认转人工；有有效→分号连接正文并返回 citations；全过期→提示过期转人工。务必统计 stale_sources 数量。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：if not question.strip() or not isinstance(current_year, int) or isinstance(current_year, bool): raise ValueError；遍历 evidence 确保每条含 id、text、year。\n第二步：valid = [e for e in evidence if e['year'] >= current_year - 1][:3]；stale = len([e for e in evidence if e['year'] < current_year - 1])。\n第三步：if not evidence: answer='暂未找到可靠政策依据...', needs_human=True。\nelif not valid: answer='现有资料已过期...', needs_human=True。\nelse: answer='根据现行政策：' + '；'.join(e['text'] for e in valid), citations=[e['id'] for e in valid], needs_human=False。"
                }
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
        ],        "hints": [
                {
                        "level": 1,
                        "title": "多层决策编排",
                        "content": "这是最复杂的变式——你需要像调度员一样编排多个决策层。先画出决策树：紧急优先 → 置信度检查 → 按类别分流。每个分支的返回格式都一样（ticket_id/route/answer/citations/trace），保持统一。"
                },
                {
                        "level": 2,
                        "title": "按优先级编排决策",
                        "content": "函数结构：(1) 验证 ticket 字段合法性 (2) 初始化 trace=['validate','route'] (3) 按优先级判断：urgent→onsite 最高；confidence<0.65→human；然后按 category 分流——device 查 device_status、account 找最高 priority 知识、chat 返回服务说明；未知类别抛错 (4) 每个分支都要追加对应节点到 trace。"
                },
                {
                        "level": 3,
                        "title": "分步实现指南",
                        "content": "第一步：验证 ticket['id'] 非空字符串、confidence 是 0~1 数字、category 是合法值。\n第二步：trace = ['validate', 'route']；若 ticket.get('urgent')：trace.append('onsite')，返回现场工程师已安排。\n第三步：if ticket['confidence'] < 0.65: trace.append('human')，返回转人工。\n第四步：按 category 处理——device: status = device_status.get(ticket.get('device_id',''))，存在则 trace.append('device') 并返回状态描述，不存在则转 onsite；account: 从 knowledge 中筛选 tags 含 'account' 的按 priority 降序取第一个，trace.append('knowledge')，返回知识文本和 citations=[k['id']]；chat: trace.append('chat')，返回 IT 服务范围说明。"
                }
        ],

    },
}
