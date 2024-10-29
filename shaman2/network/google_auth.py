from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from shaman2.common.paths import paths
from shaman2.utilities.async_sound import playsoundAsync

# If modifying scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file','https://www.googleapis.com/auth/spreadsheets']

# This method authenticates the current user with the Shaman2 Google Drive API project by either loading, refreshing,
# or generating a new token.json file.
def authenticateGoogleAPI():
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
    creds = authenticateGoogleAPI()
    driveAPIService = build('drive', 'v3', credentials=creds)
    service = driveAPIService
    return service
def buildSheetsAPIService():
    creds = authenticateGoogleAPI()
    sheetsAPIService = build('sheets', 'v4', credentials=creds)
    service = sheetsAPIService
    return service