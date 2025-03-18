import tomlkit
import pyotp
from shaman2.common.paths import paths

with open(paths["config"] / "main.toml","r") as f:
    mainConfig = tomlkit.parse(f.read())


# Handle OTP generators.
if "jumpcloudOTPCode" in mainConfig["authentication"] and mainConfig["authentication"]["jumpcloudOTPCode"].strip():
    jumpcloudOTP = pyotp.TOTP(mainConfig["authentication"]["jumpcloudOTPCode"].strip())
else:
    jumpcloudOTP = None