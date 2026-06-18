# Proxmox Selfhosted Homelab — Ansible
[![License](https://img.shields.io/github/license/Boris-Jancic/proxmox-homelab)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/Boris-Jancic/proxmox-homelab)](https://github.com/Boris-Jancic/proxmox-homelab/commits/main)
[![Ansible](https://img.shields.io/badge/Ansible-IaC-red?logo=ansible)](https://www.ansible.com/)
[![Proxmox](https://img.shields.io/badge/Proxmox-VE-orange?logo=proxmox)](https://www.proxmox.com/)
[![Docker](https://img.shields.io/badge/Docker-compose-blue?logo=docker)](https://www.docker.com/)
<img width="1261" height="449" alt="Screenshot_2026-05-26_15-53-23" src="https://github.com/user-attachments/assets/b81695c1-b942-479b-ae0b-6b604ce2599f" />
> Image is AI generated

Single-node Proxmox homelab (for now), fully managed as IaC with Ansible.
Replaces an earlier `init-all.sh` that grew unmanageable as services accumulated.

## Hardware

**Lenovo IdeaCentre 200-01IBW**

| Component | Specs |
|---|---|
| `CPU` | Intel i3-5005U (4) @ 1.900GHz |
| `Memory` | 12GB RAM |
| `Storage` | 128GB SSD + 1TB HDD |

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
         ├──▶  portainer      .110   container management UI
         └──▶  nextcloud-aio  .110   file sync + office (Ubuntu VM)

  [Proxmox PVE host]  —  CT/VM lifecycle via local API (127.0.0.1:8006)
```

External access via Cloudflare Zero Trust tunnel — no open ports on the router required.

## Services

<img width="1887" height="738" alt="image" src="https://github.com/user-attachments/assets/0c4a1f30-c3fc-429d-9383-dc7500d79f81" />

> Homepage dashboard

| Service | CT / VM | IP | Port | Docs |
|---|---|---|---|---|
| caddy | CT 100 | .100 | 80 (proxy) | [docs/caddy.md](docs/caddy.md) |
| pi-hole | CT 101 | .101 | 80 | [docs/pihole.md](docs/pihole.md) |
| vaultwarden | CT 102 | .102 | 8080 | [docs/vaultwarden.md](docs/vaultwarden.md) |
| uptime-kuma | CT 103 | .103 | 3001 | [docs/uptime-kuma.md](docs/uptime-kuma.md) |
| homepage | CT 104 | .104 | 3000 | [docs/homepage.md](docs/homepage.md) |
| portainer | VM 110 | .110 | 9000 | [docs/portainer.md](docs/portainer.md) |
| nextcloud-aio | VM 110 | .110 | 8080 / 11000 | [docs/nextcloud.md](docs/nextcloud.md) |

## Getting started

Ansible runs **directly on the PVE host**.

```bash
# 1. Set up venv and install deps
python3 -m venv ~/ansible-env && source ~/ansible-env/bin/activate
pip install ansible proxmoxer requests
ansible-galaxy collection install -r requirements.yml

# 2. Copy and fill in secrets
cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml

# 3. Adjust pve.ansible_host, CTIDs, and IPs in inventory.yml

# 4. Provision containers and VMs
ansible-playbook playbooks/provision-lxc.yml
ansible-playbook playbooks/provision-vms.yml

# 5. Configure each service
ansible-playbook playbooks/configure-<service>.yml
```

### Secrets

| Variable | Description |
|---|---|
| `proxmox_api_token_secret` | Proxmox API token UUID (`root@pam!ansible`) |
| `lxc_root_password` | Root password baked into new LXCs |
| `pihole_web_password` | Pi-hole admin UI password |
| `vaultwarden_admin_token` | Vaultwarden `/admin` token |
| `ubuntu_vm_password` | Ubuntu VM root password |
| `nextcloud_aio_password` | Nextcloud AIO admin passphrase |
| `cloudflare_tunnel_token` | Cloudflare Zero Trust tunnel token for the Caddy CT |

> **`secrets.yml` is gitignored.** Encrypt before storing anywhere: `ansible-vault encrypt group_vars/all/secrets.yml`. Append `--ask-vault-pass` to any playbook command when encrypted.

## Layout

```
ansible.cfg          Ansible config
inventory.yml        Hosts, CTIDs, per-host vars
group_vars/all/      main.yml (defaults), secrets.yml (gitignored)
playbooks/           provision-lxc, provision-vms, configure-<service>
roles/<service>/     defaults, tasks, templates, handlers
docs/                Per-service setup guides
```

## Adding a new service

1. Add host under `lxc_containers.hosts` in `inventory.yml` (`ctid`, `ansible_host`, `memory`, `disk`, `cores`). Tag `lxc_docker_host: true` if it runs Docker.
2. Run `provision-lxc.yml` to create the CT.
3. Copy `roles/pihole/` shape — `defaults/`, `tasks/main.yml` orchestrator, `tasks/install.yml` gated with `creates:`.
4. Add `playbooks/configure-<service>.yml` and a matching inventory group.

## Known limitations

- Pi-hole DNS upstreams set once at install via `setupVars.conf`, not reasserted on re-runs.
- No vault by default — `secrets.yml` is plain YAML. Use `ansible-vault encrypt` before pushing anywhere public.
- Vaultwarden `ADMIN_TOKEN` is plaintext in the rendered compose file (argon2 hash form preferred).
