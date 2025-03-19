import os
import time
import json
import ibm_boto3
from ibm_botocore.client import Config
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Timer

# Load IBM Cloud Object Storage credentials from JSON files
def load_cos_credentials(file_path):
    try:
        with open(file_path, 'r') as file:
            credentials = json.load(file)
        return credentials
    except Exception as e:
        print(f"Error loading credentials from {file_path}: {e}")
        return None

# Load credentials for Main Server from the JSON file
main_server_cos_credentials = load_cos_credentials("main_server_credentials.json")

if not main_server_cos_credentials:
    print("Error loading credentials for Main Server. Exiting.")
    exit(1)

# Create resource client for Main Server
main_server_cos = ibm_boto3.client('s3',
                                   ibm_api_key_id=main_server_cos_credentials['api_key'],
                                   ibm_service_instance_id=main_server_cos_credentials['service_instance_id'],
                                   config=Config(signature_version='oauth'),
                                   endpoint_url=main_server_cos_credentials['endpoint'])

# Function to upload a file to Main Server's bucket
def upload_file_to_main_server(file_name):
    try:
        print(f"Uploading: {file_name}")
        with open(file_name, 'rb') as file_data:
            main_server_cos.upload_fileobj(file_data, main_server_cos_credentials['bucket_name'], file_name)
        print(f"Successfully uploaded: {file_name}")
    except Exception as e:
        print(f"Error uploading {file_name} to main server: {str(e)}")

# Function to upload an entire directory
def upload_directory_to_main_server(directory_path):
    try:
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                upload_file_to_main_server(file_path)
    except Exception as e:
        print(f"Error uploading directory {directory_path}: {str(e)}")

# Dictionary to store timers for modified files
upload_timers = {}

# Debounce delay in seconds
debounce_delay = 2

# Watchdog event handler class
class MyHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            print(f"Detected modification in directory: {event.src_path}")
            upload_directory_to_main_server(event.src_path)
            return

        file_path = event.src_path
        print(f"Detected change in file: {file_path}")
        
        # Cancel previous timer if exists
        if file_path in upload_timers:
            upload_timers[file_path].cancel()
        
        # Start a new timer to delay upload
        upload_timers[file_path] = Timer(debounce_delay, upload_file_to_main_server, [file_path])
        upload_timers[file_path].start()

    def on_created(self, event):
        if event.is_directory:
            print(f"New directory created: {event.src_path}")
            upload_directory_to_main_server(event.src_path)
            return
        print(f"New file created: {event.src_path}")
        upload_file_to_main_server(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        print(f"File deleted: {event.src_path}")

# Path to the folder to monitor
folder_to_monitor = "upload"

# Setup watchdog observer to monitor the folder
event_handler = MyHandler()
observer = Observer()
observer.schedule(event_handler, path=folder_to_monitor, recursive=True)
observer.start()

print(f"Monitoring changes in folder: {folder_to_monitor}")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
    print("Monitoring stopped.")
except Exception as e:
    observer.stop()
    print(f"Error: {str(e)}")