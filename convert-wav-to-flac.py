"@author: Andrew Martin, 2024"

import os
import subprocess
import shutil
import csv
from datetime import datetime
import ctypes
import json

def load_config(filename):
    """Load configuration from JSON file."""
    with open(filename, 'r') as f:
        config = json.load(f)
    return config

def log_failure(file_name, timestamp, user, drive, directory, csv_file):
    """Log failure details to a CSV file."""
    drive_name = get_drive_name(drive)
    csv_file = os.path.join(os.path.dirname(__file__), csv_file)

    with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([file_name, timestamp, user, drive_name, directory])

def get_drive_name(drive):
    """Retrieve drive name using Windows API."""
    try:
        if os.name == 'nt':
            drive = os.path.splitdrive(drive)[0] + '\\'
            volume_name = ctypes.create_unicode_buffer(1024)
            ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive),
                volume_name,
                ctypes.sizeof(volume_name),
                None,
                None,
                None,
                None,
                0
            )
            return volume_name.value
    except Exception as e:
        print(f"Error retrieving drive name for {drive}: {e}")
    return drive

def get_wav_channels(input_file_path):
    """Get number of channels in a WAV file."""
    try:
        ffprobe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=channels',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file_path
        ]
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
        return int(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f'Failed to get channel count for {input_file_path}: {e}')
    return 0

def convert_wav_to_flac(input_file_path, output_file_path):
    """Convert WAV file to FLAC."""
    try:
        channels = get_wav_channels(input_file_path)

        ffmpeg_cmd = [
            'ffmpeg', 
            '-i', input_file_path, 
            '-c:a', 'flac', 
            '-compression_level', '5',  # Adjust compression level if needed
            '-ac', str(channels),  # Set number of output channels dynamically
            output_file_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        print(f'Converted {input_file_path} to FLAC with {channels} channels')
    except subprocess.CalledProcessError as e:
        print(f'Failed to convert {input_file_path} to FLAC: {e.stderr}')

def copy_file(input_file_path, output_file_path, csv_file):
    """Copy file from source to destination."""
    try:
        with open(input_file_path, 'rb') as src, open(output_file_path, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        print(f'Copied {input_file_path} to {output_file_path}')
    except IOError as e:
        print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = os.getlogin()
        drive, directory = os.path.splitdrive(input_file_path)
        log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)

def copy_directory(source, destination, csv_file):
    """Recursively copy directory from source to destination."""
    try:
        os.makedirs(destination, exist_ok=True)
    except OSError as e:
        print(f"Failed to create directory {destination}: {e}")
        return

    drive_name = get_drive_name(source)
    drive_folder = os.path.join(destination, drive_name)
    try:
        os.makedirs(drive_folder, exist_ok=True)
    except OSError as e:
        print(f"Failed to create drive folder {drive_folder}: {e}")
        return

    for root, dirs, files in os.walk(source):
        # Exclude system directories like "System Volume Information"
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for dir_name in dirs:
            source_dir_path = os.path.join(root, dir_name)
            relative_dir_path = os.path.relpath(source_dir_path, source)
            destination_dir_path = os.path.join(drive_folder, relative_dir_path)
            os.makedirs(destination_dir_path, exist_ok=True)

        for file in files:
            input_file_path = os.path.join(root, file)
            relative_file_path = os.path.relpath(input_file_path, source)
            output_file_path = os.path.join(drive_folder, relative_file_path)

            if file.lower().endswith('.wav'):
                try:
                    convert_wav_to_flac(input_file_path, os.path.splitext(output_file_path)[0] + '.flac')
                except subprocess.CalledProcessError as e:
                    print(f'Failed to convert {input_file_path} to FLAC: {e}')
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user = os.getlogin()
                    drive, directory = os.path.splitdrive(input_file_path)
                    log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)
            else:
                try:
                    copy_file(input_file_path, output_file_path, csv_file)
                except IOError as e:
                    print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user = os.getlogin()
                    drive, directory = os.path.splitdrive(input_file_path)
                    log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)

def main():
    try:
        # Load configuration from JSON file
        with open('config.json', 'r') as f:
            config = json.load(f)

        # Extract source, destination, and csv_file_path from config
        source_dir = config.get('source_dir', '')
        destination_dir = config.get('destination_dir', '')
        csv_file = config.get('csv_file_path', 'copy_failures.csv')

        # Copy directory
        copy_directory(source_dir, destination_dir, csv_file)
        print(f'Successfully copied directory {source_dir} to {destination_dir}')

    except FileNotFoundError:
        print("Error: Configuration file 'config.json' not found.")
    except PermissionError as e:
        print(f"Permission error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
