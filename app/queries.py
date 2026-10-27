"""Every query the app runs, against one of two data sources:

    sqlserver  the live nba database (the normal way on your PC)
    parquet    the Parquet snapshot in data/, read with DuckDB (no SQL Server needed;
               this is how the app will run once deployed)

Choose with the NBA_DATA_SOURCE environment variable: "sqlserver", "parquet", or "auto"
(the default: SQL Server if it answers, otherwise Parquet). The Parquet files are named
like the SQL objects (dbo.player.parquet), so the same SQL works on both.

Values always go in as bind parameters (:player_id), never pasted into the SQL text, so
nothing typed or selected in the app can change a query.
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config  # noqa: E402
import db  # noqa: E402

# Results are cached for 10 minutes, so clicking around the app doesn't re-run queries.
CACHE_SECONDS = 600
SOURCE_SETTING = os.getenv("NBA_DATA_SOURCE", "auto").lower()
EXPORT_COMMAND = r".venv\Scripts\python.exe src\run_job.py export"

GAME_COLUMNS = [
    "game_id", "game_date", "season", "season_type", "matchup", "wl", "is_home", "opponent_abbreviation",
    "days_from_birthday", "birthday_phase", "is_birthday_week", "is_birthday", "age_at_game",
    "minutes", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "plus_minus",
    "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
    "ts_pct", "efg_pct", "usg_pct", "off_rating", "def_rating", "net_rating", "pie",
    "pct_fga", "pct_pts", "pct_ast_fgm",
    "days_rest", "back_to_back", "key_teammates_out", "top_scorer_out", "tipoff_et", "tipoff_hour_et", "arena_city",
    "is_starter", "dist_miles", "avg_speed", "passes_received", "touches", "deflections",
]


# ---------------------------------------------------------------- choosing and using a source

@st.cache_resource
def source() -> str:
    """Which data source this app session uses. Worked out once and remembered."""
    if SOURCE_SETTING in ("sqlserver", "parquet"):
        return SOURCE_SETTING
    try:
        db.read_sql("SELECT 1 AS ok")
        return "sqlserver"
    except Exception:
        return "parquet"


@st.cache_resource
def duckdb_connection():
    """An in-memory DuckDB database whose views point at the Parquet files, named like
    the SQL Server objects (dbo.player, etl.job_run...)."""
    import duckdb   # only needed for the Parquet source

    files = sorted(config.DATA_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No Parquet files in {config.DATA_DIR}")
    con = duckdb.connect()
    for path in files:
        schema, table = path.stem.split(".", 1)
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        con.execute(f"CREATE VIEW {schema}.{table} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    # v_player_game_birthday's columns are a subset of v_player_game_features, so the
    # features file serves both instead of exporting the same games twice.
    con.execute("CREATE VIEW IF NOT EXISTS dbo.v_player_game_birthday AS SELECT * FROM dbo.v_player_game_features")
    return con


def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    if source() == "sqlserver":
        return db.read_sql(sql, params)
    # DuckDB writes parameters as $name rather than :name. A cursor per query keeps
    # concurrent app sessions from sharing one.
    cursor = duckdb_connection().cursor()
    return cursor.execute(re.sub(r":(\w+)", r"$\1", sql), params or {}).df()


def source_description() -> str:
    if source() == "sqlserver":
        return f"SQL Server (live): {config.SERVER}/{config.DATABASE}"
    manifest = config.DATA_DIR / "manifest.json"
    exported = json.loads(manifest.read_text())["exported_at"].replace("T", " ") if manifest.exists() else "unknown"
    return f"Parquet snapshot from {exported}"


def parquet_missing() -> bool:
    return source() == "parquet" and not any(config.DATA_DIR.glob("*.parquet"))


# ---------------------------------------------------------------- the queries

@st.cache_data(ttl=CACHE_SECONDS)
def players() -> pd.DataFrame:
    return run_query("""
        SELECT p.player_id, p.full_name, p.birthdate, p.birthdate_mdy, p.position, p.height,
               p.weight_lbs, p.country, p.from_year, p.is_active, t.abbreviation AS team, t.full_name AS team_name
        FROM dbo.player AS p
        LEFT JOIN dbo.team AS t ON t.team_id = p.team_id
        ORDER BY p.full_name
    """)


@st.cache_data(ttl=CACHE_SECONDS)
def player_games(player_id: int) -> pd.DataFrame:
    df = run_query(
        f"SELECT {', '.join(GAME_COLUMNS)} FROM dbo.v_player_game_features WHERE player_id = :player_id",
        {"player_id": player_id},
    )
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df.sort_values("game_date", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=CACHE_SECONDS)
def player_seasons(player_id: int) -> pd.DataFrame:
    return run_query(
        "SELECT * FROM dbo.v_birthday_week_vs_season WHERE player_id = :player_id ORDER BY season",
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_SECONDS)
def player_missed_games(player_id: int) -> pd.DataFrame:
    return run_query(
        """SELECT game_date, season, season_type, days_from_birthday, birthday_phase
           FROM dbo.v_player_missed_games WHERE player_id = :player_id ORDER BY game_date DESC""",
        {"player_id": player_id},
    )


@st.cache_data(ttl=CACHE_SECONDS)
def upcoming_birthday_games() -> pd.DataFrame:
    df = run_query("""
        SELECT player_id, full_name, game_date, away_team_tricode, home_team_tricode, game_label, days_from_birthday
        FROM dbo.v_upcoming_birthday_week_games
        ORDER BY game_date, full_name
    """)
    df["game"] = df["away_team_tricode"] + " @ " + df["home_team_tricode"]
    # A Parquet snapshot was taken on the day it was exported; drop games that have since been played.
    return df[pd.to_datetime(df["game_date"]).dt.date >= date.today()]


@st.cache_data(ttl=CACHE_SECONDS)
def league_birthday_leaders(min_games: int) -> pd.DataFrame:
    """Players' average birthday-week scoring difference across all their seasons."""
    return run_query(
        """
        SELECT full_name,
               COUNT(*) AS seasons,
               SUM(birthday_week_games) AS birthday_week_games,
               AVG(birthday_week_pts) AS birthday_week_pts,
               AVG(other_pts) AS other_pts,
               AVG(birthday_week_pts - other_pts) AS pts_difference
        FROM dbo.v_birthday_week_vs_season
        GROUP BY player_id, full_name
        HAVING SUM(birthday_week_games) >= :min_games
        """,
        {"min_games": min_games},
    )


