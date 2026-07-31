import os, json
import sqlalchemy
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from solution import setup_order_db, query_orders, Order

load_dotenv()

# ── 初始化数据库 ──
engine, Session = setup_order_db("orders.db")
session = Session()

# 插入测试数据（仅首次运行）
if session.query(Order).count() == 0:
    session.add_all([
        Order(customer_name="张三", product="Python教程", amount=99.0, status="paid"),
        Order(customer_name="李四", product="AI入门", amount=199.0, status="pending"),
        Order(customer_name="王五", product="数据分析", amount=149.0, status="paid"),
        Order(customer_name="赵六", product="机器学习实战", amount=259.0, status="paid"),
        Order(customer_name="孙七", product="深度学习", amount=89.0, status="cancelled"),
    ])
    session.commit()
    print("测试数据已插入")

# ── LangChain 模型 ──
model = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    temperature=0.2,
)

# ── AI 辅助查询 ──
messages = [
    SystemMessage(content="你是一个订单查询助手。请根据用户输入，输出 JSON 格式的过滤条件：{\"status\": \"...\"}、{\"customer_name\": \"...\"}、{\"min_amount\": ...} 或 {}。只输出 JSON。"),
    HumanMessage(content="查询已支付的订单"),
]
response = model.invoke(messages)
print("AI 解析过滤条件:", response.content)

# 用 solution 的 query_orders 实际查询数据库
paid_orders = query_orders(session, status="paid")
for o in paid_orders:
    print(f"  订单{o['id']}: {o['customer_name']} - {o['product']} ¥{o['amount']}")

session.close()
