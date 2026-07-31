<template>
  <div class="qa-page">
    <div class="qa-layout">
      <aside :class="['conversation-sidebar', { collapsed: historyCollapsed }]">
        <button class="conversation-toggle" :title="historyCollapsed ? '展开历史记录' : '收起历史记录'" @click="toggleHistory">
          <el-icon><component :is="historyCollapsed ? 'Expand' : 'Fold'" /></el-icon>
        </button>
        <template v-if="!historyCollapsed">
          <button class="new-chat-button" :disabled="creatingConversation" @click="newConversation">
            <el-icon><CirclePlus /></el-icon><span>新建对话</span>
          </button>
          <button class="export-data-button" :disabled="exportingData" @click="exportTrainingData">
            <el-icon><Download /></el-icon><span>{{ exportingData ? '正在导出…' : '导出训练数据' }}</span>
          </button>
          <div class="conversation-caption">最近对话</div>
          <div class="conversation-list">
            <button
              v-for="item in conversations"
              :key="item.id"
              :class="['conversation-item', { active: item.id === conversationId }]"
              @click="openConversation(item.id)"
            >
              <span class="conversation-copy"><b>{{ item.title || '新对话' }}</b><small>{{ item.summary || '还没有消息' }}</small></span>
              <el-icon class="conversation-delete" title="删除会话" @click.stop="removeConversation(item.id)"><Delete /></el-icon>
            </button>
            <div v-if="!conversations.length" class="conversation-empty">暂无历史对话</div>
          </div>
        </template>
      </aside>

      <div class="chat-column">
        <el-card shadow="never" class="chat-card">
          <div class="chat-messages" ref="chatBox" @click="handleCodeBlockAction" @scroll="onChatScroll">
            <!-- 加载更早消息 -->
            <div v-if="hasMoreMessages" class="load-earlier-bar">
              <button class="load-earlier-btn" :disabled="loadingMore" @click="loadEarlierMessages">
                <el-icon><ArrowUp /></el-icon>
                <span>{{ loadingMore ? '加载中…' : '加载更早的消息' }}</span>
              </button>
            </div>
            <div v-if="messages.length === 0" class="welcome-msg">
              <div class="welcome-orb"><el-icon :size="32"><Cpu /></el-icon></div>
              <h3>今天想一起解决什么？</h3>
              <p>我会结合你的学习记录、长期记忆与当前进度回答。</p>
              <div class="quick-questions">
                <el-tag v-for="q in quickQuestions" :key="q" @click="quickAsk(q)" class="quick-tag">{{ q }}</el-tag>
              </div>
            </div>
            <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
              <div class="msg-avatar"><el-icon :size="24"><component :is="msg.role === 'user' ? 'UserFilled' : 'Cpu'" /></el-icon></div>
              <div class="msg-body">
                <!-- 深度思考过程 -->
                <div v-if="msg.thinking" class="thinking-block">
                  <div class="thinking-header" @click="msg.thinkingExpanded = !msg.thinkingExpanded">
                    <el-icon :size="14"><component :is="msg.thinkingExpanded ? 'ArrowDown' : 'ArrowRight'" /></el-icon>
                    <span>深度思考过程</span>
                    <span class="thinking-tag">思考</span>
                  </div>
                  <div v-show="msg.thinkingExpanded !== false" class="thinking-content">
                    <div v-html="renderMarkdown(msg.thinking)"></div>
                  </div>
                </div>
                <!-- RAG 知识库暂不可用提示 -->
                <div v-if="msg.ragUnavailable" class="rag-unavailable-block">
                  <el-icon color="#E6A23C"><WarningFilled /></el-icon>
                  <span>{{ msg.ragUnavailable }}</span>
                </div>
                <div v-if="msg.searchUnavailable" class="rag-unavailable-block">
                  <el-icon color="#E6A23C"><WarningFilled /></el-icon>
                  <span>{{ msg.searchUnavailable }}</span>
                </div>
                <div v-if="msg.toolEvents && msg.toolEvents.length" class="tool-events-block">
                  <span class="tool-events-label">AI 自主工具</span>
                  <span
                    v-for="(event, toolIdx) in msg.toolEvents"
                    :key="toolIdx"
                    :class="['tool-event-chip', event.status]"
                  >{{ toolDisplayName(event.name) }} · {{ toolStatusLabel(event.status) }}</span>
                </div>
                <!-- RAG 知识库来源 -->
                <div v-if="msg.ragSources && msg.ragSources.length" class="rag-sources-block">
                  <div class="rag-sources-header" @click="msg.ragSourcesExpanded = !msg.ragSourcesExpanded">
                    <el-icon :size="14"><component :is="msg.ragSourcesExpanded !== false ? 'ArrowDown' : 'ArrowRight'" /></el-icon>
                    <el-icon color="#67C23A"><Collection /></el-icon>
                    <span>参考知识库（{{ msg.ragSources.length }} 条来源）</span>
                  </div>
                  <div v-show="msg.ragSourcesExpanded !== false">
                    <div class="rag-source-list">
                      <div
                        v-for="(s, i) in msg.ragSources"
                        :key="i"
                        :class="['rag-source-item', { active: i === msg._selectedSourceIndex }]"
                        @click="msg._selectedSourceIndex = (msg._selectedSourceIndex === i ? -1 : i)"
                      >
                        <span class="rag-source-icon">{{ s.source_type === 'pdf' ? '📖' : '📝' }}</span>
                        <span class="rag-source-title">{{ s.title }}</span>
                        <span v-if="s.section" class="rag-source-section">— {{ s.section }}</span>
                        <span v-if="s.page" class="rag-source-page">(第{{ s.page }}页)</span>
                        <el-icon class="rag-source-expand-icon" :size="12"><component :is="i === msg._selectedSourceIndex ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
                      </div>
                    </div>
                    <!-- 展开的源内容 -->
                    <div v-if="msg._selectedSourceIndex >= 0 && msg.ragSources[msg._selectedSourceIndex]" class="rag-source-content">
                      <div class="rag-source-content-header">
                        <el-icon><Collection /></el-icon>
                        <span>{{ msg.ragSources[msg._selectedSourceIndex].title }}</span>
                      </div>
                      <div class="rag-source-content-body" v-html="renderMarkdown(msg.ragSources[msg._selectedSourceIndex].content || '内容加载中…')"></div>
                    </div>
                  </div>
                </div>
                <!-- 联网搜索结果 -->
                <div v-if="msg.searchResults && msg.searchResults.length" class="search-results-block">
                  <div class="search-header" @click="msg.searchResultsExpanded = !msg.searchResultsExpanded">
                    <el-icon :size="14"><component :is="msg.searchResultsExpanded !== false ? 'ArrowDown' : 'ArrowRight'" /></el-icon>
                    <el-icon color="#409EFF"><Search /></el-icon>
                    <span v-if="msg.searchQuery">搜索「{{ msg.searchQuery }}」</span>
                    <span v-else>搜索到 {{ msg.searchResults.length }} 条相关结果</span>
                  </div>
                  <div v-show="msg.searchResultsExpanded !== false" class="search-result-list">
                    <a
                      v-for="(r, i) in msg.searchResults"
                      :key="i"
                      :href="r.url"
                      target="_blank"
                      class="search-result-item"
                    >
                      <div class="sr-title">{{ r.title }}</div>
                      <div class="sr-snippet" v-if="r.snippet">{{ r.snippet }}</div>
                      <div class="sr-url">{{ r.url }}</div>
                    </a>
                  </div>
                </div>
                <div v-if="msg.learningAnalysis" class="learning-analysis-block">
                  <div class="learning-analysis-title"><el-icon><DataAnalysis /></el-icon>个人学情证据</div>
                  <div>{{ learningCoverageText(msg.learningAnalysis) }}</div>
                </div>
                <div v-if="msg.memoryUpdates && msg.memoryUpdates.length" class="memory-update-block">
                  <div class="memory-update-title">记忆账本 · 本轮已同步</div>
                  <span v-for="event in msg.memoryUpdates" :key="`${event.id}-${event.action}`">
                    {{ event.message }}
                  </span>
                </div>
                <div v-if="msg.mindMap && (msg.mindMap.svg || msg.mindMap.root)" class="mind-map-block">
                  <div class="mind-map-title"><el-icon><Share /></el-icon>{{ msg.mindMap.title || '思维导图' }}</div>
                  <button
                    v-if="msg.mindMap.svg"
                    class="mind-map-canvas"
                    type="button"
                    title="点击放大思维导图"
                    @click="openMindMap(msg.mindMap)"
                    v-html="msg.mindMap.svg"
                  ></button>
                  <div v-else class="mind-map-legacy">这是旧版文本导图；重新生成后将保存为可放大的图形。</div>
                </div>
                <!-- 正式回答 -->
                <div class="msg-content" v-html="renderMarkdown(msg.answer || msg.content)"></div>
                <!-- 复制消息按钮 -->
                <button
                  class="copy-msg-btn"
                  :title="msg.role === 'user' ? '复制消息' : '复制回答'"
                  @click="copyMessage(msg)"
                >
                  <el-icon :size="14"><DocumentCopy /></el-icon>
                </button>
                <div v-if="msg.role === 'assistant' && (msg.answer || msg.content) && currentQaId && idx === messages.length - 1" class="feedback-btns">
                  <el-button size="small" text :type="feedbackGiven ? 'primary' : ''" @click="giveFeedback(1)" :disabled="feedbackGiven">
                    <el-icon><Check /></el-icon> 有用
                  </el-button>
                  <el-button size="small" text @click="giveFeedback(-1)" :disabled="feedbackGiven">
                    <el-icon><Close /></el-icon> 无用
                  </el-button>
                </div>
              </div>
            </div>
          </div>
          <div class="chat-input">
            <div v-if="uploadedFile" class="file-tag">
              <el-tag type="info" closable @close="removeFile" size="small">
                <el-icon><Document /></el-icon>
                {{ uploadedFile.name }} <span v-if="uploading">(解析中...)</span><span v-else>({{ fileType }})</span>
              </el-tag>
            </div>
            <textarea
              v-model="inputText"
              rows="2"
              placeholder="给 AI 导师发送消息"
              @keydown.enter.exact.prevent="sendMessage"
            ></textarea>
            <div class="composer-toolbar">
              <div class="composer-left">
                <el-tooltip content="上传文件" placement="top">
                  <button class="round-tool" aria-label="上传文件" @click="triggerUpload"><el-icon><Paperclip /></el-icon></button>
                </el-tooltip>
                <el-popover placement="top-start" :width="240" trigger="click" popper-class="qa-tool-popover">
                  <template #reference><button class="round-tool" aria-label="更多能力"><el-icon><Operation /></el-icon></button></template>
                  <div class="capability-menu">
                    <button @click="useRag = !useRag"><el-icon><Collection /></el-icon><span><b>课程知识库</b><small>{{ useRag ? '允许 AI 按需调用' : '已禁止' }}</small></span><em :class="{ on: useRag }"></em></button>
                    <button @click="enableLearningAnalytics = !enableLearningAnalytics"><el-icon><DataAnalysis /></el-icon><span><b>个人学情分析</b><small>{{ enableLearningAnalytics ? '允许 AI 只读查询' : '已禁止' }}</small></span><em :class="{ on: enableLearningAnalytics }"></em></button>
                    <button @click="enableMindMap = !enableMindMap"><el-icon><Share /></el-icon><span><b>思维导图</b><small>{{ enableMindMap ? '允许 AI 按需生成' : '已禁止' }}</small></span><em :class="{ on: enableMindMap }"></em></button>
                  </div>
                </el-popover>
                <button :class="['mode-chip', { active: deepThinking }]" @click="deepThinking = !deepThinking"><el-icon><View /></el-icon>深度思考</button>
                <button :class="['mode-chip', { active: enableSearch }]" title="允许 AI 在确有必要时调用 Tavily 高级搜索" @click="enableSearch = !enableSearch"><el-icon><Search /></el-icon>Tavily 搜索</button>
              </div>
              <button v-if="!sending" class="send-button" :disabled="!inputText.trim() && !uploadedFile" aria-label="发送" @click="sendMessage"><el-icon><Promotion /></el-icon></button>
              <button v-else class="send-button stop" aria-label="停止生成" @click="stopStreaming"><el-icon><CircleClose /></el-icon></button>
            </div>
            <input ref="fileInput" type="file" @change="handleFileSelect" class="hidden-file-input"
              accept=".pdf,.pptx,.docx,.xlsx,.png,.jpg,.jpeg,.gif,.bmp,.webp,.txt,.md,.py,.js,.ts,.json,.csv,.html,.css,.xml,.java,.c,.cpp,.sql" />
          </div>
        </el-card>
      </div>
    </div>
    <el-dialog
      v-model="mindMapDialogVisible"
      :title="activeMindMap?.title || '思维导图'"
      width="94vw"
      class="mind-map-dialog"
      append-to-body
    >
      <div class="mind-map-dialog-canvas" v-html="activeMindMap?.svg || ''"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { askQuestionStream, saveQA, saveUserMessage, saveAssistantMessage, uploadFile, submitFeedback, startConversation, getCurrentConversation, getConversations, getConversation, deleteConversation, downloadConversationExport } from '../api/qa'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { recordStudyVisit } from '../api/learning'
