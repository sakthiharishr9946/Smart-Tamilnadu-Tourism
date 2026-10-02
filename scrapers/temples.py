import pandas as pd
from pathlib import Path


def load_temple_data(file_path):
    path = Path(file_path)

    if not path.exists():
        return pd.DataFrame()

    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)

        if path.suffix.lower() in [".xlsx", ".xls"]:
            return pd.read_excel(path)

        if path.suffix.lower() == ".json":
            return pd.read_json(path)

    except Exception:
        return pd.DataFrame()

    return pd.DataFrame()


def save_temple_data(df, file_path):
    if df is None or df.empty:
        return False

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if path.suffix.lower() == ".csv":
            df.to_csv(path, index=False)
            return True

        if path.suffix.lower() in [".xlsx", ".xls"]:
            df.to_excel(path, index=False)
            return True

        if path.suffix.lower() == ".json":
            df.to_json(path, orient="records", indent=2)
            return True

    except Exception:
        return False

    return False


def collect_temple_data(file_path):
    return load_temple_data(file_path)