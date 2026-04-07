from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.dependencies import get_inventory_application_service
from app.schemas.inventory import (
    InventoryItemResponse,
    InventoryReservationRequest,
    InventoryReservationResponse,
)
from app.services.inventory_service import InventoryApplicationService


router = APIRouter(tags=["Inventory"])


@router.get("/api/inventory/products/{product_id}", response_model=InventoryItemResponse)
def get_inventory_item(
    product_id: Annotated[int, Path(gt=0, description="商品 ID")],
    service: Annotated[InventoryApplicationService, Depends(get_inventory_application_service)],
):
    return service.get_inventory_item(product_id)


@router.post("/internal/inventory/reservations", response_model=InventoryReservationResponse)
def reserve_inventory(
    request: InventoryReservationRequest,
    service: Annotated[InventoryApplicationService, Depends(get_inventory_application_service)],
):
    return service.reserve_inventory(request)


@router.post("/internal/inventory/reservations/{order_id}/cancel", response_model=InventoryReservationResponse)
def cancel_inventory_reservation(
    order_id: Annotated[int, Path(gt=0, description="订单 ID")],
    service: Annotated[InventoryApplicationService, Depends(get_inventory_application_service)],
):
    return service.cancel_inventory_reservation(order_id)
