import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1'

async function login(page) {
  await page.goto(`${BASE}/login`)
  await page.locator('input[placeholder="请输入用户名"]').fill('demo')
  await page.locator('input[placeholder="请输入密码"]').fill('demo123')
  await page.getByRole('button', { name: /进入学习空间/ }).click()
  await page.waitForURL('**/dashboard')
}

test('编程实验室右侧 AI 一轮异常后仍可继续下一轮对话', async ({ page }) => {
  let requestCount = 0
  await page.route('**/api/workspaces/1-1/assistant/stream', async route => {
    requestCount += 1
    const events = requestCount === 1
      ? [
          { type: 'text', content: '第一轮已经完成诊断。' },
          { type: 'done', status: 'error', error: '临时模型错误' },
        ]
      : [
          { type: 'text', content: '第二轮对话正常继续。' },
          { type: 'done', status: 'ready', available: true },
        ]
    await route.fulfill({
      status: 200,
      contentType: 'application/x-ndjson; charset=utf-8',
      body: `${events.map(event => JSON.stringify(event)).join('\n')}\n`,
    })
  })

  await login(page)
  await page.goto(`${BASE}/code-lab/1/1-1`)

  const composer = page.locator('.agent-composer textarea')
  await expect(composer).toBeEnabled()

  await composer.fill('第一轮问题')
  await composer.press('Enter')
  await expect(page.locator('.chat-list')).toContainText('第一轮已经完成诊断。')
  await expect(page.locator('.chat-list')).toContainText('临时模型错误')
  await expect(composer).toBeEnabled()

  await composer.fill('第二轮问题')
  await composer.press('Enter')
  await expect(page.locator('.chat-list')).toContainText('第二轮对话正常继续。')
  await expect(composer).toBeEnabled()
  expect(requestCount).toBe(2)
})
