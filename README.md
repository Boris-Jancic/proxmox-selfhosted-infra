# Proxmox Selfhosted Infrastructure
[![License](https://img.shields.io/github/license/Boris-Jancic/proxmox-selfhosted-infra)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/Boris-Jancic/proxmox-selfhosted-infra)](https://github.com/Boris-Jancic/proxmox-selfhosted-infra/commits/main)
[![Ansible](https://img.shields.io/badge/Ansible-IaC-red?logo=ansible)](https://www.ansible.com/)
[![Proxmox](https://img.shields.io/badge/Proxmox-VE-orange?logo=proxmox)](https://www.proxmox.com/)
[![Docker](https://img.shields.io/badge/Docker-compose-blue?logo=docker)](https://www.docker.com/)
<img width="1261" height="449" alt="Screenshot_2026-05-26_15-53-23" src="https://github.com/user-attachments/assets/b81695c1-b942-479b-ae0b-6b604ce2599f" />

This repository uses Ansible to manage a two-node Proxmox VE cluster (`skylab`). All configuration is code.

## Cluster

| Node | IP | Role | Storage |
|---|---|---|---|
| `pve-brain` (primary) | .10 | Ansible controller, storage and edge: caddy, pi-hole, Nextcloud/Portainer VM, backups | `local-lvm` (SSD) + `data-hdd` (1TB HDD) |
| `pve-worker` | .20 | Compute: vaultwarden, uptime-kuma, homepage, k8s VMs | `local-lvm` (NVMe) |

| Hardware | pve-brain | pve-worker |
|---|---|---|
| Machine | Lenovo IdeaCentre 200-01IBW | HP t640 Thin Client |
| CPU | Intel i3-5005U (2C/4T) @ 1.9GHz | AMD Ryzen Embedded R1505G (2C/4T) |
| Memory | 12GB | 13GiB usable |
| Storage | 128GB SSD + 1TB HDD | 256GB NVMe (SK hynix BC711) |

The `pve_node` value in `inventory.yml` sets the node of each guest. Refer to [docs/proxmox-host.md](docs/proxmox-host.md).

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
         ├──▶  pi-hole        .101   DNS and ad blocking for the network
         ├──▶  vaultwarden    .102   password manager
         ├──▶  uptime-kuma    .103   uptime monitoring
         ├──▶  homepage       .104   service dashboard
         ├──▶  blog           .110   Next.js blog, Portainer stack
         ├──▶  nextcloud-aio  .110   file sync and office (Ubuntu VM)
         └──▶  proxmox UI     .10    cluster web UI

  LAN only (192.168.88.0/24): portainer .110:9000/9443

  [pve-brain]: runs Ansible, manages CTs and VMs through the local API (127.0.0.1:8006)
```

External access goes through a Cloudflare Zero Trust tunnel. The router has no open ports.

The Proxmox firewall drops all inbound traffic by default:

- Apps accept traffic only from Caddy, the monitors and the nodes.
- The Proxmox GUI is available only through the tunnel.
- Portainer is available only on the LAN.

For the diagram and the rules, refer to [docs/firewall.md](docs/firewall.md). For quorum, refer to [docs/qdevice.md](docs/qdevice.md).

## Services

<img width="1887" height="738" alt="image" src="https://github.com/user-attachments/assets/0c4a1f30-c3fc-429d-9383-dc7500d79f81" />

> Homepage dashboard

| Service | CT / VM | Node | IP | Port | Docs |
|---|---|---|---|---|---|
| caddy + cloudflared | CT 100 | pve-brain | .100 | 80 (proxy) | [caddy](docs/caddy.md), [tunnel](docs/cloudflare-tunnel.md) |
| pi-hole | CT 101 | pve-brain | .101 | 53, 80 | [pihole](docs/pihole.md) |
| vaultwarden | CT 102 | pve-worker | .102 | 8080 | [vaultwarden](docs/vaultwarden.md) |
| uptime-kuma | CT 103 | pve-worker | .103 | 3001 | [uptime-kuma](docs/uptime-kuma.md) |
| homepage | CT 104 | pve-worker | .104 | 3000 | [homepage](docs/homepage.md) |
| portainer | VM 110 | pve-brain | .110 | 9000, 9443 (LAN only) | [portainer](docs/portainer.md) |
| nextcloud-aio | VM 110 | pve-brain | .110 | 8080 / 11000 | [nextcloud](docs/nextcloud.md) |
| GitHub Actions runner | VM 110 | pve-brain | .110 | None | `roles/github_runner` |
| k8s master / worker | VM 120 / 130 | pve-worker | .120 / .130 | None | Provisioned only. No configure role. |
| proxmox nodes | None | both | .10 / .20 | 8006 | [proxmox-host](docs/proxmox-host.md), [firewall](docs/firewall.md) |

## Getting started

Ansible runs **directly on `pve-brain`**.

```bash
# 1. Install the dependencies into the system Python.
#    pip writes to /usr/local/lib. It does not change the Proxmox packages.
python3 -m pip install --break-system-packages ansible==12.3.0 ansible-core==2.19.9 proxmoxer==2.3.0
ansible-galaxy collection install -r requirements.yml

# 2. Copy the secrets file. Then fill in the values.
cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml

# 3. Create the Proxmox API token (root@pam!ansible).
#    Set the nodes, CTIDs, IPs and pve_node in inventory.yml.

# 4. Provision and configure all hosts.
ansible-playbook playbooks/site.yml

# Or run each step.
ansible-playbook playbooks/provision-lxc.yml
ansible-playbook playbooks/provision-vms.yml
ansible-playbook playbooks/configure-proxmox-host.yml
ansible-playbook playbooks/configure-firewall.yml
ansible-playbook playbooks/configure-<service>.yml

# Run a part of site.yml.
ansible-playbook playbooks/site.yml --tags configure
ansible-playbook playbooks/site.yml --tags caddy
```

### Secrets

| Variable | Description |
|---|---|
| `proxmox_api_token_secret` | Proxmox API token UUID (`root@pam!ansible`) |
| `proxmox_homepage_token_secret` | Proxmox token for the homepage widget (`root@pam!homepage`) |
| `portainer_api_key` | Portainer access token for the homepage widget |
| `github_pat` | GitHub PAT that registers the self-hosted runner |
| `lxc_root_password` | Root password for new LXCs |
| `pihole_web_password` | Pi-hole admin UI password |
| `vaultwarden_admin_token` | Vaultwarden `/admin` token |
| `ubuntu_vm_password` | Ubuntu VM root password |
| `nextcloud_aio_password` | Nextcloud AIO admin passphrase |
| `cloudflare_tunnel_token` | Cloudflare Zero Trust tunnel token for the Caddy CT |
| `cloudflare_api_token` | Optional. Cloudflare API token (Tunnel: Read) for the homepage widget |

> **Git ignores `secrets.yml`.** Encrypt it with `ansible-vault encrypt group_vars/all/secrets.yml`. Then add `--ask-vault-pass` to each playbook command.

### Secret scanning

- `pre-commit install` enables [gitleaks](https://github.com/gitleaks/gitleaks) with the custom rules in `.gitleaks.toml`. A second hook stops a commit of an unencrypted `secrets.yml` or `vault.yml`.
- `.github/workflows/secret-scan.yml` runs gitleaks on each push and pull request.

## Layout

```
ansible.cfg          Ansible configuration
inventory.yml        Nodes, guests (ctid/id, pve_node), host variables, caddy_routes, firewall_in
group_vars/all/      main.yml (defaults), secrets.yml (ignored by Git), secrets.yml.example
playbooks/           site, provision-lxc, provision-vms, configure-<service>, configure-proxmox-host, configure-firewall
roles/<service>/     defaults, tasks, templates, handlers, meta (docker dependency)
docs/                Setup guide for each service
.gitleaks.toml       Secret scan rules (pre-commit and CI)
```

## Adding a new service

1. Add the host under `lxc_containers.hosts` in `inventory.yml`. Set `ctid`, `ansible_host`, `memory`, `disk` and `cores`. Set `pve_node` if the node is not pve-brain. If the host runs Docker, set `lxc_docker_host: true`.
2. Run `provision-lxc.yml` to create the CT.
3. Copy the structure of `roles/pihole/`: `defaults/`, `tasks/main.yml` as the orchestrator, and `tasks/install.yml` with a `creates:` gate. For a Docker service, add `meta/main.yml` with `dependencies: [role: docker]`.
4. Add `playbooks/configure-<service>.yml`, an inventory group with the same name, and an entry in `playbooks/site.yml`.
5. Add `firewall_in` to the host. Open the app port to `caddy`, `+monitors` and `+management`. Then run `configure-firewall.yml` again.
6. Add a `caddy_routes` entry to the `caddy` host. Then run `configure-caddy.yml` again.

## Known limitations

- The Pi-hole DNS upstreams are set one time at installation through `setupVars.conf`. A second run does not set them again.
- `secrets.yml` starts as plain YAML. The pre-commit hook only stops a commit of the unencrypted file.
- The Vaultwarden `ADMIN_TOKEN` is plain text in the compose file. An argon2 hash is better.
- The `backups` storage is on the same HDD as VM 110. Backups protect against mistakes, not against disk failure.
- VMs 120/130 use the `kvm64` CPU type. Images that need x86-64-v2 do not start there until you change the CPU type.
- The cluster has no QDevice. When one node stops, `/etc/pve` on the other node becomes read-only. Use `pvecm expected 1` on the node that runs.
- The Proxmox GUI is available only through the tunnel. If the tunnel stops, use the node console and run `pve-firewall stop`.
