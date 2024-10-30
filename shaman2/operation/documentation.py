import re
import time
from datetime import datetime
from shaman2.common.config import mainConfig, devices
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.utilities.shaman_utils import consoleUserWarning
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.network.sheets_sync import SheetSync


ordersSheet = SheetSync(spreadsheetID=mainConfig["google"]["ordersSheet"])

# This method stores the contents of an SNow order on the orders spreadsheet listed
# in mainConfig.
def storeSNowOrderToGoogle(taskNumber,orderNumber,userName,deviceID,datePlaced):
    for i in range(5):
        try:
            ordersSheet.addRows(mainConfig["google"]["snowSubSheet"],[[taskNumber,orderNumber,userName,devices[deviceID]["tmaModel"],datePlaced]])
            return True
        except Exception as e:
            time.sleep(5)
    return False



