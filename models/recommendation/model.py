import joblib
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor


MODEL_PATH = (
    Path(__file__).parent
    / "saved"
    / "recommendation_model.pkl"
)


class RecommendationModel:

    def __init__(self):
        self.model = None
        self.features = []

    def train(self, X, y):
        if X is None or y is None:
            return False

        if len(X) == 0 or len(y) == 0:
            return False

        self.model = RandomForestRegressor(
            n_estimators=200,
            random_state=42,
        )

        try:
            self.model.fit(
                X,
                y,
            )

            if hasattr(X, "columns"):
                self.features = list(
                    X.columns
                )

            return True

        except Exception:
            self.model = None
            return False

    def predict(self, X):
        if self.model is None:
            return None

        if X is None:
            return None

        try:
            return self.model.predict(X)

        except Exception:
            return None

    def save(
        self,
        model_path=MODEL_PATH,
    ):
        if self.model is None:
            return False

        model_path = Path(
            model_path
        )

        model_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            joblib.dump(
                {
                    "model": self.model,
                    "features": self.features,
                },
                model_path,
            )

            return True

        except Exception:
            return False

    def load(
        self,
        model_path=MODEL_PATH,
    ):
        model_path = Path(
            model_path
        )

        if not model_path.exists():
            return False

        try:
            saved_data = joblib.load(
                model_path
            )

            # New saved format
            if isinstance(
                saved_data,
                dict,
            ):
                self.model = saved_data.get(
                    "model"
                )

                self.features = saved_data.get(
                    "features",
                    [],
                )

            # Support old model files
            else:
                self.model = saved_data
                self.features = []

            return self.model is not None

        except Exception:
            self.model = None
            self.features = []

            return False

    def is_loaded(self):
        return self.model is not None