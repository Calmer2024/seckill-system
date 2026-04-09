#ORM 模型定义
from sqlalchemy import Column, Float, Integer, String, Text
from app.core.database import Base


class Product(Base):
    __tablename__ = "seckill_product"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)
    category = Column(String(32), nullable=False, default="home", index=True)
    rating = Column(Float, nullable=False, default=4.8)
    review_count = Column(Integer, nullable=False, default=0)
    tags = Column(Text, nullable=False, default="[]")
    summary = Column(Text, nullable=False, default="")
    highlight = Column(String(80), nullable=False, default="")
    visual_icon = Column(String(80), nullable=False, default="lucide:package-open")
