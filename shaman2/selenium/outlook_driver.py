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
        self.browser.openNewTab("Eyesafe")

        self.currentTabIndex = 0
        self.previousTabIndex = 0

        log.debug(logMessage)