from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, DateTime, Numeric
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def money_column(nullable: bool = False) -> Column:
    return Column(Numeric(12, 2), nullable=nullable)


def quantity_column(nullable: bool = False) -> Column:
    return Column(Numeric(12, 3), nullable=nullable)


def coordinate_column(nullable: bool = True) -> Column:
    return Column(Numeric(10, 7), nullable=nullable)


class IdMixin(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)


def timestamp_field() -> datetime:
    return Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


Money = Decimal
