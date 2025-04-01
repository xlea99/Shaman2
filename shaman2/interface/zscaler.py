import subprocess
import time
import os
import psutil
import shutil
from shaman2.common.paths import paths
from shaman2.common.config import mainConfig




# Add zscaler install path.
paths["zscalerInstall"] = mainConfig["misc"]["zscalerInstallPath"]

# Helper function to run a command and return (captures errors)
def runCmd(cmd):
    try:
        completed = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return completed.stdout.decode()
    except subprocess.CalledProcessError as e:
        return e.stderr.decode()

# This class provides a "safe" way to interface directly with ZScaler and ensure it leaks as little as
# possible
class ZScalerInterface:

    ZSERVICES = ["ZSATrayManager","ZSATunnel","ZSAService", "ZSAUpdater", "ZSAUpm"]
    ZPROCESSES = ["ZSATray.exe", "ZSATrayManager.exe", "ZSATunnel.exe", "ZSAService.exe", "ZSAUpdater.exe", "ZSAUpm.exe"]


    def __init__(self):

        self.installPath = paths["zscalerInstall"]
        self.disabledPath = self.installPath.with_name(self.installPath.name + "_disabled")



    # This method simply tries to obliterate zscaler if it's open.
    def kill(self):
        print("Killing ZScaler...")


        def take_ownership(folder_path):
            subprocess.run([
                "takeown", "/f", folder_path, "/r", "/d", "y"
            ], shell=True)
            subprocess.run([
                "icacls", folder_path, "/grant", "Administrators:F", "/t"
            ], shell=True)
            # Rename install folder
        take_ownership(self.installPath)
        if os.path.exists(self.installPath):
            try:
                if os.path.exists(self.disabledPath):
                    print(f"    - Removing existing disabled folder: {self.disabledPath}")
                    shutil.rmtree(self.disabledPath)
                print(f"    - Renaming install folder: {self.installPath} -> {self.disabledPath}")
                os.rename(self.installPath, self.disabledPath)
            except Exception as e:
                print(f"[!] Failed to rename install folder: {e}")
                return
        else:
            print("[!] Install path does not exist. Nothing to rename.")

        # First, kill all services in graceful order
        for service in self.ZSERVICES:
            print(f"[*] Stopping service {service}:")
            subprocess.run(["sc", "config", service, "start=", "demand"], shell=True)
            output = runCmd(["sc","stop",service])
            if "STOP_PENDING" in output or "has stopped" in output:
                print(f"    - stop command sent")
            else:
                print(f"    - output: '{output}'")

        # Kill all lingering processes
        remainingZScalerProcesses = []
        for process in psutil.process_iter():
            try:
                if process.name() in self.ZPROCESSES:
                    remainingZScalerProcesses.append(process)
            except psutil.NoSuchProcess:
                continue
        if remainingZScalerProcesses:
            print("[*] Killing remaining processes:")
            for process in remainingZScalerProcesses:
                try:
                    print(f"    - Terminating {process.name()} (PID {process.pid})")
                    process.terminate()
                except psutil.AccessDenied:
                    subprocess.call(["taskkill", "/F", "/PID", str(process.pid)])
        #time.sleep(3)
        for process in remainingZScalerProcesses:
            if process.is_running():
                try:
                    process.kill()
                    print(f"    - Process {process.name()} did not terminate gracefully and was killed.")
                except psutil.AccessDenied:
                    subprocess.call(["taskkill", "/F", "/PID", str(process.pid)])




zscaler = ZScalerInterface()
zscaler.kill()