import uuid
from datetime import datetime

from sqlalchemy import DateTime, TypeDecorator, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GUID(TypeDecorator):
    """UUID on PostgreSQL and portable string UUIDs for SQLite unit tests."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(PGUUID(as_uuid=True) if dialect.name == "postgresql" else String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        return value if value is None or isinstance(value, uuid.UUID) else uuid.UUID(value)


class Base(DeclarativeBase):
    __allow_unmapped__ = True


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
