# Caddy

Single static `caddy` binary acting as the reverse proxy for every service, with a co-located `cloudflared` tunnel as the Cloudflare entry point.

- **CT:** 100 | **IP:** 192.168.88.100 | **Port:** 80 (HTTP)
- **Entry point:** Cloudflare Zero Trust tunnel → `cloudflared` (on this CT) → `localhost:80` → Caddy → upstream
- **Tunnel setup:** step-by-step in [cloudflare-tunnel.md](cloudflare-tunnel.md)

## How it works

- Caddy serves **plain HTTP on `:80`** — site addresses are rendered as `http://<domain>` and `auto_https off` is set, because Cloudflare terminates TLS at the tunnel edge. No local certs.
- `cloudflared` is installed from the `.deb` and registered as a systemd service with `cloudflared service install <token>`. Public hostnames / ingress are managed in the **Cloudflare Zero Trust dashboard**, pointing the tunnel at `http://localhost:80`.
- The whole `Caddyfile` is rendered from the `caddy_routes` list on the `caddy` host in `inventory.yml`.

## Variables

Defaults in `roles/caddy/defaults/main.yml`. Routes set per-host in `inventory.yml`.

| Variable | Default | Description |
|---|---|---|
| `caddy_version` | `2.9.1` | Caddy release to download |
| `caddy_log_level` | `INFO` | Global log level |
| `caddy_security_headers_enabled` | `true` | Inject HSTS / nosniff / referrer-policy headers |
| `caddy_sts_seconds` | `31536000` | `Strict-Transport-Security` max-age |
| `caddy_routes` | `[]` | List of route definitions (schema below) |

### Route schema

```yaml
caddy_routes:
  - name: proxmox                                # label only
    domain: "proxmox.{{ cloudflare_zone }}"      # site address (Host match)
    destination: https://192.168.88.10:8006      # upstream URL
    # redirect_root_to: /admin/                  # optional 301 from / to subpath
    # backend_ssl: true                          # optional; force tls_insecure_skip_verify
```

- `https://` destinations automatically get `tls_insecure_skip_verify` (Proxmox, Nextcloud self-signed). Use `backend_ssl: true` to force it for an `http://` upstream that fronts HTTPS.

## Deploy

```bash
ansible-playbook playbooks/configure-caddy.yml
```

The secret `cloudflare_tunnel_token` (in `secrets.yml`) is consumed once by `cloudflared service install`.

## Notes

- **Caddy has no dashboard** — the admin API is disabled (`admin off`). Inspect via the binary on the host: `caddy validate --config /etc/caddy/Caddyfile`.
- Adding a service = add a `caddy_routes` entry + re-run the play. Caddy reloads via the `restart caddy` handler.
- A new subdomain also needs a **DNS / public-hostname entry in the Cloudflare tunnel** — otherwise the browser gets `Server Not Found`.
- `cloudflared` must dial `localhost:80`; if Caddy ever binds only `:443` you get `502 Bad Gateway`. Site addresses must keep the `http://` prefix.
