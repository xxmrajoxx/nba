import logging

import pandas as pd
from nba_api.stats.endpoints import PlayerGameLogs

import config
import db
from nba_client import fetch

logger = logging.getLogger(__name__)

KEY_COLUMNS = ["PLAYER_ID", "GAME_ID"]
INFO_COLUMNS = ["SEASON_YEAR", "GAME_DATE", "TEAM_ID", "TEAM_ABBREVIATION", "MATCHUP", "WL"]
BASE_STAT_COLUMNS = [
    "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
    "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "TOV",
    "STL", "BLK", "PF", "PTS", "PLUS_MINUS",
]
ADVANCED_STAT_COLUMNS = [
    "OFF_RATING", "DEF_RATING", "NET_RATING", "AST_PCT", "AST_TO", "AST_RATIO",
    "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "EFG_PCT", "TS_PCT",
    "USG_PCT", "PACE", "PIE", "POSS",
]
CONTEXT_COLUMNS = [
    "season", "season_type", "game_date", "team_id",
    "team_abbreviation", "opponent_abbreviation", "is_home", "matchup", "wl",
]
OUTPUT_COLUMNS = (
    ["player_id", "game_id"] + CONTEXT_COLUMNS
    + ["minutes" if c == "MIN" else c.lower() for c in BASE_STAT_COLUMNS + ADVANCED_STAT_COLUMNS]
)


def get_league_game_logs(season: str, season_type: str, measure_type: str) -> pd.DataFrame:
    # Leaving the player id out returns every player's games for the season in one request.
    return fetch(
        PlayerGameLogs,
        season_nullable=season,
        season_type_nullable=season_type,
        measure_type_player_game_logs_nullable=measure_type,
    ).player_game_logs.get_data_frame()


def tidy_game_logs(df: pd.DataFrame, season_type: str) -> pd.DataFrame:
    """Lower-case the API's column names and derive the context columns shared by player and team logs."""
    df.columns = df.columns.str.lower()
    df = df.rename(columns={"season_year": "season", "min": "minutes"})
    df["season_type"] = season_type
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    # MATCHUP looks like "LAL vs. BOS" (home) or "LAL @ BOS" (away).
    df["is_home"] = df["matchup"].str.contains("vs.", regex=False)
    df["opponent_abbreviation"] = df["matchup"].str.split().str[-1]
    return df


def build_game_logs_df(season: str, season_type: str) -> pd.DataFrame:
    base = get_league_game_logs(season, season_type, "Base")
    if base.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    advanced = get_league_game_logs(season, season_type, "Advanced")

    df = base[KEY_COLUMNS + INFO_COLUMNS + BASE_STAT_COLUMNS].merge(
        advanced[KEY_COLUMNS + ADVANCED_STAT_COLUMNS],
        on=KEY_COLUMNS,
        how="left",
    )
    return tidy_game_logs(df, season_type)[OUTPUT_COLUMNS]


def known_player_ids() -> pd.Series:
    players = db.read_sql("SELECT player_id FROM dbo.player")
    if players.empty:
        raise RuntimeError("dbo.player is empty - run the players job first")
    return players["player_id"]


def run(seasons: list) -> int:
    player_ids = known_player_ids()
    total = 0
    for season in seasons:
        for season_type in config.SEASON_TYPES:
            df = build_game_logs_df(season, season_type)
            df = df[df["player_id"].isin(player_ids)]
            logger.info(f"{season} {season_type}: {len(df)} game logs")
            total += db.upsert(df, "player_game_log", keys=["player_id", "game_id"])
    return total
