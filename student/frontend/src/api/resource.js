import request from './request'

export const getRecommendations = () => request.get('/resources/recommend')
export const getResourceList = (params) => request.get('/resources/list', { params })
export const collectResource = (id) => request.post(`/resources/collect/${id}`)
export const getCollectedResources = () => request.get('/resources/collected')

/** 根据知识点获取AI整理的学习资料（联网搜索+AI组织） */
export const getKnowledgeMaterial = (knowledge) =>
  request.get('/resources/material', { params: { knowledge } })

/** 根据资源ID获取学习资料（优先本地，兜底联网） */
export const getResourceLearnMaterial = (resourceId) =>
  request.get(`/resources/learn/${resourceId}`)

// PDF 电子书
export const uploadPdf = (file) => {
  const form = new FormData()
  form.append('file', file)
  return request.post('/resources/pdf/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}
export const getPdfList = () => request.get('/resources/pdf/list')
export const getPdfUrl = (id) => `/api/resources/pdf/${id}`
export const deletePdf = (id) => request.delete(`/resources/pdf/${id}`)
export const batchDeletePdfs = (ids) => request.post('/resources/pdf/batch-delete', { ids })
