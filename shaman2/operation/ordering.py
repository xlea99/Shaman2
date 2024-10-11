from datetime import datetime
from selenium.webdriver.common.by import By
from shaman2.selenium.browser import Browser
from shaman2.selenium.baka_driver import BakaDriver
from shaman2.selenium.cimpl_driver import CimplDriver
from shaman2.selenium.tma_driver import TMADriver, TMALocation, TMAPeople, TMAService,TMAEquipment, TMACost
from shaman2.selenium.verizon_driver import VerizonDriver
from shaman2.selenium.eyesafe_driver import EyesafeDriver
from shaman2.operation import maintenance
from shaman2.common.config import mainConfig,accessories,clients,devices,emailTemplatesConfig, deviceCimplMappings
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.utilities.shaman_utils import convertServiceIDFormat,convertStateFormat, consoleUserWarning
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.utilities.address_validation import validateAddress
from shaman2.utilities.misc import isNumber

#region === Carrier Order Reading ===

# Searches up, and reads, a full workorder given by workorderNumber.
def readCimplWorkorder(cimplDriver : CimplDriver,workorderNumber):
    maintenance.validateCimpl(cimplDriver)
    cimplDriver.navToWorkorderCenter()
    workorderNumber = str(workorderNumber)

    cimplDriver.Filters_Clear()
    cimplDriver.Filters_AddWorkorderNumber(status="Equals",workorderNumber=workorderNumber)
    cimplDriver.Filters_Apply()

    cimplDriver.openWorkorder(workorderNumber=workorderNumber)

    return cimplDriver.Workorders_ReadFullWorkorder()

# Searches up, and reads, a full Verizon order number.
def readVerizonOrder(verizonDriver : VerizonDriver,verizonOrderNumber,orderViewPeriod):
    maintenance.validateVerizon(verizonDriver)
    verizonDriver.navToOrderViewer()

    verizonDriver.OrderViewer_UpdateOrderViewDropdown(orderViewPeriod)
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
                           address1,city,state,zipCode,companyName,contactEmails : str | list,
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

    # Search for each requested accessory, add it to the cart, then continue.
    for accessoryID in accessoryIDs:
        verizonDriver.AccessorySelection_SearchForAccessory(accessoryID=accessoryID)
        verizonDriver.AccessorySelection_AddAccessoryToCart(accessoryID=accessoryID)
    verizonDriver.AccessorySelection_Continue(orderPath="NewInstall")
    # This should send us to the plan selection page.

    # Select plan, then click continue.
    deviceType = devices[deviceID]["tmaSubType"]
    verizonDriver.PlanSelection_SelectPlan(planID=clients["Sysco"]["Plans"][deviceType]["Verizon Wireless"][0]["planCode"])
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

    # Add specified features in main.toml, then continue
    if(deviceType == "Smart Phone"):
        featuresToAdd = mainConfig["sysco"]["vzwSmartphoneFeatures"]
    elif(deviceType == "Aircard"):
        featuresToAdd = mainConfig["sysco"]["vzwAircardFeatures"]
    elif(deviceType == "Tablet"):
        featuresToAdd = mainConfig["sysco"]["vzwTabletFeatures"]
    else:
        featuresToAdd = []
    if(featuresToAdd):
        verizonDriver.ShoppingCart_AddFeatures()
        for featureToAdd in featuresToAdd:
            verizonDriver.FeatureSelection_SelectFeature(featureName=featureToAdd)
        verizonDriver.FeatureSelection_Continue()
    # This should send us back to the shopping cart page.

    # Continue from shopping cart to checkout
    verizonDriver.ShoppingCart_ContinueToCheckOut()
    # This should send us to the checkout screen

    # "Clean" the contact emails for special characters which break Verizon.
    if(type(contactEmails) is not list):
        contactEmails = [contactEmails]
    finalContactEmails = []
    for contactEmail in contactEmails:
        contactEmail = contactEmail.lower().strip()
        isValidEmail = True
        for character in contactEmail:
            if(not (character.isalnum() or character in "._@")):
                isValidEmail = False
        if(isValidEmail):
            finalContactEmails.append(contactEmail)



    # Fill in shipping information, then submit the order.
    verizonDriver.Checkout_AddAddressInfo(company=companyName,attention=f"{firstName} {lastName}",
                                          address1=address1,address2=address2,city=city,zipCode=zipCode,
                                          stateAbbrev=convertStateFormat(stateString=state,targetFormat="abbreviation"),
                                          contactPhone=mainConfig["misc"]["contactPhone"],notificationEmails=finalContactEmails)
    if(reviewMode):
        playsoundAsync(paths["media"] / "shaman_order_ready.mp3")
        userResponse = input("Order is ready to be submitted. Please review, then press enter to place. Type anything else to cancel.")
        if(userResponse):
            error = ValueError("User cancelled submission of order.")
            log.error(error)
            raise error
    maintenance.validateVerizon(verizonDriver)
    orderInfo = verizonDriver.Checkout_PlaceOrder(billingAccountNum=clients["Sysco"]["Accounts"]["Verizon Wireless"])
    # Order should now be placed!

    return orderInfo
