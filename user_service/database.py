import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("未找到 DATABASE_URL 环境变量，请检查 .env 文件！")

# 创建数据库引擎
# echo=True 可以在控制台打印生成的 SQL 语句，方便小白期调试，生产环境建议改为 False
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# 创建 Session 本地工厂，后续每一次 API 请求都会分配一个独立的 Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 所有数据表模型的基类
Base = declarative_base()

# FastAPI 依赖注入：在请求到达时创建数据库会话，请求结束后自动关闭
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()