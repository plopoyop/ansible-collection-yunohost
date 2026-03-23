"""Unit tests for the plopoyop.yunohost.yunohost_firewall module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import sys
from unittest.mock import MagicMock

import pytest

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


def set_module_args(args):
    """Prepare arguments for AnsibleModule (compatible with Ansible >= 2.20)."""
    args_json = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(args_json)
    basic._ANSIBLE_PROFILE = "legacy"


class AnsibleExitJson(SystemExit):
    """Exception to capture exit_json."""

    pass


class AnsibleFailJson(SystemExit):
    """Exception to capture fail_json."""

    pass


def exit_json(*args, **kwargs):
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules."""
    mock_pkg = MagicMock()
    mock_firewall = MagicMock()
    mock_pkg.firewall = mock_firewall

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.firewall": mock_firewall,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_firewall


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module."""
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_firewall"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_firewall as mod

    return mod


def _mock_firewall_list(open_tcp=None, open_udp=None):
    """Create a mock firewall_list function with configurable open ports."""
    open_tcp = open_tcp if open_tcp is not None else [22, 80, 443]
    open_udp = open_udp if open_udp is not None else []

    def mock_list(raw=False, protocol="tcp", forwarded=False):
        if raw:
            return {}
        if protocol == "tcp":
            return {"tcp": list(open_tcp)}
        return {"udp": list(open_udp)}

    return mock_list


def _run_module(mock_fw, args, open_tcp=None, open_udp=None):
    """Set up mocks and execute the module."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    mock_fw.firewall_list.side_effect = _mock_firewall_list(open_tcp, open_udp)
    mod.main()


# ---------------------------------------------------------------------------
# state=open
# ---------------------------------------------------------------------------


class TestOpenPort:
    def test_open_new_port(self, mock_yunohost, ansible_module):
        """Open a port that is currently closed."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 8080,
                    "protocol": "tcp",
                    "comment": "My app",
                },
                open_tcp=[22, 80, 443],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["port"] == 8080
        mock_fw.firewall_open.assert_called_once_with(
            port=8080,
            protocol="tcp",
            comment="My app",
            upnp=False,
            no_reload=True,
        )
        mock_fw.firewall_reload.assert_called_once()

    def test_port_already_open(self, mock_yunohost, ansible_module):
        """No change when port is already open."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 80,
                    "protocol": "tcp",
                    "comment": "HTTP",
                },
                open_tcp=[22, 80, 443],
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_fw.firewall_open.assert_not_called()

    def test_open_port_both_protocols(self, mock_yunohost, ansible_module):
        """Open a port on both TCP and UDP."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 5353,
                    "protocol": "both",
                    "comment": "mDNS",
                },
                open_tcp=[22],
                open_udp=[],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["protocol"] == "both"
        assert mock_fw.firewall_open.call_count == 2

    def test_open_port_with_upnp(self, mock_yunohost, ansible_module):
        """Open a port with UPnP forwarding."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson):
            _run_module(
                mock_fw,
                {
                    "port": 25565,
                    "protocol": "tcp",
                    "comment": "Minecraft",
                    "upnp": True,
                },
                open_tcp=[22],
            )

        mock_fw.firewall_open.assert_called_once_with(
            port=25565,
            protocol="tcp",
            comment="Minecraft",
            upnp=True,
            no_reload=True,
        )

    def test_open_port_range(self, mock_yunohost, ansible_module):
        """Open a port range."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": "8000-8100",
                    "protocol": "tcp",
                    "comment": "App range",
                },
                open_tcp=[22],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["port"] == "8000-8100"
        mock_fw.firewall_open.assert_called_once_with(
            port="8000-8100",
            protocol="tcp",
            comment="App range",
            upnp=False,
            no_reload=True,
        )

    def test_open_port_no_reload(self, mock_yunohost, ansible_module):
        """Open a port without reloading the firewall."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 9090,
                    "protocol": "tcp",
                    "comment": "Test",
                    "no_reload": True,
                },
                open_tcp=[22],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_fw.firewall_open.assert_called_once()
        mock_fw.firewall_reload.assert_not_called()


# ---------------------------------------------------------------------------
# state=closed
# ---------------------------------------------------------------------------


class TestClosePort:
    def test_close_open_port(self, mock_yunohost, ansible_module):
        """Close a port that is currently open."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 8080,
                    "protocol": "tcp",
                    "state": "closed",
                },
                open_tcp=[22, 80, 8080],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_fw.firewall_close.assert_called_once_with(
            port=8080,
            protocol="tcp",
            no_reload=True,
        )
        mock_fw.firewall_reload.assert_called_once()

    def test_close_already_closed(self, mock_yunohost, ansible_module):
        """No change when port is already closed."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 9999,
                    "protocol": "tcp",
                    "state": "closed",
                },
                open_tcp=[22, 80],
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_fw.firewall_close.assert_not_called()

    def test_close_both_protocols(self, mock_yunohost, ansible_module):
        """Close a port on both TCP and UDP."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 5353,
                    "protocol": "both",
                    "state": "closed",
                },
                open_tcp=[22, 5353],
                open_udp=[5353],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert mock_fw.firewall_close.call_count == 2


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_open(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without opening."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 9090,
                    "protocol": "tcp",
                    "comment": "Test",
                    "_ansible_check_mode": True,
                },
                open_tcp=[22],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_fw.firewall_open.assert_not_called()
        mock_fw.firewall_reload.assert_not_called()

    def test_check_mode_close(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without closing."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 80,
                    "protocol": "tcp",
                    "state": "closed",
                    "_ansible_check_mode": True,
                },
                open_tcp=[22, 80],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_fw.firewall_close.assert_not_called()

    def test_check_mode_no_change(self, mock_yunohost, ansible_module):
        """In check_mode, no change when already in desired state."""
        mock_fw = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 80,
                    "protocol": "tcp",
                    "comment": "HTTP",
                    "_ansible_check_mode": True,
                },
                open_tcp=[22, 80],
            )

        data = result.value.args[0]
        assert data["changed"] is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_open_failure(self, mock_yunohost, ansible_module):
        """fail_json when firewall_open raises an exception."""
        mock_fw = mock_yunohost
        mock_fw.firewall_open.side_effect = Exception("nftables error")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_fw,
                {
                    "port": 9090,
                    "protocol": "tcp",
                    "comment": "Test",
                },
                open_tcp=[22],
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "nftables" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"port": 80})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
