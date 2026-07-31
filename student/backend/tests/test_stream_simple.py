"""流式API直接测试（使用aiohttp）"""
import asyncio
import aiohttp
import json
import time

async def test_streaming_api():
    """测试流式API"""
    print("=== 测试流式API ===\n")

    # 1. 注册测试用户
    print("1. 注册测试用户...")
    register_data = {
        "username": f"streamtest_{int(time.time())}",
        "password": "test123456",
        "nickname": "流测试",
        "grade": "大一",
        "learning_stage": "入门",
        "learning_goal": "学习AI智能体"
    }

    token = None

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/api/auth/register",
            headers={"Content-Type": "application/json"},
            json=register_data
        ) as resp:
            reg_result = await resp.json()
            print(f"   - 注册响应: {reg_result}")

            if reg_result.get("code") == 200:
                token = reg_result.get("data", {}).get("access_token", "")
                print(f"   - ✓ 注册成功")
            else:
                # 尝试登录
                print("   - 注册失败，尝试登录...")
                login_data = {"username": "streamtest", "password": "test123456"}
                async with session.post(
                    "http://localhost:8000/api/auth/login",
                    headers={"Content-Type": "application/json"},
                    json=login_data
                ) as login_resp:
                    login_result = await login_resp.json()
                    print(f"   - 登录响应: {login_result}")
                    if login_result.get("code") == 200:
                        token = login_result.get("data", {}).get("access_token", "")
                        print(f"   - ✓ 登录成功")

            if not token:
                print("   - ✗ 无法获取token")
                return

            print(f"   - Token获取成功: {token[:20]}...")

    # 2. 测试流式API
    print("\n2. 测试流式API (POST /qa/ask/stream)...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    request_data = {
        "question": "什么是智能体？",
        "question_type": "text",
        "explanation_level": "beginner"
    }

    chunks_received = []
    start_time = time.time()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/api/qa/ask/stream",
                headers=headers,
                json=request_data
            ) as resp:
                print(f"   - 响应状态: {resp.status}")
                print(f"   - Content-Type: {resp.headers.get('content-type', '')}")

                if resp.status == 200:
                    async for chunk in resp.content:
                        chunk_text = chunk.decode('utf-8')
                        chunks_received.append(chunk_text)
                        elapsed = time.time() - start_time
                        # 显示前80个字符
                        display_text = chunk_text[:80].replace('\n', ' ')
                        print(f"   - [{elapsed:.2f}s] {display_text}...")

                    print(f"\n   - 流式传输完成！共收到 {len(chunks_received)} 个数据块")

                    # 验证
                    all_content = "".join(chunks_received)
                    if "data:" in all_content:
                        print("   - ✓ 成功接收到SSE格式数据")
                    else:
                        print("   - ✗ 未收到SSE格式数据")

                    elapsed = time.time() - start_time
                    if elapsed < 30:
                        print(f"   - ✓ 流式响应时间正常 ({elapsed:.2f}s)")
                    else:
                        print(f"   - 流式响应时间: {elapsed:.2f}s")
                else:
                    error_text = await resp.text()
                    print(f"   - ✗ 请求失败: {error_text}")

    except Exception as e:
        print(f"   - ✗ 测试异常: {str(e)}")

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_streaming_api())