# nginx-proxy

Bare nginx acting as reverse proxy for all services. Terminates HTTP (and optionally TLS) and forwards to upstream LXCs/VMs.

- **CT:** 100 | **IP:** 192.168.88.100 | **Port:** 80 / 443

## Variables

Set per-host in `inventory.yml` under the `nginx-proxy` host entry.

| Variable | Description |
|---|---|
| `nginx_proxy_hosts` | List of vhost definitions (see schema below) |
| `nginx_client_max_body_size` | Max upload size (default `10G`) |
| `nginx_proxy_read_timeout` | Proxy timeout in seconds (default `86400`) |

### Vhost schema

```yaml
nginx_proxy_hosts:
  - name: myapp           # used for config filename
    domain: myapp.example.com
    destination: http://192.168.88.x:PORT
    ssl: false            # true → terminate TLS on :443, redirect :80
    ssl_cert: /path/to/cert.pem   # required when ssl: true
    ssl_key: /path/to/key.pem     # required when ssl: true
    backend_ssl: false    # true → disable verify for self-signed upstream
    redirect_root_to: /admin/     # optional 301 from /
    extra_config: ""      # optional raw nginx directives in location /
```

## Deploy

```bash
ansible-playbook playbooks/configure-nginx-proxy.yml
```

## Notes

- Every file in `sites-enabled/` not in `nginx_proxy_hosts` (including Debian's `default`) is **removed** on each run.
- This role does not manage certificates — place certs on the CT manually before enabling `ssl: true`.
- Websocket upgrade headers are included for all vhosts (needed for Proxmox noVNC and Vaultwarden).
