import asyncio
import json
import re

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from cluster_mcp.inventory import Inventory
from cluster_mcp.prometheus import ReadOnlyPrometheus
from cluster_mcp.server import build_server

from .conftest import REPO_ROOT, FakeResponse, FakeSession

WRITE_VERBS = re.compile(
    r"(?i)(create|delete|destroy|remove|set|update|start|stop|shutdown|reboot|migrate|exec|write|put|post)"
)


@pytest.fixture
def prom_session():
    return FakeSession(
        {
            "/api/v1/query": FakeResponse(200, {"status": "success", "data": {"resultType": "vector", "result": []}}),
            "/api/v1/alerts": FakeResponse(200, {"status": "success", "data": {"alerts": []}}),
        }
    )


@pytest.fixture
def server(pve, prom_session):
    prom = ReadOnlyPrometheus("http://prom.test:9090", session=prom_session)
    return build_server(pve, Inventory(REPO_ROOT), prom)


def run(coro):
    return asyncio.run(coro)


def call(server, name, args=None):
    result = run(server.call_tool(name, args or {}))
    return json.loads(result.content[0].text)


def test_every_tool_is_read_only(server):
    tools = run(server.list_tools())
    assert len(tools) >= 15
    for t in tools:
        assert not WRITE_VERBS.search(t.name), t.name
        assert t.annotations.read_only_hint is True
        assert t.annotations.destructive_hint is False


def test_optional_toolsets_are_off_by_default(pve):
    names = {t.name for t in run(build_server(pve).list_tools())}
    assert not any(n.startswith(("prom_", "ansible_")) for n in names)
    assert "pve_cluster_resources" in names


def test_guest_status_resolves_node(server, session):
    session.routes["/nodes/pve-worker/lxc/103/status/current"] = {"status": "running", "mem": 1}
    assert call(server, "pve_guest_status", {"vmid": 103})["status"] == "running"
    assert all(c["method"] == "GET" for c in session.calls)


def test_guest_config_is_redacted(server, session):
    session.routes["/nodes/pve-brain/qemu/110/config"] = {"cores": 3, "cipassword": "**********"}
    cfg = call(server, "pve_guest_config", {"vmid": 110})
    assert cfg == {"cores": 3, "cipassword": "<redacted>"}


def test_rrd_needs_exactly_one_target(server):
    with pytest.raises(ToolError):
        run(server.call_tool("pve_rrd", {}))
    with pytest.raises(ToolError):
        run(server.call_tool("pve_rrd", {"node": "pve-brain", "vmid": 110}))


def test_api_get_refuses_console(server):
    with pytest.raises(ToolError, match="not allowed"):
        run(server.call_tool("pve_api_get", {"path": "/nodes/pve-brain/qemu/110/vncwebsocket"}))


def test_invalid_node_is_tool_error(server):
    with pytest.raises(ToolError, match="invalid node"):
        run(server.call_tool("pve_node_status", {"node": "../x"}))


def test_prometheus_query(server, prom_session):
    assert call(server, "prom_query", {"query": "up"})["resultType"] == "vector"
    assert prom_session.calls[0]["params"] == {"query": "up"}
    assert prom_session.calls[0]["method"] == "GET"


def test_tool_calls_are_audited(server, session, caplog):
    session.routes["/cluster/status"] = [{"type": "cluster", "name": "skylab", "quorate": 1}]
    with caplog.at_level("INFO", logger="cluster_mcp.audit"):
        call(server, "pve_cluster_status")
    entry = json.loads(caplog.records[-1].getMessage())
    assert entry["tool"] == "pve_cluster_status"
    assert entry["status"] == "ok"
