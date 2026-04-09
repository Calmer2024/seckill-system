from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SeckillOrderRequest(BaseModel):
    product_id: int = Field(gt=0, description="秒杀商品 ID")
    quantity: int = Field(default=1, ge=1, le=1, description="秒杀数量，当前仅支持单件购买")


class SeckillOrderAcceptedResponse(BaseModel):
    order_id: int
    status: str
    message: str

    @field_serializer("order_id")
    def serialize_order_id(self, value: int) -> str:
        return str(value)


class PaymentRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, description="支付金额，不传时按订单金额支付")


class PaymentAcceptedResponse(BaseModel):
    order_id: int
    payment_status: str
    order_status: str
    message: str

    @field_serializer("order_id")
    def serialize_order_id(self, value: int) -> str:
        return str(value)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    user_id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    status: str
    failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("order_id")
    def serialize_order_id(self, value: int) -> str:
        return str(value)


class PendingOrderResponse(BaseModel):
    order_id: int
    status: str
    message: str

    @field_serializer("order_id")
    def serialize_order_id(self, value: int) -> str:
        return str(value)


class OrderCreatedEvent(BaseModel):
    order_id: int
    user_id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal


class InventoryResultEvent(BaseModel):
    order_id: int
    user_id: int
    product_id: int
    quantity: int
    status: str
    failure_reason: str | None = None


class PaymentRequestedEvent(BaseModel):
    order_id: int
    user_id: int
    amount: Decimal
