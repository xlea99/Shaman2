import datetime
import os
import shutil
from shaman2.common.paths import validatePath

# Simple backup management function. Will attempt to back up the file given by filePath
# to the directory backupPath, keeping at maximum backupLimit backups at any time.
def backup(filePath, backupPath, backupLimit=10):
    # Validate and create backup directory if missing
    if not os.path.exists(backupPath):
        os.mkdir(backupPath)
    validatePath(pathToValidate = backupPath)

    # Get base filename and extension here
    baseName = os.path.basename(filePath)
    fileName,fileExtension = os.path.splitext(baseName)

    # Get list of existing backup files, and sort by creation date
    allFilesInBackupDir = os.listdir(backupPath)
    existingBackups = [f for f in allFilesInBackupDir if f.startswith(f"{fileName}_") and f.endswith(fileExtension)]
    existingBackups = sorted(existingBackups, key=lambda f: os.path.getmtime(os.path.join(backupPath, f)))

    # If we have reached the backup limit, delete the oldest file
    if len(existingBackups) >= backupLimit:
        os.remove(f"{backupPath}\\{existingBackups[0]}")

    # Create a backup
    dt = datetime.datetime.now()
    timestamp = dt.strftime("%m-%d-%Y--%H-%M-%S")
    backupFileName = f"{fileName}_{timestamp}{fileExtension}"
    shutil.copy(filePath, f"{backupPath}\\{backupFileName}")