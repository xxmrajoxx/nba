import logging

import pandas as pd

import config
import db
from player_game_logs import KEY_COLUMNS, get_league_game_logs, known_player_ids

logger = logging.getLogger(__name__)

# Share of the team's totals the player accounted for while on the court.
USAGE_COLUMNS = [
    "PCT_FGM", "PCT_FGA", "PCT_FG3M", "PCT_FG3A", "PCT_FTM", "PCT_FTA",
    "PCT_OREB", "PCT_DREB", "PCT_REB", "PCT_AST", "PCT_TOV", "PCT_STL",
    "PCT_BLK", "PCT_PF", "PCT_PTS",
]
# Where the player's shots and points came from, and how many makes were assisted.
SCORING_COLUMNS = [
    "PCT_FGA_2PT", "PCT_FGA_3PT", "PCT_PTS_2PT", "PCT_PTS_2PT_MR", "PCT_PTS_3PT",
    "PCT_PTS_FB", "PCT_PTS_FT", "PCT_PTS_OFF_TOV", "PCT_PTS_PAINT",
    "PCT_AST_2PM", "PCT_UAST_2PM", "PCT_AST_3PM", "PCT_UAST_3PM",
    "PCT_AST_FGM", "PCT_UAST_FGM",
]
OUTPUT_COLUMNS = [c.lower() for c in KEY_COLUMNS + USAGE_COLUMNS + SCORING_COLUMNS]


def build_usage_df(season: str, season_type: str) -> pd.DataFrame:
    usage = get_league_game_logs(season, season_type, "Usage")
    if usage.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    scoring = get_league_game_logs(season, season_type, "Scoring")

    df = usage[KEY_COLUMNS + USAGE_COLUMNS].merge(
        scoring[KEY_COLUMNS + SCORING_COLUMNS],
        on=KEY_COLUMNS,
        how="left",
    )
    df.columns = df.columns.str.lower()
    return df


def run(seasons: list) -> int:
    player_ids = known_player_ids()
    total = 0
    for season in seasons:
        for season_type in config.SEASON_TYPES:
            df = build_usage_df(season, season_type)
            df = df[df["player_id"].isin(player_ids)]
            logger.info(f"{season} {season_type}: {len(df)} usage rows")
            total += db.upsert(df, "player_game_usage", keys=["player_id", "game_id"])
    return total
