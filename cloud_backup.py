import subprocess
import json
import asyncio
import telegram
import smtplib
import threading
import queue
import sys
import logging
from datetime import datetime
# Load Telegram configuration


# Load Email configuration
with open("email.json", "r") as email_file:
    email_config = json.load(email_file)


# Telegram Bot configuration
TOKEN = ""
CHAT_ID = ["CHAT_ID_1","CHAT_ID 2","CHAT_ID 3","CHAT_ID 4"]  # Now holds multiple chat IDs

# Email configuration
EMAIL = email_config["email_address"]
RECEIVER_EMAILS = email_config["receiver_emails"]
EMAIL_PASSWORD = email_config["email_password"]

total_main_bucket_storage_mb = 100  # Example total capacity for the main bucket in MB
total_backup_bucket_storage_mb = 100  # Example total capacity for the backup bucket in MB


with open("restore_triger.json", "r") as restore_file:
    restore_config = json.load(restore_file)

restore_triger = restore_config["restore"]
backup_to_main_trigrer=restore_triger
if restore_triger == 1:
    subprocess.run(["python", "restore.py"], text=True)
else:
    print("Restore not required")

# Function to calculate the percentage of storage used
def calculate_percentage(used_storage_mb, total_storage_mb):
    if used_storage_mb is None or total_storage_mb == 0:
        return 0  # Avoid division by zero or None value
    return (used_storage_mb / total_storage_mb) * 100

# Run buckut_stroage_check.py and capture output
try:
    result = subprocess.run(["python", "buckut_stroage_check.py"], capture_output=True, text=True)
    output = result.stdout.strip()

    # Parse JSON response
    storage_data = json.loads(output)
    # Check for errors
    if "status" in storage_data and storage_data["status"] == "error":
        print(f"Error: {storage_data['message']}")
    else:
        # Main Bucket Usage and Percentage
        print(f"Main Bucket Available: {storage_data['main_bucket']['exists']}")
        main_bucket_used = storage_data['main_bucket']['storage_mb']
        if main_bucket_used is not None:
            main_bucket_percentage = calculate_percentage(main_bucket_used, total_main_bucket_storage_mb)
            print(f"Main Storage Used: {main_bucket_used:.2f} MB ({main_bucket_percentage:.2f}%)")
        else:
            print("Main Storage Used: N/A")

        # Backup Bucket Usage and Percentage
        print(f"Backup Bucket Available: {storage_data['backup_bucket']['exists']}")
        backup_bucket_used = storage_data['backup_bucket']['storage_mb']
        if backup_bucket_used is not None:
            backup_bucket_percentage = calculate_percentage(backup_bucket_used, total_backup_bucket_storage_mb)
            print(f"Backup Storage Used: {backup_bucket_used:.2f} MB ({backup_bucket_percentage:.2f}%)")
        else:
            print("Backup Storage Used: N/A")
        

except Exception as e:
    print(f"Error executing script: {e}")

# Return the storage values for alerting
def get_storage_data():
    storage_info = {}

    # Main bucket check
    if storage_data['main_bucket'].get('exists') is True:
        main_storage_used = storage_data['main_bucket'].get('storage_mb')
        if main_storage_used is not None:  # Only calculate if storage_mb is not None
            main_bucket_percentage = calculate_percentage(main_storage_used, total_main_bucket_storage_mb)
            # Only format if the percentage is valid
            if main_bucket_percentage is not None:
                storage_info['main_storage'] = f"{main_bucket_percentage:.2f}"
            else:
                storage_info['main_storage'] = "0.00"  # Default to 0 if None

    # Backup bucket check
    if storage_data['backup_bucket'].get('exists') is True:
        backup_storage_used = storage_data['backup_bucket'].get('storage_mb')
        if backup_storage_used is not None:  # Only calculate if storage_mb is not None
            backup_bucket_percentage = calculate_percentage(backup_storage_used, total_backup_bucket_storage_mb)
            # Only format if the percentage is valid
            if backup_bucket_percentage is not None:
                storage_info['backup_storage'] = f"{backup_bucket_percentage:.2f}"
            else:
                storage_info['backup_storage'] = "0.00"  # Default to 0 if None

    return storage_info

