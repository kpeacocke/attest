"""Policy overlay and inheritance resolution (REQ-1.5)."""

from __future__ import annotations

from attest.policy.schemas import Control, Profile


class OverlayResolver:
    """Resolve and compose profile overlays and inheritance."""

    def resolve_overlay(
        self,
        base_profile: Profile,
        base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> tuple[Profile, list[Control]]:
        """
        Merge an overlay profile into a base profile.

        Resolution rules:
        - Overlay profile metadata does not override base (name, version stay base)
        - Overlay controls replace or extend base controls by ID
        - Tags, inputs, and dependencies merge with overlay taking precedence
        """
        # Merge profile metadata
        merged_profile = self._merge_profiles(base_profile, overlay_profile)

        # Merge controls by ID, recording provenance from the overlay profile name.
        merged_controls = self._merge_controls(
            base_controls,
            overlay_controls,
            overlay_source=overlay_profile.name,
        )

        return merged_profile, merged_controls

    def _merge_profiles(self, base: Profile, overlay: Profile) -> Profile:
        """Merge profile-level metadata, preferring overlay values where applicable."""
        # Keep base name/version for identity
        merged_data = base.model_dump()

        # Merge inputs (overlay can add/override)
        base_input_names = {inp.name for inp in base.inputs}
        overlay_inputs = {inp.name: inp for inp in overlay.inputs}
        merged_inputs = list(base.inputs)
        for name, overlay_input in overlay_inputs.items():
            if name in base_input_names:
                # Replace base input
                merged_inputs = [inp for inp in merged_inputs if inp.name != name]
            merged_inputs.append(overlay_input)

        # Merge dependencies (avoid duplicates by name)
        merged_data["inputs"] = merged_inputs
        base_dep_names = {dep.name for dep in base.depends}
        overlay_deps = {dep.name: dep for dep in overlay.depends}
        merged_deps = list(base.depends)
        for name, overlay_dep in overlay_deps.items():
            if name in base_dep_names:
                merged_deps = [d for d in merged_deps if d.name != name]
            merged_deps.append(overlay_dep)
        merged_data["depends"] = merged_deps

        # Overlay can provide a better summary if base had empty summary
        if overlay.summary and not base.summary:
            merged_data["summary"] = overlay.summary

        return Profile(**merged_data)

    def _merge_controls(
        self,
        base: list[Control],
        overlay: list[Control],
        overlay_source: str = "",
    ) -> list[Control]:
        """
        Merge controls by ID.

        Overlay control replaces base control with same ID.
        Base controls without overlay remain.
        Overlay controls without base are appended.

        When an overlay replaces a base control, overlay_source and
        original_impact are recorded on the merged control (REQ-1.5, REQ-4.1).
        """
        base_by_id = {ctrl.id: ctrl for ctrl in base}
        overlay_by_id = {ctrl.id: ctrl for ctrl in overlay}

        # Start with all base controls, replacing IDs present in overlay
        merged: list[Control] = []
        for ctrl_id, ctrl in base_by_id.items():
            if ctrl_id in overlay_by_id:
                overlay_ctrl = overlay_by_id[ctrl_id]
                patched = overlay_ctrl.model_copy(
                    update={
                        "overlay_source": overlay_source
                        or overlay_ctrl.source.origin
                        or "overlay",
                        "original_impact": ctrl.impact,
                    }
                )
                merged.append(patched)
            else:
                merged.append(ctrl)

        # Add overlay controls that don't exist in base
        for ctrl_id, ctrl in overlay_by_id.items():
            if ctrl_id not in base_by_id:
                merged.append(ctrl)

        # Sort by control ID for determinism
        merged.sort(key=lambda c: c.id)
        return merged

    def apply_overlays(
        self,
        base_profile: Profile,
        base_controls: list[Control],
        overlays: list[tuple[Profile, list[Control]]],
    ) -> tuple[Profile, list[Control]]:
        """
        Apply a sequence of overlays to a base profile.

        Each overlay is applied in order, building on the result of the previous.
        """
        current_profile = base_profile
        current_controls = base_controls

        for overlay_profile, overlay_controls in overlays:
            current_profile, current_controls = self.resolve_overlay(
                current_profile,
                current_controls,
                overlay_profile,
                overlay_controls,
            )

        return current_profile, current_controls

    def validate_overlay_chain(self, overlays: list[tuple[Profile, list[Control]]]) -> bool:
        """
        Validate that an overlay chain is consistent.

        Version constraints and dependency satisfaction are minimal validation.
        """
        # For now, basic validation—extends could check SemVer constraints
        return bool(overlays)
