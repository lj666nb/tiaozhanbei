import request from './request'

export const generateQuiz = (data) => request.post('/diagnosis/quiz/generate', data)
export const submitQuiz = (data) => request.post('/diagnosis/quiz/submit', data)
export const getQuizHistory = () => request.get('/diagnosis/quiz/history')
export const getQuizReport = (id) => request.get(`/diagnosis/quiz/report/${id}`)
export const getKnowledgeProfile = () => request.get('/diagnosis/profile')
