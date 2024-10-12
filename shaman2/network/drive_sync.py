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


class DriveSync:

    # If modifying scopes, delete the file token.json.
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SHAMAN2_DRIVE_FOLDER_ID = "15ajPAAzJc9UK0fWxM3L3uOC0sprprPW4"

    def __init__(self,buildService = True):
        self.service = None
        if(buildService):
            self.buildDriveAPIService()

    #region === Setup ===

    # This method authenticates the current user with the Shaman2 Google Drive API project by either loading, refreshing,
    # or generating a new token.json file.
    def __authenticateDriveAPI(self):
        creds = None
        credentialsFilePath = paths["google"] / "credentials.json"
        tokenFilePath = paths["google"] / "token.json"
        # Load previously saved credentials, or authenticate if not found
        if(tokenFilePath.exists()):
            creds = Credentials.from_authorized_user_file(filename=tokenFilePath, scopes=self.SCOPES)
        if(not creds or not creds.valid):
            if(creds and creds.expired and creds.refresh_token):
                creds.refresh(Request())
            else:
                playsoundAsync(paths["media"] / "shaman_attention.mp3")
                flow = InstalledAppFlow.from_client_secrets_file(credentialsFilePath, self.SCOPES)
                creds = flow.run_local_server(port=0)
            with open(tokenFilePath, 'w') as tokenFile:
                tokenFile.write(creds.to_json())
        return creds
    # This method builds the Google Drive API service off of the user's credentials, then returns it.
    def buildDriveAPIService(self):
        creds = self.__authenticateDriveAPI()
        driveAPIService = build('drive', 'v3', credentials=creds)
        self.service = driveAPIService

    #endregion === Setup ===

    #region === File/Folder Handling ===

    # This method checks for or creates a nested subfolder path, returning the folder ID of the deepest folder.
    def __findCreateDriveFolderPath(self,driveFolderPath):
        folderNames = driveFolderPath.split('/')
        parentID = self.SHAMAN2_DRIVE_FOLDER_ID  # Start from the Shaman2 root folder

        for folderName in folderNames:
            query = f"'{parentID}' in parents and mimeType = 'application/vnd.google-apps.folder' and name = '{folderName}'"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])

            if(items):
                # If the folder exists, use its ID as the parent for the next folder
                parentID = items[0]['id']
            else:
                # Folder doesn't exist, create it
                folderMetadata = {
                    'name': folderName,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parentID]
                }
                folder = self.service.files().create(body=folderMetadata, fields='id').execute()
                log.info(f"Created folder {folderName} with ID {folder.get('id')} under parent {parentID}")
                # Set this as the new parent for the next folder
                parentID = folder.get('id')

        # Return the ID of the deepest folder (the target path to create)
        return parentID
    # This method simply attempts to return the ID of a file, by its name, in the Shaman2 Drive folder.
    def __findDriveFileByName(self, driveFileName, driveParentFolderID):
        query = f"'{driveParentFolderID}' in parents and name = '{driveFileName}'"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])

        if items:
            # Return the file ID of the existing file
            return items[0]['id']
        return None

    # Methods for uploading a localFile to Google Drive, and downloading a Google Drive file to a local path.
    def upload(self, localFilePath, driveFilePath):
        # First, we check if this is a drive path with subfolders, or root of the Shaman2 drive folder.
        # We also create missing subdirs if necessary.
        if("/" in driveFilePath):
            driveFolderPath, driveFileName = driveFilePath.rsplit("/", 1)
            driveParentFolderID = self.__findCreateDriveFolderPath(driveFolderPath=driveFolderPath)
        else:
            driveFileName = driveFilePath
            driveParentFolderID = self.SHAMAN2_DRIVE_FOLDER_ID

        # Set up the media upload object for the local file
        media = MediaFileUpload(localFilePath, resumable=True)

        # Now, we check to see if this fileName already exists, and if so, get its fileID.
        existingFileID = self.__findDriveFileByName(driveFileName=driveFileName, driveParentFolderID=driveParentFolderID)

        # If the file already exists, update it
        if(existingFileID):
            # Use the update method to replace the file contents
            driveFile = self.service.files().update(fileId=existingFileID, media_body=media).execute()
            log.info(f"Updated {driveFilePath} ({driveFile.get('id')}) with local {localFilePath}")
        else:
            # Otherwise, upload the file as a new file
            driveFileMetadata = {
                'name': os.path.basename(driveFileName),
                'parents': [driveParentFolderID]
            }
            driveFile = self.service.files().create(body=driveFileMetadata, media_body=media, fields='id').execute()
            log.info(f"Created {driveFilePath} ({driveFile.get('id')}) with local {localFilePath}")

        return driveFile.get('id')
    def download(self, localFilePath, driveFilePath):
        # First, we check if this is a drive path with subfolders, or root of the Shaman2 drive folder.
        if("/" in driveFilePath):
            driveFolderPath, driveFileName = driveFilePath.rsplit("/", 1)
            driveParentFolderID = self.__findCreateDriveFolderPath(driveFolderPath=driveFolderPath)
        else:
            driveFileName = driveFilePath
            driveParentFolderID = self.SHAMAN2_DRIVE_FOLDER_ID

        # Now, we check to see if this file exists, and if so, get its fileID.
        fileID = self.__findDriveFileByName(driveFileName=driveFileName, driveParentFolderID=driveParentFolderID)
        if(not fileID):
            log.warning(f"File '{driveFilePath}' not found in Drive folder.")
            return None

        # Download the file from Drive
        request = self.service.files().get_media(fileId=fileID)
        with io.FileIO(localFilePath, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                log.debug(f"Download {int(status.progress() * 100)}% complete for {driveFilePath}.")

        log.info(f"Downloaded {driveFilePath} to {localFilePath}")
        return localFilePath

    #endregion === File/Folder Handling ===

driveSync = DriveSync()
uploadResult = driveSync.upload(localFilePath=paths["config"] / "clients.toml",driveFilePath="test/clients.toml")
downloadResult = driveSync.download(localFilePath=paths["bin"] / "clients.toml",driveFilePath="test/clients.toml")