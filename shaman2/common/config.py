import os
import tomlkit

thisFilePath = os.path.realpath(__file__)
configDir = os.path.dirname(os.path.dirname(os.path.dirname(thisFilePath)))

# Sets up the main.toml file, which is assumed to exist at root/config. To avoid
# circular imports, this is the one time we deal with pathing outside of paths.py.
with open(os.path.join(configDir,"config/main.toml"), "r") as f:
    config = tomlkit.parse(f.read())