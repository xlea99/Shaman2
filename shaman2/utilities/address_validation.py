import requests
import re
import json
from openai import OpenAI
from shaman2.common.logger import log
from shaman2.common.paths import paths
from shaman2.common.config import mainConfig
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.utilities.misc import isNumber


#region === OSM Nominatim Validation ===

# Uses OSMN to simply get a state, given a zip code. (Canada OR US)
def getStateFromZip(zip_code):
    # Define the OSM Nominatim URL and parameters for searching by postal code
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': zip_code,
        'format': 'json',
        'addressdetails': 1,  # Request detailed address breakdown
        'limit': 1,  # Limit results to 1 for faster response
        'countrycodes': 'CA,US'  # Restrict search to US and Canada
    }

    headers = {
        'User-Agent': 'Shaman2App/1.0 (shaman2.backlands898@simplelogin.com)'
    }

    # Make the request to Nominatim
    response = requests.get(url, params=params, headers=headers)

    # Check if we got a valid response
    if response.status_code == 200:
        results = response.json()
        if results:
            # Extract the address details from the first result
            address = results[0].get('address', {})
            # Look for 'state' or 'province' field
            state = address.get('state', None)
            if state:
                return state
            else:
                return None
        else:
            return None
    else:
        error = PermissionError(f"Failed to fetch data: HTTP {response.status_code}")
        log.error(error)
        raise error

# Uses OSM Nominatim to attempt to validate the user's address.
def osmnValidateAddress(_address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': _address,
        'format': 'json',
        'addressdetails': 1,
        'limit': 20,
        'countrycodes': 'CA,US'
    }

    headers = {
        'User-Agent': 'Shaman2App/1.0 (shaman2.backlands898@simplelogin.com)'
    }

    _response = requests.get(url, params=params, headers=headers)
    return _response.json()

#endregion === OSM Nominatim Validation ===

#region === ChatGPT Validation ===

client = OpenAI(api_key=mainConfig["authentication"]["openAIKey"])
# Uses ChatGPT to classify an address into its parts, and ignore all the random bullshit that users
# add.
classifyAddressQuery = """You are an address classifier bot, who specializes in identifying the various parts of a shipping address given to you by one of our users for ordering. Our users often make mistakes or inconsistencies when writing their shipping addresses, including putting Street Name and Unit/Apt Number out of order, forgetting a state, or writing their city in it twice.

Your job is simply to classify the various parts of a raw user address string into its parts in the json format shown below: 

{returnAddressFormat}

If anything seems to be missing, instead map it to a json "null" like this: "City": null

Put the whole result into a single code block using 3 `. Provide a very brief explanation beforehand. Note that some users may add a lot of extraneous information that can simply be removed, such as Attention To, Company Names, PHone Numbers, or even Devliery Instructions. Your only focus is on finding the 5 parts listed in the example, and ignoring everything else.

Here is the address below:

{rawAddress}
"""
returnAddressFormat = '''```
{
    "Address1": "street name/number",
    "Address2": "unit, apartment, building number etc, ONLY if applicable (is often not present in every address)",
    "City": "city name",
    "State": "state/province",
    "ZipCode": "zip/postal code"
}
```'''
def gptClassifyAddress(_rawAddress):
    _response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an address validation assistant."},
            {"role": "user", "content": classifyAddressQuery.format(returnAddressFormat=returnAddressFormat,
                                                                    rawAddress=_rawAddress)}
        ],
        temperature=0
    )

    return _response.choices[0].message.content
# Simply extracts only the address dict from GPT's response
def extractAddressFromGPTResponse(gptResponseString):
    pattern = r'```(.*?)```'
    match = re.findall(pattern, gptResponseString, re.DOTALL)
    rawAddressDict = json.loads(match[0].strip())

    cleanedAddressDict = {}
    cleanedAddressDict["Address1"] = rawAddressDict["Address1"]
    cleanedAddressDict["Address2"] = rawAddressDict["Address2"]
    cleanedAddressDict["City"] = rawAddressDict["City"]
    cleanedAddressDict["State"] = rawAddressDict["State"]

    # Zip Code cleaning
    if(rawAddressDict.get("ZipCode")):
        cleanedAddressDict["ZipCode"] = rawAddressDict["ZipCode"]
    elif(rawAddressDict.get("Zip")):
        cleanedAddressDict["ZipCode"] = rawAddressDict["Zip"]
    elif(rawAddressDict.get("Zip Code")):
        cleanedAddressDict["ZipCode"] = rawAddressDict["Zip Code"]
    elif(rawAddressDict.get("Zip code")):
        cleanedAddressDict["ZipCode"] = rawAddressDict["Zip code"]
    elif(rawAddressDict.get("Zipcode")):
        cleanedAddressDict["ZipCode"] = rawAddressDict["Zipcode"]

    return cleanedAddressDict

#endregion === ChatGPT Validation ===

# Main function, simply accepts an address string, handles edge cases, and spits out a refined address.
#TODO handle these in GUI later, to avoid crashing program and instead prompt user for decision making
def validateAddress(rawAddressString : str):
    # First, we take a raw address string given by a user and classify it using ChatGPT.
    classifiedAddressResponse = gptClassifyAddress(_rawAddress=rawAddressString)
    classifiedAddress = extractAddressFromGPTResponse(gptResponseString=classifiedAddressResponse)

    # If specifically the state is missing, we can easily resolve this by querying OSMN one extra time.
    if(classifiedAddress["State"] is None):
        classifiedAddress["State"] = getStateFromZip(classifiedAddress["ZipCode"][:5])

    # Now, we check the address with OSMN (along with removing the address2 to avoid confusion).
    osmnAddressToTest = f"{classifiedAddress['Address1']}, " if classifiedAddress["Address1"] is not None else ""
    osmnAddressToTest += f"{classifiedAddress['City']}, " if classifiedAddress["City"] is not None else ""
    osmnAddressToTest += f"{classifiedAddress['State']}, " if classifiedAddress["State"] is not None else ""
    osmnAddressToTest += f"{classifiedAddress['ZipCode'][:5]}, " if classifiedAddress["ZipCode"] is not None else ""

    # Default behavior is to crash when no Address1 is found at all.
    if(classifiedAddress["Address1"] is None):
        error = ValueError(f"ChatGPT thinks that user included literally no street address. Here's its classifiedAddress: '{classifiedAddress}'")
        log.error(error)
        raise error

    if(classifiedAddress["City"] is None):
        userResponse = input(f"The user's shipping address is missing a CITY. Please enter a city name, then press enter to continue.")
        classifiedAddress["City"] = userResponse.strip().capitalize()
    if(classifiedAddress["State"] is None):
        userResponse = input(f"The user's shipping address is missing a STATE. Please enter a state name, then press enter to continue.")
        classifiedAddress["State"] = userResponse.strip().capitalize()
    if(classifiedAddress["ZipCode"] is None):
        userResponse = input(f"The user's shipping address is missing a ZIPCODE. Please enter a zipcode name, then press enter to continue.")
        classifiedAddress["ZipCode"] = userResponse.strip().capitalize()

    # Finally, we return our classified, validated address.
    return classifiedAddress