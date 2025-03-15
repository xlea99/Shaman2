from shaman2.selenium.browser import Browser
from shaman2.selenium.baka_driver import BakaDriver
from shaman2.selenium.cimpl_driver import CimplDriver
from shaman2.selenium.tma_driver import TMADriver
from shaman2.selenium.verizon_driver import VerizonDriver
from shaman2.selenium.eyesafe_driver import EyesafeDriver
from shaman2.selenium.snow_driver import SnowDriver
from shaman2.selenium.outlook_driver import OutlookDriver
from shaman2.utilities.async_sound import playsoundAsync
from shaman2.common.paths import paths
from shaman2.common.logger import log


#region === DRIVER VALIDATION ===

# Validates that TMA is logged in, the active tab, and that it's on the portal
# for the given client.
def validateTMA(tmaDriver : TMADriver,client):
    tmaDriver.browser.switchToTab("TMA")
    currentLocation = tmaDriver.readPage()
    if not currentLocation.isLoggedIn:
        tmaDriver.logInToTMA()
    if currentLocation.client != client:
        tmaDriver.navToClientHome(client)

# Validates that Cimpl is logged and the active tab.
def validateCimpl(cimplDriver : CimplDriver):
    cimplDriver.browser.switchToTab("Cimpl")
    cimplDriver.logInToCimpl()

# Validates that Verizon is logged in (attempts automatic login, then defaults to manual) and the active tab.
def validateVerizon(verizonDriver : VerizonDriver):
    verizonDriver.browser.switchToTab("Verizon")
    try:
        verizonDriver.logInToVerizon(manual=False)
    except Exception as e:
        log.warning(e)
        playsoundAsync(paths["media"] / "shaman_attention.mp3")
        verizonDriver.logInToVerizon(manual=True)

# Validates that Baka is logged in and the active tab.
def validateBaka(bakaDriver : BakaDriver):
    bakaDriver.browser.switchToTab("Baka")
    bakaDriver.logInToBaka()

# Validates that Eyesafe is logged in and the active tab.
def validateEyesafe(eyesafeDriver : EyesafeDriver):
    eyesafeDriver.browser.switchToTab("Eyesafe")
    eyesafeDriver.logInToEyesafe()

# Validates that SNow is logged in and the active tab.
def validateSnow(snowDriver : SnowDriver):
    snowDriver.browser.switchToTab("Snow")
    snowDriver.logInToSnow()

# Validates that Outlook is logged in to specific Outlook accounts.
def validateUplandOutlook(uplandOutlookDriver : OutlookDriver):
    uplandOutlookDriver.logInToOutlook_Upland()
    uplandOutlookDriver.browser.switchToTab(f"Outlook_Upland")
def validateSysOrdBoxOutlook(sysOrdBoxOutlookDriver : OutlookDriver, uplandOutlookDriver : OutlookDriver):
    uplandOutlookDriver.logInToOutlook_Upland()
    sysOrdBoxOutlookDriver.logInToOutlook_SyscoOrdBox()
    sysOrdBoxOutlookDriver.browser.switchToTab(f"Outlook_SyscoOrdBox")


#endregion === DRIVER VALIDATION ===