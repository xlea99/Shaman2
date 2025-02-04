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
from shaman2.utilities.shaman_utils import convertStateFormat

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

    shippingAddressOpenXPath = "//legend[@data-test='shipping-address-heading']"
    billingAddressOpenXPath = "//legend[@data-test='billing-address-heading']"
    # This helper method simply "refreshes" the page by navigating back to the cart first, then back here to
    # check out to try again. Assumes we're on the checkout screen.
    def __checkout_refreshCheckoutScreen(self):
        # Click the edit cart button.
        editCartLinkXPath = "//a[@id='cart-edit-link']"
        editCartLink = self.browser.searchForElement(by=By.XPATH, value=editCartLinkXPath, timeout=15)
        self.browser.safeClick(element=editCartLink, timeout=15, scrollIntoView=True)

        # Wait for the Cart header, to ensure we've successfully gotten there.
        yourCartHeaderXPath = "//*[@class='page-heading'][contains(text(),'Your Cart')]"
        self.browser.searchForElement(by=By.XPATH, value=yourCartHeaderXPath, timeout=20, testClickable=True)

        # Now, go back to checkout from cart.
        self.checkOutFromCart()
    # One giant writeShipping method, as eyesafe's shipping validation is one of the strangest, most inconsistent
    # I've ever seen and needs to be handled very delicately.
    def __checkout_writeShippingInformation(self,firstName,lastName,address1,city,state,zipCode,phoneNumber,address2=None):
        # Fix zip code to be just 5 numbers
        zipCode = zipCode[:5]

        # This helper method simply waits until the loader is first found, THEN until it disappears.
        def waitForLoader(timeout=10):
            loaderXPath = "//div[@id='load']"

            # First, find the loader
            loaderFind1 = self.browser.searchForElement(by=By.XPATH,value=loaderXPath,timeout=timeout,testClickable=True)

            # Once its found the first time, now simply wait for it to disappear.
            if(loaderFind1):
                loaderFind2 = self.browser.searchForElement(by=By.XPATH,value=loaderXPath,timeout=60,testClickable=True,invertedSearch=True,raiseError=True)
                return True
            # If it's not found after the full timeout, assume its not going to show up.
            else:
                return True

        # This helper method simply "commits" the change of a single shipping field by clicking off the field onto the
        # page, and waiting for the loader to disappear.
        def commitField(timeout=10):
            customerHeaderToClickXPath = "//h2[contains(text(),'Customer')]"
            self.browser.safeClick(by=By.XPATH,value=customerHeaderToClickXPath,timeout=timeout,scrollIntoView=True)
            waitForLoader(timeout=timeout)

        # This helper method represents one "attempt" to write all shipping info, from beginning to end,
        # assuming that we're on the shipping info page. Also, there's a specific submethod for each part.
        # Because yeah, Eyesafe's shipping screen is THAT shit.
        def writeShipping_FirstName(retries=3):
            for j in range(retries):
                # Write First Name
                firstNameFieldXPath = "//input[@id='firstNameInput']"
                firstNameField = self.browser.searchForElement(by=By.XPATH,value=firstNameFieldXPath,timeout=10,testClickable=True)
                firstNameField.click()
                firstNameField.clear()
                firstNameField.send_keys(firstName)
                commitField()

                # Test that it actually wrote.
                firstNameField = self.browser.searchForElement(by=By.XPATH, value=firstNameFieldXPath, timeout=10,testClickable=True)
                firstNameValue = firstNameField.get_attribute("value")
                if(firstNameValue.strip().lower() == firstName.strip().lower()):
                    return True
            return False
        def writeShipping_LastName(retries=3):
            for j in range(retries):
                # Write Last Name
                lastNameFieldXPath = "//input[@id='lastNameInput']"
                lastNameField = self.browser.searchForElement(by=By.XPATH, value=lastNameFieldXPath, timeout=3)
                lastNameField.clear()
                lastNameField.send_keys(lastName)
                commitField()

                # Test that it actually wrote.
                lastNameField = self.browser.searchForElement(by=By.XPATH, value=lastNameFieldXPath, timeout=10,testClickable=True)
                lastNameValue = lastNameField.get_attribute("value")
                if(lastNameValue.strip().lower() == lastName.strip().lower()):
                    return True
            return False
        def writeShipping_State(retries=3):
            for j in range(retries):
                # Write State (just in case)
                stateDropdownXPath = "//select[@id='provinceCodeInput']"
                stateDropdown = Select(self.browser.searchForElement(by=By.XPATH, value=stateDropdownXPath, timeout=60, minSearchTime=5))
                stateDropdown.select_by_visible_text(convertStateFormat(state,targetFormat="Name"))
                commitField(timeout=3)

                # Test that it actually wrote.
                stateDropdown = Select(self.browser.searchForElement(by=By.XPATH, value=stateDropdownXPath, timeout=60, minSearchTime=5))
                stateValue = stateDropdown.first_selected_option.text
                if(stateValue.strip().lower() == state.strip().lower()):
                    return True
            return False
        def writeShipping_Address1(retries=3):
            for j in range(retries):
                # Write Address1
                address1FieldXPath = "//input[@id='addressLine1Input']"
                address1Field = self.browser.searchForElement(by=By.XPATH, value=address1FieldXPath, timeout=30)
                address1Field.clear()
                address1Field.send_keys(address1)
                commitField()

                # Test to make sure that the "address 1 check" box didn't pop up.
                address1CheckButtonXPath = "//span[normalize-space(text())='It Is Correct']"
                address1CheckButton = self.browser.searchForElement(by=By.XPATH,value=address1CheckButtonXPath,timeout=5,testClickable=True,scrollIntoView=True)
                if(address1CheckButton):
                    address1CheckButton.click()
                    commitField()

                # Test that it actually wrote.
                address1Field = self.browser.searchForElement(by=By.XPATH, value=address1FieldXPath, timeout=10,testClickable=True)
                address1Value = address1Field.get_attribute("value")
                if(address1Value.strip().lower() == address1.strip().lower()):
                    return True
            return False
        def writeShipping_Address2(retries=3):
            for j in range(retries):
                # Write Address1
                address2FieldXPath = "//input[@id='addressLine2Input']"
                address2Field = self.browser.searchForElement(by=By.XPATH, value=address2FieldXPath, timeout=30)
                address2Field.clear()
                address2Field.send_keys(address2)
                commitField()

                # Test to make sure that the "apartment validation" box didn't pop up.
                apartmentValidationXPath = "//span[normalize-space(text())='It Is Correct']"
                apartmentValidation = self.browser.searchForElement(by=By.XPATH,value=apartmentValidationXPath,timeout=5,testClickable=True,scrollIntoView=True)
                if(apartmentValidation):
                    apartmentValidation.click()
                    commitField()

                # Test that it actually wrote.
                address2Field = self.browser.searchForElement(by=By.XPATH, value=address2FieldXPath, timeout=10,testClickable=True)
                address2Value = address2Field.get_attribute("value")
                if(address2Value.strip().lower() == address2.strip().lower()):
                    return True
            return False
        def writeShipping_Phone(retries=5):
            for j in range(retries):
                # Write phone
                print(f"Attempting to write this to Eyesafe phone number: {phoneNumber}")
                phoneFieldXPath = "//input[@id='phoneInput']"
                phoneField = self.browser.searchForElement(by=By.XPATH, value=phoneFieldXPath, timeout=30)
                phoneField.clear()
                phoneField.send_keys(phoneNumber)
                commitField()

                # Test that it actually wrote.
                phoneField = self.browser.searchForElement(by=By.XPATH, value=phoneFieldXPath, timeout=10,testClickable=True)
                phoneValue = phoneField.get_attribute("value")
                if(phoneValue.strip().lower() == phoneNumber.strip().lower()):
                    return True
            return False
        def writeShipping_ZipCity(cityToTry,retries=3,promptUserOnIssue=True):
            for j in range(retries):
                # First, we test to make sure the "invalid zipcode select from list" dialogue isn't open.
                #invalidZipCodePopupXPath = "//div[contains(@class,'ui-dialog-buttonset')]/button/span[text()='OK']"
                #self.browser.safeClick(by=By.XPATH,value=invalidZipCodePopupXPath,raiseError=False,timeout=4)

                # Now, enter the zip code
                zipCodeFieldXPath = "//input[@id='postCodeInput']"
                zipCodeField = self.browser.searchForElement(by=By.XPATH,value=zipCodeFieldXPath,timeout=10,testClickable=True)
                # Click to trigger the autofill
                self.browser.scrollIntoView(zipCodeField)
                zipCodeField.click()
                zipCodeField.clear()
                # We first send a dummy zip code, to trigger the dreaded loader which can kill the whole page.
                if(zipCode[:5] == "60115"):
                    dummyZipCode = "11001"
                else:
                    dummyZipCode = "60115"
                zipCodeField.send_keys(dummyZipCode)
                waitForLoader()

                # Once the loader is gone, we can now send/write our actual zip code.
                zipCodeField = self.browser.searchForElement(by=By.XPATH, value=zipCodeFieldXPath, timeout=10,testClickable=True)
                zipCodeField.click()
                time.sleep(1)
                zipCodeField.clear()
                zipCodeField.clear()
                zipCodeField.send_keys(zipCode)

                # Now, it should pop up with some options on zip codes mapped to cities. We need to find the option
                # with our target city and click it.
                allZipCityResultsXPath = "//ul[contains(@class,'ui-autocomplete')]/li[@class='ui-menu-item']/a"
                allZipCityResults = self.browser.searchForElements(by=By.XPATH, value=allZipCityResultsXPath,timeout=15,minSearchTime=5)
                # Consider the attempt failed if no zip-cities pop up
                if(not allZipCityResults):
                   continue

                # Otherwise, start looking through each result for our target result
                foundCity = False
                allCities = []
                for zipCityResult in allZipCityResults:
                    zipCityResultText = zipCityResult.text
                    log.debug(f" | {zipCityResultText} | ")
                    thisCity = zipCityResultText[6:].strip().lower()
                    allCities.append(thisCity)
                    if(thisCity == cityToTry.strip().lower()):
                        self.browser.safeClick(element=zipCityResult,timeout=10,scrollIntoView=True)
                        foundCity = True
                        break
                # Since it already does the loader BS earlier, it doesn't seem to need this commitField here.
                commitField(timeout=3)


                if(foundCity):
                    return True
                # Handle cases where the targeted city is NOT found.
                else:
                    # First, we test to see if it's just the common "repopulate dummy" zip code issue, and if so,
                    # consider this a failed attempt.
                    if(allCities[0].strip() == ""):
                        continue

                    potentialError = ValueError(f"Eyesafe didn't show chosen city '{cityToTry}' in its result list. Here are the cities it associates with zipCode {zipCode}: {allCities}")
                    if(promptUserOnIssue):
                        # TODO GLUEEEEE
                        playsoundAsync(paths["media"] / "shaman_attention.mp3")
                        print(f"Eyesafe doesn't show chosen city '{cityToTry}' in its result list. Here are the cities it associates with zipCode {zipCode}:")
                        for counter,cityName in enumerate(allCities):
                            print(f"{counter+1}. {cityName}")
                        userResponse = input("\nIf the intended city is listed, please type its number to order for that city. Press any other non-numeric key to cancel.")
                        if(misc.isNumber(userResponse)):
                            targetIndex = int(userResponse) - 1
                            if(targetIndex < len(allCities)):
                                # Try again, with the new city.
                                cityToTry = allCities[targetIndex]
                                continue
                            else:
                                log.error(potentialError)
                                raise potentialError
                        else:
                            log.error(potentialError)
                            raise potentialError
                    else:
                        log.error(potentialError)
                        raise potentialError

            # If we reached max retries, just return false.
            return False
        def writeShipping(promptUserOnIssue):
            if not writeShipping_FirstName():
                return False
            if not writeShipping_LastName():
                return False
            if not writeShipping_ZipCity(cityToTry=city,promptUserOnIssue=promptUserOnIssue):
                return False
            if not writeShipping_State():
                return False
            if not writeShipping_Address1():
                return False
            # Write Address2 (if applicable)
            if(address2 is not None and address2 != ""):
                if not writeShipping_Address2():
                    return False
            if not writeShipping_Phone():
                return False

            # If we got here, we've succeeded - return True yay!
            return True

        # We simply attempt to writeShippingInformation maxAttempts times, resetting the page on oddities and failures
        attemptSuccess = writeShipping(promptUserOnIssue=True)

        # On success, return True - we did it woooo!
        if(attemptSuccess):
            return True
        # Otherwise, return False.
        else:
            return False
    # Simply continues from the shipping/billing screen to final checkout, assuming all info is entered.
    def __checkout_continueFromShippingBilling(self):
        continueFromShippingButtonXPath = "//button[@id='checkout-shipping-continue']"
        continueFromBillingButtonXPath = "//button[@id='checkout-billing-continue']"
        continueFromShippingBillingButton = self.browser.searchForElement(by=By.XPATH,value=[continueFromShippingButtonXPath,continueFromBillingButtonXPath],
                                                                          testClickable=True,timeout=30)
        self.browser.safeClick(element=continueFromShippingBillingButton,timeout=5,scrollIntoView=True,raiseError=False)

        # Now, we click "it is correct" on all popups that may show up
        itIsCorrectButtonXPath = "//div[@class='ui-dialog-buttonset']/button/span[text()='It Is Correct']"
        itIsCorrectButton = self.browser.searchForElement(by=By.XPATH,value=itIsCorrectButtonXPath,timeout=5)
        if(itIsCorrectButton):
            self.browser.safeClick(element=itIsCorrectButton,timeout=5,scrollIntoView=True,raiseError=False)

            # Re-click the continue button here, if it's still showing.
            continueFromShippingBillingButton = self.browser.searchForElement(by=By.XPATH,
                                                                              value=[continueFromShippingButtonXPath,
                                                                                     continueFromBillingButtonXPath],
                                                                              testClickable=True, timeout=30)
            self.browser.safeClick(element=continueFromShippingBillingButton,timeout=5,scrollIntoView=True,raiseError=False)

    # Single function to handle the actual clusterfuck that is the eyesafe checkout process in an intelligent, adaptable
    # way. Assumes we're on the checkout page to start.
    def checkOutAndSubmit(self,firstName,lastName,address1,city,state,zipCode,phoneNumber,address2=None):
        shippingAddressOpenXPath = "//legend[@data-test='shipping-address-heading']"
        billingAddressOpenXPath = "//legend[@data-test='billing-address-heading']"
        submitOrderReadyXPath = "//button[@id='checkout-payment-continue']"
        useSuggestionButtonXPath = "//span[contains(text(),'USE SUGGESTION')]"
        orderConfirmationNumberTextXPath = "//p[@data-test='order-confirmation-order-number-text']"

        checkoutPagesMap = {shippingAddressOpenXPath : "ShippingOpen",billingAddressOpenXPath: "BillingOpen",
                            submitOrderReadyXPath : "SubmitReady", orderConfirmationNumberTextXPath: "OrderConfirmation",
                            useSuggestionButtonXPath: "UseSuggestionAlert",}

        editShippingButtonXPath = "//li[contains(@class,'checkout-step--shipping')]//button[@data-test='step-edit-button']"

        # Begin loop to manage checkout logic.
        shippingEnteredSuccessfully = False
        for i in range(12):
            print(f"ATTEMPT {i}")
            # First, get the current page we're on.
            foundElement, pageName = self.browser.searchForElement(by=By.XPATH, value=checkoutPagesMap,
                                                                   testClickable=True,timeout=30,scrollIntoView=True,
                                                                   raiseError=True, logError=False,minSearchTime=3)

            # If shipping is open, handle it here.
            if(pageName == "ShippingOpen"):
                # If shipping was already entered, but is for some reason open again, try to continue from it.
                if(shippingEnteredSuccessfully):
                    self.__checkout_continueFromShippingBilling()
                    # Wait until shipping is closed.
                    self.browser.searchForElement(by=By.XPATH, value=shippingAddressOpenXPath, timeout=30,
                                                  invertedSearch=True, raiseError=True)
                # Otherwise, enter all shipping info.
                else:
                    writeShippingInfoSuccess = self.__checkout_writeShippingInformation(
                        firstName=firstName,lastName=lastName,address1=address1,
                        address2=address2,city=city,zipCode=zipCode,state=state,
                        phoneNumber=phoneNumber)
                    if(writeShippingInfoSuccess):
                        shippingEnteredSuccessfully = True
                        self.__checkout_continueFromShippingBilling()
                        # Wait until shipping is closed.
                        self.browser.searchForElement(by=By.XPATH, value=shippingAddressOpenXPath, timeout=30,
                                                      invertedSearch=True, raiseError=True)
                    # If shipping didn't write successfully for some reason, refresh the entire checkout process to
                    # hopefully try again.
                    else:
                        self.__checkout_refreshCheckoutScreen()
            # If billing is open, reopen shipping to re-enter it.
            elif(pageName == "BillingOpen"):
                editShippingButton = self.browser.searchForElement(by=By.XPATH, value=editShippingButtonXPath,
                                                                   testClickable=True, scrollIntoView=True)
                self.browser.safeClick(element=editShippingButton, scrollIntoView=True, timeout=10)
                # Trigger shipping to write again.
                shippingEnteredSuccessfully = False
            # If the "Use Suggestion" popup is open, handle it here.
            elif(pageName == "UseSuggestionAlert"):
                continueAsEnteredButtonXPath = "//span[contains(text(),'CONTINUE WITH ADDRESS AS ENTERED')]"
                continueAsEnteredButton = self.browser.searchForElement(by=By.XPATH, value=continueAsEnteredButtonXPath,
                                                                        timeout=10, testClickable=True)
                # TODO gLuEEEEEE
                playsoundAsync(paths["media"] / "shaman_attention.mp3")
                userResponse = input(
                    f"Eyesafe is suggesting a corrected address. Press 1 to use the suggestion, and press 2 to continue with the entered address. Press anything else to cancel.")
                # Use the suggestion.
                if (userResponse.strip() == "1"):
                    self.browser.safeClick(element=foundElement, timeout=10, scrollIntoView=True)
                # Continue with the entered address.
                elif (userResponse.strip() == "2"):
                    # This will submit the order for us.
                    self.browser.safeClick(element=continueAsEnteredButton, timeout=10, scrollIntoView=True)
                else:
                    error = RuntimeError(f"User cancelled Eyesafe order.")
                    log.error(error)
                    raise error
            # If the submit button is ready, handle that here.
            elif(pageName == "SubmitReady"):
                # If shipping was entered, submit the order.
                if(shippingEnteredSuccessfully):
                    # This can sometimes be intercepted by late arriving messages. If so, give it grace and don't
                    # raise error - just continue with logic.
                    print("trying to click submit")
                    self.browser.safeClick(element=foundElement, scrollIntoView=True, timeout=15,raiseError=False)
                # If shipping wasn't entered, open it up here and continue with logic.
                else:
                    editShippingButton = self.browser.searchForElement(by=By.XPATH,value=editShippingButtonXPath,testClickable=True,scrollIntoView=True)
                    self.browser.safeClick(element=editShippingButton,scrollIntoView=True,timeout=10)
                    time.sleep(2)
            # If the order confirmation pops up, grab it and return it!
            elif(pageName == "OrderConfirmation"):
                orderConfirmationNumberText = foundElement.text
                return orderConfirmationNumberText

        error = RuntimeError(f"Went through more than 12 iterations of checkout logic without exiting - review process.")
        log.error(error)
        raise error

    #endregion === Ordering ===