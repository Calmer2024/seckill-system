from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProductEntity:
    id: int
    name: str
    price: Decimal
    stock: int