import { copyToClipboard } from '../utils/clipboard'

// ═══════════════════════════════════════════════════════════
// 模块级缓存（跨组件挂载/卸载保持，避免重复请求）
// ═══════════════════════════════════════════════════════════
let _cachedConversations = null       // 缓存的对话列表
let _cachedConversationsAt = 0        // 缓存时间戳
const CONVERSATION_CACHE_TTL = 15_000 // 15 秒内不重复请求

// ═══════════════════════════════════════════════════════════
// 模块级持久流式状态（组件挂载/卸载不会中断 AI 生成）
// ═══════════════════════════════════════════════════════════
const _activeStreams = new Map() // conversationId -> { abort: Function, sending: boolean }

function _registerStream(convId, abortFn) {
  _abortStreamForConv(convId)
  _activeStreams.set(convId, { abort: abortFn, sending: true })
}

function _abortStreamForConv(convId) {
  const s = _activeStreams.get(convId)
  if (s) {
    try { s.abort() } catch (_) {}
    s.sending = false
    _activeStreams.delete(convId)
  }
}

function _isConversationStreaming(convId) {
  const s = _activeStreams.get(convId)
  return !!(s && s.sending)
}

function _finishStream(convId) {
  const s = _activeStreams.get(convId)
  if (s) { s.sending = false; _activeStreams.delete(convId) }
}

// sessionStorage 备份键（模块级，不依赖组件实例，每个对话独立备份）
const STREAM_BACKUP_PREFIX = 'qa_stream_backup_'

function _backupKey(convId) {
  return STREAM_BACKUP_PREFIX + (convId || 'unknown')
}

function _saveBackup(convId, data) {
  try { sessionStorage.setItem(_backupKey(convId), JSON.stringify({ conversationId: convId, ...data, timestamp: Date.now() })) } catch (_) {}
}

function _loadBackup(convId) {
  try {
    const raw = sessionStorage.getItem(_backupKey(convId))
    if (!raw) return null
    const b = JSON.parse(raw)
    if (Date.now() - b.timestamp > 5 * 60 * 1000) {
      sessionStorage.removeItem(_backupKey(convId))
      return null
    }
    return b
  } catch (_) { return null }
}

function _clearBackup(convId) {
  try { sessionStorage.removeItem(_backupKey(convId)) } catch (_) {}
}

// 带缓存的对话列表获取（避免每次挂载/切换都发请求）
async function _fetchConversations(force = false) {
  if (!force && _cachedConversations && (Date.now() - _cachedConversationsAt) < CONVERSATION_CACHE_TTL) {
    return _cachedConversations
  }
  try {
    const list = await getConversations()
    _cachedConversations = list
    _cachedConversationsAt = Date.now()
    return list
  } catch (_) {
    return _cachedConversations || []
  }
}

function _invalidateConversationCache() {
  _cachedConversationsAt = 0
}

const router = useRouter()

const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const questionType = ref('text')
const explanationLevel = ref('standard')
const deepThinking = ref(true)
const enableSearch = ref(true)
const useRag = ref(true)
const enableLearningAnalytics = ref(true)
const enableMindMap = ref(true)
const exportingData = ref(false)
const conversations = ref([])
const historyCollapsed = ref(localStorage.getItem('qa_history_collapsed') === 'true')
const chatBox = ref(null)
const abortStream = ref(null)
const fileInput = ref(null)
const uploadedFile = ref(null)
const fileText = ref('')
const fileBase64 = ref(null)
const fileType = ref('')
const creatingConversation = ref(false)
const uploading = ref(false)
const currentQaId = ref(null)
const feedbackGiven = ref(false)
const searchResultsData = ref(null)
const searchQuery = ref('')
const ragSourcesData = ref(null)
const ragUnavailableMsg = ref('')
const searchUnavailableMsg = ref('')
const toolEventsData = ref([])
const mindMapData = ref(null)
const memoryUpdatesData = ref([])
const mindMapDialogVisible = ref(false)
const activeMindMap = ref(null)
const learningAnalysisData = ref(null)

function openMindMap(map) {
  if (!map?.svg) return
  activeMindMap.value = map
  mindMapDialogVisible.value = true
}
const conversationId = ref(null)
const loadingMore = ref(false)
const hasMoreMessages = ref(false)
const totalMessageCount = ref(0)          // 会话中消息总数（后端返回）
const loadedMessageOffset = ref(0)        // 已加载的消息偏移量

const MSG_BATCH_SIZE = 20                 // 每次加载消息的批次大小

