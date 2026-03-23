"""Unit tests for the plopoyop.yunohost.yunohost_app module."""

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


APP_NEXTCLOUD = {
    "id": "nextcloud",
    "name": "Nextcloud",
    "description": "Cloud storage",
    "version": "1.0~ynh1",
    "domain_path": "cloud.example.com/",
}

APP_WORDPRESS = {
    "id": "wordpress",
    "name": "WordPress",
    "description": "Blog",
    "version": "2.0~ynh1",
    "domain_path": "blog.example.com/",
}


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules."""
    mock_pkg = MagicMock()
    mock_app = MagicMock()
    mock_pkg.app = mock_app

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.app": mock_app,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_app


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module."""
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_app"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_app as mod

    return mod


def _run_module(mock_app, args, installed_apps=None):
    """Set up mocks and execute the module."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())

    if installed_apps is None:
        installed_apps = []
    mock_app.app_list.return_value = {"apps": installed_apps}
    mod.main()


# ---------------------------------------------------------------------------
# state=present — install
# ---------------------------------------------------------------------------


class TestAppInstall:
    def test_install_new_app(self, mock_yunohost, ansible_module):
        """Install an app with domain/path as dedicated parameters."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = dict(APP_NEXTCLOUD)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "cloud.example.com",
                    "path": "/",
                    "args": {"admin": "admin"},
                },
                installed_apps=[],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["app"] == "nextcloud"
        call_args = mock_app.app_install.call_args[1]["args"]
        assert "domain=cloud.example.com" in call_args
        assert "admin=admin" in call_args

    def test_install_with_string_args(self, mock_yunohost, ansible_module):
        """Install with all args as a query string (backward compatible)."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = dict(APP_NEXTCLOUD)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "args": "domain=cloud.example.com&path=/&admin=admin",
                },
                installed_apps=[],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        call_args = mock_app.app_install.call_args[1]["args"]
        assert "domain=cloud.example.com" in call_args

    def test_install_with_label(self, mock_yunohost, ansible_module):
        """Install an app with a custom label."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = dict(APP_WORDPRESS)

        with pytest.raises(AnsibleExitJson):
            _run_module(
                mock_app,
                {
                    "name": "wordpress",
                    "domain": "blog.example.com",
                    "path": "/",
                    "label": "My Blog",
                },
                installed_apps=[],
            )

        mock_app.app_install.assert_called_once()
        assert mock_app.app_install.call_args[1]["label"] == "My Blog"

    def test_domain_path_merged_with_dict_args(self, mock_yunohost, ansible_module):
        """domain and path are merged into the args query string."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = dict(APP_NEXTCLOUD)

        with pytest.raises(AnsibleExitJson):
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "example.com",
                    "path": "/cloud",
                    "args": {"admin": "admin", "language": "en"},
                },
                installed_apps=[],
            )

        call_args = mock_app.app_install.call_args[1]["args"]
        assert "domain=example.com" in call_args
        assert "path=%2Fcloud" in call_args or "path=/cloud" in call_args
        assert "admin=admin" in call_args
        assert "language=en" in call_args

    def test_app_already_installed(self, mock_yunohost, ansible_module):
        """No change when app is already installed."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is False
        assert data["app_info"]["id"] == "nextcloud"
        mock_app.app_install.assert_not_called()

    def test_change_url_domain(self, mock_yunohost, ansible_module):
        """Change the domain of an installed app."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = {
            **APP_NEXTCLOUD,
            "domain_path": "new.example.com/",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "new.example.com",
                    "path": "/",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_change_url.assert_called_once_with(
            app="nextcloud",
            domain="new.example.com",
            path="/",
        )
        mock_app.app_install.assert_not_called()

    def test_change_url_path(self, mock_yunohost, ansible_module):
        """Change the path of an installed app."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = {
            **APP_NEXTCLOUD,
            "domain_path": "cloud.example.com/cloud",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "cloud.example.com",
                    "path": "/cloud",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_change_url.assert_called_once_with(
            app="nextcloud",
            domain="cloud.example.com",
            path="/cloud",
        )

    def test_no_change_same_url(self, mock_yunohost, ansible_module):
        """No change when domain and path match current state."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "cloud.example.com",
                    "path": "/",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_app.app_change_url.assert_not_called()

    def test_check_mode_change_url(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without calling app_change_url."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "new.example.com",
                    "path": "/",
                    "_ansible_check_mode": True,
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_change_url.assert_not_called()


# ---------------------------------------------------------------------------
# state=absent — remove
# ---------------------------------------------------------------------------


class TestAppRemove:
    def test_remove_installed_app(self, mock_yunohost, ansible_module):
        """Remove an installed app."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "wordpress",
                    "state": "absent",
                },
                installed_apps=[APP_WORDPRESS],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_remove.assert_called_once_with(
            app="wordpress",
            purge=False,
        )

    def test_remove_nonexistent_app(self, mock_yunohost, ansible_module):
        """No change when app is not installed."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "ghost",
                    "state": "absent",
                },
                installed_apps=[],
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_app.app_remove.assert_not_called()

    def test_remove_with_purge(self, mock_yunohost, ansible_module):
        """Remove an app with data purge."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson):
            _run_module(
                mock_app,
                {
                    "name": "wordpress",
                    "state": "absent",
                    "purge": True,
                },
                installed_apps=[APP_WORDPRESS],
            )

        mock_app.app_remove.assert_called_once_with(
            app="wordpress",
            purge=True,
        )


