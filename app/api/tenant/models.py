from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.models import Base

class Tenant(Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Name of the tenant"
    )
