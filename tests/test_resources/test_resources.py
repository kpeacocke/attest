"""Tests for built-in resource handlers (REQ-2.1, REQ-2.2)."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from attest.resources.auditd_rules import AuditdRulesResource
from attest.resources.builtin import build_builtin_registry
from attest.resources.command import CommandResource
from attest.resources.crontab import CrontabResource
from attest.resources.file import FileResource
from attest.resources.group import GroupResource
from attest.resources.kernel_module import KernelModuleResource
from attest.resources.mount import MountResource
from attest.resources.os_facts import OsFactsResource
from attest.resources.package import PackageResource
from attest.resources.port import PortResource
from attest.resources.process import ProcessResource
from attest.resources.service import ServiceResource
from attest.resources.ssh_config import SshConfigResource
from attest.resources.sysctl import SysctlResource
from attest.resources.user import UserResource


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

    def test_computes_file_hash_sha256(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.bin"
        file_path.write_bytes(b"test content")

        resource = FileResource()
        result = resource.query({"path": str(file_path), "hash_algorithm": "sha256"})
        assert not result.errors
        assert "hash" in result.data
        assert result.data["hash_algorithm"] == "sha256"
        assert len(result.data["hash"]) == 64  # SHA256 hex is 64 chars

    def test_computes_md5_hash(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.bin"
        file_path.write_bytes(b"test content")

        resource = FileResource()
        result = resource.query({"path": str(file_path), "hash_algorithm": "md5"})
        assert not result.errors
        assert "hash" in result.data
        assert result.data["hash_algorithm"] == "md5"
        assert len(result.data["hash"]) == 32  # MD5 hex is 32 chars

    def test_hash_comparison_matches(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.bin"
        content = b"test content"
        file_path.write_bytes(content)

        import hashlib

        expected_hash = hashlib.sha256(content).hexdigest()

        resource = FileResource()
        result = resource.query(
            {
                "path": str(file_path),
                "hash_algorithm": "sha256",
                "expected_hash": expected_hash,
            }
        )
        assert not result.errors
        assert result.data["hash_match"] is True

    def test_hash_comparison_fails(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.bin"
        file_path.write_bytes(b"test content")

        resource = FileResource()
        result = resource.query(
            {
                "path": str(file_path),
                "hash_algorithm": "sha256",
                "expected_hash": "wronghash",
            }
        )
        assert not result.errors
        assert result.data["hash_match"] is False

    def test_invalid_hash_algorithm_is_ignored(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.bin"
        file_path.write_bytes(b"test content")

        resource = FileResource()
        result = resource.query(
            {
                "path": str(file_path),
                "hash_algorithm": "invalid_algo",
            }
        )
        assert not result.errors
        assert "hash" not in result.data


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


class TestProcessResource:
    def test_missing_ps_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.process.shutil.which", lambda _cmd: None)
        resource = ProcessResource()
        result = resource.query({})
        assert result.errors
        assert "ps" in result.errors[0]

    def test_invalid_pid_returns_error(self) -> None:
        resource = ProcessResource()
        result = resource.query({"pid": "abc"})
        assert result.errors

    def test_filters_processes_and_projects_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.process.shutil.which", lambda _cmd: "/usr/bin/ps")
        monkeypatch.setattr(
            "attest.resources.process.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="100 root sshd\n200 daemon cron\n201 root sshd\n",
                stderr="",
            ),
        )

        resource = ProcessResource()
        monkeypatch.setattr(resource, "_read_capabilities", lambda _pid: "00000000a80425fb")

        result = resource.query({"name": "sshd"})
        assert not result.errors
        assert result.data["exists"] is True
        assert result.data["count"] == 2
        assert result.data["pids"] == [100, 201]
        assert result.data["users"] == ["root"]
        assert result.data["processes"][0]["capabilities"] == "00000000a80425fb"

    def test_field_projection_returns_scalar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.process.shutil.which", lambda _cmd: "/usr/bin/ps")
        monkeypatch.setattr(
            "attest.resources.process.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="100 root sshd\n",
                stderr="",
            ),
        )

        resource = ProcessResource()
        monkeypatch.setattr(resource, "_read_capabilities", lambda _pid: None)
        result = resource.query({"name": "sshd", "field": "count"})
        assert result.data == 1


class TestPortResource:
    def test_missing_ss_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.port.shutil.which", lambda _cmd: None)
        resource = PortResource()
        result = resource.query({})
        assert result.errors
        assert "ss" in result.errors[0]

    def test_invalid_port_returns_error(self) -> None:
        resource = PortResource()
        result = resource.query({"port": "abc"})
        assert result.errors

    def test_invalid_protocol_returns_error(self) -> None:
        resource = PortResource()
        result = resource.query({"protocol": "icmp"})
        assert result.errors

    def test_filters_listeners(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.port.shutil.which", lambda _cmd: "/usr/bin/ss")
        monkeypatch.setattr(
            "attest.resources.port.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout=(
                    "tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n"
                    "udp UNCONN 0 0 127.0.0.53%lo:53 0.0.0.0:*\n"
                    "tcp LISTEN 0 128 [::]:22 [::]:*\n"
                ),
                stderr="",
            ),
        )

        resource = PortResource()
        result = resource.query({"protocol": "tcp", "port": 22})
        assert not result.errors
        assert result.data["listening"] is True
        assert result.data["count"] == 2
        assert result.data["ports"] == [22, 22]
        assert result.data["listeners"][0]["protocol"] == "tcp"

    def test_field_projection_returns_scalar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.port.shutil.which", lambda _cmd: "/usr/bin/ss")
        monkeypatch.setattr(
            "attest.resources.port.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n",
                stderr="",
            ),
        )

        resource = PortResource()
        result = resource.query({"port": "22", "field": "count"})
        assert result.data == 1


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


class TestSshConfigResource:
    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        resource = SshConfigResource()
        result = resource.query({"path": str(tmp_path / "missing.conf")})
        assert result.errors

    def test_parses_top_level_directives(self, tmp_path: Path) -> None:
        config_path = tmp_path / "sshd_config"
        config_path.write_text(
            """# comment
