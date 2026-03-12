"""Tests for policy resolver and lockfile management (REQ-1.4)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from attest.policy.resolver import Lockfile, LockfileEntry, PolicyResolver, ResolvedDependency


class TestResolvedDependency:
    def test_create_dependency(self) -> None:
        dep = ResolvedDependency(
            name="test-policy",
            path="/path/to/policy",
            version="1.0.0",
        )
        assert dep.name == "test-policy"
        assert dep.version == "1.0.0"


class TestLockfileEntry:
    def test_from_dependency(self) -> None:
        dep = ResolvedDependency(
            name="test-policy",
            path="/path/to/policy",
            version="1.0.0",
            checksum="abc123",
        )
        entry = LockfileEntry.from_dependency(dep)
        assert entry.name == "test-policy"
        assert entry.checksum == "abc123"

    def test_to_dict(self) -> None:
        entry = LockfileEntry(name="test", path="/path", version="1.0.0")
        data = entry.to_dict()
        assert data["name"] == "test"
        assert data["path"] == "/path"


class TestLockfile:
    def test_create_empty_lockfile(self) -> None:
        lockfile = Lockfile()
        assert lockfile.schema_version == "1.0"
        assert len(lockfile.entries) == 0

    def test_add_entry(self) -> None:
        lockfile = Lockfile()
        entry = LockfileEntry(name="test", path="/path", version="1.0.0")
        lockfile.add_entry(entry)
        assert len(lockfile.entries) == 1

    def test_replace_entry(self) -> None:
        lockfile = Lockfile()
        entry1 = LockfileEntry(name="test", path="/path1", version="1.0.0")
        entry2 = LockfileEntry(name="test", path="/path2", version="2.0.0")
        lockfile.add_entry(entry1)
        lockfile.add_entry(entry2)
        assert len(lockfile.entries) == 1
        assert lockfile.entries[0].version == "2.0.0"

    def test_sort_entries(self) -> None:
        lockfile = Lockfile()
        lockfile.add_entry(LockfileEntry(name="z-policy", path="/z", version="1.0"))
        lockfile.add_entry(LockfileEntry(name="a-policy", path="/a", version="1.0"))
        lockfile.sort()
        assert lockfile.entries[0].name == "a-policy"
        assert lockfile.entries[1].name == "z-policy"

    def test_to_dict(self) -> None:
        lockfile = Lockfile()
        lockfile.add_entry(LockfileEntry(name="test", path="/path", version="1.0.0"))
        data = lockfile.to_dict()
        assert data["schema_version"] == "1.0"
        assert len(data["entries"]) == 1

    def test_write_and_read_lockfile(self, tmp_path: Path) -> None:
        lockfile_path = tmp_path / "policy.lock"
        lockfile = Lockfile()
        lockfile.add_entry(LockfileEntry(name="test", path="/path", version="1.0.0"))
        lockfile.write(lockfile_path)

        assert lockfile_path.exists()
        content = lockfile_path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["schema_version"] == "1.0"
        assert len(data["entries"]) == 1


class TestPolicyResolver:
    def test_create_resolver(self, tmp_path: Path) -> None:
        resolver = PolicyResolver(tmp_path)
        assert resolver.root_dir == tmp_path

    def test_resolve_single_profile(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "test-profile"
        profile_dir.mkdir()
        (profile_dir / "profile.yml").write_text(
            textwrap.dedent(
                """
                name: test-profile
                title: Test Profile
                version: 1.0.0
                """
            ),
            encoding="utf-8",
        )

        resolver = PolicyResolver(tmp_path)
        resolved = resolver.resolve(profile_dir)
        assert "test-profile" in resolved
        assert resolved["test-profile"].version == "1.0.0"

    def test_resolve_missing_profile_raises_error(self, tmp_path: Path) -> None:
        resolver = PolicyResolver(tmp_path)
        with pytest.raises(FileNotFoundError):
            resolver.resolve(tmp_path / "nonexistent")

    def test_lock_creates_lockfile(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "test-profile"
        profile_dir.mkdir()
        (profile_dir / "profile.yml").write_text(
            textwrap.dedent(
                """
                name: test-profile
                title: Test Profile
                version: 1.0.0
                """
            ),
            encoding="utf-8",
        )

        lockfile_path = tmp_path / "policy.lock"
        resolver = PolicyResolver(tmp_path)
        resolver.lock(profile_dir, lockfile_path)

        assert lockfile_path.exists()
        data = json.loads(lockfile_path.read_text(encoding="utf-8"))
        assert len(data["entries"]) == 1
        assert data["entries"][0]["name"] == "test-profile"

    def test_restore_from_lockfile(self, tmp_path: Path) -> None:
        lockfile_path = tmp_path / "policy.lock"
        lockfile = Lockfile()
        lockfile.add_entry(
            LockfileEntry(
                name="test-policy",
                path="/path/to/policy",
                version="1.0.0",
                checksum="abc123",
            )
        )
        lockfile.write(lockfile_path)

        resolver = PolicyResolver(tmp_path)
        resolved = resolver.restore_from_lockfile(lockfile_path)
        assert "test-policy" in resolved
        assert resolved["test-policy"].checksum == "abc123"


class TestPolicyResolverOverlays:
    """REQ-1.5: overlay dependency wiring through PolicyResolver."""

    def _make_profile_dir(
        self,
        root: Path,
        name: str,
        *,
        version: str = "1.0.0",
        depends: str = "",
    ) -> Path:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        parts = [
            f"name: {name}",
            f"title: {name} Title",
            f"version: {version}",
        ]
        if depends:
            parts.append(depends.rstrip())
        (d / "profile.yml").write_text("\n".join(parts) + "\n", encoding="utf-8")
        return d

    def _make_controls(self, dir_: Path, controls: list[dict[str, str]]) -> None:
        """Write each control as its own YAML file under dir_/controls/."""
        controls_dir = dir_ / "controls"
        controls_dir.mkdir(exist_ok=True)
        for ctrl in controls:
            lines = [f"{k}: {v}" for k, v in ctrl.items()]
            (controls_dir / f"{ctrl['id']}.yml").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )

    def test_no_overlays_returns_base(self, tmp_path: Path) -> None:
        profile_dir = self._make_profile_dir(tmp_path, "base")
        self._make_controls(
            profile_dir,
            [{"id": "ctrl-1", "title": "Control One", "impact": "0.5"}],
        )

        resolver = PolicyResolver(tmp_path)
        profile, controls = resolver.resolve_with_overlays(profile_dir)

        assert profile.name == "base"
        assert any(c.id == "ctrl-1" for c in controls)

    def test_overlay_replaces_control(self, tmp_path: Path) -> None:
        # Overlay that replaces ctrl-1 with a higher-impact version
        overlay_dir = self._make_profile_dir(tmp_path, "overlay")
        self._make_controls(
            overlay_dir,
            [{"id": "ctrl-1", "title": "Control One (Overlay)", "impact": "0.9"}],
        )

        depends_yaml = textwrap.dedent(f"""\
            depends:
              - name: overlay
                url: {overlay_dir}
                overlay: true
        """)
        profile_dir = self._make_profile_dir(tmp_path, "base", depends=depends_yaml)
        self._make_controls(
            profile_dir,
            [
                {"id": "ctrl-1", "title": "Control One", "impact": "0.5"},
                {"id": "ctrl-2", "title": "Control Two", "impact": "0.3"},
            ],
        )

        resolver = PolicyResolver(tmp_path)
        _, controls = resolver.resolve_with_overlays(profile_dir)

        ctrl_1 = next(c for c in controls if c.id == "ctrl-1")
        assert ctrl_1.impact == pytest.approx(0.9)
        assert ctrl_1.title == "Control One (Overlay)"
        assert any(c.id == "ctrl-2" for c in controls)

    def test_overlay_adds_new_control(self, tmp_path: Path) -> None:
        overlay_dir = self._make_profile_dir(tmp_path, "overlay")
        self._make_controls(
            overlay_dir,
            [{"id": "ctrl-new", "title": "Extra Control", "impact": "0.3"}],
        )

        depends_yaml = textwrap.dedent(f"""\
            depends:
              - name: overlay
                url: {overlay_dir}
                overlay: true
        """)
        profile_dir = self._make_profile_dir(tmp_path, "base", depends=depends_yaml)
        self._make_controls(
            profile_dir,
            [{"id": "ctrl-1", "title": "Control One", "impact": "0.5"}],
        )

        resolver = PolicyResolver(tmp_path)
        _, controls = resolver.resolve_with_overlays(profile_dir)

        ids = {c.id for c in controls}
        assert "ctrl-1" in ids
        assert "ctrl-new" in ids

    def test_circular_overlay_raises_value_error(self, tmp_path: Path) -> None:
        # a → b as overlay, b → a as overlay (circular)
        a_dir = tmp_path / "a"
        b_dir = tmp_path / "b"
        a_dir.mkdir()
        b_dir.mkdir()

        (a_dir / "profile.yml").write_text(
            "\n".join(
                [
                    "name: a",
                    "title: A",
                    "version: 1.0.0",
                    "depends:",
                    "  - name: b",
                    f"    url: {b_dir}",
                    "    overlay: true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (b_dir / "profile.yml").write_text(
            "\n".join(
                [
                    "name: b",
                    "title: B",
                    "version: 1.0.0",
                    "depends:",
                    "  - name: a",
                    f"    url: {a_dir}",
                    "    overlay: true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        resolver = PolicyResolver(tmp_path)
        with pytest.raises(ValueError, match="Circular overlay dependency"):
            resolver.resolve_with_overlays(a_dir)

    def test_non_overlay_depend_is_ignored(self, tmp_path: Path) -> None:
        """Non-overlay deps in `depends` should not be resolved here (REQ-1.4 scope)."""
        dep_dir = self._make_profile_dir(tmp_path, "dep")
        depends_yaml = textwrap.dedent(f"""\
            depends:
              - name: dep
                url: {dep_dir}
                overlay: false
        """)
        profile_dir = self._make_profile_dir(tmp_path, "base", depends=depends_yaml)
        self._make_controls(
            profile_dir,
            [{"id": "ctrl-1", "title": "Control One", "impact": "0.5"}],
        )

        resolver = PolicyResolver(tmp_path)
        # Should not raise, should not try to load dep_dir
        profile, _ = resolver.resolve_with_overlays(profile_dir)
        assert profile.name == "base"
