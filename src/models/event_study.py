"""Event study: how do players perform on each day around their birthday?

For every stat, estimates how far a player's performance on each day from 7 days before
to 7 days after his birthday differs from his own average for that season, adjusting for
week of season, home/away, back-to-backs, key teammates out and opponent strength. Games
more than 7 days from a birthday are the baseline (zero).

If teammates feed the birthday player, usage and shot share should spike at day 0.
If he partied and is tired, efficiency and minutes should dip at days +1 and +2.

Run every model at once with src/models/run_models.py, or just this one:

    .venv\\Scripts\\python.exe src\\models\\event_study.py
"""
import matplotlib

matplotlib.use("Agg")   # draw to files, not a window
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from data import OUTPUT_DIR, load_games  # noqa: E402
from fixed_effects import add_q_values, coefficient_rows, fit_within, player_season, week_dummies  # noqa: E402
from outcomes import OUTCOMES, available_outcomes, control_matrix  # noqa: E402

WINDOW = 7
PLOT_OUTCOMES = ["pts", "minutes", "usg_pct", "pct_fga", "ts_pct", "tov"]

# Reference palette (dataviz skill): one series, so one hue; text and grid stay neutral.
SERIES = "#2a78d6"
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BAND = "#f0efec"


def fit_event_study(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """One coefficient per day from -WINDOW to +WINDOW, with 95% confidence intervals."""
    label, unit, scale, hypothesis = OUTCOMES[outcome]
    data = df.dropna(subset=[outcome])

    days = range(-WINDOW, WINDOW + 1)
    day_columns = pd.DataFrame(
        {f"day_{d}": (data["days_from_birthday"] == d).astype(float) for d in days}, index=data.index)
    X = pd.concat([day_columns, control_matrix(data), week_dummies(data)], axis=1)

    model = fit_within(data[outcome] * scale, X, player_season(data), data["player_id"])
    rows = pd.DataFrame(coefficient_rows(model, list(day_columns.columns),
                                         outcome=outcome, label=label, unit=unit, hypothesis=hypothesis))
    rows["day"] = rows.pop("term").str.replace("day_", "").astype(int)
    rows["games"] = rows["day"].map(lambda d: int(day_columns[f"day_{d}"].sum()))
    return rows


def run(df: pd.DataFrame) -> pd.DataFrame:
    results = pd.concat([fit_event_study(df, o) for o in available_outcomes(df)], ignore_index=True)
    return add_q_values(results)


def plot(results: pd.DataFrame, path) -> None:
    outcomes = [o for o in PLOT_OUTCOMES if o in set(results["outcome"])]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), facecolor=SURFACE)
    for ax, outcome in zip(axes.flat, outcomes):
        r = results[results["outcome"] == outcome]
        title, unit = r["label"].iloc[0], r["unit"].iloc[0]
        ax.set_facecolor(SURFACE)
        ax.axvspan(-3.5, 3.5, color=BAND, zorder=0)           # the birthday week
        ax.axhline(0, color=TEXT_SECONDARY, linewidth=1, zorder=1)
        ax.vlines(r["day"], r["ci_low"], r["ci_high"], color=SERIES, linewidth=2, alpha=0.45, zorder=2)
        ax.plot(r["day"], r["estimate"], "o", color=SERIES, markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)

        ax.set_title(title, loc="left", fontsize=12, color=TEXT_PRIMARY, fontweight="bold")
        ax.set_ylabel(f"vs season average ({unit})", fontsize=9, color=TEXT_SECONDARY)
        ax.set_xticks(range(-WINDOW, WINDOW + 1, 1))
        ax.set_xticklabels([str(d) if d else "B'day" for d in range(-WINDOW, WINDOW + 1)], fontsize=8)
        ax.tick_params(colors=TEXT_SECONDARY, length=0)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)

    for ax in axes[1]:
        ax.set_xlabel("Days from birthday", fontsize=9, color=TEXT_SECONDARY)
    fig.suptitle("How players perform around their birthday", x=0.01, ha="left",
                 fontsize=15, fontweight="bold", color=TEXT_PRIMARY)
    fig.text(0.01, 0.935,
             "Difference from the same player's average that season, adjusted for week of season, home/away, "
             "back-to-backs, teammates out and opponent strength. Dots: estimate. Lines: 95% confidence interval. "
             "Shaded: birthday week (±3 days).",
             fontsize=9.5, color=TEXT_SECONDARY)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    df = load_games()
    results = run(df)
    OUTPUT_DIR.mkdir(exist_ok=True)
    results.to_csv(OUTPUT_DIR / "event_study.csv", index=False)
    plot(results, OUTPUT_DIR / "event_study.png")
    key = results[results["day"].isin([0, 1, 2])]
    print(key[["outcome", "day", "games", "estimate", "ci_low", "ci_high", "q_value"]].round(3).to_string(index=False))
    print(f"\nSaved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
