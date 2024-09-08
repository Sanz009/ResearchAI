import os

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from mongo_db_ops import get_tokens

SCOPES = ['https://www.googleapis.com/auth/drive.file']


# Authentication function (synchronous)
def authenticate(username=None):
    creds = get_tokens(username)
    service = build('drive', 'v3', credentials=creds)
    return service


# Create folder function (synchronous)
def create_folder(service, folder_name):
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    # Synchronous call to create the folder
    file = service.files().create(body=file_metadata, fields='id').execute()
    return file.get('id')


# Upload file function (synchronous)
def upload_file(service, file_path, folder_id):
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path)
    # Synchronous call to upload the file
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')


# Download file function (synchronous)
def download_file(service, file_id, destination):
    request = service.files().get_media(fileId=file_id)
    with open(destination, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            # Synchronous call to download the file chunk by chunk
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")
