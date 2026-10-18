"""Command line entry point for the pipeline.

    python src/run_job.py init_db               create the database, tables and views
    python src/run_job.py all --backfill        first full load (every season)
    python src/run_job.py all                   daily refresh (current season only)
    python src/run_job.py game_logs --season 2024-25
    python src/run_job.py game_logs --last 7    the last 7 seasons
    python src/run_job.py usage --loaded        every season that already has game logs
    python src/run_job.py tracking --limit 20   the next 20 game dates not fetched yet
    python src/run_job.py schedule --loaded     past schedules, for tip-off times and arenas
"""
import argparse
import sys

import config
import db
import player
import player_game_logs
import player_game_usage
import player_tracking
import schedule
import team_game_logs
import teams
from seasons import select_seasons

# Order matters for "all": players reference teams, game logs reference players,
# and tracking takes its game dates from the game logs.
JOB_ORDER = ["teams", "players", "schedule", "game_logs", "usage", "team_logs", "tracking"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NBA pipeline jobs")
    parser.add_argument("job", choices=["init_db", "all"] + JOB_ORDER)
    seasons = parser.add_argument_group("which seasons (schedule, game_logs, usage, team_logs; default: the current season)")
    seasons.add_argument("--season", help="a specific season, e.g. 2024-25 (also tracking)")
    seasons.add_argument("--last", type=int, help="the last N seasons, counting the current one")
    seasons.add_argument("--backfill", action="store_true", help="every season since the longest-tenured player's debut")
    seasons.add_argument("--loaded", action="store_true", help="every season that already has rows in dbo.player_game_log")
    parser.add_argument("--limit", type=int, help="tracking: stop after this many game dates")
    args = parser.parse_args()

    config.setup_logging()

    if args.job == "init_db":
        db.init_db()
        return 0

    # Resolved when each job starts, not up front: --backfill reads dbo.player, which "all" may have only just loaded.
    def chosen_seasons() -> list:
        return select_seasons(season=args.season, last=args.last, backfill=args.backfill, loaded=args.loaded)

    jobs = {
        "teams": teams.run,
        "players": player.run,
        "schedule": lambda: schedule.run(chosen_seasons()),
        "game_logs": lambda: player_game_logs.run(chosen_seasons()),
        "usage": lambda: player_game_usage.run(chosen_seasons()),
        "team_logs": lambda: team_game_logs.run(chosen_seasons()),
        "tracking": lambda: player_tracking.run(season=args.season, limit=args.limit),
    }
    failed = False
    for name in JOB_ORDER if args.job == "all" else [args.job]:
        try:
            db.run_tracked(name, jobs[name])
        except Exception:
            # Already logged and recorded in etl.job_run; keep going so one bad job
            # does not block the others, but report failure to the scheduler.
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
