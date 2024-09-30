import tomlkit
import os
from shaman2.common.paths import paths
from shaman2.common.logger import log

# This parent class provides a template for reloadable config objects, that essentially extend a
# tomlkit.TOMLDocument but allow for live reloading.
class ReloadableConfig():

    def __init__(self):
        self.tomlDoc = None
        self.reload()

    def __getitem__(self, item):
        return self.tomlDoc[item]
    def __setitem__(self, key, value):
        self.tomlDoc[key] = value

    # Overwrite this function with actual implementations.
    def reload(self):
        pass

    # Shadow some basic tomldoc functions.
    def keys(self):
        return self.tomlDoc.keys()
    def values(self):
        return self.tomlDoc.values()
    def items(self):
        return self.tomlDoc.items()


class MainConfig(ReloadableConfig):
    def reload(self):
        mainConfigPath = paths["config"] / "main.toml"
        if (os.path.exists(mainConfigPath)):
            with open(mainConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
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
            loggingSection.add(tomlkit.comment(
                'Valid levels are: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", with DEBUG showing the most info'))
            loggingSection["level"] = "INFO"
            loggingSection.add(tomlkit.comment("Maximum log file size in kilobytes"))
            loggingSection["maxSize"] = 10240
            loggingSection.add(tomlkit.comment("Number of old log files to keep"))
            loggingSection["backupCount"] = 10
            newMainConfigToml["logging"] = loggingSection
            newMainConfigToml.add(tomlkit.nl())

            cimplSection = tomlkit.table()
            cimplSection.add(tomlkit.comment(
                "If true, Cimpl won't attempt to log in automatically and will prompt the user to manually do so."))
            cimplSection["manualLogin"] = True
            newMainConfigToml["cimpl"] = cimplSection
            newMainConfigToml.add(tomlkit.nl())

            syscoSection = tomlkit.table()
            syscoSection.add(
                tomlkit.comment("If true, Sysco will order vehicle chargers. Otherwise, they'll be ignored."))
            syscoSection["orderVehicleChargers"] = False
            syscoSection.add(tomlkit.comment(
                "If true, Shaman will attempt to order colors for devices. Otherwise, all colors will default to the Cimpl mapping base."))
            syscoSection["orderColoredEquipment"] = False
            syscoSection.add(tomlkit.comment(
                "# Any accessory IDs in this list will always be ordered, corresponding to each TMA device SubType (Smart Phone, Aircard, etc.)"))
            syscoSection["vzwAccessoriesToAlwaysOrder_SmartPhone"] = ["VerizonWallAdapter"]
            syscoSection["vzwAccessoriesToAlwaysOrder_Aircard"] = []
            syscoSection["vzwAccessoriesToAlwaysOrder_Tablet"] = []
            newMainConfigToml["sysco"] = syscoSection
            newMainConfigToml.add(tomlkit.nl())

            with open(mainConfigPath, "w") as newMainConfigTomlFile:
                newMainConfigTomlFile.write(tomlkit.dumps(newMainConfigToml))
            with open(mainConfigPath, "r") as f:
                return tomlkit.parse(f.read())
mainConfig = MainConfig()

class ClientConfig(ReloadableConfig):
    def reload(self):
        clientConfigPath = paths["config"] / "clients.toml"
        if (os.path.exists(clientConfigPath)):
            with open(clientConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
        else:
            newClientConfigToml = tomlkit.document()
            with open(clientConfigPath, "w") as newClientConfigTomlFile:
                newClientConfigTomlFile.write(tomlkit.dumps(newClientConfigToml))

            error = ValueError(
                "client.toml file did not exist. File created, but needs to be filled with at least one client info before proceeding.")
            log.error(error)
            raise error
clients = ClientConfig()

class DevicesConfig(ReloadableConfig):
    def reload(self):
        devicesConfigPath = paths["config"] / "equipment/devices.toml"
        if (os.path.exists(devicesConfigPath)):
            with open(devicesConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
        else:
            newDevicesConfigToml = tomlkit.document()
            with open(devicesConfigPath, "w") as newDevicesConfigTomlFile:
                newDevicesConfigTomlFile.write(tomlkit.dumps(newDevicesConfigToml))

            error = ValueError(
                "devices.toml file did not exist. File created, but needs to be filled with device data before proceeding.")
            log.error(error)
            raise error
devices = DevicesConfig()

class DevicesCimplMappingsConfig(ReloadableConfig):
    def reload(self):
        deviceCimplMappingsConfigPath = paths["config"] / "equipment/device_cimpl_mappings.toml"
        if (os.path.exists(deviceCimplMappingsConfigPath)):
            with open(deviceCimplMappingsConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
        else:
            newDevicesConfigToml = tomlkit.document()
            with open(deviceCimplMappingsConfigPath, "w") as newDeviceCimplMappingsConfigTomlFile:
                newDeviceCimplMappingsConfigTomlFile.write(tomlkit.dumps(newDevicesConfigToml))

            error = ValueError(
                "device_cimpl_mappings.toml file did not exist. File created, but needs to be filled with device mapping data before proceeding.")
            log.error(error)
            raise error
deviceCimplMappings = DevicesCimplMappingsConfig()

class AccessoriesConfig(ReloadableConfig):
    def reload(self):
        accessoriesConfigPath = paths["config"] / "equipment/accessories.toml"
        if (os.path.exists(accessoriesConfigPath)):
            with open(accessoriesConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
        else:
            newAccessoriesConfigToml = tomlkit.document()
            with open(accessoriesConfigPath, "w") as newAccessoriesConfigTomlFile:
                newAccessoriesConfigTomlFile.write(tomlkit.dumps(newAccessoriesConfigToml))

            error = ValueError(
                "accessories.toml file did not exist. File created, but needs to be filled with accessory data before proceeding.")
            log.error(error)
            raise error
accessories = AccessoriesConfig()

class AccessoryCimplMappingsConfig(ReloadableConfig):
    def reload(self):
        accessoryCimplMappingsConfigPath = paths["config"] / "equipment/accessory_cimpl_mappings.toml"
        if (os.path.exists(accessoryCimplMappingsConfigPath)):
            with open(accessoryCimplMappingsConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
        else:
            newAccessoryCimplMappingsConfigToml = tomlkit.document()
            with open(accessoryCimplMappingsConfigPath, "w") as newAccessoryCimplMappingsConfigTomlFile:
                newAccessoryCimplMappingsConfigTomlFile.write(tomlkit.dumps(newAccessoryCimplMappingsConfigToml))

            error = ValueError(
                "accessory_cimpl_mappings.toml file did not exist. File created, but needs to be filled with accessory mapping data before proceeding.")
            log.error(error)
            raise error
accessoryCimplMappings = AccessoryCimplMappingsConfig()

class EmailTemplatesConfig(ReloadableConfig):
    def reload(self):
        emailTemplatesConfigPath = paths["config"] / "emailTemplates.toml"
        if (os.path.exists(emailTemplatesConfigPath)):
            with open(emailTemplatesConfigPath, "r") as f:
                self.tomlDoc = tomlkit.parse(f.read())
        else:
            newEmailTemplatesConfigToml = tomlkit.document()
            with open(emailTemplatesConfigPath, "w") as newEmailTemplatesConfigTomlFile:
                newEmailTemplatesConfigTomlFile.write(tomlkit.dumps(newEmailTemplatesConfigToml))

            error = ValueError("emailTemplates.toml file did not exist. File created, but needs to be filled with accessory data before proceeding.")
            log.error(error)
            raise error
emailTemplatesConfig = EmailTemplatesConfig()


