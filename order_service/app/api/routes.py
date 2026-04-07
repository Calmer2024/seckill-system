from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_order_application_service
from app.application.dto.order_dto import (
    OrderResponse,
    PaymentAcceptedResponse,
    PaymentRequest,
    SeckillOrderAcceptedResponse,
    SeckillOrderRequest,
)
from app.application.services.order_service import OrderApplicationService, OrderRepository
from app.core.database import get_order_db
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


@router.post("/{order_id}/pay", response_model=PaymentAcceptedResponse)
def pay_order(
    order_id: int,
    request: PaymentRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[OrderApplicationService, Depends(get_order_application_service)],
):
    return service.pay_order(order_id=order_id, request=request, current_user=current_user)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    order_db: Annotated[Session, Depends(get_order_db)],
):
    order = OrderRepository(order_db).get_by_order_id(order_id=order_id, user_id=current_user.user_id)
    if order:
        return order

    raise BusinessException("ORDER_NOT_FOUND", "订单不存在", 404)


@router.get("", response_model=list[OrderResponse])
def list_orders_by_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    order_db: Annotated[Session, Depends(get_order_db)],
    user_id: int | None = Query(default=None, gt=0, description="用户 ID，不传时查询当前登录用户"),
):
    target_user_id = user_id or current_user.user_id
    return OrderRepository(order_db).list_by_user_id(target_user_id)
