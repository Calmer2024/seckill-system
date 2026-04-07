from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.dependencies import get_product_query_service
from app.application.dto.product_dto import (
    CachePrewarmResponse,
    DatabaseRouteCheckResponse,
    ProductListQuery,
    ProductResponse,
    ProductSearchQuery,
)
from app.application.interfaces.product_query_service import ProductQueryService

router = APIRouter(prefix="/api", tags=["Products"])


@router.get("/products/search", response_model=list[ProductResponse])
def search_products(
    query: Annotated[ProductSearchQuery, Depends()],
    service: Annotated[ProductQueryService, Depends(get_product_query_service)],
):
    return service.search_products(query)


@router.get("/products", response_model=list[ProductResponse])
def get_product_list(
    query: Annotated[ProductListQuery, Depends()],
    service: Annotated[ProductQueryService, Depends(get_product_query_service)],
):
    return service.list_products(query)


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product_detail(
    product_id: Annotated[int, Path(gt=0, description="商品 ID，必须为正整数")],
    service: Annotated[ProductQueryService, Depends(get_product_query_service)],
):
    return service.get_product_detail(product_id)


@router.post("/products/prewarm", response_model=CachePrewarmResponse)
def trigger_cache_prewarm(
    service: Annotated[ProductQueryService, Depends(get_product_query_service)],
):
    return service.prewarm_cache()


@router.get("/internal/db-route-check", response_model=DatabaseRouteCheckResponse)
def check_db_routing(
    service: Annotated[ProductQueryService, Depends(get_product_query_service)],
):
    return service.get_database_route_diagnostics()
