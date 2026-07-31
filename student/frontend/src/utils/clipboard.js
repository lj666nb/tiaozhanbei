/**
 * 跨环境复制文本到剪贴板
 * - 安全上下文（HTTPS/localhost）：使用 navigator.clipboard API
 * - 非安全上下文（HTTP部署）：降级使用 document.execCommand('copy')
 */
export async function copyToClipboard(text) {
  if (!text) return false

  // 方案1：Clipboard API（需要安全上下文）
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (e) {
      // Clipboard API 失败 → 尝试降级
      console.warn('[copyToClipboard] Clipboard API 失败，使用降级方案:', e.message)
    }
  }

  // 方案2：execCommand 降级（兼容所有环境，包括 HTTP）
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.top = '0'
    textarea.style.left = '0'
    textarea.style.opacity = '0'
    textarea.style.pointerEvents = 'none'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    return success
  } catch (e) {
    console.error('[copyToClipboard] 降级方案也失败:', e.message)
    return false
  }
}

export default copyToClipboard
