import time
import re
import selenium.common.exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from shaman2.selenium.browser import Browser
from shaman2.utilities.shaman_utils import convertServiceIDFormat
from shaman2.common.logger import log
from shaman2.common.config import mainConfig
from shaman2.network.sheets_sync import syscoData

#region === TMA Data Structures ===

# Helper class serving as a structure for organizing and storing locational information about where the program
# is on a TMA page.
class TMALocation:

    # Basic init method initializes a few used variables.
    def __init__(self,isLoggedIn=True,client=None,entryType=None,entryID=None,activeInfoTab=None,activeLinkTab=None):
        # This variable simply denotes whether the TMA object is currently
        # logged in to TMA or not.
        self.isLoggedIn = isLoggedIn

        # This is the current client that is being operated under. At the moment,
        # the only supported clients are Sysco and (to a lesser extent) LYB. However,
        # a placeholder title "DOMAIN" serves to show that no client is currently
        # being operated on.
        self.client = client

        # This shows what type of entry we're currently working under. Possibilities include:
        # -Services
        # -Orders
        # -People
        # -Interactions
        # -Equipment
        # SPECIAL PAGES:
        # -LoginPage
        # -DomainPage
        # -ClientHomePage
        self.entryType = entryType

        # This is a unique, identifiable ID that separates this entry from all others in TMA.
        # For different type of entries, the actual ID will be different. Examples:
        # -Services (Service Number)
        # -Orders ({TMAOrderNumber,ticketOrderNumber,vendorOrderNumber})
        # -People (Network ID)
        # -Interactions (Interaction Number)
        # -Always will be RegularEquipment
        if(entryType == "Order"):
            if(type(entryID) is not dict):
                error = ValueError(f"When creating a TMA Location for an order, the entryID must be a dict ({{TMAOrderNumber,ticketOrderNumber,vendorOrderNumber}}), not '{entryID}' of type '{type(entryID)}'")
                log.error(error)
                raise error
            else:
                self.entryID = {"TMAOrderNumber" : entryID.get("TMAOrderNumber"),
                                "ticketOrderNumber": entryID.get("ticketOrderNumber"),
                                "vendorOrderNumber": entryID.get("vendorOrderNumber")}
        else:
            self.entryID = entryID

        # The currently active info (Line Info, Assignments, Links, History) tab.
        self.activeInfoTab = activeInfoTab
        # The currently active link (Services, People, Interactions, Orders) tab.
        self.activeLinkTab = activeLinkTab

        # Simple raw url of this location.
        self.rawURL = None

    # Equal operator == method compares the values of each important data point.
    def __eq__(self, otherLocationData):
        if(isinstance(otherLocationData,TMALocation)):
            isEqual = False
            if(self.isLoggedIn == otherLocationData.isLoggedIn and self.client == otherLocationData.client and self.entryType == otherLocationData.entryType):
                if(self.entryType == "Service"):
                    if(convertServiceIDFormat(self.entryID,"raw") == convertServiceIDFormat(otherLocationData.entryID,"raw")):
                        isEqual = True
                else:
                    if(self.entryType == "Order"):
                        if((self.entryID["TMAOrderNumber"] is not None and self.entryID["TMAOrderNumber"] == otherLocationData.entryID["TMAOrderNumber"]) or
                        (self.entryID["ticketOrderNumber"] is not None and self.entryID["ticketOrderNumber"] == otherLocationData.entryID["ticketOrderNumber"]) or
                        (self.entryID["vendorOrderNumber"] is not None and self.entryID["vendorOrderNumber"] == otherLocationData.entryID["vendorOrderNumber"])):
                            isEqual = True
                    else:
                        if(self.entryID == otherLocationData.entryID):
                            isEqual = True

            log.debug(f"Tested equality between {self} and {otherLocationData} : {isEqual}")
            return isEqual
        else:
            log.error(f"Tested equality with a non-TMA Location: {otherLocationData}")

    # Simple __str__ method for displaying the current location of the
    # TMA page.
    def __str__(self):
        returnString = ""

        if (self.isLoggedIn):
            returnString += f"* Client({self.client}) | EType({self.entryType}) | EID({self.entryID}) | ITab({self.activeInfoTab}) | LTab({self.activeLinkTab})"
        else:
            returnString += "? "
            if (self.entryType == "LoginPage"):
                returnString += "TMA Login Page"
                return returnString
            else:
                returnString += "External Site ("
                counter = 0
                maxChars = 30
                for i in str(self.rawURL):
                    counter += 1
                    if (counter > maxChars):
                        returnString += "...)"
                        return returnString
                    returnString += i
                returnString += ")"
        return returnString

# These classes serve as simple structs for representing singular object in TMA such as a people object, service object,
# or equipment object.
class TMAPeople:

    # Init method to initialize info for this People
    def __init__(self,locationData : TMALocation = None):
        self.location = locationData
        self.info_Client = None
        self.info_FirstName = None
        self.info_LastName = None
        self.info_Manager = None
        self.info_EmployeeID = None
        self.info_Email = None
        self.info_OpCo = None
        self.info_IsTerminated = False
        self.info_EmployeeTitle = None
        self.info_LinkedInteractions = []
        self.info_LinkedServices = []

    # A simple __str__ method for neatly displaying people objects.
    def __str__(self):
        returnString = ""

        returnString += ("Name: " + self.info_FirstName + " " + self.info_LastName + " (" + self.info_EmployeeID + ")\n")
        returnString += ("Title: " + self.info_EmployeeTitle + " (" + self.info_Client + ", " + self.info_OpCo + ")\n")
        returnString += ("Email: " + self.info_Email + "\n")
        if (self.info_IsTerminated):
            returnString += "Status: Terminated\n"
        else:
            returnString += "Status: Active\n"
        returnString += "LINKED INTERACTIONS:\n"
        for i in self.info_LinkedInteractions:
            returnString += ("-" + str(i) + "\n")
        returnString += "LINKED SERVICES:\n"
        for i in self.info_LinkedServices:
            returnString += ("-" + str(i) + "\n")

        return returnString
class TMAService:

    # Basic init method to initialize all instance variables.
    def __init__(self):
        self.info_Client = None

        self.info_ServiceNumber = None
        self.info_UserName = None
        self.info_Alias = None
        self.info_ContractStartDate = None
        self.info_ContractEndDate = None
        self.info_UpgradeEligibilityDate = None
        self.info_ServiceType = None
        self.info_Carrier = None

        self.info_InstalledDate = None
        self.info_DisconnectedDate = None
        self.info_IsInactiveService = False

        self.info_Assignment = None

        self.info_BaseCost = None
        self.info_FeatureCosts = []

        self.info_LinkedPersonName = None
        self.info_LinkedPersonNID = None
        self.info_LinkedPersonEmail = None
        self.info_LinkedInteractions = []
        self.info_LinkedOrders = []
        self.info_LinkedEquipment = None

    # __str__ method to print data contained in this object in a neat
    # and formatted way.
    def __str__(self):
        returnString = ""
        returnString += "===MAIN INFORMATION==="
        returnString += "\n\nService Number: " + str(self.info_ServiceNumber)
        returnString += "\nUser Name: " + str(self.info_UserName)
        returnString += "\nAlias: " + str(self.info_Alias)
        if (self.info_Client == "LYB"):
            returnString += "\nContract Start Date: " + str(self.info_ContractStartDate)
        elif (self.info_Client == "Sysco"):
            pass
        returnString += "\nContract End Date: " + str(self.info_ContractEndDate)
        returnString += "\nUpgrade Eligibility Date: " + str(self.info_UpgradeEligibilityDate)
        returnString += "\nService Type: " + str(self.info_ServiceType)
        returnString += "\nCarrier: " + str(self.info_Carrier)
        returnString += "\n\n===LINE INFO==="
        returnString += "\nInstalled Date: " + str(self.info_InstalledDate)
        returnString += "\nInactive: " + str(self.info_IsInactiveService)
        returnString += "\nDisconnect Date: " + str(self.info_DisconnectedDate)
        returnString += "\n\n===ASSIGNMENT INFO==="
        returnString += str(self.info_Assignment.__str__())
        returnString += "\n\n===COST INFO===\n"
        returnString += str(self.info_BaseCost.__str__())
        returnString += "\n------------------\n"
        for i in range(len(self.info_FeatureCosts)):
            returnString += str(self.info_FeatureCosts[i].__str__())
            returnString += "\n------------------\n"
        returnString += "\n\n==LINKS INFO==\n"
        returnString += "Linked User: " + str(self.info_LinkedPersonName)
        if (self.info_Client == "LYB"):
            returnString += "\n"
        elif (self.info_Client == "Sysco"):
            returnString += " (" + str(self.info_LinkedPersonNID) + ")\n"
        returnString += "Linked User's Email: " + str(self.info_LinkedPersonEmail)
        returnString += "\n"
        for i in range(len(self.info_LinkedInteractions)):
            returnString += "\nLinked Interaction: " + str(self.info_LinkedInteractions[i])
        returnString += "\n"
        for i in range(len(self.info_LinkedOrders)):
            returnString += "\nLinked Order: " + str(self.info_LinkedOrders[i])
        returnString += "\n" + str(self.info_LinkedEquipment.__str__())
        return returnString
class TMAOrder:

    # Basic init method to initialize all instance variables.
    def __init__(self):
        self.info_Client = None

        self.info_PortalOrderNumber = None
        self.info_VendorOrderNumber = None
        self.info_VendorTrackingNumber = None
        self.info_OrderStatus = None
        self.info_PlacedBy = None
        self.info_ContactName = None

        self.info_OrderClass = None
        self.info_OrderType = None
        self.info_OrderSubType = None
        self.info_SubmittedDate = None
        self.info_CompletedDate = None
        self.info_DueDate = None

        self.info_RecurringCost = None
        self.info_RecurringSavings = None
        self.info_Credits = None
        self.info_OneTimeCost = None
        self.info_RefundAmount = None

        self.info_OrderNotes = None
class TMACost:

    # Basic init method to initialize instance variables.
    def __init__(self, isBaseCost=True, featureName=None, gross=0, discountPercentage=0, discountFlat=0):
        if(type(isBaseCost) is bool):
            self.info_IsBaseCost = isBaseCost
        else:
            self.info_IsBaseCost = isBaseCost == "TRUE"
        self.info_FeatureString = featureName
        self.info_Gross = gross
        self.info_DiscountPercentage = discountPercentage
        self.info_DiscountFlat = discountFlat

    # Method to print the contents of the TMACost in a neat and formatted
    # way.
    def __str__(self):
        returnString = \
            "--Cost Object--" + \
            "\nBase Cost: " + str(self.info_IsBaseCost) + \
            "\nFeature: " + str(self.info_FeatureString) + \
            "\nGross Cost: " + str(self.info_Gross) + \
            "\nDiscount Percentage: " + str(self.info_DiscountPercentage) + \
            "\nFlat Discount: " + str(self.info_DiscountFlat) + \
            "\nNet Price: " + str(self.getNet())
        return returnString

    # Simply returns the net price of the TMACost by calculating it.
    def getNet(self):
        netPrice = self.info_Gross - self.info_DiscountFlat
        netPrice *= ((100 - self.info_DiscountPercentage) / 100)
        return netPrice
class TMAEquipment:

    # Simple constructor with option to specify linkedService, and to initialize instance variables.
    def __init__(self, linkedService=None,mainType=None, subType=None, make=None, model=None):
        self.info_MainType = mainType
        self.info_SubType = subType
        self.info_Make = make
        self.info_Model = model
        self.info_IMEI = None
        self.info_SIM = None
        self.info_LinkedService = linkedService

    # Method to print the information contained in this object in a
    # neat and formatted way.
    def __str__(self):
        returnString = "--Equipment--"
        returnString += "\nMain Type: " + str(self.info_MainType)
        returnString += "\nSub Type: " + str(self.info_SubType)
        returnString += "\nMake: " + str(self.info_Make)
        returnString += "\nModel: " + str(self.info_Model)
        returnString += "\nIMEI: " + str(self.info_IMEI)
        returnString += "\nSIM Card: " + str(self.info_SIM)

        return returnString
class TMAAssignment:
    # Initializing a TMAAssignment requires the client (LYB, Sysco, etc.) and vendor
    # (AT&T Mobility, Verizon Wireless, etc) to be specified.
    def __init__(self, client = None, vendor = None,siteCode = None,assignmentType = "Wireless"):
        self.info_Client = client
        self.info_Type = assignmentType
        self.info_Vendor = vendor


        self.info_Account = syscoData["Carriers"][self.info_Vendor]["Account Number"]

        self.info_SiteCode = siteCode
        self.info_Address = None

        # These values "don't matter" (at least not for our purposes) but are
        # still tracked.
        self.info_CompanyName = None
        self.info_Division = None
        self.info_Department = None
        self.info_CostCenter = None
        self.info_GLCode = None
        self.info_ProfitCenter = None
        self.info_BatchGroup = None

#endregion === TMA Data Structures ===

# How many TMA Location Datas will be stored at maximum, to conserve the TMA object from endlessly inflating.
#TODO doesn't actually work yet, i don't think
MAXIMUM_STORED_HISTORY = 20

