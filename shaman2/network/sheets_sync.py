from shaman2.network.google_auth import buildSheetsAPIService
from shaman2.common.config import mainConfig
import time

class SheetSync:

    # Simple init method sets up google service and sets spreadsheetID.
    def __init__(self,googleService = None,spreadsheetID = None):
        if(not googleService):
            self.googleService = buildSheetsAPIService()
        else:
            self.googleService = googleService
        self.spreadsheetID = spreadsheetID

        self.fullSheet = None

    # This method reads the full, current sheet with the given name from the given spreadsheetID, formats it, and returns
    # it as a neat Pythonic data structure. Assumes that the top row is a header. If keyColumn is specified, it returns
    # it as a dictionary as a list, assuming that the given column contains a unique key.
    def getFullSheet(self, sheetName: str,keyColumn = None):
        sheets = self.googleService.spreadsheets()
        targetRange = f'{sheetName}!{self.getSheetColumns(sheetName=sheetName)}'
        result = sheets.values().get(spreadsheetId=self.spreadsheetID, range=targetRange).execute()
        values = result.get('values', [])

        headerVals = values[0]
        returnList = []
        for row in values[1:]:
            thisRowDict = {}
            for i in range(len(headerVals)):
                thisRowDict[headerVals[i]] = row[i] if i < len(row) else ""
            returnList.append(thisRowDict)

        self.fullSheet = returnList

        if(keyColumn is None):
            return returnList
        else:
            returnDict = {}
            for row in returnList:
                returnDict[row[keyColumn]] = row
            return returnDict

    # Simply returns a range of columns on the given sheetName
    def getSheetColumns(self, sheetName):
        # Fetch the sheet metadata
        sheet_metadata = self.googleService.spreadsheets().get(spreadsheetId=self.spreadsheetID).execute()
        sheets = sheet_metadata.get('sheets', '')
        for sheet in sheets:
            if sheet['properties']['title'] == sheetName:
                columnCount = sheet['properties']['gridProperties']['columnCount']
                rangeString = f'A:{chr(64 + columnCount)}'
                return rangeString
        return None
    # Simply returns the sheetID, given the sheetName
    def getSheetIDByName(self, sheetName):
        # Retrieve metadata about the spreadsheet
        spreadsheet = self.googleService.spreadsheets().get(spreadsheetId=self.spreadsheetID).execute()
        sheets = spreadsheet.get('sheets', '')

        # Search for the sheet name and return its ID
        for sheet in sheets:
            if sheet['properties']['title'] == sheetName:
                return sheet['properties']['sheetId']
        raise ValueError(f"sheetName with name '{sheetName}' not found in DeepEnd Spreadsheet!!")

    # Methods allowing for the addition and removal of rows for the given sheetName. addRows expects a list of row-lists,
    # removeRows simply expects a 1d list of keys and a column name to search and delete for.
    def addRows(self,sheetName, values):
        body = {
            'values': values
        }
        sheetColumns = self.getSheetColumns(sheetName=sheetName)
        result = self.googleService.spreadsheets().values().append(
            spreadsheetId=self.spreadsheetID,
            range=f"{sheetName}!{sheetColumns}",
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        print(f"Rows added: {result.get('updates').get('updatedRange')}")
    def removeRows(self, sheetName, columnName, values):
        rowsToRemove = []

        # Generating a raw list of row numbers needed to be deleted
        for index, existingRow in enumerate(self.fullSheet):
            # print(f"{index} | {existingRow} | {existingRow[columnName]}")
            if (existingRow[columnName] in values):
                rowsToRemove.append(index + 2)

        # Condense row numbers into runs wherever possible
        rowsToRemove.sort()
        rowRangesToRemove = []
        currentStart = rowsToRemove[0]
        currentEnd = rowsToRemove[0]
        for index in rowsToRemove[1:]:
            if (index == currentEnd + 1):
                currentEnd = index
            else:
                rowRangesToRemove.append((currentStart, currentEnd))
                currentStart = index
                currentEnd = index
        rowRangesToRemove.append((currentStart, currentEnd))

        # Sort in descending order to avoid accidental deletions
        rowRangesToRemove.sort(key=lambda x: x[0], reverse=True)

        # Actually requesting the removals
        requests = []
        thisSheetID = self.getSheetIDByName(sheetName=sheetName)
        for startRow, endRow in rowRangesToRemove:
            requests.append({
                'deleteDimension': {
                    'range': {
                        'sheetId': thisSheetID,
                        'dimension': 'ROWS',
                        'startIndex': startRow - 1,
                        'endIndex': endRow
                    }
                }
            })

        # If the number of deletion requests is very large, split into multiple batches
        if len(requests) > 100:
            # Implement batching logic here, split `requests` into chunks of 100
            counter = 0
            for start in range(0, len(requests), 100):
                end = start + 100
                batch_requests = requests[start:end]
                self.googleService.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheetID,
                                                          body={'requests': batch_requests}).execute()
                counter += 1
                print(f"Processed batch {counter} of removals...")
                time.sleep(5)
        else:
            body = {'requests': requests}
            response = self.googleService.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheetID, body=body).execute()
            print(f"Batch delete completed, total ranges: {len(rowRangesToRemove)}")



syscoSheet = SheetSync(spreadsheetID=mainConfig["google"]["ordersSheet"])

# Helper class just to allow the sysco data object to be reloaded from anywhere.
class __SyscoDataClass:

    def __init__(self,_syscoSheet):
        self.__syscoSheet = _syscoSheet
        self.data = None
        self.reload()

    # Using the sysco spreadsheet, this downloads and updates all sysco data.
    def reload(self):
        _syscoData = {"Devices": self.__syscoSheet.getFullSheet("Devices", keyColumn="DeviceID"),
                      "Accessories": self.__syscoSheet.getFullSheet("Accessories", keyColumn="AccessoryID"),
                      "CimplMappings": self.__syscoSheet.getFullSheet("CimplMappings", keyColumn="Cimpl Entry"),
                      "Carriers": self.__syscoSheet.getFullSheet("Carriers", keyColumn="Carrier"),
                      "Plans/Features": self.__syscoSheet.getFullSheet("Plans/Features", keyColumn="PlanID")}
        self.data = _syscoData

    def __getitem__(self, item):
        return self.data[item]
syscoData = __SyscoDataClass(syscoSheet)

