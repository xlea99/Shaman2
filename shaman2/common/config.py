import tomlkit
import os
from shaman2.common.paths import paths

mainConfigPath = paths["config"] / "main.toml"
if(os.path.exists(mainConfigPath)):
    with open(mainConfigPath, "r") as f:
        mainConfig = tomlkit.parse(f.read())
else:
    newMainConfigToml = tomlkit.document()

    authSection = tomlkit.table()
    authSection.add(tomlkit.comment("TMA Login Credentials"))
    authSection["tmaUser"] = ""
    authSection["tmaPass"] = ""
    authSection.add(tomlkit.comment("Cimpl Login Credentials"))
    authSection["cimplUser"] = ""
    authSection["cimplPass"] = ""
    authSection.add(tomlkit.comment("Verizon Login Credentials"))
    authSection["verizonUser"] = ""
    authSection["verizonPass"] = ""
    authSection.add(tomlkit.comment("Baka Login Credentials"))
    authSection["bakaUser"] = ""
    authSection["bakaPass"] = ""
    newMainConfigToml["authentication"] = authSection
    newMainConfigToml.add(tomlkit.nl())

    loggingSection = tomlkit.table()
    loggingSection.add(tomlkit.comment('Valid levels are: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", with DEBUG showing the most info'))
    loggingSection["level"] = "INFO"
    loggingSection.add(tomlkit.comment("Maximum log file size in kilobytes"))
    loggingSection["maxSize"] = 10240
    loggingSection.add(tomlkit.comment("Number of old log files to keep"))
    loggingSection["backupCount"] = 10
    newMainConfigToml["logging"] = loggingSection
    newMainConfigToml.add(tomlkit.nl())

    cimplSection = tomlkit.table()
    cimplSection.add(tomlkit.comment("If true, Cimpl won't attempt to log in automatically and will prompt the user to manually do so."))
    cimplSection["manualLogin"] = True
    newMainConfigToml["cimpl"] = cimplSection
    newMainConfigToml.add(tomlkit.nl())

    with open(mainConfigPath, "w") as newMainConfigTomlFile:
        newMainConfigTomlFile.write(tomlkit.dumps(newMainConfigToml))
    with open(mainConfigPath, "r") as f:
        mainConfig = tomlkit.parse(f.read())

