import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = "<BUCKET_NAME>"   # must be globally unique
REGION = "ap-southeast-2"                      # Sydney

def create_bucket(bucket_name: str, region: str) -> None:
    s3 = boto3.client("s3", region_name=region)

    try:
        # For regions other than us-east-1, you must pass CreateBucketConfiguration
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region},
        )
        print(f"✅ Bucket created: s3://{bucket_name} (region: {region})")

    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        print(f"❌ Failed ({code}): {msg}")
        raise

if __name__ == "__main__":
    create_bucket(BUCKET_NAME, REGION)