# Places an entire Verizon new install.
def placeVerizonUpgrade(verizonDriver : VerizonDriver,serviceID,deviceID : str,accessoryIDs : list,
                           firstName,lastName,
                           address1,city,state,zipCode,companyName,contactEmails : str | list,
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
    if (type(contactEmails) is not list):
        contactEmails = [contactEmails]
    finalContactEmails = []
    for contactEmail in contactEmails:
        contactEmail = contactEmail.lower().strip()
        isValidEmail = True
        for character in contactEmail:
            if (not (character.isalnum() or character in "._@")):
                isValidEmail = False
        if (isValidEmail):
            finalContactEmails.append(contactEmail)

    # Fill in shipping information, then submit the order.
    verizonDriver.Checkout_AddAddressInfo(company=companyName,attention=f"{firstName} {lastName}",
                                          address1=address1,address2=address2,city=city,zipCode=zipCode,
                                          stateAbbrev=convertStateFormat(stateString=state,targetFormat="abbreviation"),
                                          contactPhone=mainConfig["misc"]["contactPhone"],notificationEmails=finalContactEmails)
    if(reviewMode):
        playsoundAsync(paths["media"] / "shaman_order_ready.mp3")
        userResponse = input("Order is ready to be submitted. Please review, then press enter to place. Type anything else to cancel.")
        if(userResponse):
            error = ValueError("User cancelled submission of order.")
            log.error(error)
            raise error
    maintenance.validateVerizon(verizonDriver)
    orderInfo = verizonDriver.Checkout_PlaceOrder(billingAccountNum=clients["Sysco"]["Accounts"]["Verizon Wireless"])
    # Order should now be placed!

    return orderInfo

# This method accepts an accessoryID list, and returns an accessoryID list adjusted for any norms specified
# on Sysco in the config.
def adjustAccessoriesForSyscoNorms(deviceID : str, accessoryIDs : list,carrier : str):
    accessoryIDs = set(accessoryIDs)

    # Right now, only VZW requires special cases.
    if (carrier.lower() == "verizon wireless"):
        if (not mainConfig["sysco"]["orderVehicleChargers"]):
            for accessoryID in accessoryIDs:
                if (accessories[accessoryID]["type"] == "vehicleCharger"):
                    accessoryIDs.remove(accessoryID)
                    break
        # TODO for now, the "default order wall adapter" system works, but it could do with an overhaul to support more cases down the line
        if (devices[deviceID]["tmaSubType"] == "Smart Phone"):
            extraAccessoriesToOrder = mainConfig["sysco"]["vzwAccessoriesToAlwaysOrder_SmartPhone"]
        elif (devices[deviceID]["tmaSubType"] == "Aircard"):
            extraAccessoriesToOrder = mainConfig["sysco"]["vzwAccessoriesToAlwaysOrder_Aircard"]
        elif (devices[deviceID]["tmaSubType"] == "Tablet"):
            extraAccessoriesToOrder = mainConfig["sysco"]["vzwAccessoriesToAlwaysOrder_Tablet"]
        else:
            extraAccessoriesToOrder = []
        accessoryIDs = accessoryIDs | set(extraAccessoriesToOrder)
        return list(accessoryIDs)
    else:
        return accessoryIDs

# Places an entire Eyesafe order.
def placeEyesafeOrder(eyesafeDriver : EyesafeDriver,eyesafeAccessoryName : str,
                      userFirstName : str, userLastName : str,
                      address1,city,state,zipCode,address2 = None):
    maintenance.validateEyesafe(eyesafeDriver)

    eyesafeDriver.navToShop()
    eyesafeDriver.addItemToCart(itemName=accessories[eyesafeAccessoryName]["eyesafeCardName"])
    eyesafeDriver.checkOutFromCart()
    eyesafeDriver.writeShippingInformation(firstName=userFirstName,lastName=userLastName,
                                           address1=address1,address2=address2,city=city,state=state,zipCode=zipCode)
    eyesafeDriver.continueFromShipping()
    return eyesafeDriver.submitOrder()

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
        costType = "Aircard"
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
def processPreOrderWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,verizonDriver : VerizonDriver,eyesafeDriver : EyesafeDriver,
                             workorderNumber,reviewMode=True,referenceNumber=None,subjectLine : str = None):
    # First, read the full workorder.
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
    if (workorder.getLatestOrderNote() is not None):
        warningMessage = f"Cimpl WO {workorderNumber}: An order has already been submitted for this Cimpl WO."
        if(not consoleUserWarning(warningMessage)):
            return False
    # Check to make sure no existing comments interfere with the request.
    if(workorder["Comment"] != ""):
        warningMessage = f"Cimpl WO {workorderNumber}: WARNING - There is a comment on this workorder:\n\"{workorder['Comment']}\"\n\n"
        if(not consoleUserWarning(warningMessage)):
            return False
    # Check to make sure no existing notes interfere with the request.
    if(len(workorder["Notes"]) > 0):
        warningMessage = f"Cimpl WO {workorderNumber}: WARNING - There are existing notes on this workorder."
        if(not consoleUserWarning(warningMessage)):
            return False

    # Make any necessary adjustments to accessories list.
    accessoryIDs = adjustAccessoriesForSyscoNorms(deviceID=workorder["DeviceID"],accessoryIDs=workorder["AccessoryIDs"],carrier=carrier)

    # Read the people object from TMA.
    maintenance.validateTMA(tmaDriver,"Sysco")
    tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="People", entryID=workorder["UserNetID"]))
    thisPerson = tmaDriver.People_ReadAllInformation()

    if(workorder["OperationType"] == "New Request"):
        if(len(thisPerson.info_LinkedServices) > 0):
            warningMessage = f"WARNING: User '{workorder['UserNetID']}' already has linked services."
            if (not consoleUserWarning(warningMessage)):
                return False
        maintenance.validateTMA(tmaDriver,"Sysco")
    elif(workorder["OperationType"] == "Upgrade"):
        # TODO We just navigate here to raise errors in case the line is inactive. Maybe come up with better system?
        maintenance.validateTMA(tmaDriver,"Sysco")
        tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="Service", entryID=workorder["ServiceID"]))

    # Write name on order
    print(f"Cimpl WO {workorderNumber}: Determined as valid WO for Shaman rituals")
    if(referenceNumber is not None):
        maintenance.validateCimpl(cimplDriver)
        cimplDriver.Workorders_NavToSummaryTab()
        cimplDriver.Workorders_WriteReferenceNo(referenceNo=referenceNumber)
        cimplDriver.Workorders_ApplyChanges()

    # Validate the shipping address
    validatedAddress = validateAddress(rawAddressString=workorder["RawShippingAddress"])
    print(f"Cimpl WO {workorderNumber}: Validated address as: {validatedAddress}")

    # If operation type is a New Install
    if(workorder["OperationType"] == "New Request"):
        print(f"Cimpl WO {workorderNumber}: Ordering new device ({workorder['DeviceID']}) and service for user {workorder['UserNetID']}")
        orderNumber = placeVerizonNewInstall(verizonDriver=verizonDriver,deviceID=workorder['DeviceID'],accessoryIDs=accessoryIDs,companyName="Sysco",
                                            firstName=workorder["UserFirstName"],lastName=workorder["UserLastName"],userEmail=thisPerson.info_Email,
                                            address1=validatedAddress["Address1"],address2=validatedAddress.get("Address2",None),city=validatedAddress["City"],
                                            state=validatedAddress["State"],zipCode=validatedAddress["ZipCode"],reviewMode=reviewMode,contactEmails=thisPerson.info_Email)
        print(f"Cimpl WO {workorderNumber}: Finished ordering new device and service for user {workorder['UserNetID']}")
    # If op type is Upgrade
    elif(workorder["OperationType"] == "Upgrade"):
        print(f"Cimpl WO {workorderNumber}: Ordering upgrade ({workorder['DeviceID']}) and service for user {workorder['UserNetID']} with service {workorder['ServiceID']}")
        orderNumber = placeVerizonUpgrade(verizonDriver=verizonDriver,deviceID=workorder['DeviceID'],serviceID=workorder['ServiceID'],accessoryIDs=accessoryIDs,
                                          firstName=workorder["UserFirstName"],lastName=workorder["UserLastName"],companyName="Sysco",
                                          address1=validatedAddress["Address1"],address2=validatedAddress.get("Address2", None),city=validatedAddress["City"],
                                          state=validatedAddress["State"], zipCode=validatedAddress["ZipCode"],reviewMode=reviewMode,contactEmails=thisPerson.info_Email)
        print(f"Cimpl WO {workorderNumber}: Finished ordering upgrade for user {workorder['UserNetID']} on line {workorder['ServiceID']}")
    # Otherwise, error out.
    else:
        error = ValueError(f"Incorrect operation type for preprocess of workorder: '{workorder['OperationType']}'")
        log.error(error)
        raise error

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

    # Handle ordering Eyesafe, if specified
    if(workorder["EyesafeAccessoryID"]):
        # First make sure the requested eyeSafe device is compatible with the device we've ordered.
        if(workorder['DeviceID'] in accessories[workorder["EyesafeAccessoryID"]]["compatibleDevices"]):
            eyesafeOrderNumber = placeEyesafeOrder(eyesafeDriver=eyesafeDriver,eyesafeAccessoryName=workorder["EyesafeAccessoryID"],
                                    userFirstName=thisPerson.info_FirstName,userLastName=thisPerson.info_LastName,
                                    address1=validatedAddress["Address1"],address2=validatedAddress["Address2"],
                                    city=validatedAddress["City"],state=validatedAddress["State"],zipCode=validatedAddress["ZipCode"])
            maintenance.validateCimpl(cimplDriver)
            cimplDriver.Workorders_NavToSummaryTab()
            cimplDriver.Workorders_WriteNote(subject="Eyesafe Order Placed", noteType="Information Only", status="Completed",content=eyesafeOrderNumber)
            log.info(f"Ordered Eyesafe device '{workorder["EyesafeAccessoryID"]}' per '{eyesafeOrderNumber}'")
        else:
            log.info(f"User requested eyesafe accessory '{workorder["EyesafeAccessoryID"]}', but this accessory is not compatible with the ordere device '{workorder['DeviceID']}'")

    # Confirm workorder, if not already confirmed.
    if(workorder["Status"] == "Pending"):
        if(workorder["OperationType"].lower() == "new request"):
            if carrier == "BellMobility":
                templateFileName = emailTemplatesConfig["BellMobility"]["NewInstall"].get(workorder['DeviceID'],None)
            else:
                templateFileName = emailTemplatesConfig["NormalCarrier"]["NewInstall"].get(workorder['DeviceID'],None)
        elif(workorder["OperationType"].lower() == "upgrade"):
            if carrier == "BellMobility":
                templateFileName = emailTemplatesConfig["BellMobility"]["Upgrade"].get(workorder['DeviceID'],None)
            else:
                templateFileName = emailTemplatesConfig["NormalCarrier"]["Upgrade"].get(workorder['DeviceID'],None)
        else:
            error = ValueError(f"Found incompatible order type after performing an order: '{workorder['OperationType']}'")
            log.error(error)
            raise error

        if(templateFileName is None):
            cimplDriver.Workorders_SetStatus(status="Confirm")
            print(f"Cimpl WO {workorderNumber}: Added order number to workorder notes and confirmed request.")
        else:
            templatePath = paths["emailTemplates"] / templateFileName
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
def processPostOrderWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,vzwDriver : VerizonDriver,bakaDriver : BakaDriver,workorderNumber,
                              orderViewPeriod="180 Days"):
    # Read full workorder.
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
    carrierOrderNote = workorder.getLatestOrderNote()
    if (carrierOrderNote is None):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as no completed carrier order can be found.")
        return False
    else:
        carrierOrderNumber = carrierOrderNote["ClassifiedValue"]

    # Read Verizon Order
    if(carrier == "Verizon Wireless"):
        carrierOrder = readVerizonOrder(verizonDriver=vzwDriver,verizonOrderNumber=carrierOrderNumber,orderViewPeriod=orderViewPeriod)
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

    if(not workorder["DeviceID"]):
        # Quickly generate a list of devices currently specified in device_cimpl_mappings to prompt the user with.
        commonMappedDevices = set()
        for thisDeviceID in deviceCimplMappings.values():
            commonMappedDevices.add(thisDeviceID)
        commonMappedDevices = list(commonMappedDevices)
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        promptString = f"Cimpl WO {workorderNumber}: No device is specified in the 'Hardware Info' section of Cimpl. Please manually select the ordered device, or enter anything else to skip order.\n\n"
        for counter, thisDeviceID in enumerate(commonMappedDevices):
            promptString += f"{counter}. {thisDeviceID}\n"
        userInput = input(promptString).strip()
        if(isNumber(userInput) and (0 <= int(userInput) < len(commonMappedDevices))):
            deviceID = commonMappedDevices[int(userInput)]
        else:
            return False
    else:
        deviceID = workorder["DeviceID"]

    # If operation type is a New Install
    if(workorder["OperationType"] == "New Request"):
        print(f"Cimpl WO {workorderNumber}: Building new service {carrierOrder['WirelessNumber']} for user {workorder['UserNetID']}")
        returnCode = documentTMANewInstall(tmaDriver=tmaDriver,client="Sysco",netID=workorder['UserNetID'],serviceNum=carrierOrder["WirelessNumber"],installDate=carrierOrder["OrderDate"],device=deviceID,imei=carrierOrder["IMEI"],carrier=carrier)
        if(returnCode == "Completed"):
            writeServiceToCimplWorkorder(cimplDriver=cimplDriver,serviceNum=carrierOrder["WirelessNumber"],carrier=carrier,installDate=carrierOrder["OrderDate"])
            print(f"Cimpl WO {workorderNumber}: Finished building new service {carrierOrder['WirelessNumber']} for user {workorder['UserNetID']}")
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
    if(carrierOrder["TrackingNumber"] is not None and carrierOrder["TrackingNumber"].strip() != ""):
        cimplDriver.Workorders_WriteNote(subject="Tracking",noteType="Information Only",status="Completed",content=f"Courier: {carrierOrder['Courier']}\nTracking Number: {carrierOrder['TrackingNumber']}")

    # Complete workorder
    cimplDriver.Workorders_SetStatus(status="Complete")
    print(f"Cimpl WO {workorderNumber}: Finished all Cimpl work")
    return True


