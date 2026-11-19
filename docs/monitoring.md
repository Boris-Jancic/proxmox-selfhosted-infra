# Monitoring

This document is written in ASD-STE100 Simplified Technical English.

## 1 General

The monitoring system collects data from the cluster, shows the data on dashboards and sends alerts to Telegram.

The system has these parts:

| Part | Location | Function |
|---|---|---|
| Prometheus | CT 105, port 9090 | Collects and keeps the metrics. Calculates the alert rules. |
| Alertmanager | CT 105, port 9093 | Sends the alerts to Telegram and to healthchecks.io. |
| Grafana | CT 105, port 3000 | Shows the dashboards. |
| pve-exporter | CT 105, internal | Reads the Proxmox API and gives metrics to Prometheus. |
| blackbox-exporter | CT 105, internal | Sends HTTP requests to the public websites. |

All parts are on CT 105. Ansible does not install software on the Proxmox nodes.

CT 105 (`monitoring`) is on pve-worker. Its IP address is 192.168.88.105. The parts on CT 105 run in one Docker Compose stack in `/opt/monitoring`.

Grafana, Prometheus and Alertmanager are available only on the LAN. They do not have a Caddy route. Prometheus and Alertmanager do not have a login.

## 2 Data collection

Prometheus collects data from these jobs each 30 seconds:

| Job | Target | Data |
|---|---|---|
| `pve` | pve-exporter, which reads the API of pve-brain | CPU, memory, disk, network and status of the nodes, guests and storage of the full cluster |
| `blackbox-http` | blackbox-exporter, which sends a request to each URL in `blackbox_http_targets` | Website status and response time |
| `prometheus` | Prometheus | Status of Prometheus |
| `alertmanager` | Alertmanager | Status of Alertmanager |

The `blackbox-http` request goes through Cloudflare, the tunnel and Caddy to the application. Thus, it finds a problem in each of these parts.

Prometheus keeps the data for 30 days or until the data is 8 GB. The first limit that the data gets to applies.

## 3 Dashboards

Grafana shows the **Proxmox cluster** dashboard in the **Homelab** folder. The dashboard shows CPU, memory, network and storage of the nodes and the guests. The JSON file is in `roles/monitoring/files/dashboards/`.

You cannot change this dashboard in Grafana. To change it, save a copy in Grafana, or change the JSON file in the role.

## 4 Alerts

### 4.1 Alert rules

The rules are in `roles/monitoring/templates/alert-rules.yml.j2`.

| Alert | Condition | Time before the alert starts | Severity |
|---|---|---|---|
| `WebsiteDown` | A URL in `blackbox_http_targets` does not send a 2xx response, has a TLS error or does not respond in 10 seconds. | 2 minutes | critical |
| `TargetDown` | Prometheus cannot read a target. | 2 minutes | critical |
| `PveNodeDown` | Proxmox shows that a node is offline. | 2 minutes | critical |
| `PveNodeHighMemory` | A node uses more than 90% of its memory. | 10 minutes | warning |
| `PveStorageFull` | A Proxmox storage is more than 85% full. The `local` storage of a node is on its root disk. | 10 minutes | warning |
| `PveGuestDiskFull` | The root disk of a CT is more than 85% full. | 10 minutes | warning |
| `Watchdog` | Always active. | 0 | none |

When `PveNodeDown` is active, Alertmanager does not send `TargetDown`. This alert is usually the result of the same problem.

To change the limits, change `alert_disk_used_ratio` and `alert_memory_used_ratio`.

### 4.2 Telegram messages

Alertmanager sends a message when an alert starts. It sends the message again each 4 hours while the alert stays active. It sends a "RESOLVED" message when the alert stops.

Each message shows:

- The severity: 🔴 critical, 🟠 warning, 🔵 info or ✅ resolved.
- The name of the alert.
- The summary of the alert. If the alert has no summary, the message shows the host or the URL.
- The start time in UTC. A "RESOLVED" message also shows the end time.
- Links to Grafana and Alertmanager. These links operate only on the LAN.

### 4.3 Watchdog

