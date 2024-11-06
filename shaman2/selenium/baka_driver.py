from selenium.webdriver.common.by import By
from datetime import datetime
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

    # Simple method to test whether Baka is signed in.
    def testIfLoggedIn(self):
        self.browser.switchToTab("Baka")

        signOutButtonString = "//a[contains(text(),'Sign Out')]"
        if(self.browser.searchForElement(by=By.XPATH,value=signOutButtonString,timeout=1)):
            return True
        else:
            return False

    #region === Orders and History ===

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
            elif("imei:" in lowerLine):
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

    #endregion === Orders and History ===
