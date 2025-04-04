import re
from datetime import datetime
import time
from selenium.webdriver.common.by import By
from shaman2.selenium.browser import Browser
from shaman2.selenium.baka_driver import BakaDriver
from shaman2.selenium.cimpl_driver import CimplDriver
from shaman2.selenium.tma_driver import TMADriver, TMALocation, TMAPeople, TMAService,TMAEquipment, TMACost
from shaman2.selenium.verizon_driver import VerizonDriver
from shaman2.selenium.eyesafe_driver import EyesafeDriver
from shaman2.selenium.snow_driver import SnowDriver
from shaman2.selenium.outlook_driver import OutlookDriver
from shaman2.operation import maintenance
from shaman2.operation import documentation
from shaman2.common.config import mainConfig
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.network.sheets_sync import syscoData
from shaman2.utilities.shaman_utils import convertServiceIDFormat,convertStateFormat, consoleUserWarning, validateCarrier
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.utilities.address_validation import validateAddress
from shaman2.utilities.misc import isNumber

DEFAULT_SNOW_IPHONE = "iPhone14_128GB"
DEFAULT_SNOW_ANDROID = "GalaxyS24_128GB"
DEFAULT_SNOW_IPHONE_CASE = syscoData["Devices"][DEFAULT_SNOW_IPHONE]["Verizon Wireless Default Case"]
DEFAULT_SNOW_ANDROID_CASE = syscoData["Devices"][DEFAULT_SNOW_ANDROID]["Verizon Wireless Default Case"]
DEFAULT_SNOW_CHARGER = syscoData["Devices"][DEFAULT_SNOW_IPHONE]["Verizon Wireless AlwaysOrder Accessories"]

def standardizeToDateObject(dateString,carrier):
    VERIZON_DATE_FORMAT = "%m/%d/%Y"
    ATT_DATE_FORMAT = "%m/%d/%Y"
    BELL_DATE_FORMAT = "%m/%d/%Y"
    ROGERS_DATE_FORMAT = "%B %d %Y %I:%M %p"

    if carrier == "Verizon Wireless":
        return datetime.strptime(dateString,VERIZON_DATE_FORMAT)
    elif carrier == "Bell Mobility":
        return datetime.strptime(dateString,BELL_DATE_FORMAT)
    elif carrier == "Rogers":
        return datetime.strptime(dateString,ROGERS_DATE_FORMAT)
    elif carrier == "AT&T Mobility":
        return datetime.strptime(dateString, ATT_DATE_FORMAT)
    else:
        error = ValueError(f"Invalid carrier to convert date format for: {carrier}")
        log.error(error)
        raise error

#region === Device, Accessory, and Plan Validation ===

# Given a deviceID and a carrier, this method returns single plan and a list of extra features.
def getPlansAndFeatures(deviceID,carrier):
    carrier = validateCarrier(carrier)
    mainPlanID = syscoData["Devices"][deviceID][f"{carrier} Plan"]
    featureIDs = syscoData["Devices"][deviceID][f"{carrier} Features"].split(",") if syscoData["Devices"][deviceID][f"{carrier} Features"] else []
    mainPlan = syscoData["Plans/Features"][mainPlanID]
    features = []
    for featureID in featureIDs:
        features.append(syscoData["Plans/Features"][featureID.strip()])
    return mainPlan,features

# Given a deviceID and a carrier, returns either a deviceID or None depending on specifications in the SyscoData
# such as fallbacks and carrier orderability.
def validateDeviceID(deviceID,carrier):
    carrier = validateCarrier(carrier)
    deviceOrderableCarriers = syscoData["Devices"][deviceID]["Orderable Carriers"].split(",") if syscoData["Devices"][deviceID]["Orderable Carriers"] else []
    deviceOrderableCarriers = [thisCarrier.strip() for thisCarrier in deviceOrderableCarriers]
    # If the carrier is listed as orderable for this device, we're good to go and simply return the deviceID as is.
    if carrier in deviceOrderableCarriers:
        return deviceID
    # Otherwise, we first try to fallback.
    else:
        fallbackDevice = syscoData["Devices"][deviceID][f"Fallback ({carrier})"].strip()
        # If a fallback device is found, we try to validate this instead.
        if fallbackDevice != "":
            return validateDeviceID(deviceID=fallbackDevice,carrier=carrier)
        # Otherwise, we've reached the end of the line and simply return none.
        else:
            return None

# Given a deviceID, a carrier, and a list of accessoryIDs, this returns a list of accessoryIDs (and potentially special
# accessory types) validated against the device and carrier.
def validateAccessoryIDs(deviceID,carrier,accessoryIDs,removeDuplicateTypes=True):
    print(f"INITIAL ACCESSORIES LIST: {accessoryIDs}")
    carrier = validateCarrier(carrier)
    # First, we ensure the accessoryIDs list has only unique accessoryIDs in it.
    accessoryIDs = list(set(accessoryIDs))

    # Now, we add in any extra "alwaysOrder" accessoryIDs as specified by the spreadsheet.
    fullAccessoryIDs = accessoryIDs
    if f"{carrier} AlwaysOrder Accessories" in syscoData["Devices"][deviceID].keys():
        extraAccessories = syscoData["Devices"][deviceID][f"{carrier} AlwaysOrder Accessories"].split(",") if syscoData["Devices"][deviceID][f"{carrier} AlwaysOrder Accessories"] else []
        extraAccessories = [extraAccessory.strip() for extraAccessory in extraAccessories]
        fullAccessoryIDs.extend(extraAccessories)

    # Helper methods to check availability and compatibility of a single accessoryID.
    def checkAccessoryAvailability(_accessoryID):
        if _accessoryID not in syscoData["Accessories"].keys():
            error = ValueError(f"Invalid accessoryID in list: '{_accessoryID}'")
            log.error(error)
            raise error
        return syscoData["Accessories"][_accessoryID][f"Available ({carrier})"] == "TRUE"
    def checkAccessoryCompatibility(_accessoryID):
        compatibleDevices = syscoData["Accessories"][_accessoryID]["Compatible Devices"].split(",") if syscoData["Accessories"][_accessoryID]["Compatible Devices"] else []
        compatibleDevices = [thisDevice.strip() for thisDevice in compatibleDevices]
        return deviceID in compatibleDevices
    # Helper method to handle accessory substitution.
    def substituteSingleAccessory(_accessoryID):
        targetAccessory = _accessoryID
        foundValidAccessory = False
        triedDefault = False

        # First, get a set of all accessories of the given _accessoryID's type that are both compatible AND available.
        validPotentialAccessoryIDs = []
        for configuredAccessoryID,configuredAccessory in syscoData["Accessories"].items():
            if configuredAccessory["Accessory Type"] == syscoData["Accessories"][_accessoryID]["Accessory Type"]:
                if checkAccessoryAvailability(configuredAccessoryID):
                    if checkAccessoryCompatibility(configuredAccessoryID):
                        validPotentialAccessoryIDs.append(configuredAccessoryID)

        # Loop to manage final device substitution.
        while not foundValidAccessory:
            # Test if the accessory is available and compatible.
            if checkAccessoryAvailability(targetAccessory) and checkAccessoryCompatibility(targetAccessory):
                foundValidAccessory = True
                break
            # If not, try to substitute.
            else:
                # Cases have preconfigured "Default Cases" that we fall back to first.
                if (syscoData["Accessories"][_accessoryID]["Accessory Type"] == "Case" and
                        f"{carrier} Default Case" in syscoData["Devices"][deviceID].values() and
                        not triedDefault):
                    triedDefault = True
                    defaultCase = syscoData["Device"][deviceID][f"{carrier} Default Case"].strip()
                    targetAccessory = defaultCase
                    continue
                # Otherwise, try to substitute from the list of valid accessories.
                else:
                    if len(validPotentialAccessoryIDs) == 0:
                        break
                    else:
                        targetAccessory = validPotentialAccessoryIDs.pop(0)

        return targetAccessory if foundValidAccessory else None

    validatedAccessoryIDs = []
    for thisAccessoryID in fullAccessoryIDs:
        substitutedAccessoryID = substituteSingleAccessory(thisAccessoryID)
        if substitutedAccessoryID:
            validatedAccessoryIDs.append(substitutedAccessoryID)

    # If set to removeDuplicateTypes, we do that here, simply prioritizing the first valid accessory of each type.
    if removeDuplicateTypes:
        cleanedAccessoryIDs = []
        usedAccessoryTypes = set()
        for accessoryID in validatedAccessoryIDs:
            if syscoData["Accessories"][accessoryID]["Accessory Type"] not in usedAccessoryTypes:
                usedAccessoryTypes.add(syscoData["Accessories"][accessoryID]["Accessory Type"])
                cleanedAccessoryIDs.append(accessoryID)
            else:
                log.info(f"Skipping accessory '{accessoryID}', as it has a duplicate type to other accessories in the list.")
    else:
        cleanedAccessoryIDs = validatedAccessoryIDs

    # Finally, we filter out any special accessories, putting them in their own return structures.
    finalAccessoryIDs = []
    eyesafeAccessories = []
    for accessoryID in cleanedAccessoryIDs:
        if syscoData["Accessories"][accessoryID]["Accessory Type"] == "Eyesafe":
            eyesafeAccessories.append(accessoryID)
        else:
            finalAccessoryIDs.append(accessoryID)

    # We should now be left with a list of nuclear, validated, clean accessoryIDs, as well as potential special
    # accessory type. We return this as a dict.
    returnDict = {"AccessoryIDs" : finalAccessoryIDs, "EyesafeAccessoryIDs" : eyesafeAccessories}
    print(f"FINAL ACCESSORIES DICT: {returnDict}")
    return returnDict


