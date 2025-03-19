import json
import ibm_boto3
from ibm_botocore.client import Config
from ibm_botocore.exceptions import ClientError

# Function to load COS credentials from a JSON file
def load_cos_credentials(file_path):
    try:
        with open(file_path, 'r') as file:
            credentials = json.load(file)
        return credentials
    except Exception as e:
        return {"error": f"Error loading credentials from {file_path}: {str(e)}"}

# Load credentials for Main Server and Backup Server
main_server_cos_credentials = load_cos_credentials("main_server_credentials.json")
backup_server_cos_credentials = load_cos_credentials("backup_server_credentials.json")

# Validate credentials
if "error" in main_server_cos_credentials or "error" in backup_server_cos_credentials:
    print(json.dumps({"status": "error", "message": "Failed to load credentials"}))
    exit(1)

# Function to initialize IBM COS client
def init_cos_client(credentials):
    return ibm_boto3.client(
        "s3",
        ibm_api_key_id=credentials["api_key"],
        ibm_service_instance_id=credentials["service_instance_id"],
        config=Config(signature_version="oauth"),
        endpoint_url=credentials["endpoint"]
    )

# Initialize COS clients
main_cos_client = init_cos_client(main_server_cos_credentials)
backup_cos_client = init_cos_client(backup_server_cos_credentials)

# Function to check if a bucket exists
def is_bucket_available(cos_client, bucket_name):
    try:
        cos_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError:
        return False

# Function to check storage usage in a bucket
def get_storage_size(cos_client, bucket_name):
    try:
        response = cos_client.list_objects_v2(Bucket=bucket_name)
        total_size = sum(obj["Size"] for obj in response.get("Contents", [])) if "Contents" in response else 0
        return total_size / (1024**2)  # Convert to MB
    except Exception:
        return None

# Get bucket names
main_bucket_name = main_server_cos_credentials.get("bucket_name", "YOUR_MAIN_BUCKET")
backup_bucket_name = backup_server_cos_credentials.get("bucket_name", "YOUR_BACKUP_BUCKET")

# Check storage details
storage_details = {
    "main_bucket": {
        "exists": is_bucket_available(main_cos_client, main_bucket_name),
        "storage_mb": get_storage_size(main_cos_client, main_bucket_name)
    },
    "backup_bucket": {
        "exists": is_bucket_available(backup_cos_client, backup_bucket_name),
        "storage_mb": get_storage_size(backup_cos_client, backup_bucket_name)
    }
}
# Print JSON output
print(json.dumps(storage_details))
