# Portainer CE

Docker container management UI. Runs as a Docker Compose service on the Ubuntu VM alongside Nextcloud AIO.

- **VM:** 110 | **IP:** 192.168.88.110 | **Port:** 9000 (HTTP), 9443 (HTTPS self-signed)
- **Access:** LAN only (`http://192.168.88.110:9000`). No Caddy route or tunnel hostname; the PVE firewall allows 9000/9443 from `192.168.88.0/24` only.

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
- Data persists in `/opt/portainer/data` on the VM.
- Bump `portainer_image` deliberately; check releases at https://github.com/portainer/portainer/releases.

## Workloads (stacks)

Deploy Docker/compose workloads as Portainer **stacks** (Stacks → Add stack), not as files on the VM. Git-backed stacks keep the compose file in the app's repo; secrets go in the stack's environment variables.

### Blog (`nextjs-blog`) — CI/CD

Push to `main` → GitHub Actions (`.github/workflows/deploy.yml` in the blog repo) builds the `runner` image → pushes `ghcr.io/boris-jancic/nextjs-blog:{latest,<sha>}` → `redeploy` job on the self-hosted runner (ubuntu-vm1, `roles/github_runner`) POSTs the stack webhook over loopback → Portainer re-pulls compose + image and redeploys.

One-time setup:

1. **GitHub PAT** (fine-grained, repo `nextjs-blog`: Contents read; plus classic `read:packages` for GHCR — or one classic token with `repo` + `read:packages`).
2. **Portainer → Registries → Add → Custom**: `ghcr.io`, user `Boris-Jancic`, password = PAT.
3. **Portainer → Stacks → Add stack → Repository**, name `nextjs-blog` (same compose project name as the old manual deploy, so it adopts its containers):
   - URL `https://github.com/Boris-Jancic/nextjs-blog`, ref `refs/heads/main`, compose path `docker-compose.yml`, authentication = PAT.
   - GitOps updates: on, mechanism **Webhook**, **Re-pull image** on. Copy the webhook URL.
   - Env vars: `MINIO_DATA_DIR=/minio-data`, `MINIO_API_PORT=9100`, `MINIO_CONSOLE_PORT=9101` (9000 is Portainer), `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `JWT_SECRET`, `ADMIN_PASSWORD_HASH`. Missing `JWT_SECRET`/`ADMIN_PASSWORD_HASH` silently falls back to the compose dev defaults (admin password `admin`).
4. **Runner**: `ansible-playbook playbooks/configure-github-runner.yml` (needs `github_pat` in `secrets.yml`).
5. **Blog repo → Settings → Secrets and variables → Actions**: secret `PORTAINER_WEBHOOK_URL` = `http://127.0.0.1:9000/api/stacks/webhooks/<id>`; variable `NEXT_PUBLIC_SITE_URL` (inlined at build time).

Rollback: in the stack editor set env `BLOG_IMAGE=ghcr.io/boris-jancic/nextjs-blog:<old-sha>` and update the stack.

Gotchas:

- **Cloudflare Bot Fight Mode challenges GitHub-hosted runners** (`403`, `cf-mitigated: challenge`) and can't be skipped per path on the Free plan — hence the self-hosted runner for the webhook call.
- **Failed stack deploys tear the stack down** — Portainer runs `compose down` on failure, so a bad deploy means downtime, not a stuck old version.
