# Nextcloud AIO

Nextcloud All-in-One runs the mastercontainer which spawns and manages all Nextcloud sub-containers (Apache, database, Redis, etc.).

- **VM:** 110 | **IP:** 192.168.88.110
- **AIO admin UI:** `https://192.168.88.110:8080` (direct, not via proxy)
- **Nextcloud:** `https://cloud.{{ cloudflare_zone }}` (via nginx-proxy → port 11000)

## Secrets

Set in `group_vars/all/secrets.yml`:

| Variable | Description |
|---|---|
| `nextcloud_aio_password` | AIO admin UI passphrase |

## Variables

Defaults in `roles/nextcloud-aio/defaults/main.yml`.

| Variable | Default | Description |
|---|---|---|
| `nextcloud_aio_image` | `nextcloud/all-in-one:latest` | Mastercontainer image |
| `nextcloud_aio_data_dir` | `/mnt/nextcloud-data` | Host path for all Nextcloud data |
| `nextcloud_aio_admin_port` | `8080` | AIO admin UI port |
| `nextcloud_aio_apache_port` | `11000` | Nextcloud Apache port (proxied by nginx) |
| `nextcloud_aio_domain` | `cloud.{{ cloudflare_zone }}` | Public Nextcloud domain |
| `nextcloud_aio_skip_domain_validation` | `true` | Skip AIO domain check (required for reverse-proxy setup) |

## Deploy

```bash
ansible-playbook playbooks/configure-nextcloud.yml
```

## First-run setup

After deploy, open the AIO admin UI directly:

```
https://192.168.88.110:8080
```

1. Log in with `nextcloud_aio_password`.
2. `NC_DOMAIN` is pre-filled from `nextcloud_aio_domain`.
3. **Set the correct Unix timezone** (e.g. `Europe/Berlin`) in the AIO UI before starting containers.
4. Start the containers from the AIO UI.
5. Wait for all containers to show green, then open `https://cloud.{{ cloudflare_zone }}`.

> Follow the official Nextcloud AIO reverse-proxy documentation for any additional configuration:
> https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md

## Notes

- VM must exist first — provision with `ansible-playbook playbooks/provision-vms.yml`.
- Data dir (`/mnt/nextcloud-data`) must exist on the VM before first run; the role does not create it.
- AIO spawns its own containers — do not manage them with `docker compose` directly.
- nginx-proxy needs two vhosts: `cloud.*` → port 11000 and `nextcloud.*` → port 8080 (with `backend_ssl: true`).
