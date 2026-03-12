"""Tests for Policy loader (REQ-1.1, REQ-1.2)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from attest.policy.loader import LoadError, load_controls, load_profile, load_profile_bundle


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def _profile_dir(tmp_path: Path, profile_yaml: str, controls: dict[str, str] | None = None) -> Path:
    """Create a minimal profile directory structure."""
    _write(tmp_path, "profile.yml", profile_yaml)
    if controls:
        ctrl_dir = tmp_path / "controls"
        ctrl_dir.mkdir()
        for fname, content in controls.items():
            _write(ctrl_dir, fname, content)
    return tmp_path


VALID_PROFILE = """
    name: linux-hardening
    title: Linux Hardening Profile
    version: 1.0.0
"""

VALID_CONTROL = """
    id: LH-001
    title: SSH root login disabled
    tests:
      - name: check sshd
        resource: sshd_config
        operator: eq
        expected: "no"
"""


class TestLoadProfile:
    def test_loads_valid_profile(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "profile.yml", VALID_PROFILE)
        profile = load_profile(path)
        assert profile.name == "linux-hardening"
        assert profile.version == "1.0.0"

    def test_missing_file_raises_load_error(self, tmp_path: Path) -> None:
        with pytest.raises(LoadError, match="Cannot read"):
            load_profile(tmp_path / "missing.yml")

    def test_invalid_yaml_raises_load_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "bad.yml", ": : invalid:")
        with pytest.raises(LoadError, match="YAML parse error"):
            load_profile(path)

    def test_non_mapping_raises_load_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "list.yml", "- item1\n- item2\n")
        with pytest.raises(LoadError, match="must be a YAML mapping"):
            load_profile(path)

    def test_invalid_schema_raises_validation_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "profile.yml", "name: INVALID NAME\ntitle: T\nversion: 1.0\n")
        with pytest.raises(ValidationError):
            load_profile(path)


class TestLoadControls:
    def test_loads_sorted_by_id(self, tmp_path: Path) -> None:
        ctrl_dir = tmp_path / "controls"
        ctrl_dir.mkdir()
        _write(ctrl_dir, "z_control.yml", "id: ZZ-001\ntitle: Z\ntests: []\n")
        _write(ctrl_dir, "a_control.yml", "id: AA-001\ntitle: A\ntests: []\n")
        controls = load_controls(ctrl_dir)
        assert controls[0].id == "AA-001"
        assert controls[1].id == "ZZ-001"

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(LoadError, match="does not exist"):
            load_controls(tmp_path / "nonexistent")


class TestLoadProfileBundle:
    def test_bundle_with_controls(self, tmp_path: Path) -> None:
        _profile_dir(tmp_path, VALID_PROFILE, {"lh001.yml": VALID_CONTROL})
        profile, controls = load_profile_bundle(tmp_path)
        assert profile.name == "linux-hardening"
        assert len(controls) == 1
        assert controls[0].id == "LH-001"

    def test_bundle_without_controls_dir(self, tmp_path: Path) -> None:
        _profile_dir(tmp_path, VALID_PROFILE)
        _, controls = load_profile_bundle(tmp_path)
        assert len(controls) == 0
