# Monitoring

Prometheus + Alertmanager + Grafana + blackbox-exporter + [pve-exporter](https://github.com/prometheus-pve/prometheus-pve-exporter) as one Docker Compose stack, plus `node_exporter` on both Proxmox nodes.

- **CT:** 105 | **Node:** pve-worker | **IP:** 192.168.88.105
- **Grafana:** `http://192.168.88.105:3000` (LAN only, no Caddy route)
- **Prometheus:** `http://192.168.88.105:9090` (LAN only, no auth)
- **Alertmanager:** `http://192.168.88.105:9093` (LAN only, no auth; silences)

## What is scraped

| Job | Target | Source |
|---|---|---|
| `node` | both nodes `:9100` | Debian `prometheus-node-exporter` (`roles/node_exporter`) |
| `pve` | pve-exporter → first node's API `:8006` | cluster-wide: nodes, guests, storage (`cluster=1`) |
| `pve-node` | pve-exporter → each node's API | per-node config, e.g. guest `onboot` (`node=1`) |
| `alertmanager` | itself | |
| `blackbox-http` | blackbox-exporter → each URL in `blackbox_http_targets` | public sites, probed end to end through Cloudflare |
| `prometheus` | itself | |

Dashboards are provisioned into the **Homelab** folder:

- **Proxmox cluster** (bundled, `roles/monitoring/files/dashboards/`): node/guest CPU, memory, network, storage and guest disk use.
- **Node Exporter Full** (rfmoz, pinned commit): per-node host detail.

## Alerts

Rules: `roles/monitoring/templates/alert-rules.yml.j2`. Alertmanager sends them to Telegram, repeating every 4h while firing, plus a resolved message.

| Alert | Fires when | For |
|---|---|---|
| `WebsiteDown` | a URL in `blackbox_http_targets` fails (non-2xx, TLS error, timeout 10s) | 2m |
| `WebsiteSlow` | a URL takes more than 5s to respond | 10m |
| `TargetDown` | any scrape target (node_exporter, pve-exporter, ...) unreachable | 2m |
| `PveNodeDown` | PVE reports a node offline (mutes `TargetDown` / `PveGuestStopped`) | 2m |
| `PveGuestStopped` | a guest with `onboot=1` is stopped | 5m |
| `PveStorageFull` / `PveGuestDiskFull` | PVE storage / CT root disk > 85% | 10m |
| `HostDiskFull` | node filesystem > 85% | 10m |
| `HostHighMemory` / `HostHighCpu` | node RAM / CPU > 90% | 10m |
| `Watchdog` | always; pings `alertmanager_healthchecks_url` every minute | — |

The Watchdog is a dead-man's switch: if the CT, Prometheus or Alertmanager dies, healthchecks.io stops getting pings and alerts you. Without the URL it is dropped.

Thresholds: `alert_disk_used_ratio`, `alert_memory_used_ratio`, `alert_cpu_used_ratio`.

### Telegram setup

1. In Telegram, message `@BotFather` → `/newbot` → copy the token.
2. Send your bot any message (or add it to a group and post there).
3. `curl -s https://api.telegram.org/bot<token>/getUpdates` → `message.chat.id` (negative for groups).
4. Put both in `secrets.yml` as `alertmanager_telegram_bot_token` / `alertmanager_telegram_chat_id`.
5. Optional: create a healthchecks.io check (period 1 min, grace 5 min) and set `alertmanager_healthchecks_url` to its ping URL.

Test after deploy: `docker exec alertmanager amtool alert add Test severity=warning --alertmanager.url=http://localhost:9093`.

## Prerequisites

1. Create the token: Datacenter → Permissions → API Tokens → Add, user `root@pam`, ID `prometheus`, privilege separation **on**.
2. Put its secret in `secrets.yml` as `proxmox_prometheus_token_secret`, set `grafana_admin_password` and the Telegram secrets (see above).
3. Grant it PVEAuditor: `ansible-playbook playbooks/configure-proxmox-host.yml --tags tokens`.

## Deploy

```bash
ansible-playbook playbooks/provision-lxc.yml
ansible-playbook playbooks/configure-firewall.yml
ansible-playbook playbooks/configure-monitoring.yml
```

The firewall run opens 8006 (`api_clients`) and 9100 (`metrics_scrapers`) on the nodes to the monitoring CT, and 3000/9090/9093 on the CT to the LAN.

## Variables

Defaults in `roles/monitoring/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `prometheus_image` | `prom/prometheus:v3.15.1` | Image tag |
| `grafana_image` | `grafana/grafana:13.2.6` | Image tag |
| `pve_exporter_image` | `prompve/prometheus-pve-exporter:3.11.0` | Image tag |
| `alertmanager_image` | `prom/alertmanager:v0.34.2` | Image tag |
| `alertmanager_repeat_interval` | `4h` | Re-notify interval while an alert fires |
| `blackbox_exporter_image` | `prom/blackbox-exporter:v0.29.0` | Image tag |
| `blackbox_http_targets` | `https://blog.<zone>` | Public URLs to probe |
| `prometheus_retention_time` / `_size` | `30d` / `8GB` | TSDB retention, whichever hits first |
| `prometheus_scrape_interval` | `30s` | Global scrape interval |
| `pve_exporter_cluster_target` | first node in `proxmox_nodes` | Node whose API pve-exporter reads |

## Notes

- `grafana_admin_password` only applies when Grafana's DB is created. Change it later in the UI or with `docker exec grafana grafana cli admin reset-admin-password <pw>`.
- If the target node (pve-brain) is down, `pve` metrics stop; `node` metrics for the other node continue. Point `pve_exporter_cluster_target` at the surviving node if needed.
- Provisioned dashboards are read-only in the UI. Save a copy to edit, or change the JSON in the role.
- Data lives in `/opt/monitoring` on the CT.
