# Pi-hole

Network-wide DNS-based ad blocker. Installed bare (no Docker) via the official unattended installer.

- **CT:** 101 | **IP:** 192.168.88.101 | **Port:** 80 (admin at `/admin/`)

## Secrets

Set in `group_vars/all/secrets.yml`:

| Variable | Description |
|---|---|
| `pihole_web_password` | Web admin UI password |

## Variables

Defaults in `roles/pihole/defaults/main.yml`. Override in `inventory.yml` or `group_vars`.

| Variable | Default | Description |
|---|---|---|
| `pihole_dns_upstreams` | `[1.1.1.1, 1.0.0.1, gateway]` | Upstream DNS servers |
| `pihole_query_logging` | `true` | Log DNS queries |
| `pihole_blocking_enabled` | `true` | Enable ad blocking |
| `pihole_dhcp_active` | `false` | Enable DHCP server |
| `pihole_cache_size` | `10000` | DNS cache entries |

## Deploy

```bash
ansible-playbook playbooks/configure-pihole.yml
```

## Notes

- Installer runs only once (`creates: /usr/local/bin/pihole`). To reinstall, remove that binary first.
- Password idempotency keyed on `/etc/pihole/.ansible_password_hash`. Delete to force re-sync.
- Point router DNS at `192.168.88.101` after first successful deploy.
