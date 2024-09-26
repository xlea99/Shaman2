from datetime import datetime
from selenium.webdriver.common.by import By
from shaman2.selenium.browser import Browser
from shaman2.selenium.baka_driver import BakaDriver
from shaman2.selenium.cimpl_driver import CimplDriver, classifyHardwareInfo,getNetworkIDFromActions,findPlacedCimplOrderNumber
from shaman2.selenium.tma_driver import TMADriver, TMALocation, TMAPeople, TMAService, TMAOrder, TMAEquipment, TMACost, TMAAssignment
from shaman2.selenium.verizon_driver import VerizonDriver
from shaman2.operation import maintenance
from shaman2.common.config import mainConfig,clients,devices,accessories
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.utilities.shaman_utils import convertServiceIDFormat,convertStateFormat
from shaman2.utilities.async_sound import playsoundAsync

#region === Carrier Order Reading ===

# Searches up, and reads, a full workorder given by workorderNumber.
def readCimplWorkorder(cimplDriver : CimplDriver,workorderNumber):
    maintenance.validateCimpl(cimplDriver)
    cimplDriver.navToWorkorderCenter()

    cimplDriver.Filters_Clear()
    cimplDriver.Filters_AddWorkorderNumber(status="Equals",workorderNumber=workorderNumber)
    cimplDriver.Filters_Apply()

    cimplDriver.openWorkorder(workorderNumber=workorderNumber)

    return cimplDriver.Workorders_ReadFullWorkorder()

# Searches up, and reads, a full Verizon order number.
def readVerizonOrder(verizonDriver : VerizonDriver,verizonOrderNumber):
    maintenance.validateVerizon(verizonDriver)
    verizonDriver.navToOrderViewer()

    verizonDriver.OrderViewer_SearchOrder(orderNumber=verizonOrderNumber)

    return verizonDriver.OrderViewer_ReadDisplayedOrder()

# Searches up, and reads, a full Baka order number.
def readBakaOrder(bakaDriver : BakaDriver,bakaOrderNumber):
    maintenance.validateBaka(bakaDriver)

    bakaDriver.navToOrderHistory()
    bakaDriver.openOrder(bakaOrderNumber)
    return bakaDriver.readOrder()

#endregion === Carrier Order Reading ===

#region === Carrier Order Placing ===

# Places an entire Verizon new install.
def placeVerizonNewInstall(verizonDriver : VerizonDriver,deviceID : str,accessoryIDs : list,
                           firstName,lastName,userEmail,
                           address1,city,state,zipCode,contactEmails : str | list,
                           address2="",reviewMode = True,emptyCart=True,deviceColor=None):
    maintenance.validateVerizon(verizonDriver)

    if(emptyCart):
        verizonDriver.emptyCart()

    # Search for the device, click on it, select contract, and add to cart.
    verizonDriver.shopNewDevice()
    verizonDriver.DeviceSelection_SearchForDevice(deviceID=deviceID,orderPath="NewInstall")
    verizonDriver.DeviceSelection_SelectDevice(deviceID=deviceID,orderPath="NewInstall")
    verizonDriver.DeviceSelection_DeviceView_SelectColor(deviceID=deviceID,colorName=deviceColor,orderPath="NewInstall")
    verizonDriver.DeviceSelection_DeviceView_Select2YearContract(orderPath="NewInstall")
    verizonDriver.DeviceSelection_DeviceView_AddToCartAndContinue(orderPath="NewInstall")
    # This should send us to the Accessories shopping screen.



