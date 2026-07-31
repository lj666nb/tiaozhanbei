import { onMounted, nextTick } from 'vue'
import mermaid from 'mermaid'

// ===================================================================
//  全局单例
// ===================================================================
let initialized = false

// ===================================================================
//  Mermaid 主题：圆角矩形 · 浅蓝科技风（#409EFF）
// ===================================================================
const BASE_THEME = {
  theme: 'base',
  themeVariables: {
    primaryColor: '#e8f4fd',
    primaryBorderColor: '#409EFF',
    primaryTextColor: '#1a1a2e',
    lineColor: '#409EFF',
    secondaryColor: '#f0f7ff',
    fontSize: '14px',
    fontFamily: 'inherit',
    borderRadius: '10px',
  },
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
    padding: 20,
    nodeSpacing: 50,
    rankSpacing: 50,
    useMaxWidth: true,
  },
  maxTextSize: 50000,
  maxEdges: 500,
  securityLevel: 'loose',
  startOnLoad: false,
}

// ===================================================================
//  初始化
// ===================================================================
export function initMermaid(config = {}) {
  if (initialized) return
  mermaid.initialize({ ...BASE_THEME, ...config })
  initialized = true
}

// ===================================================================
//  渲染：查找容器内 <code class="language-mermaid"> → 转 <div> → mermaid.run
// ===================================================================
export async function renderMermaidIn(container) {
  if (typeof container === 'string') container = document.querySelector(container)
  if (!container) return 0
  if (!initialized) initMermaid()

  // step 1: convert <code class="language-mermaid"> to <div class="mermaid">
  container.querySelectorAll('code.language-mermaid').forEach((code) => {
    const pre = code.closest('pre')
    if (!pre) return
    const div = document.createElement('div')
    div.className = 'mermaid'
    div.textContent = code.textContent
    pre.replaceWith(div)
  })

  // step 2: render each mermaid div individually (better error isolation)
  const divs = container.querySelectorAll('div.mermaid:not([data-processed])')
  if (divs.length === 0) return 0

  let successCount = 0
  for (const d of divs) {
    d.setAttribute('data-processed', 'true')
    const code = d.textContent.trim()
    if (!code) continue

    try {
      // 先验证语法
      await mermaid.parse(code)
      // 语法OK，生成唯一ID并渲染
      const id = 'mermaid_' + Math.random().toString(36).slice(2, 10)
      const { svg } = await mermaid.render(id, code)
      d.innerHTML = svg
      successCount++
    } catch (e) {
      console.error('[useMermaid] 渲染失败:', e.message || e, 'code:', code.substring(0, 200))
      // 提取第一个节点名作为标题
      var title = '流程图'
      var m = code.match(/flowchart\s+(TD|LR)\s*([\s\S]*)/i)
      if (m) {
        var firstNode = m[2].match(/(\w+)\[/)
        if (firstNode) title = firstNode[1]
      }
      d.innerHTML = '<div style="padding:16px;background:#fafafa;border:1px dashed #d9d9d9;border-radius:8px;text-align:center;color:#909399;font-size:13px">'
        + '<span>图表渲染失败</span>'
        + '<span style="display:block;margin-top:4px;font-size:11px;color:#c0c4cc">' + title + '</span>'
        + '</div>'
      // 把错误信息存为隐藏属性方便调试
      d.setAttribute('data-mermaid-error', e.message || 'unknown')
    }
  }
  return successCount
}

// ===================================================================
//  Vue 3 组合式函数
// ===================================================================
export function useMermaid(containerRef) {
  const render = async () => {
    await nextTick()
    if (!containerRef?.value) return 0
    return renderMermaidIn(containerRef.value)
  }
  const reRender = async (retries = 2) => {
    let count = await render()
    for (let i = 0; i < retries && count === 0; i++) {
      await new Promise(r => setTimeout(r, 200))
      count = await render()
    }
    return count
  }
  onMounted(async () => { await reRender() })
  return { render, reRender }
}

// ===================================================================
//  中文术语 → camelCase 英文 ID 映射表
// ===================================================================
const SEMANTIC_MAP = {
  'AI智能体': 'aiAgent', '智能体': 'agent',
  '大语言模型': 'llmCore', '推理引擎': 'reasoningEngine', 'LLM': 'llmCore',
  '工具系统': 'toolSystem', '记忆系统': 'memorySystem',
  '规划系统': 'planningSystem', '感知系统': 'perceptionSystem',
  '文本理解': 'textUnderstand', '知识推理': 'knowledgeReason',
  '内容生成': 'contentGenerate', '意图识别': 'intentRecognize',
  '情感分析': 'sentimentAnalyze', '逻辑判断': 'logicJudge',
  '搜索/代码': 'searchCode', 'API/文件': 'apiFile',
  '工具调用执行': 'toolExec',
  '短期记忆': 'shortMemory', '长期记忆': 'longMemory', '工作记忆': 'workingMemory',
  '短/长/工': 'shortMemory', '作记忆': 'workingMemory',
  '任务拆解': 'taskSplit', '步骤调度': 'stepSchedule', '规划器拆解': 'taskSplit',
  '多模态': 'multimodal', '实时数据': 'realtimeData',
  '感知层': 'perceptionLayer', '推理层': 'reasoningLayer', '执行层': 'actionLayer',
  '规划模块': 'planningModule', '记忆模块': 'memoryModule', '工具模块': 'toolModule',
  'Observe': 'observe', '观察': 'observe', 'Orient': 'orient', '判断': 'orient',
  'Decide': 'decide', '决策': 'decide', 'Think': 'think', '思考': 'think',
  'Act': 'act', '行动': 'act',
  '传感器': 'sensor', '条件-动作规则集': 'ruleEngine', '执行器': 'actuator',
  '世界模型': 'worldModel', '规划器': 'planner',
  '反应层': 'reactiveLayer', '慎思层': 'deliberativeLayer',
  '协调层': 'coordinationLayer', '消息总线': 'messageBus',
  '信念': 'belief', '欲望': 'desire', '意图': 'intention',
  '用户/环境': 'userEnv', '用户': 'user', '环境反馈': 'feedback',
  '输入目标': 'inputGoal', '输入文本': 'inputText', '输出文本': 'outputText',
  '交付成果': 'deliverable', '循环直到目标达成': 'loopGoal',
  '观察结果反馈': 'observationFeedback',
  '反应性': 'reactivity', '主动性': 'proactiveness',
  '自主性': 'autonomy', '社交能力': 'socialAbility',
  '协调智能体': 'orchestrator', '搜索智能体': 'searcher',
  '分析智能体': 'analyst', '写作智能体': 'writer',
  '紧急制动': 'emergencyBrake', '连接断开重连': 'reconnect', '异常熔断': 'circuitBreak',
  '用户改变需求': 'demandChange', '数据源超时': 'sourceTimeout', '工具调用失败': 'toolFail',
  '市场趋势变化': 'marketTrend', '用户行为模式改变': 'behaviorShift', '政策更新': 'policyUpdate',
  '自然语言对话': 'nlpDialog', '情感识别': 'emotionDetect', '意图理解': 'intentParse',
  '消息传递': 'msgPass', '任务分配': 'taskAssign', '结果汇总': 'resultMerge',
  '承担特定角色': 'takeRole', '履行角色职责': 'dutyExec',
  '冲突解决': 'conflictResolve', '资源竞争共识': 'resourceConsensus',
}

/** 清洗 mermaid 节点标签中的非法字符（引号、换行等会导致解析失败） */
function _sanitizeLabel(text) {
  if (!text) return ''
  return text
    .replace(/["""]/g, '')      // 移除所有双引号（mermaid 用 " 做标签定界符）
    .replace(/\n/g, ' ')        // 换行 → 空格
    .replace(/\\/g, '')         // 反斜杠 → 移除
    .trim()
}

/** 将文本转为 camelCase 语义 ID */
function _id(text) {
  if (SEMANTIC_MAP[text]) return SEMANTIC_MAP[text]
  for (const [k, v] of Object.entries(SEMANTIC_MAP)) { if (text.includes(k)) return v }
  const eng = text.match(/[A-Za-z][a-z]+/g)
  if (eng && eng.length >= 2) return eng.map((w, i) => i === 0 ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()).join('').substring(0, 24)
  const cn = text.replace(/[^一-龥]/g, '').substring(0, 4)
  return cn ? 'node' + cn : 'node'
}

// ===================================================================
//  统一包装：节点定义 + 箭头 + classDef
// ===================================================================
function _fmt(defs, edges, nodeIds) {
  const classLines = nodeIds && nodeIds.length > 0
    ? _wrapClassLine(nodeIds)
    : ''
  return '```mermaid\n' +
    'flowchart TD\n' +
    defs +
    (edges ? '\n' + edges : '') +
    '\n    %% 统一样式：圆角矩形 · 浅蓝色\n' +
    '    classDef boxStyle fill:#e8f4fd,stroke:#409EFF,rx:10\n' +
    classLines +
    '\n```'
}

/** 将 class 行按合理长度换行 */
function _wrapClassLine(ids) {
  if (ids.length === 0) return ''
  const lines = []
  let cur = ''
  for (const id of ids) {
    const part = (cur ? ',' : '') + id
    if (cur && (cur + part).length > 72) {
      lines.push('    class ' + cur + ' boxStyle')
      cur = id
    } else {
      cur += part
    }
  }
  if (cur) lines.push('    class ' + cur + ' boxStyle')
  return lines.join('\n')
}

// ===================================================================
//  ASCII → Mermaid 总入口（模式匹配分发）
// ===================================================================
export function asciiToMermaid(ascii) {
  if (!ascii || typeof ascii !== 'string') return null
  const lines = ascii.split('\n')
  if ((ascii.match(/[┌─│└├┐┘┴┬┤┼]/g) || []).length < 6) return null
  if (ascii.includes('AI智能体') && ascii.includes('大语言模型')) return _aiAgent()
  if ((ascii.includes('Observe') && ascii.includes('Act')) ||
      (ascii.includes('观察') && ascii.includes('行动') && ascii.includes('思考'))) return _ota(ascii)
  if (ascii.includes('▼')) return _vertical(ascii, lines)
  if ((ascii.match(/├|┤/g) || []).length >= 2) return _layered(ascii, lines)
  if (ascii.includes('▶')) return _horizontal(ascii, lines)
  if (ascii.includes('┬') || ascii.includes('┴')) return _tree(ascii, lines)
  return null
}

// ===================================================================
//  模式1：AI 智能体嵌套层级图
// ===================================================================
function _aiAgent() {
  const defs = [
    '    %% 顶层节点',
    '    aiAgent[" AI智能体"]',
    '    llmCore[" 大语言模型<br/>（推理引擎）"]',
    '',
    '    subgraph cap [" 推理能力"]',
    '        direction LR',
    '        textUnderstand["文本理解"]',
    '        knowledgeReason["知识推理"]',
    '        contentGenerate["内容生成"]',
    '        intentRecognize["意图识别"]',
    '        sentimentAnalyze["情感分析"]',
    '        logicJudge["逻辑判断"]',
    '    end',
    '',
    '    subgraph toolSystem [" 工具系统"]',
    '        searchCode["搜索/代码"]',
    '        apiFile["API/文件"]',
    '    end',
    '',
    '    subgraph memorySystem [" 记忆系统"]',
    '        shortMemory["短期记忆"]',
    '        longMemory["长期记忆"]',
    '        workingMemory["工作记忆"]',
    '    end',
    '',
    '    subgraph planningSystem [" 规划系统"]',
    '        taskSplit["任务拆解"]',
    '        stepSchedule["步骤调度"]',
    '    end',
    '',
    '    subgraph perceptionSystem [" 感知系统"]',
    '        multimodal["多模态"]',
    '        realtimeData["实时数据"]',
    '    end',
  ].join('\n')

  const edges = [
    '    %% 箭头关系',
    '    aiAgent --> llmCore',
    '    llmCore --> cap',
    '    aiAgent --> toolSystem',
    '    aiAgent --> memorySystem',
    '    aiAgent --> planningSystem',
    '    aiAgent --> perceptionSystem',
  ].join('\n')

  const ids = ['aiAgent', 'llmCore', 'textUnderstand', 'knowledgeReason', 'contentGenerate',
    'intentRecognize', 'sentimentAnalyze', 'logicJudge', 'searchCode', 'apiFile',
    'shortMemory', 'longMemory', 'workingMemory', 'taskSplit', 'stepSchedule', 'multimodal', 'realtimeData']
  return _fmt(defs, edges, ids)
}

// ===================================================================
//  模式2：OTA / OODA 循环图
// ===================================================================
function _ota(ascii) {
  const isOODA = ascii.includes('Orient') || ascii.includes('判断')
  let defs, edges, ids

  if (isOODA) {
    defs = [
      '    %% 节点定义',
      '    observe[" Observe 观察"]',
      '    orient["🧭 Orient 判断"]',
      '    decide[" Decide 决策"]',
      '    actOoda[" Act 行动"]',
    ].join('\n')
    edges = [
      '    %% 循环关系',
      '    observe --> orient',
      '    orient --> decide',
      '    decide --> actOoda',
      '    actOoda -.->|循环| observe',
    ].join('\n')
    ids = ['observe', 'orient', 'decide', 'actOoda']
  } else {
    defs = [
      '    %% 节点定义',
      '    observe[" Observe 观察"]',
      '    think[" Think 思考"]',
      '    act[" Act 行动"]',
    ].join('\n')
    edges = [
      '    %% 循环关系',
      '    observe --> think',
      '    think --> act',
      '    act -.->|循环| observe',
    ].join('\n')
    ids = ['observe', 'think', 'act']
  }

  return _fmt(defs, edges, ids)
}

// ===================================================================
//  模式3：竖向流程图（▼ 箭头）
// ===================================================================
function _vertical(ascii, lines) {
  const full = lines.join('\n'), boxes = []
  const re = /┌([─]+)┐\n([\s\S]*?)\n└([─]+)┘/g
  let m
  while ((m = re.exec(full)) !== null) {
    const lm = m[2].match(/│\s*(.+?)\s*│/)
    if (lm) boxes.push(lm[1].trim().replace(/\s+/g, ' ').substring(0, 60))
  }
  if (!boxes.length) {
    lines.forEach(l => { const x = l.match(/│\s*([^\s│].{2,60}?)\s*│/); if (x) boxes.push(x[1].trim().replace(/\s+/g, ' ')) })
  }
  if (boxes.length < 2) return null

  const entries = boxes.map(b => {
    const s = b.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').replace(/：.*$/, '').replace(/:.*$/, '').trim()
    return { id: _id(s), label: s || b.substring(0, 30) }
  })

  const seen = new Set(), dl = [], el = [], ids = []
  entries.forEach((e, i) => {
    if (!seen.has(e.id)) { dl.push('    ' + e.id + '["' + _sanitizeLabel(e.label) + '"]'); seen.add(e.id); ids.push(e.id) }
    if (i > 0) el.push('    ' + entries[i - 1].id + ' --> ' + e.id)
  })
  if (dl.length > 0) dl.unshift('    %% 节点定义')
  if (el.length > 0) el.unshift('    %% 箭头关系')
  return _fmt(dl.join('\n'), el.join('\n'), ids)
}

// ===================================================================
//  模式4：分层堆叠（├ ┤）
// ===================================================================
function _layered(ascii, lines) {
  const layers = []
  let cur = { title: '', items: [] }
  lines.forEach(l => {
    const h = l.match(/│\s*(.{2,60}?)(?:（[^）]+）)?\s*│/)
    if (h && l.includes('│')) {
      if (cur.title || cur.items.length > 0) layers.push({ ...cur })
      cur = { title: h[1].trim(), items: [] }
    } else {
      const it = l.match(/│\s*[·•-]\s*(.+?)\s*│/)
      if (it) cur.items.push(it[1].trim())
    }
  })
  if (cur.title || cur.items.length > 0) layers.push(cur)
  if (layers.length < 2) return null

  const dl = [], el = [], ids = []
  layers.forEach((ly, i) => {
    const id = _id(ly.title)
    const desc = ly.items.length ? '<br/>' + ly.items.map(x => '· ' + x).join('<br/>') : ''
    dl.push('    ' + id + '["' + _sanitizeLabel(ly.title + desc) + '"]')
    ids.push(id)
    if (i > 0) el.push('    ' + _id(layers[i - 1].title) + ' --> ' + id)
  })
  if (dl.length > 0) dl.unshift('    %% 节点定义')
  if (el.length > 0) el.unshift('    %% 箭头关系')
  return _fmt(dl.join('\n'), el.join('\n'), ids)
}

// ===================================================================
//  模式5：横向流程（▶ 箭头）
// ===================================================================
function _horizontal(ascii, lines) {
  const full = lines.join('\n'), boxes = []
  const re = /┌([─]+)┐\n([\s\S]*?)\n└([─]+)┘/g
  let m
  while ((m = re.exec(full)) !== null) {
    const hdr = m[0], col = full.indexOf(hdr)
    const tls = m[2].split('\n').map(l => l.replace(/^│\s*/, '').replace(/\s*│$/, '').trim()).filter(Boolean)
    boxes.push({ label: tls.join('<br/>') || '?', col, raw: hdr })
  }
  if (boxes.length < 2) {
    const bls = []
    lines.forEach((l, li) => { const x = l.match(/│\s*(.+?)\s*│/); if (x) bls.push({ t: x[1].trim(), line: li, col: l.indexOf('│') }) })
    const mg = []; let c = null
    bls.forEach(b => {
      if (c && b.line === c.lastLine + 1 && Math.abs(b.col - c.col) < 5) { c.lines.push(b.t); c.lastLine = b.line }
      else { if (c) mg.push(c); c = { lines: [b.t], col: b.col, lastLine: b.line } }
    })
    if (c) mg.push(c)
    mg.forEach(mg => boxes.push({ label: mg.lines.join('<br/>'), col: mg.col, raw: '' }))
  }
  if (boxes.length < 2) return null
  boxes.sort((a, b) => a.col - b.col)

  const ents = boxes.map(b => ({ id: _id(b.label.replace(/<br\/>/g, ' ')), label: b.label }))
  const dl = [], el = [], ids = [], seen = new Set()

  ents.forEach((e, i) => {
    let uid = e.id
    if (seen.has(uid)) uid = e.id + (i + 1)
    seen.add(uid)
    dl.push('    ' + uid + '["' + _sanitizeLabel(e.label) + '"]')
    ids.push(uid)
    if (i > 0) el.push('    ' + ents[i - 1].id + ' --> ' + uid)
  })

  const after = full.substring(boxes[boxes.length - 1].col + (boxes[boxes.length - 1].raw?.length || 20))
  const nm = after.match(/[^\s┌└┐┘┬┴├┤│─▶].{5,60}/)
  if (nm) {
    const note = nm[0].trim()
    if (note.length > 3 && !note.startsWith('```')) {
      const nid = 'note' + note.replace(/[^一-龥]/g, '').substring(0, 4)
      dl.push('    ' + nid + '["' + _sanitizeLabel(note) + '"]')
      ids.push(nid)
      el.push('    ' + ents[ents.length - 1].id + ' -..-> ' + nid)
    }
  }

  if (dl.length > 0) dl.unshift('    %% 节点定义')
  if (el.length > 0) el.unshift('    %% 箭头关系')
  return _fmt(dl.join('\n'), el.join('\n'), ids)
}

// ===================================================================
//  模式6：树形分支（┬ ┴）
// ===================================================================
function _tree(ascii, lines) {
  const nodes = []
  lines.forEach((l, i) => {
    const tm = l.match(/│?\s*([^\s│┌└├┐┘┬┴┤┼─]{2,50})\s*│?/)
    if (tm) nodes.push({ text: tm[1].trim(), line: i, col: l.indexOf(tm[1]) })
  })
  if (nodes.length < 2) return null

  const byLine = {}
  nodes.forEach(n => { if (!byLine[n.line]) byLine[n.line] = []; byLine[n.line].push(n) })
  const sorted = Object.keys(byLine).map(Number).sort((a, b) => a - b)

  const map = new Map(), es = new Set()
  for (let i = 0; i < sorted.length - 1; i++) {
    (byLine[sorted[i]] || []).forEach(p => {
      const pid = _id(p.text); map.set(pid, p.text)
      ;(byLine[sorted[i + 1]] || []).forEach(c => { const cid = _id(c.text); map.set(cid, c.text); es.add(pid + ' --> ' + cid) })
    })
  }

  const dl = [], ids = []
  map.forEach((label, id) => { dl.push('    ' + id + '["' + _sanitizeLabel(label) + '"]'); ids.push(id) })
  const el = Array.from(es).map(e => '    ' + e)

  if (dl.length > 0) dl.unshift('    %% 节点定义')
  if (el.length > 0) el.unshift('    %% 箭头关系')
  return _fmt(dl.join('\n'), el.join('\n'), ids)
}

export default useMermaid
