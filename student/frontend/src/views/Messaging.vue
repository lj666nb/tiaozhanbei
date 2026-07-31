<template>
  <el-container class="messaging-shell">
    <!-- 左侧会话列表 -->
    <el-aside width="280px" class="conv-sidebar">
      <div class="conv-header">
        <span class="conv-title">
          会话列表
          <el-badge v-if="totalUnread > 0" :value="totalUnread" class="unread-badge" />
        </span>
        <div class="conv-actions">
          <el-button size="small" text @click="loadConversations">
            <el-icon><Refresh /></el-icon>
          </el-button>
          <el-button size="small" type="primary" @click="modalOpen = true">
            <el-icon><Plus /></el-icon>
            新建
          </el-button>
        </div>
      </div>

      <div class="conv-list" v-loading="loading">
        <template v-if="conversations.length === 0 && !loading">
          <el-empty description="暂无会话" :image-size="60" style="margin-top: 40px">
            <el-button type="primary" @click="modalOpen = true">
              <el-icon><Plus /></el-icon>
              发起新对话
            </el-button>
          </el-empty>
        </template>

        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: selectedConv?.id === conv.id }"
          @click="selectConv(conv)"
        >
          <div class="conv-row">
            <el-avatar :size="36" icon="UserFilled" style="background-color: #0F52BA" />
            <div class="conv-info">
              <strong>{{ conv.title }}</strong>
              <small>{{ conv.teacher_name }}</small>
            </div>
            <div class="conv-meta">
              <el-badge v-if="conv.unread_count > 0" :value="conv.unread_count" />
              <el-button
                size="small"
                text
                type="danger"
                :icon="Delete"
                @click.stop="handleDeleteConv(conv.id)"
              />
            </div>
          </div>
          <p v-if="conv.last_message" class="conv-preview">{{ conv.last_message }}</p>
        </div>
      </div>
    </el-aside>

    <!-- 右侧聊天区 -->
    <el-main class="chat-area">
      <template v-if="!selectedConv">
        <div class="chat-empty">
          <el-empty description="选择一个会话开始交流" :image-size="80" />
        </div>
      </template>

      <template v-else>
        <!-- 聊天头部 -->
        <div class="chat-header">
          <el-avatar :size="32" icon="UserFilled" style="background-color: #52c41a" />
          <div class="chat-header-info">
            <strong>{{ selectedConv.title }}</strong>
            <small>教师: {{ selectedConv.teacher_name }}</small>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="msg-list" ref="msgListRef" v-loading="msgLoading">
          <template v-if="messages.length === 0 && !msgLoading">
            <el-empty description="暂无消息，发送第一条消息吧" :image-size="60" />
          </template>

          <div
            v-for="msg in messages"
            :key="msg.id"
            class="msg-bubble"
            :class="{ 'msg-mine': msg.sender_role === 'student' }"
          >
            <span class="msg-sender">{{ msg.sender_role === 'student' ? '我' : msg.sender_name }}</span>
            <span class="msg-time">· {{ formatTime(msg.created_at) }}</span>
            <div class="msg-content">{{ msg.content }}</div>
          </div>
          <div ref="msgEndRef" />
        </div>

        <!-- 输入区 -->
        <div class="chat-input">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            @keydown.enter.exact.prevent="handleSend"
            resize="none"
          />
          <el-button type="primary" :icon="Promotion" @click="handleSend" :disabled="!inputText.trim()">
            发送
          </el-button>
        </div>
      </template>
    </el-main>

    <!-- 新建会话弹窗 -->
    <el-dialog v-model="modalOpen" title="发起新对话" width="420px" :close-on-click-modal="false">
      <div class="dialog-form">
        <label>教师姓名</label>
        <el-input v-model="newTeacherName" placeholder="输入教师姓名（如：admin）" />

        <label style="margin-top: 12px">对话标题（可选）</label>
        <el-input v-model="newConvTitle" :placeholder="newTeacherName ? `与 ${newTeacherName} 的对话` : '默认标题'" />
      </div>
      <template #footer>
        <el-button @click="modalOpen = false">取消</el-button>
        <el-button type="primary" @click="handleCreateConv">创建</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Plus, Delete, Promotion } from '@element-plus/icons-vue'
import {
  listConversations,
  createConversation,
  deleteConversation,
  getMessages,
  sendMessage,
  markRead,
  getStreamUrl,
} from '../api/messaging'

// ── 获取当前学生用户名 ──
function getStudentUsername() {
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const state = JSON.parse(raw)
      const user = state.user || state
      return user.username || user.nickname || '学生'
    }
  } catch { /* ignore */ }
  return '学生'
}

const studentName = ref(getStudentUsername())

// ── 状态 ──
const conversations = ref([])
const selectedConv = ref(null)
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const msgLoading = ref(false)
const totalUnread = ref(0)

// 弹窗
const route = useRoute()
const modalOpen = ref(false)
const newTeacherName = ref('')
const newConvTitle = ref('')

const msgListRef = ref(null)
const msgEndRef = ref(null)

let sse = null

