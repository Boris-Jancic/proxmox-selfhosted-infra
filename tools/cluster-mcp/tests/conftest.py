from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cluster_mcp.proxmox import ReadOnlyProxmox

REPO_ROOT = Path(__file__).resolve().parents[3]

RESOURCES = [
    {"type": "node", "node": "pve-brain", "status": "online"},
    {"type": "qemu", "vmid": 110, "node": "pve-brain", "name": "ubuntu-vm1", "status": "running"},
    {"type": "lxc", "vmid": 103, "node": "pve-worker", "name": "uptime-kuma", "status": "running"},
]


class FakeResponse:
    def __init__(self, status: int, body: Any) -> None:
        self.status_code = status
        self.reason = "OK" if status == 200 else "ERR"
        self._body = body

    def json(self) -> Any:
        return self._body


class FakeSession:
    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self.routes = routes or {}
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        for suffix, body in self.routes.items():
            if url.endswith(suffix):
                return body if isinstance(body, FakeResponse) else FakeResponse(200, {"data": body})
        return FakeResponse(404, {"data": None})


@pytest.fixture
def session() -> FakeSession:
    return FakeSession({"/cluster/resources": RESOURCES})


@pytest.fixture
def pve(session: FakeSession) -> ReadOnlyProxmox:
    return ReadOnlyProxmox("https://pve.test:8006/api2/json", "root@pam!mcp", "s3cr3t", session=session)
