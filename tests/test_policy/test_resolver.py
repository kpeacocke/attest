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
