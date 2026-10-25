"""Colours, stat definitions and helpers shared by every page of the app."""
from datetime import date

import streamlit as st

import queries

# Colours from the reference data-viz palette: one hue for single-series charts, three
# distinct hues for the birthday phases, and a neutral grey for ordinary games.
SERIES = "#2a78d6"
NEUTRAL = "#a3a29b"
PHASES = {
    "before": ("Before (1-3 days)", "#2a78d6"),
    "on":     ("On birthday", "#eb6834"),
    "after":  ("After (1-3 days)", "#1baf7a"),
    "none":   ("Other games", NEUTRAL),
}
PHASE_ORDER = [label for label, _ in PHASES.values()]

# Stats offered in the charts: column -> (label, unit, multiplier for fractions)
STATS = {
    "pts":         ("Points", "points", 1),
    "reb":         ("Rebounds", "rebounds", 1),
    "ast":         ("Assists", "assists", 1),
    "minutes":     ("Minutes", "minutes", 1),
    "ts_pct":      ("True shooting %", "% points", 100),
    "usg_pct":     ("Usage rate", "% points", 100),
    "pct_fga":     ("Share of team shot attempts", "% points", 100),
    "pct_ast_fgm": ("% of made shots assisted", "% points", 100),
    "tov":         ("Turnovers", "turnovers", 1),
    "plus_minus":  ("Plus/minus", "points", 1),
    "fga":         ("Shot attempts", "shots", 1),
}


def next_birthday(birthdate: date, today: date) -> tuple:
    """(date of the next birthday, days until it, age he turns)."""
    def on_year(year):
        try:
            return birthdate.replace(year=year)
        except ValueError:          # 29 February in a non-leap year
            return date(year, 2, 28)
    upcoming = on_year(today.year)
    if upcoming < today:
        upcoming = on_year(today.year + 1)
    return upcoming, (upcoming - today).days, upcoming.year - birthdate.year


def birthday_on(birthdate: date, year: int) -> date:
    """His birthday in a given year (29 February birthdays fall on 28 February in other years)."""
    try:
        return birthdate.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def birthday_label(days: int) -> str:
    if days == 0:
        return "On birthday"
    return f"{abs(days)} day{'s' if abs(days) != 1 else ''} {'before' if days < 0 else 'after'}"


def require_data() -> None:
    """Stop the page with a clear message if there is no data source, else show which one is in use."""
    if queries.parquet_missing():
        st.error("SQL Server isn't available and there is no Parquet snapshot yet. Create one on a computer with "
                 f"SQL Server: `{queries.EXPORT_COMMAND}`")
        st.stop()
    st.sidebar.caption(f"Data: {queries.source_description()}")
