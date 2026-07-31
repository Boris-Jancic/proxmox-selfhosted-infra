# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

Ansible runs **directly on the Proxmox host** (not a remote workstation). It is installed via pip into the system Python (`ansible-core` + `proxmoxer` + `requests` in `/usr/local/lib/python3.11/dist-packages`), so `ansible-playbook` is on `PATH` — no venv to activate. (An earlier setup used `~/ansible-env`; that venv no longer exists.)

Proxmox API is reached at `127.0.0.1:8006` (loopback). API auth uses **token** (`root@pam!ansible` + `proxmox_api_token_secret` from `secrets.yml`). Token ID is set in `group_vars/all/main.yml` as `proxmox_api_token_id`.

## Common commands

```bash
# Provision + configure everything (full homelab bring-up)
ansible-playbook playbooks/site.yml

# Only configure plays (skip provisioning); per-service: --tags caddy, --tags pihole, ...
ansible-playbook playbooks/site.yml --tags configure

# Provision / start all LXC containers
ansible-playbook playbooks/provision-lxc.yml

# Provision Ubuntu VMs (downloads cloud image, creates VM, cloud-init, waits for SSH)
ansible-playbook playbooks/provision-vms.yml

# Configure a single service
ansible-playbook playbooks/configure-<service>.yml

# Dry-run (works for configure plays, not provision-lxc)
ansible-playbook playbooks/configure-<service>.yml --check

# Run only specific tasks by tag
ansible-playbook playbooks/configure-<service>.yml --tags install

# Limit to one host
ansible-playbook playbooks/configure-caddy.yml --limit caddy
```

If `secrets.yml` is vault-encrypted, append `--ask-vault-pass` to any command above.

## Architecture

Two distinct play types — never mix them:

1. **Provision** (`provision-lxc.yml`) — talks to Proxmox API via `community.proxmox.proxmox` (localhost connection). Creates LXCs, injects SSH key, and writes `lxc.apparmor.profile: unconfined` into `/etc/pve/lxc/<ctid>.conf` for hosts tagged `lxc_docker_host: true`.

2. **Configure** (`configure-*.yml`) — SSHes into the target LXC or the PVE host, runs a single named role.

### Role shape

All roles follow `roles/pihole/` as the canonical example:
- `defaults/main.yml` — all tunables with defaults
- `tasks/main.yml` — thin orchestrator (`include_tasks`)
- `tasks/install.yml` — gated with `creates:` or `when:` so re-runs are cheap
- `templates/` — Jinja2 configs
- `handlers/main.yml` — service reload/restart

Roles that need Docker declare `meta/main.yml` → `dependencies: [role: docker]`. Ansible deduplicates per play, so Docker is installed exactly once even if multiple roles depend on it.

### Secrets & variables

- `group_vars/all/main.yml` — non-secret defaults (IPs, template VMID, `cloudflare_zone`)
- `group_vars/all/secrets.yml` — gitignored; copy from `secrets.yml.example` and fill in
- Per-host variables (e.g. `caddy_routes`, `homepage_allowed_hosts`) live directly on the host entry in `inventory.yml`
- `cloudflare_zone` is defined once in `main.yml`; domains throughout `inventory.yml` reference it as `"subdomain.{{ cloudflare_zone }}"`

### Service map

| Host (CT) | IP | Runtime | Port |
|---|---|---|---|
| caddy (100) | .100 | caddy binary + cloudflared | 80 |
| pi-hole (101) | .101 | bare pihole | 80 |
| vaultwarden (102) | .102 | Docker compose | 8080 |
| uptime-kuma (103) | .103 | Docker compose | 3001 |
| homepage (104) | .104 | Docker compose | 3000 |
| ubuntu-vm1 (VM 110) | .110 | Docker compose (AIO) | 8080 (admin), 11000 (Nextcloud) |

## Known gotchas

- **`--check` fails for `provision-lxc.yml`** — `community.proxmox` skips itself in check mode. Run for real; existing CTs return `changed=0`.
- **New LXC may have empty `/etc/resolv.conf`** — set nameserver via Proxmox GUI before the configure play runs.
- **IPv6 hangs `apt`** — add `Acquire::ForceIPv4 "true"` to `/etc/apt/apt.conf.d/99force-ipv4` if apt stalls in a new CT.
- **`proxmoxer` + `requests` must be importable by the same Python that runs Ansible** (`/usr/bin/python3`) — missing them causes cryptic import errors from the Proxmox module. Both live in `/usr/local/lib/python3.11/dist-packages`.
- **pip installs go to `/usr/local/lib`, not Proxmox's own packages** — Debian-managed packages in `/usr/lib/python3/dist-packages` (including Proxmox's) are never overwritten by pip; don't force `--target` or `--break-system-packages` into `/usr/lib`.
- **Caddy is the reverse proxy** — `caddy_routes` on the `caddy` host in `inventory.yml` renders the full Caddyfile; routes serve plain HTTP on `:80` (`http://` site addresses, `auto_https off`) because Cloudflare terminates TLS at the tunnel. The co-located `cloudflared` tunnel dials `localhost:80`.
- **`https://` upstreams need no extra flag** — the Caddyfile template auto-adds `tls_insecure_skip_verify` when `destination` starts with `https://` (covers Proxmox + Nextcloud self-signed certs); override with `backend_ssl: true` otherwise.
- **Pi-hole password idempotency** keyed on marker file `/etc/pihole/.ansible_password_hash` — delete it to force a re-sync.
- **Vaultwarden**: first run needs `vaultwarden_signups_allowed: "true"` to register the first account, then flip to `"false"` and re-run.
- **Nextcloud AIO first run**: after `configure-nextcloud.yml`, visit `https://192.168.88.110:8080` to complete setup in the AIO admin UI. `NC_DOMAIN` is pre-filled from `nextcloud_aio_domain`. `SKIP_DOMAIN_VALIDATION` is set so the reverse-proxy setup doesn't block init.
- **docker role supports both Debian and Ubuntu** — repo URL uses `{{ ansible_distribution | lower }}` so the same role works for LXCs (Debian) and the Ubuntu VM.

## Adding a new service

1. Add a host entry under `lxc_containers.hosts` in `inventory.yml` (ctid, ansible_host, memory, disk, cores). Tag `lxc_docker_host: true` if it runs Docker.
2. Run `provision-lxc.yml` to create the CT.
3. Copy `roles/pihole/` shape; add `tasks/install.yml` gated with `creates:` for idempotency.
4. Add `playbooks/configure-<service>.yml` targeting the new inventory group.
5. Add a matching inventory group under `children:`.
6. Add a `caddy_routes` entry on the `caddy` host in `inventory.yml`, then re-run `configure-caddy.yml`.