#endregion === Device, Accessory, and Plan Validation ===
#region === Carrier Order Reading ===

# Searches up, and reads, a full Verizon order number.
def readVerizonOrder(verizonDriver : VerizonDriver,verizonOrderNumber,orderViewPeriod):
    maintenance.validateVerizon(verizonDriver)
    verizonDriver.navToOrderViewer()

    verizonDriver.OrderViewer_UpdateOrderViewDropdown(orderViewPeriod)
    verizonDriver.OrderViewer_SearchOrder(orderNumber=verizonOrderNumber)

    result = verizonDriver.OrderViewer_ReadDisplayedOrder()
    return result.data

# Searches up, and reads, a full Baka order number.
def readBakaOrder(bakaDriver : BakaDriver,bakaOrderNumber):
    maintenance.validateBaka(bakaDriver)

    bakaDriver.navToOrderHistory()
    bakaDriver.openOrder(bakaOrderNumber)
    return bakaDriver.readOrder()

def readRogersOrder(uplandOutlookDriver : OutlookDriver, sysOrdBoxOutlookDriver : OutlookDriver,
                    rogersOrderNumber):
    maintenance.validateSysOrdBoxOutlook(sysOrdBoxOutlookDriver=sysOrdBoxOutlookDriver,uplandOutlookDriver=uplandOutlookDriver)

    # This helper method parses a raw Rogers order email string into a neat python dictionary.
    def parseRawRogersOrder(rogersOrderString):
        rogersOrderParse = {
            "OrderNumber": r"Order Number\s+(\d+)",
            "OrderDate": r"Order Date\s+(.*)",
            "OrderType": r"(?:.|\n)*Order Type\s+(.*)",
            "TrackingNumber": r"Waybill No.\s+(\w+)",
            "UserName": r"Subscriber Name\s+(.*)",
            "WirelessNumber": r"Phone Number\s+(.*)",
            "IMEI": r"IMEI\s+(\d+)"
        }

        returnDict = {}
        for key, pattern in rogersOrderParse.items():
            matches = re.findall(pattern, rogersOrderString)
            if matches:
                returnDict[key] = matches[0]
        #TODO glue?
        returnDict["Courier"] = "Purolator"
        return returnDict

    sysOrdBoxOutlookDriver.searchForTerm(searchTerm=rogersOrderNumber)
    searchResults = sysOrdBoxOutlookDriver.readAllVisibleEmailSummaries()

    targetEmail = None
    for result in searchResults:
        if result["Subject"].strip() == f"Order {rogersOrderNumber} Closed" and result["SenderEmail"] == "mheather@imaginewireless.net":
            targetEmail = result
    if not targetEmail:
        return False


    sysOrdBoxOutlookDriver.openVisibleEmail(targetEmail)
    rawRogersOrderString = sysOrdBoxOutlookDriver.readOpenEmailFullContent()
    return parseRawRogersOrder(rawRogersOrderString)

#endregion === Carrier Order Reading ===
#region === Carrier Order Placing ===

# Places an entire Verizon new install.
def placeVerizonNewInstall(verizonDriver : VerizonDriver,deviceID : str,accessoryIDs : list,plan,features,
                           firstName,lastName,userEmail,
                           address1,city,state,zipCode,companyName,contactEmails : str | list,
                           address2="",reviewMode = True,emptyCart=True,deviceColor=None):
    maintenance.validateVerizon(verizonDriver)

    if emptyCart:
        verizonDriver.emptyCart()

    # Search for the device, click on it, select contract, and add to cart.
    verizonDriver.shopNewDevice()
    verizonDriver.DeviceSelection_SearchSelectDevice(deviceID=deviceID,orderPath="NewInstall")
    verizonDriver.DeviceSelection_DeviceView_SelectSizeColor(deviceID=deviceID,colorName=deviceColor,orderPath="NewInstall")
    if deviceID != "iPad11_128GB": #TODO glue
        verizonDriver.DeviceSelection_DeviceView_Select2YearContract(orderPath="NewInstall")
    verizonDriver.DeviceSelection_DeviceView_AddToCartAndContinue(orderPath="NewInstall")
    # This should send us to the Accessories shopping screen.

    # Search for each requested accessory, add it to the cart, then continue.
    for accessoryID in accessoryIDs:
        if accessoryID:
            verizonDriver.AccessorySelection_SearchForAccessory(accessoryID=accessoryID)
            verizonDriver.AccessorySelection_AddAccessoryToCart(accessoryID=accessoryID)
    verizonDriver.AccessorySelection_Continue(orderPath="NewInstall")
    # This should send us to the plan selection page.

    # Select plan, then click continue.
    deviceType = syscoData["Devices"][deviceID]["TMA Sub Type"]
    verizonDriver.PlanSelection_SelectPlan(planID=plan["Carrier Lookup Code"])
    verizonDriver.PlanSelection_Continue()
    # This should send us to the device protection page.

    # We simply decline device protection and continue.
    verizonDriver.DeviceProtection_DeclineAndContinue()
    # This should send us to the number assignment page.

    # Generate the number and fill in user information.
    verizonDriver.NumberSelection_SelectAreaCode(zipCode=zipCode)
    verizonDriver.NumberSelection_NavToAddUserInformation()
    verizonDriver.UserInformation_EnterBasicInfo(firstName=firstName,lastName=lastName,email=userEmail)
    verizonDriver.UserInformation_EnterAddressInfo(address1=address1,address2=address2,city=city,
                                                   stateAbbrev=convertStateFormat(stateString=state,targetFormat="abbreviation"),zipCode=zipCode)
    verizonDriver.UserInformation_SaveInfo()
    verizonDriver.NumberSelection_Continue()
    # This should send us to the shopping cart page.

    # Add any necessary features.
    if features:
        verizonDriver.ShoppingCart_AddFeatures()
        for feature in features:
            verizonDriver.FeatureSelection_SelectFeature(featureName=feature["Carrier Lookup Code"])
        verizonDriver.FeatureSelection_Continue()
    # This should send us back to the shopping cart page.

    # Continue from shopping cart to checkout
    verizonDriver.ShoppingCart_ContinueToCheckOut()
    # This should send us to the checkout screen

    # "Clean" the contact emails for special characters which break Verizon.
    if type(contactEmails) is not list:
        contactEmails = [contactEmails]
    finalContactEmails = []
    for contactEmail in contactEmails:
        if contactEmail is None:
            continue
        contactEmail = contactEmail.lower().strip()
        isValidEmail = True
        for character in contactEmail:
            if not (character.isalnum() or character in "._@"):
                isValidEmail = False
        if isValidEmail:
            finalContactEmails.append(contactEmail)



    # Fill in shipping information, then submit the order.
    verizonDriver.Checkout_AddAddressInfo(company=companyName,attention=f"{firstName} {lastName}",
                                          address1=address1,address2=address2,city=city,zipCode=zipCode,
                                          stateAbbrev=convertStateFormat(stateString=state,targetFormat="abbreviation"),
                                          contactPhone=mainConfig["misc"]["contactPhone"],notificationEmails=finalContactEmails)
    if reviewMode:
        playsoundAsync(paths["media"] / "shaman_order_ready.mp3")
        userResponse = input("Order is ready to be submitted. Please review, then press enter to place. Type anything else to cancel.")
        if userResponse:
            error = ValueError("User cancelled submission of order.")
            log.error(error)
            raise error
    maintenance.validateVerizon(verizonDriver)
    orderInfo = verizonDriver.Checkout_PlaceOrder(billingAccountNum=syscoData["Carriers"]["Verizon Wireless"]["Account Number"])
    # Order should now be placed!

    return orderInfo