The `Watchdog` alert is always active. Alertmanager sends it each minute to the healthchecks.io URL in `alertmanager_healthchecks_url`.

If CT 105, Prometheus or Alertmanager stops, healthchecks.io does not get the signal. Then healthchecks.io sends an alert to you.

If `alertmanager_healthchecks_url` is empty, Alertmanager does not send the `Watchdog` alert.

## 5 Procedures

### 5.1 Make the Telegram bot

1. In Telegram, send `/newbot` to `@BotFather`.
2. Write down the token that `@BotFather` gives.
3. Open the chat with your bot.
4. Push **Start**.
5. Send a message to the bot.
6. On pve-brain, get the chat ID:

   ```bash
   curl -s "https://api.telegram.org/bot<token>/getUpdates" | python3 -c 'import sys,json;[print(u["message"]["chat"]["id"]) for u in json.load(sys.stdin)["result"] if "message" in u]'
   ```

7. Write down the chat ID. The chat ID of a group is a negative number.
8. Make sure that the bot can send a message to you:

   ```bash
   curl -s "https://api.telegram.org/bot<token>/sendMessage" -d chat_id=<id> -d text=test
   ```

NOTE: If `getUpdates` shows `"result":[]`, the bot did not get a message. Do step 3 to step 6 again. Do step 6 immediately after step 5.

NOTE: You can also get your user ID from `@userinfobot`. For a private chat, the user ID is the chat ID.

CAUTION: Do not put the bot token in chats, tickets or commits. If the token is visible to other persons, send `/revoke` to `@BotFather` and use the new token.

### 5.2 Prepare the secrets and the token

1. In the Proxmox GUI, go to **Datacenter → Permissions → API Tokens**.
2. Click **Add**.
3. Set **User** to `root@pam`, **Token ID** to `prometheus` and **Privilege Separation** to on.
4. Write down the token secret.
5. Add these values to `group_vars/all/secrets.yml`:

   | Variable | Value |
   |---|---|
   | `proxmox_prometheus_token_secret` | The token secret from step 4 |
   | `grafana_admin_password` | A strong password |
   | `alertmanager_telegram_bot_token` | The bot token from procedure 5.1 |
   | `alertmanager_telegram_chat_id` | The chat ID from procedure 5.1 |
   | `alertmanager_healthchecks_url` | Optional. The ping URL of a healthchecks.io check with a period of 1 minute and a grace time of 5 minutes. |

6. Give the read-only role to the token:

   ```bash
   ansible-playbook playbooks/platform/proxmox-host.yml --tags tokens </dev/null | cat
   ```

NOTE: The playbook stops with an error if the token does not exist. Do step 1 to step 4 first.

### 5.3 Deploy

Do these steps on pve-brain, in the repository directory.

1. Make CT 105:

   ```bash
   ansible-playbook playbooks/provision/lxc.yml </dev/null | cat
   ```

2. Apply the firewall rules:

   ```bash
   ansible-playbook playbooks/platform/firewall.yml </dev/null | cat
   ```

3. Install the monitoring stack:

   ```bash
   ansible-playbook playbooks/services/monitoring.yml </dev/null | cat
   ```

The firewall playbook opens these ports:

| Source | Destination | Port |
|---|---|---|
| CT 105 | Both nodes | 8006 (`api_clients`) |
| LAN | CT 105 | 3000, 9090, 9093 |

### 5.4 Do a test of the system

Do these steps on pve-brain.

1. Make sure that all targets are `up`:

   ```bash
   curl -s http://192.168.88.105:9090/api/v1/targets | python3 -c 'import sys,json;[print(t["labels"]["job"],t["labels"]["instance"],t["health"],t["lastError"]) for t in json.load(sys.stdin)["data"]["activeTargets"]]'
   ```

2. Make sure that only `Watchdog` is active:

   ```bash
   curl -s http://192.168.88.105:9090/api/v1/alerts | python3 -c 'import sys,json;[print(a["labels"]["alertname"],a["state"]) for a in json.load(sys.stdin)["data"]["alerts"]]'
   ```

