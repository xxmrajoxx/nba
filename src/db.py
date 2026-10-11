import logging
import re
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import config

logger = logging.getLogger(__name__)


@lru_cache
def get_engine(database: str = config.DATABASE) -> Engine:
    connection_string = (
        f"mssql+pyodbc://@{config.SERVER}/{database}"
        f"?driver={config.DRIVER.replace(' ', '+')}"
        "&trusted_connection=yes"
    )
    return create_engine(connection_string, fast_executemany=True)


def init_db() -> None:
    """Create the database if it is missing, then run every script in sql/ in name order."""
    master = get_engine("master").execution_options(isolation_level="AUTOCOMMIT")
    with master.connect() as conn:
        conn.exec_driver_sql(f"IF DB_ID(N'{config.DATABASE}') IS NULL CREATE DATABASE [{config.DATABASE}]")
    logger.info(f"Database {config.DATABASE} is ready")

    for path in sorted(config.SQL_DIR.glob("*.sql")):
        # GO is a batch separator understood by SSMS/sqlcmd, not by SQL Server itself.
        batches = re.split(r"^\s*GO\s*$", path.read_text(), flags=re.MULTILINE | re.IGNORECASE)
        with get_engine().begin() as conn:
            for batch in batches:
                if batch.strip():
                    conn.exec_driver_sql(batch)
        logger.info(f"Ran {path.name}")


def upsert(df: pd.DataFrame, table: str, keys: list, schema: str = "dbo") -> int:
    """Insert new rows and update existing ones, matching on `keys`.

    The DataFrame is bulk-loaded into stg.<table> and then MERGEd into the target, all in
    one transaction, so a job can be re-run any number of times without creating duplicates.
    Only the columns present in the DataFrame are touched.
    """
    if df.empty:
        return 0

    columns = list(df.columns)
    column_list = ", ".join(f"[{c}]" for c in columns)
    on_clause = " AND ".join(f"t.[{k}] = s.[{k}]" for k in keys)
    set_clause = ", ".join(f"t.[{c}] = s.[{c}]" for c in columns if c not in keys)
    insert_values = ", ".join(f"s.[{c}]" for c in columns)

    with get_engine().begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS stg.[{table}]"))
        # Copy the target's column types so staging never has to guess them.
        conn.execute(text(f"SELECT TOP 0 {column_list} INTO stg.[{table}] FROM {schema}.[{table}]"))
        df.to_sql(table, conn, schema="stg", if_exists="append", index=False, chunksize=10_000)
        conn.execute(text(f"""
            MERGE {schema}.[{table}] AS t
            USING stg.[{table}] AS s ON {on_clause}
            WHEN MATCHED THEN
                UPDATE SET {set_clause}, t.updated_at = SYSUTCDATETIME()
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ({column_list}) VALUES ({insert_values});
        """))

    logger.info(f"Upserted {len(df)} rows into {schema}.{table}")
    return len(df)


def read_sql(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn)


def run_tracked(job_name: str, job) -> int:
    """Run a job function and record the outcome in etl.job_run."""
    engine = get_engine()
    with engine.begin() as conn:
        run_id = conn.execute(
            text("INSERT INTO etl.job_run (job_name, status) OUTPUT INSERTED.run_id VALUES (:job, 'running')"),
            {"job": job_name},
        ).scalar_one()

    finish = text("""
        UPDATE etl.job_run
        SET finished_at = SYSUTCDATETIME(), status = :status, rows_loaded = :rows, message = :message
        WHERE run_id = :run_id
    """)
    logger.info(f"Job {job_name} started (run_id={run_id})")
    try:
        rows = job()
    except Exception as e:
        with engine.begin() as conn:
            conn.execute(finish, {"status": "failed", "rows": None, "message": str(e)[:4000], "run_id": run_id})
        logger.exception(f"Job {job_name} failed")
        raise

    with engine.begin() as conn:
        conn.execute(finish, {"status": "success", "rows": rows, "message": None, "run_id": run_id})
    logger.info(f"Job {job_name} finished: {rows} rows")
    return rows
