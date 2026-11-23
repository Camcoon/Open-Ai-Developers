from decimal import Decimal

from sqlmodel import Field, SQLModel


class Ta(SQLModel, table=True):
    __tablename__ = "tas"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    hourly_rate: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=8,
        decimal_places=2,
        ge=0,
    )
    performance_rating: float = Field(default=0.0, ge=0.0, le=5.0)
