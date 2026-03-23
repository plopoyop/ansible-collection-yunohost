"""Unit tests for the plopoyop.yunohost.yunohost_postinstall module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
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
    """Exception to capture exit_json (inherits from SystemExit so it is not
    caught by 'except Exception' blocks)."""

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


BASE_ARGS = {
    "domain": "example.com",
    "username": "admin",
    "fullname": "Admin User",
    "password": "S3cure!Pass",
}


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules and return them."""
    mock_pkg = MagicMock()
    mock_tools = MagicMock()
    mock_pkg.tools = mock_tools

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.tools": mock_tools,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_pkg


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module, then return it."""
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_postinstall"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_postinstall as mod

    return mod


def _run_module(mock_pkg, args, installed=False):
    """Set up mocks and execute the module."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    # Mock os.path.isfile to control the "is installed" check
    original_isfile = os.path.isfile
    mod.os.path.isfile = lambda p: (
        installed if p == mod.YUNOHOST_INSTALLED_MARKER else original_isfile(p)
    )
    mod.main()


# ---------------------------------------------------------------------------
# Successful postinstall
# ---------------------------------------------------------------------------


class TestPostinstall:
    def test_run_postinstall(self, mock_yunohost, ansible_module):
        """Run postinstall on a fresh system."""
        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_yunohost, BASE_ARGS, installed=False)

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["installed"] is True
        assert data["domain"] == "example.com"
        assert data["username"] == "admin"
        mock_yunohost.tools.tools_postinstall.assert_called_once_with(
            domain="example.com",
            username="admin",
            fullname="Admin User",
            password="S3cure!Pass",
            ignore_dyndns=False,
            force_diskspace=False,
            overwrite_root_password=True,
        )

    def test_postinstall_with_options(self, mock_yunohost, ansible_module):
        """Run postinstall with optional flags enabled."""
        args = {
            **BASE_ARGS,
            "ignore_dyndns": True,
            "force_diskspace": True,
            "overwrite_root_password": False,
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_yunohost, args, installed=False)

        data = result.value.args[0]
        assert data["changed"] is True
        mock_yunohost.tools.tools_postinstall.assert_called_once_with(
            domain="example.com",
            username="admin",
            fullname="Admin User",
            password="S3cure!Pass",
            ignore_dyndns=True,
            force_diskspace=True,
            overwrite_root_password=False,
        )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_already_installed(self, mock_yunohost, ansible_module):
        """No change if YunoHost is already installed."""
        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_yunohost, BASE_ARGS, installed=True)

        data = result.value.args[0]
        assert data["changed"] is False
        assert data["installed"] is True
        mock_yunohost.tools.tools_postinstall.assert_not_called()


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_not_installed(self, mock_yunohost, ansible_module):
        """In check_mode on a fresh system, report changed without acting."""
        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_yunohost,
                {**BASE_ARGS, "_ansible_check_mode": True},
                installed=False,
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["installed"] is False
        mock_yunohost.tools.tools_postinstall.assert_not_called()

    def test_check_mode_already_installed(self, mock_yunohost, ansible_module):
        """In check_mode on an installed system, report no change."""
        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_yunohost,
                {**BASE_ARGS, "_ansible_check_mode": True},
                installed=True,
            )

        data = result.value.args[0]
        assert data["changed"] is False
        assert data["installed"] is True
        mock_yunohost.tools.tools_postinstall.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_postinstall_failure(self, mock_yunohost, ansible_module):
        """fail_json when tools_postinstall raises an exception."""
        mock_yunohost.tools.tools_postinstall.side_effect = Exception(
            "postinstall_low_rootfsspace"
        )

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(mock_yunohost, BASE_ARGS, installed=False)

        data = result.value.args[0]
        assert data["failed"] is True
        assert "postinstall_low_rootfsspace" in data["msg"]
        assert data["domain"] == "example.com"

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed on the system."""
        set_module_args(BASE_ARGS)
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
