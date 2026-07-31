# 项目 4：用 SQLAlchemy 构建订单数据库

## 一、我们要解决什么问题

前三个项目让你跑通了 AI 对话的完整链路。现在我们要给客服 Agent 接上「真实数据」——**订单信息**。

想象一个真实的客服场景：

> 用户问：「我的订单发了吗？」→ Agent 需要**查数据库**才能回答。

如果没有数据库，Agent 只能编造答案（幻觉）。有了数据库，Agent 的回答就有了**可验证的事实基础**。

### 什么是 ORM？

> 🧠 **关键概念：ORM（Object-Relational Mapping）** 让你用 Python 类来操作数据库表，而不用手写 SQL 字符串。你定义 `class Order(Base)`，SQLAlchemy 自动把它映射到 `orders` 表。
>
> **类比**：就像翻译官——你用 Python 语法说「查所有已支付订单」，ORM 帮你翻译成 SQL 发给数据库，再把结果翻译回 Python 对象。

```
你的代码:   session.query(Order).filter(Order.status == 'paid')
              ↓ SQLAlchemy 翻译
SQL:        SELECT * FROM orders WHERE status = 'paid'
              ↓ SQLite 执行
结果:       [(1, '张三', 'Python教程', 99.0, 'paid'), ...]
              ↓ SQLAlchemy 映射
Python:     [<Order id=1 customer='张三' ...>, ...]
```

### 本节目标

1. **理解 ORM**：为什么不用手写 SQL
2. **定义模型**：用 SQLAlchemy 声明式语法定义 `Order` 类
3. **创建数据库**：`create_engine` + `Base.metadata.create_all`
4. **实现查询**：按状态、客户、金额组合过滤，返回字典列表

---

## 二、开始前：搭建本节项目

创建 `requirements.txt`、`.env`、`solution.py`、`app.py`。本节新增 `sqlalchemy` 依赖。

<!-- lab-check:structure -->

```bash
python -m venv .venv
pip install -r requirements.txt
```

<!-- lab-check:environment -->
<!-- lab-check:dependencies -->

---

## 三、定义 Order 模型

### 3.1 最小可运行示例

先用 Python 交互环境验证模型定义能否正常创建表：

```python
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    customer_name = Column(String, nullable=False)
    product = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default='pending')

# 验证：创建内存数据库
engine = create_engine('sqlite:///test_orders.db')
Base.metadata.create_all(engine)
print('表创建成功！')
```

<!-- lab-check:first_llm_call -->

> 🧠 **声明式基类 `Base`**：所有模型都继承自它，SQLAlchemy 通过它知道哪些类是数据库表。`__tablename__` 指定表名，`Column` 定义列的类型和约束。

### 3.2 列类型速查

| 列 | 类型 | 说明 |
|-----|------|------|
| `id` | `Integer, primary_key=True` | 主键，自动递增 |
| `customer_name` | `String, nullable=False` | 不能为空 |
| `product` | `String, nullable=False` | 商品名 |
| `amount` | `Float, nullable=False` | 订单金额 |
| `status` | `String, default='pending'` | 默认值为 pending |

---

## 四、实现 setup_order_db

