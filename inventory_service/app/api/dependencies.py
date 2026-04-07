from typing import Annotated

import redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_inventory_db, get_redis_client
from app.services.inventory_service import InventoryApplicationService


def get_inventory_application_service(
    inventory_db: Annotated[Session, Depends(get_inventory_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis_client)],
) -> InventoryApplicationService:
    return InventoryApplicationService(inventory_db=inventory_db, redis_client=redis_client)
