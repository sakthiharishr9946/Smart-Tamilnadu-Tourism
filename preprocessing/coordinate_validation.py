import pandas as pd

from config.constants import (
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
)


def validate_tamilnadu_coordinates(latitude, longitude):
    if latitude is None or longitude is None:
        return False

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False

    return (
        MIN_LATITUDE <= latitude <= MAX_LATITUDE
        and MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
    )


def validate_coordinate_columns(df):
    if df is None or df.empty:
        return False, ["DataFrame is empty"]

    required_columns = {"latitude", "longitude"}

    if not required_columns.issubset(df.columns):
        return False, ["Latitude or longitude column is missing"]

    errors = []

    for index, row in df.iterrows():
        if not validate_tamilnadu_coordinates(
            row["latitude"],
            row["longitude"]
        ):
            errors.append(
                f"Invalid Tamil Nadu coordinates at row {index}"
            )

    return len(errors) == 0, errors


def filter_valid_coordinates(df):
    if df is None or df.empty:
        return pd.DataFrame()

    if not {"latitude", "longitude"}.issubset(df.columns):
        return pd.DataFrame()

    valid_rows = df.apply(
        lambda row: validate_tamilnadu_coordinates(
            row["latitude"],
            row["longitude"]
        ),
        axis=1,
    )

    return df[valid_rows].reset_index(drop=True)


def validate_and_filter_coordinates(df):
    valid, errors = validate_coordinate_columns(df)

    if not valid:
        return pd.DataFrame(), errors

    filtered_df = filter_valid_coordinates(df)

    return filtered_df, []