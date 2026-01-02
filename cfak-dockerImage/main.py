import boto3
import os
import time
import sys

# --- CONFIGURATION & INITIALIZATION ---
# These variables are injected by Lambda or CloudFormation
TARGET_INSTANCE_ID = os.environ.get('TARGET_INSTANCE_ID')
BUCKET_NAME = os.environ.get('TARGET_BUCKET')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'C-FAK')

# AWS Clients
ec2 = boto3.client('ec2')
ssm = boto3.client('ssm')
s3 = boto3.client('s3')

def log(msg):
    """Simple logging with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def upload_tools_to_s3():
    """Uploads local Docker binaries to the S3 Bucket for the victim to download."""
    log(f"Uploading forensic tools to s3://{BUCKET_NAME}/tools/ ...")
    
    # Upload AVML (Linux)
    try:
        s3.upload_file('/app/bin/avml', BUCKET_NAME, 'tools/avml')
        log("-> AVML uploaded successfully.")
    except Exception as e:
        log(f"Error uploading AVML: {e}")

    # Upload WinPMEM (Windows)
    try:
        s3.upload_file('/app/bin/winpmem.exe', BUCKET_NAME, 'tools/winpmem.exe')
        log("-> WinPMEM uploaded successfully.")
    except Exception as e:
        log(f"Error uploading WinPMEM: {e}")

def get_instance_platform(instance_id):
    """Detects if the instance is Linux or Windows."""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        # AWS reports 'windows' in Platform; if empty, it is usually Linux
        platform = instance.get('Platform', 'linux')
        log(f"Instance {instance_id} detected as: {platform}")
        return platform
    except Exception as e:
        log(f"Error retrieving instance info: {e}")
        return 'unknown'

def send_ssm_command(instance_id, commands, document_name):
    """Sends commands to the instance and waits for the result."""
    log(f"Sending commands to {instance_id}...")
    
    try:
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName=document_name,
            Parameters={'commands': commands},
            Comment=f'{PROJECT_NAME} Forensic Acquisition'
        )
        command_id = response['Command']['CommandId']
        
        # Wait for completion (Polling)
        log(f"Command sent (ID: {command_id}). Waiting for execution...")
        while True:
            time.sleep(5)
            output = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            status = output['Status']
            
            if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                log(f"Execution finished with status: {status}")
                if status != 'Success':
                    log(f"ERROR OUTPUT: {output.get('StandardErrorContent')}")
                else:
                    log("Command executed successfully.")
                break
                
    except Exception as e:
        log(f"Critical failure sending SSM: {e}")

def acquire_linux(instance_id):
    # Bash commands for Linux
    # 1. Download AVML from S3
    # 2. Grant execution permissions
    # 3. Execute memory dump
    # 4. Upload evidence to S3
    # 5. Cleanup
    
    mem_filename = f"{instance_id}_memory.lime"
    
    cmds = [
        f"aws s3 cp s3://{BUCKET_NAME}/tools/avml /tmp/avml",
        "chmod +x /tmp/avml",
        f"echo 'Starting RAM capture with AVML...'",
        f"/tmp/avml /tmp/{mem_filename}",
        f"echo 'Uploading evidence to S3...'",
        f"aws s3 cp /tmp/{mem_filename} s3://{BUCKET_NAME}/evidence/{mem_filename}",
        "rm /tmp/avml",
        f"rm /tmp/{mem_filename}"
    ]
    
    send_ssm_command(instance_id, cmds, "AWS-RunShellScript")

def acquire_windows(instance_id):
    # PowerShell commands for Windows
    mem_filename = f"{instance_id}_memory.raw"
    
    cmds = [
        f"aws s3 cp s3://{BUCKET_NAME}/tools/winpmem.exe C:\\Windows\\Temp\\winpmem.exe",
        f"Write-Host 'Starting RAM capture with WinPMEM...'",
        # WinPMEM requires driver load, output in raw format
        f"C:\\Windows\\Temp\\winpmem.exe -o C:\\Windows\\Temp\\{mem_filename}",
        f"Write-Host 'Uploading evidence to S3...'",
        f"aws s3 cp C:\\Windows\\Temp\\{mem_filename} s3://{BUCKET_NAME}/evidence/{mem_filename}",
        "Remove-Item C:\\Windows\\Temp\\winpmem.exe",
        f"Remove-Item C:\\Windows\\Temp\\{mem_filename}"
    ]
    
    send_ssm_command(instance_id, cmds, "AWS-RunPowerShellScript")

def main():
    log("=== C-FAK FORENSIC CONTROLLER STARTED ===")
    
    if not TARGET_INSTANCE_ID or not BUCKET_NAME:
        log("ERROR: Missing environment variables (TARGET_INSTANCE_ID or TARGET_BUCKET).")
        sys.exit(1)

    # 1. Prepare tools in the cloud
    upload_tools_to_s3()

    # 2. Identify Target
    platform = get_instance_platform(TARGET_INSTANCE_ID)

    # 3. Execute Acquisition
    if platform == 'windows':
        acquire_windows(TARGET_INSTANCE_ID)
    elif platform == 'linux':
        acquire_linux(TARGET_INSTANCE_ID)
    else:
        log("Unsupported or unknown operating system. Aborting.")

    log("=== OPERATION FINISHED ===")

if __name__ == "__main__":
    main()