import re
import time
import random
import unicodedata
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.common.paths import paths
from shaman2.common.logger import log
from selenium.common.exceptions import NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException,ElementClickInterceptedException

BAD_ELEMENT_EXCEPTIONS = (NoSuchElementException,StaleElementReferenceException,ElementNotInteractableException,ElementClickInterceptedException)

# This function accepts a phone number in ANY format (assuming it contains an actual phone number an
# no extra numbers), and converts it to one of three forms:
# -dashed (512-819-2010)
# -dotted (512.819.2010)
# -raw    (5128192010)
def convertServiceIDFormat(serviceID, targetFormat):
    # First, strip all non-numeric characters to get the raw format
    rawNumber = re.sub(r'\D', '', serviceID)  # \D matches any non-digit

    # Based on the desired target format, format the raw number accordingly
    if(targetFormat == 'dashed'):
        return f"{rawNumber[:3]}-{rawNumber[3:6]}-{rawNumber[6:]}"
    elif(targetFormat == 'dotted'):
        return f"{rawNumber[:3]}.{rawNumber[3:6]}.{rawNumber[6:]}"
    elif(targetFormat == 'raw'):
        return rawNumber
    else:
        raise ValueError("Invalid target format. Use 'dashed', 'dotted', or 'raw'.")

# This function accepts a string that contains a state represented as either a full name or an
# abbreviation, then converts to either format:
# -abbreviation (TX)
# -name (Texas)
def convertStateFormat(stateString, targetFormat):
    stateDict = {
        "al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas", "ca": "california",
        "co": "colorado", "ct": "connecticut", "de": "delaware", "fl": "florida", "ga": "georgia",
        "hi": "hawaii", "id": "idaho", "il": "illinois", "in": "indiana", "ia": "iowa", "ks": "kansas",
        "ky": "kentucky", "la": "louisiana", "me": "maine", "md": "maryland", "ma": "massachusetts",
        "mi": "michigan", "mn": "minnesota", "ms": "mississippi", "mo": "missouri", "mt": "montana",
        "ne": "nebraska", "nv": "nevada", "nh": "new hampshire", "nj": "new jersey", "nm": "new mexico",
        "ny": "new york", "nc": "north carolina", "nd": "north dakota", "oh": "ohio", "ok": "oklahoma",
        "or": "oregon", "pa": "pennsylvania", "ri": "rhode island", "sc": "south carolina", "sd": "south dakota",
        "tn": "tennessee", "tx": "texas", "ut": "utah", "vt": "vermont", "va": "virginia", "wa": "washington",
        "wv": "west virginia", "wi": "wisconsin", "wy": "wyoming"
    }

    # Clean the user input
    cleanedStateString = re.sub(r'[^a-zA-Z]+', '', stateString).lower()

    # Check if it's an abbreviation or a full name (ignoring spaces)
    if cleanedStateString in stateDict.keys():  # abbreviation format
        stateAbbrev = cleanedStateString
        stateName = stateDict[stateAbbrev]
    elif cleanedStateString in [value.replace(" ", "") for value in stateDict.values()]:  # name without spaces
        # Find the abbreviation by matching the spaceless name
        stateAbbrev = next(key for key, value in stateDict.items() if value.replace(" ", "") == cleanedStateString)
        stateName = stateDict[stateAbbrev]
    else:
        raise ValueError(f"Invalid state string given '{stateString}'")

    # Return in the desired format
    if targetFormat.lower() == "abbreviation":
        return stateAbbrev.upper()
    elif targetFormat.lower() == "name":
        return stateName.title()
    else:
        raise ValueError(f"Invalid targetFormat specified '{targetFormat}'")

# This helper method handles warning the user about something, and allowing them to choose to (C)ontinue (True),
# (S)kip (False) or error out.
def consoleUserWarning(warningMessage,
                       continueMessage = "Continuing.",
                       skipMessage = "Skipping",
                       errorMessage = "User cancelled program runtime due to warning.",
                       addUserInstructionsToWarning = True):
    playsoundAsync(paths["media"] / "shaman_attention.mp3")
    if(addUserInstructionsToWarning):
        warningMessage = warningMessage + " Type Enter or C to (C)ontinue. Type S to (S)kip. Type anything else to cancel program run."
    userResponse = input(warningMessage).strip().lower()
    if(userResponse == "c" or userResponse == ""):
        if(continueMessage):
            print(continueMessage)
        return True
    elif(userResponse == "s"):
        if(skipMessage):
            print(skipMessage)
        return False
    else:
        error = ValueError(errorMessage)
        log.error(error)
        raise error

# This method simply adds a "natural pause", at a random time interval, to break automation detection on sites.
def naturalPause():
    pauseTime = random.uniform(0.3,2.5)

    # Sometimes, add way more time just for realism.
    if(random.random() > 0.85):
        pauseTime += random.randrange(1,11)

    # Wait the time.
    time.sleep(pauseTime)

# This helper method attempts to convert between the many different carrier formats into our one standardized format.
def validateCarrier(carrierString):
    testCarrierString = ("".join(char for char in carrierString if char.isalpha())).lower()
    if("verizon" in testCarrierString or "vzw" in testCarrierString):
        return "Verizon Wireless"
    elif("tmobile" in testCarrierString):
        return "T Mobile"
    elif("bell" in testCarrierString):
        return "Bell Mobility"
    elif("rogers" in testCarrierString):
        return "Rogers"
    elif("att" in testCarrierString):
        return "AT&T Mobility"
    else:
        return None

# This method simply normalizes a name (EX: Takes Jeanné and outputs Jeanne) for use with choosy ordering sites.
def normalizeName(name):
    # Normalize the name to decompose combined characters into base characters + diacritics
    normalized = unicodedata.normalize('NFD', name)
    # Filter out diacritics (Unicode combining marks)
    asciiName = ''.join(char for char in normalized if not unicodedata.combining(char))
    # Return the normalized name
    return asciiName

print(normalizeName("Jeanné"))