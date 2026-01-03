from nba_api.stats.endpoints import playergamelogs
from nba_api.stats.static import players
import pandas as pd
import logging 
import time
from typing import Optional, List, Dict
from pathlib import Path
from datetime import date, UTC, datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PLAYER_NAMES: List[str] = [
    "Karl-Anthony Towns",
    "Domantas Sabonis",
    "Rudy Gobert",
    "Ivica Zubac",
    "Jalen Duren",
    "Donovan Clingan",
    "Isaiah Hartenstein",
    "Jalen Johnson",
    "Bam Adebayo",
    "Alperen Sengun",
    "Andre Drummond",
    "Josh Giddey",
    "Evan Mobley",
    "Deandre Ayton",
    "Mitchell Robinson",
    "Steven Adams",
    "Scottie Barnes",
    "Alex Sarr",
    "Mark Williams",
    "Josh Hart"
]

def get_player_id(player_name: str) -> int:
    try:
        logging.info(f"obtaining player id for {player_name}")
        matches = players.find_players_by_full_name(player_name)

        if not matches:
            logging.warning(f"Player not found: {player_name}")
            return None
        
        exact = [p for p in matches if p.get("full_name", "").lower() == player_name.lower()]
        chosen = exact[0] if exact else matches[0]

        return int(chosen["id"])

    except Exception:
        logging.exception(f"Error while looking up player_id for: {player_name}")
        return None
 

def fetch_player_game_logs(player_name: str, season: str, league_id: str="00", season_type: str="Regular Season") -> pd.DataFrame:
    try:
        player_id = get_player_id(player_name)
        if player_id is None:
            return pd.DataFrame()

        logging.info(f"extracting game logs for {player_name} for {season}")

        endpoint = playergamelogs.PlayerGameLogs(
            player_id_nullable=player_id,
            season_nullable=season,
            league_id_nullable=league_id,
            season_type_nullable=season_type
        )

        df = endpoint.player_game_logs.get_data_frame()
        
        if df.empty:
            logging.warning(f"no game logs for {player_name} for {season}")
            return pd.DataFrame()
        
        # Important - Metadata enrichment - unlocks partitioning in S3, Filtering in Bedrock
        df["player_name"] = player_name
        df["season"] = season
        df["player_id"] = player_id
        df["season_type"] = season_type
        
        logging.info(f"sucessfully extracted game log for {player_name} for {season}")
        return df

    except Exception:
        logging.exception(f"error extracting game logs for {player_name} for {season}")
        return pd.DataFrame()
    
def main():
    SEASON = "2025-26"
    all_dfs: List[pd.DataFrame] = []

    logging.info(f"commencing nba player game log extraction")

    for name in PLAYER_NAMES:
        df = fetch_player_game_logs(player_name=name, season=SEASON)
        if not df.empty:
            all_dfs.append(df)

            time.sleep(1)

    if not all_dfs:
        logging.error(f"no game logs collected for any player")
        return
    
    final_df = pd.concat(all_dfs, ignore_index=True)

    BASE_DIR = Path(__file__).resolve().parents[1]  # project root (nba/)
    OUTPUT_DIR = BASE_DIR / "src/player_game_logs"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_season = SEASON.replace("/", "-")
    extract_date = datetime.now(UTC).strftime("%Y%m%d")

    output_path = OUTPUT_DIR / f"nba_player_game_logs_{safe_season}_{extract_date}.csv"
    final_df.to_csv(output_path, index=False)

    logging.info(f"Saved file to {output_path}")

if __name__ =="__main__":
    main()

