from app.repositories.user import UserRepository
from app.schemas.user import RegularUserCreate
from app.utilities.security import (
    create_access_token,
    encrypt_password,
    verify_password,
)


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def authenticate_user(self, username: str, password: str) -> str | None:
        user = self.user_repo.get_by_username(username)
        if not user or not verify_password(
            plaintext_password=password, encrypted_password=user.password
        ):
            return None
        access_token = create_access_token(
            data={"sub": f"{user.id}", "role": user.role}
        )
        return access_token

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        *,
        role: str = "regular_user",
        name: str = "",
        experience_course_ids: list[int] | None = None,
    ):
        if role not in {"regular_user", "ta"}:
            raise ValueError("Public registration only allows regular users or TAs")
        if role == "ta" and not name.strip():
            raise ValueError("Name is required for TA registration")
        if role != "ta" and experience_course_ids:
            raise ValueError("Prior course experience is only valid for TA accounts")

        new_user = RegularUserCreate(
            username=username,
            email=email,
            password=encrypt_password(password),
            role=role,
        )
        return self.user_repo.create(
            new_user,
            ta_name=name.strip(),
            experience_course_ids=experience_course_ids,
        )

    def create_managed_user(
        self,
        username: str,
        email: str,
        password: str,
        *,
        role: str,
        name: str = "",
        experience_course_ids: list[int] | None = None,
    ):
        if role not in {"regular_user", "ta", "hod", "admin"}:
            raise ValueError("Select a valid account role")
        if not username.strip() or not email.strip() or not password:
            raise ValueError("Username, email, and password are required")
        if role == "ta" and not name.strip():
            raise ValueError("Name is required for TA accounts")
        if role != "ta" and experience_course_ids:
            raise ValueError("Prior course experience is only valid for TA accounts")

        new_user = RegularUserCreate(
            username=username.strip(),
            email=email.strip().lower(),
            password=encrypt_password(password),
            role=role,
        )
        return self.user_repo.create(
            new_user,
            ta_name=name.strip(),
            experience_course_ids=experience_course_ids,
        )