# ---------------------------------------------------------------------------
# state=latest — upgrade
# ---------------------------------------------------------------------------


class TestAppUpgrade:
    def test_upgrade_available(self, mock_yunohost, ansible_module):
        """Upgrade an app when an update is available."""
        mock_app = mock_yunohost
        mock_app.app_info.side_effect = [
            {**APP_NEXTCLOUD, "upgrade": {"available": True}},  # upgrade check
            {**APP_NEXTCLOUD, "version": "1.1~ynh1"},  # final info
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "latest",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_upgrade.assert_called_once_with(
            app="nextcloud",
            force=False,
            no_safety_backup=False,
            ignore_yunohost_version=False,
        )

    def test_no_upgrade_available(self, mock_yunohost, ansible_module):
        """No change when app is already up to date."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = {
            **APP_NEXTCLOUD,
            "upgrade": {"available": False},
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "latest",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_app.app_upgrade.assert_not_called()

    def test_latest_installs_if_missing(self, mock_yunohost, ansible_module):
        """state=latest installs the app if not already installed."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = dict(APP_NEXTCLOUD)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "latest",
                    "domain": "cloud.example.com",
                    "path": "/",
                    "args": {"admin": "admin"},
                },
                installed_apps=[],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_install.assert_called_once()
        mock_app.app_upgrade.assert_not_called()

    def test_force_upgrade(self, mock_yunohost, ansible_module):
        """Force upgrade even when no update is detected."""
        mock_app = mock_yunohost
        mock_app.app_info.side_effect = [
            {**APP_NEXTCLOUD, "upgrade": {"available": False}},
            {**APP_NEXTCLOUD, "version": "1.0~ynh1"},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "latest",
                    "force": True,
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_upgrade.assert_called_once()


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_install(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without installing."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "domain": "cloud.example.com",
                    "path": "/",
                    "_ansible_check_mode": True,
                },
                installed_apps=[],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_install.assert_not_called()

    def test_check_mode_remove(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without removing."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "absent",
                    "_ansible_check_mode": True,
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_remove.assert_not_called()

    def test_check_mode_upgrade(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without upgrading."""
        mock_app = mock_yunohost
        mock_app.app_info.return_value = {
            **APP_NEXTCLOUD,
            "upgrade": {"available": True},
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "latest",
                    "_ansible_check_mode": True,
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_app.app_upgrade.assert_not_called()

    def test_check_mode_no_change(self, mock_yunohost, ansible_module):
        """In check_mode, no change when already in desired state."""
        mock_app = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "_ansible_check_mode": True,
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["changed"] is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_install_failure(self, mock_yunohost, ansible_module):
        """fail_json when app_install raises an exception."""
        mock_app = mock_yunohost
        mock_app.app_install.side_effect = Exception("App install failed")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "broken_app",
                    "domain": "example.com",
                    "path": "/",
                },
                installed_apps=[],
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "App install failed" in data["msg"]

    def test_remove_failure(self, mock_yunohost, ansible_module):
        """fail_json when app_remove raises an exception."""
        mock_app = mock_yunohost
        mock_app.app_remove.side_effect = Exception("Cannot remove")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_app,
                {
                    "name": "nextcloud",
                    "state": "absent",
                },
                installed_apps=[APP_NEXTCLOUD],
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Cannot remove" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"name": "nextcloud"})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
