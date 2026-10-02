import pandas as pd


def clean_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame()

    cleaned = df.copy()

    cleaned.columns = (
        cleaned.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    cleaned = cleaned.drop_duplicates()

    for column in cleaned.select_dtypes(include="object").columns:
        cleaned[column] = cleaned[column].apply(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    return cleaned


def handle_missing_values(df, numeric_fill=0, text_fill="Unknown"):
    if df is None or df.empty:
        return pd.DataFrame()

    cleaned = df.copy()

    numeric_columns = cleaned.select_dtypes(
        include=["number"]
    ).columns

    text_columns = cleaned.select_dtypes(
        include=["object"]
    ).columns

    for column in numeric_columns:
        cleaned[column] = cleaned[column].fillna(numeric_fill)

    for column in text_columns:
        cleaned[column] = cleaned[column].fillna(text_fill)

    return cleaned


def clean_tourism_data(df):
    cleaned = clean_dataframe(df)
    cleaned = handle_missing_values(cleaned)

    if "place_name" in cleaned.columns:
        cleaned = cleaned[
            cleaned["place_name"].astype(str).str.strip() != ""
        ]

    if "rating" in cleaned.columns:
        cleaned["rating"] = pd.to_numeric(
            cleaned["rating"],
            errors="coerce"
        ).clip(0, 5)

    if "latitude" in cleaned.columns:
        cleaned["latitude"] = pd.to_numeric(
            cleaned["latitude"],
            errors="coerce"
        )

    if "longitude" in cleaned.columns:
        cleaned["longitude"] = pd.to_numeric(
            cleaned["longitude"],
            errors="coerce"
        )

    if "entry_fee" in cleaned.columns:
        cleaned["entry_fee"] = pd.to_numeric(
            cleaned["entry_fee"],
            errors="coerce"
        ).fillna(0)

    return cleaned.reset_index(drop=True)