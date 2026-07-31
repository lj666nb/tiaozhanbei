import request from './request'

// 学习路径生成需要较长时间（LLM生成大JSON），使用独立超时配置
export const generateLearningPath = (data) =>
  request.post('/learning/path/generate', data, { timeout: 300000 })  // 5分钟超时
/** 记录学习访问（轻量，不计入loading） */
export const recordStudyVisit = () => request.post('/learning/visit').catch(() => {})
export const getLearningPath = () => request.get('/learning/path')
export const deleteLearningPath = () => request.delete('/learning/path')
export const generateDiagnosticTest = (data) => request.post('/learning/path/diagnostic-test', data)
export const updatePathProgress = (data) => request.put('/learning/path/progress', data)
export const getDailyTasks = (date) => request.get('/learning/tasks', { params: { date } })
export const completeTask = (data, date) => request.put('/learning/tasks/complete', data, { params: { date } })
export const getErrorBook = (page = 1) => request.get('/learning/error-book', { params: { page } })
export const reviewError = (id) => request.put(`/learning/error-book/${id}/review`)
export const reviewSessionErrors = (sessionId) => request.put(`/learning/error-book/session/${sessionId}/review-all`)
export const getErrorSessions = () => request.get('/learning/error-book/sessions')
export const getErrorsBySession = (sessionId, page = 1) => request.get(`/learning/error-book/session/${sessionId}`, { params: { page } })
export const getOrphanErrors = (page = 1) => request.get('/learning/error-book/orphan', { params: { page } })
export const deleteSessionErrors = (sessionId) => request.delete(`/learning/error-book/session/${sessionId}`)
export const deleteOrphanErrors = () => request.delete('/learning/error-book/orphan')
export const batchDeleteErrors = (ids) => request.post('/learning/error-book/batch-delete', { ids })

export const generateTaskQuiz = (data) => request.post('/learning/task-quiz', data)
export const getLearningResource = (knowledge) => request.get('/learning/resource', { params: { knowledge } })

export const getCodeTask = (taskDay) => request.get(`/learning/code-task/${taskDay}`)
export const executeCode = (data) => request.post('/learning/code-execute', data)
export const getCodeAnswer = (taskDay) => request.get(`/learning/code-answer/${taskDay}`)
export const generateCodeStepGuide = (data) => request.post('/learning/code-step-guide', data)
export const checkCodeStep = (data) => request.post('/learning/code-step-check', data)

// 教程文档管理
export const saveTutorial = (knowledgeTag, data) =>
  request.put(`/learning/tutorial/${encodeURIComponent(knowledgeTag)}`, data)

export const deleteTutorial = (knowledgeTag) =>
  request.delete(`/learning/tutorial/${encodeURIComponent(knowledgeTag)}`)

export const generateAITutorial = (data) =>
  request.post('/learning/tutorial/generate', data)