# Places an entire Verizon new install.
def placeVerizonUpgrade(verizonDriver : VerizonDriver,serviceID,deviceID : str,accessoryIDs : list,
                           firstName,lastName,
                           address1,city,state,zipCode,companyName,contactEmails : str | list,
                        address2="",reviewMode = True,emptyCart=True,deviceColor=None):
    maintenance.validateVerizon(verizonDriver)

    if emptyCart:
        verizonDriver.emptyCart()

    # Pull up the line and click "upgrade"
    verizonDriver.pullUpLine(serviceID=serviceID)
    upgradeStatus = verizonDriver.LineViewer_UpgradeLine()
    if upgradeStatus in ["NotETFEligible", "MTNPending"]:
        return upgradeStatus
    # This should send us to the device selection page.

    # Search for the device, click on it, select contract, and add to cart.
    verizonDriver.DeviceSelection_SearchSelectDevice(deviceID=deviceID,orderPath="Upgrade")
    verizonDriver.DeviceSelection_DeviceView_SelectSizeColor(deviceID=deviceID, colorName=deviceColor,orderPath="Upgrade")
    verizonDriver.DeviceSelection_DeviceView_Select2YearContract(orderPath="Upgrade")
    verizonDriver.DeviceSelection_DeviceView_DeclineDeviceProtection()
    verizonDriver.DeviceSelection_DeviceView_AddToCartAndContinue(orderPath="Upgrade")
    # This should send us straight to the shopping cart.

    # We immediately go back to add accessories from the shopping cart.
    verizonDriver.ShoppingCart_AddAccessories()
    # This should send us to the Accessories shopping screen.

    # Search for each requested accessory, add it to the cart, then continue.
    for accessoryID in accessoryIDs:
        print(f"Searching for accessory '{accessoryID}'")
        verizonDriver.AccessorySelection_SearchForAccessory(accessoryID=accessoryID)
        verizonDriver.AccessorySelection_AddAccessoryToCart(accessoryID=accessoryID)
    verizonDriver.AccessorySelection_Continue(orderPath="Upgrade")
    # This should send us back to the shopping cart.

    # Continue from shopping cart to checkout
    verizonDriver.ShoppingCart_ContinueToCheckOut()
    # This should send us to the checkout screen


    # "Clean" the contact emails for special characters which break Verizon.
    if type(contactEmails) is not list:
        contactEmails = [contactEmails]
    finalContactEmails = []
    for contactEmail in contactEmails:
        contactEmail = contactEmail.lower().strip()
        isValidEmail = True
        for character in contactEmail:
            if not (character.isalnum() or character in "._@"):
                isValidEmail = False
        if isValidEmail:
            finalContactEmails.append(contactEmail)

    # Fill in shipping information, then submit the order.
    verizonDriver.Checkout_AddAddressInfo(company=companyName,attention=f"{firstName} {lastName}",
                                          address1=address1,address2=address2,city=city,zipCode=zipCode,
                                          stateAbbrev=convertStateFormat(stateString=state,targetFormat="abbreviation"),
                                          contactPhone=mainConfig["misc"]["contactPhone"],notificationEmails=finalContactEmails)
    if reviewMode:
        playsoundAsync(paths["media"] / "shaman_order_ready.mp3")
        userResponse = input("Order is ready to be submitted. Please review, then press enter to place. Type anything else to cancel.")
        if userResponse:
            error = ValueError("User cancelled submission of order.")
            log.error(error)
            raise error
    maintenance.validateVerizon(verizonDriver)
    orderInfo = verizonDriver.Checkout_PlaceOrder(billingAccountNum=syscoData["Carriers"]["Verizon Wireless"]["Account Number"])
    # Order should now be placed!

    return orderInfo

# Places an entire Eyesafe order.
def placeEyesafeOrder(eyesafeDriver : EyesafeDriver,eyesafeAccessoryID : str,
                      userFirstName : str, userLastName : str,
                      address1,city,state,zipCode,phoneNumber,address2 = None):
    maintenance.validateEyesafe(eyesafeDriver)

    eyesafeDriver.navToShop()
    eyesafeDriver.addItemToCart(itemName=syscoData["Accessories"][eyesafeAccessoryID]["Eyesafe Card Name"])
    eyesafeDriver.checkOutFromCart()
    return eyesafeDriver.checkOutAndSubmit(firstName=userFirstName,lastName=userLastName,
                                           address1=address1,address2=address2,city=city,state=state,zipCode=zipCode,
                                           phoneNumber=phoneNumber)

# Adds service information to Cimpl (service num, install date, account) and applies it.
def writeServiceToCimplWorkorder(cimplDriver : CimplDriver,serviceNum,carrier,installDate):
    maintenance.validateCimpl(cimplDriver)

    currentLocation = cimplDriver.getLocation()
    if not currentLocation["Location"].startswith("Workorder_"):
        error = ValueError("Couldn't run writeServiceToCimplWorkorder, as Cimpl Driver is not currently on a workorder!")
        log.error(error)
        raise error

    cimplDriver.Workorders_NavToDetailsTab()
    cimplDriver.Workorders_WriteServiceID(serviceID=convertServiceIDFormat(serviceNum,targetFormat="raw"))
    cimplDriver.Workorders_WriteAccount(accountNum=syscoData['Carriers'][carrier]["Account Number"])
    cimplDriver.Workorders_WriteStartDate(startDate=standardizeToDateObject(dateString=installDate,carrier=carrier).strftime("%m/%d/%Y"))

    cimplDriver.Workorders_ApplyChanges()

#endregion === Carrier Order Placing ===
#region === Ticketing Service Management ===

# Searches up, and reads, a full SCTASK in Snow given taskNumber
def readSnowTask(snowDriver : SnowDriver,taskNumber):
    maintenance.validateSnow(snowDriver)
    snowDriver.navToRequest(requestNumber=taskNumber)
    return snowDriver.Tasks_ReadFullTask()
# Extract and return a list of Verizon order numbers found in an SCTask.
def getSCTaskOrders(scTask):
    verizonOrderPattern = r"MB\d+"
    foundOrders = []
    # Loop through the activities to find order numbers
    for activity in scTask["Activities"]:
        # Check "BaseContent" for matches
        if activity["BaseContent"]:
            foundOrders.extend(re.findall(verizonOrderPattern, activity["BaseContent"]))

        # Check "EmailContent" for matches
        if activity["EmailContent"]:
            foundOrders.extend(re.findall(verizonOrderPattern, activity["EmailContent"]))

    # Return the list of found order numbers
    return foundOrders

# Searches up, and reads, a full Cimpl workorder given by workorderNumber.
def readCimplWorkorder(cimplDriver : CimplDriver,workorderNumber):
    maintenance.validateCimpl(cimplDriver)
    cimplDriver.navToWorkorderCenter()
    workorderNumber = str(workorderNumber)

    cimplDriver.Filters_Clear()
    cimplDriver.waitForLoadingScreen()
    cimplDriver.Filters_AddWorkorderNumber(status="Equals",workorderNumber=workorderNumber)
    cimplDriver.Filters_Apply()

    cimplDriver.openWorkorder(workorderNumber=workorderNumber)

    return cimplDriver.Workorders_ReadFullWorkorder()

#endregion === Ticketing Service Management ===
#region === TMA Documentation ===

