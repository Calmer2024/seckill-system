# 秒杀下单、消息队列与分库分表工作文档

## 1. 本次改造目标

本次围绕秒杀下单链路补齐了以下能力：

- 新增 `order_service`，提供秒杀下单、按订单 ID 查询订单、按用户 ID 查询订单能力。
- 使用 Redis 缓存库存，并通过 Lua 脚本实现原子预扣库存与用户幂等控制。
- 使用 Kafka 将秒杀请求异步化，订单创建改为消费端处理，降低流量洪峰对数据库的直接冲击。
- 使用雪花算法生成订单 ID。
- 使用 ShardingSphere-Proxy 对订单表进行分库分表。
  - 按 `user_id` 分库
  - 按 `order_id` 分表
- 增加前端秒杀页真实下单与查单能力，支持登录后直接演示整条链路。

## 2. 整体架构

### 2.1 服务与组件

- `redis`
  - 存放秒杀库存缓存
  - 存放用户商品幂等 key
  - 存放订单异步处理状态
- `kafka`
  - 削峰填谷
  - 负责承接 API 层写入的秒杀请求事件
- `order_service`
  - 提供下单与查单 HTTP 接口
  - 负责 Redis 预扣库存与 Kafka 生产消息
- `order_worker`
  - 消费 Kafka 订单事件
  - 完成数据库扣减库存、创建订单、失败补偿
- `shardingsphere-proxy`
  - 为订单表提供统一逻辑库 `order_db`
  - 将订单数据路由到 `order_db_0` / `order_db_1`
- `mysql-primary`
  - 保存商品库存表与分片后的订单物理表

### 2.2 请求链路

1. 用户调用 `POST /api/orders/seckill`
2. `order_service` 先查库确认用户没有成功下过单
3. 读取商品库存并预热 Redis 库存 key
4. Redis Lua 脚本原子执行：
   - 校验同一用户同一商品是否已占位
   - 校验 Redis 库存是否充足
   - 扣减 Redis 库存
   - 写入用户商品幂等 key
   - 写入订单状态 `QUEUED`
5. API 生成雪花订单号，发送 Kafka 消息，立即返回“已排队”
6. `order_worker` 消费消息，执行：
   - 再查订单库，避免重复消费
   - 更新 MySQL 商品库存 `stock = stock - 1 where stock >= 1`
   - 通过 ShardingSphere 写入逻辑订单表 `t_order`
   - 写入用户购买记录表 `t_user_purchase_record`
7. 成功时更新 Redis 订单状态为 `SUCCESS`
8. 失败时执行补偿：
   - 回补 MySQL 商品库存
   - 回补 Redis 库存
   - 删除用户商品幂等 key
   - 标记 Redis 订单状态为 `FAILED`

## 3. 幂等性设计

### 3.1 API 层幂等

- Redis 使用 key：`seckill:user:{user_id}:product:{product_id}`
- Lua 脚本保证“检查重复下单 + 扣减库存”在一个原子操作中完成
- 同一用户同一商品再次请求会直接返回 `409 DUPLICATE_ORDER`

### 3.2 数据库层兜底

- API 正式入队前会先查订单库，避免 Redis 幂等 key 过期后重复预扣库存
- 订单落库时同步写入 `t_user_purchase_record`
  - 主键：`(user_id, product_id)`
  - 作为数据库层“同一用户同一商品只能成功一次”的唯一约束

### 3.3 消费端幂等

- Worker 消费 Kafka 消息前，先根据 `user_id + product_id` 查询是否已存在成功订单
- 若订单已存在，则直接将 Redis 状态改为成功，避免重复落库

## 4. 数据一致性设计

### 4.1 防超卖

- 第一层：Redis 预扣库存，拦截绝大多数并发请求
- 第二层：MySQL 扣减库存使用条件更新
  - `update seckill_product set stock = stock - 1 where id = ? and stock >= 1`
- 即使 Redis 和数据库出现短时偏差，数据库层仍会兜底，避免最终超卖

### 4.2 异步失败补偿

当消费端出现以下异常时：

- 订单表插入失败
- 用户购买记录插入失败
- 业务运行期异常

会执行以下补偿：

- 回滚订单事务
- 回补数据库库存
- 回补 Redis 库存
- 清理 Redis 用户商品幂等 key
- 将订单状态改为 `FAILED`

### 4.3 最终一致性说明

