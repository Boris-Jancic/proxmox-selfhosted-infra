# Monitoring

Prometheus + Grafana + [pve-exporter](https://github.com/prometheus-pve/prometheus-pve-exporter) as one Docker Compose stack, plus `node_exporter` on both Proxmox nodes.

- **CT:** 105 | **Node:** pve-worker | **IP:** 192.168.88.105
- **Grafana:** `http://192.168.88.105:3000` (LAN only, no Caddy route)
- **Prometheus:** `http://192.168.88.105:9090` (LAN only, no auth)

## What is scraped

| Job | Target | Source |
|---|---|---|
| `node` | both nodes `:9100` | Debian `prometheus-node-exporter` (`roles/node_exporter`) |
| `pve` | pve-exporter → first node's API `:8006` | cluster-wide: nodes, guests, storage (`cluster=1`) |
| `prometheus` | itself | |

Dashboards are provisioned into the **Homelab** folder:

- **Proxmox cluster** (bundled, `roles/monitoring/files/dashboards/`): node/guest CPU, memory, network, storage and guest disk use.
- **Node Exporter Full** (rfmoz, pinned commit): per-node host detail.

## Prerequisites

1. Create the token: Datacenter → Permissions → API Tokens → Add, user `root@pam`, ID `prometheus`, privilege separation **on**.
2. Put its secret in `secrets.yml` as `proxmox_prometheus_token_secret`, and set `grafana_admin_password`.
3. Grant it PVEAuditor: `ansible-playbook playbooks/configure-proxmox-host.yml --tags tokens`.

## Deploy

```bash
ansible-playbook playbooks/provision-lxc.yml
ansible-playbook playbooks/configure-firewall.yml
ansible-playbook playbooks/configure-monitoring.yml
```

The firewall run opens 8006 (`api_clients`) and 9100 (`metrics_scrapers`) on the nodes to the monitoring CT, and 3000/9090 on the CT to the LAN.

## Variables

Defaults in `roles/monitoring/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `prometheus_image` | `prom/prometheus:v3.15.1` | Image tag |
| `grafana_image` | `grafana/grafana:13.2.6` | Image tag |
| `pve_exporter_image` | `prompve/prometheus-pve-exporter:3.11.0` | Image tag |
| `prometheus_retention_time` / `_size` | `30d` / `8GB` | TSDB retention, whichever hits first |
| `prometheus_scrape_interval` | `30s` | Global scrape interval |
| `pve_exporter_cluster_target` | first node in `proxmox_nodes` | Node whose API pve-exporter reads |

## Notes

- `grafana_admin_password` only applies when Grafana's DB is created. Change it later in the UI or with `docker exec grafana grafana cli admin reset-admin-password <pw>`.
- If the target node (pve-brain) is down, `pve` metrics stop; `node` metrics for the other node continue. Point `pve_exporter_cluster_target` at the surviving node if needed.
- Provisioned dashboards are read-only in the UI. Save a copy to edit, or change the JSON in the role.
- Data lives in `/opt/monitoring` on the CT.
