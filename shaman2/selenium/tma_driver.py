import time
import copy
from datetime import datetime
from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import Select
from shaman2.selenium.browser import Browser
from shaman2.utilities.shaman_utils import convertServiceIDFormat
from shaman2.common.logger import log
from shaman2.common.config import mainConfig, clientConfig

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
        # -Orders ([TMAOrderNumber,ticketOrderNumber,vendorOrderNumber])
        # -People (Network ID)
        # -Interactions (Interaction Number)
        # -Always will be RegularEquipment
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
                returnString += "Exterior Site ("
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
class People:

    # Init method to initialize info for this People
    def __init__(self,locationData : TMALocation = None):
        self.location = locationData
        self.info_Client = None
        self.info_FirstName = None
        self.info_LastName = None
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
class Service:

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
class Order:

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
class Cost:

    # Basic init method to initialize instance variables.
    def __init__(self, isBaseCost=True, featureName=None, gross=0, discountPercentage=0, discountFlat=0):
        self.info_IsBaseCost = isBaseCost
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
class Equipment:

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
        returnString += "\nLinked Service:" + str(self.info_LinkedService)

        return returnString
class Assignment:
    # Initializing a TMAAssignment requires the client (LYB, Sysco, etc.) and vendor
    # (AT&T Mobility, Verizon Wireless, etc) to be specified.
    def __init__(self, client = None, vendor = None,siteCode = None,assignmentType = "Wireless"):
        self.info_Client = client
        self.info_Type = assignmentType
        self.info_Vendor = vendor


        self.info_Account = clientConfig[client]["Accounts"][vendor][self.info_Vendor]

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

