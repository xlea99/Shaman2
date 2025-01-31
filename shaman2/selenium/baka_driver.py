from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from datetime import datetime
import time
from shaman2.selenium.browser import Browser
from shaman2.common.config import mainConfig
from shaman2.common.logger import log

class BakaDriver:

    # An already created browserObject must be hooked into the BakaDriver to work.
    # Baka runs entirely within the browser object.
    def __init__(self,browserObject : Browser):
        logMessage = "Initialized new BakaDriver object"
        self.browser = browserObject

        if ("Baka" in self.browser.tabs.keys()):
            self.browser.closeTab("Baka")
            logMessage += ", and closed existing Verizon tab."
        else:
            logMessage += "."
        self.browser.openNewTab("Baka")

        self.currentTabIndex = 0
        self.previousTabIndex = 0

        log.debug(logMessage)

    # This method sets the page to the Baka log in screen, then goes through the process of
    # logging in.
    def logInToBaka(self):
        self.browser.switchToTab("Baka")

        if(not self.testIfLoggedIn()):
            self.browser.get("https://www.baka.ca/signin?from=%2F")

            userNameField = self.browser.find_element(by=By.XPATH,value="//input[@id='auth_login']")
            passwordField = self.browser.find_element(by=By.XPATH,value="//input[@id='auth_pass']")
            userNameField.send_keys(mainConfig["authentication"]["bakaUser"])
            passwordField.send_keys(mainConfig["authentication"]["bakaPass"])

            submitButton = self.browser.find_element(by=By.XPATH,value="//button[@type='submit']")
            submitButton.click()

            time.sleep(5)

    # Simple method to test whether Baka is signed in.
    def testIfLoggedIn(self):
        self.browser.switchToTab("Baka")

        signOutButtonString = "//a[contains(text(),'Sign Out')]"
        if(self.browser.searchForElement(by=By.XPATH,value=signOutButtonString,timeout=1)):
            return True
        else:
            return False

    #region === Placed Orders and History ===

    # This method simply navigates to the Baka "Order History" page.
    def navToOrderHistory(self):
        self.browser.switchToTab("Baka")
        self.browser.get("https://www.baka.ca/myaccount/orders")

    # Assuming the driver is currently on the Order History page, this method opens a specific
    # order entry page given by the orderNumber.
    def openOrder(self,orderNumber):
        self.browser.switchToTab("Baka")
        targetOrderEntry = self.browser.searchForElement(by=By.XPATH,value=f"//article/div[@id='{orderNumber}']//a",timeout=3)
        if(targetOrderEntry):
            targetOrderEntry.click()
            return True
        else:
            return False

    # Assuming the driver is currently open to a specific order, this method reads all information
    # about that order into a neatly formatted dictionary, and returns it.
    # TODO do we need to read costs? Or nah?
    def readOrder(self):
        self.browser.switchToTab("Baka")
        orderHeaderDetails = self.browser.find_element(by=By.XPATH,value="//article/header/h2[text()='Order Details']/parent::header/parent::article").text
        orderMainDetails = self.browser.find_element(by=By.XPATH,value="//article/div/h3[text()='Order Details']/parent::div/parent::article").text

        fullDetails = orderHeaderDetails + orderMainDetails
        returnDict = {}
        for line in fullDetails.splitlines():
            lowerLine = line.lower()
            if("reference number:" in lowerLine):
                returnDict["OrderNumber"] = lowerLine.split("reference number:")[1].split("order details")[0].strip().upper()
            elif("status:" in lowerLine):
                returnDict["Status"] = lowerLine.split("status:")[1].split("order details")[0].strip().title()
            elif("order placed on:" in lowerLine):
                dateObj = datetime.strptime(lowerLine.split("order placed on:")[1].split("order details")[0].strip().capitalize(), "%B %d, %Y")
                formattedDateString = dateObj.strftime("%m/%d/%Y")
                returnDict["OrderDate"] = formattedDateString
            elif("purolator #:" in lowerLine):
                returnDict["TrackingNumber"] = lowerLine.split("purolator #:")[1].split("order details")[0].strip().upper()
                returnDict["Courier"] = "Purolator"
            elif("cell number:" in lowerLine):
                returnDict["WirelessNumber"] = lowerLine.split("cell number:")[1].strip()
            elif("agreement number" in lowerLine):
                returnDict["AgreementNumber:"] = lowerLine.split("agreement number:")[1].strip()
            elif("imei" in lowerLine):
                returnDict["IMEI"] = lowerLine.split("imei")[1].lstrip("/ESN:").strip()
            elif("term:" in lowerLine):
                returnDict["Term"] = lowerLine.split("term:")[1].strip().title()
            elif("type:" in lowerLine):
                returnDict["OrderType"] = lowerLine.split("type:")[1].strip().title()
            elif("name of user:" in lowerLine):
                returnDict["UserName"] = lowerLine.split("name of user:")[1].strip().title()
            elif("sim:" in lowerLine):
                returnDict["SIM"] = lowerLine.split("sim:")[1].split("(")[0].strip()

        return returnDict

    #endregion === Placed Orders and History ===

    #region === Ordering ===

    # Navigates to the device selection page for ordering.
    def navToDeviceSelection(self):
        self.browser.switchToTab("Baka")

        deviceSelectionPageURL = "https://www.baka.ca/devices"
        self.browser.get(deviceSelectionPageURL)

        # Wait for page to load.
        mobileSortXPath = "//form[@id='mobile_sort']"
        self.browser.searchForElement(by=By.XPATH,value=mobileSortXPath,timeout=30,testClickable=True)
    # Assumes we're on the device selection page, and tries to select the given device card, then click "Buy Now".
    def DeviceSelection_StartDeviceOrder(self,deviceCardName,deviceProductOverviewHeader):
        self.browser.switchToTab("Baka")

        targetCardXPath = f"//aside[@itemprop='model'][translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{deviceCardName.lower()}']"
        targetCard = self.browser.searchForElement(by=By.XPATH,value=targetCardXPath,timeout=10,testClickable=True)
        targetCard.click()

        # Wait for the product overview to load.
        productOverviewHeaderXPath = f"//article[@class='product-overview']//*[@itemprop='name'][translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{deviceProductOverviewHeader.lower()}']"
        self.browser.searchForElement(by=By.XPATH,value=productOverviewHeaderXPath,timeout=30,raiseError=True)
        time.sleep(3)

        # Now, click "Buy Now".
        buyNowButtonXPath = "//button[@id='product_btn'][normalize-space(text())='Buy Now']"
        buyNowButton = self.browser.searchForElement(by=By.XPATH,value=buyNowButtonXPath,timeout=15,testClickable=True)
        buyNowButton.click()

        # Wait for the order device to load to ensure order process was successfully started
        orderDeviceXPath = f"//article[@id='cart_active_item']//*[@id='order_device'][translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{deviceProductOverviewHeader.lower()}']"
        self.browser.searchForElement(by=By.XPATH,value=orderDeviceXPath,timeout=30,testClickable=True,raiseError=True)
        time.sleep(3)
    # Assumes we're on the order type selection page, and selects the chosen order type.
    def DeviceSelection_ChooseInstallUpgrade(self,orderType : str):
        self.browser.switchToTab("Baka")

        if(orderType.lower() == "install"):
            installRadioXPath = "//span[normalize-space(text())='\"I want to create a new mobile number\"']/parent::label"
            targetRadio = self.browser.searchForElement(by=By.XPATH,value=installRadioXPath,timeout=10,testClickable=True)
        elif(orderType.lower() == "upgrade"):
            upgradeRadioXPath = "//span[normalize-space(text())='\"I want to keep my number\" or \"Upgrade My Device\"']/parent::label"
            targetRadio = self.browser.searchForElement(by=By.XPATH, value=upgradeRadioXPath, timeout=10,testClickable=True)
        else:
            error = ValueError(f"Invalid order type: '{orderType}'")
            log.error(error)
            raise error

        targetRadio.click()

    # Assumes we're on the InstallUpgrade screen, and have selected either "Install" or "Upgrade". Configures each
    # screen according to passed in arguments.
    def InstallConfig_ConfigureInstall(self,name,serviceArea,accountName):
        self.browser.switchToTab("Baka")

        # Write the user's name
        nameFieldXPath = "//input[@id='username']"
        nameField = self.browser.searchForElement(by=By.XPATH,value=nameFieldXPath,timeout=20,testClickable=True)
        nameField.clear()
        nameField.send_keys(name)
        time.sleep(0.5)

        # Select the Service Area
        serviceAreaDropdownXPath = "//select[@id='service_area']"
        serviceAreaDropdown = Select(self.browser.searchForElement(by=By.XPATH,value=serviceAreaDropdownXPath,timeout=20,testClickable=True))
        serviceAreaDropdown.select_by_visible_text(serviceArea)
        time.sleep(0.5)

        # Select "yes" for adding to an existing account.
        yesExistingAccountRadioButtonXPath = "//div[@id='new_activation_existing_account_div']//span[@class='form-radio-name'][normalize-space(text())='Yes']/parent::label"
        yesExistingAccountRadioButton = self.browser.searchForElement(by=By.XPATH,value=yesExistingAccountRadioButtonXPath,timeout=20,testClickable=True)
        yesExistingAccountRadioButton.click()
        time.sleep(0.5)

        # Select the existing account.
        existingAccountDropdownXPath = "//select[@id='bell_account_existing']"
        existingAccountDropdown = Select(self.browser.searchForElement(by=By.XPATH,value=existingAccountDropdownXPath,timeout=20,testClickable=True))
        existingAccountDropdown.select_by_visible_text(accountName)
        time.sleep(0.5)

        # Click continue.
        continueButtonXPath = "//button[@id='activation_submit']"
        continueButton = self.browser.searchForElement(by=By.XPATH,value=continueButtonXPath,timeout=20,testClickable=True)
        continueButton.click()
        time.sleep(0.5)
    def UpgradeConfig_ConfigureUpgrade(self,):
        self.browser.switchToTab("Baka")

        # First, click "yes" to "Is your current plan with Bell Mobility?"
        withBellRadioXPath = "//label[@id='with_bell_label']"
        withBellRadio = self.browser.searchForElement(by=By.XPATH,value=withBellRadioXPath,timeout=20,testClickable=True)
        withBellRadio.click()
        time.sleep(0.5)

        # Now, click "yes" to "Is your current plan with Sysco Foods Canada?"
        withSyscoRadioXPath = "//label[@id='upgrade_account_label']"
        withSyscoRadio = self.browser.searchForElement(by=By.XPATH,value=withSyscoRadioXPath,timeout=20,testClickable=True)
        withSyscoRadio.click()
        time.sleep(0.5)

        # Click "Keep current plan" under "Which plan do you want?"
        keepCurrentPlanRadioXPath = "//label[@id='want_new_plan_no_label']"
        keepCurrentPlanRadio = self.browser.searchForElement(by=By.XPATH,value=keepCurrentPlanRadioXPath,timeout=20,testClickable=True)
        keepCurrentPlanRadio.click()

        # Now we select that the existing line "does" have data
        lineHasDataCheckboxXPath = "//label[@class='checkbox'][@for='has_data_yes']"




    #endregion === Ordering ===



br = Browser()
baka = BakaDriver(br)
baka.logInToBaka()
baka.navToDeviceSelection()
baka.DeviceSelection_StartDeviceOrder("Apple iPhone 13","Apple iPhone 13 128GB (Midnight)")