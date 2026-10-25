"""Shared data loading for the models in this folder."""
import sys
from pathlib import Path

import pandas as pd

# The models live one folder below src/, so make src/ importable (for db and config).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402
from outcomes import CONTROLS, OUTCOMES  # noqa: E402

OUTPUT_DIR = config.PROJECT_ROOT / "outputs"

BASE_COLUMNS = ["player_id", "full_name", "season", "game_date", "days_from_birthday", "birthday_phase", "age_at_game"]


def add_week_of_season(df: pd.DataFrame) -> pd.DataFrame:
    # Weeks since the season's first game. Birthdays in February land in a different
    # part of the schedule from birthdays in November, so models control for this.
    df["game_date"] = pd.to_datetime(df["game_date"])
    season_start = df.groupby("season")["game_date"].transform("min")
    df["week_of_season"] = (df["game_date"] - season_start).dt.days // 7
    return df


def load_games(columns: list = None) -> pd.DataFrame:
    """Regular-season games the player actually played in, from dbo.v_player_game_features.
    By default loads every outcome and control the models use."""
    columns = columns if columns is not None else list(OUTCOMES) + CONTROLS
    wanted = list(dict.fromkeys(BASE_COLUMNS + columns))   # keeps order, drops duplicates
    df = db.read_sql(f"""
        SELECT {", ".join(wanted)}
        FROM dbo.v_player_game_features
        WHERE season_type = 'Regular Season' AND minutes > 0
    """)
    return add_week_of_season(df)


def load_availability() -> pd.DataFrame:
    """Every regular-season game a player's team played while he was on it, with played = 1
    if he played and 0 if he missed it."""
    df = db.read_sql("""
        SELECT player_id, season, game_date, days_from_birthday, birthday_phase, 1 AS played
        FROM dbo.v_player_game_features
        WHERE season_type = 'Regular Season' AND minutes > 0
        UNION ALL
        SELECT player_id, season, game_date, days_from_birthday, birthday_phase, 0 AS played
        FROM dbo.v_player_missed_games
        WHERE season_type = 'Regular Season'
    """)
    return add_week_of_season(df)
