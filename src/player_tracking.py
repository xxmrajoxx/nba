import logging

import pandas as pd
from nba_api.stats.endpoints import LeagueDashPtStats, LeagueHustleStatsPlayer
from sqlalchemy import text

import db
from nba_client import fetch

logger = logging.getLogger(__name__)

DATASET = "tracking"
FIRST_TRACKING_SEASON = "2013-14"
FIRST_HUSTLE_SEASON = "2015-16"

TRACKING_COLUMNS = [
    "DIST_FEET", "DIST_MILES", "DIST_MILES_OFF", "DIST_MILES_DEF",
    "AVG_SPEED", "AVG_SPEED_OFF", "AVG_SPEED_DEF",
]
HUSTLE_COLUMNS = [
    "CONTESTED_SHOTS", "CONTESTED_SHOTS_2PT", "CONTESTED_SHOTS_3PT", "DEFLECTIONS",
    "CHARGES_DRAWN", "SCREEN_ASSISTS", "SCREEN_AST_PTS", "OFF_LOOSE_BALLS_RECOVERED",
    "DEF_LOOSE_BALLS_RECOVERED", "LOOSE_BALLS_RECOVERED", "OFF_BOXOUTS", "DEF_BOXOUTS", "BOX_OUTS",
]


def get_tracking_for_date(game_date, season: str, season_type: str) -> pd.DataFrame:
    """Tracking and hustle stats for every player who played on one date.

    These stats are only published per game through box score endpoints (one request per
    game). Asking the league-wide endpoints for a single day returns the same numbers for
    every game that day in one request, because a player plays at most one game a day.
    """
    day = game_date.strftime("%m/%d/%Y")
    tracking = fetch(
        LeagueDashPtStats,
        season=season,
        season_type_all_star=season_type,
        player_or_team="Player",
        pt_measure_type="SpeedDistance",
        per_mode_simple="Totals",
        date_from_nullable=day,
        date_to_nullable=day,
    ).get_data_frames()[0]
    # reindex keeps the column set fixed when a result is empty or an old season lacks a stat
    df = tracking.reindex(columns=["PLAYER_ID"] + TRACKING_COLUMNS)

    if season >= FIRST_HUSTLE_SEASON:
        hustle = fetch(
            LeagueHustleStatsPlayer,
            season=season,
            season_type_all_star=season_type,
            per_mode_time="Totals",
            date_from_nullable=day,
            date_to_nullable=day,
        ).get_data_frames()[0]
        df = df.merge(hustle.reindex(columns=["PLAYER_ID"] + HUSTLE_COLUMNS), on="PLAYER_ID", how="outer")
    else:
        df = df.reindex(columns=["PLAYER_ID"] + TRACKING_COLUMNS + HUSTLE_COLUMNS)

    df.columns = df.columns.str.lower()
    return df


def run(season: str = None, limit: int = None) -> int:
    """Fetch tracking and hustle stats for every game date in dbo.player_game_log that has
    not been fetched yet, oldest first. Each date is saved as it completes, so the job can
    be stopped (Ctrl+C) and re-run to carry on from where it left off."""
    pending = db.read_sql(f"""
        SELECT DISTINCT l.game_date, l.season, l.season_type
        FROM dbo.player_game_log AS l
        WHERE l.season >= '{FIRST_TRACKING_SEASON}'
          AND NOT EXISTS (
              SELECT 1 FROM etl.date_load AS d WHERE d.dataset = '{DATASET}' AND d.game_date = l.game_date
          )
        ORDER BY l.game_date
    """)
    if season:
        pending = pending[pending["season"] == season]
    if limit:
        pending = pending.head(limit)
    logger.info(f"{len(pending)} game dates to fetch")

    mark_loaded = text("INSERT INTO etl.date_load (dataset, game_date, rows_loaded) VALUES (:dataset, :game_date, :rows)")
    total = 0
    for i, row in enumerate(pending.itertuples(index=False), start=1):
        df = get_tracking_for_date(row.game_date, row.season, row.season_type)
        # The endpoints give no game id, so take it from the game log (which also limits rows to known players).
        with db.get_engine().connect() as conn:
            games = pd.read_sql(
                text("SELECT player_id, game_id, game_date FROM dbo.player_game_log WHERE game_date = :game_date"),
                conn,
                params={"game_date": row.game_date},
            )
        df = games.merge(df, on="player_id", how="inner")

        rows = db.upsert(df, "player_game_tracking", keys=["player_id", "game_id"])
        with db.get_engine().begin() as conn:
            conn.execute(mark_loaded, {"dataset": DATASET, "game_date": row.game_date, "rows": rows})
        total += rows
        logger.info(f"[{i}/{len(pending)}] {row.game_date} {row.season_type}: {rows} rows")
    return total