# Performs a full New Install in TMA, building a new service based on the provided information.
def documentTMANewInstall(tmaDriver : TMADriver,client,netID,serviceNum,installDate,device,imei,carrier,planFeatures):
    maintenance.validateTMA(tmaDriver, client=client)
    if device not in syscoData["Devices"].keys():
        error = ValueError(f"Specified device '{device}' is not configured in devices.toml.")
        log.error(error)
        raise error

    netID = netID.strip()
    serviceNum = convertServiceIDFormat(serviceID=serviceNum,targetFormat="dashed")

    tmaDriver.navToLocation(TMALocation(client="Sysco",entryType="People",entryID=netID.strip()))
    targetUser = TMAPeople(locationData=tmaDriver.currentLocation)
    targetUser.info_Client = "Sysco"
    tmaDriver.People_ReadBasicInfo(targetUser)

    # First, we need to build the service as a TMA.Service struct before we actually build it in TMA.
    newService = TMAService()
    newService.info_Client = "Sysco"
    newService.info_Carrier = carrier
    newService.info_UserName = f"{targetUser.info_FirstName} {targetUser.info_LastName}"
    newService.info_ServiceNumber = serviceNum.strip()
    newService.info_ServiceType = syscoData["Devices"][device]["TMA Service Type"]


    installDateObj = standardizeToDateObject(dateString=installDate,carrier=carrier)
    if carrier in ["Verizon Wireless"]:
        contractEndDateYears = 2
    else:
        contractEndDateYears = 3
    expirationDateObj = installDateObj.replace(year=installDateObj.year + contractEndDateYears)

    newService.info_InstalledDate = installDateObj.strftime("%m/%d/%Y")
    newService.info_ContractEndDate = expirationDateObj.strftime("%m/%d/%Y")
    newService.info_UpgradeEligibilityDate = expirationDateObj.strftime("%m/%d/%Y")

    thisEquipment = TMAEquipment(linkedService=newService,
                                     mainType=syscoData["Devices"][device]["TMA Main Type"],
                                     subType=syscoData["Devices"][device]["TMA Sub Type"],
                                     make=syscoData["Devices"][device]["TMA Make"],
                                     model=syscoData["Devices"][device]["TMA Model"])
    newService.info_LinkedEquipment = thisEquipment
    if imei is None:
        newService.info_LinkedEquipment.info_IMEI = ""
    else:
        newService.info_LinkedEquipment.info_IMEI = imei

    if newService.info_ServiceType == "iPhone" or newService.info_ServiceType == "Android":
        costType = "Smart Phone"
    elif newService.info_ServiceType == "Cell Phone":
        costType = "Cell Phone"
    elif newService.info_ServiceType == "Tablet":
        costType = "Tablet"
    elif newService.info_ServiceType == "Mifi":
        costType = "Aircard"
    else:
        raise ValueError(f"Invalid service type: {newService.info_ServiceType}")

    baseCost = None
    featureCosts = []
    for planFeature in planFeatures:
        newCost = TMACost(isBaseCost=planFeature["TMA IsBaseCost"], featureName=planFeature["TMA Feature Name"], gross=planFeature["TMA Gross Cost"],
                          discountFlat=planFeature["TMA Discount Flat"], discountPercentage=planFeature["TMA Discount Percent"])
        if planFeature["TMA IsBaseCost"] == "TRUE":
            if baseCost is not None:
                raise ValueError(f"Multiple base costs for a single equipment entry in equipment.toml: {costType}|{carrier}")
            else:
                baseCost = newCost
        else:
            featureCosts.append(newCost)
    newService.info_BaseCost = baseCost
    newService.info_FeatureCosts = featureCosts

    # Creates a new linked service, which also opens a new pop up window.
    tmaDriver.People_CreateNewLinkedService()
    tmaDriver.switchToNewTab()

    # Select the modal service type here.
    tmaDriver.Service_SelectModalServiceType("Cellular")

    # Now we write the main information, and the installed date in LineInfo.
    tmaDriver.Service_WriteMainInformation(newService,"Sysco")
    tmaDriver.Service_WriteInstalledDate(newService)

    # We can now insert the service.
    result = tmaDriver.Service_InsertUpdate()
    #TODO better handling for this?
    if result == "ServiceAlreadyExists":
        tmaDriver.returnToBaseTMA()
        return "ServiceAlreadyExists"

    # The screen now changes over to the Accounts wizard, but stays on the same tab.
    tmaDriver.Assignment_BuildAssignmentFromAccount("Sysco",carrier,targetUser.info_OpCo)

    # Return to base TMA now that the popup window should be closed.
    tmaDriver.returnToBaseTMA()

    # Now that we've processed the assignment, the popup window has closed and we need to
    # switch back to base TMA window. We also need to force TMA to update and display the new service
    tmaDriver.People_NavToLinkedTab("services")

    # We can now open the newly created service from our People object, replacing this window
    # with the service entry.
    tmaDriver.People_OpenServiceFromPeople(serviceNum,extraWaitTime=15)

    # Now, we can write cost objects.
    tmaDriver.Service_WriteCosts(newService,isBase=True)
    tmaDriver.Service_WriteCosts(newService,isBase=False)

    # Now we create our new linked equipment, and switch to that new popup tab.
    tmaDriver.Service_NavToServiceTab("links")
    tmaDriver.Service_NavToLinkedTab("equipment")
    tmaDriver.Service_CreateLinkedEquipment()
    tmaDriver.switchToNewTab()

    # We build our Equipment information. After clicking insert, we forcibly close
    # this tab and return to base TMA.
    tmaDriver.Equipment_SelectEquipmentType(newService.info_LinkedEquipment.info_MainType)
    writeIMEI = True if newService.info_LinkedEquipment.info_IMEI else False
    writeSIM = True if newService.info_LinkedEquipment.info_SIM else False
    tmaDriver.Equipment_WriteAll(newService.info_LinkedEquipment,writeIMEI=writeIMEI,writeSIM=writeSIM)
    tmaDriver.Equipment_InsertUpdate()
    tmaDriver.returnToBaseTMA()

    # Finally, we update the display again and update the service to make sure
    # everything has worked.
    tmaDriver.Service_NavToLinkedTab("orders")
    tmaDriver.Service_NavToLinkedTab("equipment")
    tmaDriver.Service_InsertUpdate()

    return "Completed"
# Performs a full Upgrade in TMA, editing an existing service based on the provided information.
def documentTMAUpgrade(tmaDriver : TMADriver,client,serviceNum,installDate,device,imei,carrier):
    maintenance.validateTMA(tmaDriver,client=client)
    if device not in syscoData["Devices"].keys():
        error = ValueError(f"Specified device '{device}' is not configured in devices.toml.")
        log.error(error)
        raise error

    # First, we navigate to the service that's been upgraded.
    tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="Service", entryID=serviceNum.strip()))

    # First thing to update in the upgrade elib and expiration dates.
    installDateObject = standardizeToDateObject(dateString=installDate,carrier=carrier)
    upgradeEligibilityDate = installDateObject.replace(year=installDateObject.year + 2)
    tmaDriver.Service_WriteUpgradeEligibilityDate(rawValue=upgradeEligibilityDate.strftime("%m/%d/%Y"))
    tmaDriver.Service_WriteContractEndDate(rawValue=upgradeEligibilityDate.strftime("%m/%d/%Y"))
    tmaDriver.Service_InsertUpdate()

    # Now we check to make sure that the Service Type hasn't changed.
    newServiceType = syscoData["Devices"][device]["TMA Service Type"]
    if newServiceType != tmaDriver.Service_ReadMainInfo().info_ServiceType:
        tmaDriver.Service_WriteServiceType(rawValue=newServiceType)
        tmaDriver.Service_InsertUpdate()

    # Now, we navigate to the equipment and update the IMEI and device info.
    tmaDriver.Service_NavToEquipmentFromService()

    thisEquipment = TMAEquipment(mainType=syscoData["Devices"][device]["TMA Main Type"],
                                     subType=syscoData["Devices"][device]["TMA Sub Type"],
                                     make=syscoData["Devices"][device]["TMA Make"],
                                     model=syscoData["Devices"][device]["TMA Model"])
    deviceToBuild = thisEquipment
    if imei is None:
        deviceToBuild.info_IMEI = ""
    else:
        deviceToBuild.info_IMEI = imei
    writeIMEI = True if deviceToBuild.info_IMEI else False
    writeSIM = True if deviceToBuild.info_SIM else False
    print(deviceToBuild)
    print(writeIMEI)
    tmaDriver.Equipment_WriteAll(equipmentObject=deviceToBuild,writeIMEI=writeIMEI,writeSIM=writeSIM)
    tmaDriver.Equipment_InsertUpdate()

#endregion === TMA Documentation ===

#region === Full Cimpl Workflows ===

