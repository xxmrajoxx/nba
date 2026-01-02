from nba_api.stats.endpoints import CommonAllPlayers
import pandas as pd
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def fetch_players(
    league_id: str,
    season: str,
    is_only_current_season: bool = True,
    output_csv: str = "active_nba_players.csv",
) -> pd.DataFrame:
    try:
        season_flag = 1 if is_only_current_season else 0
        logging.info(
            f"Fetching players for league_id={league_id}, season={season}, is_only_current_season={is_only_current_season}"
        )

        endpoint = CommonAllPlayers(
            league_id=league_id,
            season=season,
            is_only_current_season=season_flag,
        )

        players_df = endpoint.common_all_players.get_data_frame()
        logging.info(f"Fetched {len(players_df)} players from the API.")

        if players_df.empty:
            logging.warning("No players data retrieved from the API.")
            return players_df

        players_df.to_csv(output_csv, index=False)
        logging.info(f"Saved {len(players_df)} players to {output_csv}")
        print(f"Saved {len(players_df)} players to {output_csv}")
        return players_df

    except Exception:
        logging.exception("An error occurred while fetching players data.")
        return pd.DataFrame()


def build_players_lookup_from_csv(csv_file: str) -> dict[str, int]:
    try:
        df = pd.read_csv(csv_file)

        required_cols = {"DISPLAY_FIRST_LAST", "PERSON_ID", "TEAM_ID"}
        missing = required_cols - set(df.columns)
        if missing:
            raise KeyError(f"CSV is missing columns: {missing}")

        # normalize names for matching
        names = (
            df["DISPLAY_FIRST_LAST"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        lookup = dict(zip(names, df["PERSON_ID"]))
        logging.info(f"Built players lookup dictionary from {csv_file} with {len(lookup)} entries.")
        return lookup

    except Exception:
        logging.exception("An error occurred while building players lookup from CSV.")
        return {}


def find_player_ids(players: list[str], lookup: dict[str, int]) -> pd.DataFrame:
    results = []

    for name in players:
        key = str(name).strip().lower()
        person_id = lookup.get(key)

        if person_id is None:
            logging.error(f"Player '{name}' not found in lookup dictionary.")
        else:
            logging.info(f"Found Player ID for '{name}': {person_id}")
            results.append({"name": name, "person_id": int(person_id)})

    return pd.DataFrame(results)


if __name__ == "__main__":
    target_players = [
        "Nikola Jokic",
        "Karl-Anthony Towns",
        "Domantas Sabonis",
        "Rudy Gobert",
        "Ivica Zubac",
        "Jalen Duren",
        "Donovan Clingan",
        "Isaiah Hartenstein",
        "Jalen Johnson",
        "Jusuf Nurkic",
        "Bam Adebayo",
        "Alperen Sengun",
        "Andre Drummond",
        "Josh Giddey",
        "Evan Mobley",
        "Nikola Vucevic",
        "Deandre Ayton",
        "Mitchell Robinson",
        "Steven Adams",
        "Scottie Barnes",
        "Alex Sarr",
        "Luka Doncic",
        "Mark Williams",
        "Josh Hart",
    ]

    csv_path = "active_nba_players_2025_26.csv"

    # 1) fetch + save
    players_df = fetch_players(
        league_id="00",
        season="2025-26",
        is_only_current_season=True,
        output_csv=csv_path,
    )

    if players_df.empty:
        raise SystemExit("Stopping: players_df is empty (API returned no data).")

    # 2) build lookup (THIS was missing in your code)
    lookup = build_players_lookup_from_csv(csv_path)

    if not lookup:
        raise SystemExit("Stopping: lookup dictionary is empty (CSV read/format issue).")

    # 3) match target players -> ids
    results_df = find_player_ids(target_players, lookup)

    results_df.to_csv("player_ids_lookup.csv", index=False)
    logging.info("Saved player_ids_lookup.csv")
    print(results_df)
