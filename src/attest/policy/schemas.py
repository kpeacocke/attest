"""Pydantic schemas for Attest policy objects (REQ-1.1, REQ-1.2, REQ-1.3)."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Reusable types
# ---------------------------------------------------------------------------

ControlId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_\-]+$")]


# ---------------------------------------------------------------------------
# Profile input (REQ-1.3)
# ---------------------------------------------------------------------------


class ProfileInput(BaseModel):
    """A typed input parameter declared by a profile."""

    name: str
    type: str = "string"  # string | integer | float | boolean | list
    description: str = ""
    required: bool = False
    default: Any = None

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        allowed = {"string", "integer", "float", "boolean", "list"}
        if v not in allowed:
            raise ValueError(f"Input type '{v}' is not valid; must be one of {sorted(allowed)}.")
        return v


# ---------------------------------------------------------------------------
# Profile dependency (REQ-1.4)
# ---------------------------------------------------------------------------


class ProfileDependency(BaseModel):
    """A declared dependency on another profile or overlay."""

    name: str
    url: str | None = None
    version: str | None = None
    overlay: bool = False  # True → this is a profile overlay (REQ-1.5)


# ---------------------------------------------------------------------------
# Control tags (REQ-1.2) — structured namespace keys
# ---------------------------------------------------------------------------


class ControlTags(BaseModel):
    """Structured compliance framework tag mappings."""

    nist: list[str] = Field(default_factory=list)
    cis_level: int | None = None
    stig_severity: str | None = None
    custom: list[str] = Field(default_factory=list)

    @field_validator("stig_severity")
    @classmethod
    def _valid_stig(cls, v: str | None) -> str | None:
        if v is not None and v not in {"CAT I", "CAT II", "CAT III"}:
            raise ValueError(
                f"stig_severity '{v}' is not valid; must be 'CAT I', 'CAT II', or 'CAT III'."
            )
        return v

    @field_validator("cis_level")
    @classmethod
    def _valid_cis(cls, v: int | None) -> int | None:
        if v is not None and v not in {1, 2}:
            raise ValueError(f"cis_level '{v}' is not valid; must be 1 or 2.")
        return v


# ---------------------------------------------------------------------------
# Test assertion (part of REQ-1.2)
# ---------------------------------------------------------------------------

VALID_OPERATORS = frozenset(
    {"eq", "ne", "contains", "regex", "exists", "not_exists", "cmp", "in_list", "not_in_list"}
)


class TestAssertion(BaseModel):
    """A single test assertion within a control."""

    __test__ = False

    name: str
    resource: str
    operator: str
    expected: Any = None
    # Optional resource-specific parameters forwarded to the resource handler.
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("operator")
    @classmethod
    def _valid_operator(cls, v: str) -> str:
        if v not in VALID_OPERATORS:
            raise ValueError(
                f"Operator '{v}' is not supported. Valid operators: {sorted(VALID_OPERATORS)}."
            )
        return v


# ---------------------------------------------------------------------------
# Control source provenance (REQ-1.2)
# ---------------------------------------------------------------------------


class ControlSource(BaseModel):
    """Provenance block: where this control content came from."""

    origin: str = ""
    upstream_id: str | None = None
    upstream_version: str | None = None


# ---------------------------------------------------------------------------
# Control (REQ-1.2)
# ---------------------------------------------------------------------------


class Control(BaseModel):
    """A single compliance control with tests."""

    id: ControlId
    title: str
    desc: str = ""
    impact: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: ControlTags = Field(default_factory=ControlTags)
    only_if: str | None = None
    skip_if: str | None = None
    tests: list[TestAssertion] = Field(default_factory=list)
    source: ControlSource = Field(default_factory=ControlSource)

    @field_validator("tests")
    @classmethod
    def _at_least_one_test_or_empty(cls, v: list[TestAssertion]) -> list[TestAssertion]:
        # Tests may be empty during authoring; validator.py enforces completeness.
        return v

    @model_validator(mode="after")
    def _no_conflicting_predicates(self) -> "Control":
        if self.only_if and self.skip_if:
            raise ValueError(f"Control '{self.id}' has both 'only_if' and 'skip_if'; use only one.")
        return self


# ---------------------------------------------------------------------------
# Profile supports block (REQ-1.1)
# ---------------------------------------------------------------------------


class PlatformSupport(BaseModel):
    """Platform applicability hint for a profile."""

    os: str | None = None
    family: str | None = None
    min_version: str | None = None


# ---------------------------------------------------------------------------
# Profile (REQ-1.1)
# ---------------------------------------------------------------------------


class Profile(BaseModel):
    """Top-level profile definition."""

    name: str
    title: str
    version: str
    summary: str = ""
    licence: str = ""
    supports: list[PlatformSupport] = Field(default_factory=list)
    inputs: list[ProfileInput] = Field(default_factory=list)
    depends: list[ProfileDependency] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _slug_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9_\-]+$", v):
            raise ValueError(
                f"Profile name '{v}' must be lowercase alphanumeric, hyphens, or underscores."
            )
        return v
