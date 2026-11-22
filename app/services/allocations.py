"""Manual and auto TA course assignment."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, func, select

from app.database import engine
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.department import Department
from app.models.ta import Ta
from app.models.ta_experience import TaExperience
from app.services.allocation_auth import get_user
from app.services.capacity_guard import CapacityGuard
from app.services.constants import WEEKLY_HOUR_CAP
from app.services.strategies import get_strategy

#recently edited
_RR_CURSOR = 0


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_tas() -> list[dict[str, Any]]:
    with Session(engine) as session:
        rows = session.exec(select(Ta).order_by(Ta.id)).all()
        return [r.model_dump() for r in rows]


def list_courses() -> list[dict[str, Any]]:
    with Session(engine) as session:
        rows = session.exec(select(Course).order_by(Course.id)).all()
        return [r.model_dump() for r in rows]


def list_assignments() -> list[dict[str, Any]]:
    with Session(engine) as session:
        rows = session.exec(select(Assignment).order_by(Assignment.id)).all()
        return [r.model_dump() for r in rows]


def _load_by_ta(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(Assignment.ta_id, func.sum(Assignment.weekly_hours)).group_by(
            Assignment.ta_id
        )
    ).all()
    return {ta_id: int(total) for ta_id, total in rows}


def _experience_set(session: Session) -> set[tuple[int, int]]:
    rows = session.exec(select(TaExperience.ta_id, TaExperience.course_id)).all()
    return {(ta_id, course_id) for ta_id, course_id in rows}


def _budget_remaining(session: Session) -> int:
    dept = session.get(Department, 1)
    return int(dept.budget_hours_remaining)


#recently edited
def _request_validation_error(hours: int, budget_remaining: int) -> str | None:
    try:
        CapacityGuard.validate_request(
            hours=hours,
            budget_remaining=budget_remaining,
        )
    except ValueError as exc:
        return str(exc)
    return None


#recently edited
def _ta_capacity(ta_id: int, load_by_ta: dict[int, int]) -> tuple[int, int]:
    used = load_by_ta.get(ta_id, 0)
    return used, WEEKLY_HOUR_CAP - used


#recently edited
def _persist_assignment(
    session: Session,
    *,
    ta_id: int,
    course_id: int,
    weekly_hours: int,
    department: Department,
) -> Assignment:
    current_load = _load_by_ta(session).get(ta_id, 0)
    CapacityGuard.validate_ta(current_load=current_load, hours=weekly_hours)

    row = Assignment(
        ta_id=ta_id,
        course_id=course_id,
        weekly_hours=weekly_hours,
        created_at=_now(),
    )
    department.budget_hours_remaining -= weekly_hours
    session.add(row)
    session.add(department)
    try:
        session.commit()
        session.refresh(row)
    except (SQLAlchemyError, RuntimeError):
        session.rollback()
        raise
    return row


def ta_remaining_hours(ta_id: int) -> int:
    with Session(engine) as session:
        _, remaining = _ta_capacity(ta_id, _load_by_ta(session))
    return remaining


#recently edited
def highlight_candidates(course_id: int) -> list[dict[str, Any]]:
    """Soft preference view — experienced flagged for HOD."""
    with Session(engine) as session:
        course = session.get(Course, course_id)
        if course is None:
            return []
        exp = _experience_set(session)
        load = _load_by_ta(session)
        tas = [t.model_dump() for t in session.exec(select(Ta).order_by(Ta.id)).all()]
    out = []
    for t in tas:
        used, remaining = _ta_capacity(t["id"], load)
        out.append(
            {
                **t,
                "prior_experience": (t["id"], course_id) in exp,
                "weekly_hours_used": used,
                "weekly_hours_remaining": remaining,
            }
        )
    return out


#recently edited
def assign_manual(
    hod_id: int, *, ta_id: int, course_id: int, weekly_hours: int
) -> dict[str, Any]:
    user = get_user(hod_id)
    if not user or user["role"] != "hod":
        return {"ok": False, "error": "hod only"}

    with Session(engine) as session:
        ta = session.get(Ta, ta_id)
        course = session.get(Course, course_id)
        if not ta or not course:
            return {"ok": False, "error": "ta or course not found"}

        department = session.get(Department, 1)
        if department is None:
            return {"ok": False, "error": "department not found"}

        request_error = _request_validation_error(
            weekly_hours,
            int(department.budget_hours_remaining),
        )
        if request_error:
            return {"ok": False, "error": request_error}

        try:
            row = _persist_assignment(
                session,
                ta_id=ta_id,
                course_id=course_id,
                weekly_hours=weekly_hours,
                department=department,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except (SQLAlchemyError, RuntimeError):
            return {"ok": False, "error": "allocation could not be persisted"}
        assignment = row.model_dump()

    return {
        "ok": True,
        "assignment": assignment,
        "over_cap": False,
        "over_budget": False,
    }


#recently edited
def assign_auto(
    hod_id: int, *, course_id: int, weekly_hours: int, mode: str
) -> dict[str, Any]:
    global _RR_CURSOR
    user = get_user(hod_id)
    if not user or user["role"] != "hod":
        return {"ok": False, "error": "hod only"}

    if weekly_hours <= 0:
        return {"ok": False, "error": "hours must be positive"}

    try:
        strategy = get_strategy(mode)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    with Session(engine) as session:
        course_row = session.get(Course, course_id)
        if course_row is None:
            return {"ok": False, "error": "course not found"}
        department = session.get(Department, 1)
        if department is None:
            return {"ok": False, "error": "department not found"}
        budget = int(department.budget_hours_remaining)

        request_error = _request_validation_error(weekly_hours, budget)
        if request_error:
            return {"ok": False, "error": request_error}

        tas = [t.model_dump() for t in session.exec(select(Ta).order_by(Ta.id)).all()]
        experience = _experience_set(session)
        load = _load_by_ta(session)
        eligible_tas = CapacityGuard.eligible_candidates(
            tas=tas,
            load_by_ta=load,
            hours=weekly_hours,
        )
        if not eligible_tas:
            return {"ok": False, "error": "no TAs have sufficient weekly capacity"}

        ranked_tas = strategy.rank(
            eligible_tas,
            course_id=course_id,
            experience_pairs=experience,
            load_by_ta=load,
        )
        if not ranked_tas:
            return {"ok": False, "error": "no eligible TAs"}

        next_cursor = None
        if mode == "round_robin":
            cursor = _RR_CURSOR % len(ranked_tas)
            selected_ta = ranked_tas[cursor]
            next_cursor = cursor + 1
        else:
            selected_ta = ranked_tas[0]

        ta_id = int(selected_ta["id"])
        current_load = load.get(ta_id, 0)
        try:
            row = _persist_assignment(
                session,
                ta_id=ta_id,
                course_id=course_id,
                weekly_hours=weekly_hours,
                department=department,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except (SQLAlchemyError, RuntimeError):
            return {"ok": False, "error": "allocation could not be persisted"}
        assignment = row.model_dump()

    if next_cursor is not None:
        _RR_CURSOR = next_cursor

    pick = {
        "ok": True,
        "ta_id": ta_id,
        "mode": mode,
        "reason": (
            "prior course experience"
            if (ta_id, course_id) in experience
            else "eligible candidate"
        ),
        "projected_load": current_load + weekly_hours,
        "cap": WEEKLY_HOUR_CAP,
    }
    if next_cursor is not None:
        pick["next_cursor"] = next_cursor

    return {
        "ok": True,
        "assignment": assignment,
        "auto": pick,
        "over_cap": False,
        "over_budget": False,
    }


#recently edited
def review_board() -> dict[str, Any]:
    with Session(engine) as session:
        courses = [c.model_dump() for c in session.exec(select(Course)).all()]
        assignments = [a.model_dump() for a in session.exec(select(Assignment)).all()]
        load = _load_by_ta(session)
        budget = _budget_remaining(session)
        tas = [t.model_dump() for t in session.exec(select(Ta)).all()]
    ta_view = []
    for ta in tas:
        used, remaining = _ta_capacity(ta["id"], load)
        ta_view.append(
            {
                **ta,
                "weekly_hours_used": used,
                "weekly_hours_remaining": remaining,
            }
        )
    return {
        "courses": courses,
        "assignments": assignments,
        "tas": ta_view,
        "budget_hours_remaining": budget,
        "weekly_hour_cap": WEEKLY_HOUR_CAP,
    }
