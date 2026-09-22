import pandas as pd


CITY_MAPPING = {
    "JHB": "Johannesburg", "Jhb": "Johannesburg", "jhb": "Johannesburg",
    "PTA": "Pretoria",     "Pta": "Pretoria",     "pta": "Pretoria",
    "CPT": "Cape Town",    "Cpt": "Cape Town",    "cpt": "Cape Town",
}

EXCLUDED_TEXT_COLUMNS = ["Email", "Phone"]


def clean_dataset(df: pd.DataFrame, options: dict) -> tuple[pd.DataFrame, list]:
    """
    Apply selected cleaning operations to df.

    options keys (all bool):
        remove_duplicates, trim_spaces, standardize_text,
        standardize_cities, fill_missing, fix_invalid_age

    Returns:
        cleaned_df  — the cleaned DataFrame
        audit_log   — list of {"Operation": str, "Changes": int}
    """
    cleaned = df.copy()
    audit = []

    if options.get("remove_duplicates"):
        before = len(cleaned)
        cleaned = cleaned.drop_duplicates()
        audit.append({"Operation": "Duplicate rows removed", "Changes": before - len(cleaned)})

    if options.get("trim_spaces"):
        count = 0
        for col in cleaned.select_dtypes(include=["object"]).columns:
            orig = cleaned[col].astype("string")
            new  = orig.str.strip()
            count += int((orig != new).sum())
            cleaned[col] = new
        audit.append({"Operation": "Spaces removed", "Changes": count})

    if options.get("standardize_text"):
        count = 0
        for col in cleaned.select_dtypes(include=["object", "string"]).columns:
            if col not in EXCLUDED_TEXT_COLUMNS:
                orig = cleaned[col].astype("string")
                new  = orig.str.title()
                count += int((orig != new).sum())
                cleaned[col] = new
        audit.append({"Operation": "Text values standardized", "Changes": count})

    if options.get("standardize_cities") and "City" in cleaned.columns:
        orig = cleaned["City"].astype("string")
        new  = cleaned["City"].replace(CITY_MAPPING)
        count = int((orig != new).sum())
        cleaned["City"] = new
        audit.append({"Operation": "City values standardized", "Changes": count})
    elif options.get("standardize_cities"):
        audit.append({"Operation": "City values standardized", "Changes": 0})

    if options.get("fill_missing"):
        count = 0
        for col in cleaned.columns:
            before = int(cleaned[col].isnull().sum())
            if cleaned[col].dtype == "object":
                cleaned[col] = cleaned[col].fillna("Unknown")
            elif pd.api.types.is_numeric_dtype(cleaned[col]):
                cleaned[col] = cleaned[col].fillna(cleaned[col].median())
            count += before - int(cleaned[col].isnull().sum())
        audit.append({"Operation": "Missing values filled", "Changes": count})

    if options.get("fix_invalid_age") and "Age" in cleaned.columns:
        try:
            mask = (cleaned["Age"] < 18) | (cleaned["Age"] > 100)
            count = int(mask.sum())
            cleaned.loc[mask, "Age"] = pd.NA
            audit.append({"Operation": "Invalid ages flagged", "Changes": count})
        except Exception:
            audit.append({"Operation": "Invalid ages flagged", "Changes": 0})
    elif options.get("fix_invalid_age"):
        audit.append({"Operation": "Invalid ages flagged", "Changes": 0})

    return cleaned, audit