# Given a workorderNumber, this method examines it, tries to figure out the type of workorder it is, and whether
# it is valid to submit automatically through the respective carrier.
def processPreOrderWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,verizonDriver : VerizonDriver,eyesafeDriver : EyesafeDriver,
                             workorderNumber,reviewMode=True,referenceNumber=None,subjectLine : str = None):
    # First, read the full workorder.
    print(f"Cimpl WO {workorderNumber}: Beginning automation")
    workorder = readCimplWorkorder(cimplDriver=cimplDriver,workorderNumber=workorderNumber)

    # Test to ensure the operation type is valid
    if workorder["OperationType"] not in ("New Request", "Upgrade"):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order type '{workorder['OperationType']}' is not understood by the Shaman.")
        return False
    # Test to ensure status is operable
    if workorder["Status"] == "Completed" or workorder["Status"] == "Cancelled":
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order is already {workorder['Status']}")
        return False
    # Test for correct carrier
    if workorder["Carrier"].lower() == "verizon wireless":
        carrier = "Verizon Wireless"
    else:
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as carrier is not Verizon ({workorder['Carrier']})")
        return False
    # Test to ensure it hasn't already been placed
    if workorder.getLatestOrderNote() is not None:
        warningMessage = f"Cimpl WO {workorderNumber}: An order has already been submitted for this Cimpl WO."
        if not consoleUserWarning(warningMessage):
            return False
    # Check to make sure no existing comments interfere with the request.
    if workorder["Comment"] != "":
        # Cimpl requests often have comments now that read something like "Request Number REQ10005410981". These are
        # simply API submitted orders, and we assume these don't need to be checked.
        snowRequestNumberRegex = r"^\s*Request Number REQ\d+\s*$"
        workorderRegexMatches = re.findall(snowRequestNumberRegex,workorder["Comment"].strip())
        if not workorderRegexMatches:
            warningMessage = f"Cimpl WO {workorderNumber}: WARNING - There is a comment on this workorder:\n\"{workorder['Comment']}\"\n\n"
            if not consoleUserWarning(warningMessage):
                return False
    # Check to make sure no existing notes interfere with the request.
    if len(workorder["Notes"]) > 0:
        warningMessage = f"Cimpl WO {workorderNumber}: WARNING - There are existing notes on this workorder."
        if not consoleUserWarning(warningMessage):
            return False

    # Validate and get the true plans/features, deviceID, and accessoryIDs for this orders.
    deviceID = validateDeviceID(workorder["DeviceID"],carrier=workorder["Carrier"])
    if not deviceID:
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as no device could validate from this entry: '{workorder['DeviceID']}'")
        return False
    validatedAccessories = validateAccessoryIDs(deviceID=deviceID,carrier=workorder["Carrier"],accessoryIDs=workorder["AccessoryIDs"])
    accessoryIDs = validatedAccessories["AccessoryIDs"]
    eyesafeAccessoryIDs = validatedAccessories["EyesafeAccessoryIDs"]

    #TODO THIS IS TEMPORARY
    #if deviceID == "iPhone16e_128GB":
    #    for accessoryID in accessoryIDs:
    #        if syscoData["Accessories"][accessoryID]["Accessory Type"] != "Wall Adapter" or len(eyesafeAccessoryIDs) > 0:
    #            print(f"Cimpl WO {workorderNumber}: Skipping workorder, as its for an iPhone with Accessories.")
    #            return False

    basePlan, features = getPlansAndFeatures(deviceID=deviceID,carrier=workorder["Carrier"])
    featuresToBuildOnCarrier = []
    for feature in features:
        if feature["BuildOnCarrier"] == "TRUE":
            featuresToBuildOnCarrier.append(feature)
    # Get the eyesafe accessoryID or set to None
    if eyesafeAccessoryIDs:
        eyesafeAccessoryID = eyesafeAccessoryIDs[0]
    else:
        eyesafeAccessoryID = None

    # Read the people object from TMA.
    maintenance.validateTMA(tmaDriver,"Sysco")
    tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="People", entryID=workorder["UserNetID"]))
    thisPerson = tmaDriver.People_ReadAllInformation()

    if workorder["OperationType"] == "New Request":
        if len(thisPerson.info_LinkedServices) > 0:
            warningMessage = f"WARNING: User '{workorder['UserNetID']}' already has linked services."
            if not consoleUserWarning(warningMessage):
                return False
        maintenance.validateTMA(tmaDriver,"Sysco")
    elif workorder["OperationType"] == "Upgrade":
        # TODO We just navigate here to raise errors in case the line is inactive. Maybe come up with better system?
        maintenance.validateTMA(tmaDriver,"Sysco")
        tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="Service", entryID=workorder["ServiceID"]))

    # Write name on order
    print(f"Cimpl WO {workorderNumber}: Determined as valid WO for Shaman rituals")
    if referenceNumber is not None:
        maintenance.validateCimpl(cimplDriver)
        cimplDriver.Workorders_NavToSummaryTab()
        cimplDriver.Workorders_WriteReferenceNo(referenceNo=referenceNumber)
        cimplDriver.Workorders_ApplyChanges()

    # Validate the shipping address
    print(workorder["UserShipping"])
    validatedAddress = validateAddress(rawAddressString=workorder["UserShipping"])
    print(f"Cimpl WO {workorderNumber}: Validated address as: {validatedAddress}")

    # If operation type is a New Install
    if workorder["OperationType"] == "New Request":
        print(f"Cimpl WO {workorderNumber}: Ordering new device ({deviceID}) and service for user {workorder['UserNetID']}")
        results = placeVerizonNewInstall(verizonDriver=verizonDriver,deviceID=deviceID,accessoryIDs=accessoryIDs,companyName="Sysco",plan=basePlan,features=featuresToBuildOnCarrier,
                                            firstName=workorder["UserFirstName"],lastName=workorder["UserLastName"],userEmail=thisPerson.info_Email,
                                            address1=validatedAddress["Address1"],address2=validatedAddress.get("Address2",None),city=validatedAddress["City"],
                                            state=validatedAddress["State"],zipCode=validatedAddress["ZipCode"],reviewMode=reviewMode,contactEmails=thisPerson.info_Email)
        print(f"Cimpl WO {workorderNumber}: Finished ordering new device and service for user {workorder['UserNetID']}")
        orderNumber = results.data
    # If op type is Upgrade
    elif workorder["OperationType"] == "Upgrade":
        print(f"Cimpl WO {workorderNumber}: Ordering upgrade ({workorder['DeviceID']}) and service for user {workorder['UserNetID']} with service {workorder['ServiceID']}")
        results = placeVerizonUpgrade(verizonDriver=verizonDriver,deviceID=deviceID,serviceID=workorder['ServiceID'],accessoryIDs=accessoryIDs,
                                          firstName=workorder["UserFirstName"],lastName=workorder["UserLastName"],companyName="Sysco",
                                          address1=validatedAddress["Address1"],address2=validatedAddress.get("Address2", None),city=validatedAddress["City"],
                                          state=validatedAddress["State"], zipCode=validatedAddress["ZipCode"],reviewMode=reviewMode,contactEmails=thisPerson.info_Email)
        orderNumber = results.data
        if orderNumber == "NotETFEligible":
            playsoundAsync(paths["media"] / "shaman_attention.mp3")
            input(f"Cimpl WO {workorderNumber}: Not yet eligible for ETF upgrade. Open SNow ticket and cancel request. Press any key to continue to next request.")
            return False
        elif orderNumber == "MTNPending":
            playsoundAsync(paths["media"] / "shaman_attention.mp3")
            input(f"Cimpl WO {workorderNumber}: Line is stuck on 'MTNPending' error. Please submit an SM ticket with Verizon to resolve. Press any ket to continue to next request.")
            return False
        else:
            print(f"Cimpl WO {workorderNumber}: Finished ordering upgrade for user {workorder['UserNetID']} on line {workorder['ServiceID']}")
    # Otherwise, error out.
    else:
        error = ValueError(f"Incorrect operation type for preprocess of workorder: '{workorder['OperationType']}'")
        log.error(error)
        raise error

    maintenance.validateCimpl(cimplDriver)
    if orderNumber is False:
        return False
    elif orderNumber == "MTNPending":
        print(f"Cimpl WO {workorderNumber}: Couldn't upgrade line {workorder['ServiceID']} due to 'MTN Pending' error on Verizon.")
        return False
    elif orderNumber == "NotETFEligible":
        print(f"Cimpl WO {workorderNumber}: Couldn't upgrade line {workorder['ServiceID']} because it is too early to upgrade with ETF waiver.")
        return False

    cimplDriver.Workorders_NavToSummaryTab()
    cimplDriver.Workorders_WriteNote(subject="Order Placed",noteType="Information Only",status="Completed",content=orderNumber)

    # Confirm workorder, if not already confirmed.
    if workorder["Status"] == "Pending":
        templateFileName = None
        if workorder["OperationType"].lower() == "new request":
            templateFileName = syscoData["Devices"][deviceID][f"{carrier} New Install Email Template"].strip()
        elif workorder["OperationType"].lower() == "upgrade":
            templateFileName = syscoData["Devices"][deviceID][f"{carrier} Upgrade Email Template"].strip()


        if templateFileName:
            templatePath = paths["emailTemplates"] / templateFileName
            with open(templatePath, "r") as file:
                emailContent = file.read()

            cimplDriver.Workorders_SetStatus(status="Confirm",emailRecipients=thisPerson.info_Email,emailCCs="BTNetworkServicesMobility@sysco.com",emailContent=emailContent)
            print(f"Cimpl WO {workorderNumber}: Added order number to workorder notes and confirmed request.")
        else:
            cimplDriver.Workorders_SetStatus(status="Confirm")
            print(f"Cimpl WO {workorderNumber}: Added order number to workorder notes and confirmed request.")

    if subjectLine is not None:
        cimplDriver.Workorders_NavToSummaryTab()
        subjectLine = subjectLine.replace("%D",datetime.now().strftime('%m/%d/%Y'))
        cimplDriver.Workorders_WriteSubject(subject=subjectLine)
        cimplDriver.Workorders_ApplyChanges()

    # Handle ordering Eyesafe, if specified
    if eyesafeAccessoryID:
        #with open(paths["root"] / "eyesafe_wos_to_place.txt", "a") as f:
        #    f.write(f"\n{workorderNumber}")
        #    print(f"ALERT!! ALERT!! EYESAFE ORDER WO: {workorderNumber}")
        if workorder["OperationType"] == "New Request":
            eyesafePhoneNumberFieldEntry = workorder['UserNetID']
        elif workorder["OperationType"] == "Upgrade":
            eyesafePhoneNumberFieldEntry = workorder['ServiceID']
        else:
            error = ValueError(f"Tried to place eyesafe order on a non New Install/Upgrade!")
            log.error(error)
            raise error
        eyesafeOrderNumber = placeEyesafeOrder(eyesafeDriver=eyesafeDriver,eyesafeAccessoryID=eyesafeAccessoryID,
                                userFirstName=thisPerson.info_FirstName,userLastName=thisPerson.info_LastName,
                                address1=validatedAddress["Address1"],address2=validatedAddress["Address2"],
                                city=validatedAddress["City"],state=validatedAddress["State"],zipCode=validatedAddress["ZipCode"],
                                               phoneNumber=eyesafePhoneNumberFieldEntry)
        maintenance.validateCimpl(cimplDriver)
        cimplDriver.Workorders_NavToSummaryTab()
        cimplDriver.Workorders_WriteNote(subject="Eyesafe Order Placed", noteType="Information Only", status="Completed",content=eyesafeOrderNumber)
        log.info(f"Ordered Eyesafe device '{eyesafeAccessoryID}' per '{eyesafeOrderNumber}'")

    return True

