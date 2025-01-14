from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time
from shaman2.selenium.browser import Browser
from shaman2.common.logger import log
from shaman2.common.config import mainConfig
from shaman2.common.paths import paths
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.utilities import misc

class OutlookDriver:

    # An already created browserObject must be hooked into the OutlookDriver to work.
    # Outlook runs entirely within the browser object. An account name is also an
    # important aspect unique to the OutlookDriver, as multiple Outlook tabs may be open
    # at a time, just to different accounts.
    def __init__(self,browserObject : Browser):
        logMessage = "Initialized new unassigned Outlook object"
        self.browser = browserObject
        self.outlookType = "UNASSIGNED"
        log.debug(logMessage)

    #region === Basic Navigation ===

    # This method logs in to Upland email, and sets this OutlookDriver to Upland type.
    def logInToOutlook_Upland(self):
        #TODO check if already logged in

        # First, open a new tab for this Outlook_Upland driver.
        self.browser.openNewTab("Outlook_Upland")
        self.browser.switchToTab("Outlook_Upland")
        self.outlookType = "Upland"

        # Navigate to outlook.
        self.browser.get("https://outlook.office.com/mail")

        # Enter email (from Jumpcloud email in config)
        emailInputXPath = "//input[@type='email']"
        emailInput = self.browser.searchForElement(by=By.XPATH,value=emailInputXPath,timeout=10)
        emailInput.clear()
        emailInput.send_keys(mainConfig["authentication"]["jumpcloudUser"])
        emailInput.send_keys(Keys.ENTER)

        # Now, we should be on JumpCloud login screen
        jumpcloudSignInHeaderXPath = "//*[normalize-space(text())='Log in to your application using JumpCloud']"
        self.browser.searchForElement(by=By.XPATH,value=jumpcloudSignInHeaderXPath,testClickable=True,testLiteralClick=True,timeout=60)
        jumpcloudEmailInputXPath = "//input[@type='email']"
        jumpcloudEmailInput = self.browser.searchForElement(by=By.XPATH, value=jumpcloudEmailInputXPath, timeout=60)
        jumpcloudEmailInput.clear()
        jumpcloudEmailInput.send_keys(mainConfig["authentication"]["jumpcloudUser"])

        jumpcloudContinueButtonXPath = "//button[@data-automation='loginButton']"
        jumpcloudContinueButton = self.browser.searchForElement(by=By.XPATH, value=jumpcloudContinueButtonXPath,timeout=30)
        jumpcloudContinueButton.click()

        jumpcloudPassInputXPath = "//input[@type='password']"
        jumpcloudPassInput = self.browser.searchForElement(by=By.XPATH, value=jumpcloudPassInputXPath, timeout=60)
        jumpcloudPassInput.clear()
        jumpcloudPassInput.send_keys(mainConfig["authentication"]["jumpcloudPass"])

        jumpcloudContinueButtonXPath = "//button[@data-automation='loginButton']"
        jumpcloudContinueButton = self.browser.searchForElement(by=By.XPATH, value=jumpcloudContinueButtonXPath,timeout=30)
        jumpcloudContinueButton.click()

        # Wait for the MFA screen to load
        verifyIdentityHeaderXPath = "//*[normalize-space(text())='Verify Your Identity']"
        self.browser.searchForElement(by=By.XPATH, value=verifyIdentityHeaderXPath, testClickable=True,
                                      testLiteralClick=True, timeout=60)

        # If the JumpCloud Protect option is listed, click on it.
        jumpcloudProtectMFAXPath = "//button[contains(@data-test-id,'MfaButtons__push')]"
        jumpcloudProtectMFA = self.browser.searchForElement(by=By.XPATH, value=jumpcloudProtectMFAXPath, timeout=1)
        if (jumpcloudProtectMFA):
            jumpcloudProtectMFA.click()

        # Prompt the user to fill in SSO
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        print("Please complete the MFA for JumpCloud to finish Cimpl login. You have 3 minutes remaining before the program crashes.")

        # Wait for the "Stay signed in?" page to load, and handle it.
        staySignedInHeaderXPath = "//div[normalize-space(text())='Stay signed in?']"
        staySignedInHeader = self.browser.searchForElement(by=By.XPATH,value=staySignedInHeaderXPath,timeout=30)
        if (staySignedInHeader):
            yesStaySignedInButtonXPath = "//input[@value='Yes']"
            yesStaySignedInButton = self.browser.searchForElement(by=By.XPATH,value=yesStaySignedInButtonXPath,timeout=10)
            yesStaySignedInButton.click()

        # Wait for the side folder pane to load, to confirm we've signed in correctly.
        sideFolderPaneInboxXPath = "//div[@id='folderPaneDroppableContainer']//span[normalize-space(text())='Inbox']"
        sideFolderPaneInbox = self.browser.searchForElement(by=By.XPATH,value=sideFolderPaneInboxXPath,timeout=60)
        if(sideFolderPaneInbox):
            return True
        else:
            return False

    # This method logs in to the Sysco Ord Box, and sets this OutlookDriver to SyscoOrdBox type. This RELIES
    # on the Upland outlook instance already being open, and will fail without it.
    def logInToSyscoOrdBox(self):
        # Ensure the uplandOutlookDriver is valid.
        if("Outlook_Upland" not in self.browser.tabs.keys()):
            error = ValueError(f"You MUST have an Outlook_Upland driver already logged in in order to open the SyscoOrdBox!")
            log.error(error)
            raise error

        # HAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHA
        """# Open the initials button.
        meInitialsButtonXPath = "//div[@id='meInitialsButton']"
        self.browser.safeClick(by=By.XPATH,value=meInitialsButtonXPath,timeout=10,scrollIntoView=True,jsClick=True)

        # Click "open another mailbox."
        openAnotherMailboxButtonXPath = "//a[@id='mectrl_OwaOpenTargetMailboxLink']"
        self.browser.safeClick(by=By.XPATH,value=openAnotherMailboxButtonXPath,timeout=10,scrollIntoView=True)

        # Wait for the "open another mailbox" dialog to show, then enter the ord box address.
        openAnotherMailboxPromptHeaderXPath = "//div[normalize-space(text())='Open another mailbox']"
        self.browser.searchForElement(by=By.XPATH,value=openAnotherMailboxPromptHeaderXPath,timeout=60)
        openAnotherMailboxPromptInputXPath = f"{openAnotherMailboxPromptHeaderXPath}/parent::div/following-sibling::div//div[@role='textbox']"
        openAnotherMailboxPromptInput = self.browser.searchForElement(by=By.XPATH,value=openAnotherMailboxPromptInputXPath,timeout=30,testClickable=True)
        openAnotherMailboxPromptInput.clear()
        openAnotherMailboxPromptInput.send_keys("sysco_wireless_orders@cimpl.com")

        # Wait for the suggestion to load, then click to open it.
        ordBoxSuggestionXPath = "//button[@type='button'][@aria-label='SysWireLessOrd - sysco_wireless_orders@cimpl.com']"
        ordBoxSuggestion = self.browser.safeClick(by=By.XPATH,value=ordBoxSuggestionXPath,timeout=20,scrollIntoView=True)
        # Confirm the click added the email.
        ordBoxCardXPath = "//span[normalize-space(text())='SysWireLessOrd']"
        self.browser.searchForElement(by=By.XPATH,value=ordBoxCardXPath,timeout=20,raiseError=True)
        # Finally, click open.
        openButtonXPath = "//span[normalize-space(text())='Open']"
        self.browser.safeClick(by=By.XPATH,value=openButtonXPath,timeout=20,scrollIntoView=True)"""

        # Simply open a new tab, and go straight to the outlook account, bypassing logins.
        self.browser.openNewTab(tabName="Outlook_SyscoOrdBox")
        self.browser.switchToTab(tabName="Outlook_SyscoOrdBox")
        self.outlookType = "SyscoOrdBox"
        self.browser.get("https://outlook.office.com/mail/sysco_wireless_orders@cimpl.com/")

    #endregion === Basic Navigation ===

    #region === Email Reading ===

    # This method accepts a single email element, and returns the full content as an emailDict.
    def readSingleEmailPreview(self,emailElement):
        senderEmailXPath = "./div/div[@role='option']/div/div/div/div/div[2]/div[2]/div[1]/div[1]/span"
        subjectXPath = "./div/div[@role='option']/div/div/div/div/div[2]/div[2]/div[2]/div[1]/span"
        timestampXPath = "./div/div[@role='option']/div/div/div/div/div[2]/div[2]/div[2]/span"
        contentXPath = "./div/div[@role='option']/div/div/div/div/div[2]/div[2]/div[3]/div/div[1]/span"

        returnDict = {}

        senderEmailElement = emailElement.find_elements(by=By.XPATH,value=senderEmailXPath)
        if(senderEmailElement):
            returnDict["SenderEmail"] = senderEmailElement[0].get_attribute("title")
        subjectElement = emailElement.find_elements(by=By.XPATH,value=subjectXPath)
        if(subjectElement):
            returnDict["Subject"] = subjectElement[0].text.strip()
        timestampElement = emailElement.find_elements(by=By.XPATH,value=timestampXPath)
        if(timestampElement):
            returnDict["Timestamp"] = timestampElement[0].text.strip()
        contentElement = emailElement.find_elements(by=By.XPATH,value=contentXPath)
        if(contentElement):
            returnDict["ContentPreview"] = contentElement[0].text.strip()

        return returnDict

    # This method simply reads all visible emails in the scroller, and returns them as a list.
    def readAllVisibleEmailPreviews(self):
        self.browser.switchToTab(tabName=f"Outlook_{self.outlookType}")

        allVisibleMessagesXPath = "//div[@id='MailList']//div[contains(@class,'customScrollBar')]/div/div"
        allVisibleMessages = self.browser.find_elements(by=By.XPATH,value=allVisibleMessagesXPath)

        returnList = []
        for visibleMessage in allVisibleMessages:
            # Skip "invisible" messages.
            thisStyleString = visibleMessage.get_attribute("style")
            if("height: 0px;" in thisStyleString):
                continue

            emailDict = self.readSingleEmailPreview(visibleMessage)
            # Skip "ghost" messages.
            if(emailDict):
                returnList.append(emailDict)

        return returnList


    #endregion === Email Reading ===



br = Browser()
uplandOutlook = OutlookDriver(br)
uplandOutlook.logInToOutlook_Upland()
visibleEmails = uplandOutlook.readAllVisibleEmailPreviews()