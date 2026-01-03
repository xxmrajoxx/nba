from nba_api.stats.endpoints import teamgamelogs
from nba_api.stats.static import teams
import pandas as pd
import logging
from pathlib import Path
from datetime import date
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

OUTPUT_DIR = Path("src/team_game_logs")

def fetch_nba_teams() -> pd.DataFrame:
    logging.info("Fetching NBA teams")

    nba_teams = teams.get_teams()

    team_df = (
        pd.DataFrame(nba_teams)[["id", "full_name", "abbreviation"]]
        .sort_values("full_name")
        .reset_index(drop=True)
    )

    # OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # team_df.to_csv(OUTPUT_DIR / "nba_teams.csv", index=False)
    return team_df

def fetch_team_game_logs(team_id: int, season: str, season_type: str = "Regular Season", league_id: str = "00",) -> pd.DataFrame:
    endpoint = teamgamelogs.TeamGameLogs(
        team_id_nullable=team_id,
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable=league_id,
    )

    return endpoint.get_data_frames()[0]

def fetch_all_teams_game_logs(season: str = "2025-26", season_type: str = "Regular Season") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    team_df = fetch_nba_teams()
    all_logs = []  # collect all team DataFrames

    for _, row in team_df.iterrows():
        team_id = int(row["id"])
        team_name = row["full_name"]
        team_abbr = row["abbreviation"]

        try:
            logging.info(f"Fetching {team_abbr} game logs")
            df = fetch_team_game_logs(team_id, season, season_type)

            # add team identifiers
            df["TEAM_ID"] = team_id
            df["TEAM_NAME"] = team_name
            df["TEAM_ABBREVIATION"] = team_abbr

            all_logs.append(df)

            time.sleep(1)

        except Exception:
            logging.exception(f"Failed for {team_name}")

    if not all_logs:
        logging.warning("No game logs collected")
        return

    final_df = pd.concat(all_logs, ignore_index=True)

    run_date = date.today().isoformat()  # YYYY-MM-DD
    output_file = OUTPUT_DIR / f"team_game_logs_{season}_{run_date}.csv"

    final_df.to_csv(output_file, index=False)
    logging.info(f"Saved combined game logs -> {output_file}")

if __name__ == "__main__":
    fetch_all_teams_game_logs(
        season="2025-26",
        season_type="Regular Season",
    )