# Function to determine the Telegram message based on percentage
def get_telegram_message(percentage, storage_type):
    if percentage >= 95:
        return f"ALERT: Stop Uploading! You have reached 95% or more on the {storage_type} storage."
    elif percentage >= 90:
        return f"ALERT: You have reached 90% on the {storage_type} storage - Take Immediate Action."
    elif percentage >= 80:
        return f"WARNING: You have reached 80% on the {storage_type} storage - Please Check."
    elif percentage >= 70:
        return f"WARNING: You have reached 70% on the {storage_type} storage - Keep an eye on the progress."

# Async function to send Telegram notifications
async def send_alert_telegram(storage_data):
    bot = telegram.Bot(token=TOKEN)
    telegram_status = {}

    for storage_type, percentage in storage_data.items():
        percentage_value = float(percentage)

        if percentage_value < 70:
            telegram_status[storage_type] = "telegram_not_sent"
            continue

        message = get_telegram_message(percentage_value, storage_type)
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            telegram_status[storage_type] = "telegram_sent"
        except Exception as e:
            telegram_status[storage_type] = "telegram_error"

    with open("alert_telegram.json", "w") as json_file:
        json.dump({"telegram_status": telegram_status}, json_file, indent=4)

# Function to send alert emails
def send_alert_email(storage_data):
    email_status = {}

    for storage_type, percentage in storage_data.items():
        percentage_value = float(percentage)

        if percentage_value < 70:
            email_status[storage_type] = "email_not_sent"
            continue

        subject = f"IBM Project : {storage_type.capitalize()} Storage Alert"
        email_body = f"Subject: {subject}\n\n{get_telegram_message(percentage_value, storage_type)}"

        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL, EMAIL_PASSWORD)

            for receiver_email in RECEIVER_EMAILS:
                server.sendmail(EMAIL, receiver_email, email_body)
            
            email_status[storage_type] = "email_sent"
        except Exception as e:
            email_status[storage_type] = "email_error"
        finally:
            server.quit()

    with open("alert_storage_email.json", "w") as json_file:
        json.dump({"email_status": email_status}, json_file)

main_bucket_storage = None
backup_bucket_storage = None
restore=None



def uplode_storage():
    global main_bucket_storage, backup_bucket_storage,restore,backup_to_main_trigrer
    print(f"main_bucket_storage: {main_bucket_storage}, backup_bucket_storage: {backup_bucket_storage}, restore :{restore}, backup_to_main_trigrer:{backup_to_main_trigrer}")

    with open("restore_triger.json", "w") as json_file:
        json.dump({"restore": restore}, json_file)


    if main_bucket_storage == 0 and backup_bucket_storage == 0:
        print("Both bucket are not found")
        exit()

    elif main_bucket_storage == 0:
        print("Shift backup bucket no main bucket")
        auto_upload_backup_to_storage()
        

    elif backup_bucket_storage == 0:
        print("No backup bucket, continue Main backup")
        auto_upload_main_to_storage()

    elif main_bucket_storage == 1 and backup_bucket_storage == 1:
        print("Both bucket are full")
        exit()

    elif main_bucket_storage == 1:
        print("Main bucket is full")
        auto_upload_backup_to_storage()

    elif backup_bucket_storage == 1:
        print("Backup bucket is full")
        auto_upload_main_to_storage()

    elif main_bucket_storage == 2 and backup_bucket_storage == 2:
        print("Runing normaly")
        auto_upload_monitoring()