### 4.1 创建引擎和表

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def setup_order_db(db_path='orders.db'):
    """创建 SQLite 引擎和表，返回 engine 和 Session 类。"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
```

> 🧠 **`create_engine`**：创建数据库连接。SQLite 用文件路径（`sqlite:///orders.db`），文件不存在时自动创建。
>
> 🧠 **`sessionmaker`**：工厂函数，每次调用 `Session()` 都创建一个新会话——相当于一次「数据库对话」。会话结束时 `commit()` 提交修改或 `rollback()` 撤销。

### 4.2 为什么返回 Session 类而不是实例？

每个查询应该创建自己的会话实例，用完即关。返回 `Session` 类（工厂）让调用方自己管理会话生命周期。

```python
engine, Session = setup_order_db('orders.db')
session = Session()         # 创建会话
# ... 查询 ...
session.close()             # 关闭会话
```

<!-- lab-check:implementation -->

---

## 五、实现 query_orders

### 5.1 基础查询

```python
def query_orders(session, **filters):
    """按可选条件查询订单。
    
    支持的过滤器:
        status: 订单状态 ('paid', 'pending', 'cancelled')
        customer_name: 客户名
        min_amount: 最小金额
    
    Returns:
        list[dict]: 订单字典列表
    """
    query = session.query(Order)
    
    if 'status' in filters:
        query = query.filter(Order.status == filters['status'])
    if 'customer_name' in filters:
        query = query.filter(Order.customer_name == filters['customer_name'])
    if 'min_amount' in filters:
        query = query.filter(Order.amount >= filters['min_amount'])
    
    return [
        {
            'id': order.id,
            'customer_name': order.customer_name,
            'product': order.product,
            'amount': order.amount,
            'status': order.status,
        }
        for order in query.all()
    ]
```

### 5.2 查询逻辑解析

```text
session.query(Order)              =>  SELECT * FROM orders
  .filter(Order.status == 'paid') =>  WHERE status = 'paid'
  .filter(Order.amount >= 100)    =>  AND amount >= 100
  .all()                          =>  执行查询，返回列表
```

> 🧠 **链式 `.filter()`**：每次 `.filter()` 返回新的查询对象，多个 filter 之间是 **AND** 关系。如果想用 OR，用 `or_()`。

### 5.3 返回字典而非 ORM 对象

```python
# 不推荐：返回 Order 对象（与数据库会话绑定，会话关闭后访问属性可能出错）
# 推荐：返回普通字典（独立、可序列化、随时可用）
return [{'id': o.id, 'customer_name': o.customer_name, 'product': o.product, 'amount': o.amount, 'status': o.status} for o in query.all()]
```

---

## 六、接入可运行应用

将 `solution.py` 中的函数导入 `app.py`，完成端到端验证：

```python
from solution import setup_order_db, query_orders, Order

engine, Session = setup_order_db('orders.db')
session = Session()

# 插入测试数据（仅首次运行）
from solution import Base
Base.metadata.create_all(engine)
if session.query(Order).count() == 0:
    session.add_all([
        Order(customer_name='张三', product='Python教程', amount=99.0, status='paid'),
        Order(customer_name='李四', product='AI入门', amount=199.0, status='pending'),
    ])
    session.commit()

# 查询示例
paid_orders = query_orders(session, status='paid')
for o in paid_orders:
    print(f"订单{o['id']}: {o['customer_name']} - {o['product']} ¥{o['amount']}")

session.close()
```

<!-- lab-check:integration -->

---

## 七、AI 工程验收

运行 `python -m lab_test` 进行最终验收。

<!-- lab-check:acceptance -->

---

## 八、常见问题

### Q: SQLite 和 PostgreSQL 有什么区别？
**A:** SQLite 是文件数据库（一个 `.db` 文件），不需要额外安装服务，适合学习和单机应用。PostgreSQL 是网络数据库服务器，适合生产环境。SQLAlchemy 的好处是：切换数据库只需改一行 `create_engine` 的 URL，代码不用动。

### Q: 为什么不用 `session.execute(text("SELECT ..."))` 手写 SQL？
**A:** 可以，但不推荐作为主要方式。ORM 的好处：编译时检查列名是否正确（手写 SQL 字符串拼错要到运行时才知道）、自动防 SQL 注入、数据库切换方便。

### Q: `nullable=False` 是必须的吗？
**A:** 在项目 4 的判题测试中没有严格要求，但在真实项目中强烈建议：它能防止脏数据（比如缺少客户名的订单）进入数据库。这就是**数据完整性约束**。

---

## 九、本节要点回顾

| 概念 | 一句话解释 |
|------|-----------|
| ORM | Python 类 ↔ 数据库表的映射 |
| `declarative_base()` | 创建模型基类 |
| `Column` | 定义表的列 |
| `create_engine` | 连接数据库 |
| `sessionmaker` | 创建会话工厂 |
| `.filter()` | 添加查询条件 |
| `.all()` | 执行查询并返回全部结果 |

**下一步：** 项目 5 将教你如何用提示模板把查询到的订单信息格式化成用户可以看懂的回复。
