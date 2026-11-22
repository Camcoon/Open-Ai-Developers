import pytest
from sqlmodel import Session, select

import app.services.allocation_auth as allocation_auth
import app.services.allocations as allocations
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.department import Department
from app.models.ta import Ta
from app.models.ta_experience import TaExperience
from app.models.user import User


def seed_allocation_database(test_session):
    hod = User(
        username="hod",
        email="hod@example.com",
        password="unused",
        role="hod",
    )
    course = Course(code="COMP3613", title="Software Engineering", budgeted_hours=30)
    tas = [
        Ta(name="Alex", email="alex@example.com"),
        Ta(name="Blair", email="blair@example.com"),
        Ta(name="Casey", email="casey@example.com"),
    ]
    department = Department(id=1, budget_hours_remaining=62)

    test_session.add(hod)
    test_session.add(course)
    test_session.add(department)
    for ta in tas:
        test_session.add(ta)
    test_session.commit()

    return hod.id, course.id


@pytest.fixture
def allocation_db(test_session, monkeypatch):
    hod_id, course_id = seed_allocation_database(test_session)
    monkeypatch.setattr(allocations, "engine", test_session.bind)
    monkeypatch.setattr(allocation_auth, "engine", test_session.bind)

    course = test_session.get(Course, course_id)
    tas = test_session.exec(select(Ta)).all()
    return hod_id, course.id, tas


def test_experience_first_prefers_experienced_eligible_ta(allocation_db):
    hod_id, course_id, tas = allocation_db

    with Session(allocations.engine) as session:
        session.add(TaExperience(ta_id=tas[0].id, course_id=course_id))
        session.add(Assignment(ta_id=tas[1].id, course_id=course_id, weekly_hours=18, created_at="now"))
        session.commit()

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=2,
        mode="experience_first",
    )

    assert result["ok"] is True
    assert result["assignment"]["ta_id"] == tas[0].id


def test_least_loaded_selects_lowest_workload(allocation_db):
    hod_id, course_id, tas = allocation_db

    with Session(allocations.engine) as session:
        session.add(Assignment(ta_id=tas[0].id, course_id=course_id, weekly_hours=10, created_at="now"))
        session.add(Assignment(ta_id=tas[1].id, course_id=course_id, weekly_hours=5, created_at="now"))
        session.commit()

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=2,
        mode="least_loaded",
    )

    assert result["ok"] is True
    assert result["assignment"]["ta_id"] == tas[2].id


def test_18_plus_2_is_allowed(allocation_db):
    hod_id, course_id, tas = allocation_db

    with Session(allocations.engine) as session:
        session.add(Assignment(ta_id=tas[0].id, course_id=course_id, weekly_hours=18, created_at="now"))
        session.commit()

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=2,
        mode="least_loaded",
    )

    assert result["ok"] is True


def test_18_plus_3_is_rejected(allocation_db):
    hod_id, course_id, tas = allocation_db

    with Session(allocations.engine) as session:
        session.add(Assignment(ta_id=tas[0].id, course_id=course_id, weekly_hours=18, created_at="now"))
        session.commit()

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=3,
        mode="least_loaded",
    )

    assert result["ok"] is True
    assert result["assignment"]["ta_id"] != tas[0].id


@pytest.mark.parametrize("weekly_hours", [0, -1])
def test_non_positive_hours_change_no_state(allocation_db, weekly_hours):
    hod_id, course_id, _ = allocation_db

    with Session(allocations.engine) as session:
        before_assignments = len(session.exec(select(Assignment)).all())
        before_budget = session.get(Department, 1).budget_hours_remaining

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=weekly_hours,
        mode="least_loaded",
    )

    with Session(allocations.engine) as session:
        assert len(session.exec(select(Assignment)).all()) == before_assignments
        assert session.get(Department, 1).budget_hours_remaining == before_budget
    assert result == {"ok": False, "error": "hours must be positive"}


def test_unknown_mode_changes_no_state(allocation_db):
    hod_id, course_id, _ = allocation_db

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=1,
        mode="unknown",
    )

    assert result["ok"] is False
    assert "Unsupported allocation mode" in result["error"]


def test_insufficient_budget_changes_no_state(allocation_db):
    hod_id, course_id, tas = allocation_db

    with Session(allocations.engine) as session:
        dept = session.get(Department, 1)
        dept.budget_hours_remaining = 1
        for ta in tas:
            session.add(Assignment(ta_id=ta.id, course_id=course_id, weekly_hours=20, created_at="now"))
        session.commit()

    before_budget = 1
    before_count = 3

    insufficient = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=2,
        mode="least_loaded",
    )

    with Session(allocations.engine) as session:
        assert session.get(Department, 1).budget_hours_remaining == before_budget
        assert len(session.exec(select(Assignment)).all()) == before_count

    assert insufficient == {"ok": False, "error": "exceeds department budget"}


def test_no_eligible_candidate_changes_no_state(allocation_db):
    hod_id, course_id, tas = allocation_db

    with Session(allocations.engine) as session:
        for ta in tas:
            session.add(Assignment(ta_id=ta.id, course_id=course_id, weekly_hours=20, created_at="now"))
        session.commit()

    before_budget = 62
    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=1,
        mode="least_loaded",
    )

    with Session(allocations.engine) as session:
        assert session.get(Department, 1).budget_hours_remaining == before_budget
        assert len(session.exec(select(Assignment)).all()) == 3

    assert result == {"ok": False, "error": "no TAs have sufficient weekly capacity"}


def test_success_persists_assignment_and_deducts_budget(allocation_db):
    hod_id, course_id, _ = allocation_db

    before_budget = 62
    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=3,
        mode="least_loaded",
    )

    with Session(allocations.engine) as session:
        assignments = session.exec(select(Assignment)).all()
        dept = session.get(Department, 1)

    assert result["ok"] is True
    assert len(assignments) == 1
    assert assignments[0].weekly_hours == 3
    assert dept.budget_hours_remaining == before_budget - 3


def test_persistence_failure_rolls_back_assignment_and_budget(allocation_db, monkeypatch):
    hod_id, course_id, _ = allocation_db

    def fail_commit(session):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(Session, "commit", fail_commit)

    result = allocations.assign_auto(
        hod_id,
        course_id=course_id,
        weekly_hours=3,
        mode="least_loaded",
    )

    assert result == {"ok": False, "error": "allocation could not be persisted"}

    with Session(allocations.engine) as session:
        assert len(session.exec(select(Assignment)).all()) == 0
        assert session.get(Department, 1).budget_hours_remaining == 62
