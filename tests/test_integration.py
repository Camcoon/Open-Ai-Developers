from decimal import Decimal

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, create_engine, select

from app.config import get_settings
from app.database import _ensure_ta_profile_columns, get_session
from app.main import app
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.department import Department
from app.models.ta import Ta
from app.models.user import User
from app.repositories.user import UserRepository
from app.services import allocations
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.utilities.security import verify_password


def test_save_password(test_session):
    repository = UserRepository(test_session)
    service = AuthService(repository)

    created = service.register_user("alice", "alice@example.com", "secret")
    saved = repository.get_by_username("alice")

    assert saved is not None
    assert created.id == saved.id
    assert saved.username == "alice"
    assert saved.email == "alice@example.com"
    assert saved.role == "regular_user"
    assert saved.password != "secret"
    assert verify_password("secret", saved.password)


def test_login(test_session):
    repository = UserRepository(test_session)
    service = AuthService(repository)
    service.register_user("alice", "alice@example.com", "secret")

    token = service.authenticate_user("alice", "secret")
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == str(repository.get_by_username("alice").id)
    assert payload["role"] == "regular_user"


def test_register_user(test_session):
    repository = UserRepository(test_session)
    auth_service = AuthService(repository)
    auth_service.register_user("alice", "alice@example.com", "secret")

    users = UserService(repository).get_all_users()

    assert len(users) == 1
    assert users[0].username == "alice"
    assert users[0].email == "alice@example.com"


def test_ta_registration_creates_ta_record(test_session):
    def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = TestClient(app).post(
            "/register",
            data={
                "username": "taylor",
                "name": "Taylor TA",
                "email": "taylor@example.com",
                "password": "secret",
                "role": "ta",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 303
    user = test_session.exec(select(User).where(User.username == "taylor")).one()
    ta = test_session.exec(select(Ta).where(Ta.email == "taylor@example.com")).one()
    assert user.role == "ta"
    assert ta.name == "Taylor TA"
    assert ta.hourly_rate == Decimal("0.00")
    assert ta.performance_rating == 0.0


def test_public_registration_cannot_create_admin(test_session):
    def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = TestClient(app).post(
            "/register",
            data={
                "username": "self-admin",
                "name": "Self Admin",
                "email": "self-admin@example.com",
                "password": "secret",
                "role": "admin",
            },
            follow_redirects=True,
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert "Public registration only allows regular users or TAs" in response.text
    assert test_session.exec(
        select(User).where(User.username == "self-admin")
    ).first() is None


def test_legacy_ta_table_is_migrated_with_default_profile_fields():
    legacy_engine = create_engine("sqlite://")
    try:
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE tas "
                    "(id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                    "email TEXT NOT NULL UNIQUE)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO tas (id, name, email) "
                    "VALUES (1, 'Legacy TA', 'legacy@example.com')"
                )
            )

        _ensure_ta_profile_columns(legacy_engine)

        columns = {
            column["name"] for column in inspect(legacy_engine).get_columns("tas")
        }
        assert {"hourly_rate", "performance_rating"} <= columns
        with Session(legacy_engine) as session:
            ta = session.get(Ta, 1)
        assert ta.hourly_rate == Decimal("0.00")
        assert ta.performance_rating == 0.0
    finally:
        legacy_engine.dispose()


#recently edited
@pytest.fixture
def manual_assignment_client(db_session, monkeypatch):
    monkeypatch.setattr(allocations, "engine", db_session.get_bind())
    monkeypatch.setattr(
        allocations,
        "get_user",
        lambda user_id: {"id": user_id, "role": "hod"},
    )
    return TestClient(app)


def _seed_manual_assignment_data(db_session, *, budget: int, current_load: int = 0):
    ta = Ta(name="Test TA", email="test-ta@example.com")
    course = Course(code="TEST1000", title="Test course", budgeted_hours=20)
    department = Department(id=1, budget_hours_remaining=budget)
    db_session.add(ta)
    db_session.add(course)
    db_session.add(department)
    db_session.flush()

    if current_load:
        db_session.add(
            Assignment(
                ta_id=ta.id,
                course_id=course.id,
                weekly_hours=current_load,
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    db_session.commit()
    return ta, course


def test_manual_assignment_succeeds(manual_assignment_client, db_session):
    ta, course = _seed_manual_assignment_data(db_session, budget=10)

    response = manual_assignment_client.post(
        "/api/assignments/manual",
        headers={"X-User-Id": "42"},
        json={"ta_id": ta.id, "course_id": course.id, "weekly_hours": 5},
    )

    assert response.status_code == 200
    assert response.json()["assignment"]["ta_id"] == ta.id
    assert len(db_session.exec(select(Assignment)).all()) == 1
    assert db_session.get(Department, 1).budget_hours_remaining == 5


def test_manual_assignment_rejects_ta_over_20_hours(
    manual_assignment_client, db_session
):
    ta, course = _seed_manual_assignment_data(
        db_session,
        budget=10,
        current_load=18,
    )

    response = manual_assignment_client.post(
        "/api/assignments/manual",
        headers={"X-User-Id": "42"},
        json={"ta_id": ta.id, "course_id": course.id, "weekly_hours": 3},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "exceeds TA weekly hour cap"
    assert len(db_session.exec(select(Assignment)).all()) == 1
    assert db_session.get(Department, 1).budget_hours_remaining == 10


def test_manual_assignment_rejects_department_budget_exceeded(
    manual_assignment_client, db_session
):
    ta, course = _seed_manual_assignment_data(db_session, budget=4)

    response = manual_assignment_client.post(
        "/api/assignments/manual",
        headers={"X-User-Id": "42"},
        json={"ta_id": ta.id, "course_id": course.id, "weekly_hours": 5},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "exceeds department budget"
    assert db_session.exec(select(Assignment)).all() == []
    assert db_session.get(Department, 1).budget_hours_remaining == 4
