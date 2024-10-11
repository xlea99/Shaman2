import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from shaman2.common.paths import paths
from shaman2.common.logger import log
from shaman2.utilities.async_sound import playsoundAsync

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SHAMAN2_DRIVE_FOLDER_ID = "15ajPAAzJc9UK0fWxM3L3uOC0sprprPW4"

# This method authenticates the current user with the Shaman2 Google Drive API project by either loading, refreshing,
# or generating a new token.json file.
def authenticateDriveAPI():
    creds = None
    credentialsFilePath = paths["google"] / "credentials.json"
    tokenFilePath = paths["google"] / "token.json"
    # Load previously saved credentials, or authenticate if not found
    if(tokenFilePath.exists()):
        creds = Credentials.from_authorized_user_file(filename=tokenFilePath, scopes=SCOPES)
    if(not creds or not creds.valid):
        if(creds and creds.expired and creds.refresh_token):
            creds.refresh(Request())
        else:
            playsoundAsync(paths["media"] / "shaman_attention.mp3")
            flow = InstalledAppFlow.from_client_secrets_file(credentialsFilePath, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(tokenFilePath, 'w') as tokenFile:
            tokenFile.write(creds.to_json())
    return creds

# This method builds the Google Drive API service off of the user's credentials, then returns it.
def buildDriveAPIService():
    creds = authenticateDriveAPI()
    _driveAPIService = build('drive', 'v3', credentials=creds)
    return _driveAPIService

# This method uploads the gives file to the Shaman2 folder in drive, and returns the fileID.
def uploadFile(service, filePath):
    fileMetadata = {
        'name': os.path.basename(filePath),
        'parents': [SHAMAN2_DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(filePath, resumable=True)
    file = service.files().create(body=fileMetadata, media_body=media, fields='id').execute()
    log.info(f"Uploaded {filePath} with file ID {file.get('id')}")
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

driveAPIService = buildDriveAPIService()
#result = uploadFile(service=driveAPIService,filePath=paths["config"] / "clients.toml")