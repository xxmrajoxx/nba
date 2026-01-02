from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.static import teams
import pandas as pd
import os
import logging

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


def get_current_nba_teams() -> pd.DataFrame:
    """
    Returns current NBA teams with team_id + full_name + abbreviation.
    """
    teams_list = teams.get_teams()
    df = pd.DataFrame(teams_list)

    if "is_nba" in df.columns:
        df = df[df["is_nba"] == True].copy()

    cols = [c for c in ["id", "full_name", "abbreviation"] if c in df.columns]
    df = df[cols].rename(columns={"id": "TEAM_ID", "full_name": "TEAM_NAME"})
    return df.sort_values("TEAM_NAME").reset_index(drop=True)


def fetch_league_team_game_logs(season: str, season_type: str = "Regular Season") -> pd.DataFrame:
    """
    Fetches TEAM game logs for the whole league in ONE request, then returns a DataFrame.
    Uses LeagueGameLog with PlayerOrTeam='T'.
    """
    logging.info(f"Fetching LEAGUE team game logs for season={season}, type={season_type}")

    endpoint = leaguegamelog.LeagueGameLog(
        season=season,
        season_type_all_star=season_type,
        league_id="00",
        player_or_team_abbreviation="T",  # 'T' = team logs
    )

    df = endpoint.league_game_log.get_data_frame()

    if df.empty:
        logging.warning("LeagueGameLog returned an empty DataFrame.")
    else:
        logging.info(f"Fetched {len(df)} rows from LeagueGameLog.")

    return df


def fetch_all_teams_game_logs(
    season: str,
    season_type: str = "Regular Season",
    out_dir: str = "team_game_logs",
    save_one_file_per_team: bool = True,
) -> None:
    os.makedirs(out_dir, exist_ok=True)

    teams_df = get_current_nba_teams()
    teams_csv = os.path.join(out_dir, f"teams_{season.replace('-', '_')}.csv")
    teams_df.to_csv(teams_csv, index=False)
    logging.info(f"Saved teams list -> {teams_csv}")

    logs_df = fetch_league_team_game_logs(season=season, season_type=season_type)
    if logs_df.empty:
        logging.warning("No data collected (LeagueGameLog empty).")
        return

    # Ensure TEAM_ID is numeric for merge/filter
    if "TEAM_ID" in logs_df.columns:
        logs_df["TEAM_ID"] = pd.to_numeric(logs_df["TEAM_ID"], errors="coerce")

    # Add team names
    merged = logs_df.merge(teams_df, on="TEAM_ID", how="left")
    merged["SEASON"] = season
    merged["SEASON_TYPE"] = season_type

    # Save combined file for all teams
    combined_file = os.path.join(
        out_dir,
        f"all_teams_gamelogs_{season.replace('-', '_')}_{safe_filename(season_type)}.csv",
    )
    merged.to_csv(combined_file, index=False)
    logging.info(f"Saved combined file -> {combined_file}")

    # Save one CSV per team (optional)
    if save_one_file_per_team and "TEAM_ID" in merged.columns:
        for team_id, team_df in merged.groupby("TEAM_ID"):
            team_name = team_df["TEAM_NAME"].iloc[0] if "TEAM_NAME" in team_df.columns else str(team_id)
            team_file = os.path.join(
                out_dir,
                f"{safe_filename(str(team_name))}_{season.replace('-', '_')}_{safe_filename(season_type)}.csv",
            )
            team_df.to_csv(team_file, index=False)
            logging.info(f"Saved team file -> {team_file}")


if __name__ == "__main__":
    fetch_all_teams_game_logs(
        season="2019-20",
        season_type="Regular Season",
        out_dir="team_game_logs",
        save_one_file_per_team=True,
    )
