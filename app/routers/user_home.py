from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep
from app.services import allocations
from app.utilities.flash import flash

from . import router, templates


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(request: Request, user: AuthDep):
    if user.role not in {"hod", "admin", "deputy"}:
        return templates.TemplateResponse(
            request=request,
            name="app.html",
            context={
                "user": user,
                "personal_dashboard": allocations.personal_dashboard(
                    email=str(user.email),
                    fallback_name=user.username,
                ),
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={
            "user": user,
            **allocations.review_board(),
            "show_details": False,
        },
    )


@router.get(
    "/allocations",
    response_class=HTMLResponse,
    name="manage_allocations_view",
)
async def manage_allocations_view(request: Request, user: AuthDep):
    if user.role not in {"hod", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD or admin only",
        )

    return templates.TemplateResponse(
        request=request,
        name="manage_allocations.html",
        context={
            "user": user,
            **allocations.allocation_management_data(),
        },
    )


@router.post("/allocations/manual", name="create_manual_assignment")
async def create_manual_assignment(
    request: Request,
    user: AuthDep,
    ta_id: int = Form(...),
    course_id: int = Form(...),
    weekly_hours: int = Form(...),
    start_week: int = Form(1),
    end_week: int = Form(1),
):
    if user.role not in {"hod", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD or admin only",
        )
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identity is missing",
        )

    result = allocations.assign_manual(
        user.id,
        ta_id=ta_id,
        course_id=course_id,
        weekly_hours=weekly_hours,
        start_week=start_week,
        end_week=end_week,
    )
    if result["ok"]:
        flash(request, "Assignment created successfully.")
    else:
        flash(request, result["error"], "danger")

    return RedirectResponse(
        url=request.url_for("manage_allocations_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/allocations/auto/suggest", name="suggest_automatic_assignment")
async def suggest_automatic_assignment(
    request: Request,
    user: AuthDep,
    course_id: int = Form(...),
    weekly_hours: int = Form(...),
    mode: str = Form(...),
    start_week: int = Form(1),
    end_week: int = Form(1),
):
    if user.role not in {"hod", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD or admin only",
        )

    result = allocations.suggest_auto(
        user.id,
        course_id=course_id,
        weekly_hours=weekly_hours,
        mode=mode,
        start_week=start_week,
        end_week=end_week,
    )
    if not result["ok"]:
        flash(request, result["error"], "danger")
        recommendations = None
    else:
        recommendations = result

    return templates.TemplateResponse(
        request=request,
        name="manage_allocations.html",
        context={
            "user": user,
            **allocations.allocation_management_data(),
            "recommendations": recommendations,
            "selected_course_id": course_id,
            "selected_weekly_hours": weekly_hours,
            "selected_mode": mode,
            "selected_start_week": start_week,
            "selected_end_week": end_week,
        },
    )


@router.post("/allocations/auto", name="create_automatic_assignment")
async def create_automatic_assignment(
    request: Request,
    user: AuthDep,
    course_id: int = Form(...),
    weekly_hours: int = Form(...),
    mode: str = Form(...),
    start_week: int = Form(1),
    end_week: int = Form(1),
):
    if user.role not in {"hod", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD or admin only",
        )
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identity is missing",
        )

    result = allocations.assign_auto(
        user.id,
        course_id=course_id,
        weekly_hours=weekly_hours,
        mode=mode,
        start_week=start_week,
        end_week=end_week,
    )
    if result["ok"]:
        flash(request, "Automatic allocation created successfully.")
    else:
        flash(request, result["error"], "danger")

    return RedirectResponse(
        url=request.url_for("manage_allocations_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
