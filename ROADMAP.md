# Roadmap: modelling the birthday effect

What we are working on next, the data behind it, the models to try, and the order to do it in. For how the pipeline works and how to run it, see [README.md](README.md).

_Status as of 11 October 2026._

## The question

Do active NBA players perform differently around their birthday, and if so, why? Two explanations are on the table, and they predict different things:

| Explanation | What we would expect to see | When |
|---|---|---|
| **Teammates feed him** | More volume: higher usage, a bigger share of the team's shots and points, more assisted baskets. Efficiency about the same. | On the birthday itself |
| **He partied and is tired** | Worse quality: lower shooting efficiency, fewer minutes, more turnovers, less distance covered, slower speed, fewer hustle plays. | The game or two after |

Both could be true at once and cancel out in a whole-week average, so the analysis splits the window into **before**, **on** and **after** the birthday instead of treating the week as one block.

## Datasets

### Loaded

| Dataset | Table | Coverage | Used for |
|---|---|---|---|
| Players and birthdates | `dbo.player` | 622 active players | The birthday itself, age |
| Player game logs, box score and advanced | `dbo.player_game_log` | 2017-18 to 2024-25, 112,850 rows | Outcomes: points, efficiency, minutes, turnovers, usage rate |
| Usage and scoring splits | `dbo.player_game_usage` | Every game log row | "Teammates feed him": share of team shots, assisted baskets |
| Team game logs | `dbo.team_game_log` | Every game in those seasons | Team totals, opponent, pace |
| Schedule | `dbo.schedule` | 2026-27 | Upcoming birthday-week games |

### Partly loaded

| Dataset | Table | Coverage | Used for |
|---|---|---|---|
| Tracking (distance, speed) and hustle stats | `dbo.player_game_tracking` | 3 of 1,637 game dates | "Partied and tired": the most direct fatigue signals |

Finishing this is the first next step. It takes about an hour and a half and can be stopped and resumed:

```powershell
.venv\Scripts\python.exe src\run_job.py tracking
```

### Not loaded yet

| Dataset | Why we might want it | Cost | Priority |
|---|---|---|---|
| Preseason game logs | Early-to-mid October birthdays (Josh Giddey, October 10) only ever fall in the preseason, so those players have no birthday games in the data at all | Cheap: one more season type in the existing job | High |
| 2025-26 game logs | The most recent completed season is missing | Cheap: `game_logs --season 2025-26`, then `usage` and `team_logs` | High |
| Missed games | A player who sits out the day after his birthday is absent from the game logs, so the most tired players may be silently missing. Derive from team games the player's team played that he did not | No new data: SQL over `team_game_log` and `player_game_log` | High |
| Opponent strength before the game | Season-to-date defensive rating of the opponent, as a fair measure of how hard the game was | No new data: rolling average over `team_game_log` | Medium |
| Travel and time zones | Fatigue unrelated to the birthday that we should control for | Derivable from arena city in `dbo.schedule` for 2026-27 only; older seasons need more data | Low |
| Injury reports | Separate "rested" from "hurt" for missed games | No clean source in `nba_api` | Low |

## What we have to work with

Regular-season games with minutes played, 2017-18 to 2024-25:

| Phase | Games | Players |
|---|---|---|
| Before (1 to 3 days before) | 825 | 178 |
| On the birthday | 282 | 136 |
| After (1 to 3 days after) | 798 | 191 |
| Any other game | 102,752 | 421 |

The on-the-day sample is small. That shapes everything below: it is enough to detect a moderate league-wide effect, but not to say much about any single player, and far too little to train a model on birthday games alone.

## Models

### 1. Effect model: fixed-effects regression (do this first)

This answers the actual question: how big is the effect, and how sure are we?

```
outcome = player-season baseline + home/away + days of rest + opponent strength + birthday phase
```

- **Outcomes, one model each.** For "teammates feed him": `usg_pct`, `pct_fga`, `pct_pts`, `pct_ast_fgm`, `fga`. For "partied and tired": `ts_pct`, `minutes`, `tov`, `dist_miles`, `avg_speed`, `deflections`, `contested_shots`.
- **Why fixed effects.** Each player is compared with himself in the same season, so a star's birthday is not compared with a bench player's ordinary Tuesday.
- **What comes out.** A coefficient for each phase with a confidence interval, such as "on their birthday players take X more of their team's shots, give or take Y".
- **Tools.** `statsmodels` (ordinary least squares with player-season dummies, or `MixedLM`), with standard errors clustered by player.

Follow-up questions for the same model, by adding interactions:

- Is the effect stronger for younger players (a 21st birthday against a 34th)?
- Home against away, and does the city matter?
- Does a night off between the birthday and the next game remove the "after" dip?

### 2. Prediction model: gradient-boosted trees (second)

This answers a different question: does knowing about the birthday help predict a player's next game?

- **Target.** Points first, then a second model for true shooting %.
- **Features.** Rolling averages over the player's last 5, 10 and 20 games (points, minutes, usage, shot attempts), home/away, days of rest, back-to-back, opponent strength to date, age, and the birthday phase.
- **Tools.** LightGBM or XGBoost.
- **The test.** Train the model with and without the birthday features. If the error does not improve, the birthday carries no predictive value beyond recent form, which is itself a finding.

### Rules for both

- **Split by time.** Train on older seasons, test on the newest. A random split leaks the future into training.
- **No leakage.** Every feature must be known before tip-off. The `team_*` and `opponent_*` columns in `v_player_game_features` describe the same game, so they explain a performance but cannot be used to predict one. Rolling averages must exclude the game being predicted.
- **Beat a baseline first.** "The player's season average so far" is hard to beat by much.
- **Many outcomes, many chances to be fooled.** Testing a dozen outcomes means one will look significant by luck. Decide the main outcomes up front (`pct_fga` on the day, `ts_pct` after) and treat the rest as exploratory.

## Next steps

1. **Finish the tracking load.** Run the `tracking` job to completion.
2. **Fill the data gaps.** Load 2025-26, and add preseason as a season type so October birthdays are covered.
3. **Run the first-pass analysis.** `src/analysis.py` compares birthday week with the rest of the season. It is written but has never been run.
4. **Explore before modelling.** Average each outcome by `days_from_birthday` from -7 to +7 and plot it. If either explanation is true, it should be visible here first.
5. **Build the missed-games table.** Team games the player did not appear in, flagged by birthday phase.
6. **Build the modelling dataset.** A view or table with rolling features and opponent strength to date, checked for leakage.
7. **Fit the effect model.** One regression per main outcome; report coefficients and intervals for before, on and after.
8. **Fit the prediction model.** Baseline, then boosted trees with and without birthday features.
9. **Write up the findings.** What the data supports, what it does not, and the limits below.

New Python dependencies when we reach steps 4 to 8: `statsmodels`, `scikit-learn`, `lightgbm`, `matplotlib`, and `jupyter` if we want notebooks.

## Limits to keep in mind

- **Active players only.** Older seasons contain only the players still in the league today, a survivor sample and not the league as it was.
- **Off-season birthdays.** Players born from about July to September never play near their birthday and drop out entirely.
- **Preseason is different.** If preseason is added, minutes are restricted and effort varies, so it should be analysed separately from regular-season games.
- **We cannot observe the party.** A dip after the birthday is consistent with tiredness, but the data cannot say what caused it.
- **Small effects are likely.** The honest prior is that any birthday effect is small or zero. A well-supported "no effect" is a valid result.
