# Cloudflare Tunnel setup

How to wire the Caddy reverse proxy (CT 100) to the internet through a Cloudflare Zero Trust tunnel. No router ports are opened — `cloudflared` dials out to Cloudflare, and Cloudflare routes public traffic back down the tunnel to Caddy on `localhost:80`.

```
Internet → Cloudflare edge → tunnel → cloudflared (CT 100) → Caddy :80 → upstream service
```

See [caddy.md](caddy.md) for the proxy/role details.

## Prerequisites

- A domain on Cloudflare (this repo uses `cloudflare_zone`, e.g. `jancic.website`).
- Cloudflare Zero Trust enabled (free tier is fine): <https://one.dash.cloudflare.com>.

## 1. Create the tunnel

1. Zero Trust dashboard → **Networks → Tunnels → Create a tunnel**.
2. Connector type: **Cloudflared**. Name it (e.g. `homelab-caddy`). Save.
3. On the install screen, **copy the token** — the long `eyJ...` string from the `cloudflared service install <TOKEN>` command. That token is all you need; ignore the install commands (the Ansible role installs `cloudflared` for you).

## 2. Store the token

Put the token in `group_vars/all/secrets.yml`:

```yaml
cloudflare_tunnel_token: "eyJhIjoi…"   # paste the full token
```

> Rotating later? Just replace the value and re-run the play — the role detects the change and re-installs the tunnel service automatically.

## 3. Add public hostnames (one per service)

Still in the tunnel config → **Public Hostnames → Add a public hostname**. Each service in `caddy_routes` needs one entry. **Service is always `http://localhost:80`** — Caddy does the host-based routing from there.

| Subdomain | Domain | Service (origin) |
|---|---|---|
| `proxmox` | `proxmox.<zone>` | `http://localhost:80` |
| `pihole` | `pihole.<zone>` | `http://localhost:80` |
| `cloud` | `cloud.<zone>` | `http://localhost:80` |
| `nextcloud` | `nextcloud.<zone>` | `http://localhost:80` |
| `homepage` | `homepage.<zone>` | `http://localhost:80` |
| `kuma` | `kuma.<zone>` | `http://localhost:80` |
| `portainer` | `portainer.<zone>` | `http://localhost:80` |
| `vaultwarden` | `vaultwarden.<zone>` | `http://localhost:80` |

Cloudflare auto-creates the matching DNS `CNAME` for each hostname. The hostnames must match the `domain` values in the `caddy` host's `caddy_routes` (in `inventory.yml`) exactly.

> Adding a new service later = add a `caddy_routes` entry **and** a public hostname here, both pointing the new subdomain at `http://localhost:80`.

## 4. Deploy

```bash
ansible-playbook playbooks/provision-lxc.yml      # if CT 100 not yet created
ansible-playbook playbooks/configure-caddy.yml    # installs caddy + cloudflared, applies token
```

## 5. Verify

```bash
# Tunnel registered cleanly (look for "Registered tunnel connection", no ERR loop):
ssh root@192.168.88.100 'journalctl -u cloudflared --no-pager | tail -15'

# Caddy answers per-host on :80:
ssh root@192.168.88.100 'curl -s -o /dev/null -w "%{http_code}\n" -H "Host: homepage.<zone>" http://localhost/'

# End-to-end from anywhere:
curl -I https://homepage.<zone>/
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `502 Bad Gateway` | Tunnel up but origin unreachable — Caddy not on `:80`, or service down | `ss -tlnp \| grep :80` on CT 100; ensure `caddy` active. Site addresses must keep the `http://` prefix so Caddy binds `:80`. |
| `Server Not Found` / DNS error | No public hostname for that subdomain on this tunnel | Add it in step 3. A new tunnel starts with **zero** hostnames. |
| `cloudflared` retry loop, high CPU | Wrong/old token | Replace `cloudflare_tunnel_token` in `secrets.yml`, re-run `configure-caddy.yml`. |
| `control stream encountered a failure` repeating | Token belongs to a deleted/other tunnel | Recreate tunnel (step 1), new token, re-run. |
| Subdomain works, app misbehaves (cookies/redirects) | Upstream expects HTTPS scheme | Caddy forwards `X-Forwarded-Proto`; for self-signed HTTPS upstreams set `destination: https://…` (auto `tls_insecure_skip_verify`). |

> Harmless warnings in `cloudflared` logs: `ping_group_range` (ICMP disabled in unprivileged LXC) and Caddy's `$HOME environment variable is empty`.
