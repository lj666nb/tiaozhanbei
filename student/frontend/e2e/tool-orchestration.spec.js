import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1'

async function login(page) {
  await page.goto(`${BASE}/login`)
  await page.locator('input[placeholder="请输入用户名"]').fill('demo')
  await page.locator('input[placeholder="请输入密码"]').fill('demo123')
  await page.getByRole('button', { name: /进入学习空间/ }).click()
  await page.waitForURL('**/dashboard')
}

test('QA 展示自主工具、思维导图、降级提示并支持训练数据导出', async ({ page }) => {
  const consoleErrors = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await login(page)
  const currentConversationLoaded = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/qa/conversations/current'
  )
  await page.goto(`${BASE}/qa`)
  await currentConversationLoaded

  await expect(page.getByRole('button', { name: 'Tavily 搜索' })).toBeVisible()
  await expect(page.getByRole('button', { name: /导出训练数据/ })).toBeVisible()

  await page.getByRole('button', { name: '更多能力' }).click()
  await expect(page.getByText('课程知识库', { exact: true })).toBeVisible()
  await expect(page.getByText('个人学情分析', { exact: true })).toBeVisible()
  await expect(page.getByText('思维导图', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.route('**/*', route => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname === '/api/qa/save-user-message' || pathname === '/api/qa/save-assistant-message') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: 200, data: { message_id: 1 } }),
      })
    }
    if (pathname !== '/api/qa/ask/stream') return route.continue()
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
      'data: {"tool_events":[{"name":"web_search","status":"unavailable"},{"name":"generate_mind_map","status":"ok"},{"name":"analyze_learning_data","status":"ok"}]}',
      'data: {"search_unavailable":true,"message":"Tavily 高级搜索暂不可用"}',
      'data: {"learning_analysis":{"snapshot":{"coverage":"limited","coverage_note":"正式测评样本偏少，只能作为阶段性观察。"}}}',
      'data: {"mind_map":{"title":"智能体记忆","root":{"label":"智能体记忆","children":[{"label":"短期记忆","children":[]},{"label":"长期记忆","children":[]}]}}}',
      'data: {"content":"【回答】这是工具编排后的测试回答。"}',
      'data: [DONE]',
      '',
      ].join('\n\n'),
    })
  })

  await page.locator('textarea[placeholder="给 AI 导师发送消息"]').fill('生成智能体记忆思维导图')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('Tavily 高级搜索暂不可用', { exact: true })).toBeVisible()
  await expect(page.locator('.tool-event-chip')).toHaveCount(3)
  await expect(page.locator('.mind-map-block')).toContainText('短期记忆')
  await expect(page.locator('.mind-map-block')).toContainText('长期记忆')
  await expect(page.locator('.learning-analysis-block')).toContainText('阶段性观察')
  await expect(page.getByText('这是工具编排后的测试回答。')).toBeVisible()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /导出训练数据/ }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.jsonl$/)
  expect(consoleErrors).toEqual([])
})