class TMADriver():

    # To initialize our TMA driver class, we have to first attach an existing
    # Browser object.
    def __init__(self,browserObject: Browser):
        logMessage = "Initialized new TMADriver object"
        self.browser = browserObject

        if("TMA" in self.browser.tabs.keys()):
            self.browser.closeTab("TMA")
            logMessage += ", and closed existing TMA tab."
        else:
            logMessage += "."
        self.browser.openNewTab("TMA")

        self.locationHistory = []
        self.currentLocation = TMALocation()

        # Used to reliably work on the appropriate TMA page, popup or otherwise.
        self.currentTMATab = ["TMA",False]

        log.debug(logMessage)

    # region === General Site Navigation ===

    # This method simply logs in to TMA (with 5 attempts, to overcome potential glitch) from the TMA login screen.
    # If not at TMA login screen, it simply warns and does nothing.
    def logInToTMA(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        self.readPage()

        if (not self.currentLocation.isLoggedIn):
            self.browser.get("https://tma4.icomm.co/tma/NonAuthentic/Login.aspx")
            self.readPage()
            usernameField = self.browser.find_element(by=By.CSS_SELECTOR,value="#ctl00_ContentPlaceHolder1_Login1_UserName")
            passwordField = self.browser.find_element(by=By.CSS_SELECTOR,value="#ctl00_ContentPlaceHolder1_Login1_Password")
            usernameField.clear()
            passwordField.clear()
            usernameField.send_keys(mainConfig["authentication"]["tmaUser"])
            passwordField.send_keys(mainConfig["authentication"]["tmaPass"])

            loginButtonElement = self.browser.find_element(by=By.CSS_SELECTOR,value="#ctl00_ContentPlaceHolder1_Login1_LoginButton")
            self.browser.safeClick(element=loginButtonElement,timeout=10,
                                   successfulClickCondition=lambda b: b.searchForElement(element=loginButtonElement,timeout=5,invertedSearch=True))
            if (self.browser.current_url == "https://tma4.icomm.co/tma/Authenticated/Domain/Default.aspx"):
                self.readPage()
                if (self.currentLocation.isLoggedIn):
                    log.info("Successfully logged in to TMA.")
                    return True
        else:
            log.warning("Attempted to log in to TMA, but TMA is already logged in!")

    # These methods help streamline the process of switching to a new TMA popup tab when certain
    # TMA actions happen. SwitchToNewTab will try to locate a single new popupTMA tab, and switch
    # to it. ReturnToBaseTMA will close all TMA popup tabs, and switch back to the base TMA tab.
    def switchToNewTab(self,timeout=10):
        for i in range(timeout):
            popupDict = self.browser.checkForPopupTabs()

            newTMATabs = []
            for newPopupTab in popupDict["newPopupTabs"]:
                if(newPopupTab.startswith("tma4.icomm.co")):
                    newTMATabs.append(newPopupTab)

            # This means we haven't yet found any new TMA popup tabs.
            if(len(newTMATabs) == 0):
                time.sleep(1)
                continue
            # This means we've located our target TMA popup tab.
            elif(len(newTMATabs) == 1):
                self.browser.switchToTab(newTMATabs[0],popup=True)
                self.currentTMATab = [newTMATabs[0],True]
                log.info(f"Successfully switched to open TMA tab, with handle {newTMATabs[0]}")
                return True
            # This means we've found more than 1 new TMA popup tabs, which
            # shouldn't ever happen. We error out here.
            else:
                error = RuntimeError("Expected a single TMA popup to appear, but found multiple.")
                log.error(error)
                raise error
        # If we can't find the new popup after timeout times, we return
        # False.
        log.error("Could not find a new TMA popup tab to switch to.")
        return False
    def returnToBaseTMA(self):
        self.browser.checkForPopupTabs()
        for popupTabName in self.browser.popupTabs.keys():
            if(popupTabName.startswith("tma4.icomm.co")):
                self.browser.closeTab(popupTabName,popup=True)
        self.browser.switchToTab("TMA",popup=False)
        self.currentTMATab = ["TMA",False]
        log.info(f"Switched back to default TMA tab with handle {self.browser.tabs['TMA']}")

    # This method reads the current open page in TMA, and generates a new (or overrides a provided)
    # TMALocation to be returned for navigational use. Default behavior is to store this new location
    # data as the current location.
    def readPage(self,storeAsCurrent = True):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        locationData = TMALocation()

        locationData.rawURL = self.browser.current_url
        # Test if we're even on a TMA page.
        if ("tma4.icomm.co" in locationData.rawURL):
            # Test if we're logged in to TMA.
            if ("https://tma4.icomm.co/tma/Authenticated" in locationData.rawURL):
                locationData.isLoggedIn = True

                # ----------------------------------------------------------
                # Here we test what client we're on right now.
                # ----------------------------------------------------------
                clientNameHeaderPath = "//a[contains(@id,'lnkDomainHome')]/parent::div"
                headerText = self.browser.searchForElement(by=By.XPATH, value=clientNameHeaderPath,timeout=3).text
                clientName = headerText.split("-")[1].strip()
                if (clientName == ""):
                    locationData.client = None
                    locationData.entryType = "DomainPage"
                    #locationData.isInactive = None
                    locationData.entryID = None
                else:
                    locationData.client = clientName
                    # ----------------------------------------------------------
                    # Here we test for what entry type we're on right now, the
                    # associated "EntryID", and whether it is considered
                    # "inactive".
                    # ----------------------------------------------------------
                    if ("Client/People/" in locationData.rawURL):
                        locationData.entryType = "People"
                        # TODO implement dynamic support for other clients than just Sysco
                        # We pull the Sysco Network ID as our EntryID for People.
                        networkIDString = "//span[contains(@id,'lblEmployeeID')]/following-sibling::span"
                        networkID = self.browser.find_element(by=By.XPATH, value=networkIDString).text
                        locationData.entryID = networkID
                    elif ("Client/Services/" in locationData.rawURL):
                        locationData.entryType = "Service"
                        # We pull the service number as our EntryID for Service.
                        serviceNumberPath = "//input[contains(@id,'txtServiceId')]"
                        serviceNumber = self.browser.searchForElement(by=By.XPATH, value=serviceNumberPath,timeout=3).get_attribute("value")
                        locationData.entryID = convertServiceIDFormat(serviceID=serviceNumber,targetFormat="dashed")
                    elif ("Client/Interactions/" in locationData.rawURL):
                        locationData.entryType = "Interaction"
                        # Here, we pull the Interaction Number as our EntryID.
                        interactionNumberPath = "//span[contains(@id,'txtInteraction')]/following-sibling::span"
                        interactionNumberElement = self.browser.searchForElement(by=By.CSS_SELECTOR, value=interactionNumberPath,timeout=1)
                        if (interactionNumberElement):
                            interactionNumber = interactionNumberElement.text
                            locationData.entryID = interactionNumber
                        else:
                            locationData.entryID = "InteractionSearch"
                    elif ("Client/Orders/" in locationData.rawURL):
                        locationData.entryType = "Order"
                        # Orders are special in that their entryID should consist of three
                        # separate parts - the TMAOrderNumber, ticketOrderNumber, and
                        # vendorOrderNumber.
                        vendorOrderPath = "//span[text()='Vendor Order #:']/following-sibling::input"
                        vendorOrderNumber = self.browser.find_element(by=By.XPATH, value=vendorOrderPath).get_attribute("value")
                        vendorOrderNumber = None if vendorOrderNumber == "" else vendorOrderNumber

                        TMAOrderPath = "//span[text()='Order #:']/following-sibling::span"
                        TMAOrderNumber = self.browser.find_element(by=By.XPATH, value=TMAOrderPath).text
                        TMAOrderNumber = None if TMAOrderNumber == "" else TMAOrderNumber

                        ticketOrderPath = "//span[text()='Remedy Ticket']/following-sibling::input"
                        ticketOrderNumber = self.browser.find_element(by=By.XPATH, value=ticketOrderPath).get_attribute("value")
                        ticketOrderNumber = None if ticketOrderNumber == "" else ticketOrderNumber

                        locationData.entryID = {"TMAOrderNumber": TMAOrderNumber,
                                                "ticketOrderNumber": ticketOrderNumber,
                                                "vendorOrderNumber": vendorOrderNumber}
                    elif ("Client/Equipment/" in locationData.rawURL):
                        locationData.entryType = "Equipment"
                        locationData.entryID = "RegularEquipment"
                    elif ("Client/ClientHome" in locationData.rawURL):
                        locationData.entryType = "ClientHomePage"
                        locationData.entryID = None
                    # ----------------------------------------------------------
                    # ----------------------------------------------------------
                    # ----------------------------------------------------------
                # ----------------------------------------------------------
                # ----------------------------------------------------------
                # ----------------------------------------------------------
            # This means we're not logged in to TMA.
            else:
                locationData.isLoggedIn = False
                locationData.client = None
                locationData.entryType = "LoginPage"
                #locationData.isInactive = None
                locationData.entryID = None
        # This means we're not even on a TMA page.
        else:
            locationData.isLoggedIn = False
            locationData.client = None
            locationData.entryType = None
            #locationData.isInactive = None
            locationData.entryID = None

        if(storeAsCurrent):
            self.currentLocation = locationData

        log.debug(f"Read this page: ({locationData})")
        return locationData
    # This method simply waits (until timeout time has passed) for the page with the given navigation
    # data to load. FuzzyPageDetection means that this method will ignore info and link tabs.
    def waitForLocationLoad(self,location : TMALocation, timeout=120, fuzzyPageDetection=False):
        endTime = time.time() + timeout
        while time.time() < endTime:
            try:
                newLocationData = self.readPage(storeAsCurrent=False)
                if(newLocationData == location and ((newLocationData.activeLinkTab == location.activeLinkTab and newLocationData.activeInfoTab == location.activeInfoTab) or fuzzyPageDetection)):
                    return True
                else:
                    time.sleep(0.5)
            # A bit gluey or nah?
            except Exception as e:
                if(time.time() >= endTime):
                    raise e
                else:
                    time.sleep(0.5)
                    continue
        error = ValueError(f"waitForLocationLoad never loaded the targeted page:\n{location}")
        log.error(error)
        raise error
    # This method waits until the TMA loader element in invisible - in other words, it waits until TMA considers the
    # page to be "finished loading". DOESN'T WORK on popup TMA tabs (couldn't find any loader-type elements)
    def waitForTMALoader(self,timeout=120):
        startTime = time.time()
        loaderXPath = "//div[@id='ctl00_updateMainPage'][@aria-hidden='false']"
        loaderElement = self.browser.searchForElement(by=By.XPATH,value=loaderXPath,timeout=1.5)
        loaderSuccessfullyFound = False
        if(loaderElement):
            self.browser.searchForElement(by=By.XPATH,value=loaderXPath,timeout=timeout,invertedSearch=True,raiseError=True)
            loaderSuccessfullyFound = True

        logMessage = f"Waited on TMA loader for {time.time() - startTime} seconds"
        if(not loaderSuccessfullyFound):
            logMessage += f", failed to find loader to exist for longer than a second"
        log.debug(logMessage)

    # This method simply navigates to a specific client's home page, from the Domain. If not on DomainPage,
    # it simply warns and does nothing.
    def navToClientHome(self,clientName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(not self.currentLocation.isLoggedIn):
            log.error(f"Could not navToClientHome '{clientName}', as TMA is not currently logged in.")
            return False

        targetClientHomeLink = self.browser.find_element(by=By.XPATH,value=f"//a[text()='{clientName}']")
        clientHomeURL = targetClientHomeLink.get_attribute("href")

        self.browser.get(clientHomeURL)

        # Tries to verify that the clientHomepage has been reached 5 times.
        targetLocation = TMALocation(client=clientName,entryType="ClientHomePage")
        self.waitForLocationLoad(location=targetLocation)
        self.waitForTMALoader()
    # This method return TMA to the homepage from wherever it currently is, as long as TMA is logged in.
    def navToDomain(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.readPage()
        # TODO is shit like this really helpful?
        if(not self.currentLocation.isLoggedIn):
            log.error("Could not execute navToDomain, as TMA is not currently logged in!")
            return False

        TMAHeader = self.browser.find_element(by=By.XPATH,value="//form[@name='aspnetForm']/div[@id='container-main']/div[@id='container-top']/div[@id='header-left']/a[@id='ctl00_lnkDomainHome'][contains(@href,'Default.aspx')]")
        TMAHeader.click()

        targetLocation = TMALocation(entryType="DomainPage")
        self.waitForLocationLoad(location=targetLocation)
        self.waitForTMALoader()
    # This method intelligently searches for and opens an entry as specified by a locationData. Method is able to be called from anywhere as long as TMA is
    # currently logged in, and locationData is valid.
    def navToLocation(self,locationData : TMALocation = None, timeout=60):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.readPage()
        if(not self.currentLocation.isLoggedIn):
            error = PermissionError(f"Can not navigate to location '{locationData}' - not currently logged in to TMA.")
            log.error(error)
            raise error

        # First, we need to make sure we're on the correct client.
        if(locationData.client != self.currentLocation.client):
            self.navToClientHome(locationData.client)

        selectionMenuString = "//div/div/div/div/div/div/select[starts-with(@id,'ctl00_LeftPanel')]/option"
        searchBarString = "//div/div/fieldset/input[@title='Press (ENTER) to submit. ']"
        inactiveCheckboxString = "//div/div/div/input[starts-with(@id,'ctl00_LeftPanel')][contains(@id,'chkClosed')][@type='checkbox']"

        if(locationData.entryType == "Interaction"):
            interactionsOption = self.browser.find_element(by=By.XPATH,value=f"{selectionMenuString}[@value='interactions']")
            interactionsOption.click()
            self.waitForTMALoader()
            searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
            searchBar.clear()
            searchBar.send_keys(str(locationData.entryID))
            self.waitForTMALoader()
            searchBar.send_keys(u'\ue007')
            resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[starts-with(text(),'" + locationData.entryID + " (')]"
            resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120,raiseError=True)
            resultItem.click()
        elif(locationData.entryType == "Service"):
            servicesOption = self.browser.find_element(by=By.XPATH,value=selectionMenuString + "[@value='services']")
            servicesOption.click()
            self.waitForTMALoader()

            # TODO right now, this ALWAYS sets inactive to false. Come back here if we need to actually
            # account for inactive users.
            inactiveCheckbox = self.browser.find_element(by=By.XPATH,value=inactiveCheckboxString)
            if (str(inactiveCheckbox.get_attribute("CHECKED")) == "true"):
                inactiveCheckbox.click()
                self.waitForTMALoader()
            elif (str(inactiveCheckbox.get_attribute("CHECKED")) == "None"):
                pass
            self.waitForTMALoader()
            searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
            searchBar.clear()
            searchBar.send_keys(str(locationData.entryID))
            self.waitForTMALoader()
            searchBar = self.browser.find_element(by=By.XPATH, value=searchBarString)
            searchBar.send_keys(u'\ue007')
            targetServiceIDField = f"//input[contains(@id,'txtServiceId')][@value='{convertServiceIDFormat(locationData.entryID,'dashed')}' or @value='{convertServiceIDFormat(locationData.entryID,'dotted')}' or @value='{convertServiceIDFormat(locationData.entryID,'raw')}']"
            resultString = f"//div[contains(@id,'UpdatePanelResults')]//tr[contains(@class,'sgvitems')]//a[starts-with(text(),'{convertServiceIDFormat(locationData.entryID,'dashed')}')]"
            resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120,raiseError=True)
            self.browser.safeClick(element=resultItem,timeout=120,retryClicks=True,testInterval=3,
                                   successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=targetServiceIDField,invertedSearch=True,timeout=5))
        elif(locationData.entryType == "People"):
            peopleOption = self.browser.find_element(by=By.XPATH,value=selectionMenuString + "[@value='people']")
            peopleOption.click()
            self.waitForTMALoader()
            #TODO right now, this ALWAYS sets inactive to false. Come back here if we need to actually
            # account for inactive users.
            inactiveCheckbox = self.browser.find_element(by=By.XPATH,value=inactiveCheckboxString)
            if (str(inactiveCheckbox.get_attribute("CHECKED")) == "true"):
                inactiveCheckbox.click()
                self.waitForTMALoader()
            elif (str(inactiveCheckbox.get_attribute("CHECKED")) == "None"):
                pass
            searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
            searchBar.clear()
            searchBar.send_keys(str(locationData.entryID))
            searchBar = self.browser.searchForElement(by=By.XPATH,value=searchBarString,testClickable=True,timeout=3)
            searchBar.send_keys(u'\ue007')
            self.waitForTMALoader()
            caseAdjustedPeopleID = locationData.entryID.lower()
            resultString = f"//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),': {caseAdjustedPeopleID} ')]"
            resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120)
            resultItem.click()
        elif(locationData.entryType == "Order"):
            ordersOption = self.browser.find_element(by=By.XPATH,value=selectionMenuString + "[@value='orders']")
            ordersOption.click()
            self.waitForTMALoader()
            searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
            searchBar.clear()
            # For orders, since there are 3 potential numbers to search by, we prioritize them in this order: TMA Order Number, Vendor Order Number, Ticket Order Number.
            if(locationData.entryID["TMAOrderNumber"] is None):
                if (locationData.entryID["vendorOrderNumber"] is None):
                    if(locationData.entryID["ticketOrderNumber"] is None):
                        error = ValueError(f"Tried navigating to order '{locationData}', but all 3 order specifiers are None.")
                        log.error(error)
                        raise error
                    else:
                        orderNumber = locationData.entryID["ticketOrderNumber"]
                        orderNumber = orderNumber.lower()
                        resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'/ " + orderNumber + " (')]"
                else:
                    orderNumber = locationData.entryID["vendorOrderNumber"]
                    orderNumber = orderNumber.lower()
                    resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),': " + orderNumber + " ')]"
            else:
                orderNumber = locationData.entryID["TMAOrderNumber"]
                orderNumber = orderNumber.lower()
                resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[starts-with(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'" + orderNumber + ": ')]"
            searchBar.send_keys(str(orderNumber))
            self.waitForTMALoader()
            searchBar.send_keys(u'\ue007')
            resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120)
            resultItem.click()
            self.waitForTMALoader()
        else:
            error = ValueError(f"Can not search for entryType: {locationData.entryType}")
            log.error(error)
            raise error

        self.waitForLocationLoad(location=locationData,fuzzyPageDetection=True)
        self.waitForTMALoader()
        self.readPage(storeAsCurrent=True)
        log.info(f"Successfully navigated to location '{self.currentLocation}'")
        return True

    # endregion === General Site Navigation ===

    # region === Service Data & Navigation ===

    # All these methods assume that TMA is currently on a Service entry.

    # Reads main information from the "Line Info" service tab of a Service Entry in
    # TMA. If a Service object is supplied, it reads the info into this object - otherwise
    # it returns a new Service object.
    def Service_ReadMainInfo(self, serviceObject : TMAService = None, client = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            serviceObject = TMAService()
        xpathPrefix = "//div/fieldset/ol/li"
        self.Service_NavToServiceTab("Line Info")

        # Handle getting the client
        if(client is None):
            if(serviceObject.info_Client is None):
                log.warning(f"Main info of service is trying to be read without specifying a client in the serivce OR the funciton call. Defaulting to Sysco.")
                client = "Sysco"
            else:
                client = serviceObject.info_Client
        else:
            if(serviceObject.info_Client is None):
                serviceObject.info_Client = client

        if (client == "LYB"):
            serviceObject.info_ServiceNumber = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtServiceId')][contains(@id,'Detail_txtServiceId')]").get_attribute(
                "value")
            serviceObject.info_UserName = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtUserName')][contains(@id,'Detail_txtUserName')]").get_attribute(
                "value")
            serviceObject.info_Alias = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtDescription1')][contains(@id,'Detail_txtDescription1')]").get_attribute(
                "value")
            serviceObject.info_ContractStartDate = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$ICOMMTextbox1')][contains(@id,'Detail_ICOMMTextbox1')]").get_attribute(
                "value")
            serviceObject.info_ContractEndDate = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtDescription3')][contains(@id,'Detail_txtDescription3')]").get_attribute(
                "value")
            serviceObject.info_UpgradeEligibilityDate = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtContractEligibilityDate')][contains(@id,'Detail_txtContractEligibilityDate')]").get_attribute(
                "value")
            serviceObject.info_ServiceType = Select(self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/select[contains(@name,'Detail$ddlServiceType$ddlServiceType_ddl')][contains(@id,'Detail_ddlServiceType_ddlServiceType_ddl')]")).first_selected_option.text
            serviceObject.info_Carrier = Select(self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/select[contains(@name,'Detail$ddlCarrier$ddlCarrier_ddl')][contains(@id,'Detail_ddlCarrier_ddlCarrier_ddl')]")).first_selected_option.text
        elif (client == "Sysco"):
            serviceObject.info_ServiceNumber = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtServiceId')][contains(@id,'Detail_txtServiceId')]").get_attribute(
                "value")
            serviceObject.info_UserName = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtUserName')][contains(@id,'Detail_txtUserName')]").get_attribute(
                "value")
            serviceObject.info_Alias = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtDescription1')][contains(@id,'Detail_txtDescription1')]").get_attribute(
                "value")
            serviceObject.info_ContractStartDate = None
            serviceObject.info_ContractEndDate = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtDescription5')][contains(@id,'Detail_txtDescription5')]").get_attribute(
                "value")
            serviceObject.info_UpgradeEligibilityDate = self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/input[contains(@name,'Detail$txtContractEligibilityDate')][contains(@id,'Detail_txtContractEligibilityDate')]").get_attribute(
                "value")
            serviceObject.info_ServiceType = Select(self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/select[contains(@name,'Detail$ddlServiceType$ddlServiceType_ddl')][contains(@id,'Detail_ddlServiceType_ddlServiceType_ddl')]")).first_selected_option.text
            serviceObject.info_Carrier = Select(self.browser.find_element(by=By.XPATH, value=
            xpathPrefix + "/select[contains(@name,'Detail$ddlCarrier$ddlCarrier_ddl')][contains(@id,'Detail_ddlCarrier_ddlCarrier_ddl')]")).first_selected_option.text

        log.debug(f"Successfully read main info for service {serviceObject.info_ServiceNumber}")
        return serviceObject
    # LINE INFO : Reads "Line Info" (install and disco date, inactive checkbox) for this service entry.
    def Service_ReadLineInfoInfo(self, serviceObject : TMAService = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("line info")
        if(serviceObject is None):
            serviceObject = TMAService()

        prefix = "//div/div/ol/li"
        serviceObject.info_InstalledDate = self.browser.find_element(by=By.XPATH, value=
        prefix + "/input[contains(@name,'Detail$txtDateInstalled')][contains(@id,'Detail_txtDateInstalled')]").get_attribute(
            "value")
        serviceObject.info_DisconnectedDate = self.browser.find_element(by=By.XPATH, value=
        prefix + "/input[contains(@name,'Detail$txtDateDisco')][contains(@id,'Detail_txtDateDisco')]").get_attribute(
            "value")
        serviceObject.info_IsInactiveService = self.browser.find_element(by=By.XPATH, value=
        prefix + "/input[contains(@name,'Detail$chkInactive$ctl01')][contains(@id,'Detail_chkInactive_ctl01')]").is_selected()

        log.debug(f"Successfully read line info for service {serviceObject.info_ServiceNumber}")
        return serviceObject
    # COST ENTRIES : Read methods pertaining to cost entries associated with this service.
    def Service_ReadBaseCost(self, serviceObject : TMAService = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("base costs")
        if(serviceObject is None):
            serviceObject = TMAService()
        # We always overwrite the existing info_BaseCost if there was one.
        serviceObject.info_BaseCost = TMACost(isBaseCost=True)
        baseCostRowXPath = "//table[contains(@id,'Detail_sfBaseCosts_sgvFeatures')]/tbody/tr[contains(@class,'sgvitems')]"
        baseCostRow = self.browser.searchForElement(by=By.XPATH,value=baseCostRowXPath,timeout=1)
        if(baseCostRow):
            allDataEntries = baseCostRow.find_elements(by=By.TAG_NAME,value="td")
            serviceObject.info_BaseCost.info_FeatureString = allDataEntries[0].text
            serviceObject.info_BaseCost.info_Gross = allDataEntries[1].text
            serviceObject.info_BaseCost.info_DiscountPercentage = allDataEntries[2].text
            serviceObject.info_BaseCost.info_DiscountFlat = allDataEntries[3].text
        log.debug(f"Successfully read base cost for service {serviceObject.info_ServiceNumber}")
        return serviceObject
    def Service_ReadFeatureCosts(self, serviceObject : TMAService = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("features")
        if(serviceObject is None):
            serviceObject = TMAService()
        serviceObject.info_FeatureCosts = []

        featureCostRowsXPath = "//table[contains(@id,'Detail_sfStandardFeatures_sgvFeatures')]/tbody/tr[contains(@class,'sgvitems')]"
        featureCostRows = self.browser.find_elements(by=By.XPATH, value=featureCostRowsXPath)
        if(featureCostRows):
            for featureCostRow in featureCostRows:
                thisFeatureCostObject = TMACost(isBaseCost=False)
                allDataEntries = featureCostRow.find_elements(by=By.TAG_NAME, value="td")
                thisFeatureCostObject.info_FeatureString = allDataEntries[0].text
                thisFeatureCostObject.info_Gross = allDataEntries[1].text
                thisFeatureCostObject.info_DiscountPercentage = allDataEntries[2].text
                thisFeatureCostObject.info_DiscountFlat = allDataEntries[3].text
                serviceObject.info_FeatureCosts.append(thisFeatureCostObject)
        log.debug(f"Successfully read feature costs for service {serviceObject.info_ServiceNumber}")
        return serviceObject
    # LINKED ITEMS : Read methods pertaining to linked items to this service. Some methods are sensitive to
    # client, particularly linked people.
    def Service_ReadLinkedPerson(self, serviceObject : TMAService = None, client=None):
        if(client is None):
            if(serviceObject.info_Client is None):
                log.warning("No client specified in function call OR provided in serviceObject. Defaulting to sysco.")
                client = "Sysco"
            else:
                client = serviceObject.info_Client

        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("people")

        linkedPersonNameXPath = "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[5]"
        linkedPersonNameElement = self.browser.find_element(by=By.XPATH,value=linkedPersonNameXPath)
        linkedPersonName = linkedPersonNameElement.text
        if(client == "Sysco"):
            linkedPersonNetIDXPath = "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[7]"
            linkedPersonNetIDElement = self.browser.find_element(by=By.XPATH,value=linkedPersonNetIDXPath)
            linkedPersonNetID = linkedPersonNetIDElement.text
        linkedPersonEmailXPath = "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[11]"
        linkedPersonEmailElement = self.browser.find_element(by=By.XPATH, value=linkedPersonEmailXPath)
        linkedPersonEmail = linkedPersonEmailElement.text

        if(client == "Sysco"):
            # noinspection PyUnboundLocalVariable
            log.debug(f"Successfully read linked person: {linkedPersonName} | {linkedPersonNetID} | {linkedPersonEmail}")
        if(serviceObject is None):
            if(client == "Sysco"):
                return {"Name" : linkedPersonName, "NetID" : linkedPersonNetID, "Email" : linkedPersonEmail}
        else:
            serviceObject.info_LinkedPersonName = linkedPersonName
            if(client == "Sysco"):
                serviceObject.info_LinkedPersonNID = linkedPersonNetID
            serviceObject.info_LinkedPersonEmail = linkedPersonEmail
            return serviceObject
    def Service_ReadLinkedInteractions(self, serviceObject : TMAService = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("interactions")

        pageCountTextXPath = "//table/tbody/tr/td/span[contains(@id,'Detail_ucassociations_link_lblPages')]"
        pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
        pageCountMatch = re.search(r'of (\d+)', pageCountText)
        pageCount = int(pageCountMatch.group(1))

        linkedElementsXPath = "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[4]"
        nextButtonXPath = "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$ucassociations_link$btnNext')][contains(@id,'Detail_ucassociations_link_btnNext')]"


        arrayOfLinkedIntNumbers = []
        for i in range(pageCount):
            arrayOfLinkedInteractionsOnPage = self.browser.find_elements(by=By.XPATH, value=linkedElementsXPath)
            arrayOfLinkedIntNumbersOnPage = []
            for j in arrayOfLinkedInteractionsOnPage:
                arrayOfLinkedIntNumbersOnPage.append(j.text)
            for j in arrayOfLinkedIntNumbersOnPage:
                if (j in arrayOfLinkedIntNumbers):
                    continue
                arrayOfLinkedIntNumbers.append(j)

            if ((i + 1) < pageCount):
                nextButton = self.browser.find_element(by=By.XPATH, value=nextButtonXPath)

                while True:
                    self.browser.safeClick(element=nextButton)
                    self.waitForTMALoader()
                    pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
                    pageCountMatch = re.search(r'Page (\d+)', pageCountText)
                    currentPageNumber = int(pageCountMatch.group(1))

                    if (currentPageNumber == i + 2):
                        break
                    self.waitForTMALoader()
                    continue
                continue

        log.info(f"Successfully read: {arrayOfLinkedIntNumbers}")
        if(serviceObject is None):
            return arrayOfLinkedIntNumbers
        else:
            serviceObject.info_LinkedInteractions = arrayOfLinkedIntNumbers
            return serviceObject
    def Service_ReadLinkedOrders(self, serviceObject : TMAService = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("orders")

        pageCountTextXPath = "//table/tbody/tr/td/span[contains(@id,'Detail_ucassociations_link_lblPages')]"
        pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
        pageCountMatch = re.search(r'of (\d+)', pageCountText)
        pageCount = int(pageCountMatch.group(1))

        linkedOrdersXPath = "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[6]"
        nextButtonXPath = "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$ucassociations_link$btnNext')][contains(@id,'Detail_ucassociations_link_btnNext')]"

        arrayOfLinkedOrderNumbers = []
        for i in range(pageCount):
            arrayOfLinkedOrdersOnPage = self.browser.find_elements(by=By.XPATH, value=linkedOrdersXPath)
            arrayOfLinkedOrderNumbersOnPage = []
            for j in arrayOfLinkedOrdersOnPage:
                arrayOfLinkedOrderNumbersOnPage.append(j.text)
            for j in arrayOfLinkedOrderNumbersOnPage:
                if (j in arrayOfLinkedOrderNumbers):
                    continue
                arrayOfLinkedOrderNumbers.append(j)

            time.sleep(1)
            if ((i + 1) < pageCount):
                while True:
                    self.browser.safeClick(by=By.XPATH, value=nextButtonXPath)
                    self.waitForTMALoader()
                    pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
                    pageCountMatch = re.search(r'Page (\d+)', pageCountText)
                    currentPageNumber = int(pageCountMatch.group(1))

                    if (currentPageNumber == i + 2):
                        break
                    self.waitForTMALoader()
                    continue
                continue

        log.info(f"Successfully read: {arrayOfLinkedOrderNumbers}.")
        if(serviceObject is None):
            return arrayOfLinkedOrderNumbers
        else:
            serviceObject.info_LinkedOrders = arrayOfLinkedOrderNumbers
            return serviceObject
    def Service_ReadAllLinkedInformation(self, serviceObject : TMAService = None, client=None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            serviceObject = TMAService()
        self.Service_ReadLinkedPerson(serviceObject,client=client)
        self.Service_ReadLinkedInteractions(serviceObject)
        self.Service_ReadLinkedOrders(serviceObject)
        #TODO add support for linked equipment. Does readSimpleEquipmentInfo give enough?
        #self.Service_ReadLinkedEquipment(serviceObject)
        self.Service_ReadSimpleEquipmentInfo(serviceObject)

        log.debug(f"Successfully read linked info for service {serviceObject.info_ServiceNumber}")
        return True
    # EQUIPMENT : Reads basic information about any linked equipment. Does NOT open the equipment -
    # only reads what is visible from the linked equipment tab.
    def Service_ReadSimpleEquipmentInfo(self, serviceObject : TMAService = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            serviceObject = TMAService()
        serviceObject.info_LinkedEquipment = TMAEquipment()

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("equipment")

        linkedEquipmentsXPath = "//table/tbody/tr/td/table[contains(@id,'link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]"
        linkedEquipment = self.browser.find_element(by=By.XPATH,value=linkedEquipmentsXPath)
        equipmentData = linkedEquipment.find_elements(by=By.TAG_NAME,value="td")

        serviceObject.info_LinkedEquipment.info_Make = equipmentData[4]
        serviceObject.info_LinkedEquipment.info_Model = equipmentData[5]
        serviceObject.info_LinkedEquipment.info_MainType = equipmentData[6]
        serviceObject.info_LinkedEquipment.info_SubType = equipmentData[7]

        log.debug(f"Successfully read simple linked equipment info for service {serviceObject.info_ServiceNumber}")
        return serviceObject

    # Simple write methods for each of the elements existing in the "Main Info" category
    # (info that's displayed on the top part of the service entry) If a serviceObject is
    # given, it'll write from the given serviceObject. Otherwise, they take a raw value
    # as well.
    def Service_WriteServiceNumber(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ServiceNumber

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        serviceNumberInputXPath = "//div/fieldset/ol/li/input[contains(@name,'Detail$txtServiceId')][contains(@id,'Detail_txtServiceId')]"
        serviceNumberInput = self.browser.find_element(by=By.XPATH, value=serviceNumberInputXPath)
        serviceNumberInput.clear()
        serviceNumberInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteUserName(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_UserName

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        userNameInputXPath = "//div/fieldset/ol/li/input[contains(@name,'Detail$txtUserName')][contains(@id,'Detail_txtUserName')]"
        userNameInput = self.browser.find_element(by=By.XPATH, value=userNameInputXPath)
        userNameInput.clear()
        userNameInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteAlias(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_Alias

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        aliasInputXPath = "//div/fieldset/ol/li/input[contains(@name,'Detail$txtDescription1')][contains(@id,'Detail_txtDescription1')]"
        aliasInput = self.browser.find_element(by=By.XPATH, value=aliasInputXPath)
        aliasInput.clear()
        aliasInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteContractStartDate(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ContractStartDate

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        contractStartDateInputXPath = "//div/fieldset/ol/li/input[contains(@name,'Detail$ICOMMTextbox1')][contains(@id,'Detail_ICOMMTextbox1')]"
        contractStartDateInput = self.browser.find_element(by=By.XPATH, value=contractStartDateInputXPath)
        contractStartDateInput.clear()
        contractStartDateInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteContractEndDate(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ContractEndDate

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        contractEndDateInputXPath = "//div/fieldset/ol/li/input[contains(@name,'Detail$txtDescription5')][contains(@id,'Detail_txtDescription5')]"
        contractEndDateInput = self.browser.find_element(by=By.XPATH, value=contractEndDateInputXPath)
        contractEndDateInput.clear()
        contractEndDateInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteUpgradeEligibilityDate(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_UpgradeEligibilityDate

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        upgradeEligibilityDateInputXPath = "//div/fieldset/ol/li/input[contains(@name,'Detail$txtContractEligibilityDate')][contains(@id,'Detail_txtContractEligibilityDate')]"
        upgradeEligibilityDateInput = self.browser.find_element(by=By.XPATH, value=upgradeEligibilityDateInputXPath)
        upgradeEligibilityDateInput.clear()
        upgradeEligibilityDateInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteServiceType(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ServiceType

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        serviceTypeSelect = "//div/fieldset/ol/li/select[contains(@name,'Detail$ddlServiceType$ddlServiceType_ddl')][contains(@id,'Detail_ddlServiceType_ddlServiceType_ddl')]"
        targetValueXPath = f"{serviceTypeSelect}/option[text()='{valueToWrite}']"
        targetValueElement = self.browser.searchForElement(by=By.XPATH,value=targetValueXPath,timeout=1,raiseError=True)
        targetValueElement.click()
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteCarrier(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_Carrier

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        carrierSelect = "//div/fieldset/ol/li/select[contains(@name,'Detail$ddlCarrier$ddlCarrier_ddl')][contains(@id,'Detail_ddlCarrier_ddlCarrier_ddl')]"
        targetValueXPath = f"{carrierSelect}/option[text()='{valueToWrite}']"
        targetValueElement = self.browser.searchForElement(by=By.XPATH,value=targetValueXPath,timeout=1,raiseError=True)
        targetValueElement.click()
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteMainInformation(self, serviceObject : TMAService, client : str = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(client is None):
            if(serviceObject.info_Client is None):
                error = ValueError("Tried to writeMainInformation without specifying a client OR having info_Client in the serviceObject.")
                log.error(error)
                raise error
            else:
                client = serviceObject.info_Client

        self.Service_WriteServiceNumber(serviceObject)
        self.Service_WriteUserName(serviceObject)
        self.Service_WriteAlias(serviceObject)
        # List clients here that use contract start dates.
        if (client in ["LYB"]):
            self.Service_WriteContractStartDate(serviceObject)
        self.Service_WriteContractEndDate(serviceObject)
        self.Service_WriteUpgradeEligibilityDate(serviceObject)
        self.Service_WriteServiceType(serviceObject)
        self.Service_WriteCarrier(serviceObject)
        log.debug(f"Successfully wrote all main information.")
    # Write methods for each of the "Line Info" values. If a serviceObject is
    # given, it'll write from the given serviceObject. Otherwise, they take a raw value
    # as well.
    def Service_WriteInstalledDate(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_InstalledDate

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        installedDateInputXPath = "//div/div/ol/li/input[contains(@name,'Detail$txtDateInstalled')][contains(@id,'Detail_txtDateInstalled')]"
        installedDateInput = self.browser.find_element(by=By.XPATH, value=installedDateInputXPath)
        installedDateInput.clear()
        installedDateInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteDisconnectedDate(self, serviceObject : TMAService = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_DisconnectedDate

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        disconnectedDateInputXPath = "//div/div/ol/li/input[contains(@name,'Detail$txtDateDisco')][contains(@id,'Detail_txtDateDisco')]"
        disconnectedDateInput = self.browser.find_element(by=By.XPATH, value=disconnectedDateInputXPath)
        disconnectedDateInput.clear()
        disconnectedDateInput.send_keys(valueToWrite)
        log.debug(f"Successfully wrote: {valueToWrite}")
    def Service_WriteIsInactiveService(self, serviceObject : TMAService = None, rawValue : bool = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(rawValue is None):
            valueToWrite = serviceObject.info_IsInactiveService
        else:
            valueToWrite = rawValue

        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        inactiveServiceCheckboxXPath = "//div/div/ol/li/input[contains(@name,'Detail$chkInactive$ctl01')][contains(@id,'Detail_chkInactive_ctl01')]"
        self.browser.safeClick(by=By.XPATH,value=inactiveServiceCheckboxXPath,
                               retryClicks=True,clickDelay=3,timeout=30,
                               successfulClickCondition=lambda b: b.testForSelectedElement(by=By.XPATH,value=inactiveServiceCheckboxXPath))
        log.debug(f"Successfully {'checked isInactive' if valueToWrite else 'unchecked isInactive'}")
        return True
    # Method for writing/building base and feature costs onto a service entry. If a serviceObject
    # is given, it will prioritize building the cost objects associated with that serviceObject.
    # Otherwise, if a raw costObject is given, it'll simply build that cost object.
    def Service_WriteCosts(self, serviceObject : TMAService = None, costObjects : (TMACost, list) = None, isBase : bool = True):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(costObjects is None):
            if(serviceObject is None):
                error = ValueError("Can't write costs object without either specifying costObjects to write directly, or providing a serviceObjects with prespecified cost objects.")
                log.error(error)
                raise error

            if(isBase):
                costsToWrite = [serviceObject.info_BaseCost]
            else:
                costsToWrite = serviceObject.info_FeatureCosts
        else:
            if(type(costObjects) is list):
                costsToWrite = costObjects
            else:
                costsToWrite = [costObjects]

        if(isBase):
            self.Service_NavToServiceTab("base costs")
        else:
            self.Service_NavToServiceTab("features")

        XPathPrefix = '//div[@class="newitem"][contains(@id,"divFeature")]'
        createNewButtonXPath = '//a[contains(@id, "_lnkNewFeature")][text()="Create New"]'
        newItemTestForXPath = '//div[contains(@id,"divFeature")][@class="newitem"]'
        grossFormXPath = f'{XPathPrefix}/div/div/ol/li/input[contains(@name,"$txtCost_gross")][contains(@id,"_txtCost_gross")]'
        discountPercentFormXPath = f'{XPathPrefix}/div/div/ol/li/input[contains(@name,"$txtDiscount")][contains(@id,"_txtDiscount")]'
        discountFlatFormXPath = f'{XPathPrefix}/div/div/ol/li/input[contains(@name,"$txtDiscountFlat")][contains(@id,"_txtDiscountFlat")]'
        insertButtonXPath = f'{XPathPrefix}/span[contains(@id,"btnsSingle")]/div/input[contains(@name, "$btnsSingle$ctl01")][contains(@value, "Insert")]'

        for costToWrite in costsToWrite:
            createNewButtonElement = self.browser.find_element(by=By.XPATH,value=createNewButtonXPath)
            self.browser.safeClick(element=createNewButtonElement,jsClick=True)
            self.waitForTMALoader()
            self.browser.safeClick(by=By.XPATH,value=createNewButtonXPath,retryClicks=True,timeout=30,
                                   successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=newItemTestForXPath))
            featureSelectionXPath = f"{XPathPrefix}/div/div/select[contains(@name,'$ddlFeature$ddlFeature_ddl')]"
            featureSelectionDropdown = Select(self.browser.searchForElement(by=By.XPATH,value=featureSelectionXPath,timeout=30,
                                                                            minSearchTime=3,testClickable=True))
            featureSelectionDropdown.select_by_visible_text(costToWrite.info_FeatureString)

            if(costToWrite.info_Gross is not None):
                grossForm = self.browser.searchForElement(by=By.XPATH, value=grossFormXPath,testClickable=True,testLiteralClick=True,timeout=5)
                grossForm.send_keys(costToWrite.info_Gross)
            if(costToWrite.info_DiscountPercentage is not None):
                discountPercentForm = self.browser.searchForElement(by=By.XPATH, value=discountPercentFormXPath,testClickable=True,testLiteralClick=True,timeout=5)
                discountPercentForm.send_keys(costToWrite.info_DiscountPercentage)
            if(costToWrite.info_DiscountFlat is not None):
                discountFlatForm = self.browser.searchForElement(by=By.XPATH, value=discountFlatFormXPath,testClickable=True,testLiteralClick=True,timeout=5)
                discountFlatForm.send_keys(costToWrite.info_DiscountFlat)

            self.browser.safeClick(by=By.XPATH, value=insertButtonXPath,jsClick=True)

            # Wait until the new cost appears, just in case of TMAfuckery.
            finishedCostXPath = f"//table[contains(@id,'sgvFeatures')]/tbody/tr[contains(@class,'sgvitems')]/td[text()='{costToWrite.info_FeatureString}']"
            self.browser.searchForElement(by=By.XPATH,value=finishedCostXPath,timeout=30,raiseError=True)
            self.waitForTMALoader()

        # TODO add visualization of costs?
        log.debug(f"Successfully wrote costs.")

    # This method simply clicks the "update" button (twice) on the service.
    def Service_InsertUpdate(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        insertButtonXPath = "//span[@class='buttons']/div[@class='buttons']/input[contains(@name,'ButtonControl1$ctl')][@value='Insert']"
        updateButtonXPath = "//span[@class='buttons']/div[@class='buttons']/input[contains(@name,'ButtonControl1$ctl')][@value='Update']"
        if (self.browser.searchForElement(by=By.XPATH, value=updateButtonXPath,timeout=1)):
            self.browser.safeClick(by=By.XPATH,value=updateButtonXPath,clickDelay=1,timeout=5)
            log.debug("Updated service.")
            return True
        elif(self.browser.searchForElement(by=By.XPATH,value=insertButtonXPath,timeout=1)):
            self.browser.safeClick(by=By.XPATH,value=insertButtonXPath,clickDelay=1,timeout=5)
            # Tests for whether the service might already exist and handles it.
            # TODO come back here to determine how to actually intercept this.
            serviceAlreadyExistsString = "//span[text()='The Service already exists in the database.']"
            if (self.browser.searchForElement(by=By.XPATH, value=serviceAlreadyExistsString, timeout=2)):
                log.warning("Tried to insert service, but service already exists in database!")
                return "ServiceAlreadyExists"
            log.info("Inserted service.")
        else:
            log.warn("Neither insert nor update buttons exist on page when trying to InsertUpdate.")
            return False
    # This method simply clicks on "create new linked equipment" for the service entry we're on. Does nothing
    # with it, and WILL pop up a new window, so switchToNewTab will be required afterward.
    def Service_CreateLinkedEquipment(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("equipment")
        createNewEquipmentXPath = "//table/tbody/tr/td/div/table/tbody/tr/td/a[contains(@id,'link_lnkCreateNew')][text()='Create New Linked Item']"
        self.browser.safeClick(by=By.XPATH, value=createNewEquipmentXPath)
        log.debug("Successfully clicked 'create new linked item' for equipment.")

    # Method to navigate between all service tabs, and one for getting the current service tab.
    serviceTabDictionary = {"line info": "btnLineInfoExtended",
                            "assignments": "btnAssignments",
                            "used for": "btnUsedFor",
                            "base costs": "btnBaseCosts",
                            "features": "btnFeatures",
                            "fees": "btnFees",
                            "links": "btnLinks",
                            "history": "btnHistory"}
    def Service_NavToServiceTab(self, serviceTab):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTabXPath = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[contains(@name,'{self.serviceTabDictionary[serviceTab.lower()]}')][translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{serviceTab.lower()}']"
        serviceTabTestForXPath = f"{targetTabXPath}[@class='selected']"

        self.browser.safeClick(by=By.XPATH, value=targetTabXPath,retryClicks=True, clickDelay=3, timeout=60,
                                   successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=serviceTabTestForXPath))
        self.waitForTMALoader()
        log.debug(f"Successfully navigated to serviceTab '{serviceTab}'.")
        return True
    def Service_GetCurrentServiceTab(self):
        targetTab = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[@class='selected']"
        return self.browser.find_element(by=By.XPATH,value=targetTab).get_attribute("value")
    # Helper method to easily navigate to linked tabs.
    def Service_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTabXPath = f"//table[contains(@id,'Detail_ucassociations_link_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'{linkedTabName.lower()}')]"
        targetTabTestForXPath = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH, value=targetTabXPath, retryClicks=True,clickDelay=3,timeout=60,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=targetTabTestForXPath))
        self.waitForTMALoader()
        log.debug(f"Successfully navigated to linkedTab '{linkedTabName}'")
    # This method navigates TMA from a service to its linked equipment. Method
    # assumes that there is only one linked equipment.
    # TODO add support for multiple equipment (not that this should EVER happen in TMA)
    def Service_NavToEquipmentFromService(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("equipment")
        equipmentArray = self.browser.find_elements(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]")
        if (len(equipmentArray) == 0):
            error = RuntimeError("Could not navToEquipmentFromService, as there is no equipment presently linked.")
            log.error(error)
            raise error
        elif (len(equipmentArray) > 1):
            error = ValueError("Multiple equipments linked to service. This is not yet handled - will require some refactoring of code.")
            log.error(error)
            raise error
        else:
            equipmentIndex = 1
        equipmentDoorXPath = f"//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')][{equipmentIndex}]/td[2]"
        expectedURL = "https://tma4.icomm.co/tma/Authenticated/Client/Equipment"
        self.browser.safeClick(by=By.XPATH,value=equipmentDoorXPath,
                               retryClicks=True,clickDelay=5,timeout=30,prioritizeCondition=True,
                               successfulClickCondition=lambda b: b.waitForURL(urlSnippet=expectedURL,timeout=0,raiseError=False))
        self.waitForTMALoader()
    # This method assumes that TMA is currently in the process of creating a new service,
    # and asking for the Modal Service Type. This method simply attempts to select the given serviceType.
    def Service_SelectModalServiceType(self,serviceType):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        modalServiceTypeLinkXPath = f"//div/div/fieldset/a[contains(@id,'modalLinkButton')][text()='{serviceType}']"
        self.browser.safeClick(by=By.XPATH,value=modalServiceTypeLinkXPath,retryClicks=True,timeout=30,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=modalServiceTypeLinkXPath,timeout=1,invertedSearch=True))
        log.debug(f"Successfully selected service type '{serviceType}.")
        return True

    # endregion === Service Data & Navigation ===

    #region === Order Data & Navigation ===

    # All these methods assume that TMA is currently on an Order entry.


    # Read methods for each part of the Order entry.
    def Order_ReadMainInfo(self, orderObject : TMAOrder = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(orderObject is None):
            orderObject = TMAOrder()

        orderObject.info_PortalOrderNumber = self.browser.find_element(by=By.XPATH,value="//span[text()='Portal Order Number']/following-sibling::input").text
        orderObject.info_VendorOrderNumber = self.browser.find_element(by=By.XPATH,value="//span[text()='Vendor Order #:']/following-sibling::input").text
        orderObject.info_VendorTrackingNumber = self.browser.find_element(by=By.XPATH,value="//span[text()='Vendor Tracking #:']/following-sibling::input").text
        orderObject.info_OrderStatus = Select(self.browser.find_element(by=By.XPATH,value="//span[text()='Order Status:']/following-sibling::select")).first_selected_option.text
        orderObject.info_PlacedBy = Select(self.browser.find_element(by=By.XPATH,value="//span[text()='Placed By:']/following-sibling::select")).first_selected_option.text
        orderObject.info_ContactName = self.browser.find_element(by=By.XPATH,value="//span[text()='Contact Name:']/following-sibling::input").text

        orderObject.info_OrderClass = Select(self.browser.find_element(by=By.XPATH,value="//span[text()='Order Class:']/following-sibling::select")).first_selected_option.text
        orderObject.info_OrderType = Select(self.browser.find_element(by=By.XPATH,value="//span[text()='Order Type:']/following-sibling::select")).first_selected_option.text
        orderObject.info_OrderSubType = Select(self.browser.find_element(by=By.XPATH,value="//span[text()='Order Sub-Type:']/following-sibling::select")).first_selected_option.text
        orderObject.info_SubmittedDate = self.browser.find_element(by=By.XPATH,value="//span[text()='Submitted:']/following-sibling::input").text
        orderObject.info_CompletedDate = self.browser.find_element(by=By.XPATH,value="//span[text()='Completed:']/following-sibling::input").text
        orderObject.info_DueDate = self.browser.find_element(by=By.XPATH,value="//span[text()='Due:']/following-sibling::input").text

        orderObject.info_RecurringCost = self.browser.find_element(by=By.XPATH,value="//span[text()='Cost:']/following-sibling::input").text
        orderObject.info_RecurringSavings = self.browser.find_element(by=By.XPATH,value="//span[text()='Savings:']/following-sibling::input").text
        orderObject.info_Credits = self.browser.find_element(by=By.XPATH,value="//span[text()='Credits:']/following-sibling::input").text
        orderObject.info_OneTimeCost = self.browser.find_element(by=By.XPATH,value="//span[text()='One Time Cost:']/following-sibling::input").text
        orderObject.info_RefundAmount = self.browser.find_element(by=By.XPATH,value="//span[text()='Refund Amount:']/following-sibling::input").text

        return orderObject
    def Order_ReadOrderNotes(self, orderObject : TMAOrder = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(orderObject is None):
            orderObject = TMAOrder()

        self.Order_NavToOrderTab("notes")
        orderObject.info_OrderNotes = self.browser.find_element(by=By.XPATH,value="//textarea[contains(@id,'txtSummary')]").text
        return orderObject
    # TODO hehe this function doesn't actually work. Make it work.
    def Order_ReadLinkedService(self, orderObject : TMAOrder = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(orderObject is None):
            orderObject = TMAOrder()

        self.Order_NavToOrderTab("links")
        self.Order_NavToLinkedTab("services")

    # Write methods for each part of the Order entry.
    # Main Info
    def Order_WritePortalOrderNumber(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_PortalOrderNumber
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        portalOrderFieldXPath = "//span[text()='Portal Order Number']/following-sibling::input"
        portalOrderField = self.browser.find_element(by=By.XPATH,value=portalOrderFieldXPath)
        portalOrderField.clear()
        portalOrderField.send_keys(rawValue)
    def Order_WriteVendorOrderNumber(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_VendorOrderNumber
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        vendorOrderFieldXPath = "//span[text()='Vendor Order #:']/following-sibling::input"
        vendorOrderField = self.browser.find_element(by=By.XPATH,value=vendorOrderFieldXPath)
        vendorOrderField.clear()
        vendorOrderField.send_keys(rawValue)
    def Order_WriteVendorTrackingNumber(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_VendorTrackingNumber
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        vendorTrackingFieldXPath = "//span[text()='Vendor Tracking #:']/following-sibling::input"
        vendorTrackingField = self.browser.find_element(by=By.XPATH,value=vendorTrackingFieldXPath)
        vendorTrackingField.clear()
        vendorTrackingField.send_keys(rawValue)
    def Order_WriteContactName(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_ContactName
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        contactNameFieldXPath = "//span[text()='Contact Name:']/following-sibling::input"
        contactNameField = self.browser.find_element(by=By.XPATH,value=contactNameFieldXPath)
        contactNameField.clear()
        contactNameField.send_keys(rawValue)
    def Order_WriteSubmittedDate(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_SubmittedDate
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        submittedDateFieldXPath = "//span[text()='Submitted:']/following-sibling::input"
        submittedDateField = self.browser.find_element(by=By.XPATH,value=submittedDateFieldXPath)
        submittedDateField.clear()
        submittedDateField.send_keys(rawValue)
    def Order_WriteCompletedDate(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_CompletedDate
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        completedDateFieldXPath = "//span[text()='Completed:']/following-sibling::input"
        completedDateField = self.browser.find_element(by=By.XPATH,value=completedDateFieldXPath)
        completedDateField.clear()
        completedDateField.send_keys(rawValue)
    def Order_WriteDueDate(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_DueDate
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        dueDateFieldXPath = "//span[text()='Due:']/following-sibling::input"
        dueDateField = self.browser.find_element(by=By.XPATH,value=dueDateFieldXPath)
        dueDateField.clear()
        dueDateField.send_keys(rawValue)
    def Order_WriteRecurringCost(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RecurringCost
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        recurringCostFieldXPath = "//span[text()='Cost:']/following-sibling::input"
        recurringCostField = self.browser.find_element(by=By.XPATH,value=recurringCostFieldXPath)
        recurringCostField.clear()
        recurringCostField.send_keys(rawValue)
    def Order_WriteRecurringSavings(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RecurringSavings
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        recurringSavingsFieldXPath = "//span[text()='Savings:']/following-sibling::input"
        recurringSavingsField = self.browser.find_element(by=By.XPATH,value=recurringSavingsFieldXPath)
        recurringSavingsField.clear()
        recurringSavingsField.send_keys(rawValue)
    def Order_WriteCredits(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_Credits
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        creditsFieldXPath = "//span[text()='Credits:']/following-sibling::input"
        creditsField = self.browser.find_element(by=By.XPATH,value=creditsFieldXPath)
        creditsField.clear()
        creditsField.send_keys(rawValue)
    def Order_WriteOneTimeCost(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OneTimeCost
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        oneTimeCostFieldXPath = "//span[text()='One Time Cost:']/following-sibling::input"
        oneTimeCostField = self.browser.find_element(by=By.XPATH,value=oneTimeCostFieldXPath)
        oneTimeCostField.clear()
        oneTimeCostField.send_keys(rawValue)
    def Order_WriteRefundAmount(self, orderObject : TMAOrder = None, rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RefundAmount
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        refundAmountFieldXPath = "//span[text()='Refund Amount:']/following-sibling::input"
        refundAmountField = self.browser.find_element(by=By.XPATH,value=refundAmountFieldXPath)
        refundAmountField.clear()
        refundAmountField.send_keys(rawValue)
    def Order_WriteOrderStatus(self, orderObject: TMAOrder = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderStatus
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        orderStatusDropdownXPath = f"//span[text()='Order Status:']/following-sibling::select/option[text()='{valueToWrite}']"
        orderStatusDropdown = self.browser.find_element(by=By.XPATH,value=orderStatusDropdownXPath)
        orderStatusDropdown.click()
    def Order_WritePlacedBy(self, orderObject: TMAOrder = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_PlacedBy
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        placedByDropdownXPath = f"//span[text()='Placed By:']/following-sibling::select/option[text()='{valueToWrite}']"
        placedByDropdown = self.browser.find_element(by=By.XPATH,value=placedByDropdownXPath)
        placedByDropdown.click()
    def Order_WriteOrderClass(self, orderObject: TMAOrder = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderClass
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        orderClassDropdownXPath = f"//span[text()='Order Class:']/following-sibling::select/option[text()='{valueToWrite}']"
        orderClassDropdown = self.browser.find_element(by=By.XPATH,value=orderClassDropdownXPath)
        orderClassDropdown.click()
    def Order_WriteOrderType(self, orderObject: TMAOrder = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderType
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        orderTypeDropdownXPath = f"//span[text()='Order Type:']/following-sibling::select/option[text()='{valueToWrite}']"
        orderTypeDropdown = self.browser.find_element(by=By.XPATH,value=orderTypeDropdownXPath)
        orderTypeDropdown.click()
    def Order_WriteOrderSubType(self, orderObject: TMAOrder = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderSubType
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        orderSubTypeDropdownXPath = f"//span[text()='Order Sub-Type:']/following-sibling::select/option[text()='{valueToWrite}']"
        orderSubTypeDropdown = self.browser.find_element(by=By.XPATH,value=orderSubTypeDropdownXPath)
        orderSubTypeDropdown.click()
    # Other
    def Order_WriteOrderNotes(self, orderObject: TMAOrder = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RecurringCost
        if (valueToWrite is None):
            log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        self.Order_NavToOrderTab("notes")

        orderNotesFieldXPath = "//textarea[contains(@id,'txtSummary')]"
        orderNotesField = self.browser.find_element(by=By.XPATH, value=orderNotesFieldXPath)
        orderNotesField.clear()
        orderNotesField.send_keys(rawValue)
    # Method to click either insert or update, whichever is present.
    def Order_InsertUpdate(self):
        insertButtonString = "//input[@value='Insert']"
        insertButton = self.browser.searchForElement(by=By.XPATH,value=insertButtonString)
        if(insertButton):
            insertButton.click()
            return True

        updateButtonString = "//input[@value='Update']"
        updateButton = self.browser.searchForElement(by=By.XPATH,value=updateButtonString)
        if(updateButton):
            updateButton.click()
            return True

        return False

    # Method to navigate between all order tabs, and one for getting the current order tab.
    def Order_NavToOrderTab(self, orderTab):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTabXPath = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{orderTab.lower()}']"
        orderTabTestForXPath = f"{targetTabXPath}[contains(@class,'selected')]"
        self.browser.safeClick(by=By.XPATH,value=targetTabXPath,retryClicks=True,timeout=120,clickDelay=10,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=orderTabTestForXPath))
    def Order_GetCurrentOrderTab(self):
        targetTabXPath = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[contains(@class,'selected')]"
        return self.browser.find_element(by=By.XPATH,value=targetTabXPath).get_attribute("value")
    # Helper method to easily navigate to linked tabs.
    def Order_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTabXPath = f"//table[contains(@id,'Detail_ucassociations_link_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'{linkedTabName.lower()}')]"
        targetTabTestForXPath = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH,value=targetTabXPath,retryClicks=True,timeout=120,clickDelay=10,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=targetTabTestForXPath))
        log.debug(f"Successfully navigated to linkedTab '{linkedTabName}'")

    #endregion ====================Order Data & Navigation ===========================

    # region === People Data & Navigation ===

    # All these methods assume that TMA is currently on a People entry.

    # Reads basic information about a People entry in TMA. If a People object is supplied,
    # it reads the basic info into this object - otherwise, it returns a new People object.
    def People_ReadBasicInfo(self, peopleObject : TMAPeople = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = TMAPeople()
        peopleObject.location = self.currentLocation

        firstNameString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtFirstName__label')]/following-sibling::span"
        peopleObject.info_FirstName = self.browser.searchForElement(by=By.XPATH, value=firstNameString,timeout=10).text
        lastNameString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtLastName__label')]/following-sibling::span"
        peopleObject.info_LastName = self.browser.searchForElement(by=By.XPATH, value=lastNameString,timeout=10).text
        employeeIDString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_lblEmployeeID__label')]/following-sibling::span"
        peopleObject.info_EmployeeID = self.browser.searchForElement(by=By.XPATH, value=employeeIDString,timeout=10).text
        managerString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_ddlManager__label')]/following-sibling::span"
        peopleObject.info_Manager = self.browser.searchForElement(by=By.XPATH,value=managerString,timeout=10).text
        emailString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtEmail__label')]/following-sibling::span"
        peopleObject.info_Email = self.browser.searchForElement(by=By.XPATH, value=emailString,timeout=10).text
        employeeStatusString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_ddlpeopleStatus__label')]/following-sibling::span"
        employeeStatus = self.browser.searchForElement(by=By.XPATH, value=employeeStatusString,timeout=10).text
        if (employeeStatus == "Active"):
            peopleObject.info_IsTerminated = False
        else:
            peopleObject.info_IsTerminated = True
        OpCoString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_lblLocationCode1__label')]/following-sibling::span"
        peopleObject.info_OpCo = self.browser.searchForElement(by=By.XPATH, value=OpCoString,timeout=10).text
        employeeTitleString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtTitle__label')]/following-sibling::span"
        peopleObject.info_EmployeeTitle = self.browser.searchForElement(by=By.XPATH, value=employeeTitleString,timeout=10).text

        log.debug(f"Successfully read basic info for people object {peopleObject.info_FirstName} {peopleObject.info_LastName}")
        return peopleObject
    # Reads an array of linked interactions of a people Object. If a People object is supplied,
    # it reads the info into this object - otherwise, it returns a new People object.
    def People_ReadLinkedInteractions(self, peopleObject : TMAPeople = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = TMAPeople()
        self.People_NavToLinkedTab("interactions")

        pageCountTextXPath = "//table/tbody/tr/td/span[contains(@id,'Detail_associations_link1_lblPages')]"
        pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
        pageCountMatch = re.search(r'of (\d+)', pageCountText)
        pageCount = int(pageCountMatch.group(1))

        linkedInteractionsXPath = "//table[contains(@id,'associations_link1_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[4]"
        nextButtonXPath = "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$associations_link1$btnNext')][contains(@id,'Detail_associations_link1_btnNext')]"
        arrayOfLinkedIntNumbers = []
        for i in range(pageCount):
            arrayOfLinkedInteractionsOnPage = self.browser.find_elements(by=By.XPATH, value=linkedInteractionsXPath)
            arrayOfLinkedIntNumbersOnPage = []
            for j in arrayOfLinkedInteractionsOnPage:
                arrayOfLinkedIntNumbersOnPage.append(j.text)
            for j in arrayOfLinkedIntNumbersOnPage:
                if (j in arrayOfLinkedIntNumbers):
                    continue
                arrayOfLinkedIntNumbers.append(j)

            if ((i + 1) < pageCount):
                while True:
                    self.browser.safeClick(by=By.XPATH, value=nextButtonXPath,timeout=3)
                    self.waitForTMALoader()
                    pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
                    pageCountMatch = re.search(r'Page (\d+)', pageCountText)
                    currentPageNumber = int(pageCountMatch.group(1))

                    if (currentPageNumber == i + 2):
                        break
                    continue
                continue

        peopleObject.info_LinkedInteractions = arrayOfLinkedIntNumbers
        log.debug(f"Successfully read linked Ints for people object {peopleObject.info_FirstName} {peopleObject.info_LastName}: '{arrayOfLinkedIntNumbers}'")
        return peopleObject
    # Reads an array of linked services of a people Object. If a People object is supplied,
    # it reads the info into this object - otherwise, it returns a new People object.
    # Reads an array of linked service numbers into info_LinkedServices
    def People_ReadLinkedServices(self, peopleObject : TMAPeople = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = TMAPeople()
        self.People_NavToLinkedTab("services")

        pageCountTextXPath = "//table/tbody/tr/td/span[contains(@id,'Detail_associations_link1_lblPages')]"
        pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
        pageCountMatch = re.search(r'of (\d+)', pageCountText)
        pageCount = int(pageCountMatch.group(1))

        linkedServicesXPath = "//table[contains(@id,'associations_link1_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[5]"
        nextButtonXPath = "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$associations_link1$btnNext')][contains(@id,'Detail_associations_link1_btnNext')]"
        arrayOfLinkedServiceNumbers = []
        for i in range(pageCount):
            arrayOfLinkedServicesOnPage = self.browser.find_elements(by=By.XPATH, value=linkedServicesXPath)
            arrayOfLinkedServiceNumbersOnPage = []
            for j in arrayOfLinkedServicesOnPage:
                arrayOfLinkedServiceNumbersOnPage.append(j.text)
            for j in arrayOfLinkedServiceNumbersOnPage:
                if (j in arrayOfLinkedServiceNumbers):
                    continue
                arrayOfLinkedServiceNumbers.append(j)

            if ((i + 1) < pageCount):
                while True:
                    self.browser.safeClick(by=By.XPATH, value=nextButtonXPath)
                    self.waitForTMALoader()
                    pageCountText = self.browser.find_element(by=By.XPATH, value=pageCountTextXPath).text
                    pageCountMatch = re.search(r'Page (\d+)', pageCountText)
                    currentPageNumber = int(pageCountMatch.group(1))

                    if (currentPageNumber == i + 2):
                        break
                    continue
                continue

        peopleObject.info_LinkedServices = arrayOfLinkedServiceNumbers
        log.debug(f"Successfully read linked services for people object {peopleObject.info_FirstName} {peopleObject.info_LastName}: {arrayOfLinkedServiceNumbers}.")
        return peopleObject
    # Simply reads in all information about a single People Entry. If a People object is supplied,
    # it reads the info into this object - otherwise, it returns a new People object.
    def People_ReadAllInformation(self, peopleObject : TMAPeople = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = TMAPeople()

        self.People_ReadBasicInfo(peopleObject)
        self.People_ReadLinkedInteractions(peopleObject)
        self.People_ReadLinkedServices(peopleObject)

        log.debug(f"Successfully read all information for people object {peopleObject.info_FirstName} {peopleObject.info_LastName}.")
        return peopleObject

    # Helper method to easily navigate to a linked tab on this People object.
    def People_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTabXPath = f"//table[contains(@id,'Detail_associations_link1_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'{linkedTabName.lower()}')]"
        targetTabTestForXPath = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH,value=targetTabXPath,retryClicks=True,clickDelay=10,timeout=120,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=targetTabTestForXPath))
        log.debug(f"Successfully navigated to linkedTabName '{linkedTabName}'")
    # Assuming that TMA is currently on a "People" page, this function navigates to
    # the 'Services' linked tab, then simply clicks create new.
    def People_CreateNewLinkedService(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.People_NavToLinkedTab("services")
        createNewXPath = "//table/tbody/tr/td/div/table/tbody/tr/td/a[contains(@id,'link1_lnkCreateNew')][text()='Create New Linked Item']"
        self.browser.safeClick(by=By.XPATH, value=createNewXPath)
        log.debug("Successfully clicked on Create New Linked Service.")
    # This method opens up a service, given by a serviceID, turning the currently open tab
    # from a TMA people tab to a TMA service tab. Assumes we're currently on a people entry.
    # ExtraWaitTime is provided, because after a new service is created, TMA likes to be a little bitch
    # and take sometimes 15+seconds for it to appear.
    def People_OpenServiceFromPeople(self, serviceID,extraWaitTime=0):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.People_NavToLinkedTab("services")

        openServiceButtonXPath = f"//tbody/tr[contains(@class,'sgvitems')]/td[text()='{serviceID}']/parent::tr/td/a[contains(@id,'lnkDetail')]"
        nextPageButtonXPath = "//input[contains(@id,'btnNext')][contains(@id,'Detail')]"
        openServiceButton = None
        pagesChecked = 0
        # Try to find the created service, including support for flipping through pages (max 50)
        for i in range(50):
            pagesChecked += 1
            openServiceButton = self.browser.searchForElement(by=By.XPATH, value=openServiceButtonXPath,timeout=3+extraWaitTime)
            if(not openServiceButton):
                nextPageButton = self.browser.find_element(by=By.XPATH,value=nextPageButtonXPath)
                if(nextPageButton.get_attribute("disabled") != "true"):
                    nextPageButton.click()
                    self.waitForTMALoader()
                else:
                    break
            else:
                break

        if(openServiceButton):
            targetAddress = openServiceButton.get_attribute("href")
            self.browser.get(targetAddress)
            self.browser.waitForURL(urlSnippet="tma4.icomm.co/tma/Authenticated/Client/Services",timeout=60)
            self.waitForTMALoader()
            self.readPage()
            log.info(f"Successfully opened linked service '{serviceID}' from people entry.")
        else:
            error = RuntimeError(f"Couldn't locate linked service '{serviceID}' on current people object after {pagesChecked} pages.")
            log.error(error)
            raise error

    # endregion === People Data & Navigation ===

    # region === Equipment Data & Navigation ===

    # All these methods assume that TMA is currently on an Equipment entry.

    # Reads main information about an Equipment entry in TMA. If an Equipment object is supplied,
    # it reads the info into this object - otherwise, it returns a new Equipment object.
    def Equipment_ReadMainInfo(self, equipmentObject : TMAEquipment = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(equipmentObject is None):
            equipmentObject = TMAEquipment()
        xpathPrefix = "//div/fieldset/ol/li"

        equipmentObject.info_MainType = self.browser.find_element(by=By.XPATH, value=
        xpathPrefix + "/span[contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite__lblType')]/following-sibling::span").text

        subtypeDropdownXPath = f"{xpathPrefix}/select[contains(@name,'Detail$ddlEquipmentTypeComposite$ddlEquipmentTypeComposite_ddlSubType')][contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite_ddlSubType')]"
        equipmentObject.info_SubType = Select(self.browser.find_element(by=By.XPATH, value=subtypeDropdownXPath)).first_selected_option.text
        makeDropdownXPath = f"{xpathPrefix}/select[contains(@name,'Detail$ddlEquipmentTypeComposite$ddlEquipmentTypeComposite_ddlMake')][contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite_ddlMake')]"
        equipmentObject.info_Make = Select(self.browser.find_element(by=By.XPATH, value=makeDropdownXPath)).first_selected_option.text
        modelDropdownXPath = f"{xpathPrefix}/select[contains(@name,'Detail$ddlEquipmentTypeComposite$ddlEquipmentTypeComposite_ddlModel')][contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite_ddlModel')]"
        equipmentObject.info_Model = Select(self.browser.find_element(by=By.XPATH, value=modelDropdownXPath)).first_selected_option.text

        imeiFieldXPath = "//fieldset/fieldset/ol/li/input[contains(@name,'Detail$txtimei')][contains(@id,'Detail_txtimei')]"
        equipmentObject.info_IMEI = self.browser.find_element(by=By.XPATH, value=imeiFieldXPath).get_attribute("value")
        simFieldXPath = "//fieldset/fieldset/ol/li/input[contains(@name,'Detail$txtSIM')][contains(@id,'Detail_txtSIM')]"
        equipmentObject.info_SIM = self.browser.find_element(by=By.XPATH, value=simFieldXPath).get_attribute("value")

        log.debug("Successfully read equipment main info.")
        return equipmentObject

    # Write methods for various aspects of the equipment entry. If an Equipment object is supplied,
    # it pulls the info to write from this object. If not, it uses the "literalValue" object to write
    # instead.
    # TODO handle linked services better - no methods exist, just kinda assume its configured correctly in TMA
    def Equipment_WriteSubType(self, equipmentObject : TMAEquipment = None, literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (literalValue is None):
            if(equipmentObject.info_SubType is None):
                error = ValueError("Neither a literalValue nor a specified equipment value is specified, and one must exist to write.")
                log.error(error)
                raise error
            else:
                valToWrite = equipmentObject.info_SubType
        else:
            valToWrite = literalValue

        subTypeDropdownXPath = f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlSubType')][contains(@name,'$ddlEquipmentTypeComposite_ddlSubType')]/option[text()='{valToWrite}']"
        self.browser.safeClick(by=By.XPATH,value=subTypeDropdownXPath)
        log.debug(f"Successfully wrote '{valToWrite}'")
        return True
    def Equipment_WriteMake(self, equipmentObject : TMAEquipment = None, literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (literalValue is None):
            if(equipmentObject.info_Make is None):
                error = ValueError("Neither a literalValue nor a specified equipment value is specified, and one must exist to write.")
                log.error(error)
                raise error
            else:
                valToWrite = equipmentObject.info_Make
        else:
            valToWrite = literalValue

        makeDropdownXPath = f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlMake')][contains(@name,'$ddlEquipmentTypeComposite_ddlMake')]/option[text()='{valToWrite}']"
        self.browser.safeClick(by=By.XPATH, value=makeDropdownXPath,timeout=10)
        log.debug(f"Successfully wrote '{valToWrite}'")
        return True
    def Equipment_WriteModel(self, equipmentObject : TMAEquipment = None, literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (literalValue is None):
            if(equipmentObject.info_Model is None):
                error = ValueError("Neither a literalValue nor a specified equipment value is specified, and one must exist to write.")
                log.error(error)
                raise error
            else:
                valToWrite = equipmentObject.info_Model
        else:
            valToWrite = literalValue

        modelDropdownXPath = f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlModel')][contains(@name,'$ddlEquipmentTypeComposite_ddlModel')]/option[text()='{valToWrite}']"
        self.browser.safeClick(by=By.XPATH, value=modelDropdownXPath,timeout=10)
        log.debug(f"Successfully wrote '{valToWrite}'")
        return True
    def Equipment_WriteIMEI(self, equipmentObject : TMAEquipment = None, literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (literalValue is None):
            if(equipmentObject.info_IMEI is None):
                error = ValueError("Neither a literalValue nor a specified equipment value is specified, and one must exist to write.")
                log.error(error)
                raise error
            else:
                valToWrite = equipmentObject.info_IMEI
        else:
            valToWrite = literalValue

        def writeIMEI():
            IMEIXPath = "//div/fieldset/div/fieldset/fieldset/ol/li/input[contains(@id,'txtimei')]"
            IMEIElement = self.browser.searchForElement(by=By.XPATH, value=IMEIXPath,testClickable=True,timeout=10)
            IMEIElement.clear()
            IMEIElement.send_keys(valToWrite)
            log.debug(f"Successfully wrote '{valToWrite}'")
            return True

        # For some reason, this function was quite unstable. Added a special check to resolve this rare error.
        try:
            return writeIMEI()
        except selenium.common.exceptions.StaleElementReferenceException as e:
            time.sleep(5)
            return writeIMEI()
    def Equipment_WriteSIM(self, equipmentObject : TMAEquipment = None, literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (literalValue is None):
            if(equipmentObject.info_SIM is None):
                error = ValueError("Neither a literalValue nor a specified equipment value is specified, and one must exist to write.")
                log.error(error)
                raise error
            else:
                valToWrite = equipmentObject.info_SIM
        else:
            valToWrite = literalValue

        SIMXPath = "//div/fieldset/div/fieldset/fieldset/ol/li/input[contains(@id,'Detail_Equipment_txtSIM')]"
        SIMElement = self.browser.find_element(by=By.XPATH, value=SIMXPath)
        SIMElement.clear()
        SIMElement.send_keys(valToWrite)
        log.debug(f"Successfully wrote '{literalValue}'")
        return True
    # Helper method to write ALL possible writeable info for this Equipment entry. Must specify
    # an Equipment object to pull information from - if any info is None, it will error out.
    def Equipment_WriteAll(self, equipmentObject : TMAEquipment,writeIMEI=True,writeSIM=True):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        errorMessage = "Can't writeAll from given equipment object, as it is missing "
        if(equipmentObject.info_SubType is None):
            errorMessage += "a subtype."
            error = ValueError(errorMessage)
            log.error(error)
            raise error
        if(equipmentObject.info_Make is None):
            errorMessage += "a make."
            error = ValueError(errorMessage)
            log.error(error)
            raise error
        if(equipmentObject.info_Model is None):
            errorMessage += "a model."
            error = ValueError(errorMessage)
            log.error(error)
            raise error

        self.Equipment_WriteSubType(equipmentObject)
        self.Equipment_WriteMake(equipmentObject)
        self.Equipment_WriteModel(equipmentObject)
        if(writeSIM):
            self.Equipment_WriteSIM(equipmentObject)
        if(writeIMEI):
            self.Equipment_WriteIMEI(equipmentObject)
    # Simply clicks on either "insert" or "update" on this equipment.
    def Equipment_InsertUpdate(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        insertButtonXPath = "//span/div/input[contains(@name,'ButtonControl1')][@value = 'Insert']"
        updateButtonXPath = "//span/div/input[contains(@name,'ButtonControl1')][@value = 'Update']"
        if(self.browser.searchForElement(by=By.XPATH,value=insertButtonXPath,timeout=1)):
            self.browser.safeClick(by=By.XPATH,value=insertButtonXPath,timeout=5)
            self.waitForTMALoader()
            self.browser.safeClick(by=By.XPATH,value=updateButtonXPath,timeout=5)
            log.info("Successfully inserted equipment.")
        elif(self.browser.searchForElement(by=By.XPATH,value=updateButtonXPath,timeout=1)):
            self.browser.safeClick(by=By.XPATH,value=updateButtonXPath,minClicks=1,timeout=5)
            log.debug("Successfully updated equipment.")
        else:
            error = RuntimeError("Couldn't InsertUpdate, as neither Insert nor Update were found.")
            log.error(error)
            raise error

    # Helper method to easily navigate to a linked tab on this Equipment object.
    def Equipment_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTabXPath = f"//table[contains(@id,'Detail_associations_link1_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[starts-with(text(),'{linkedTabName.lower()}')]"
        targetTabTestForXPath = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH,value=targetTabXPath,retryClicks=True,timeout=60,clickDelay=3,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=targetTabTestForXPath))
        log.debug(f"Successfully navigated to linkedTab '{linkedTabName}'")
    # This method navigates TMA from an equipment entry to a linked service.
    # Method assumes that Equipment is currently on the "Links" tab, and that
    # there is only one linked service.
    def Equipment_NavToServiceFromEquipment(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Equipment_NavToLinkedTab("Services")

        linkedServiceXPath = "//table[contains(@id,'associations_link1_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[2]"
        self.browser.safeClick(by=By.XPATH,value=linkedServiceXPath,retryClicks=True,timeout=60,clickDelay=8,prioritizeCondition=True,
                               successfulClickCondition=lambda b: b.waitForURL(urlSnippet="https://tma4.icomm.co/tma/Authenticated/Client/Services",timeout=1))
        log.debug("Successfully navigated to service from equipment entry.")
        return True
    # This method checks whether we're on the "Equipment Type" selection screen, and if so,
    # selects the given equipment type. If we're not on that screen, this function merely
    # returns false.
    def Equipment_SelectEquipmentType(self,equipmentType):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        equipmentTypeXPath = f"//body/form/div/div/fieldset/a[contains(@id,'ctl00_modalLinkButton')][text()='{equipmentType}']"
        self.browser.safeClick(by=By.XPATH,value=equipmentTypeXPath,retryClicks=True,timeout=30,clickDelay=5,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=equipmentTypeXPath,invertedSearch=True))
        log.debug(f"Successfully selected equipmentType '{equipmentType}'")

    # endregion === Equipment Data & Navigation ===

    # region === Assignment Navigation ===

    # All these methods assume that TMA is currently on the assignment wizard.
    # TODO add supported reading of assignment info into assignment objects.

    # The "Sysco Method" of creating assignments - looks up the Account/Vendor first, then specifies
    # the site from a list of available sites. If an AssignmentObject is provided, this method will
    # try to build an exact copy of it (and will ignore client,vendor, and siteCode variables)
    # TODO The above comment is a lie. This does not YET support AssignmentObjects - only literals.
    def Assignment_BuildAssignmentFromAccount(self,client,vendor,siteCode):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        # This helper function will help us quickly get the current and total pages number of whatever tab we're on
        # in the assignment wizard.
        pageCountTextXPath = "//span[contains(@id,'wizFindExistingAssigment')][contains(@id,'lblPages')]"
        def getPageNumbers():
            pageCountText = self.browser.searchForElement(by=By.XPATH, value=pageCountTextXPath,timeout=10,raiseError=True).text
            pageCountMatch = re.search(r'Page (\d+) of (\d+)', pageCountText)
            currentPage = int(pageCountMatch.group(1))  # First number (current page)
            totalPages = int(pageCountMatch.group(2))  # Second number (total pages)
            return currentPage,totalPages
        # This template can be used to test for a specific sideTab in the Account Wizard to see if it's the "active" tab.
        sideTabXPathTemplate = "//a[contains(@id,'SideBarButton')][translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{tabName}']/parent::div"
        # Meanwhile, this simpler XPath can be used to simply get the active sideTab, whatever that is.
        currentSideTabXPath = "//div/a[contains(@id,'SideBarButton')]"

        siteCode = str(siteCode).zfill(3)
        log.debug(f"Attempting to build assignment off of this site code: {siteCode}")


        # First, we click on the "accounts" button until we detect that we're on the accounts sideTab.
        existingAccountsButtonXPath = "//td/div/div/a[contains(@id,'wizFindExistingAssigment_lnkFindAccount')]"
        self.browser.safeClick(by=By.XPATH,value=existingAccountsButtonXPath,retryClicks=True,timeout=60,clickDelay=2,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="accounts")))

        #region === Accounts Sidetab ===
        # Now, we should be on the "Accounts" sideTab
        # Always select "Wireless" as assignment type (for now)
        wirelessTypeDropdownSelectionXPath = "//tr/td/div/fieldset/ol/li/select[contains(@id,'wizFindExistingAssigment_ddlAccountType')]/option[text()='Wireless']"
        wirelessTypeDropdownSelection = self.browser.find_element(by=By.XPATH, value=wirelessTypeDropdownSelectionXPath)
        self.browser.safeClick(element=wirelessTypeDropdownSelection)
        # Select the vendor from the dropdown.
        vendorDropdownSelectionXPath = f"//tr/td/div/fieldset/ol/li/select[contains(@id,'wizFindExistingAssigment_ddlVendor')]/option[text()='{vendor}']"
        vendorDropdownSelection = self.browser.searchForElement(by=By.XPATH,value=vendorDropdownSelectionXPath)
        if(not vendorDropdownSelection):
            log.error(f"Incorrect vendor selected to make assignment: {vendor}")
        self.browser.safeClick(element=vendorDropdownSelection)
        # Now select the appropriate account as found based on the vendor.
        accountNumber = syscoData["Carriers"][vendor]["Account Number"]
        accountNumberDropdownSelectionXPath = f"//tr/td/div/fieldset/ol/li/select[contains(@id,'wizFindExistingAssigment_ddlAccount')]/option[text()='{accountNumber}']"
        accountNumberDropdownSelection = self.browser.searchForElement(by=By.XPATH,value=accountNumberDropdownSelectionXPath,timeout=10)
        self.browser.safeClick(element=accountNumberDropdownSelection)
        # Finally, click "select" to search
        searchedAccountSelectButtonXPath = "//tr/td/div/fieldset/ol/li/input[contains(@id,'wizFindExistingAssigment_btnSearchedAccountSelect')]"
        self.browser.safeClick(by=By.XPATH,value=searchedAccountSelectButtonXPath,retryClicks=True,timeout=60,clickDelay=3,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="sites")))
        #endregion === Accounts Sidetab ===

        #region === Sites Sidetab ===
        # Now, we should be on the "Sites" sideTab
        # To find the valid site, we will flip through all pages until we locate our exact match.
        targetSiteXPath = f"//table[contains(@id,'sgvSites')]/tbody/tr[contains(@class,'sgvitems')]/td[1][starts-with(text(),'{siteCode}')]"
        nextButtonCSS = "#wizLinkAssignments_wizFindExistingAssigment_gvpSites_btnNext"
        # Here we loop through each site, looking for our specified site code.
        while True:
            currentPageNumber,totalPageNumber = getPageNumbers()
            targetSiteElement = self.browser.searchForElement(by=By.XPATH,value=targetSiteXPath,timeout=1,testClickable=True)
            if(targetSiteElement):
                break
            elif(currentPageNumber >= totalPageNumber):
                error = RuntimeError(f"Could not find site code '{siteCode}' in assignment wizard after flipping through {totalPageNumber} pages on the Sites sideTab.")
                log.error(error)
                raise error
            else:
                # Flip to the next page. First build a test XPATH to ensure the next page has been reached.
                nextPageTextTestForXPath = f"{pageCountTextXPath}[contains(text(),'(Page {currentPageNumber + 1} of {totalPageNumber})')]"
                self.browser.safeClick(by=By.CSS_SELECTOR,value=nextButtonCSS,timeout=30,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=nextPageTextTestForXPath))
        # We've now found our element, so we can click on it.
        self.browser.safeClick(element=targetSiteElement,retryClicks=True,timeout=60,clickDelay=3,
                               successfulClickCondition=lambda b: b.searchForElement(element=targetSiteElement,invertedSearch=True))
        #endregion === Sites Sidetab ===

        #region === Misc Sidetabs ===
        # At this point, what will pop up next is completely and utterly unpredictable. To remedy this,
        # we use a while loop to continuously react to each screen that pops up next, until we find the
        # "make assignment" screen.
        while True:
            logMessage = "Checking for next page in assignment wizard..."
            currentTab = self.browser.find_element(by=By.XPATH,value=currentSideTabXPath).text.lower()
            # If TMA pops up with "Company" selection. This usually only happens with OpCo 000,in which case
            # we'd select 000. There are a couple other special cases which are handled as well.
            if (currentTab == "company"):
                log.debug(f"{logMessage} Found company page on assignment wizard")
                if (siteCode in ["000","262","331"]):
                    selectorForSiteCodeXPath = f"//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='{siteCode}']"
                    self.browser.safeClick(by=By.XPATH,value=selectorForSiteCodeXPath,retryClicks=True,timeout=60,clickDelay=3,
                                           successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="company"),invertedSearch=True))
                else:
                    error = RuntimeError("Company tab is asking for information on a non-000 OpCo! Edits will be required. God help you!")
                    log.error(error)
                    raise error

            # If TMA pops up with "Division" selection. Again, this usually only occurs (to my knowledge) on 000
            # OpCo, in which case the only selectable option is "Corp Offices". If this shows up on a non-000
            # OpCo, the method will throw an error.
            elif (currentTab == "division"):
                log.debug(f"{logMessage} Found division page on assignment wizard")
                if (siteCode == "000"):
                    selectorForCorpOfficesXPath = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='Corp Offices']"
                    self.browser.safeClick(by=By.XPATH, value=selectorForCorpOfficesXPath, retryClicks=True, timeout=60,clickDelay=3,
                                           successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="division"),invertedSearch=True))
                else:
                    error = RuntimeError("Division tab is asking for information on a non-000 OpCo! Edits will be required. God help you!")
                    log.error(error)
                    raise error

            # If TMA pops up with "Department" selection. In almost every case, I believe we should be selecting
            # Wireless-OPCO. The one exception seems to be, of course, OpCo 000. In that case, we select
            # "Wireless-Corp Liable".
            elif (currentTab == "department"):
                log.debug(f"{logMessage} Found department page on assignment wizard")
                if (siteCode == "000"):
                    departmentSelectionChoiceXPATH = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='Wireless-Corp Liable']"
                else:
                    departmentSelectionChoiceXPATH = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='Wireless-OPCO']"
                self.browser.safeClick(by=By.XPATH, value=departmentSelectionChoiceXPATH, retryClicks=True, timeout=60,clickDelay=3,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="department"),invertedSearch=True))

            # If TMA pops up with "CostCenters" selection. We've been told to essentially ignore this, and pick whatever
            # the last option is.
            elif (currentTab == "costcenters"):
                log.debug(f"{logMessage} Found cost centers page on assignment wizard")
                allCostCenterEntriesXPath = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td"
                allEntries = self.browser.find_elements(by=By.XPATH, value=allCostCenterEntriesXPath)
                entriesQuantity = len(allEntries)
                lastEntry = allEntries[entriesQuantity - 1]
                self.browser.safeClick(element=lastEntry, retryClicks=True, timeout=60,clickDelay=3,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="costcenters"),invertedSearch=True))

            # If TMA pops up with "ProfitCenter" selection. This is essentially the same as CostCenters, with no necessary
            # special exception for OpCo 000.
            elif (currentTab == "profitcenter"):
                log.debug(f"{logMessage} Found profit center page on assignment wizard")
                allProfitCenterEntriesXPath = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td"
                allEntries = self.browser.find_elements(by=By.XPATH, value=allProfitCenterEntriesXPath)
                entriesQuantity = len(allEntries)
                lastEntry = allEntries[entriesQuantity - 1]
                self.browser.safeClick(element=lastEntry, retryClicks=True, timeout=60, clickDelay=3,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=sideTabXPathTemplate.format(tabName="profitcenter"),invertedSearch=True))

            # If TMA brings us to "Finalize" we exit the loop as we've finished with making the assignment.
            elif (currentTab == "finalize"):
                log.debug(f"{logMessage} Found finalize page of assignment wizard!")
                break

            # Other cases.
            else:
                # Sometimes sites will still register - just skip it if so. Any other case REALLY shouldn't ever happen.
                if(currentTab != "sites"):
                    error = RuntimeError(f"{logMessage} Found strange value for assignment wizard tab: {currentTab}")
                    log.error(error)
                    raise error
        #endregion === Misc Sidetabs ===

        yesMakeAssignmentButtonXPath = "//table/tbody/tr/td/div/ol/li/a[contains(@id,'wizFindExistingAssigment_lnkLinkAssignment')][text()='Yes, make the assignment.']"
        self.browser.safeClick(by=By.XPATH,value=yesMakeAssignmentButtonXPath,retryClicks=True,timeout=60,clickDelay=5,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=yesMakeAssignmentButtonXPath,invertedSearch=True))
        log.info("Successfully created assignment.")

    # endregion === Assignment Navigation ===

    #region === Special Searches ===

    # This method attempts to return the People object of a Sysco user, given a simple userName to search, and a manager
    # name to verify against
    def searchPeopleFromNameAndSup(self,userName, supervisorName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        self.readPage()

        # Clean the supervisor name for later use.
        supervisorName = re.sub(r'[^A-Za-z0-9]', '', supervisorName)

        # First, we need to make sure we're on Sysco
        if(self.currentLocation.client != "Sysco"):
            self.navToClientHome("Sysco")

        selectionMenuString = "//div/div/div/div/div/div/select[starts-with(@id,'ctl00_LeftPanel')]/option"
        searchBarString = "//div/div/fieldset/input[@title='Press (ENTER) to submit. ']"
        inactiveCheckboxString = "//div/div/div/input[starts-with(@id,'ctl00_LeftPanel')][contains(@id,'chkClosed')][@type='checkbox']"

        peopleOption = self.browser.find_element(by=By.XPATH,value=selectionMenuString + "[@value='people']")
        peopleOption.click()
        self.waitForTMALoader()

        # Make sure inactive is False
        inactiveCheckbox = self.browser.find_element(by=By.XPATH,value=inactiveCheckboxString)
        if (str(inactiveCheckbox.get_attribute("CHECKED")) == "true"):
            inactiveCheckbox.click()
            self.waitForTMALoader()
        elif (str(inactiveCheckbox.get_attribute("CHECKED")) == "None"):
            pass

        searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
        searchBar.clear()
        searchBar.send_keys(str(userName))
        searchBar = self.browser.searchForElement(by=By.XPATH,value=searchBarString,testClickable=True,timeout=3)
        searchBar.send_keys(u'\ue007')
        self.waitForTMALoader()

        # Get the full list of results
        peopleResultsXPath = f"//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a"
        peopleResults = self.browser.find_elements(by=By.XPATH,value=peopleResultsXPath)

        # If there's no results, assume the person doesn't exist.
        if(len(peopleResults) == 0):
            return None
        # Otherwise, document each found netID for later testing.
        else:
            potentialNetIDs = set()
            for peopleResult in peopleResults:
                netIDPattern = r":\s([A-Za-z0-9]{8,10})(?=\s)"
                netIDMatch = re.search(netIDPattern,peopleResult.text)
                if(netIDMatch):
                    potentialNetIDs.add(str(netIDMatch.group(1)).strip().lower())

            # Now that we have a list of NetIDs that may be our target user, we test each one to check for
            # the target supervisor.
            for potentialNetID in potentialNetIDs:
                self.navToLocation(TMALocation(client="Sysco",entryType="People",entryID=potentialNetID))
                resultPeopleObject = self.People_ReadAllInformation()
                # This means we found our network ID, and return it
                if(supervisorName == re.sub(r'[^A-Za-z0-9]', '', resultPeopleObject.info_Manager)):
                    return resultPeopleObject

            # If we've gotten here and still haven't found anything, that means we haven't found it, and return None.
            return None



    #endregion === Special Searches ===

# orderType - New Install, Upgrade, etc.
# client - Sysco, SLB, Rimkus, etc.
# carrier - Verizon, AT&T, etc.
# portalOrderNum - Number of portal order, via email, or SNow ticket
# orderDate - Date order was placed
# uas placeserName - User order wd for
# account - Carrier account number
# device - Name of the device
# imei - IMEI of the device
# monthlyChargeback - Who pays the monthly service cost (Corp, BYOD, etc.)
# deviceChargeback - Who paid for the device (Corp, BYOD, etc.)
# plan - Name of the plan
# serviceNum - The number assigned by this order
# specialNotes - Any special notes
# tracking - The tracking number
def genTMAOrderNotes(orderType,carrier=None,portalOrderNum=None,orderDate=None,userName=None,device=None,imei=None,
                     monthlyChargeback=None,deviceChargeback=None,plan=None,serviceNum=None,specialNotes=None,tracking=None):
    resultString = ""
    if(orderType == "New Install"):
        resultString += f"{orderType.upper()} ordered per  {portalOrderNum} {orderDate} for {userName} on {carrier} account\n"
    elif(orderType == "Upgrade"):
        resultString += f"{orderType.upper()} ordered per  {portalOrderNum} {orderDate} for {userName} - {serviceNum} on {carrier} account\n"
    resultString += "\n"
    resultString += f"DEVICE- {device}\n"
    resultString += f"IMEI- {imei}\n"
    resultString += "\n"
    resultString += f"Chargeback Device: {deviceChargeback}\n"
    resultString += f"Chargeback Monthly Service: {monthlyChargeback}\n"
    resultString += "\n"
    if(orderType == "New Install"):
        resultString += f"PLANS:{plan}\n"
    elif(orderType == "Upgrade"):
        resultString += f"PLANS changes?: {plan}\n"
    if(orderType == "New Install"):
        resultString += "\n"
        resultString += f"Number assigned: {serviceNum}\n"
    resultString += "\n"
    resultString += f"Special notes: {orderType} {specialNotes}\n"
    resultString += f"TRACKING: {tracking}"

    return resultString