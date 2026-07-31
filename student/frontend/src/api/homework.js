/**
 * 我的作业 API — 学生端
 * 调用教师端后端 (端口 8000)
 */
import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 120000 })

function studentName() {
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const state = JSON.parse(raw)
      const user = state.user || state
      return user.username || user.nickname || '学生'
    }
  } catch { /* */ }
  return '学生'
}

export function listAssignments(params = {}) {
  return api.get('/assignments', {
    params: { student: studentName(), ...params },
  })
}

export function getAssignment(id) {
  return api.get(`/assignments/${id}`)
}

export function submitHomework(assignmentId, data) {
  return api.post(`/assignments/${assignmentId}/submit`, {
    ...data,
    student_name: studentName(),
  })
}

export function getMySubmissions() {
  return api.get(`/assignments/submissions/student/${studentName()}`)
}
