"""Built-in resource registry for bootstrap runtime."""

from __future__ import annotations

from attest.resources.command import CommandResource
from attest.resources.file import FileResource
from attest.resources.interfaces import ResourceRegistry
from attest.resources.os_facts import OsFactsResource
from attest.resources.package import PackageResource
from attest.resources.port import PortResource
from attest.resources.process import ProcessResource
from attest.resources.service import ServiceResource
from attest.resources.ssh_config import SshConfigResource
from attest.resources.sysctl import SysctlResource


def build_builtin_registry() -> ResourceRegistry:
    """Register built-in resource handlers available in the Python core."""
    registry = ResourceRegistry()
    registry.register("os_facts", OsFactsResource())
    registry.register("file", FileResource())
    registry.register("command", CommandResource())
    registry.register("package", PackageResource())
    registry.register("port", PortResource())
    registry.register("process", ProcessResource())
    registry.register("service", ServiceResource())
    registry.register("ssh_config", SshConfigResource())
    registry.register("sysctl", SysctlResource())
    return registry
