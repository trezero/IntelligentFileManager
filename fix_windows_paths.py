#!/usr/bin/env python3
"""
Script to fix Windows paths in the JSON file by adding the missing backslash after the drive letter
"""

import json
import os
import sys
import re

def fix_windows_paths():
    """Fix Windows paths in the JSON file by adding the missing backslash after C:"""
    json_path = 'claudeDownloadIndex.json'
    
    if not os.path.exists(json_path):
        print(f"Error: File {json_path} not found!")
        return False
    
    print(f"Reading JSON file: {json_path}")
    
    try:
        # Load the JSON data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Track fixes
        fixes_made = 0
        
        # Fix paths in each category
        for category in data['categories']:
            for file_entry in data['categories'][category]['files']:
                if 'path' in file_entry and file_entry['path'].startswith('C:Users'):
                    file_entry['path'] = file_entry['path'].replace('C:Users', 'C:\\Users')
                    fixes_made += 1
        
        # Fix paths in the duplicates section
        if 'summary' in data and 'duplicates' in data['summary']:
            for dup_entry in data['summary']['duplicates']:
                if 'original' in dup_entry and dup_entry['original'].startswith('C:Users'):
                    dup_entry['original'] = dup_entry['original'].replace('C:Users', 'C:\\Users')
                    fixes_made += 1
                
                if 'duplicate' in dup_entry and dup_entry['duplicate'].startswith('C:Users'):
                    dup_entry['duplicate'] = dup_entry['duplicate'].replace('C:Users', 'C:\\Users')
                    fixes_made += 1
                
                if 'duplicates' in dup_entry:
                    for i, path in enumerate(dup_entry['duplicates']):
                        if path.startswith('C:Users'):
                            dup_entry['duplicates'][i] = path.replace('C:Users', 'C:\\Users')
                            fixes_made += 1
        
        # Save the updated data to a new file first (safer)
        backup_path = f"{json_path}.bak2"
        print(f"Creating backup: {backup_path}")
        with open(backup_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Now update the original file
        print(f"Updating original file: {json_path}")
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Fix complete! {fixes_made} paths fixed.")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Fixing Windows paths in JSON file...")
    if fix_windows_paths():
        print("Success! The JSON file has been updated with corrected Windows paths.")
    else:
        print("Failed to fix paths.")