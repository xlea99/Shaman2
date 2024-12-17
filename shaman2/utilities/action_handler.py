from enum import Enum
import time
from functools import wraps
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
    meta : dict = None
    data: any = None

    # Helper bool override to evaluate the truthiness of this action result.
    def __bool__(self):
        return self.status.value[1]

# Decorator to handle retries, logging, and ActionResult enforcement for actions.
#
# raiseErrorOn -        Any status codes specified in this argument will raise an error, instead of being returned, AFTER all attempts have been considered/tried.
def action(
    retry=False, maxAttempts=3, retryBackoff=1,
    retryStatusCodeWhitelist=None, retryStatusCodeBlacklist=None,
    retryExceptionWhitelist=None, retryExceptionBlacklist=None,
    raiseErrorOn=(StatusCode.BAD_ELEMENT, StatusCode.AMBIGUOUS_PAGE, StatusCode.GENERAL_FAILURE)
):

    # Handle default values
    raiseErrorOn = list(raiseErrorOn) if not isinstance(raiseErrorOn, list) else raiseErrorOn
    if not retry:
        maxAttempts = 1

    # Helper function to determine if a status code allows retries
    def should_retry_status_code(status):
        if retryStatusCodeWhitelist is not None:
            return status in retryStatusCodeWhitelist
        if retryStatusCodeBlacklist is not None:
            return status not in retryStatusCodeBlacklist
        return False  # Default: no retries if no whitelist/blacklist is set

    # Helper function to determine if an exception allows retries
    def should_retry_exception(exception):
        if retryExceptionWhitelist is not None:
            return isinstance(exception, tuple(retryExceptionWhitelist))
        if retryExceptionBlacklist is not None:
            return not isinstance(exception, tuple(retryExceptionBlacklist))
        return False  # Default: no retries if no whitelist/blacklist is set

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            lastFailureResult = None

            # === Try Attempts ===
            while attempts < maxAttempts:
                lastFailureResult = None
                attempts += 1
                try:
                    log.info(f"Starting Action '{func.__name__}' (Attempt {attempts}/{maxAttempts}) with args: {args}, kwargs: {kwargs}")

                    # Call the function
                    result = func(*args, **kwargs)

                    # Ensure result is an ActionResult
                    if not isinstance(result, ActionResult):
                        raise ValueError(f"Action '{func.__name__}' returned a non-ActionResult: {result}")

                    # If status code is retryable, save result and retry
                    if should_retry_status_code(result.status):
                        log.warning(f"Action '{func.__name__}' returned retryable status: {result.status}")
                        lastFailureResult = result
                    else:
                        # If not retryable, exit attempt phase early
                        log.info(f"Action '{func.__name__}' ended with status: {result.status}")
                        return result

                except Exception as e:
                    # Handle exceptions and check if they are retryable
                    if should_retry_exception(e):
                        log.warning(f"Action '{func.__name__}' failed with retryable exception: {e}")
                        lastFailureResult = e
                    else:
                        # If exception is not retryable, raise immediately
                        log.error(f"Action '{func.__name__}' failed with non-retryable exception: {e}", exc_info=True)
                        raise

                # Wait before retrying
                if attempts < maxAttempts:
                    sleep_time = retryBackoff * (2 ** (attempts - 1))
                    log.info(f"Retrying Action '{func.__name__}' after {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)

            log.error(f"Action '{func.__name__}' exhausted all {maxAttempts} attempts.")

            # === Handle Failure Cases Only ===
            if lastFailureResult:
                # At this point, all attempts have failed to produce a valid result.
                if isinstance(lastFailureResult, Exception):
                    # If a non-retryable exception was the final outcome, raise it
                    log.error(f"Action '{func.__name__}' (After {maxAttempts} attempts) raised an exception: {lastFailureResult}")
                    raise lastFailureResult
                elif isinstance(lastFailureResult,ActionResult):
                    # Check if the final status code should raise an error
                    if lastFailureResult.status in raiseErrorOn:
                        error_message = f"Action '{func.__name__}' (After {maxAttempts} attempts) failed with error status code: {lastFailureResult.status}"
                        log.error(error_message)
                        raise RuntimeError(error_message)
                    # Otherwise, return the final ActionResult
                    else:
                        log.warning(f"Action '{func.__name__}' completed with final status: {lastFailureResult.status}")
                        return lastFailureResult
            # If the most recent attempt returned nothing, we just return a general failure.
            return ActionResult(status=StatusCode.GENERAL_FAILURE)

        return wrapper
    return decorator