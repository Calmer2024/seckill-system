from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProductEntity:
    id: int
    name: str
    price: Decimal
    stock: int
    category: str
    rating: float
    review_count: int
    tags: list[str]
    summary: str
    highlight: str
    visual_icon: str
