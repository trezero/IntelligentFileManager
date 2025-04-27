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
from pathlib import Path

# Default port for the web server
PORT = 8000

# Check if running on Windows for recycle bin functionality
IS_WINDOWS = sys.platform.startswith('win')

if IS_WINDOWS:
    try:
        import winshell
        import win32com.client
        HAS_WINSHELL = True
    except ImportError:
        print("Note: winshell module not found. Installing required packages for Recycle Bin support...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "winshell"])
            import winshell
            import win32com.client
            HAS_WINSHELL = True
            print("Successfully installed Recycle Bin support packages.")
        except Exception as e:
            print(f"Warning: Could not install Recycle Bin support: {e}")
            print("Files will be permanently deleted instead of moved to Recycle Bin.")
            HAS_WINSHELL = False
else:
    HAS_WINSHELL = False
    print("Not running on Windows. Files will be permanently deleted instead of moved to Recycle Bin.")

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
                
                # Get the base Downloads directory - handle both Windows and WSL paths
                downloads_dir = os.path.abspath(os.getcwd())
                if downloads_dir.startswith('/mnt/'):
                    downloads_dir_prefix = '/mnt/c/Users/winadmin/Downloads'
                else:
                    downloads_dir_prefix = 'C:\\Users\\winadmin\\Downloads'
                
                print(f"Downloads directory: {downloads_dir}")
                print(f"Downloads prefix: {downloads_dir_prefix}")
                
                # Process each file
                results = []
                for file_path in file_paths:
                    try:
                        # Clean up the path
                        cleaned_path = file_path.replace('\\', '/').strip()
                        
                        # Convert relative path to absolute if needed
                        if not cleaned_path.startswith('/') and not cleaned_path.startswith('C:'):
                            if downloads_dir.startswith('/'):
                                # WSL path
                                absolute_path = os.path.join(downloads_dir, cleaned_path).replace('\\', '/')
                            else:
                                # Windows path
                                absolute_path = os.path.join(downloads_dir, cleaned_path).replace('/', '\\')
                        else:
                            absolute_path = cleaned_path
                        
                        # Determine if we need to convert between Windows and WSL paths
                        if absolute_path.startswith('/mnt/c/'):
                            # Convert WSL path to Windows path for file operations
                            windows_path = 'C:' + absolute_path[6:].replace('/', '\\')
                            is_wsl_path = True
                        elif absolute_path.startswith('C:'):
                            # Already a Windows path
                            windows_path = absolute_path
                            is_wsl_path = False
                        else:
                            # Other path format - keep as is
                            windows_path = absolute_path
                            is_wsl_path = False
                        
                        print(f"Processing path: {file_path}")
                        print(f"Absolute path: {absolute_path}")
                        print(f"Windows path: {windows_path}")
                        
                        # Check if this path is within the Downloads directory
                        if is_wsl_path and not absolute_path.startswith(downloads_dir_prefix):
                            print(f"Path not in Downloads: {absolute_path}")
                            results.append({
                                'path': file_path,
                                'success': False,
                                'error': 'Path is outside of the Downloads directory'
                            })
                            continue
                        
                        # Check if the path exists and delete accordingly
                        if os.path.exists(windows_path):
                            print(f"Deleting: {windows_path}")
                            success, error = self._delete_file(windows_path, use_recycle_bin)
                            results.append({
                                'path': file_path,
                                'success': success,
                                'error': error
                            })
                        else:
                            # Try with wildcard matching if the direct path doesn't exist
                            if '*' in windows_path:
                                matching_files = glob.glob(windows_path)
                                if matching_files:
                                    for match in matching_files:
                                        success, error = self._delete_file(match, use_recycle_bin)
                                        results.append({
                                            'path': match,
                                            'success': success,
                                            'error': error
                                        })
                                else:
                                    results.append({
                                        'path': file_path,
                                        'success': False,
                                        'error': 'No matching files found'
                                    })
                            else:
                                # Try WSL path if Windows path failed
                                if IS_WINDOWS and not os.path.exists(absolute_path):
                                    results.append({
                                        'path': file_path,
                                        'success': False,
                                        'error': f'File not found at {windows_path} or {absolute_path}'
                                    })
                                else:
                                    success, error = self._delete_file(absolute_path, use_recycle_bin)
                                    results.append({
                                        'path': file_path,
                                        'success': success,
                                        'error': error
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
                
            if IS_WINDOWS and HAS_WINSHELL and use_recycle_bin:
                try:
                    # Use recycle bin on Windows
                    print(f"Using recycle bin for: {file_path}")
                    if os.path.isdir(file_path):
                        # For directories, we need to handle them differently
                        shell = win32com.client.Dispatch("Shell.Application")
                        folder = shell.Namespace(0)  # 0 is the Recycle Bin
                        folder.MoveHere(file_path, 0)  # 0 means no dialog
                    else:
                        # For files, we can use winshell
                        winshell.delete_file(file_path, no_confirm=True, allow_undo=True)
                except Exception as recycling_error:
                    print(f"Recycle bin error: {recycling_error}, falling back to regular deletion")
                    # If recycling fails, fall back to regular deletion
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    else:
                        os.remove(file_path)
            else:
                # Regular deletion
                print(f"Using regular deletion for: {file_path}")
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