const quickQuestions = [
  '你对我有什么认识？',
  'AI智能体和大模型有什么区别？',
  '什么是思维链(Chain-of-Thought)提示？',
  'Agent的工具调用(Tool Use)是如何工作的？',
  '多智能体系统如何解决冲突？',
  'LangChain框架的核心组件有哪些？'
]

const TOOL_NAMES = {
  web_search: 'Tavily 搜索',
  knowledge_search: '课程知识库',
  analyze_learning_data: '学情分析',
  generate_mind_map: '思维导图'
}

function toolDisplayName(name) {
  return TOOL_NAMES[name] || name || '未知工具'
}

function toolStatusLabel(status) {
  return status === 'ok' ? '完成' : (status === 'unavailable' ? '暂不可用' : '失败')
}

function learningCoverageText(analysis) {
  const snapshot = analysis?.snapshot || {}
  const labels = {
    limited: '当前正式测评样本较少，以下结论仅作阶段性观察。',
    partial: '当前已有部分学习证据，结论仍需更多练习验证。',
    sufficient: '当前已有多来源学习证据，可用于趋势分析。'
  }
  return snapshot.coverage_note || labels[snapshot.coverage] || '已完成当前用户的只读学情查询。'
}

async function exportTrainingData() {
  exportingData.value = true
  try {
    await downloadConversationExport()
    ElMessage.success('训练数据已导出，API Key 和常见隐私字段已自动脱敏')
  } catch (error) {
    ElMessage.error(error.message || '导出失败')
  } finally {
    exportingData.value = false
  }
}

onMounted(async () => {
  recordStudyVisit()

  try {
    const conversation = await getCurrentConversation()
    conversationId.value = conversation?.id || null

    // ① 侧边栏对话列表：从统一响应中提取（与消息在同一请求中返回，零额外延迟）
    const convList = conversation?._conversations
    if (Array.isArray(convList) && convList.length) {
      conversations.value = sortConversations(convList)
      // 预热缓存，后续 _fetchConversations 调用走缓存
      _cachedConversations = convList
      _cachedConversationsAt = Date.now()
    } else {
      // 降级：单独加载对话列表
      _fetchConversations().then(list => {
        conversations.value = sortConversations(list)
      }).catch(() => {})
    }

    // ② 当前对话消息
    const initialMsgs = Array.isArray(conversation?.messages) ? conversation.messages : []
    messages.value = _restoreMessages(initialMsgs)
    loadedMessageOffset.value = initialMsgs.length
    hasMoreMessages.value = initialMsgs.length >= 10

    // 恢复流式备份：如果该会话仍有活跃的流式响应，恢复已收到的内容
    const streamBackup = _loadBackup(conversationId.value)
    if (streamBackup && streamBackup.conversationId === conversationId.value) {
      const lastMsg = messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
      if (lastMsg && lastMsg.role === 'assistant' && (!lastMsg.content || lastMsg.content === '') && (!lastMsg.answer || lastMsg.answer === '')) {
        const backupMsg = streamBackup.message
        if (backupMsg.thinking || backupMsg.answer || backupMsg.ragSources || backupMsg.searchResults || backupMsg.toolEvents || backupMsg.mindMap || backupMsg.memoryUpdates) {
          messages.value[messages.value.length - 1] = {
            role: 'assistant',
            content: backupMsg.content || '',
            thinking: backupMsg.thinking || undefined,
            answer: backupMsg.answer || undefined,
            thinkingExpanded: backupMsg.thinkingExpanded !== false,
            learningContext: backupMsg.learningContext || undefined,
            ragSources: backupMsg.ragSources || undefined,
            ragUnavailable: backupMsg.ragUnavailable || undefined,
            searchUnavailable: backupMsg.searchUnavailable || undefined,
            toolEvents: backupMsg.toolEvents || undefined,
            mindMap: backupMsg.mindMap || undefined,
            memoryUpdates: backupMsg.memoryUpdates || undefined,
            learningAnalysis: backupMsg.learningAnalysis || undefined,
            searchResults: backupMsg.searchResults || undefined,
            searchQuery: backupMsg.searchQuery || undefined
          }
        }
      }
      // 如果流仍在进行中，恢复 sending 状态和 abort 引用
      if (_isConversationStreaming(conversationId.value)) {
        sending.value = true
        abortStream.value = () => _abortStreamForConv(conversationId.value)
        // 将备份数据应用到最后一个占位消息
        _applyBackupToLastMessage(streamBackup)
      }
    }

    if (messages.value.length > 0) {
      await nextTick()
      scrollToBottom(true)
    }
  } catch(e) {}
})

// 组件卸载时不中断流式响应 — 流在模块级继续运行，切回来时恢复
onBeforeUnmount(() => {
  // 不清除 abortStream — 模块级 _activeStreams 负责管理生命周期
  // 不设置 sending = false — 流可能仍在进行中
})

function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 自定义 marked 渲染器：为代码块添加复制和运行按钮
const SUPPORTED_LANGS = ['python', 'py', 'python3', 'javascript', 'js', 'node', 'c', 'cpp', 'c++', 'cplusplus', 'java']
const mdRenderer = new marked.Renderer()
mdRenderer.code = function(code, infostring) {
  const lang = infostring || 'plaintext'
  const isSupported = SUPPORTED_LANGS.includes(lang.toLowerCase())
  const runBtn = isSupported
    ? `<button class="code-toolbar-btn run-btn" data-action="run" data-lang="${lang}" title="运行代码">
         <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
         运行
       </button>`
    : ''
  return `<div class="code-block-wrapper">
    <div class="code-toolbar">
      <span class="code-lang-tag">${lang}</span>
      <div class="code-toolbar-actions">
        <button class="code-toolbar-btn copy-btn" data-action="copy" title="复制代码">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          复制
        </button>
        ${runBtn}
      </div>
    </div>
    <pre><code class="language-${lang}">${escapeHtml(code)}</code></pre>
  </div>`
}

function fixMarkdownTables(text) {
  // 修復 LLM 生成的表格分隔行列数不匹配问题（如 4 列表头 + 5 列分隔）
  const lines = text.split('\n')
  for (let i = 0; i < lines.length - 1; i++) {
    const header = lines[i].trim()
    const sep = (lines[i + 1] || '').trim()
    if (!header.startsWith('|') || !header.endsWith('|')) continue
    if (!sep.startsWith('|') || !sep.endsWith('|')) continue
    // 分隔行仅含 | - : 和空格
    if (!/^[|\-:\s]+$/.test(sep)) continue
    const headerCols = header.split('|').filter(s => s.trim().length > 0).length
    const sepCols = sep.split('|').filter(s => s.trim().length > 0).length
    if (headerCols > 0 && sepCols > 0 && headerCols !== sepCols) {
      lines[i + 1] = '|' + Array(headerCols).fill('---').join('|') + '|'
    }
    i++ // 跳过分隔行
  }
  return lines.join('\n')
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked(fixMarkdownTables(text), { breaks: true, renderer: mdRenderer })
}

