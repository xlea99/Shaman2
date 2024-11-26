import tomlkit
from shaman2.common.paths import paths

with open(paths["config"] / "main.toml","r") as f:
    mainConfig = tomlkit.parse(f.read())

with open(paths["config"] / "emailTemplates.toml","r") as f:
    emailTemplatesConfig = tomlkit.parse(f.read())