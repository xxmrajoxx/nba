from datetime import date

import db


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def current_season() -> str:
    today = date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return season_label(start_year)


def seasons_since(start_year: int) -> list:
    current_start = int(current_season().split("-")[0])
    return [season_label(y) for y in range(start_year, current_start + 1)]


def select_seasons(season: str = None, last: int = None, backfill: bool = False, loaded: bool = False) -> list:
    """Turn the command line options into a list of seasons. With no option: the current season."""
    if loaded:
        # Whatever seasons already have game logs, so the other per-season tables can be lined up with them.
        return db.read_sql("SELECT DISTINCT season FROM dbo.player_game_log ORDER BY season")["season"].tolist()
    if backfill:
        # Every season since the longest-tenured player in dbo.player entered the league.
        first_year = db.read_sql("SELECT MIN(from_year) AS first_year FROM dbo.player")["first_year"].iloc[0]
        return seasons_since(int(first_year))
    if last:
        return seasons_since(int(current_season().split("-")[0]) - last + 1)
    return [season or current_season()]
