from typing import Optional

from sqlmodel import Field, SQLModel


class Assignment(SQLModel, table=True):
    __tablename__ = "assignments"

    id: Optional[int] = Field(default=None, primary_key=True)
    ta_id: int = Field(index=True)
    course_id: int = Field(index=True)
    weekly_hours: int
    start_week: int = Field(default=1, ge=1)
    end_week: int = Field(default=1, ge=1)
    created_at: str
