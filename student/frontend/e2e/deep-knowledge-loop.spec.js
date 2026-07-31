import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1'

async function login(page) {
  await page.goto(`${BASE}/login`)
  await page.getByPlaceholder('请输入用户名').fill('demo')
  await page.getByPlaceholder('请输入密码').fill('demo123')
  await page.getByRole('button', { name: /进入学习空间/ }).click()
  await page.waitForURL('**/dashboard')
}

test('知识召回、图形思维导图和记忆账本形成可见闭环', async ({ page }) => {
  await login(page)

  const token = await page.evaluate(() => localStorage.getItem('token'))
  const headers = { Authorization: `Bearer ${token}` }
  const ragResponse = await page.request.get(
    `${BASE}/api/rag/search?q=${encodeURIComponent('多模态智能体如何实现')}&top_k=6`,
    { headers, timeout: 180_000 },
  )
  expect(ragResponse.ok()).toBeTruthy()
  const rag = (await ragResponse.json()).data
  expect(rag.results_count).toBe(6)
  expect(rag.sources[0].section).toContain('架构')
  expect(rag.sources[0].content.length).toBeGreaterThan(700)
  expect(rag.sources.map(item => item.content).join('')).not.toContain('AI Agent 实现篇')

  const mapResponse = await page.request.get(`${BASE}/api/qa/mind-maps/1`, { headers })
  expect(mapResponse.ok()).toBeTruthy()
  const mindMap = (await mapResponse.json()).data
  expect(mindMap.persistent).toBe(true)
  expect(mindMap.svg).toContain('<path')
  expect(mindMap.svg).toContain('短期记忆')

  await page.goto(`${BASE}/qa`)
  await page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/qa/conversations/current'
  )

  await page.route('**/api/qa/save-user-message', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      code: 200,
      data: {
        message_id: 90001,
        memory_updates: [{
          id: 90001,
          action: 'updated',
          message: '已更新：当前关注方向 → 智能体记忆',
        }],
      },
    }),
  }))
  await page.route('**/api/qa/save-assistant-message', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ code: 200, data: { message_id: 90002 } }),
  }))
  await page.route('**/api/qa/ask/stream', route => route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: [
      `data: ${JSON.stringify({ mind_map: mindMap })}`,
      `data: ${JSON.stringify({ content: '【回答】已生成可持久保存的智能体记忆思维导图。' })}`,
      'data: [DONE]',
      '',
    ].join('\n\n'),
  }))

  await page.getByPlaceholder('给 AI 导师发送消息').fill('生成智能体记忆思维导图')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('记忆账本 · 本轮已同步')).toBeVisible()
  await expect(page.getByText(/当前关注方向 → 智能体记忆/)).toBeVisible()
  const canvas = page.locator('.mind-map-canvas')
  await expect(canvas).toBeVisible()
  await expect(canvas.locator('svg path')).toHaveCount(9)
  await expect(canvas.locator('svg text')).toContainText(['智能体记忆', '短期记忆', '长期记忆'])
  await canvas.click()
  await expect(page.locator('.mind-map-dialog')).toBeVisible()
  await expect(page.locator('.mind-map-dialog-canvas svg path')).toHaveCount(9)

  await page.goto(`${BASE}/profile`)
  await expect(page.getByText('整体用户画像')).toBeVisible()
  await expect(page.getByText(/SiliconFlow/).first()).toBeVisible()
  await expect(page.getByText(/固定模型：BAAI\/bge-large-zh-v1.5/).first()).toBeVisible()
  await expect(page.locator('body')).not.toContainText('DashScope text-embedding-v3')
  await page.getByRole('button', { name: /长期记忆/ }).click()
  await expect(page.getByRole('button', { name: '新增记忆' })).toBeVisible()
  await expect(page.getByText(/自动新增、冲突更新和过期清理/)).toBeVisible()
})
