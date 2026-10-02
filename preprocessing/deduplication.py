import pandas as pd


def remove_duplicate_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    return df.drop_duplicates().reset_index(drop=True)


def remove_duplicate_places(df):
    if df is None or df.empty:
        return pd.DataFrame()

    cleaned = df.copy()

    if "place_name" not in cleaned.columns:
        return remove_duplicate_rows(cleaned)

    duplicate_columns = ["place_name"]

    if "district" in cleaned.columns:
        duplicate_columns.append("district")

    if "city" in cleaned.columns:
        duplicate_columns.append("city")

    return cleaned.drop_duplicates(
        subset=duplicate_columns,
        keep="first"
    ).reset_index(drop=True)


def remove_duplicate_coordinates(df):
    if df is None or df.empty:
        return pd.DataFrame()

    cleaned = df.copy()

    if not {"latitude", "longitude"}.issubset(cleaned.columns):
        return cleaned.reset_index(drop=True)

    # Rows missing coordinates all look like the same (NaN, NaN) pair to
    # pandas' drop_duplicates, which would otherwise collapse every
    # coordinate-less place (e.g. from sources that don't publish lat/long)
    # down to a single row. Only dedupe rows that actually have coordinates.
    has_coords = cleaned["latitude"].notna() & cleaned["longitude"].notna()

    with_coords = cleaned[has_coords].drop_duplicates(
        subset=["latitude", "longitude"],
        keep="first"
    )
    without_coords = cleaned[~has_coords]

    cleaned = pd.concat([with_coords, without_coords])

    return cleaned.reset_index(drop=True)


def deduplicate_tourism_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    cleaned = remove_duplicate_rows(df)

    if "place_name" in cleaned.columns:
        cleaned = remove_duplicate_places(cleaned)

    if {"latitude", "longitude"}.issubset(cleaned.columns):
        cleaned = remove_duplicate_coordinates(cleaned)

    return cleaned.reset_index(drop=True)