def auto_shift_bucket(storage_data):
    global main_bucket_storage, backup_bucket_storage,restore,backup_to_main_trigrer 
    try:
        # Check if the keys 'main_storage' and 'backup_storage' exist in the data
        if 'main_storage' not in storage_data:
            subject = get_email_subject("main_storage_not_found")
            message = get_email_message("main_storage_not_found")
            send_email(subject, message)
            asyncio.run(send_telegram_message(message))
            main_bucket_storage = 0  # ✅ Corrected variable name
            restore=1
            raise KeyError("'main_storage' not found in storage_data")

        if 'backup_storage' not in storage_data:
            subject = get_email_subject("backup_storage_not_found")
            message = get_email_message("backup_storage_not_found")
            send_email(subject, message)
            asyncio.run(send_telegram_message(message))
            backup_bucket_storage = 0  # ✅ Corrected variable name
            restore=1
            raise KeyError("'backup_storage' not found in storage_data")

        # Extract storage percentages
        main_storage_percentage = float(storage_data['main_storage'])
        backup_storage_percentage = float(storage_data['backup_storage'])

        # Handle main storage condition
        if main_storage_percentage >= 95:  
            print(f"Main bucket is full at {main_storage_percentage:.2f}%. Shifting storage to backup bucket.")
            subject = get_email_subject("main_bucket_full")
            message = get_email_message("main_bucket_full")
            send_email(subject, message)
            asyncio.run(send_telegram_message(message))
            main_bucket_storage = 1  # ✅ Corrected variable name
                    
            if backup_storage_percentage < 95:  
                print(f"Backup bucket has space ({backup_storage_percentage:.2f}%). Proceeding to shift storage.")
            else:
                subject = get_email_subject("backup_bucket_full")  # ✅ Fixed assignment
                message = get_email_message("backup_bucket_full")
                send_email(subject, message)
                asyncio.run(send_telegram_message(message))
                backup_bucket_storage = 1  # ✅ Corrected variable name
                print(f"Backup bucket is also full at {backup_storage_percentage:.2f}%. Storage cannot be shifted.")
        else:
            main_bucket_storage = 2  # ✅ Corrected variable name
            print(f"Main bucket has {main_storage_percentage:.2f}% available. No need to shift.")

        # Handle backup storage condition
        if backup_storage_percentage >= 95:
            subject = get_email_subject("backup_bucket_full")  # ✅ Fixed assignment
            message = get_email_message("backup_bucket_full")
            send_email(subject, message)
            asyncio.run(send_telegram_message(message))
            backup_bucket_storage = 1  # ✅ Corrected variable name
            print(f"Backup bucket is full at {backup_storage_percentage:.2f}%. Stop uploading.")
        else:
            backup_bucket_storage = 2  # ✅ Corrected variable name
            print(f"Backup bucket has {backup_storage_percentage:.2f}% available. Continue uploading if needed.")

    except Exception as e:
        print(f"Error in auto_shift_bucket: {e}")


def send_email(subject, message):
    email_body = f"Subject: {subject}\n\n{message}"

    try:
        # Connect to Gmail's SMTP server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()  # Start TLS encryption
        
        # Log in to your email account
        server.login(EMAIL, EMAIL_PASSWORD)  # Replace with your email password or app password
        
        # Send the email to all recipients in the list
        for receiver_email in RECEIVER_EMAILS:
            server.sendmail(EMAIL, receiver_email, email_body)
        
        print("Error Email sent successfully!")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Quit the server connection
        server.quit()
def get_email_subject(condition):
    if condition == "main_bucket_full":
        return f"Critical: Main storage bucket is full"
    elif condition =="backup_bucket_full":
        return f"Warning: Backup storage bucket is full"
    elif condition == "main_storage_not_found":
        return "Warning: Main Storage Unavailable - Using Backup Storage"
    elif condition == "backup_storage_not_found":
        return "Critical: Backup Storage Not Available"
    elif condition == "main_storage_and_backup_storage_not_found":
        return "Critical: Both Main and Backup Storage Unavailable"
# Function to generate email message based on the condition
def get_email_message(condition):
    if condition == "main_bucket_full":
        return f"CRITICAL ERROR: The main storage bucket is full. All backups are being redirected to the backup bucket."
    elif condition =="backup_bucket_full":
        return f"WARNING: The backup storage bucket is full. Please clean up the bucket or increase."
    elif condition == "main_storage_not_found":
        return "WARNING: Main storage is unavailable. Uploads will be redirected to backup storage."
    elif condition == "backup_storage_not_found":
        return "CRITICAL ERROR: Backup storage is unavailable. Please resolve the issue immediately."
    elif condition == "main_storage_and_backup_storage_not_found":
        return "CRITICAL ERROR: Both main and backup storage are unavailable. Please resolve the issue immediately."

async def send_telegram_message(message):
    bot = telegram.Bot(token=TOKEN)
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
        print("Telegram message sent successfully!")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")


        print(f"Failed to execute {script}: {e}")