function handleCodeBlockAction(e) {
  const btn = e.target.closest('.code-toolbar-btn')
  if (!btn) return
  const wrapper = btn.closest('.code-block-wrapper')
  const codeEl = wrapper?.querySelector('code')
  const code = codeEl?.textContent || ''
  if (btn.dataset.action === 'copy') {
    copyToClipboard(code).then(ok => {
      ElMessage[ok ? 'success' : 'warning'](ok ? '代码已复制到剪贴板' : '复制失败，请手动复制')
    })
  } else if (btn.dataset.action === 'run') {
    const lang = btn.dataset.lang || 'python'
    sessionStorage.setItem('qa-run-code', code)
    sessionStorage.setItem('qa-run-lang', lang)
    router.push('/code-runner')
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploadedFile.value = file
  uploading.value = true
  try {
    const result = await uploadFile(file)
    fileText.value = result.text
    fileBase64.value = result.base64 || null
    fileType.value = result.file_type
    ElMessage.success(`${result.file_type} 解析完成`)
  } catch (err) {
    ElMessage.error(err.message || '文件解析失败')
    uploadedFile.value = null
  } finally {
    uploading.value = false
    // 重置input，允许重复选择同一文件
    if (fileInput.value) fileInput.value.value = ''
  }
}

function removeFile() {
  uploadedFile.value = null
  fileText.value = ''
  fileBase64.value = null
  fileType.value = ''
}

async function newConversation() {
  // 防止并发重复创建（race condition）
  if (creatingConversation.value) return
  // 已在空对话中，不重复新建
  if (messages.value.length === 0) {
    ElMessage.info('您已在最新的对话中')
    return
  }
  creatingConversation.value = true
  try {
    // 有消息时确认后再新建
    try {
      const dialogMsg = sending.value
        ? '当前AI正在生成回答中，新建对话将中断当前回答。确定要新建对话吗？'
        : '确定要新建对话吗？当前对话内容将保留在历史记录中。'
      await ElMessageBox.confirm(
        dialogMsg,
        '新建对话',
        { type: 'warning', confirmButtonText: '新建', cancelButtonText: '取消' }
      )
    } catch (_) {
      return  // 用户取消
    }
    messages.value = []
    currentQaId.value = null
    feedbackGiven.value = false
    removeFile()
    try {
      const conversation = await startConversation()
      conversationId.value = conversation?.id || null
      conversations.value = sortConversations(await _fetchConversations(true))
    } catch (_) {
      conversationId.value = null
    }
  } finally {
    creatingConversation.value = false
  }
}

function sortConversations(list) {
  if (!Array.isArray(list)) return []
  return list.sort((a, b) => {
    const aTime = a.last_active_at || a.created_at || ''
    const bTime = b.last_active_at || b.created_at || ''
    if (aTime !== bTime) return bTime.localeCompare(aTime)
    return (b.id || 0) - (a.id || 0)
  })
}

async function loadEarlierMessages() {
  if (loadingMore.value || !conversationId.value) return
  loadingMore.value = true
  const prevScrollHeight = chatBox.value?.scrollHeight || 0
  try {
    const newOffset = loadedMessageOffset.value + MSG_BATCH_SIZE
    const conversation = await getConversation(conversationId.value, {
      msg_limit: MSG_BATCH_SIZE,
      msg_offset: newOffset
    })
    const olderMsgs = _restoreMessages(Array.isArray(conversation?.messages) ? conversation.messages : [])
    if (olderMsgs.length > 0) {
      // 去重：只保留不重复的消息
      const existingIds = new Set(messages.value.map(m => m.content + m.role))
      const uniqueOlder = olderMsgs.filter(m => !existingIds.has((m.content || m.answer || '') + m.role))
      if (uniqueOlder.length > 0) {
        messages.value = [...uniqueOlder, ...messages.value]
        loadedMessageOffset.value = newOffset
      } else {
        // 去重后无新消息，说明已全部加载
        hasMoreMessages.value = false
      }
      // 更新 hasMore 状态
      if (olderMsgs.length < MSG_BATCH_SIZE) {
        hasMoreMessages.value = false
      }
    } else {
      hasMoreMessages.value = false
    }
    // 恢复滚动位置（新内容在顶部）
    await nextTick()
    if (chatBox.value) {
      chatBox.value.scrollTop = chatBox.value.scrollHeight - prevScrollHeight
    }
  } catch (_) {
    // 加载失败静默处理
  } finally {
    loadingMore.value = false
  }
}

// 聊天框滚动检测（用户滚动到顶部时自动加载更早消息）
function onChatScroll() {
  if (!chatBox.value || !hasMoreMessages.value || loadingMore.value) return
  if (chatBox.value.scrollTop < 50) {
    loadEarlierMessages()
  }
}

function toggleHistory() {
  historyCollapsed.value = !historyCollapsed.value
  localStorage.setItem('qa_history_collapsed', String(historyCollapsed.value))
}

async function openConversation(id) {
  if (id === conversationId.value) return
  // 允许在流式生成中切换对话 — 旧对话的流继续在后台运行
  const isStreaming = _isConversationStreaming(id)
  try {
    const conversation = await getConversation(id)
    conversationId.value = conversation?.id || id
    // 优先使用流式备份恢复（流式进行中的对话后端尚未保存）
    const backup = _loadBackup(id)
    if (isStreaming && backup && backup.conversationId === id) {
      // 流式进行中：用后端数据初始化基础消息，再用备份恢复最后一条
      const baseMsgs = _restoreMessages(Array.isArray(conversation?.messages) ? conversation.messages : [])
      const bm = backup.message
      // 构建最后一条助手消息（包含思考过程、RAG源、搜索结果等）
      const streamMsg = {
        role: 'assistant',
        content: bm.content || '',
        thinking: bm.thinking || undefined,
        answer: bm.answer || undefined,
        thinkingExpanded: bm.thinkingExpanded !== false,
        learningContext: bm.learningContext || undefined,
        ragSources: bm.ragSources || undefined,
        ragUnavailable: bm.ragUnavailable || undefined,
        searchUnavailable: bm.searchUnavailable || undefined,
        toolEvents: bm.toolEvents || undefined,
        mindMap: bm.mindMap || undefined,
        memoryUpdates: bm.memoryUpdates || undefined,
        learningAnalysis: bm.learningAnalysis || undefined,
        searchResults: bm.searchResults || undefined,
        searchQuery: bm.searchQuery || undefined
      }
      // 如果后端已保存该消息，替换；否则追加
      if (baseMsgs.length > 0 && baseMsgs[baseMsgs.length - 1].role === 'assistant') {
        baseMsgs[baseMsgs.length - 1] = streamMsg
      } else {
        baseMsgs.push(streamMsg)
      }
      messages.value = baseMsgs
    } else {
      messages.value = _restoreMessages(Array.isArray(conversation?.messages) ? conversation.messages : [])
    }
    // 跟踪消息加载状态：判断是否还有更早的消息
    loadedMessageOffset.value = (Array.isArray(conversation?.messages) ? conversation.messages.length : 0)
    hasMoreMessages.value = loadedMessageOffset.value >= 25 // 如果刚好满一批，可能还有更多
    currentQaId.value = null
    feedbackGiven.value = false
    if (isStreaming) {
      sending.value = true
      abortStream.value = () => _abortStreamForConv(id)
    } else {
      sending.value = false
      abortStream.value = null
    }
    await nextTick()
    if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
  } catch (_) {
    ElMessage.error('会话加载失败')
  }
}

async function removeConversation(id) {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个对话吗？删除后不可恢复。',
      '删除对话',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteConversation(id)
    conversations.value = conversations.value.filter(item => item.id !== id)
    if (conversationId.value === id) await newConversation()
    ElMessage.success('会话已删除')
  } catch (err) {
    if (err !== 'cancel' && err?.action !== 'cancel') {
      ElMessage.error('会话删除失败')
    }
  }
}

async function giveFeedback(rating) {
  if (!currentQaId.value || feedbackGiven.value) return
  try {
    await submitFeedback({ qa_history_id: currentQaId.value, rating })
    feedbackGiven.value = true
    ElMessage.success(rating === 1 ? '感谢反馈！已记录为有用回答' : '感谢反馈！我们会持续改进')
  } catch (err) {
    ElMessage.error('反馈提交失败')
  }
}

