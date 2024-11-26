import time
from shaman2.common.config import mainConfig
from shaman2.common.logger import log
from shaman2.network.sheets_sync import syscoSheet




# This method stores the contents of an SCTASK order on the orders spreadsheet listed
# in mainConfig.
def storeSCTASKToGoogle(taskNumber,orderNumber,userName,deviceID,datePlaced):
    for i in range(5):
        try:
            syscoSheet.addRows(mainConfig["google"]["snowSubSheet"],[[taskNumber,orderNumber,userName,syscoSheet["Devices"][deviceID]["TMA Model"],datePlaced]])
            return True
        except Exception as e:
            time.sleep(3)
    return False

# This method "archives" the SCTASK number given from active orders to history on the sheet.
def archiveSCTASKOnGoogle(taskNumber,closedBy,serviceNumber,fullSCTASKSheet = None):
    if(not fullSCTASKSheet):
        fullSCTASKSheet = downloadSCTASKs()

    targetTask = None
    for existingTask in fullSCTASKSheet:
        if(existingTask["ServiceNow Ticket"].strip() == taskNumber.strip()):
            targetTask = existingTask
    if(targetTask is None):
        error = ValueError(f"Task number '{taskNumber}' doesn't seem to exist on sheet '{mainConfig["google"]["snowSubSheet"]}'")
        log.error(error)
        raise error

    # First, add the sctask to the archive
    for i in range(5):
        try:
            syscoSheet.addRows("SCTASKArchive",[[taskNumber,targetTask["Order"],targetTask["User"],targetTask["Device"],targetTask["Date Placed"],closedBy,serviceNumber]])
            break
        except Exception as e:
            time.sleep(3)
    # Then, remove the sctask from the active document.
    for i in range(5):
        try:
            syscoSheet.removeRows(sheetName=mainConfig["google"]["snowSubSheet"],columnName="ServiceNow Ticket",values=taskNumber)
            return True
        except Exception as e:
            time.sleep(3)
    return False

# This method downloads the full list of active SCTASK orders and returns it as a dictionary.
def downloadSCTASKs():
    for i in range(5):
        try:
            return syscoSheet.getFullSheet(mainConfig["google"]["snowSubSheet"])
        except Exception as e:
            time.sleep(3)
    return None


results = downloadSCTASKs()