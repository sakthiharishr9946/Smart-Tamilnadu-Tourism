import pandas as pd


def prepare_crowd_input(
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


def predict_crowd(model, features):
    if model is None:
        return None

    if features is None or features.empty:
        return None

    try:
        prediction = model.predict(features)

        if prediction is None or len(prediction) == 0:
            return None

        return prediction[0]

    except Exception:
        return None


def predict_crowd_level(
    model,
    month,
    day_of_week,
    is_weekend,
    is_holiday,
    is_festival,
    festival_importance,
):
    features = prepare_crowd_input(
        month,
        day_of_week,
        is_weekend,
        is_holiday,
        is_festival,
        festival_importance,
    )

    return predict_crowd(
        model,
        features,
    )