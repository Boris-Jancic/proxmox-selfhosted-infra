# Cluster MCP server (read-only)

[MCP](https://modelcontextprotocol.io) server that gives an LLM agent (Claude Code, Claude Desktop, any MCP client) **read-only** access to the cluster: Proxmox API, Ansible inventory/facts and, when configured, Prometheus. Ask "why is VM 110 slow?" and the agent answers from live data. Code: `tools/cluster-mcp/`. Tracking issue: #42.

## Guardrails

| Layer | What it enforces |
|---|---|
| PVE token | `root@pam!mcp`, privilege separation on, `PVEAuditor` on `/`. Enforced by `roles/proxmox_host` (tag `tokens`). Cannot write even if the code had a bug. |
| HTTP client | `ReadOnlyProxmox` / `ReadOnlyPrometheus` only issue `GET`, no redirects. Paths are validated (no `..`, encoded separators) and console/scan/ticket endpoints are refused. |
| Tool surface | No write tools. Every tool carries `readOnlyHint: true`, `destructiveHint: false`; a test fails if a tool name contains a write verb. |
| Secrets | Token secret only from env. `secrets.yml`, `vault.yml` and any `$ANSIBLE_VAULT` file are never opened; secret-looking keys are redacted from vars, facts and guest configs. |
| Audit | Every tool call is logged as JSON (tool, redacted args, status, duration) to stderr and, optionally, `CLUSTER_MCP_AUDIT_LOG`. |

## Tools

| Tool | Source |
|---|---|
| `pve_cluster_status`, `pve_cluster_resources` | quorum, nodes, every guest/storage with live usage |
| `pve_node_status`, `pve_storage` | per-node CPU/mem/rootfs/kernel, storages |
| `pve_guest_status`, `pve_guest_config` | per-VMID; node + type resolved automatically |
| `pve_rrd` | historical CPU/mem/IO/pressure for a node or guest |
| `pve_tasks`, `pve_task_log` | recent tasks (backups, migrations), task logs |
| `pve_api_get` | any other GET under `/api2/json` |
| `ansible_inventory`, `ansible_host_vars` | `inventory.yml` + `group_vars` (unrendered Jinja) |
| `ansible_facts` | cached facts (needs `ANSIBLE_FACT_CACHE`) |
| `prom_query`, `prom_query_range`, `prom_alerts`, `prom_targets` | only when `PROMETHEUS_URL` is set |

## Setup (on pve-brain)

1. Create the token: Datacenter → Permissions → API Tokens → Add, user `root@pam`, token ID `mcp`, **privilege separation on**. Copy the secret.
2. Enforce the read-only ACL (also fails loudly if the token is missing):

   ```bash
   ansible-playbook playbooks/configure-proxmox-host.yml --limit pve --tags tokens
   ```

3. Install:

   ```bash
   python3 -m pip install --break-system-packages ./tools/cluster-mcp
   ```

4. Register it with Claude Code (user scope, so the secret stays out of the repo):

   ```bash
   claude mcp add skylab --scope user \
     -e PVE_TOKEN_ID='root@pam!mcp' \
     -e PVE_TOKEN_SECRET="$(cat ~/.config/cluster-mcp/token)" \
     -e CLUSTER_MCP_REPO="$PWD" \
     -e ANSIBLE_FACT_CACHE=~/.cache/ansible/facts \
     -- cluster-mcp
   ```

   Claude Desktop: same command and env under `mcpServers.skylab` in `claude_desktop_config.json`.

Facts are cached by `ansible.cfg` (`fact_caching = jsonfile`) on every play that gathers them.

## Environment

| Variable | Default | Description |
|---|---|---|
| `PVE_TOKEN_ID` | — | `root@pam!mcp` |
| `PVE_TOKEN_SECRET` | — | token secret, never committed |
| `PVE_HOST` / `PVE_PORT` | `127.0.0.1` / `8006` | API endpoint (or `PVE_URL` for the full `.../api2/json`) |
| `PVE_VERIFY_TLS` | `/etc/pve/pve-root-ca.pem` if present, else system CAs | `true`, `false` or a CA bundle path |
| `PROMETHEUS_URL` | unset (tools off) | e.g. `http://prometheus:9090` |
| `PROMETHEUS_VERIFY_TLS` | `true` | as above |
| `CLUSTER_MCP_REPO` | first parent of `$PWD` with `inventory.yml` | repo root for inventory tools (off if none found) |
| `ANSIBLE_FACT_CACHE` | unset | jsonfile fact cache directory |
| `CLUSTER_MCP_AUDIT_LOG` | unset | extra audit log file |
| `CLUSTER_MCP_TIMEOUT` | `10` | HTTP timeout, seconds |

## Development

```bash
cd tools/cluster-mcp
pip install -e '.[test]' ruff
ruff check . && ruff format --check . && pytest -q
```

Tests mock all HTTP and run against the real `inventory.yml`; CI runs them in `.github/workflows/cluster-mcp.yml`.
