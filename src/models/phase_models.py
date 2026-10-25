"""Models that pool the birthday into three phases: before (1-3 days), on the day, after (1-3 days).

Pooling gives each phase several hundred games instead of one day's ~270, so the
intervals are narrower than the day-by-day event study, and there are far fewer
estimates to be fooled by.

    phase_effects   every stat, before / on / after, adjusted for controls
    phase_by_age    the same, split by the age the player turns (under 25 / 25-29 / 30+)
    availability    does the chance of playing at all change around a birthday?
    player_effects  each player's own birthday-week effect, adjusted for small samples
"""
import numpy as np
import pandas as pd

from fixed_effects import add_q_values, coefficient_rows, demean, fit_within, player_season, week_dummies
from outcomes import OUTCOMES, available_outcomes, control_matrix

PHASES = ["before", "on", "after"]
AGE_GROUPS = ["Under 25", "25-29", "30+"]
PLAYER_OUTCOMES = ["pts", "minutes", "usg_pct", "pct_fga", "ts_pct", "reb", "ast"]
NEARBY_DAYS = 30


def phase_columns(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({p: (df["birthday_phase"] == p).astype(float) for p in PHASES}, index=df.index)


def phase_effects(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in available_outcomes(df):
        label, unit, scale, hypothesis = OUTCOMES[outcome]
        data = df.dropna(subset=[outcome])
        phases = phase_columns(data)
        X = pd.concat([phases, control_matrix(data), week_dummies(data)], axis=1)
        model = fit_within(data[outcome] * scale, X, player_season(data), data["player_id"])
        for row in coefficient_rows(model, PHASES, outcome=outcome, label=label, unit=unit, hypothesis=hypothesis):
            row["phase"] = row.pop("term")
            row["games"] = int(phases[row["phase"]].sum())
            rows.append(row)
    return add_q_values(pd.DataFrame(rows))


def age_turning(df: pd.DataFrame) -> pd.Series:
    """The age reached at the nearest birthday: before it, he is still one year younger."""
    return df["age_at_game"] + (df["days_from_birthday"] < 0).astype(int)


def age_group(age: pd.Series) -> pd.Series:
    return pd.cut(age, bins=[0, 24, 29, 100], labels=AGE_GROUPS).astype(str)


def phase_by_age(df: pd.DataFrame, outcomes: list = None) -> pd.DataFrame:
    """One phase effect per age group: phase x age-group interaction terms."""
    groups = age_group(age_turning(df))
    rows = []
    for outcome in outcomes or available_outcomes(df):
        label, unit, scale, hypothesis = OUTCOMES[outcome]
        keep = df[outcome].notna()
        data, data_groups = df[keep], groups[keep]
        terms = pd.DataFrame({
            f"{p}|{g}": ((data["birthday_phase"] == p) & (data_groups == g)).astype(float)
            for p in PHASES for g in AGE_GROUPS
        }, index=data.index)
        X = pd.concat([terms, control_matrix(data), week_dummies(data)], axis=1)
        model = fit_within(data[outcome] * scale, X, player_season(data), data["player_id"])
        for row in coefficient_rows(model, list(terms.columns), outcome=outcome, label=label, unit=unit):
            row["phase"], row["age_group"] = row.pop("term").split("|")
            row["games"] = int(terms[f"{row['phase']}|{row['age_group']}"].sum())
            rows.append(row)
    return add_q_values(pd.DataFrame(rows))


def availability(av: pd.DataFrame) -> pd.DataFrame:
    """Linear probability model: played (0/1) on phase, with player-season fixed effects.
    Estimates are in percentage points of the chance of playing."""
    phases = phase_columns(av)
    X = pd.concat([phases, week_dummies(av)], axis=1)
    model = fit_within(av["played"] * 100.0, X, player_season(av), av["player_id"])
    rows = pd.DataFrame(coefficient_rows(model, PHASES, outcome="played", label="Chance of playing", unit="% points"))
    rows["phase"] = rows.pop("term")
    rows["games"] = rows["phase"].map(lambda p: int(phases[p].sum()))
    rows["missed"] = rows["phase"].map(lambda p: int(((av["birthday_phase"] == p) & (av["played"] == 0)).sum()))
    rows["normal_play_rate"] = av.loc[av["birthday_phase"] == "none", "played"].mean() * 100
    return add_q_values(rows)


def player_effects(df: pd.DataFrame) -> pd.DataFrame:
    """Each player's own birthday-week effect, adjusted for small samples ("shrinkage").

    A player has only 2-4 birthday-week games a season, so his raw birthday-week average is
    mostly luck. This is a simple hierarchical (empirical Bayes) model:

      raw       = his average in birthday-week games, relative to his games in the month
                  around his birthday (within 30 days) that same season
      league    = the same for every player pooled together
      tau2      = how much players' true birthday effects really differ from each other,
                  estimated from how much more the raw values vary than luck alone explains
      weight    = tau2 / (tau2 + noise / games): near 1 with lots of games and real
                  differences between players, near 0 otherwise
      adjusted  = league + weight * (raw - league)

    If tau2 comes out as zero, the data shows no sign that players differ, and every
    player's adjusted effect equals the league's.
    """
    outcomes = [o for o in PLAYER_OUTCOMES if o in available_outcomes(df)]
    # Compare the birthday week with the surrounding month, not the whole season. A birthday
    # falls at the same point every season, so a whole-season baseline would mistake role
    # changes (a rookie's minutes growing through the year) for a birthday effect.
    df = df[df["days_from_birthday"].abs() <= NEARBY_DAYS]
    rows = []
    groups = player_season(df)
    week = df["days_from_birthday"].abs() <= 3
    for outcome in outcomes:
        label, unit, scale, _ = OUTCOMES[outcome]
        keep = df[outcome].notna()
        value = demean(df.loc[keep, outcome] * scale, groups[keep])
        in_week = week[keep]

        player_ids = df.loc[keep, "player_id"]
        league = value[in_week].mean()
        per_player = value[in_week].groupby(player_ids[in_week]).agg(["mean", "count"])
        # Each player's own game-to-game variation: a bench player's minutes swing far more
        # than a star's, so one league-wide figure would overstate how much players differ.
        noise = value[~in_week].groupby(player_ids[~in_week]).var().reindex(per_player.index)
        noise = noise.fillna(value[~in_week].var())
        sampling = noise / per_player["count"]
        tau2 = max(0.0, (per_player["mean"] - league).var() - sampling.mean())

        weight = tau2 / (tau2 + sampling)
        adjusted = league + weight * (per_player["mean"] - league)
        adjusted_sd = np.sqrt(weight * sampling)          # zero when fully shrunk to the league value
        raw_sd = np.sqrt(sampling)

        rows.append(pd.DataFrame({
            "player_id": per_player.index,
            "outcome": outcome, "label": label, "unit": unit,
            "games": per_player["count"].values,
            "raw": per_player["mean"].values,
            "raw_low": (per_player["mean"] - 1.96 * raw_sd).values,
            "raw_high": (per_player["mean"] + 1.96 * raw_sd).values,
            "adjusted": adjusted.values,
            "adjusted_low": (adjusted - 1.96 * adjusted_sd).values,
            "adjusted_high": (adjusted + 1.96 * adjusted_sd).values,
            "league": league,
            "weight": weight.values,
            "between_player_sd": np.sqrt(tau2),
        }))
    return pd.concat(rows, ignore_index=True)
