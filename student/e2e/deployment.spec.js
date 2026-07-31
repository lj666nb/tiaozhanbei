/**
 * Playwright E2E 测试 — 验证冷部署后学习资源和代码界面正常加载
 *
 * 运行方式:
 *   cd frontend && npx playwright test ../e2e/deployment.spec.js --headed
 *
 * 前置条件:
 *   1. 后端运行在 http://localhost:8000
 *   2. 前端运行在 http://localhost:5173 (dev) 或 http://localhost (production)
 */

import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';  // Vite dev server
const API_BASE = 'http://localhost:8000';

test.describe('AI Learning Platform — Deployment Verification', () => {

  test('Login with demo account', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.waitForSelector('input[type="text"], input[placeholder*="用户"]', { timeout: 10000 });

    // Fill login form
    const usernameInput = page.locator('input[type="text"], input').first();
    const passwordInput = page.locator('input[type="password"]');
    await usernameInput.fill('demo');
    await passwordInput.fill('demo123');

    // Click login button
    await page.click('button:has-text("登录"), button:has-text("登 录")');

    // Wait for navigation to dashboard
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Check token stored
    const token = await page.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeTruthy();
    console.log('  Login successful, token stored');
  });

  test('Exercise descriptions load in CodeLab left panel', async ({ page }) => {
    // Login first
    await page.goto(`${BASE}/login`);
    await page.locator('input[type="text"], input').first().fill('demo');
    await page.locator('input[type="password"]').fill('demo123');
    await page.click('button:has-text("登录")');
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Navigate to code lab for exercise 1-1
    await page.goto(`${BASE}/code-lab/1/1-1`);
    await page.waitForTimeout(3000); // Wait for Monaco editor + API

    // Check that left panel title is loaded (not the stub text)
    const problemTitle = page.locator('.card-title');
    await expect(problemTitle).toBeVisible({ timeout: 5000 });

    const titleText = await problemTitle.textContent();
    expect(titleText).not.toContain('加载中');
    expect(titleText).not.toContain('题目详情从后端加载');
    console.log(`  Problem title: ${titleText}`);

    // Check that description section exists
    const descSection = page.locator('.problem-section').first();
    await expect(descSection).toBeVisible({ timeout: 5000 });

    const descText = await descSection.textContent();
    expect(descText.length).toBeGreaterThan(20);
    console.log(`  Description length: ${descText.length} chars`);
  });

  test('Code execution works in CodeLab', async ({ page }) => {
    // Login
    await page.goto(`${BASE}/login`);
    await page.locator('input[type="text"], input').first().fill('demo');
    await page.locator('input[type="password"]').fill('demo123');
    await page.click('button:has-text("登录")');
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Navigate to code lab
    await page.goto(`${BASE}/code-lab/1/1-1`);
    await page.waitForTimeout(3000);

    // Click "Run Code" button
    const runButton = page.locator('button:has-text("运行代码")');
    await expect(runButton).toBeVisible({ timeout: 5000 });
    await runButton.click();

    // Wait for terminal output
    await page.waitForTimeout(3000);

    // Check terminal has output
    const terminal = page.locator('.terminal-body');
    const terminalText = await terminal.textContent();
    expect(terminalText.length).toBeGreaterThan(5);
    console.log(`  Terminal output: ${terminalText.substring(0, 100)}...`);
  });

  test('Resources page loads content', async ({ page }) => {
    // Login
    await page.goto(`${BASE}/login`);
    await page.locator('input[type="text"], input').first().fill('demo');
    await page.locator('input[type="password"]').fill('demo123');
    await page.click('button:has-text("登录")');
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Navigate to resources page
    await page.goto(`${BASE}/resources`);
    await page.waitForTimeout(2000);

    // Check that resource cards are displayed
    const pageContent = await page.textContent('body');
    expect(pageContent.length).toBeGreaterThan(100);
    console.log('  Resources page loaded');
  });

});
