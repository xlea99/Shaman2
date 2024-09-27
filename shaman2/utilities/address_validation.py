import requests
import re
import json
import time
from openai import OpenAI
from shaman2.common.logger import log
from shaman2.common.config import mainConfig

#region === OSM Nominatim Validation ===

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

# Uses ChatGPT to check for any oddities in the address compared to the OSMN address (unit numbers in Address1,
# for example) and refines it.
client = OpenAI(api_key=mainConfig["authentication"]["openAIKey"],)
chatGPTAddressQuery = """
    You are an address validation assistant. You are a part of a program called "Shaman2" which automates
    phone orders for a carrier. As a part of the phone ordering process, users submit address to us, which 
    we then take to the carrier (Verizon, AT&T, Bell Mobility, Rogers, etc.) to input into a shipping field
    to send the phone to. However, quite often, users will input addresses that aren't quite valid, have typos,
    or other mistakes. Our form is really quite simple - it contains space for an Address1 (street address), 
    Address2 (apartment/complex number), City, State/Province, Zip/Area Code. However, our uses sometimes still
    manage to get confused enough to do things like entering the Apartment Number into Address1 and the street
    number into Address2, or entering both into Address1, etc. Sometimes, the address they list simply don't exist,
    or validate to a slightly different city or zip code.

    To remedy this, we use a 2-step address validation system. In this system, you are **Part 2**. Part one involves
    using a request to OpenStreetMaps Nominatim to attempt to validate the address. The function "validateOSM" accepts
    a single string, which we rip straight from the address that the user gave us, and it returns a formatted OSMN
    object with the validated address IF it could be validated. Here, we catch errors like:
    -Outright invalid addresses
    -Addresses that may map to slightly different cities/zips for shipping
    -Similar issues involving address validity.

    However, OSMN does not do well with everything, ESPECIALLY with units or apartment numbers. This is where you come
    in, as **Part 2** of the Shaman2's address verification service. Here's what we're going to give you:

    -ORIGINAL_ADDRESS - This refers to the plain, simple string that the user gave us directly. It might be perfectly
    valid, it might be an absolute mess.
    -OSMN_ADDRESS - This is the output of running ORIGINAL_ADDRESS through step 1 of our validation service. It will
    be neatly formatted, but may include some extraneous information that's unimportant like a neighborhood.

    What you're looking for is any inconsistencies or oddities between the two. As I already stated, stuff like
    neighborhoods are unimportant, but since the OSMN_ADDRESS often misses apartment numbers, be extra vigilant
    about these. If you do notice anything that looks like an apartment, unit, suite number or something like that,
    remember that that goes in ADDRESS 2, not in Address 1 or anywhere else. Furthermore, OSMN is REALLY good with 
    getting exact streetnames. 9999 times out of 10000, the street name that OSMN validates is EXACTLY right. So,
    if there's something in the ORIGINAL_ADDRESS Address1 that's not in the OSMN_ADDRESS Address1, it's almost 
    certainly a mistaken Address2 and, rarely, just outright unimportant. Simply try your best to detect any 
    oddities/discrepencies, if there are any (there often won't be any) and then return what YOU BELIEVE is the final, 
    validated address.

    Now that you understand your task, please observe the actual addresses in question and respond with your results:

    ORIGINAL_ADDRESS = {originalAddress}
    OSMN_ADDRESS = {osmnAddress}   

    Go ahead and discuss your reasoning, but at the very end of your response, I would like you to give me your
    final version of the address. Write in a simple JSON object and surround the whole thing in 3 dollar signs so
    that my program can read it, like so: 


"""
exampleOutputString = """
    ```
    $$$
    {
        "Address1" : "",
        "Address2" : "",
        "City" : "",
        "State" : "",
        "Zip" : "",
    }
    $$$
    ```
"""
def gptValidateAddress(_originalAddress, _osmnAddress):
    _response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an address validation assistant."},
            {"role": "user", "content": chatGPTAddressQuery.format(originalAddress=_originalAddress,
                                                                  osmnAddress=_osmnAddress) + exampleOutputString}
        ],
        temperature=0
    )

    return _response.choices[0].message.content
# Simply extracts only the address dict from GPT's response
def extractGPTAddressFromResponse(gptResponseString):
    pattern = r'\$\$\$(.*?)\$\$\$'
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
def validateAddress(addressString : str):
    osmnAddress = osmnValidateAddress(_address=addressString)

    if(len(osmnAddress) == 0):
        error = ValueError(f"OSMN did not find any addresses that match user's address \"{addressString}\"")
        log.error(error)
        raise error
    elif(len(osmnAddress) == 1):
        gptResponse = gptValidateAddress(_originalAddress=addressString,_osmnAddress=osmnAddress)
        gptAddress = extractGPTAddressFromResponse(gptResponseString=gptResponse)
        return gptAddress
    else:
        error = ValueError(f"OSMN did not find multiple addresses that look like user's address \"{addressString}\":\n\n{osmnAddress}")
        log.error(error)
        raise error

