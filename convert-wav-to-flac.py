import os
import subprocess
import shutil

source_dir = 'E:\\'
destination_dir = 'S:\\'

def convert_wav_to_flac(input_file_path, output_file_path):
    try:
        ffmpeg_cmd = [
            'ffmpeg', 
            '-i', input_file_path, 
            '-c:a', 'flac', 
            #'-ac', '2',  # Set number of output channels (e.g., 2 for stereo)
            '-compression_level', '6',  # Adjust compression level if needed
            output_file_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        print(f'Converted {input_file_path} to FLAC')
    except subprocess.CalledProcessError as e:
        print(f'Failed to convert {input_file_path} to FLAC: {e.stderr}')

def copy_file(input_file_path, output_file_path):
    try:
        if not os.path.exists(output_file_path):  # Only copy if the file doesn't exist in destination
            with open(input_file_path, 'rb') as src, open(output_file_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            print(f'Copied {input_file_path} to {output_file_path}')
        else:
            print(f'Skipping {output_file_path} (already exists)')
    except IOError as e:
        print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')

def copy_directory(source, destination):
    source_XXX_dir = os.path.join(source, 'XXX') # XXX is the distinction for updating the files; this would be your first folder in the directory so it knows to look for it.
    destination_XXX_dir = os.path.join(destination, 'XXX') # These aren't neccessary (if process is interrupted this will update paused files) So I would reccomend removing this if that's not a concern.

    try:
        os.makedirs(destination_XXX_dir, exist_ok=True)
    except OSError as e:
        print(f"Failed to create directory {destination_XXX_dir}: {e}")
        return

    # Function to recursively copy files while maintaining directory structure
    def copy_files_recursively(source_dir, destination_dir):
        for root, dirs, files in os.walk(source_dir):
            for dir_name in dirs:
                source_sub_dir = os.path.join(root, dir_name)
                relative_sub_dir = os.path.relpath(source_sub_dir, source_dir)
                destination_sub_dir = os.path.join(destination_dir, relative_sub_dir)
                os.makedirs(destination_sub_dir, exist_ok=True)

            for file in files:
                input_file_path = os.path.join(root, file)
                relative_file_path = os.path.relpath(input_file_path, source_dir)
                output_file_path = os.path.join(destination_dir, relative_file_path)

                # Remove file extension for comparison
                file_name, file_ext = os.path.splitext(file)

                # Check if the file (without extension) exists in destination
                if not os.path.exists(os.path.join(destination_dir, relative_file_path)):
                    if file_ext.lower() == '.wav':
                        # Check if there's a corresponding .flac file in destination
                        if os.path.exists(os.path.join(destination_dir, relative_file_path.replace('.wav', '.flac'))):
                            print(f'Skipping {input_file_path} (FLAC version already exists)')
                        else:
                            # Convert .wav to .flac and copy
                            try:
                                convert_wav_to_flac(input_file_path, os.path.splitext(output_file_path)[0] + '.flac')
                            except Exception as e:
                                print(f'Failed to convert {input_file_path} to FLAC: {e}')
                    else:
                        # Directly copy other file types
                        try:
                            copy_file(input_file_path, output_file_path)
                        except IOError as e:
                            print(f'Failed to copy {input_file_path} to {output_file_path}: {e}')
                else:
                    print(f'Skipping {output_file_path} (already exists)')

    # Copy files from source 'XXX' directory to destination 'XXX' directory
    copy_files_recursively(source_XXX_dir, destination_XXX_dir)

def file_checksum(file_path):
    # Placeholder for generating a checksum or hash of a file
    # Replace this with your actual implementation if needed
    return None

try:
    copy_directory(source_dir, destination_dir)
    print(f'Successfully copied directory {source_dir} to {destination_dir}')
except PermissionError as e:
    print(f"Permission error: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
