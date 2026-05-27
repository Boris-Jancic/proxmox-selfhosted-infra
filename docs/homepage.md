# Homepage

Self-hosted start page / service dashboard. Runs as a Docker Compose service.

- **CT:** 104 | **IP:** 192.168.88.104 | **Port:** 3000
- **Public URL:** `https://homepage.{{ cloudflare_zone }}` (via nginx-proxy)

## Variables

Defaults in `roles/homepage/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `homepage_image` | `ghcr.io/gethomepage/homepage:v1.12.3` | Docker image tag |
| `homepage_host_port` | `3000` | Host port |
| `homepage_allowed_hosts` | `<ansible_host>:3000` | Allowed `Host` headers (v0.10+ requirement) |

`homepage_allowed_hosts` is set per-host in `inventory.yml`. Include every name the browser may send:

```yaml
homepage_allowed_hosts: "homepage.yourdomain.com,192.168.88.104:3000"
```

## Deploy

```bash
ansible-playbook playbooks/configure-homepage.yml
```

## Notes

- CT must be tagged `lxc_docker_host: true` in `inventory.yml`.
- Dashboard config (services, bookmarks, widgets) is managed via Jinja2 templates in `roles/homepage/templates/`. Edit those templates to customise the dashboard, then re-run the playbook.
- Config files land in `/opt/homepage/config` on the CT.
- Bump `homepage_image` deliberately; check releases at https://github.com/gethomepage/homepage/releases.