# Given a workorderNumber, this method examines it, tries to figure out the type of workorder it is and whether
# it has a relevant order number, looks up to see if order is completed, and then closes it in TMA.
def processPostOrderWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,vzwDriver : VerizonDriver,bakaDriver : BakaDriver,uplandOutlookDriver : OutlookDriver, sysOrdBoxOutlookDriver : OutlookDriver,
                              workorderNumber,orderViewPeriod="180 Days"):
    # Read full workorder.
    print(f"Cimpl WO {workorderNumber}: Beginning automation")
    workorder = readCimplWorkorder(cimplDriver=cimplDriver,workorderNumber=workorderNumber)

    # Test to ensure the operation type is valid
    if workorder["OperationType"] not in ("New Request", "Upgrade"):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order type '{workorder['OperationType']}' is not understood by the Shaman.")
        return False

    # Test to ensure status is operable
    if workorder["Status"] == "Completed" or workorder["Status"] == "Cancelled":
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order is already {workorder['Status']}")
        return False

    # Test for correct carrier
    carrier = validateCarrier(workorder["Carrier"])
    if not carrier:
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as carrier is not Verizon, Bell, or Rogers: ({workorder['Carrier']})")
        return False

    # Test to ensure it can properly locate the order number
    carrierOrderNote = workorder.getLatestOrderNote()
    if carrierOrderNote is None:
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as no completed carrier order can be found.")
        return False
    else:
        carrierOrderNumber = carrierOrderNote["ClassifiedValue"]

    # Read Verizon Order
    if carrier == "Verizon Wireless":
        carrierOrder = readVerizonOrder(verizonDriver=vzwDriver,verizonOrderNumber=carrierOrderNumber,orderViewPeriod=orderViewPeriod)
        if carrierOrder is None:
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order number '{carrierOrderNumber}' is not yet showing in the Verizon Order Viewer.")
            return False
        elif carrierOrder["Status"] != "Completed":
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order number '{carrierOrderNumber}' has status '{carrierOrder['Status']}' and not Complete.")
            return False
    # Read Bell Order
    elif carrier == "Bell Mobility":
        carrierOrder = readBakaOrder(bakaDriver=bakaDriver,bakaOrderNumber=carrierOrderNumber)
        if carrierOrder["Status"] != "Complete":
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order number '{carrierOrderNumber}' has status '{carrierOrder['Status']}' and not Complete.")
            return False
    # Read Rogers Order
    elif carrier == "Rogers":
        carrierOrder = readRogersOrder(uplandOutlookDriver=uplandOutlookDriver,sysOrdBoxOutlookDriver=sysOrdBoxOutlookDriver,
                        rogersOrderNumber=carrierOrderNumber)
        if not carrierOrder:
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as no completed order info email for order number '{carrierOrderNumber}' has been received by the SysOrdBox.")
            return False
    else:
        raise ValueError("This should never happen. This means a non-supported carrier was validated by function - fix code immediately.")

    # Get device model ID from Cimpl
    print(f"Cimpl WO {workorderNumber}: Determined as valid WO for Shaman rituals")
    if not workorder["DeviceID"]:
        # Quickly generate a list of devices currently specified in device_cimpl_mappings to prompt the user with.
        commonMappedDevices = set()
        for thisDeviceID in syscoData["Devices"].keys():
            commonMappedDevices.add(thisDeviceID)
        commonMappedDevices = list(commonMappedDevices)
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        promptString = f"Cimpl WO {workorderNumber}: No device is specified in the 'Hardware Info' section of Cimpl. Please manually select the ordered device, or enter anything else to skip order.\n\n"
        for counter, thisDeviceID in enumerate(commonMappedDevices):
            promptString += f"{counter}. {thisDeviceID}\n"
        userInput = input(promptString).strip()
        if isNumber(userInput) and (0 <= int(userInput) < len(commonMappedDevices)):
            deviceID = commonMappedDevices[int(userInput)]
        else:
            return False
    else:
        deviceID = validateDeviceID(deviceID=workorder["DeviceID"],carrier=carrier)
    # Get target plans/features to build as costs
    basePlan,features = getPlansAndFeatures(deviceID=deviceID,carrier=carrier)
    features.append(basePlan)
    featuresToBuildOnTMA = []
    for feature in features:
        if feature["WriteToTMA"] == "TRUE":
            featuresToBuildOnTMA.append(feature)

    # If operation type is a New Install
    if workorder["OperationType"] == "New Request":
        print(f"Cimpl WO {workorderNumber}: Building new service {carrierOrder['WirelessNumber']} for user {workorder['UserNetID']}")
        returnCode = documentTMANewInstall(tmaDriver=tmaDriver,client="Sysco",netID=workorder['UserNetID'],serviceNum=carrierOrder["WirelessNumber"],installDate=carrierOrder["OrderDate"],device=deviceID,imei=carrierOrder["IMEI"],carrier=carrier,planFeatures=featuresToBuildOnTMA)
        if returnCode == "Completed":
            writeServiceToCimplWorkorder(cimplDriver=cimplDriver,serviceNum=carrierOrder["WirelessNumber"],carrier=carrier,installDate=carrierOrder["OrderDate"])
            print(f"Cimpl WO {workorderNumber}: Finished building new service {carrierOrder['WirelessNumber']} for user {workorder['UserNetID']}")
        elif returnCode == "ServiceAlreadyExists":
            print(f"Cimpl WO {workorderNumber}: Can't build new service for {carrierOrder['WirelessNumber']}, as the service already exists in the TMA database")
            return False
        elif returnCode == "WrongDevice":
            print(f"Cimpl WO {workorderNumber}: Failed to build new service in TMA, got wrong device '{deviceID}'")
            return False
    # If operation type is an Upgrade
    elif workorder["OperationType"] == "Upgrade":
        print(f"Cimpl WO {workorderNumber}: Processing Upgrade for service {carrierOrder['WirelessNumber']}")
        returnCode = documentTMAUpgrade(tmaDriver=tmaDriver,client="Sysco",serviceNum=workorder["ServiceID"],installDate=carrierOrder["OrderDate"],device=deviceID,imei=carrierOrder["IMEI"],carrier=carrier)
        if returnCode == "Completed":
            print(f"Cimpl WO {workorderNumber}: Finished upgrading TMA service {carrierOrder['WirelessNumber']}")
        elif returnCode == "WrongDevice":
            print(f"Cimpl WO {workorderNumber}: Failed to upgrade service in TMA, got wrong device '{deviceID}'")
            return False

    # Write tracking information
    maintenance.validateCimpl(cimplDriver)
    cimplDriver.Workorders_NavToSummaryTab()
    if carrierOrder.get("TrackingNumber", None) is not None and carrierOrder["TrackingNumber"].strip() != "":
        cimplDriver.Workorders_WriteNote(subject="Tracking",noteType="Information Only",status="Completed",content=f"Courier: {carrierOrder['Courier']}\nTracking Number: {carrierOrder['TrackingNumber']}")

    # Complete workorder
    cimplDriver.Workorders_SetStatus(status="Complete")
    print(f"Cimpl WO {workorderNumber}: Finished all Cimpl work")
    return True

