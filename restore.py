import os
import ibm_boto3
from ibm_botocore.client import Config
import json
from datetime import datetime, timedelta

# Directory to store restored files
RESTORE_DIRECTORY = "restored"
# Ensure the directory exists
os.makedirs(RESTORE_DIRECTORY, exist_ok=True)
# Load IBM Cloud Object Storage credentials from JSON files
def load_cos_credentials(file_path):
    try:
        with open(file_path, 'r') as file:
            credentials = json.load(file)
        return credentials
    except Exception as e:
        print(f"Error loading credentials from {file_path}: {e}")
        return None

# Load the credentials for both servers
main_server_cos_credentials = load_cos_credentials("main_server_credentials.json")
backup_server_cos_credentials = load_cos_credentials("backup_server_credentials.json")

if not main_server_cos_credentials or not backup_server_cos_credentials:
    print("Error loading credentials. Exiting.")
    exit(1)

# Extract bucket names, defaulting to empty strings if not provided
main_bucket_name = main_server_cos_credentials.get('bucket_name', '')
backup_bucket_name = backup_server_cos_credentials.get('bucket_name', '')

# Create resource clients for both servers
main_server_cos = ibm_boto3.client('s3',
                                   ibm_api_key_id=main_server_cos_credentials['api_key'],
                                   ibm_service_instance_id=main_server_cos_credentials['service_instance_id'],
                                   config=Config(signature_version='oauth'),
                                   endpoint_url=main_server_cos_credentials['endpoint'])

backup_server_cos = ibm_boto3.client('s3',
                                     ibm_api_key_id=backup_server_cos_credentials['api_key'],
                                     ibm_service_instance_id=backup_server_cos_credentials['service_instance_id'],
                                     config=Config(signature_version='oauth'),
                                     endpoint_url=backup_server_cos_credentials['endpoint'])

# Function to check bucket availability
def is_bucket_available(cos_client, bucket_name):
    try:
        cos_client.head_bucket(Bucket=bucket_name)
        return True
    except Exception:
        return False

# Restore function
def restore_files(cos_client, bucket_name, restore_all):
    try:
        print(f"Using bucket name: {bucket_name}")

        # List all objects in the bucket
        response = cos_client.list_objects_v2(Bucket=bucket_name)
        
        if 'Contents' not in response:
            print("No files found in the bucket.")
            return

        now = datetime.utcnow()
        restore_time_limit = now - timedelta(minutes=20)
        
        for obj in response['Contents']:
            last_modified = obj['LastModified'].replace(tzinfo=None)  # Remove timezone for comparison
            object_key = obj['Key']

            # Restore based on user choice
            if restore_all or last_modified >= restore_time_limit:
                print(f"Restoring file: {object_key}")

                # Full path for the restored file
                download_path = os.path.join(RESTORE_DIRECTORY, object_key)

                # Ensure subdirectories are created if needed
                os.makedirs(os.path.dirname(download_path), exist_ok=True)

                # Download the file
                cos_client.download_file(bucket_name, object_key, download_path)
                print(f"File '{object_key}' restored to '{download_path}' successfully.")
    except Exception as e:
        print(f"An error occurred during the restore process: {e}")

# Main function
def main():
    # Check which bucket is available
    bucket_name = None
    cos_client = None

    # Check mainstorage first
    if main_bucket_name and is_bucket_available(main_server_cos, main_bucket_name):
        bucket_name = main_bucket_name
        cos_client = main_server_cos
    elif backup_bucket_name and is_bucket_available(backup_server_cos, backup_bucket_name):
        bucket_name = backup_bucket_name
        cos_client = backup_server_cos

    if not bucket_name:
        print("No available bucket found. Exiting.")
        exit(1)

    # Ask user whether to restore all or only last 20 minutes
    choice = input("Do you want to restore all files or only those modified in the last 20 minutes? (all/last20): ").strip().lower()
    if choice not in ["all", "last20"]:
        print("Invalid choice. Exiting.")
        exit(1)

    restore_all = choice == "all"
    restore_files(cos_client, bucket_name, restore_all)

if __name__ == "__main__":
    main()