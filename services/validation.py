import re
import pandas as pd


# ---------------------------------------------------------------------------
# Default rule configuration — can be overridden via session_state settings
# ---------------------------------------------------------------------------
DEFAULT_RULES = {
    "age_min": 18,
    "age_max": 100,
    "missing_threshold_pct": 10.0,
    "duplicate_threshold_pct": 5.0,
}


def _status(issue_count: int, records: int, threshold_pct: float = 0) -> str:
    """Derive passed / warning / failed from issue count."""
    if issue_count == 0:
        return "passed"
    ratio = issue_count / max(records, 1) * 100
    if ratio <= threshold_pct:
        return "warning"
    return "failed"


def check_completeness(df: pd.DataFrame, threshold_pct: float = 10.0) -> list:
    """One result row per column — flags columns with missing values."""
    results = []
    for col in df.columns:
        missing = int(df[col].isnull().sum())
        results.append({
            "Rule":             "Completeness",
            "Column":           col,
            "Records Checked":  len(df),
            "Issues Found":     missing,
            "Status":           _status(missing, len(df), threshold_pct),
        })
    return results


def check_uniqueness(df: pd.DataFrame, threshold_pct: float = 5.0) -> list:
    """Checks for duplicate rows across the whole dataset."""
    dupes = int(df.duplicated().sum())
    return [{
        "Rule":             "Uniqueness",
        "Column":           "(all columns)",
        "Records Checked":  len(df),
        "Issues Found":     dupes,
        "Status":           _status(dupes, len(df), threshold_pct),
    }]


def check_age_validity(df: pd.DataFrame, age_min: int = 18, age_max: int = 100) -> list:
    """Flags Age values outside the configured valid range."""
    if "Age" not in df.columns:
        return []
    try:
        numeric_age = pd.to_numeric(df["Age"], errors="coerce")
        invalid = int(((numeric_age < age_min) | (numeric_age > age_max)).sum())
        return [{
            "Rule":             f"Age Range ({age_min}–{age_max})",
            "Column":           "Age",
            "Records Checked":  len(df),
            "Issues Found":     invalid,
            "Status":           _status(invalid, len(df)),
        }]
    except Exception:
        return []


def check_email_format(df: pd.DataFrame) -> list:
    """Flags values in Email column that don't match a basic email pattern."""
    if "Email" not in df.columns:
        return []
    pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    invalid = int(df["Email"].dropna().apply(
        lambda v: not bool(pattern.match(str(v)))
    ).sum())
    return [{
        "Rule":             "Email Format",
        "Column":           "Email",
        "Records Checked":  int(df["Email"].notna().sum()),
        "Issues Found":     invalid,
        "Status":           _status(invalid, len(df), 5.0),
    }]


def check_phone_format(df: pd.DataFrame) -> list:
    """Flags Phone values that contain letters or are unusually short."""
    if "Phone" not in df.columns:
        return []
    def is_suspicious(v):
        s = str(v).strip()
        digits = re.sub(r"[\s\-\+\(\)]", "", s)
        return bool(re.search(r"[a-zA-Z]", s)) or len(digits) < 7
    invalid = int(df["Phone"].dropna().apply(is_suspicious).sum())
    return [{
        "Rule":             "Phone Format",
        "Column":           "Phone",
        "Records Checked":  int(df["Phone"].notna().sum()),
        "Issues Found":     invalid,
        "Status":           _status(invalid, len(df), 5.0),
    }]


def check_city_consistency(df: pd.DataFrame) -> list:
    """Flags known city abbreviations / inconsistent spellings."""
    if "City" not in df.columns:
        return []
    known_inconsistent = {
        "jhb", "jhb", "pta", "cpt",
        "johannesburg ", " johannesburg",
        "pretoria ", " pretoria",
    }
    invalid = int(df["City"].dropna().apply(
        lambda v: str(v).strip().lower() in known_inconsistent
    ).sum())
    return [{
        "Rule":             "City Consistency",
        "Column":           "City",
        "Records Checked":  int(df["City"].notna().sum()),
        "Issues Found":     invalid,
        "Status":           _status(invalid, len(df), 5.0),
    }]


def check_data_types(df: pd.DataFrame) -> list:
    """
    Flags columns that are stored as object/string but appear to be
    numeric (>80% of non-null values parse as numbers).
    """
    results = []
    for col in df.select_dtypes(include=["object"]).columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        numeric_count = pd.to_numeric(non_null, errors="coerce").notna().sum()
        ratio = numeric_count / len(non_null)
        if ratio > 0.8:
            results.append({
                "Rule":             "Data Type",
                "Column":           col,
                "Records Checked":  len(non_null),
                "Issues Found":     int(numeric_count),
                "Status":           "warning",
            })
    return results


def run_all_validations(df: pd.DataFrame, rules: dict = None) -> pd.DataFrame:
    """
    Run every validation rule and return a combined results DataFrame.
    Pass a rules dict to override defaults (age_min, age_max, etc.).
    """
    cfg = {**DEFAULT_RULES, **(rules or {})}
    results = []
    results += check_completeness(df, cfg["missing_threshold_pct"])
    results += check_uniqueness(df, cfg["duplicate_threshold_pct"])
    results += check_age_validity(df, cfg["age_min"], cfg["age_max"])
    results += check_email_format(df)
    results += check_phone_format(df)
    results += check_city_consistency(df)
    results += check_data_types(df)

    result_df = pd.DataFrame(results)

    # Add display-friendly Status column
    status_map = {
        "passed":  "🟢 Passed",
        "warning": "🟡 Warning",
        "failed":  "🔴 Failed",
    }
    result_df["Status"] = result_df["Status"].map(status_map).fillna(result_df["Status"])
    return result_df
