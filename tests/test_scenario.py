"""Shallow scenario smoke tests — intentionally weak."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.assignment import Assignment
from app.models.department import Department
from app.seed import seed


def setup_module() -> None:
    seed(reset=True)


client = TestClient(app)


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


#recently edited
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
    assert client.get("/docs", cookies={"access_token": hod_cookie}).status_code == 401
    assert (
        client.get("/openapi.json", cookies={"access_token": hod_cookie}).status_code
        == 401
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


def test_review_board():
    r = client.get("/api/review")
    assert r.status_code == 200
    assert "tas" in r.json()
    assert "assignments" in r.json()


#recently edited
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
def test_auto_rejects_non_positive_hours_without_state_change(reset_scenario, weekly_hours):
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
            session.add(Assignment(
                ta_id=ta_id,
                course_id=1,
                weekly_hours=20,
                created_at="2099-01-01T10:00:00+00:00",
            ))
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
