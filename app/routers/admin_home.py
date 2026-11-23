from typing import Annotated

from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.dependencies.auth import AdminDep, AuthDep, CourseManagerDep
from app.dependencies.session import SessionDep
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.ta import Ta
from app.models.ta_experience import TaExperience
from app.models.user import User
from app.repositories.user import UserRepository
from app.services import allocations
from app.services.auth_service import AuthService
from app.utilities.flash import flash

from . import router, templates


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(request: Request, user: AdminDep):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            **allocations.review_board(),
        },
    )


@router.get("/review", response_class=HTMLResponse, name="review_board_view")
async def review_board_view(request: Request, user: AuthDep):
    if user.role not in {"hod", "admin", "deputy"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD or admin only",
        )
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "user": user,
            **allocations.review_board(),
            "show_details": True,
        },
    )


@router.get(
    "/manage-courses",
    response_class=HTMLResponse,
    name="manage_courses_view",
)
async def manage_courses_view(
    request: Request,
    user: CourseManagerDep,
    db: SessionDep,
):
    courses = db.exec(select(Course).order_by(Course.code)).all()
    return templates.TemplateResponse(
        request=request,
        name="manage_courses.html",
        context={
            "user": user,
            "courses": courses,
        },
    )


@router.post("/manage-courses", name="create_course")
def create_course(
    request: Request,
    user: CourseManagerDep,
    db: SessionDep,
    code: str = Form(...),
    title: str = Form(...),
    budgeted_hours: int = Form(...),
):
    normalized_code = code.strip().upper()
    normalized_title = title.strip()
    if not normalized_code or not normalized_title or budgeted_hours <= 0:
        flash(
            request,
            "Enter a course code, title, and positive budgeted hours.",
            "danger",
        )
        return RedirectResponse(
            url=request.url_for("manage_courses_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    existing_course = db.exec(
        select(Course).where(Course.code == normalized_code)
    ).first()
    if existing_course is not None:
        flash(request, "A course with that code already exists.", "danger")
        return RedirectResponse(
            url=request.url_for("manage_courses_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    db.add(
        Course(
            code=normalized_code,
            title=normalized_title,
            budgeted_hours=budgeted_hours,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, "A course with that code already exists.", "danger")
    else:
        flash(request, "Course created successfully.")

    return RedirectResponse(
        url=request.url_for("manage_courses_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manage-courses/delete/{course_id}", name="delete_course")
def delete_course(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    course_id: int,
):
    course = db.get(Course, course_id)
    if course is None:
        flash(request, "Course not found.", "danger")
        return RedirectResponse(
            url=request.url_for("manage_courses_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    assignment = db.exec(
        select(Assignment).where(Assignment.course_id == course_id)
    ).first()
    if assignment is not None:
        flash(
            request,
            "Cannot delete a course with active assignments. Remove its assignments first.",
            "danger",
        )
        return RedirectResponse(
            url=request.url_for("manage_courses_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    experiences = db.exec(
        select(TaExperience).where(TaExperience.course_id == course_id)
    ).all()
    for experience in experiences:
        db.delete(experience)
    db.delete(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, "Course cannot be deleted while it is in use.", "danger")
    else:
        flash(request, "Course deleted successfully.")

    return RedirectResponse(
        url=request.url_for("manage_courses_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/accounts", response_class=HTMLResponse, name="manage_accounts_view")
async def manage_accounts_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
):
    users = db.exec(select(User).order_by(User.username)).all()
    ta_profiles = {ta.email: ta for ta in db.exec(select(Ta)).all()}
    ta_experiences: dict[int, list[int]] = {}
    for experience in db.exec(select(TaExperience)).all():
        ta_experiences.setdefault(experience.ta_id, []).append(experience.course_id)
    courses = db.exec(select(Course).order_by(Course.code)).all()
    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={
            "user": user,
            "users": users,
            "ta_profiles": ta_profiles,
            "ta_experiences": ta_experiences,
            "courses": courses,
            "roles": (
                ("regular_user", "Regular user"),
                ("ta", "Teaching assistant"),
                ("deputy", "Deputy"),
                ("hod", "Head of department"),
                ("admin", "Admin"),
            ),
        },
    )


@router.post("/accounts", name="create_managed_account")
def create_managed_account(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    name: str = Form(""),
    experience_course_ids: Annotated[list[int] | None, Form()] = None,
):
    auth_service = AuthService(UserRepository(db))
    try:
        auth_service.create_managed_user(
            username,
            email,
            password,
            role=role,
            name=name,
            experience_course_ids=experience_course_ids,
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
    except IntegrityError:
        flash(request, "Username or email already exists.", "danger")
    else:
        flash(request, "Account created successfully.")

    return RedirectResponse(
        url=request.url_for("manage_accounts_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/accounts/{account_id}/role", name="update_account_role")
def update_account_role(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    account_id: int,
    role: str = Form(...),
    name: str = Form(""),
    experience_course_ids: Annotated[list[int] | None, Form()] = None,
):
    allowed_roles = {"regular_user", "ta", "deputy", "hod", "admin"}
    account = db.get(User, account_id)
    if account is None:
        flash(request, "Account not found.", "danger")
    elif role not in allowed_roles:
        flash(request, "Select a valid account role.", "danger")
    elif account.id == user.id and role != "admin":
        flash(request, "You cannot demote your own admin account.", "danger")
    elif role == "ta" and not name.strip():
        flash(request, "Enter a name for the TA profile.", "danger")
    else:
        user_repo = UserRepository(db)
        if role == "ta":
            ta_profile = db.exec(select(Ta).where(Ta.email == account.email)).first()
            if ta_profile is None:
                ta_profile = Ta(name=name.strip(), email=account.email)
                db.add(ta_profile)
                db.flush()
            else:
                ta_profile.name = name.strip()
                db.add(ta_profile)
            if ta_profile.id is None:
                raise RuntimeError("TA profile was not assigned an ID")
            try:
                user_repo.replace_ta_experience(
                    ta_profile.id,
                    experience_course_ids or [],
                )
            except ValueError as exc:
                db.rollback()
                flash(request, str(exc), "danger")
                return RedirectResponse(
                    url=request.url_for("manage_accounts_view"),
                    status_code=status.HTTP_303_SEE_OTHER,
                )
        account.role = role
        db.add(account)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            flash(request, "Could not update this account.", "danger")
        else:
            flash(request, "Account role updated successfully.")

    return RedirectResponse(
        url=request.url_for("manage_accounts_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
