from __future__ import annotations

import functools
import json
import logging
import sys
import time
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from .config import Config
from .inventory import Inventory, InventoryError
from .prometheus import PrometheusError, ReadOnlyPrometheus
from .proxmox import ProxmoxError, ReadOnlyProxmox, check_node
from .redact import redact

INSTRUCTIONS = """\
Read-only view of the `skylab` Proxmox VE cluster (nodes pve-brain, pve-worker),
its Ansible inventory and, when configured, Prometheus. No tool can change state:
to act on a finding, propose the Ansible playbook or command for a human to run.
Start with pve_cluster_resources for an overview; VMIDs map to inventory hosts via
`id`/`ctid` in ansible_host_vars."""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
KNOWN_ERRORS = (ProxmoxError, PrometheusError, InventoryError)

audit_log = logging.getLogger("cluster_mcp.audit")


def _audited(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        status = "ok"
        try:
            return fn(*args, **kwargs)
        except KNOWN_ERRORS as exc:
            status = "error"
            raise ToolError(str(exc)) from None
        except Exception:
            status = "error"
            raise
        finally:
            audit_log.info(
                json.dumps(
                    {
                        "tool": fn.__name__,
                        "args": redact(kwargs),
                        "status": status,
                        "ms": round((time.monotonic() - start) * 1000),
                    }
                )
            )

    return wrapper


def build_server(
    pve: ReadOnlyProxmox,
    inventory: Inventory | None = None,
    prometheus: ReadOnlyPrometheus | None = None,
) -> MCPServer:
    mcp = MCPServer("skylab-cluster", instructions=INSTRUCTIONS)

    def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
        mcp.tool(annotations=READ_ONLY)(_audited(fn))
        return fn

    def guest_path(vmid: int) -> str:
        node, kind = pve.guest_ref(vmid)
        return f"/nodes/{node}/{kind}/{vmid}"

    @tool
    def pve_cluster_status() -> Any:
        """Cluster membership and quorum: nodes, online state, quorate flag."""
        return pve.get("/cluster/status")

    @tool
    def pve_cluster_resources(type: Literal["vm", "node", "storage", "sdn"] | None = None) -> Any:
        """Every node, guest and storage with live CPU/mem/disk usage, status and node placement."""
        return pve.get("/cluster/resources", {"type": type})

    @tool
    def pve_node_status(node: str) -> Any:
        """Node details: CPU model/load, memory, swap, rootfs, kernel, PVE version, uptime."""
        return pve.get(f"/nodes/{check_node(node)}/status")

    @tool
    def pve_guest_status(vmid: int) -> Any:
        """Live status of a VM or CT: state, uptime, CPU, memory, disk and network I/O, HA state."""
        return pve.get(f"{guest_path(vmid)}/status/current")

    @tool
    def pve_guest_config(vmid: int) -> Any:
        """Configuration of a VM or CT (CPU type, cores, memory, disks, NICs). Secret fields are redacted."""
        return redact(pve.get(f"{guest_path(vmid)}/config"))

    @tool
    def pve_rrd(
        node: str | None = None,
        vmid: int | None = None,
        timeframe: Literal["hour", "day", "week", "month", "year"] = "hour",
        cf: Literal["AVERAGE", "MAX"] = "AVERAGE",
    ) -> Any:
        """Historical CPU/memory/disk/net/IO-pressure series for a node (node=) or guest (vmid=)."""
        if (node is None) == (vmid is None):
            raise ToolError("pass exactly one of node or vmid")
        base = guest_path(vmid) if vmid is not None else f"/nodes/{check_node(node or '')}"
        return pve.get(f"{base}/rrddata", {"timeframe": timeframe, "cf": cf})

    @tool
    def pve_storage(node: str) -> Any:
        """Storages on a node with type, content, total/used/avail bytes and active state."""
        return pve.get(f"/nodes/{check_node(node)}/storage")

    @tool
    def pve_tasks(node: str, limit: int = 20, errors_only: bool = False, vmid: int | None = None) -> Any:
        """Recent tasks on a node (backups, migrations, starts), newest first, with status."""
        params = {"limit": max(1, min(limit, 200)), "errors": int(errors_only), "vmid": vmid}
        return pve.get(f"/nodes/{check_node(node)}/tasks", params)

    @tool
    def pve_task_log(node: str, upid: str, limit: int = 200) -> Any:
        """Log lines of one task, by UPID from pve_tasks."""
        path = f"/nodes/{check_node(node)}/tasks/{pve.upid(upid)}/log"
        return pve.get(path, {"limit": max(1, min(limit, 2000))})

    @tool
    def pve_api_get(path: str) -> Any:
        """Any other read-only GET under /api2/json, e.g. /nodes/pve-brain/disks/list or /cluster/backup.
        Console, scan and ticket endpoints are refused."""
        return redact(pve.get(path))

    if inventory is not None:

        @tool
        def ansible_inventory() -> Any:
            """Ansible groups, children and hosts (with ansible_host) from inventory.yml."""
            return inventory.summary()

        @tool
        def ansible_host_vars(host: str) -> Any:
            """Merged group_vars + host vars for one inventory host, unrendered Jinja. Secrets are redacted."""
            return inventory.host(host)

        @tool
        def ansible_facts(host: str, keys: list[str] | None = None) -> Any:
            """Cached Ansible facts for a host (OS, kernel, CPU, memory, mounts, IPs).
            Pass keys (e.g. ["mounts", "default_ipv4"]) to pick specific facts."""
            return inventory.facts(host, keys)

    if prometheus is not None:

        @tool
        def prom_query(query: str, time: str | None = None) -> Any:
            """Instant PromQL query. time is RFC3339 or unix seconds; default now."""
            return prometheus.get("query", {"query": query, "time": time})

        @tool
        def prom_query_range(query: str, start: str, end: str, step: str = "60s") -> Any:
            """Range PromQL query. start/end are RFC3339 or unix seconds."""
            return prometheus.get("query_range", {"query": query, "start": start, "end": end, "step": step})

        @tool
        def prom_alerts() -> Any:
            """Currently pending and firing alerts."""
            return prometheus.get("alerts")

        @tool
        def prom_targets(state: Literal["active", "dropped", "any"] = "active") -> Any:
            """Scrape targets and their health (up/down, last error)."""
            return prometheus.get("targets", {"state": state})

    return mcp


def _setup_logging(cfg: Config) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if cfg.audit_log:
        cfg.audit_log.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(cfg.audit_log))
    fmt = logging.Formatter("%(asctime)s %(name)s %(message)s")
    for h in handlers:
        h.setFormatter(fmt)
        audit_log.addHandler(h)
    audit_log.setLevel(logging.INFO)
    audit_log.propagate = False


def main() -> None:
    cfg = Config.from_env()
    _setup_logging(cfg)
    pve = ReadOnlyProxmox(cfg.pve_url, cfg.pve_token_id, cfg.pve_token_secret, cfg.pve_verify, cfg.timeout)
    if not pve.configured:
        audit_log.warning("PVE_TOKEN_ID / PVE_TOKEN_SECRET not set: pve_* tools will fail")
    inventory = Inventory(cfg.repo_root, cfg.fact_cache) if cfg.repo_root else None
    prometheus = (
        ReadOnlyPrometheus(cfg.prometheus_url, cfg.prometheus_verify, cfg.timeout) if cfg.prometheus_url else None
    )
    build_server(pve, inventory, prometheus).run("stdio")


if __name__ == "__main__":
    main()
