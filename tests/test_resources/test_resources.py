"""Tests for built-in resource handlers (REQ-2.1, REQ-2.2)."""

from __future__ import annotations

from pathlib import Path

from attest.resources.builtin import build_builtin_registry
from attest.resources.command import CommandResource
from attest.resources.file import FileResource
from attest.resources.os_facts import OsFactsResource
from attest.resources.package import PackageResource
from attest.resources.service import ServiceResource
from attest.resources.sysctl import SysctlResource


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


class TestPackageResource:
    def test_missing_name_returns_error(self) -> None:
        resource = PackageResource()
        result = resource.query({})
        assert result.errors

    def test_query_returns_structured_fields(self) -> None:
        resource = PackageResource()
        result = resource.query({"name": "bash"})
        if result.errors:
            # Environment may not provide a supported package tool.
            assert "package query tool" in result.errors[0]
            return

        assert isinstance(result.data, dict)
        assert "installed" in result.data
        assert "version" in result.data


class TestServiceResource:
    def test_missing_name_returns_error(self) -> None:
        resource = ServiceResource()
        result = resource.query({})
        assert result.errors

    def test_query_returns_state_or_platform_error(self) -> None:
        resource = ServiceResource()
        result = resource.query({"name": "ssh"})
        if result.errors:
            assert "systemctl" in result.errors[0]
            return

        assert isinstance(result.data, dict)
        assert "running" in result.data
        assert "enabled" in result.data


class TestSysctlResource:
    def test_missing_key_returns_error(self) -> None:
        resource = SysctlResource()
        result = resource.query({})
        assert result.errors

    def test_reads_existing_key_or_reports_error(self) -> None:
        resource = SysctlResource()
        result = resource.query({"key": "kernel.ostype"})
        if result.errors:
            # Some minimal containers may not expose this key/tool.
            assert result.errors[0]
            return

        assert isinstance(result.data, str)
        assert result.data


class TestBuiltinRegistry:
    def test_contains_new_resources(self) -> None:
        registry = build_builtin_registry()
        assert registry.has("package")
        assert registry.has("service")
        assert registry.has("sysctl")
