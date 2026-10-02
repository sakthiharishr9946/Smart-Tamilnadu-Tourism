import pandas as pd


def normalize_text(value):
    if pd.isna(value):
        return value

    return " ".join(str(value).strip().split())


def normalize_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()

    text_columns = normalized.select_dtypes(
        include=["object"]
    ).columns

    for column in text_columns:
        normalized[column] = normalized[column].apply(normalize_text)

    return normalized


def normalize_ratings(df):
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()

    if "rating" in normalized.columns:
        normalized["rating"] = pd.to_numeric(
            normalized["rating"],
            errors="coerce"
        ).clip(0, 5)

    if "rating_count" in normalized.columns:
        normalized["rating_count"] = pd.to_numeric(
            normalized["rating_count"],
            errors="coerce"
        ).fillna(0).astype(int)

    return normalized


def normalize_coordinates(df):
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()

    if "latitude" in normalized.columns:
        normalized["latitude"] = pd.to_numeric(
            normalized["latitude"],
            errors="coerce"
        ).round(6)

    if "longitude" in normalized.columns:
        normalized["longitude"] = pd.to_numeric(
            normalized["longitude"],
            errors="coerce"
        ).round(6)

    return normalized


def normalize_tourism_data(df):
    normalized = normalize_dataframe(df)
    normalized = normalize_ratings(normalized)
    normalized = normalize_coordinates(normalized)

    return normalized