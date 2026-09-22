from datetime import datetime
from database.connection import get_session
from database.models import (
    Dataset, CleaningRun, CleaningAudit, QualityCheck, DatasetVersion
)


def generate_run_code(session) -> str:
    """
    Generate a human-readable run code like RUN-2026-00001.
    The sequence number is based on the current count of runs in the DB.
    """
    year = datetime.now().year
    count = session.query(CleaningRun).count() + 1
    return f"RUN-{year}-{count:05d}"


def save_dataset_metadata(filename: str, file_type: str,
                          row_count: int, col_count: int,
                          quality_score: float) -> int:
    """Insert a dataset record and return its dataset_id."""
    session = get_session()
    try:
        name = filename.rsplit(".", 1)[0]  # strip extension for display name
        record = Dataset(
            dataset_name=name,
            original_filename=filename,
            file_type=file_type,
            row_count=row_count,
            column_count=col_count,
            quality_score=quality_score,
            status="uploaded",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        # Version 1 = original upload
        version = DatasetVersion(
            dataset_id=record.dataset_id,
            run_id=None,
            version_number=1,
            description="Original upload",
            row_count=row_count,
            quality_score=quality_score,
        )
        session.add(version)
        session.commit()

        return record.dataset_id
    finally:
        session.close()


def save_cleaning_run(dataset_id: int, original_rows: int, cleaned_rows: int,
                      rows_removed: int, score_before: float,
                      score_after: float, audit_log: list,
                      quality_checks_df) -> str:
    """
    Insert a CleaningRun, its CleaningAudit rows, QualityCheck rows,
    and a new DatasetVersion. Returns the run_code string.
    """
    session = get_session()
    try:
        run_code = generate_run_code(session)

        # Get next version number for this dataset
        existing_versions = session.query(DatasetVersion).filter_by(
            dataset_id=dataset_id
        ).count()
        next_version = existing_versions + 1

        run = CleaningRun(
            run_code=run_code,
            dataset_id=dataset_id,
            original_rows=original_rows,
            cleaned_rows=cleaned_rows,
            rows_removed=rows_removed,
            quality_score_before=score_before,
            quality_score_after=score_after,
            version=next_version,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        # Audit rows
        for entry in audit_log:
            session.add(CleaningAudit(
                run_id=run.run_id,
                operation=entry["Operation"],
                changes=entry["Changes"],
            ))

        # Quality check rows
        if quality_checks_df is not None and not quality_checks_df.empty:
            status_reverse = {
                "🟢 Passed": "passed",
                "🟡 Warning": "warning",
                "🔴 Failed": "failed",
            }
            for _, row in quality_checks_df.iterrows():
                session.add(QualityCheck(
                    dataset_id=dataset_id,
                    run_id=run.run_id,
                    column_name=str(row.get("Column", "")),
                    check_type=str(row.get("Rule", "")),
                    issue_count=int(row.get("Issues Found", 0)),
                    records_checked=int(row.get("Records Checked", 0)),
                    status=status_reverse.get(str(row.get("Status", "")), "unknown"),
                ))

        # New dataset version
        session.add(DatasetVersion(
            dataset_id=dataset_id,
            run_id=run.run_id,
            version_number=next_version,
            description=f"After cleaning run {run_code}",
            row_count=cleaned_rows,
            quality_score=score_after,
        ))

        # Update dataset status
        dataset = session.query(Dataset).filter_by(dataset_id=dataset_id).first()
        if dataset:
            dataset.status = "cleaned"
            dataset.quality_score = score_after

        session.commit()
        return run_code
    finally:
        session.close()


def get_cleaning_history(limit: int = 50) -> list:
    """Return recent cleaning runs as a list of dicts."""
    session = get_session()
    try:
        runs = (
            session.query(CleaningRun, Dataset)
            .join(Dataset, CleaningRun.dataset_id == Dataset.dataset_id)
            .order_by(CleaningRun.run_timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "Run ID":        r.run_code,
                "Dataset":       d.original_filename,
                "Date":          r.run_timestamp.strftime("%d %b %Y %H:%M") if r.run_timestamp else "",
                "Original Rows": r.original_rows,
                "Cleaned Rows":  r.cleaned_rows,
                "Rows Removed":  r.rows_removed,
                "Score Before":  r.quality_score_before,
                "Score After":   r.quality_score_after,
                "Version":       f"v{r.version}",
            }
            for r, d in runs
        ]
    finally:
        session.close()


def get_audit_for_run(run_code: str) -> list:
    """Return audit log entries for a specific run_code."""
    session = get_session()
    try:
        run = session.query(CleaningRun).filter_by(run_code=run_code).first()
        if not run:
            return []
        entries = session.query(CleaningAudit).filter_by(run_id=run.run_id).all()
        return [{"Operation": e.operation, "Changes": e.changes} for e in entries]
    finally:
        session.close()


def get_all_datasets() -> list:
    """Return all datasets as a list of dicts."""
    session = get_session()
    try:
        datasets = session.query(Dataset).order_by(Dataset.uploaded_at.desc()).all()
        return [
            {
                "ID":           d.dataset_id,
                "Dataset":      d.original_filename,
                "Uploaded":     d.uploaded_at.strftime("%d %b %Y %H:%M") if d.uploaded_at else "",
                "Rows":         d.row_count,
                "Columns":      d.column_count,
                "Quality Score": d.quality_score,
                "Status":       d.status,
            }
            for d in datasets
        ]
    finally:
        session.close()


def get_quality_history() -> list:
    """Return quality score over time for charting."""
    session = get_session()
    try:
        runs = session.query(CleaningRun).order_by(CleaningRun.run_timestamp).all()
        return [
            {
                "run_code":  r.run_code,
                "timestamp": r.run_timestamp,
                "score":     r.quality_score_after,
            }
            for r in runs
        ]
    finally:
        session.close()


def get_db_summary() -> dict:
    """Return counts for the Database page."""
    session = get_session()
    try:
        return {
            "datasets":       session.query(Dataset).count(),
            "cleaning_runs":  session.query(CleaningRun).count(),
            "quality_checks": session.query(QualityCheck).count(),
            "audit_entries":  session.query(CleaningAudit).count(),
        }
    finally:
        session.close()
