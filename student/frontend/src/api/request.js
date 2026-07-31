import axios from 'axios'
import { ElMessage } from 'element-plus'

// 基础地址优先级：运行时配置 > 环境变量 > 默认值
// window.__API_BASE_URL__ 由 public/config.js 注入，部署后可直接修改无需重新构建
const apiBaseUrl = window.__API_BASE_URL__
  || import.meta.env.VITE_API_BASE_URL
  || '/api'

const request = axios.create({
  baseURL: apiBaseUrl,
  timeout: 120000
})

request.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 开发调试：打印实际请求 URL
  if (import.meta.env.DEV) {
    console.log('[API]', config.method?.toUpperCase(), config.baseURL + config.url)
  }
  return config
})

request.interceptors.response.use(
  response => {
    const data = response.data
    if (data.code !== 200) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data.data
  },
  error => {
    // 401 → 清除过期 token，跳转登录
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const errorMsg = error.response?.data?.detail
      || error.response?.data?.message
      || error.message
      || '网络错误，请稍后重试'
    console.error('[API Error]', error.config?.url, errorMsg)
    ElMessage.error(errorMsg)
    return Promise.reject(error)
  }
)

export default request
