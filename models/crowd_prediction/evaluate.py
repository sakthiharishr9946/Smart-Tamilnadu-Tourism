import joblib
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)


def evaluate_crowd_model(
    model,
    X_test,
    y_test,
):
    if model is None:
        return None

    if X_test is None or y_test is None:
        return None

    if len(X_test) == 0 or len(y_test) == 0:
        return None

    try:
        predictions = model.predict(
            X_test
        )

        accuracy = accuracy_score(
            y_test,
            predictions,
        )

        report = classification_report(
            y_test,
            predictions,
            output_dict=True,
            zero_division=0,
        )

        matrix = confusion_matrix(
            y_test,
            predictions,
        )

        return {
            "accuracy": round(
                float(accuracy),
                4,
            ),
            "classification_report": report,
            "confusion_matrix": matrix,
        }

    except Exception:
        return None


def evaluate_saved_model(
    model_path,
    X_test,
    y_test,
):
    try:
        saved_data = joblib.load(
            model_path
        )
    except Exception:
        return None

    if not isinstance(
        saved_data,
        dict,
    ):
        return None

    model = saved_data.get(
        "model"
    )

    if model is None:
        return None

    return evaluate_crowd_model(
        model,
        X_test,
        y_test,
    )


def create_evaluation_dataframe(
    evaluation_result,
):
    if not evaluation_result:
        return pd.DataFrame()

    report = evaluation_result.get(
        "classification_report",
        {},
    )

    rows = []

    for label, metrics in report.items():
        if not isinstance(
            metrics,
            dict,
        ):
            continue

        rows.append(
            {
                "class": label,
                "precision": metrics.get(
                    "precision",
                    0,
                ),
                "recall": metrics.get(
                    "recall",
                    0,
                ),
                "f1_score": metrics.get(
                    "f1-score",
                    0,
                ),
                "support": metrics.get(
                    "support",
                    0,
                ),
            }
        )

    return pd.DataFrame(rows)