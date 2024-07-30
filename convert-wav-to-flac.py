"@author: Andrew Martin, 2024"

import os
import subprocess
import shutil
import csv
from datetime import datetime
import ctypes
import json

# Sets the limit as 18 TB then converts that to bits
MAX_STORAGE_LIMIT_TB = 18
MAX_STORAGE_LIMIT_BYTES = MAX_STORAGE_LIMIT_TB * 1024**4

def load_config(filename): # Get source/destination and csv file from config.json
    with open(filename, 'r') as f:
        config = json.load(f)
    return config

def log_failure(file_name, timestamp, user, drive, directory, csv_file): # Writes copy failures to csv file
    drive_name = get_drive_name(drive)
    csv_file = os.path.join(os.path.dirname(__file__), csv_file)

    with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([file_name, timestamp, user, drive_name, directory])

def get_drive_name(drive): # Gets the name of source directory
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

def get_wav_channels(input_file_path): # Detects the number of channels in the source WAV files
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

def convert_wav_to_flac(input_file_path, output_file_path): # Convert WAV files to FLAC
    try:
        channels = get_wav_channels(input_file_path)

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_file_path,
            '-c:a', 'flac',
            '-compression_level', '5',
            '-ac', str(channels),
            output_file_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        print(f'Converted {input_file_path} to FLAC with {channels} channels')
    except subprocess.CalledProcessError as e:
        print(f'Failed to convert {input_file_path} to FLAC: {e.stderr}')

def copy_file(input_file_path, output_file_path, csv_file): # Copy from source to destination
    try:
        file_size = os.path.getsize(input_file_path)
        destination_drive = os.path.splitdrive(output_file_path)[0]
        available_space = get_available_space(destination_drive)
        if file_size > available_space:
            print(f'Insufficient space to copy {input_file_path}. Required: {file_size}, Available: {available_space}')
            return

        with open(input_file_path, 'rb') as src, open(output_file_path, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        print(f'Copied {input_file_path} to {output_file_path}')
    except IOError as e:
        print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = os.getlogin()
        drive, directory = os.path.splitdrive(input_file_path)
        log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)

def get_available_space(drive): # Sees how much space is available on destination drive
    if os.name == 'nt':
        free_bytes = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(drive),
            None,
            None,
            ctypes.byref(free_bytes)
        )
        return free_bytes.value
    else:
        stat = os.statvfs(drive)
        return stat.f_frsize * stat.f_bavail

def compare_and_copy(source, drive_folder, csv_file): # In the case your run gets cancelled mid copy, this will search
    total_copied_size = 0                             # through copied files and begin the process where you left off
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() != 'system volume information']
        for dir_name in dirs:
            source_dir_path = os.path.join(root, dir_name)
            relative_dir_path = os.path.relpath(source_dir_path, source)
            destination_dir_path = os.path.join(drive_folder, relative_dir_path)
            os.makedirs(destination_dir_path, exist_ok=True)

        for file in files:
            input_file_path = os.path.join(root, file)
            relative_file_path = os.path.relpath(input_file_path, source)
            output_file_path = os.path.join(drive_folder, relative_file_path)

            if file.lower().endswith('.wav'): # Checks if there is a WAV file in the source with a FLAC of the same
                try:                          # name in the destination
                    flac_file_path = os.path.splitext(output_file_path)[0] + '.flac'
                    if not os.path.exists(flac_file_path):
                        convert_wav_to_flac(input_file_path, flac_file_path)
                except subprocess.CalledProcessError as e:
                    print(f'Failed to convert {input_file_path} to FLAC: {e}')
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user = os.getlogin()
                    drive, directory = os.path.splitdrive(input_file_path)
                    log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)
            else:
                try:
                    file_size = os.path.getsize(input_file_path)
                    total_copied_size += file_size
                    if total_copied_size > MAX_STORAGE_LIMIT_BYTES:
                        print(f'Exceeded maximum storage limit of {MAX_STORAGE_LIMIT_TB} TB.')
                        return

                    if not os.path.exists(output_file_path):
                        copy_file(input_file_path, output_file_path, csv_file)
                    else:
                        print(f'Skipping copy of {input_file_path}, file already exists in destination.')
                except IOError as e:
                    print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user = os.getlogin()
                    drive, directory = os.path.splitdrive(input_file_path)
                    log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)

def regular_copy(source, drive_folder, csv_file): # Regular copy code if there are no matches
    total_copied_size = 0
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() != 'system volume information']
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
                    file_size = os.path.getsize(input_file_path)
                    total_copied_size += file_size
                    if total_copied_size > MAX_STORAGE_LIMIT_BYTES:
                        print(f'Exceeded maximum storage limit of {MAX_STORAGE_LIMIT_TB} TB.')
                        return

                    if not os.path.exists(output_file_path):
                        copy_file(input_file_path, output_file_path, csv_file)
                    else:
                        print(f'Skipping copy of {input_file_path}, file already exists in destination.')
                except IOError as e:
                    print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user = os.getlogin()
                    drive, directory = os.path.splitdrive(input_file_path)
                    log_failure(os.path.basename(input_file_path), timestamp, user, drive, directory, csv_file)

def copy_directory(source, destination, csv_file): # Copies the source directory to the destination
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
    
    #Check if the first folder in destination matches the name of the source drive, if it does the update script runs
    first_folder_in_source = os.path.basename(os.path.normpath(source))
    first_folder_in_destination = os.listdir(destination)[0] if os.path.exists(destination) else None

    if first_folder_in_destination and first_folder_in_destination == first_folder_in_source:
        compare_and_copy(source, drive_folder, csv_file)
    else:
        regular_copy(source, drive_folder, csv_file)

def main(): # Reads congig.json, gets the source, destination and csv, then copies
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)

        source_dir = config.get('source_dir', '')
        destination_dir = config.get('destination_dir', '')
        csv_file = config.get('csv_file_path', 'copy_failures.csv')

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
