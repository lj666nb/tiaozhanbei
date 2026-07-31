"""面向工程实践的 Agent 课程蓝图。

学习路径、教程资料与编程实验通过 material/lab_id 显式绑定，避免再次退化成
只罗列知识概念的课程目录。
"""

COURSE_TRACKS = [
    {
        "name": "起步：第一段 AI 对话",
        "description": "从环境配置开始，亲手完成单轮对话、多轮记忆与流式输出。",
        "tasks": [
            {
                "topic": "项目1：发出第一条模型消息",
                "knowledge": "01-第一段LangChain对话",
                "framework": "LangChain",
                "deliverable": "可运行的 chat.py",
                "duration": "45分钟",
                "action": "安装依赖、配置环境变量，用消息列表调用模型并打印回答",
                "resource": "引导教程 + 编程实验 1-1",
                "check": "能解释 system/user 消息的作用，并构造合法消息列表",
                "lab_id": "1-1",
                "module_id": 1,
            },
            {
                "topic": "项目2：让对话记住上下文",
                "knowledge": "02-多轮对话与上下文",
                "framework": "LangChain",
                "deliverable": "带历史记录的命令行聊天",
                "duration": "60分钟",
                "action": "维护消息历史、追加一轮对话并限制上下文长度",
                "resource": "引导教程 + 编程实验 1-2",
                "check": "连续追问时能引用上一轮信息，历史超限时可安全裁剪",
                "lab_id": "1-2",
                "module_id": 1,
            },
            {
                "topic": "项目3：实现流式回答体验",
                "knowledge": "03-流式输出与健壮配置",
                "framework": "LangChain",
                "deliverable": "逐字输出且可处理空片段的聊天程序",
                "duration": "60分钟",
                "action": "使用 stream、统一片段格式并补充超时与错误提示",
                "resource": "引导教程 + 编程实验 1-3",
                "check": "流式片段可稳定拼接，接口失败时能给出可执行排查信息",
                "lab_id": "1-3",
                "module_id": 1,
            },
        ],
    },
    {
        "name": "LangChain：链与工具 Agent",
        "description": "先搭建订单数据库，再把它接入可复用提示链、工具调用和 Agent 循环。",
        "tasks": [
            {
                "topic": "项目4：用 SQLAlchemy 构建订单数据库",
                "knowledge": "04-SQLAlchemy订单数据库",
                "framework": "SQLAlchemy + SQLite",
                "deliverable": "可查询的订单数据库",
                "duration": "75分钟",
                "action": "定义 Order 模型、创建 SQLite 引擎、实现带过滤的查询函数",
                "resource": "引导教程 + 编程实验 2-1",
                "check": "可按状态、客户、金额组合查询，过滤条件和结果字段正确",
                "lab_id": "2-1",
                "module_id": 2,
            },
            {
                "topic": "项目5：构建可复用提示链",
                "knowledge": "04-LangChain提示链",
                "framework": "LangChain",
                "deliverable": "客服提示模板与输入校验",
                "duration": "60分钟",
                "action": "把角色、业务约束和用户问题拆成可复用提示链，基于项目4的订单数据生成回复",
                "resource": "引导教程 + 编程实验 2-2",
                "check": "模板字段缺失时明确报错，相同模板可处理不同问题",
                "lab_id": "2-2",
                "module_id": 2,
            },
            {
                "topic": "项目6：给 Agent 接上业务工具",
                "knowledge": "05-LangChain工具调用",
                "framework": "LangChain",
                "deliverable": "订单查询与退款规则工具",
                "duration": "75分钟",
                "action": "定义工具契约、校验调用参数并安全返回工具结果，工具内部对接项目4的订单数据库",
                "resource": "引导教程 + 编程实验 2-3",
                "check": "未知工具和非法参数不会被执行，正常调用返回统一结构",
                "lab_id": "2-3",
                "module_id": 2,
            },
            {
                "topic": "项目7：完成第一个工具 Agent",
                "knowledge": "06-LangChain工具Agent",
                "framework": "LangChain create_agent",
                "deliverable": "可循环调用工具的客服 Agent",
                "duration": "90分钟",
                "action": "用 create_agent 连接模型与工具，并理解模型—工具—模型循环",
                "resource": "引导教程 + 编程实验 2-4",
                "check": "能执行多步工具计划、保留每步观察结果并生成最终回答",
                "lab_id": "2-4",
                "module_id": 2,
            },
        ],
    },
    {
        "name": "LangGraph：状态与工作流",
        "description": "显式管理状态、节点、条件边和持久化，让复杂流程可观察、可恢复。",
        "tasks": [
            {
                "topic": "项目8：搭建第一个 StateGraph",
                "knowledge": "07-LangGraph状态图",
                "framework": "LangGraph",
                "deliverable": "输入—模型—输出状态图",
                "duration": "75分钟",
                "action": "定义 TypedDict 状态、节点返回增量并编译执行图",
                "resource": "引导教程 + 编程实验 3-1",
                "check": "节点只更新负责的字段，状态合并结果可预测",
                "lab_id": "3-1",
                "module_id": 3,
            },
            {
                "topic": "项目9：用条件边实现智能路由",
                "knowledge": "08-LangGraph条件路由",
                "framework": "LangGraph",
                "deliverable": "咨询/查单/人工三路客服图",
                "duration": "90分钟",
                "action": "设计路由函数与条件边，让不同请求进入不同节点",
                "resource": "引导教程 + 编程实验 3-2",
                "check": "紧急或低置信度请求转人工，其余请求进入正确业务节点",
                "lab_id": "3-2",
                "module_id": 3,
            },
            {
                "topic": "项目10：加入记忆、检查点与恢复",
                "knowledge": "09-LangGraph记忆与恢复",
                "framework": "LangGraph",
                "deliverable": "可按 thread_id 延续的对话图",
                "duration": "90分钟",
                "action": "使用 checkpointer 保存线程状态，模拟失败后从检查点恢复",
                "resource": "引导教程 + 编程实验 3-3",
                "check": "不同线程互不串话，同一线程可在历史状态上继续执行",
                "lab_id": "3-3",
                "module_id": 3,
            },
        ],
    },
    {
        "name": "工程项目：可上线客服 Agent",
        "description": "把检索、引用、容错、人工升级和端到端编排组合成完整工程。",
        "tasks": [
            {
                "topic": "项目11：实现可验证的知识检索",
                "knowledge": "10-RAG检索与引用",
                "framework": "LangChain + RAG",
                "deliverable": "带分数与来源的 Top-K 检索器",
                "duration": "90分钟",
                "action": "切分知识、计算相关度、过滤低分结果并保留引用来源",
                "resource": "引导教程 + 编程实验 4-1",
                "check": "结果按相关度稳定排序，低于阈值的内容不会污染上下文",
                "lab_id": "4-1",
                "module_id": 4,
            },
            {
                "topic": "项目12：实现有依据的回答与降级",
                "knowledge": "11-有依据回答与降级",
                "framework": "LangGraph + RAG",
                "deliverable": "拒绝无依据回答的生成节点",
                "duration": "90分钟",
                "action": "组织检索上下文、输出引用，在无证据时转人工而非编造",
                "resource": "引导教程 + 编程实验 4-2",
                "check": "回答中的引用可追溯；无结果、超时和异常都有明确降级路径",
                "lab_id": "4-2",
                "module_id": 4,
            },
            {
                "topic": "毕业项目：端到端客服 Agent",
                "knowledge": "12-端到端Agent工程",
                "framework": "LangChain + LangGraph",
                "deliverable": "可审计、可恢复、可转人工的客服系统",
                "duration": "120分钟",
                "action": "组合意图路由、检索、工具执行、人工升级与运行轨迹",
                "resource": "引导教程 + 编程实验 4-3",
                "check": "完成私有业务场景测试、代码答辩和故障修复闭环",
                "lab_id": "4-3",
                "module_id": 4,
            },
        ],
    },
]

