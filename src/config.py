import logging
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
LOG_DIR = PROJECT_ROOT / "logs"
# Parquet snapshot of the database for the app (written by the export job).
DATA_DIR = Path(os.getenv("NBA_DATA_DIR", PROJECT_ROOT / "data"))

# Override any of these with environment variables, e.g. NBA_SQL_SERVER=localhost\SQLEXPRESS
SERVER = os.getenv("NBA_SQL_SERVER", "localhost")
DATABASE = os.getenv("NBA_SQL_DATABASE", "nba")
DRIVER = os.getenv("NBA_SQL_DRIVER", "ODBC Driver 17 for SQL Server")

# stats.nba.com throttles aggressive clients, so every request is spaced out and retried.
REQUEST_DELAY_SECONDS = 0.6
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 5

SEASON_TYPES = ["Regular Season", "Playoffs"]


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "nba_pipeline.log"),
            logging.StreamHandler(),
        ],
    )
