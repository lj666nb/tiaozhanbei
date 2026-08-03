// 项目制 Agent 编程路线。题目正文与私有测试由后端提供，这里只负责课程导航。
export const MODULES = [
  {
    id: 1,
    name: '阶段一：第一段 AI 对话',
    level: '入门',
    project: '命令行聊天助手',
    description: '从消息协议开始，完成上下文记忆与流式输出；每一关都直接服务于可运行聊天程序。',
    tasks: [
      { id: '1-1', title: '构造第一组对话消息', duration: '45分钟' },
      { id: '1-2', title: '维护并裁剪多轮上下文', duration: '60分钟' },
      { id: '1-3', title: '合并流式响应片段', duration: '60分钟' },
    ],
  },
  {
    id: 2,
    name: '阶段二：LangChain 工具 Agent',
    level: '进阶',
    project: '订单客服 Agent',
    description: '先用 SQLAlchemy 搭建持久化订单数据库（后续项目全部复用），再接入可复用提示链、安全工具契约和 Agent 循环。',
    tasks: [
      { id: '2-1', title: '用 SQLAlchemy 构建订单数据库', duration: '90分钟' },
      { id: '2-2', title: '渲染可复用客服提示模板', duration: '60分钟' },
      { id: '2-3', title: '校验并执行工具调用', duration: '75分钟' },
      { id: '2-4', title: '实现多步工具执行循环', duration: '90分钟' },
    ],
  },
  {
    id: 3,
    name: '阶段三：LangGraph 状态工作流',
    level: '高级',
    project: '可恢复客服工作流',
    description: '显式设计状态增量、条件路由与线程检查点，让复杂流程可观察、可中断、可恢复。',
    tasks: [
      { id: '3-1', title: '合并节点产生的状态增量', duration: '75分钟' },
      { id: '3-2', title: '设计客服请求条件路由', duration: '90分钟' },
      { id: '3-3', title: '实现线程检查点与恢复', duration: '90分钟' },
    ],
  },
  {
    id: 4,
    name: '阶段四：端到端 Agent 工程',
    level: '工程',
    project: '可上线智能客服',
    description: '组合检索、引用、人工升级和执行轨迹，并通过私有业务场景、答辩与故障修复验收。',
    tasks: [
      { id: '4-1', title: '实现带阈值的 Top-K 检索', duration: '90分钟' },
      { id: '4-2', title: '生成有引用的回答与安全降级', duration: '90分钟' },
      { id: '4-3', title: '编排端到端客服 Agent', duration: '120分钟' },
    ],
  },
]

for (const module of MODULES) module.taskCount = module.tasks.length

export const MOCK_PROGRESS = { 1: 0, 2: 0, 3: 0, 4: 0 }
