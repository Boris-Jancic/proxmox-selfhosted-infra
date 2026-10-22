# Homepage

Self-hosted start page / service dashboard. Runs as a Docker Compose service.

- **CT:** 104 | **IP:** 192.168.88.104 | **Port:** 3000
- **Public URL:** `https://homepage.{{ cloudflare_zone }}` (via Caddy)

## Variables

Defaults in `roles/homepage/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `homepage_image` | `ghcr.io/gethomepage/homepage:v1.12.3` | Docker image tag |
| `homepage_host_port` | `3000` | Host port |
| `homepage_allowed_hosts` | `<ansible_host>:3000` | Allowed `Host` headers (v0.10+ requirement) |
| `portainer_env_id` | `2` | Portainer environment ID for the widget |
| `homepage_runner_repo` | `Boris-Jancic/nextjs-blog` | Repo whose runners page the GitHub runner card links to |

`homepage_allowed_hosts` is set per-host in `inventory.yml`. Include every name the browser may send:

```yaml
homepage_allowed_hosts: "homepage.yourdomain.com,192.168.88.104:3000"
```

## Layout

| Group | Cards |
|---|---|
| Infrastructure | one Proxmox widget per `proxmox_nodes` host, Pi-hole, Caddy (+ cloudflared) |
| Compute | Portainer (ubuntu-vm1), GitHub runner, every other VM in `virtual_machines` (k8s nodes) |
| Apps | Blog, Vaultwarden, Uptime Kuma, Nextcloud |
| Admin / Social | bookmarks; Admin links each node's PVE UI |

Guest cards carry `proxmoxNode`/`proxmoxVMID` from inventory, so they show the guest's CPU/RAM and follow `pve_node` after a migration. Credentials for that live in the rendered `proxmox.yaml` (one entry per node, secret via `HOMEPAGE_VAR_PROXMOX_PASSWORD`).

The `root@pam!homepage` token is read-only: privilege separation on, `PVEAuditor` on `/` (propagated). `roles/proxmox_host` enforces both (`ansible-playbook playbooks/configure-proxmox-host.yml --limit pve --tags tokens`); the secret is unchanged. Without the ACL node stats render as NaN and guest badges stay empty.

## Deploy

```bash
ansible-playbook playbooks/configure-homepage.yml
```

## Notes

- CT must be tagged `lxc_docker_host: true` in `inventory.yml`.
- Dashboard config (services, bookmarks, widgets) is managed via Jinja2 templates in `roles/homepage/templates/`. Edit those templates to customise the dashboard, then re-run the playbook.
- Config files land in `/opt/homepage/config` on the CT.
- Bump `homepage_image` deliberately; check releases at https://github.com/gethomepage/homepage/releases.
