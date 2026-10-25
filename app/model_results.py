"""Loads the model results written by src/models/run_models.py from the outputs/ folder."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
FILES = ["event_study.csv", "phase_effects.csv", "phase_by_age.csv", "availability.csv", "player_effects.csv"]
RUN_COMMAND = r".venv\Scripts\python.exe src\models\run_models.py"


def version() -> float:
    """Latest modification time of the result files. Passing it to the cached loaders means
    re-running the models makes the app pick up the new files straight away."""
    paths = [OUTPUT_DIR / f for f in FILES]
    return max(p.stat().st_mtime for p in paths) if all(p.exists() for p in paths) else 0.0


def available() -> bool:
    return version() > 0


@st.cache_data
def load(name: str, _version: float) -> pd.DataFrame:
    return pd.read_csv(OUTPUT_DIR / name)


@st.cache_data
def info(_version: float) -> dict:
    path = OUTPUT_DIR / "model_info.json"
    return json.loads(path.read_text()) if path.exists() else {}


def results() -> dict:
    v = version()
    return {name.removesuffix(".csv"): load(name, v) for name in FILES} | {"info": info(v)}
