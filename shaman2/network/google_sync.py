import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']


# Step 1: Authenticate the user
def authenticate():
    creds = None
    # Load previously saved credentials, or authenticate if not found
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds


# Step 2: Build the Google Drive API service
def build_service():
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    return service


# Step 3: Upload a file to Google Drive
def upload_file(service, file_path, drive_folder_id=None):
    file_metadata = {'name': os.path.basename(file_path)}
    if drive_folder_id:
        file_metadata['parents'] = [drive_folder_id]

    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {file_path} with file ID {file.get('id')}")
    return file.get('id')


# Step 4: Download a file from Google Drive
def download_file(service, file_id, dest_path):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(dest_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")
    fh.close()


# Example usage
if __name__ == '__main__':
    service = build_service()

    # Upload a file (e.g., a .toml file)
    upload_file(service, 'devices.toml')

    # Download a file
    download_file(service, 'your_file_id_here', 'downloaded_file.toml')