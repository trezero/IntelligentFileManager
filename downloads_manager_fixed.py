#!/usr/bin/env python3
"""
Downloads Manager - A simple web application to manage download files
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
import subprocess
from pathlib import Path

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

def get_wsl_home():
    """Get the Windows path to the WSL home directory"""
    try:
        result = subprocess.run(['wslpath', '-w', '/'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except:
        return None

def convert_path_if_needed(path):
    """Convert path to format suitable for current environment"""
    # If we're in WSL, we need Windows paths for recycling
    if IS_WSL and path.startswith('/mnt/'):
        return wsl_path_to_windows(path)
    return path

class DownloadsManagerHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for Downloads Manager"""
    
    def end_headers(self):
        # Add CORS headers to allow JavaScript to access the JSON file
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super().end_headers()
    
    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.end_headers()
    
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
                        clean_path = os.path.normpath(file_path)
                        
                        print(f"Original path: {file_path}")
                        print(f"Normalized path: {clean_path}")
                        
                        # Check if the path exists
                        if os.path.exists(clean_path):
                            print(f"Path exists, deleting: {clean_path}")
                            success, error = self._delete_file(clean_path, use_recycle_bin)
                            results.append({
                                'path': file_path,
                                'success': success,
                                'error': error
                            })
                        else:
                            # Try converting to Windows path if in WSL
                            if IS_WSL and clean_path.startswith('/mnt/'):
                                win_path = wsl_path_to_windows(clean_path)
                                print(f"Converting to Windows path: {win_path}")
                                
                                # Use cmd to check if Windows path exists
                                check_cmd = f"powershell.exe test-path '{win_path}'"
                                result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
                                
                                if "True" in result.stdout:
                                    print(f"Windows path exists, deleting via PowerShell: {win_path}")
                                    if use_recycle_bin:
                                        # Use PowerShell to move to recycle bin
                                        ps_script = f"Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{win_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                                        subprocess.run(['powershell.exe', '-Command', ps_script], capture_output=True, check=False)
                                        success, error = True, None
                                    else:
                                        # Delete using PowerShell
                                        delete_cmd = f"powershell.exe Remove-Item -Path '{win_path}' -Force"
                                        result = subprocess.run(delete_cmd, shell=True, capture_output=True, text=True)
                                        success = result.returncode == 0
                                        error = result.stderr if not success else None
                                    
                                    results.append({
                                        'path': file_path,
                                        'success': success,
                                        'error': error
                                    })
                                else:
                                    print(f"Windows path not found: {win_path}")
                                    results.append({
                                        'path': file_path,
                                        'success': False,
                                        'error': f"File not found at {win_path}"
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
            
            # In WSL, if the path is under /mnt, use PowerShell to delete
            if IS_WSL and file_path.startswith('/mnt/'):
                win_path = wsl_path_to_windows(file_path)
                print(f"Using PowerShell to delete Windows path: {win_path}")
                
                if use_recycle_bin:
                    # Use PowerShell to move to recycle bin
                    ps_script = f"Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{win_path}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
                    result = subprocess.run(['powershell.exe', '-Command', ps_script], capture_output=True, check=False)
                else:
                    # Delete using PowerShell
                    delete_cmd = f"powershell.exe Remove-Item -Path '{win_path}' -Force"
                    result = subprocess.run(delete_cmd, shell=True, capture_output=True, text=True)
                
                success = result.returncode == 0
                error = result.stderr if not success else None
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
            
            # Remove deleted files from each category
            for category in data['categories']:
                data['categories'][category]['files'] = [
                    file for file in data['categories'][category]['files']
                    if file['path'] not in deleted_paths
                ]
            
            # Remove deleted files from duplicates list
            if 'duplicates' in data['summary']:
                new_duplicates = []
                for dup_entry in data['summary']['duplicates']:
                    if 'duplicate' in dup_entry and dup_entry['duplicate'] in deleted_paths:
                        # Skip this entry if the duplicate was deleted
                        continue
                    if 'duplicates' in dup_entry:
                        # Filter out deleted duplicates
                        dup_entry['duplicates'] = [d for d in dup_entry['duplicates'] if d not in deleted_paths]
                        if not dup_entry['duplicates']:
                            # Skip if all duplicates were deleted
                            continue
                    new_duplicates.append(dup_entry)
                data['summary']['duplicates'] = new_duplicates
            
            # Write the updated data back to the file
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
                
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