# 秒杀下单、库存预扣减与一致性方案工作文档

## 1. 改造目标

本次围绕商品秒杀场景完成了两条关键一致性链路改造：

1. 秒杀下单时，基于 Redis 预扣减库存，实现高并发下的防超卖与限购。
2. 通过基于消息的最终一致性方案，保障：
   - 下单与库存扣减一致性
   - 订单支付与订单状态更新一致性

本次改造后的服务边界如下：

- `order_service`
  - 负责秒杀下单、订单查询、订单支付
  - 使用自己的订单库 `order_db`
- `inventory_service`
  - 负责库存预留、库存确认、库存回补
  - 使用自己的库存库 `inventory_db`
- `Redis`
  - 承担库存预扣减、用户限购 Key
- `Kafka`
  - 承担订单创建事件、库存确认结果事件、支付结果事件

## 2. 实现方案总览

### 2.1 秒杀下单链路

采用“Redis 预扣减 + 库存服务预留 + 订单服务 Outbox + Kafka 异步确认”的方案：

1. 用户调用 `POST /api/orders/seckill`
2. `order_service` 先校验用户是否已存在活动订单
3. `order_service` 调用 `inventory_service` 的预留接口
4. `inventory_service` 内部执行：
   - Redis Lua 原子脚本校验限购、校验库存、执行预扣减
   - 库存库本地事务将 `available_stock -> reserved_stock`
   - 写入 `inventory_reservation`
5. `order_service` 在本地事务内：
   - 写入订单表，状态为 `PENDING_INVENTORY`
   - 写入订单 Outbox 事件 `ORDER_CREATED`
6. `order_worker` 轮询 Outbox，将 `ORDER_CREATED` 发布到 Kafka
7. `inventory_worker` 消费 `ORDER_CREATED`
   - 将库存从 `reserved_stock -> sold_stock`
   - 将预留状态改为 `CONFIRMED`
   - 写入库存 Outbox 事件 `INVENTORY_CONFIRMED`
8. `inventory_worker` 发布库存确认结果
9. `order_worker` 消费库存结果
   - 成功则将订单状态更新为 `CREATED`
   - 失败则将订单状态更新为 `FAILED`

### 2.2 支付链路

采用“支付记录本地事务 + Outbox + Kafka 异步改订单状态”的方案：

1. 用户调用 `POST /api/orders/{order_id}/pay`
2. `order_service` 在本地事务内：
   - 将订单状态改为 `PAYING`
   - 写入 `t_payment`
   - 写入 Outbox 事件 `PAYMENT_REQUESTED`
3. `order_worker` 将支付事件投递到 Kafka
4. `order_worker` 作为支付结果消费者继续消费该事件
   - 将支付记录改为 `SUCCESS`
   - 将订单状态改为 `PAID`

这条链路体现的是支付事实与订单状态更新之间的消息最终一致性，而不是单库内直接同步改状态。

## 3. Redis 预扣减设计

库存服务使用 Redis Lua 脚本实现秒杀入口的原子校验与预扣减。

### 3.1 Key 设计

- `seckill:stock:{product_id}`
  - 商品可用库存缓存
- `seckill:user:{user_id}:product:{product_id}`
  - 用户限购 Key
- `seckill:reservation:{order_id}`
  - 预留状态 Key

### 3.2 原子能力

Lua 脚本一次完成以下动作：

- 校验用户是否已经抢购该商品
- 校验 Redis 库存是否足够
- 原子扣减 Redis 库存
- 写入用户限购 Key
- 写入预留状态 Key

### 3.3 防超卖与限购

- Redis 层先挡住绝大多数并发请求，避免数据库被直接打穿
- 库存库仍然维护 `available_stock / reserved_stock / sold_stock`
- 即使 Redis 与数据库之间出现短暂偏差，库存服务本地事务仍会保证库存状态有迹可循

## 4. 一致性设计

### 4.1 下单 + 库存扣减一致性

核心设计点：

- `inventory_service` 对“库存预留”使用本地事务
- `order_service` 对“订单创建 + Outbox”使用本地事务
- 两个服务通过 Kafka 进行异步对账

一致性表现：

- 若库存预留失败，则订单不会创建
- 若订单本地事务失败，`order_service` 会同步调用库存取消接口回补库存
- 若订单已创建但库存确认结果未回传，订单状态停留在 `PENDING_INVENTORY`
- 若库存确认成功，订单最终变为 `CREATED`
- 若库存确认失败，订单最终变为 `FAILED`

### 4.2 订单支付 + 订单状态更新一致性

核心设计点：

