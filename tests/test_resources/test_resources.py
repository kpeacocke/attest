"""Tests for built-in resource handlers (REQ-2.1, REQ-2.2)."""

from __future__ import annotations

from pathlib import Path

from attest.resources.command import CommandResource
from attest.resources.file import FileResource
from attest.resources.os_facts import OsFactsResource


class TestOsFactsResource:
    def test_returns_platform_mapping(self) -> None:
        resource = OsFactsResource()
        result = resource.query({})
        assert not result.errors
        assert isinstance(result.data, dict)
        assert "system" in result.data

    def test_field_projection(self) -> None:
        resource = OsFactsResource()
        result = resource.query({"field": "system"})
        assert isinstance(result.data, str)


class TestFileResource:
    def test_exists_field_true_for_existing_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.txt"
        file_path.write_text("content", encoding="utf-8")

        resource = FileResource()
        result = resource.query({"path": str(file_path), "field": "exists"})
        assert not result.errors
        assert result.data is True

    def test_missing_path_parameter_returns_error(self) -> None:
        resource = FileResource()
        result = resource.query({})
        assert result.errors


class TestCommandResource:
    def test_executes_command(self) -> None:
        resource = CommandResource()
        result = resource.query({"command": "printf hello"})
        assert not result.errors
        assert result.data["rc"] == 0
        assert result.data["stdout"] == "hello"

    def test_timeout_returns_error(self) -> None:
        resource = CommandResource()
        result = resource.query({"command": "sleep 2", "timeout": 1})
        assert result.errors
        assert "timed out" in result.errors[0]
