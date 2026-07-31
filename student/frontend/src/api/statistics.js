/**
 * statistics.js — 统计数据 API 层（唯一网络请求入口）
 *
 * 架构约定：
 * - 所有网络请求只在此文件发起，页面和 Store 不直接调后端
 * - 全部对接后端真实 API，不再使用任何 Mock 数据
 * - 同一账号在不同设备登录时数据完全一致（数据源 = 服务器 SQLite 数据库）
 */

// ============ 通用请求封装 ============

function authHeaders() {
  return { 'Authorization': 'Bearer ' + (localStorage.getItem('token') || '') }
}

async function apiGet(url) {
  const res = await fetch(url, { headers: authHeaders() })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data.data || data
}

async function apiPost(url, body = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data.data || data
}

// ============ 概览统计（真实后端） ============

/** GET /api/analytics/stats → analytics_service.get_user_stats() */
export async function fetchStats() {
  return apiGet('/api/analytics/stats')
}

// ============ 知识点掌握度（真实后端） ============

/** GET /api/diagnosis/profile → diagnosis_service.get_user_knowledge_profile() */
export async function fetchKnowledgeMastery() {
  const profile = await apiGet('/api/diagnosis/profile')
  return { mastery: profile.mastery || {}, has_data: profile.has_data || {} }
}

// ============ 最近学习动态（真实后端，跨设备一致） ============

/** GET /api/analytics/activity → analytics_service.get_recent_activity()
 *  合并 测评/答疑/错题 三类活动，来自数据库查询 */
export async function fetchRecentActivity() {
  return apiGet('/api/analytics/activity')
}

// ============ 周报 / 月报（真实后端） ============

/** GET /api/analytics/report/weekly → analytics_service.get_weekly_report() */
export async function fetchWeeklyReport() {
  return apiGet('/api/analytics/report/weekly')
}

/** GET /api/analytics/report/monthly → analytics_service.get_monthly_report() */
export async function fetchMonthlyReport() {
  return apiGet('/api/analytics/report/monthly')
}

// ============ 成长轨迹（真实后端） ============

/** GET /api/analytics/growth → analytics_service.get_growth_data() */
export async function fetchGrowthData() {
  return apiGet('/api/analytics/growth')
}

// ============ 提交测评结果（真实后端，跨设备同步） ============

/** POST /api/analytics/submit-result → 记录测评完成事件到 learning_records 表 */
export async function submitQuizResult(result) {
  const { knowledge = '综合练习' } = result || {}
  return apiPost('/api/analytics/submit-result', {
    knowledge_tag: knowledge,
    result: JSON.stringify(result || {})
  })
}

// ============ 刷新统计（后端无额外操作，仅验证连通性） ============

export async function refreshStats() {
  // 调用 health 确认后端可达
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error('后端服务不可达')
  return { success: true }
}
