"""SQLAlchemy 2.0 ORM models for AetherApply."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_hash = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Unknown Title", index=True)
    company = Column(String(255), nullable=False, default="Unknown Company", index=True)
    platform = Column(String(64), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    match_score = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="discovered", nullable=False, index=True)
    source = Column(String(64), default="unknown", nullable=False)
    source_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    applications = relationship("ApplicationRecord", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Job id={self.id} title='{self.title}' company='{self.company}' platform='{self.platform}' score={self.match_score}>"


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    platform = Column(String(64), nullable=False)
    status = Column(String(32), default="queued_manual", nullable=False)  # submitted, failed, queued_manual
    submission_details = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=utc_now, nullable=False)

    job = relationship("Job", back_populates="applications")

    def __repr__(self) -> str:
        return f"<ApplicationRecord id={self.id} job_id={self.job_id} platform='{self.platform}' status='{self.status}'>"


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    message_id = Column(String(255), primary_key=True)
    source = Column(String(64), default="gmail", nullable=False)
    processed_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<ProcessedMessage id='{self.message_id}' source='{self.source}'>"
