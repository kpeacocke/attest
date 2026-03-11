"""Tests for overlay resolution and inheritance composition."""

import pytest

from attest.policy.overlay import OverlayResolver
from attest.policy.schemas import Control, Profile, ProfileInput


class TestOverlayResolver:
    """Test suite for profile overlay resolution."""

    @pytest.fixture
    def resolver(self) -> OverlayResolver:
        """Provide an OverlayResolver instance."""
        return OverlayResolver()

    @pytest.fixture
    def simple_base_profile(self) -> Profile:
        """Create a minimal base profile."""
        return Profile(
            name="base",
            title="Base Profile",
            version="1.0.0",
            summary="Base profile",
            inputs=[ProfileInput(name="env", description="Environment", required=True)],
            depends=[],
        )

    @pytest.fixture
    def simple_base_controls(self) -> list[Control]:
        """Create minimal base controls."""
        return [
            Control(
                id="C1",
                title="Control 1",
                desc="Base control 1",
            ),
            Control(
                id="C2",
                title="Control 2",
                desc="Base control 2",
            ),
        ]

    @pytest.fixture
    def overlay_profile(self) -> Profile:
        """Create an overlay profile."""
        return Profile(
            name="overlay",
            title="Overlay Profile",
            version="1.1.0",
            summary="Overlay profile",
            inputs=[ProfileInput(name="region", description="AWS region", required=False)],
            depends=[],
        )

    @pytest.fixture
    def overlay_controls(self) -> list[Control]:
        """Create overlay controls."""
        return [
            Control(
                id="C1",  # Override C1
                title="Control 1 (Overlaid)",
                desc="Overlaid control 1",
            ),
            Control(
                id="C3",  # New control
                title="Control 3",
                desc="New control added by overlay",
            ),
        ]

    def test_resolve_overlay_replaces_matching_controls(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> None:
        """Overlay controls with matching IDs should replace base controls."""
        merged_profile, merged_controls = resolver.resolve_overlay(
            simple_base_profile,
            simple_base_controls,
            overlay_profile,
            overlay_controls,
        )

        # Find C1 in merged—should be the overlay version
        c1 = next((c for c in merged_controls if c.id == "C1"), None)
        assert c1 is not None
        assert c1.title == "Control 1 (Overlaid)"

    def test_resolve_overlay_preserves_unmatched_controls(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> None:
        """Base controls without overlay should remain unchanged."""
        merged_profile, merged_controls = resolver.resolve_overlay(
            simple_base_profile,
            simple_base_controls,
            overlay_profile,
            overlay_controls,
        )

        # C2 should still exist from base
        c2 = next((c for c in merged_controls if c.id == "C2"), None)
        assert c2 is not None
        assert c2.desc == "Base control 2"

    def test_resolve_overlay_adds_new_controls(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> None:
        """Overlay controls without base match should be added."""
        merged_profile, merged_controls = resolver.resolve_overlay(
            simple_base_profile,
            simple_base_controls,
            overlay_profile,
            overlay_controls,
        )

        # C3 should be present (new from overlay)
        c3 = next((c for c in merged_controls if c.id == "C3"), None)
        assert c3 is not None

    def test_resolve_overlay_merges_inputs(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> None:
        """Inputs should merge, with overlay overriding base."""
        merged_profile, _ = resolver.resolve_overlay(
            simple_base_profile,
            simple_base_controls,
            overlay_profile,
            overlay_controls,
        )

        input_names = {inp.name for inp in merged_profile.inputs}
        assert "env" in input_names  # From base
        assert "region" in input_names  # From overlay

    def test_resolve_overlay_deterministic_order(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> None:
        """Merged controls should be sorted by ID for determinism."""
        _, merged_controls = resolver.resolve_overlay(
            simple_base_profile,
            simple_base_controls,
            overlay_profile,
            overlay_controls,
        )

        control_ids = [c.id for c in merged_controls]
        assert control_ids == sorted(control_ids)

    def test_resolve_overlay_preserves_base_profile_identity(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
        overlay_profile: Profile,
        overlay_controls: list[Control],
    ) -> None:
        """Overlay should not override base profile name and version."""
        merged_profile, _ = resolver.resolve_overlay(
            simple_base_profile,
            simple_base_controls,
            overlay_profile,
            overlay_controls,
        )

        assert merged_profile.name == "base"
        assert merged_profile.version == "1.0.0"

    def test_apply_overlays_sequence(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
    ) -> None:
        """Applying multiple overlays should chain results."""
        # First overlay
        overlay1 = Profile(
            name="overlay1",
            title="Overlay 1",
            version="1.1.0",
            summary="First overlay",
            inputs=[],
            depends=[],
        )
        overlay1_controls = [
            Control(id="C1", title="C1 Modified by Overlay 1", desc="desc"),
        ]

        # Second overlay
        overlay2 = Profile(
            name="overlay2",
            title="Overlay 2",
            version="1.2.0",
            summary="Second overlay",
            inputs=[],
            depends=[],
        )
        overlay2_controls = [
            Control(id="C1", title="C1 Modified by Overlay 2", desc="desc"),
        ]

        result_profile, result_controls = resolver.apply_overlays(
            simple_base_profile,
            simple_base_controls,
            [
                (overlay1, overlay1_controls),
                (overlay2, overlay2_controls),
            ],
        )

        # Second overlay should win
        c1 = next((c for c in result_controls if c.id == "C1"), None)
        assert c1 is not None
        assert c1.title == "C1 Modified by Overlay 2"

    def test_apply_overlays_preserves_identity(
        self,
        resolver: OverlayResolver,
        simple_base_profile: Profile,
        simple_base_controls: list[Control],
    ) -> None:
        """Apply overlays should preserve base profile identity."""
        overlay = Profile(
            name="overlay",
            title="Overlay",
            version="1.1.0",
            summary="Overlay",
            inputs=[],
            depends=[],
        )
        overlay_controls = []

        result_profile, _ = resolver.apply_overlays(
            simple_base_profile,
            simple_base_controls,
            [(overlay, overlay_controls)],
        )

        assert result_profile.name == "base"
        assert result_profile.version == "1.0.0"

    def test_merge_profiles_adds_empty_summary_from_overlay(self) -> None:
        """If base summary is empty, overlay summary can provide it."""
        resolver = OverlayResolver()

        base = Profile(
            name="base",
            title="Base",
            version="1.0.0",
            summary="",
            inputs=[],
            depends=[],
        )
        overlay = Profile(
            name="overlay",
            title="Overlay",
            version="1.0.0",
            summary="From overlay",
            inputs=[],
            depends=[],
        )

        merged = resolver._merge_profiles(base, overlay)
        assert merged.summary == "From overlay"

    def test_merge_profiles_preserves_base_summary(self) -> None:
        """Base summary should not be replaced if already present."""
        resolver = OverlayResolver()

        base = Profile(
            name="base",
            title="Base",
            version="1.0.0",
            summary="Base summary",
            inputs=[],
            depends=[],
        )
        overlay = Profile(
            name="overlay",
            title="Overlay",
            version="1.0.0",
            summary="Overlay summary",
            inputs=[],
            depends=[],
        )

        merged = resolver._merge_profiles(base, overlay)
        assert merged.summary == "Base summary"

    def test_merge_controls_empty_base(self) -> None:
        """Merging with empty base should return overlay controls."""
        resolver = OverlayResolver()

        overlay_controls = [
            Control(id="C1", title="Control 1", desc="desc"),
        ]

        merged = resolver._merge_controls([], overlay_controls)
        assert len(merged) == 1
        assert merged[0].id == "C1"

    def test_merge_controls_empty_overlay(self) -> None:
        """Merging with empty overlay should return base controls."""
        resolver = OverlayResolver()

        base_controls = [
            Control(id="C1", title="Control 1", desc="desc"),
        ]

        merged = resolver._merge_controls(base_controls, [])
        assert len(merged) == 1
        assert merged[0].id == "C1"

    def test_merge_controls_duplicates_in_overlay_keep_first(self) -> None:
        """When overlay has duplicates, merging should use overlay version."""
        resolver = OverlayResolver()

        base_controls = [
            Control(id="C1", title="Base C1", desc="base"),
        ]
        overlay_controls = [
            Control(id="C1", title="Overlay C1", desc="overlay"),
        ]

        merged = resolver._merge_controls(base_controls, overlay_controls)
        assert len(merged) == 1
        assert merged[0].title == "Overlay C1"