当前方案属于“Redis 快速拦截 + MySQL 条件更新 + 异步补偿”的最终一致性方案，适合作业和中小规模秒杀演示场景。

如果后续要进一步提升一致性保障，建议继续演进：

- 引入事务消息或本地消息表
- 引入订单任务表状态机
- 引入库存流水表/补偿任务扫描
- 使用 Alembic/Flyway 管控订单分片表结构变更

## 5. 分库分表设计

### 5.1 技术选型

- 使用 `ShardingSphere-Proxy`
- 配置文件：`infra/shardingsphere/conf/config-sharding.yaml`

### 5.2 路由规则

逻辑库：

- `order_db`

物理库：

- `order_db_0`
- `order_db_1`

逻辑表：

- `t_order`

物理表：

- `t_order_0`
- `t_order_1`

分片规则：

- 分库：`ds_${user_id % 2}`
- 分表：`t_order_${order_id % 2}`

辅助表：

- `t_user_purchase_record`
- 仅按 `user_id` 分库，不再分表

## 6. 关键文件说明

### 6.1 订单服务

- `order_service/app/main.py`
  - FastAPI 启动入口
- `order_service/app/api/routes.py`
  - 下单与查单接口
- `order_service/app/application/services/order_service.py`
  - 雪花 ID、Redis Lua、Kafka 生产消费、库存补偿、订单落库主逻辑
- `order_service/app/worker.py`
  - Kafka 消费 worker 启动入口
- `order_service/app/models/order.py`
  - 逻辑订单表与用户购买记录表模型

### 6.2 基础设施

- `docker-compose.yml`
  - 增加 `zookeeper`、`kafka`、`shardingsphere-proxy`、`order_service`、`order_worker`
- `infra/mysql/primary/init/02-init-seckill-and-order-schema.sql`
  - 初始化商品表、订单分片物理库、订单分片物理表
- `infra/shardingsphere/conf/server.yaml`
  - Proxy 权限与基础配置
- `infra/shardingsphere/conf/config-sharding.yaml`
  - 分库分表规则
- `nginx.conf`
  - 增加 `/api/orders` 路由转发

### 6.3 前端

- `frontend/src/utils/http.js`
  - 自动附带登录 token
- `frontend/src/services/orderApi.js`
  - 秒杀下单与查单 API
- `frontend/src/pages/FlashSaleArena.jsx`
  - 接入真实秒杀下单与轮询查单
- `frontend/src/pages/AuthPortal.jsx`
  - 改为走统一 API 基址，避免固定写死端口

## 7. 对外接口

### 7.1 提交秒杀请求

- `POST /api/orders/seckill`

请求体：

```json
{
  "product_id": 1,
  "quantity": 1
}
```

返回示例：

```json
{
  "order_id": 302134190368219136,
  "status": "QUEUED",
  "message": "下单请求已进入队列，请稍后查询订单结果"
}
```

### 7.2 按订单 ID 查询

- `GET /api/orders/{order_id}`

若订单仍在异步处理中，会返回：

```json
{
  "order_id": 302134190368219136,
  "status": "QUEUED",
  "message": "订单仍在异步处理，请稍后刷新"
}
```

订单落库后会返回完整订单数据。

### 7.3 按用户 ID 查询

- `GET /api/orders`
- `GET /api/orders?user_id=1`

默认查询当前登录用户订单列表。

## 8. 本地启动与验证

### 8.1 启动

```bash
docker compose up --build
```

### 8.2 建议验证顺序

1. 注册并登录用户
2. 打开前端秒杀页
3. 倒计时结束后点击秒杀按钮
4. 观察页面是否进入“排队中”
5. 观察 `order_worker` 日志是否消费消息成功
6. 调用 `GET /api/orders/{order_id}` 查看最终订单状态
7. 重复对同一商品下单，确认返回重复下单错误

### 8.3 我本次已完成的本地验证

- `python -m compileall order_service/app`
- `npm run build`
- `docker compose config`

以上检查均已通过，说明：

- 新增 Python 代码无语法错误
- 前端改动可正常打包
- Compose 编排语法有效

## 9. 已知说明

- 当前订单状态的“处理中”阶段主要保存在 Redis，适合秒杀场景下的轻量轮询。
- Worker 当前采用单消费者容器方式运行，便于演示链路和控制重复消费复杂度。
- 订单最终一致性依赖补偿逻辑；若后续进入更高可靠性的生产场景，建议继续引入事务消息、本地消息表与定时补偿任务。
