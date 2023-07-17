"""
This module reads the configuration from the config.toml file. The config object is used
throughout the project so reusing the code can be as easy as only touching the .toml.
"""
import pathlib
import tomli

with open(
    file=pathlib.Path(__file__).parent.parent / "config" / "config.toml",
    mode="rb",
) as config_file:
    config = tomli.load(config_file)
