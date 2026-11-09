from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import requests

NODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")
PATH_RE = re.compile(r"^(/[A-Za-z0-9_.:@!=%-]+)+/?$")
ENCODED_SEP_RE = re.compile(r"%(2e|2f|5c)", re.IGNORECASE)
# GET endpoints that reach outside the cluster or open consoles, even read-only.
DENIED_PATH_RE = re.compile(r"(^|/)(scan|vncwebsocket|termproxy|spiceproxy|vncproxy)(/|$)|^/access/ticket")


class ProxmoxError(RuntimeError):
    pass


def check_node(node: str) -> str:
    if not NODE_RE.match(node):
        raise ProxmoxError(f"invalid node name: {node!r}")
    return node


def check_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if ".." in path or "//" in path or ENCODED_SEP_RE.search(path) or not PATH_RE.match(path):
        raise ProxmoxError(f"invalid API path: {path!r}")
    if DENIED_PATH_RE.search(path):
        raise ProxmoxError(f"path not allowed: {path!r}")
    return path.rstrip("/") or "/"


class ReadOnlyProxmox:
    """Proxmox VE API client that can only issue GET requests.

    The token should also be a PVEAuditor token with privilege separation on,
    so a bug here still cannot change anything.
    """

    def __init__(
        self,
        base_url: str,
        token_id: str | None,
        token_secret: str | None,
        verify: bool | str = True,
        timeout: float = 10,
        session: requests.Session | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token_id = token_id
        self._token_secret = token_secret
        self._verify = verify
        self._timeout = timeout
        self._session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self._token_id and self._token_secret)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.configured:
            raise ProxmoxError("PVE_TOKEN_ID / PVE_TOKEN_SECRET are not set")
        path = check_path(path)
        try:
            resp = self._session.request(
                "GET",
                self._base + path,
                params={k: v for k, v in (params or {}).items() if v is not None},
                headers={"Authorization": f"PVEAPIToken={self._token_id}={self._token_secret}"},
                verify=self._verify,
                timeout=self._timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise ProxmoxError(f"GET {path} failed: {type(exc).__name__}") from None
        if resp.status_code != 200:
            raise ProxmoxError(f"GET {path} -> HTTP {resp.status_code} {resp.reason}")
        return resp.json().get("data")

    def guest_ref(self, vmid: int) -> tuple[str, str]:
        """Return (node, type) for a VMID, type being 'qemu' or 'lxc'."""
        for res in self.get("/cluster/resources", {"type": "vm"}) or []:
            if int(res.get("vmid", -1)) == vmid:
                return res["node"], res["type"]
        raise ProxmoxError(f"guest {vmid} not found")

    @staticmethod
    def upid(upid: str) -> str:
        if not upid.startswith("UPID:") or "/" in upid:
            raise ProxmoxError(f"invalid UPID: {upid!r}")
        return quote(upid, safe="")
