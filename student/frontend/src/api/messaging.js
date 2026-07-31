/**
 * 师生通信 API — 学生端
 *
 * 调用教师端后端（共享数据库）的消息接口。
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

/**
 * 获取当前学生用户信息（从 Pinia store）
 */
function getStudentInfo() {
  try {
    // 从 localStorage 读取 Pinia persisted state
    const raw = localStorage.getItem('user')
    if (raw) {
      const state = JSON.parse(raw)
      // Pinia persisted state: { token, user: { username, nickname, ... }, _verified }
      const user = state.user || state
      return {
        username: user.username || user.nickname || '学生',
        token: state.token || user.token || '',
      }
    }
  } catch { /* ignore */ }
  return { username: '学生', token: '' }
}

// ── 会话 ──

export function listConversations() {
  const { username } = getStudentInfo()
  return api.get('/messaging/conversations', {
    params: { username: encodeURIComponent(username), role: 'student' },
  })
}

export function createConversation(data) {
  return api.post('/messaging/conversations', data)
}

export function deleteConversation(id) {
  return api.delete(`/messaging/conversations/${id}`)
}

// ── 消息 ──

export function getMessages(convId, page = 1) {
  return api.get(`/messaging/conversations/${convId}/messages`, {
    params: { page, page_size: 50 },
  })
}

export function sendMessage(convId, data) {
  return api.post(`/messaging/conversations/${convId}/messages`, data)
}

export function markRead(convId) {
  return api.put(`/messaging/conversations/${convId}/read`, null, {
    params: { reader_role: 'student' },
  })
}

export function getUnreadCount() {
  const { username } = getStudentInfo()
  return api.get('/messaging/unread-count', {
    params: { username: encodeURIComponent(username), role: 'student' },
  })
}

// ── SSE 流地址 ──

export function getStreamUrl() {
  const { username } = getStudentInfo()
  return `/api/messaging/stream?username=${encodeURIComponent(username)}&role=student`
}