async function sendMessage() {
  const hasFile = fileText.value && uploadedFile.value
  if ((!inputText.value.trim() && !hasFile) || sending.value) return
  const q = inputText.value.trim() || (hasFile ? `请提取以下文件的核心要点` : '')
  const isFileOnly = hasFile && !inputText.value.trim()
  let activeLearningContext = null

  // 用户消息仅显示文件信息，不展示文件内容
  let displayContent
  if (hasFile) {
    displayContent = `📎 **${uploadedFile.value.name}** (${fileType.value})`
    if (q && !isFileOnly) displayContent += `\n\n${q}`
  } else {
    displayContent = q
  }
  messages.value.push({ role: 'user', content: displayContent })
  inputText.value = ''
  sending.value = true

  // 添加空的助手消息占位，流式填充内容
  messages.value.push({ role: 'assistant', content: '' })
  const assistantIdx = messages.value.length - 1
  const thisConvId = conversationId.value // 捕获当前会话 ID（流式结束前不会变）

  // ⚡ 立即保存用户消息到数据库，防止刷新丢失
  saveUserMessage({
    question: q,
    conversation_id: thisConvId,
    question_type: questionType.value,
    explanation_level: explanationLevel.value,
  }).then((res) => {
    if (res && res.conversation_id) {
      conversationId.value = res.conversation_id
      if (res.conversation_id !== thisConvId) {
        // 新建会话：刷新侧边栏
        _fetchConversations(true).then(list => { conversations.value = sortConversations(list) }).catch(() => {})
      }
    }
    if (res?.memory_updates?.length) {
      memoryUpdatesData.value = res.memory_updates
      _applyToLastAssistant({ memoryUpdates: res.memory_updates })
      _saveBackup(thisConvId, {
        message: { ...(messages.value[assistantIdx] || {}), memoryUpdates: res.memory_updates }
      })
    }
  }).catch((err) => {
    console.error('[QA] 保存用户消息失败:', err)
  })

  const scrollToBottom = (force = false) => {
    nextTick(() => {
      if (!chatBox.value) return
      const el = chatBox.value
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      if (force || distanceFromBottom < 100) {
        el.scrollTop = el.scrollHeight
      }
    })
  }
  scrollToBottom(true)

  const file_text_sent = hasFile ? fileText.value : null
  const file_base64_sent = hasFile ? fileBase64.value : null

  // 构建对话历史（不包含当前用户消息和空的助手占位）
  const conversationHistory = messages.value.slice(0, -2).map(m => {
    let content = m.content || m.answer || ''
    if (m.role === 'assistant' && m.thinking && m.answer) {
      content = `【思考过程】\n${m.thinking}\n【回答】\n${m.answer}`
    } else if (m.role === 'assistant' && m.thinking) {
      content = `【思考过程】\n${m.thinking}\n\n${content}`
    }
    return { role: m.role, content }
  })

  searchResultsData.value = null
  searchQuery.value = ''
  ragSourcesData.value = null
  ragUnavailableMsg.value = ''
  searchUnavailableMsg.value = ''
  toolEventsData.value = []
  mindMapData.value = null
  memoryUpdatesData.value = []
  learningAnalysisData.value = null

  // 清除可能残留的流式备份
  _clearBackup(thisConvId)

  // 模块级流在 askQuestionStream 调用后注册（其返回值就是 abort 函数）

  // 工具函数：将备份数据应用到当前最后一条助手消息
  function _applyToLastAssistant(data) {
    const msgs = messages.value
    if (!msgs.length) return
    const last = msgs[msgs.length - 1]
    if (last.role !== 'assistant') return
    // 只在当前会话 ID 匹配时应用
    if (thisConvId && conversationId.value !== thisConvId) return
    msgs[msgs.length - 1] = { ...last, ...data }
  }

  const streamAbort = askQuestionStream(
    {
      question: q,
      question_type: questionType.value,
      explanation_level: explanationLevel.value,
      deep_thinking: deepThinking.value,
      enable_search: enableSearch.value,
      use_rag: useRag.value,
      enable_learning_analytics: enableLearningAnalytics.value,
      enable_mind_map: enableMindMap.value,
      file_text: file_text_sent,
      file_base64: file_base64_sent,
      history: conversationHistory,
      conversation_id: thisConvId
    },
    {
      onLearningContext(context) {
        activeLearningContext = context
        _applyToLastAssistant({ learningContext: context })
        // 保存到模块级备份（跨组件持久）
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), learningContext: context }
        })
      },
      onRagSources(sources) {
        // 暂存 RAG 数据，等思考完成后（检测到【回答】标记）再显示
        ragSourcesData.value = sources
        ragUnavailableMsg.value = ''
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), ragSources: sources, ragUnavailable: null }
        })
      },
      onRagUnavailable(message) {
        // RAG 不可用提示也等思考完成后显示
        ragUnavailableMsg.value = message
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), ragUnavailable: message }
        })
      },
      onSearchUnavailable(message) {
        searchUnavailableMsg.value = message
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), searchUnavailable: message }
        })
      },
      onToolEvents(events) {
        toolEventsData.value = events
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), toolEvents: events }
        })
      },
      onMindMap(mindMap) {
        mindMapData.value = mindMap
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), mindMap }
        })
      },
      onLearningAnalysis(analysis) {
        learningAnalysisData.value = analysis
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), learningAnalysis: analysis }
        })
      },
      onSearchResults(results, sq) {
        // 暂存搜索结果，等思考完成后（检测到【回答】标记）再显示
        searchResultsData.value = results
        searchQuery.value = sq
        _saveBackup(thisConvId, {
          message: { ...(messages.value[assistantIdx] || {}), searchResults: results, searchQuery: sq }
        })
      },
      onChunk(chunkText, fullAnswer, fullReasoning) {
        const msg = _buildAssistantMsg(fullAnswer, fullReasoning)
        if (activeLearningContext) msg.learningContext = activeLearningContext
        // 只在思考完成后（answer 开始生成）才显示 RAG 来源和搜索结果
        // 实现顺序：深度思考过程 → 参考知识库/联网搜索 → 正式回答
        if (msg.answer) {
          if (ragUnavailableMsg.value) msg.ragUnavailable = ragUnavailableMsg.value
          if (searchUnavailableMsg.value) msg.searchUnavailable = searchUnavailableMsg.value
          if (toolEventsData.value.length) msg.toolEvents = toolEventsData.value
          if (mindMapData.value) msg.mindMap = mindMapData.value
          if (learningAnalysisData.value) msg.learningAnalysis = learningAnalysisData.value
          if (memoryUpdatesData.value.length) msg.memoryUpdates = memoryUpdatesData.value
          if (ragSourcesData.value) {
            msg.ragSources = ragSourcesData.value
            msg.ragSourcesExpanded = true
            msg._selectedSourceIndex = -1
          }
          if (searchResultsData.value) {
            msg.searchResults = searchResultsData.value
            msg.searchQuery = searchQuery.value
            msg.searchResultsExpanded = true
          }
        }
        // 只在当前查看的会话匹配时才更新 UI
        if (conversationId.value === thisConvId) {
          messages.value[assistantIdx] = msg
        }
        // 始终保存到模块级备份（即使切到其他页面也能恢复）
        _saveBackup(thisConvId, {
          message: msg
        })
        // 不再强制滚动 — 用户可自由翻阅
      },
      onDone(fullAnswer, fullReasoning) {
        const msg = _buildAssistantMsg(fullAnswer, fullReasoning)
        if (activeLearningContext) msg.learningContext = activeLearningContext
        if (ragUnavailableMsg.value) msg.ragUnavailable = ragUnavailableMsg.value
        if (searchUnavailableMsg.value) msg.searchUnavailable = searchUnavailableMsg.value
        if (toolEventsData.value.length) msg.toolEvents = toolEventsData.value
        if (mindMapData.value) msg.mindMap = mindMapData.value
        if (learningAnalysisData.value) msg.learningAnalysis = learningAnalysisData.value
        if (memoryUpdatesData.value.length) msg.memoryUpdates = memoryUpdatesData.value
        if (ragSourcesData.value) {
          msg.ragSources = ragSourcesData.value
          msg.ragSourcesExpanded = false
          msg._selectedSourceIndex = -1
        }
        if (searchResultsData.value) {
          msg.searchResults = searchResultsData.value
          msg.searchQuery = searchQuery.value
          msg.searchResultsExpanded = false
        }
        if (conversationId.value === thisConvId) {
          messages.value[assistantIdx] = msg
          sending.value = false
          abortStream.value = null
          scrollToBottom(true)
        }
        _finishStream(thisConvId)
        _clearBackup(thisConvId)
        if (hasFile) removeFile()
        feedbackGiven.value = false
        // 保存助手回答到后端（用户消息已在 sendMessage 开始时保存）
        let answerToSave = fullAnswer
        if (fullReasoning && !fullAnswer.includes('【思考过程】')) {
          answerToSave = `【思考过程】\n${fullReasoning}\n【回答】\n${fullAnswer}`
        }
        const actualConvId = conversationId.value || thisConvId
        saveAssistantMessage({
          question: q,
          answer: answerToSave,
          question_type: questionType.value,
          explanation_level: explanationLevel.value,
          conversation_id: actualConvId,
          rag_sources: ragSourcesData.value,
          search_results: searchResultsData.value,
          search_query: searchQuery.value,
          tool_events: toolEventsData.value,
          mind_map: mindMapData.value,
          learning_analysis: learningAnalysisData.value,
          memory_updates: memoryUpdatesData.value
        }).then((result) => {
          if (result && result.conversation_id) conversationId.value = result.conversation_id
          _fetchConversations(true).then(res => { conversations.value = sortConversations(res) }).catch(() => {})
        }).catch((err) => {
          console.error('[QA] 保存助手回答失败:', err)
          // 降级：使用旧 saveQA 作为兜底
          saveQA({
            question: q,
            answer: answerToSave,
            question_type: questionType.value,
            explanation_level: explanationLevel.value,
            conversation_id: actualConvId,
            rag_sources: ragSourcesData.value,
            search_results: searchResultsData.value,
            search_query: searchQuery.value,
            tool_events: toolEventsData.value,
            mind_map: mindMapData.value,
            learning_analysis: learningAnalysisData.value,
            memory_updates: memoryUpdatesData.value
          }).then((res2) => {
            if (res2 && res2.id) currentQaId.value = res2.id
            if (res2 && res2.conversation_id) conversationId.value = res2.conversation_id
            _fetchConversations(true).then(res3 => { conversations.value = sortConversations(res3) }).catch(() => {})
          }).catch((err2) => {
            console.error('[QA] 兜底保存也失败:', err2)
          })
        })
      },
      onError(err) {
        if (conversationId.value === thisConvId) {
          messages.value[assistantIdx] = { role: 'assistant', content: `❌ **出错了**: ${err.message}` }
          sending.value = false
          abortStream.value = null
        }
        _finishStream(thisConvId)
        _clearBackup(thisConvId)
        ElMessage.error(err.message || '流式请求失败')
      }
    }
  )
  // 注册模块级流 — askQuestionStream 返回的是 abort 函数
  // 即使组件卸载、用户切到其他页面，AI 也在后台继续生成
  _registerStream(thisConvId, streamAbort)
  abortStream.value = streamAbort
}

