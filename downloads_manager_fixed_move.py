#!/usr/bin/env python3
"""
Downloads Manager - A complete solution with delete and move functionality
"""

import json
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import time
import urllib.parse
from urllib.parse import parse_qs
import shutil
import traceback
import glob
from pathlib import Path
import re

# Default port for the web server
PORT = 8000

# Check if running on Windows or WSL
IS_WINDOWS = sys.platform.startswith('win')
IS_WSL = 'Microsoft' in open('/proc/version').read() if os.path.exists('/proc/version') else False

def wsl_path_to_windows(wsl_path):
    """Convert a WSL path to a Windows path"""
    if wsl_path.startswith('/mnt/'):
        # Extract the drive letter
        drive = wsl_path[5].upper()
        # Convert the rest of the path
        win_path = f"{drive}:{wsl_path[7:].replace('/', '\\')}"
        return win_path
    return wsl_path

def windows_path_to_wsl(win_path):
    """Convert a Windows path to a WSL path"""
    if re.match(r'^[A-Za-z]:', win_path):
        drive = win_path[0].lower()
        path = win_path[2:].replace('\\', '/')
        return f"/mnt/{drive}{path}"
    return win_path

def convert_path_if_needed(path):
    """Convert path to format suitable for current environment"""
    # If we're in WSL, we need Windows paths for recycling
    if IS_WSL and path.startswith('/mnt/'):
        return wsl_path_to_windows(path)
    if IS_WINDOWS and path.startswith('/mnt/'):
        return wsl_path_to_windows(path)
    return path

class DownloadsManagerHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for Downloads Manager"""
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def end_headers(self):
        # Add CORS headers to allow JavaScript to access the JSON file
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super().end_headers()
    
    def do_GET(self):
        """Handle GET requests with special case for JSON file"""
        # Check if this is a request for the JSON file
        if self.path.endswith('claudeDownloadIndex.json'):
            # Make sure we send the freshest version
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            
            # Read the file and send it
            with open('claudeDownloadIndex.json', 'rb') as f:
                self.wfile.write(f.read())
            return
        
        # Otherwise, handle normally
        return super().do_GET()
    
    def do_POST(self):
        """Handle POST requests for file operations like move"""
        try:
            # Parse the URL path
            parsed_path = urllib.parse.urlparse(self.path)
            
            # Handle move file request
            if parsed_path.path == '/api/move':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                move_data = json.loads(post_data)
                
                # Validate the request data
                if 'files' not in move_data or 'destination' not in move_data:
                    self.send_error(400, "Missing required fields in move request")
                    return
                
                # Get files to move and destination
                files_to_move = move_data['files']
                destination = move_data['destination']
                
                print(f"Move request received: {len(files_to_move)} files to {destination}")
                
                # Make sure destination exists
                if not os.path.exists(destination) and not destination.startswith('C:'):
                    try:
                        os.makedirs(destination, exist_ok=True)
                        print(f"Created destination directory: {destination}")
                    except Exception as e:
                        print(f"Error creating destination directory: {e}")
                elif destination.startswith('C:') and IS_WSL:
                    # For Windows paths in WSL, use PowerShell to create the directory
                    try:
                        ps_script = f"if (!(Test-Path -Path '{destination}')) {{ New-Item -ItemType Directory -Path '{destination}' -Force }}"
                        result = subprocess.run(['powershell.exe', '-Command', ps_script], 
                                              capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"PowerShell error creating directory: {result.stderr}")
                    except Exception as e:
                        print(f"Error creating Windows directory: {e}")
                
                # Process the move operation
                results = []
                for file_path in files_to_move:
                    try:
                        # Get the file name from the path
                        if '\\' in file_path:
                            # Windows path
                            file_name = file_path.split('\\')[-1]
                        else:
                            # Unix path
                            file_name = file_path.split('/')[-1]
                        
                        # Create the destination path
                        dest_path = os.path.join(destination, file_name)
                        
                        # Handle Windows paths in WSL
                        if IS_WSL:
                            if file_path.startswith('C:'):
                                # Use PowerShell to move Windows files
                                ps_script = f"Move-Item -Path '{file_path}' -Destination '{destination}\\{file_name}' -Force"
                                result = subprocess.run(['powershell.exe', '-Command', ps_script], 
                                                       capture_output=True, text=True)
                                
                                success = result.returncode == 0
                                error = result.stderr if not success else None
                                
                                results.append({
                                    'path': file_path,
                                    'success': success,
                                    'error': error,
                                    'destination': dest_path
                                })
                                continue
                            elif destination.startswith('C:'):
                                # Convert WSL path to Windows and use PowerShell
                                win_src = wsl_path_to_windows(file_path)
                                ps_script = f"Move-Item -Path '{win_src}' -Destination '{destination}\\{file_name}' -Force"
                                result = subprocess.run(['powershell.exe', '-Command', ps_script], 
                                                       capture_output=True, text=True)
                                
                                success = result.returncode == 0
                                error = result.stderr if not success else None
                                
                                results.append({
                                    'path': file_path,
                                    'success': success,
                                    'error': error,
                                    'destination': dest_path
                                })
                                continue
                        
                        # Standard case - both are Unix paths or both are Windows paths
                        if os.path.exists(file_path):
                            print(f"Moving: {file_path} -> {dest_path}")
                            if os.path.isdir(file_path):
                                # For directories, use shutil.move
                                shutil.move(file_path, dest_path)
                            else:
                                # For files, use os.rename (faster than shutil.move)
                                os.rename(file_path, dest_path)
                            
                            results.append({
                                'path': file_path,
                                'success': True,
                                'destination': dest_path
                            })
                        else:
                            results.append({
                                'path': file_path,
                                'success': False,
                                'error': f"File not found: {file_path}"
                            })
                            
                    except Exception as e:
                        print(f"Error moving file {file_path}: {e}")
                        traceback.print_exc()
                        results.append({
                            'path': file_path,
                            'success': False,
                            'error': str(e)
                        })
                
                # Update JSON file to reflect moved files
                self._update_json_file_after_move(results)
                
                # Send response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'results': results
                }).encode())
                return
                
            # If not a recognized endpoint
            self.send_error(404, "API endpoint not found")
        
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")
            traceback.print_exc()
    
    def do_DELETE(self):
        """Handle DELETE requests for file deletion"""
        try:
            # Parse the URL path
            parsed_path = urllib.parse.urlparse(self.path)
            
            # Check if this is a file deletion request
            if parsed_path.path == '/api/delete':
                # Get parameters from query string
                params = parse_qs(parsed_path.query)
                
                # Check for required parameters
                if 'path' not in params:
                    self.send_error(400, "Missing 'path' parameter")
                    return
                
                # Get file paths to delete (can be multiple)
                file_paths = params['path']
                use_recycle_bin = params.get('useRecycleBin', ['true'])[0].lower() == 'true'
                
                # Process each file
                results = []
                for file_path in file_paths:
                    try:
                        # Clean up and normalize the path
                        clean_path = file_path
                        
                        # Ensure Windows paths use proper backslashes
                        if clean_path.startswith('C:') and '/' in clean_path:
                            clean_path = clean_path.replace('/', '\\')
                        
                        print(f"Original path: {file_path}")
                        print(f"Normalized path: {clean_path}")
                        
                        # Convert path if needed for the current environment
                        if IS_WSL and clean_path.startswith('C:'):
                            # Convert Windows path to WSL path for existence check
                            wsl_path = windows_path_to_wsl(clean_path)
                            if os.path.exists(wsl_path):
                                clean_path = wsl_path
                                print(f"Converted to WSL path: {clean_path}")
                        
                        # Check if the path exists
                        path_exists = os.path.exists(clean_path)
                        
                        if path_exists:
                            print(f"Path exists, deleting: {clean_path}")
                            success, error = self._delete_file(clean_path, use_recycle_bin)
                            results.append({
                                'path': file_path,
                                'success': success,
                                'error': error
                            })
                        else:
                            # Try PowerShell for Windows paths
                            if IS_WSL and clean_path.startswith('C:'):
                                win_path = clean_path
                                print(f"Using PowerShell to check Windows path: {win_path}")
                                
                                # Use PowerShell to delete
                                if use_recycle_bin:
                                    # Use PowerShell RecycleBin
                                    ps_script = f"Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{win_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                                    import subprocess
                                    cmd = ['powershell.exe', '-Command', ps_script]
                                else:
                                    # Use PowerShell Delete
                                    import subprocess
                                    cmd = ['powershell.exe', '-Command', f"Remove-Item -Path '{win_path}' -Force -Recurse"]
                                
                                # Execute the command
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                
                                success = result.returncode == 0
                                error = result.stderr if result.stderr else None
                                
                                results.append({
                                    'path': file_path, 
                                    'success': success,
                                    'error': error
                                })
                            else:
                                print(f"Path not found: {clean_path}")
                                results.append({
                                    'path': file_path,
                                    'success': False,
                                    'error': f"File not found at {clean_path}"
                                })
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        traceback.print_exc()
                        results.append({
                            'path': file_path,
                            'success': False,
                            'error': str(e)
                        })
                
                # Update JSON file to remove deleted items
                self._update_json_file(results)
                
                # Send response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'results': results
                }).encode())
                return
                
            self.send_error(404, "API endpoint not found")
        
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")
            traceback.print_exc()
    
    def _delete_file(self, file_path, use_recycle_bin=True):
        """Delete a file/directory with option to use recycle bin"""
        try:
            print(f"Deleting file: {file_path} (use_recycle_bin={use_recycle_bin})")
            
            # Double check that file exists
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}"
            
            # In WSL with Windows path
            if IS_WSL and file_path.startswith('C:'):
                try:
                    # Use PowerShell to delete Windows paths
                    if use_recycle_bin:
                        # Use RecycleBin via PowerShell
                        ps_script = f"Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{file_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                        import subprocess
                        cmd = ['powershell.exe', '-Command', ps_script]
                    else:
                        # Use Remove-Item for permanent deletion
                        import subprocess
                        cmd = ['powershell.exe', '-Command', f"Remove-Item -Path '{file_path}' -Force -Recurse"]
                    
                    # Execute the command
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    success = result.returncode == 0
                    error = result.stderr if result.stderr else None
                    
                    return success, error
                except Exception as e:
                    return False, str(e)
            
            # Handle WSL paths or if running on Windows
            else:
                if IS_WSL and use_recycle_bin and file_path.startswith('/mnt/'):
                    # For WSL paths that need to go to recycling bin, convert to Windows
                    win_path = wsl_path_to_windows(file_path)
                    print(f"Converting WSL path to Windows for recycle bin: {win_path}")
                    
                    # Use PowerShell for recycling
                    ps_script = f"Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{win_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                    import subprocess
                    cmd = ['powershell.exe', '-Command', ps_script]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    success = result.returncode == 0
                    error = result.stderr if result.stderr else None
                    
                    return success, error
                else:
                    # Regular deletion using Python
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    else:
                        os.remove(file_path)
                    return True, None
                
        except Exception as e:
            print(f"Deletion error: {e}")
            traceback.print_exc()
            return False, str(e)
    
    def _update_json_file_after_move(self, move_results):
        """Update the JSON file to reflect moved files"""
        try:
            json_path = 'claudeDownloadIndex.json'
            if not os.path.exists(json_path):
                return
            
            # Load the JSON data
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Get list of successfully moved files
            moved_files = [result['path'] for result in move_results if result['success']]
            
            # Skip if nothing was successfully moved
            if not moved_files:
                return
            
            print(f"Updating JSON file to remove {len(moved_files)} moved files")
            
            # File paths might be in different formats (Windows vs Unix)
            def normalize_path(path):
                path = path.rstrip('/\\')
                return path.lower() if IS_WINDOWS else path
            
            # Create normalized versions of moved paths
            normalized_moved_files = [normalize_path(path) for path in moved_files]
            
            # Remove moved files from each category
            for category in data['categories']:
                data['categories'][category]['files'] = [
                    file for file in data['categories'][category]['files']
                    if normalize_path(file['path']) not in normalized_moved_files
                ]
            
            # Write the updated data back to the file
            backup_path = f"{json_path}.bak_moved"
            print(f"Creating backup: {backup_path}")
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Now update the original file
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"JSON file updated successfully after move operation")
            
        except Exception as e:
            print(f"Error updating JSON file after move: {e}")
            traceback.print_exc()
    
    def _update_json_file(self, delete_results):
        """Update the JSON file to remove entries for deleted files"""
        try:
            json_path = 'claudeDownloadIndex.json'
            if not os.path.exists(json_path):
                return
            
            # Load the JSON data
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Get list of successfully deleted paths
            deleted_paths = [result['path'] for result in delete_results if result['success']]
            
            # Skip if nothing was successfully deleted
            if not deleted_paths:
                return
            
            print(f"Updating JSON file to remove {len(deleted_paths)} deleted files")
            
            # File paths might be in different formats (Windows vs Unix)
            # We'll normalize them for comparison
            def normalize_path(path):
                # Strip trailing slashes
                path = path.rstrip('/\\')
                # Convert to lowercase for case-insensitive comparison on Windows
                return path.lower() if IS_WINDOWS else path
            
            # Create normalized versions of deleted paths
            normalized_deleted_paths = [normalize_path(path) for path in deleted_paths]
            
            # Remove deleted files from each category
            for category in data['categories']:
                data['categories'][category]['files'] = [
                    file for file in data['categories'][category]['files']
                    if normalize_path(file['path']) not in normalized_deleted_paths
                ]
            
            # Remove deleted files from duplicates list
            if 'duplicates' in data['summary']:
                new_duplicates = []
                for dup_entry in data['summary']['duplicates']:
                    if 'original' in dup_entry and normalize_path(dup_entry['original']) in normalized_deleted_paths:
                        # Skip this entry if the original was deleted
                        continue
                    if 'duplicate' in dup_entry and normalize_path(dup_entry['duplicate']) in normalized_deleted_paths:
                        # Skip this entry if the duplicate was deleted
                        continue
                    if 'duplicates' in dup_entry:
                        # Filter out deleted duplicates
                        dup_entry['duplicates'] = [d for d in dup_entry['duplicates'] 
                                                if normalize_path(d) not in normalized_deleted_paths]
                        if not dup_entry['duplicates']:
                            # Skip if all duplicates were deleted
                            continue
                    new_duplicates.append(dup_entry)
                
                data['summary']['duplicates'] = new_duplicates
            
            # Write the updated data back to the file
            backup_path = f"{json_path}.bak_deleted"
            print(f"Creating backup: {backup_path}")
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Now update the original file
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"JSON file updated successfully")
            
        except Exception as e:
            print(f"Error updating JSON file: {e}")
            traceback.print_exc()
    
    def log_message(self, format, *args):
        # Customize logging to be more informative
        sys.stdout.write(f"[Downloads Manager] {format % args}\n")
        sys.stdout.flush()

def start_server(directory=None):
    """Start the HTTP server"""
    if directory:
        os.chdir(directory)
    
    # Ensure we're in the directory containing the HTML and JSON files
    if not os.path.exists('downloadedFiles.html') or not os.path.exists('claudeDownloadIndex.json'):
        print(f"Error: Required files not found in {os.getcwd()}")
        print("Make sure both downloadedFiles.html and claudeDownloadIndex.json exist in this directory.")
        return False
    
    server_address = ('localhost', PORT)
    httpd = HTTPServer(server_address, DownloadsManagerHandler)
    print(f"Starting server at http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")
    
    return httpd

def open_browser():
    """Open the browser after a short delay to ensure the server is running"""
    time.sleep(1)
    webbrowser.open(f'http://localhost:{PORT}/downloadedFiles.html')

if __name__ == '__main__':
    # Get the directory containing the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not script_dir:  # In case the script is run directly from the directory
        script_dir = os.getcwd()
    
    print("Downloads Manager")
    print("=================")
    print(f"Working directory: {script_dir}")
    print(f"Running in WSL: {IS_WSL}")
    
    # Import subprocess for shell commands
    import subprocess
    
    # Start the server
    httpd = start_server(script_dir)
    if not httpd:
        sys.exit(1)
    
    # Open browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        # Run the server until interrupted
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()