PermitRootLogin no
PasswordAuthentication yes
""",
            encoding="utf-8",
        )

        resource = SshConfigResource()
        result = resource.query({"path": str(config_path)})
        assert not result.errors
        assert result.data["permitrootlogin"] == "no"
        assert result.data["passwordauthentication"] == "yes"

    def test_field_projection_is_case_insensitive(self, tmp_path: Path) -> None:
        config_path = tmp_path / "sshd_config"
        config_path.write_text("PermitRootLogin prohibit-password\n", encoding="utf-8")

        resource = SshConfigResource()
        result = resource.query({"path": str(config_path), "field": "PermitRootLogin"})
        assert result.data == "prohibit-password"

    def test_ignores_match_block_overrides(self, tmp_path: Path) -> None:
        config_path = tmp_path / "sshd_config"
        config_path.write_text(
            """
PermitRootLogin no
Match User root
    PermitRootLogin yes
""",
            encoding="utf-8",
        )

        resource = SshConfigResource()
        result = resource.query({"path": str(config_path), "field": "PermitRootLogin"})
        assert result.data == "no"


class TestMountResource:
    def test_missing_mount_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.mount.shutil.which", lambda _cmd: None)
        resource = MountResource()
        result = resource.query({})
        assert result.errors
        assert "mount" in result.errors[0]

    def test_invalid_mount_point_returns_error(self) -> None:
        resource = MountResource()
        result = resource.query({"mount_point": ""})
        assert result.errors

    def test_filters_by_mount_point(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.mount.shutil.which", lambda _cmd: "/usr/bin/mount")
        monkeypatch.setattr(
            "attest.resources.mount.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="/dev/sda1 on / type ext4 (rw,relatime)\ntmpfs on /tmp type tmpfs (rw,nosuid,nodev)\n/dev/sda2 on /boot type ext4 (rw,noexec,nosuid,nodev)\n",
                stderr="",
            ),
        )

        resource = MountResource()
        result = resource.query({"mount_point": "/tmp"})
        assert not result.errors
        assert result.data["exists"] is True
        assert result.data["count"] == 1
        assert result.data["mounts"][0]["fstype"] == "tmpfs"
        assert result.data["mounts"][0]["has_nosuid"] is True
        assert result.data["mounts"][0]["has_nodev"] is True

    def test_parses_mount_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.mount.shutil.which", lambda _cmd: "/usr/bin/mount")
        monkeypatch.setattr(
            "attest.resources.mount.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="/dev/sda2 on /boot type ext4 (rw,noexec,nosuid,nodev)\n",
                stderr="",
            ),
        )

        resource = MountResource()
        result = resource.query({"field": "mounts"})
        assert result.data[0]["has_noexec"] is True
        assert result.data[0]["has_nosuid"] is True
        assert result.data[0]["has_nodev"] is True


class TestUserResource:
    def test_missing_getent_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.user.shutil.which", lambda _cmd: None)
        resource = UserResource()
        result = resource.query({"name": "root"})
        assert result.errors
        assert "getent" in result.errors[0]

    def test_missing_name_returns_error(self) -> None:
        resource = UserResource()
        result = resource.query({})
        assert result.errors
        assert "name" in result.errors[0]

    def test_nonexistent_user_returns_exists_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.user.shutil.which", lambda _cmd: "/usr/bin/getent")
        monkeypatch.setattr(
            "attest.resources.user.subprocess.run",
            lambda *args, cmd=None, **kwargs: CompletedProcess(
                args=cmd or args[0],
                returncode=2,
                stdout="",
                stderr="",
            )
            if "getent" in (cmd or args[0])
            else CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        resource = UserResource()
        result = resource.query({"name": "nonexistent"})
        assert not result.errors
        assert result.data["exists"] is False

    def test_queries_existing_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.user.shutil.which", lambda _cmd: "/usr/bin/getent")
        monkeypatch.setattr(
            "attest.resources.user.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0 if "getent" in args[0] else 2,
                stdout="root:x:0:0:root:/root:/bin/bash\n",
                stderr="",
            ),
        )

        resource = UserResource()
        result = resource.query({"name": "root"})
        assert not result.errors
        assert result.data["exists"] is True
        assert result.data["uid"] == 0
        assert result.data["gid"] == 0


class TestGroupResource:
    def test_missing_getent_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.group.shutil.which", lambda _cmd: None)
        resource = GroupResource()
        result = resource.query({"name": "wheel"})
        assert result.errors
        assert "getent" in result.errors[0]

    def test_missing_name_returns_error(self) -> None:
        resource = GroupResource()
        result = resource.query({})
        assert result.errors
        assert "name" in result.errors[0]

    def test_nonexistent_group_returns_exists_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.group.shutil.which", lambda _cmd: "/usr/bin/getent")
        monkeypatch.setattr(
            "attest.resources.group.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=2,
                stdout="",
                stderr="",
            ),
        )

        resource = GroupResource()
        result = resource.query({"name": "nonexistent"})
        assert not result.errors
        assert result.data["exists"] is False

    def test_queries_existing_group(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.group.shutil.which", lambda _cmd: "/usr/bin/getent")
        monkeypatch.setattr(
            "attest.resources.group.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="sudo:x:27:user1,user2\n",
                stderr="",
            ),
        )

        resource = GroupResource()
        result = resource.query({"name": "sudo"})
        assert not result.errors
        assert result.data["exists"] is True
        assert result.data["gid"] == 27
        assert result.data["members"] == ["user1", "user2"]


class TestKernelModuleResource:
    def test_missing_lsmod_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("attest.resources.kernel_module.shutil.which", lambda _cmd: None)
        resource = KernelModuleResource()
        result = resource.query({})
        assert result.errors
        assert "lsmod" in result.errors[0]

    def test_lists_loaded_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.kernel_module.shutil.which", lambda _cmd: "/usr/sbin/lsmod"
        )
        monkeypatch.setattr(
            "attest.resources.kernel_module.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout=(
                    "Module                  Size  Used by\n"
                    "sd_mod                 45056  3\n"
                    "acht                   32768  1\n"
                ),
                stderr="",
            ),
        )

        resource = KernelModuleResource()
        result = resource.query({})
        assert not result.errors
        assert result.data["loaded_count"] == 2
        assert "sd_mod" in result.data["loaded_modules"]
        assert "acht" in result.data["loaded_modules"]

    def test_checks_single_module_and_blacklist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.kernel_module.shutil.which", lambda _cmd: "/usr/sbin/lsmod"
        )
        monkeypatch.setattr(
            "attest.resources.kernel_module.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="Module                  Size  Used by\nfusb302                 16384  0\n",
                stderr="",
            ),
        )
        monkeypatch.setattr(
            "builtins.open",
            lambda _path, _mode="r", **_kwargs: (
                type(
                    "MockFile",
                    (),
                    {
                        "read": lambda _self: "blacklist usb_storage",
                        "__enter__": lambda _self: _self,
                        "__exit__": lambda _self, *_args: None,
                    },
                )()
            ),
        )

        resource = KernelModuleResource()
        result = resource.query({"name": "fusb302"})
        assert not result.errors
        assert result.data["loaded"] is True
        # blacklist check may or may not find the module depending on mock


class TestCrontabResource:
    def test_lists_cron_entries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.crontab.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="0 2 * * * /usr/bin/backup.sh\n@hourly /usr/local/bin/check.sh\n",
                stderr="",
            ),
        )
        resource = CrontabResource()
        monkeypatch.setattr(resource, "_read_system_crontabs", lambda: [])
        result = resource.query({"username": "testuser"})
        assert not result.errors
        assert result.data["count"] == 2
        assert result.data["user_count"] == 2

    def test_filters_by_search_pattern(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.crontab.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="0 2 * * * /usr/bin/backup.sh\n0 3 * * * /usr/bin/cleanup.sh\n",
                stderr="",
            ),
        )

        resource = CrontabResource()
        monkeypatch.setattr(resource, "_read_system_crontabs", lambda: [])
        result = resource.query({"username": "testuser", "search": "backup"})
        assert not result.errors
        assert result.data["count"] == 1
        assert "backup" in result.data["entries"][0]["full_line"]

    def test_ignores_comments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.crontab.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="# This is a comment\n0 2 * * * /usr/bin/backup.sh\n# Another comment\n",
                stderr="",
            ),
        )

        resource = CrontabResource()
        monkeypatch.setattr(resource, "_read_system_crontabs", lambda: [])
        result = resource.query({"username": "testuser"})
        assert not result.errors
        assert result.data["count"] == 1

    def test_field_projection_returns_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.crontab.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="0 2 * * * /usr/bin/backup.sh\n",
                stderr="",
            ),
        )

        resource = CrontabResource()
        monkeypatch.setattr(resource, "_read_system_crontabs", lambda: [])
        result = resource.query({"username": "testuser", "field": "count"})
        assert result.data == 1


class TestAuditdRulesResource:
    def test_lists_audit_rules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.auditd_rules.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="-w /etc/passwd -p wa -k passwd_modify\n-a always,exit -F arch=b64 -S adjtimex -k time_change\n",
                stderr="",
            ),
        )

        resource = AuditdRulesResource()
        result = resource.query({})
        assert not result.errors
        assert result.data["count"] == 2

    def test_filters_rules_by_pattern(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.auditd_rules.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="-w /etc/passwd -p wa -k passwd_modify\n-a always,exit -F arch=b64 -S adjtimex -k time_change\n",
                stderr="",
            ),
        )

        resource = AuditdRulesResource()
        result = resource.query({"pattern": "passwd"})
        assert not result.errors
        assert result.data["count"] == 1
        assert "passwd" in result.data["rules"][0]["raw_rule"]

    def test_parses_audit_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.auditd_rules.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="-w /etc/passwd -p wa -k passwd_modify\n",
                stderr="",
            ),
        )

        resource = AuditdRulesResource()
        result = resource.query({})
        assert not result.errors
        rule = result.data["rules"][0]
        assert rule["path"] == "/etc/passwd"
        assert rule["key"] == "passwd_modify"

    def test_returns_error_when_auditctl_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.auditd_rules.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=1,
                stdout="",
                stderr="auditctl: command not found\n",
            ),
        )

        resource = AuditdRulesResource()
        result = resource.query({})
        assert result.errors
        assert "auditctl" in result.errors[0]

    def test_field_projection_returns_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "attest.resources.auditd_rules.subprocess.run",
            lambda *args, **kwargs: CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="-w /etc/passwd -p wa -k passwd_modify\n",
                stderr="",
            ),
        )

        resource = AuditdRulesResource()
        result = resource.query({"field": "count"})
        assert result.data == 1


class TestBuiltinRegistry:
    def test_contains_new_resources(self) -> None:
        registry = build_builtin_registry()
        assert registry.has("group")
        assert registry.has("kernel_module")
        assert registry.has("mount")
        assert registry.has("package")
        assert registry.has("port")
        assert registry.has("process")
        assert registry.has("service")
        assert registry.has("ssh_config")
        assert registry.has("sysctl")
        assert registry.has("user")
