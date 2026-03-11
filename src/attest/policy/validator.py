"""Profile and control validation logic (REQ-1.1, REQ-1.2, REQ-1.3)."""

from __future__ import annotations

from dataclasses import dataclass, field

from attest.policy.schemas import Control, Profile


@dataclass
class ValidationResult:
    """Outcome of a profile or control validation pass."""

    valid: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def validate_profile(profile: Profile) -> ValidationResult:
    """Validate a loaded Profile beyond basic schema checks.

    Returns a ValidationResult; callers should check .valid and surface .errors.
    """
    errors: list[str] = []

    if not profile.title.strip():
        errors.append("Profile 'title' must not be empty.")
    if not profile.version.strip():
        errors.append("Profile 'version' must not be empty.")

    # Validate that required inputs have no default (they must be supplied at runtime).
    for inp in profile.inputs:
        if inp.required and inp.default is not None:
            errors.append(
                f"Input '{inp.name}' is marked required but also has a default value; "
                "remove the default or mark it optional."
            )

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_controls(controls: list[Control]) -> ValidationResult:
    """Validate a list of loaded controls for uniqueness and completeness.

    Returns a ValidationResult.
    """
    errors: list[str] = []

    ids_seen: set[str] = set()
    for control in controls:
        if control.id in ids_seen:
            errors.append(f"Duplicate control ID '{control.id}'.")
        ids_seen.add(control.id)

        if not control.title.strip():
            errors.append(f"Control '{control.id}' must have a non-empty 'title'.")

        if not control.tests:
            errors.append(f"Control '{control.id}' has no tests; at least one test is required.")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_bundle(profile: Profile, controls: list[Control]) -> ValidationResult:
    """Validate a complete profile bundle (profile + controls together).

    Combines profile and controls validation results.
    """
    p_result = validate_profile(profile)
    c_result = validate_controls(controls)
    all_errors = p_result.errors + c_result.errors
    return ValidationResult(valid=len(all_errors) == 0, errors=all_errors)
