import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1'

async function login(page) {
  await page.goto(`${BASE}/login`)
  await page.locator('input[placeholder="请输入用户名"]').fill('demo')
  await page.locator('input[placeholder="请输入密码"]').fill('demo123')
  await page.getByRole('button', { name: /进入学习空间/ }).click()
  await page.waitForURL('**/dashboard')
}

test('实验室顶部展示四阶段闭环，答辩评审可持久化回看', async ({ page }) => {
  await login(page)

  const correctCode = `
def build_chat_messages(system_prompt, user_input):
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("system_prompt 不能为空")
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("user_input 不能为空")
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_input.strip()},
    ]
`
  const answers = [
    { question_id: 'q1', answer: '输入参数是系统提示和用户文本；先做类型与空值校验，再清理空白并按顺序构造消息，最后返回新的消息列表。' },
    { question_id: 'q2', answer: '关键条件分支用于拒绝空字符串和错误类型，因为下游要求非空文本；去掉后非法输入用例会失败并产生错误消息。' },
    { question_id: 'q3', answer: 'AIMessage 是对象而非字符串，正文放在 content 属性中，同时还能保存 token 用量、finish_reason 等响应元数据；直接 print 会看到对象结构。' },
  ]

  const sessionId = await page.evaluate(async ({ code, defenseAnswers }) => {
    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
    const started = await fetch('/api/capability/sessions', {
      method: 'POST',
      headers,
      body: JSON.stringify({ exercise_id: '1-1', force_new: true }),
    }).then(response => response.json())
    const id = started.data.id
    await fetch(`/api/capability/sessions/${id}/code-passed`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ code }),
    })
    await fetch(`/api/capability/sessions/${id}/defense`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ answers: defenseAnswers, ai_usage: '测试中未使用 AI 提示' }),
    })
    return id
  }, { code: correctCode, defenseAnswers: answers })

  await page.goto(`${BASE}/code-lab/1/1-1`)
  const progress = page.locator('.capability-progress')
  await expect(progress).toBeVisible()
  await expect(progress).toContainText('实验推进')
  await expect(progress).toContainText('原理答辩')
  await expect(progress).toContainText('故障修复')
  await expect(progress).toContainText('变式迁移')
  await expect(progress.locator('.flow-step.current')).toContainText('故障修复')
  await expect(page.getByText('学习复盘')).toHaveCount(0)

  await progress.getByRole('button', { name: /原理答辩/ }).click()
  await expect(page.getByText('查看评分、点评与标准答案')).toBeVisible()
  await expect(page.locator('.review-overview')).toContainText('原理答辩总分')
  await expect(page.locator('.review-card')).toHaveCount(3)
  await expect(page.getByText('标准参考答案').first()).toBeVisible()
  await page.screenshot({ path: 'test-results/capability-progress.png', fullPage: true })

  await page.evaluate(async id => {
    const token = localStorage.getItem('token')
    await fetch('/api/capability/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ exercise_id: '1-1', force_new: true, previous_session_id: id }),
    })
  }, sessionId)
})
