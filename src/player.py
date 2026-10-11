import logging

import pandas as pd
from nba_api.stats.endpoints import CommonAllPlayers, CommonPlayerInfo
from sqlalchemy import bindparam, text

import db
from nba_client import fetch

logger = logging.getLogger(__name__)

DETAILS_BATCH_SIZE = 50


def get_active_players() -> pd.DataFrame:
    all_players = fetch(CommonAllPlayers, is_only_current_season=1).get_data_frames()[0]
    active = all_players[all_players["ROSTERSTATUS"] == 1]
    df = active[["PERSON_ID", "DISPLAY_FIRST_LAST", "TEAM_ID", "FROM_YEAR", "TO_YEAR"]].rename(columns={
        "PERSON_ID": "player_id",
        "DISPLAY_FIRST_LAST": "full_name",
        "TEAM_ID": "team_id",
        "FROM_YEAR": "from_year",
        "TO_YEAR": "to_year",
    })
    # Free agents come back with team_id 0, which is not a real team.
    df["team_id"] = df["team_id"].astype("Int64").mask(df["team_id"] == 0)
    df["from_year"] = pd.to_numeric(df["from_year"], errors="coerce").astype("Int64")
    df["to_year"] = pd.to_numeric(df["to_year"], errors="coerce").astype("Int64")
    df["is_active"] = True
    return df.reset_index(drop=True)


def get_player_details(player_ids: list) -> pd.DataFrame:
    records = []
    for player_id in player_ids:
        try:
            info = fetch(CommonPlayerInfo, player_id=player_id).get_data_frames()[0].iloc[0]
        except Exception as e:
            # Leave the birthdate NULL; the next run will pick this player up again.
            logger.error(f"Failed to fetch player info for player_id {player_id}: {e}")
            continue
        birthdate = pd.to_datetime(info["BIRTHDATE"], errors="coerce")
        records.append({
            "player_id": player_id,
            "birthdate": birthdate.date() if pd.notnull(birthdate) else None,
            "position": info["POSITION"] or None,
            "height": info["HEIGHT"] or None,
            "weight_lbs": pd.to_numeric(info["WEIGHT"], errors="coerce"),
            "country": info["COUNTRY"] or None,
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df["weight_lbs"] = df["weight_lbs"].astype("Int64")
    return df


def run() -> int:
    active = get_active_players()
    rows = db.upsert(active, "player", keys=["player_id"])

    # Anyone no longer on the active list (retired, waived out of the league) is kept but flagged.
    with db.get_engine().begin() as conn:
        conn.execute(
            text("UPDATE dbo.player SET is_active = 0 WHERE is_active = 1 AND player_id NOT IN :ids")
            .bindparams(bindparam("ids", expanding=True)),
            {"ids": active["player_id"].tolist()},
        )

    # Birthdates need one API call per player and never change, so only fetch the ones we lack.
    # Batches are saved as they complete, so an interrupted run resumes where it stopped.
    missing = db.read_sql("SELECT player_id FROM dbo.player WHERE birthdate IS NULL AND is_active = 1")
    missing_ids = missing["player_id"].tolist()
    logger.info(f"Fetching details for {len(missing_ids)} players without a birthdate")
    for start in range(0, len(missing_ids), DETAILS_BATCH_SIZE):
        details = get_player_details(missing_ids[start:start + DETAILS_BATCH_SIZE])
        db.upsert(details, "player", keys=["player_id"])

    return rows
