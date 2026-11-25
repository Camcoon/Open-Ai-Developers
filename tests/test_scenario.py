"""Shallow scenario smoke tests — intentionally weak."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.department import Department
from app.models.ta import Ta
from app.models.ta_experience import TaExperience
from app.models.user import User
from app.seed import seed


def setup_module() -> None:
    seed(reset=True)


client = TestClient(app)


def _login_cookie(username: str, password: str) -> str:
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    cookie = response.cookies.get("access_token")
    assert cookie
    return cookie


def _register_cookie(
    username: str,
    role: str,
    name: str = "",
    experience_course_ids: list[int] | None = None,
) -> str:
    data = {
        "username": username,
        "name": name,
        "email": f"{username}@example.com",
        "password": "test-password",
        "role": role,
    }
    if experience_course_ids:
        data["experience_course_ids"] = [
            str(course_id) for course_id in experience_course_ids
        ]
    response = client.post(
        "/register",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303
    return _login_cookie(username, "test-password")


@pytest.fixture
def reset_scenario():
    seed(reset=True)
    yield


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["scenario"] == "ta-allocations"


def test_login_hod():
    r = client.post(
        "/api/auth/login",
        json={"email": "hod@example.com", "password": "hod-dev"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "hod"
    assert "password" not in r.json()["user"]
    assert "password_hash" not in r.json()["user"]


# recently edited
def test_openapi_docs_are_admin_only():
    assert client.get("/docs").status_code == 401
    assert client.get("/openapi.json").status_code == 401

    hod_login = client.post(
        "/login",
        data={"username": "hod", "password": "hod-dev"},
        follow_redirects=False,
    )
    hod_cookie = hod_login.cookies.get("access_token")
    assert hod_cookie
    hod_home = client.get("/app", cookies={"access_token": hod_cookie})
    assert hod_home.status_code == 200
    assert 'href="/docs"' not in hod_home.text
    assert client.get("/docs", cookies={"access_token": hod_cookie}).status_code == 403
    assert (
        client.get("/openapi.json", cookies={"access_token": hod_cookie}).status_code
        == 403
    )

    admin_login = client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    admin_cookie = admin_login.cookies.get("access_token")
    assert admin_cookie
    admin_home = client.get("/admin", cookies={"access_token": admin_cookie})
    assert admin_home.status_code == 200
    assert 'href="/docs"' in admin_home.text
    docs = client.get("/docs", cookies={"access_token": admin_cookie})
    schema = client.get("/openapi.json", cookies={"access_token": admin_cookie})
    assert docs.status_code == 200
    assert "/openapi.json" in docs.text
    assert schema.status_code == 200
    assert "/api/review" in schema.json()["paths"]


# recently edited
def test_review_board():
    r = client.get("/api/review")
    assert r.status_code == 200
    board = r.json()
    assert "tas" in board
    assert "assignments" in r.json()
    board_ta = next(ta for ta in board["tas"] if ta["id"] == 1)
    candidate_ta = next(
        ta
        for ta in client.get("/api/courses/1/candidates").json()["candidates"]
        if ta["id"] == 1
    )
    assert candidate_ta["weekly_hours_used"] == board_ta["weekly_hours_used"]
    assert candidate_ta["weekly_hours_remaining"] == board_ta["weekly_hours_remaining"]


def test_admin_dashboard_renders_allocation_data(reset_scenario):
    login_response = client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    cookie = login_response.cookies.get("access_token")
    response = client.get("/admin", cookies={"access_token": cookie})

    assert response.status_code == 200
    assert "Alex TA" in response.text
    assert "Total TAs" in response.text
    assert "Total courses" in response.text
    assert "Department budget remaining" in response.text
    assert "62" in response.text
    assert "18" in response.text
    assert "2" in response.text
    assert "Current assignments" not in response.text
    body = response.text.split('<main class="app-main">', 1)[1]
    assert 'href="/api/assignments"' not in body
    assert 'href="/review"' not in body
    assert 'href="/accounts"' not in body
    for link_text in (
        "Home",
        "Manage Assignments",
        "Manage Courses",
        "Review Board",
        "Admin Overview",
        "Manage Accounts",
        "API docs",
        "Sign out",
    ):
        assert f">{link_text}</a>" in response.text

    assert (
        client.get("/allocations", cookies={"access_token": cookie}).status_code == 200
    )

    review_response = client.get("/review", cookies={"access_token": cookie})
    assert 'href="/api/review"' not in review_response.text
    assert 'href="/api/tas"' not in review_response.text


def test_admin_and_hod_can_manage_courses(reset_scenario):
    admin_cookie = _login_cookie("admin", "admin")
    page = client.get("/manage-courses", cookies={"access_token": admin_cookie})

    assert page.status_code == 200
    assert "COMP3613" in page.text
    nav = page.text.split('<nav class="app-topnav"', 1)[1].split("</nav>", 1)[0]
    for path in ("/api/review", "/api/assignments", "/api/tas", "/api/courses"):
        assert path not in nav
    for label in (
        "Home",
        "Manage Assignments",
        "Review Board",
        "Admin Overview",
        "Manage Courses",
        "API docs",
        "Sign out",
    ):
        assert f">{label}</a>" in nav

    created = client.post(
        "/manage-courses",
        data={
            "code": "COMP9999",
            "title": "Test course",
            "budgeted_hours": "12",
        },
        cookies={"access_token": admin_cookie},
        follow_redirects=True,
    )
    assert created.status_code == 200
    assert "Course created successfully." in created.text
    assert "COMP9999" in created.text

    hod_cookie = _login_cookie("hod", "hod-dev")
    hod_page = client.get(
        "/manage-courses",
        cookies={"access_token": hod_cookie},
    )
    assert hod_page.status_code == 200
    assert "Delete" not in hod_page.text
    assert "Manage Courses" in hod_page.text

    hod_created = client.post(
        "/manage-courses",
        data={
            "code": "COMP9998",
            "title": "HOD course",
            "budgeted_hours": "10",
        },
        cookies={"access_token": hod_cookie},
        follow_redirects=True,
    )
    assert "Course created successfully." in hod_created.text
    assert "COMP9998" in hod_created.text


def test_course_deletion_requires_admin_and_blocks_assigned_courses(reset_scenario):
    admin_cookie = _login_cookie("admin", "admin")
    hod_cookie = _login_cookie("hod", "hod-dev")

    with Session(engine) as session:
        assigned_course = session.exec(
            select(Course).where(Course.code == "COMP3613")
        ).one()
        unused_course = session.exec(
            select(Course).where(Course.code == "COMP2602")
        ).one()
        assigned_course_id = assigned_course.id
        unused_course_id = unused_course.id

    client.cookies.clear()
    client.cookies.set("access_token", admin_cookie)
    blocked = client.post(
        f"/manage-courses/delete/{assigned_course_id}",
        follow_redirects=True,
    )
    assert "Cannot delete a course with active assignments." in blocked.text
    with Session(engine) as session:
        assert session.get(Course, assigned_course_id) is not None

    client.cookies.clear()
    client.cookies.set("access_token", hod_cookie)
    denied = client.post(
        f"/manage-courses/delete/{unused_course_id}",
        follow_redirects=False,
    )
    assert denied.status_code == 403

    client.cookies.clear()
    client.cookies.set("access_token", admin_cookie)
    deleted = client.post(
        f"/manage-courses/delete/{unused_course_id}",
        follow_redirects=True,
    )
    assert "Course deleted successfully." in deleted.text
    with Session(engine) as session:
        assert session.get(Course, unused_course_id) is None


def test_admin_accounts_create_roles_and_preserve_ta_profile(reset_scenario):
    admin_cookie = _login_cookie("admin", "admin")
    hod_cookie = _login_cookie("hod", "hod-dev")
    assert (
        client.get("/accounts", cookies={"access_token": hod_cookie}).status_code == 403
    )
    admin_cookie = _login_cookie("admin", "admin")

    page = client.get("/accounts", cookies={"access_token": admin_cookie})
    assert page.status_code == 200
    assert "Create account" in page.text
    assert "Existing accounts" in page.text
    assert "Prior course experience" in page.text

    with Session(engine) as session:
        experience_course_ids = session.exec(
            select(Course.id).where(Course.code == "COMP1601")
        ).all()
        experience_course_ids.append(
            session.exec(select(Course.id).where(Course.code == "COMP2602")).one()
        )

    created = client.post(
        "/accounts",
        data={
            "username": "new-ta",
            "name": "New Teaching Assistant",
            "email": "new-ta@example.com",
            "password": "initial-secret",
            "role": "ta",
            "experience_course_ids": [str(course_id) for course_id in experience_course_ids],
        },
        cookies={"access_token": admin_cookie},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert (
        "Account created successfully."
        in client.get("/accounts", cookies={"access_token": admin_cookie}).text
    )
    with Session(engine) as session:
        admin_id = session.exec(select(User.id).where(User.username == "admin")).one()
        ta_user = session.exec(select(User).where(User.username == "new-ta")).one()
        ta_profile = session.exec(
            select(Ta).where(Ta.email == "new-ta@example.com")
        ).one()
        ta_experience = session.exec(
            select(TaExperience)
            .where(TaExperience.ta_id == ta_profile.id)
            .order_by(TaExperience.course_id)
        ).all()
        assert ta_user.role == "ta"
        assert ta_user.password != "initial-secret"
        assert ta_profile.name == "New Teaching Assistant"
        assert [experience.course_id for experience in ta_experience] == sorted(
            experience_course_ids
        )
        ta_user_id = ta_user.id
        ta_profile_id = ta_profile.id
        ta_experience_id = ta_experience[0].id

    changed_role = client.post(
        f"/accounts/{ta_user_id}/role",
        data={"role": "regular_user", "name": "New Teaching Assistant"},
        cookies={"access_token": admin_cookie},
        follow_redirects=False,
    )
    assert changed_role.status_code == 303
    assert (
        "Account role updated successfully."
        in client.get("/accounts", cookies={"access_token": admin_cookie}).text
    )
    with Session(engine) as session:
        assert session.get(User, ta_user_id).role == "regular_user"
        assert session.get(Ta, ta_profile_id).name == "New Teaching Assistant"
        assert session.get(TaExperience, ta_experience_id) is not None

    for username, role in (("new-hod", "hod"), ("second-admin", "admin")):
        response = client.post(
            "/accounts",
            data={
                "username": username,
                "name": "",
                "email": f"{username}@example.com",
                "password": "initial-secret",
                "role": role,
            },
            cookies={"access_token": admin_cookie},
            follow_redirects=False,
        )
        assert response.status_code == 303
        with Session(engine) as session:
            created_account = session.exec(
                select(User).where(User.username == username)
            ).one()
            assert created_account.role == role

    self_demotion = client.post(
        f"/accounts/{admin_id}/role",
        data={"role": "hod", "name": ""},
        cookies={"access_token": admin_cookie},
        follow_redirects=False,
    )
    assert self_demotion.status_code == 303
    with Session(engine) as session:
        assert session.get(User, admin_id).role == "admin"


def test_review_page_renders_board_for_hod(reset_scenario):
    login_response = client.post(
        "/login",
        data={"username": "hod", "password": "hod-dev"},
        follow_redirects=False,
    )
    cookie = login_response.cookies.get("access_token")
    response = client.get("/review", cookies={"access_token": cookie})

    assert response.status_code == 200
    assert "Current assignments" in response.text
    assert "Alex TA" in response.text
    assert "COMP3613" in response.text
    assert "Hours remaining" in response.text
    assert 'href="/api/review"' not in response.text
    assert 'href="/api/assignments"' not in response.text
    assert 'href="/api/tas"' not in response.text


def test_app_home_renders_allocation_summary(reset_scenario):
    login_response = client.post(
        "/login",
        data={"username": "hod", "password": "hod-dev"},
        follow_redirects=False,
    )
    cookie = login_response.cookies.get("access_token")
    response = client.get("/app", cookies={"access_token": cookie})

    assert response.status_code == 200
    assert "Allocation overview" in response.text
    assert "Department hours remaining" in response.text
    body = response.text.split('<main class="app-main">', 1)[1]
    assert 'href="/review"' not in body
    assert 'href="/allocations"' not in body
    assert "Manage Assignments</a>" not in body
    nav = response.text.split('<nav class="app-topnav"', 1)[1].split("</nav>", 1)[0]
    assert ">Manage Assignments</a>" in nav
    assert ">Manage Courses</a>" in nav
    assert ">Review Board</a>" in nav
    assert 'href="/api/courses"' not in response.text
    assert 'href="/api/tas"' not in response.text


def test_deputy_navigation_only_shows_permitted_pages(reset_scenario):
    admin_cookie = _login_cookie("admin", "admin")
    client.post(
        "/accounts",
        data={
            "username": "deputy",
            "email": "deputy@example.com",
            "password": "deputy-password",
            "role": "deputy",
        },
        cookies={"access_token": admin_cookie},
        follow_redirects=False,
    )
    deputy_cookie = _login_cookie("deputy", "deputy-password")

    home = client.get("/app", cookies={"access_token": deputy_cookie})
    nav = home.text.split('<nav class="app-topnav"', 1)[1].split("</nav>", 1)[0]
    assert home.status_code == 200
    assert ">Manage Assignments</a>" not in nav
    assert ">Manage Courses</a>" not in nav
    assert ">Review Board</a>" in nav
    review = client.get("/review", cookies={"access_token": deputy_cookie})
    allocations_page = client.get(
        "/allocations",
        cookies={"access_token": deputy_cookie},
    )
    courses_page = client.get(
        "/manage-courses",
        cookies={"access_token": deputy_cookie},
    )
    assert review.status_code == 200
    assert allocations_page.status_code == 403
    assert courses_page.status_code == 403


def test_ta_registration_rejects_unknown_experience_courses(reset_scenario):
    registration_page = client.get("/register")
    assert registration_page.status_code == 200
    assert "COMP1601" in registration_page.text

    response = client.post(
        "/register",
        data={
            "username": "invalid-experience-ta",
            "name": "Invalid Experience TA",
            "email": "invalid-experience-ta@example.com",
            "password": "test-password",
            "role": "ta",
            "experience_course_ids": ["999999"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Select only existing courses for TA experience" in response.text
    with Session(engine) as session:
        assert (
            session.exec(
                select(User).where(User.username == "invalid-experience-ta")
            ).first()
            is None
        )
        assert (
            session.exec(
                select(Ta).where(Ta.email == "invalid-experience-ta@example.com")
            ).first()
            is None
        )


def test_ta_home_shows_only_own_courses_and_remaining_hours(reset_scenario):
    with Session(engine) as session:
        experience_course_id = session.exec(
            select(Course.id).where(Course.code == "COMP1601")
        ).one()
    cookie = _register_cookie(
        "dashboard-ta",
        "ta",
        "Dashboard TA",
        experience_course_ids=[experience_course_id],
    )
    with Session(engine) as session:
        ta = session.exec(
            select(Ta).where(Ta.email == "dashboard-ta@example.com")
        ).one()
        course = session.exec(select(Course).where(Course.code == "COMP2602")).one()
        session.add(
            Assignment(
                ta_id=ta.id,
                course_id=course.id,
                weekly_hours=5,
                created_at="2099-01-01T10:00:00+00:00",
            )
        )
        session.commit()

    response = client.get("/app", cookies={"access_token": cookie})

    assert response.status_code == 200
    assert "Welcome, Dashboard TA" in response.text
    assert "COMP2602" in response.text
    assert "Databases" in response.text
    assert "Your weekly hours remaining" in response.text
    assert ">15<" in response.text
    assert "Your prior course experience" in response.text
    assert "COMP1601" in response.text
    for private_global_value in (
        "Department",
        "Total TAs",
        "Total courses",
        "Alex TA",
        "COMP3613",
        "Review Board",
        "Manage Assignments",
        "Admin Overview",
    ):
        assert private_global_value not in response.text
    assert 'href="/review"' not in response.text
    assert 'href="/allocations"' not in response.text
    assert 'href="/admin"' not in response.text


def test_regular_user_home_shows_only_personal_empty_state(reset_scenario):
    cookie = _register_cookie("dashboard-user", "regular_user")
    response = client.get("/app", cookies={"access_token": cookie})

    assert response.status_code == 200
    assert "Welcome, dashboard-user" in response.text
    assert "No courses are assigned to you." in response.text
    assert "Your weekly hours remaining" in response.text
    assert ">20<" in response.text
    assert "Department" not in response.text
    assert "Total TAs" not in response.text
    assert "Total courses" not in response.text
    nav = response.text.split('<nav class="app-topnav"', 1)[1].split("</nav>", 1)[0]
    assert ">Home</a>" in nav
    assert ">Sign out</a>" in nav
    for forbidden_link in (
        "/review",
        "/allocations",
        "/admin",
        "/manage-courses",
        "/accounts",
    ):
        assert f'href="{forbidden_link}' not in nav


def test_ta_and_regular_users_get_forbidden_on_restricted_routes(reset_scenario):
    restricted_paths = (
        "/admin",
        "/allocations",
        "/review",
        "/manage-courses",
        "/accounts",
    )
    for username, role in (
        ("restricted-ta", "ta"),
        ("restricted-user", "regular_user"),
    ):
        cookie = _register_cookie(
            username, role, "Restricted TA" if role == "ta" else ""
        )
        for path in restricted_paths:
            response = client.get(path, cookies={"access_token": cookie})
            assert response.status_code == 403, (role, path, response.status_code)

        assert (
            client.post(
                "/allocations/manual",
                data={"ta_id": "1", "course_id": "1", "weekly_hours": "1"},
                cookies={"access_token": cookie},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/manage-courses",
                data={"code": "COMP9997", "title": "Forbidden", "budgeted_hours": "1"},
                cookies={"access_token": cookie},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/accounts",
                data={
                    "username": "forbidden",
                    "email": "forbidden@example.com",
                    "password": "secret",
                    "role": "admin",
                },
                cookies={"access_token": cookie},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/accounts/1/role",
                data={"role": "admin"},
                cookies={"access_token": cookie},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/manage-courses/delete/1",
                cookies={"access_token": cookie},
            ).status_code
            == 403
        )


def test_hod_manage_allocations_page_shows_tas_courses_and_experience(
    reset_scenario,
):
    cookie = _login_cookie("hod", "hod-dev")
    response = client.get("/allocations", cookies={"access_token": cookie})

    assert response.status_code == 200
    assert "Manual assignment" in response.text
    assert "Available TAs" in response.text
    assert "Alex TA" in response.text
    assert "18" in response.text
    assert "2" in response.text
    assert "COMP3613" in response.text
    assert "Department budget remaining" in response.text
    assert "Manage Assignments</a>" in response.text
    assert "/allocations" in response.text


def test_manual_assignment_form_creates_assignment(reset_scenario):
    cookie = _login_cookie("hod", "hod-dev")
    response = client.post(
        "/allocations/manual",
        data={"ta_id": "2", "course_id": "1", "weekly_hours": "2"},
        cookies={"access_token": cookie},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Assignment created successfully." in response.text
    board = client.get("/api/review").json()
    assignment = board["assignments"][-1]
    assert assignment["ta_id"] == 2
    assert assignment["course_id"] == 1
    assert assignment["weekly_hours"] == 2
    assert board["budget_hours_remaining"] == 60


def test_manual_assignment_form_rejects_ta_over_weekly_cap(reset_scenario):
    cookie = _login_cookie("hod", "hod-dev")
    before = client.get("/api/assignments").json()["assignments"]
    response = client.post(
        "/allocations/manual",
        data={"ta_id": "1", "course_id": "1", "weekly_hours": "3"},
        cookies={"access_token": cookie},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "exceeds TA weekly hour cap" in response.text
    assert client.get("/api/assignments").json()["assignments"] == before


# recently edited
def _hod_user_id() -> int:
    response = client.post(
        "/api/auth/login",
        json={"email": "hod@example.com", "password": "hod-dev"},
    )
    assert response.status_code == 200
    return response.json()["user"]["id"]


def test_auto_validates_request_before_finding_candidates(monkeypatch):
    def fail_if_candidates_are_checked(*args, **kwargs):
        pytest.fail("candidate filtering ran before request validation")

    monkeypatch.setattr(
        "app.services.allocations.CapacityGuard.eligible_candidates",
        fail_if_candidates_are_checked,
    )
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 63, "mode": "round_robin"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "exceeds department budget"


def test_auto_revalidates_selected_ta_before_persistence(monkeypatch):
    before = client.get("/api/assignments").json()["assignments"]
    hod_id = _hod_user_id()

    def reject_selected_ta(*args, **kwargs):
        raise ValueError("selected TA capacity changed")

    monkeypatch.setattr(
        "app.services.allocations.CapacityGuard.validate_ta",
        reject_selected_ta,
    )
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(hod_id)},
        json={"course_id": 1, "weekly_hours": 1, "mode": "round_robin"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "selected TA capacity changed"
    assert client.get("/api/assignments").json()["assignments"] == before


def test_auto_selects_only_tas_with_capacity():
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 3, "mode": "round_robin"},
    )

    assert response.status_code == 200
    assignment = response.json()["assignment"]
    assert assignment["ta_id"] != 1
    assert assignment["weekly_hours"] == 3


def test_auto_experience_first_allows_exactly_20_hours(reset_scenario):
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 2, "mode": "experience_first"},
    )

    assert response.status_code == 200
    assert response.json()["assignment"]["ta_id"] == 1
    assert response.json()["assignment"]["weekly_hours"] == 2


def test_auto_experience_first_excludes_ta_over_20(reset_scenario):
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 3, "mode": "experience_first"},
    )

    assert response.status_code == 200
    assert response.json()["assignment"]["ta_id"] != 1


def test_auto_least_loaded_persists_lowest_loaded_choice(reset_scenario):
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 2, "mode": "least_loaded"},
    )

    assert response.status_code == 200
    assert response.json()["assignment"]["ta_id"] == 2

    with Session(engine) as session:
        saved = session.exec(select(Assignment).order_by(Assignment.id)).all()
        dept = session.get(Department, 1)

    assert len(saved) == 2
    assert saved[-1].ta_id == 2
    assert saved[-1].weekly_hours == 2
    assert dept.budget_hours_remaining == 60


@pytest.mark.parametrize("weekly_hours", [0, -2])
def test_auto_rejects_non_positive_hours_without_state_change(
    reset_scenario, weekly_hours
):
    before = client.get("/api/assignments").json()["assignments"]

    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": weekly_hours, "mode": "least_loaded"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "hours must be positive"
    assert client.get("/api/assignments").json()["assignments"] == before


def test_auto_rejects_unknown_mode_without_state_change(reset_scenario):
    before = client.get("/api/assignments").json()["assignments"]

    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 1, "mode": "unsupported"},
    )

    assert response.status_code == 400
    assert "Unsupported allocation mode" in response.json()["detail"]
    assert client.get("/api/assignments").json()["assignments"] == before


def test_auto_rejects_insufficient_budget_without_state_change(reset_scenario):
    with Session(engine) as session:
        dept = session.get(Department, 1)
        dept.budget_hours_remaining = 1
        session.add(dept)
        session.commit()

    before = client.get("/api/assignments").json()["assignments"]
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 2, "mode": "least_loaded"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "exceeds department budget"
    assert client.get("/api/assignments").json()["assignments"] == before


def test_auto_rejects_no_eligible_ta_without_state_change(reset_scenario):
    with Session(engine) as session:
        for ta_id in (1, 2, 3):
            session.add(
                Assignment(
                    ta_id=ta_id,
                    course_id=1,
                    weekly_hours=20,
                    created_at="2099-01-01T10:00:00+00:00",
                )
            )
        session.commit()

    before = client.get("/api/assignments").json()["assignments"]
    response = client.post(
        "/api/assignments/auto",
        headers={"X-User-Id": str(_hod_user_id())},
        json={"course_id": 1, "weekly_hours": 1, "mode": "least_loaded"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "no TAs have sufficient weekly capacity"
    assert client.get("/api/assignments").json()["assignments"] == before
