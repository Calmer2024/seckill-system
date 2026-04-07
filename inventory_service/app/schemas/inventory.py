from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InventoryReservationRequest(BaseModel):
    order_id: int
    user_id: int
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=1)


class InventoryReservationResponse(BaseModel):
    order_id: int
    status: str
    message: str


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    unit_price: Decimal
    available_stock: int
    reserved_stock: int
    sold_stock: int
    updated_at: datetime | None = None


class InventoryResultEvent(BaseModel):
    order_id: int
    user_id: int
    product_id: int
    quantity: int
    status: str
    failure_reason: str | None = None
