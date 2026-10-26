# Data loads: what's in the database, and what to run next

A record of which data has been loaded into the `nba` database, what is missing, and the commands to run next. **Update the "Last checked" date, the coverage tables and the load log after every load.** The [coverage queries](#check-coverage-yourself) at the bottom produce every number on this page.

**Last checked: 25 October 2026, 21:20 (Sydney time).**

## Contents

1. [At a glance](#at-a-glance)
2. [Coverage by season](#coverage-by-season)
3. [Gaps and pending work](#gaps-and-pending-work)
4. [Views, the app snapshot and the models](#views-the-app-snapshot-and-the-models)
5. [Load log](#load-log)
6. [What to run next](#what-to-run-next)
7. [Check coverage yourself](#check-coverage-yourself)

---

## At a glance

| Table | Loaded | Last loaded |
|---|---|---|
| `dbo.team` | All 30 teams | 11 Oct 2026 |
| `dbo.player` | 622 players, 519 active, all with birthdates | 25 Oct 2026 |
| `dbo.schedule` | 2017-18 to 2024-25, and 2026-27 (full season schedule) | 25 Oct 2026 |
| `dbo.player_game_log` | 2017-18 to 2024-25 (regular season + playoffs), 2026-27 to **24 Oct 2026** | 25 Oct 2026 |
| `dbo.player_game_usage` | Same as the game log (one row per game-log row) | 25 Oct 2026 |
| `dbo.team_game_log` | Same seasons as the game log | 25 Oct 2026 |
| `dbo.player_game_tracking` | **Barely started:** 3 test dates in 2017-18, and 2026-27 to 24 Oct 2026 | 25 Oct 2026 |

**Missing entirely:** the **2025-26** season (every table), preseason games (any season), and tracking for 2017-18 to 2024-25.

Times in `etl.job_run` are UTC, 11 hours behind Sydney (AEDT): a job finishing at 21:15 Sydney time shows as 10:15.

---

## Coverage by season

### Game logs

| Season | Regular season | Playoffs | First game | Last game |
|---|---|---|---|---|
| 2017-18 | 6,644 rows, 1,230 games | 516 rows, 82 games | 17 Oct 2017 | 8 Jun 2018 |
| 2018-19 | 8,425 rows, 1,230 games | 596 rows, 82 games | 16 Oct 2018 | 13 Jun 2019 |
| 2019-20 | 8,741 rows, 1,059 games | 690 rows, 83 games | 22 Oct 2019 | 11 Oct 2020 |
| 2020-21 | 10,403 rows, 1,080 games | 916 rows, 85 games | 22 Dec 2020 | 20 Jul 2021 |
| 2021-22 | 13,521 rows, 1,230 games | 1,182 rows, 87 games | 19 Oct 2021 | 16 Jun 2022 |
| 2022-23 | 16,370 rows, 1,230 games | 1,248 rows, 84 games | 18 Oct 2022 | 12 Jun 2023 |
| 2023-24 | 19,014 rows, 1,230 games | 1,357 rows, 82 games | 24 Oct 2023 | 17 Jun 2024 |
| 2024-25 | 21,545 rows, 1,230 games | 1,682 rows, 84 games | 22 Oct 2024 | 22 Jun 2025 |
| **2025-26** | **not loaded** | **not loaded** | | |
| 2026-27 | 812 rows, 36 games | (not started) | 20 Oct 2026 | **24 Oct 2026** |

Rows are player-games for **players in `dbo.player`** (today's active players plus anyone previously loaded), not every player in the league. Older seasons therefore have fewer rows: only the players still around today. 2019-20 and 2020-21 have fewer games because of COVID-shortened seasons.

### The other tables, per season

| Season | Game log rows | Usage rows | Team rows | Schedule rows | Tracking rows | Tracking dates done |
|---|---|---|---|---|---|---|
| 2017-18 | 7,160 | 7,160 | 2,624 | 1,393 | 90 | 3 of 212 |
| 2018-19 | 9,021 | 9,021 | 2,624 | 1,395 | 0 | 0 of 213 |
| 2019-20 | 9,431 | 9,431 | 2,284 | 1,145 | 0 | 0 of 192 |
| 2020-21 | 11,319 | 11,319 | 2,330 | 1,221 | 0 | 0 of 187 |
| 2021-22 | 14,703 | 14,703 | 2,634 | 1,393 | 0 | 0 of 210 |
| 2022-23 | 17,618 | 17,618 | 2,628 | 1,394 | 0 | 0 of 209 |
| 2023-24 | 20,371 | 20,371 | 2,624 | 1,396 | 0 | 0 of 204 |
| 2024-25 | 23,227 | 23,227 | 2,628 | 1,400 | 0 | 0 of 210 |
| 2025-26 | | | | | | |
| 2026-27 | 812 | 812 | 72 | 1,274 (whole season) | 812 | 3 of 5 |

Usage rows should always equal game log rows. Team rows are 2 per game across all teams, so they don't depend on `dbo.player`.

### Tracking dates done (`etl.date_load`)

| Date | Rows | Note |
|---|---|---|
| 17 Oct 2017 | 13 | Test date |
| 18 Oct 2017 | 57 | Test date |
| 19 Oct 2017 | 20 | Test date |
| 20 Oct 2026 | 68 | |
| 21 Oct 2026 | 254 | |
| 22 Oct 2026 | 45 | |
| 23 Oct 2026 | (pending) | Hustle and starters saved; distance, passing and touches not published by the NBA yet |
| 24 Oct 2026 | (pending) | Same |

---

## Gaps and pending work

In priority order.

| Gap | Why it matters | Command | Time |
|---|---|---|---|
| **Tracking for 23-24 Oct 2026** | Distance, passing and touches missing for 445 rows | `run_job.py tracking --season 2026-27` (retries automatically) | Under a minute |
| **2025-26 season** | The most recent full season; more birthday games for the models; the Today page shows no games on 2025-26 dates | See [Load 2025-26](#load-the-2025-26-season) | A few minutes |
| **Tracking 2017-18 to 2024-25** | Needed to model the "tired" stats (distance, speed, hustle) and passes received / touches | `run_job.py tracking` | About 2-2.5 hours, resumable |
| **Preseason** | October birthdays (e.g. Josh Giddey, 10 Oct) only ever fall in the preseason | Needs a code change: add `"Pre Season"` to `SEASON_TYPES` in `src/config.py` | |
| **2016-17 and earlier** | Optional. Only a few players still active | `game_logs --backfill`, etc. | |

---

## Views, the app snapshot and the models

**Views are never "loaded".** They are saved queries that read the tables every time, so they are always as current as the tables underneath. Nothing needs running for them. The SQL defines them; `init_db` (re)creates them after the SQL files change.

| View | Built from | Current as of |
|---|---|---|
| `v_player_game_birthday` | player_game_log + player | the tables |
| `v_birthday_week_vs_season` | v_player_game_birthday | the tables |
| `v_upcoming_birthday_week_games` | schedule + player (games from today on) | the tables |
| `v_team_game_context`, `v_team_key_players`, `v_team_game_absences` | team_game_log + player_game_log | the tables |
| `v_player_missed_games` | team_game_log + player_game_log | the tables |
| `v_player_game_context` | all of the above + schedule | the tables |
| `v_player_game_features` | everything: the modelling view | the tables |

**Two things are copies and do need refreshing** after a load:

| Copy | Last refreshed | Covers | Refresh with |
|---|---|---|---|
| Parquet snapshot for the app (`data/`) | 25 Oct 2026, 21:18 | Tables as of then (to 24 Oct 2026) | `run_job.py export` |
| Model results (`outputs/`) | 25 Oct 2026, 21:19 | 105,469 regular-season games, 503 players, 2017-18 to 2026-27 | `src\models\run_models.py` |

The exact times are in `data/manifest.json` and `outputs/model_info.json`.

---

## Load log

Newest first. Add a row for every load.

| Date (Sydney) | What was run | Result |
|---|---|---|
| 25 Oct 2026 | `players`, `schedule`, `game_logs`, `usage`, `team_logs`, `tracking`, all `--season 2026-27`; then `export` and `run_models.py` | 2026-27 opening week loaded: 36 games, 812 player rows (20-24 Oct). Active players 622 → 519 after roster cuts. Tracking for 23-24 Oct not published yet; fixed the tracking job so those dates retry |
| 18 Oct 2026 | `schedule --loaded`; `tracking --limit 3` (after adding passing, touches and starters) | Past schedules for 2017-18 to 2024-25 (10,737 games). Tracking re-tested on 3 dates |
| 11-14 Oct 2026 | `game_logs` for 2017-18 to 2024-25 (reloaded by hand), `usage --loaded`, `team_logs --loaded` | 8 seasons of game logs (112,850 rows), usage and team logs to match |
| 11 Oct 2026 | `init_db`, `teams`, `players`, `schedule` (2026-27), `tracking --limit 3` | Database created. 30 teams, 622 players with birthdates, the 2026-27 schedule. Tracking tested on 3 dates |

---

## What to run next

All commands run from the project folder: `C:\Users\andre\PycharmProjects\ajo\nba`.

### During the season (daily, or whenever you want to catch up)

```powershell
.venv\Scripts\python.exe src\run_job.py players
.venv\Scripts\python.exe src\run_job.py schedule
.venv\Scripts\python.exe src\run_job.py game_logs
.venv\Scripts\python.exe src\run_job.py usage
.venv\Scripts\python.exe src\run_job.py team_logs
.venv\Scripts\python.exe src\run_job.py tracking --season 2026-27
.venv\Scripts\python.exe src\run_job.py export
.venv\Scripts\python.exe src\models\run_models.py
```

- With no season option, the season jobs load the **current season** (2026-27). They re-download it whole and upsert, so missing a few days is fine: one run catches up.
- `--season 2026-27` on `tracking` keeps it to this season. Without it, it starts the long backfill of older seasons.
- `run_job.py all` does all of the jobs in one go, but **includes the full tracking backfill** until that is finished.
- Tracking dates from the last 7 days that the NBA hasn't published yet are retried automatically on the next run.

### Load the 2025-26 season

```powershell
.venv\Scripts\python.exe src\run_job.py game_logs --season 2025-26
.venv\Scripts\python.exe src\run_job.py usage --season 2025-26
.venv\Scripts\python.exe src\run_job.py team_logs --season 2025-26
.venv\Scripts\python.exe src\run_job.py schedule --season 2025-26
.venv\Scripts\python.exe src\run_job.py export
.venv\Scripts\python.exe src\models\run_models.py
```

Players who retired after 2025-26 but aren't in `dbo.player` won't be included; that's consistent with the other seasons.

### The tracking backfill (one-off, long)

```powershell
.venv\Scripts\python.exe src\run_job.py tracking
```

About 2-2.5 hours for 2017-18 to 2024-25, plus about 15 minutes for 2025-26 once that is loaded. Ctrl+C stops it safely; run it again to carry on. Add `--limit 100` to do it in chunks. Afterwards, re-run `export` and `run_models.py`: the tracking stats then join the models and the app automatically.

### After any load

1. Run the [coverage queries](#check-coverage-yourself) and update the tables on this page.
2. Add a row to the [load log](#load-log).
3. Check `etl.job_run` for failures: `SELECT TOP 20 * FROM etl.job_run ORDER BY run_id DESC;`

---

## Check coverage yourself

Paste into SSMS (database `nba`). These produce every number on this page.

```sql
-- Game logs by season and season type
SELECT season, season_type, COUNT(*) AS rows_, COUNT(DISTINCT game_id) AS games,
       MIN(game_date) AS first_date, MAX(game_date) AS last_date
FROM dbo.player_game_log
GROUP BY season, season_type
ORDER BY season, season_type;

-- Every table side by side, per season
SELECT l.season,
       COUNT(*) AS log_rows,
       (SELECT COUNT(*) FROM dbo.player_game_usage u JOIN dbo.player_game_log x
            ON x.player_id = u.player_id AND x.game_id = u.game_id WHERE x.season = l.season) AS usage_rows,
       (SELECT COUNT(*) FROM dbo.team_game_log t WHERE t.season = l.season) AS team_rows,
       (SELECT COUNT(*) FROM dbo.schedule s WHERE s.season = l.season) AS schedule_rows,
       (SELECT COUNT(*) FROM dbo.player_game_tracking t JOIN dbo.player_game_log x
            ON x.player_id = t.player_id AND x.game_id = t.game_id WHERE x.season = l.season) AS tracking_rows,
       (SELECT COUNT(DISTINCT x.game_date) FROM dbo.player_game_log x WHERE x.season = l.season) AS game_dates,
       (SELECT COUNT(*) FROM etl.date_load d WHERE d.dataset = 'tracking' AND d.game_date IN
            (SELECT DISTINCT game_date FROM dbo.player_game_log y WHERE y.season = l.season)) AS tracking_dates_done
FROM dbo.player_game_log AS l
GROUP BY l.season
ORDER BY l.season;

-- Tracking dates with games but not yet done (what the tracking job will fetch next)
SELECT DISTINCT season, game_date
FROM dbo.player_game_log AS l
WHERE NOT EXISTS (SELECT 1 FROM etl.date_load AS d WHERE d.dataset = 'tracking' AND d.game_date = l.game_date)
ORDER BY game_date DESC;

-- Played games in the schedule that have no game logs yet (should be empty after a load)
SELECT s.game_date, s.away_team_tricode + ' @ ' + s.home_team_tricode AS game, s.game_status_text
FROM dbo.schedule AS s
WHERE s.game_status_text LIKE 'Final%'
  AND s.game_id LIKE '002%'                                   -- regular season
  AND s.season IN (SELECT DISTINCT season FROM dbo.player_game_log)
  AND NOT EXISTS (SELECT 1 FROM dbo.player_game_log AS l WHERE l.game_id = s.game_id)
ORDER BY s.game_date;

-- Players
SELECT COUNT(*) AS players, SUM(CAST(is_active AS INT)) AS active, COUNT(birthdate) AS with_birthdate
FROM dbo.player;

-- Last successful run of each job (UTC)
SELECT job_name, MAX(finished_at) AS last_success_utc, COUNT(*) AS successful_runs
FROM etl.job_run
WHERE status = 'success'
GROUP BY job_name
ORDER BY job_name;
```
