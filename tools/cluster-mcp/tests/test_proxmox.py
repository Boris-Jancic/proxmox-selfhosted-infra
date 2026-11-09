import pytest

from cluster_mcp.proxmox import ProxmoxError, ReadOnlyProxmox, check_path

from .conftest import FakeResponse, FakeSession


def test_get_sends_token_and_only_get(pve, session):
    assert pve.get("/cluster/resources")[1]["vmid"] == 110
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["headers"]["Authorization"] == "PVEAPIToken=root@pam!mcp=s3cr3t"
    assert call["allow_redirects"] is False


def test_client_has_no_write_methods():
    for name in ("post", "put", "delete", "patch", "create", "set", "request"):
        assert not hasattr(ReadOnlyProxmox, name)


@pytest.mark.parametrize(
    "path",
    [
        "/nodes/../access",
        "/nodes//x",
        "/nodes/pve-brain/%2e%2e/x",
        "/nodes/pve-brain/qemu/110/vncwebsocket",
        "/nodes/pve-brain/termproxy",
        "/nodes/pve-brain/scan/nfs",
        "/access/ticket",
        "/nodes/pve brain",
        "/nodes/pve-brain?x=1",
    ],
)
def test_rejects_bad_paths(path):
    with pytest.raises(ProxmoxError):
        check_path(path)


def test_accepts_normal_paths():
    assert check_path("nodes/pve-brain/status") == "/nodes/pve-brain/status"


def test_unconfigured_refuses():
    client = ReadOnlyProxmox("https://x/api2/json", None, None, session=FakeSession())
    with pytest.raises(ProxmoxError, match="PVE_TOKEN"):
        client.get("/version")


def test_http_error_does_not_leak_secret():
    s = FakeSession({"/version": FakeResponse(401, {})})
    client = ReadOnlyProxmox("https://x/api2/json", "root@pam!mcp", "s3cr3t", session=s)
    with pytest.raises(ProxmoxError) as exc:
        client.get("/version")
    assert "s3cr3t" not in str(exc.value)


def test_guest_ref(pve):
    assert pve.guest_ref(103) == ("pve-worker", "lxc")
    with pytest.raises(ProxmoxError):
        pve.guest_ref(999)


def test_upid_is_encoded():
    upid = "UPID:pve-brain:00001:00002:6700:vzdump::root@pam!mcp:"
    assert "%3A" in ReadOnlyProxmox.upid(upid)
    assert check_path(f"/nodes/pve-brain/tasks/{ReadOnlyProxmox.upid(upid)}/log")
    with pytest.raises(ProxmoxError):
        ReadOnlyProxmox.upid("../../x")