# Setup logging for better visibility
logging.basicConfig(filename='script_error.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run_script(script, output_queue):
    """Runs a script and continuously adds output to the queue."""
    try:
        logging.info(f"Starting to run script: {script}")
        print(f"Running script: {script}")  # Print script name when it starts
        
        process = subprocess.Popen(
            ["python", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        # Continuously read stdout from the process
        for line in process.stdout:
            print(f"{script}: {line.strip()}")  # Debug print for output
            output_queue.put((script, line.strip()))  # Store script name with output
        
        # Collect stderr if there's any error and add to the queue
        error_output = process.stderr.read()
        if error_output:
            print(f"ERROR from {script}: {error_output}")  # Debug print for errors
            output_queue.put((script, f"ERROR: {error_output}"))
            logging.error(f"Error running script {script}: {error_output}")
        
        process.stdout.close()
        process.stderr.close()
        process.wait()  # Ensure the process finishes
        logging.info(f"Finished running script: {script}")
        print(f"Finished running script: {script}")
    except Exception as e:
        output_queue.put((script, f"Error running {script}: {str(e)}"))
        logging.error(f"Exception occurred while running {script}: {str(e)}")
        print(f"Error running {script}: {str(e)}")  # Print error message directly

def dynamic_output_printer(output_queues, json_file):
    """Prints the dynamic output from multiple script queues and stores it in a JSON file."""
    output_data = {script: [] for script in output_queues.keys()}
    
    print("Starting dynamic output printer...")  # Debug print to see if this part is executed

    while any(not q.empty() for q in output_queues.values()):
        for script, q in output_queues.items():
            try:
                output = q.get(timeout=1)
            except queue.Empty:
                output = None
            
            if output is not None:
                print(f"{script:<40} | {output[1]}")  # Debug print for dynamic output
                sys.stdout.flush()
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                output_data[script].append({"timestamp": timestamp, "output": output[1]})
                
                with open(json_file, 'w') as f:
                    json.dump(output_data, f, indent=4)
        
        time.sleep(0.1)  # Prevent CPU overuse

def run_scripts_and_monitor(scripts, json_file):
    """Dynamically runs multiple scripts and monitors their output."""
    logging.info("Starting script execution and monitoring...")
    print("Starting script execution and monitoring...")  # Debug print
    
    output_queues = {script: queue.Queue() for script in scripts}
    
    # Start script execution in separate threads
    threads = []
    for script in scripts:
        print(f"Starting thread for {script}")  # Debug print
        thread = threading.Thread(target=run_script, args=(script, output_queues[script]))
        thread.start()
        threads.append(thread)
    
    # Start dynamic output printer thread
    printer_thread = threading.Thread(target=dynamic_output_printer, args=(output_queues, json_file))
    printer_thread.daemon = True  # Daemon thread exits with main program
    printer_thread.start()
    
    # Wait for all script threads to complete
    for thread in threads:
        thread.join()
    
    logging.info("All scripts have finished execution.")
    print("All scripts have finished execution.")

# Example usage
def auto_upload_monitoring():
    print(f'backup_to_main_trigrer:{backup_to_main_trigrer}')
    if backup_to_main_trigrer == 1:
        print("")
        print("backup_to main.py, only auto_uplode_monitoring_backup_to_main and main_to_backup_10m.py")
        print("")
        scripts = ["backup_to main.py","auto_uplode_monitoring_backup_to_main.py", "main_to_backup_10m.py"]
    else:
        print("")
        print("only auto_uplode_monitoring_backup_to_main and main_to_backup_10m.py")
        print("")
        scripts = ["auto_uplode_monitoring_backup_to_main.py", "main_to_backup_10m.py"]     
    json_file = "output_monitoring.json"
    run_scripts_and_monitor(scripts, json_file)

def auto_upload_backup_to_storage():
    scripts = ["auto_uplode_monitoring_backup_to_backup_stroage.py"]
    json_file = "backup_storage_monitoring.json"
    run_scripts_and_monitor(scripts, json_file)

def auto_upload_main_to_storage():
    scripts = ["auto_uplode_monitoring_main_to_backup_stroage.py"]
    json_file = "main_storage_monitoring.json"
    run_scripts_and_monitor(scripts, json_file)

if __name__ == "__main__":
    storage_data = get_storage_data()
    asyncio.run(send_alert_telegram(storage_data))  # Run Telegram alerts
    send_alert_email(storage_data)
    auto_shift_bucket(storage_data) # Run auto shift bucket functionality
    uplode_storage() # Run upload storage functionality
