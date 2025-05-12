import os
import time
import logging
import dropbox
from dotenv import load_dotenv

# Setup logging with timestamps
logging.basicConfig(
    filename='cleanup_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
if not DROPBOX_ACCESS_TOKEN:
    raise ValueError("DROPBOX_ACCESS_TOKEN not found in .env file.")

# Initialize Dropbox client with your friend’s token
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def has_memo_in_filename(filename):
    return 'memo' in filename.lower()

def create_archive_folder(dbx, archive_path):
    """Create an archive folder in Dropbox if it doesn't exist."""
    try:
        dbx.files_get_metadata(archive_path)
        logging.info(f"Archive folder already exists: {archive_path}")
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            try:
                dbx.files_create_folder_v2(archive_path)
                logging.info(f"Created archive folder: {archive_path}")
            except dropbox.exceptions.ApiError as e:
                logging.error(f"Error creating archive folder {archive_path}: {e}")
                raise
        else:
            logging.error(f"Error checking archive folder {archive_path}: {e}")
            raise

def list_dropbox_folder(dbx, folder_path, recursive=True):
    result = {
        'memo_files': [],
        'other_files': [],
        'folders': []
    }
    try:
        response = dbx.files_list_folder(folder_path, recursive=recursive)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                if has_memo_in_filename(entry.name):
                    result['memo_files'].append(entry.path_lower)
                else:
                    result['other_files'].append(entry.path_lower)
            elif isinstance(entry, dropbox.files.FolderMetadata):
                result['folders'].append(entry.path_lower)
        
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            for entry in response.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    if has_memo_in_filename(entry.name):
                        result['memo_files'].append(entry.path_lower)
                    else:
                        result['other_files'].append(entry.path_lower)
                elif isinstance(entry, dropbox.files.FolderMetadata):
                    result['folders'].append(entry.path_lower)
    except dropbox.exceptions.ApiError as e:
        logging.error(f"Error listing Dropbox folder {folder_path}: {e}")
    return result

def move_dropbox_file(dbx, file_path, archive_path, dry_run=True):
    """Move a file in Dropbox to the archive folder."""
    new_path = os.path.join(archive_path, os.path.basename(file_path))
    if dry_run:
        logging.info(f"[DRY RUN] Would move file: {file_path} to {new_path}")
        return True
    try:
        dbx.files_move_v2(file_path, new_path, allow_ownership_transfer=True)
        logging.info(f"Moved file: {file_path} to {new_path}")
        return True
    except dropbox.exceptions.ApiError as e:
        logging.error(f"Error moving file {file_path} to {new_path}: {e}")
        return False

def move_dropbox_folder(dbx, folder_path, archive_path, dry_run=True):
    """Move a folder in Dropbox to the archive folder."""
    new_path = os.path.join(archive_path, os.path.basename(folder_path))
    if dry_run:
        logging.info(f"[DRY RUN] Would move folder: {folder_path} to {new_path}")
        return True
    try:
        dbx.files_move_v2(folder_path, new_path, allow_ownership_transfer=True)
        logging.info(f"Moved folder: {folder_path} to {new_path}")
        return True
    except dropbox.exceptions.ApiError as e:
        logging.error(f"Error moving folder {folder_path} to {new_path}: {e}")
        return False

def process_folder(dbx, folder_path, archive_path, delete_empty_folders=True, dry_run=True):
    logging.info(f"Processing folder: {folder_path}")
    contents = list_dropbox_folder(dbx, folder_path, recursive=False)
    logging.info(f"Found {len(contents['memo_files'])} memo files, {len(contents['other_files'])} other files, and {len(contents['folders'])} folders.")

    # Move all "memo" files in the current folder to the archive
    for file in contents['memo_files']:
        move_dropbox_file(dbx, file, archive_path, dry_run)

    # Process subfolders
    for folder in contents['folders']:
        subfolder_path = folder
        subfolder_contents = list_dropbox_folder(dbx, subfolder_path, recursive=False)
        if (len(subfolder_contents['memo_files']) == 1 and 
            not subfolder_contents['other_files'] and 
            not subfolder_contents['folders']):
            # Move the single "memo" file and the folder to the archive
            all_moved = True
            for file in subfolder_contents['memo_files']:
                if not move_dropbox_file(dbx, file, archive_path, dry_run):
                    all_moved = False
            if all_moved:
                move_dropbox_folder(dbx, subfolder_path, archive_path, dry_run)
            else:
                logging.info(f"Could not move the memo file in {subfolder_path}, skipping folder move.")
        else:
            # Recursively process the subfolder
            process_folder(dbx, subfolder_path, archive_path, delete_empty_folders, dry_run)

def main():
    logging.info("Dropbox Folder Memo File Cleanup Tool started")
    print("Dropbox Folder Memo File Cleanup Tool")
    print("---------------------------------")
    
    dropbox_folder_paths = [
        "/path/to/shared/folder"  # Replace with the folder path in your friend’s Dropbox
    ]
    archive_path = "/path/to/shared/folder/Archive"  # Archive folder in your friend’s Dropbox
    
    # Create the archive folder
    create_archive_folder(dbx, archive_path)
    
    for folder_path in dropbox_folder_paths:
        try:
            print(f"\nProcessing folder: {folder_path}")
            start_time = time.time()
            process_folder(dbx, folder_path, archive_path, dry_run=True)
            print(f"Completed in {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logging.error(f"Error processing folder {folder_path}: {e}")
            print(f"Error processing folder {folder_path}: {e}")
    
    print("\nAnalysis and cleanup process completed! Set dry_run=False to perform actual moves.")
    logging.info("Analysis and cleanup process completed.")

if __name__ == "__main__":
    main()