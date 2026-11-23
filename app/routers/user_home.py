from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep
from app.services import allocations
from app.utilities.flash import flash

from . import router, templates


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(request: Request, user: AuthDep):
    if user.role not in {"hod", "admin"}:
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
    )
    if result["ok"]:
        flash(request, "Assignment created successfully.")
    else:
        flash(request, result["error"], "danger")

    return RedirectResponse(
        url=request.url_for("manage_allocations_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
