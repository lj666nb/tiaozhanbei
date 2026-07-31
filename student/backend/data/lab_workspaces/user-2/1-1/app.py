# app.py —— 重构版：使用提取出的消息构造函数
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from solution import build_chat_messages   # ← 新增：导入我们提取的函数

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
if not api_key:
    raise RuntimeError("缺少 LLM_API_KEY，请先在 .env 中填写你的 API Key")

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=api_key,
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    temperature=0.2,
    timeout=30,
    max_retries=2,
)

# ← 重构点：用函数调用替代原来写死的消息列表
#   原来：messages = [{"role": "system", "content": "..."}, {"role": "user", ...}]
#   现在：一行函数调用，system_prompt 和 user_input 作为参数传入
messages = build_chat_messages(
    "你是一位耐心的 Python 助教，回答控制在 120 字以内。",
    "请用一个生活例子解释 AI Agent。",
)

response = model.invoke(messages)
print(response.content)