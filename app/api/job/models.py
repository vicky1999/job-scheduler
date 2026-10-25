from uuid import UUID
from sqlalchemy import ForeignKey, Uuid, String, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.core.models import Base
from app.api.job.constants import JobStatus

from sqlalchemy.dialects.postgresql import ENUM

class Job(Base):
    __tablename__ = "jobs"

    name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Name of the job",
    )

    description: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Job description",
    )

    scheduled_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When the job is scheduled",
    )

    handler: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="handler to handle the job on execution"
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Payload passed to the handler"
    )

    status: Mapped[JobStatus] = mapped_column(
        ENUM(JobStatus, name="jobstatus"),
        nullable=False,
        default = JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
        comment="Status of handler"
    )

    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Result of execution"
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Tracks the number of retries happened for the job"
    )

    last_retried_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Tracks the date time the last retry happened"
    )

    # Worker ownership and lease
    locked_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    lease_expires_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    started_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Start time of the job execution"
    )

    completed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="End time of the job execution"
    )

    last_error: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant the job is associated with"
    )

    __table_args__ = (
        Index(
            "ix_jobs_scheduled_at_status",
            "scheduled_at",
            "status",
        ),
        Index(
            "ix_jobs_status_scheduled_at_tenant",
            "status",
            "scheduled_at",
            "tenant_id",
        ),
        Index(
            "ix_jobs_status_lease_expires_at",
            "status",
            "lease_expires_at",
        ),
    )

    