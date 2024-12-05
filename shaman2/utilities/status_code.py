from enum import Enum

class StatusCode(Enum):

    #region === Basic Status Codes ===

    SUCCESS = "Success"             # Denotes a general Success.

    GENERAL_FAILURE = "Failure"     # Denotes a general Failure.
    BAD_ELEMENT = "Bad Element"     # Means that some element that was expected to be found/not found/interacted with, couldn't be.
    USER_ABORT = "User Abort"       # Means the user chose to abort/halt the current task.
    LOGIN_ERROR = "Login Error"     # Means that the log in for some website didn't work correctly.

    #endregion === Basic Status Codes ===

    #region === Verizon Status Codes ===

    VERIZON_MTN_PENDING = "MTN Pending Error"


    #endregion === Verizon Status Codes ===