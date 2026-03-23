"""Unit tests for the plopoyop.yunohost.yunohost_permission module."""

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


PERM_NEXTCLOUD_MAIN = {
    "label": "Nextcloud",
    "allowed": ["all_users"],
    "corresponding_users": ["admin", "john"],
    "url": "/",
    "show_tile": True,
    "protected": False,
    "auth_header": True,
    "additional_urls": [],
}

PERM_WORDPRESS_MAIN = {
    "label": "WordPress",
    "allowed": ["admins"],
    "corresponding_users": ["admin"],
    "url": "/",
    "show_tile": True,
    "protected": False,
    "auth_header": True,
    "additional_urls": [],
}


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules."""
    mock_pkg = MagicMock()
    mock_perm = MagicMock()
    mock_pkg.permission = mock_perm

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.permission": mock_perm,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_perm


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module."""
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_permission"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_permission as mod

    return mod


def _run_module(mock_perm, args):
    """Set up mocks and execute the module."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    mod.main()


# ---------------------------------------------------------------------------
# Change allowed
# ---------------------------------------------------------------------------


class TestChangeAllowed:
    def test_add_group(self, mock_yunohost, ansible_module):
        """Add visitors to make an app public."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)
        mock_perm.user_permission_update.return_value = {
            **PERM_NEXTCLOUD_MAIN,
            "allowed": ["all_users", "visitors"],
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["all_users", "visitors"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "visitors" in data["allowed"]
        assert "visitors" in data["changed_details"]["added"]
        mock_perm.user_permission_update.assert_called_once()

    def test_remove_group(self, mock_yunohost, ansible_module):
        """Restrict app to admins only."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)
        mock_perm.user_permission_update.return_value = {
            **PERM_NEXTCLOUD_MAIN,
            "allowed": ["admins"],
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud",
                    "allowed": ["admins"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "all_users" in data["changed_details"]["removed"]
        assert "admins" in data["changed_details"]["added"]

    def test_replace_allowed(self, mock_yunohost, ansible_module):
        """Replace the entire allowed list."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_WORDPRESS_MAIN)
        mock_perm.user_permission_update.return_value = {
            **PERM_WORDPRESS_MAIN,
            "allowed": ["all_users", "visitors"],
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "wordpress.main",
                    "allowed": ["all_users", "visitors"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        kwargs = mock_perm.user_permission_update.call_args[1]
        assert "all_users" in kwargs["add"]
        assert "visitors" in kwargs["add"]
        assert "admins" in kwargs["remove"]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_no_change_when_matching(self, mock_yunohost, ansible_module):
        """No change when allowed list already matches."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["all_users"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_perm.user_permission_update.assert_not_called()

    def test_auto_append_main(self, mock_yunohost, ansible_module):
        """'.main' is appended automatically when no dot in name."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud",
                    "allowed": ["all_users"],
                },
            )

        data = result.value.args[0]
        assert data["permission"] == "nextcloud.main"
        assert data["changed"] is False

    def test_order_independent(self, mock_yunohost, ansible_module):
        """Allowed list comparison is order-independent."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = {
            **PERM_NEXTCLOUD_MAIN,
            "allowed": ["admins", "all_users"],
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["all_users", "admins"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False


# ---------------------------------------------------------------------------
# Attributes (label, show_tile, protected)
# ---------------------------------------------------------------------------


class TestAttributes:
    def test_change_label(self, mock_yunohost, ansible_module):
        """Change the display label of a permission."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)
        mock_perm.user_permission_update.return_value = {
            **PERM_NEXTCLOUD_MAIN,
            "label": "My Cloud",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["all_users"],
                    "label": "My Cloud",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        kwargs = mock_perm.user_permission_update.call_args[1]
        assert kwargs["label"] == "My Cloud"

    def test_change_show_tile(self, mock_yunohost, ansible_module):
        """Change show_tile without changing allowed."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)
        mock_perm.user_permission_update.return_value = {
            **PERM_NEXTCLOUD_MAIN,
            "show_tile": False,
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["all_users"],
                    "show_tile": False,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_change(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without applying."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["visitors", "all_users"],
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_perm.user_permission_update.assert_not_called()

    def test_check_mode_no_change(self, mock_yunohost, ansible_module):
        """In check_mode, no change when already matching."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.return_value = dict(PERM_NEXTCLOUD_MAIN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nextcloud.main",
                    "allowed": ["all_users"],
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_permission_not_found(self, mock_yunohost, ansible_module):
        """fail_json when permission does not exist."""
        mock_perm = mock_yunohost
        mock_perm.user_permission_info.side_effect = Exception("permission_not_found")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_perm,
                {
                    "name": "nonexistent.main",
                    "allowed": ["all_users"],
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "permission_not_found" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"name": "nextcloud", "allowed": ["all_users"]})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
