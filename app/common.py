"""Colours, stat definitions and helpers shared by every page of the app."""
from datetime import date

import pandas as pd
import streamlit as st

import queries

# The app uses a dark theme (.streamlit/config.toml). Colours are the reference data-viz
# palette's dark-mode steps, which are chosen and validated for dark surfaces: one hue for
# single-series charts, three distinct hues for the birthday phases, and a neutral grey for
# ordinary games and reference lines.
BACKGROUND = "#0a0a0a"
SERIES = "#3987e5"
NEUTRAL = "#8a8983"
PHASES = {
    "before": ("Before (1-3 days)", "#3987e5"),
    "on":     ("On birthday", "#d95926"),
    "after":  ("After (1-3 days)", "#199e70"),
    "none":   ("Other games", NEUTRAL),
}
PHASE_ORDER = [label for label, _ in PHASES.values()]
# The NBA dates every game by its US Eastern tip-off, so an evening game in the US is the
# next day in Australia. Dates and times shown to the user are converted to this time zone;
# the birthday analysis keeps the US date, the day the game was played where it was played.
LOCAL_TZ = "Australia/Sydney"
LOCAL_NAME = "Sydney"

# Row highlight for "this player plays on the chosen day": a tint of the birthday orange.
HIGHLIGHT = "rgba(217, 89, 38, 0.24)"

# Stats offered in the charts: column -> (label, unit, multiplier for fractions)
STATS = {
    "pts":         ("Points", "points", 1),
    "reb":         ("Rebounds", "rebounds", 1),
    "ast":         ("Assists", "assists", 1),
    "fg3m":        ("3-pointers made", "threes", 1),
    "fg3a":        ("3-point attempts", "attempts", 1),
    "fgm":         ("Field goals made", "shots", 1),
    "fga":         ("Shot attempts", "shots", 1),
    "minutes":     ("Minutes", "minutes", 1),
    "stl":         ("Steals", "steals", 1),
    "blk":         ("Blocks", "blocks", 1),
    "tov":         ("Turnovers", "turnovers", 1),
    "plus_minus":  ("Plus/minus", "points", 1),
    "ts_pct":      ("True shooting %", "% points", 100),
    "usg_pct":     ("Usage rate", "% points", 100),
    "pct_fga":     ("Share of team shot attempts", "% points", 100),
    "pct_ast_fgm": ("% of made shots assisted", "% points", 100),
}

PAGE_CSS = """
<style>
/* Tighter top of page */
.block-container { padding-top: 2.2rem; }
/* Metrics as cards */
[data-testid="stMetric"] {
    background: #141413;
    border: 1px solid #2e2e2c;
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] p {
    color: #c3c2b7;
    font-size: 0.78rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
/* Section headings with a quiet rule underneath */
h3 { border-bottom: 1px solid #2e2e2c; padding-bottom: 0.35rem; }
</style>
"""


def to_local(tipoff_et) -> pd.Series:
    """Tip-off times on the schedule's US Eastern clock, converted to LOCAL_TZ (as naive
    datetimes, ready for .dt.strftime). Daylight saving on both sides is handled; a missing
    tip-off stays missing."""
    eastern = pd.to_datetime(pd.Series(tipoff_et)).dt.tz_localize(
        "America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    return eastern.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)


def style_page() -> None:
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


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
