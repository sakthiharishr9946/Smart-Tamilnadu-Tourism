from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from config.settings import CROWD_MODEL_DIR


FEATURE_COLUMNS = [
    "month",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "is_festival",
    "festival_importance",
]

TARGET_COLUMN = "crowd_level"


def prepare_training_data(df):
    if df is None or df.empty:
        return None, None

    data = df.copy()

    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN]

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

    X = data[FEATURE_COLUMNS].copy()

    y = data[TARGET_COLUMN].astype(str)

    return X, y


def train_crowd_model(
    df,
    model_name="crowd_model.pkl",
):
    X, y = prepare_training_data(df)

    if X is None or y is None:
        return None

    if len(X) < 5:
        return None

    if y.nunique() < 2:
        return None

    # Encode festival importance
    festival_encoder = LabelEncoder()

    X["festival_importance"] = (
        festival_encoder.fit_transform(
            X["festival_importance"].astype(str)
        )
    )

    # Encode target crowd level
    label_encoder = LabelEncoder()

    y_encoded = label_encoder.fit_transform(y)

    # Check whether stratified splitting is possible
    class_counts = pd.Series(
        y_encoded
    ).value_counts()

    use_stratify = class_counts.min() >= 2

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_encoded,
        test_size=0.2,
        random_state=42,
        stratify=y_encoded if use_stratify else None,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
    )

    model.fit(
        X_train,
        y_train,
    )

    model_path = (
        Path(CROWD_MODEL_DIR)
        / model_name
    )

    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        {
            "model": model,
            "label_encoder": label_encoder,
            "festival_encoder": festival_encoder,
            "features": FEATURE_COLUMNS,
        },
        model_path,
    )

    return {
        "model": model,
        "label_encoder": label_encoder,
        "festival_encoder": festival_encoder,
        "features": FEATURE_COLUMNS,
        "model_path": str(model_path),
        "X_test": X_test,
        "y_test": y_test,
    }