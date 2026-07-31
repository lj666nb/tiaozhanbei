import request from './request'

export const startCapabilitySession = (exerciseId, forceNew = false) =>
  request.post('/capability/sessions', { exercise_id: exerciseId, force_new: forceNew })

export const getCapabilitySession = (sessionId) =>
  request.get(`/capability/sessions/${sessionId}`)

export const recordCapabilityEvents = (sessionId, events) =>
  request.post(`/capability/sessions/${sessionId}/events`, { events })

export const markCapabilityCodePassed = (sessionId, code) =>
  request.post(`/capability/sessions/${sessionId}/code-passed`, { code }, { timeout: 180000 })

export const submitCapabilityDefense = (sessionId, answers, aiUsage) =>
  request.post(`/capability/sessions/${sessionId}/defense`, {
    answers,
    ai_usage: aiUsage,
  })

export const submitCapabilityRepair = (sessionId, code, explanation) =>
  request.post(`/capability/sessions/${sessionId}/repair`, { code, explanation }, { timeout: 180000 })

/** 保留上次评分并重新注入故障，开始下一次修复尝试 */
export const retryCapabilityRepair = (sessionId) =>
  request.post(`/capability/sessions/${sessionId}/repair/retry`)

/** 将可见项目刷新为初始化、全测试通过、故障修复或变式迁移状态。 */
export const switchCapabilityProjectState = (sessionId, state) =>
  request.post(`/capability/sessions/${sessionId}/project-state`, { state })

/** 跳过能力验证，仅以测试分数完成关卡 */
export const skipCapability = (sessionId) =>
  request.post(`/capability/sessions/${sessionId}/skip`)

/** 获取能力验证回顾数据（用户回答 vs 标准答案） */
export const getSessionReview = (sessionId) =>
  request.get(`/capability/sessions/${sessionId}/review`)

/** 变式迁移：生成变式场景 */
export const generateVariant = (sessionId) =>
  request.post(`/capability/sessions/${sessionId}/variant/generate`)

/** 变式迁移：提交变式代码 */
export const submitVariant = (sessionId, code) =>
  request.post(`/capability/sessions/${sessionId}/variant/submit`, { code }, { timeout: 180000 })

/** 获取已完成实验的详细历史记录 */
export const getCapabilityHistory = () =>
  request.get('/capability/history')

/** 获取所有已完成关卡的分数概览 */
export const getCapabilityScores = () =>
  request.get('/capability/scores')

