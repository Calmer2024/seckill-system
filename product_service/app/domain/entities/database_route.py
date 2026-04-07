from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatabaseRouteSnapshot:
    read_role: str
    write_role: str
    replica_enabled: bool
    read_database: str | None
    write_database: str | None
    read_product_count: int
    write_product_count: int
