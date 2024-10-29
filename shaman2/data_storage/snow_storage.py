import re
import datetime
from tomlkit.items import Array as tomlkitArray
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.utilities.async_sound import playsoundAsync





class SnowTask:

    def __init__(self):
        self.vals = { # Raw ticket values
                     "Number": None,
                     "Request": None,
                     "RequestItem": None,
                     "AssignmentGroup": None,
                     "AssignedTo": None,
                     "State": None,
                     "Priority": None,
                     "ShortDescription": None,
                     "Description": None,
                     "Activities": [],
                     # Classified values
                     "OrderEmployeeName": None,
                     "OrderSupervisorName": None,
                     "OrderShippingAddress": None,
                     "OrderDevice": None,
                     "OrderAccessoryBundle": None}

    # Simple getter and setter methods for accessing object like a dictionary.
    def __getitem__(self, item):
        return self.vals[item]
    def __setitem__(self, key, value):
        if(key == "Activities"):
            error = ValueError("Please use builtin 'addActivity' method to store note information.")
            log.error(error)
            raise error
        elif(key == "Description"):
            self.vals["Description"] = value
            self.__classifySnowOrderInfoFromDescription()
        else:
            self.vals[key] = value

    # Adder method for adding an activity, to ensure they conform to format.
    def addActivity(self,createdBy,timestamp,baseContent,emailContent):
        self.vals["Activities"].append({"CreatedBy": createdBy,"Timestamp": timestamp,"BaseContent": baseContent,"EmailContent": emailContent})

    #region === Helpers ===

    # This helper method attempts to classify the order text blob from SCTASK descriptions into a neat dictionary of relevant information
    def __classifySnowOrderInfoFromDescription(self):
        employeeNamePattern = r"Employee name:\s*([A-Za-z\s]+)(?=\s*Location:)"
        supervisorNamePattern = r"Supervisor:\s*([A-Za-z\s]+)(?=\s*Start Date:)"
        shippingAddressPattern = r"Address device to be shipped to:\s*(.+?)(?=\s*Device shipped will be)"
        devicePattern = r"Sysco standard (\w+) Device"
        accessoryBundlePattern = r"(Accessory bundle will be included)"

        employeeNameSearch = re.search(employeeNamePattern, self["Description"])
        supervisorNameSearch = re.search(supervisorNamePattern, self["Description"])
        shippingAddressSearch = re.search(shippingAddressPattern, self["Description"])
        deviceSearch = re.search(devicePattern, self["Description"])
        accessoryBundleSearch = re.search(accessoryBundlePattern, self["Description"])

        self.vals["OrderEmployeeName"] = employeeNameSearch.group(1).strip() if employeeNameSearch else None
        self.vals["OrderSupervisorName"] = supervisorNameSearch.group(1).strip() if supervisorNameSearch else None
        self.vals["OrderShippingAddress"] = shippingAddressSearch.group(1).strip() if shippingAddressSearch else None
        self.vals["OrderDevice"] = deviceSearch.group(1).strip() if deviceSearch else None
        self.vals["OrderAccessoryBundle"] = True if accessoryBundleSearch else False

    #endregion === Helpers ===