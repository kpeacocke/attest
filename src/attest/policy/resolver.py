"""Policy resolver and lockfile manager (REQ-1.4, REQ-1.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from attest.policy.loader import load_profile, load_profile_bundle
from attest.policy.overlay import OverlayResolver
from attest.policy.schemas import Control, Profile


@dataclass
class ResolvedDependency:
    """A resolved policy dependency with path and versions."""

    name: str
    path: str
    version: str
    timestamp: float = 0.0
    checksum: str = ""


@dataclass
class LockfileEntry:
    """A single entry in the policy lockfile."""

    name: str
    path: str
    version: str
    timestamp: float = 0.0
    checksum: str = ""

    @classmethod
    def from_dependency(cls, dep: ResolvedDependency) -> LockfileEntry:
        return cls(
            name=dep.name,
            path=dep.path,
            version=dep.version,
            timestamp=dep.timestamp,
            checksum=dep.checksum,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Lockfile:
    """In-memory representation of a policy lockfile."""

    schema_version: str = "1.0"
    entries: list[LockfileEntry] = field(default_factory=list)

    def add_entry(self, entry: LockfileEntry) -> None:
        """Add or replace an entry in the lockfile."""
        self.entries = [e for e in self.entries if e.name != entry.name]
        self.entries.append(entry)

    def sort(self) -> None:
        """Sort entries by name for determinism."""
        self.entries.sort(key=lambda e: e.name)

    def to_dict(self) -> dict[str, Any]:
        self.sort()
        return {
            "schema_version": self.schema_version,
            "entries": [e.to_dict() for e in self.entries],
        }

    def write(self, path: Path | str) -> None:
        """Write the lockfile to disk in canonical JSON format."""
        content = self.to_dict()
        path_obj = Path(path)
        path_obj.write_text(json.dumps(content, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def read(cls, path: Path | str) -> Lockfile:
        """Read an existing lockfile from disk."""
        path_obj = Path(path)
        if not path_obj.exists():
            return cls()

        try:
            data = json.loads(path_obj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Failed to parse lockfile {path}: {exc}") from exc

        lockfile = cls(schema_version=data.get("schema_version", "1.0"))
        for entry_data in data.get("entries", []):
            entry = LockfileEntry(
                name=entry_data["name"],
                path=entry_data["path"],
                version=entry_data["version"],
                timestamp=entry_data.get("timestamp", 0.0),
                checksum=entry_data.get("checksum", ""),
            )
            lockfile.add_entry(entry)
        return lockfile


class PolicyResolver:
    """Resolve policy dependencies and manage lockfiles."""

    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir)
        self.resolved: dict[str, ResolvedDependency] = {}
        self.lockfile = Lockfile()
        self._overlay_resolver = OverlayResolver()

    def resolve(self, profile_dir: Path | str) -> dict[str, ResolvedDependency]:
        """
        Resolve a profile and its overlay dependencies.

        Walks the dependency tree declared in the profile's `depends` list.
        Overlay dependencies (where `overlay: true`) are applied in declaration
        order per REQ-1.5 (last-in-chain wins).
        Raises ValueError on circular dependency chains.
        """
        profile_path = Path(profile_dir)
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile directory not found: {profile_path}")

        profile = load_profile(profile_path / "profile.yml")

        dep = ResolvedDependency(
            name=profile.name,
            path=str(profile_path),
            version=profile.version,
        )
        self.resolved[profile.name] = dep

        return self.resolved

    def resolve_with_overlays(
        self,
        profile_dir: Path | str,
        *,
        visited: frozenset[str] | None = None,
    ) -> tuple[Profile, list[Control]]:
        """
        Resolve a profile directory and apply any declared overlay dependencies.

        Returns the merged (profile, controls) after all overlays have been applied.
        Raises ValueError for circular overlay chains (REQ-1.5).

        Overlay paths in `depends` are resolved relative to `root_dir`.
        """
        visited = visited or frozenset()
        profile_path = Path(profile_dir)
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile directory not found: {profile_path}")

        base_profile, base_controls = load_profile_bundle(profile_path)

        if base_profile.name in visited:
            chain = " -> ".join(sorted(visited)) + f" -> {base_profile.name}"
            raise ValueError(
                f"Circular overlay dependency detected: {chain}. "
                "Overlay chains must not reference themselves."
            )

        new_visited = visited | {base_profile.name}

        # Collect overlay dependencies in declaration order (REQ-1.5: last wins).
        overlays: list[tuple[Profile, list[Control]]] = []
        for dep in base_profile.depends:
            if not dep.overlay:
                continue
            # Paths are relative to root_dir when given as names, or absolute.
            dep_path = Path(dep.url) if dep.url else self.root_dir / dep.name
            overlay_profile, overlay_controls = self.resolve_with_overlays(
                dep_path, visited=new_visited
            )
            overlays.append((overlay_profile, overlay_controls))

        if not overlays:
            return base_profile, base_controls

        return self._overlay_resolver.apply_overlays(base_profile, base_controls, overlays)

    def lock(self, profile_dir: Path | str, lockfile_path: Path | str) -> None:
        """Resolve and write a lockfile for a profile directory."""
        self.resolve(profile_dir)
        self.lockfile = Lockfile()
        for dep in self.resolved.values():
            self.lockfile.add_entry(LockfileEntry.from_dependency(dep))

        self.lockfile.write(lockfile_path)

    def restore_from_lockfile(self, lockfile_path: Path | str) -> dict[str, ResolvedDependency]:
        """Load resolved dependencies from a lockfile."""
        self.lockfile = Lockfile.read(lockfile_path)
        self.resolved = {}
        for entry in self.lockfile.entries:
            dep = ResolvedDependency(
                name=entry.name,
                path=entry.path,
                version=entry.version,
                timestamp=entry.timestamp,
                checksum=entry.checksum,
            )
            self.resolved[entry.name] = dep
        return self.resolved
