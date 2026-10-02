from pathlib import Path

import joblib
import pandas as pd

from config.settings import CROWD_MODEL_DIR


DEFAULT_MODEL_PATH = (
    Path(CROWD_MODEL_DIR)
    / "crowd_model.pkl"
)


def load_crowd_model(
    model_path=DEFAULT_MODEL_PATH,
):
    model_path = Path(model_path)

    if not model_path.exists():
        return None

    try:
        return joblib.load(model_path)
    except Exception:
        return None


def prepare_prediction_data(
    month,
    day_of_week,
    is_weekend,
    is_holiday,
    is_festival,
    festival_importance,
):
    return pd.DataFrame(
        [
            {
                "month": month,
                "day_of_week": day_of_week,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "is_festival": is_festival,
                "festival_importance": festival_importance,
            }
        ]
    )


def encode_festival_importance(
    features,
    festival_encoder,
):
    if festival_encoder is None:
        return features

    try:
        value = str(
            features.loc[
                0,
                "festival_importance",
            ]
        )

        encoded_value = festival_encoder.transform(
            [value]
        )[0]

        features.loc[
            0,
            "festival_importance",
        ] = encoded_value

        return features

    except (ValueError, TypeError):
        return None


def predict_crowd(
    model_data,
    month,
    day_of_week,
    is_weekend,
    is_holiday,
    is_festival,
    festival_importance,
):
    if not model_data:
        return None

    model = model_data.get("model")

    label_encoder = model_data.get(
        "label_encoder"
    )

    festival_encoder = model_data.get(
        "festival_encoder"
    )

    if model is None:
        return None

    features = prepare_prediction_data(
        month,
        day_of_week,
        is_weekend,
        is_holiday,
        is_festival,
        festival_importance,
    )

    features = encode_festival_importance(
        features,
        festival_encoder,
    )

    if features is None:
        return None

    try:
        prediction = model.predict(
            features
        )

        if (
            label_encoder is not None
            and len(prediction) > 0
        ):
            prediction = (
                label_encoder.inverse_transform(
                    prediction
                )
            )

        if len(prediction) == 0:
            return None

        return str(prediction[0])

    except Exception:
        return None


def predict_crowd_probability(
    model_data,
    month,
    day_of_week,
    is_weekend,
    is_holiday,
    is_festival,
    festival_importance,
):
    if not model_data:
        return None

    model = model_data.get("model")

    label_encoder = model_data.get(
        "label_encoder"
    )

    festival_encoder = model_data.get(
        "festival_encoder"
    )

    if model is None:
        return None

    if not hasattr(
        model,
        "predict_proba",
    ):
        return None

    features = prepare_prediction_data(
        month,
        day_of_week,
        is_weekend,
        is_holiday,
        is_festival,
        festival_importance,
    )

    features = encode_festival_importance(
        features,
        festival_encoder,
    )

    if features is None:
        return None

    try:
        probabilities = model.predict_proba(
            features
        )[0]

        classes = model.classes_

        if label_encoder is not None:
            class_labels = (
                label_encoder.inverse_transform(
                    classes
                )
            )
        else:
            class_labels = classes

        return {
            str(label): round(
                float(probability),
                4,
            )
            for label, probability in zip(
                class_labels,
                probabilities,
            )
        }

    except Exception:
        return None