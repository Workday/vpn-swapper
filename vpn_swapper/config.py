import argparse
import json
import logging
import os
from pathlib import Path
from traceback import format_exc
from typing import List, IO, Dict, Any


class Config(object):
    DIR_KEY: str = "_dir"
    FILE_KEY: str = "_file"

    # Command line arguments take precedence over config file values
    def __init__(self, name: str, args: Dict):
        self.name = name
        self.base_dir = f"{Path.home()}/.{name}"
        self._defaults = {}
        self.conf = {}

        try:
            # the slash does work either way on windows, but including a standard one for compatibility
            conf_file_locations: List[str] = [args.get('config_file', ''),
                                              f"{self.base_dir}/config.json",
                                              f"{os.getcwd()}/config.json",
                                              f"{os.getcwd()}\\config.json"]

            f = self._open_config(conf_file_locations)
            conf: Dict = json.load(f)
            # We want to remove all the keys with value None so that the merge works as expected. At this point
            # writing our own merge method that does all of this in one pass is prob more efficient but not worth the
            # effort.args is of type Namespace, we want a dict, hence vars()

            # In this merge, command line arguments take precedence over config file values, which take precedence over
            # hardcoded default values
            self.conf: Dict = {**self.defaults(), **conf, **args}
        except Exception as ex:
            logging.error(f"Failed to initialize {self.name}: {repr(ex)}")
            logging.debug(format_exc())

    def defaults(self):
        return self._defaults

    @classmethod
    def from_args(cls, name: str, args: argparse.Namespace):
        args_dict: Dict = {k: v for k, v in vars(args).items() if v is not None}
        return cls(name, args_dict)

    def _open_config(self, paths: List[str]) -> IO:
        for p in paths:
            try:
                f = open(p, 'r')
                logging.info(f"Using config file at {p}")
                return f
            except OSError as err:
                logging.debug(f"Could not find/open config file {p}: {repr(err)}")

        logging.error("Failed to find any configuration file. Exiting")

    def __getitem__(self, key: str) -> Any:
        attr = ''  # type checker error if not defined

        try:
            attr = self.conf[key]
        except KeyError:
            logging.warning(f"Property {key} not found in configuration")
            return None

        # Some smarts to try and provide absolute paths when the attribute requested is a dir or a file
        if key.endswith(self.DIR_KEY) or key.endswith(self.FILE_KEY):
            logging.debug(f"Converted {attr} to a path because it ({key}) ends with {self.DIR_KEY} or {self.FILE_KEY}")
            try:
                attr = Path(attr).resolve()
            except TypeError:
                logging.error(f"Tried to convert {attr} to a Path but failed.")
                logging.debug(format_exc())
        return attr

    def __setitem__(self, key: str, value: Any) -> None:
        # We really probably don't want to be overwriting any of our config stuff, but don't prevent it
        if key in self.conf:
            logging.warning(f"Overwriting {key} with value {value} (previously {self.conf[value]}")
        else:
            logging.debug(f"Setting {key} to {value}")

        self.conf[key] = value
