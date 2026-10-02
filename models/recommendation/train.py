from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
)


MODEL_PATH = (
    Path(__file__).parent
    / "saved"
    / "recommendation_model.pkl"
)


FEATURE_COLUMNS = [
    "rating",
    "rating_count",
    "popularity_score",
    "distance_km",
    "interest_score",
    "rating_confidence",
]


TARGET_COLUMN = "recommendation_score"


def prepare_training_data(df):
    if df is None or df.empty:
        return None, None

    data = df.copy()

    required_columns = (
        FEATURE_COLUMNS
        + [TARGET_COLUMN]
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        return None, None

    data = data.dropna(
        subset=required_columns
    )

    if data.empty:
        return None, None

    X = data[
        FEATURE_COLUMNS
    ].copy()

    for column in FEATURE_COLUMNS:
        X[column] = pd.to_numeric(
            X[column],
            errors="coerce",
        )

    y = pd.to_numeric(
        data[TARGET_COLUMN],
        errors="coerce",
    )

    valid_rows = (
        X.notna().all(axis=1)
        & y.notna()
    )

    X = X.loc[valid_rows]
    y = y.loc[valid_rows]

    if X.empty or y.empty:
        return None, None

    return X, y


def train_recommendation_model(
    df,
    model_name="recommendation_model.pkl",
):
    X, y = prepare_training_data(df)

    if X is None or y is None:
        return None

    if len(X) < 5:
        return None

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
        )
    )

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
    )

    try:
        model.fit(
            X_train,
            y_train,
        )

        predictions = model.predict(
            X_test
        )

        mae = mean_absolute_error(
            y_test,
            predictions,
        )

        if len(y_test) >= 2:
            r2 = r2_score(
                y_test,
                predictions,
            )
        else:
            r2 = 0.0

    except Exception:
        return None

    model_path = (
        Path(__file__).parent
        / "saved"
        / model_name
    )

    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        joblib.dump(
            {
                "model": model,
                "features": FEATURE_COLUMNS,
            },
            model_path,
        )
    except Exception:
        return None

    return {
        "model": model,
        "features": FEATURE_COLUMNS,
        "model_path": str(model_path),
        "mae": round(
            float(mae),
            4,
        ),
        "r2_score": round(
            float(r2),
            4,
        ),
        "X_test": X_test,
        "y_test": y_test,
        "predictions": predictions,
    }