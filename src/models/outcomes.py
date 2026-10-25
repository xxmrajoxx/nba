"""The stats the models test, and the control variables they adjust for."""
import pandas as pd

# column -> (label, unit, multiplier, which explanation it tests)
# Fractions such as 0.25 are multiplied by 100 so results read in percentage points.
OUTCOMES = {
    "pts":             ("Points", "points", 1, "Overall"),
    "reb":             ("Rebounds", "rebounds", 1, "Overall"),
    "ast":             ("Assists", "assists", 1, "Overall"),
    "usg_pct":         ("Usage rate", "% points", 100, "Teammates feed him"),
    "pct_fga":         ("Share of team shot attempts", "% points", 100, "Teammates feed him"),
    "pct_ast_fgm":     ("% of made shots assisted", "% points", 100, "Teammates feed him"),
    "passes_received": ("Passes received", "passes", 1, "Teammates feed him"),
    "touches":         ("Touches", "touches", 1, "Teammates feed him"),
    "ts_pct":          ("True shooting %", "% points", 100, "Partied and tired"),
    "minutes":         ("Minutes", "minutes", 1, "Partied and tired"),
    "tov":             ("Turnovers", "turnovers", 1, "Partied and tired"),
    "dist_miles":      ("Miles run", "miles", 1, "Partied and tired"),
    "avg_speed":       ("Average speed", "mph", 1, "Partied and tired"),
    "deflections":     ("Deflections", "deflections", 1, "Partied and tired"),
    "contested_shots": ("Contested shots", "shots", 1, "Partied and tired"),
}

# A stat is only modelled once enough games have it. Tracking stats join automatically
# after the tracking job has loaded them.
MIN_GAMES = 5000

# Things known before tip-off that affect performance whatever the date.
CONTROLS = ["is_home", "back_to_back", "key_teammates_out", "top_scorer_out", "opponent_def_rating_to_date"]


def available_outcomes(df: pd.DataFrame) -> list:
    return [c for c in OUTCOMES if c in df.columns and df[c].notna().sum() >= MIN_GAMES]


def control_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Controls as numbers, with gaps filled so no game is dropped.

    back_to_back and the opponent rating are empty for a player's or team's first game of
    the season; those get "not a back-to-back" and the league-average rating.
    """
    X = pd.DataFrame(index=df.index)
    X["is_home"] = df["is_home"].astype(float)
    X["back_to_back"] = df["back_to_back"].fillna(False).astype(float)
    X["key_teammates_out"] = df["key_teammates_out"].fillna(0).astype(float)
    X["top_scorer_out"] = df["top_scorer_out"].fillna(False).astype(float)
    rating = df["opponent_def_rating_to_date"]
    X["opponent_def_rating_to_date"] = rating.fillna(rating.mean())
    return X
