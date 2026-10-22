# Vaultwarden

Self-hosted Bitwarden-compatible password manager. Runs as a Docker Compose service.

- **CT:** 102 | **IP:** 192.168.88.102 | **Port:** 8080
- **Public URL:** `https://vaultwarden.{{ cloudflare_zone }}` (via Caddy)

## Secrets

Set in `group_vars/all/secrets.yml`:

| Variable | Description |
|---|---|
| `vaultwarden_admin_token` | Admin panel token (`/admin`) — use a strong random string |

## Variables

Defaults in `roles/vaultwarden/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `vaultwarden_image` | `vaultwarden/server:1.32.7` | Docker image tag |
| `vaultwarden_domain` | `https://vault.{{ cloudflare_zone }}` | Public HTTPS URL (must match browser URL for WebAuthn) |
| `vaultwarden_signups_allowed` | `true` | Allow new registrations |
| `vaultwarden_host_port` | `8080` | Host port |

## Deploy

```bash
# First run — allow registration
ansible-playbook playbooks/configure-vaultwarden.yml

# Register your account at https://vaultwarden.yourdomain, then lock it down
# Edit secrets.yml: vaultwarden_signups_allowed: "false"
ansible-playbook playbooks/configure-vaultwarden.yml
```

## Notes

- CT must be tagged `lxc_docker_host: true` in `inventory.yml` (sets AppArmor to `unconfined`).
- Bump `vaultwarden_image` deliberately — `latest` risks silent vault format upgrades.
- Data persists in `/opt/vaultwarden/data` on the CT.