#endregion === Full Cimpl Workflows ===
#region === Full SNow Workflows ===

# This method takes and orders for one single new hire SCTASK.
def processPreOrderSCTASK(tmaDriver : TMADriver,snowDriver : SnowDriver,verizonDriver : VerizonDriver,
                          taskNumber, assignTo,reviewMode=True):
    print(f"{taskNumber}: Beginning automation")

    # First, read the full SNow task.
    scTask = readSnowTask(snowDriver=snowDriver,taskNumber=taskNumber)

    # Make sure the note isn't assigned to somebody else, then assign it to assignTo
    if scTask["AssignedTo"] is not None and scTask["AssignedTo"] != "" and scTask["AssignedTo"].lower() != assignTo.lower():
        warningMessage = f"WARNING: This SCTASK is already assigned to '{scTask['AssignedTo']}'"
        if not consoleUserWarning(warningMessage):
            return False
    snowDriver.Tasks_WriteAssignedTo(assignedTo=assignTo)

    foundVerizonOrders = getSCTaskOrders(scTask=scTask)
    if foundVerizonOrders:
        warningMessage = f"WARNING: There are existing Verizon orders on the SCTASK."
        if not consoleUserWarning(warningMessage):
            return False

    # Add the Upland/Cimpl tag to the SCTASK.
    snowDriver.Tasks_AddTag("Upland/Cimpl")

    # Set the order to WIP
    snowDriver.Tasks_WriteState("Work in Progress")

    # Update, then reopen to avoid doing duplicate orders with other people in the queue.
    snowDriver.Tasks_Update()
    snowDriver.navToRequest(requestNumber=taskNumber)

    # Classify the device intended to be ordered.
    #TODO GET THIS SHIT UP TO DATE STUPID BITCH
    if scTask["OrderDevice"].lower() == "apple":
        deviceID = DEFAULT_SNOW_IPHONE
    elif scTask["OrderDevice"].lower() == "android":
        deviceID = DEFAULT_SNOW_ANDROID
    else:
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        print(f"{taskNumber}: Unknown device specified in ticket: '{scTask['OrderDevice']}'")
        return False

    # Classify accessoryIDs depending on if accessories were requested.
    if scTask["OrderAccessoryBundle"]:
        accessoryIDs = [DEFAULT_SNOW_CHARGER]
        if scTask["OrderDevice"].lower() == "apple":
            accessoryIDs.append(DEFAULT_SNOW_IPHONE_CASE)
        else:
            accessoryIDs.append(DEFAULT_SNOW_ANDROID_CASE)
    else:
        accessoryIDs = []

    # Validate and get the true plans/features, deviceID, and accessoryIDs for this order.
    deviceID = validateDeviceID(deviceID=deviceID,carrier="Verizon Wireless")
    accessoryIDs = validateAccessoryIDs(deviceID=deviceID,carrier="Verizon Wireless",accessoryIDs=accessoryIDs)["AccessoryIDs"]
    basePlan, features = getPlansAndFeatures(deviceID=deviceID,carrier="Verizon Wireless")
    featuresToBuildOnCarrier = []
    for feature in features:
        if feature["BuildOnCarrier"] == "TRUE":
            featuresToBuildOnCarrier.append(feature)

    # Try to determine the employee's info given the order's username and supervisor name.
    maintenance.validateTMA(tmaDriver=tmaDriver,client="Sysco")
    searchedPeopleObject = tmaDriver.searchPeopleFromNameAndSup(userName=scTask["OrderEmployeeName"],supervisorName=scTask["OrderSupervisorName"])
    if searchedPeopleObject:
        userFirstName = searchedPeopleObject.info_FirstName
        userLastName = searchedPeopleObject.info_LastName
        contactEmail = searchedPeopleObject.info_Email

        # Check to make sure the user doesn't already have a service.
        if len(searchedPeopleObject.info_LinkedServices) > 0:
            warningMessage = f"WARNING: User '{searchedPeopleObject.info_EmployeeID}' already has linked services."
            if not consoleUserWarning(warningMessage):
                return False
    else:
        userFirstName,userLastName = scTask["OrderEmployeeName"].split(" ",maxsplit=1)
        contactEmail = None

    # Validate and clean the address that the user gave.
    validatedAddress = validateAddress(rawAddressString=scTask["OrderShippingAddress"])
    print(f"{taskNumber}: Found validated address: {validatedAddress}")

    print(f"{taskNumber}: Determined as valid SCTASK for Shaman rituals.")

    # Process the new install.
    print(f"{taskNumber}: Ordering new device ({deviceID}) and service for user {userFirstName} {userLastName}")
    orderResult = placeVerizonNewInstall(verizonDriver=verizonDriver,deviceID=deviceID,accessoryIDs=accessoryIDs,companyName="Sysco",plan=basePlan,features=featuresToBuildOnCarrier,
                                        firstName=userFirstName,lastName=userLastName,userEmail=contactEmail if contactEmail is not None else "sysco_wireless_mac@cimpl.com",
                                        address1=validatedAddress["Address1"],address2=validatedAddress.get("Address2",None),city=validatedAddress["City"],
                                        state=validatedAddress["State"],zipCode=validatedAddress["ZipCode"],reviewMode=reviewMode,contactEmails=contactEmail)
    fullOrderNumber = orderResult.data
    verizonOrderNumber = re.search(r"(MB\d+)",fullOrderNumber).group(1).strip()
    print(f"{taskNumber}: Finished ordering new device and service for user {userFirstName} {userLastName} ({verizonOrderNumber})")

    # Add workorder to SCTASK notes.
    maintenance.validateSnow(snowDriver)
    snowDriver.Tasks_WriteNote(noteContent=fullOrderNumber)
    snowDriver.Tasks_Update()

    # Document the order.
    storeResult = documentation.storeSCTASKToGoogle(taskNumber=taskNumber,orderNumber=verizonOrderNumber,userName=f"{userFirstName} {userLastName}",deviceID=deviceID,datePlaced=datetime.today().strftime("%H:%M:%S %d-%m-%Y"))
    if not storeResult:
        warningMessage = f"WARNING: Tried to store result of order 5 times, but google failed five times. Manually document?"
        if not consoleUserWarning(warningMessage):
            return False

