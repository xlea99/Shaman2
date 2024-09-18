import re

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
def convertStateFormat(stateString,targetFormat):
    stateDict = {
        "al": "alabama",
        "ak": "alaska",
        "az": "arizona",
        "ar": "arkansas",
        "ca": "california",
        "co": "colorado",
        "ct": "connecticut",
        "de": "delaware",
        "fl": "florida",
        "ga": "georgia",
        "hi": "hawaii",
        "id": "idaho",
        "il": "illinois",
        "in": "indiana",
        "ia": "iowa",
        "ks": "kansas",
        "ky": "kentucky",
        "la": "louisiana",
        "me": "maine",
        "md": "maryland",
        "ma": "massachusetts",
        "mi": "michigan",
        "mn": "minnesota",
        "ms": "mississippi",
        "mo": "missouri",
        "mt": "montana",
        "ne": "nebraska",
        "nv": "nevada",
        "nh": "new hampshire",
        "nj": "new jersey",
        "nm": "new mexico",
        "ny": "new york",
        "nc": "north carolina",
        "nd": "north dakota",
        "oh": "ohio",
        "ok": "oklahoma",
        "or": "oregon",
        "pa": "pennsylvania",
        "ri": "rhode island",
        "sc": "south carolina",
        "sd": "south dakota",
        "tn": "tennessee",
        "tx": "texas",
        "ut": "utah",
        "vt": "vermont",
        "va": "virginia",
        "wa": "washington",
        "wv": "west virginia",
        "wi": "wisconsin",
        "wy": "wyoming"
    }

    stateName = None
    stateAbbrev = None
    if(stateString.lower() in stateDict.keys()):
        stateAbbrev = stateString.lower()
        stateName = stateDict[stateAbbrev]
    elif(stateString.lower() in stateDict.values()):
        stateName = stateString.lower()
        for key,value in stateDict.items():
            if(value == stateName):
                stateAbbrev = key
                break
    else:
        raise ValueError(f"Invalid state string given '{stateString}'")

    if(targetFormat.lower() == "abbreviation"):
        return stateAbbrev.upper()
    elif(targetFormat.lower() == "name"):
        return stateName.title()
    else:
        raise ValueError(f"Invalid targetFormat specified '{targetFormat}'")