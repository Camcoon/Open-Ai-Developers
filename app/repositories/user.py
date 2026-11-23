import logging
from typing import Optional, Tuple

from sqlmodel import Session, func, select

from app.models.course import Course
from app.models.ta import Ta
from app.models.ta_experience import TaExperience
from app.models.user import User, UserBase
from app.schemas.user import UserUpdate
from app.utilities.pagination import Pagination

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_data: UserBase,
        *,
        ta_name: str | None = None,
        experience_course_ids: list[int] | None = None,
    ) -> Optional[User]:
        try:
            user_db = User.model_validate(user_data)
            self.db.add(user_db)
            if user_db.role == "ta":
                ta = Ta(
                    name=ta_name or user_db.username,
                    email=user_db.email,
                )
                self.db.add(ta)
                self.db.flush()
                if ta.id is None:
                    raise RuntimeError("TA profile was not assigned an ID")
                self.replace_ta_experience(ta.id, experience_course_ids or [])
            elif experience_course_ids:
                raise ValueError(
                    "Prior course experience is only valid for TA accounts"
                )
            self.db.commit()
            self.db.refresh(user_db)
            return user_db
        except Exception as e:
            logger.error(f"An error occurred while saving user: {e}")
            self.db.rollback()
            raise

    def replace_ta_experience(
        self,
        ta_id: int,
        experience_course_ids: list[int],
    ) -> None:
        selected_ids = set(experience_course_ids)
        if selected_ids:
            courses = self.db.exec(
                select(Course).where(Course.id.in_(selected_ids))
            ).all()
            valid_ids = {course.id for course in courses if course.id is not None}
            if selected_ids != valid_ids:
                raise ValueError("Select only existing courses for TA experience")

        existing = self.db.exec(
            select(TaExperience).where(TaExperience.ta_id == ta_id)
        ).all()
        existing_ids = {experience.course_id for experience in existing}
        for experience in existing:
            if experience.course_id not in selected_ids:
                self.db.delete(experience)
        for course_id in selected_ids - existing_ids:
            self.db.add(TaExperience(ta_id=ta_id, course_id=course_id))

    def search_users(
        self, query: str, page: int = 1, limit: int = 10
    ) -> Tuple[list[User], Pagination]:
        offset = (page - 1) * limit
        db_qry = select(User)
        if query:
            db_qry = db_qry.where(
                User.username.ilike(f"%{query}%") | User.email.ilike(f"%{query}%")
            )
        count_qry = select(func.count()).select_from(db_qry.subquery())
        count_todos = self.db.exec(count_qry).one()

        users = self.db.exec(db_qry.offset(offset).limit(limit)).all()
        pagination = Pagination(total_count=count_todos, current_page=page, limit=limit)

        return users, pagination

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.exec(select(User).where(User.username == username)).one_or_none()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_all_users(self) -> list[User]:
        return self.db.exec(select(User)).all()

    def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        user = self.db.get(User, user_id)
        if not user:
            raise Exception("Invalid user id given")
        if user_data.username:
            user.username = user_data.username
        if user_data.email:
            user.email = user_data.email

        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception as e:
            logger.error(f"An error occurred while updating user: {e}")
            self.db.rollback()
            raise

    def delete_user(self, user_id: int):
        user = self.db.get(User, user_id)
        if not user:
            raise Exception("User doesn't exist")
        try:
            self.db.delete(user)
            self.db.commit()
        except Exception as e:
            logger.error(f"An error occurred while deleting user: {e}")
            self.db.rollback()
            raise