# Places an entire Verizon new install.
def placeVerizonUpgrade(verizonDriver : VerizonDriver,serviceID,deviceID : str,accessoryIDs : list,
                           firstName,lastName,
                           address1,city,state,zipCode,contactEmails : str | list,
                        address2="",reviewMode = True,emptyCart=True,deviceColor=None):
    maintenance.validateVerizon(verizonDriver)

    if(emptyCart):
        verizonDriver.emptyCart()

    # Pull up the line and click "upgrade"
    verizonDriver.pullUpLine(serviceID=serviceID)
    verizonDriver.LineViewer_UpgradeLine()
    # This should send us to the device selection page.

    # Search for the device, click on it, select contract, and add to cart.
    verizonDriver.DeviceSelection_SearchForDevice(deviceID=deviceID,orderPath="Upgrade")
    verizonDriver.DeviceSelection_SelectDevice(deviceID=deviceID,orderPath="Upgrade")
    verizonDriver.DeviceSelection_DeviceView_SelectColor(deviceID=deviceID, colorName=deviceColor,orderPath="Upgrade")
    verizonDriver.DeviceSelection_DeviceView_Select2YearContract(orderPath="Upgrade")
    verizonDriver.DeviceSelection_DeviceView_DeclineDeviceProtection()
    verizonDriver.DeviceSelection_DeviceView_AddToCartAndContinue(orderPath="Upgrade")
    # This should send us straight to the shopping cart.

    # We immediately go back to add accessories from the shopping cart.
    verizonDriver.ShoppingCart_AddAccessories()
    # This should send us to the Accessories shopping screen.


# Adds service information to Cimpl (service num, install date, account) and applies it.
def writeServiceToCimplWorkorder(cimplDriver : CimplDriver,serviceNum,carrier,installDate):
    maintenance.validateCimpl(cimplDriver)

    currentLocation = cimplDriver.getLocation()
    if(not currentLocation["Location"].startswith("Workorder_")):
        error = ValueError("Couldn't run writeServiceToCimplWorkorder, as Cimpl Driver is not currently on a workorder!")
        log.error(error)
        raise error

    cimplDriver.Workorders_NavToDetailsTab()
    cimplDriver.Workorders_WriteServiceID(serviceID=convertServiceIDFormat(serviceNum,targetFormat="raw"))
    cimplDriver.Workorders_WriteAccount(accountNum=clients['Sysco']['Accounts'][carrier])
    cimplDriver.Workorders_WriteStartDate(startDate=installDate)

    cimplDriver.Workorders_ApplyChanges()

#endregion === Carrier Order Placing ===

#region === TMA Documentation ===

# Performs a full New Install in TMA, building a new service based on the provided information.
def documentTMANewInstall(tmaDriver : TMADriver,client,netID,serviceNum,installDate,device,imei,carrier):
    maintenance.validateTMA(tmaDriver, client=client)
    if(device not in devices.keys()):
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
    newService.info_ServiceType = devices[device]["tmaServiceType"]

    newService.info_InstalledDate = installDate
    expDateObj = datetime.strptime(installDate,"%m/%d/%Y")
    expDateObj = expDateObj.replace(year=expDateObj.year + 2)
    newService.info_ContractEndDate = expDateObj.strftime("%m/%d/%Y")
    newService.info_UpgradeEligibilityDate = expDateObj.strftime("%m/%d/%Y")

    # TODO support for multiple clients other than sysco
    thisEquipment = TMAEquipment(linkedService=newService,
                                     mainType=devices[device]["tmaMainType"],
                                     subType=devices[device]["tmaSubType"],
                                     make=devices[device]["tmaMake"],
                                     model=devices[device]["tmaModel"])
    newService.info_LinkedEquipment = thisEquipment
    if(imei is None):
        newService.info_LinkedEquipment.info_IMEI = ""
    else:
        newService.info_LinkedEquipment.info_IMEI = imei

    if(newService.info_ServiceType == "iPhone" or newService.info_ServiceType == "Android"):
        costType = "Smart Phone"
    elif(newService.info_ServiceType == "Cell Phone"):
        costType = "CellPhone"
    elif(newService.info_ServiceType == "Tablet"):
        costType = "Tablet"
    elif(newService.info_ServiceType == "Mifi"):
        costType = "Mifi"
    else:
        raise ValueError(f"Invalid service type: {newService.info_ServiceType}")
    allCosts = clients["Sysco"]["Plans"][costType][carrier]

    baseCost = None
    featureCosts = []
    for cost in allCosts:
        newCost = TMACost(isBaseCost=cost["isBaseCost"], featureName=cost["featureName"], gross=cost["gross"],
                          discountFlat=cost["discountFlat"], discountPercentage=cost["discountPercentage"])
        if(cost["isBaseCost"] is True):
            if(baseCost is not None):
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
    if(result == "ServiceAlreadyExists"):
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
def documentTMAUpgrade(tmaDriver : TMADriver,client,serviceNum,installDate,device,imei):
    maintenance.validateTMA(tmaDriver,client=client)
    if(device not in devices.keys()):
        error = ValueError(f"Specified device '{device}' is not configured in devices.toml.")
        log.error(error)
        raise error

    # First, we navigate to the service that's been upgraded.
    tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="Service", entryID=serviceNum.strip()))

    # First thing to update in the upgrade elib and expiration dates.
    upgradeEligibilityDate = datetime.strptime(installDate,"%m/%d/%Y")
    upgradeEligibilityDate = upgradeEligibilityDate.replace(year=upgradeEligibilityDate.year + 2)
    tmaDriver.Service_WriteUpgradeEligibilityDate(rawValue=upgradeEligibilityDate.strftime("%m/%d/%Y"))
    tmaDriver.Service_WriteContractEndDate(rawValue=upgradeEligibilityDate.strftime("%m/%d/%Y"))
    tmaDriver.Service_InsertUpdate()

    # Now we check to make sure that the Service Type hasn't changed.
    newServiceType = devices[device]["tmaServiceType"]
    if(newServiceType != tmaDriver.Service_ReadMainInfo().info_ServiceType):
        tmaDriver.Service_WriteServiceType(rawValue=newServiceType)
        tmaDriver.Service_InsertUpdate()

    # Now, we navigate to the equipment and update the IMEI and device info.
    tmaDriver.Service_NavToEquipmentFromService()

    thisEquipment = TMAEquipment(mainType=devices[device]["tmaMainType"],
                                     subType=devices[device]["tmaSubType"],
                                     make=devices[device]["tmaMake"],
                                     model=devices[device]["tmaModel"])
    deviceToBuild = thisEquipment
    if(imei is None):
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


