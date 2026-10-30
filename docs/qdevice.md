# Corosync QDevice

A two-node cluster has two votes and needs two for quorum. When either node is down, the other loses quorum: `/etc/pve` becomes read-only and guests can't be started or changed. A QDevice adds a third vote from a small external host running `corosync-qnetd`.

`roles/qdevice` installs `corosync-qnetd` on the host in the `qdevice` inventory group, authorizes the cluster SSH key there, installs `corosync-qdevice` on both nodes and runs `pvecm qdevice setup` once from the primary node.

## Requirements for the qnetd host

- Always on, Debian/Ubuntu, root SSH reachable from the controller (pve-brain).
- **Not** a guest of this cluster: if it runs on a node, it dies with that node and adds nothing.
- Reachable from both nodes on TCP 5403. Latency doesn't matter much (unlike corosync itself).

## Deploy

```yaml
# inventory.yml
qdevice:
  vars:
    ansible_user: root
  hosts:
    qdevice-pi:
      ansible_host: 192.168.88.5
```

```bash
ansible-playbook playbooks/configure-qdevice.yml
pvecm status   # Expected votes: 3, Qdevice listed under Membership
```

Both nodes must be online for the setup. The play is a no-op while the `qdevice` group is empty. To remove the QDevice: `pvecm qdevice remove`.
