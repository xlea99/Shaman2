import selenium.common.exceptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
from shaman2.selenium.browser import Browser
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.common.config import mainConfig, devices, accessories
from shaman2.utilities.async_sound import playsoundAsync

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
    def logInToVerizon(self,manual=False):
        self.browser.switchToTab("Verizon")

        # Test if already signed in.
        if("https://mb.verizonwireless.com" in self.browser.current_url):
            return True
        else:
            self.browser.get("https://mblogin.verizonwireless.com/account/business/login/unifiedlogin")
            if(manual):
                playsoundAsync(paths["media"] / "shaman_attention.mp3")
                userResponse = input("Press enter once logged in to Verizon. Press any other key to cancel.")
                if(userResponse != ""):
                    error = RuntimeError("User cancelled login process.")
                    log.error(error)
                    raise error
            else:
                #region === USERNAME LOGIN SCREEN ===
                usernameFieldXPath = "//label[text()='User ID']/following-sibling::input"
                usernameField = self.browser.searchForElement(by=By.XPATH,value=usernameFieldXPath,testClickable=True,timeout=30)
                usernameField.send_keys(mainConfig["authentication"]["verizonUser"])
                usernameField.send_keys(Keys.ENTER)
                # Wait for username field to disappear.
                self.browser.searchForElement(element=usernameField,timeout=60,testNotStale=False,
                                              invertedSearch=True)
                #endregion === USERNAME LOGIN SCREEN ===

                #region === HWYLTLI SCREEN ===
                # This screen may pop up, asking the user how they want to log in.
                howDoYouWantToLogInHeaderXPath = "//h3[contains(text(),'How do you want to log in?')]"
                howDoYouWantToLogInHeader = self.browser.searchForElement(by=By.XPATH,value=howDoYouWantToLogInHeaderXPath,
                                              testClickable=True,testLiteralClick=True,timeout=3)
                if(howDoYouWantToLogInHeader):
                    logInWithPasswordOptionXPath = "//a[contains(text(),'Log in with my password')]"
                    logInWithPasswordOption = self.browser.searchForElement(by=By.XPATH,value=logInWithPasswordOptionXPath,testClickable=True,timeout=30)
                    logInWithPasswordOption.click()
                    # Wait for HDYWTLI header to disappear.
                    self.browser.searchForElement(element=logInWithPasswordOption, timeout=60,testNotStale=False,
                                                  invertedSearch=True)
                #endregion === HWYLTLI SCREEN ===

                #region === PASSWORD LOGIN SCREEN ===
                # This screen means we're on the enter password screen.
                passLogInHeaderXPath = "//h3[text()='Log in']"
                passLogInHeader = self.browser.searchForElement(by=By.XPATH,value=passLogInHeaderXPath,
                                              testClickable=True,testLiteralClick=True,timeout=3)
                if(passLogInHeader):
                    passwordFieldXPath = "//input[@type='password']"
                    passwordField = self.browser.searchForElement(by=By.XPATH, value=passwordFieldXPath,testClickable=True,timeout=30)
                    passwordField.clear()
                    passwordField.send_keys(mainConfig["authentication"]["verizonPass"])
                    passwordField.send_keys(Keys.ENTER)
                    # Wait for pass log in header to disappear.
                    self.browser.searchForElement(element=passwordField, timeout=60,testNotStale=False,
                                                  invertedSearch=True)
                #endregion === PASSWORD LOGIN SCREEN ===

                #region === OTP SCREEN ===
                otpHeaderXPATH = "//*[contains(text(),'Verify with phone or email')]"
                otpHeader = self.browser.searchForElement(by=By.XPATH,value=otpHeaderXPATH,
                                              testClickable=True,testLiteralClick=True,timeout=3)
                if(otpHeader):
                    playsoundAsync(paths['media'] / "shaman_attention.mp3")
                    userInput = input("VERIZON WIRELESS: Requesting one time code. Please enter 2FA code, then enter once at VZW main page to continue. Enter anything else to cancel.")
                    if (userInput != ""):
                        error = RuntimeError("User cancelled login process.")
                        log.error(error)
                        raise error
                    # Wait for OTP header to disappear.
                    self.browser.searchForElement(element=otpHeader, timeout=15,testNotStale=False,
                                                  invertedSearch=True)
                #endregion === OTP SCREEN ===

                # We should now be on the main Verizon Homepage - we test this to make sure.
                self.browser.searchForElement(by=By.XPATH, value="//span[contains(text(),'Shop Devices')]",
                                              testClickable=True, timeout=60,raiseError=True)
                self.testForUnregisteredPopup()

    # This method tests for and handles the "X users are still unregistered" popup that sometimes occurs on the
    # Homescreen page.
    def testForUnregisteredPopup(self):
        unregisteredUsersPopupXPath = "//app-notification-dialog//div[contains(text(),'users are still unregistered')]/parent::div/parent::app-notification-dialog"
        unregisteredUsersCloseButtonXPath = f"{unregisteredUsersPopupXPath}//i[contains(@class,'icon-close')]"

        unregisteredUsersCloseButton = self.browser.searchForElement(by=By.XPATH,value=unregisteredUsersCloseButtonXPath,timeout=2)
        if(unregisteredUsersCloseButton):
            unregisteredUsersCloseButton.click()
            self.browser.searchForElement(by=By.XPATH,value=unregisteredUsersCloseButtonXPath,timeout=30,invertedSearch=True,
                                          testClickable=True)
            return True
        else:
            return True

    # This method navigates to the MyBiz homescreen from whatever page Verizon is currently on.
    def navToHomescreen(self):
        self.browser.switchToTab("Verizon")
        homeLink = self.browser.searchForElement(by=By.XPATH,value="//a[@title='Home Link']",timeout=10,testClickable=True)
        homeLink.click()

        # Wait for shop new device button to confirm page load.
        self.browser.searchForElement(by=By.XPATH,value="//span[contains(text(),'Shop Devices')]",timeout=30,testClickable=True)
        self.testForUnregisteredPopup()

    # This method navigates to the Verizon order viewer.
    def navToOrderViewer(self):
        self.browser.switchToTab("Verizon")
        self.testForUnregisteredPopup()

        if(not self.browser.searchForElement(by=By.XPATH,value="//app-view-orders",timeout=2)):
            self.navToHomescreen()
            #try:
            #    viewOrdersLink = self.browser.searchForElement(by=By.XPATH,value="//span[contains(text(),'View Orders')]",timeout=10,raiseError=True)
            #except selenium.common.exceptions.NoSuchElementException:
            #    viewOrdersLink = self.browser.searchForElement(by=By.XPATH,value="//div[contains(@class,'ordersPosition')]",timeout=15,raiseError=True)
            #viewOrdersLink.click()
            self.browser.get("https://mb.verizonwireless.com/mbt/secure/index?transType=ORDERSTATUS#/vieworders")

            # Yes, the typo is intentional lmfao
            viewOrdersHeaderXPath = "//div[contains(@class,'view-orders-conatiner')]//h2[contains(text(),'Orders')]"
            self.browser.searchForElement(by=By.XPATH,value=viewOrdersHeaderXPath,timeout=120,
                                          testClickable=True,testLiteralClick=True)

    #endregion === Site Navigation ===

    #region === Order Viewer ===

    # This method reads the entire displayed order and converts it into a formatted Python
    # dictionary. readUnloadingOrder is a special method for when Verizon orders show up but won't load
    # for unknown reasons, so that it still returns something.
    def OrderViewer_ReadDisplayedOrder(self):
        self.browser.switchToTab("Verizon")
        order = {}

        # Test to prevent "No results found"
        if(self.browser.searchForElement(by=By.XPATH, value="//div[contains(text(),'No Results Found')]",timeout=1)):
            log.warning("Tried to read a displayed Verizon order, but got 'No Results Found' on the order viewer.")
            return None

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
        self.browser.safeClick(element=lineInformationButton,timeout=bodyValueTimeout)
        lineInformation = self.browser.searchForElement(by=By.XPATH,value="//div[@aria-labelledby='tab2']/ul/div/li/div[contains(@class,'column-2')]",timeout=bodyValueTimeout)
        imeiMatch = re.compile(r'Device ID: (\d+)').search(lineInformation.text)
        order["IMEI"] = imeiMatch.group(1) if imeiMatch else None
        simMatch = re.compile(r'SIM ID: (\d+)').search(lineInformation.text)
        order["SIM"] = simMatch.group(1) if simMatch else None

        #endregion === Body Values ===

        log.debug(f"Read this Verizon order: {order}")
        return order

    # This method uses an orderNumber to search for an order on the OrderViewer. Returns True if the order is
    # found, and False if it isn't found. #TODO there used to be "Are you still there?" detection in here, but we're going to move it externally. See Shaman1 for implementation
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
            expandIcon = self.browser.searchForElement(by=By.XPATH,value=foundOrderExpandIconXPath,timeout=1)
            if(expandIcon):
                expandIcon.click()
            return True
        else:
            return False

    #endregion === Order Viewer ===

    #region === Line Viewer ===

    # This method pulls up the given serviceID in Verizon, from anywhere. It cancels out whatever
    # was previously happening.
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
                                          testClickable=True, timeout=15, raiseError=False)
            error = ValueError(f"Verizon is saying that line '{serviceID}' cannot be found.")
            log.error(error)
            raise error
        else:
            upgradeDateHeaderXPath = "//sub[text()='Upgrade date']"
            self.browser.searchForElement(by=By.XPATH, value=upgradeDateHeaderXPath, timeout=120,
                                          testClickable=True, testLiteralClick=True)

    # Assumes we're on the line viewer for a specific line, and clicks "Upgrade device" to begin
    # an upgrade. Also handles ETF shenanigans, so that either way, this function either ends up
    # at the Device Selection page or returns false for lines that can't use waivers.
    def LineViewer_UpgradeLine(self):
        # Helper method to detect and handle potential "mtnPendingError" message on certain upgrade lines.
        def mtnPendingError():
            mtnPendingErrorBoxString = "//app-modal-header/div[contains(text(),'The following wireless number is ineligible for this service.')]"
            mtnPendingErrorBox = self.browser.searchForElement(by=By.XPATH,value=mtnPendingErrorBoxString,timeout=3)
            if(mtnPendingErrorBox):
                mtnPendingErrorCancelButtonString = "//app-modal-invalid-items-list//i[@aria-label='Close-Icon']"
                mtnPendingErrorCancelButton = self.browser.searchForElement(by=By.XPATH,value=mtnPendingErrorCancelButtonString,testClickable=True,timeout=30)
                mtnPendingErrorCancelButton.click()

                upgradeDateHeaderXPath = "//sub[text()='Upgrade date']"
                self.browser.searchForElement(by=By.XPATH,value=upgradeDateHeaderXPath,testClickable=True,testLiteralClick=True,timeout=30,minSearchTime=2)
                return True
            else:
                return False

        # Do this if device is found as eligible for standard upgrade
        upgradeDeviceEligibleButtonXPath = "//button[contains(text(),'Upgrade device')]"
        upgradeDeviceEligibleButton = self.browser.searchForElement(by=By.XPATH,value=upgradeDeviceEligibleButtonXPath,timeout=2)
        if(upgradeDeviceEligibleButton):
            upgradeDeviceEligibleButton.click()
            # Handle cases where clicking the "upgrade" button fails.
            if(not self.browser.searchForElement(by=By.XPATH,value="//div[@id='page-header']//h1[contains(text(),'Shop Devices')]",
                                                 testClickable=True,testLiteralClick=True,timeout=20)):
                if(mtnPendingError()):
                    return "MTNPending"
                else:
                    error = ValueError("Clicking the 'upgrade' button either never loaded or landed at an ambiguous location.")
                    log.error(error)
                    raise error
        # Do this if device is found an ineligible for standard upgrade
        else:
            upgradeDeviceIneligibleButtonXPath = "//a[@type='button'][contains(text(),'Upgrade Options')]"
            upgradeDeviceIneligibleButton = self.browser.searchForElement(by=By.XPATH,value=upgradeDeviceIneligibleButtonXPath,timeout=2)
            if(upgradeDeviceIneligibleButton):
                upgradeDeviceIneligibleButton.click()
                # Handle cases where clicking the "upgrade" button fails.
                upgradeOptionsXPath = "//div/*[contains(text(),'Choose upgrade options for non-eligible lines')]"
                if(not self.browser.searchForElement(by=By.XPATH,value=upgradeOptionsXPath,timeout=15)):
                    if (mtnPendingError()):
                        return "MTNPending"
                    else:
                        error = ValueError("Clicking the 'upgrade' button either never loaded or landed at an ambiguous location.")
                        log.error(error)
                        raise error
                else:
                    upgradeOptionsDropdownXPath = "//button[@class='drop-down-vz']"
                    upgradeOptionsDropdown = self.browser.searchForElement(by=By.XPATH,value=upgradeOptionsDropdownXPath,timeout=15,testClickable=True)
                    upgradeOptionsDropdown.click()

                    waiverOptionXPath = f"{upgradeOptionsDropdownXPath}/following-sibling::ul/li[contains(text(),'Waiver')]"
                    waiverOption = self.browser.searchForElement(by=By.XPATH,value=waiverOptionXPath,timeout=15,testClickable=True)
                    waiverOption.click()

                    elementNotEligibleXPath = "//div[contains(@class,'Notification')][contains(text(),'The wireless number you are attempting to upgrade is not eligible to use a Waiver.')]"
                    if(self.browser.searchForElement(by=By.XPATH,value=elementNotEligibleXPath,timeout=5)):
                        return "NotETFEligible"

                    continueButtonString = "//app-choose-upgrade//button[contains(text(),'Continue')]"
                    continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonString,testClickable=True,timeout=15)
                    continueButton.click()

                    shopDevicesHeaderXPath = "//div[@id='page-header']/div/h1[contains(text(),'Shop Devices')]"
                    self.browser.searchForElement(by=By.XPATH,value=shopDevicesHeaderXPath,testClickable=True,testLiteralClick=True,timeout=120,minSearchTime=5)
            else:
                error = ValueError("Couldn't find ANY upgrade button, whether eligible or ineligible, on the line viewer page!")
                log.error(error)
                raise error
        return True

    #endregion === Line Viewer ===

    #region === Device Ordering ===

    # This method navigates to homescreen, then clicks "shop devices" to begin a new install
    # request.
    def shopNewDevice(self):
        self.browser.switchToTab("Verizon")
        self.testForUnregisteredPopup()

        shopDevicesButton = self.browser.find_element(by=By.XPATH,value="//span[contains(text(),'Shop Devices')]")
        shopDevicesButton.click()

        # Now we wait to ensure that we've fully navigated to the newDevice screen.
        shopDevicesHeaderXPath = "//h2[contains(text(),'Shop Devices')]"
        self.browser.searchForElement(by=By.XPATH,value=shopDevicesHeaderXPath,timeout=120,minSearchTime=5,
                                      testClickable=True,testLiteralClick=True)

    # This method clears the full cart, from anywhere. It cancels out whatever was previously
    # happening, but ensures the cart is fully empty for future automation. Since Verizon is a miserable
    # excuse for a website, sometimes clicking on "clear cart" just literally does nothing. Therefore, this
    # method contains "attempts" parameter which will repeat trying to clear the cart if it seems unsuccessful.
    def emptyCart(self,attempts=2):
        self.navToHomescreen()

        miniCart = self.browser.searchForElement(by=By.XPATH,value="//app-mini-cart/div/div/span",timeout=30,testClickable=True)
        miniCart.click()

        noItemsInCartXPath = "//div[contains(text(),'No items in the cart yet, please continue shopping.')]"
        if (not self.browser.searchForElement(by=By.XPATH,value=noItemsInCartXPath,timeout=2)):
            viewCartButtonXPath = "//button[@clickname='MB View Shopping Cart']"
            viewCartButton = self.browser.searchForElement(by=By.XPATH,value=viewCartButtonXPath,timeout=60,testClickable=True)
            viewCartButton.click()

            for i in range(attempts):
                shoppingCartHeaderXPath = "//div[contains(@class,'device-shopping-cart-content-left')]//h1[contains(text(),'Shopping cart')]"
                self.browser.searchForElement(by=By.XPATH,value=shoppingCartHeaderXPath,timeout=60,testClickable=True,testLiteralClick=True)

                clearCartButtonXPath = "//a[@id='dtm_clearcart']"
                clearCartButton = self.browser.searchForElement(by=By.XPATH,value=clearCartButtonXPath,timeout=30,testClickable=True)
                clearCartButton.click()

                confirmationClearButtonXPath = "//mat-dialog-container//button[text()='Clear']"
                confirmationClearButton = self.browser.searchForElement(by=By.XPATH,value=confirmationClearButtonXPath,timeout=30,testClickable=True)
                confirmationClearButton.click()

                cartCleared = self.browser.searchForElement(by=By.XPATH,value="//h1[text()='Your cart is empty.']",timeout=60,
                                              testClickable=True,testLiteralClick=True)
                if(cartCleared):
                    self.navToHomescreen()
                    return True
                else:
                    continue
            error = RuntimeError(f"Could not successfully clear cart after {attempts} attempts!")
            log.error(error)
            raise error

    # Assumes we're on the device selection page. Given a Universal Device ID, searches for that
    # device (if supported) on Verizon.
    def DeviceSelection_SearchForDevice(self,deviceID,orderPath="NewInstall"):
        searchBox = self.browser.searchForElement(by=By.XPATH,value="//input[@id='search']",timeout=15,testClickable=True)
        searchButton = self.browser.searchForElement(by=By.XPATH,value="//span[contains(@class,'icon-search')]",timeout=15,testClickable=True)

        searchBox.clear()
        searchBox.send_keys(devices[deviceID]["vzwSearchTerm"])
        searchButton.click()

        if(orderPath == "NewInstall"):
            # Now we test to ensure that the proper device card has fully loaded.
            targetDeviceCardXPath = f"//div/div[contains(@class,'device-name')][contains(text(),'{devices[deviceID]['vzwNewInstallCardName']}')]"
            self.browser.searchForElement(by=By.XPATH,value=targetDeviceCardXPath,timeout=60,testClickable=True)
        else:
            # Now we test to ensure that the proper device card has fully loaded.
            targetDeviceCardXPath = f"//div/div[contains(@class,'device-title')][text()='{devices[deviceID]['vzwUpgradeCardName']}']"
            self.browser.searchForElement(by=By.XPATH,value=targetDeviceCardXPath,timeout=60,testClickable=True)
    def DeviceSelection_SelectDevice(self,deviceID,orderPath="NewInstall"):
        if(orderPath == "NewInstall"):
            targetDeviceCardXPath = f"//div/div[contains(@class,'device-name')][contains(text(),'{devices[deviceID]['vzwNewInstallCardName']}')]"
            deviceDetailsXPath = f"//div[contains(@class,'pdp-header-section')]/div[contains(@class,'left-top-details')]/div[contains(text(),'{devices[deviceID]['vzwNewInstallCardName']}')]"
        else:
            targetDeviceCardXPath = f"//div/div[contains(@class,'device-title')][text()='{devices[deviceID]['vzwUpgradeCardName']}']"
            deviceDetailsXPath = f"//div[contains(@class,'pdp-header-section')]//div[contains(text(),'{devices[deviceID]['vzwUpgradeCardName']}')]"

        targetDeviceCard = self.browser.searchForElement(by=By.XPATH,value=targetDeviceCardXPath,timeout=5)
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", targetDeviceCard)
        self.browser.safeClick(element=targetDeviceCard,timeout=10)

        # Test for device details to confirm device has been successfully pulled up.
        self.browser.searchForElement(by=By.XPATH,value=deviceDetailsXPath,timeout=60,minSearchTime=5,
                                      testClickable=True,testLiteralClick=True)
    # Assumes we're in the quick view menu for a device. Various options for this menu.
    def DeviceSelection_DeviceView_Select2YearContract(self,orderPath="NewInstall"):
        if(orderPath == "NewInstall"):
            yearlyContractXPath = "//div[contains(@class,'payment-option-each')]/div[contains(text(),'Yearly contract')]/parent::div"
            yearlyContractSelection = self.browser.searchForElement(by=By.XPATH,value=yearlyContractXPath,timeout=15,testClickable=True)
            yearlyContractSelection.click()

            twoYearContractSelectionXPath = "//div/ul/li/div[contains(text(),'2 Year Contract Required')]/parent::li"
            twoYearContractSelection = self.browser.searchForElement(by=By.XPATH,value=twoYearContractSelectionXPath,timeout=15,testClickable=True)
            self.browser.safeClick(element=twoYearContractSelection,timeout=10,scrollIntoView=True)
        else:
            twoYearContractXPath = "//div[contains(@class,'payment-option-each')]//div[contains(text(),'2 year contract')]"
            twoYearContractSelection = self.browser.searchForElement(by=By.XPATH,value=twoYearContractXPath,timeout=15,testClickable=True,raiseError=True)
            self.browser.safeClick(element=twoYearContractSelection,timeout=10,scrollIntoView=True)
    def DeviceSelection_DeviceView_DeclineDeviceProtection(self):
        declineDeviceProtectionOptionBaseXPath = "//div[contains(text(),'Decline Device Protection')]"
        declineDeviceProtectionOption = self.browser.searchForElement(by=By.XPATH,value=f"{declineDeviceProtectionOptionBaseXPath}/parent::div/parent::div",timeout=15,testClickable=True)
        self.browser.safeClick(element=declineDeviceProtectionOption,timeout=10,scrollIntoView=True,
                               successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=f"{declineDeviceProtectionOptionBaseXPath}[contains(@class,'bold')]"))
    def DeviceSelection_DeviceView_SelectColor(self,deviceID=None,colorName=None,orderPath="NewInstall"):
        if(colorName is None):
            if(deviceID):
                colorName = devices[deviceID]["vzwDefaultColor"]
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

            if(not foundColor):
                error = ValueError(f"Supplied color '{colorName}' does not seem to exist in Verizon Wireless for the searched device!")
                log.error(error)
                raise error
        # Color selection for upgrades is much easier, as the radio buttons are labeled with the actual color name.
        else:
            colorboxXPath = "//div[@class='colorbox']"

            colorSelectionXPath = f"{colorboxXPath}/div[@title='{colorName}']"
            colorSelection = self.browser.searchForElement(by=By.XPATH,value=colorSelectionXPath,timeout=5)
            if(colorSelection):
                self.browser.safeClick(element=colorSelection,timeout=15)
            else:
                error = ValueError(f"Supplied color '{colorName}' does not seem to exist in Verizon Wireless for the searched device!")
                log.error(error)
                raise error
    def DeviceSelection_DeviceView_AddToCartAndContinue(self,orderPath="NewInstall"):
        if(orderPath == "NewInstall"):
            addToCartButtonXPath = "//button[@id='dtm_addcart']"
            addToCartButton = self.browser.searchForElement(by=By.XPATH,value=addToCartButtonXPath,timeout=10,testClickable=True)
            addToCartButton.click()

            # Wait for header confirming device added
            deviceAddedToCartXPath = "//div[contains(text(),'Your new device has been added to your cart.')]"
            self.browser.searchForElement(by=By.XPATH,value=deviceAddedToCartXPath,timeout=30,testClickable=True)

            # Click continue
            continueButtonXPath = "//nav[@id='stickyMenubar']//button[contains(text(),'Continue')]"
            continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonXPath,timeout=30,testClickable=True)
            self.browser.safeClick(element=continueButton,timeout=10,scrollIntoView=True)

            # Wait for accessories page to load
            shopAccessoriesHeaderXPath = "//section[contains(@class,'top-section')]//div[contains(text(),'Shop Accessories')]"
            self.browser.searchForElement(by=By.XPATH,value=shopAccessoriesHeaderXPath,timeout=60,
                                          testClickable=True,testLiteralClick=True)
        else:
            buyNowButtonXPath = "//button[text()='Buy Now']"
            buyNowButton = self.browser.searchForElement(by=By.XPATH,value=buyNowButtonXPath,timeout=10,testClickable=True)
            self.browser.safeClick(element=buyNowButton,timeout=10,scrollIntoView=True)

            # Wait for Shopping Cart page to load to confirm successful device add
            shoppingCartHeaderXPath = "//div[contains(@class,'device-shopping-cart-content-left')]//h1[contains(text(),'Shopping cart')]"
            self.browser.searchForElement(by=By.XPATH,value=shoppingCartHeaderXPath,timeout=60,minSearchTime=5)

    # Assumes we're on the accessory selection page. Given a Universal Accessory ID, searches
    # for that accessory (if support) on Verizon.
    def AccessorySelection_SearchForAccessory(self,accessoryID):
        searchBox = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='search']",timeout=15)
        searchButton = self.browser.waitForClickableElement(by=By.XPATH,value="//button[@id='grid-search-button']",timeout=15)

        searchBox.clear()
        searchBox.send_keys(b.accessories["VerizonMappings"][accessoryID]["SearchTerm"])
        searchButton.click()

        # Now we test to ensure that the proper device card has fully loaded.
        targetAccessoryCard = f"//app-accessory-tile/div/div/div[contains(@class,'product-name')][contains(text(),'{b.accessories['VerizonMappings'][accessoryID]['CardName']}')]"
        self.waitForPageLoad(by=By.XPATH,value=targetAccessoryCard)
    def AccessorySelection_SelectAccessoryQuickView(self,accessoryID):
        targetAccessoryCardString = f"//app-accessory-tile/div/div/div[contains(@class,'product-name')][contains(text(),'{b.accessories['VerizonMappings'][accessoryID]['CardName']}')]"
        targetAccessoryCard = self.browser.find_element(by=By.XPATH,value=targetAccessoryCardString,timeout=5)
        self.browser.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", targetAccessoryCard)
        targetAccessoryQuickViewButton = self.browser.waitForClickableElement(by=By.XPATH, value=f"{targetAccessoryCardString}/parent::div/following-sibling::div/button[contains(@class,'quick-view-btn')]", timeout=15)
        self.browser.simpleSafeClick(element=targetAccessoryQuickViewButton,timeout=20)

        productNameHeaderString = "//div[@class='product-name']/h2/span"
        self.waitForPageLoad(by=By.XPATH,value=productNameHeaderString,testClick=True)
    # Assumes we're in the quick view menu for an accessory. Various options for this menu.
    def AccessorySelection_QuickView_AddToCart(self):
        addToCartButtonString = "//a[contains(text(),'Add to cart')]"
        addToCartButton = self.browser.waitForClickableElement(by=By.XPATH,value=addToCartButtonString)
        addToCartButton.click()

        self.browser.waitForClickableElement(by=By.XPATH,value="//div/div/div[contains(text(),'Nice choice! Your new accessory has been added to your cart.')]",testClick=True)
    def AccessorySelection_QuickView_Close(self):
        closeQuickViewButtonString = "//mat-dialog-container//span[contains(@class,'icon-close')]"
        closeQuickViewButton = self.browser.waitForClickableElement(by=By.XPATH,value=closeQuickViewButtonString)
        closeQuickViewButton.click()

        self.waitForPageLoad(by=By.XPATH,value="//div[text()='Shop Accessories']",testClick=True)
    # Method to continue to the next page after the accessory selection.
    def AccessorySelection_Continue(self,orderPath="NewInstall"):
        continueButtonString = "//div/div/section/div/button[text()='Continue']"
        continueButton = self.browser.waitForClickableElement(by=By.XPATH,value=continueButtonString)
        continueButton.click()

        if(orderPath == "NewInstall"):
            choosePlanHeaderString = "//div/div/div/h1[contains(text(),'Select your new plans')]"
            self.waitForPageLoad(by=By.XPATH,value=choosePlanHeaderString,testClick=True)
        else:
            shoppingCartHeaderString = "//div/div/h1[contains(text(),'Shopping cart')]"
            self.waitForPageLoad(by=By.XPATH, value=shoppingCartHeaderString, testClick=True)

    # Assumes we're on the plan selection page. Given a Plan ID and a plan type,
    # selects it from this page.
    def PlanSelection_SelectPlan(self,planID,planType):
        targetPlanTypeTabString = f"//ul[@class='Tabs-list']/li[contains(@class,'Tab')]/button[@id='{planType}']"
        targetPlanTypeTab = self.browser.waitForClickableElement(by=By.XPATH,value=targetPlanTypeTabString)
        targetPlanTypeTab.click()

        choosePlanHeaderString = "//div/div/div/h1[text()='Select your plan']"
        self.waitForPageLoad(by=By.XPATH,value=choosePlanHeaderString,testClick=True)

        needHelpChoosingPlanBoxString = "//div[@aria-label='Click for assistance via chat.']//img[@title='dismiss chat']"
        needHelpChoosingPlanBox = self.browser.elementExists(by=By.XPATH, value=needHelpChoosingPlanBoxString,timeout=5)
        if (needHelpChoosingPlanBox):
            needHelpChoosingPlanBox.click()
            time.sleep(1)
        targetPlanCardString = f"//div[contains(@class,'plan-card')][@title='Plan ID - {planID}']/div[@class='plan-card-inner']//button[contains(text(),'Select plan')]"
        targetPlanCard = self.browser.find_element(by=By.XPATH,value=targetPlanCardString)
        self.browser.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", targetPlanCard)
        self.browser.simpleSafeClick(element=targetPlanCard,timeout=5)


        self.browser.waitForClickableElement(by=By.XPATH,value="//div[contains(text(),'Continue to the next step.')]")
    # Method to continue to the next page after the plan selection.
    def PlanSelection_Continue(self):
        continueButtonString = "//div/div/button[@id='stickybutton'][contains(text(),'Continue')]"
        continueButton = self.browser.waitForClickableElement(by=By.XPATH,value=continueButtonString)
        continueButton.click()

        deviceProtectionHeader = "//app-equipment-protection-landing-mobile-evolution//div[contains(text(),'Select your device protection')]"
        self.waitForPageLoad(by=By.XPATH,value=deviceProtectionHeader,testClick=True)

    # Assumes we're on the device protection page. Clicks on "decline". Note that this also serves
    # as the "continue" button for this page.
    def DeviceProtection_Decline(self,orderPath="NewInstall"):
        declineDeviceProtectionString = "//button[contains(text(),'Decline device protection')]"
        declineDeviceProtection = self.browser.waitForClickableElement(by=By.XPATH,value=declineDeviceProtectionString)
        declineDeviceProtection.click()

        if(orderPath.lower() == "newinstall"):
            numberAssignPageHeader = "//div/div/div/div[contains(text(),'Assign numbers and users to your new devices.')]"
            self.waitForPageLoad(by=By.XPATH,value=numberAssignPageHeader,testClick=True)
        else:
            accessoriesPageHeader = "//section/div/div[text()='Shop Accessories']"
            self.waitForPageLoad(by=By.XPATH,value=accessoriesPageHeader,testClick=True)

    # Assumes we're on the number selection page. Given an initial zip code, tests that zip code and sequential
    # zip codes to determine the first available.
    def NumberSelection_SelectAreaCode(self,zipCode):
        zipCode = zipCode.split("-")[0]
        zipCodeFormString = "//input[@id='zip']"
        zipCodeForm = self.browser.waitForClickableElement(by=By.XPATH,value=zipCodeFormString)
        areaCodeFormString = "//div[contains(@class,'area-dropdown')]"

        zipCodeToTry = int(zipCode)
        foundAreaCode = False
        for i in range(20):
            zipCodeForm.clear()
            if(zipCodeToTry < 10000):
                zipCodeForm.send_keys(f"0{zipCodeToTry}")
            else:
                zipCodeForm.send_keys(str(zipCodeToTry))

            areaCodeForm = self.browser.waitForClickableElement(by=By.XPATH,value=areaCodeFormString)
            self.browser.simpleSafeClick(element=areaCodeForm)

            self.browser.waitForClickableElement(by=By.XPATH,value="//i[contains(@class,'icon-up-caret')]")

            firstAreaCodeResult = self.browser.elementExists(by=By.XPATH,value=f"{areaCodeFormString}//div/ul/li[@class='ng-star-inserted'][1]",timeout=20)
            if(firstAreaCodeResult):
                firstAreaCodeResult.click()
                foundAreaCode = True
                break
            else:
                noNumbersAvailable = self.browser.elementExists(by=By.XPATH,value="//div[contains(text(),'The city or zip code you entered has no numbers available')]")
                if(noNumbersAvailable):
                    zipCode += 10
                    continue
                else:
                    raise ValueError("No zip codes found, but Verizon isn't raising the expected 'No zip codes found' error. Review order flow to ensure process hasn't changed.")
        if(not foundAreaCode):
            raise ValueError("Couldn't find a valid area code after 20 tries!")

        assignNumbersButtonString = "//button[text()='Assign numbers to all']"
        assignNumbersButton = self.browser.waitForClickableElement(by=By.XPATH,value=assignNumbersButtonString)
        assignNumbersButton.click()

        numberHasBeenAssignedHeaderString = "//div[contains(text(),'You assigned numbers to all your devices. Next, add user information.')]"
        self.waitForPageLoad(by=By.XPATH,value=numberHasBeenAssignedHeaderString,testClick=True)
    # Assumes a number has been selected, as navigates to the add user information page.
    def NumberSelection_NavToAddUserInformation(self):
        addUserInfoButtonString = "//button[text()='Add user information']"
        addUserInfoButton = self.browser.waitForClickableElement(by=By.XPATH,value=addUserInfoButtonString)
        addUserInfoButton.click()

        userInfoHeaderString = "//div[contains(text(),'Add user information to your selected device.')]"
        self.waitForPageLoad(by=By.XPATH,value=userInfoHeaderString,testClick=True)
    # Assumes we're on the user information page. Enters in basic user information.
    def UserInformation_EnterBasicInfo(self,firstName,lastName,email):
        firstNameField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='firstName']")
        firstNameField.clear()
        firstNameField.send_keys(firstName)

        lastNameField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@formcontrolname='lastName']")
        lastNameField.clear()
        lastNameField.send_keys(lastName)

        emailField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@type='email']")
        emailField.clear()
        emailField.send_keys(email)

        time.sleep(1)
        if(self.browser.elementExists(by=By.XPATH,value="//span[contains(text(),'Please enter a valid email address.')]")):
            raise ValueError(f"Verizon believes that email '{email}' is invalid.")
    # Assumes we're on the user information page. Enters in address information.
    def UserInformation_EnterAddressInfo(self,address1,address2,city,stateAbbrev,zipCode):
        editAddressButton = self.browser.waitForClickableElement(by=By.XPATH,value="//span[@class='edit-add-label']")
        editAddressButton.click()

        address1Field = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@formcontrolname='addressLine1']")
        address1Field.clear()
        address1Field.send_keys(address1)

        if(address2 is not None and address2 != ""):
            address2Field = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@formcontrolname='addressLine2']")
            address2Field.clear()
            address2Field.send_keys(address2)

        cityField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@formcontrolname='city']")
        cityField.clear()
        cityField.send_keys(city)

        stateFieldString = "//select[@formcontrolname='state']"
        stateField = Select(self.browser.find_element(by=By.XPATH, value=stateFieldString))
        stateField.select_by_visible_text(stateAbbrev)

        zipCodeField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@formcontrolname='zipCode']")
        zipCodeField.clear()
        zipCodeField.send_keys(zipCode)
    # Saves the user information inputted, which takes us back to the NumberSelection
    def UserInformation_SaveInfo(self):
        saveButtonString = "//div/div/button[text()='Save']"
        saveButton = self.browser.waitForClickableElement(by=By.XPATH,value=saveButtonString)
        saveButton.click()

        userInfoUpdatedSuccessfullyHeaderString = "//div[contains(@class,'colorBackgroundSuccess')]//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'user information')]"
        self.waitForPageLoad(by=By.XPATH,value=userInfoUpdatedSuccessfullyHeaderString,testClick=True)
    # Continues to the next screen from the Number Selection screen, assuming a number has been
    # selected and all user inputted.
    def NumberSelection_Continue(self):
        continueButtonString = "//div[contains(@class,'AS-header')]/button[text()='Continue'][contains(@class,'continue-btn')]"
        continueButton = self.browser.waitForClickableElement(by=By.XPATH,value=continueButtonString)
        continueButton.click()

        shoppingCartHeaderString = "//div/div/h1[contains(text(),'Shopping cart')]"
        self.waitForPageLoad(by=By.XPATH,value=shoppingCartHeaderString,testClick=True,waitTime=3,timeout=3,raiseError=False)

        # Test if Verizon believes the address can't be validated.
        if(self.browser.elementExists(by=By.XPATH,value="//div[contains(text(),'The address could not be validated. Please review and correct.')]")):
            continueButton = self.browser.waitForClickableElement(by=By.XPATH, value=continueButtonString)
            continueButton.click()
            self.waitForPageLoad(by=By.XPATH, value=shoppingCartHeaderString,testClick=True,waitTime=4)


    # Helper method verifies that there is only one line listed in the shopping cart, AND that that line
    # is currently expanded.
    def ShoppingCart_ValidateSingleLine(self):
        allCartLinesXPath = "//*[contains(@class,'dsc-line-list')]/*[@class='ng-star-inserted']"
        allCartLines = self.browser.find_elements(by=By.XPATH,value=allCartLinesXPath)
        if(len(allCartLines) == 0):
            error = RuntimeError("Attempted to validate a single line in the shopping cart, but found zero lines instead!")
            log.error(error)
            raise error
        elif(len(allCartLines) == 1):
            expandLineButtonXPath = f"{allCartLinesXPath}//div[contains(@class,'dsc-line-accordion-icon')]/i"

            # Test to make sure the line is expanded
            closedExpandLineButton = self.browser.searchForElement(by=By.XPATH,value=f"{expandLineButtonXPath}[contains(@class,'icon-plus')]",timeout=1.5)
            if(closedExpandLineButton):
                self.browser.safeClick(element=closedExpandLineButton,timeout=5,
                                       successfulClickCondition=lambda b: b.searchForElement(by=By.XPATH,value=f"{expandLineButtonXPath}[contains(@class,'icon-minus')]"))
        else:
            error = RuntimeError(f"Attempted to validate a single line in the shopping cart, but found {len(allCartLines)} lines instead!")
            log.error(error)
            raise error
    # Assumes we're on the shopping cart overview screen. Simply clicks "check out" to continue
    # to check out screen.
    def ShoppingCart_ContinueToCheckOut(self):
        checkOutButtonString = "//div[contains(@class,'device-shopping-cart-content-right')]/div/button[contains(text(),'Check out')]"
        checkOutButton = self.browser.waitForClickableElement(by=By.XPATH,value=checkOutButtonString)
        self.browser.simpleSafeClick(element=checkOutButton)

        checkoutHeaderString = "//div[@class='checkoutBox']//h1[text()='Checkout']"
        self.waitForPageLoad(by=By.XPATH,value=checkoutHeaderString,testClick=True)
    # From shopping cart, clicks back to add accessories to the given order. For use with upgrades,
    # which ATM bypass the accessory selection screen by default.
    def ShoppingCart_AddAccessories(self):
        # First, validate that they're only one line added.
        self.ShoppingCart_ValidateSingleLine()

        # Then, click on "Add accessories"
        addAccessoriesXPath = "//div[contains(@class,'dsc-add-accessories-btn')]/a[contains(text(),'Add accessories')]"
        addAccessories = self.browser.searchForElement(by=By.XPATH,value=addAccessoriesXPath,timeout=10,testClickable=True)
        addAccessories.click()

        # Finally, wait for Accessories screen to load.
        shopAccessoriesHeaderXPath = "//section[contains(@class,'top-section')]//div[contains(text(),'Shop Accessories')]"
        self.browser.searchForElement(by=By.XPATH, value=shopAccessoriesHeaderXPath, timeout=60,
                                      testClickable=True, testLiteralClick=True)

    # Assumes we're on the checkout screen. Attempts to click on "add address" to add
    # a full address info.
    def Checkout_AddAddressInfo(self,company,attention,address1,city,stateAbbrev,zipCode,contactPhone,
                                notificationEmails : list = None,address2 = ""):
        addNewAddressButtonString = "//div[contains(@class,'new-address')]"
        addNewAddressButton = self.browser.waitForClickableElement(by=By.XPATH,value=addNewAddressButtonString)
        addNewAddressButton.click()

        companyField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='firmName']")
        companyField.clear()
        companyField.send_keys(company)

        attentionField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='attention']")
        attentionField.clear()
        attentionField.send_keys(attention)

        address1Field = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='add1']")
        address1Field.clear()
        address1Field.send_keys(address1)

        if(address2 is not None and address2 != ""):
            address2Field = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='add2']")
            address2Field.clear()
            address2Field.send_keys(address2)

        cityField = self.browser.waitForClickableElement(by=By.XPATH,value="//input[@id='city']")
        cityField.clear()
        cityField.send_keys(city)

        stateSelect = Select(self.browser.waitForClickableElement(by=By.XPATH,value="//select[@id='states']"))
        stateSelect.select_by_visible_text(stateAbbrev)

        contactPhoneField = self.browser.waitForClickableElement(by=By.XPATH, value="//input[@name='phoneNumber']")
        contactPhoneField.clear()
        contactPhoneField.send_keys(contactPhone)

        # First, we remove all existing emails if present.
        existingOldEmails = self.browser.find_elements(by=By.XPATH,value="//input[@type='email']/parent::div/following-sibling::div[@class='remove-btn']")
        for existingOldEmail in existingOldEmails:
            existingOldEmail.click()

        # Now, we add all emails specified as arguments.
        for newEmail in notificationEmails:
            addNewNotifyButtonString = "//div[contains(@class,'add-notify')]/div[contains(text(),'Add new notification')]/parent::div"
            addNewNotifyButton = self.browser.waitForClickableElement(by=By.XPATH,value=addNewNotifyButtonString)
            allOldEmailFields = self.browser.find_elements(by=By.XPATH, value="//input[@type='email']")
            allNewEmailFields = None
            for i in range(5):
                addNewNotifyButton.click()
                allNewEmailFields = self.browser.find_elements(by=By.XPATH, value="//input[@type='email']")
                if(len(allNewEmailFields) > len(allOldEmailFields)):
                    break
                else:
                    time.sleep(1)
                    continue

            allNewEmailFields[-1].clear()
            allNewEmailFields[-1].send_keys(newEmail)

        zipCodeField = self.browser.waitForClickableElement(by=By.XPATH, value="//input[@name='zipCode']")
        zipCodeField.clear()
        zipCodeField.send_keys(zipCode)

        checkoutHeaderString = "//div[@class='checkoutBox']//h1[text()='Checkout']"
        self.waitForPageLoad(by=By.XPATH,value=checkoutHeaderString,testClick=True)

        # Finally, we continue back to payment.
        continueToPaymentButtonString = "//button[contains(text(),'Continue to Payment')]"
        continueToPaymentButton = self.browser.waitForClickableElement(by=By.XPATH,value=continueToPaymentButtonString)
        continueToPaymentButton.click()

        self.waitForPageLoad(by=By.XPATH,value="//div[@class='shipdisplay-method']/h4[text()='Shipping method']",waitTime=3,timeout=3,raiseError=False)
        if(self.browser.elementExists(by=By.XPATH,value="//div[contains(@class,'error-notification')][contains(text(),'Address could not be validated. Please review and correct.')]")):
            continueToPaymentButton = self.browser.waitForClickableElement(by=By.XPATH,value=continueToPaymentButtonString)
            continueToPaymentButton.click()