@st.cache_data(ttl=CACHE_SECONDS)
def games_on(day: date) -> pd.DataFrame:
    """Every game scheduled on one date (US date, as the NBA schedule uses), with the final
    score once the team game logs for it are loaded."""
    df = run_query("""
        SELECT s.game_id, s.season, s.game_date, s.game_datetime_est, s.game_label, s.game_sub_label,
               s.game_status_text, s.arena_name, s.arena_city, s.arena_state,
               s.away_team_tricode, s.home_team_tricode, a.pts AS away_pts, h.pts AS home_pts
        FROM dbo.schedule AS s
        LEFT JOIN dbo.team_game_log AS a ON a.game_id = s.game_id AND a.team_id = s.away_team_id
        LEFT JOIN dbo.team_game_log AS h ON h.game_id = s.game_id AND h.team_id = s.home_team_id
        WHERE s.game_date = :day
        ORDER BY s.game_datetime_est, s.game_id
    """, {"day": day})
    df["game_datetime_est"] = pd.to_datetime(df["game_datetime_est"])
    return df


@st.cache_data(ttl=CACHE_SECONDS)
def season_games(season: str) -> pd.DataFrame:
    """Every loaded game of one season, box score only. Reads v_player_game_birthday rather
    than the modelling view: a whole season from the modelling view takes nearly a minute
    on SQL Server, this takes under a second."""
    df = run_query("""
        SELECT b.player_id, b.game_id, b.game_date, b.season_type, b.matchup, b.wl, b.days_from_birthday,
               b.minutes, b.pts, b.reb, b.ast, b.stl, b.blk, b.tov, b.fgm, b.fga, b.fg_pct, b.fg3m, b.fg3a,
               b.fg3_pct, b.ftm, b.fta, b.ts_pct, b.plus_minus, s.game_datetime_est AS tipoff_et
        FROM dbo.v_player_game_birthday AS b
        LEFT JOIN dbo.schedule AS s ON s.game_id = b.game_id
        WHERE b.season = :season
    """, {"season": season})
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


@st.cache_data(ttl=CACHE_SECONDS)
def nearest_game_dates(day: date) -> pd.DataFrame:
    """The closest dates before and after `day` that have games, for when `day` has none."""
    return run_query("""
        SELECT MAX(CASE WHEN game_date < :day THEN game_date END) AS previous_date,
               MIN(CASE WHEN game_date > :day THEN game_date END) AS next_date
        FROM dbo.schedule
    """, {"day": day})


@st.cache_data(ttl=CACHE_SECONDS)
def pipeline_status() -> pd.DataFrame:
    df = run_query("""
        SELECT run_id, job_name, status, started_at, finished_at, rows_loaded
        FROM etl.job_run ORDER BY run_id DESC
    """)
    return df.head(10)