function _buildAssistantMsg(fullText, nativeReasoning) {
  if (deepThinking.value) {
    // 策略1：DeepSeek 原生 reasoning_content — 推理在 native 字段，正文在 content
    if (nativeReasoning) {
      // 从 answer 文本中剥离【思考过程】/【回答】标记，避免双重显示
      let answerText = fullText || ''
      const answerMarker = answerText.indexOf('【回答】')
      if (answerMarker >= 0) {
        answerText = answerText.substring(answerMarker + '【回答】'.length).trim()
      } else {
        answerText = answerText.replace(/【思考过程】[\s\S]*$/g, '').trim()
      }
      return {
        role: 'assistant',
        thinking: nativeReasoning,
        answer: answerText,
        thinkingExpanded: true
      }
    }

    // 提取内容的辅助函数：在 marker 处切割，支持 XML 和中文两种格式
    const _splitAt = (text, marker) => {
      const idx = text.indexOf(marker)
      if (idx < 0) return null
      return { before: text.substring(0, idx), after: text.substring(idx + marker.length).trim() }
    }

    // 策略2a：XML 格式 <thinking>...</thinking><answer>...</answer>
    const xmlSplit = _splitAt(fullText, '</thinking>')
    if (xmlSplit) {
      const thinkingRaw = xmlSplit.before.replace(/<thinking>\s*/gi, '').trim()
      const answerPart = xmlSplit.after.replace(/<answer>\s*/gi, '').replace(/<\/answer>\s*/gi, '').trim()
      if (thinkingRaw || answerPart) {
        return {
          role: 'assistant',
          thinking: thinkingRaw || '（思考中…）',
          answer: answerPart,
          thinkingExpanded: true
        }
      }
    }

    // 策略2b：中文格式 【思考过程】...【回答】...
    const answerIdx = fullText.indexOf('【回答】')
    if (answerIdx >= 0) {
      const thinkingRaw = fullText.substring(0, answerIdx)
      const answer = fullText.substring(answerIdx + '【回答】'.length).trim()
      const thinking = thinkingRaw.replace(/【思考过程】\s*/g, '').trim()
      return {
        role: 'assistant',
        thinking: thinking || '（思考中…）',
        answer: answer || '（生成中…）',
        thinkingExpanded: true
      }
    }

    // 策略3：有思考标记但没回答标记 → 正在流式输出思考过程，始终作为 thinking 显示
    const hasXmlThinking = fullText.includes('<thinking>')
    const hasCnThinking = fullText.includes('【思考过程】')
    if (hasXmlThinking || hasCnThinking) {
      const thinking = fullText.replace(/<thinking>\s*/gi, '').replace(/【思考过程】\s*/g, '').trim()
      return { role: 'assistant', thinking, answer: '', thinkingExpanded: true }
    }
  }
  return { role: 'assistant', content: fullText }
}

function stopStreaming() {
  if (conversationId.value) {
    _abortStreamForConv(conversationId.value)
  }
  abortStream.value = null
  sending.value = false
  _clearBackup(conversationId.value)
}

