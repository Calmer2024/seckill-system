from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base

class User(Base):
    """
    用户模型，对应 seckill_user 数据库中的 users 表
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="用户唯一ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="加密后的密码哈希值")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="账号创建时间")