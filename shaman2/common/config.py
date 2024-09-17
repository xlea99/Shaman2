import tomlkit
from shaman2.common.paths import paths

# Sets up the main.toml file, which is assumed to exist at root/config. To avoid
# circular imports, this is the one time we deal with pathing outside of paths.py.
with open(paths["config"] / "main.toml", "r") as f:
    config = tomlkit.parse(f.read())