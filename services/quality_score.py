import pandas as pd


def calculate_quality_score(df: pd.DataFrame) -> int:
    """
    Return a 0-100 quality score based on measurable data problems.

    Penalties:
      - Missing values  : up to -30  (proportional to missing cell ratio)
      - Duplicates      : up to -20  (proportional to duplicate row ratio)
      - Invalid ages    : up to -20  (if Age column exists)
      - Columns >50% NA : -5 each   (structural completeness)
    """
    score = 100
    total_cells = df.shape[0] * df.shape[1]
    if total_cells == 0:
        return 0

    missing_ratio = df.isnull().sum().sum() / total_cells
    score -= min(30, round(missing_ratio * 100))

    dup_ratio = df.duplicated().sum() / max(len(df), 1)
    score -= min(20, round(dup_ratio * 100))

    if "Age" in df.columns:
        try:
            invalid = ((df["Age"] < 18) | (df["Age"] > 100)).sum()
            score -= min(20, round(invalid / max(len(df), 1) * 100))
        except Exception:
            pass

    for col in df.columns:
        if df[col].isnull().sum() / max(len(df), 1) > 0.5:
            score -= 5

    return max(0, min(100, int(score)))


def quality_label(score: int):
    """Return (emoji, label, css_class) for a given score."""
    if score >= 90:
        return "🟢", "Excellent", "dc-badge-green"
    elif score >= 70:
        return "🟡", "Needs Attention", "dc-badge-yellow"
    else:
        return "🔴", "Poor Quality", "dc-badge-red"
