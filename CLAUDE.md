# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

Ansible runs **directly on the primary Proxmox node `pve-brain`** (not a remote workstation). It is installed via pip into the system Python (`ansible` + `ansible-core` + `proxmoxer` in `/usr/local/lib/python3.13/dist-packages`; `requests`/`yaml` come from Debian), so `ansible-playbook` is on `PATH` — no venv to activate.

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

# Node-level config on both nodes (hostname, journald cap, no-subscription repos, root shell);
# backup storage/job + metric servers on pve-brain only
ansible-playbook playbooks/configure-proxmox-host.yml
ansible-playbook playbooks/configure-proxmox-host.yml --limit pve-worker

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

### Lint (CI gate)

`.github/workflows/ansible-lint.yml` runs on every push/PR on GitHub-hosted runners: `yamllint --strict`, `ansible-lint` (`production` profile, config in `.ansible-lint`), and `ansible-playbook --syntax-check` on every playbook. Tool versions are pinned in `requirements-ci.txt` (`ansible-core` matches pve-brain). Same checks locally:

```bash
pip install -r requirements-ci.txt && ansible-galaxy collection install -r requirements.yml
yamllint --strict . && ansible-lint
for pb in playbooks/*.yml; do ansible-playbook --syntax-check "$pb" </dev/null; done
```

No `--check` in CI: hosted runners can't reach 192.168.88.x, and the only self-hosted runner is scoped to `nextjs-blog`. A runner for this public repo would need root SSH to both nodes, so don't add one. Commands gated by `when:` use `changed_when: true`; handler names are capitalised and `notify:` must match exactly (case-sensitive).

## Architecture

Two distinct play types — never mix them:

1. **Provision** (`provision-lxc.yml`, `provision-vms.yml`) — talks to the Proxmox API via `community.proxmox` (localhost connection), creating each guest on its `pve_node`. Node-local steps (template download, `qm` cloud-init, `lxc.apparmor.profile: unconfined` for `lxc_docker_host: true` CTs) run on the owning node via `pve_node_host`.

2. **Configure** (`configure-*.yml`) — SSHes into the target guest or the `proxmox_nodes`, runs a single named role.

### Role shape

All roles follow `roles/pihole/` as the canonical example:
- `defaults/main.yml` — all tunables with defaults
- `tasks/main.yml` — thin orchestrator (`include_tasks`)
- `tasks/install.yml` — gated with `creates:` or `when:` so re-runs are cheap
- `templates/` — Jinja2 configs
- `handlers/main.yml` — service reload/restart

Roles that need Docker declare `meta/main.yml` → `dependencies: [role: docker]`. Ansible deduplicates per play, so Docker is installed exactly once even if multiple roles depend on it.

Roles: `caddy`, `pihole`, `vaultwarden`, `uptime-kuma`, `homepage`, `portainer`, `nextcloud-aio`, `github_runner`, `docker`, `ubuntu` (VM provisioning), `proxmox_host`, `pve_firewall`, `qdevice`.

### Secrets & variables

- `group_vars/all/main.yml` — non-secret defaults (IPs, template VMID, `cloudflare_zone`)
- `group_vars/all/secrets.yml` — gitignored; copy from `secrets.yml.example` and fill in. Never commit it, and never put real values in the `.example`
- Secret scanning: gitleaks (`.gitleaks.toml`, custom rules for formats stock gitleaks misses) runs in pre-commit and in `.github/workflows/secret-scan.yml`; a pre-commit hook rejects any non-vaulted `secrets.yml`/`vault.yml`. Don't weaken the rules to get a commit through
- Per-host variables (e.g. `caddy_routes`, `homepage_allowed_hosts`) live directly on the host entry in `inventory.yml`
- `cloudflare_zone` is defined once in `main.yml`; domains throughout `inventory.yml` reference it as `"subdomain.{{ cloudflare_zone }}"`

### Service map

| Host (CT) | Node | IP | Runtime | Port |
|---|---|---|---|---|
| caddy (100) | pve-brain | .100 | caddy binary + cloudflared | 80 |
| pi-hole (101) | pve-brain | .101 | bare pihole | 80 |
| vaultwarden (102) | pve-worker | .102 | Docker compose | 8080 |
| uptime-kuma (103) | pve-worker | .103 | Docker compose | 3001 |
| homepage (104) | pve-worker | .104 | Docker compose | 3000 |
| ubuntu-vm1 (VM 110) | pve-brain | .110 | Docker compose | Portainer 9000, Nextcloud AIO 8080 (admin) / 11000, blog 3000 |
| ubuntu-vm1 (VM 110) | pve-brain | .110 | systemd | GitHub Actions runner (`roles/github_runner`) |
| ubuntu-vm2/3 (VM 120/130) | pve-worker | .120/.130 | k8s VMs, provisioned only (no configure role) | — |

The blog on :3000 is a Portainer git stack from a separate repo, not managed here; only its Caddy route lives in this repo.

Two-node cluster `skylab` (group `proxmox_nodes`): `pve-brain` (192.168.88.10, inventory label `pve`, primary — `proxmox_node` in `group_vars/all/main.yml`) and `pve-worker` (192.168.88.20). Ansible runs on pve-brain. Each guest's node is `pve_node` in `inventory.yml` (default `proxmox_node`); `pve_node_host` maps it to the node's inventory entry for node-local `qm`/`pct` commands. See `docs/proxmox-host.md`.

## Known gotchas

