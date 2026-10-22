# Uptime Kuma

Self-hosted uptime monitoring with a web UI. Runs as a Docker Compose service.

- **CT:** 103 | **IP:** 192.168.88.103 | **Port:** 3001
- **Public URL:** `https://kuma.{{ cloudflare_zone }}` (via Caddy)

## Variables

Defaults in `roles/uptime-kuma/defaults/main.yml`. No secrets required.

| Variable | Default | Description |
|---|---|---|
| `uptime_kuma_image` | `louislam/uptime-kuma:2.3.2` | Docker image tag |
| `uptime_kuma_host_port` | `3001` | Host port |

## Deploy

```bash
ansible-playbook playbooks/configure-uptime-kuma.yml
```

## Notes

- CT must be tagged `lxc_docker_host: true` in `inventory.yml`.
- First visit creates the admin account — do this immediately after deploy.
- Data persists in `/opt/uptime-kuma/data` on the CT.
- Bump `uptime_kuma_image` deliberately; check releases at https://github.com/louislam/uptime-kuma/releases.
