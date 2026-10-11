import pandas as pd
from nba_api.stats.static import teams

import db


def build_teams_df() -> pd.DataFrame:
    df = pd.DataFrame(teams.get_teams()).rename(columns={"id": "team_id"})
    return df[["team_id", "abbreviation", "full_name", "nickname", "city", "state", "year_founded"]]


def run() -> int:
    return db.upsert(build_teams_df(), "team", keys=["team_id"])
