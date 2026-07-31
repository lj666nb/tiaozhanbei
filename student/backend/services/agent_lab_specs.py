"""服务端私有业务场景。

这些用例不会通过资源接口发送给浏览器；学生只能看到题目契约和失败场景名称。
"""

SPECS = {
    "1-1": {
        "target": "build_chat_messages",
        "cases": [
            {"description": "基础消息顺序", "args": ["你是助教", "解释 Agent"], "expected": [
                {"role": "system", "content": "你是助教"}, {"role": "user", "content": "解释 Agent"}
            ]},
            {"description": "保留个性化对话指令", "args": [
                "你是旅行规划师；称呼用户为小林；优先推荐博物馆",
                "我周末去西安，请结合我的偏好安排半天行程"
            ], "expected": [
                {"role": "system", "content": "你是旅行规划师；称呼用户为小林；优先推荐博物馆"},
                {"role": "user", "content": "我周末去西安，请结合我的偏好安排半天行程"}
            ]},
            {"description": "清理首尾空白", "args": ["  严谨回答  ", "\n你好\t"], "expected": [
                {"role": "system", "content": "严谨回答"}, {"role": "user", "content": "你好"}
            ]},
            {"description": "保留消息内部格式", "args": ["保留\n分行规则", "第一行\n  第二行"], "expected": [
                {"role": "system", "content": "保留\n分行规则"},
                {"role": "user", "content": "第一行\n  第二行"}
            ]},
            {"description": "每次调用返回独立消息对象", "args": ["助教", "你好"], "expected": [
                {"role": "system", "content": "助教"}, {"role": "user", "content": "你好"}
            ], "fresh_result": True},
            {"description": "拒绝空系统提示", "args": ["\n\t", "你好"], "exception": "ValueError"},
            {"description": "拒绝空用户消息", "args": ["助手", "   "], "exception": "ValueError"},
            {"description": "拒绝非字符串系统提示", "args": [None, "你好"], "exception": "ValueError"},
            {"description": "拒绝非字符串用户消息", "args": ["助手", 123], "exception": "ValueError"},
            # ── 以下为增强测试点：确保函数不是简单硬编码 ──
            {"description": "处理仅含空白字符的输入（全角空格与制表符）", "args": ["　　　", "问题"], "exception": "ValueError"},
            {"description": "拒绝布尔值输入", "args": [True, "你好"], "exception": "ValueError"},
            {"description": "拒绝列表类型输入", "args": ["助教", ["问题1", "问题2"]], "exception": "ValueError"},
            {"description": "拒绝数字类型系统提示", "args": [42, "你好"], "exception": "ValueError"},
            {"description": "处理含引号和特殊字符的输入", "args": [
                '请用 "专业" 且 "友好" 的语气回答',
                "解释 '智能体' 和 'Agent' 的区别"
            ], "expected": [
                {"role": "system", "content": '请用 "专业" 且 "友好" 的语气回答'},
                {"role": "user", "content": "解释 '智能体' 和 'Agent' 的区别"}
            ]},
            {"description": "处理含 emoji 的用户消息", "args": ["你是助教", "你好👋 请问如何学习AI？😊"], "expected": [
                {"role": "system", "content": "你是助教"},
                {"role": "user", "content": "你好👋 请问如何学习AI？😊"}
            ]},
            {"description": "处理极长系统提示（200+字符）", "args": [
                "你是一个专业的技术顾问。" + "经验丰富。" * 30,
                "简短问题"
            ], "expected": [
                {"role": "system", "content": "你是一个专业的技术顾问。" + "经验丰富。" * 30},
                {"role": "user", "content": "简短问题"}
            ]},
            {"description": "连续3次调用返回独立对象且不相互污染", "args": ["助教", "测试消息"], "expected": [
                {"role": "system", "content": "助教"}, {"role": "user", "content": "测试消息"}
            ], "fresh_result": True},
        ],
    },
    "1-2": {
        "target": "append_turn_and_trim",
        "cases": [
            {"description": "追加第一轮对话", "args": [[{"role": "system", "content": "助教"}], "问题", "回答", 5], "expected": [
                {"role": "system", "content": "助教"}, {"role": "user", "content": "问题"}, {"role": "assistant", "content": "回答"}
            ], "immutable": True},
            {"description": "保留系统消息与最近上下文", "args": [[
                {"role": "system", "content": "S"}, {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"}, {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"}
            ], "u3", "a3", 5], "expected": [
                {"role": "system", "content": "S"}, {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"}, {"role": "user", "content": "u3"},
                {"role": "assistant", "content": "a3"}
            ], "immutable": True},
            {"description": "无系统消息时从尾部裁剪", "args": [[
                {"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}
            ], "u2", "a2", 3], "expected": [
                {"role": "assistant", "content": "a1"}, {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"}
            ], "immutable": True},
            {"description": "拒绝过小上下文上限", "args": [[], "u", "a", 1], "exception": "ValueError"},
        ],
    },
    "1-3": {
        "mode": "stream_chunks",
        "target": "normalize_stream_chunks",
        "extra_cases": 2,
        "cases": [
            {"description": "拼接字符串与空片段", "args": [["你", None, "", "好"]], "expected": "你好"},
            {"description": "读取消息字典", "args": [[{"content": "流"}, {"content": None}, {"content": "式"}]], "expected": "流式"},
            {"description": "读取文本内容块", "args": [[{"content": [
                {"type": "text", "text": "A"}, {"type": "tool", "id": "1"}, {"type": "text", "text": "B"}
            ]}]], "expected": "AB"},
            {"description": "忽略内容块中的非文本事件", "args": [[{"content": [
                {"type": "tool_call", "name": "search"}, None, {"type": "text", "text": "完成"}
            ]}]], "expected": "完成"},
            {"description": "拒绝未知顶层片段", "args": [[123]], "exception": "ValueError"},
            {"description": "拒绝未知内容结构", "args": [[{"content": 123}]], "exception": "ValueError"},
        ],
    },
    "2-2": {
        "target": "render_support_prompt",
        "cases": [
            {"description": "渲染多个字段", "args": ["用户{user_id}咨询：{question}", {"user_id": "U1", "question": "如何退款"}], "expected": "用户U1咨询：如何退款"},
            {"description": "替换重复占位符", "args": ["{name}你好，确认{name}", {"name": "小林"}], "expected": "小林你好，确认小林"},
            {"description": "允许额外输入字段", "args": ["问题：{q}", {"q": 42, "unused": True}], "expected": "问题：42"},
            {"description": "缺少模板字段时报错", "args": ["{a}-{b}", {"a": "x"}], "exception": "ValueError"},
        ],
    },
    "2-3": {"mode": "tool_call", "target": "execute_tool_call"},
    "2-4": {"mode": "tool_plan", "target": "run_tool_plan"},
    "2-1": {
        "mode": "sqlalchemy_query",
        "target": "setup_order_db",
        "cases": [
            {"description": "创建数据库并定义Order模型", "args": [], "setup_only": True},
            {"description": "按状态过滤已支付订单", "args": [{"status": "paid"}], "expected_count": 3,
             "expected_keys": ["id", "customer_name", "product", "amount", "status"]},
            {"description": "按客户名查询", "args": [{"customer_name": "张三"}], "expected_count": 1},
            {"description": "按最小金额过滤", "args": [{"min_amount": 150.0}], "expected_count": 2},
            {"description": "组合过滤条件", "args": [{"status": "paid", "min_amount": 100.0}], "expected_count": 2},
        ],
        "extra_cases": 2,
    },
    "3-1": {
        "target": "merge_state",
        "cases": [
            {"description": "追加消息并覆盖路由", "args": [
                {"messages": ["u1"], "route": "start"}, {"messages": ["a1"], "route": "done"}, {"messages": "append"}
            ], "expected": {"messages": ["u1", "a1"], "route": "done"}, "immutable": True},
            {"description": "新增普通状态字段", "args": [{"count": 1}, {"answer": "ok"}, {}], "expected": {"count": 1, "answer": "ok"}, "immutable": True},
            {"description": "追加字段首次出现", "args": [{}, {"trace": ["route"]}, {"trace": "append"}], "expected": {"trace": ["route"]}, "immutable": True},
            {"description": "拒绝非列表追加值", "args": [{"messages": []}, {"messages": "bad"}, {"messages": "append"}], "exception": "ValueError"},
        ],
    },
    "3-2": {
        "target": "route_support_request",
        "cases": [
            {"description": "紧急请求优先转人工", "args": [{"intent": "order", "confidence": 0.99, "urgent": True}], "expected": "human"},
            {"description": "低置信度转人工", "args": [{"intent": "faq", "confidence": 0.59, "urgent": False}], "expected": "human"},
            {"description": "置信度边界进入知识节点", "args": [{"intent": "faq", "confidence": 0.6, "urgent": False}], "expected": "knowledge"},
            {"description": "订单与闲聊路由", "args": [{"intent": "order", "confidence": 0.8, "urgent": False}], "expected": "order_tool"},
            {"description": "拒绝布尔置信度", "args": [{"intent": "chat", "confidence": True, "urgent": False}], "exception": "ValueError"},
            {"description": "拒绝未知意图", "args": [{"intent": "other", "confidence": 0.8, "urgent": False}], "exception": "ValueError"},
        ],
    },
    "3-3": {"mode": "checkpoint", "target": "save_checkpoint"},
    "4-1": {
        "target": "retrieve_top_k",
        "cases": [
            {"description": "按相关度和id稳定排序", "args": [["退款", "时效", "退款"], [
                {"id": "B", "text": "退款时效为3天", "terms": ["退款", "时效"]},
                {"id": "A", "text": "退款入口", "terms": ["退款"]},
                {"id": "C", "text": "退款规则", "terms": ["退款", "规则", "时效"]}
            ], 2, 1], "expected": [
                {"id": "B", "text": "退款时效为3天", "score": 2},
                {"id": "C", "text": "退款规则", "score": 2}
            ], "immutable": True},
            {"description": "过滤低分结果", "args": [["发票"], [
                {"id": "A", "text": "退款", "terms": ["退款"]}
            ], 3, 1], "expected": []},
            {"description": "零阈值仍按分数排序", "args": [["x"], [
                {"id": "B", "text": "b", "terms": []}, {"id": "A", "text": "a", "terms": []}
            ], 2, 0], "expected": [
                {"id": "A", "text": "a", "score": 0}, {"id": "B", "text": "b", "score": 0}
            ]},
            {"description": "拒绝非法k", "args": [["x"], [], 0, 0], "exception": "ValueError"},
        ],
    },
    "4-2": {
        "target": "build_grounded_response",
        "cases": [
            {"description": "无证据安全转人工", "args": ["怎么退款", []], "expected": {
                "answer": "暂未找到可靠依据，已为你转接人工客服。", "citations": [], "needs_human": True
            }},
            {"description": "回答与引用对应", "args": ["怎么退款", [
                {"id": "D1", "text": "在订单页申请退款", "score": 3},
                {"id": "D2", "text": "审核通常需要1天", "score": 2}
            ]], "expected": {
                "answer": "根据资料：在订单页申请退款；审核通常需要1天", "citations": ["D1", "D2"], "needs_human": False
            }},
            {"description": "最多引用三条证据", "args": ["q", [
                {"id": "1", "text": "a", "score": 4}, {"id": "2", "text": "b", "score": 3},
                {"id": "3", "text": "c", "score": 2}, {"id": "4", "text": "d", "score": 1}
            ]], "expected": {"answer": "根据资料：a；b；c", "citations": ["1", "2", "3"], "needs_human": False}},
            {"description": "拒绝空问题", "args": ["  ", []], "exception": "ValueError"},
        ],
    },
    "4-3": {
        "target": "handle_support_turn",
        "cases": [
            {"description": "紧急请求直接升级", "args": [
                {"id": "R1", "text": "立即处理", "intent": "faq", "confidence": 0.99, "urgent": True, "terms": ["退款"]}, {}, []
            ], "expected": {"request_id": "R1", "route": "human", "answer": "已为你转接人工客服。", "citations": [], "trace": ["validate", "route", "human"]}, "immutable": True},
            {"description": "订单工具返回状态", "args": [
                {"id": "R2", "text": "订单在哪", "intent": "order", "confidence": 0.9, "urgent": False, "order_id": "O1"},
                {"O1": "已发货"}, []
            ], "expected": {"request_id": "R2", "route": "order", "answer": "订单O1当前状态：已发货", "citations": [], "trace": ["validate", "route", "order"]}, "immutable": True},
            {"description": "找不到订单时降级", "args": [
                {"id": "R3", "text": "查订单", "intent": "order", "confidence": 0.8, "urgent": False, "order_id": "X"}, {}, []
            ], "expected": {"request_id": "R3", "route": "human", "answer": "未找到订单，已为你转接人工客服。", "citations": [], "trace": ["validate", "route", "order", "human"]}},
            {"description": "FAQ检索并引用来源", "args": [
                {"id": "R4", "text": "退款时效", "intent": "faq", "confidence": 0.8, "urgent": False, "terms": ["退款", "时效"]}, {},
                [{"id": "D1", "text": "退款入口", "terms": ["退款"]}, {"id": "D2", "text": "退款时效3天", "terms": ["退款", "时效"]}]
            ], "expected": {"request_id": "R4", "route": "knowledge", "answer": "退款时效3天", "citations": ["D2"], "trace": ["validate", "route", "knowledge"]}},
            {"description": "无知识证据时降级", "args": [
                {"id": "R5", "text": "发票", "intent": "faq", "confidence": 0.8, "urgent": False, "terms": ["发票"]}, {}, []
            ], "expected": {"request_id": "R5", "route": "human", "answer": "暂未找到可靠依据，已为你转接人工客服。", "citations": [], "trace": ["validate", "route", "knowledge", "human"]}},
            {"description": "普通闲聊直接响应", "args": [
                {"id": "R6", "text": "你好", "intent": "chat", "confidence": 0.7, "urgent": False}, {}, []
            ], "expected": {"request_id": "R6", "route": "respond", "answer": "你好，我可以帮你查询订单或解答常见问题。", "citations": [], "trace": ["validate", "route", "respond"]}},
            {"description": "拒绝非法置信度", "args": [
                {"id": "R7", "text": "x", "intent": "chat", "confidence": 2, "urgent": False}, {}, []
            ], "exception": "ValueError"},
        ],
    },
}

FLAGSHIP_IDS = set(SPECS)