// ── 滚动到底部 ──
function scrollToBottom() {
  nextTick(() => {
    msgEndRef.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

// ── 加载会话列表 ──
async function loadConversations() {
  if (!studentName.value) return
  loading.value = true
  try {
    const res = await listConversations()
    const list = res.data?.data?.conversations || []
    conversations.value = list
    totalUnread.value = list.reduce((s, c) => s + (c.unread_count || 0), 0)
  } catch {
    // 静默处理
  } finally {
    loading.value = false
  }
}

// ── 选择会话 ──
async function selectConv(conv) {
  selectedConv.value = conv
  msgLoading.value = true
  try {
    const res = await getMessages(conv.id)
    messages.value = res.data?.data?.messages || []
    await markRead(conv.id)
    loadConversations()
    scrollToBottom()
  } catch {
    ElMessage.error('加载消息失败')
  } finally {
    msgLoading.value = false
  }
}

// ── 发送消息 ──
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !selectedConv.value) return
  inputText.value = ''
  try {
    await sendMessage(selectedConv.value.id, {
      sender_name: studentName.value,
      sender_role: 'student',
      content: text,
    })
    await loadCurrentMessages()
  } catch {
    ElMessage.error('发送失败')
  }
}

async function loadCurrentMessages() {
  if (!selectedConv.value) return
  try {
    const res = await getMessages(selectedConv.value.id)
    messages.value = res.data?.data?.messages || []
    scrollToBottom()
  } catch { /* ignore */ }
}

// ── 新建会话 ──
async function handleCreateConv() {
  const teacherName = newTeacherName.value.trim()
  if (!teacherName) return
  try {
    const res = await createConversation({
      title: newConvTitle.value.trim() || `与 ${teacherName} 的对话`,
      student_name: studentName.value,
      teacher_name: teacherName,
    })
    const newConv = res.data?.data
    modalOpen.value = false
    newTeacherName.value = ''
    newConvTitle.value = ''
    await loadConversations()
    if (newConv) {
      selectedConv.value = newConv
      await loadCurrentMessages()
    }
  } catch {
    ElMessage.error('创建失败')
  }
}

// ── 删除会话 ──
async function handleDeleteConv(convId) {
  try {
    await deleteConversation(convId)
    if (selectedConv.value?.id === convId) {
      selectedConv.value = null
      messages.value = []
    }
    await loadConversations()
    ElMessage.success('会话已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 格式化时间 ──
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return `${d.getMonth() + 1}/${d.getDate()} ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}

// ── SSE 实时监听 ──
function connectSSE() {
  if (!studentName.value) return
  const url = getStreamUrl()
  sse = new EventSource(url)

  sse.addEventListener('new_message', (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.conversation_id === selectedConv.value?.id) {
        // 当前会话 → 追加消息
        const exists = messages.value.find(m => m.id === data.message?.id)
        if (!exists) {
          messages.value = [...messages.value, data.message]
          scrollToBottom()
          if (selectedConv.value?.id) markRead(selectedConv.value.id)
        }
      }
      loadConversations()
    } catch { /* ignore parse errors */ }
  })

  sse.addEventListener('connected', (event) => {
    console.log('[Messaging] SSE 已连接:', event.data)
  })

  sse.onerror = () => {
    sse.close()
    setTimeout(connectSSE, 3000)
  }
}

// ── 生命周期 ──
onMounted(() => {
  loadConversations()
  connectSSE()
  // 从课程卡片点击过来的「联系教师」预填
  const teacherParam = route.query.teacher
  if (teacherParam) {
    newTeacherName.value = teacherParam
    newConvTitle.value = `与 ${teacherParam} 的对话`
    modalOpen.value = true
  }
})

onUnmounted(() => {
  if (sse) sse.close()
})
</script>

<style scoped>
.messaging-shell {
  height: calc(100vh - 80px);
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

/* ── 左侧会话列表 ── */
.conv-sidebar {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #eee;
  background: #fafbfc;
  height: 100%;
}

.conv-header {
  padding: 14px 16px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conv-title {
  font-weight: 600;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.conv-actions {
  display: flex;
  gap: 4px;
}

.conv-list {
  flex: 1;
  overflow: auto;
}

.conv-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.2s;
}

.conv-item:hover { background: #f0f4ff; }
.conv-item.active { background: #e6f0ff; }

.conv-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.conv-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.conv-info strong {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-info small {
  font-size: 11px;
  color: #999;
}

.conv-meta {
  display: flex;
  align-items: center;
  gap: 2px;
}

.conv-preview {
  margin: 6px 0 0 46px;
  font-size: 11px;
  color: #aaa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 右侧聊天区 ── */
.chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-header {
  padding: 12px 20px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-header-info {
  display: flex;
  flex-direction: column;
}

.chat-header-info strong { font-size: 14px; }

.chat-header-info small {
  font-size: 11px;
  color: #999;
}

/* 消息列表 */
.msg-list {
  flex: 1;
  overflow: auto;
  padding: 16px 20px;
  background: #f5f7fa;
}

.msg-bubble {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 14px;
}

.msg-bubble.msg-mine {
  align-items: flex-end;
}

.msg-sender {
  font-size: 10px;
  color: #bbb;
  margin-bottom: 2px;
}

.msg-time {
  font-size: 10px;
  color: #bbb;
  margin-bottom: 2px;
}

.msg-content {
  max-width: 65%;
  padding: 10px 14px;
  border-radius: 12px 12px 12px 4px;
  background: #fff;
  color: #333;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
}

.msg-mine .msg-content {
  border-radius: 12px 12px 4px 12px;
  background: #0F52BA;
  color: #fff;
  box-shadow: 0 2px 6px rgba(15,82,186,0.2);
}

/* 输入区 */
.chat-input {
  padding: 12px 20px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.chat-input :deep(.el-textarea__inner) {
  resize: none;
}

/* 弹窗 */
.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dialog-form label {
  font-weight: 500;
  font-size: 13px;
  color: #333;
}

/* 通知角标样式 */
.unread-badge {
  margin-left: 4px;
}
</style>
