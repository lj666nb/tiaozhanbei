import request from './request'

export const getStats = () => request.get('/analytics/stats')
export const getWeeklyReport = () => request.get('/analytics/report/weekly')
export const getMonthlyReport = () => request.get('/analytics/report/monthly')
export const getGrowthData = () => request.get('/analytics/growth')
export const recordActivity = (params) => request.post('/analytics/record', null, { params })
