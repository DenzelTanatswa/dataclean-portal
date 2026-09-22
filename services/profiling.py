import pandas as pd


def column_quality_label(missing_pct: float) -> str:
    if missing_pct == 0:
        return "🟢 Good"
    elif missing_pct <= 10:
        return "🟡 Warning"
    else:
        return "🔴 Critical"


def create_quality_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Return a per-column quality summary DataFrame."""
    rows = []
    for col in df.columns:
        missing = int(df[col].isnull().sum())
        missing_pct = round(missing / max(len(df), 1) * 100, 1)
        rows.append({
            "Column":     col,
            "Data Type":  str(df[col].dtype),
            "Missing":    missing,
            "Missing %":  missing_pct,
            "Unique":     int(df[col].nunique()),
            "Duplicates": int(df[col].duplicated().sum()),
            "Quality":    column_quality_label(missing_pct),
        })
    return pd.DataFrame(rows)


def get_issues(df: pd.DataFrame) -> list:
    """Return list of (severity_emoji, message) tuples from actual data."""
    issues = []
    missing_total = int(df.isnull().sum().sum())
    dup_total = int(df.duplicated().sum())

    if missing_total > 0:
        sev = "🔴" if missing_total > 10 else "🟡"
        issues.append((sev, f"{missing_total} missing value(s) detected"))
    else:
        issues.append(("🟢", "No missing values detected"))

    if dup_total > 0:
        sev = "🔴" if dup_total > 5 else "🟡"
        issues.append((sev, f"{dup_total} duplicate row(s) detected"))
    else:
        issues.append(("🟢", "No duplicate rows detected"))

    if "Age" in df.columns:
        try:
            invalid_ages = int(((df["Age"] < 18) | (df["Age"] > 100)).sum())
            if invalid_ages > 0:
                issues.append(("🔴", f"{invalid_ages} invalid age value(s) detected"))
            else:
                issues.append(("🟢", "No invalid age values detected"))
        except Exception:
            pass

    bad_cols = [c for c in df.columns
                if df[c].isnull().sum() / max(len(df), 1) > 0.5]
    if bad_cols:
        issues.append(("🔴", f"{len(bad_cols)} column(s) with >50% missing data"))
    else:
        issues.append(("🟢", "No structural issues detected"))

    return issues
