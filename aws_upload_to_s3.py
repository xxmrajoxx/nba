import os
import boto3
from botocore.exceptions import ClientError

# CHANGE THIS
BUCKET_NAME = "<BUCKET_NAME>"   # must be globally unique

# Local folder containing CSVs
LOCAL_FOLDER = "player_game_logs"

# S3 folder (prefix)
S3_PREFIX = "nba/player_game_logs/"

def upload_folder(bucket_name: str, local_folder: str, s3_prefix: str) -> None:
    s3 = boto3.client("s3")

    if not os.path.isdir(local_folder):
        raise NotADirectoryError(f"Folder not found: {local_folder}")

    for filename in os.listdir(local_folder):
        local_path = os.path.join(local_folder, filename)

        # Skip directories
        if not os.path.isfile(local_path):
            continue

        s3_key = f"{s3_prefix}{filename}"

        try:
            s3.upload_file(local_path, bucket_name, s3_key)
            print(f"Uploaded: {local_path}")
            print(f"s3://{bucket_name}/{s3_key}")
        except ClientError as e:
            print(f"Failed to upload {filename}")
            raise e

    print("All files uploaded successfully.")


if __name__ == "__main__":
    upload_folder(BUCKET_NAME, LOCAL_FOLDER, S3_PREFIX)
