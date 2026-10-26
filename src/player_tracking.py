import logging
from datetime import date, timedelta

import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerStats, LeagueDashPtStats, LeagueHustleStatsPlayer
from sqlalchemy import text

import db
from nba_client import fetch

logger = logging.getLogger(__name__)

DATASET = "tracking"
FIRST_TRACKING_SEASON = "2013-14"
FIRST_HUSTLE_SEASON = "2015-16"
# The NBA publishes tracking stats a day or two after the games. A recent date that comes
# back without them is retried on the next run instead of being marked as done.
RECENT_DAYS = 7

# Player tracking stat sets, by the API's pt_measure_type name.
PT_MEASURES = {
    "SpeedDistance": [
        "DIST_FEET", "DIST_MILES", "DIST_MILES_OFF", "DIST_MILES_DEF",
        "AVG_SPEED", "AVG_SPEED_OFF", "AVG_SPEED_DEF",
    ],
    "Passing": [
        "PASSES_MADE", "PASSES_RECEIVED", "FT_AST", "SECONDARY_AST", "POTENTIAL_AST", "AST_PTS_CREATED",
    ],
    "Possessions": [
        "TOUCHES", "FRONT_CT_TOUCHES", "TIME_OF_POSS", "AVG_SEC_PER_TOUCH", "AVG_DRIB_PER_TOUCH",
        "PTS_PER_TOUCH", "ELBOW_TOUCHES", "POST_TOUCHES", "PAINT_TOUCHES",
    ],
}
HUSTLE_COLUMNS = [
    "CONTESTED_SHOTS", "CONTESTED_SHOTS_2PT", "CONTESTED_SHOTS_3PT", "DEFLECTIONS",
    "CHARGES_DRAWN", "SCREEN_ASSISTS", "SCREEN_AST_PTS", "OFF_LOOSE_BALLS_RECOVERED",
    "DEF_LOOSE_BALLS_RECOVERED", "LOOSE_BALLS_RECOVERED", "OFF_BOXOUTS", "DEF_BOXOUTS", "BOX_OUTS",
]


def get_pt_stats(measure: str, day: str, season: str, season_type: str) -> pd.DataFrame:
    df = fetch(
        LeagueDashPtStats,
        season=season,
        season_type_all_star=season_type,
        player_or_team="Player",
        pt_measure_type=measure,
        per_mode_simple="Totals",
        date_from_nullable=day,
        date_to_nullable=day,
    ).get_data_frames()[0]
    # reindex keeps the column set fixed when a result is empty or an old season lacks a stat
    return df.reindex(columns=["PLAYER_ID"] + PT_MEASURES[measure])


def get_hustle_stats(day: str, season: str, season_type: str) -> pd.DataFrame:
    if season < FIRST_HUSTLE_SEASON:
        return pd.DataFrame(columns=["PLAYER_ID"] + HUSTLE_COLUMNS)
    df = fetch(
        LeagueHustleStatsPlayer,
        season=season,
        season_type_all_star=season_type,
        per_mode_time="Totals",
        date_from_nullable=day,
        date_to_nullable=day,
    ).get_data_frames()[0]
    return df.reindex(columns=["PLAYER_ID"] + HUSTLE_COLUMNS)


def get_starter_ids(day: str, season: str, season_type: str) -> set:
    df = fetch(
        LeagueDashPlayerStats,
        season=season,
        season_type_all_star=season_type,
        starter_bench_nullable="Starters",
        date_from_nullable=day,
        date_to_nullable=day,
    ).get_data_frames()[0]
    return set(df["PLAYER_ID"])


def get_tracking_for_date(game_date, season: str, season_type: str) -> pd.DataFrame:
    """Tracking, passing, touches, hustle and starter data for every player who played on one date.

    These stats are only published per game through box score endpoints (one request per
    game). Asking the league-wide endpoints for a single day returns the same numbers for
    every game that day in one request each, because a player plays at most one game a day.
    """
    day = game_date.strftime("%m/%d/%Y")
    frames = [get_pt_stats(measure, day, season, season_type) for measure in PT_MEASURES]
    frames.append(get_hustle_stats(day, season, season_type))

    df = frames[0]
    for frame in frames[1:]:
        df = df.merge(frame, on="PLAYER_ID", how="outer")
    df.columns = df.columns.str.lower()
    df.attrs["starter_ids"] = get_starter_ids(day, season, season_type)
    return df


def run(season: str = None, limit: int = None) -> int:
    """Fetch tracking data for every game date in dbo.player_game_log that has not been
    fetched yet, oldest first. Each date is saved as it completes, so the job can be
    stopped (Ctrl+C) and re-run to carry on from where it left off."""
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
        stats = get_tracking_for_date(row.game_date, row.season, row.season_type)
        # Start from the game log: the endpoints give no game id, and every player who
        # played should get a row (and a starter flag) even if a tracking stat is missing.
        with db.get_engine().connect() as conn:
            df = pd.read_sql(
                text("SELECT player_id, game_id, game_date FROM dbo.player_game_log WHERE game_date = :game_date"),
                conn,
                params={"game_date": row.game_date},
            )
        df["is_starter"] = df["player_id"].isin(stats.attrs["starter_ids"])
        df = df.merge(stats, on="player_id", how="left")

        rows = db.upsert(df, "player_game_tracking", keys=["player_id", "game_id"])
        total += rows
        not_published = df["dist_miles"].isna().all() and row.game_date >= date.today() - timedelta(days=RECENT_DAYS)
        if not_published:
            # Save what there is (hustle, starters) but leave the date pending, so the next
            # run fetches it again once the tracking stats are out.
            logger.warning(f"[{i}/{len(pending)}] {row.game_date}: tracking stats not published yet; "
                           f"saved {rows} rows without them and will retry on the next run")
            continue
        with db.get_engine().begin() as conn:
            conn.execute(mark_loaded, {"dataset": DATASET, "game_date": row.game_date, "rows": rows})
        logger.info(f"[{i}/{len(pending)}] {row.game_date} {row.season_type}: {rows} rows")
    return total
