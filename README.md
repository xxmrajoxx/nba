# NBA birthday-week pipeline

A local data pipeline that pulls NBA data from [nba_api](https://github.com/swar/nba_api), loads it into SQL Server, and answers one question:

> **Do active NBA players perform differently during their birthday week?**

Everything runs on your own machine: Python fetches the data, SQL Server stores it, and SQL views plus a small Python script do the analysis.

## How it fits together

```
stats.nba.com  ──►  Python jobs  ──►  staging tables  ──►  final tables  ──►  views  ──►  analysis
 (nba_api)          (src/*.py)         (stg schema)        (dbo schema)     (dbo.v_*)   (analysis.py)
```

1. A **job** asks the NBA stats API for data and tidies it into a pandas DataFrame.
2. The DataFrame is bulk-loaded into a **staging table** (`stg.<table>`).
3. A SQL `MERGE` copies staging into the **final table**: new rows are inserted, existing rows are updated.
4. **Views** add the birthday logic on top of the tables.
5. Every job run is recorded in `etl.job_run`.

## Setup

You need SQL Server running locally (default instance, Windows authentication), the "ODBC Driver 17 for SQL Server", and Python 3.12.

```powershell
cd C:\Users\andre\PycharmProjects\ajo\nba
python -m venv .venv                                  # only if .venv does not exist yet
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\run_job.py init_db       # creates the nba database, tables and views
```

Connection settings live in [src/config.py](src/config.py). To point at a different server or database without editing code, set `NBA_SQL_SERVER`, `NBA_SQL_DATABASE` or `NBA_SQL_DRIVER` as environment variables.

## Running jobs

All jobs go through one command. Always use the virtual environment's Python:

```powershell
.venv\Scripts\python.exe src\run_job.py <job> [options]
```

| Command | What it does | API requests |
|---|---|---|
| `init_db` | Creates the database if missing, then runs every script in `sql/` | 0 |
| `teams` | Loads the 30 teams | 0 (bundled with nba_api) |
| `players` | Loads active players; fetches birthdate, position, height, weight and country for any player who doesn't have them yet | 1 + one per new player |
| `schedule` | Loads the current season's schedule | 1 |
| `schedule --season 2025-26` | Loads a specific season's schedule | 1 |
| `game_logs` | Loads game logs for the current season | up to 4 |
| `game_logs --season 2024-25` | One specific season | up to 4 |
| `game_logs --last 7` | The last 7 seasons, counting the current one | up to 28 |
| `game_logs --backfill` | Every season since the longest-tenured active player's debut (2003-04) | ~96 |
| `usage` | Loads usage and scoring splits per player per game | up to 4 per season |
| `team_logs` | Loads team game logs (box score and advanced) | up to 4 per season |
| `tracking` | Loads tracking (distance, speed) and hustle stats for every game date in the game logs not fetched yet | 2 per game date |
| `tracking --limit 20` | Only the next 20 game dates | 40 |
| `all` | Every job above, in dependency order | |

`game_logs`, `usage` and `team_logs` take the same season options: `--season 2024-25`, `--last N`, `--backfill`, or `--loaded` (every season that already has rows in `dbo.player_game_log`, handy for lining the other tables up with the game logs). With no option they load the current season.

**`tracking` is the slow one.** It needs two requests per game date, about 3.5 seconds a date, so eight seasons (around 1,640 dates) takes roughly an hour and a half the first time. Each date is saved as it completes: stop it with Ctrl+C whenever you like and run it again to carry on. After the first load a daily run only fetches the new dates. Note that `all` includes it.

Order matters the first time: players reference teams, game logs reference players, and tracking takes its game dates from the game logs. `all` handles that for you.

**Every job is safe to re-run.** Because loading is an upsert, running a job twice gives the same result as running it once. If a job is interrupted, just run it again.

### Typical use

```powershell
# First time
.venv\Scripts\python.exe src\run_job.py init_db
.venv\Scripts\python.exe src\run_job.py all --backfill

# Day to day during the season
.venv\Scripts\python.exe src\run_job.py all
```

### Scheduling a daily refresh

[scripts/register_scheduled_task.ps1](scripts/register_scheduled_task.ps1) registers a Windows Task Scheduler task called `nba-pipeline-daily` that runs `all` at 6:00 AM. Run it once from PowerShell:

```powershell
.\scripts\register_scheduled_task.ps1
```

Remove it with `Unregister-ScheduledTask -TaskName "nba-pipeline-daily"`. This script has been written but not yet run.

## The database

Database: `nba` on `localhost`.

### `dbo.team`
One row per NBA team. Key: `team_id`.

### `dbo.player`
One row per active player. Key: `player_id`.

| Column | Notes |
|---|---|
| `birthdate` | A real `DATE`. Use this for sorting and date maths. |
| `birthdate_mdy` | The same date as `MM-DD-YYYY` text. Computed from `birthdate`, so it is always in sync and is never loaded directly. |
| `team_id` | `NULL` for free agents. |
| `from_year`, `to_year` | First and latest season in the league. |
| `is_active` | Set to 0 when a player drops off the active list; the row and their game logs are kept. |

### `dbo.schedule`
One row per scheduled game (preseason, regular season, cup games). Key: `game_id`. Team ids are not foreign keys because preseason opponents can be non-NBA teams.

### `dbo.player_game_log`
One row per player per game. Key: (`player_id`, `game_id`). Only players in `dbo.player` are kept.

- **Context:** `season`, `season_type` (Regular Season / Playoffs), `game_date`, `team_id`, `opponent_abbreviation`, `is_home`, `wl`.
- **Box score:** `minutes`, `pts`, `reb`, `ast`, `stl`, `blk`, `tov`, `pf`, `plus_minus`, and field goal / three-point / free throw makes, attempts and percentages.
- **Advanced:** `off_rating`, `def_rating`, `net_rating`, `usg_pct`, `ts_pct`, `efg_pct`, `ast_pct`, `ast_to`, `ast_ratio`, `oreb_pct`, `dreb_pct`, `reb_pct`, `tm_tov_pct`, `pace`, `pie`, `poss`.

### `dbo.player_game_usage`
One row per player per game. Key: (`player_id`, `game_id`). Joins one-to-one with `dbo.player_game_log`.

- **Share of team totals while on court:** `pct_fga` (share of the team's shot attempts), `pct_pts`, `pct_ast`, `pct_reb`, `pct_tov` and the rest.
- **Shot and points profile:** `pct_fga_3pt`, `pct_pts_paint`, `pct_pts_fb` (fast break), `pct_pts_ft` and so on.
- **Assisted or self-created:** `pct_ast_fgm` is the share of the player's made shots that a teammate assisted; `pct_uast_fgm` is the unassisted share.

### `dbo.team_game_log`
One row per team per game, so two rows per game. Key: (`team_id`, `game_id`). Same box score and advanced columns as the player log. Use it for team totals and for the opponent in a game (same `game_id`, different `team_id`).

### `dbo.player_game_tracking`
One row per player per game. Key: (`player_id`, `game_id`).

- **Tracking:** `dist_miles`, `dist_miles_off`, `dist_miles_def`, `avg_speed` (miles per hour), `avg_speed_off`, `avg_speed_def`. Available from 2013-14.
- **Hustle:** `contested_shots`, `deflections`, `charges_drawn`, `screen_assists`, `loose_balls_recovered`, `box_outs` and their breakdowns. Available from 2015-16; an occasional player-game has tracking but no hustle row.

### `etl.date_load`
Which game dates the `tracking` job has already fetched. To re-fetch a date, delete its row here and run the job again.

### `etl.job_run`
One row per job execution: job name, start and finish time, status (`running` / `success` / `failed`), rows loaded, and the error message if it failed. Check on the pipeline with:

```sql
SELECT TOP 20 * FROM etl.job_run ORDER BY run_id DESC;
```

### `stg.*`
Staging tables used by the upsert. Each holds whatever the most recent load put there; they are dropped and recreated on every run.

## The birthday-week analysis

**Definition:** a game is in a player's *birthday week* if it was played within 3 days either side of their birthday (a 7-day window centred on the day).

### Views ([sql/02_views.sql](sql/02_views.sql))

| View | What it gives you |
|---|---|
| `dbo.v_player_game_birthday` | Every game log row plus `days_from_birthday` (negative = before, 0 = on the day), `is_birthday_week`, `is_birthday`, and `age_at_game` |
| `dbo.v_birthday_week_vs_season` | One row per player-season: birthday-week averages next to that player's averages for the rest of the same season |
| `dbo.v_upcoming_birthday_week_games` | Games still to be played that fall in an active player's birthday week |
| `dbo.v_player_game_features` | One wide row per player per game for modelling: everything in `v_player_game_birthday` plus usage and scoring splits, tracking and hustle stats, team and opponent totals, `days_rest`, and `birthday_phase` (`before` / `on` / `after` / `none`) |

`v_player_game_features` is the table to model from. Two things to know about it: `days_rest` is empty for a player's first game in the data and is very large for the first game of each season (the gap is the whole off-season), and `team_*` / `opponent_*` columns describe the same game, so they are context for explaining a performance, not inputs you would have before tip-off.

The nearest birthday is not always in the same calendar year as the game: for a December 30 birthday, a January 1 game is 2 days *after* the birthday, not 363 days before the next one. The views check the previous, current and next year's birthday and keep the closest.

### Why compare within a season?

Comparing a player's birthday-week games against their whole career would be misleading: players improve and decline over the years, so a career average is not a fair baseline for any one week. Comparing against the rest of the *same season* holds the player's age, role and team roughly constant, so what is left over is closer to a real birthday effect.

### Running it

```powershell
.venv\Scripts\python.exe src\analysis.py
```

[src/analysis.py](src/analysis.py) reads `v_birthday_week_vs_season` and, for points, rebounds, assists, minutes, true shooting % and plus/minus, reports the average difference (birthday week minus rest of season) with a 95% bootstrap confidence interval. If the interval includes 0, the data is consistent with birthdays making no difference. It also lists the players with the biggest scoring boosts and drops. This script has been written but not yet run against the data.

### Things to keep in mind when reading the results

- **Off-season birthdays.** Players born roughly July to September never play a regular-season game in their birthday week, so they drop out of the analysis.
- **Small samples.** A birthday week is 2 to 4 games a year. Individual player results are noisy; the league-wide average is the more trustworthy number.
- **Active players only.** The data covers players active today, so older seasons contain only the players who lasted. That is a survivor sample, not the whole league as it was.
- **Changing the window.** To try a different definition, change the `<= 3` in the two views in `sql/02_views.sql` and run `init_db` again.

### The two explanations being tested

| Explanation | What it predicts | Where to look |
|---|---|---|
| Teammates feed the birthday player | More volume: higher `usg_pct`, `pct_fga`, `pct_pts`, and more assisted baskets (`pct_ast_fgm`), mostly on the day itself | `birthday_phase = 'on'` |
| He partied and is tired | Worse quality: lower `ts_pct`, fewer `minutes`, more `tov`, less `dist_miles` and `avg_speed`, fewer `deflections` and `contested_shots`, mostly in the next game or two | `birthday_phase = 'after'` |

## Design decisions

**Tracking and hustle are fetched per game date, not per game.** They are only published per game through box score endpoints, which would mean about 21,000 requests for eight seasons. The league-wide tracking and hustle endpoints accept a one-day date range and return every player who played that day; because nobody plays twice in a day, that is the same per-game data in about 3,300 requests. The game id is then looked up from the game log.

**Game logs are fetched per season, not per player or per team.** Calling `PlayerGameLogs` without a player or team filter returns every player's games for a season in one response. Seven seasons with both season types and both stat sets is 28 requests, against about 840 looping over teams and about 17,000 looping over players.

**Advanced stats come from a second call.** The API returns box score ("Base") and "Advanced" stats separately, so each season is fetched twice and joined on player + game.

**Birthdates are fetched once.** They need one request per player and never change, so the players job only fetches them for players who don't have one yet. Batches of 50 are saved as they complete, so an interrupted run resumes where it stopped.

**Loads are upserts, not appends.** Appending would create duplicates on every re-run. `MERGE` on the table's key means a job can be re-run freely. The staging table is created by copying the final table's column types, so pandas never has to guess them.

**Requests are paced and retried.** stats.nba.com throttles aggressive clients. Every request waits 0.6 seconds, times out after 60, and is retried up to 4 times with increasing waits. On retry a fresh HTTP connection is opened, because after a few hundred requests the API can stop answering on the old one.

**Dates are stored as dates.** `birthdate` is a `DATE` so that date arithmetic and sorting work; the display format is provided separately by `birthdate_mdy`.

## Project layout

```
nba/
├── requirements.txt
├── sql/
│   ├── 01_schema.sql              tables, schemas, indexes
│   └── 02_views.sql               birthday-week views
├── src/
│   ├── run_job.py                 command line entry point
│   ├── config.py                  connection settings, API pacing, logging
│   ├── db.py                      engine, init_db, upsert, job tracking
│   ├── nba_client.py              paced, retrying wrapper around nba_api calls
│   ├── seasons.py                 season label helpers ("2025-26")
│   ├── teams.py                   teams job
│   ├── player.py                  players job
│   ├── schedule.py                schedule job
│   ├── player_game_logs.py        game logs job
│   ├── player_game_usage.py       usage and scoring splits job
│   ├── team_game_logs.py          team game logs job
│   ├── player_tracking.py         tracking and hustle job
│   └── analysis.py                birthday-week analysis
├── scripts/
│   └── register_scheduled_task.ps1
└── logs/
    └── nba_pipeline.log           created on first run, not committed
```

To add a new table: add a `CREATE TABLE` (with an `updated_at` column) to `sql/01_schema.sql`, write a module with a `run()` function that builds a DataFrame and calls `db.upsert(df, "table", keys=[...])`, and register it in `JOB_ORDER` and `jobs` in `src/run_job.py`.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `ModuleNotFoundError` | You ran plain `python`. Use `.venv\Scripts\python.exe`. |
| `Login failed` / `Cannot open database "nba"` | Run `init_db` first, and check SQL Server is running. |
| `Read timed out` warnings | Normal now and then; the request is retried automatically. If every request fails, wait a few minutes before trying again. |
| `dbo.player is empty` | Run the `players` job before `game_logs`. |
| `tracking` says `0 game dates to fetch` | Either everything is fetched already, or `dbo.player_game_log` is empty. |
| A job shows `running` in `etl.job_run` forever | It was killed mid-run. Re-run the job; the stale row is harmless. |
| New column missing in SSMS | Right-click the table in Object Explorer and choose Refresh. |

## Useful queries

```sql
-- How much is loaded?
SELECT season, season_type, COUNT(*) AS rows
FROM dbo.player_game_log
GROUP BY season, season_type
ORDER BY season, season_type;

-- One player's birthday-week games
SELECT game_date, matchup, days_from_birthday, minutes, pts, reb, ast, ts_pct
FROM dbo.v_player_game_birthday
WHERE full_name = 'LeBron James' AND is_birthday_week = 1
ORDER BY game_date;

-- Who has a birthday-week game coming up?
SELECT * FROM dbo.v_upcoming_birthday_week_games ORDER BY game_date;
```