# This method attempts to close an SCTASK (simply updating the ticket with tracking, and close) based
# on the given SCTASK number.
def processPostOrdersSCTASK(snowDriver : SnowDriver,verizonDriver : VerizonDriver,taskNumber : (str,list) = None,useDriveSCTasks=True):
    if taskNumber:
        if type(taskNumber) is not list:
            taskNumber = [taskNumber]

    if useDriveSCTasks:
        # First, get the full list of pending SCTASKs to close.
        scTasks = documentation.downloadSCTASKs()
    else:
        scTasks = taskNumber

    # Validate Verizon
    maintenance.validateVerizon(verizonDriver)
    verizonDriver.navToOrderViewer()

    # Now, iterate through each one and close.
    for scTask in scTasks:
        thisTaskNumber = scTask["ServiceNow Ticket"] if useDriveSCTasks else scTask

        # Filter for specific tasks, if necessary.
        if useDriveSCTasks and taskNumber:
            if thisTaskNumber not in taskNumber:
                continue

        print(f"{thisTaskNumber}: Beginning request close.")

        # Nav to the SNow request.
        maintenance.validateSnow(snowDriver)
        snowDriver.navToRequest(thisTaskNumber)
        thisSnowRequest = snowDriver.Tasks_ReadFullTask()

        # If using the sheets doc, simply pull stored order. Otherwise, read from the literal task.
        if useDriveSCTasks:
            orderNumber = scTask["Order"]
        else:
            allVerizonOrders = getSCTaskOrders(scTask=thisSnowRequest)
            if allVerizonOrders:
                # Use latest order number by default #TODO glue?
                orderNumber = allVerizonOrders[-1]
            else:
                print(f"Skipping {thisTaskNumber}, as no Verizon order was found.")
                log.warning(f"Skipping {thisTaskNumber}, as no Verizon order was found.")
                continue

        # First, try to pull up the order in Verizon.
        maintenance.validateVerizon(verizonDriver)
        carrierOrder = readVerizonOrder(verizonDriver=verizonDriver, verizonOrderNumber=orderNumber,orderViewPeriod="180 Days")
        if carrierOrder is None:
            print(f"{thisTaskNumber}: Can't close request, as order number '{orderNumber}' is not yet showing in the Verizon Order Viewer.")
            continue
        elif carrierOrder["Status"] != "Completed":
            print(f"{thisTaskNumber}: Can't complete WO, as order number '{orderNumber}' has status '{carrierOrder['Status']}' and not Complete.")
            continue

        # Check to make sure the request is still open.
        if thisSnowRequest["State"] in ["Closed Complete", "Closed Incomplete", "Closed Skipped"]:
            print(f"{thisTaskNumber}: Task is already in state '{thisSnowRequest['State']}'")
        else:
            trackingNote = f"Service Number: {carrierOrder['WirelessNumber']}\n"
            # Get tracking number if provided, and write to the SNow ticket.
            if carrierOrder["TrackingNumber"] is not None and carrierOrder["TrackingNumber"].strip() != "":
                trackingNote += f"Courier: {carrierOrder['Courier']}\nTracking Number: {carrierOrder['TrackingNumber']}"

            # Close the order.
            snowDriver.Tasks_WriteState("Closed Complete")
            snowDriver.Tasks_WriteAdditionalNote(noteContent=trackingNote)
            snowDriver.Tasks_Update()

        # Archive the task in the Google sheet.
        if useDriveSCTasks:
            documentation.archiveSCTASKOnGoogle(taskNumber=thisTaskNumber, closedBy="Alex", serviceNumber="", fullSCTASKSheet=scTasks)

        print(f"{thisTaskNumber}: Closed request.")


#endregion === Full SNow Workflows

if True:
    try:
        # Drivers init
        br = Browser()
        tma = TMADriver(br)
        cimpl = CimplDriver(br)
        snow = SnowDriver(br)
        vzw = VerizonDriver(br)
        baka = BakaDriver(br)
        eyesafe = EyesafeDriver(br)
        uplandOutlook = OutlookDriver(br)
        sysOrdBoxOutlook = OutlookDriver(br)

        #maintenance.validateCimpl(cimplDriver=cimpl)
        #time.sleep(3)
        #playsoundAsync(paths['media'] / "shaman_attention.mp3")
        #input("Please turn off Zscaler before continuing, friend.")

        # Manually log in to Verizon first, just to make life easier atm
        maintenance.validateVerizon(verizonDriver=vzw)

        # SCTASK processing
        preProcessSCTASKs = ["SCTASK1181771",
                             "SCTASK1181769",
                             "SCTASK1181765",
                             "SCTASK1181756",
                             "SCTASK1181745",
                             "SCTASK1181742",
                             "SCTASK1181733",
                             "SCTASK1181725",
                             "SCTASK1181721",
                             "SCTASK1181715",
                             "SCTASK1181714",
                             "SCTASK1181713"]
        postProcessSCTASKs = [] # Note that, if no postProcessSCTASKs are specified, all valid SCTASKs in the sheet will be closed. Input just "None" to NOT do this.
        for task in preProcessSCTASKs:
            processPreOrderSCTASK(tmaDriver=tma,snowDriver=snow,verizonDriver=vzw,
                                  taskNumber=task,assignTo=mainConfig["snow"]["assignTo"],reviewMode=True)
        #processPostOrdersSCTASK(snowDriver=snow,verizonDriver=vzw,taskNumber=postProcessSCTASKs,useDriveSCTasks=False)






        # Cimpl processing
        preProcessWOs = []


        postProcessWOs = []
        for wo in postProcessWOs:
            processPostOrderWorkorder(tmaDriver=tma,cimplDriver=cimpl,vzwDriver=vzw,bakaDriver=baka,uplandOutlookDriver=uplandOutlook,sysOrdBoxOutlookDriver=sysOrdBoxOutlook,
                                  workorderNumber=wo)
        for wo in preProcessWOs:
            processPreOrderWorkorder(tmaDriver=tma,cimplDriver=cimpl,verizonDriver=vzw,eyesafeDriver=eyesafe,
                                  workorderNumber=wo,referenceNumber=mainConfig["cimpl"]["referenceNumber"],subjectLine=mainConfig["cimpl"]["subjectLine"],reviewMode=False)

    except Exception as e:
        playsoundAsync(paths["media"] / "shaman_error.mp3")
        raise e




# TEMPLATES
#
# ORDERING A NEW PHONE:
# _firstName, _lastName, _userEmail = "", "", ""
# _address1, _address2, _city, _state, _zipCode = "", "", "", "", ""
# _deviceID, _accessoryIDs = "iPhone14_128GB", ["BelkinWallAdapter","iPhone14_Defender"]
# _contactEmails = []
# placeVerizonNewInstall(verizonDriver=vzw,deviceID=_deviceID,accessoryIDs=_accessoryIDs,
#                        plan=getPlansAndFeatures(deviceID=_deviceID,carrier="Verizon Wireless")[0],features=getPlansAndFeatures(deviceID=_deviceID,carrier="Verizon Wireless")[1],
#                        firstName=_firstName,lastName=_lastName,userEmail=_userEmail,address1=_address1,address2=_address2,city=_city,state=_state,zipCode=_zipCode,companyName="Sysco",contactEmails=_contactEmails)
#
# ORDERING AN UPGRADE
# _serviceID = ""
# _firstName, _lastName, _userEmail = "", "", ""
# _address1, _address2, _city, _state, _zipCode = "", "", "", "", ""
# _deviceID, _accessoryIDs = "iPhone14_128GB", ["BelkinWallAdapter","iPhone14_Defender"]
# _contactEmails = []
# placeVerizonUpgrade(verizonDriver=vzw,serviceID=_serviceID,deviceID=_deviceID,accessoryIDs=_accessoryIDs,
#                        firstName=_firstName,lastName=_lastName,address1=_address1,address2=_address2,city=_city,state=_state,zipCode=_zipCode,companyName="Sysco",contactEmails=_contactEmails)
#
# DOCUMENTING A PHONE IN TMA:
# documentTMANewInstall(tmaDriver=tma,client="Sysco",netID="",serviceNum="",installDate="",device="iPhone14_128GB",imei="",carrier="Verizon Wireless",
#                       planFeatures=[getPlansAndFeatures(deviceID="iPhone14_128GB",carrier="Verizon Wireless")[0]])
# documentTMAUpgrade(tmaDriver=tma,client="Sysco",serviceNum="",installDate="",device="iPhone14_128GB",imei="")



