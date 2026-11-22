"""Ranking strategies for TA allocation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.services.constants import WEEKLY_HOUR_CAP

Candidate = dict[str, Any]


class RankingStrategy(ABC):
    """Common interface for ranking eligible TA candidates."""

    @abstractmethod
    def rank(
        self,
        candidates: list[Candidate],
        *,
        course_id: int,
        experience_pairs: set[tuple[int, int]],
        load_by_ta: dict[int, int],
    ) -> list[Candidate]:
        """Return candidates ordered from most preferred to least preferred."""
        raise NotImplementedError


class ExperienceFirstStrategy(RankingStrategy):
    """Prioritize TAs with prior experience in the requested course."""

    def rank(
        self,
        candidates: list[Candidate],
        *,
        course_id: int,
        experience_pairs: set[tuple[int, int]],
        load_by_ta: dict[int, int],
    ) -> list[Candidate]:
        return sorted(
            candidates,
            key=lambda ta: (
                (ta["id"], course_id) not in experience_pairs,
                load_by_ta.get(ta["id"], 0),
                ta["id"],
            ),
        )


class LeastLoadedStrategy(RankingStrategy):
    """Prioritize TAs with the lowest current weekly workload."""

    def rank(
        self,
        candidates: list[Candidate],
        *,
        course_id: int,
        experience_pairs: set[tuple[int, int]],
        load_by_ta: dict[int, int],
    ) -> list[Candidate]:
        return sorted(
            candidates,
            key=lambda ta: (
                load_by_ta.get(ta["id"], 0),
                ta["id"],
            ),
        )


STRATEGIES: dict[str, RankingStrategy] = {
    "experience_first": ExperienceFirstStrategy(),
    "least_loaded": LeastLoadedStrategy(),
}

MODES = tuple(STRATEGIES)


def get_strategy(mode: str) -> RankingStrategy:
    """Return the ranking strategy registered for a supported mode."""
    try:
        return STRATEGIES[mode]
    except KeyError:
        supported = ", ".join(sorted(STRATEGIES))
        raise ValueError(
            f"Unsupported allocation mode: {mode}. "
            f"Supported modes: {supported}"
        ) from None


def auto_select_ta(
    *,
    mode: str,
    course: dict[str, Any],
    tas: list[dict[str, Any]],
    experience: set[tuple[int, int]],
    load_by_ta: dict[int, int],
    budget_remaining: int,
    hours: int,
    round_robin_cursor: int = 0,
) -> dict[str, Any]:
    """Compatibility wrapper for the existing allocation service.

    Phase 6 integration should replace this wrapper with the CapacityGuard
    and Strategy classes directly. This wrapper remains only so the starter
    service can continue importing the module during independent development.
    """
    del round_robin_cursor

    if hours <= 0:
        return {"ok": False, "error": "hours must be positive"}
    if hours > budget_remaining:
        return {"ok": False, "error": "exceeds department budget"}

    candidates = [
        ta
        for ta in tas
        if load_by_ta.get(ta["id"], 0) + hours <= WEEKLY_HOUR_CAP
    ]
    if not candidates:
        return {"ok": False, "error": "no eligible TAs"}

    try:
        strategy = get_strategy(mode)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    ranked = strategy.rank(
        candidates,
        course_id=course["id"],
        experience_pairs=experience,
        load_by_ta=load_by_ta,
    )
    if not ranked:
        return {"ok": False, "error": "no eligible TAs"}

    chosen = ranked[0]
    projected_load = load_by_ta.get(chosen["id"], 0) + hours
    return {
        "ok": True,
        "ta_id": chosen["id"],
        "mode": mode,
        "reason": (
            "prior course experience"
            if (chosen["id"], course["id"]) in experience
            else "eligible candidate"
        ),
        "projected_load": projected_load,
        "cap": WEEKLY_HOUR_CAP,
    }
