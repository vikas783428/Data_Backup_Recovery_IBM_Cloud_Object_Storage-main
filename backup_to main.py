import ibm_boto3
from ibm_botocore.client import Config
import os
import time
import json

# Load IBM Cloud Object Storage credentials from JSON files

def load_cos_credentials(file_path):
    try:
        with open(file_path, 'r') as file:
            credentials = json.load(file)
        return credentials
    except Exception as e:
        print(f"Error loading credentials from {file_path}: {e}")
        return None

# Load the credentials for Main Server and Backup Server
main_server_cos_credentials = load_cos_credentials("main_server_credentials.json")
backup_server_cos_credentials = load_cos_credentials("backup_server_credentials.json")

if not main_server_cos_credentials or not backup_server_cos_credentials:
    print("Error loading credentials. Exiting.")
    exit(1)

# Create resource client for Main Server
main_server_cos = ibm_boto3.client('s3',
                                   ibm_api_key_id=main_server_cos_credentials['api_key'],
                                   ibm_service_instance_id=main_server_cos_credentials['service_instance_id'],
                                   config=Config(signature_version='oauth'),
                                   endpoint_url=main_server_cos_credentials['endpoint'])

# Create resource client for Backup Server
backup_server_cos = ibm_boto3.client('s3',
                                     ibm_api_key_id=backup_server_cos_credentials['api_key'],
                                     ibm_service_instance_id=backup_server_cos_credentials['service_instance_id'],
                                     config=Config(signature_version='oauth'),
                                     endpoint_url=backup_server_cos_credentials['endpoint'])

# Now, Copy the file from Backup Server's bucket to Main Server's bucket
def backup_files():
    try:
        # List objects in the Backup Server bucket
        objects = backup_server_cos.list_objects_v2(Bucket=backup_server_cos_credentials['bucket_name'])
        if 'Contents' in objects:
            print(f"Found {len(objects['Contents'])} objects in the backup server bucket.")

            # List objects in the Main Server bucket to compare timestamps
            main_objects = main_server_cos.list_objects_v2(Bucket=main_server_cos_credentials['bucket_name'])
            main_files = {obj['Key']: obj['LastModified'] for obj in main_objects.get('Contents', [])}

            # Iterate through each object and copy it to the Main Server bucket if new or modified
            for obj in objects['Contents']:
                file_name = obj['Key']
                backup_last_modified = obj['LastModified']
                print(f"Checking: {file_name}")

                # Check if the file exists in the Main Server and if it is newer or not present
                if file_name not in main_files or backup_last_modified > main_files[file_name]:
                    print(f"Backing up: {file_name}")

                    try:
                        # Copy object from Backup Server bucket to Main Server bucket
                        copy_source = {'Bucket': backup_server_cos_credentials['bucket_name'], 'Key': file_name}
                        main_server_cos.copy_object(CopySource=copy_source,
                                                     Bucket=main_server_cos_credentials['bucket_name'],
                                                     Key=file_name)
                        print(f"Successfully backed up: {file_name}")
                    except Exception as e:
                        print(f"Error backing up {file_name}: {str(e)}")
                else:
                    print(f"No need to back up (unchanged): {file_name}")
        else:
            print("No objects found in the backup server bucket.")
    except Exception as e:
        print(f"Error listing objects from the backup server bucket: {str(e)}")

# Perform the backup once
backup_files()  # Perform the backup one time
