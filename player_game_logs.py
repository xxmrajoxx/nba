from nba_api.stats.endpoints import playergamelogs
import pandas as pd
import logging
import os
import time
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def safe_filename(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("'", "")
    )


def last_n_seasons(end_start_year: int, n: int) -> List[str]:
    # Example: end_start_year=2024, n=3 -> ["2024-25","2023-24","2022-23"]
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(end_start_year, end_start_year - n, -1)]


def fetch_game_logs(
    player_id: int,
    player_name: str,
    season: str,
    league_id: str = "00",
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """
    Fetch a single player's game logs for a single season.
    Returns DataFrame (possibly empty). Does NOT write CSV.
    """
    try:
        logging.info(f"Fetching game logs for {player_name} (id={player_id}), season={season}")

        endpoint = playergamelogs.PlayerGameLogs(
            player_id_nullable=player_id,
            season_nullable=season,
            league_id_nullable=league_id,
            season_type_nullable=season_type,
        )

        df = endpoint.player_game_logs.get_data_frame()

        if df.empty:
            logging.warning(f"No game logs returned for {player_name} season={season}")
            return df

        # Add helpful columns
        df["PLAYER_ID"] = player_id
        df["PLAYER_NAME"] = player_name
        df["SEASON"] = season

        logging.info(f"Fetched {len(df)} game logs for {player_name} season={season}")
        return df

    except Exception:
        logging.exception(f"Error fetching logs for {player_name} season={season}")
        return pd.DataFrame()


def fetch_logs_for_players_one_file_each(
    players: List[Dict[str, str]],
    seasons: List[str],
    sleep_seconds: float = 0.8,
    out_dir: str = "player_game_logs",
    league_id: str = "00",
    season_type: str = "Regular Season",
) -> None:
    """
    For each player:
      - fetch all seasons
      - save ONE CSV per player containing all seasons combined
    """
    os.makedirs(out_dir, exist_ok=True)

    for p in players:
        name = p["name"]
        player_id = int(p["person_id"])
        logging.info(f"=== START player: {name} ({player_id}) ===")

        per_player_dfs = []

        for season in seasons:
            df = fetch_game_logs(
                player_id=player_id,
                player_name=name,
                season=season,
                league_id=league_id,
                season_type=season_type,
            )

            if not df.empty:
                per_player_dfs.append(df)

            time.sleep(sleep_seconds)

        if not per_player_dfs:
            logging.warning(f"No data collected for player: {name}")
            logging.info(f"=== END player: {name} ({player_id}) ===")
            continue

        player_df = pd.concat(per_player_dfs, ignore_index=True)

        # Optional: sort if these columns exist (nba_api sometimes provides GAME_DATE)
        sort_cols = []
        if "SEASON" in player_df.columns:
            sort_cols.append("SEASON")
        if "GAME_DATE" in player_df.columns:
            sort_cols.append("GAME_DATE")
        if sort_cols:
            player_df = player_df.sort_values(sort_cols).reset_index(drop=True)

        out_path = os.path.join(
            out_dir,
            f"{safe_filename(name)}_gamelogs_{len(seasons)}_seasons.csv",
        )
        player_df.to_csv(out_path, index=False)
        logging.info(f"Saved {len(player_df)} rows -> {out_path}")

        logging.info(f"=== END player: {name} ({player_id}) ===")


if __name__ == "__main__":
    players = [
        {"name": "Karl-Anthony Towns", "person_id": "1626157"},
        {"name": "Domantas Sabonis", "person_id": "1627734"},
        {"name": "Rudy Gobert", "person_id": "203497"},
        {"name": "Ivica Zubac", "person_id": "1627826"},
        {"name": "Jalen Duren", "person_id": "1631105"},
        {"name": "Donovan Clingan", "person_id": "1642270"},
        {"name": "Isaiah Hartenstein", "person_id": "1628392"},
        {"name": "Jalen Johnson", "person_id": "1630552"},
        {"name": "Bam Adebayo", "person_id": "1628389"},
        {"name": "Alperen Sengun", "person_id": "1630578"},
        {"name": "Andre Drummond", "person_id": "203083"},
        {"name": "Josh Giddey", "person_id": "1630581"},
        {"name": "Evan Mobley", "person_id": "1630596"},
        {"name": "Deandre Ayton", "person_id": "1629028"},
        {"name": "Mitchell Robinson", "person_id": "1629011"},
        {"name": "Steven Adams", "person_id": "203500"},
        {"name": "Scottie Barnes", "person_id": "1630567"},
        {"name": "Alex Sarr", "person_id": "1642259"},
        {"name": "Mark Williams", "person_id": "1631109"},
        {"name": "Josh Hart", "person_id": "1628404"},
    ]

    seasons = last_n_seasons(end_start_year=2026, n=10)

    fetch_logs_for_players_one_file_each(
        players=players,
        seasons=seasons,
        sleep_seconds=0.8,
        out_dir="player_game_logs",
        league_id="00",
        season_type="Regular Season",
    )
