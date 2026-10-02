import pandas as pd


REQUIRED_PLACE_COLUMNS = [
    "place_name",
    "district",
    "latitude",
    "longitude",
]


def validate_dataframe(df):
    if df is None:
        return False, ["DataFrame is None"]

    if not isinstance(df, pd.DataFrame):
        return False, ["Input is not a pandas DataFrame"]

    if df.empty:
        return False, ["DataFrame is empty"]

    return True, []


def validate_required_columns(df, required_columns=None):
    if required_columns is None:
        required_columns = REQUIRED_PLACE_COLUMNS

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        return False, missing_columns

    return True, []


def validate_coordinates(df):
    if df is None or df.empty:
        return False, ["DataFrame is empty"]

    if not {"latitude", "longitude"}.issubset(df.columns):
        return False, ["Latitude or longitude column is missing"]

    errors = []

    invalid_latitude = (
        df["latitude"].isna()
        | (df["latitude"] < -90)
        | (df["latitude"] > 90)
    )

    invalid_longitude = (
        df["longitude"].isna()
        | (df["longitude"] < -180)
        | (df["longitude"] > 180)
    )

    if invalid_latitude.any():
        errors.append("Invalid latitude values found")

    if invalid_longitude.any():
        errors.append("Invalid longitude values found")

    return len(errors) == 0, errors


def validate_ratings(df):
    if df is None or df.empty:
        return False, ["DataFrame is empty"]

    if "rating" not in df.columns:
        return False, ["Rating column is missing"]

    errors = []

    invalid_rating = (
        df["rating"].isna()
        | (df["rating"] < 0)
        | (df["rating"] > 5)
    )

    if invalid_rating.any():
        errors.append("Invalid rating values found")

    return len(errors) == 0, errors


def validate_tourism_data(df):
    errors = []

    valid, dataframe_errors = validate_dataframe(df)

    if not valid:
        return False, dataframe_errors

    valid, column_errors = validate_required_columns(df)

    if not valid:
        errors.extend(
            [
                f"Missing required column: {column}"
                for column in column_errors
            ]
        )

    if valid:
        coordinate_valid, coordinate_errors = validate_coordinates(df)

        if not coordinate_valid:
            errors.extend(coordinate_errors)

    if "rating" in df.columns:
        rating_valid, rating_errors = validate_ratings(df)

        if not rating_valid:
            errors.extend(rating_errors)

    return len(errors) == 0, errors