import request from './request'

function streamAuthHeaders() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleStreamAuthFailure(response) {
  if (response.status !== 401) return
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
  throw new Error('登录状态已失效，请重新登录')
}

export const getLabWorkspace = (exerciseId, reset = false) =>
  request.get(`/workspaces/${exerciseId}`, { params: { reset } })

export const getLabProgressOverview = () => request.get('/workspaces/progress/all')

export const listLabEntries = (exerciseId, path = '') =>
  request.get(`/workspaces/${exerciseId}/entries`, { params: { path } })

export const readLabFile = (exerciseId, path) =>
  request.get(`/workspaces/${exerciseId}/file`, { params: { path } })

export const saveLabFile = (exerciseId, path, content) =>
  request.put(`/workspaces/${exerciseId}/file`, { path, content })

export const deleteLabFile = (exerciseId, path) =>
  request.delete(`/workspaces/${exerciseId}/file`, { data: { path } })

export const createLabDirectory = (exerciseId, path) =>
  request.post(`/workspaces/${exerciseId}/directory`, { path })

export const moveLabEntry = (exerciseId, path, destination) =>
  request.post(`/workspaces/${exerciseId}/entry/move`, { path, destination })

export const duplicateLabEntry = (exerciseId, path, destination) =>
  request.post(`/workspaces/${exerciseId}/entry/duplicate`, { path, destination })

export const deleteLabEntry = (exerciseId, path) =>
  request.delete(`/workspaces/${exerciseId}/entry`, { data: { path } })

export const runLabTerminal = (exerciseId, command) =>
  request.post(`/workspaces/${exerciseId}/terminal`, { command }, { timeout: 200000 })

export async function streamLabTerminal(exerciseId, command, onEvent, signal) {
  const baseUrl = window.__API_BASE_URL__ || import.meta.env.VITE_API_BASE_URL || '/api'
  const response = await fetch(`${baseUrl}/workspaces/${encodeURIComponent(exerciseId)}/terminal/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...streamAuthHeaders(),
    },
    body: JSON.stringify({ command }),
    signal,
  })
  if (!response.ok) {
    handleStreamAuthFailure(response)
    let detail = `终端请求失败（${response.status}）`
    try { detail = (await response.json()).detail || detail } catch (_) { /* non-json response */ }
    throw new Error(detail)
  }
  if (!response.body) throw new Error('当前浏览器不支持实时终端输出')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalEvent = null
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.trim()) continue
      const event = JSON.parse(line)
      if (event.type === 'error') throw new Error(event.message || '终端执行失败')
      if (event.type === 'done') finalEvent = event
      onEvent?.(event)
    }
    if (done) break
  }
  return finalEvent || { exit_code: 1, cwd: '', active_env: '' }
}

export const checkLabStage = (exerciseId, stageId) =>
  request.post(`/workspaces/${exerciseId}/check`, { stage_id: stageId }, { timeout: 180000 })

export const askLabAssistant = (exerciseId, question, activeFile, mode = 'agent', stageId = '') =>
  request.post(
    `/workspaces/${exerciseId}/assistant`,
    { question, active_file: activeFile, mode, stage_id: stageId },
    { timeout: 180000 },
  )

export async function streamLabAssistant(exerciseId, question, activeFile, mode, stageId, onEvent, signal) {
  const baseUrl = window.__API_BASE_URL__ || import.meta.env.VITE_API_BASE_URL || '/api'
  const response = await fetch(`${baseUrl}/workspaces/${encodeURIComponent(exerciseId)}/assistant/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...streamAuthHeaders(),
    },
    body: JSON.stringify({ question, active_file: activeFile || '', mode, stage_id: stageId || '' }),
    signal,
  })
  if (!response.ok) {
    handleStreamAuthFailure(response)
    let detail = `导师请求失败（${response.status}）`
    try { detail = (await response.json()).detail || detail } catch (_) { /* non-json response */ }
    throw new Error(detail)
  }
  if (!response.body) throw new Error('当前浏览器不支持实时流式传输')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const event = JSON.parse(line)
        onEvent(event)
      } catch (_) { /* skip invalid JSON */ }
    }
    if (done) break
  }
}

export const resetLabAssistant = exerciseId =>
  request.delete(`/workspaces/${exerciseId}/assistant/history`)
