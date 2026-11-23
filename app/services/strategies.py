"""Ranking strategies for TA allocation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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


class RoundRobinStrategy(RankingStrategy):
    """Rank eligible candidates in their existing stable order."""

    def rank(
        self,
        candidates: list[Candidate],
        *,
        course_id: int,
        experience_pairs: set[tuple[int, int]],
        load_by_ta: dict[int, int],
    ) -> list[Candidate]:
        del course_id, experience_pairs, load_by_ta
        return list(candidates)


STRATEGIES: dict[str, RankingStrategy] = {
    "experience_first": ExperienceFirstStrategy(),
    "least_loaded": LeastLoadedStrategy(),
    "round_robin": RoundRobinStrategy(),
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