# Given a workorderNumber, this method examines it, tries to figure out the type of workorder it is, and whether
# it is valid to submit automatically through the respective carrier.
def processPreOrderWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,workorderNumber,reviewMode=True,referenceNumber=None,subjectLine : str = None):
    maintenance.validateCimpl(cimplDriver)
    print(f"Cimpl WO {workorderNumber}: Beginning automation")
    workorder = readCimplWorkorder(cimplDriver=cimplDriver,workorderNumber=workorderNumber)

    # Test to ensure the operation type is valid
    if(workorder["OperationType"] not in ("New Request","Upgrade")):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order type '{workorder['OperationType']}' is not understood by the Shaman.")
        return False

    # Test to ensure status is operable
    if(workorder["Status"] == "Completed" or workorder["Status"] == "Cancelled"):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order is already {workorder['Status']}")
        return False

    # Test for correct carrier
    if(workorder["Carrier"].lower() == "verizon wireless"):
        carrier = "Verizon Wireless"
    else:
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as carrier is not Verizon ({workorder['Carrier']})")
        return False

    # Test to ensure it hasn't already been placed
    if (findPlacedCimplOrderNumber(workorder["Notes"],carrier=carrier) is not None):
        print(f"Cimpl WO {workorderNumber}: An order has already been submitted for this Cimpl WO. Please review.")
        return False

    # Get device model ID from Cimpl
    # TODO better device validation?
    userID = getNetworkIDFromActions(workorder["Actions"])
    classifiedHardware = classifyHardwareInfo(workorder["HardwareInfo"],carrier=workorder["Carrier"])
    deviceID = classifiedHardware["DeviceID"]
    accessoryIDs = classifiedHardware["AccessoryIDs"]

    if(workorder["Comment"] != ""):
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        userInput = input(f"WARNING: There is a comment on this workorder:\n\"{workorder['Comment']}\"\n\n Press enter to continue ordering. Type anything to cancel.")
        if(userInput != ""):
            return False
    maintenance.validateCimpl(cimplDriver)

    if(len(workorder["Notes"]) > 0):
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        userInput = input("WARNING: There are existing notes on this workorder. Please review, then press enter to continue. Type anything to cancel.")
        if(userInput != ""):
            return False
    maintenance.validateCimpl(cimplDriver)

    maintenance.validateTMA(tmaDriver,"Sysco")
    tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="People", entryID=userID))
    thisPerson = tmaDriver.People_ReadAllInformation()

    if(workorder["OperationType"] == "New Request"):
        if(len(thisPerson.info_LinkedServices) > 0):
            playsoundAsync(paths["media"] / "shaman_attention.mp3")
            userInput = input(f"WARNING: User '{userID}' already has linked services. Press enter to continue. Type anything to cancel.")
            if(userInput != ""):
                return False
        maintenance.validateTMA(tmaDriver,"Sysco")
    elif(workorder["OperationType"] == "Upgrade"):
        # TODO We just navigate here to raise errors in case the line is inactive. Maybe come up with better system?
        maintenance.validateTMA(tmaDriver,"Sysco")
        tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="Service", entryID=workorder["ServiceID"]))

    print(f"Cimpl WO {workorderNumber}: Determined as valid WO for Shaman rituals")
    if(referenceNumber is not None):
        maintenance.validateCimpl(cimplDriver)
        cimplDriver.Workorders_NavToSummaryTab()
        cimplDriver.Workorders_WriteReferenceNo(referenceNo=referenceNumber)
        cimplDriver.Workorders_ApplyChanges()

    # If operation type is a New Install
    if(workorder["OperationType"] == "New Request"):
        print(f"Cimpl WO {workorderNumber}: Ordering new device ({deviceID}) and service for user {userID}")
        orderNumber = placeVerizonNewInstall(drivers=drivers,deviceID=deviceID,accessoryIDs=accessoryIDs,
                                            firstName=thisPerson.info_FirstName,lastName=thisPerson.info_LastName,userEmail=thisPerson.info_Email,
                                            address1=workorder["Shipping"]["Address1"],address2=workorder["Shipping"]["Address2"],city=workorder["Shipping"]["City"],
                                            state=workorder["Shipping"]["State"],zipCode=workorder["Shipping"]["ZipCode"],reviewMode=reviewMode,contactEmails=thisPerson.info_Email)
        print(f"Cimpl WO {workorderNumber}: Finished ordering new device and service for user {userID}")
    elif(workorder["OperationType"] == "Upgrade"):
        print(f"Cimpl WO {workorderNumber}: Ordering upgrade ({deviceID}) and service for user {userID} with service {workorder['ServiceID']}")
        orderNumber = placeVerizonUpgrade(drivers=drivers,deviceID=deviceID,serviceID=workorder['ServiceID'],accessoryIDs=accessoryIDs,
                                            firstName=thisPerson.info_FirstName,lastName=thisPerson.info_LastName,
                                            address1=workorder["Shipping"]["Address1"],address2=workorder["Shipping"]["Address2"],city=workorder["Shipping"]["City"],
                                            state=workorder["Shipping"]["State"],zipCode=workorder["Shipping"]["ZipCode"],reviewMode=reviewMode,contactEmails=thisPerson.info_Email)
        print(f"Cimpl WO {workorderNumber}: Finished ordering upgrade for user {userID} on line {workorder['ServiceID']}")
    else:
        raise ValueError(f"Incorrect operation type for preprocess of workorder: '{workorder['OperationType']}'")

    maintenance.validateCimpl(cimplDriver)
    if(orderNumber is False):
        return False
    elif(orderNumber == "MTNPending"):
        print(f"Cimpl WO {workorderNumber}: Couldn't upgrade line {workorder['ServiceID']} due to 'MTN Pending' error on Verizon.")
        return False
    elif(orderNumber == "NotETFEligible"):
        print(f"Cimpl WO {workorderNumber}: Couldn't upgrade line {workorder['ServiceID']} because it is too early to upgrade with ETF waiver.")
        return False

    cimplDriver.Workorders_NavToSummaryTab()
    cimplDriver.Workorders_WriteNote(subject="Order Placed",noteType="Information Only",status="Completed",content=orderNumber)

    # Confirm workorder, if not already confirmed.
    if(workorder["Status"] == "Pending"):
        if(workorder["OperationType"].lower() == "new request"):
            if carrier == "BellMobility":
                templatePath = f"{b.paths.emailTemplates}/{b.emailTemplates['BellMobility']['NewInstall'][deviceID]}"
            else:
                templatePath = f"{b.paths.emailTemplates}/{b.emailTemplates['NormalCarrier']['NewInstall'][deviceID]}"
        elif(workorder["OperationType"].lower() == "upgrade"):
            if carrier == "BellMobility":
                templatePath = f"{b.paths.emailTemplates}/{b.emailTemplates['BellMobility']['Upgrade'][deviceID]}"
            else:
                templatePath = f"{b.paths.emailTemplates}/{b.emailTemplates['NormalCarrier']['Upgrade'][deviceID]}"
        else:
            raise ValueError(f"Found incompatible order type after performing an order: '{workorder['OperationType']}'")
        with open(templatePath, "r") as file:
            emailContent = file.read()

        cimplDriver.Workorders_SetStatus(status="Confirm",emailRecipients=thisPerson.info_Email,emailCCs="btnetworkservicesmobility@sysco.com",emailContent=emailContent)
        print(f"Cimpl WO {workorderNumber}: Added order number to workorder notes and confirmed request.")

    if(subjectLine is not None):
        cimplDriver.Workorders_NavToSummaryTab()
        subjectLine = subjectLine.replace("%D",datetime.now().strftime('%m/%d/%Y'))
        cimplDriver.Workorders_WriteSubject(subject=subjectLine)
        cimplDriver.Workorders_ApplyChanges()

    return True

