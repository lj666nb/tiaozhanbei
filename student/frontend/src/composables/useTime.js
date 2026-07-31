/**
 * useTime.js — 公共时间格式化工具
 * 将后端返回的时间字符串转换为友好的相对时间文本
 * 可在任意组件中复用
 */

/**
 * 将时间字符串/时间戳转换为相对时间描述
 * @param {string|Date} timeStr - 后端返回的时间，格式 "2026-07-13 14:20:00" 或 ISO 字符串
 * @returns {string} 友好的相对时间文本，如 "3分钟前"、"4小时前"、"昨天"
 *
 * 使用示例：
 *   import { relativeTime } from '@/composables/useTime'
 *   relativeTime('2026-07-13 14:20:00')  // → "14分钟前"
 */
export function relativeTime(timeStr) {
  if (!timeStr) return ''

  const now = new Date()
  const target = new Date(timeStr)
  // 无效日期直接返回原始字符串
  if (isNaN(target.getTime())) return timeStr

  const diffMs = now - target
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  // 1分钟内
  if (diffSeconds < 60) {
    return '刚刚'
  }
  // 1小时内
  if (diffMinutes < 60) {
    return diffMinutes + '分钟前'
  }
  // 当天
  if (diffHours < 24) {
    return diffHours + '小时前'
  }
  // 昨天
  if (diffDays === 1) {
    return '昨天'
  }
  // 2天内
  if (diffDays < 3) {
    return diffDays + '天前'
  }
  // 超过3天，返回简短日期
  const month = target.getMonth() + 1
  const day = target.getDate()
  return month + '/' + day
}

/**
 * 将时间字符串格式化为标准显示格式 YYYY-MM-DD HH:mm
 * @param {string|Date} timeStr - 时间字符串
 * @returns {string} 格式化后的时间
 */
export function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  if (isNaN(d.getTime())) return timeStr
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
