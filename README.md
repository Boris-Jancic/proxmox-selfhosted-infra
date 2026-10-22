# Proxmox Selfhosted Homelab — Ansible
[![License](https://img.shields.io/github/license/Boris-Jancic/proxmox-selfhosted-infra)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/Boris-Jancic/proxmox-selfhosted-infra)](https://github.com/Boris-Jancic/proxmox-selfhosted-infra/commits/main)
[![Ansible](https://img.shields.io/badge/Ansible-IaC-red?logo=ansible)](https://www.ansible.com/)
[![Proxmox](https://img.shields.io/badge/Proxmox-VE-orange?logo=proxmox)](https://www.proxmox.com/)
[![Docker](https://img.shields.io/badge/Docker-compose-blue?logo=docker)](https://www.docker.com/)
<img width="1261" height="449" alt="Screenshot_2026-05-26_15-53-23" src="https://github.com/user-attachments/assets/b81695c1-b942-479b-ae0b-6b604ce2599f" />
> Image is AI generated

Two-node Proxmox VE cluster (`skylab`), fully managed as IaC with Ansible.
Replaces an earlier `init-all.sh` that grew unmanageable as services accumulated.

## Cluster

| Node | IP | Role | Storage |
|---|---|---|---|
| `pve-brain` (primary) | .10 | Ansible controller, storage + edge: caddy, pi-hole, Nextcloud/Portainer VM, backups | `local-lvm` (SSD) + `data-hdd` (1TB HDD) |
| `pve-worker` | .20 | Compute: vaultwarden, uptime-kuma, homepage, k8s VMs | `local-lvm` (NVMe) |

| Hardware | pve-brain | pve-worker |
|---|---|---|
| Machine | Lenovo IdeaCentre 200-01IBW | HP t640 Thin Client |
| CPU | Intel i3-5005U (2C/4T) @ 1.9GHz | AMD Ryzen Embedded R1505G (2C/4T) |
| Memory | 12GB | 13GiB usable |
| Storage | 128GB SSD + 1TB HDD | 256GB NVMe (SK hynix BC711) |

Each guest's node is set by `pve_node` in `inventory.yml`. See [docs/proxmox-host.md](docs/proxmox-host.md).

## Network topology

```
  Internet
     │
     ▼
  Cloudflare (DNS + Zero Trust tunnel)
     │
     ▼
  [caddy .100]    ◀──  Cloudflare tunnel entry point (:80)
         │
         ├──▶  pi-hole        .101   DNS + network-wide ad-blocking
         ├──▶  vaultwarden    .102   self-hosted password manager
         ├──▶  uptime-kuma    .103   service uptime monitoring
         ├──▶  homepage       .104   unified service dashboard
         ├──▶  portainer      .110   container management UI (Ubuntu VM)
         ├──▶  blog           .110   Next.js blog, Portainer-managed stack
         ├──▶  nextcloud-aio  .110   file sync + office (Ubuntu VM)
         └──▶  proxmox UI     .10    cluster web UI

  [pve-brain]  —  runs Ansible; CT/VM lifecycle via local API (127.0.0.1:8006)
```

External access via Cloudflare Zero Trust tunnel — no open ports on the router required.

## Services

<img width="1887" height="738" alt="image" src="https://github.com/user-attachments/assets/0c4a1f30-c3fc-429d-9383-dc7500d79f81" />

> Homepage dashboard

| Service | CT / VM | Node | IP | Port | Docs |
|---|---|---|---|---|---|
| caddy + cloudflared | CT 100 | pve-brain | .100 | 80 (proxy) | [caddy](docs/caddy.md), [tunnel](docs/cloudflare-tunnel.md) |
| pi-hole | CT 101 | pve-brain | .101 | 80 | [pihole](docs/pihole.md) |
| vaultwarden | CT 102 | pve-worker | .102 | 8080 | [vaultwarden](docs/vaultwarden.md) |
| uptime-kuma | CT 103 | pve-worker | .103 | 3001 | [uptime-kuma](docs/uptime-kuma.md) |
| homepage | CT 104 | pve-worker | .104 | 3000 | [homepage](docs/homepage.md) |
| portainer | VM 110 | pve-brain | .110 | 9000 | [portainer](docs/portainer.md) |
| nextcloud-aio | VM 110 | pve-brain | .110 | 8080 / 11000 | [nextcloud](docs/nextcloud.md) |
| GitHub Actions runner | VM 110 | pve-brain | .110 | — | `roles/github_runner` |
| k8s master / worker | VM 120 / 130 | pve-worker | .120 / .130 | — | provisioned only, no configure role |
| proxmox nodes | — | both | .10 / .20 | 8006 | [proxmox-host](docs/proxmox-host.md) |

## Getting started

Ansible runs **directly on `pve-brain`**.

```bash
# 1. Install deps into system Python (lands in /usr/local/lib, leaves Proxmox's packages alone)
python3 -m pip install --break-system-packages ansible==12.3.0 ansible-core==2.19.9 proxmoxer==2.3.0
ansible-galaxy collection install -r requirements.yml

# 2. Copy and fill in secrets
cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml

# 3. Create the Proxmox API token (root@pam!ansible) and adjust nodes, CTIDs, IPs and pve_node in inventory.yml

# 4. Provision + configure everything in one run
ansible-playbook playbooks/site.yml

# ...or run the steps individually
ansible-playbook playbooks/provision-lxc.yml
ansible-playbook playbooks/provision-vms.yml
ansible-playbook playbooks/configure-proxmox-host.yml
ansible-playbook playbooks/configure-<service>.yml

# Subsets of site.yml
ansible-playbook playbooks/site.yml --tags configure
ansible-playbook playbooks/site.yml --tags caddy
```

### Secrets

| Variable | Description |
|---|---|
| `proxmox_api_token_secret` | Proxmox API token UUID (`root@pam!ansible`) |
| `proxmox_homepage_token_secret` | Proxmox token for the homepage widget (`root@pam!homepage`) |
| `portainer_api_key` | Portainer access token for the homepage widget |
| `github_pat` | GitHub PAT used to register the self-hosted runner |
| `lxc_root_password` | Root password baked into new LXCs |
| `pihole_web_password` | Pi-hole admin UI password |
| `vaultwarden_admin_token` | Vaultwarden `/admin` token |
| `ubuntu_vm_password` | Ubuntu VM root password |
| `nextcloud_aio_password` | Nextcloud AIO admin passphrase |
| `cloudflare_tunnel_token` | Cloudflare Zero Trust tunnel token for the Caddy CT |
| `cloudflare_api_token` | Optional Cloudflare API token (Tunnel: Read) for the homepage widget |

> **`secrets.yml` is gitignored.** Encrypt it: `ansible-vault encrypt group_vars/all/secrets.yml`, then append `--ask-vault-pass` to playbook commands.

### Secret scanning

- `pre-commit install` enables [gitleaks](https://github.com/gitleaks/gitleaks) (custom rules in `.gitleaks.toml`) and a hook that rejects any non-vaulted `secrets.yml` / `vault.yml`.
- `.github/workflows/secret-scan.yml` runs gitleaks on every push and PR.

## Layout

```
ansible.cfg          Ansible config
inventory.yml        Nodes, guests (ctid/id, pve_node), per-host vars, caddy_routes
group_vars/all/      main.yml (defaults), secrets.yml (gitignored), secrets.yml.example
playbooks/           site, provision-lxc, provision-vms, configure-<service>, configure-proxmox-host
roles/<service>/     defaults, tasks, templates, handlers, meta (docker dependency)
docs/                Per-service setup guides
.gitleaks.toml       Secret-scan rules (pre-commit + CI)
```

## Adding a new service

1. Add host under `lxc_containers.hosts` in `inventory.yml` (`ctid`, `ansible_host`, `memory`, `disk`, `cores`, `pve_node` if not pve-brain). Tag `lxc_docker_host: true` if it runs Docker.
2. Run `provision-lxc.yml` to create the CT.
3. Copy `roles/pihole/` shape — `defaults/`, `tasks/main.yml` orchestrator, `tasks/install.yml` gated with `creates:`. Docker services add `meta/main.yml` → `dependencies: [role: docker]`.
4. Add `playbooks/configure-<service>.yml`, a matching inventory group, and an entry in `playbooks/site.yml`.
5. Add a `caddy_routes` entry on the `caddy` host and re-run `configure-caddy.yml`.

## Known limitations

- Pi-hole DNS upstreams set once at install via `setupVars.conf`, not reasserted on re-runs.
- `secrets.yml` starts as plain YAML; the pre-commit hook only blocks committing it unencrypted.
- Vaultwarden `ADMIN_TOKEN` is plaintext in the rendered compose file (argon2 hash form preferred).
- Backups (`backups` storage) sit on the same HDD as VM 110: they cover mistakes, not disk failure.
- VMs 120/130 still run the `kvm64` CPU type; images needing x86-64-v2 fail there until changed.
