import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from shaman2.selenium.browser import Browser
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.common.config import mainConfig
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.utilities.shaman_utils import convertServiceIDFormat,normalizeName, BAD_ELEMENT_EXCEPTIONS
from shaman2.utilities.action_handler import action,ActionResult,StatusCode
from shaman2.network.sheets_sync import syscoData

class VerizonDriver:

    # An already created browserObject must be hooked into the VerizonDriver to work.
    # Verizon runs entirely within the browser object.
    def __init__(self,browserObject : Browser):
        logMessage = "Initialized new VerizonDriver object"
        self.browser = browserObject

        if ("Verizon" in self.browser.tabs.keys()):
            self.browser.closeTab("Verizon")
            logMessage += ", and closed existing Verizon tab."
        else:
            logMessage += "."
        self.browser.openNewTab("Verizon")

        self.currentTabIndex = 0
        self.previousTabIndex = 0

        log.info(logMessage)

    #region === Site Navigation ===

    # This method sets the page to the Verizon log in screen, then goes through the process of
    # logging in.
    @action()
    def logInToVerizon(self,manual=False):
        self.browser.switchToTab("Verizon")

        # Test if already signed in.
        if("https://mb.verizonwireless.com" in self.browser.current_url):
            log.info("Already logged in to Verizon.")
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            self.browser.get("https://mblogin.verizonwireless.com/account/business/login/unifiedlogin")
            if(manual):
                log.info("Prompted user to log in to Verizon manually...")
                playsoundAsync(paths["media"] / "shaman_attention.mp3")
                userResponse = input("Press enter once logged in to Verizon. Press any other key to cancel.")
                if(userResponse != ""):
                    log.warning("User cancelled manual login process.")
                    return ActionResult(status=StatusCode.USER_ABORT)
                log.info("User finished manual login process.")
            else:
                # Build the map of possible login pages.
                usernameFieldXPath = "//input[@id='pwdUserID']"
                passwordFieldXPath = "//input[@type='password']"
                howDoYouWantToLogInHeaderXPath = "//*[normalize-space(text())='How do you want to log in?']"
                otpHeaderXPath = "//*[normalize-space(text())='Select a verification method']"
                homepageXPath = "//label[contains(@class,'custom-search-input-label')][contains(normalize-space(text()),'Welcome,')]"
                loginPagesMap = {usernameFieldXPath : "Username", passwordFieldXPath : "Password",
                                 howDoYouWantToLogInHeaderXPath : "HDYWTLI", otpHeaderXPath : "OTP",homepageXPath : "Homepage"}

                # Begin loop to manage login logic.
                for i in range(10):
                    # First, get the current page we're on.
                    foundElement,pageName = self.browser.searchForElement(by=By.XPATH,value=loginPagesMap,
                                                                          testClickable=True,testLiteralClick=True,
                                                                          timeout=30,raiseError=True,logError=False)

                    # If we're on the username page, foundElement is our usernameField.
                    if(pageName == "Username"):
                        foundElement.clear()
                        foundElement.send_keys(mainConfig["authentication"]["verizonUser"])
                        foundElement.send_keys(Keys.ENTER)
                        # Wait for username field to disappear before proceeding.
                        self.browser.searchForElement(element=foundElement,timeout=60,testNotStale=False,
                                                      invertedSearch=True,raiseError=True)
                    # If we're on the password page, foundElement is our passwordField.
                    elif(pageName == "Password"):
                        foundElement.clear()
                        foundElement.send_keys(mainConfig["authentication"]["verizonPass"])
                        foundElement.send_keys(Keys.ENTER)
                        # Wait for pass log in header to disappear before proceeding.
                        self.browser.searchForElement(element=foundElement, timeout=60, testNotStale=False,
                                                      invertedSearch=True)
                    # If we're on the "How Do You Want To Log In" page, we just need to find and click "log in with password" option.
                    elif(pageName == "HDYWTLI"):
                        logInWithPasswordOptionXPath = "//div[@class='pwdless_option_text']/a[normalize-space(text())='Password']"
                        logInWithPasswordOption = self.browser.searchForElement(by=By.XPATH,value=logInWithPasswordOptionXPath,testClickable=True,timeout=30)
                        logInWithPasswordOption.click()
                        # Wait for HDYWTLI header to disappear before proceeding.
                        self.browser.searchForElement(element=foundElement, timeout=60,testNotStale=False,
                                                      invertedSearch=True)
                    # If we're on the OTP page, we need to get the OTP from the user.
                    elif(pageName == "OTP"):
                        playsoundAsync(paths['media'] / "shaman_attention.mp3")
                        print("VERIZON WIRELESS: Requesting one time code. Please enter 2FA code - you have 3 minutes before self-destruction.")
                        # Wait for HomePage to load deliberately here.
                        self.browser.searchForElement(by=By.XPATH,value=homepageXPath, timeout=180,testClickable=True,testLiteralClick=True)
                    # If we're at the HomePage screen, we're done.
                    elif(pageName == "Homepage"):
                        self.testForUnregisteredPopup()
                        return ActionResult(status=StatusCode.SUCCESS)

                # If we've left the loop, that means we went through 10 iterations of login logic without exiting,
                # signaling a bizarre process change.
                log.error(f"Went through more than 10 iterations of login logic without exiting - review process.",exc_info=True)
                return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # This method tests for and handles the "X users are still unregistered" popup that sometimes occurs on the
    # Homescreen page.
    @action()
    def testForUnregisteredPopup(self):
        unregisteredUsersPopupXPath = "//app-notification-dialog//div[contains(text(),'users are still unregistered')]/parent::div/parent::app-notification-dialog"
        unregisteredUsersCloseButtonXPath = f"{unregisteredUsersPopupXPath}//i[contains(@class,'icon-close')]"

        unregisteredUsersCloseButton = self.browser.searchForElement(by=By.XPATH,value=unregisteredUsersCloseButtonXPath,timeout=2)
        if(unregisteredUsersCloseButton):
            unregisteredUsersCloseButton.click()
            log.info("Closed unregistered users popup.")
            self.browser.searchForElement(by=By.XPATH,value=unregisteredUsersCloseButtonXPath,timeout=30,invertedSearch=True,
                                          testClickable=True)
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            log.debug("Found no unregistered popup to close.")
            return ActionResult(status=StatusCode.SUCCESS)

    # This method navigates to the MyBiz homescreen from whatever page Verizon is currently on.
    @action()
    def navToHomescreen(self):
        self.browser.switchToTab("Verizon")

        # Go to the link directly.
        self.browser.get("https://mb.verizonwireless.com/mbt/secure/index?appName=esm#/esm/dashboard")

        # Wait for shop new device button to confirm page load.
        testResult = self.browser.searchForElement(by=By.XPATH,value="//label[contains(@class,'custom-search-input-label')][contains(normalize-space(text()),'Welcome,')]",
                                      timeout=30, testClickable=True)
        if(testResult):
            # TODO ????? deal with status code here too for unregistered popup DO WE EVEN NEED IT????
            #self.testForUnregisteredPopup()
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            log.error(RuntimeError(f"Verizon homescreen never loaded!"),exc_info=True)
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # This method navigates to the Verizon order viewer.
    @action()
    def navToOrderViewer(self):
        self.browser.switchToTab("Verizon")
        # Yes, the typo is intentional lmfao
        viewOrdersHeaderXPath = "//div[contains(@class,'view-orders-conatiner')]//h2[contains(text(),'Orders')]"

        if(not self.browser.searchForElement(by=By.XPATH,value=viewOrdersHeaderXPath,timeout=2)):
            # Navigate to the link directly.
            self.browser.get("https://mb.verizonwireless.com/mbt/secure/index?transType=ORDERSTATUS#/vieworders")

            # Test to ensure we got to the expected page.
            testResult = self.browser.searchForElement(by=By.XPATH,value=viewOrdersHeaderXPath,timeout=60,
                                          testClickable=True,testLiteralClick=True)
            if(testResult):
                return ActionResult(status=StatusCode.SUCCESS)
            else:
                log.error(RuntimeError(f"Verizon order viewer never loaded!"), exc_info=True)
                return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
        return ActionResult(status=StatusCode.SUCCESS)

    #endregion === Site Navigation ===

    #region === Order Viewer ===

    # This method reads the entire displayed order and converts it into a formatted Python
    # dictionary. readUnloadingOrder is a special method for when Verizon orders show up but won't load
    # for unknown reasons, so that it still returns something.
    @action()
    def OrderViewer_ReadDisplayedOrder(self):
        self.browser.switchToTab("Verizon")
        order = {}

        # Test to prevent "No results found"
        if(self.browser.searchForElement(by=By.XPATH, value="//div[contains(text(),'No Results Found')]",timeout=1)):
            log.warning("Tried to read a displayed Verizon order, but got 'No Results Found' on the order viewer.")
            return ActionResult(status=StatusCode.NO_RESULTS)

        # Header Values
        headerRowPrefixXPath = "//tbody[@class='p-element p-datatable-tbody']/tr[1]"
        order["OrderNumber"] = self.browser.searchForElement(by=By.XPATH,value=f"{headerRowPrefixXPath}/td[1]/div",timeout=60).text
        order["WirelessNumber"] = self.browser.searchForElement(by=By.XPATH,value=f"{headerRowPrefixXPath}/td[2]/a").text
        order["OrderDate"] = self.browser.searchForElement(by=By.XPATH,value=f"{headerRowPrefixXPath}/td[3]/div").text
        order["ProductSolution"] = self.browser.searchForElement(by=By.XPATH,value=f"{headerRowPrefixXPath}/td[4]/div").text
        order["OrderType"] = self.browser.searchForElement(by=By.XPATH,value=f"{headerRowPrefixXPath}/td[5]/div").text
        order["Status"] = self.browser.searchForElement(by=By.XPATH,value=f"{headerRowPrefixXPath}/td[6]/div").text

        #region === Body Values ===
        # Since these values may not yet exist if the order is not completed, we catch any NoSuchElementExceptions and
        # store a None value instead.
        bodyValueTimeout = 30

        # Ace Order Number/Loc Code
        aceLocNumberField = self.browser.searchForElement(by=By.XPATH,value="//div[text()='Ace/Loc Order number']/following-sibling::div",timeout=bodyValueTimeout)
        if(aceLocNumberField):
            aceLocMatch = re.search(r"Order #: (\d+) Loc: (\w+)", aceLocNumberField.text)
            order["AceOrderNumber"] = aceLocMatch.group(1)
            order["AceLocationNumber"] = aceLocMatch.group(2)
        else:
            order["AceOrderNumber"] = None
            order["AceLocationNumber"] = None
            # We lower bodyValueTimeout, as this likely means the order isn't loading due to Verizon's ingenuinity
            bodyValueTimeout = 2

        # Ship Date
        shipDateField = self.browser.searchForElement(by=By.XPATH,value="//div[text()='Ship Date']/following-sibling::div",timeout=bodyValueTimeout)
        order["ShipDate"] = shipDateField.text if shipDateField else None

        # Ship To
        shipToField = self.browser.searchForElement(by=By.XPATH, value="//div[text()='Ship To']/following-sibling::div/address",timeout=bodyValueTimeout)
        order["ShipTo"] = shipToField.text if shipDateField else None

        # Courier
        courierField = self.browser.searchForElement(by=By.XPATH, value="//div[text()='Courier']/following-sibling::div",timeout=bodyValueTimeout)
        order["Courier"] = courierField.text if courierField else None

        # Tracking
        trackingField = self.browser.searchForElement(by=By.XPATH, value="//div[text()='Tracking Number']/following-sibling::div/a",timeout=bodyValueTimeout)
        order["TrackingNumber"] = trackingField.text if trackingField else None

        # Package Details #TODO temporarily (permanently?) disabled. See Shaman1 for past implementation
        order["PackageDetails"] = {}

        # Line Information
        lineInformationButton = self.browser.searchForElement(by=By.XPATH, value="//a[contains(text(),'Line Information')]",timeout=bodyValueTimeout)
        if(lineInformationButton):
            self.browser.safeClick(element=lineInformationButton,timeout=bodyValueTimeout)
            lineInformation = self.browser.searchForElement(by=By.XPATH,value="//div[@aria-labelledby='tab2']/ul/div/li/div[contains(@class,'column-2')]",timeout=bodyValueTimeout)
            imeiMatch = re.compile(r'Device ID: (\d+)').search(lineInformation.text)
            order["IMEI"] = imeiMatch.group(1) if imeiMatch else None
            simMatch = re.compile(r'SIM ID: (\d+)').search(lineInformation.text)
            order["SIM"] = simMatch.group(1) if simMatch else None
        # Sometimes, there just isn't any line information. Cause of course there's not. No reason as far as I can
        # tell, sometimes Verizon just... doesn't show it.
        else:
            order["IMEI"] = None
            order["SIM"] = None
            log.warning(f"Order viewer isn't loading line information for order {order['OrderNumber']}. Proceeding without IMEI etc.")

        #endregion === Body Values ===

        log.debug(f"Read this Verizon order: {order}")
        return ActionResult(status=StatusCode.SUCCESS,data=order)

    # This method uses an orderNumber to search for an order on the OrderViewer. Returns True if the order is
    # found, and False if it isn't found. #TODO there used to be "Are you still there?" detection in here, but we're going to move it externally. See Shaman1 for implementation
    @action()
    def OrderViewer_SearchOrder(self,orderNumber : str):
        self.browser.switchToTab("Verizon")

        searchField = self.browser.find_element(by=By.XPATH,value="//input[@id='search']")
        searchField.clear()
        searchField.send_keys(orderNumber)

        searchButton = self.browser.find_element(by=By.XPATH,value="//span[@id='grid-search-icon']")
        searchButton.click()
        # Wait for the Order header to become clickable again (meaning loading has finished.) Yes, the typo is
        # intentional lmfao
        viewOrdersHeaderXPath = "//div[contains(@class,'view-orders-conatiner')]//h2[contains(text(),'Orders')]"
        self.browser.searchForElement(by=By.XPATH, value=viewOrdersHeaderXPath, minSearchTime=3,timeout=120,
                                      testClickable=True, testLiteralClick=True)

        foundOrderLocator = self.browser.searchForElement(by=By.XPATH,value=f"//div[text()='{orderNumber}']",timeout=1)
        if(foundOrderLocator):
            # Helper section to ensure that Verizon doesn't decide to randomly collapse the order on lookup for unknown reasons.
            foundOrderExpandIconXPath = f"//div[text()='{orderNumber}']/following-sibling::td/div/span[@class='onedicon icon-plus-small']"
            expandIcon = self.browser.searchForElement(by=By.XPATH,value=foundOrderExpandIconXPath,timeout=2)
            if(expandIcon):
                expandIcon.click()
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.NO_RESULTS)

    # This method sets the "view date" dropdown to the given selection (30, 60, 90, 120, 150, 180 Days and 13 months)
    @action()
    def OrderViewer_UpdateOrderViewDropdown(self,viewPeriod : str):
        viewPeriod = viewPeriod.title()
        validChoices = ["30 Days","60 Days","90 Days","120 Days","150 Days","180 Days","13 Months"]
        if(viewPeriod not in validChoices):
            error = ValueError(f"Invalid choice to select for viewPeriod: '{viewPeriod}'")
            log.error(error)
            raise error

        viewDropdownMenuXPath = "//div[contains(@class,'selectdropDown')]//label[normalize-space(text())='View']/parent::div/div/button[contains(@class,'dropDownSelect')]"
        # Check to see if this option is already selected.
        if(self.browser.searchForElement(by=By.XPATH,value=f"{viewDropdownMenuXPath}[normalize-space(text())='{viewPeriod}']",timeout=3)):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            # First, click on the dropdown menu itself
            viewDropdownMenu = self.browser.searchForElement(by=By.XPATH,value=viewDropdownMenuXPath,timeout=60,testClickable=True)
            self.browser.safeClick(element=viewDropdownMenu,timeout=30)

            # Now, locate and click the selected option
            viewPeriodOptionXPath = f"{viewDropdownMenuXPath}/parent::div/div//span[normalize-space(text())='{viewPeriod}']"
            self.browser.safeClick(by=By.XPATH,value=viewPeriodOptionXPath,timeout=30)

            # Now, we wait for both the updated dropdown view AND the clickable orders header before continuing.
            self.browser.searchForElement(by=By.XPATH,value=f"{viewDropdownMenuXPath}[normalize-space(text())='{viewPeriod}']",timeout=60)
            # Yes, the typo is intentional lmfao
            viewOrdersHeaderXPath = "//div[contains(@class,'view-orders-conatiner')]//h2[contains(text(),'Orders')]"
            testResult = self.browser.searchForElement(by=By.XPATH, value=viewOrdersHeaderXPath, timeout=120,testClickable=True, testLiteralClick=True)
            if(testResult):
                return ActionResult(status=StatusCode.SUCCESS)
            else:
                return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    #endregion === Order Viewer ===

    #region === Line Viewer ===

    # This method pulls up the given serviceID in Verizon, from anywhere. It cancels out whatever
    # was previously happening.
    @action()
    def pullUpLine(self,serviceID):
        self.navToHomescreen()

        serviceSearchBarString = "//input[@id='dtm_search']"
        serviceSearchBar = self.browser.searchForElement(by=By.XPATH,value=serviceSearchBarString,testClickable=True,timeout=15)
        serviceSearchBar.clear()
        serviceSearchBar.send_keys(str(serviceID))
        serviceSearchBar.send_keys(Keys.ENTER)

        # First, wait for the line loader to disappear.
        lineLoadingXPath = "//div[contains(@class,'loading ng-star-inserted')]"
        self.browser.searchForElement(by=By.XPATH, value=lineLoadingXPath, timeout=10,invertedSearch=True)
        self.testForUnregisteredPopup()

        # Test if Verizon can't find the line.
        if(self.browser.searchForElement(by=By.XPATH,value="//p[contains(text(),'No results found.')]",timeout=2)):
            self.testForUnregisteredPopup()
            exitButton = self.browser.searchForElement(by=By.XPATH, value="//i[@id='icnClose']",timeout=3,testClickable=True)
            exitButton.click()
            self.browser.searchForElement(by=By.XPATH, value="//span[contains(text(),'Shop Devices')]",
                                          testClickable=True, timeout=15)
            log.error(f"Verizon is saying that line '{serviceID}' cannot be found.")
            return ActionResult(status=StatusCode.NO_RESULTS)
        else:
            upgradeDateHeaderXPath = "//sub[text()='Upgrade date']"
            testResult = self.browser.searchForElement(by=By.XPATH, value=upgradeDateHeaderXPath, timeout=120,
                                          testClickable=True, testLiteralClick=True)
            if(testResult):
                return ActionResult(status=StatusCode.SUCCESS)
            else:
                return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're on the line viewer for a specific line, and clicks "Upgrade device" to begin
    # an upgrade. Also handles ETF shenanigans, so that either way, this function either ends up
    # at the Device Selection page or returns false for lines that can't use waivers.
    @action()
    def LineViewer_UpgradeLine(self,useETFWaiver=True):
        upgradeDeviceEligibleButtonXPath = "//button[contains(text(),'Upgrade device')]"
        upgradeDeviceIneligibleButtonXPath = "//a[@type='button'][contains(text(),'Upgrade Options')]"
        earlyUpgradeOptionsHeaderXPath = "//div/*[contains(text(),'Choose upgrade options for non-eligible lines')]"
        mtnPendingErrorBoxString = "//app-modal-header/div[contains(text(),'The following wireless number is ineligible for this service.')]"
        shopDevicesHeaderXPath = "//div[@id='page-header']/div/h1[normalize-space(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))='shop devices']"

        upgradePagesMap = {upgradeDeviceEligibleButtonXPath : "UpgradeEligible", upgradeDeviceIneligibleButtonXPath : "UpgradeIneligible",
                           mtnPendingErrorBoxString : "MTNPending",earlyUpgradeOptionsHeaderXPath : "EarlyUpgradeOptions",
                           shopDevicesHeaderXPath : "ShopDevices"}

        clickedUpgrade = False
        upgradeEligible = None
        for i in range(10):
            # Perform the search for the current page of the upgrade process we're on.
            foundElement,alias = self.browser.searchForElement(by=By.XPATH,value=upgradePagesMap,timeout=30,
                                                               testClickable=True,scrollIntoView=True)
            # TODO Handle cases when the line isn't active (suspended)

            # Handle clicking on the upgrade button.
            if((alias == "UpgradeEligible" or alias == "UpgradeIneligible") and not clickedUpgrade):
                if(alias == "Upgrade Eligible"):
                    upgradeEligible = True
                else:
                    upgradeEligible = False
                # Click on the upgrade button
                self.browser.safeClick(element=foundElement,timeout=30,scrollIntoView=True)
                clickedUpgrade = True
                # Remove both upgrade options from the search dict, so they're not found again.
                upgradePagesMap.pop(upgradeDeviceEligibleButtonXPath,None)
                upgradePagesMap.pop(upgradeDeviceIneligibleButtonXPath,None)
            # Handle MTN Pending errors that may pop up.
            elif(alias == "MTNPending"):
                mtnPendingErrorCancelButtonString = "//app-modal-invalid-items-list//i[@aria-label='Close-Icon']"
                mtnPendingErrorCancelButton = self.browser.searchForElement(by=By.XPATH,value=mtnPendingErrorCancelButtonString,testClickable=True,timeout=30)
                mtnPendingErrorCancelButton.click()

                # Try to let the upgrade page load back before giving control back.
                upgradeDateHeaderXPath = "//sub[text()='Upgrade date']"
                self.browser.searchForElement(by=By.XPATH,value=upgradeDateHeaderXPath,testClickable=True,testLiteralClick=True,timeout=30,minSearchTime=2)
                log.warning("Line has the MTN Pending error - can't upgrade at the moment.")
                return ActionResult(status=StatusCode.VERIZON_MTN_PENDING)
            # Handle navigating the early upgrade options and ETF waiver application
            elif(alias == "EarlyUpgradeOptions"):
                if(useETFWaiver):
                    earlyUpgradeOptionsDropdownXPath = "//button[@class='drop-down-vz']"
                    earlyUpgradeOptionsDropdown = self.browser.searchForElement(by=By.XPATH,value=earlyUpgradeOptionsDropdownXPath,timeout=15,testClickable=True)
                    earlyUpgradeOptionsDropdown.click()

                    waiverOptionXPath = f"{earlyUpgradeOptionsDropdownXPath}/following-sibling::ul/li[contains(text(),'Waiver')]"
                    waiverOption = self.browser.searchForElement(by=By.XPATH,value=waiverOptionXPath,timeout=15,testClickable=True)
                    waiverOption.click()

                    elementNotEligibleXPath = "//*[contains(text(),'The wireless number you are attempting to upgrade is not eligible to use a Waiver.')]"
                    if(self.browser.searchForElement(by=By.XPATH,value=elementNotEligibleXPath,timeout=5)):
                        log.warning("Line is not yet eligible to be upgraded with an ETF waiver.")
                        return ActionResult(status=StatusCode.VERIZON_EARLY_UPGRADE_NO_ETF)

                    continueButtonString = "//app-choose-upgrade//button[contains(text(),'Continue')]"
                    continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonString,testClickable=True,timeout=15)
                    # Sometimes, a very very strange thing happens where something clicks this BEFORE the search.
                    # Literally no idea what, or how. I've looked everywhere, I've tried to reproduce it manually.
                    # Genuinely believe that this section of the code is haunted so, uh, hi Selenium spirit. Don't mind
                    # me.
                    if(continueButton):
                        continueButton.click()
                    log.info("Applied ETF waiver to line during upgrade.")
                else:
                    log.warning("Line requires ETF waiver to be upgraded, and action was run with useETFWaiver set to False.")
                    return ActionResult(status=StatusCode.VERIZON_EARLY_UPGRADE_NO_ETF)
            # If we get to the "Shop Devices" screen, we've completed getting from the line viewer to upgrade wizard
            elif(alias == "ShopDevices"):
                # We make sure it's literally clickable before proceeding.
                self.browser.searchForElement(element=foundElement, testClickable=True,
                                              testLiteralClick=True, timeout=30, minSearchTime=3,raiseError=True)
                return ActionResult(status=StatusCode.SUCCESS,data={"UpgradeEligible" : upgradeEligible})

        # If we've exited the loop, that means we went through 10 iterations of logic without finding end condition,
        # signaling a process change.
        log.error(f"Went through more than 10 iterations of logic without exiting - review process.",exc_info=True)
        return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)


    #endregion === Line Viewer ===

    #region === Device Ordering ===

    # This method navigates to homescreen, then navigates to the shop new device URL to begin a new install
    # request.
    @action()
    def shopNewDevice(self):
        self.browser.switchToTab("Verizon")
        self.testForUnregisteredPopup()

        self.browser.get("https://mb.verizonwireless.com/mbt/secure/index?appName=comm&transType=NSE#/device-gridwall/mobile-evolution")

        # Now we wait to ensure that we've fully navigated to the newDevice screen.
        shopDevicesHeaderXPath = "//h2[contains(text(),'Shop Devices')]"
        testResult = self.browser.searchForElement(by=By.XPATH,value=shopDevicesHeaderXPath,timeout=120,minSearchTime=5,
                                      testClickable=True,testLiteralClick=True)
        if(testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # This method clears the full cart, from anywhere. It effectively cancels whatever was previously
    # happening, but ensures the cart is fully empty for future automation. Since Verizon is a miserable
    # excuse for a website, sometimes clicking on "clear cart" just literally does nothing. Therefore, this
    # method contains "attempts" parameter which will repeat trying to clear the cart if it seems unsuccessful.
    @action()
    def emptyCart(self):
        self.browser.switchToTab("Verizon")

        # First, navigate to the cart url.
        verizonCartURL = "https://mb.verizonwireless.com/mbt/secure/index?appName=comm&transType=NSE&navtrk=globalnav%3Ashop%3Asmartphones#/device-shopping-cart"
        self.browser.get(verizonCartURL)

        clearCartButtonXPath = "//a[@id='dtm_clearcart']"
        emptyShoppingCartHeaderXPath = "//*[normalize-space(text())='Your cart is empty.']"
        confirmClearButtonXPath = "//div[contains(@class,'app-clear-cart-popup')]//button[normalize-space(text())='Clear']"

        clearCartPagesMap = {clearCartButtonXPath: "clearCartButton", emptyShoppingCartHeaderXPath: "cartIsEmpty",
                         confirmClearButtonXPath: "confirmClearPopupButton"}

        # Begin loop to manage clear cart logic.
        haveClearedCart = False
        for i in range(10):
            # First, get the current page we're on.
            foundElement, elementName = self.browser.searchForElement(by=By.XPATH, value=clearCartPagesMap,minSearchTime=5,
                                                                   testClickable=True,timeout=60, raiseError=True, logError=False)

            # If the cart is empty, we're done.
            if(elementName == "cartIsEmpty"):
                if(haveClearedCart):
                    log.debug("Cleared cart successfully.")
                else:
                    log.debug("Cart is already empty.")
                return ActionResult(status=StatusCode.SUCCESS)

            # If the "confirm clear" prompt is up, we click clear here.
            elif(elementName == "confirmClearPopupButton"):
                # Click "confirm" in the popup.
                self.browser.safeClick(element=foundElement, scrollIntoView=True, timeout=10)
                haveClearedCart = True

            # If the clear cart button is currently clickable, we click it to open up the "confirm clear" prompt.
            elif(elementName == "clearCartButton"):
                # Click "clear cart".
                self.browser.safeClick(element=foundElement,scrollIntoView=True,timeout=10,jsClick=True)

            time.sleep(1)



        # If we've gone through 10 steps of cart clear logic without confirmation that it actually cleared,
        # we assume it errored out and that we're now on an ambiguous page
        return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're on the device selection page. Given a Universal Device ID, searches for that
    # device (if supported) on Verizon. # TODO move the search term stuff to higher level - shouldn't need syscoSheet in this file technically
    # TODO this function is getting quite slow, which is pretty first world problem esque, but still
    @action()
    def DeviceSelection_SearchSelectDevice(self,deviceID,orderPath="NewInstall",searchAttempts = 3):
        if(orderPath == "NewInstall"):
            targetDeviceCardXPath = f"//div/div[contains(@class,'device-name')][normalize-space(text())='{syscoData["Devices"][deviceID]["Verizon Wireless New Install Card Name"]}']"
            targetDeviceOpenButtonXPath = f"{targetDeviceCardXPath}/following-sibling::div/div[@class='quick-view']/button"
            deviceDetailsXPath = f"//div[contains(@class,'pdp-header-section')]/div[contains(@class,'left-top-details')]/div[contains(text(),'{syscoData["Devices"][deviceID]["Verizon Wireless New Install Card Name"]}')]"
        else:
            targetDeviceCardXPath = f"//div/div[contains(@class,'device-title')][text()='{syscoData["Devices"][deviceID]["Verizon Wireless Upgrade Card Name"]}']"
            targetDeviceOpenButtonXPath = targetDeviceCardXPath
            deviceDetailsXPath = f"//div[contains(@class,'pdp-header-section')]//div[normalize-space(text())='{syscoData["Devices"][deviceID]["Verizon Wireless Upgrade Card Name"]}']"
        shopDevicesHeaderXPath = "//h2[contains(text(),'Shop Devices')]"


        f"//div/div[contains(@class,'device-title')][text()='iPhone 14']"

        # Helper method to search for a device one time, and wait until (roughly) the loading screen is gone.
        def searchDevice(clearFilters=False):
            if(clearFilters):
                clearFiltersButtonXPath = "//div[contains(@class,'filter-badges')]/a[contains(text(),'Clear all')]"
                clearFiltersButton = self.browser.searchForElement(by=By.XPATH,value=clearFiltersButtonXPath,timeout=60,testClickable=True)
                self.browser.safeClick(element=clearFiltersButton,timeout=60,scrollIntoView=True)

            searchBox = self.browser.searchForElement(by=By.XPATH,value="//input[@id='search']",timeout=15,testClickable=True)
            searchButton = self.browser.searchForElement(by=By.XPATH,value="//span[contains(@class,'icon-search')]",timeout=15,testClickable=True)
            searchBox.clear()
            searchBox.send_keys(syscoData["Devices"][deviceID]["Verizon Wireless Search Term"])
            self.browser.safeClick(element=searchButton,timeout=60)

            # We wait for the "shop devices" header to be clickable again, to roughly assume its finished loading.
            self.browser.searchForElement(by=By.XPATH,value=shopDevicesHeaderXPath,timeout=20,minSearchTime=4,testClickable=True,testLiteralClick=True)
        # Helper method to try to select the device by its card.
        def selectDevice():
            clickResult = self.browser.safeClick(by=By.XPATH,value=targetDeviceOpenButtonXPath, timeout=10,scrollIntoView=True,raiseError=False)

            if(clickResult):
                # Test for device details to confirm device has been successfully pulled up.
                return True if self.browser.searchForElement(by=By.XPATH, value=deviceDetailsXPath, timeout=30, minSearchTime=3,
                                              testClickable=True, testLiteralClick=True) else False
            else:
                return False

        tryClearFilters = False
        selectionSuccessful = False
        for attempt in range(searchAttempts):
            # Search device.
            searchDevice(clearFilters=tryClearFilters)
            # Add a small post-search wait to avoid weird Verizon shit
            time.sleep(3)
            # Try to select the device card.
            selectResult = selectDevice()

            # If selected successfully, break loop
            if(selectResult):
                selectionSuccessful = True
                break
            # Otherwise, try again after a wait.
            else:
                tryClearFilters = True
                time.sleep(5)
                continue

        if(selectionSuccessful):
            return ActionResult(status=StatusCode.SUCCESS)
        # Otherwise, raise an error.
        else:
            noResultsFoundXPath = "//span[contains(text(),'Sorry, no results found. Please try again with other key words.')]"
            if(self.browser.searchForElement(by=By.XPATH,value=noResultsFoundXPath,timeout=3)):
                log.warning(f"Verizon is report that no device with id '{deviceID}' can be found.")
                return ActionResult(status=StatusCode.NO_RESULTS)
            else:
                log.error(f"Verizon is getting stuck on device selection page.")
                return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Assumes we're in the quick view menu for a device. Various options for this menu.
    @action()
    def DeviceSelection_DeviceView_Select2YearContract(self,orderPath="NewInstall"):
        if(orderPath == "NewInstall"):
            yearlyContractXPath = "//div[contains(@class,'payment-option-each')]/div[contains(text(),'Yearly contract')]/parent::div"
            yearlyContractSelection = self.browser.searchForElement(by=By.XPATH,value=yearlyContractXPath,timeout=15,testClickable=True)
            yearlyContractSelection.click()

            twoYearContractSelectionXPath = "//div/ul/li/div[contains(text(),'2 Year Contract Required')]/parent::li"
            twoYearContractSelection = self.browser.searchForElement(by=By.XPATH,value=twoYearContractSelectionXPath,timeout=15,testClickable=True)
            self.browser.safeClick(element=twoYearContractSelection,timeout=60,scrollIntoView=True)
        else:
            twoYearContractXPath = "//div[contains(@class,'payment-option-each')]//div[contains(text(),'2 year contract')]"
            twoYearContractSelection = self.browser.searchForElement(by=By.XPATH,value=twoYearContractXPath,timeout=15,testClickable=True,raiseError=True)
            self.browser.safeClick(element=twoYearContractSelection,timeout=60,scrollIntoView=True)
        return ActionResult(status=StatusCode.SUCCESS)
    @action()
    def DeviceSelection_DeviceView_DeclineDeviceProtection(self):
        declineDeviceProtectionOptionBaseXPath = "//div[contains(text(),'Decline Device Protection')]"
        declineDeviceProtectionOptionXPath = f"{declineDeviceProtectionOptionBaseXPath}/parent::div/parent::div"
        self.browser.safeClick(by=By.XPATH,value=declineDeviceProtectionOptionXPath,timeout=30,scrollIntoView=True,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=f"{declineDeviceProtectionOptionBaseXPath}[contains(@class,'bold')]"))
        return ActionResult(status=StatusCode.SUCCESS)
    @action()
    def DeviceSelection_DeviceView_SelectColor(self,deviceID=None,colorName=None,orderPath="NewInstall"):
        if(colorName is None):
            if(deviceID):
                #TODO handle errors with sheet lookup or nah?
                colorName = syscoData["Devices"][deviceID]["Verizon Wireless Default Color"]
            else:
                error = ValueError("Specified to select a Default color, but no deviceID was specified!")
                log.error(error)
                raise error

        # For newInstalls, Verizon, in its infinite wisdom, has absolutely no labels on which color is which
        # other than literal RGB values. Therefore, we have to "guess and check" if we aren't currently selected
        # on the color we want.
        if(orderPath == "NewInstall"):
            currentColorHeaderXPath = "//div[contains(text(),'What color do you want?')]/following-sibling::div"
            allColorboxOptionsXPath = "//div[contains(@class,'colorbox')]//div[@class='colorbox-button']"
            allColorboxOptions = self.browser.find_elements(by=By.XPATH,value=allColorboxOptionsXPath)

            foundColor = False
            for colorboxOption in allColorboxOptions:
                # First, test if the previous selected color was correct:
                currentlySelectedColor = self.browser.searchForElement(by=By.XPATH,value=currentColorHeaderXPath,timeout=20,testClickable=True).text.strip().lower()
                if(currentlySelectedColor == colorName.lower()):
                    foundColor = True
                    break
                # If not, click on this new color and test it out.
                else:
                    self.browser.safeClick(element=colorboxOption,timeout=20)
                    continue

            if(foundColor):
                return ActionResult(status=StatusCode.SUCCESS)
            else:
                log.warning(f"Supplied color '{colorName}' does not seem to exist in Verizon Wireless for the searched device!")
                return ActionResult(status=StatusCode.VERIZON_MISSING_COLOR)
        # Color selection for upgrades is much easier, as the radio buttons are labeled with the actual color name.
        else:
            colorboxXPath = "//div[@class='colorbox']"

            colorSelectionXPath = f"{colorboxXPath}/div[@title='{colorName}']"
            colorSelection = self.browser.searchForElement(by=By.XPATH,value=colorSelectionXPath,timeout=5)
            if(colorSelection):
                self.browser.safeClick(element=colorSelection,timeout=15)
                return ActionResult(status=StatusCode.SUCCESS)
            else:
                log.warning(f"Supplied color '{colorName}' does not seem to exist in Verizon Wireless for the searched device!")
                return ActionResult(status=StatusCode.VERIZON_MISSING_COLOR)
    @action()
    def DeviceSelection_DeviceView_AddToCartAndContinue(self,orderPath="NewInstall"):
        if(orderPath == "NewInstall"):
            addToCartButtonXPath = "//button[@id='device-add-to-cart']"
            addToCartButton = self.browser.searchForElement(by=By.XPATH,value=addToCartButtonXPath,timeout=10,testClickable=True)
            addToCartButton.click()

            # Wait for header confirming device added
            deviceAddedToCartXPath = "//div[contains(text(),'Your new device has been added to your cart.')]"
            self.browser.searchForElement(by=By.XPATH,value=deviceAddedToCartXPath,timeout=30,testClickable=True)

            # Click continue
            continueButtonXPath = "//app-nse-multistep-progress-bar/following-sibling::*//button[normalize-space(text())='Continue']"
            shopAccessoriesHeaderXPath = "//section[contains(@class,'top-section')]//div[contains(text(),'Shop Accessories')]"
            self.browser.safeClick(by=By.XPATH,value=continueButtonXPath,timeout=120,scrollIntoView=True,retryClicks=True,
                                   clickDelay=10,successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=shopAccessoriesHeaderXPath))

            # Wait for accessories page to load
            testResult = self.browser.searchForElement(by=By.XPATH,value=shopAccessoriesHeaderXPath,timeout=60,
                                          testClickable=True,testLiteralClick=True)
        else:
            buyNowButtonXPath = "//button[text()='Buy Now']"
            buyNowButton = self.browser.searchForElement(by=By.XPATH,value=buyNowButtonXPath,timeout=10,testClickable=True)
            self.browser.safeClick(element=buyNowButton,timeout=120,scrollIntoView=True)

            # Wait for Shopping Cart page to load to confirm successful device add
            shoppingCartHeaderXPath = "//div[contains(@class,'device-shopping-cart-content-left')]//h1[contains(text(),'Shopping cart')]"
            testResult = self.browser.searchForElement(by=By.XPATH,value=shoppingCartHeaderXPath,timeout=60,minSearchTime=5)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're on the accessory selection page. Given a Universal Accessory ID, searches
    # for that accessory (if supported) on Verizon.
    @action()
    def AccessorySelection_SearchForAccessory(self,accessoryID):
        searchBox = self.browser.searchForElement(by=By.XPATH,value="//input[@id='search']",timeout=15,testClickable=True)
        searchButton = self.browser.searchForElement(by=By.XPATH,value="//span[@class='onedicon icon-search']",timeout=15,testClickable=True)

        searchBox.clear()
        searchBox.send_keys(syscoData["Accessories"][accessoryID]["Verizon Wireless Search Term"])
        self.browser.safeClick(element=searchButton,timeout=10)

        # Now we test to ensure that the proper device card has fully loaded.
        targetAccessoryCardXPath = f"//app-accessory-tile/div/div/div[contains(@class,'product-name')][contains(text(),'{syscoData["Accessories"][accessoryID]["Verizon Wireless Card Name"]}')]"
        testResult = self.browser.searchForElement(by=By.XPATH,value=targetAccessoryCardXPath,timeout=60)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    @action()
    def AccessorySelection_AddAccessoryToCart(self,accessoryID):
        targetAccessoryCardXPath = f"//app-accessory-tile/div/div/div[contains(@class,'product-name')][contains(text(),'{syscoData["Accessories"][accessoryID]["Verizon Wireless Card Name"]}')]//ancestor::div[contains(@class,'accessory-card')]"
        targetAccessoryAddToCartButtonXPath = f"{targetAccessoryCardXPath}//button[contains(@class,'add-cart-btn')]"
        targetAccessoryAddToCartButton = self.browser.searchForElement(by=By.XPATH,value=targetAccessoryAddToCartButtonXPath,timeout=60)
        self.browser.safeClick(element=targetAccessoryAddToCartButton,timeout=60)

        # Wait for confirmation that it was added to the cart.
        #TODO technically, it might be better to not only wait for confirmation to appear, but then to ALSO wait for
        # it to DISAPPEAR. maybe implement?
        addedToCartConfirmationXPath = "//div[contains(text(),'Your new accessory has been added to your cart.')]"
        testResult = self.browser.searchForElement(by=By.XPATH,value=addedToCartConfirmationXPath,timeout=120)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Method to manually continue to the next page after the accessory selection.
    @action()
    def AccessorySelection_Continue(self,orderPath="NewInstall"):
        continueButtonString = "//div[contains(@class,'mobile-button')]/button[contains(@class,'continue-btn')]"
        continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonString,timeout=60)
        self.browser.safeClick(element=continueButton,timeout=60)

        if(orderPath == "NewInstall"):
            # If this is a NewInstall, the next page should be the Plan Selection page.
            selectPlanHeaderXPath = "//div[contains(@class,'select-plan-container')]//h1[contains(text(),'Select plan')]"
            testResult = self.browser.searchForElement(by=By.XPATH,value=selectPlanHeaderXPath,timeout=120,testClickable=True,testLiteralClick=True)
        else:
            # If this is an upgrade, the next page should be back on the shopping cart.
            shoppingCartHeaderXPath = "//div[contains(@class,'device-shopping-cart-content-left')]//h1[contains(text(),'Shopping cart')]"
            testResult = self.browser.searchForElement(by=By.XPATH,value=shoppingCartHeaderXPath,timeout=60,minSearchTime=5)

        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're on the plan selection page. Given a Plan ID and a plan type,
    # selects it from this page.
    @action()
    def PlanSelection_SelectPlan(self,planID):
        # Should start on the Plan selection page. #TODO get into the habit of checking the page before every function?
        selectPlanHeaderXPath = "//div[contains(@class,'select-plan-container')]//h1[contains(text(),'Select plan')]"
        self.browser.searchForElement(by=By.XPATH, value=selectPlanHeaderXPath, timeout=120, testClickable=True,
                                      testLiteralClick=True)

        targetPlanCardXPath = f"//div[contains(@class,'plan-card')][contains(@title,'Plan ID - {planID}')]/div[@class='plan-card-inner']//button[contains(text(),'Select plan')]"
        targetPlanCard = self.browser.searchForElement(by=By.XPATH,value=targetPlanCardXPath,timeout=60,testClickable=True)
        self.browser.scrollIntoView(targetPlanCard)
        self.browser.safeClick(element=targetPlanCard,timeout=60)

        # Wait for confirmation that the plan has been selected.
        testResult = self.browser.searchForElement(by=By.XPATH,value="//div[contains(text(),'Continue to the next step.')]",timeout=60)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Method to continue to the next page after the plan selection.
    @action()
    def PlanSelection_Continue(self):
        continueButtonString = "//div/div/button[@id='stickybutton'][contains(text(),'Continue')]"
        continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonString,timeout=60)
        self.browser.scrollIntoView(continueButton)
        self.browser.safeClick(element=continueButton,timeout=60)

        # We wait until the device protection header is found, meaning we went to the next page.
        testResult = self.browser.searchForElement(by=By.XPATH,value=self.deviceProtectionHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    deviceProtectionHeaderXPath = "//app-equipment-protection-landing-mobile-evolution//*[normalize-space(text())='Shop device protection']"
    # Assumes we're on the device protection page. Clicks on "decline". Note that this also serves
    # as the "continue" button for this page.
    @action()
    def DeviceProtection_DeclineAndContinue(self):
        #TODO sometimes weird shit happens on this page with multiple lines. Handle.
        # Check that the device protection header is found, meaning we're on the right page.

        self.browser.searchForElement(by=By.XPATH,value=self.deviceProtectionHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True)

        declineDeviceProtectionXPath = "//button[normalize-space(text())='Decline and continue']"
        self.browser.safeClick(by=By.XPATH,value=declineDeviceProtectionXPath,timeout=120)

        # We wait for the number assignment page header to load, meaning we've successfully navigated to the next page.
        numberAssignPageHeaderXPath = "//div[contains(text(),'Assign numbers and users to your new devices.')]"
        testResult = self.browser.searchForElement(by=By.XPATH,value=numberAssignPageHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're on the number selection page. Given an initial zip code, tests zip code and sequential
    # zip codes to determine, select, and apply the first available.
    @action()
    def NumberSelection_SelectAreaCode(self,zipCode):
        # First we check for the number assignment page header to load, meaning we're on the right page.
        numberAssignPageHeaderXPath = "//div[contains(text(),'Assign numbers and users to your new devices.')]"
        self.browser.searchForElement(by=By.XPATH,value=numberAssignPageHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True)

        # Then, we check to ensure the spinner is gone, to make sure the page has "settled" before interacting with it.
        zipCodeSpinnerXPath = "//div[contains(@class,'spinner')]"
        self.browser.searchForElement(by=By.XPATH, value=zipCodeSpinnerXPath, timeout=30, invertedSearch=True,minSearchTime=3)

        zipCode = zipCode.split("-")[0].strip()
        zipCodeFormXPath = "//input[@id='zip']"
        zipCodeForm = self.browser.searchForElement(by=By.XPATH,value=zipCodeFormXPath,timeout=60,testClickable=True)
        areaCodeDropdownXPath = "//div[contains(@class,'area-dropdown')]"
        areaCodeScrollAreaXPath = "//div[contains(@class,'dropdown-scroll') or contains(@class,'dd-list')]"
        areaCodeResultsXPath = f"{areaCodeDropdownXPath}//div/ul/li[@class='ng-star-inserted'][1]"
        noNumbersAvailableXPath = "//div[contains(text(),'The city or zip code you entered has no numbers available')]"

        # Wait for the spinner to disappear if it's there again.
        self.browser.searchForElement(by=By.XPATH,value=zipCodeSpinnerXPath,timeout=30,invertedSearch=True,minSearchTime=3)
        zipCodeSpinnerXPath = ""
        zipCodeForm.clear()
        zipCodeForm.send_keys(f"{zipCode:05}")

        # This helper function is used to bring stability to a website that is truly and deeply broken.
        def selectAreaCode():
            # First, open the dropdown. Wait until either the scrollArea is found (meaning area codes should be listed)
            # or Verizon says that there's no area codes available.
            initialClickResult = self.browser.safeClick(by=By.XPATH,value=areaCodeDropdownXPath,timeout=20,raiseError=False,
                                   successfulClickCondition=lambda b:
                                   (b.searchForElement(by=By.XPATH,value=areaCodeScrollAreaXPath) or b.searchForElement(by=By.XPATH,value=noNumbersAvailableXPath)))
            if(not initialClickResult):
                return False

            # Wait for the spinner.
            self.browser.searchForElement(by=By.XPATH, value=zipCodeSpinnerXPath, timeout=30, invertedSearch=True,minSearchTime=3)

            # Handle the case where Verizon says no numbers are available
            if(self.browser.searchForElement(by=By.XPATH, value=noNumbersAvailableXPath, timeout=3, testClickable=True)):
                playsoundAsync(paths["media"] / "shaman_attention.mp3")
                userResponse = input(f"Verizon is saying there are no area codes available for the given zip '{zipCode}'. Please manually select an area code, and press enter to continue. Press any key to cancel.")
                if (userResponse):
                    error = ValueError("No zip codes found, and user cancelled manual input.")
                    log.error(error)
                    raise error
                else:
                    # Assume the user successfully manually selected an areaCode and return True.
                    return True
            # Otherwise, try to find the list of area codes.
            else:
                # Get area code results.
                areaCodeResults = self.browser.searchForElements(by=By.XPATH, value=areaCodeResultsXPath, timeout=10)

                # Check if any area code results are found, if not, try another zip code.
                if(areaCodeResults):
                    self.browser.safeClick(element=areaCodeResults[0],timeout=10)
                    # Wait for the spinner one final time
                    self.browser.searchForElement(by=By.XPATH, value=zipCodeSpinnerXPath, timeout=30, invertedSearch=True,minSearchTime=1)
                    return True
                else:
                    return False

        # Try to select an areaCode 3 times.
        selectionStatus = False
        for i in range(3):
            selectionStatus = selectAreaCode()
            if(selectionStatus):
                break
        if(not selectionStatus):
            log.error(f"Couldn't successfully select an area code after 3 attempts!")
            return ActionResult(status=StatusCode.VERIZON_ZIP_SELECTION_FAILURE)

        assignNumbersButtonXPath = "//button[text()='Assign numbers to all']"
        assignNumbersButton = self.browser.searchForElement(by=By.XPATH, value=assignNumbersButtonXPath, timeout=30,testClickable=True)
        self.browser.safeClick(element=assignNumbersButton, timeout=30)

        # Test to see the Verizon recognizes the number as assigned.
        numberHasBeenAssignedHeaderXPath = "//div[contains(text(),'You assigned numbers to all your devices.')]"
        testResult = self.browser.searchForElement(by=By.XPATH, value=numberHasBeenAssignedHeaderXPath, timeout=30,testClickable=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.VERIZON_ZIP_SELECTION_FAILURE)

    # Assumes a number has been selected, and navigates to the add user information page.
    @action()
    def NumberSelection_NavToAddUserInformation(self):
        addUserInfoButtonXPath = "//button[text()='Add user information']"
        addUserInfoButton = self.browser.searchForElement(by=By.XPATH,value=addUserInfoButtonXPath,timeout=30,testClickable=True)
        self.browser.safeClick(element=addUserInfoButton,timeout=30)

        # Wait for user info page to load.
        userInfoHeaderXPath = "//div[contains(text(),'Add user information to your selected device.')]"
        testResult = self.browser.searchForElement(by=By.XPATH,value=userInfoHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Assumes we're on the user information page. Enters in basic user information.
    @action()
    def UserInformation_EnterBasicInfo(self,firstName,lastName,email):
        # Check to ensure we're actually on the info page.
        userInfoHeaderXPath = "//div[contains(text(),'Add user information to your selected device.')]"
        self.browser.searchForElement(by=By.XPATH,value=userInfoHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True)

        # Write first name
        firstNameField = self.browser.searchForElement(by=By.XPATH,value="//input[@id='firstName']",timeout=30,testClickable=True)
        firstNameField.clear()
        firstNameField.send_keys(normalizeName(firstName))

        # Writ last name
        lastNameField = self.browser.searchForElement(by=By.XPATH,value="//input[@formcontrolname='lastName']",timeout=30,testClickable=True)
        lastNameField.clear()
        lastNameField.send_keys(normalizeName(lastName))

        # Write email
        emailField = self.browser.searchForElement(by=By.XPATH,value="//input[@type='email']",timeout=30,testClickable=True)
        emailField.clear()
        emailField.send_keys(email)

        if(self.browser.searchForElement(by=By.XPATH,value="//span[contains(text(),'Please enter a valid email address.')]",timeout=3)):
            log.error(f"Verizon believes that email '{email}' is invalid.")
            return ActionResult(status=StatusCode.VERIZON_INVALID_EMAIL)
        else:
            return ActionResult(status=StatusCode.SUCCESS)
    # Assumes we're on the user information page. Enters in address information.
    @action()
    def UserInformation_EnterAddressInfo(self,address1,address2,city,stateAbbrev,zipCode):
        # First, click on "edit address"
        editAddressButtonXPath = "//span[contains(@class,'edit-add-label')][contains(text(),'Edit address')]"
        editAddressButton = self.browser.searchForElement(by=By.XPATH,value=editAddressButtonXPath,timeout=30,testClickable=True)
        self.browser.safeClick(element=editAddressButton,timeout=30)

        # Write Address 1
        address1FieldXPath = "//input[@formcontrolname='addressLine1']"
        address1Field = self.browser.searchForElement(by=By.XPATH,value=address1FieldXPath,timeout=30,testClickable=True)
        address1Field.clear()
        address1Field.send_keys(address1)

        # Write Address 2 (if applicable)
        if(address2 is not None and address2 != ""):
            address2FieldXPath = "//input[@formcontrolname='addressLine2']"
            address2Field = self.browser.searchForElement(by=By.XPATH,value=address2FieldXPath,timeout=30,testClickable=True)
            address2Field.clear()
            address2Field.send_keys(address2)

        # Write City
        cityFieldXPath = "//input[@formcontrolname='city']"
        cityField = self.browser.searchForElement(by=By.XPATH,value=cityFieldXPath,timeout=30,testClickable=True)
        cityField.clear()
        cityField.send_keys(city)

        # Write State
        stateFieldString = "//select[@formcontrolname='state']"
        stateField = Select(self.browser.searchForElement(by=By.XPATH, value=stateFieldString,timeout=30))
        stateField.select_by_visible_text(stateAbbrev)

        # Write Zip
        zipCodeFieldXPath = "//input[@formcontrolname='zipCode']"
        zipCodeField = self.browser.searchForElement(by=By.XPATH,value=zipCodeFieldXPath,timeout=30,testClickable=True)
        zipCodeField.clear()
        zipCodeField.send_keys(zipCode)

        return ActionResult(status=StatusCode.SUCCESS)
    # Saves the user information inputted, which takes us back to the NumberSelection
    @action()
    def UserInformation_SaveInfo(self):
        saveButtonXPath = "//button[contains(text(),'Save')]"
        saveButton = self.browser.searchForElement(by=By.XPATH,value=saveButtonXPath,timeout=30)
        saveButton.click()

        # Now we wait to see that the user info has been successfully updated.
        yourDevicesHeaderXPath = "//div[contains(text(),'Your devices')]"
        testResult = self.browser.searchForElement(by=By.XPATH,value=yourDevicesHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True,raiseError=True,scrollIntoView=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Continues to the next screen from the Number Selection screen, assuming a number has been
    # selected and all user inputted.
    @action()
    def NumberSelection_Continue(self):
        continueButtonXPath = "//app-nse-multistep-progress-bar/following-sibling::div/button[contains(@class,'continue-btn')]"
        continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonXPath,timeout=30,testClickable=True)
        self.browser.safeClick(element=continueButton,timeout=30)

        # Test for the next page, which should be on the shopping cart.
        shoppingCartHeaderXPath = "//div[contains(@class,'device-shopping-cart-content-left')]//h1[contains(text(),'Shopping cart')]"
        addressDoesntExistXPath = "//div[contains(text(),'The address you entered could not be validated.')]"
        aliasDict = {shoppingCartHeaderXPath : "ShoppingCart",addressDoesntExistXPath : "AddressDoesntExist"}

        foundElement,alias = self.browser.searchForElement(by=By.XPATH, value=aliasDict, timeout=60, minSearchTime=5,testClickable=True)
        if(alias == "ShoppingCart"):
            return ActionResult(status=StatusCode.SUCCESS)
        elif(alias == "AddressDoesntExist"):
            log.warning("Verizon Wireless reports that the given address cannot be validated.")
            return ActionResult(status=StatusCode.VERIZON_INVALID_ADDRESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're currently on the feature selection page, and attempts to toggle ON the given feature.
    @action()
    def FeatureSelection_SelectFeature(self,featureName):
        featureFormXPathPrefix = "//app-choose-feature-single-line//div[contains(@class,'inner-grid-header')]"
        specificFeatureTitleXPathPrefix = f"{featureFormXPathPrefix}//span[text()='{featureName}']"
        specificFeatureToggleXPath = f"{specificFeatureTitleXPathPrefix}/parent::span/parent::div/label[contains(@class,'Form-toggle')]"
        specificFeatureIsActiveXPath = f"{specificFeatureTitleXPathPrefix}/parent::span/parent::div/parent::div/parent::div//div[contains(@class,'feature-status')]/p[contains(text(),'Added')]"

        # Click the selected feature
        specificFeatureToggle = self.browser.searchForElement(by=By.XPATH,value=specificFeatureToggleXPath,timeout=30,testClickable=True)
        self.browser.scrollIntoView(specificFeatureToggle)
        self.browser.safeClick(element=specificFeatureToggle,timeout=30)

        # Wait for it to show as "added"
        testResult = self.browser.searchForElement(by=By.XPATH,value=specificFeatureIsActiveXPath,timeout=30)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Simply continues from the FeatureSelection screen
    @action()
    def FeatureSelection_Continue(self):
        continueButtonXPath = "//div[contains(@class,'header-button')]/button[contains(text(),'Continue')]"
        continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonXPath,timeout=30,testClickable=True)
        self.browser.safeClick(element=continueButton,timeout=30)

        # Test to make sure we've arrived back at the shopping cart.
        shoppingCartHeaderXPath = "//div[contains(@class,'device-shopping-cart-content-left')]//h1[contains(text(),'Shopping cart')]"
        testResult = self.browser.searchForElement(by=By.XPATH, value=shoppingCartHeaderXPath, timeout=60, minSearchTime=5)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Helper method verifies that there is only one line listed in the shopping cart, AND that that line
    # is currently expanded.
    @action()
    def ShoppingCart_ValidateSingleLine(self):
        allCartLinesXPath = "//*[contains(@class,'dsc-line-list')]/*[@class='ng-star-inserted']"
        allCartLines = self.browser.find_elements(by=By.XPATH,value=allCartLinesXPath)
        if(len(allCartLines) == 0):
            log.error("Attempted to validate a single line in the shopping cart, but found zero lines instead!")
            return ActionResult(status=StatusCode.SUCCESS)
        elif(len(allCartLines) == 1):
            expandLineButtonXPath = f"{allCartLinesXPath}//div[contains(@class,'dsc-line-accordion-icon')]/i"

            # Test to make sure the line is expanded
            closedExpandLineButton = self.browser.searchForElement(by=By.XPATH,value=f"{expandLineButtonXPath}[contains(@class,'icon-plus')]",timeout=1.5)
            if(closedExpandLineButton):
                self.browser.safeClick(element=closedExpandLineButton,timeout=5,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=f"{expandLineButtonXPath}[contains(@class,'icon-minus')]"))
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            log.error(f"Attempted to validate a single line in the shopping cart, but found {len(allCartLines)} lines instead!")
            return ActionResult(status=StatusCode.SUCCESS)
    # From shopping cart, clicks back to add accessories to the given order. For use with upgrades,
    # which ATM bypass the accessory selection screen by default.
    @action()
    def ShoppingCart_AddAccessories(self):
        # First, validate that they're only one line added.
        validateSingleLineResult = self.ShoppingCart_ValidateSingleLine()
        if(not validateSingleLineResult.status):
            return ActionResult(status=validateSingleLineResult.status)

        # Then, click on "Add accessories"
        addAccessoriesXPath = "//div[contains(@class,'dsc-add-accessories-btn')]/a[contains(text(),'Add accessories')]"
        addAccessories = self.browser.searchForElement(by=By.XPATH,value=addAccessoriesXPath,timeout=10,testClickable=True)
        self.browser.safeClick(element=addAccessories,scrollIntoView=True,timeout=10)

        # Finally, wait for Accessories screen to load.
        shopAccessoriesHeaderXPath = "//section[contains(@class,'top-section')]//div[contains(text(),'Shop Accessories')]"
        testResult = self.browser.searchForElement(by=By.XPATH, value=shopAccessoriesHeaderXPath, timeout=60,
                                      testClickable=True, testLiteralClick=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # From shopping cart, clicks back to add features to the given order.
    @action()
    def ShoppingCart_AddFeatures(self):
        # First, validate that they're only one line added.
        self.ShoppingCart_ValidateSingleLine()

        # Then, click on "Manage features"
        addFeaturesXPath = "//div[contains(@class,'dsc-features-actions')]//span[contains(text(),'Manage Features')]"
        addFeatures = self.browser.searchForElement(by=By.XPATH,value=addFeaturesXPath,timeout=10,testClickable=True)
        self.browser.safeClick(element=addFeatures,timeout=30)

        # Finally, wait for Accessories screen to load.
        selectFeaturesHeaderXPath = "//h3[contains(text(),'Select features')]"
        testResult = self.browser.searchForElement(by=By.XPATH, value=selectFeaturesHeaderXPath, timeout=60,
                                      testClickable=True, testLiteralClick=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)
    # Assumes we're on the shopping cart overview screen. Simply clicks "check out" to continue
    # to check out screen.
    @action()
    def ShoppingCart_ContinueToCheckOut(self):
        checkOutButtonXPaths = ["//div[@class='progress']//button[normalize-space(text())='Checkout']","//div[contains(@class,'device-shopping-cart-content-right')]//button[normalize-space(text())='Checkout']"]
        checkOutButton = self.browser.searchForElement(by=By.XPATH,value=checkOutButtonXPaths,timeout=30,testClickable=True)
        self.browser.safeClick(element=checkOutButton,timeout=30,scrollIntoView=True)

        # Test to ensure we've arrived at the checkout screen.
        checkoutHeaderXPath = "//div[@class='checkoutBox']//h1[text()='Checkout']"
        testResult = self.browser.searchForElement(by=By.XPATH,value=checkoutHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True)
        if (testResult):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

    # Assumes we're on the checkout screen. Attempts to click on "add address" to add
    # a full address info.
    @action()
    def Checkout_AddAddressInfo(self,company,attention,address1,city,stateAbbrev,zipCode,contactPhone,
                                notificationEmails : list = None,address2 = "",overrideVerizonInvalidAddress=False):
        if(address2 is None):
            address2 = ""

        # First, convert contactPhone to the correct format.
        contactPhone = convertServiceIDFormat(serviceID=contactPhone,targetFormat="raw")

        # Test to ensure we're on the checkout screen.
        checkoutHeaderXPath = "//div[@class='checkoutBox']//h1[text()='Checkout']"
        self.browser.searchForElement(by=By.XPATH,value=checkoutHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True)

        #region === Writing Shipping Info ===

        companyFieldXPath = "//input[@id='firmName']"
        # We try multiple add/edit shipping methods to ensure it works regardless of the page we're on.
        addNewAddressButtonXPath = "//div[contains(@class,'new-address')]"
        editShippingAddressButtonXPath = "//div[contains(@class,'edit-btn')]"

        addEditShippingButton = self.browser.searchForElement(by=By.XPATH,value=[addNewAddressButtonXPath,editShippingAddressButtonXPath],timeout=30)
        self.browser.safeClick(element=addEditShippingButton,timeout=30,retryClicks=True,clickDelay=3,scrollIntoView=True,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=companyFieldXPath,testClickable=True))

        # Write company name
        companyField = self.browser.searchForElement(by=By.XPATH,value=companyFieldXPath,timeout=30,testClickable=True)
        companyField.clear()
        companyField.send_keys(company)

        # Write attention
        attentionFieldXPath = "//input[@id='attention']"
        attentionField = self.browser.searchForElement(by=By.XPATH,value=attentionFieldXPath,timeout=30,testClickable=True)
        attentionField.clear()
        attentionField.send_keys(normalizeName(attention))

        # Write address1
        address1FieldXPath = "//input[@id='add1']"
        address1Field = self.browser.searchForElement(by=By.XPATH,value=address1FieldXPath,timeout=30,testClickable=True)
        address1Field.clear()
        address1Field.send_keys(address1)

        # Write address2
        if(address2 is not None and address2 != ""):
            address2FieldXPath = "//input[@id='add2']"
            address2Field = self.browser.searchForElement(by=By.XPATH,value=address2FieldXPath,timeout=30,testClickable=True)
            address2Field.clear()
            address2Field.send_keys(address2)

        # Write City
        cityFieldXPath = "//input[@id='city']"
        cityField = self.browser.searchForElement(by=By.XPATH,value=cityFieldXPath,timeout=30,testClickable=True)
        cityField.clear()
        cityField.send_keys(city)

        # Write state
        stateSelectXPath = "//select[@id='states']"
        stateSelect = Select(self.browser.searchForElement(by=By.XPATH,value=stateSelectXPath,timeout=30,testClickable=True))
        stateSelect.select_by_visible_text(stateAbbrev)

        # Write contact phone
        contactPhoneFieldXPath = "//input[@name='phoneNumber']"
        contactPhoneField = self.browser.searchForElement(by=By.XPATH, value=contactPhoneFieldXPath,timeout=30,testClickable=True)
        contactPhoneField.clear()
        contactPhoneField.send_keys(contactPhone)

        # To add emails, first, we remove all existing emails if present.
        existingOldEmailsXPath = "//input[@type='email']/parent::div/following-sibling::div[@class='remove-btn']"
        existingOldEmails = self.browser.find_elements(by=By.XPATH,value=existingOldEmailsXPath)
        for existingOldEmail in existingOldEmails:
            self.browser.safeClick(element=existingOldEmail,timeout=10)
        # Now, we add all emails specified as arguments.
        for newEmail in notificationEmails:
            addNewNotifyButtonXPath = "//div[contains(@class,'add-notify')]/div[contains(text(),'Add new notification')]/parent::div"
            addNewNotifyButton = self.browser.searchForElement(by=By.XPATH,value=addNewNotifyButtonXPath,timeout=30,testClickable=True)

            # Try this until a new email field actually appears.
            successfullyWroteEmail = False
            for i in range(10):
                self.browser.safeClick(element=addNewNotifyButton,timeout=30)
                try:
                    allNewEmailFields = self.browser.find_elements(by=By.XPATH, value="//input[@type='email']")
                    allNewEmailFields[-1].clear()
                    allNewEmailFields[-1].send_keys(newEmail)
                    successfullyWroteEmail = True
                    break
                except IndexError:
                    continue
            if not successfullyWroteEmail:
                log.warning(f"Failed to add a new field to write email '{newEmail}' 10 times.")
                return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

        # Write zip code last, as this triggers a load
        zipCodeFieldXPath = "//input[@name='zipCode']"
        zipCodeField = self.browser.searchForElement(by=By.XPATH, value=zipCodeFieldXPath,timeout=30,testClickable=True)
        zipCodeField.clear()
        zipCodeField.send_keys(zipCode)

        # Test again for the clickable checkout header, to ensure all loading is done
        self.browser.searchForElement(by=By.XPATH, value=checkoutHeaderXPath, timeout=60, testClickable=True,scrollIntoView=True,
                                      testLiteralClick=True, minSearchTime=3)

        # Finally, we continue back to payment.
        continueToPaymentButtonXPath = "//button[contains(text(),'Continue to Payment')]"
        continueToPaymentButton = self.browser.searchForElement(by=By.XPATH, value=continueToPaymentButtonXPath,testClickable=True,scrollIntoView=True)
        self.browser.safeClick(element=continueToPaymentButton, timeout=120)

        addressCouldNotBeValidatedXPath = "//div[contains(text(),'Address could not be validated.')]"
        shippingAddressFullXPath = "//div[@class='shipdisplay-left']/p[contains(@class,'collapse-shipping')]"
        pageMap = {addressCouldNotBeValidatedXPath : "AddressNotValid",shippingAddressFullXPath: "ShippingReady"}
        shippingWritten = False
        for i in range(4):
            foundElement,pageName = self.browser.searchForElement(by=By.XPATH,value=pageMap,testClickable=True,
                                                                  timeout=30,scrollIntoView=True,raiseError=True)
            # Handle cases where Verizon reports the address as invalid.
            if(pageName == "AddressNotValid"):
                # If address could not be validated, but override is on, simply click continue again.
                if (overrideVerizonInvalidAddress):
                    continueToPaymentButton = self.browser.searchForElement(by=By.XPATH, value=continueToPaymentButtonXPath,testClickable=True)
                    self.browser.safeClick(element=continueToPaymentButton, timeout=120)
                else:
                    #TODO GLUEUEUEUEUEUEUEUE
                    userResponse = input(f"Verizon's claiming that the address is invalid. Please review - press enter to continue, press any other keys to cancel.")
                    if (userResponse):
                        error = ValueError(f"Verizon believes address is invalid")
                        log.error(error)
                        raise error
                        #log.warning("Verizon believes that the given address could not be validated.")
                        #return ActionResult(status=StatusCode.VERIZON_INVALID_ADDRESS)
                    else:
                        continueToPaymentButton = self.browser.searchForElement(by=By.XPATH,value=continueToPaymentButtonXPath,testClickable=True)
                        self.browser.safeClick(element=continueToPaymentButton, timeout=120)
            elif(pageName == "ShippingReady"):
                shippingWritten = True
                break
        if(not shippingWritten):
            log.warning("Tried to continue from shipping address input 4 times, but never succeeded.")
            return ActionResult(status=StatusCode.AMBIGUOUS_PAGE)

        #endregion === Writing Shipping Info ===

        # Now, we test to make sure that Verizon Wireless didn't ninja-edit the shipping address into something else.
        shippingAddressFull = self.browser.searchForElement(by=By.XPATH,value=shippingAddressFullXPath,timeout=30,testClickable=True,testLiteralClick=True,scrollIntoView=True).text
        rawVerizonAddressString = shippingAddressFull.lower().strip()
        # Helper function for helping to compare the expected address and verizon's final address
        def classifyVerizonFinalAddress(verizonAddressString):
            addressLines = verizonAddressString.strip().split("\n")

            streetLine = addressLines[1]
            cityStateZipLine = addressLines[2]

            addresses = streetLine.strip().split(",")
            address1 = addresses[0].strip()
            if (len(addresses) >= 2):
                address2 = addresses[1].strip()
            else:
                address2 = None

            city, stateZipCode = cityStateZipLine.split(",")
            city = city.strip()
            state, zipCode = stateZipCode.split("-")
            state = state.strip()
            zipCode = zipCode.strip()

            return {"Address1": address1, "Address2": address2, "City": city, "State": state, "ZipCode": zipCode}
        classifiedVerizonAddress = classifyVerizonFinalAddress(rawVerizonAddressString)
        print(f"Address1 : {address1.lower().strip()}")
        print(f"Address2 : {address2.lower().strip()}")
        print(f"City : {city.lower().strip()}")
        print(f"State : {stateAbbrev.lower().strip()}")
        print(f"ZipCode : {zipCode.lower().split('-')[0].strip()}")
        # Test the expected address against the classifiedVerizonAddress
        if(classifiedVerizonAddress["Address1"] == address1.lower().strip() and
           classifiedVerizonAddress["City"] == city.lower().strip() and
           classifiedVerizonAddress["State"] == stateAbbrev.lower().strip() and
           classifiedVerizonAddress["ZipCode"] == zipCode.lower().split('-')[0].strip() and
                ((address2 == "" and classifiedVerizonAddress["Address2"] is None) or (classifiedVerizonAddress["Address2"] == address2.lower().strip()))):
            return ActionResult(status=StatusCode.SUCCESS)
        else:
            # TODO handle this through status codes/retroactively?
            playsoundAsync(paths["media"] / "shaman_attention.mp3")
            userResponse = input(f"Verizon ninja-edited the shipping address. Verizon's final address was :\n\n{classifiedVerizonAddress}. Press enter to proceed anyways (you may make a change in the shipping if you prefer), type anything else to cancel.")
            if(userResponse):
                error = ValueError(f"Verizon ninja-edited the shipping address. Verizon's final address was :\n\n{classifiedVerizonAddress}")
                log.error(error)
                raise error
            else:
                return ActionResult(status=StatusCode.SUCCESS)
    # Assumes address info has been filled, and places the order, returning the order info.
    @action()
    def Checkout_PlaceOrder(self,billingAccountNum):
        #TODO some glue here. Truncates the second half of
        billToAccountButtonXPath = f"//div[@id='billToAccount']//span[contains(text(),'{billingAccountNum.split('-')[0]}')]/parent::label/span[@class='checkmark']"
        billToAccountButton = self.browser.searchForElement(by=By.XPATH,value=billToAccountButtonXPath,timeout=30,testClickable=True,scrollIntoView=True)
        self.browser.safeClick(element=billToAccountButton,timeout=30)

        # Click submit
        submitOrderButtonXPath = "//app-order-total//button[contains(text(),'Submit Order')]"
        submitOrderButton = self.browser.searchForElement(by=By.XPATH,value=submitOrderButtonXPath,timeout=120,testClickable=True)
        self.browser.safeClick(element=submitOrderButton,timeout=120)

        orderSummaryHeaderString = "//h2[text()='Order summary']"
        self.browser.searchForElement(by=By.XPATH,value=orderSummaryHeaderString,timeout=60,testClickable=True,testLiteralClick=True)

        fullOrderInfoXPath = "//div[contains(@class,'order-number')]/parent::div"
        fullOrderInfo = self.browser.searchForElement(by=By.XPATH,value=fullOrderInfoXPath,timeout=60,testClickable=True)
        if(fullOrderInfo):
            return ActionResult(status=StatusCode.SUCCESS,data=fullOrderInfo.text)
        else:
            return ActionResult(status=StatusCode.VERIZON_FAILED_ORDER_PLACE)

    #endregion === Device Ordering ===