# How many TMA Location Datas will be stored at maximum, to conserve the TMA object from endlessly inflating.
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
    def switchToNewTab(self,timeout=30):
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
                log.error(f"Multiple popups found!")
                raise MultipleTMAPopups()
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
                headerText = self.browser.find_element(by=By.XPATH, value=clientNameHeaderPath).text
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

                        TMAOrderPath = "//span[text()='Order #:']/following-sibling::span"
                        TMAOrderNumber = self.browser.find_element(by=By.XPATH, value=TMAOrderPath).text

                        ticketOrderPath = "//span[text()='Remedy Ticket']/following-sibling::input"
                        ticketOrderNumber = self.browser.find_element(by=By.XPATH, value=ticketOrderPath).get_attribute("value")

                        # TODO use a dict instead for ease of use
                        locationData.entryID = [TMAOrderNumber, ticketOrderNumber, vendorOrderNumber]
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
            newLocationData = self.readPage(storeAsCurrent=False)
            if(newLocationData == location and ((newLocationData.activeLinkTab == location.activeLinkTab and newLocationData.activeInfoTab == location.activeInfoTab) or fuzzyPageDetection)):
                return True
            else:
                time.sleep(0.5)
        error = ValueError(f"waitForLocationLoad never loaded the targeted page:\n{location}")
        log.error(error)
        raise error
    # This method waits until the TMA loader element in invisible - in other words, it waits until TMA considers the
    # page to be "finished loading". DOESN'T WORK on popup TMA tabs (couldn't find any loader-type elements)
    def waitForTMALoader(self,timeout=120):
        startTime = time.time()
        loaderXPath = "//div[@id='ctl00_updateMainPage'][@aria-hidden='false']"
        loaderElement = self.browser.searchForElement(by=By.XPATH,value=loaderXPath,timeout=1)
        if(loaderElement):
            self.browser.searchForElement(by=By.XPATH,value=loaderXPath,timeout=timeout,invertedSearch=True,debug=True,raiseError=True)
            print(f"Waited on TMA loader for {time.time() - startTime} seconds")
            return True
        else:
            log.warning("Tried to wait for TMA loader, but no loader was found on this page!")

    # This method simply navigates to a specific client's home page, from the Domain. If not on DomainPage,
    # it simply warns and does nothing.
    def navToClientHome(self,clientName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(self.currentLocation.isLoggedIn != True):
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
    # TODO This function has some reliability issues. Sometimes, the result is clicked too quickly OR the page is read too quickly before the result page can load.
    def navToLocation(self,locationData : TMALocation = None, timeout=60):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        copyOfTargetLocation = copy.copy(locationData)

        self.readPage()
        if(not self.currentLocation.isLoggedIn):
            #TODO actual raise error here
            log.error(f"Can not navigate to location '{locationData}' - not currently logged in to TMA.")
            return False

        # First, we need to make sure we're on the correct client.
        if(locationData.client != self.currentLocation.client):
            self.navToClientHome(locationData.client)

        selectionMenuString = "//div/div/div/div/div/div/select[starts-with(@id,'ctl00_LeftPanel')]/option"
        searchBarString = "//div/div/fieldset/input[@title='Press (ENTER) to submit. ']"
        inactiveCheckboxString = "//div/div/div/input[starts-with(@id,'ctl00_LeftPanel')][contains(@id,'chkClosed')][@type='checkbox']"

        if(locationData.entryType == "Interaction"):
            interactionsOption = self.browser.find_element(by=By.XPATH,value=f"{selectionMenuString}[@value='interactions']")
            interactionsOption.click()
            time.sleep(2)
            searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
            searchBar.clear()
            searchBar.send_keys(str(locationData.entryID))
            time.sleep(2)
            searchBar.send_keys(u'\ue007')
            resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[starts-with(text(),'" + locationData.entryID + " (')]"
            resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120,raiseError=True)
            resultItem.click()
        elif(locationData.entryType == "Service"):
            servicesOption = self.browser.find_element(by=By.XPATH,value=selectionMenuString + "[@value='services']")
            servicesOption.click()
            time.sleep(2)

            # TODO right now, this ALWAYS sets inactive to false. Come back here if we need to actually
            # account for inactive users.
            inactiveCheckbox = self.browser.find_element(by=By.XPATH,value=inactiveCheckboxString)
            if (str(inactiveCheckbox.get_attribute("CHECKED")) == "true"):
                inactiveCheckbox.click()
                time.sleep(5)
            elif (str(inactiveCheckbox.get_attribute("CHECKED")) == "None"):
                pass
            for i in range(5):
                try:
                    time.sleep(3)
                    searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
                    searchBar.clear()
                    searchBar.send_keys(str(locationData.entryID))
                    time.sleep(2)
                    searchBar = self.browser.find_element(by=By.XPATH, value=searchBarString)
                    searchBar.send_keys(u'\ue007')
                    targetServiceIDField = f"//input[contains(@id,'txtServiceId')][@value='{convertServiceIDFormat(locationData.entryID,'dashed')}' or @value='{convertServiceIDFormat(locationData.entryID,'dotted')}' or @value='{convertServiceIDFormat(locationData.entryID,'raw')}']"
                    resultString = f"//div[contains(@id,'UpdatePanelResults')]//tr[contains(@class,'sgvitems')]//a[starts-with(text(),'{convertServiceIDFormat(locationData.entryID,'dashed')}')]"
                    resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120,raiseError=True)
                    self.browser.safeClick(element=resultItem,timeout=120,retryClicks=True,testInterval=3,
                                           successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=targetServiceIDField,invertedSearch=True,timeout=5))
                    time.sleep(3)
                    break
                except Exception as e:
                    if(i == 4):
                        raise e
                    else:
                        time.sleep(2)
        elif(locationData.entryType == "People"):
            peopleOption = self.browser.find_element(by=By.XPATH,value=selectionMenuString + "[@value='people']")
            peopleOption.click()
            #time.sleep(2)
            self.waitForTMALoader()
            #TODO right now, this ALWAYS sets inactive to false. Come back here if we need to actually
            # account for inactive users.
            inactiveCheckbox = self.browser.find_element(by=By.XPATH,value=inactiveCheckboxString)
            if (str(inactiveCheckbox.get_attribute("CHECKED")) == "true"):
                inactiveCheckbox.click()
                #time.sleep(5)
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
            time.sleep(2)
            searchBar = self.browser.find_element(by=By.XPATH,value=searchBarString)
            searchBar.clear()
            # For orders, since there are 3 potential numbers to search by, we prioritize them in this order: TMA Order Number, Vendor Order Number, Ticket Order Number.
            if(locationData.entryID[0] == "" or locationData.entryID[0] is None):
                if (locationData.entryID[2] == "" or locationData.entryID[2] is None):
                    orderNumber = locationData.entryID[1]
                    orderNumber = orderNumber.lower()
                    orderNumberIndex = 1
                    resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'/ " + orderNumber + " (')]"
                else:
                    orderNumber = locationData.entryID[2]
                    orderNumber = orderNumber.lower()
                    orderNumberIndex = 2
                    resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),': " + orderNumber + " ')]"
            else:
                orderNumber = locationData.entryID[0]
                orderNumber = orderNumber.lower()
                orderNumberIndex = 0
                resultString = "//div[contains(@id,'UpdatePanelResults')]/fieldset/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td/a[starts-with(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'" + orderNumber + ": ')]"
            searchBar.send_keys(str(orderNumber))
            time.sleep(2)
            searchBar.send_keys(u'\ue007')
            resultItem = self.browser.searchForElement(by=By.XPATH,value=resultString,timeout=120)
            resultItem.click()
            time.sleep(3)
            self.readPage()
            for i in range(10):
                if(not self.currentLocation.isLoggedIn):
                    continue
                elif(self.currentLocation.client != locationData.client):
                    continue
                elif(self.currentLocation.entryType != locationData.entryType):
                    continue
                elif(self.currentLocation.entryID != locationData.entryID):
                    continue
                else:
                    log.info(f"Successfully navigated to location '{self.currentLocation}'")
                    return True
            errorString = "Error while running navToLocation. This page is wrong due to inconsistencies between: "
            if (self.currentLocation.isLoggedIn == False):
                errorString += " isLoggedIn, "
            if (self.currentLocation.client != locationData.client):
                errorString += " client, "
            if (self.currentLocation.entryType != locationData.entryType):
                errorString += " entryType, "
            if (self.currentLocation.entryID != locationData.entryID):
                errorString += " entryID, "
            log.error(errorString)
            return False
        else:
            #TODO raise actual error here
            log.error(f"Can not search for entryType: {locationData.entryType}")
            return False

        self.waitForTMALoader()
        self.waitForLocationLoad(location=locationData,fuzzyPageDetection=True)


    # endregion === General Site Navigation ===

    # region ====================Service Data & Navigation ===========================

    # All these methods assume that TMA is currently on a Service entry.

    # Reads main information from the "Line Info" service tab of a Service Entry in
    # TMA. If a Service object is supplied, it reads the info into this object - otherwise
    # it returns a new Service object.
    def Service_ReadMainInfo(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            serviceObject = Service()
        xpathPrefix = "//div/fieldset/ol/li"
        self.Service_NavToServiceTab("Line Info")

        if (serviceObject.info_Client == "LYB"):
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
        elif (serviceObject.info_Client == "Sysco"):
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

        b.log.info("Successfully read.")
        return serviceObject
    # LINE INFO : Reads "Line Info" (install and disco date, inactive checkbox) for this service entry.
    def Service_ReadLineInfoInfo(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("line info")
        if(serviceObject is None):
            serviceObject = Service()

        prefix = "//div/div/ol/li"
        serviceObject.info_InstalledDate = self.browser.find_element(by=By.XPATH, value=
        prefix + "/input[contains(@name,'Detail$txtDateInstalled')][contains(@id,'Detail_txtDateInstalled')]").get_attribute(
            "value")
        serviceObject.info_DisconnectedDate = self.browser.find_element(by=By.XPATH, value=
        prefix + "/input[contains(@name,'Detail$txtDateDisco')][contains(@id,'Detail_txtDateDisco')]").get_attribute(
            "value")
        serviceObject.info_IsInactiveService = self.browser.find_element(by=By.XPATH, value=
        prefix + "/input[contains(@name,'Detail$chkInactive$ctl01')][contains(@id,'Detail_chkInactive_ctl01')]").is_selected()

        b.log.info("Successfully read.")
        return serviceObject
    # COST ENTRIES : Read methods pertaining to cost entries associated with this service.
    def Service_ReadBaseCost(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("base costs")
        if(serviceObject is None):
            serviceObject = Service()
        # We always overwrite the existing info_BaseCost if there was one.
        serviceObject.info_BaseCost = Cost(isBaseCost=True)
        baseCostRowXPath = "//table[contains(@id,'Detail_sfBaseCosts_sgvFeatures')]/tbody/tr[contains(@class,'sgvitems')]"
        if(self.browser.elementExists(by=By.XPATH,value = baseCostRowXPath)):
            baseCostRow = self.browser.find_element(by=By.XPATH,value=baseCostRowXPath)
            allDataEntries = baseCostRow.find_elements(by=By.TAG_NAME,value="td")
            serviceObject.info_BaseCost.info_FeatureString = allDataEntries[0].text
            serviceObject.info_BaseCost.info_Gross = allDataEntries[1].text
            serviceObject.info_BaseCost.info_DiscountPercentage = allDataEntries[2].text
            serviceObject.info_BaseCost.info_DiscountFlat = allDataEntries[3].text
        b.log.info("Successfully read.")
        return serviceObject
    def Service_ReadFeatureCosts(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("features")
        if(serviceObject is None):
            serviceObject = Service()
        serviceObject.info_FeatureCosts = []

        featureCostRowsXPath = "//table[contains(@id,'Detail_sfStandardFeatures_sgvFeatures')]/tbody/tr[contains(@class,'sgvitems')]"
        if(self.browser.elementExists(by=By.XPATH,value=featureCostRowsXPath)):
            featureCostRows = self.browser.find_elements(by=By.XPATH,value=featureCostRowsXPath)
            for featureCostRow in featureCostRows:
                thisFeatureCostObject = Cost(isBaseCost=False)
                allDataEntries = featureCostRow.find_elements(by=By.TAG_NAME, value="td")
                thisFeatureCostObject.info_FeatureString = allDataEntries[0].text
                thisFeatureCostObject.info_Gross = allDataEntries[1].text
                thisFeatureCostObject.info_DiscountPercentage = allDataEntries[2].text
                thisFeatureCostObject.info_DiscountFlat = allDataEntries[3].text
                serviceObject.info_FeatureCosts.append(thisFeatureCostObject)
        b.log.info("Successfully read.")
        return serviceObject
    # LINKED ITEMS : Read methods pertaining to linked items to this service.
    # TODO support for multiple linked people for these three functions, maybe condense to one?
    def Service_ReadLinkedPersonName(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("people")
        if(serviceObject is None):
            result = self.browser.find_element(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[5]").text
            b.log.info(f"Successfully read: {result}")
            return result
        else:
            serviceObject.info_LinkedPersonName = self.browser.find_element(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[5]").text
            b.log.info(f"Successfully read: {serviceObject.info_LinkedPersonName}")
            return serviceObject
    def Service_ReadLinkedPersonNID(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("people")
        if(serviceObject is None):
            result = self.browser.find_element(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[7]").text
            b.log.info(f"Successfully read: {result}")
            return result
        else:
            serviceObject.info_LinkedPersonNID = self.browser.find_element(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[7]").text
            b.log.info(f"Successfully read: {serviceObject.info_LinkedPersonNID}")
            return serviceObject
    def Service_ReadLinkedPersonEmail(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("people")
        if(serviceObject is None):
            result = self.browser.find_element(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[11]").text
            b.log.info(f"Successfully read: {result}")
            return result
        else:
            serviceObject.info_LinkedPersonEmail = self.browser.find_element(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[11]").text
            b.log.info(f"Successfully read: {serviceObject.info_LinkedPersonEmail}")
            return serviceObject
    def Service_ReadLinkedInteractions(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("interactions")

        pageCountText = self.browser.find_element(by=By.XPATH, value="//table/tbody/tr/td/span[contains(@id,'Detail_ucassociations_link_lblPages')]").text
        pageCount = int(pageCountText.split("of ")[1].split(")")[0])

        arrayOfLinkedIntNumbers = []
        for i in range(pageCount):
            arrayOfLinkedInteractionsOnPage = self.browser.find_elements(by=By.XPATH, value=
            "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[4]")
            arrayOfLinkedIntNumbersOnPage = []
            for j in arrayOfLinkedInteractionsOnPage:
                arrayOfLinkedIntNumbersOnPage.append(j.text)
            for j in arrayOfLinkedIntNumbersOnPage:
                if (j in arrayOfLinkedIntNumbers):
                    continue
                arrayOfLinkedIntNumbers.append(j)

            time.sleep(1)
            if ((i + 1) < pageCount):
                nextButton = self.browser.find_element(by=By.XPATH, value="//table/tbody/tr/td/div/div/input[contains(@name,'Detail$ucassociations_link$btnNext')][contains(@id,'Detail_ucassociations_link_btnNext')]")

                while True:
                    self.browser.safeClick(by=None, element=nextButton)
                    time.sleep(3)
                    currentPageNumber = ''
                    pageCountText = self.browser.find_element(by=By.XPATH, value="//table/tbody/tr/td/span[contains(@id,'Detail_ucassociations_link_lblPages')]").text
                    spaceCheck = False
                    for j in pageCountText:
                        if (spaceCheck == True):
                            if (j == ' '):
                                break
                            currentPageNumber += j
                        if (j == ' '):
                            spaceCheck = True
                            continue
                    currentPageNumber = int(currentPageNumber)

                    if (currentPageNumber == i + 2):
                        break
                    time.sleep(2)
                    continue
                continue

        if(serviceObject is None):
            b.log.info(f"Successfully read: {arrayOfLinkedIntNumbers}.")
            return arrayOfLinkedIntNumbers
        else:
            serviceObject.info_LinkedInteractions = arrayOfLinkedIntNumbers
            b.log.info(f"Successfully read: {arrayOfLinkedIntNumbers}.")
            return serviceObject
    def Service_ReadLinkedOrders(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("orders")

        pageCountText = self.browser.find_element(by=By.XPATH, value="//table/tbody/tr/td/span[contains(@id,'Detail_ucassociations_link_lblPages')]").text
        pageCount = int(pageCountText.split(" of ")[1].split(")")[0])

        arrayOfLinkedOrderNumbers = []
        for i in range(pageCount):
            arrayOfLinkedOrdersOnPage = self.browser.find_elements(by=By.XPATH, value=
            "//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[6]")
            arrayOfLinkedOrderNumbersOnPage = []
            for j in arrayOfLinkedOrdersOnPage:
                arrayOfLinkedOrderNumbersOnPage.append(j.text)
            for j in arrayOfLinkedOrderNumbersOnPage:
                if (j in arrayOfLinkedOrderNumbers):
                    continue
                arrayOfLinkedOrderNumbers.append(j)

            time.sleep(1)
            if ((i + 1) < pageCount):
                nextButton = "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$ucassociations_link$btnNext')][contains(@id,'Detail_ucassociations_link_btnNext')]"

                while True:
                    self.browser.safeClick(by=By.XPATH, element=nextButton)
                    time.sleep(3)
                    currentPageNumber = ''
                    pageCountText = self.browser.find_element(by=By.XPATH, value=
                    "//table/tbody/tr/td/span[contains(@id,'Detail_ucassociations_link_lblPages')]").text
                    spaceCheck = False
                    for j in pageCountText:
                        if (spaceCheck == True):
                            if (j == ' '):
                                break
                            currentPageNumber += j
                        if (j == ' '):
                            spaceCheck = True
                            continue
                    currentPageNumber = int(currentPageNumber)

                    if (currentPageNumber == i + 2):
                        break
                    time.sleep(2)
                    continue
                continue

        if(serviceObject is None):
            b.log.info(f"Successfully read: {arrayOfLinkedOrderNumbers}.")
            return arrayOfLinkedOrderNumbers
        else:
            serviceObject.info_LinkedOrders = arrayOfLinkedOrderNumbers
            b.log.info(f"Successfully read: {arrayOfLinkedOrderNumbers}.")
            return serviceObject
    def Service_ReadAllLinkedInformation(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            serviceObject = Service()
        self.Service_ReadLinkedPersonName(serviceObject)
        if (serviceObject.info_Client == "LYB"):
            self.Service_ReadLinkedPersonEmail(serviceObject)
        elif (serviceObject.info_Client == "Sysco"):
            self.Service_ReadLinkedPersonEmail(serviceObject)
            self.Service_ReadLinkedPersonNID(serviceObject)
        self.Service_ReadLinkedInteractions(serviceObject)
        self.Service_ReadLinkedOrders(serviceObject)
        #TODO add support for linked equipment
        #self.Service_ReadLinkedEquipment(serviceObject)

        b.log.info("Successfully read.")
        return True
    # EQUIPMENT : Reads basic information about any linked equipment. Does NOT open the equipment -
    # only reads what is visible from the linked equipment tab.
    def Service_ReadSimpleEquipmentInfo(self,serviceObject : Service = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            serviceObject = Service()
        serviceObject.info_LinkedEquipment = Equipment()

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("equipment")

        linkedEquipmentsXPath = "//table/tbody/tr/td/table[contains(@id,'link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]"
        linkedEquipment = self.browser.find_element(by=By.XPATH,value=linkedEquipmentsXPath)
        equipmentData = linkedEquipment.find_elements(by=By.TAG_NAME,value="td")

        serviceObject.info_LinkedEquipment.info_Make = equipmentData[4]
        serviceObject.info_LinkedEquipment.info_Model = equipmentData[5]
        serviceObject.info_LinkedEquipment.info_MainType = equipmentData[6]
        serviceObject.info_LinkedEquipment.info_SubType = equipmentData[7]

        b.log.info("Successfully read.")
        return serviceObject


    # Simple write methods for each of the elements existing in the "Main Info" category
    # (info that's displayed on the top part of the service entry) If a serviceObject is
    # given, it'll write from the given serviceObject. Otherwise, they take a raw value
    # as well.
    def Service_WriteServiceNumber(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ServiceNumber

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        serviceNumberInput = self.browser.find_element(by=By.XPATH, value="//div/fieldset/ol/li/input[contains(@name,'Detail$txtServiceId')][contains(@id,'Detail_txtServiceId')]")
        serviceNumberInput.clear()
        serviceNumberInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteUserName(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_UserName

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        userNameInput = self.browser.find_element(by=By.XPATH, value="//div/fieldset/ol/li/input[contains(@name,'Detail$txtUserName')][contains(@id,'Detail_txtUserName')]")
        userNameInput.clear()
        userNameInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteAlias(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_Alias

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        aliasInput = self.browser.find_element(by=By.XPATH, value=
        "//div/fieldset/ol/li/input[contains(@name,'Detail$txtDescription1')][contains(@id,'Detail_txtDescription1')]")
        aliasInput.clear()
        aliasInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteContractStartDate(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ContractStartDate

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        contractStartDateInput = self.browser.find_element(by=By.XPATH, value="//div/fieldset/ol/li/input[contains(@name,'Detail$ICOMMTextbox1')][contains(@id,'Detail_ICOMMTextbox1')]")
        contractStartDateInput.clear()
        contractStartDateInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteContractEndDate(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ContractEndDate

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        contractEndDateInput = self.browser.find_element(by=By.XPATH, value="//div/fieldset/ol/li/input[contains(@name,'Detail$txtDescription5')][contains(@id,'Detail_txtDescription5')]")
        contractEndDateInput.clear()
        contractEndDateInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteUpgradeEligibilityDate(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_UpgradeEligibilityDate

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        upgradeEligibilityDateInput = self.browser.find_element(by=By.XPATH, value="//div/fieldset/ol/li/input[contains(@name,'Detail$txtContractEligibilityDate')][contains(@id,'Detail_txtContractEligibilityDate')]")
        upgradeEligibilityDateInput.clear()
        upgradeEligibilityDateInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteServiceType(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_ServiceType

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        serviceTypeSelect = "//div/fieldset/ol/li/select[contains(@name,'Detail$ddlServiceType$ddlServiceType_ddl')][contains(@id,'Detail_ddlServiceType_ddlServiceType_ddl')]"
        targetValue = f"{serviceTypeSelect}/option[text()='{valueToWrite}']"
        if (self.browser.elementExists(by=By.XPATH, value=targetValue)):
            self.browser.find_element(by=By.XPATH, value=targetValue).click()
            b.log.info(f"Successfully wrote: {valueToWrite}")
        else:
            b.log.error(f"Could not writeServiceType with this value: {valueToWrite}")
    def Service_WriteCarrier(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_Carrier

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        carrierSelect = "//div/fieldset/ol/li/select[contains(@name,'Detail$ddlCarrier$ddlCarrier_ddl')][contains(@id,'Detail_ddlCarrier_ddlCarrier_ddl')]"
        targetValue = f"{carrierSelect}/option[text()='{valueToWrite}']"
        if (self.browser.elementExists(by=By.XPATH, value=targetValue)):
            self.browser.find_element(by=By.XPATH, value=targetValue).click()
            b.log.info(f"Successfully wrote: {valueToWrite}")
        else:
            b.log.error(f"Could not writeCarrier with this value: {valueToWrite}")
    # This main write helper method chains together previous write methods for a single serviceObject.
    # Client is required, and is used to logically decide whether to write
    # certain aspects (like Contract Start Date).
    def Service_WriteMainInformation(self,serviceObject : Service,client : str):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_WriteServiceNumber(serviceObject)
        self.Service_WriteUserName(serviceObject)
        self.Service_WriteAlias(serviceObject)
        # List clients here that user contract start dates.
        if (client in ["LYB"]):
            self.Service_WriteContractStartDate(serviceObject)
        self.Service_WriteContractEndDate(serviceObject)
        self.Service_WriteUpgradeEligibilityDate(serviceObject)
        self.Service_WriteServiceType(serviceObject)
        self.Service_WriteCarrier(serviceObject)
        b.log.info(f"Successfully wrote all main information.")
    # Write methods for each of the "Line Info" values. If a serviceObject is
    # given, it'll write from the given serviceObject. Otherwise, they take a raw value
    # as well.
    def Service_WriteInstalledDate(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_InstalledDate

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False
        installedDateInput = self.browser.find_element(by=By.XPATH, value="//div/div/ol/li/input[contains(@name,'Detail$txtDateInstalled')][contains(@id,'Detail_txtDateInstalled')]")
        installedDateInput.clear()
        installedDateInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    def Service_WriteDisconnectedDate(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_DisconnectedDate

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False
        disconnectedDateInput = self.browser.find_element(by=By.XPATH, value="//div/div/ol/li/input[contains(@name,'Detail$txtDateDisco')][contains(@id,'Detail_txtDateDisco')]")
        disconnectedDateInput.clear()
        disconnectedDateInput.send_keys(valueToWrite)
        b.log.info(f"Successfully wrote: {valueToWrite}")
    # TODO look at making this function standardized/more efficient
    def Service_WriteIsInactiveService(self,serviceObject : Service = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (serviceObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = serviceObject.info_IsInactiveService

        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        inactiveServiceCheckbox = self.browser.find_element(by=By.XPATH, value="//div/div/ol/li/input[contains(@name,'Detail$chkInactive$ctl01')][contains(@id,'Detail_chkInactive_ctl01')]")
        for i in range(20):
            self.browser.implicitly_wait(5)
            boxToggle = inactiveServiceCheckbox.is_selected()
            if (boxToggle == valueToWrite):
                b.log.info(f"Successfully wrote: {valueToWrite}")
                return True
            else:
                inactiveServiceCheckbox.click()
                time.sleep(4)
        b.log.error("Could not toggle inactiveServiceCheckbox to 'on'.")
        return False
    # TODO decide - do we actually need one overarching lineinfo method? Prolly not
    # Method for writing/building base and feature costs onto a service entry. If a serviceObject
    # is given, it will prioritize building the cost objects associated with that serviceObject.
    # Otherwise, if a raw costObject is given, it'll simply build that cost object.
    # TODO error handling when not supply either cost or service object
    def Service_WriteCosts(self,serviceObject : Service = None,costObjects : Cost = None,isBase : bool = True):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(isBase):
            self.Service_NavToServiceTab("base costs")
        else:
            self.Service_NavToServiceTab("features")
        if(serviceObject is None):
            if(type(costObjects) is list):
                costsToWrite = costObjects
            else:
                costsToWrite = [costObjects]
        else:
            if(isBase):
                costsToWrite = [serviceObject.info_BaseCost]
            else:
                costsToWrite = serviceObject.info_FeatureCosts


        prefix = '//div[@class="newitem"][contains(@id,"divFeature")]'
        createNewButton = '//a[contains(@id, "_lnkNewFeature")][text()="Create New"]'
        newItemTestFor = '//div[contains(@id,"divFeature")][@class="newitem"]'


        for costToWrite in costsToWrite:
            createNewButtonElement = self.browser.find_element(by=By.XPATH,value=createNewButton)
            time.sleep(1)
            self.browser.driver.execute_script("arguments[0].click();",createNewButtonElement)
            time.sleep(3)
            # TODO TMA is ass, and this section just proves it. The thing is, cost names are selected from dropdown, but clicking it doesn't actually update the "selected='selected'" attribute, so there's literally no way to tell. only solution is try, then test. implement this later (try adding it, test if the right feature was added and if not, try again.)
            self.browser.safeClick(by=By.XPATH, element=createNewButton, repeat=True, repeatUntilNewElementExists=newItemTestFor)
            featureNameSelectionString = f"{prefix}/div/div/select[contains(@name,'$ddlFeature$ddlFeature_ddl')]/option[text()='{costToWrite.info_FeatureString}']"
            self.browser.safeClick(by=By.XPATH, element=featureNameSelectionString,repeat=True,timeout=5)

            if(costToWrite.info_Gross is not None):
                grossForm = self.browser.find_element(by=By.XPATH, value=f'{prefix}/div/div/ol/li/input[contains(@name,"$txtCost_gross")][contains(@id,"_txtCost_gross")]')
                grossForm.send_keys(costToWrite.info_Gross)
            if(costToWrite.info_DiscountPercentage is not None):
                discountPercentForm = self.browser.find_element(by=By.XPATH, value=f'{prefix}/div/div/ol/li/input[contains(@name,"$txtDiscount")][contains(@id,"_txtDiscount")]')
                discountPercentForm.send_keys(costToWrite.info_DiscountPercentage)
            if(costToWrite.info_DiscountFlat is not None):
                discountFlatForm = self.browser.find_element(by=By.XPATH, value=f'{prefix}/div/div/ol/li/input[contains(@name,"$txtDiscountFlat")][contains(@id,"_txtDiscountFlat")]')
                discountFlatForm.send_keys(costToWrite.info_DiscountFlat)

            insertButton = self.browser.find_element(by=By.XPATH, value=f'{prefix}/span[contains(@id,"btnsSingle")]/div/input[contains(@name, "$btnsSingle$ctl01")][contains(@value, "Insert")]')
            self.browser.safeClick(by=None, element=insertButton,jsClick=True)
            finishedCost = f"//table[contains(@id,'sgvFeatures')]/tbody/tr[contains(@class,'sgvitems')]/td[text()='{costToWrite.info_FeatureString}']"
            if(not self.browser.elementExists(by=By.XPATH,value=finishedCost,timeout=20)):
                raise ValueError("Bitch no you didn't")


        # TODO add visualization of costs?
        b.log.debug(f"Successfully wrote costs.")


    # This method simply clicks the "update" button (twice) on the service.
    def Service_InsertUpdate(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        insertButtonString = "//span[@class='buttons']/div[@class='buttons']/input[contains(@name,'ButtonControl1$ctl')][@value='Insert']"
        updateButtonXPath = "//span[@class='buttons']/div[@class='buttons']/input[contains(@name,'ButtonControl1$ctl')][@value='Update']"
        if (self.browser.elementExists(by=By.XPATH, value=updateButtonXPath)):
            self.browser.safeClick(by=By.XPATH, element=updateButtonXPath)
            self.browser.safeClick(by=By.XPATH, element=updateButtonXPath)
            b.log.info("Updated service.")
        elif(self.browser.elementExists(by=By.XPATH,value=insertButtonString)):
            self.browser.safeClick(by=By.XPATH,element=insertButtonString)
            b.log.info("Inserted service.")
        else:
            b.log.warn("Neither insert nor update buttons exist.")
            return False

        serviceAlreadyExistsString = "//span[text()='The Service already exists in the database.']"
        if(self.browser.elementExists(by=By.XPATH,value=serviceAlreadyExistsString,timeout=1)):
            return "ServiceAlreadyExists"
        else:
            return True
    # This method simply clicks on "create new linked equipment" for the service entry we're on. Does nothing
    # with it, and WILL pop up a new window, so switchToNewTab will be required afterwards.
    def Service_CreateLinkedEquipment(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("equipment")
        createNewString = "//table/tbody/tr/td/div/table/tbody/tr/td/a[contains(@id,'link_lnkCreateNew')][text()='Create New Linked Item']"
        self.browser.safeClick(by=By.XPATH, element=createNewString)
        b.log.info("Successfully clicked 'create new service.'")
    # This method accepts a string to represent a service tab in a TMA
    # service. It will then attempt to navigate to that tab, or do nothing
    # if that is the currently active service tab. Dictionaries are also defined
    # for the various tab XPATHs, as well as XPATHs to various elements
    # used to verify that the nav was successful.

    # Method to navigate between all service tabs, and one for getting the current service tab.
    def Service_NavToServiceTab(self, serviceTab):
        serviceTabDictionary = {"line info": "btnLineInfoExtended",
                                "assignments": "btnAssignments",
                                "used for": "btnUsedFor",
                                "base costs": "btnBaseCosts",
                                "features": "btnFeatures",
                                "fees": "btnFees",
                                "links": "btnLinks",
                                "history": "btnHistory"}

        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTab = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[contains(@name,'{serviceTabDictionary[serviceTab.lower()]}')][translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{serviceTab.lower()}']"
        serviceTabTestFor = f"{targetTab}[@class='selected']"

        if (self.browser.safeClick(by=By.XPATH, element=targetTab, repeat=True, repeatUntilNewElementExists=serviceTabTestFor,clickDelay=5)):
            b.log.info(f"Successfully navigated to serviceTab '{serviceTab}'.")
            return True
        else:
            b.log.error(f"Failed to navigate to serviceTab '{serviceTab}'.")
            return False
    def Service_GetCurrentServiceTab(self):
        targetTab = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[@class='selected']"
        return self.browser.find_element(by=By.XPATH,value=targetTab).get_attribute("value")
    # Helper method to easily navigate to linked tabs.
    # TODO add error handling here
    def Service_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTab = f"//table[contains(@id,'Detail_ucassociations_link_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'{linkedTabName.lower()}')]"
        targetTabTestFor = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH, element=targetTab, repeat=True, repeatUntilNewElementExists=targetTabTestFor,clickDelay=5)
        b.log.info(f"Successfully navigated to linkedTab '{linkedTabName}'")
    # This method navigates TMA from a service to its linked equipment. Method
    # assumes that there is only one linked equipment.
    # TODO add support for multiple equipment (not that this should EVER happen in TMA)
    # TODO proper error handling
    def Service_NavToEquipmentFromService(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Service_NavToServiceTab("links")
        self.Service_NavToLinkedTab("equipment")
        equipmentArray = self.browser.find_elements(by=By.XPATH, value="//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]")
        if (len(equipmentArray) == 0):
            b.log.warning("Could not navToEquipmentFromService, as there is no equipment presently linked.")
            return False
        elif (len(equipmentArray) > 1):
            equipmentIndex = 1
            # TODO handle this scenario where multiple equipment exist
            b.log.warning("Multiple equipments linked to service. Please input target equipment: ")
        else:
            equipmentIndex = 1
        equipmentDoor = f"//table[contains(@id,'ucassociations_link_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')][{equipmentIndex}]/td[2]"
        for i in range(12):
            if ("https://tma4.icomm.co/tma/Authenticated/Client/Equipment" in self.browser.get_current_url()):
                b.log.info("Successfully navigated to linked equipment from service.")
                return True
            else:
                if (i > 9):
                    b.log.error("Could not successfully navigate to linked equipment from service.")
                    return False
                self.browser.implicitly_wait(10)
                self.browser.safeClick(by=By.XPATH, element=equipmentDoor)
                time.sleep(5)
    # This method assumes that TMA is currently in the process of creating a new service,
    # and asking for the Modal Service Type. This method simply attempts to select the given
    # type - if not on this screen, this function just returns false.
    # TODO LIES LIES! It runs no matter what. BETTER ERROR REPORTING!
    # TODO this function seems broken? Fuckle stiltskin
    def Service_SelectModalServiceType(self,serviceType):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        #if("UserControls/Common/ModalServiceTypeGroup" not in self.browser.get_current_url()):
        #    return False
        modalServiceTypeLinkXPath = f"//div/div/fieldset/a[contains(@id,'modalLinkButton')][text()='{serviceType}']"
        self.browser.safeClick(by=By.XPATH,element=modalServiceTypeLinkXPath,repeat=True,repeatUntilElementDoesNotExist=modalServiceTypeLinkXPath)
        b.log.info(f"Successfully selected service type '{serviceType}.")
        return True



    # endregion ====================Service Data & Navigation ===========================

    #region ====================Order Data & Navigation ===========================

    # All these methods assume that TMA is currently on an Order entry.


    # Read methods for each part of the Order entry.
    def Order_ReadMainInfo(self,orderObject : Order = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(orderObject is None):
            orderObject = Order()

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
    def Order_ReadOrderNotes(self,orderObject : Order = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(orderObject is None):
            orderObject = Order()

        self.Order_NavToOrderTab("notes")
        orderObject.info_OrderNotes = self.browser.find_element(by=By.XPATH,value="//textarea[contains(@id,'txtSummary')]").text
        return orderObject
    # TODO hehe this function doesn't actually work. Make it work.
    def Order_ReadLinkedService(self,orderObject : Order = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if(orderObject is None):
            orderObject = Order()

        self.Order_NavToOrderTab("links")
        self.Order_NavToLinkedTab("services")

    # Write methods for each part of the Order entry.
    # TODO condense this (and maybe the service equivalents?) down to a single function using mapped values?
    # Main Info
    def Order_WritePortalOrderNumber(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_PortalOrderNumber
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Portal Order Number']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteVendorOrderNumber(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_VendorOrderNumber
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Vendor Order #:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteVendorTrackingNumber(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_VendorTrackingNumber
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Vendor Tracking #:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteContactName(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_ContactName
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Contact Name:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteSubmittedDate(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_SubmittedDate
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Submitted:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteCompletedDate(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_CompletedDate
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Completed:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteDueDate(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_DueDate
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Due:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteRecurringCost(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RecurringCost
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Cost:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteRecurringSavings(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RecurringSavings
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Savings:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteCredits(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_Credits
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Credits:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteOneTimeCost(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OneTimeCost
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='One Time Cost:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteRefundAmount(self,orderObject : Order = None,rawValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RefundAmount
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        targetField = self.browser.find_element(by=By.XPATH,value="//span[text()='Refund Amount:']/following-sibling::input")
        targetField.clear()
        targetField.send_keys(rawValue)
    def Order_WriteOrderStatus(self, orderObject: Order = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderStatus
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        dropdownPrefix = "//span[text()='Order Status:']/following-sibling::select"
        targetField = self.browser.find_element(by=By.XPATH,value=f"{dropdownPrefix}/option[text()='{valueToWrite}']")
        targetField.click()
    def Order_WritePlacedBy(self, orderObject: Order = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_PlacedBy
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        dropdownPrefix = "//span[text()='Placed By:']/following-sibling::select"
        targetField = self.browser.find_element(by=By.XPATH,value=f"{dropdownPrefix}/option[text()='{valueToWrite}']")
        targetField.click()
    def Order_WriteOrderClass(self, orderObject: Order = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderClass
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        dropdownPrefix = "//span[text()='Order Class:']/following-sibling::select"
        targetField = self.browser.find_element(by=By.XPATH,value=f"{dropdownPrefix}/option[text()='{valueToWrite}']")
        targetField.click()
    def Order_WriteOrderType(self, orderObject: Order = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderType
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        dropdownPrefix = "//span[text()='Order Type:']/following-sibling::select"
        targetField = self.browser.find_element(by=By.XPATH,value=f"{dropdownPrefix}/option[text()='{valueToWrite}']")
        targetField.click()
    def Order_WriteOrderSubType(self, orderObject: Order = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_OrderSubType
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        dropdownPrefix = "//span[text()='Order Sub-Type:']/following-sibling::select"
        targetField = self.browser.find_element(by=By.XPATH,value=f"{dropdownPrefix}/option[text()='{valueToWrite}']")
        targetField.click()
    # Other
    def Order_WriteOrderNotes(self, orderObject: Order = None, rawValue=None):
        self.browser.switchToTab(self.currentTMATab[0], self.currentTMATab[1])
        if (orderObject is None):
            valueToWrite = rawValue
        else:
            valueToWrite = orderObject.info_RecurringCost
        if (valueToWrite is None):
            b.log.warning(f"Didn't write, as valueToWrite is {valueToWrite}")
            return False

        self.Order_NavToOrderTab("notes")

        targetField = self.browser.find_element(by=By.XPATH, value="//textarea[contains(@id,'txtSummary')]")
        targetField.clear()
        targetField.send_keys(rawValue)
    # Method to click either insert or update, whichever is present.
    def Order_InsertUpdate(self):
        insertButtonString = "//input[@value='Insert']"
        insertButton = self.browser.elementExists(by=By.XPATH,value=insertButtonString)
        if(insertButton):
            insertButton.click()
            return True

        updateButtonString = "//input[@value='Update']"
        updateButton = self.browser.elementExists(by=By.XPATH,value=updateButtonString)
        if(updateButton):
            updateButton.click()
            return True

        return False

    # Method to navigate between all order tabs, and one for getting the current order tab.
    def Order_NavToOrderTab(self, orderTab):
        orderTabDictionary = {  "notes": "btnSummary",
                                "assignments": "btnAssignments",
                                "links": "btnLinks",
                                "email": "btnEmail",
                                "attachments": "btnAttachments",
                                "notes2": "btnActionComments",
                                "history": "btnHistory"}

        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTab = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[contains(@name,'{orderTabDictionary[orderTab.lower()]}')]"
        orderTabTestFor = f"{targetTab}[@class='selected']"

        if (self.browser.safeClick(by=By.XPATH, element=targetTab, repeat=True, repeatUntilNewElementExists=orderTabTestFor)):
            b.log.info(f"Successfully navigated to serviceTab '{orderTab}'.")
            return True
        else:
            b.log.error(f"Failed to navigate to serviceTab '{orderTab}'.")
            return False
    def Order_GetCurrentOrderTab(self):
        targetTab = f"//div[contains(@id,'divTabButtons')][@class='tabButtons']/input[@class='selected']"
        return self.browser.find_element(by=By.XPATH,value=targetTab).get_attribute("value")
    # Helper method to easily navigate to linked tabs.
    # TODO add error handling here
    def Order_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTab = f"//table[contains(@id,'Detail_ucassociations_link_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'{linkedTabName.lower()}')]"
        targetTabTestFor = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH, element=targetTab, repeat=True, repeatUntilNewElementExists=targetTabTestFor)
        b.log.info(f"Successfully navigated to linkedTab '{linkedTabName}'")

    #endregion ====================Order Data & Navigation ===========================

    # region =====================People Data & Navigation ===========================

    # All these methods assume that TMA is currently on a People entry.

    # Reads basic information about a People entry in TMA. If a People object is supplied,
    # it reads the basic info into this object - otherwise, it returns a new People object.
    def People_ReadBasicInfo(self,peopleObject : People = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = People()
        peopleObject.location = self.currentLocation

        firstNameString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtFirstName__label')]/following-sibling::span"
        peopleObject.info_FirstName = self.browser.find_element(by=By.XPATH, value=firstNameString,timeout=10).text
        lastNameString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtLastName__label')]/following-sibling::span"
        peopleObject.info_LastName = self.browser.find_element(by=By.XPATH, value=lastNameString,timeout=10).text
        employeeIDString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_lblEmployeeID__label')]/following-sibling::span"
        peopleObject.info_EmployeeID = self.browser.find_element(by=By.XPATH, value=employeeIDString,timeout=10).text
        emailString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtEmail__label')]/following-sibling::span"
        peopleObject.info_Email = self.browser.find_element(by=By.XPATH, value=emailString,timeout=10).text
        employeeStatusString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_ddlpeopleStatus__label')]/following-sibling::span"
        employeeStatus = self.browser.find_element(by=By.XPATH, value=employeeStatusString,timeout=10).text
        if (employeeStatus == "Active"):
            peopleObject.info_IsTerminated = False
        else:
            peopleObject.info_IsTerminated = True
        OpCoString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_lblLocationCode1__label')]/following-sibling::span"
        peopleObject.info_OpCo = self.browser.find_element(by=By.XPATH, value=OpCoString,timeout=10).text
        employeeTitleString = "//div/div/fieldset/ol/li/span[contains(@id,'Detail_txtTitle__label')]/following-sibling::span"
        peopleObject.info_EmployeeTitle = self.browser.find_element(by=By.XPATH, value=employeeTitleString,timeout=10).text

        b.log.info("Successfully read.")
        return peopleObject
    # Reads an array of linked interactions of a people Object. If a People object is supplied,
    # it reads the info into this object - otherwise, it returns a new People object.
    def People_ReadLinkedInteractions(self,peopleObject : People = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = People()
        self.People_NavToLinkedTab("interactions")

        pageCountText = self.browser.find_element(by=By.XPATH, value=
        "//table/tbody/tr/td/span[contains(@id,'Detail_associations_link1_lblPages')]").text
        checkForSpace = False
        readNumbers = False
        pageCount = ''
        for i in pageCountText:
            if (i == 'f'):
                checkForSpace = True
                continue
            if (checkForSpace == True):
                checkForSpace = False
                readNumbers = True
                continue
            if (readNumbers == True):
                if (i == ')'):
                    break
                else:
                    pageCount += i
                    continue
        pageCount = int(pageCount)

        arrayOfLinkedIntNumbers = []
        for i in range(pageCount):
            arrayOfLinkedInteractionsOnPage = self.browser.find_elements(by=By.XPATH, value=
            "//table[contains(@id,'associations_link1_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[4]")
            arrayOfLinkedIntNumbersOnPage = []
            for j in arrayOfLinkedInteractionsOnPage:
                arrayOfLinkedIntNumbersOnPage.append(j.text)
            for j in arrayOfLinkedIntNumbersOnPage:
                if (j in arrayOfLinkedIntNumbers):
                    continue
                arrayOfLinkedIntNumbers.append(j)

            time.sleep(1)
            if ((i + 1) < pageCount):
                nextButton = self.browser.find_element(by=By.XPATH, value=
                "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$associations_link1$btnNext')][contains(@id,'Detail_associations_link1_btnNext')]")

                while True:
                    self.browser.safeClick(by=None, element=nextButton)
                    time.sleep(3)
                    currentPageNumber = ''
                    pageCountText = self.browser.find_element(by=By.XPATH, value=
                    "//table/tbody/tr/td/span[contains(@id,'Detail_associations_link1_lblPages')]").text
                    spaceCheck = False
                    for j in pageCountText:
                        if (spaceCheck == True):
                            if (j == ' '):
                                break
                            currentPageNumber += j
                        if (j == ' '):
                            spaceCheck = True
                            continue
                    currentPageNumber = int(currentPageNumber)

                    if (currentPageNumber == i + 2):
                        break
                    time.sleep(2)
                    continue
                continue

        peopleObject.info_LinkedInteractions = arrayOfLinkedIntNumbers
        b.log.info(f"Successfully read: {arrayOfLinkedIntNumbers}")
        return peopleObject
    # Reads an array of linked services of a people Object. If a People object is supplied,
    # it reads the info into this object - otherwise, it returns a new People object.
    # Reads an array of linked service numbers into info_LinkedServices
    # TODO This function likely predates the wheel. Look at it.
    def People_ReadLinkedServices(self,peopleObject : People = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = People()
        self.People_NavToLinkedTab("services")

        pageCountText = self.browser.find_element(by=By.XPATH, value=
        "//table/tbody/tr/td/span[contains(@id,'Detail_associations_link1_lblPages')]").text
        checkForSpace = False
        readNumbers = False
        pageCount = ''
        for i in pageCountText:
            if (i == 'f'):
                checkForSpace = True
                continue
            if (checkForSpace == True):
                checkForSpace = False
                readNumbers = True
                continue
            if (readNumbers == True):
                if (i == ')'):
                    break
                else:
                    pageCount += i
                    continue
        pageCount = int(pageCount)

        arrayOfLinkedServiceNumbers = []
        for i in range(pageCount):
            arrayOfLinkedServicesOnPage = self.browser.find_elements(by=By.XPATH, value=
            "//table[contains(@id,'associations_link1_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[5]")
            arrayOfLinkedServiceNumbersOnPage = []
            for j in arrayOfLinkedServicesOnPage:
                arrayOfLinkedServiceNumbersOnPage.append(j.text)
            for j in arrayOfLinkedServiceNumbersOnPage:
                if (j in arrayOfLinkedServiceNumbers):
                    continue
                arrayOfLinkedServiceNumbers.append(j)

            time.sleep(1)
            if ((i + 1) < pageCount):
                nextButton = self.browser.find_element(by=By.XPATH, value=
                "//table/tbody/tr/td/div/div/input[contains(@name,'Detail$associations_link1$btnNext')][contains(@id,'Detail_associations_link1_btnNext')]")

                while True:
                    self.browser.safeClick(by=None, element=nextButton)
                    time.sleep(3)
                    currentPageNumber = ''
                    pageCountText = self.browser.find_element(by=By.XPATH, value=
                    "//table/tbody/tr/td/span[contains(@id,'Detail_associations_link1_lblPages')]").text
                    spaceCheck = False
                    for j in pageCountText:
                        if (spaceCheck == True):
                            if (j == ' '):
                                break
                            currentPageNumber += j
                        if (j == ' '):
                            spaceCheck = True
                            continue
                    currentPageNumber = int(currentPageNumber)

                    if (currentPageNumber == i + 2):
                        break
                    time.sleep(2)
                    continue
                continue

        peopleObject.info_LinkedServices = arrayOfLinkedServiceNumbers
        b.log.info(f"Successfully read: {arrayOfLinkedServiceNumbers}.")
        return peopleObject
    # Simply reads in all information about a single People Entry. If a People object is supplied,
    # it reads the info into this object - otherwise, it returns a new People object.
    def People_ReadAllInformation(self,peopleObject : People = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(peopleObject is None):
            peopleObject = People()

        self.People_ReadBasicInfo(peopleObject)
        self.People_ReadLinkedInteractions(peopleObject)
        self.People_ReadLinkedServices(peopleObject)

        b.log.info("Successfully read")
        return peopleObject

    # Helper method to easily navigate to a linked tab on this People object.
    def People_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTab = f"//table[contains(@id,'Detail_associations_link1_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'{linkedTabName.lower()}')]"
        targetTabTestFor = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH, element=targetTab, repeat=True, repeatUntilNewElementExists=targetTabTestFor)
        b.log.info(f"Successfully navigated to linkedTabName '{linkedTabName}'")
    # Assuming that TMA is currently on a "People" page, this function navigates to
    # the 'Services' linked tab, then simply clicks create new.
    def People_CreateNewLinkedService(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.People_NavToLinkedTab("services")
        createNewString = "//table/tbody/tr/td/div/table/tbody/tr/td/a[contains(@id,'link1_lnkCreateNew')][text()='Create New Linked Item']"
        self.browser.safeClick(by=By.XPATH, element=createNewString)
        b.log.info("Successfully clicked on Create New Linked Service.")
    # This method opens up a service, given by a serviceID, turning the currently open tab
    # from a TMA people tab to a TMA service tab. Assumes we're currently on a people entry.
    # TODO error handling for when service does not exist.
    # TODO add condition wait for TMA header to load
    def People_OpenServiceFromPeople(self, serviceID):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.People_NavToLinkedTab("services")

        openServiceButtonPath = f"//tbody/tr[contains(@class,'sgvitems')]/td[text()='{serviceID}']/parent::tr/td/a[contains(@id,'lnkDetail')]"
        print(f"BEANS: {openServiceButtonPath}")

        # Try to find the created service, including support for flipping through pages (max 50)
        for i in range(50):
            openServiceButton = self.browser.find_element(by=By.XPATH, value=openServiceButtonPath,ignoreErrors=True)
            if(openServiceButton is None):
                nextPageButtonPath = "//input[contains(@id,'btnNext')][contains(@id,'Detail')]"
                nextPageButton = self.browser.find_element(by=By.XPATH,value=nextPageButtonPath)
                if(nextPageButton.get_attribute("disabled") != "true"):
                    pageCounterPath = "//span[contains(@id,'lblPages')][contains(@id,'Detail')]"
                    currentPageCounterText = self.browser.find_element(by=By.XPATH,value=pageCounterPath).text
                    nextPageButton.click()

                    #TODO kinda gluey, basically we're comparing the page number counters until we notice a change to
                    # attempt another check. Good or nah?
                    flippedPage = False
                    for i in range(30):
                        newPageCounterText = self.browser.find_element(by=By.XPATH, value=pageCounterPath).text
                        if(newPageCounterText != currentPageCounterText):
                            flippedPage = True
                            break
                        else:
                            time.sleep(1)

                    if(flippedPage):
                        continue
                    else:
                        raise ValueError("TMA took far too long to load a page change while searching for created service.")
            else:
                break

        targetAddress = openServiceButton.get_attribute("href")
        self.browser.get(targetAddress)
        time.sleep(3)
        self.readPage()
        b.log.info(f"Successfully opened linked service '{serviceID}' from people entry..")

    # endregion =====================People Data & Navigation ===========================

    # region ===================Equipment Data & Navigation ==========================

    # All these methods assume that TMA is currently on an Equipment entry.

    # Reads main information about a Equipment entry in TMA. If an Equipment object is supplied,
    # it reads the info into this object - otherwise, it returns a new Equipment object.
    def Equipment_ReadMainInfo(self,equipmentObject : Equipment = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if(equipmentObject is None):
            equipmentObject = Equipment()
        xpathPrefix = "//div/fieldset/ol/li"

        equipmentObject.info_MainType = self.browser.find_element(by=By.XPATH, value=
        xpathPrefix + "/span[contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite__lblType')]/following-sibling::span").text

        equipmentObject.info_SubType = Select(self.browser.find_element(by=By.XPATH, value=
        xpathPrefix + "/select[contains(@name,'Detail$ddlEquipmentTypeComposite$ddlEquipmentTypeComposite_ddlSubType')][contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite_ddlSubType')]")).first_selected_option.text
        equipmentObject.info_Make = Select(self.browser.find_element(by=By.XPATH, value=
        xpathPrefix + "/select[contains(@name,'Detail$ddlEquipmentTypeComposite$ddlEquipmentTypeComposite_ddlMake')][contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite_ddlMake')]")).first_selected_option.text
        equipmentObject.info_Model = Select(self.browser.find_element(by=By.XPATH, value=
        xpathPrefix + "/select[contains(@name,'Detail$ddlEquipmentTypeComposite$ddlEquipmentTypeComposite_ddlModel')][contains(@id,'Detail_ddlEquipmentTypeComposite_ddlEquipmentTypeComposite_ddlModel')]")).first_selected_option.text

        equipmentObject.info_IMEI = self.browser.find_element(by=By.XPATH, value=
        "//fieldset/fieldset/ol/li/input[contains(@name,'Detail$txtimei')][contains(@id,'Detail_txtimei')]").get_attribute(
            "value")
        equipmentObject.info_SIM = self.browser.find_element(by=By.XPATH, value=
        "//fieldset/fieldset/ol/li/input[contains(@name,'Detail$txtSIM')][contains(@id,'Detail_txtSIM')]").get_attribute(
            "value")

        b.log.info("Successfully read.")
        return equipmentObject

    # Write methods for various aspects of the equipment entry. If an Equipment object is supplied,
    # it pulls the info to write from this object. If not, it uses the "literalValue" object to write
    # instead.
    # TODO error reporting when neither an equipobj and literalval are supplied
    # TODO handle linked services better - no methods exist, just kinda assume its configured correctly in TMA
    def Equipment_WriteSubType(self,equipmentObject : Equipment = None,literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (equipmentObject.info_SubType is None):
            if(literalValue is None):
                b.log.warning(f"Didn't write, as literalValue is '{literalValue}'")
                return False
            else:
                valToWrite = literalValue
        else:
            valToWrite = equipmentObject.info_SubType
        subTypeDropdownString = f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlSubType')][contains(@name,'$ddlEquipmentTypeComposite_ddlSubType')]/option[text()='{valToWrite}']"
        self.browser.safeClick(by=By.XPATH, element=subTypeDropdownString)
        b.log.info(f"Successfully wrote '{literalValue}'")
        return True
    def Equipment_WriteMake(self,equipmentObject : Equipment = None,literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (equipmentObject.info_Make is None):
            if (literalValue is None):
                b.log.warning(f"Didn't write, as literalValue is '{literalValue}'")
                return False
            else:
                valToWrite = literalValue
        else:
            valToWrite = equipmentObject.info_Make
        makeDropdownString = f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlMake')][contains(@name,'$ddlEquipmentTypeComposite_ddlMake')]/option[text()='{valToWrite}']"
        self.browser.safeClick(by=By.XPATH, element=makeDropdownString)
        b.log.info(f"Successfully wrote '{literalValue}'")
        return True
    def Equipment_WriteModel(self,equipmentObject : Equipment = None,literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (equipmentObject.info_Model is None):
            if (literalValue is None):
                b.log.warning(f"Didn't write, as literalValue is '{literalValue}'")
                return False
            else:
                valToWrite = literalValue
        else:
            valToWrite = equipmentObject.info_Model
        modelDropdownString = f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlModel')][contains(@name,'$ddlEquipmentTypeComposite_ddlModel')]/option[text()='{valToWrite}']"
        self.browser.safeClick(by=By.XPATH, element=modelDropdownString)
        b.log.info(f"Successfully wrote '{literalValue}'")
        return True
    def Equipment_WriteIMEI(self,equipmentObject : Equipment = None,literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (equipmentObject.info_IMEI is None):
            if (literalValue is None):
                b.log.warning(f"Didn't write, as literalValue is '{literalValue}'")
                return False
            else:
                valToWrite = literalValue
        else:
            valToWrite = equipmentObject.info_IMEI
        IMEIString = "//div/fieldset/div/fieldset/fieldset/ol/li/input[contains(@id,'txtimei')]"
        IMEIElement = self.browser.find_element(by=By.XPATH, value=IMEIString)
        IMEIElement.clear()
        IMEIElement.send_keys(valToWrite)
        b.log.info(f"Successfully wrote '{literalValue}'")
        return True
    def Equipment_WriteSIM(self,equipmentObject : Equipment = None,literalValue = None):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        if (equipmentObject.info_SIM is None):
            if (literalValue is None):
                b.log.warning(f"Didn't write, as literalValue is '{literalValue}'")
                return False
            else:
                valToWrite = literalValue
        else:
            valToWrite = equipmentObject.info_SIM
        SIMString = "//div/fieldset/div/fieldset/fieldset/ol/li/input[contains(@id,'Detail_Equipment_txtSIM')]"
        SIMElement = self.browser.find_element(by=By.XPATH, value=SIMString)
        SIMElement.clear()
        SIMElement.send_keys(valToWrite)
        b.log.info(f"Successfully wrote '{literalValue}'")
        return True
    # Helper method to write ALL possible writeable info for this Equipment entry. Must specify
    # an Equipment object to pull information from - if info is None, it will not Write. If all
    # values are successfully written, it returns true - otherwise, returns false. Also contains
    # helper explicit waits for the dropdowns.
    def Equipment_WriteAll(self,equipmentObject : Equipment):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        self.Equipment_WriteSIM(equipmentObject)
        self.Equipment_WriteIMEI(equipmentObject)

        if(equipmentObject.info_SubType is None):
            return False
        self.Equipment_WriteSubType(equipmentObject)

        if(equipmentObject.info_Make is None):
            return False
        WebDriverWait(self.browser.driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlMake')][contains(@name,'$ddlEquipmentTypeComposite_ddlMake')]/option[text()='{equipmentObject.info_Make}']")))
        self.Equipment_WriteMake(equipmentObject)

        if(equipmentObject.info_Model is None):
            return False
        WebDriverWait(self.browser.driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//div/fieldset/div/fieldset/ol/li/select[contains(@id,'ddlEquipmentTypeComposite_ddlModel')][contains(@name,'$ddlEquipmentTypeComposite_ddlModel')]/option[text()='{equipmentObject.info_Model}']")))
        self.Equipment_WriteModel(equipmentObject)
    # Simply clicks on either "insert" or "update" on this equipment.
    # TODO more error handling
    def Equipment_InsertUpdate(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        insertButtonString = "//span/div/input[contains(@name,'ButtonControl1')][@value = 'Insert']"
        updateButtonString = "//span/div/input[contains(@name,'ButtonControl1')][@value = 'Update']"
        if(self.browser.elementExists(by=By.XPATH,value=insertButtonString)):
            self.browser.safeClick(by=By.XPATH, element=insertButtonString, repeat=False)
            self.browser.safeClick(by=By.XPATH, element=updateButtonString, repeat=True, repeatUntilNewElementExists=updateButtonString)
            b.log.info("Successfully inserted equipment.")
        elif(self.browser.elementExists(by=By.XPATH,value=updateButtonString)):
            self.browser.safeClick(by=By.XPATH, element=updateButtonString, repeat=True, repeatUntilNewElementExists=updateButtonString)
            b.log.info("Successfully updated equipment.")
        else:
            b.log.error("Couldn't InsertUpdate, as neither Insert nor Update were found.")

    # Helper method to easily navigate to a linked tab on this Equipment object.
    def Equipment_NavToLinkedTab(self, linkedTabName):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        targetTab = f"//table[contains(@id,'Detail_associations_link1_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[starts-with(text(),'{linkedTabName.lower()}')]"
        targetTabTestFor = f"//span[contains(text(),'{linkedTabName.lower()}')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"
        self.browser.safeClick(by=By.XPATH, element=targetTab, repeat=True, repeatUntilNewElementExists=targetTabTestFor)
        b.log.info(f"Successfully navigated to linkedTab '{linkedTabName}'")
    # This method navigates TMA from an equipment entry to a linked service.
    # Method assumes that Equipment is currently on the "Links" tab, and that
    # there is only one linked service.
    # TODO error handling
    def Equipment_NavToServiceFromEquipment(self):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        serviceTab = "//table[contains(@id,'Detail_associations_link1_gvTable2')]/tbody/tr[contains(@class,'gridviewbuttons')]/td/span[contains(text(),'services')]"
        serviceTabTestFor = "//span[contains(text(),'services')]/parent::td/parent::tr[contains(@class,'gridviewbuttonsSelected')]"

        self.browser.safeClick(by=By.XPATH, element=serviceTab, repeat=True, repeatUntilNewElementExists=serviceTabTestFor)

        linkedService = "//table[contains(@id,'associations_link1_sgvAssociations')]/tbody/tr[contains(@class,'sgvitems')]/td[2]"

        for i in range(12):
            if ("https://tma4.icomm.co/tma/Authenticated/Client/Services" in self.browser.get_current_url()):
                b.log.info("Successfully navigated to service from equipment entry.")
                return True
            else:
                self.browser.implicitly_wait(10)
                self.browser.safeClick(by=By.XPATH, element=linkedService)
                time.sleep(5)
        b.log.error("Could not successfully navToServiceFromEquipment.")
        return False
    # This method checks whether we're on the "Equipment Type" selection screen, and if so,
    # selects the given equipment type. If we're not on that screen, this function merely
    # returns false.
    # TODO LIES! LIES LIES LIES!!!!
    def Equipment_SelectEquipmentType(self,equipmentType):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        equipmentTypeXPath = f"//body/form/div/div/fieldset/a[contains(@id,'ctl00_modalLinkButton')][text()='{equipmentType}']"
        self.browser.safeClick(by=By.XPATH, element=equipmentTypeXPath,repeatUntilElementDoesNotExist=equipmentTypeXPath)
        b.log.debug(f"Successfully selected equipmentType '{equipmentType}'")



    # endregion ===================Equipment Data & Navigation ==========================

    # region ======================Assignment Navigation =============================

    # All these methods assume that TMA is currently on the assignment wizard.
    # TODO add supported reading of assignment info into assignment objects.


    # The "Sysco Method" of creating assignments - looks up the Account/Vendor first, then specifies
    # the site from a list of available sites. If an AssignmentObject is provided, this method will
    # try to build an exact copy of it (and will ignore client,vendor, and siteCode variables)
    # TODO The above comment is a lie. This does not YET support AssignmentObjects - only literals.
    # TODO also proper error handling.
    # TODO this function is insanely un-optimized. Optimize it foo
    def Assignment_BuildAssignmentFromAccount(self,client,vendor,siteCode):
        self.browser.switchToTab(self.currentTMATab[0],self.currentTMATab[1])

        # Temporarily increase implicit wait, since assignment wizard is highly unstable.
        self.browser.implicitly_wait(5)

        siteCode = str(siteCode).zfill(3)

        b.log.info(f"Attempting to build assignment off of this site code: {siteCode}")

        existingAccountsButton = "//td/div/div/a[contains(@id,'wizFindExistingAssigment_lnkFindAccount')]"
        accountsTabTestFor = "//a[contains(@id,'ctl01_SideBarButton')][text()='Accounts']/parent::div"
        self.browser.safeClick(by=By.XPATH, element=existingAccountsButton, repeat=True, repeatUntilNewElementExists=accountsTabTestFor)

        self.browser.implicitly_wait(5)

        # Always select "Wireless" as assignment type (for now)
        wirelessTypeDropdownSelection = self.browser.find_element(by=By.XPATH, value="//tr/td/div/fieldset/ol/li/select[contains(@id,'wizFindExistingAssigment_ddlAccountType')]/option[text()='Wireless']")
        self.browser.safeClick(by=By.XPATH, element=wirelessTypeDropdownSelection)

        # Select the vendor from the dropdown.
        vendorDropdownSelectionString = f"//tr/td/div/fieldset/ol/li/select[contains(@id,'wizFindExistingAssigment_ddlVendor')]/option[text()='{vendor}']"
        if(not self.browser.elementExists(by=By.XPATH,value=vendorDropdownSelectionString)):
            b.log.error(f"Incorrect vendor selected to make assignment: {vendor}")
        vendorDropdownSelection = self.browser.find_element(by=By.XPATH, value=vendorDropdownSelectionString)
        self.browser.safeClick(by=By.XPATH, element=vendorDropdownSelection)

        accountNumber = b.clients[client]["Accounts"][vendor]

        # Now select the appropriate account as found based on the vendor.
        accountNumberDropdownSelectionString = f"//tr/td/div/fieldset/ol/li/select[contains(@id,'wizFindExistingAssigment_ddlAccount')]/option[text()='{accountNumber}']"
        accountNumberDropdownSelection = WebDriverWait(self.browser.driver,10).until(EC.presence_of_element_located((By.XPATH, accountNumberDropdownSelectionString)))
        self.browser.safeClick(by=By.XPATH, element=accountNumberDropdownSelection)

        searchedAccountSelectButton = "//tr/td/div/fieldset/ol/li/input[contains(@id,'wizFindExistingAssigment_btnSearchedAccountSelect')]"
        sitesTabTestFor = "//a[contains(@id,'ctl02_SideBarButton')][text()='Sites']/parent::div"
        self.browser.safeClick(by=By.XPATH, element=searchedAccountSelectButton, repeat=True, repeatUntilNewElementExists=sitesTabTestFor)

        # To find the valid site, we will flip through all pages until we locate our exact match.
        pageCountText = self.browser.find_element(by=By.XPATH, value="//table/tbody/tr/td/span[contains(@id,'wizFindExistingAssigment')][contains(@id,'lblPages')]").text
        pageCount = int(pageCountText.split("of ")[1].split(")")[0])

        # We know that this is the element we will eventually click on, once it exists.
        targetSiteString = f"//table[contains(@id,'sgvSites')]/tbody/tr[contains(@class,'sgvitems')]/td[1][starts-with(text(),{siteCode})]"

        # This will get us a list of all sites present on the page.
        allSitesOnPageString = f"//table[contains(@id,'sgvSites')]/tbody/tr[contains(@class,'sgvitems')]/td[1]"

        # Next button CSS_SELECTOR string.
        nextButtonString = "#wizLinkAssignments_wizFindExistingAssigment_gvpSites_btnNext"

        # Here we loop through each site, looking for our specified site code. b
        foundTargetCode = False
        currentPageNumber = 0
        targetSiteElement = None
        while True:
            previousPageNumber = currentPageNumber
            # Here we test to make sure we've actually flipped the page, if necessary.
            while (currentPageNumber == previousPageNumber):
                pageCountTextString = "//table/tbody/tr/td/span[contains(@id,'wizFindExistingAssigment')][contains(@id,'lblPages')]"
                # TODO We GOTTA find a better way to do this shit!
                for i in range(5):
                    try:
                        pageCountTextElement = WebDriverWait(self.browser.driver,10).until(Browser.wait_for_non_stale_element((By.XPATH,pageCountTextString)))
                        pageCountText = pageCountTextElement.text
                        break
                    except selenium.common.exceptions.StaleElementReferenceException:
                        time.sleep(0.2)
                        continue
                currentPageNumber = int(pageCountText.split(" of ")[0].split("(Page ")[1])
                time.sleep(0.2)
            allSitesOnPage = self.browser.find_elements(by=By.XPATH,value=allSitesOnPageString)
            for foundSiteElement in allSitesOnPage:
                foundSiteCode = foundSiteElement.text.split("-")[0]
                if(foundSiteCode == siteCode):
                    targetSiteElement = foundSiteElement
                    foundTargetCode = True
                    break

            if(foundTargetCode):
                break
            #TODO proper error reporting.
            elif(currentPageNumber >= pageCount):
                b.log.error(f"Could not find site code '{siteCode}' in assignment wizard.")
                return False
            else:
                # Flip to the next page.
                self.browser.find_element(by=By.CSS_SELECTOR,value=nextButtonString).click()

        # If we got here, that means we've now found our element, so we can click on it.
        # TODO rarely, this click doesn't succeed. WHY????
        self.browser.safeClick(by=By.XPATH, element=targetSiteElement,repeat=True,repeatUntilElementDoesNotExist=targetSiteElement)

        # At this point, what will pop up next is completely and utterly unpredictable. To remedy this,
        # we use a while loop to continuously react to each screen that pops up next, until we find the
        # "make assignment" screen.
        currentTabString = "//table[contains(@id,'SideBarList')]/tbody/tr/td/div[starts-with(@style,'background-color: White')]/a"
        visitedTabs = []
        while True:
            b.log.debug("Checking for next page in assignment wizard...")

            currentTab = self.browser.find_element(by=By.XPATH,value=currentTabString).text.lower()
            # If TMA pops up with "Company" selection. This usually only happens with OpCo 000,in which case
            # we'd select 000. Since I know of no other scenarios where Company pops up, for now, if it pops up
            # on an OpCo that's NOT 000, this will throw an error.
            if (currentTab == "company"):
                b.log.debug("Found company page on assignment wizard")
                if (siteCode == "000"):
                    selectorFor000String = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='000']"
                    selectedCompanyTab = "//a[contains(@id,'ctl03_SideBarButton')][text()='Company']/parent::div"
                    self.browser.safeClick(by=By.XPATH, element=selectorFor000String, repeat=True, repeatUntilElementDoesNotExist=selectedCompanyTab)
                else:
                    b.log.error("Company tab is asking for information on a non-000 OpCo! Edits will be required. God help you!")
                    return False

            # If TMA pops up with "Division" selection. Again, this usually only occurs (to my knowledge) on 000
            # OpCo, in which case the only selectable option is "Corp Offices". If this shows up on a non-000
            # OpCo, the method will throw an error.
            elif (currentTab == "division"):
                b.log.debug("Found division page on assignment wizard")
                if (siteCode == "000"):
                    selectorForCorpOfficesString = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='Corp Offices']"
                    selectedDivisionTab = "//a[contains(@id,'ctl05_SideBarButton')][text()='Division']/parent::div"
                    self.browser.safeClick(by=By.XPATH, element=selectorForCorpOfficesString, repeat=True, repeatUntilElementDoesNotExist=selectedDivisionTab)
                else:
                    b.log.error("Division tab is asking for information on a non-000 OpCo! Edits will be required. God help you!")
                    return False

            # If TMA pops up with "Department" selection. In almost every case, I believe we should be selecting
            # Wireless-OPCO. The one exception seems to be, of course, OpCo 000. In that case, we select
            # "Wireless-Corp Liable".
            elif (currentTab == "department"):
                b.log.debug("Found department page on assignment wizard")
                selectedDepartmentTab = "//a[contains(@id,'ctl06_SideBarButton')][text()='Department']/parent::div"
                if (siteCode == "000"):
                    selectorForCorpLiableString = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='Wireless-Corp Liable']"
                    self.browser.safeClick(by=By.XPATH, element=selectorForCorpLiableString, repeat=True, repeatUntilElementDoesNotExist=selectedDepartmentTab)
                else:
                    selectorForWirelessOPCOString = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='Wireless-OPCO']"
                    self.browser.safeClick(by=By.XPATH, element=selectorForWirelessOPCOString, repeat=True, repeatUntilElementDoesNotExist=selectedDepartmentTab)

            # If TMA pops up with "CostCenters" selection. We've been told to essentially ignore this, and pick whatever
            # the last option is. However, for OpCo 000, it seems to be better to select "CAFINA".
            elif (currentTab == "costcenters"):
                b.log.debug("Found cost centers page on assignment wizard")
                selectedCostCentersTab = "//a[contains(@id,'ctl04_SideBarButton')][text()='CostCenters']/parent::div"
                # FOR NOW, even in the case of 000, we select the bottom choice. This might change.
                #if (siteCode == "000"):
                #    selectorForCAFINAString = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td[text()='CAFINA']"
                #    self.browser.safeClick(by=By.XPATH, element=selectorForCAFINAString, repeat=True, repeatUntilElementDoesNotExist=selectedCostCentersTab)
                #else:
                selectorForAllEntries = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td"
                allEntries = self.browser.find_elements(by=By.XPATH, value=selectorForAllEntries)
                entriesQuantity = len(allEntries)
                lastEntry = allEntries[entriesQuantity - 1]
                self.browser.safeClick(by=By.XPATH, element=lastEntry, repeat=True, repeatUntilElementDoesNotExist=selectedCostCentersTab)

            # If TMA pops up with "ProfitCenter" selection. This is essentially the same as CostCenters, with no necessary
            # special exception for OpCo 000.
            elif (currentTab == "profitcenter"):
                b.log.debug("Found profit center page on assignment wizard")
                selectorForAllEntries = "//table/tbody/tr/td/div/div/table/tbody/tr[contains(@class,'sgvitems')]/td"
                selectedProfitCenterTab = "//a[contains(@id,'ctl08_SideBarButton')][text()='ProfitCenter']/parent::div"
                allEntries = self.browser.find_elements(by=By.XPATH, value=selectorForAllEntries)
                entriesQuantity = len(allEntries)
                lastEntry = allEntries[entriesQuantity - 1]
                self.browser.safeClick(by=By.XPATH, element=lastEntry, repeat=True, repeatUntilElementDoesNotExist=selectedProfitCenterTab)

            # If TMA brings us to "Finalize" we exit the loop as we've finished with making the assignment.
            elif (currentTab == "finalize"):
                b.log.debug("Found finalize page of assignment wizard!")
                break

            # Other cases.
            else:
                # Sometimes sites will still register - just skip it if so. Any other case REALLY shouldn't ever happen.
                if(currentTab != "sites"):
                    b.log.error(f"Found strange value for assignment wizard tab: {currentTab}")

        yesMakeAssignmentButton = "//table/tbody/tr/td/div/ol/li/a[contains(@id,'wizFindExistingAssigment_lnkLinkAssignment')][text()='Yes, make the assignment.']"
        self.browser.safeClick(by=By.XPATH, element=yesMakeAssignmentButton, repeat=True, repeatUntilElementDoesNotExist=yesMakeAssignmentButton)
        b.log.debug("Successfully created assignment.")

        # Revert implicit wait back.
        self.browser.implicitly_wait(1)

        # Since the account-assignment method can take wildly different paths, ESPECIALLY for
        # Sysco, we use a while loop to organically respond to whatever options is presents
        # us with after the site is selected.
    # The "LYB Method" of creating assignments - looks up the Site first, then specifies the Vendor
    # and account afterwards.
    # TODO This function is fucking ancient, and almost 100% doesn't work. Needs large rewrite.
    '''
    def Assignment_BuildAssignmentFromSite(self,client,vendor,siteCode):
        existingSitesButton = "//td/div/div/a[contains(@id,'wizFindExistingAssigment_lnkFindSite')]"
        sitesTabTestFor = "//a[contains(@id,'ctl02_SideBarButton')][text()='Sites']/parent::div"
        self.browser.safeClick(by=By.XPATH, element=existingSitesButton, repeat=True, repeatUntilNewElementExists=sitesTabTestFor)

        self.browser.implicitly_wait(5)

        locationCodeSelection = self.browser.find_element(by=By.XPATH, value=
        "//div/fieldset/ol/li/select[contains(@name,'wizFindExistingAssigment$ddlSiteCodes')]/option[text()='" + self.info_SiteCode + "']")
        self.browser.safeClick(by=None, element=locationCodeSelection)

        selectButton = "//div/fieldset/ol/li/input[contains(@name,'wizFindExistingAssigment$btnSearchedSiteSelect')][contains(@id,'wizFindExistingAssigment_btnSearchedSiteSelect')]"
        vendorColumnTestFor = "//table[contains(@id,'wizFindExistingAssigment_sgvAccounts')]/tbody/tr/th/a[text()='Vendor']"
        self.browser.safeClick(by=By.XPATH, element=selectButton, repeat=True, repeatUntilNewElementExists=vendorColumnTestFor)

        pageCountText = self.browser.find_element(by=By.XPATH, value=
        "//table/tbody/tr/td/span[contains(@id,'wizFindExistingAssigment')][contains(@id,'lblPages')]").text
        checkForSpace = False
        readNumbers = False
        pageCount = ''
        for i in pageCountText:
            if (i == 'f'):
                checkForSpace = True
                continue
            if (checkForSpace == True):
                checkForSpace = False
                readNumbers = True
                continue
            if (readNumbers == True):
                if (i == ')'):
                    break
                else:
                    pageCount += i
                    continue
        pageCount = int(pageCount)
        for i in range(pageCount):
            validAccount = "//table[contains(@id,'wizFindExistingAssigment_sgvAccounts')]/tbody/tr[(contains(@class,'sgvitems')) and not(contains(@class,'sgvaccounts closed'))]/td[text()='" + self.info_Vendor + "']/following-sibling::td[text()='" + self.thisAccountDict.get(
                self.info_Vendor) + "']/parent::tr"
            if (self.TMADriver.browser.elementExists(by=By.XPATH, value=validAccount)):
                break
            else:
                if ((i + 1) < pageCount):
                    nextButton = "//table/tbody/tr/td/div/div/input[contains(@id,'wizFindExistingAssigment')][contains(@id,'btnNext')][contains(@name,'btnNext')]"
                    while True:
                        self.TMADriver.browser.safeClick(by=By.XPATH, element=nextButton)
                        time.sleep(3)
                        currentPageNumber = ''
                        pageCountText = self.TMADriver.browser.find_element(by=By.XPATH, value=
                        "//table/tbody/tr/td/span[contains(@id,'wizFindExistingAssigment')][contains(@id,'lblPages')]").text
                        spaceCheck = False
                        for j in pageCountText:
                            if (spaceCheck == True):
                                if (j == ' '):
                                    break
                                currentPageNumber += j
                            if (j == ' '):
                                spaceCheck = True
                                continue
                        currentPageNumber = int(currentPageNumber)

                        if (currentPageNumber == i + 2):
                            break
                        time.sleep(2)
                        continue
                    continue
                else:
                    print(
                        "ERROR: Site '" + self.info_SiteCode + "' does not contain proper account for '" + self.info_Vendor + "'.")
                    return False

        validAccount = "//table[contains(@id,'wizFindExistingAssigment_sgvAccounts')]/tbody/tr[(contains(@class,'sgvitems')) and not(contains(@class,'sgvaccounts closed'))]/td[text()='" + self.info_Vendor + "']/following-sibling::td[text()='" + self.__accountNumber + "']/parent::tr"
        yesMakeAssignmentTestFor = "//table/tbody/tr/td/div/ol/li/a[contains(@id,'wizFindExistingAssigment_lnkLinkAssignment')][text()='Yes, make the assignment.']"

        self.TMADriver.browser.safeClick(by=By.XPATH, element=validAccount, timeout=60, repeat=True, repeatUntilNewElementExists=yesMakeAssignmentTestFor)

        print(
            "INFO: Successfully made assignment to site '" + self.info_SiteCode + "' and vendor '" + self.info_Vendor + "'.")
        yesMakeAssignmentButton = "//table/tbody/tr/td/div/ol/li/a[contains(@id,'wizFindExistingAssigment_lnkLinkAssignment')][text()='Yes, make the assignment.']"
        self.TMADriver.browser.safeClick(by=By.XPATH, element=yesMakeAssignmentButton, repeat=True, repeatUntilElementDoesNotExist=yesMakeAssignmentButton)
        return True
    '''

    # endregion ======================Assignment Navigation =============================

class MultipleTMAPopups(Exception):
    def __init__(self):
        super().__init__("Expected a single TMA popup to appear, but found multiple.")


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


br = Browser()
t = TMADriver(br)
t.logInToTMA()
input("search for andram?")
t.navToLocation(TMALocation(client="Sysco",entryType="People",entryID="asup5134"))
#input("search for francois?")
#t.navToLocation(TMALocation(client="Sysco",entryType="People",entryID="fexp3586"))
#input("search for jingles?")
#t.navToLocation(TMALocation(client="Sysco",entryType="People",entryID="jjin7173"))

#input("search for andram's phone?")
#t.navToLocation(TMALocation(client="Sysco",entryType="Service",entryID="437-247-0448"))
#input("search for francois' phone?")
#t.navToLocation(TMALocation(client="Sysco",entryType="Service",entryID="438-336-7857"))
#input("search for jingle's phone?")
#t.navToLocation(TMALocation(client="Sysco",entryType="Service",entryID="317-372-6252"))