import os
import logging
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def upload_folder_csvs_to_s3(
    bucket_name: str,
    local_folder: str,
    s3_prefix: str = "",
    region_name: str | None = None,
) -> None:
    """
    Upload all .csv files from local_folder to s3://bucket_name/s3_prefix/
    """
    folder = Path(local_folder)

    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Local folder does not exist or is not a directory: {local_folder}")

    # Normalize prefix (no leading '/', ensure trailing '/' if not empty)
    s3_prefix = s3_prefix.strip().lstrip("/")
    if s3_prefix and not s3_prefix.endswith("/"):
        s3_prefix += "/"

    session = boto3.Session(region_name=region_name) if region_name else boto3.Session()
    s3 = session.client("s3")

    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        logging.warning(f"No CSV files found in: {local_folder}")
        return

    uploaded = 0
    failed = 0

    for file_path in csv_files:
        s3_key = f"{s3_prefix}{file_path.name}"

        try:
            logging.info(f"Uploading {file_path} -> s3://{bucket_name}/{s3_key}")
            s3.upload_file(str(file_path), bucket_name, s3_key)
            uploaded += 1
        except (ClientError, NoCredentialsError) as e:
            failed += 1
            logging.error(f"FAILED upload for {file_path.name}: {e}")

    logging.info(f"Done. Uploaded={uploaded}, Failed={failed}")


if __name__ == "__main__":
    # ✅ EDIT THESE
    BUCKET_NAME = "ajo-nba-player-stats"
    LOCAL_FOLDER = "game_logs"  # e.g. the folder where those CSVs are
    S3_PREFIX = "nba/player_game_logs"  # optional "folder" in S3 (can be "")

    upload_folder_csvs_to_s3(
        bucket_name=BUCKET_NAME,
        local_folder=LOCAL_FOLDER,
        s3_prefix=S3_PREFIX,
        region_name="ap-southeast-2",  # Sydney (optional but recommended)
    )