# Does what it says on the tin
def placeMissingEyesafeOrderFromCimplWorkorder(tmaDriver : TMADriver,cimplDriver : CimplDriver,eyesafeDriver : EyesafeDriver,
                                               workorderNumber):
    maintenance.validateCimpl(cimplDriver)
    print(f"Cimpl WO {workorderNumber}: Beginning automation")
    workorder = readCimplWorkorder(cimplDriver=cimplDriver,workorderNumber=workorderNumber)

    # Test to ensure the operation type is valid
    if(workorder["OperationType"] not in ("New Request","Upgrade")):
        print(f"Cimpl WO {workorderNumber}: Can't complete WO, as order type '{workorder['OperationType']}' is not understood by the Shaman.")
        return False

    # Test to ensure it hasn't already been placed
    for note in workorder["Notes"]:
        if("eyesafe" in note["Subject"].lower()):
            print(f"Cimpl WO {workorderNumber}: An eyesafe order has already been submitted for this Cimpl WO.")
            return False

    # Get device model ID from Cimpl
    if(not workorder["DeviceID"]):
        print(f"Cimpl WO {workorderNumber}: Failed to validate hardware info, likely due to missing device in order.")
        return False
    eyesafeAccessory = workorder["EyesafeAccessoryID"]

    if(not eyesafeAccessory):
        print(f"Cimpl WO {workorderNumber}: No eyesafe device was requested.")
        return False

    # Read the people object from TMA.
    maintenance.validateTMA(tmaDriver,"Sysco")
    tmaDriver.navToLocation(TMALocation(client="Sysco", entryType="People", entryID=workorder['UserNetID']))
    thisPerson = tmaDriver.People_ReadAllInformation()

    # Validate the shipping address
    validatedAddress = validateAddress(rawAddressString=workorder["RawShippingAddress"])
    print(validatedAddress)

    # Handle ordering Eyesafe
    eyesafeOrderNumber = placeEyesafeOrder(eyesafeDriver=eyesafeDriver, eyesafeAccessoryName=eyesafeAccessory,
                                               userFirstName=thisPerson.info_FirstName,
                                               userLastName=thisPerson.info_LastName,
                                               address1=validatedAddress["Address1"],
                                               address2=validatedAddress["Address2"],
                                               city=validatedAddress["City"], state=validatedAddress["State"],
                                               zipCode=validatedAddress["ZipCode"])

    maintenance.validateCimpl(cimplDriver)
    if(workorder["Status"] != "Completed"):
        cimplDriver.Workorders_NavToSummaryTab()
        cimplDriver.Workorders_WriteNote(subject="Eyesafe Order Placed", noteType="Information Only",
                                         status="Completed", content=eyesafeOrderNumber)

    print(f"Cimpl WO {workorderNumber}: Eyesafe Order completed - '{eyesafeOrderNumber}'")



