from enum import Enum
from dataclasses import dataclass
from shaman2.common.logger import log
from shaman2.utilities.shaman_utils import BAD_ELEMENT_EXCEPTIONS


class StatusCode(Enum):

    #region === Basic Status Codes ===

    SUCCESS = ("Success",True)             # Denotes a general Success.

    GENERAL_FAILURE = ("Failure",False)     # Denotes a general Failure.
    BAD_ELEMENT = ("Bad Element",False)     # Means that some element that was expected to be found/not found/interacted with, couldn't be.
    USER_ABORT = ("User Abort",False)       # Means the user chose to abort/halt the current task.
    AMBIGUOUS_PAGE = ("Ambiguous Page",False)   # Means that an unexpected page appeared, and the Shaman now doesn't know where we are.

    NO_RESULTS = ("No Results",False)       # Used when no results are found in some search context.

    #endregion === Basic Status Codes ===

    #region === Verizon Status Codes ===

    VERIZON_MTN_PENDING = ("VZW MTN Pending Error",False)
    VERIZON_EARLY_UPGRADE_NO_ETF = ("VZW Early Upgrade No ETF",False)
    VERIZON_MISSING_COLOR = ("VZW Missing Color",False)
    VERIZON_ZIP_SELECTION_FAILURE = ("VZW Zip Selection Failure",False)
    VERIZON_INVALID_EMAIL = ("VZW Invalid Email",False)
    VERIZON_INVALID_ADDRESS = ("VZW Invalid Address", False)
    VERIZON_CART_INCONSISTENCY = ("VZW Cart Inconsistency",False)
    VERIZON_FAILED_ORDER_PLACE = ("VZW Failed Order Place",False)

    #endregion === Verizon Status Codes ===

    # Helper bool override to evaluate the truthiness of this status code.
    def __bool__(self):
        return self.value[1]


# Simple datastructure to manage the returns from various actions across the drivers.
@dataclass
class ActionResult:
    status : StatusCode = StatusCode.SUCCESS
    data: any = None

    # Helper bool override to evaluate the truthiness of this action result.
    def __bool__(self):
        return self.status.value[1]

# Decorator for general handling of "action" type functions/methods.
def action(func):
    def wrapper(*args,**kwargs):
        # Try to run the actual function.
        try:
            log.info(f"Starting Action '{func.__name__}' with args: ({args}), kwargs: ({kwargs})")
            result = func(*args,**kwargs)
            if(isinstance(result,ActionResult)):
                log.info(f"Action '{func.__name__}' completed with status: {result.status}, data: {result.data}")
                return result
            # Enforce that all return types for actions are ActionResults.
            else:
                error = ValueError(f"Completed Action '{func.__name__}' returned non-ActionResult: {result}")
                log.error(error)
                raise error
        # General catch for otherwise unmanaged bad element exceptions.
        except BAD_ELEMENT_EXCEPTIONS as e:
            log.error(f"Action '{func.__name__}' failed due to bad element error: {e}",exc_info=True)
            return ActionResult(status=StatusCode.BAD_ELEMENT)
        except Exception as e:
            log.error(f"Action '{func.__name__}' failed due to unexpected/unmanaged error: {e}", exc_info=True)
            raise e
    return wrapper