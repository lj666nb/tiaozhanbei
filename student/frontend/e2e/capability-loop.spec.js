import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1'

async function login(page) {
  await page.goto(`${BASE}/login`)
  await page.locator('input[placeholder="请输入用户名"]').fill('demo')
  await page.locator('input[placeholder="请输入密码"]').fill('demo123')
  await page.getByRole('button', { name: /进入学习空间/ }).click()
  await page.waitForURL('**/dashboard')
}

async function replaceEditorCode(page, code) {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE })
  await page.evaluate((value) => navigator.clipboard.writeText(value), code)
  await page.getByRole('textbox', { name: 'Editor content' }).focus()
  await page.keyboard.press('Control+A')
  await page.keyboard.press('Control+V')
}

test('代码通过后必须完成答辩与故障修复，最终生成能力报告', async ({ page }) => {
  await login(page)

  await page.goto(`${BASE}/code-lab`)
  await expect(page.locator('.module-card')).toHaveCount(1)
  await expect(page.locator('.module-card')).toContainText('旗舰实战：智能客服工单分派')

  // 新建独立验证会话，避免历史演示数据影响状态。
  await page.evaluate(async () => {
    const token = localStorage.getItem('token')
    await fetch('/api/capability/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ exercise_id: '7-1', force_new: true }),
    })
  })

  await page.goto(`${BASE}/code-lab/7/7-1`)
  await expect(page.locator('.evidence-rail')).toBeVisible()
  await expect(page.locator('.rail-stage.active')).toContainText('功能正确')

  const correctCode = `PRIORITIES = ("low", "normal", "high", "urgent")
SLA = {"low": 480, "normal": 120, "high": 30, "urgent": 15}

def dispatch_ticket(ticket, agents, now_minutes):
    if not isinstance(ticket, dict) or not isinstance(agents, list):
        raise ValueError("结构非法")
    required_ticket = ("id", "category", "priority", "vip", "created_at")
    if not all(key in ticket for key in required_ticket):
        raise ValueError("ticket 缺少字段")
    if (not isinstance(ticket["id"], str) or not ticket["id"]
            or not isinstance(ticket["category"], str) or not ticket["category"]
            or ticket["priority"] not in PRIORITIES or not isinstance(ticket["vip"], bool)):
        raise ValueError("ticket 字段非法")
    created_at = ticket["created_at"]
    if (not isinstance(created_at, int) or isinstance(created_at, bool) or created_at < 0
            or not isinstance(now_minutes, int) or isinstance(now_minutes, bool) or now_minutes < created_at):
        raise ValueError("时间非法")
    priority_index = PRIORITIES.index(ticket["priority"])
    if ticket["vip"]:
        priority_index += 1
    if now_minutes - created_at >= 60:
        priority_index += 1
    effective_priority = PRIORITIES[min(priority_index, len(PRIORITIES) - 1)]
    eligible = []
    for item in agents:
        required_agent = ("id", "skills", "online", "active_cases", "capacity")
        if not isinstance(item, dict) or not all(key in item for key in required_agent):
            raise ValueError("客服结构非法")
        active, capacity = item["active_cases"], item["capacity"]
        if (not isinstance(item["id"], str) or not item["id"] or not isinstance(item["skills"], list)
                or not isinstance(item["online"], bool) or not isinstance(active, int) or isinstance(active, bool)
                or active < 0 or not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0):
            raise ValueError("客服字段非法")
        if item["online"] and ticket["category"] in item["skills"] and active < capacity:
            eligible.append(item)
    selected = min(eligible, key=lambda item: (item["active_cases"] / item["capacity"], item["id"])) if eligible else None
    return {
        "ticket_id": ticket["id"], "status": "assigned" if selected else "queued",
        "agent_id": selected["id"] if selected else None, "effective_priority": effective_priority,
        "sla_minutes": SLA[effective_priority],
        "reason": "matched_skill_and_capacity" if selected else "no_eligible_agent",
    }
`

  await replaceEditorCode(page, correctCode)
  await page.getByRole('button', { name: '提交代码' }).click()

  await expect(page.getByText('代码已通过，能力尚未验证')).toBeVisible({ timeout: 30000 })
  const answers = [
    'dispatch_ticket 的输入参数是工单、客服列表和当前时间；处理步骤是校验、升级优先级、过滤候选人、比较负载率，输出并返回稳定的分派字典结果。',
    'for 循环在客服列表遍历结束时终止；输入为空属于边界情况，会得到空候选并排队。规模扩大时复杂度近似线性，需要关注排序或扫描的性能。',
    '面对异常或边界输入，我会在函数入口的校验层增加保护，明确修改位置，并补充测试用例验证 ValueError、返回结构以及输入没有被修改。',
  ]
  const textareas = page.locator('.defense-question textarea')
  for (let index = 0; index < answers.length; index += 1) {
    await textareas.nth(index).fill(answers[index])
  }
  await page.getByRole('button', { name: /提交答辩并进入故障修复/ }).click()

  await expect(page.locator('.repair-brief')).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.rail-stage.active')).toContainText('故障修复')
  await replaceEditorCode(page, correctCode)
  await page.locator('.repair-brief textarea').fill(
    '故障根因是关键返回值被改成空值，导致测试读取不到字典；我恢复了返回表达式并重新运行全部用例。',
  )
  await page.getByRole('button', { name: '提交故障修复并判题' }).click()

  await expect(page.getByText('能力证据报告')).toBeVisible({ timeout: 30000 })
  await expect(page.locator('.verified-badge')).toHaveText('能力已验证')
  await expect(page.locator('.dimension-card')).toHaveCount(4)
  await page.waitForTimeout(1200)
  await page.screenshot({ path: 'test-results/capability-loop.png', fullPage: true })
})
