# Proxmox host

Configuration of the PVE nodes themselves (not guests): node identity and root-volume housekeeping on every node; backup storage + job and metric servers on the primary node only.

Two-node cluster `skylab` (inventory group `proxmox_nodes`):

| Inventory entry | Node (`pve_node`) | IP | FQDN | Role |
|---|---|---|---|---|
| `pve` | `pve-brain` (= `proxmox_node`, primary) | 192.168.88.10 | `pve-brain.bong` | Storage + edge: data-hdd, backups, Nextcloud VM, caddy, pi-hole |
| `pve-worker` | `pve-worker` | 192.168.88.20 | `pve-worker.home.arpa` | Compute: k8s VMs, vaultwarden, uptime-kuma, homepage (NVMe `local-lvm` only) |

The inventory entry name is only an Ansible label; `pve_node` is what must match the hostname.

### Guest placement

Every guest has `pve_node` (default `proxmox_node`, set in `group_vars/all/main.yml`). `pve_node_host` maps it back to the node's inventory entry, which provisioning uses to run `qm`/`pct`/`pveam` on the right node. VMs on `pve-worker` also need `vm_storage: local-lvm` — `data-hdd` exists only on pve-brain.

Changing `pve_node` does **not** move a guest. Migrate it first, then update the inventory:

```bash
pct migrate <ctid> pve-worker --restart              # CT, ~seconds of downtime
qm migrate <vmid> pve-worker --targetstorage local-lvm  # stopped VM, disk copied over 1GbE
```

## Variables

Defaults in `roles/proxmox_host/defaults/main.yml`. `proxmox_node` lives in `group_vars/all/main.yml`; `pve_node` and `proxmox_domain` are set per node in `inventory.yml`.

| Variable | Default | Description |
|---|---|---|
| `proxmox_node` | `pve-brain` | Primary node: API target, default `pve_node` for guests |
| `pve_node` | per node | Must equal the node's real hostname (asserted) |
| `proxmox_domain` | `bong` (fallback) | Domain for the FQDN in `/etc/hosts` and postfix; per node in inventory |
| `proxmox_host_primary` | `pve_node == proxmox_node` | Runs backup storage/job + metric tasks |
| `journald_max_use` | `200M` | `SystemMaxUse` for the persistent journal |
| `proxmox_unused_isos` | `[]` | ISO filenames in `local:iso` to delete |
| `backup_vg` / `backup_thinpool` | `data-hdd` / `data` | Thin pool the backup LV is carved from |
| `backup_lv` / `backup_lv_size` | `backups` / `200g` | Thin LV (ext4, label `pvebackups`) |
| `backup_mount` | `/mnt/backups` | Mount point (fstab, `nofail`) |
| `backup_storage_id` | `backups` | PVE storage ID (`dir`, content `backup`) |
| `backup_keep_last` | `2` | `prune-backups keep-last` for storage and job |
| `backup_job_id` | `backup-ce63a726-7399` | Existing job is adopted and repointed |
| `backup_job_schedule` | `sun 01:00` | Job schedule |
| `backup_job_vmids` | `110` | Comma-separated VMIDs; add `100,101,102,103,104,120,130` for everything |
| `proxmox_disabled_metric_servers` | `[InfluxDB]` | Metric server IDs kept disabled |

## Deploy

```bash
ansible-playbook playbooks/configure-proxmox-host.yml
ansible-playbook playbooks/configure-proxmox-host.yml --tags backup     # storage + job only
ansible-playbook playbooks/configure-proxmox-host.yml --tags cleanup
```

Idempotent: a re-run reports `changed=0`.

## Why backups live on data-hdd

`local` storage is `/var/lib/vz` on the **40G root LV**. A single VM 110 backup is ~9G, so two backups plus ISOs filled root to 95% and the weekly job failed with `vma_queue_write: write error - Broken pipe`. Backups now go to a thin LV on the 931G `data-hdd` pool.

> The backup LV is on the **same physical disk** (`sdb`) as VM 110/120/130. It protects against bad changes and deletions, not disk failure — copy backups to another machine or an external disk for that.

## Renaming the node (runbook)

The node was renamed `pve` → `pve-brain`. Renaming is manual; Ansible only guards against drift (`pve_node` must equal the hostname). Per the [Proxmox wiki](https://pve.proxmox.com/wiki/Renaming_a_PVE_node), for a single-node setup:

1. Before rebooting, make `/etc/hosts` resolve the **new** name to the node IP (`192.168.88.10 pve-brain.bong pve-brain`). Otherwise `pve-cluster` (pmxcfs) fails with `Unable to resolve node name ... to a non-loopback IP address` and every PVE service stays down.
2. `hostnamectl set-hostname <new>` and reboot.
3. Move guest configs: `mv /etc/pve/nodes/<old>/qemu-server/*.conf /etc/pve/nodes/<new>/qemu-server/` and the same for `lxc/`.
4. If a corosync config exists, change the node `name` in `/etc/pve/corosync.conf` **and** `/etc/corosync/corosync.conf`, bump `config_version`, restart `corosync`.
5. `pvecm updatecerts --force`, restart `pveproxy`/`pvedaemon`/`pvestatd`/`pve-firewall`/`pvescheduler`/`pve-ha-*`, then start guests: `pvesh create /nodes/<new>/startall`.
6. Remove the old directory: `rm -r /etc/pve/nodes/<old>`.
7. Replace the old name wherever it was referenced:
   - `pve_node` on the node entry in `inventory.yml` (and `proxmox_node` in `group_vars/all/main.yml` if it is the primary)
   - `pve_node` on every guest living on it
   - the homepage Proxmox widgets (rendered from each node's `pve_node`)
   - `/etc/pve/priv/known_hosts` (`pve` → `pve-brain`)
   - postfix `myhostname`
   - **metric servers in `/etc/pve/status.cfg` that name the host** (see below)

## Troubleshooting

- **All guests show status `unknown` in the UI.** `pvestatd` is failing. Check `journalctl -u pvestatd`. Cause here: the `InfluxDB` metric server had `server PVE`, a name that only resolved through the old `/etc/hosts` alias, so `pvestatd` errored every cycle and never published status. Fix by pointing it at a real host, or disable it (this role does).
- **Root volume filling up.** `du -xh --max-depth=2 /var/lib/vz | sort -rh | head`. ISOs, CT templates and any backup written to `local` live there. Use `proxmox_unused_isos` to delete ISOs and keep backups on the `backups` storage.
- **Backup fails with `no such logical volume data-hdd/data`.** Seen once in September; the thin pool was present and the error did not recur. Check `lvs -a` and `systemctl status lvm2-monitor`.

## Notes

- Removed during the cleanup (not recreated by Ansible): Kali and Ubuntu live-server ISOs. The noble cloud image is kept because `roles/ubuntu` downloads it for `provision-vms.yml`.
- `local-lvm` has two LVs not referenced by any guest config: `vm-106-disk-0` (20G) and `vm-101-disk-0` (4G). Review before removing.
