from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .redact import redact

SECRET_FILE_RE = re.compile(r"(?i)(^|[._-])(secrets?|vault)([._-]|$)")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
FACT_SUMMARY = (
    "ansible_hostname",
    "ansible_distribution",
    "ansible_distribution_version",
    "ansible_kernel",
    "ansible_architecture",
    "ansible_virtualization_type",
    "ansible_virtualization_role",
    "ansible_processor_vcpus",
    "ansible_memtotal_mb",
    "ansible_memfree_mb",
    "ansible_swaptotal_mb",
    "ansible_uptime_seconds",
    "ansible_default_ipv4",
    "ansible_dns",
    "ansible_mounts",
    "ansible_date_time",
)


class InventoryError(RuntimeError):
    pass


class _SafeLoader(yaml.SafeLoader):
    pass


_SafeLoader.add_constructor("!vault", lambda loader, node: "<redacted>")
_SafeLoader.add_constructor("!unsafe", lambda loader, node: loader.construct_scalar(node))


def _is_vaulted(path: Path) -> bool:
    with path.open("rb") as fh:
        return fh.read(14) == b"$ANSIBLE_VAULT"


def _load_yaml(path: Path) -> Any:
    if SECRET_FILE_RE.search(path.name) or _is_vaulted(path):
        return None
    with path.open() as fh:
        return yaml.load(fh, Loader=_SafeLoader)


def _vars_dir(base: Path, name: str) -> dict[str, Any]:
    """Merge <base>/<name>.yml and <base>/<name>/*.yml, skipping secret/vault files."""
    merged: dict[str, Any] = {}
    candidates = [base / f"{name}.yml", base / f"{name}.yaml"]
    if (base / name).is_dir():
        candidates += sorted(p for p in (base / name).iterdir() if p.suffix in (".yml", ".yaml"))
    for path in candidates:
        if path.is_file():
            data = _load_yaml(path)
            if isinstance(data, dict):
                merged.update(data)
    return merged


class Inventory:
    """Static, read-only view of inventory.yml + group_vars/host_vars.

    Values are not Jinja-templated and secret files are never opened.
    """

    def __init__(self, repo_root: Path, fact_cache: Path | None = None) -> None:
        self.root = repo_root
        self.fact_cache = fact_cache
        inv = _load_yaml(repo_root / "inventory.yml") or {}
        self.groups: dict[str, set[str]] = {}
        self.children: dict[str, list[str]] = {}
        self.group_vars: dict[str, dict[str, Any]] = {}
        self.host_vars: dict[str, dict[str, Any]] = {}
        self.host_groups: dict[str, list[str]] = {}
        self._walk("all", inv.get("all") or {}, ["all"])

    def _walk(self, name: str, node: dict[str, Any], chain: list[str]) -> None:
        self.groups.setdefault(name, set())
        self.group_vars.setdefault(name, {}).update(node.get("vars") or {})
        for host, hvars in (node.get("hosts") or {}).items():
            self.host_vars.setdefault(host, {}).update(hvars or {})
            for g in chain:
                self.groups.setdefault(g, set()).add(host)
            groups = self.host_groups.setdefault(host, [])
            groups += [g for g in chain if g not in groups]
        for child, child_node in (node.get("children") or {}).items():
            self.children.setdefault(name, []).append(child)
            self._walk(child, child_node or {}, [*chain, child])

    def summary(self) -> dict[str, Any]:
        return {
            "groups": {g: sorted(h) for g, h in sorted(self.groups.items())},
            "children": self.children,
            "hosts": {
                h: {"ansible_host": v.get("ansible_host"), "groups": self.host_groups[h]}
                for h, v in sorted(self.host_vars.items())
            },
        }

    def host(self, host: str) -> dict[str, Any]:
        if host not in self.host_vars:
            raise InventoryError(f"unknown host: {host!r}")
        merged: dict[str, Any] = {}
        for g in self.host_groups[host]:
            merged.update(_vars_dir(self.root / "group_vars", g))
            merged.update(self.group_vars.get(g, {}))
        merged.update(_vars_dir(self.root / "host_vars", host))
        merged.update(self.host_vars[host])
        return {"host": host, "groups": self.host_groups[host], "vars": redact(merged)}

    def facts(self, host: str, keys: list[str] | None = None) -> dict[str, Any]:
        if self.fact_cache is None:
            raise InventoryError("ANSIBLE_FACT_CACHE is not set (see fact_caching in ansible.cfg)")
        if not HOST_RE.match(host) or host not in self.host_vars:
            raise InventoryError(f"unknown host: {host!r}")
        path = self.fact_cache / host
        if not path.is_file():
            raise InventoryError(f"no cached facts for {host}; run any play against it first")
        facts = json.loads(path.read_text())
        wanted = keys or list(FACT_SUMMARY)
        out = {}
        for k in wanted:
            bare = k.removeprefix("ansible_")
            for key in (f"ansible_{bare}", bare):
                if key in facts:
                    out[f"ansible_{bare}"] = facts[key]
                    break
        return {"host": host, "cached_at": path.stat().st_mtime, "facts": redact(out)}
