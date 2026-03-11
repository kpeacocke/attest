"""INI/config file resource (REQ-2.4: structured config file parsers)."""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class IniFileResource:
    """Read values from INI/config-format files via configparser.

    Parameters
    ----------
    path : str
        Absolute or relative path to the INI file.
    section : str, optional
        Section name to read from. If omitted, returns a dict of all sections.
    key : str, optional
        Key name within the section. Requires ``section`` to be specified.
        If omitted (with a section given), returns all key/value pairs in that section.
    """

    def query(self, params: dict[str, Any]) -> ResourceResult:
        raw_path = params.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            return ResourceResult(
                data=None,
                errors=["'ini_file' resource requires a non-empty 'path' parameter."],
            )

        file_path = Path(raw_path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            return ResourceResult(
                data=None,
                errors=[f"Cannot read INI file '{raw_path}': {exc}"],
            )

        config = configparser.ConfigParser()
        try:
            config.read_string(text)
        except configparser.Error as exc:
            return ResourceResult(
                data=None,
                errors=[f"INI parse error in '{raw_path}': {exc}"],
            )

        section = params.get("section")
        key = params.get("key")

        if section is None:
            # Return entire document as nested dict; include DEFAULT if present.
            data: dict[str, Any] = {}
            if config.defaults():
                data["DEFAULT"] = dict(config.defaults())
            for sec in config.sections():
                data[sec] = dict(config[sec])
            return ResourceResult(data=data, errors=[], timings={})

        if not isinstance(section, str):
            return ResourceResult(
                data=None,
                errors=["'section' parameter must be a string."],
            )

        if not config.has_section(section):
            return ResourceResult(
                data=None,
                errors=[f"Section '{section}' not found in '{raw_path}'."],
            )

        if key is None:
            return ResourceResult(
                data=dict(config[section]),
                errors=[],
                timings={},
            )

        if not isinstance(key, str):
            return ResourceResult(
                data=None,
                errors=["'key' parameter must be a string."],
            )

        if not config.has_option(section, key):
            return ResourceResult(
                data=None,
                errors=[f"Key '{key}' not found in section '{section}' in '{raw_path}'."],
            )

        return ResourceResult(data=config.get(section, key), errors=[], timings={})