# Given a workorderNumber, this method examines it, tries to figure out the type of workorder it is and whether
# it has a relevant order number, looks up to see if order is completed, and then closes it in TMA.
def processPostOrderWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,vzwDriver : VerizonDriver,bakaDriver : BakaDriver,
                              workorderNumber):

    print(f"Cimpl WO {workorderNumber}: Beginning automation")
    workorder = readCimplWorkorder(cimplDriver=cimplDriver,workorderNumber=workorderNumber)

    # Test to ensure the operation type is valid
    if(workorder["OperationType"] not in ("New Request","Upgrade")):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order type '{workorder['OperationType']}' is not understood by the Shaman.")
        return False

    # Test to ensure status is operable
    if(workorder["Status"] == "Completed" or workorder["Status"] == "Cancelled"):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order is already {workorder['Status']}")
        return False

    # Test for correct carrier
    if(workorder["Carrier"].lower() == "verizon wireless"):
        carrier = "Verizon Wireless"
    elif(workorder["Carrier"].lower() == "bell mobility"):
        carrier = "Bell Mobility"
    else:
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as carrier is not Verizon or Bell ({workorder['Carrier']})")
        return False

    # Test to ensure it can properly locate the order number
    carrierOrderNumber = findPlacedCimplOrderNumber(workorder["Notes"],carrier=carrier)
    if (carrierOrderNumber is None):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as no completed carrier order can be found.")
        return False

    # TODO only supports verizon and bell atm
    # Read Verizon Order
    if(carrier == "Verizon Wireless"):
        carrierOrder = readVerizonOrder(verizonDriver=vzwDriver,verizonOrderNumber=carrierOrderNumber)
        if(carrierOrder is None):
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order number '{carrierOrderNumber}' is not yet showing in the Verizon Order Viewer.")
            return False
        elif(carrierOrder["Status"] != "Completed"):
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order number '{carrierOrderNumber}' has status '{carrierOrder['Status']}' and not Complete.")
            return False
    # Read Bell Order
    elif(carrier == "Bell Mobility"):
        carrierOrder = readBakaOrder(bakaDriver=bakaDriver,bakaOrderNumber=carrierOrderNumber)
        if(carrierOrder["Status"] != "Complete"):
            print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order number '{carrierOrderNumber}' has status '{carrierOrder['Status']}' and not Complete.")
            return False
    else:
        raise ValueError("This should never happen. This means a non-supported carrier was validated by function - fix code immediately.")

    # Get device model ID from Cimpl
    print(f"Cimpl WO {workorderNumber}: Determined as valid WO for Shaman rituals")
    hardwareInfo = classifyHardwareInfo(workorder["HardwareInfo"],workorder["Carrier"],raiseNoEquipmentError=False)
    if(hardwareInfo):
        deviceID = hardwareInfo["DeviceID"]
    else:
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        userInput = input("No device is specified in the 'Hardware Info' section of Cimpl. Please manually select the ordered device, or enter anything else to cancel.\n\n"
                          "1. iPhone 13 128gb\n2. Samsung Galaxy S23FE 128gb\n3. Verizon Orbic 5G UW\n")
        if(userInput == "1"):
            deviceID = "iPhone13_128GB"
        elif(userInput == "2"):
            deviceID = "GalaxyS23_128GB"
        elif(userInput == "3"):
            deviceID = "Orbic"
        else:
            return False

    # If operation type is a New Install
    if(workorder["OperationType"] == "New Request"):
        userID = getNetworkIDFromActions(workorder["Actions"])
        print(f"Cimpl WO {workorderNumber}: Building new service {carrierOrder['WirelessNumber']} for user {userID}")
        returnCode = documentTMANewInstall(tmaDriver=tmaDriver,client="Sysco",netID=userID,serviceNum=carrierOrder["WirelessNumber"],installDate=carrierOrder["OrderDate"],device=deviceID,imei=carrierOrder["IMEI"],carrier=carrier)
        if(returnCode == "Completed"):
            writeServiceToCimplWorkorder(cimplDriver=cimplDriver,serviceNum=carrierOrder["WirelessNumber"],carrier=carrier,installDate=carrierOrder["OrderDate"])
            print(f"Cimpl WO {workorderNumber}: Finished building new service {carrierOrder['WirelessNumber']} for user {userID}")
        elif(returnCode == "ServiceAlreadyExists"):
            print(f"Cimpl WO {workorderNumber}: Can't build new service for {carrierOrder['WirelessNumber']}, as the service already exists in the TMA database")
            return False
        elif(returnCode == "WrongDevice"):
            print(f"Cimpl WO {workorderNumber}: Failed to build new service in TMA, got wrong device '{deviceID}'")
            return False
    # If operation type is an Upgrade
    elif(workorder["OperationType"] == "Upgrade"):
        print(f"Cimpl WO {workorderNumber}: Processing Upgrade for service {carrierOrder['WirelessNumber']}")
        returnCode = documentTMAUpgrade(tmaDriver=tmaDriver,client="Sysco",serviceNum=carrierOrder["WirelessNumber"],installDate=carrierOrder["OrderDate"],device=deviceID,imei=carrierOrder["IMEI"])
        if(returnCode == "Completed"):
            print(f"Cimpl WO {workorderNumber}: Finished upgrading TMA service {carrierOrder['WirelessNumber']}")
        elif(returnCode == "WrongDevice"):
            print(f"Cimpl WO {workorderNumber}: Failed to upgrade service in TMA, got wrong device '{deviceID}'")
            return False

    # Write tracking information
    maintenance.validateCimpl(cimplDriver)
    cimplDriver.Workorders_NavToSummaryTab()
    if(carrierOrder["TrackingNumber"].strip() != ""):
        cimplDriver.Workorders_WriteNote(subject="Tracking",noteType="Information Only",status="Completed",content=f"Courier: {carrierOrder['Courier']}\nTracking Number: {carrierOrder['TrackingNumber']}")

    # Complete workorder
    cimplDriver.Workorders_SetStatus(status="Complete")
    print(f"Cimpl WO {workorderNumber}: Finished all Cimpl work")
    return True


