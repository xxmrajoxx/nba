from nba_api.stats.endpoints import playergamelogs
from nba_api.stats.static import players
import pandas as pd
import logging 
import time
from typing import Optional, List, Dict
import os

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
        nba_players = players.find_players_by_full_name(player_name)

        if not nba_players:
            logging.warning(f"Player not found: {player_name}")
        return None

        return int(nba_players[0]["id"])
    
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
    all_dfs = []

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
    output_file = f"nba_player_game_logs{SEASON}.csv"
    final_df.to_csv(output_file, index=False)

    logging.info(f"saved file")

if __name__ =="__main__":
    main

