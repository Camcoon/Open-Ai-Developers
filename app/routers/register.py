from typing import Annotated

from fastapi import Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.dependencies import SessionDep
from app.models.course import Course
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService
from app.utilities.flash import flash

from . import router, templates


# View route (loads the page)
@router.get("/register", response_class=HTMLResponse)
async def register_view(request: Request, db: SessionDep):
    courses = db.exec(select(Course).order_by(Course.code)).all()
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"courses": courses},
    )


# Action route (performs an action)
@router.post(
    "/register",
    response_class=HTMLResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup_user(
    request: Request,
    db: SessionDep,
    username: str = Form(),
    email: str = Form(),
    password: str = Form(),
    name: str = Form(""),
    role: str = Form("regular_user"),
    experience_course_ids: Annotated[list[int] | None, Form()] = None,
):
    user_repo = UserRepository(db)
    auth_service = AuthService(user_repo)
    try:
        auth_service.register_user(
            username,
            email,
            password,
            role=role,
            name=name,
            experience_course_ids=experience_course_ids,
        )
        flash(request, "Registration completed! Sign in now!")
        return RedirectResponse(
            url=request.url_for("login_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("register_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except IntegrityError:
        flash(request, "Username or email already exists", "danger")
        return RedirectResponse(
            url=request.url_for("register_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