async function copyMessage(msg) {
  // 提取纯文本：优先用 answer/content，对于用户消息直接用 content
  const text = msg.answer || msg.content || ''
  if (!text.trim()) {
    ElMessage.warning('没有可复制的内容')
    return
  }
  // 去除 markdown 格式标记，复制纯文本
  const plainText = text
    .replace(/[*#~`>|]/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  const ok = await copyToClipboard(plainText)
  ElMessage[ok ? 'success' : 'warning'](ok ? '已复制到剪贴板' : '复制失败，请手动复制')
}

// ── 流式备份辅助 ─────────────────────────────────────────────
// _saveBackup / _loadBackup / _clearBackup 已在模块级定义
// 将备份数据应用到当前最后一条助手消息
function _applyBackupToLastMessage(backup) {
  if (!backup || !backup.message) return
  const msgs = messages.value
  if (!msgs.length) return
  const last = msgs[msgs.length - 1]
  if (last.role !== 'assistant') return
  const bm = backup.message
  msgs[msgs.length - 1] = {
    role: 'assistant',
    content: bm.content || '',
    thinking: bm.thinking || undefined,
    answer: bm.answer || undefined,
    thinkingExpanded: bm.thinkingExpanded !== false,
    learningContext: bm.learningContext || undefined,
    ragSources: bm.ragSources || undefined,
    ragUnavailable: bm.ragUnavailable || undefined,
    searchUnavailable: bm.searchUnavailable || undefined,
    toolEvents: bm.toolEvents || undefined,
    mindMap: bm.mindMap || undefined,
    memoryUpdates: bm.memoryUpdates || undefined,
    learningAnalysis: bm.learningAnalysis || undefined,
    searchResults: bm.searchResults || undefined,
    searchQuery: bm.searchQuery || undefined
  }
}

function quickAsk(q) {
  inputText.value = q
  sendMessage()
}

// 恢复从后端加载的消息：解析【思考过程】...【回答】...，恢复 metadata
function _restoreMessages(rawMessages) {
  if (!Array.isArray(rawMessages)) return []
  return rawMessages.map(m => {
    if (m.role !== 'assistant') return m
    const restored = { ...m }
    const content = m.content || ''

    const restoreSplit = (text) => {
      // XML 格式
      const xmlIdx = text.indexOf('</thinking>')
      if (xmlIdx >= 0) {
        const thinkingRaw = text.substring(0, xmlIdx).replace(/<thinking>\s*/gi, '').trim()
        const answerText = text.substring(xmlIdx + '</thinking>'.length).replace(/<answer>\s*/gi, '').replace(/<\/answer>\s*/gi, '').trim()
        return { thinking: thinkingRaw, answer: answerText }
      }
      // 中文格式
      const answerIdx = text.indexOf('【回答】')
      if (answerIdx >= 0) {
        const thinkingText = text.substring(0, answerIdx).replace(/【思考过程】\s*/g, '').trim()
        const answerText = text.substring(answerIdx + '【回答】'.length).trim()
        return { thinking: thinkingText, answer: answerText }
      }
      // 只有思考标记
      if (text.includes('<thinking>') || text.includes('【思考过程】')) {
        const thinkingText = text.replace(/<thinking>\s*/gi, '').replace(/【思考过程】\s*/g, '').trim()
        if (thinkingText && thinkingText.length <= 500) {
          return { thinking: thinkingText, answer: '' }
        }
      }
      return null
    }

    const split = restoreSplit(content)
    if (split) {
      if (split.thinking) {
        restored.thinking = split.thinking
        restored.thinkingExpanded = false
      }
      restored.answer = split.answer
      delete restored.content
    }
    // 恢复 RAG 来源（现在直接从后端 metadata 返回）
    if (m.rag_sources && Array.isArray(m.rag_sources) && m.rag_sources.length) {
      restored.ragSources = m.rag_sources
      restored.ragSourcesExpanded = false  // 加载后默认折叠
      restored._selectedSourceIndex = -1
    }
    // 恢复联网搜索结果
    if (m.search_results && Array.isArray(m.search_results) && m.search_results.length) {
      restored.searchResults = m.search_results
      restored.searchQuery = m.search_query || ''
      restored.searchResultsExpanded = false  // 加载后默认折叠
    }
    if (m.tool_events && Array.isArray(m.tool_events)) restored.toolEvents = m.tool_events
    if (m.mind_map) restored.mindMap = m.mind_map
    if (m.memory_updates) restored.memoryUpdates = m.memory_updates
    if (m.learning_analysis) restored.learningAnalysis = m.learning_analysis
    return restored
  })
}

function openContextLab(context) {
  if (!context?.lab_id) return
  router.push(`/code-lab/${String(context.lab_id).split('-')[0]}/${context.lab_id}`)
}

</script>

<style scoped>
.qa-page { height: 100%; min-height: 0; overflow: hidden; }
.qa-layout { display: flex; gap: 16px; height: 100%; }
.chat-column { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.history-column { width: 260px; flex-shrink: 0; }

.page-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: bold; }

/* 聊天卡片：flex布局，input固定在底部 */
.chat-card { height: 100%; display: flex; flex-direction: column; }
.chat-card :deep(.el-card__header) { flex-shrink: 0; }
.chat-card :deep(.el-card__body) { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.chat-messages { flex: 1; overflow-y: auto; padding: 8px 0; }
.chat-input { flex-shrink: 0; border-top: 1px solid #f0f0f0; padding-top: 10px; margin-top: 8px; }

/* 历史卡片：固定不滚动 */
.history-card { height: 100%; display: flex; flex-direction: column; }
.history-card :deep(.el-card__header) { flex-shrink: 0; }
.history-card :deep(.el-card__body) { flex: 1; overflow-y: auto; }
.history-list { flex: 1; overflow-y: auto; }

.welcome-msg { text-align: center; padding: 40px 20px; }
.welcome-msg h3 { margin: 12px 0 8px; color: #303133; }
.welcome-msg p { color: #909399; font-size: 14px; margin-bottom: 16px; }
.quick-tag { cursor: pointer; margin: 4px; }
.quick-tag:hover { background: #409EFF; color: #fff; }
.message { display: flex; gap: 10px; padding: 12px 0; border-bottom: 1px solid #f5f5f5; }
.message.user { justify-content: flex-end; }
.message.user .msg-avatar { order: 10; }
.message.user .msg-body { flex: 0 1 auto; }
.message.assistant .msg-content { background: #e6f7ff; border-radius: 0 12px 12px 12px; }
.message.user .msg-content { background: #f0f0f0; border-radius: 12px 0 12px 12px; width: fit-content; }
.msg-content { padding: 12px 16px; max-width: 75%; line-height: 1.7; font-size: 14px; word-break: break-word; -webkit-user-drag: none; user-select: text; }
.msg-content :deep(p) { margin: 4px 0; }
.msg-content :deep(pre) { background: #282c34; color: #abb2bf; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
.msg-content :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.msg-content :deep(pre code) { background: none; padding: 0; }
/* markdown 表格 */
.msg-content :deep(table) { width: 100%; margin: 10px 0; border-collapse: collapse; border: 1px solid #dcdfe6; border-radius: 6px; overflow: hidden; }
.msg-content :deep(th), .msg-content :deep(td) { border: 1px solid #dcdfe6; padding: 8px 14px; text-align: left; font-size: 13px; }
.msg-content :deep(th) { background: #f5f7fa; color: #303133; font-weight: 600; }
.msg-content :deep(tr:nth-child(even)) { background: #fafbfc; }
.msg-content :deep(tr:hover) { background: #f0f4ff; }

/* 代码块工具栏（复制+运行按钮） */
.msg-content :deep(.code-block-wrapper) {
  position: relative;
  margin: 10px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #3a3f4b;
}
.msg-content :deep(.code-toolbar) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #21252b;
  border-bottom: 1px solid #3a3f4b;
  font-size: 12px;
}
.msg-content :deep(.code-lang-tag) {
  color: #abb2bf;
  font-size: 11px;
  font-family: 'Consolas', monospace;
  text-transform: lowercase;
}
.msg-content :deep(.code-toolbar-actions) {
  display: flex;
  gap: 6px;
}
.msg-content :deep(.code-toolbar-btn) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border: 1px solid #555;
  border-radius: 4px;
  background: transparent;
  color: #abb2bf;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1;
}
.msg-content :deep(.code-toolbar-btn:hover) {
  background: #3a3f4b;
  color: #fff;
}
.msg-content :deep(.code-toolbar-btn.copy-btn:hover) {
  border-color: #409EFF;
  color: #409EFF;
}
.msg-content :deep(.code-toolbar-btn.run-btn:hover) {
  border-color: #67C23A;
  color: #67C23A;
}
.msg-content :deep(.code-block-wrapper pre) {
  margin: 0;
  border-radius: 0;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

.feedback-btns { margin-top: 4px; padding-left: 2px; }
.feedback-btns .el-button { font-size: 12px; padding: 2px 8px; }

/* 复制消息按钮 */
.copy-msg-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  margin-top: 4px;
  border: 1px solid #e0e4ea;
  border-radius: 6px;
  background: #fff;
  color: #8b95a8;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
  flex-shrink: 0;
}
.message:hover .copy-msg-btn,
.copy-msg-btn:hover { opacity: 1; }
.copy-msg-btn:hover {
  color: #4657d8;
  border-color: #aab5ed;
  background: #f6f7ff;
}
.message.user .copy-msg-btn { align-self: flex-end; }

/* 隐藏文件输入框（兼容所有浏览器的安全策略） */
.hidden-file-input {
  position: absolute;
  width: 0.1px;
  height: 0.1px;
  opacity: 0;
  overflow: hidden;
  z-index: -1;
}

.input-options { margin-bottom: 8px; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.file-tag { margin-bottom: 6px; }
.send-area { margin-top: 8px; }
.text-input { margin: 8px 0; }
.history-item { padding: 8px 10px; border-bottom: 1px solid #f5f5f5; cursor: pointer; }
.history-item:hover { background: #f5f7fa; }
.h-question { font-size: 12px; color: #303133; line-height: 1.4; }
.h-meta { font-size: 11px; color: #c0c4cc; margin-top: 3px; }

/* 深度思考 */
.msg-body { min-width: 0; }
.message.user .msg-body { display: flex; flex-direction: column; align-items: flex-end; }
.message.assistant .msg-body { flex: 1; }
.thinking-block {
  margin-bottom: 8px;
  border: 1px solid #e8d5a3;
  border-radius: 8px;
  overflow: hidden;
  background: #fffdf5;
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #b8860b;
  font-weight: 500;
  user-select: none;
}
.thinking-header:hover { background: #fff8e1; }
.thinking-tag {
  margin-left: auto;
  font-size: 11px;
  background: #fef3c7;
  color: #b45309;
  padding: 1px 8px;
  border-radius: 10px;
}
.thinking-content {
  padding: 8px 14px 12px;
  font-size: 12px;
  color: #8b7355;
  line-height: 1.7;
  border-top: 1px solid #f0e4c0;
  max-height: 400px;
  overflow-y: auto;
}
.thinking-content :deep(h1),
.thinking-content :deep(h2),
.thinking-content :deep(h3) { font-size: 13px; color: #b8860b; }
.thinking-content :deep(p) { margin: 4px 0; }
.thinking-content :deep(code) { font-size: 11px; background: #fef9e7; color: #b45309; }
.thinking-content :deep(pre) { font-size: 11px; background: #fffbeb; }

/* 联网搜索结果 */
/* RAG 知识库暂不可用 */
.rag-unavailable-block {
  margin-bottom: 10px;
  background: #fef8e7;
  border: 1px solid #f5dab1;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #b88230;
}
/* RAG 知识库来源 */
.rag-sources-block {
  margin-bottom: 10px;
  background: #f0fdf4;
  border: 1px solid #b7e4c7;
  border-radius: 8px;
  overflow: hidden;
}
.rag-sources-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #67C23A;
  background: #e8f8ef;
  cursor: pointer;
  user-select: none;
}
.rag-sources-header:hover { background: #d0f0d8; }
.rag-source-list { padding: 4px 8px 8px; max-height: 240px; overflow-y: auto; }
.rag-source-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  margin: 2px 0;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  cursor: pointer;
  transition: background 0.15s;
}
.rag-source-item:hover { background: #dcedc8; }
.rag-source-item.active { background: #c8e6c9; }
.rag-source-icon { flex-shrink: 0; }
.rag-source-title { font-weight: 500; color: #2e7d32; }
.rag-source-section { color: #909399; }
.rag-source-page { color: #b0b3bb; font-size: 11px; }
.rag-source-expand-icon { margin-left: auto; flex-shrink: 0; color: #8b95a8; }
.rag-source-content {
  border-top: 1px solid #b7e4c7;
  background: #fff;
}
.rag-source-content-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  font-size: 12px; font-weight: 500; color: #2e7d32;
  background: #f0fdf4; border-bottom: 1px solid #dcedc8;
}
.rag-source-content-body {
  padding: 10px 14px; max-height: 260px; overflow-y: auto;
  font-size: 12px; color: #606266; line-height: 1.7;
}
/* 联网搜索结果 */
.search-results-block {
  margin-bottom: 10px;
  background: #f0f7ff;
  border: 1px solid #b3d8ff;
  border-radius: 8px;
  overflow: hidden;
}
.search-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #409EFF;
  background: #e8f3ff;
  cursor: pointer;
  user-select: none;
}
.search-header:hover { background: #d6eaff; }
.search-result-list { padding: 4px 8px 8px; max-height: 300px; overflow-y: auto; }
.search-result-item {
  display: block;
  padding: 8px 10px;
  margin: 4px 0;
  border-radius: 6px;
  text-decoration: none;
  transition: background .15s;
}
.search-result-item:hover { background: #fff; }
.sr-title {
  font-size: 13px;
  font-weight: 500;
  color: #1a66cc;
  margin-bottom: 2px;
}
.sr-snippet {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
  margin-bottom: 2px;
}
.sr-url {
  font-size: 11px;
  color: #67C23A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.learning-context-block {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid #cfd7ff;
  border-radius: 9px;
  color: #4052a5;
  background: #f3f5ff;
  font-size: 12px;
}
.learning-context-block span { min-width: 0; flex: 1; }
.learning-context-block button {
  flex: 0 0 auto;
  padding: 4px 8px;
  border: 1px solid #aebaf5;
  border-radius: 7px;
  color: #4058c5;
  background: #fff;
  font-size: 10px;
  cursor: pointer;
}
.learning-context-block button:hover { border-color: #7186ec; background: #e9edff; }

/* DeepSeek 风格的紧凑对话工作区 */
.qa-page{height:100%!important;min-height:0;overflow:hidden}
.qa-layout{position:relative;display:flex;height:100%;gap:0!important;overflow:hidden;border:0;border-radius:0;background:#fff;box-shadow:none}
.conversation-sidebar{position:relative;width:252px;min-width:252px;display:flex;flex-direction:column;padding:14px 10px 10px;border-right:1px solid #e8ebf1;background:#f7f8fa;transition:width .24s,min-width .24s,padding .24s}
.conversation-sidebar.collapsed{width:48px;min-width:48px;padding:14px 7px}
.conversation-toggle{display:grid;width:34px;height:34px;place-items:center;align-self:flex-end;border:1px solid #dce1e9;border-radius:10px;color:#59667b;background:#fff;cursor:pointer}
.conversation-sidebar.collapsed .conversation-toggle{align-self:center}
.new-chat-button{height:42px;display:flex;align-items:center;justify-content:center;gap:9px;margin-top:14px;border:1px solid #dfe3ea;border-radius:12px;color:#28354c;background:#fff;font-size:13px;font-weight:650;cursor:pointer;box-shadow:0 3px 10px rgba(31,45,79,.04)}
.new-chat-button:hover{border-color:#aab5ed;background:#f6f7ff}
.export-data-button{height:34px;display:flex;align-items:center;justify-content:center;gap:7px;margin-top:8px;border:0;border-radius:10px;color:#657086;background:transparent;font-size:11px;cursor:pointer}
.export-data-button:hover{color:#4058c5;background:#eceffa}.export-data-button:disabled{opacity:.55;cursor:wait}
.conversation-caption{margin:20px 8px 8px;color:#9aa3b2;font-size:10px;font-weight:750;letter-spacing:.08em}
.conversation-list{min-height:0;flex:1;overflow-y:auto}
.conversation-item{width:100%;display:flex;align-items:center;gap:7px;margin:2px 0;padding:9px 8px;border:0;border-radius:9px;color:#344056;background:transparent;text-align:left;cursor:pointer}
.conversation-item:hover,.conversation-item.active{background:#e9ebf1}.conversation-item.active{color:#4052c5}
.conversation-copy{min-width:0;flex:1}.conversation-copy b,.conversation-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.conversation-copy b{font-size:12px}.conversation-copy small{margin-top:4px;color:#9099a8;font-size:9px}
.conversation-delete{opacity:0;color:#9aa2b0}.conversation-item:hover .conversation-delete{opacity:1}.conversation-delete:hover{color:#e05e6b}.conversation-empty{padding:24px 8px;color:#a2aab8;font-size:11px;text-align:center}
.chat-column{min-height:0;flex:1;min-width:0}.chat-card{height:100%;min-height:0;border:0!important;border-radius:0!important;background:#fff}.chat-card :deep(.el-card__body){min-height:0;padding:0!important}
.chat-messages{min-height:0;padding:18px clamp(14px,3vw,44px) 12px!important;overscroll-behavior:contain;scrollbar-gutter:stable}
/* 加载更早消息 */
.load-earlier-bar{display:flex;justify-content:center;padding:8px 0 16px}
.load-earlier-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 16px;border:1px solid #dfe3ea;border-radius:16px;color:#5f6a7c;background:#f7f8fa;font-size:12px;cursor:pointer;transition:all .15s}
.load-earlier-btn:hover:not(:disabled){border-color:#a9b9ff;color:#3f63dc;background:#f0f4ff}
.load-earlier-btn:disabled{opacity:.5;cursor:not-allowed}
.welcome-msg{padding:clamp(55px,11vh,120px) 20px 32px}.welcome-orb{display:grid;width:62px;height:62px;margin:0 auto;place-items:center;border-radius:20px;color:#fff;background:linear-gradient(145deg,#6073ee,#55a7df);box-shadow:0 14px 30px rgba(74,104,211,.2)}.welcome-msg h3{font-size:22px}.welcome-msg p{margin-bottom:24px}
.chat-input{margin:0 clamp(12px,3vw,44px) 12px!important;padding:12px 14px 10px!important;border:1px solid #dfe3ea!important;border-radius:18px;background:#fff;box-shadow:0 10px 28px rgba(35,49,84,.09)}
.chat-input:focus-within{border-color:#9ba8ed!important;box-shadow:0 10px 30px rgba(66,83,185,.13)}
.chat-input textarea{display:block;width:100%;min-height:46px;max-height:132px;resize:none;border:0;outline:0;color:#202b3e;background:transparent;font:14px/1.6 inherit}
.chat-input textarea::placeholder{color:#a9b0bd}.composer-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:5px}.composer-left{display:flex;align-items:center;gap:7px;min-width:0;flex-wrap:wrap}
.round-tool{display:grid;width:30px;height:30px;place-items:center;border:1px solid #e1e5eb;border-radius:9px;color:#4d596d;background:#fff;cursor:pointer}.round-tool:hover{background:#f3f5f9}.mode-chip{height:30px;display:flex;align-items:center;gap:5px;padding:0 10px;border:1px solid #e0e4ea;border-radius:15px;color:#5f6a7c;background:#fff;font-size:11px;cursor:pointer}.mode-chip.active{border-color:#a9b9ff;color:#3f63dc;background:#f0f4ff}
.send-button{display:grid;width:34px;height:34px;flex:0 0 34px;place-items:center;border:0;border-radius:50%;color:#fff;background:#6275ee;cursor:pointer}.send-button:disabled{color:#aeb5c2;background:#eceff3;cursor:not-allowed}.send-button.stop{background:#e65f6b}.file-tag{margin:0 0 7px}.capability-menu{display:grid;gap:4px}.capability-menu button{display:flex;align-items:center;gap:9px;width:100%;padding:9px;border:0;border-radius:9px;color:#344056;background:transparent;text-align:left;cursor:pointer}.capability-menu button:hover:not(:disabled){background:#f2f4f9}.capability-menu button:disabled{opacity:.48;cursor:not-allowed}.capability-menu button>span{min-width:0;flex:1}.capability-menu b,.capability-menu small{display:block}.capability-menu b{font-size:12px}.capability-menu small{margin-top:3px;color:#98a1af;font-size:9px}.capability-menu em{width:8px;height:8px;border-radius:50%;background:#c8ced8}.capability-menu em.on{background:#4f72e8;box-shadow:0 0 0 4px rgba(79,114,232,.12)}
.tool-events-block{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:9px}.tool-events-label{color:#858fa1;font-size:10px}.tool-event-chip{padding:3px 8px;border:1px solid #cbd5f5;border-radius:12px;color:#4557a6;background:#f3f5ff;font-size:10px}.tool-event-chip.unavailable,.tool-event-chip.error{border-color:#f0d4a8;color:#a66a18;background:#fff9ec}
.learning-analysis-block{margin-bottom:10px;padding:10px 12px;border:1px solid #d6dcf7;border-radius:9px;color:#56617a;background:#f6f7fd;font-size:11px;line-height:1.6}.learning-analysis-title{display:flex;align-items:center;gap:6px;margin-bottom:4px;color:#4053a7;font-size:12px;font-weight:650}
.memory-update-block{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:10px;padding:9px 11px;border:1px solid #cfe8df;border-radius:10px;background:#f3fbf8}.memory-update-title{width:100%;color:#447566;font-size:10px;font-weight:750;letter-spacing:.04em}.memory-update-block span{padding:4px 8px;border-radius:12px;color:#356455;background:#e2f4ed;font-size:10px}
.mind-map-block{margin-bottom:12px;padding:12px 14px;border:1px solid #d9def1;border-radius:12px;background:#fbfcff}.mind-map-title{display:flex;align-items:center;gap:7px;margin-bottom:9px;color:#39466f;font-size:13px;font-weight:700}.mind-map-canvas{display:block;width:100%;max-height:360px;padding:0;overflow:auto;border:1px solid #e3e7f2;border-radius:10px;background:#fbfcff;cursor:zoom-in}.mind-map-canvas :deep(svg){display:block;width:100%;min-width:720px;height:auto}.mind-map-canvas:hover{border-color:#aeb8dd;box-shadow:0 8px 24px rgba(45,59,105,.08)}.mind-map-legacy{padding:16px;border-radius:9px;color:#7f889e;background:#f3f5fa;font-size:11px}
:global(.mind-map-dialog .el-dialog__body){padding:8px 18px 20px}.mind-map-dialog-canvas{max-height:78vh;overflow:auto;border:1px solid #e2e6f0;border-radius:12px;background:#fbfcff}.mind-map-dialog-canvas :deep(svg){display:block;width:max(100%,980px);height:auto}
@media(max-width:900px){.conversation-sidebar{position:absolute;z-index:10;inset:0 auto 0 0;box-shadow:10px 0 28px rgba(25,37,69,.14)}.conversation-sidebar.collapsed{position:relative;box-shadow:none}.chat-messages{padding-inline:16px!important}.chat-input{margin-inline:12px!important}.mode-chip{padding-inline:7px;font-size:10px}}
@media(max-width:900px){.qa-page{height:auto!important;min-height:calc(100dvh - 112px)}}
</style>
