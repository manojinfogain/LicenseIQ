from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoginAccount(Base):
    """Authorised app sign-in accounts (email + password hash + role)."""

    __tablename__ = "login_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role_code: Mapped[str] = mapped_column(String(50), index=True)
    role_display_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("1"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("GETDATE()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("GETDATE()"),
    )
