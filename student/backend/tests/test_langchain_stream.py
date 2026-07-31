"""LangChain流式输出测试 - 详细版"""
import asyncio
import aiohttp
import json
import time

async def test_streaming_api():
    """测试流式API"""
    print("=== 测试LangChain流式API ===\n")

    # 1. 登录获取token
    print("1. 登录获取token...")
    login_data = {
        "username": "demo",
        "password": "demo123"
    }

    token = None

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/api/auth/login",
            headers={"Content-Type": "application/json"},
            json=login_data
        ) as resp:
            login_result = await resp.json()
            if login_result.get("code") == 200:
                token = login_result.get("data", {}).get("access_token", "")
                print(f"   - ✓ 登录成功")
            else:
                print(f"   - ✗ 登录失败")
                return

    # 2. 测试流式API
    print("\n2. 测试流式API (POST /api/qa/ask/stream)...")

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

                        # 解析并显示内容
                        if chunk_text.startswith("data: "):
                            data_str = chunk_text[6:].strip()
                            if data_str == "[DONE]":
                                print(f"   - [{elapsed:.2f}s] [DONE]")
                            else:
                                try:
                                    data = json.loads(data_str)
                                    if "error" in data:
                                        print(f"   - [{elapsed:.2f}s] 错误: {data['error']}")
                                    elif "content" in data:
                                        content = data['content']
                                        print(f"   - [{elapsed:.2f}s] content: {repr(content[:50])}")
                                    else:
                                        print(f"   - [{elapsed:.2f}s] raw: {data_str[:50]}")
                                except:
                                    print(f"   - [{elapsed:.2f}s] raw: {data_str[:50]}")

                    print(f"\n   - 流式传输完成！共收到 {len(chunks_received)} 个数据块")

                    # 统计
                    all_content = "".join(chunks_received)
                    error_count = all_content.count('"error"')
                    content_count = all_content.count('"content"')

                    if error_count > 0:
                        print(f"   - ⚠ 收到 {error_count} 个错误消息")
                    if content_count > 0:
                        print(f"   - ✓ 收到 {content_count} 个内容片段")

                else:
                    error_text = await resp.text()
                    print(f"   - ✗ 请求失败: {error_text}")

    except Exception as e:
        print(f"   - ✗ 测试异常: {str(e)}")

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_streaming_api())