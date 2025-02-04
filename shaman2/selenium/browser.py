from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement
import time
from typing import Callable
from urllib.parse import urlparse
from shaman2.common.logger import log
from shaman2.common.paths import paths
import datetime
import os
import zipfile
import requests
from win32api import GetFileVersionInfo, LOWORD, HIWORD


class Browser(webdriver.Chrome):

    # Init method initializes members of class, and opensBrowser if true.
    def __init__(self):
        # Get the user's current chrome version
        self.userChromeVersion = None
        self.__getUserChromeVersion()

        # Sets up the chromedriver path, managing version downloading.
        self.chromeDriverPath = None
        self.__setupChromeDriver()

        # Setup browserOptions
        self.__browserOptions = None
        self.__setupBrowserOptions()

        # Initialize the browser Service using the webdriver path
        self.__service = Service(self.chromeDriverPath)

        # Build the actual Browser
        super().__init__(service=self.__service, options=self.__browserOptions)

        # Initialize some member variables
        self.tabs = {}
        self.popupTabs = {}
        self.currentTab = None
        self.currentTabIsPopup = False
        self.tabs["Base"] = self.window_handles[0]
        self.currentTab = "Base"

        log.debug("Finished init for Browser object.")

    # Sets up, and returns, a hardened BrowserOptions object for use with the Browser.
    def __setupBrowserOptions(self):
        # Create a chrome options and set needed options
        chromeOptions = webdriver.ChromeOptions()
        chromeOptions.add_experimental_option("prefs", {
            "download.default_directory": str(paths["downloads"]),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })

        # Suppress WebDriver-related automation flags
        chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
        chromeOptions.add_experimental_option("useAutomationExtension", False)

        # Set a realistic User-Agent to avoid default Selenium identifier
        chromeOptions.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )

        # Disable logging to reduce noise (optional but helpful)
        chromeOptions.add_argument("--log-level=3")

        # Enable a full windowed browser experience
        chromeOptions.add_argument("--start-maximized")

        # Disable headless mode detection (if used)
        chromeOptions.add_argument("--disable-blink-features=AutomationControlled")

        # Enable consistent browser fingerprinting
        chromeOptions.add_argument("--disable-extensions")
        chromeOptions.add_argument("--disable-popup-blocking")
        chromeOptions.add_argument("--profile-directory=Default")

        # TODO chromeOptions.add_argument("--user-data-dir=/path/to/your/custom/profile")  # Optional: mimics a logged-in user

        # Disable the WebRTC leak to hide local IP
        chromeOptions.add_argument("--disable-webrtc")

        # Disable password manager prompts
        chromeOptions.add_argument("--disable-save-password-bubble")

        # Sets the Browser object's options to our result.
        self.__browserOptions = chromeOptions

    # This method simply gets the Chrome version that the user currently has installed
    def __getUserChromeVersion(self):
        chromePath1 = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        chromePath2 = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        if (os.path.exists(chromePath1)):
            userChromePath = chromePath1
        elif (os.path.exists(chromePath2)):
            userChromePath = chromePath2
        else:
            error = FileNotFoundError("Chrome not found in standard installation paths.")
            raise error

        try:
            # Get version info from the executable
            info = GetFileVersionInfo(userChromePath, "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            version = f"{HIWORD(ms)}.{LOWORD(ms)}.{HIWORD(ls)}.{LOWORD(ls)}"
            self.userChromeVersion = version
        except Exception as e:
            raise ValueError(f"Could not fetch Chrome version from '{userChromePath}', with this error:\n\n{e}")

    # This method, given that local class variable self.userChromeVersion is found, downloads the latest
    # chromedriver version for that given version if it doesn't already exist in bin.
    def __setupChromeDriver(self):
        if(self.userChromeVersion is None):
            error = ValueError(f"Trying to download ChromeDriver without userChromeVersion found!")
            log.error(error)
            raise error
        else:
            # First, make sure the install folder exists
            installFolder = paths["chromedriver"] / self.userChromeVersion
            if(not os.path.exists(installFolder)):
                os.mkdir(installFolder)
            os.chmod(installFolder, 0o777)

            # Check that we haven't already downloaded a chromedriver for this version of chrome.
            targetChromedriverInstallPath = installFolder / "chromedriver.exe"
            if(os.path.exists(targetChromedriverInstallPath)):
                return True
            else:
                # Check that .zip exists for this version
                chromeDriverURL = f"https://storage.googleapis.com/chrome-for-testing-public/{self.userChromeVersion}/win64/chromedriver-win64.zip"
                headResponse = requests.head(chromeDriverURL)
                if(headResponse.status_code == 200):
                    # If it does, download it to our install folder.
                    fileResponse = requests.get(chromeDriverURL)
                    zipPath = installFolder / f"chromedriver_{self.userChromeVersion}.zip"
                    with open(zipPath, "wb") as f:
                        for chunk in fileResponse.iter_content(chunk_size=8192):
                            f.write(chunk)
                        log.info(f"Downloaded new chromedriver.zip version ({self.userChromeVersion})")
                    time.sleep(1)
                    os.chmod(zipPath,0o777)

                    # Extract chromedriver.exe
                    with zipfile.ZipFile(installFolder / f"chromedriver_{self.userChromeVersion}.zip","r") as zipRef:
                        zipRef.extractall(installFolder)

                    # Clean up the zip file
                    os.remove(installFolder / f"chromedriver_{self.userChromeVersion}.zip")

                    # Set the new chromedriver path.
                    self.chromeDriverPath = installFolder / "chromedriver-win64/chromedriver.exe"

                # Otherwise, raise error - will likely require manual intervention
                else:
                    error = FileNotFoundError(f"ChromeDriverAPI returned non 200 status code: '{headResponse.status_code}'")
                    log.error(error)
                    raise error

    #region === Tab Management ===

    # This method simply opens a new tab to the given URL, and returns the window
    # handle. It also adds the tab to self.tabs, storing it under the "name" name.
    # If no URL is given, it simply opens a blank tab.
    def openNewTab(self,tabName,url = ""):
        previousWindowList = set(self.window_handles)

        self.execute_script(f"window.open('{url}');")

        newWindowList = set(self.window_handles)
        newHandle = (newWindowList - previousWindowList).pop()
        self.tabs[tabName] = newHandle
        self.currentTab = tabName

        log.debug(f"Opened new tab '{tabName}' with this url: {url[:20]}")
    # This method handles closing the given tabName. If the tabName does not exist,
    # it throws an error unless "raiseError" is false.
    def closeTab(self,tabName,popup=False,raiseError=True):
        # Always prevent closing of Base tab.
        if(tabName == "Base"):
            return False

        # Handle closing of a regular tab.
        if(tabName in self.tabs.keys() and popup is False):
            self.switchToTab(tabName,popup=False)
            self.close()
            self.switchToTab("Base",popup=False)
            log.debug(f"Closed regular tab '{tabName}'.")
            return True
        # Handle closing of a popup tab.
        elif(tabName in self.popupTabs.keys() and popup is True):
            self.switchToTab(tabName,popup=True)
            self.close()
            self.switchToTab("Base",popup=False)
            log.debug(f"Closed POPUP tab '{tabName}'.")
            return True
        # Do this if the target tabName isn't found - either raise an error or warning.
        else:
            if(raiseError):
                log.critical(f"Could not close tab with name '{tabName}', as it doesn't exist.")
                raise ValueError(f"The tab '{tabName}' does not appear to exist in the tabs list:\n{str(self.tabs.keys())}")
            else:
                log.warning(f"Could not close tab with name '{tabName}', as it doesn't exist.")
                return False
    # This method simply allows for the renaming of one tabName to another. If previousTabName
    # doesn't exist OR newTabName already exists, it'll raise an error.
    def renameTab(self,previousTabName,newTabName,popup=False,raiseError=True):
        # Always prevent renaming to or of Base
        if(previousTabName == "Base" or newTabName == "Base"):
            error = ValueError("Cannot rename a tab to/from Base!")
            if(raiseError):
                log.error(error)
                raise error
            else:
                log.warning(error)
                return False

        # Protect against renaming a tab to a tabName that already exists
        if(newTabName in self.tabs.keys() or newTabName in self.popupTabs.keys()):
            error = ValueError(f"New tab name '{newTabName}' already exists!")
            if (raiseError):
                log.error(error)
                raise error
            else:
                log.warning(error)
                return False

        # If the previousTabName is a normal tab.
        if(not popup and previousTabName in self.tabs.keys()):
            thisTabContent = self.tabs[previousTabName]
            self.tabs[newTabName] = thisTabContent
            del self.tabs[previousTabName]
        elif(popup and previousTabName in self.popupTabs.keys()):
            thisTabContent = self.popupTabs[previousTabName]
            self.popupTabs[newTabName] = thisTabContent
            del self.popupTabs[previousTabName]
        # Handle the previousTabName not existing.
        else:
            error = ValueError(f"Could not rename tab with name '{previousTabName}', as it doesn't exist.")
            if(raiseError):
                log.error(error)
                raise error
            else:
                log.warning(error)
                return False

    # This method allows switching to the given tabName. If the tabName does not
    # exist, it throws an error.
    def switchToTab(self,tabName,popup=False):
        try:
            if(self.currentTab == tabName and self.tabs.get(self.currentTab) == self.current_window_handle):
                onTargetTab = True
            else:
                onTargetTab = False
        except selenium.common.exceptions.NoSuchWindowException:
            onTargetTab = False

        # If we're already on the target tab, nothing more needs to be done.
        if(onTargetTab):
            return True

        # If the target tab is a basic tab, simply use the self.tabs dict to switch to the mapped
        # window handle.
        if(tabName in self.tabs.keys() and popup is False):
            self.switch_to.window(self.tabs[tabName])
            self.currentTab = tabName
            self.currentTabIsPopup = False
            log.debug(f"Switched to regular tab '{tabName}'.")
            return True
        # If the target tab is a popup tab, instead use the self.popupTabs dict to switch to the mapped
        # window handle of the popup tab.
        elif(tabName in self.popupTabs.keys() and popup is True):
            self.switch_to.window(self.popupTabs[tabName])
            self.currentTab = tabName
            self.currentTabIsPopup = True
            log.debug(f"Switched to POPUP tab '{tabName}'.")
            return True
        # If the tabName requested doesn't exist, treat it as an error and raise it.
        else:
            log.error(f"Tab name '{tabName}' does not exist to open.")
            raise ValueError(f"The tab '{tabName}' does not appear to exist in the tabs list:\n{str(self.tabs.keys())}")

    # This method checks to find, and then store, any 'popupTabs' that might have
    # appeared. These are tabs that were NOT opened using the "openNewTab" method
    # and are usually the result of automation from a different tab. It returns a
    # list of newly found popup tabs and removed popup tabs by their popupTabName.
    def checkForPopupTabs(self):
        changedTabs = {"newPopupTabs" : [], "removedPopupTabs" : []}

        # First, we check for new popup tabs.
        for windowHandle in self.window_handles:
            if(windowHandle not in self.tabs.values() and windowHandle not in self.popupTabs.values()):
                self.switch_to.window(windowHandle)

                # Wait until the URL netloc is non-empty, or a timeout occurs.
                try:
                    WebDriverWait(self, 5).until(lambda driver: urlparse(driver.current_url).netloc != '')
                except selenium.common.exceptions.TimeoutException:
                    log.warning(f"Timeout: Popup tab's URL did not load within the expected time. Handle: {windowHandle}")

                # Once we have the URL, we parse it.
                parsedURL = urlparse(self.current_url)
                domain = parsedURL.netloc

                # Store the popup tab and add it to the changed tabs.
                while domain in self.popupTabs.keys():
                    domain += "_new"
                changedTabs["newPopupTabs"].append(domain)
                self.popupTabs[domain] = windowHandle

                # Switch back to the current tab after processing popup
                self.switchToTab(self.currentTab, popup=False)

        # Next, we check for stale popup tabs.
        tabsToRemove = []
        for popupTabName, windowHandle in self.popupTabs.items():
            if(windowHandle not in self.window_handles):
                changedTabs["removedPopupTabs"].append(popupTabName)
                tabsToRemove.append(popupTabName)

        removedCurrentTab = False
        for tabToRemove in tabsToRemove:
            self.popupTabs.pop(tabToRemove)
            if(self.currentTabIsPopup and tabToRemove == self.currentTab):
                removedCurrentTab = True

        # Do this if it's detected that the popup tab that Shaman thinks we're on right now has been closed.
        if(removedCurrentTab):
            self.switchToTab(tabName="Base")

        log.debug(f"Checked for changedTabs, found these changes: {changedTabs}")
        return changedTabs

    #endregion === Tab Management ===

    #region === Element Manipulation ===

    # This advanced element finder/tester method provides the ability to both test for the status of an
    # element, new or existing, on the page, as well as returning it.
    #
    # by -      Search method for the given value (By.XPATH, By.CSS_SELECTOR). Requires a value to be specified
    # value -   Search term to search for using the method specified by "by" (a literal xpath or CSS selector)
    #           Supports MULTIPLE values as a list - will search each value sequentially, considering the first one found the first success.
    #           If a DICT is provided, mapped as {SeleniumIdentifier : "Alias"}, it'll return both the alias and the found element when the given value is found.
    # element - An existing WebElement to test on. Can't use with by/value
    # timeout - How long to search for, at minimum. Defaults to zero to run exactly one test.
    # minSearchTime -           Ensures that, even if the test initially passes, it keeps searching for the element until this time has been reached. If the search fails even after first succeeding, the whole search is considered failed.
    # testNotStale -            Tests that the element is not considered "stale"
    # testClickable -           Tests that the element is considered "clickable"
    # testScrolledInView -      Tests that the element is scrolled into view
    # testLiteralClick -        ACTUALLY attempts to click the element, for when certain elements report as clickable but still somehow aren't.
    # scrollIntoView -          Whether to attempt to scroll the element into view, BEFORE doing tests.
    # invertedSearch -          Inverts the search - instead of searching for presence of element, searches for LACK of element on page
    # raiseError/logError -     Whether to raise and log the error when the test fails, or simply return "False"
    # singleTestInterval -      How long to perform each single test for, defaulting at 0.2 seconds per test.
    # shadowRootStack -         Specifies an element that exists in a shadowRoot, or a nested shadowRoot. First attempts to scope into the root (first to last), before searching for the element. Each entry should be a dict as (by:by,value:value,extraElementTests:extraElementTests,withSubElement:withSubElement)
    # extraElementTests -       Provides the ability to run extra tests on the element after it's found, but before declaring the search successful. Provides as a stack of lambdas evaluating a boolean (lambda el: el.get_attribute("beans") == "pinto")
    # TODO is this enough to defeat Verizon's weird elements that selenium believes are clickable, but secretly aren't yet?
    def searchForElement(self,by = None,value : (str,list,dict) = None,element : WebElement = None,timeout : float = 0, minSearchTime : float = 0,
                         testNotStale = True,testClickable = False,testScrolledInView = False,testLiteralClick = False,
                         invertedSearch = False,scrollIntoView=False,raiseError = False,logError = None,singleTestInterval = 0.1,debug=False,
                         shadowRootStack : list = None,extraElementTests : list = None):
        # Throw error if both a value and an element are given
        if(value and element):
            error = ValueError("Both a value and an element cannot be specified together in searchForElement.")
            log.error(error,stack_info=True)
            raise error
        # Unless logError is specified, we copy the value of raiseError
        if(logError is None):
            logError = raiseError

        # Convert value to a identifierList for standardized processing.
        if(type(value) is str or value is None):
            identifierList = [value]
        elif(type(value) is dict):
            identifierList = list(value.keys())
        else:
            identifierList = value

        lastException = None
        minTestTime = time.time() + minSearchTime
        endTestTime = time.time() + timeout
        searchAttempt = 0
        wait = WebDriverWait(self, singleTestInterval)
        while(searchAttempt < 1 or time.time() < endTestTime):
            searchAttempt += 1
            try:
                # First, specify the root - unless there's a shadowRootStack, this is always the browser itself.
                if(shadowRootStack):
                    root = self
                    for selector in shadowRootStack:
                        allPotentialShadowHosts = root.find_elements(by=selector["by"],value=selector["value"])#,extraElementTests=selector.get("extraElementTests",None))

                        # Evaluate any "extraElementTests" conditions to determine list of all valid shadow hosts
                        if(selector.get("extraElementTests",None)):
                            allValidShadowHosts = []
                            for potentialShadowHost in allPotentialShadowHosts:
                                for extraElementTest in selector["extraElementTests"]:
                                    try:
                                        if extraElementTest(potentialShadowHost):
                                            allValidShadowHosts.append(potentialShadowHost)
                                    except Exception as e:
                                        pass
                        else:
                            allValidShadowHosts = allPotentialShadowHosts

                        # Raise error (fail test) if no valid shadow hosts are found.
                        if (len(allValidShadowHosts) == 0):
                            raise selenium.common.exceptions.NoSuchElementException(f"No valid shadow hosts found with selector '{selector['value']}'")

                        # Test for any specific sub elements if specified.
                        if(selector.get("withSubElement")):
                            targetShadowHost = None
                            for validShadowHost in allValidShadowHosts:
                                tempRoot = self.execute_script("return arguments[0].shadowRoot",validShadowHost)
                                withSubElementTestResult = tempRoot.find_elements(by=selector["withSubElement"]["by"],value=selector["withSubElement"]["value"])
                                if(withSubElementTestResult):
                                    # Evaluate any "extraElementTests" conditions on the sub element to determine its validity
                                    if (selector["withSubElement"]["extraElementTests"]):
                                        for thisSubElement in withSubElementTestResult:
                                            for extraElementTest in selector["withSubElement"]["extraElementTests"]:
                                                try:
                                                    if extraElementTest(thisSubElement):
                                                        # This means we've located the subelement with tests, and this is our target shadow host.
                                                        targetShadowHost = validShadowHost
                                                        break
                                                except Exception as e:
                                                    pass
                                            if(targetShadowHost):
                                                break
                                    else:
                                        # This means we've located the subelement, and this is our target shadow host.
                                        targetShadowHost = validShadowHost
                                # Break loop if the targetShadowHost has been found.
                                if(targetShadowHost):
                                    break
                            if(not targetShadowHost):
                                raise selenium.common.exceptions.NoSuchElementException(f"No valid shadow hosts found with selector '{selector['value']}'")
                        else:
                            targetShadowHost = allValidShadowHosts[0]

                        root = self.execute_script("return arguments[0].shadowRoot",targetShadowHost)
                else:
                    root = self

                # If element is not provided, test to find it by locator
                if(not element):
                    nextIdentifier = identifierList[searchAttempt % len(identifierList)]
                    if(debug):
                        log.debug(f"Attempting selenium find_element for next identifier: {nextIdentifier}")
                    targetElement = root.find_element(by=by,value=nextIdentifier)
                else:
                    nextIdentifier = None
                    targetElement = element
                    # If it's an inverted search AND a given element, we simply try to take a sample attribute to ensure
                    # it still exists.
                    if(invertedSearch):
                        test = targetElement.text

                if(scrollIntoView):
                    self.scrollIntoView(targetElement)

                # Perform various other tests if specified
                if(testNotStale):
                    wait.until(wait_for_non_stale_element(targetElement))
                if(testClickable):
                    wait.until(EC.element_to_be_clickable(targetElement))
                if(testScrolledInView):
                    wait.until(wait_for_element_scrolled_in_viewport(targetElement))
                if(testLiteralClick):
                    self.safeClick(element=targetElement,timeout=singleTestInterval,raiseError=True,logging=False)

                if(extraElementTests):
                    for extraElementTest in extraElementTests:
                        if not extraElementTest(targetElement):
                            raise selenium.common.exceptions.NoSuchElementException(f"Extra test {extraElementTest} failed on element {targetElement}.")

                # === TESTS PASS ===
                # If all tests pass, and this is an inverted search, that means the element is still present and we
                # need to continue testing (if timeout allows)
                if(invertedSearch):
                    time.sleep(0.1)
                    # Set the next valueIndex to test, in case there's multiple.
                    continue
                # If all tests pass, and this is a standard search, return the element
                else:
                    # However, as a caveat, if minTestTime hasn't been reached, we ignore success and keep searching.
                    if(time.time() >= minTestTime):
                        if(debug):
                            log.debug(f"Searched successfully for element with {searchAttempt} search attempts.")
                        if(type(value) is dict):
                            return targetElement,value[nextIdentifier]
                        else:
                            return targetElement
                    else:
                        time.sleep(0.1)
                        # Set the next valueIndex to test, in case there's multiple.
                        continue

            # === TESTS FAIL ===
            except Exception as e:
                lastException = e
                # If the tests didn't pass, and this is an inverted search, that means the element is considered to
                # be lacking from the page, and we're done.
                if(invertedSearch):
                    # Again, as a caveat, if minTestTime hasn't been reached, we ignore success and keep searching.
                    if(time.time() >= minTestTime):
                        if(debug):
                            log.debug(f"InvertedSearched successfully for element with {searchAttempt} search attempts.")
                        if(type(value) is dict):
                            return True,None
                        else:
                            return True
                    else:
                        time.sleep(0.1)
                        continue
                # If the tests didn't pass, and this is a regular search, that means the element is not yet
                # considered "found" and we continue testing (if timeout allows)
                else:
                    time.sleep(0.1)
                    continue

        # If timeout expires without success, return False or raise an error
        if(raiseError):
            if(invertedSearch):
                error = selenium.common.exceptions.NoSuchElementException(f"InvertedSearched for element, but element persisted on page past timeout after {searchAttempt} search attempts.")
                if(logError):
                    log.error(error,stack_info=True)
                raise error
            else:
                if (logError):
                    log.error(lastException,stack_info=True)
                raise lastException
        else:
            if(debug):
                log.debug(f"Failed to successfully{" inverted" if invertedSearch else ""} search for element after {searchAttempt} search attempts.")
            if(type(value) is dict):
                return False,None
            else:
                return False

    # Similar, but much simpler searchForElements which searches for multiple elements at once and is only concerned
    # with the amount of elements returned.
    def searchForElements(self, by, value, timeout : float = 0, minSearchTime : float = 0,
                          invertedSearch = False, raiseError = False, pollInterval = 0.1):
        minTestTime = time.time() + minSearchTime
        endTestTime = time.time() + timeout
        searchAttempt = 0
        searchSuccessful = False
        while (searchAttempt < 1 or time.time() < endTestTime):
            searchAttempt += 1
            # Try to find elements
            targetElements = self.find_elements(by=by, value=value)

            # Do this if no elements are present in the return.
            if(len(targetElements) == 0):
                # If this is an inverted search, since we found no elements we consider the search successful.
                if (invertedSearch):
                    if(time.time() >= minTestTime):
                        searchSuccessful = True
                        break
                    else:
                        time.sleep(pollInterval)
                        continue
                # Otherwise, we keep testing.
                else:
                    time.sleep(pollInterval)
                    continue
            # Do this if elements are present in the return
            else:
                # If this is an inverted search, we keep looking since elements are still found.
                if (invertedSearch):
                    time.sleep(pollInterval)
                    continue
                # Otherwise, we consider the search successful.
                else:
                    if (time.time() >= minTestTime):
                        searchSuccessful = targetElements
                        break
                    else:
                        time.sleep(pollInterval)
                        continue

        # If timeout expires without success, return False or raise an error
        if (searchSuccessful):
            return searchSuccessful
        else:
            if(raiseError):
                error = ValueError(f"Failed to successfully{" inverted" if invertedSearch else ""} search for elements after {searchAttempt} search attempts.")
                log.error(error,stack_info=True)
                raise error
            else:
                return False


    # This advanced element clicker method provides the ability to "soft" or "fuzzy" click on an element that
    # may be highly volatile (thanks TMA), using various methods and condition testing to do so. Any condition
    # passed in must be a method of the Browser object (I.E. should be a searchForElement lambda function) like so:
    #
    # browser.safeClick(by=By.XPATH,value="//button",condition=lambda b: b.searchForElement(element=existingElement,invertedSearch=True)
    #
    # by -      Search method for the given element to click (By.XPATH, By.CSS_SELECTOR). Requires a value to be specified
    # value -   Search term to search for using the method specified by "by" (a literal xpath or CSS selector) to click. Can be a list of elements.
    # element - An existing WebElement to attempt to click on. Can't use with by/value
    # timeout - How long to attempt to click for, at minimum. Defaults to zero to run exactly one click attempt.
    # successfulClickCondition -    A condition that will be tested AFTER a made click to determine whether it was considered "successful" or not.
    # prioritizeCondition -         This means that the condition comes before all when determining click success, even the click itself. Other error messages will be ignored as long as condition is true.
    # jsClick -                     Whether to click using javascript, or selenium
    # raiseError -                  Whether to raise an error after unsuccessful click and timeout.
    # logError -                    Whether to log an error after unsuccessful click and timeout.
    # retryClicks -                 Whether multiple clicks should even be attempted on first failed click.
    # minClicks/maxClicks -         Configurable min and max clicks to attempt, regardless of success.
    # testInterval -                Time interval to wait between element searches.
    # clickDelay -                  Time to wait between successive click attempts.
    # scrollIntoView -              Attempts to scroll the element into view before each click.
    def safeClick(self,element : WebElement = None,by = None,value : (str,list) = None,timeout : float = 0,
                  successfulClickCondition : Callable = None,prioritizeCondition = True, jsClick=False,raiseError=True,logging=True,scrollIntoView=False,
                  retryClicks = False,minClicks : int = 0,maxClicks : int = 10**10,testInterval=0.5,clickDelay=0):
        # Throw error if both a value and an element are given
        if(value and element):
            error = ValueError("Both a value and an element cannot be specified together in safeClick.")
            if(logging):
                log.error(error,stack_info=True)
            raise error

        # Helper method to evaluate if the condition is currently true.
        def evaluateCondition():
            # If condition exists, evaluate it. Otherwise, consider it successful by default.
            if(successfulClickCondition):
                return successfulClickCondition(self)
            else:
                return True

        lastException = None
        testAttempt = 0
        clickCount = 0
        clickSuccessful = False
        endTime = time.time() + timeout
        nextClickTime = time.time()
        # Begin the click loop
        while (testAttempt < 1 or time.time() < endTime):
            hasEvaluatedConditionThisLoop = False
            testAttempt += 1
            try:
                # Get the element, searching for it if necessary
                if(element):
                    targetElement = element
                else:
                    targetElement = self.searchForElement(by=by,value=value,timeout=testInterval,raiseError=True,logError=False)

                # Attempt to scroll into view if specified. Adds a sleep to make sure the action is finished.
                if(scrollIntoView):
                    self.scrollIntoView(targetElement)
                    time.sleep(1)

                # Attempt to click if we still have clicks left and retryClicks is True.
                if ((clickCount == 0 or (retryClicks and clickCount < maxClicks)) and time.time() >= nextClickTime):
                    if(jsClick):
                        self.execute_script("arguments[0].click();", targetElement)
                    else:
                        targetElement.click()
                    clickCount += 1
                    nextClickTime = time.time() + clickDelay

                if (clickCount >= minClicks):
                    hasEvaluatedConditionThisLoop = True
                    if(evaluateCondition()):
                        clickSuccessful = True
                        break


                # This means that a click was "made", but considered unsuccessful. We raise an error, to be caught
                # and potentially handled further in our except block.
                raise TimeoutError(f"safeClick on element '{element if element else value}' unsuccessful after {testAttempt} click attempts and {clickCount} actual clicks.")


            except Exception as e:
                lastException = e
                # If this click has a prioritizedCondition, we evaluate the condition here.
                if(prioritizeCondition and successfulClickCondition is not None):
                    if(not hasEvaluatedConditionThisLoop):
                        if(evaluateCondition()):
                            if(clickCount >= minClicks):
                                clickSuccessful = True
                                break
                time.sleep(testInterval)

        # Return a boolean or raise error depending on whether the click was successful or not.
        if(clickSuccessful):
            if (logging):
                log.debug(f"safeClick on element '{element if element else value}' successful after {testAttempt} click attempts and {clickCount} actual clicks.")
            return True
        else:
            if(raiseError):
                if(logging):
                    log.error(lastException,stack_info=True)
                raise lastException
            else:
                if(logging):
                    log.warning(lastException)
                return False


    #endregion === Element Manipulation ===

    #region === Tests ===

    # Simply tests whether the element is considered "checked" or not.
    def testForSelectedElement(self,by = None, value : str = None,element : WebElement = None,inverted=False):
        # Throw error if both a value and an element are given
        if(value and element):
            error = ValueError("Both a value and an element cannot be specified together in safeClick.")
            log.error(error,stack_info=True)
            raise error

        if(value):
            element = self.searchForElement(by=by,value=value)

        if(inverted):
            return not element.is_selected()
        else:
            return element.is_selected()


    #endregion === Tests ===

    #region === Utilities ===

    # Simply waits until the given URL string can be found in the browser's URL.
    def waitForURL(self,urlSnippet,timeout=30,raiseError=True):
        endTime = time.time() + timeout

        testCount = 0
        while testCount < 1  or time.time() < endTime:
            testCount += 1
            # If URL is found, we return True as the wait is done.
            if(urlSnippet in self.current_url):
                return True
            else:
                time.sleep(0.5)

        # If we've reached the endTime without finding the URL, the wait failed.
        errorMessage = f"Waited for URL: '{urlSnippet}' on page, but URL was never found after timeout of {timeout}"
        if(raiseError):
            error = RuntimeError(errorMessage)
            log.error(error,stack_info=True)
            raise error
        else:
            log.warning(errorMessage)
            return False

    # Takes a "snapshot" of the given tabName, saving a screenshot and the HTML of the full DOM at the time of
    # taking to the log folder.
    def snapshotTab(self,tabName=None,popup=False):
        if(tabName is None):
            tabName = self.currentTab
        elif((tabName not in self.tabs and not popup) or (tabName not in self.popupTabs and popup)):
            log.error(f"Cannot take snapshot: Tab '{tabName}' does not exist.",stack_info=True)
            raise ValueError(f"Tab '{tabName}' does not exist.")
        self.switchToTab(tabName=tabName,popup=popup)

        # Create a unique filename based on the current timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fileBaseName = f"{tabName}_snapshot_{timestamp}"

        # Define file paths
        htmlFilePath = paths["snapshots"] / f"{fileBaseName}.html"
        screenshotFilePath = paths["snapshots"] / f"{fileBaseName}.png"

        # Save the HTML content to a file
        html_content = self.page_source  # Gets the HTML content of the current tab
        with open(htmlFilePath, "w", encoding="utf-8") as file:
            file.write(html_content)
        log.debug(f"HTML snapshot saved to '{htmlFilePath}'")

        # Save the screenshot to a file
        self.save_screenshot(screenshotFilePath)
        log.debug(f"Screenshot saved to '{screenshotFilePath}'")

        return htmlFilePath, screenshotFilePath

    # Simply scrolls the given element into view.
    def scrollIntoView(self,element : WebElement):
        self.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

    # Attempts to hover the given element.
    def hoverElement(self,element : WebElement):
        actions = ActionChains(self)
        actions.move_to_element(element).perform()

    #endregion === Utilities ===


# A few custom expected condition classes.
class wait_for_non_stale_element(object):
    def __init__(self, element):
        self.element = element

    def __call__(self, driver):
        try:
            # Access an attribute of the element to ensure it is not stale.
            test = self.element.text
            return self.element  # Return the element if it's not stale.
        except selenium.common.exceptions.StaleElementReferenceException:
            return False
class wait_for_element_scrolled_in_viewport(object):
    def __init__(self, element):
        self.element = element

    def __call__(self, driver):
        return driver.execute_script("""
            var rect = arguments[0].getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        """, self.element)