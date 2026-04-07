from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SeckillOrderRequest(BaseModel):
    product_id: int = Field(gt=0, description="秒杀商品 ID")
    quantity: int = Field(default=1, ge=1, le=1, description="秒杀数量，当前仅支持单件购买")


class SeckillOrderAcceptedResponse(BaseModel):
    order_id: int
    status: str
    message: str


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    user_id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PendingOrderResponse(BaseModel):
    order_id: int
    status: str
    message: str


class OrderEvent(BaseModel):
    order_id: int
    user_id: int
    product_id: int
    quantity: int
    unit_price: Decimal