br = Browser()
tma = TMADriver(br)
cimpl = CimplDriver(br)
vzw = VerizonDriver(br)
baka = BakaDriver(br)

if(True):
    placeVerizonNewInstall(verizonDriver=vzw,
                           deviceID="iPhone14_128GB",accessoryIDs=["VerizonWallAdapter"],
                           firstName="John",lastName="Sysco",userEmail="john.sysco@test.com",
                           address1="1370 Enclave Parkway",city="Houston",state="Texas",zipCode="77077",
                           contactEmails="asomheil@uplandsoftware.com")
if(False):
    placeVerizonUpgrade(verizonDriver=vzw,serviceID="281-961-7581",
                        deviceID="iPhone14_128GB",accessoryIDs=["VerizonWallAdapter"],
                        firstName="John",lastName="Sysco",
                        address1="1370 Enclave Parkway",city="Houston",state="Texas",zipCode="77077",
                        contactEmails="asomheil@uplandsoftware.com")

wosToProcess = []
for wo in wosToProcess:
    try:
        processPostOrderWorkorder(tmaDriver=tma,cimplDriver=cimpl,vzwDriver=vzw,bakaDriver=baka,
                          workorderNumber=wo)
    except Exception as e:
        playsoundAsync(paths["media"] / "shaman_error.mp3")
        raise e