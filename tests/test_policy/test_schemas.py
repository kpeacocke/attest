"""Tests for Policy layer schemas (REQ-1.1, REQ-1.2, REQ-1.3)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from attest.policy.schemas import (
    Control,
    ControlTags,
    Profile,
    ProfileInput,
)


class TestProfileSchema:
    def test_valid_minimal_profile(self) -> None:
        p = Profile(name="test-profile", title="Test", version="1.0.0")
        assert p.name == "test-profile"

    def test_name_must_be_lowercase_slug(self) -> None:
        with pytest.raises(ValidationError, match="lowercase"):
            Profile(name="Test Profile", title="Test", version="1.0.0")

    def test_name_allows_hyphens_and_underscores(self) -> None:
        p = Profile(name="my_profile-v2", title="T", version="1.0")
        assert p.name == "my_profile-v2"

    def test_inputs_list(self) -> None:
        p = Profile(
            name="p",
            title="P",
            version="1.0",
            inputs=[{"name": "env", "type": "string", "required": True}],
        )
        assert p.inputs[0].required is True


class TestProfileInput:
    def test_valid_types(self) -> None:
        for t in ("string", "integer", "float", "boolean", "list"):
            inp = ProfileInput(name="x", type=t)
            assert inp.type == t

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValidationError, match="not valid"):
            ProfileInput(name="x", type="dict")


class TestControlSchema:
    def test_valid_minimal_control(self) -> None:
        c = Control(
            id="LH-001",
            title="SSH root login disabled",
            tests=[
                {"name": "check sshd", "resource": "sshd_config", "operator": "eq", "expected": "no"}
            ],
        )
        assert c.id == "LH-001"
        assert len(c.tests) == 1

    def test_impact_clamped(self) -> None:
        with pytest.raises(ValidationError):
            Control(id="X-001", title="T", impact=1.5, tests=[])

    def test_conflicting_predicates_raises(self) -> None:
        with pytest.raises(ValidationError, match="only_if.*skip_if|skip_if.*only_if"):
            Control(
                id="X-001",
                title="T",
                only_if="platform == 'linux'",
                skip_if="platform == 'windows'",
                tests=[],
            )

    def test_invalid_operator_raises(self) -> None:
        with pytest.raises(ValidationError, match="not supported"):
            Control(
                id="X-001",
                title="T",
                tests=[{"name": "t", "resource": "r", "operator": "magic", "expected": "x"}],
            )


class TestControlTags:
    def test_valid_stig_severity(self) -> None:
        tags = ControlTags(stig_severity="CAT I")
        assert tags.stig_severity == "CAT I"

    def test_invalid_stig_raises(self) -> None:
        with pytest.raises(ValidationError, match="not valid"):
            ControlTags(stig_severity="CAT IV")

    def test_valid_cis_levels(self) -> None:
        for lvl in (1, 2):
            tags = ControlTags(cis_level=lvl)
            assert tags.cis_level == lvl

    def test_invalid_cis_raises(self) -> None:
        with pytest.raises(ValidationError, match="not valid"):
            ControlTags(cis_level=3)
