from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, ForeignKey
)
from sqlalchemy.sql import func
from database.connection import Base


class Dataset(Base):
    """
    One row per uploaded file.
    Stores file metadata, shape, quality score, and processing status.
    """
    __tablename__ = "datasets"

    dataset_id   = Column(Integer, primary_key=True, autoincrement=True)
    dataset_name = Column(String(255), nullable=False)
    original_filename = Column(String(255))
    file_type    = Column(String(10))          # csv / xlsx
    row_count    = Column(Integer)
    column_count = Column(Integer)
    uploaded_at  = Column(DateTime, server_default=func.now())
    quality_score = Column(Float)
    status       = Column(String(50), default="uploaded")  # uploaded / cleaned / exported


class CleaningRun(Base):
    """
    One row per cleaning execution.
    Links back to the source dataset and records before/after metrics.
    """
    __tablename__ = "cleaning_runs"

    run_id       = Column(Integer, primary_key=True, autoincrement=True)
    run_code     = Column(String(30), unique=True)   # e.g. RUN-2026-00001
    dataset_id   = Column(Integer, ForeignKey("datasets.dataset_id"))
    run_timestamp = Column(DateTime, server_default=func.now())
    original_rows = Column(Integer)
    cleaned_rows  = Column(Integer)
    rows_removed  = Column(Integer)
    quality_score_before = Column(Float)
    quality_score_after  = Column(Float)
    version      = Column(Integer, default=1)


class CleaningAudit(Base):
    """
    One row per individual cleaning operation within a run.
    E.g. 'Spaces removed: 4' or 'Duplicate rows removed: 1'.
    """
    __tablename__ = "cleaning_audit"

    audit_id   = Column(Integer, primary_key=True, autoincrement=True)
    run_id     = Column(Integer, ForeignKey("cleaning_runs.run_id"))
    operation  = Column(String(255))
    changes    = Column(Integer)
    timestamp  = Column(DateTime, server_default=func.now())


class QualityCheck(Base):
    """
    One row per validation rule per run.
    Records how many issues were found and whether the rule passed/failed.
    """
    __tablename__ = "quality_checks"

    check_id     = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id   = Column(Integer, ForeignKey("datasets.dataset_id"))
    run_id       = Column(Integer, ForeignKey("cleaning_runs.run_id"), nullable=True)
    column_name  = Column(String(255))
    check_type   = Column(String(100))   # e.g. completeness / uniqueness / validity
    issue_count  = Column(Integer)
    records_checked = Column(Integer)
    status       = Column(String(20))    # passed / warning / failed
    timestamp    = Column(DateTime, server_default=func.now())


class DatasetVersion(Base):
    """
    Tracks each version of a dataset as cleaning progresses.
    Version 1 = original upload. Each cleaning run increments the version.
    """
    __tablename__ = "dataset_versions"

    version_id   = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id   = Column(Integer, ForeignKey("datasets.dataset_id"))
    run_id       = Column(Integer, ForeignKey("cleaning_runs.run_id"), nullable=True)
    version_number = Column(Integer)
    description  = Column(Text)
    row_count    = Column(Integer)
    quality_score = Column(Float)
    created_at   = Column(DateTime, server_default=func.now())
