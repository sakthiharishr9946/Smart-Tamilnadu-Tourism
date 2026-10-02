import pandas as pd


CROWD_FEATURE_COLUMNS = [
    "month",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "is_festival",
    "festival_importance",
]


def get_season(month):
    try:
        month = int(month)
    except (TypeError, ValueError):
        return "Unknown"

    if month in [3, 4, 5]:
        return "Summer"

    if month in [6, 7, 8, 9]:
        return "Monsoon"

    if month in [10, 11, 12, 1, 2]:
        return "Winter"

    return "Unknown"


def create_crowd_features(df):
    if df is None or df.empty:
        return pd.DataFrame()

    features = df.copy()

    if "date" in features.columns:
        features["date"] = pd.to_datetime(
            features["date"],
            errors="coerce",
        )

        features["month"] = features[
            "date"
        ].dt.month

        features["day_of_week"] = features[
            "date"
        ].dt.dayofweek

    if "day_of_week" in features.columns:
        features["is_weekend"] = (
            features["day_of_week"] >= 5
        ).astype(int)

    if "is_holiday" not in features.columns:
        features["is_holiday"] = 0

    if "is_festival" not in features.columns:
        features["is_festival"] = 0

    if "festival_importance" not in features.columns:
        features["festival_importance"] = 0.0

    for column in CROWD_FEATURE_COLUMNS:
        if column in features.columns:
            features[column] = pd.to_numeric(
                features[column],
                errors="coerce",
            ).fillna(0)

    return features


def calculate_crowd_features(
    month=1,
    day_of_week=0,
    is_weekend=0,
    is_holiday=0,
    is_festival=0,
    festival_importance=0,
):
    return {
        "month": month,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
        "is_festival": is_festival,
        "festival_importance": festival_importance,
    }