- **`--check` fails for `provision-lxc.yml`** — `community.proxmox` skips itself in check mode. Run for real; existing CTs return `changed=0`.
- **New LXC may have empty `/etc/resolv.conf`** — set nameserver via Proxmox GUI before the configure play runs.
- **IPv6 hangs `apt`** — add `Acquire::ForceIPv4 "true"` to `/etc/apt/apt.conf.d/99force-ipv4` if apt stalls in a new CT.
- **`proxmoxer` + `requests` must be importable by the same Python that runs Ansible** (`/usr/bin/python3`) — missing them causes cryptic import errors from the Proxmox module. They live in `/usr/local/lib/python3.<ver>/dist-packages` — a Debian/PVE major upgrade bumps Python and leaves them behind (`No module named 'ansible'`); reinstall with `python3 -m pip install --break-system-packages ansible==12.3.0 ansible-core==2.19.9 proxmoxer==2.3.0`.
- **pip installs go to `/usr/local/lib`, not Proxmox's own packages** — Debian-managed packages in `/usr/lib/python3/dist-packages` (including Proxmox's) are never overwritten by pip; don't force `--target` or `--break-system-packages` into `/usr/lib`.
- **Caddy is the reverse proxy** — `caddy_routes` on the `caddy` host in `inventory.yml` renders the full Caddyfile; routes serve plain HTTP on `:80` (`http://` site addresses, `auto_https off`) because Cloudflare terminates TLS at the tunnel. The co-located `cloudflared` tunnel dials `localhost:80`.
- **`https://` upstreams need no extra flag** — the Caddyfile template auto-adds `tls_insecure_skip_verify` when `destination` starts with `https://` (covers Proxmox + Nextcloud self-signed certs); override with `backend_ssl: true` otherwise.
- **The repo is public** — keep secrets, tokens, internal hostnames beyond what `inventory.yml` already has, and anything that maps the attack surface out of commits, docs and PR text.
- **Pi-hole password idempotency** keyed on marker file `/etc/pihole/.ansible_password_hash` — delete it to force a re-sync.
- **Vaultwarden**: first run needs `vaultwarden_signups_allowed: "true"` to register the first account, then flip to `"false"` and re-run.
- **Nextcloud AIO first run**: after `configure-nextcloud.yml`, visit `https://192.168.88.110:8080` to complete setup in the AIO admin UI. `NC_DOMAIN` is pre-filled from `nextcloud_aio_domain`. `SKIP_DOMAIN_VALIDATION` is set so the reverse-proxy setup doesn't block init.
- **docker role supports both Debian and Ubuntu** — repo URL uses `{{ ansible_distribution | lower }}` so the same role works for LXCs (Debian) and the Ubuntu VM.

- **Each node's `pve_node` must equal its real hostname** — `roles/proxmox_host` asserts it. Guest configs live in `/etc/pve/nodes/<hostname>/`; a mismatch makes every guest vanish. Renaming a node is manual — see the runbook in `docs/proxmox-host.md`, and make `/etc/hosts` resolve the new name *before* rebooting or pmxcfs won't start.
- **Guests all `unknown` in the UI** — `pvestatd` is failing, usually on a metric server in `/etc/pve/status.cfg` whose host no longer resolves. `roles/proxmox_host` keeps the dead `InfluxDB` entry disabled.
- **Never write backups to `local`** — it is `/var/lib/vz` on the 40G root LV and fills it. Backups go to the `backups` storage (`/mnt/backups`, thin LV on `data-hdd`), managed by `roles/proxmox_host`. It is on the same disk as the VMs, so not disk-failure protection.
- **`pve_node` describes placement, it doesn't move guests** — migrate first (`pct migrate <id> pve-worker --restart`, `qm migrate <id> pve-worker --targetstorage local-lvm`), then edit inventory. VMs on pve-worker need `vm_storage: local-lvm` (no `data-hdd` there).
- **VM CPU type must be ≥ x86-64-v2** — without `cpu:` Proxmox uses `kvm64` (v1), and modern images (UBI/RHEL9 glibc, e.g. `pgsty/silo`) die with `Fatal glibc error: CPU does not support x86-64-v2`. `roles/ubuntu` sets `vm_cpu: x86-64-v2-AES` at creation only; existing VMs need `qm set <id> --cpu x86-64-v2-AES` + a full stop/start. VM 110 is done; 120/130 still run `kvm64`.
- **Run `ansible-playbook` with stdin redirected in non-TTY shells** (`</dev/null | cat`) — otherwise it aborts with "Non-blocking file handles detected".

- **PVE firewall is on, default DROP** (`roles/pve_firewall`, `docs/firewall.md`). A guest only accepts what its `firewall_in` in `inventory.yml` lists (plus SSH from `+management`, ping from LAN); a new port or a new client of an existing port needs a rule there and a re-run of `configure-firewall.yml`. Node GUI/SSH only from the `management` IPSet (nodes + `pve_fw_admin_cidrs`, empty by default) and 8006 from Caddy, so admin access is tunnel-only via `proxmox.<zone>`; lockout recovery is `pve-firewall stop` from the node console.
- **Two-node quorum needs the QDevice** (`roles/qdevice`, `docs/qdevice.md`). Without it, one node down makes `/etc/pve` read-only on the other.

## Adding a new service

1. Add a host entry under `lxc_containers.hosts` in `inventory.yml` (ctid, ansible_host, memory, disk, cores, `pve_node` if not pve-brain). Tag `lxc_docker_host: true` if it runs Docker.
2. Run `provision-lxc.yml` to create the CT.
3. Copy `roles/pihole/` shape; add `tasks/install.yml` gated with `creates:` for idempotency.
4. Add `playbooks/configure-<service>.yml` targeting the new inventory group, and import it in `playbooks/site.yml`.
5. Add a matching inventory group under `children:`.
6. Add `firewall_in` on the new host (its app port from `caddy`, `+monitors`, `+management`) and re-run `configure-firewall.yml`.
7. Add a `caddy_routes` entry on the `caddy` host in `inventory.yml`, then re-run `configure-caddy.yml`.
