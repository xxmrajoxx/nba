import pandas as pd
from nba_api.stats.endpoints import ScheduleLeagueV2

import db
from nba_client import fetch
from seasons import current_season

COLUMNS = {
    "gameId": "game_id",
    "gameDate": "game_date",
    "gameDateTimeEst": "game_datetime_est",
    "day": "day",
    "weekNumber": "week_number",
    "weekName": "week_name",
    "gameLabel": "game_label",
    "gameSubLabel": "game_sub_label",
    "gameStatusText": "game_status_text",
    "arenaName": "arena_name",
    "arenaCity": "arena_city",
    "arenaState": "arena_state",
    "homeTeam_teamId": "home_team_id",
    "homeTeam_teamTricode": "home_team_tricode",
    "awayTeam_teamId": "away_team_id",
    "awayTeam_teamTricode": "away_team_tricode",
}


def build_schedule_df(season: str) -> pd.DataFrame:
    games = fetch(ScheduleLeagueV2, season=season).season_games.get_data_frame()
    df = games[list(COLUMNS)].rename(columns=COLUMNS)
    df.insert(1, "season", season)
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    df["game_datetime_est"] = pd.to_datetime(df["game_datetime_est"], errors="coerce", utc=True).dt.tz_localize(None)
    # Games whose teams are not decided yet (e.g. cup knockout rounds) have team id 0.
    for col in ("home_team_id", "away_team_id"):
        df[col] = df[col].astype("Int64").mask(df[col] == 0)
    df = df.replace("", None)
    return df.sort_values("game_date").reset_index(drop=True)


def run(season: str = None) -> int:
    return db.upsert(build_schedule_df(season or current_season()), "schedule", keys=["game_id"])
