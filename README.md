# Proxmox Selfhosted Homelab — Ansible
[![License](https://img.shields.io/github/license/Boris-Jancic/proxmox-homelab)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/Boris-Jancic/proxmox-homelab)](https://github.com/Boris-Jancic/proxmox-homelab/commits/main)
[![Ansible](https://img.shields.io/badge/Ansible-IaC-red?logo=ansible)](https://www.ansible.com/)
[![Proxmox](https://img.shields.io/badge/Proxmox-VE-orange?logo=proxmox)](https://www.proxmox.com/)
[![Docker](https://img.shields.io/badge/Docker-compose-blue?logo=docker)](https://www.docker.com/)
<img width="1261" height="449" alt="Screenshot_2026-05-26_15-53-23" src="https://github.com/user-attachments/assets/b81695c1-b942-479b-ae0b-6b604ce2599f" />
> Image is AI generated

Single-node Proxmox homelab (for now), fully managed as IaC with Ansible.
Runs the following services:
- self-hosted DNS ad-blocking (Pi-hole)
- password management (Vaultwarden)
- file sync (Nextcloud AIO)
- uptime monitoring (Uptime Kuma)
- service dashboard (Homepage)

Services are behind an nginx reverse proxy with TLS.
This project replaces an earlier `init-all.sh` that grew unmanageable as services accumulated.


## Hardware

The specific mini PC I am using now is the **Lenovo IdeaCentre 200-01IBW**
| Component | Specs |
|---|---|
| `Storage` | 128GB SSD + 1TB HDD |
| `CPU` | Intel i3-5005U (4) @ 1.900GHz |
| `Memory` | 12GB RAM |


## Network topology

```
                    LAN (192.168.88.0/24)

  [nginx-proxy .100]  ◀──  HTTPS entry point (80/443)
         │
         ├──▶  pi-hole        .101   DNS + network-wide ad-blocking
         ├──▶  vaultwarden    .102   self-hosted password manager
         ├──▶  uptime-kuma    .103   service uptime monitoring
         ├──▶  homepage       .104   unified service dashboard
         ├──▶  portainer      .110   container management UI
         └──▶  nextcloud-aio  .110   file sync + office (Ubuntu VM)

  [Proxmox PVE host]  —  CT/VM lifecycle via local API (127.0.0.1:8006)
```

All services are LAN-only by default. Point external DNS at nginx-proxy to expose selectively.

## Services
<img width="1887" height="738" alt="image" src="https://github.com/user-attachments/assets/0c4a1f30-c3fc-429d-9383-dc7500d79f81" />

> Homepage dashboard

| Role | CT | Port | Notes |
|---|---|---|---|
| pi-hole | pi-hole | 80 | v6+ only. Installs if missing, enforces web admin password. |
| vaultwarden | vaultwarden | 8080 | Docker compose. `ADMIN_TOKEN` from `secrets.yml`. |
| homepage | homepage | 3000 | Docker compose. Templates `settings/services/bookmarks/widgets.yaml` from inventory. |
| uptime-kuma | uptime-kuma | 3001 | Docker compose. First-run admin setup is browser-only. |
| portainer | ubuntu-vm1 (VM 110) | 9000 | Docker compose. CE edition. nginx-proxy terminates TLS, forwards to :9000. |
| nextcloud-aio | ubuntu-vm1 (VM 110) | 8080 (admin), 11000 (Nextcloud) | Docker compose. Ubuntu 24.04 VM. AIO mastercontainer spawns all sub-services. Passphrase printed by Ansible after deploy. |
| nginx-proxy | nginx-proxy | 80/443 | Bare-metal nginx. One vhost per `nginx_proxy_hosts` entry. Owns `sites-enabled/`. |

Service roles needing Docker pull `roles/docker/` via `meta/main.yml`
(Ansible deduplicates per play). The `docker` role supports both Debian
(LXCs) and Ubuntu (VMs) via `ansible_distribution | lower`.

## Layout

```
ansible.cfg, inventory.yml, requirements.yml
group_vars/all/{main.yml, secrets.yml.example}
playbooks/                  one per service + provision-lxc + bootstrap-existing-lxc-keys
roles/<service>/            defaults, tasks, templates, handlers
```

## Getting started

Ansible runs **on the PVE host itself**

### On the PVE host

1. `pip install --user ansible proxmoxer requests` (into venv — see CLAUDE.md)
2. `ansible-galaxy collection install -r requirements.yml`
3. Confirm an ed25519 key exists at `~/.ssh/id_ed25519.pub` — Ansible injects it into new LXCs at provision time. Override `controller_ssh_pubkey_path` in `group_vars/all/main.yml` for RSA.
4. Set `pve.ansible_host` and adjust LXC CTIDs / IPs in `inventory.yml`.
5. Copy and fill in secrets:

```bash
cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml
```

| Variable | Description |
|---|---|
| `proxmox_api_password` | `root@pam` password for Proxmox API |
| `lxc_root_password` | root password baked into new LXCs |
| `pihole_web_password` | Pi-hole admin UI password |
| `vaultwarden_admin_token` | Vaultwarden `/admin` token |
| `ubuntu_vm_password` | Ubuntu VM root password |
| `nextcloud_aio_password` | Nextcloud AIO admin passphrase |

> **`secrets.yml` is gitignored.** Encrypt before storing anywhere: `ansible-vault encrypt group_vars/all/secrets.yml`. Append `--ask-vault-pass` to any playbook command when encrypted.

## Workflows

```
ansible-playbook playbooks/1-provision-lxc.yml               # create + start LXCs
ansible-playbook playbooks/2-bootstrap-existing-lxc-keys.yml # one-time SSH retrofit
ansible-playbook playbooks/3-provision-vms.yml               # create Ubuntu VM + base config
ansible-playbook playbooks/configure-<service>.yml           # per-service install + configure
ansible-playbook playbooks/configure-nextcloud.yml           # Nextcloud AIO (prints passphrase)
```

`--check` doesn't work for `provision-lxc` — `community.general.proxmox`
skips itself in check mode. Run for real; existing CTs report `changed=0`.

### Service notes

- **pi-hole** — first run is slow (~5–10 min). Password idempotency keyed on
  marker file `/etc/pihole/.ansible_password_hash`.
- **vaultwarden** — first run, leave `vaultwarden_signups_allowed: "true"`,
  register the first account at `http://<ip>:8080/`, then flip to `"false"`
  and re-run.
- **homepage** — Ansible owns `settings.yaml` etc. Edit the templates under
  `roles/homepage/templates/`, not the rendered files on the CT.
- **uptime-kuma** — credentials live in sqlite; no env vars to template.
- **nextcloud-aio** — Ubuntu VM (110) provisioned via `3-provision-vms.yml`. After
  `configure-nextcloud.yml`, Ansible prints the AIO admin passphrase. Visit
  `https://192.168.88.110:8080` to complete setup. `NC_DOMAIN` pre-filled from
  `nextcloud_aio_domain`. `AIO_PASSWORD` sets passphrase from `secrets.yml`.

### nginx-proxy vhost schema

Set `nginx_proxy_hosts` on the `nginx-proxy` host in `inventory.yml`. Per
entry:

- `name`, `domain`, `destination` — required.
- `ssl: true` — terminate TLS locally; needs `ssl_cert` + `ssl_key`. Cert
  files must already exist (this role does **not** run certbot).
  Auto-generates `:80 → :443` redirect.
- `backend_ssl: true` — `proxy_ssl_verify off` + `proxy_ssl_server_name on`
  for self-signed upstreams (Proxmox 8006, Nextcloud-AIO admin :8080).
  Inferred automatically from `https://` in `destination`.
- `redirect_root_to: /admin/` — 301 from `/` to subpath (used for pi-hole).
- `extra_config` — raw nginx directives appended inside `location /`.

Defaults: `client_max_body_size 10G`, websocket upgrade headers,
`proxy_read_timeout 86400`. Anything in `sites-enabled/` not in the managed
list (including Debian's `default`) is removed.

## Docker-in-LXC: AppArmor override

Docker in an unprivileged LXC trips AppArmor at runc init. Fix:

```
lxc.apparmor.profile: unconfined
```

Automated — tag the host in `inventory.yml` with `lxc_docker_host: true`.
`1-provision-lxc.yml`'s second play writes the line into
`/etc/pve/lxc/<ctid>.conf` and reboots the CT if newly added.

Trade-off: AppArmor fully disabled inside the CT (I know this is bad but for a single node cluster I will take the punches untill I refactor this).
The narrower `lxc.sysctl.net.ipv4.ip_unprivileged_port_start = 0` was the previous
approach — replaced because newer Docker workloads kept hitting unrelated
AppArmor denials.

## Adding things

**New LXC:** add under `lxc_containers.hosts` with `ctid`, `ansible_host`,
`memory`, `disk`, `cores`. Sync to PVE, then run `1-provision-lxc.yml`.

**New service role:** copy `roles/pihole/` shape (defaults, tasks/main.yml
orchestrator, tasks/install.yml gated with `creates:`, templates). Add a
playbook in `playbooks/`, add the host to the right inventory group.

## Known limitations

- Pi-hole DNS upstreams set once via `setupVars.conf` at install, not reasserted.
- Pi-hole v5.x unsupported (assumes `pihole.toml`).
- Nextcloud-AIO first-run domain/storage setup is browser-only after Ansible deploy.
- No vault — `secrets.yml` is plain YAML. `ansible-vault encrypt` before
  pushing anywhere public.
- Vaultwarden `ADMIN_TOKEN` is plaintext in the rendered compose file
  (argon2 hash form preferred; not done).
- `community.general.proxmox` is deprecated in favor of `community.proxmox`;
  migration on the TODO.
