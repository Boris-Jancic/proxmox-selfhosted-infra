from __future__ import annotations

from typing import Any

import requests

# Fixed, read-only Prometheus HTTP API endpoints. Admin endpoints are never reachable.
ENDPOINTS = {
    "query": "/api/v1/query",
    "query_range": "/api/v1/query_range",
    "alerts": "/api/v1/alerts",
    "targets": "/api/v1/targets",
    "rules": "/api/v1/rules",
}


class PrometheusError(RuntimeError):
    pass


class ReadOnlyPrometheus:
    def __init__(
        self,
        base_url: str,
        verify: bool | str = True,
        timeout: float = 10,
        session: requests.Session | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._verify = verify
        self._timeout = timeout
        self._session = session or requests.Session()

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        path = ENDPOINTS[endpoint]
        try:
            resp = self._session.request(
                "GET",
                self._base + path,
                params={k: v for k, v in (params or {}).items() if v is not None},
                verify=self._verify,
                timeout=self._timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise PrometheusError(f"GET {path} failed: {type(exc).__name__}") from None
        try:
            body = resp.json()
        except ValueError:
            raise PrometheusError(f"GET {path} -> HTTP {resp.status_code}, non-JSON body") from None
        if body.get("status") != "success":
            raise PrometheusError(f"GET {path} -> {body.get('errorType')}: {body.get('error')}")
        return body.get("data")
