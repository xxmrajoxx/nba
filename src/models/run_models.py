"""Run every model and save the results the Birthday Explorer app reads.

    .venv\\Scripts\\python.exe src\\models\\run_models.py

Writes to outputs/:
    event_study.csv / .png   performance on each day from -7 to +7
    phase_effects.csv        before / on / after, every stat
    phase_by_age.csv         before / on / after, by the age the player turns
    availability.csv         change in the chance of playing at all
    player_effects.csv       each player's own birthday-week effect, adjusted for small samples
    model_info.json          when the models ran and on what data
"""
import json
import time
from datetime import datetime

import event_study
import phase_models
from data import OUTPUT_DIR, load_availability, load_games
from outcomes import CONTROLS, OUTCOMES, available_outcomes


def main() -> None:
    started = time.time()
    print("Loading games from SQL Server...")
    df = load_games()
    outcomes = available_outcomes(df)
    print(f"  {len(df):,} games, {df['player_id'].nunique()} players, {df['season'].min()} to {df['season'].max()}")
    skipped = [o for o in OUTCOMES if o not in outcomes]
    print(f"  modelling {len(outcomes)} stats" + (f"; skipped (not enough data yet): {', '.join(skipped)}" if skipped else ""))

    OUTPUT_DIR.mkdir(exist_ok=True)
    steps = [
        ("event study (day by day)", lambda: event_study.run(df), "event_study.csv"),
        ("before / on / after", lambda: phase_models.phase_effects(df), "phase_effects.csv"),
        ("by age group", lambda: phase_models.phase_by_age(df), "phase_by_age.csv"),
        ("chance of playing", lambda: phase_models.availability(load_availability()), "availability.csv"),
        ("per-player effects", lambda: phase_models.player_effects(df), "player_effects.csv"),
    ]
    results = {}
    for name, step, filename in steps:
        t = time.time()
        results[filename] = step()
        results[filename].to_csv(OUTPUT_DIR / filename, index=False)
        print(f"  {name}: {len(results[filename])} rows -> {filename} ({time.time() - t:.0f}s)")
    event_study.plot(results["event_study.csv"], OUTPUT_DIR / "event_study.png")

    info = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "games": len(df),
        "players": int(df["player_id"].nunique()),
        "seasons": [df["season"].min(), df["season"].max()],
        "outcomes": outcomes,
        "skipped_outcomes": skipped,
        "controls": CONTROLS + ["week of season", "player-season fixed effects"],
    }
    (OUTPUT_DIR / "model_info.json").write_text(json.dumps(info, indent=2))

    phases = results["phase_effects.csv"]
    significant = phases[phases["significant"]]
    print(f"\nBefore / on / after: {len(significant)} of {len(phases)} estimates significant after correcting for multiple tests.")
    if len(significant):
        print(significant[["label", "phase", "estimate", "ci_low", "ci_high", "q_value"]].round(3).to_string(index=False))
    print(f"\nDone in {time.time() - started:.0f}s. Results in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