- 支付请求不会直接把订单改成 `PAID`
- 而是先落支付记录与 Outbox，再异步消费消息修改订单状态

一致性表现：

- 若本地事务失败，则既不会有支付记录，也不会有支付事件
- 若 Outbox 已落库但还未投递，worker 可继续补发
- 若消息已投递但消费者暂未执行，订单保持 `PAYING`
- 消费成功后订单变更为 `PAID`

## 5. 数据模型

### 5.1 库存库 `inventory_db`

- `inventory_item`
  - 商品库存主表
  - 维护 `available_stock / reserved_stock / sold_stock`
- `inventory_reservation`
  - 秒杀库存预留记录
  - 记录每个订单对应的库存预留状态
- `inventory_outbox_event`
  - 库存服务本地消息表

### 5.2 订单库 `order_db`

- `t_order`
  - 订单主表
  - 新增 `failure_reason`
- `t_payment`
  - 支付记录表
- `t_order_outbox_event`
  - 订单服务本地消息表
- `t_user_purchase_record`
  - 用户成功购买记录表

## 6. 分库分表

订单相关表继续通过 ShardingSphere-Proxy 管理。

### 6.1 逻辑表

- `t_order`
- `t_payment`
- `t_order_outbox_event`
- `t_user_purchase_record`

### 6.2 分片规则

- 分库：`ds_${user_id % 2}`
- 订单表分表：`t_order_${order_id % 2}`
- 支付表分表：`t_payment_${order_id % 2}`
- Outbox 表分表：`t_order_outbox_event_${aggregate_id % 2}`

## 7. 关键接口

### 7.1 提交秒杀订单

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
  "status": "PENDING_INVENTORY",
  "message": "订单已创建并预扣库存，等待库存服务异步确认"
}
```

### 7.2 查询订单

- `GET /api/orders/{order_id}`

订单状态可能包含：

- `PENDING_INVENTORY`
- `CREATED`
- `PAYING`
- `PAID`
- `FAILED`

### 7.3 发起支付

- `POST /api/orders/{order_id}/pay`

请求体：

```json
{
  "amount": 19.90
}
```

返回示例：

```json
{
  "order_id": 302134190368219136,
  "payment_status": "PROCESSING",
  "order_status": "PAYING",
  "message": "支付请求已受理，订单状态将异步更新"
}
```

### 7.4 库存服务内部接口

- `POST /internal/inventory/reservations`
- `POST /internal/inventory/reservations/{order_id}/cancel`
- `GET /api/inventory/products/{product_id}`

## 8. 关键文件

### 8.1 订单服务

- `order_service/app/application/services/order_service.py`
  - 下单、支付、Outbox 发布、库存结果消费、支付结果消费
- `order_service/app/api/routes.py`
  - 秒杀下单、支付、查单接口
- `order_service/app/models/order.py`
  - 订单、支付、Outbox 模型

### 8.2 库存服务

- `inventory_service/app/services/inventory_service.py`
  - Redis 预扣减、库存预留、库存确认、库存回补、Outbox 发布
- `inventory_service/app/api/routes.py`
  - 库存查询、库存预留、库存取消接口
- `inventory_service/app/models/inventory.py`
  - 库存主表、预留表、Outbox 表模型

### 8.3 基础设施

- `infra/mysql/primary/init/02-init-seckill-and-order-schema.sql`
  - 初始化库存库、订单库、分表结构
- `infra/shardingsphere/conf/config-sharding.yaml`
  - 支付表与 Outbox 表分片规则
- `docker-compose.yml`
  - 新增 `inventory_service`、`inventory_worker`

## 9. 验证方式

### 9.1 已完成验证

- `python -m compileall order_service/app`
- `python -m compileall inventory_service/app`
- `docker compose config`

以上检查已通过。

### 9.2 建议联调顺序

1. `docker compose up --build`
2. 登录用户
3. 调用 `POST /api/orders/seckill`
4. 查询订单，确认状态从 `PENDING_INVENTORY` 变为 `CREATED`
5. 调用 `POST /api/orders/{order_id}/pay`
6. 查询订单，确认状态从 `PAYING` 变为 `PAID`
7. 使用同一用户对同一商品重复下单，确认返回 `409 DUPLICATE_ORDER`

## 10. 已知说明

- 当前支付链路中的“支付成功”是通过消息闭环模拟的，适合作业与演示场景。
- 当前 Outbox 采用轮询发布模型，结构清晰，便于演示事务消息思想。
- 如果继续向生产级演进，建议补充：
  - 定时补偿任务
  - Outbox 死信与重试上限
  - 支付服务独立化
  - 库存恢复/订单失败对账任务
