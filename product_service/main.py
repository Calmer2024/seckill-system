import json
import random
import redis
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Product Service", description="商品微服务")

# 连接 Redis
# 注意：这里的 host='cache' 是因为我们稍后在 docker-compose.yml 里把 Redis 容器命名为了 cache
# 如果你现在想在本地直接运行测试，可以临时把 'cache' 改成 'localhost'
redis_client = redis.Redis(host='cache', port=6379, decode_responses=True)

# 模拟数据库里的商品数据 (为了省去配置 MySQL 的时间，我们先用假数据测试高并发)
MOCK_DB = {
    1: {"id": 1, "name": "iPhone 16 Pro", "price": 7999, "stock": 100},
    2: {"id": 2, "name": "MacBook Air M3", "price": 8999, "stock": 50}
}


@app.get("/api/products/{product_id}")
def get_product_detail(product_id: int):
    cache_key = f"product:{product_id}"

    try:
        # 1. 尝试从缓存读取
        cached_data = redis_client.get(cache_key)
        if cached_data:
            # 【防御：缓存穿透】如果是空值标记，直接返回 404
            if cached_data == "NULL":
                raise HTTPException(status_code=404, detail="商品不存在")
            # 打印日志方便我们稍后压测时观察是否走了缓存
            print(f"⚡ [命中缓存] 返回商品 {product_id}")
            return json.loads(cached_data)

        # 2. 缓存没命中，查询“数据库”
        print(f"🐌 [未命中缓存] 正在查询数据库获取商品 {product_id}...")
        db_product = MOCK_DB.get(product_id)

        if not db_product:
            # 【防御：缓存穿透】数据库也没有，塞入短暂的空值标记
            redis_client.setex(cache_key, 60, "NULL")
            raise HTTPException(status_code=404, detail="商品不存在")

        # 3. 查到数据，写入缓存
        # 【防御：缓存雪崩】基础过期时间(1小时) + 随机抖动(0~10分钟)
        base_expire = 3600
        random_jitter = random.randint(0, 600)
        redis_client.setex(cache_key, base_expire + random_jitter, json.dumps(db_product))

        return db_product

    except redis.ConnectionError:
        # 降级处理：如果 Redis 挂了，直接走数据库，保证系统可用
        print("⚠️ Redis 连接失败，降级走数据库")
        db_product = MOCK_DB.get(product_id)
        if not db_product:
            raise HTTPException(status_code=404, detail="商品不存在")
        return db_product