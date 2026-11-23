"""TA allocations scenario JSON API (OpenAPI /docs)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field

from app.services import allocation_auth as auth
from app.services import allocations
from app.services.strategies import MODES
from app.config import get_settings
from app.utilities.security import create_access_token

router = APIRouter(tags=["ta-allocations"])


class LoginBody(BaseModel):
    email: str
    password: str


class ManualAssignBody(BaseModel):
    ta_id: int
    course_id: int
    weekly_hours: int
    start_week: int = 1
    end_week: int = 1


class AutoAssignBody(BaseModel):
    course_id: int
    weekly_hours: int
    mode: str = Field(description=" | ".join(MODES))
    start_week: int = 1
    end_week: int = 1


class SuggestionBody(AutoAssignBody):
    pass


class EditAssignmentBody(BaseModel):
    weekly_hours: int
    start_week: int = 1
    end_week: int = 1


class EndAssignmentBody(BaseModel):
    end_week: int


def _actor_id(request: Request, x_user_id: str | None) -> int:
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    if token:
        try:
            payload = jwt.decode(
                token,
                get_settings().secret_key,
                algorithms=[get_settings().jwt_algorithm],
            )
            return int(payload["sub"])
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="invalid bearer token") from exc
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        return int(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-User-Id must be int") from exc


@router.post("/auth/login")
def login(body: LoginBody) -> dict[str, Any]:
    user = auth.login(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return {"user": user, "access_token": token, "token_type": "bearer"}


@router.get("/tas")
def tas() -> dict[str, Any]:
    return {"tas": allocations.list_tas()}


@router.get("/courses")
def courses() -> dict[str, Any]:
    return {"courses": allocations.list_courses()}


@router.get("/courses/{course_id}/candidates")
def candidates(course_id: int) -> dict[str, Any]:
    return {"candidates": allocations.highlight_candidates(course_id)}


@router.get("/assignments")
def assignments() -> dict[str, Any]:
    return {"assignments": allocations.list_assignments()}


@router.patch("/assignments/{assignment_id}")
def edit(
    request: Request,
    assignment_id: int,
    body: EditAssignmentBody,
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    result = allocations.edit_assignment(
        _actor_id(request, x_user_id),
        assignment_id,
        weekly_hours=body.weekly_hours,
        start_week=body.start_week,
        end_week=body.end_week,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/assignments/{assignment_id}/end")
def end(
    request: Request,
    assignment_id: int,
    body: EndAssignmentBody,
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    result = allocations.end_assignment(
        _actor_id(request, x_user_id),
        assignment_id,
        body.end_week,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/review")
def review() -> dict[str, Any]:
    return allocations.review_board()


@router.post("/assignments/manual")
def manual(
    request: Request,
    body: ManualAssignBody,
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    result = allocations.assign_manual(
        _actor_id(request, x_user_id),
        ta_id=body.ta_id,
        course_id=body.course_id,
        weekly_hours=body.weekly_hours,
        start_week=body.start_week,
        end_week=body.end_week,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/assignments/auto")
def auto(
    request: Request,
    body: AutoAssignBody,
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    result = allocations.assign_auto(
        _actor_id(request, x_user_id),
        course_id=body.course_id,
        weekly_hours=body.weekly_hours,
        mode=body.mode,
        start_week=body.start_week,
        end_week=body.end_week,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/assignments/suggest")
def suggest(
    request: Request,
    body: SuggestionBody,
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    result = allocations.suggest_auto(
        _actor_id(request, x_user_id),
        course_id=body.course_id,
        weekly_hours=body.weekly_hours,
        mode=body.mode,
        start_week=body.start_week,
        end_week=body.end_week,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/assignments/export.csv")
def export_assignments() -> Response:
    return Response(
        content=allocations.assignments_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assignments.csv"},
    )
