"""Command line entry point for the pipeline.

    python src/run_job.py init_db               create the database, tables and views
    python src/run_job.py all --backfill        first full load (every season)
    python src/run_job.py all                   daily refresh (current season only)
    python src/run_job.py game_logs --season 2024-25
    python src/run_job.py game_logs --last 7    the last 7 seasons
"""
import argparse
import sys

import config
import db
import player
import player_game_logs
import schedule
import teams

# Order matters for "all": players reference teams, game logs reference players.
JOB_ORDER = ["teams", "players", "schedule", "game_logs"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NBA pipeline jobs")
    parser.add_argument("job", choices=["init_db", "all"] + JOB_ORDER)
    parser.add_argument("--backfill", action="store_true", help="game_logs: load every season, not just the current one")
    parser.add_argument("--season", help="schedule / game_logs: a specific season, e.g. 2024-25")
    parser.add_argument("--last", type=int, help="game_logs: load the last N seasons, counting the current one")
    args = parser.parse_args()

    config.setup_logging()

    if args.job == "init_db":
        db.init_db()
        return 0

    jobs = {
        "teams": teams.run,
        "players": player.run,
        "schedule": lambda: schedule.run(season=args.season),
        "game_logs": lambda: player_game_logs.run(backfill=args.backfill, season=args.season, last=args.last),
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
