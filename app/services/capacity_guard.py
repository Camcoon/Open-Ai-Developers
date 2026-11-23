"""Capacity validation for TA allocation requests."""

#recently edited
from typing import Any

from app.services.constants import WEEKLY_HOUR_CAP


class CapacityGuard:
    @staticmethod
    def validate_request(hours: int, budget_remaining: int) -> None:
        if hours <= 0:
            raise ValueError("hours must be positive")
        if hours > budget_remaining:
            raise ValueError("exceeds department budget")

    @staticmethod
    def validate_ta(current_load: int, hours: int) -> None:
        if current_load + hours > WEEKLY_HOUR_CAP:
            raise ValueError("exceeds TA weekly hour cap")

    @staticmethod
    def eligible_candidates(
        tas: list[dict[str, Any]],
        load_by_ta: dict[int, int],
        hours: int,
    ) -> list[dict[str, Any]]:
        return [
            ta
            for ta in tas
            if load_by_ta.get(ta["id"], 0) + hours <= WEEKLY_HOUR_CAP
        ]
