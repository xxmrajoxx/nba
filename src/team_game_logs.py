import logging

import pandas as pd
from nba_api.stats.endpoints import TeamGameLogs

import config
import db
from nba_client import fetch
from player_game_logs import (
    ADVANCED_STAT_COLUMNS, BASE_STAT_COLUMNS, CONTEXT_COLUMNS, INFO_COLUMNS, tidy_game_logs,
)

logger = logging.getLogger(__name__)

KEY_COLUMNS = ["TEAM_ID", "GAME_ID"]
# Usage rate is a player stat; a team's is always 100%.
TEAM_ADVANCED_COLUMNS = [c for c in ADVANCED_STAT_COLUMNS if c != "USG_PCT"]
OUTPUT_COLUMNS = (
    ["team_id", "game_id"] + [c for c in CONTEXT_COLUMNS if c != "team_id"]
    + ["minutes" if c == "MIN" else c.lower() for c in BASE_STAT_COLUMNS + TEAM_ADVANCED_COLUMNS]
)


def get_league_team_logs(season: str, season_type: str, measure_type: str) -> pd.DataFrame:
    return fetch(
        TeamGameLogs,
        season_nullable=season,
        season_type_nullable=season_type,
        measure_type_player_game_logs_nullable=measure_type,
    ).team_game_logs.get_data_frame()


def build_team_logs_df(season: str, season_type: str) -> pd.DataFrame:
    base = get_league_team_logs(season, season_type, "Base")
    if base.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    advanced = get_league_team_logs(season, season_type, "Advanced")

    info_columns = [c for c in INFO_COLUMNS if c != "TEAM_ID"]
    df = base[KEY_COLUMNS + info_columns + BASE_STAT_COLUMNS].merge(
        advanced[KEY_COLUMNS + TEAM_ADVANCED_COLUMNS],
        on=KEY_COLUMNS,
        how="left",
    )
    return tidy_game_logs(df, season_type)[OUTPUT_COLUMNS]


def run(seasons: list) -> int:
    total = 0
    for season in seasons:
        for season_type in config.SEASON_TYPES:
            df = build_team_logs_df(season, season_type)
            logger.info(f"{season} {season_type}: {len(df)} team game logs")
            total += db.upsert(df, "team_game_log", keys=["team_id", "game_id"])
    return total
