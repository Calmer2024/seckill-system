from typing import Annotated

import redis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_order_application_service
from app.application.dto.order_dto import (
    OrderResponse,
    PendingOrderResponse,
    SeckillOrderAcceptedResponse,
    SeckillOrderRequest,
)
from app.application.services.order_service import OrderApplicationService, OrderRepository, StockCacheService
from app.core.database import get_order_db, get_redis_client
from app.core.exceptions.business_exception import BusinessException
from app.core.security import CurrentUser, get_current_user


router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post("/seckill", response_model=SeckillOrderAcceptedResponse)
def create_seckill_order(
    request: SeckillOrderRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[OrderApplicationService, Depends(get_order_application_service)],
):
    return service.submit_seckill_order(request=request, current_user=current_user)


@router.get("/{order_id}", response_model=OrderResponse | PendingOrderResponse)
def get_order_detail(
    order_id: int,
    order_db: Annotated[Session, Depends(get_order_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)],
):
    stock_cache_service = StockCacheService(redis_client)
    order_owner = stock_cache_service.get_order_owner(order_id)
    order = OrderRepository(order_db).get_by_order_id(order_id=order_id, user_id=order_owner)
    if order:
        return order

    status = stock_cache_service.get_order_status(order_id)
    if status:
        return PendingOrderResponse(
            order_id=order_id,
            status=status,
            message="订单仍在异步处理，请稍后刷新",
        )

    raise BusinessException("ORDER_NOT_FOUND", "订单不存在", 404)


@router.get("", response_model=list[OrderResponse])
def list_orders_by_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    order_db: Annotated[Session, Depends(get_order_db)],
    user_id: int | None = Query(default=None, gt=0, description="用户 ID，不传时查询当前登录用户"),
):
    target_user_id = user_id or current_user.user_id
    return OrderRepository(order_db).list_by_user_id(target_user_id)
