# Portainer CE

Docker container management UI. Runs as a Docker Compose service on the Ubuntu VM alongside Nextcloud AIO.

- **VM:** 110 | **IP:** 192.168.88.110 | **Port:** 9000 (HTTP), 9443 (HTTPS self-signed)
- **Public URL:** via nginx-proxy → `http://192.168.88.110:9000`

## Variables

Defaults in `roles/portainer/defaults/main.yml`. No secrets required.

| Variable | Default | Description |
|---|---|---|
| `portainer_image` | `portainer/portainer-ce:2.21.5` | Docker image tag |
| `portainer_host_port` | `9000` | HTTP UI port |
| `portainer_https_port` | `9443` | HTTPS UI port (self-signed cert) |

## Deploy

```bash
ansible-playbook playbooks/configure-portainer.yml
```

## Notes

- Runs on `ubuntu-vm1` (VM 110) — VM must be provisioned first via `provision-vms.yml`.
- First visit creates the admin account — do this immediately after deploy (Portainer locks out after a timeout).
- nginx-proxy should forward to port 9000 (HTTP); no need for `backend_ssl`.
- Data persists in `/opt/portainer/data` on the VM.
- Bump `portainer_image` deliberately; check releases at https://github.com/portainer/portainer/releases.
