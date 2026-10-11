"""Do players perform differently in their birthday week?

Each observation is one player-season: the player's birthday-week average minus their
average over the rest of that same season. If birthdays make no difference, those
differences should centre on zero.

    python src/analysis.py
"""
import numpy as np
import pandas as pd

import db

METRICS = ["pts", "reb", "ast", "minutes", "ts_pct", "plus_minus"]
BOOTSTRAP_SAMPLES = 10_000


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator) -> tuple:
    """95% confidence interval for the mean, by resampling the observations with replacement."""
    samples = rng.choice(values, size=(BOOTSTRAP_SAMPLES, len(values)), replace=True)
    return tuple(np.percentile(samples.mean(axis=1), [2.5, 97.5]))


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = []
    for metric in METRICS:
        diff = (df[f"birthday_week_{metric}"] - df[f"other_{metric}"]).dropna().to_numpy()
        low, high = bootstrap_ci(diff, rng)
        rows.append({
            "metric": metric,
            "player_seasons": len(diff),
            "birthday_week_avg": df[f"birthday_week_{metric}"].mean(),
            "rest_of_season_avg": df[f"other_{metric}"].mean(),
            "mean_diff": diff.mean(),
            "ci_low": low,
            "ci_high": high,
            # If the interval contains 0, the data is consistent with no birthday effect.
            "significant": not (low <= 0 <= high),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = db.read_sql("SELECT * FROM dbo.v_birthday_week_vs_season")
    print(f"{len(df)} player-seasons from {df['player_id'].nunique()} players, "
          f"{int(df['birthday_week_games'].sum())} birthday-week games\n")
    print(summarise(df).round(3).to_string(index=False))

    by_player = (
        df.assign(pts_diff=df["birthday_week_pts"] - df["other_pts"])
        .groupby("full_name")
        .agg(seasons=("season", "count"), birthday_week_games=("birthday_week_games", "sum"), pts_diff=("pts_diff", "mean"))
        .query("birthday_week_games >= 10")
        .sort_values("pts_diff", ascending=False)
    )
    print("\nBiggest birthday-week scoring boosts (10+ birthday-week games):")
    print(by_player.head(10).round(2).to_string())
    print("\nBiggest birthday-week scoring drops:")
    print(by_player.tail(10).round(2).to_string())
