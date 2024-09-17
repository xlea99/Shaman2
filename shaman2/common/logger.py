import os
import logging
from logging.handlers import RotatingFileHandler
from shaman2.common.paths import paths
import datetime

# Setup of custom logger for program-wide use.
def setupCustomLogger(logDirectory : str, level : int = logging.NOTSET,
                 maxSingleFileSize : int = 1*1024*1024, maxFileCount : int = 5,logName : str = __name__,
                 logFormat:str = '%(asctime)s - %(levelname)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s'):
    # Custom rotation and cleanup function
    def rotateLogs():
        # List all log files
        logs = [log for log in os.listdir(logDirectory) if log.endswith(".log")]
        # If we have more logs than maxLogCount, delete the oldest
        while len(logs) > maxFileCount - 1:
            oldest_log = min(logs, key=lambda x: os.path.getctime(os.path.join(logDirectory, x)))
            os.remove(os.path.join(logDirectory, oldest_log))
            logs.remove(oldest_log)

    # Set up the special "Test" log level for specific testing.
    TEST_LOG_LEVEL = 25
    logging.addLevelName(TEST_LOG_LEVEL,"TEST")
    def test(self,message,*args,**kwargs):
        if(self.isEnabledFor(TEST_LOG_LEVEL)):
            self._log(TEST_LOG_LEVEL,message,args,**kwargs)
    logging.Logger.test = test

    # Setup initial logger.
    _logger = logging.getLogger(logName)
    _logger.setLevel(level)

    # Setup handler
    handler = RotatingFileHandler(
        paths["logs"] / f"{logName}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
        maxBytes=maxSingleFileSize, backupCount=maxFileCount - 1, delay=True)
    handler.setLevel(level)
    _logger.addHandler(handler)
    handler.rotator = lambda source, dest: rotateLogs()

    # Setup formatter
    formatter = logging.Formatter(logFormat)
    handler.setFormatter(formatter)

    # Initial run of rotate logs, in case the existing directory already contains multiple log files.
    rotateLogs()

    # Return actual logger.
    return _logger

log = setupCustomLogger(logDirectory=paths["logs"],level=logging.DEBUG,logName="log")
log.info("Initialized logger.")