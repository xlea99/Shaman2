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

class EyesafeDriver:

    # An already created browserObject must be hooked into the EyesafeDriver to work.
    # Eyesafe runs entirely within the browser object.
    def __init__(self,browserObject : Browser):
        logMessage = "Initialized new EyesafeDriver object"
        self.browser = browserObject

        if("Eyesafe" in self.browser.tabs.keys()):
            self.browser.closeTab("Eyesafe")
            logMessage += ", and closed existing Cimpl tab."
        else:
            logMessage += "."
        self.browser.openNewTab("Eyesafe")

        self.currentTabIndex = 0
        self.previousTabIndex = 0

        log.debug(logMessage)

    #region === Site Navigation ===

    # Navigates to and logs in to Eyesafe.
    def logInToEyesafe(self):
        self.browser.switchToTab("Eyesafe")

        # Check if we're on any eyesafe page at the moment.
        if ("eyesafe" in self.browser.current_url):
            # If we are, test if we're signed in by trying to locate a sign in button.
            signInButtonXPath = "//span[contains(text(),'Sign in')]"
            signInButton = self.browser.searchForElement(by=By.XPATH, value=signInButtonXPath, timeout=1)
            if(signInButton):
                signedIn = False
            else:
                signedIn = True
        else:
            signedIn = False

        # First, check that we are actually not signed in. We test to see if we can find the "sign in" button and
        # that we're not on shop.eyesafe to determine this.
        if(not signedIn):
            # Nav to login page
            self.browser.get("https://shop.eyesafe.com/login.php?from=account.php%3Faction%3D")

            # We first deliberately take some time to wait for the dumbass coupon to pop up.
            self.closeCouponPopup(timeout=20)

            # Now, we decline all cookies
            declineAllCookiesButtonXPath = "//div[@id='hs-eu-cookie-confirmation-button-group']/a[@id='hs-eu-decline-button']"
            declineAllCookiesButton = self.browser.searchForElement(by=By.XPATH,value=declineAllCookiesButtonXPath,timeout=10)
            self.browser.safeClick(element=declineAllCookiesButton,timeout=5)

            # Enter credentials
            loginEmailFieldXPath = "//input[@id='login_email']"
            loginEmailField = self.browser.searchForElement(by=By.XPATH,value=loginEmailFieldXPath,timeout=5,testClickable=True)
            loginEmailField.clear()
            loginEmailField.send_keys(mainConfig["authentication"]["eyesafeUser"])

            passwordFieldXPath = "//input[@id='login_pass']"
            passwordField = self.browser.searchForElement(by=By.XPATH,value=passwordFieldXPath,timeout=5,testClickable=True)
            passwordField.clear()
            passwordField.send_keys(mainConfig["authentication"]["eyesafePass"])
            passwordField.send_keys(Keys.ENTER)

            # Search for the "Orders" header to ensure we logged in successfully
            ordersPageHeaderXPath = "//*[@class='page-heading'][text()='Orders']"
            self.browser.searchForElement(by=By.XPATH,value=ordersPageHeaderXPath,timeout=30)
            return True
        else:
            return True

    # Simply searches for and closes the coupon popup.
    def closeCouponPopup(self,timeout=1):
        self.browser.switchToTab("Eyesafe")

        couponPopupXPath = "//a[contains(@class,'close-couponmodal')]"
        couponPopup = self.browser.searchForElement(by=By.XPATH,value=couponPopupXPath,timeout=timeout,testClickable=True)
        if(couponPopup):
            couponPopup.click()

    # Navigates to the order history center.
    def navToOrderViewer(self):
        self.browser.switchToTab("Eyesafe")
        self.browser.get("https://shop.eyesafe.com/account.php?action=order_status")

        # Search for the "Orders" header to ensure we got there successfully
        ordersPageHeaderXPath = "//*[@class='page-heading'][text()='Orders']"
        self.browser.searchForElement(by=By.XPATH,value=ordersPageHeaderXPath,timeout=30)

    # Navigates to the Shop screen.
    def navToShop(self):
        self.browser.switchToTab("Eyesafe")
        self.browser.get("https://shop.eyesafe.com/categories")

        # Search for the "Categories" header to ensure we got there successfully
        categoriesPageHeaderXPath = "//*[@class='page-heading'][text()='Categories']"
        self.browser.searchForElement(by=By.XPATH,value=categoriesPageHeaderXPath,timeout=30)

    #endregion === Site Navigation ===

    #region === Ordering ===

    # This method assumes we're on the shop screen, and adds the item with the given name (as it shows directly
    # on eyesafe) to the cart.
    def addItemToCart(self,itemName : str):
        self.browser.switchToTab("Eyesafe")

        targetCardXPath = f"//article[@class='card ']//a[normalize-space(text())='{itemName}']"
        self.browser.safeClick(by=By.XPATH,value=targetCardXPath,timeout=30)

        # This should bring us to the item details screen. We now find the "add to cart" button and click it.
        addToCartButtonXPath = "//input[@id='form-action-addToCart']"
        self.browser.safeClick(by=By.XPATH,value=addToCartButtonXPath,timeout=30,scrollIntoView=True)

        # NOw we navigate to the cart.
        viewEditCartButtonXPath = "//a[contains(text(),'View or edit your cart')]"
        self.browser.safeClick(by=By.XPATH,value=viewEditCartButtonXPath,timeout=30)

        # Finally we search for the Cart header, to ensure we've successfully gotten there.
        yourCartHeaderXPath = "//*[@class='page-heading'][contains(text(),'Your Cart')]"
        self.browser.searchForElement(by=By.XPATH,value=yourCartHeaderXPath,timeout=20,testClickable=True)

    # This method assumes we're on the cart, and it simply clicks "check out"
    def checkOutFromCart(self):
        self.browser.switchToTab("Eyesafe")

        checkoutButtonXPath = "//a[contains(@class,'button')][text()='Check out']"
        checkoutButton = self.browser.searchForElement(by=By.XPATH,value=checkoutButtonXPath,timeout=5)
        checkoutButton.click()

        # Check for the "Save this address to my address book" link to confirm we're on the checkout screen
        # and that shipping info is showing.
        saveToAddressBookXPath = "//label[contains(text(),'Save this address in my address book.')]"
        self.browser.searchForElement(by=By.XPATH,value=saveToAddressBookXPath,timeout=30,testClickable=True)

    # One giant writeShipping method, as eyesafe's shipping validation is one of the strangest, most inconsistent
    # I've ever seen and needs to be handeled very delicately.
    def writeShippingInformation(self,firstName,lastName,address1,city,state,zipCode,address2=None,maxAttempts=5):
        # Fix zip code to be just 5 numbers
        zipCode = zipCode[:5]

        # This helper method simply "refreshes" the page by navigating back to the cart first, then back here to
        # check out to try again. Assumes we're on the checkout screen.
        def refreshCheckoutScreen():
            # Click the edit cart button.
            editCartLinkXPath = "//a[@id='cart-edit-link']"
            editCartLink = self.browser.searchForElement(by=By.XPATH,value=editCartLinkXPath,timeout=15)
            self.browser.safeClick(element=editCartLink,timeout=15,scrollIntoView=True)

            # Wait for the Cart header, to ensure we've successfully gotten there.
            yourCartHeaderXPath = "//*[@class='page-heading'][contains(text(),'Your Cart')]"
            self.browser.searchForElement(by=By.XPATH, value=yourCartHeaderXPath, timeout=20, testClickable=True)

            # Now, go back to checkout from cart.
            self.checkOutFromCart()

        # This helper method represents one "attempt" to write all shipping info, from beginning to end,
        # assuming that we're on the shipping info page.
        def writeShippingInformationAttempt(promptUserOnIssue):
            # Write First Name
            firstNameFieldXPath = "//input[@id='firstNameInput']"
            firstNameField = self.browser.searchForElement(by=By.XPATH,value=firstNameFieldXPath,timeout=10,testClickable=True)
            firstNameField.clear()
            firstNameField.send_keys(firstName)

            # Write Last Name
            lastNameFieldXPath = "//input[@id='lastNameInput']"
            lastNameField = self.browser.searchForElement(by=By.XPATH,value=lastNameFieldXPath,timeout=3)
            lastNameField.clear()
            lastNameField.send_keys(lastName)

            #region === Zip/City ===

            # First, we test to make sure the "invalid zipcode select from list" dialogue isn't open.
            invalidZipCodePopupXPath = "//div[contains(@class,'ui-dialog-buttonset')]/button/span[text()='OK']"
            self.browser.safeClick(by=By.XPATH,value=invalidZipCodePopupXPath,raiseError=False,timeout=4)

            # Now, enter the zip code
            zipCodeFieldXPath = "//input[@id='postCodeInput']"
            zipCodeField = self.browser.searchForElement(by=By.XPATH,value=zipCodeFieldXPath,timeout=10,testClickable=True)
            # Click to trigger the autofill
            zipCodeField.click()
            # A bit of manual wait time seems to just go a long, long way for this site right here
            time.sleep(1)
            zipCodeField.clear()
            time.sleep(1)
            zipCodeField.send_keys(zipCode)
            time.sleep(2)

            # Now, it should pop up with some options on zip codes mapped to cities. We need to find the option
            # with our target city and click it.
            allZipCityResultsXPath = "//ul[contains(@class,'ui-autocomplete')]/li[@class='ui-menu-item']/a"
            allZipCityResults = self.browser.searchForElements(by=By.XPATH, value=allZipCityResultsXPath,timeout=10)
            # Consider the attempt failed if no zip-cities pop up
            if(not allZipCityResultsXPath):
                return False

            # Otherwise, start looking through each result for our target result
            foundCity = False
            allCities = []
            for zipCityResult in allZipCityResults:
                zipCityResultText = zipCityResult.text
                thisCity = zipCityResultText[6:].strip().lower()
                allCities.append(thisCity)
                if(thisCity == city.strip().lower()):
                    self.browser.safeClick(element=zipCityResult,timeout=10,scrollIntoView=True)
                    foundCity = True
                    break

            # Handle cases where the targeted city is NOT found.
            if(not foundCity):
                potentialError = ValueError(f"Eyesafe didn't show chosen city '{city}' in its result list. Here are the cities it associates with zipCode {zipCode}: {allCities}")
                if(promptUserOnIssue):
                    # TODO GLUEEEEE
                    playsoundAsync(paths["media"] / "shaman_attention.mp3")
                    print(f"Eyesafe doesn't show chosen city '{city}' in its result list. Here are the cities it associates with zipCode {zipCode}:")
                    for counter,cityName in enumerate(allCities):
                        print(f"{counter+1}. {cityName}")
                    userResponse = input("\nIf the intended city is listed, please type its number to order for that city. Press any other non-numeric key to cancel.")
                    if(misc.isNumber(userResponse)):
                        targetIndex = int(userResponse) - 1
                        if(targetIndex < len(allCities)):
                            newTargetCity = allCities[targetIndex]
                            # Return the new targetCity here for reattempt.
                            return newTargetCity
                        else:
                            log.error(potentialError)
                            raise potentialError
                    else:
                        log.error(potentialError)
                        raise potentialError
                else:
                    log.error(potentialError)
                    raise potentialError

            #endregion === Zip/City ===

            # Write State (just in case)
            stateDropdownXPath = "//select[@id='provinceCodeInput']"
            stateDropdown = Select(self.browser.searchForElement(by=By.XPATH, value=stateDropdownXPath, timeout=30))
            stateDropdown.select_by_visible_text(state.strip())

            # Write Address1
            address1FieldXPath = "//input[@id='addressLine1Input']"
            address1Field = self.browser.searchForElement(by=By.XPATH, value=address1FieldXPath, timeout=30)
            address1Field.clear()
            address1Field.send_keys(address1)

            # Write Address2 (if applicable)
            if(address2 is not None and address2 != ""):
                address2FieldXPath = "//input[@id='addressLine2Input']"
                address2Field = self.browser.searchForElement(by=By.XPATH, value=address2FieldXPath, timeout=30)
                address2Field.clear()
                address2Field.send_keys(address2)

            # If we got here, we've succeeded - return True yay!
            return True

        # We simply attempt to writeShippingInformation maxAttempts times, resetting the page on oddities and failures
        for i in range(maxAttempts):
            attemptSuccess = writeShippingInformationAttempt(promptUserOnIssue=True)

            # On success, return True - we did it woooo!
            if(attemptSuccess):
                return True
            # Otherwise, reset and try again.
            else:
                refreshCheckoutScreen()

        # If we leave the for loop without returning True, we've failed :(
        error = RuntimeError(f"Tried to write shipping information {maxAttempts} times, but it was never successful.")
        log.error(error)
        raise error

    # Simply continues from the shipping screen to final checkout, assuming all shipping info is entered.
    def continueFromShipping(self):
        continueFromShippingButtonXPath = "//button[@id='checkout-shipping-continue']"
        continueFromShippingButton = self.browser.searchForElement(by=By.XPATH,value=continueFromShippingButtonXPath,testClickable=True,timeout=30)
        self.browser.safeClick(element=continueFromShippingButton,timeout=5,scrollIntoView=True,raiseError=False)

        # Now, we click "it is correct" on all popups that may show up
        itIsCorrectButtonXPath = "//div[@class='ui-dialog-buttonset']/button/span[text()='It Is Correct']"
        itIsCorrectButton = self.browser.searchForElement(by=By.XPATH,value=itIsCorrectButtonXPath,timeout=5)
        if(itIsCorrectButton):
            self.browser.safeClick(element=itIsCorrectButton,timeout=5,scrollIntoView=True,raiseError=False)

            # Re-click the continue button here, if it's still showing.
            continueFromShippingButtonXPath = "//button[@id='checkout-shipping-continue']"
            continueFromShippingButton = self.browser.searchForElement(by=By.XPATH,value=continueFromShippingButtonXPath,testClickable=True, timeout=30)
            self.browser.safeClick(element=continueFromShippingButton,timeout=5,scrollIntoView=True,raiseError=False)

        # Check that the "Save this address to my address book" link is gone, meaning we're done with shipping.
        saveToAddressBookXPath = "//label[contains(text(),'Save this address in my address book.')]"
        self.browser.searchForElement(by=By.XPATH,value=saveToAddressBookXPath,timeout=30,invertedSearch=True,raiseError=True)

    # Assumes there is an order waiting to be submitted at checkout, and submits it. Also
    # handles "Is ThIs ThE rIgHt AdDrEsS?"
    def submitOrder(self):
        # Click submit
        submitOrderButtonXPath = "//button[@id='checkout-payment-continue']"
        submitOrderButton = self.browser.searchForElement(by=By.XPATH,value=submitOrderButtonXPath)
        self.browser.safeClick(element=submitOrderButton,scrollIntoView=True,timeout=20)


        # We test for Eyesafe's address suggestion now.
        useSuggestionButtonXPath = "//span[contains(text(),'USE SUGGESTION')]"
        useSuggestionButton = self.browser.searchForElement(by=By.XPATH,value=useSuggestionButtonXPath,timeout=10,testClickable=True)
        if(useSuggestionButton):
            continueAsEnteredButtonXPath = "//span[contains(text(),'CONTINUE WITH ADDRESS AS ENTERED')]"
            continueAsEnteredButton = self.browser.searchForElement(by=By.XPATH, value=continueAsEnteredButtonXPath, timeout=10, testClickable=True)
            #TODO gLuEEEEEE
            playsoundAsync(paths["media"] / "shaman_attention.mp3")
            userResponse = input(f"Eyesafe is suggesting a corrected address. Press 1 to use the suggestion, and press 2 to continue with the entered address. Press anything else to cancel.")
            if(userResponse.strip() == "1"):
                self.browser.safeClick(element=useSuggestionButton,timeout=10,scrollIntoView=True)
                # Eyesafe will send us back to the shipping screen, so we continue from it again, then try to submit
                # again.
                self.continueFromShipping()
                self.submitOrder()
            elif(userResponse.strip() == "2"):
                # This will submit the order for us.
                self.browser.safeClick(element=continueAsEnteredButton,timeout=10,scrollIntoView=True)
            else:
                error = RuntimeError(f"User cancelled Eyesafe order.")
                log.error(error)
                raise error

        # Finally, we get the order number and return it.
        orderConfirmationNumberTextXPath = "//p[@data-test='order-confirmation-order-number-text']"
        orderConfirmationNumberText = self.browser.searchForElement(by=By.XPATH,value=orderConfirmationNumberTextXPath,timeout=20,testClickable=True).text
        return orderConfirmationNumberText

    #endregion === Ordering ===