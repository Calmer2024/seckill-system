import json
import random
import redis
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ================= 1. 真实的 MySQL 配置 =================
# 注意密码和数据库名要和 docker-compose.yml 保持绝对一致！
DATABASE_URL = "mysql+pymysql://root:418124@mysql:3306/seckill_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ================= 2. 定义真实的商品表结构 =================
class Product(Base):
    __tablename__ = "seckill_product"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    price = Column(Float)
    stock = Column(Integer)


# 【核心魔法】启动时让 SQLAlchemy 去 MySQL 里建表 (如果表不存在的话)
Base.metadata.create_all(bind=engine)

# ================= 3. 微服务初始化 =================
app = FastAPI(title="Product Service", description="真实的商品微服务")

# 1. 创建 Redis 连接池
# max_connections: 池子里最多能装多少个连接。比如 100 个，第 101 个请求来了就得排队等别人还回来。
# timeout: 建立连接的超时时间，防止网络卡顿导致程序一直死等。
pool = redis.ConnectionPool(
    host='redis',
    port=6379,
    decode_responses=True,
    max_connections=200,
    timeout=5
)

# 2. 让 Redis 客户端使用这个连接池去拿连接
redis_client = redis.Redis(connection_pool=pool)


# 依赖注入：获取数据库 Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================= 4. 高并发读接口 (真假结合) =================
@app.get("/api/products/{product_id}")
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    cache_key = f"product:{product_id}"

    try:
        # 1. 尝试从缓存读取
        cached_data = redis_client.get(cache_key)
        if cached_data:
            if cached_data == "NULL":  # 防御：缓存穿透
                raise HTTPException(status_code=404, detail="商品不存在")
            print(f"⚡ [命中缓存] 返回商品 {product_id}")
            return json.loads(cached_data)

        # 2. 缓存没命中，查询【真实的 MySQL 数据库】
        print(f"🐌 [未命中缓存] 正在查询真实 MySQL 数据库获取商品 {product_id}...")
        db_product = db.query(Product).filter(Product.id == product_id).first()

        if not db_product:
            # 防御：缓存穿透 (数据库也没有，塞入短暂的空值标记)
            redis_client.setex(cache_key, 60, "NULL")
            raise HTTPException(status_code=404, detail="商品不存在")

        # 3. 查到真实数据，转成字典写入缓存
        product_dict = {
            "id": db_product.id,
            "name": db_product.name,
            "price": db_product.price,
            "stock": db_product.stock
        }

        # 防御：缓存雪崩 (基础时间 + 随机抖动)
        base_expire = 3600
        random_jitter = random.randint(0, 600)
        redis_client.setex(cache_key, base_expire + random_jitter, json.dumps(product_dict))

        return product_dict

    except redis.ConnectionError:
        print("⚠️ Redis 连接失败，降级走真实数据库")
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            raise HTTPException(status_code=404, detail="商品不存在")
        return {"id": db_product.id, "name": db_product.name, "price": db_product.price, "stock": db_product.stock}