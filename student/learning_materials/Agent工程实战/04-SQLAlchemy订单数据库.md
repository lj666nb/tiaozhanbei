# 项目 4：用 SQLAlchemy 构建订单数据库

## 一、我们要解决什么问题

前三个项目让你跑通了 AI 对话的完整链路。现在我们要给客服 Agent 接上「真实数据」——**订单信息**。

想象一个真实的客服场景：

> 用户问：「我的订单发了吗？」→ Agent 需要**查数据库**才能回答。

如果没有数据库，Agent 只能编造答案（幻觉）。有了数据库，Agent 的回答就有了**可验证的事实基础**。

> 🧠 **这个数据库很特别**：它不是你写完就扔的一次性练习。项目 5（提示模板）、项目 6（工具调用）、项目 7（工具 Agent）以及最终的毕业项目，**全部都会导入并查询你在这里创建的同一个 `orders.db` 文件**。你正在构建的是整个订单客服系统的数据基础层。

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
2. **定义模型**：用 SQLAlchemy 声明式语法定义包含 11 列的 `Order` 类
3. **创建数据库**：`create_engine` + `Base.metadata.create_all`，生成持久化的 `orders.db` 文件
4. **实现查询**：支持 7 种过滤器（编号、客户、类别、状态、快递、金额范围），返回字典列表

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

以下代码放入 `solution.py`（**只放定义，不放执行语句**——判题安全检查不允许模块顶层有裸函数调用）：

```python
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    order_id = Column(String(20), unique=True, nullable=False)
    customer_name = Column(String(50), nullable=False)
    customer_phone = Column(String(20))
    product = Column(String(100), nullable=False)
    category = Column(String(30), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    carrier = Column(String(30))
    eta = Column(String(20))
    created_at = Column(String(20), nullable=False)
```

在终端中交互验证模型定义是否正确：

```bash
python -c "
from solution import Base, Order
from sqlalchemy import create_engine
engine = create_engine('sqlite:///orders.db')
Base.metadata.create_all(engine)
print('表创建成功！orders.db 已生成')
"
```

<!-- lab-check:first_llm_call -->

> 🧠 **声明式基类 `Base`**：所有模型都继承自它，SQLAlchemy 通过它知道哪些类是数据库表。`__tablename__` 指定表名，`Column` 定义列的类型和约束。

### 3.2 列类型速查

| 列 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| `id` | `Integer, primary_key=True` | NOT NULL | 主键，自动递增 |
| `order_id` | `String(20), unique=True` | NOT NULL, UNIQUE | 业务编号，如 `ORD-20260730-0001` |
| `customer_name` | `String(50)` | NOT NULL | 客户姓名 |
| `customer_phone` | `String(20)` | 可空 | 联系电话（可空——不是所有渠道都需要） |
| `product` | `String(100)` | NOT NULL | 商品名称 |
| `category` | `String(30)` | NOT NULL | 商品类别：图书 / 电子产品 / 服装 / 食品 等 |
| `amount` | `Float` | NOT NULL | 订单金额（元） |
| `status` | `String(20)` | NOT NULL, default='pending' | 状态：pending → paid → shipped → delivered；也可能 refunding → refunded 或 cancelled |
| `carrier` | `String(30)` | 可空 | 快递公司（发货后才填充），如 顺丰速运 / 中通快递 / 京东物流 |
| `eta` | `String(20)` | 可空 | 预计送达日期（发货后才填充） |
| `created_at` | `String(20)` | NOT NULL | 订单创建日期（ISO 格式） |

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

