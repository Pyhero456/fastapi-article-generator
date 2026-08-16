from sqlalchemy import String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from datetime import datetime
from app.schemas import PaymentStatus
from app.schemas import Plan

class User(Base):
    __tablename__ = "users"

    id:Mapped[int] = mapped_column(primary_key=True)
    username:Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password:Mapped[str] = mapped_column(String)
    refresh_tokens:Mapped[list["RefreshToken"]] = relationship(back_populates="user",cascade="all, delete-orphan")
    is_admin:Mapped[bool] = mapped_column(default=False)
    api_access:Mapped[bool]= mapped_column(default = False)
    

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id:Mapped[int] = mapped_column(primary_key=True)
    token_hash:Mapped[str] = mapped_column(String, unique = True, index = True)
    user_id:Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at:Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked:Mapped[bool] = mapped_column(Boolean, default = False)
    user:Mapped["User"] = relationship(back_populates="refresh_tokens")

class Payment(Base):
    __tablename__ = "payments"

    id:Mapped[int] = mapped_column(primary_key=True)
    reference:Mapped[str] = mapped_column(String, unique = True, index = True)
    user_id:Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount_cents:Mapped[int] = mapped_column()
    status:Mapped[PaymentStatus] = mapped_column(default = PaymentStatus.pending)
    plan: Mapped[str | None] = mapped_column(
    String,
    nullable=True)
    payment_type:Mapped[str] = mapped_column(String, default="api_access")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id:Mapped[int] = mapped_column(primary_key=True)
    user_id:Mapped[int] = mapped_column(ForeignKey("users.id"), unique = True)
    plan:Mapped[str] = mapped_column(String)
    status:Mapped[str] = mapped_column(String, default="active")
    started_at:Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at:Mapped[datetime]
    articles_used:Mapped[int] = mapped_column(default=0)


PLAN_LIMITS = {
    Plan.STARTER: 10,
    Plan.PRO: 25,
    Plan.UNLIMITED: None,
}

PLAN_PRICES = {
    Plan.STARTER: 2900,       # $29
    Plan.PRO: 4900,           # $49
    Plan.UNLIMITED: 9900,     # $99
}

OVERAGE_PRICES = {
    Plan.STARTER: 200,        # $2
    Plan.PRO: 150,            # $1.50
    Plan.UNLIMITED: 0,
}
