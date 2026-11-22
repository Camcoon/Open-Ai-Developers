import pytest

from app.services.strategies import (
    ExperienceFirstStrategy,
    LeastLoadedStrategy,
    get_strategy,
)


@pytest.fixture
def candidates():
    return [{"id": 1}, {"id": 2}, {"id": 3}]


def test_experience_first_ranks_experienced_candidate_first(candidates):
    ranked = ExperienceFirstStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs={(2, 10)},
        load_by_ta={1: 0, 2: 15, 3: 2},
    )

    assert [ta["id"] for ta in ranked] == [2, 1, 3]


def test_experience_first_does_not_remove_inexperienced_candidates(candidates):
    ranked = ExperienceFirstStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs={(1, 10)},
        load_by_ta={1: 5, 2: 0, 3: 8},
    )

    assert [ta["id"] for ta in ranked] == [1, 2, 3]
    assert {ta["id"] for ta in ranked} == {1, 2, 3}


def test_experience_first_falls_back_to_workload_without_experience(candidates):
    ranked = ExperienceFirstStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs=set(),
        load_by_ta={1: 8, 2: 2, 3: 5},
    )

    assert [ta["id"] for ta in ranked] == [2, 3, 1]


def test_experience_first_orders_experienced_by_lowest_workload(candidates):
    ranked = ExperienceFirstStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs={(1, 10), (2, 10)},
        load_by_ta={1: 12, 2: 4, 3: 0},
    )

    assert [ta["id"] for ta in ranked] == [2, 1, 3]


def test_least_loaded_ranks_lowest_weekly_load_first(candidates):
    ranked = LeastLoadedStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs={(1, 10)},
        load_by_ta={1: 15, 2: 3, 3: 8},
    )

    assert [ta["id"] for ta in ranked] == [2, 3, 1]


def test_least_loaded_uses_ta_id_for_equal_loads():
    candidates = [{"id": 3}, {"id": 1}, {"id": 2}]

    ranked = LeastLoadedStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs=set(),
        load_by_ta={1: 4, 2: 4, 3: 4},
    )

    assert [ta["id"] for ta in ranked] == [1, 2, 3]


def test_experience_first_returns_empty_list_for_no_candidates():
    ranked = ExperienceFirstStrategy().rank(
        [],
        course_id=10,
        experience_pairs=set(),
        load_by_ta={},
    )

    assert ranked == []


def test_least_loaded_returns_empty_list_for_no_candidates():
    ranked = LeastLoadedStrategy().rank(
        [],
        course_id=10,
        experience_pairs=set(),
        load_by_ta={},
    )

    assert ranked == []


def test_get_strategy_returns_experience_first():
    assert isinstance(
        get_strategy("experience_first"),
        ExperienceFirstStrategy,
    )


def test_get_strategy_returns_least_loaded():
    assert isinstance(
        get_strategy("least_loaded"),
        LeastLoadedStrategy,
    )


def test_get_strategy_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unsupported allocation mode"):
        get_strategy("unknown")


def test_ranking_does_not_mutate_original_candidate_order():
    candidates = [{"id": 2}, {"id": 1}]
    original = list(candidates)

    LeastLoadedStrategy().rank(
        candidates,
        course_id=10,
        experience_pairs=set(),
        load_by_ta={1: 1, 2: 5},
    )

    assert candidates == original
