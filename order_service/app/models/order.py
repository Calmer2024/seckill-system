from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Order(Base):
    __tablename__ = "t_order"

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserPurchaseRecord(Base):
    __tablename__ = "t_user_purchase_record"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PaymentRecord(Base):
    __tablename__ = "t_payment"

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROCESSING")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OrderOutboxEvent(Base):
    __tablename__ = "t_order_outbox_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    observability_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
