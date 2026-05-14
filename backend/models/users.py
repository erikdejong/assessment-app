from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from utils.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "app"}

    username: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
