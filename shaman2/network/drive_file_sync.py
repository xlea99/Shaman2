import os
import io
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from shaman2.common.paths import paths
from shaman2.common.logger import log
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.network.google_auth import buildDriveAPIService


class DriveFileSync:

    SHAMAN2_DRIVE_FOLDER_ID = "15ajPAAzJc9UK0fWxM3L3uOC0sprprPW4"

    # Simple __init__ method
    def __init__(self,googleService = None):
        self.service = None
        if(not googleService):
            self.service = buildDriveAPIService()

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

#driveSync = DriveFileSync()
#uploadResult = driveSync.upload(localFilePath=paths["config"] / "clients.toml",driveFilePath="test/clients.toml")
#downloadResult = driveSync.download(localFilePath=paths["bin"] / "clients.toml",driveFilePath="test/clients.toml")