"""Manual and auto TA course assignment."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
from app.services.strategies import MODES, auto_select_ta

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

        load = _load_by_ta(session).get(ta_id, 0)
        dept = session.get(Department, 1)
        budget = int(dept.budget_hours_remaining)
        
        request_error = _request_validation_error(weekly_hours, budget)
        if request_error:
            return {"ok": False, "error": request_error}
            
        try:
            CapacityGuard.validate_ta(current_load=load, hours=weekly_hours)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        row = Assignment(
            ta_id=ta_id,
            course_id=course_id,
            weekly_hours=weekly_hours,
            created_at=_now(),
        )
        session.add(row)
        dept.budget_hours_remaining -= weekly_hours
        session.add(dept)
        session.commit()
        session.refresh(row)
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
    if mode not in MODES:
        pass

    with Session(engine) as session:
        course_row = session.get(Course, course_id)
        if course_row is None:
            return {"ok": False, "error": "course not found"}
        course = course_row.model_dump()
        budget = _budget_remaining(session)
        
        request_error = _request_validation_error(weekly_hours, budget)
        if request_error:
            return {"ok": False, "error": request_error}

        tas = [t.model_dump() for t in session.exec(select(Ta).order_by(Ta.id)).all()]
        exp = _experience_set(session)
        load = _load_by_ta(session)
        eligible_tas = CapacityGuard.eligible_candidates(
            tas=tas,
            load_by_ta=load,
            hours=weekly_hours,
        )
        if not eligible_tas:
            return {"ok": False, "error": "no TAs have sufficient weekly capacity"}

    pick = auto_select_ta(
        mode=mode,
        course=course,
        tas=eligible_tas,
        experience=exp,
        load_by_ta=load,
        budget_remaining=budget,
        hours=weekly_hours,
        round_robin_cursor=_RR_CURSOR,
    )
    if not pick.get("ok"):
        return pick

    result = assign_manual(
        hod_id,
        ta_id=pick["ta_id"],
        course_id=course_id,
        weekly_hours=weekly_hours,
    )
    if result.get("ok"):
        result["auto"] = pick
        if "next_cursor" in pick:
            _RR_CURSOR = int(pick["next_cursor"])
    return result


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