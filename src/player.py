import logging
import time
from datetime import date

import pandas as pd
from nba_api.stats.endpoints import CommonAllPlayers, CommonPlayerInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

REQUEST_DELAY_SECONDS = 0.6
OUTPUT_CSV_PATH = "active_players.csv"


def get_active_players() -> pd.DataFrame:
    all_players = CommonAllPlayers(is_only_current_season=1).get_data_frames()[0]
    active = all_players[all_players["ROSTERSTATUS"] == 1].copy()
    return active[["PERSON_ID", "DISPLAY_FIRST_LAST", "TEAM_ID", "TEAM_NAME", "TEAM_ABBREVIATION"]]


def calculate_age(birthdate: date) -> int:
    today = date.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def get_birthdates(player_ids: list) -> pd.DataFrame:
    records = []
    for player_id in player_ids:
        try:
            info = CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
            birthdate = pd.to_datetime(info.loc[0, "BIRTHDATE"]).date()
        except Exception as e:
            logger.error(f"Failed to fetch player info for player_id {player_id}: {e}")
            birthdate = None
        records.append({"PERSON_ID": player_id, "BIRTHDATE": birthdate})
        time.sleep(REQUEST_DELAY_SECONDS)
    return pd.DataFrame(records)


def build_active_players_df() -> pd.DataFrame:
    active = get_active_players()
    birthdates = get_birthdates(active["PERSON_ID"].tolist())
    df = active.merge(birthdates, on="PERSON_ID", how="left")
    df["AGE"] = df["BIRTHDATE"].apply(lambda b: calculate_age(b) if pd.notnull(b) else None)

    df = df.rename(columns={
        "PERSON_ID": "player_id",
        "DISPLAY_FIRST_LAST": "full_name",
        "AGE": "age",
        "BIRTHDATE": "birthdate",
        "TEAM_ID": "team_id",
        "TEAM_NAME": "team_name",
        "TEAM_ABBREVIATION": "team_abbreviation",
    })
    return df[["player_id", "full_name", "age", "birthdate", "team_id", "team_name", "team_abbreviation"]]


if __name__ == "__main__":
    df = build_active_players_df()
    df.to_csv(OUTPUT_CSV_PATH, index=False)
    logger.info(f"Wrote {len(df)} active players to {OUTPUT_CSV_PATH}")
