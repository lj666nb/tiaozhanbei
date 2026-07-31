"""流式输出Playwright测试"""
import asyncio
import playwright
from playwright.async_api import async_playwright
import subprocess
import time
import sys

# 全局变量保存服务器进程
server_process = None

def start_server():
    """启动后端服务器"""
    global server_process
    print("启动后端服务器...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=r"d:\助学demo\backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # 等待服务器启动
    print("服务器已启动")

def stop_server():
    """停止后端服务器"""
    global server_process
    if server_process:
        print("停止服务器...")
        server_process.terminate()
        server_process.wait(timeout=5)
        print("服务器已停止")

async def test_streaming():
    """测试流式输出功能"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print("\n=== 测试流式输出功能 ===")

        # 1. 注册测试用户
        print("1. 注册测试用户...")
        try:
            reg_response = await page.request.post(
                "http://localhost:8000/api/auth/register",
                headers={"Content-Type": "application/json"},
                data='{"username":"streamtest_' + str(int(time.time())) + '","password":"test123456","nickname":"流测试","grade":"大一","learning_stage":"入门","learning_goal":"学习AI智能体"}'
            )
            reg_data = await reg_response.json()
            if reg_data.get("code") == 200 or reg_data.get("code") == 0:
                token = reg_data.get("data", {}).get("access_token", "")
                print(f"   - 注册成功")
            else:
                print(f"   - 注册响应: {reg_data}")
                # 尝试登录
                print("   - 尝试登录...")
                login_response = await page.request.post(
                    "http://localhost:8000/api/auth/login",
                    headers={"Content-Type": "application/json"},
                    data='{"username":"streamtest","password":"test123456"}'
                )
                login_data = await login_response.json()
                token = login_data.get("data", {}).get("access_token", "") if "data" in login_data else ""
                if not token:
                    print("   - ✗ 无法获取token，跳过API测试")
                    await browser.close()
                    return
        except Exception as e:
            print(f"   - 注册异常: {e}")
            await browser.close()
            return

        # 2. 测试流式API端点
        print("2. 测试流式API (POST /qa/ask/stream)...")

        chunks_received = []
        start_time = time.time()

        try:
            async with page.request.post(
                "http://localhost:8000/api/qa/ask/stream",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                data='{"question":"什么是智能体？","question_type":"text","explanation_level":"beginner"}'
            ) as response:
                print(f"   - 响应状态: {response.status}")

                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    print(f"   - Content-Type: {content_type}")

                    # 读取流式内容
                    async for chunk in response.content:
                        chunk_text = chunk.decode('utf-8')
                        chunks_received.append(chunk_text)
                        elapsed = time.time() - start_time
                        print(f"   - [{elapsed:.2f}s] 收到数据: {chunk_text[:80]}...")

                    print(f"\n   - 流式传输完成！共收到 {len(chunks_received)} 个数据块")

                    # 验证是否收到数据
                    all_content = "".join(chunks_received)
                    if "data:" in all_content:
                        print("   - ✓ 成功接收到SSE格式数据")
                    else:
                        print("   - ✗ 未收到SSE格式数据")

                    if time.time() - start_time < 30:
                        print("   - ✓ 流式响应时间正常")
                    else:
                        print("   - 流式响应时间较长")
                else:
                    error_text = await response.text()
                    print(f"   - 请求失败: {error_text}")

        except Exception as e:
            print(f"   - 测试异常: {str(e)}")

        # 3. 清理
        print("\n3. 关闭浏览器...")
        await browser.close()
        print("   - 测试完成")

async def run_tests():
    """运行所有测试"""
    start_server()
    try:
        await test_streaming()
    finally:
        stop_server()

if __name__ == "__main__":
    asyncio.run(run_tests())