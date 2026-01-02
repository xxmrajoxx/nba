from nba_api.stats.endpoints import PlayerCareerStats
from nba_api.stats.static import players
import pandas as pd

PLAYER_NAMES = [
    "Nikola Jokic",
    "Luka Doncic",
    "Jayson Tatum"
]

def get_player_id(player_name):
    nba_players = players.find_players_by_full_name(player_name)
    if not nba_players:
        raise ValueError(f"Player not found: {player_name}")
    return nba_players[0]["id"]

def fetch_player_stats(player_name):
    player_id = get_player_id(player_name)
    career = PlayerCareerStats(player_id=player_id)
    df = career.get_data_frames()[0]
    df["player_name"] = player_name
    return df

def main():
    all_players_df = []

    for name in PLAYER_NAMES:
        print(f"Fetching stats for {name}")
        df = fetch_player_stats(name)
        all_players_df.append(df)

    final_df = pd.concat(all_players_df, ignore_index=True)
    final_df.to_csv("nba_player_stats.csv", index=False)
    print("Saved nba_player_stats.csv")

if __name__ == "__main__":
    main()
