import json

import pytest

from cluster_mcp.inventory import Inventory, InventoryError

from .conftest import REPO_ROOT


@pytest.fixture
def inv():
    return Inventory(REPO_ROOT)


def test_summary_has_real_hosts(inv):
    s = inv.summary()
    assert "caddy" in s["groups"]["lxc_containers"]
    assert "ubuntu-vm1" in s["groups"]["virtual_machines"]
    assert s["hosts"]["pve-worker"]["ansible_host"] == "192.168.88.20"


def test_host_vars_merge_and_redact(inv):
    v = inv.host("uptime-kuma")["vars"]
    assert v["ctid"] == 103
    assert v["pve_node"] == "pve-worker"
    assert v["ansible_user"] == "root"
    assert v["proxmox_api_token_id"] == "<redacted>"
    assert not any("secret" in k and v[k] != "<redacted>" for k in v)


def test_unknown_host(inv):
    with pytest.raises(InventoryError):
        inv.host("nope")


def test_secret_files_never_loaded(tmp_path):
    (tmp_path / "group_vars" / "all").mkdir(parents=True)
    (tmp_path / "inventory.yml").write_text("all:\n  hosts:\n    h1:\n      ansible_host: 10.0.0.1\n")
    (tmp_path / "group_vars" / "all" / "main.yml").write_text("plain: 1\nvaulted: !vault |\n  $ANSIBLE_VAULT;1.1\n")
    (tmp_path / "group_vars" / "all" / "secrets.yml").write_text("leak: hunter2\n")
    (tmp_path / "group_vars" / "all" / "other.yml").write_text("$ANSIBLE_VAULT;1.1;AES256\n6162\n")
    v = Inventory(tmp_path).host("h1")["vars"]
    assert v["plain"] == 1
    assert v["vaulted"] == "<redacted>"
    assert "leak" not in v


def test_facts(tmp_path):
    cache = tmp_path / "facts"
    cache.mkdir()
    (cache / "caddy").write_text(json.dumps({"ansible_kernel": "6.8", "ansible_memtotal_mb": 256, "huge": "x"}))
    inv = Inventory(REPO_ROOT, cache)
    f = inv.facts("caddy")["facts"]
    assert f == {"ansible_kernel": "6.8", "ansible_memtotal_mb": 256}
    assert inv.facts("caddy", ["kernel"])["facts"] == {"ansible_kernel": "6.8"}
    with pytest.raises(InventoryError):
        inv.facts("pi-hole")
    with pytest.raises(InventoryError):
        inv.facts("../etc/passwd")


def test_facts_disabled():
    with pytest.raises(InventoryError, match="ANSIBLE_FACT_CACHE"):
        Inventory(REPO_ROOT).facts("caddy")