3. Send a test alert:

   ```bash
   ssh root@192.168.88.105 'docker exec alertmanager amtool alert add Test severity=warning --annotation=summary="test" --alertmanager.url=http://localhost:9093'
   ```

4. Make sure that the Telegram message arrives in approximately 30 seconds.
5. Make sure that the "RESOLVED" message arrives in approximately 5 minutes.
6. Open `http://192.168.88.105:3000`. Log in as `admin` with `grafana_admin_password`.
7. Make sure that the dashboard in the **Homelab** folder shows data.

### 5.5 Add a website

1. Add the URL to `blackbox_http_targets` in `roles/monitoring/defaults/main.yml`.
2. Do step 3 of procedure 5.3.
3. Do step 1 of procedure 5.4.

### 5.6 Change the Grafana admin password

Grafana uses `grafana_admin_password` only when it makes its database for the first time. To change the password after that, do this step:

```bash
ssh root@192.168.88.105 'docker exec grafana grafana cli admin reset-admin-password <password>'
```

## 6 Troubleshooting

| Problem | Possible cause | Correction |
|---|---|---|
| `getUpdates` shows `"result":[]`. | The bot did not get a message, or the message is older than 24 hours. | Do step 3 to step 6 of procedure 5.1 again. |
| `docker exec` shows `No such container: alertmanager`. | You are on the wrong host, or the stack is not installed. | Use CT 105 (192.168.88.105). Do step 3 of procedure 5.3. |
| SSH shows `REMOTE HOST IDENTIFICATION HAS CHANGED`. | CT 105 is new and has a new host key. | Do procedure 6.1. |
| The `pve` target is `down` with a timeout. | The firewall rules are not applied. | Do step 2 of procedure 5.3. |
| A `pve` target is `down` with error 401 or 403. | The token does not exist or does not have the read-only role. | Do procedure 5.2. |
| Telegram shows `403 Forbidden: bot can't initiate conversation`. | You did not push **Start** in the chat with the bot. | Do step 3 and step 4 of procedure 5.1. |
| The `pve` metrics stop. | pve-brain is offline. | Set `pve_exporter_cluster_target` to the IP address of pve-worker. Do step 3 of procedure 5.3. |

### 6.1 Replace the host key of CT 105

1. Get the fingerprint of the key from the CT:

   ```bash
   ssh root@192.168.88.20 'pct exec 105 -- ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub'
   ```

2. Compare this fingerprint with the fingerprint in the SSH warning.

   WARNING: If the two fingerprints are not the same, do not continue. Another device can use the IP address.

3. Remove the old key:

   ```bash
   ssh-keygen -f /root/.ssh/known_hosts -R 192.168.88.105
   ```

4. Connect again and accept the new key:

   ```bash
   ssh -o StrictHostKeyChecking=accept-new root@192.168.88.105 true
   ```

## 7 Variables

The default values are in `roles/monitoring/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `prometheus_image` | `prom/prometheus:v3.15.1` | Prometheus image |
| `alertmanager_image` | `prom/alertmanager:v0.34.2` | Alertmanager image |
| `grafana_image` | `grafana/grafana:13.2.6` | Grafana image |
| `pve_exporter_image` | `prompve/prometheus-pve-exporter:3.11.0` | pve-exporter image |
| `blackbox_exporter_image` | `prom/blackbox-exporter:v0.29.0` | blackbox-exporter image |
| `prometheus_scrape_interval` | `30s` | Time between two data collections |
| `prometheus_retention_time` | `30d` | Maximum age of the data |
| `prometheus_retention_size` | `8GB` | Maximum size of the data |
| `alertmanager_repeat_interval` | `4h` | Time between two messages for the same active alert |
| `blackbox_http_targets` | `https://blog.<zone>` | Websites that blackbox-exporter checks |
| `pve_exporter_cluster_target` | First node in `proxmox_nodes` | Node whose API gives the cluster data |
| `alert_disk_used_ratio` | `0.85` | Disk limit for the disk alerts |
| `alert_memory_used_ratio` | `0.90` | Memory limit for `PveNodeHighMemory` |

NOTE: The images have a fixed version. Read the release notes before you change a version.
