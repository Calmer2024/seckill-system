#ORM 模型定义
from sqlalchemy import Column, Integer, String, Float
from app.core.database import Base


class Product(Base):
    __tablename__ = "seckill_product"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)
