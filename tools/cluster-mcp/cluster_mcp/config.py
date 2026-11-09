from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PVE_CLUSTER_CA = Path("/etc/pve/pve-root-ca.pem")


def _verify(value: str | None, default: bool | str) -> bool | str:
    if value is None or value == "":
        return default
    if value.lower() in ("0", "false", "no", "off"):
        return False
    if value.lower() in ("1", "true", "yes", "on"):
        return True
    return value


def _find_repo(start: Path) -> Path | None:
    for d in (start, *start.parents):
        if (d / "inventory.yml").is_file() and (d / "group_vars").is_dir():
            return d
    return None


@dataclass(frozen=True)
class Config:
    pve_url: str
    pve_token_id: str | None
    pve_token_secret: str | None
    pve_verify: bool | str
    timeout: float
    prometheus_url: str | None
    prometheus_verify: bool | str
    repo_root: Path | None
    fact_cache: Path | None
    audit_log: Path | None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        e = os.environ if env is None else env
        host = e.get("PVE_HOST", "127.0.0.1")
        port = e.get("PVE_PORT", "8006")
        default_ca: bool | str = str(PVE_CLUSTER_CA) if PVE_CLUSTER_CA.is_file() else True
        repo = e.get("CLUSTER_MCP_REPO")
        cache = e.get("ANSIBLE_FACT_CACHE")
        audit = e.get("CLUSTER_MCP_AUDIT_LOG")
        return cls(
            pve_url=e.get("PVE_URL") or f"https://{host}:{port}/api2/json",
            pve_token_id=e.get("PVE_TOKEN_ID") or None,
            pve_token_secret=e.get("PVE_TOKEN_SECRET") or None,
            pve_verify=_verify(e.get("PVE_VERIFY_TLS"), default_ca),
            timeout=float(e.get("CLUSTER_MCP_TIMEOUT", "10")),
            prometheus_url=(e.get("PROMETHEUS_URL") or "").rstrip("/") or None,
            prometheus_verify=_verify(e.get("PROMETHEUS_VERIFY_TLS"), True),
            repo_root=Path(repo).expanduser() if repo else _find_repo(Path.cwd()),
            fact_cache=Path(cache).expanduser() if cache else None,
            audit_log=Path(audit).expanduser() if audit else None,
        )
