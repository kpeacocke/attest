"""Built-in resource registry for bootstrap runtime."""

from __future__ import annotations

from attest.resources.auditd_rules import AuditdRulesResource
from attest.resources.command import CommandResource
from attest.resources.crontab import CrontabResource
from attest.resources.file import FileResource
from attest.resources.group import GroupResource
from attest.resources.ini_file import IniFileResource
from attest.resources.interfaces import ResourceRegistry
from attest.resources.json_file import JsonFileResource
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
from attest.resources.yaml_file import YamlFileResource


def build_builtin_registry() -> ResourceRegistry:
    """Register built-in resource handlers available in the Python core."""
    registry = ResourceRegistry()
    registry.register("os_facts", OsFactsResource())
    registry.register("file", FileResource())
    registry.register("ini_file", IniFileResource())
    registry.register("json_file", JsonFileResource())
    registry.register("yaml_file", YamlFileResource())
    registry.register("command", CommandResource())
    registry.register("auditd_rules", AuditdRulesResource())
    registry.register("crontab", CrontabResource())
    registry.register("group", GroupResource())
    registry.register("kernel_module", KernelModuleResource())
    registry.register("mount", MountResource())
    registry.register("package", PackageResource())
    registry.register("port", PortResource())
    registry.register("process", ProcessResource())
    registry.register("service", ServiceResource())
    registry.register("ssh_config", SshConfigResource())
    registry.register("sysctl", SysctlResource())
    registry.register("user", UserResource())
    return registry
