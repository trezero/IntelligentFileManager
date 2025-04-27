#!/usr/bin/env python3
"""
Script to convert all WSL paths in the JSON file to Windows paths
"""

import json
import os
import sys

def wsl_path_to_windows(path):
    """Convert a WSL path to a Windows path"""
    if path.startswith('/mnt/'):
        # Extract the drive letter
        drive = path[5].upper()
        # Convert the rest of the path
        win_path = f"{drive}:{path[7:].replace('/', '\\')}"
        return win_path
    return path

def convert_json_paths():
    """Convert all paths in the JSON file from WSL to Windows format"""
    json_path = 'claudeDownloadIndex.json'
    
    if not os.path.exists(json_path):
        print(f"Error: File {json_path} not found!")
        return False
    
    print(f"Reading JSON file: {json_path}")
    
    try:
        # Load the JSON data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Track conversion counts
        paths_converted = 0
        
        # Convert paths in each category
        for category in data['categories']:
            for file_entry in data['categories'][category]['files']:
                if 'path' in file_entry and file_entry['path'].startswith('/mnt/'):
                    file_entry['path'] = wsl_path_to_windows(file_entry['path'])
                    paths_converted += 1
        
        # Convert paths in the duplicates section
        if 'summary' in data and 'duplicates' in data['summary']:
            for dup_entry in data['summary']['duplicates']:
                if 'original' in dup_entry and dup_entry['original'].startswith('/mnt/'):
                    dup_entry['original'] = wsl_path_to_windows(dup_entry['original'])
                    paths_converted += 1
                
                if 'duplicate' in dup_entry and dup_entry['duplicate'].startswith('/mnt/'):
                    dup_entry['duplicate'] = wsl_path_to_windows(dup_entry['duplicate'])
                    paths_converted += 1
                
                if 'duplicates' in dup_entry:
                    for i, path in enumerate(dup_entry['duplicates']):
                        if path.startswith('/mnt/'):
                            dup_entry['duplicates'][i] = wsl_path_to_windows(path)
                            paths_converted += 1
        
        # Save the updated data to a new file first (safer)
        backup_path = f"{json_path}.bak"
        print(f"Creating backup: {backup_path}")
        with open(backup_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Now update the original file
        print(f"Updating original file: {json_path}")
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Conversion complete! {paths_converted} paths converted.")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Converting WSL paths to Windows paths in JSON file...")
    if convert_json_paths():
        print("Success! The JSON file has been updated with Windows paths.")
    else:
        print("Failed to convert paths.")