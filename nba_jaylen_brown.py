import time
import json
from datetime import datetime

import pandas as pd
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import players


def current_nba_season() -> str:
    """
    NBA season format used by nba_api is like '2024-25'.
    Season starts around Oct. If month >= 10, season starts this year; else previous year.
    """
    now = datetime.utcnow()
    start_year = now.year if now.month >= 10 else now.year - 1
    end_year_short = (start_year + 1) % 100
    return f"{start_year}-{end_year_short:02d}"


def find_player_id(full_name: str) -> int:
    matches = players.find_players_by_full_name(full_name)
    if not matches:
        raise ValueError(f"Player not found: {full_name}")
    # If multiple, take the first exact-ish match
    return matches[0]["id"]


def main():
    player_name = "Jaylen Brown"
    season = current_nba_season()

    player_id = find_player_id(player_name)

    # Be polite to the endpoint; helps avoid rate-limits
    time.sleep(1)

    # Career stats includes season-by-season rows; we’ll filter to current season
    career = playercareerstats.PlayerCareerStats(player_id=player_id)
    df = career.get_data_frames()[0]  # season totals regular season

    # Filter to the season we want
    season_df = df[df["SEASON_ID"].str.contains(season.replace("-", ""))]

    # If format differs, fallback to a different filter
    if season_df.empty:
        season_df = df[df["SEASON_ID"].str.endswith(season.split("-")[1])]

    # Save both raw and simplified outputs
    out_dir = "output"
    pd.options.mode.chained_assignment = None
    season_df.to_csv(f"{out_dir}/jaylen_brown_{season}_season_totals.csv", index=False)

    payload = {
        "player": player_name,
        "player_id": player_id,
        "season": season,
        "rows": season_df.to_dict(orient="records"),
    }
    with open(f"{out_dir}/jaylen_brown_{season}_season_totals.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved Jaylen Brown season totals for {season} to {out_dir}/")


if __name__ == "__main__":
    import os

    os.makedirs("output", exist_ok=True)
    main()
