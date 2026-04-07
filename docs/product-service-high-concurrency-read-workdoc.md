# 商品服务高并发读功能工作文档

## 1. 目标

本次改造围绕“高并发读”场景落地了以下能力：

- 基于 DDD 思想重构 `product_service`，将接口层、应用服务层、领域接口层、基础设施层解耦。
- 引入 Redis 商品详情/列表缓存。
- 处理缓存穿透、缓存击穿、缓存雪崩。
- 提供 MySQL 读写分离配置与主从初始化脚本。
- 增加统一异常处理、请求参数校验、结构化日志。
- 保留兼容入口，避免已有调用方大面积联动修改。

## 2. 分层设计

### Controller

- 文件：`product_service/app/api/routes.py`
- 责任：只负责接收 HTTP 请求、参数校验和调用应用服务，不直接操作数据库和缓存。

### Service Interface

- 文件：`product_service/app/application/interfaces/product_query_service.py`
- 责任：定义查询商品列表、商品详情、缓存预热、读写路由检查等能力。

### Service Impl

- 文件：`product_service/app/application/services/product_query_service_impl.py`
- 责任：编排缓存、仓储、降级、互斥锁、日志与业务异常。

### DTO

- 文件：`product_service/app/application/dto/product_dto.py`
- 责任：统一输入输出模型，利用 Pydantic 做类似 Hibernate Validator 的参数校验。

### Domain

- 文件：`product_service/app/domain/entities/product.py`
- 文件：`product_service/app/domain/repositories/product_repository.py`
- 文件：`product_service/app/domain/services/cache_service.py`
- 责任：定义核心领域对象与抽象接口，不依赖 FastAPI/Redis/SQLAlchemy 细节。

### Infrastructure

- 文件：`product_service/app/infrastructure/database/product_repository.py`
- 文件：`product_service/app/infrastructure/cache/redis_cache_service.py`
- 文件：`product_service/app/infrastructure/logging/logger.py`
- 责任：实现数据库访问、Redis 缓存访问、结构化日志输出。

## 3. 核心并发设计

### 3.1 缓存穿透

- 商品不存在时写入空值占位 `__NULL__`。
- 短 TTL 防止无效商品 ID 持续打到数据库。

### 3.2 缓存击穿

- 热点 key 回源时使用 Redis 分布式互斥锁。
- 只允许一个线程重建缓存，其余线程短暂等待后重试。
- 锁释放使用 Lua 脚本，避免误删他人锁。

### 3.3 缓存雪崩

- 列表缓存与详情缓存统一增加 TTL 抖动。
- 预热接口支持将默认列表页和详情页提前灌入 Redis。

### 3.4 依赖超时与降级

- Redis 连接设置了连接超时和读写超时。
- 读库查询失败时，可回退到写库。
- 缓存不可用时，服务仍可直接走数据库返回结果。

## 4. 读写分离实现

### 4.1 代码侧

- `DATABASE_URL` 指向主库。
- `READ_DATABASE_URL` 指向从库。
- `get_write_db()` 和 `get_read_db()` 提供双 Session 注入。
- `SqlAlchemyProductRepository` 默认读从库，必要时回退主库。

### 4.2 容器侧

- `docker-compose.yml` 中新增：
  - `mysql-primary`
  - `mysql-replica`
  - `mysql-replica-init`
- `infra/mysql/primary/init/01-create-replication-user.sql` 用于创建复制账号。
- `infra/mysql/scripts/setup-replica.sh` 用于启动后配置 GTID 主从复制。

### 4.3 验证接口

- `GET /api/internal/db-route-check`
- 返回读角色、写角色、读库名、写库名、商品数量、是否启用副本。

## 5. 对外接口

### 获取商品列表

- `GET /api/products?page=1&size=20&keyword=phone`

### 搜索商品

- `GET /api/products/search?keyword=phone&limit=10`

### 获取商品详情

- `GET /api/products/{product_id}`

### 手动缓存预热

- `POST /api/products/prewarm`

### 读写分离检查

- `GET /api/internal/db-route-check`

## 6. 错误处理与日志

### 统一异常

- 文件：`product_service/app/core/exceptions/business_exception.py`
- 文件：`product_service/app/core/exceptions/handlers.py`
- 输出统一错误结构：`code`、`message`、`request_id`

### 结构化日志

- 全部采用 JSON 日志，便于 ELK / Loki / Cloud Logging 收集。
- 日志中记录事件名、请求 ID、路径、耗时、缓存 key、商品 ID 等非敏感字段。
- 避免输出用户敏感信息、密码、完整连接串。

## 7. 性能注意点

- `prewarm_cache()` 已改为分批回源、分批写 Redis，避免预热时占用过多内存。
- 列表查询仍基于 `name like '%keyword%'`，当商品规模继续增长时，建议接入 Elasticsearch。
- 当前 `price` 字段沿用现有表结构中的浮点类型；若后续进入真实交易链路，建议升级为 `DECIMAL(10,2)`。

## 8. 本地验证步骤

1. 执行 `docker compose up --build`
2. 等待 `mysql-replica-init` 执行完成
3. 调用 `POST /api/products/prewarm`
4. 多次调用 `GET /api/products/{id}`，观察 Redis 命中和结构化日志
5. 调用 `GET /api/internal/db-route-check`，确认读路由已指向副本

## 9. 后续建议

- 将 `Base.metadata.create_all()` 替换为 Alembic 迁移。
- 为热点详情接口补充压测脚本，例如 `wrk` 或 `JMeter`。
- 如果要扩展到真正秒杀扣减链路，建议在 `inventory_service` 中使用 Redis Lua 或数据库乐观锁做库存扣减。
