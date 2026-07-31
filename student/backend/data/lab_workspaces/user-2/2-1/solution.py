from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    customer_name = Column(String, nullable=False)
    product = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default='pending')


def setup_order_db(db_path='orders.db'):
    """创建 SQLite 引擎和表，返回 engine 和 Session 类。"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session

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