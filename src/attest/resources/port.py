"""Port resource (REQ-2.2): query listening ports on Linux hosts."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class PortResource:
    """Query listening TCP and UDP ports with deterministic filtering."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        protocol = params.get("protocol")
        field = params.get("field")
        parsed_port = self._parse_port(params.get("port"))

        if parsed_port is None and params.get("port") is not None:
            return ResourceResult(
                data=None,
                errors=["'port' resource parameter 'port' must be an integer."],
                timings={},
            )

        if protocol is not None and protocol not in {"tcp", "udp"}:
            return ResourceResult(
                data=None,
                errors=["'port' resource parameter 'protocol' must be 'tcp' or 'udp'."],
                timings={},
            )

        if not shutil.which("ss"):
            return ResourceResult(
                data=None,
                errors=["'ss' command is not available on this host."],
                timings={},
            )

        completed = subprocess.run(
            ["ss", "-H", "-lntu"],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "port listing failed"
            return ResourceResult(data=None, errors=[stderr], timings={})

        listeners = self._parse_ss_output(completed.stdout)
        if protocol is not None:
            listeners = [listener for listener in listeners if listener["protocol"] == protocol]
        if parsed_port is not None:
            listeners = [listener for listener in listeners if listener["port"] == parsed_port]

        listeners.sort(
            key=lambda item: (str(item["protocol"]), int(item["port"]), str(item["address"]))
        )
        data = {
            "listening": bool(listeners),
            "count": len(listeners),
            "ports": [listener["port"] for listener in listeners],
            "listeners": listeners,
        }

        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})

    def _parse_port(self, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _parse_ss_output(self, output: str) -> list[dict[str, object]]:
        listeners: list[dict[str, object]] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split(None, 5)
            if len(parts) < 5:
                continue

            protocol = parts[0]
            state = parts[1]
            endpoint = parts[4]

            parsed_endpoint = self._parse_endpoint(endpoint)
            if parsed_endpoint is None:
                continue

            address, port = parsed_endpoint
            listeners.append(
                {
                    "protocol": protocol,
                    "state": state,
                    "address": address,
                    "port": port,
                }
            )
        return listeners

    def _parse_endpoint(self, endpoint: str) -> tuple[str, int] | None:
        cleaned = endpoint.strip()
        if not cleaned:
            return None

        if cleaned.startswith("[") and "]:" in cleaned:
            host_part, port_part = cleaned.rsplit(":", 1)
            address = host_part.strip("[]")
        elif ":" in cleaned:
            address, port_part = cleaned.rsplit(":", 1)
        else:
            return None

        if not port_part.isdigit():
            return None

        address = address.split("%", 1)[0]
        return (address, int(port_part))
