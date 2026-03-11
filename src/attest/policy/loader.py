"""YAML loader for Attest profiles and controls (REQ-1.1, REQ-1.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from attest.policy.schemas import Control, Profile


class LoadError(Exception):
    """Raised when a profile or control file cannot be loaded or parsed."""


def _load_yaml(path: Path) -> Any:
    """Load a YAML file and return the parsed object, or raise LoadError."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LoadError(f"Cannot read '{path}': {exc}") from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise LoadError(f"YAML parse error in '{path}': {exc}") from exc


def load_profile(profile_path: Path) -> Profile:
    """Parse and validate a profile.yml file.

    Raises LoadError on I/O or YAML problems.
    Raises pydantic.ValidationError on schema violations.
    """
    data = _load_yaml(profile_path)
    if not isinstance(data, dict):
        raise LoadError(f"'{profile_path}' must be a YAML mapping, not {type(data).__name__}.")
    return Profile.model_validate(data)


def load_controls(controls_dir: Path) -> list[Control]:
    """Load and validate all control YAML files from a directory.

    Files are returned sorted by control ID for deterministic ordering (REQ-7.4).
    Raises LoadError or pydantic.ValidationError on problems.
    """
    if not controls_dir.is_dir():
        raise LoadError(f"Controls directory '{controls_dir}' does not exist.")

    controls: list[Control] = []
    for yaml_file in sorted(controls_dir.glob("*.yml")):
        data = _load_yaml(yaml_file)
        if not isinstance(data, dict):
            raise LoadError(
                f"Control file '{yaml_file}' must be a YAML mapping, not {type(data).__name__}."
            )
        controls.append(Control.model_validate(data))

    # Sort by stable control ID so execution order is deterministic.
    controls.sort(key=lambda c: c.id)
    return controls


def load_profile_bundle(profile_dir: Path) -> tuple[Profile, list[Control]]:
    """Load a complete profile directory: profile.yml + controls/*.yml.

    Returns (profile, sorted list of controls).
    """
    profile = load_profile(profile_dir / "profile.yml")
    controls_dir = profile_dir / "controls"
    controls = load_controls(controls_dir) if controls_dir.is_dir() else []
    return profile, controls
