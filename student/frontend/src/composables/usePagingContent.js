/**
 * usePagingContent.js — 长文本电子书翻页组合式函数
 *
 * 功能：
 *   - 将 HTML 长文本按自然段落边界自动分页
 *   - 段落/图表/代码块不会被拦腰切断
 *   - 支持 Prev/Next 翻页、页码跳转、键盘左右键、鼠标滚轮
 *   - 窗口 resize 自动重新分页，始终回到第 1 页
 *   - 关闭弹窗后再次打开默认第 1 页
 */

import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

/** 不能被拆分的顶层块标签（这些标签作为分页原子单元） */
const ATOMIC_TAGS = new Set([
  'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
  'P', 'PRE', 'TABLE', 'UL', 'OL',
  'BLOCKQUOTE', 'DIV', 'FIGURE', 'IMG',
  'VIDEO', 'AUDIO', 'CANVAS',
])

/**
 * 第二层保险：检测未格式化的 mermaid 代码（flowchart TD / graph LR 等），
 * 自动包装为 <div class="mermaid"> 以便 mermaid-js 渲染。
 * 防止后端漏掉未格式化的 Mermaid 字符串直接暴露给用户。
 */
function autoWrapMermaid(htmlString) {
  if (!htmlString) return htmlString

  // 检测包含 flowchart / graph / sequenceDiagram 等关键字但未被 .mermaid 包裹的代码块
  // 模式：``` 围栏内是 mermaid 图表代码，但 marked 可能没有正确识别语言标签
  let result = htmlString

  // 1. <pre><code> 中含有 flowchart/graph 但外层不在 .mermaid 内 → 转为 mermaid div
  result = result.replace(
    /<pre><code(?: class="[^"]*")?>([\s\S]*?)<\/code><\/pre>/g,
    (match, code) => {
      const decoded = code
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&').replace(/&quot;/g, '"')
      const trimmed = decoded.trim()
      if (/^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|gitGraph)\s/.test(trimmed)) {
        return '<div class="mermaid">' + decoded + '</div>'
      }
      return match  // 普通代码块保持原样
    }
  )

  // 2. 直接裸露在 HTML 中的 flowchart TD 文本（极其罕见，兜底用）
  //    检查没有被任何标签包裹的 flowchart 文本
  //    这种情况一般不处理，因为 marked 会正确解析围栏代码块

  return result
}