TRACK_NAMES = [track["name"] for track in COURSE_TRACKS]


def build_course_path(selected_tracks: list[str], learning_depth: str = "标准") -> dict:
    """按课程既定依赖顺序构建项目制学习路径。"""
    selected = set(selected_tracks)
    phases = []
    day = 1
    for track in COURSE_TRACKS:
        if track["name"] not in selected:
            continue
        tasks = []
        for source in track["tasks"]:
            task = {"day": day, **source}
            tasks.append(task)
            day += 1
        phases.append({
            "name": track["name"],
            "description": track["description"],
            "tasks": tasks,
        })

    return {
        "curriculum_version": "agent-project-path-v1",
        "phases": phases,
        "estimated_total_days": day - 1,
        "learning_depth": learning_depth,
        "weekly_goals": [
            "每次学习都运行代码，保存一次可复现结果",
            "先完成最小版本，再补边界、错误处理和测试",
            "每周至少完成一次代码解释或故障修复",
        ],
        "key_milestones": [
            "独立完成多轮 AI 对话",
            "完成可调用工具的 LangChain Agent",
            "完成可恢复的 LangGraph 工作流",
            "交付端到端客服 Agent",
        ],
        "tips": "按项目顺序学习。教程负责带你敲出第一版，实验室负责检验你能否独立补全、解释和修复。",
        "modules_selected": selected_tracks,
    }