br = Browser()
tma = TMADriver(br)
cimpl = CimplDriver(br)
vzw = VerizonDriver(br)
baka = BakaDriver(br)
eyesafe = EyesafeDriver(br)

missingEyesafeWOs = []
for wo in missingEyesafeWOs:
    try:
        # Place any missing eyesafe orders.
        placeMissingEyesafeOrderFromCimplWorkorder(tmaDriver=tma,cimplDriver=cimpl,eyesafeDriver=eyesafe,workorderNumber=wo)
    except Exception as e:
        playsoundAsync(paths["media"] / "shaman_error.mp3")
        raise e

preProcessWOs = []
for wo in preProcessWOs:
    try:
        processPreOrderWorkorder(tmaDriver=tma,cimplDriver=cimpl,verizonDriver=vzw,eyesafeDriver=eyesafe,
                          workorderNumber=wo,referenceNumber=mainConfig["cimpl"]["referenceNumber"],subjectLine="Order Placed %D")
    except Exception as e:
        playsoundAsync(paths["media"] / "shaman_error.mp3")
        raise e

postProcessWOs = []
for wo in postProcessWOs:
    try:
        processPostOrderWorkorder(tmaDriver=tma,cimplDriver=cimpl,vzwDriver=vzw,bakaDriver=baka,
                          workorderNumber=wo)
    except Exception as e:
        playsoundAsync(paths["media"] / "shaman_error.mp3")
        raise e


# TEMPLATES
#
# ORDERING A NEW PHONE:
# placeVerizonNewInstall(verizonDriver=vzw,deviceID="iPhone14_128GB",accessoryIDs=["BelkinWallAdapter","iPhone14Defender"],
#                        firstName="",lastName="",userEmail="",address1="",address2="",city="",state="",zipCode="",companyName="Sysco",contactEmails="")
# placeVerizonUpgrade(verizonDriver=vzw,serviceID="",deviceID="iPhone14_128GB",accessoryIDs=["BelkinWallAdapter","iPhone14Defender"],
#                        firstName="",lastName="",address1="",address2="",city="",state="",zipCode="",companyName="Sysco",contactEmails="")
#
# DOCUMENTING A PHONE IN TMA:
# documentTMANewInstall(tmaDriver=tma,client="Sysco",netID="",serviceNum="",installDate="",device="iPhone14_128GB",imei="",carrier="Verizon Wireless")
# documentTMAUpgrade(tmaDriver=tma,client="Sysco",serviceNum="",installDate="",device="iPhone14_128GB",imei="")