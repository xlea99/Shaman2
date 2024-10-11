import re
import datetime
from tomlkit.items import Array as tomlkitArray
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.common.config import accessories,deviceCimplMappings,accessoryCimplMappings
from shaman2.utilities.async_sound import playsoundAsync




# This class represents a single Cimpl Workorder, and provides various methods for interacting with it on a data
# level.
class CimplWO():

    def __init__(self):
        self.vals = {# Header info
                     "WONumber" : None,
                     "Status" : None,
                     "Carrier" : None,
                     "DueDate" : None,
                     "OperationType" : None,
                     # Summary info
                     "Comment" : None,
                     "ReferenceNumber" : None,
                     "Subject" : None,
                     "WorkorderOwner" : None,
                     "Requestor" : None,
                     "Notes" : [],
                     # Detail info
                     "ServiceID" : None,
                     "Account" : None,
                     "StartDate" : None,
                     "HardwareInfo" : [],
                     "Actions" : [],
                     # Scraped info
                     "UserFirstName" : None,
                     "UserLastName" : None,
                     "UserNetID" : None,
                     "UserShipping" : None,
                     "DeviceID" : [],
                     "AccessoryIDs" : [],
                     "EyesafeAccessoryID" : None}

    # Simple getter and setter methods for accessing object like a dictionary.
    def __getitem__(self, item):
        return self.vals[item]
    def __setitem__(self, key, value):
        if(key == "Note"):
            error = ValueError("Please use builtin 'addNote' method to store note information.")
            log.error(error)
            raise error
        elif(key == "Actions"):
            self.vals["Actions"] = value
            self.__scrapeActions()
        elif(key == "HardwareInfo"):
            self.vals["HardwareInfo"] = value
            self.__classifyHardwareInfo()
        else:
            self.vals[key] = value
    # Helper method for adding a note in a standardized way to the list of notes.
    def addNote(self,user,createdDate,subject,noteType,status,content,classifyNote = True):
        thisNote = {"User" : user,
                    "CreatedDate" : createdDate,
                    "Subject" : subject,
                    "Type" : noteType,
                    "Status" : status,
                    "Content" : content,
                    "Classification" : None,
                    "ClassifiedValue" : None,
                    "Timestamp" : None}

        # Classify the note
        if(classifyNote):
            thisNote = self.__classifyNote(thisNote)

        # Add a datetime timestamp for easy comparison.
        thisNote["Timestamp"] = datetime.datetime.strptime(thisNote["CreatedDate"], '%m/%d/%Y %I:%M %p')
        self.vals["Notes"].append(thisNote)

    # This helper method attempts to get the latest order placed per the notes (in case of multiple orders, it
    # always prefers the most recent) and returns the order number.
    def getLatestOrderNote(self):
        latestOrderNote = None
        for note in self.vals["Notes"]:
            if(note["Classification"].endswith("Order") and note["Classification"] not in ["EyesafeOrder"]):
                if(latestOrderNote):
                    if(note["Timestamp"] > latestOrderNote["Timestamp"]):
                        latestOrderNote = note
                else:
                    latestOrderNote = note
        return latestOrderNote

    #region === Internal Classification ===

    # This method attempts to classify the hardware information given into Shaman-compatible deviceIDs and
    # accessoryIDs.
    def __classifyHardwareInfo(self):
        # Helper function to attempt to read a value from either the device or accessories mappings config and,
        # if it's not present, prompt the user to add it an reload.
        def getSafeHardwareMapping(hardwareName,hardwareType):
            hardwareID = None
            try:
                if(hardwareType == "device"):
                    hardwareID = deviceCimplMappings[hardwareName.strip().strip('"')]
                elif(hardwareType == "accessory"):
                    hardwareID = accessoryCimplMappings[hardwareName.strip().strip('"')]
            except KeyError:
                playsoundAsync(paths["media"] / "shaman_attention.mp3")
                # TODO pretty duct-tapey, huh?
                _userResponse = input(f"Unknown Cimpl {hardwareType} detected: '{hardwareName}'. If this is a valid Cimpl {hardwareType}, add it to the {hardwareType}_cimpl_mappings.toml and press enter to reload the config. Type anything else to exit.")
                if (_userResponse):
                    _error = KeyError(f"'{hardwareName}' is not a mapped Cimpl {hardwareType}.")
                    log.error(_error)
                    raise _error
                else:
                    # If the user makes changes, reload the cimpl mappings program-wide to accommodate new changes.
                    if (hardwareType == "Device"):
                        deviceCimplMappings.reload()
                        hardwareID = deviceCimplMappings[hardwareName.strip().strip('"')]
                    elif (hardwareType == "Accessory"):
                        accessoryCimplMappings.reload()
                        hardwareID = accessoryCimplMappings[hardwareName.strip().strip('"')]
            return hardwareID

        # First, we build simple lists of all devices and accessories that are requested in the hardware info,
        # each mapped to the corresponding Shaman hardware ID.
        allDeviceIDs = []
        allAccessoryIDs = []
        if(self.vals["HardwareInfo"]):
            for hardware in self.vals["HardwareInfo"]:
                if (hardware["Type"] == "Equipment"):
                    thisDeviceID = getSafeHardwareMapping(hardware["Name"],"device")
                    if (isinstance(thisDeviceID, (list, tomlkitArray))):
                        allDeviceIDs.extend(thisDeviceID)
                    else:
                        allDeviceIDs.append(thisDeviceID)
                elif (hardware["Type"] == "Accessory"):
                    thisAccessoryID = getSafeHardwareMapping(hardware["Name"],"accessory")
                    if (isinstance(thisAccessoryID, (list, tomlkitArray))):
                        allAccessoryIDs.extend(thisAccessoryID)
                    else:
                        allAccessoryIDs.append(thisAccessoryID)

        # Check to ensure no duplicate device or accessory types due to a Sysco user getting a bit over-excited
        # with accessory the order page
        allDeviceIDs = list(set(allDeviceIDs))
        allAccessoryIDs = set(allAccessoryIDs)

        # At this point, there SHOULD only be one deviceID. If there's not, this order is definitely too complex
        # for the Shaman.
        if(len(allDeviceIDs) > 1):
            error = ValueError(f"More than one deviceID present in Cimpl WO {self.vals['WONumber']}: '{allDeviceIDs}' Can't be automated ATM.")
            log.error(error)
            raise error
        else:
            deviceID = allDeviceIDs[0] if allDeviceIDs else None

        # Now, we further flatten our accessories list, only allowing one accessory "type" per workorder.
        finalAccessoryIDs = set()
        usedTypes = set()
        for accessoryID in allAccessoryIDs:
            if (accessories[accessoryID]["type"] not in usedTypes):
                usedTypes.add(accessories[accessoryID]["type"])
                finalAccessoryIDs.add(accessoryID)

        # At this point, both our deviceID and accessoryIDs should be essentially complete. The only thing we
        # have left to accommodate for is a potential Eyesafe accessory. First, we find them all.
        eyesafeDevices = []
        for accessoryID in finalAccessoryIDs:
            if (accessories[accessoryID]["type"] == "eyesafe"):
                eyesafeDevices.append(accessoryID)
        # We remove them from the accessoryIDs list, since they're not considered accessories - they're
        # EyesafeAccessories and are ordered completely differently.
        for thisEyesafeDevice in eyesafeDevices:
            finalAccessoryIDs.discard(thisEyesafeDevice)
        # If the current deviceID doesn't have a compatible Eyesafe device, or if the brilliant supergenius Sysco
        # employee somehow found a way to order an incompatible Eyesafe accessory, we handle it here.
        finalEyesafeDevices = []
        for thisEyesafeDevice in eyesafeDevices:
            if(deviceID not in accessories[thisEyesafeDevice]["compatibleDevices"]):
                log.warning(f"A Sysco user added a non-compatible Eyesafe device to their order. '{thisEyesafeDevice}' is not compatible with chosen device '{deviceID}'.")
            else:
                finalEyesafeDevices.append(thisEyesafeDevice)
        # Finally, we set the list (and then get what should be the only remaining item) to account for duplicates.
        finalEyesafeDevices = list(set(finalEyesafeDevices))
        if(len(finalEyesafeDevices) > 1):
            error = ValueError(f"It should not be physically possible for you to be reading this. The fact you reached this code confirms that there are fundamental truths about logic and the universe that we've taken for granted that, not only may not be true, but may have warped our very understanding of philosophy and understanding. God help you, for the world is not what you thought it was.")
            log.error(error)
            raise error
        else:
            eyesafeDevice = finalEyesafeDevices[0] if finalEyesafeDevices else None

        self.vals["DeviceID"] = deviceID
        self.vals["AccessoryIDs"] = finalAccessoryIDs
        self.vals["EyesafeAccessoryID"] = eyesafeDevice
    # This method attempts to scrape various important values from a Cimpl actions list.
    def __scrapeActions(self,):
        for actionString in self.vals["Actions"]:
            # This action string contains both our user's netID AND their name.
            if(actionString.startswith("Assigned to Employee")):
                header, netID, rawName = actionString.split("-",2)
                lastName, firstName = rawName.split(",")
                netID = netID.strip()
                firstName = firstName.strip()
                lastName = lastName.strip()
                self.vals["UserFirstName"] = firstName
                self.vals["UserLastName"] = lastName
                self.vals["UserNetID"] = netID
            # This action string contains our raw shipping address.
            elif(actionString.startswith("Shipping Address")):
                self.vals["UserShipping"] = actionString.split("-")[1].strip()
    # This method attempts to classify a singe note dict into something more specific.
    @staticmethod
    def __classifyNote(noteDict):
        # If "eyesafe" is in the subject, we check to try and determine the order number of the eyesafe order.
        if("eyesafe" in noteDict["Subject"].lower()):
            eyesafeOrderPattern = r'\d+'

            # Value to eventually store the matches we found.
            orderMatch = None
            # Value to distinguish the type of order this is.
            orderType = None

            # Search for order number.
            eyesafeOrderMatch = re.findall(eyesafeOrderPattern,noteDict["Content"])
            if(eyesafeOrderMatch):
                orderMatch = eyesafeOrderMatch
                orderType = "EyesafeOrder"

            # If no match was found, assume this isn't an order number, or is an order number that the
            # Shaman doesn't recognize, and move to the next classification test.
            if(orderMatch):
                # Assume that we've now found the order number, we test to ensure multiple weren't detected.
                if(len(orderMatch) > 1):
                    error = ValueError(f"Multiple Eyesafe order numbers detected in note '{noteDict['Content']}'")
                    log.error(error)
                    raise error

                # Now, return the classified noteDict.
                noteDict["Classification"] = orderType
                noteDict["ClassifiedValue"] = orderMatch[0]
                return noteDict

        # If "order" is in the subject, we check to try and determine the order number/order type.
        if("order" in noteDict["Subject"].lower()):
            verizonOrderPattern = r"MB\d+"
            bakaOrderPattern = r"N\d{8}"

            # Value to eventually store the matches we found.
            orderMatch = None
            # Value to distinguish the type of order this is.
            orderType = None

            # Search for order numbers.
            verizonOrderMatch = re.findall(verizonOrderPattern,noteDict["Content"])
            bakaOrderMatch = re.findall(bakaOrderPattern,noteDict["Content"])

            if(verizonOrderMatch):
                if(orderMatch):
                    error = ValueError(f"Multiple order numbers from different carriers detected in this note: '{noteDict['Content']}'. Tf?")
                    log.error(error)
                    raise error
                orderMatch = verizonOrderMatch
                orderType = "VerizonOrder"
            if(bakaOrderMatch):
                if (orderMatch):
                    error = ValueError(f"Multiple order numbers from different carriers detected in this note: '{noteDict['Content']}'. Tf?")
                    log.error(error)
                    raise error
                orderMatch = bakaOrderMatch
                orderType = "BakaOrder"

            # If no match was found, assume this isn't an order number, or is an order number that the
            # Shaman doesn't recognize, and move to the next classification test.
            if(orderMatch):
                # Assume that we've now found the order number, we test to ensure multiple weren't detected.
                if(len(orderMatch) > 1):
                    error = ValueError(f"Multiple order numbers detected in note '{noteDict['Content']}'")
                    log.error(error)
                    raise error

                # Now, return the classified noteDict.
                noteDict["Classification"] = orderType
                noteDict["ClassifiedValue"] = orderMatch[0]
                return noteDict

        # IF "tracking" is in the subject, we check to try and determine the tracking number/courier type.
        if("tracking" in noteDict["Subject"].lower()):
            upsTrackingPattern = r"1Z[0-9A-Z]{16}$"
            # FedEX and Purolator tracking numbers are stupidly unpredictable, so we have to rely on there being
            # another tell in the note.
            fedexTrackingPattern = r"(?is)fedex.*?(\d{10,})"
            purolatorTrackingPattern = r"(?is)purolator.*?([a-zA-Z0-9]{10,})"

            # Value to eventually store the matches we found.
            trackingMatch = None
            # Value to distinguish the type of order this is.
            trackingType = None

            # Search for order numbers.
            upsTrackingMatch = re.findall(upsTrackingPattern,noteDict["Content"])
            fedexTrackingMatch = re.findall(fedexTrackingPattern,noteDict["Content"])
            purolatorTrackingMatch = re.findall(purolatorTrackingPattern,noteDict["Content"])

            if(upsTrackingMatch):
                if(trackingMatch):
                    error = ValueError(f"Multiple tracking numbers from different couriers detected in this note: '{noteDict['Content']}'. Tf?")
                    log.error(error)
                    raise error
                trackingMatch = upsTrackingMatch
                trackingType = "UPSTracking"
            if(fedexTrackingMatch):
                if(trackingMatch):
                    error = ValueError(f"Multiple tracking numbers from different couriers detected in this note: '{noteDict['Content']}'. Tf?")
                    log.error(error)
                    raise error
                trackingMatch = fedexTrackingMatch
                trackingType = "FEDEXTracking"
            if(purolatorTrackingMatch):
                if(trackingMatch):
                    error = ValueError(f"Multiple tracking numbers from different couriers detected in this note: '{noteDict['Content']}'. Tf?")
                    log.error(error)
                    raise error
                trackingMatch = purolatorTrackingMatch
                trackingType = "PurolatorTracking"

            # If no match was found, assume this isn't an order number, or is an order number that the
            # Shaman doesn't recognize, and move to the next classification test.
            if(trackingMatch):
                # Assume that we've now found the order number, we test to ensure multiple weren't detected.
                if(len(trackingMatch) > 1):
                    error = ValueError(f"Multiple tracking numbers detected in note '{noteDict['Content']}'")
                    log.error(error)
                    raise error

                # Now, return the classified noteDict.
                noteDict["Classification"] = trackingType
                noteDict["ClassifiedValue"] = trackingMatch[0]
                return noteDict

        # If we've gotten here, that means if wasn't able to classify the note as any other specific
        # type, so we just consider this "other".
        noteDict["Classification"] = "Other"
        noteDict["ClassifiedValue"] = None
        return noteDict

    #endregion === Internal Classification ===

