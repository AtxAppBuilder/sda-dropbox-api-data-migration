import os
import time
import logging
import dropbox
from dropbox.exceptions import ApiError
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

# Step 1: Check for "memo" in filename
def has_memo_in_filename(filename):
    return 'memo' in filename.lower()

# Step 2: List folder contents using Dropbox API
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
    except ApiError as e:
        logging.error(f"Error listing Dropbox folder {folder_path}: {e}")
    return result

# Step 3: Move a file or folder to the archive
def move_to_archive(dbx, source_path, archive_path, dry_run=True):
    try:
        target_path = f"{archive_path}/{os.path.basename(source_path)}"
        if dry_run:
            logging.info(f"[DRY RUN] Would move {source_path} to {target_path}")
            return True
        dbx.files_move_v2(dropbox.files.RelocationArg(source_path, target_path))
        logging.info(f"Moved {source_path} to {target_path}")
        return True
    except ApiError as e:
        logging.error(f"Error moving {source_path} to {target_path}: {e}")
        return False

# Step 4: Process folder recursively
def process_folder(dbx, folder_path, archive_path, delete_empty_folders=True, dry_run=True):
    logging.info(f"Processing folder: {folder_path}")
    contents = list_dropbox_folder(dbx, folder_path, recursive=False)
    logging.info(f"Found {len(contents['memo_files'])} memo files, {len(contents['other_files'])} other files, and {len(contents['folders'])} folders.")

    # Move memo files to archive
    for file in contents['memo_files']:
        move_to_archive(dbx, file, archive_path, dry_run)

    # Move folders with exactly one memo file to archive
    for folder in contents['folders']:
        subfolder_path = folder
        subfolder_contents = list_dropbox_folder(dbx, subfolder_path, recursive=False)
        if (len(subfolder_contents['memo_files']) == 1 and 
            not subfolder_contents['other_files'] and 
            not subfolder_contents['folders']):
            move_to_archive(dbx, subfolder_path, archive_path, dry_run)
        else:
            process_folder(dbx, subfolder_path, archive_path, delete_empty_folders, dry_run)

# Step 5: Main function
def main():
    logging.info("Dropbox Folder Memo File Cleanup Tool started")
    print("Dropbox Folder Memo File Cleanup Tool")
    print("---------------------------------")
    
    dropbox_folder_paths = [
        "/renee killelea/$ jlr data migration/david"  # Source path
    ]
    archive_path = "/renee killelea/$ jlr data migration/david/archive"  # Archive path
    
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