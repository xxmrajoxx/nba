"""Export job: writes the tables and views the app uses to Parquet files in data/.

The files are a snapshot of SQL Server that the app can read with DuckDB, so it can run
without SQL Server: on another computer, or deployed to the cloud.

    .venv\\Scripts\\python.exe src\\run_job.py export
"""
import json
import logging
from datetime import datetime

import config
import db

logger = logging.getLogger(__name__)

# Parquet file name (schema.table) -> query. The file names match the SQL names, so the
# app's queries work unchanged against either source.
EXPORTS = {
    "dbo.team": "SELECT * FROM dbo.team",
    "dbo.player": "SELECT * FROM dbo.player",
    "dbo.schedule": "SELECT * FROM dbo.schedule",
    "dbo.team_game_log": "SELECT * FROM dbo.team_game_log",
    "dbo.v_player_game_features": "SELECT * FROM dbo.v_player_game_features",
    "dbo.v_birthday_week_vs_season": "SELECT * FROM dbo.v_birthday_week_vs_season",
    "dbo.v_player_missed_games": "SELECT * FROM dbo.v_player_missed_games",
    "dbo.v_upcoming_birthday_week_games": "SELECT * FROM dbo.v_upcoming_birthday_week_games",
    "etl.job_run": "SELECT TOP 50 * FROM etl.job_run ORDER BY run_id DESC",
}


def run() -> int:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, sql in EXPORTS.items():
        df = db.read_sql(sql)
        path = config.DATA_DIR / f"{name}.parquet"
        # Write to a temporary file and then swap it in, so an app reading the old file
        # never sees a half-written one.
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(path)
        counts[name] = len(df)
        logger.info(f"Exported {len(df):,} rows to {path.name}")

    manifest = {"exported_at": datetime.now().isoformat(timespec="seconds"), "rows": counts}
    (config.DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return sum(counts.values())