#
            self.waitForPageLoad(by=By.XPATH, value="//div[@class='shipdisplay-method']/h4[text()='Shipping method']")
        else:
            self.waitForPageLoad(by=By.XPATH, value="//div[@class='shipdisplay-method']/h4[text()='Shipping method']")

        shippingAddressFullString = "//div[@class='shipdisplay-left']/p[contains(@class,'collapse-shipping')]"
        shippingAddressFull = self.browser.waitForClickableElement(by=By.XPATH,value=shippingAddressFullString,testClick=True).text

        if(address2 != ""):
            expectedShippingAddressString = f"{company} ATTN: {attention}\n{address1},{address2}\n{city}, {stateAbbrev} - {zipCode}\nTel: {contactPhone}".lower()
        else:
            expectedShippingAddressString = f"{company} ATTN: {attention}\n{address1}\n{city}, {stateAbbrev} - {zipCode}\nTel: {contactPhone}".lower()


        if(shippingAddressFull.lower().strip() == expectedShippingAddressString.strip()):
            return True
        else:
            return False
    # Assumes address info has been filled, and places the order, returning the order info.
    def Checkout_PlaceOrder(self):
        # TODO only sysco support for rn
        # TODO some glue here, trunactes the -00007 from account. Fine or nah?
        billToAccountButtonString = f"//label[contains(@class,'payment-radio-container')][contains(text(),'Bill to Account')]/span[contains(text(),'{b.clients['Sysco']['Accounts']['Verizon Wireless'].split('-')[0]}')]"
        billToAccountButton = self.browser.waitForClickableElement(by=By.XPATH,value=billToAccountButtonString)
        billToAccountButton.click()

        submitOrderButtonString = "//app-order-total//button[text()='Submit Order']"
        submitOrderButton = self.browser.waitForClickableElement(by=By.XPATH,value=submitOrderButtonString)
        submitOrderButton.click()

        orderSummaryHeaderString = "//h2[text()='Order summary']"
        self.waitForPageLoad(by=By.XPATH,value=orderSummaryHeaderString,testClick=True)

        fullOrderInfoString = "//div[contains(@class,'order-number')]/parent::div"
        return self.browser.waitForClickableElement(by=By.XPATH,value=fullOrderInfoString).text




    #endregion === Device Ordering ===


"//app-device-cards//div[normalize-space(text())='iPhone 14']"