以下为使用示例（在 `app.py` 或终端中运行，**不要放入 solution.py**）：

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
        order_id:       订单编号，精确匹配
        customer_name:  客户名，模糊匹配（LIKE %xxx%）
        category:       商品类别，精确匹配
        status:         订单状态，精确匹配
        carrier:        快递公司，精确匹配
        min_amount:     最低金额（>=）
        max_amount:     最高金额（<=）
    
    Returns:
        list[dict]: 订单字典列表（含全部11列）
    """
    query = session.query(Order)
    
    if 'order_id' in filters:
        query = query.filter(Order.order_id == filters['order_id'])
    if 'customer_name' in filters:
        query = query.filter(Order.customer_name.like(f"%{filters['customer_name']}%"))
    if 'category' in filters:
        query = query.filter(Order.category == filters['category'])
    if 'status' in filters:
        query = query.filter(Order.status == filters['status'])
    if 'carrier' in filters:
        query = query.filter(Order.carrier == filters['carrier'])
    if 'min_amount' in filters:
        query = query.filter(Order.amount >= filters['min_amount'])
    if 'max_amount' in filters:
        query = query.filter(Order.amount <= filters['max_amount'])
    
    return [
        {
            'id': order.id,
            'order_id': order.order_id,
            'customer_name': order.customer_name,
            'customer_phone': order.customer_phone,
            'product': order.product,
            'category': order.category,
            'amount': order.amount,
            'status': order.status,
            'carrier': order.carrier,
            'eta': order.eta,
            'created_at': order.created_at,
        }
        for order in query.all()
    ]
```

### 5.2 查询逻辑解析

```text
session.query(Order)              =>  SELECT * FROM orders
  .filter(Order.status == 'paid') =>  WHERE status = 'paid'
  .filter(Order.amount >= 100)    =>  AND amount >= 100
  .filter(Order.category == '图书') =>  AND category = '图书'
  .all()                          =>  执行查询，返回列表
```

> 🧠 **链式 `.filter()`**：每次 `.filter()` 返回新的查询对象，多个 filter 之间是 **AND** 关系。客户名使用 `.like()` 实现模糊搜索。
>
> 🧠 **min_amount 和 max_amount 可以组合**：同时传入 `min_amount=100, max_amount=200` 就是金额在 100~200 之间的订单。

### 5.3 返回字典而非 ORM 对象

```python
# 不推荐：返回 Order 对象（与数据库会话绑定，会话关闭后访问属性可能出错）
# 推荐：返回普通字典（独立、可序列化、随时可用）
return [
    {'id': o.id, 'order_id': o.order_id, 'customer_name': o.customer_name,
     'product': o.product, 'category': o.category, 'amount': o.amount,
     'status': o.status, 'carrier': o.carrier, 'eta': o.eta, ...}
    for o in query.all()
]
```

---

## 六、接入可运行应用

将 `solution.py` 中的函数导入 `app.py`，完成端到端验证：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from solution import setup_order_db, query_orders, Order, Base

engine, Session = setup_order_db('orders.db')
session = Session()

# 插入测试数据（仅首次运行）
Base.metadata.create_all(engine)
if session.query(Order).count() == 0:
    session.add_all([
        Order(order_id='ORD-20260730-0001', customer_name='张三', customer_phone='13800001111',
              product='Python编程从入门到实践', category='图书', amount=89.00, status='delivered',
              carrier='顺丰速运', eta='2026-07-25', created_at='2026-07-20'),
        Order(order_id='ORD-20260730-0002', customer_name='李四', customer_phone='13800002222',
              product='AI智能体开发实战', category='图书', amount=199.00, status='shipped',
              carrier='中通快递', eta='2026-08-05', created_at='2026-07-28'),
        Order(order_id='ORD-20260730-0003', customer_name='王五', customer_phone='13800003333',
              product='机械键盘K850', category='电子产品', amount=459.00, status='paid',
              carrier=None, eta=None, created_at='2026-07-30'),
        Order(order_id='ORD-20260730-0004', customer_name='赵六', customer_phone='13800004444',
              product='蓝牙耳机Pro', category='电子产品', amount=299.00, status='refunding',
              carrier=None, eta=None, created_at='2026-07-29'),
        Order(order_id='ORD-20260730-0005', customer_name='孙七', customer_phone='13800005555',
              product='有机绿茶礼盒', category='食品', amount=128.00, status='pending',
              carrier=None, eta=None, created_at='2026-08-01'),
        Order(order_id='ORD-20260730-0006', customer_name='周八', customer_phone='13800006666',
              product='Python教程进阶版', category='图书', amount=149.00, status='shipped',
              carrier='京东物流', eta='2026-08-03', created_at='2026-07-31'),
        Order(order_id='ORD-20260730-0007', customer_name='吴九', customer_phone='13800007777',
              product='智能手表S3', category='电子产品', amount=899.00, status='delivered',
              carrier='顺丰速运', eta='2026-07-22', created_at='2026-07-18'),
        Order(order_id='ORD-20260730-0008', customer_name='郑十', customer_phone='13800008888',
              product='纯棉T恤三件装', category='服装', amount=199.00, status='cancelled',
              carrier=None, eta=None, created_at='2026-08-02'),
        Order(order_id='ORD-20260730-0009', customer_name='张三', customer_phone='13800001111',
              product='数据分析实战', category='图书', amount=79.00, status='paid',
              carrier=None, eta=None, created_at='2026-08-01'),
        Order(order_id='ORD-20260730-0010', customer_name='李白', customer_phone='13800009999',
              product='深度学习框架', category='图书', amount=259.00, status='refunded',
              carrier=None, eta=None, created_at='2026-07-15'),
    ])
    session.commit()
    print(f"已插入 {session.query(Order).count()} 条订单数据。")

# 查询示例
paid_orders = query_orders(session, status='paid')
for o in paid_orders:
    print(f"[{o['order_id']}] {o['customer_name']} - {o['product']} ¥{o['amount']}")

# 演示新过滤器：按快递公司查询
shipped = query_orders(session, carrier='顺丰速运')
print(f"\n顺丰配送的订单：{len(shipped)} 条")
for o in shipped:
    print(f"  {o['order_id']}: {o['product']} → 预计 {o['eta']} 送达")

session.close()
```

<!-- lab-check:integration -->

---

## 七、AI 工程验收

运行 `python -m lab_test` 进行最终验收。

<!-- lab-check:acceptance -->

---

## 八、常见问题

### Q: 这个数据库在后续项目中怎么用？
**A:** 项目 5（提示模板）、项目 6（工具调用）、项目 7（工具 Agent）和毕业项目（端到端客服），**全部**会导入并查询你现在创建的 `orders.db`。这就是为什么我们要用真实数据建模——它不是一次性的练习题，而是整个客服系统的数据基础层。后续项目的教程会教你用 `sqlite:///../2-1/orders.db` 引用这个数据库。

### Q: SQLite 和 PostgreSQL 有什么区别？
**A:** SQLite 是文件数据库（一个 `.db` 文件），不需要额外安装服务，适合学习和单机应用。PostgreSQL 是网络数据库服务器，适合生产环境。SQLAlchemy 的好处是：切换数据库只需改一行 `create_engine` 的 URL，代码不用动。

### Q: 为什么不用 `session.execute(text("SELECT ..."))` 手写 SQL？
**A:** 可以，但不推荐作为主要方式。ORM 的好处：编译时检查列名是否正确（手写 SQL 字符串拼错要到运行时才知道）、自动防 SQL 注入、数据库切换方便。

### Q: `nullable=False` 是必须的吗？
**A:** 在项目 4 的判题测试中没有严格要求，但在真实项目中强烈建议：它能防止脏数据（比如缺少客户名的订单）进入数据库。这就是**数据完整性约束**。
**注意**：`customer_phone`、`carrier`、`eta` 设计为可空——不是所有订单都需要电话（如微信小程序订单），快递信息也只在发货后才填充。这是真实业务建模的体现。

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
