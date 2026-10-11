from datetime import date


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def current_season() -> str:
    today = date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return season_label(start_year)


def seasons_since(start_year: int) -> list:
    current_start = int(current_season().split("-")[0])
    return [season_label(y) for y in range(start_year, current_start + 1)]