export function usePagingContent(contentRef) {
  // ===== 状态 =====
  const currentPage = ref(1)
  const totalPages = ref(1)
  const pageBlocks = ref([])      // 当前页要显示的 HTML 块数组
  const rawBlocks = ref([])        // 所有解析出的 HTML 块
  const pageMap = ref([])          // [{ startIdx, endIdx }] 每页包含的块索引范围

  let resizeObserver = null
  let measureContainer = null
  let blockHeights = []            // 每个块的高度（px）

  // ===== 计算属性 =====
  const isFirstPage = computed(() => currentPage.value <= 1)
  const isLastPage = computed(() => currentPage.value >= totalPages.value)
  const pageInfo = computed(() => `第 ${currentPage.value} 页 / 共 ${totalPages.value} 页`)

  // ===== 步骤 1：将 HTML 字符串拆分为原子块 =====
  function parseBlocks(htmlString) {
    if (!htmlString) return []

    // 第二层保险：自动检测并包裹未格式化的 mermaid 代码
    htmlString = autoWrapMermaid(htmlString)

    // 创建临时 DOM 解析 HTML
    const parser = new DOMParser()
    const doc = parser.parseFromString(`<div>${htmlString}</div>`, 'text/html')
    const container = doc.body.firstChild

    const blocks = []
    for (const child of container.childNodes) {
      const tag = child.nodeName?.toUpperCase()

      // 文本节点 → 如果非空则包装为 <p>
      if (child.nodeType === Node.TEXT_NODE) {
        const text = child.textContent.trim()
        if (text) {
          blocks.push(`<p>${text}</p>`)
        }
        continue
      }

      // 元素节点
      if (child.nodeType === Node.ELEMENT_NODE) {
        if (tag === 'SCRIPT' || tag === 'STYLE') continue

        // 空元素跳过
        if (tag !== 'IMG' && tag !== 'BR' && tag !== 'HR' &&
            !child.textContent.trim() && !child.querySelector('img')) {
          continue
        }

        // 保留原始 HTML
        blocks.push(child.outerHTML)
      }
    }

    // 过滤掉空段落
    return blocks.filter(b => {
      const stripped = b.replace(/<[^>]+>/g, '').trim()
      return stripped.length > 0 || b.includes('<img') || b.includes('<svg')
    })
  }

  // ===== 步骤 2：测量每个块的高度 =====
  function createMeasureContainer() {
    // 移除旧容器（宽度可能已变化）
    removeMeasureContainer()
    const width = contentRef.value?.clientWidth || Math.min(window.innerWidth * 0.75, 1300) - 56
    measureContainer = document.createElement('div')
    measureContainer.style.cssText = `
      position: absolute; visibility: hidden; width: ${width}px;
      pointer-events: none; font-size: 16px; line-height: 1.9; padding: 20px 0;
      box-sizing: border-box;
    `
    document.body.appendChild(measureContainer)
  }

  function removeMeasureContainer() {
    if (measureContainer) {
      measureContainer.remove()
      measureContainer = null
    }
  }

  function measureBlockHeights(blocks) {
    if (!contentRef.value) return []
    if (!measureContainer) createMeasureContainer()

    // 同步宽度到实际内容区
    const actualWidth = contentRef.value.clientWidth
    if (actualWidth > 0) {
      measureContainer.style.width = `${actualWidth}px`
    }

    const heights = []

    for (const block of blocks) {
      measureContainer.innerHTML = block
      const firstChild = measureContainer.firstElementChild
      if (firstChild) {
        const rect = firstChild.getBoundingClientRect()
        const style = window.getComputedStyle(firstChild)
        const marginTop = parseFloat(style.marginTop) || 0
        const marginBottom = parseFloat(style.marginBottom) || 0
        heights.push(rect.height + marginTop + marginBottom)
      } else {
        heights.push(measureContainer.getBoundingClientRect().height)
      }
    }

    measureContainer.innerHTML = ''
    return heights
  }

  // ===== 步骤 3：按可用高度将块分配到各页 =====
  function buildPageMap(heights) {
    if (heights.length === 0) {
      return [{ startIdx: 0, endIdx: 0 }]
    }

    // 可用高度：优先取内容区实际 clientHeight，兜底按 80vh 估算（与弹窗高度一致）
    const rawHeight = contentRef.value?.clientHeight || 0
    const paddingV = 30  // 内容区内边距留白
    // 兜底：80vh - 标题栏50px - 翻页栏50px ≈ 窗口高度 × 0.7
    const fallbackHeight = Math.max(600, window.innerHeight * 0.70)
    const availableHeight = rawHeight > 150 ? rawHeight - paddingV : fallbackHeight

    const pages = []
    let startIdx = 0
    let currentHeight = 0

    for (let i = 0; i < heights.length; i++) {
      const h = heights[i]

      // 单个块超过一页 → 独占一页
      if (h > availableHeight && currentHeight === 0) {
        pages.push({ startIdx: i, endIdx: i + 1 })
        startIdx = i + 1
        currentHeight = 0
        continue
      }

      // 当前页放不下 → 新开一页
      if (currentHeight + h > availableHeight && currentHeight > 0) {
        pages.push({ startIdx, endIdx: i })
        startIdx = i
        currentHeight = h
      } else {
        currentHeight += h
      }
    }

    // 最后一页
    if (startIdx < heights.length) {
      pages.push({ startIdx, endIdx: heights.length })
    }

    return pages.length > 0 ? pages : [{ startIdx: 0, endIdx: heights.length }]
  }

  // ===== 步骤 4：渲染当前页 =====
  function renderCurrentPage() {
    if (!pageMap.value.length || !rawBlocks.value.length) {
      pageBlocks.value = []
      totalPages.value = 1
      return
    }

    totalPages.value = pageMap.value.length

    // 修正越界的页码
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
    }
    if (currentPage.value < 1) {
      currentPage.value = 1
    }

    const page = pageMap.value[currentPage.value - 1]
    if (!page) {
      pageBlocks.value = []
      return
    }

    pageBlocks.value = rawBlocks.value.slice(page.startIdx, page.endIdx)
  }

  // ===== 公开 API =====

  /** 设置新内容，触发分页计算 */
  async function setContent(htmlString) {
    rawBlocks.value = parseBlocks(htmlString)

    if (!rawBlocks.value.length) {
      pageMap.value = []
      pageBlocks.value = []
      totalPages.value = 1
      currentPage.value = 1
      return
    }

    await nextTick()

    // 确保 ResizeObserver 已连接（dialog 可能刚打开，ref 现在才可用）
    if (contentRef.value && !resizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        repaginate()
      })
      resizeObserver.observe(contentRef.value)
    }

    createMeasureContainer()
    blockHeights = measureBlockHeights(rawBlocks.value)
    removeMeasureContainer()

    pageMap.value = buildPageMap(blockHeights)
    currentPage.value = 1
    renderCurrentPage()
  }

  /** 重新分页（窗口大小变化时调用） */
  function repaginate() {
    if (!rawBlocks.value.length) return

    createMeasureContainer()
    blockHeights = measureBlockHeights(rawBlocks.value)
    removeMeasureContainer()

    const oldTotal = totalPages.value
    pageMap.value = buildPageMap(blockHeights)
    // 尽量保持当前页不变
    if (currentPage.value > pageMap.value.length) {
      currentPage.value = pageMap.value.length
    }
    renderCurrentPage()
  }

  /** 上一页 */
  function prevPage() {
    if (currentPage.value > 1) {
      currentPage.value--
      renderCurrentPage()
    }
  }

  /** 下一页 */
  function nextPage() {
    if (currentPage.value < totalPages.value) {
      currentPage.value++
      renderCurrentPage()
    }
  }

  /** 跳转到指定页 */
  function goToPage(page) {
    const p = Math.max(1, Math.min(totalPages.value, parseInt(page) || 1))
    if (p !== currentPage.value) {
      currentPage.value = p
      renderCurrentPage()
    }
  }

  /** 键盘事件处理（仅在有分页内容时生效） */
  function onKeydown(e) {
    if (totalPages.value <= 1) return  // 无分页内容时忽略
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      prevPage()
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      nextPage()
    }
  }

  /** 滚轮事件处理 */
  function onWheel(e) {
    // 只在弹窗内容区域处理
    if (e.target.closest('.paging-content-area')) {
      e.preventDefault()
      if (e.deltaY > 0) {
        nextPage()
      } else if (e.deltaY < 0) {
        prevPage()
      }
    }
  }

  /** 重置到第 1 页 */
  function reset() {
    currentPage.value = 1
    renderCurrentPage()
  }

  // ===== 生命周期 =====
  onMounted(() => {
    // 键盘和滚轮全局生效，翻页函数内部有 totalPages 守卫
    document.addEventListener('keydown', onKeydown)
    document.addEventListener('wheel', onWheel, { passive: false })
  })

  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    resizeObserver = null
    removeMeasureContainer()
    document.removeEventListener('keydown', onKeydown)
    document.removeEventListener('wheel', onWheel)
  })

  return {
    // 状态
    currentPage,
    totalPages,
    pageBlocks,
    pageInfo,
    isFirstPage,
    isLastPage,

    // 方法
    setContent,
    repaginate,
    prevPage,
    nextPage,
    goToPage,
    reset,
  }
}
