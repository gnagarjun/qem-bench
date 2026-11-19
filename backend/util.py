import numpy as np
import pandas as pd


def records(df: pd.DataFrame) -> list[dict]:
    clean = df.replace([np.inf, -np.inf], [1e308, -1e308]).astype(object).where(df.notna(), None)
    return clean.to_dict(orient="records")


def filt(df: pd.DataFrame, **kw) -> pd.DataFrame:
    for k, v in kw.items():
        if v is None or v == "":
            continue
        col = df[k]
        df = df[col == (int(v) if col.dtype.kind in "iu" else float(v) if col.dtype.kind == "f" else v)]
    return df
