"""Unit tests for the plopoyop.yunohost.yunohost_settings module."""

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


# Values indexed by option_id for easy lookup
SETTING_VALUES = {
    "ssh_port": 22,
    "ssh_password_authentication": 1,
    "ssh_compatibility": "modern",
    "admin_strength": 1,
    "nginx_redirect_to_https": 1,
    "smtp_relay_enabled": 0,
    "smtp_relay_host": "",
}

# Full mode panel structure (for key path map building)
FULL_CONFIG = {
    "panels": [
        {
            "id": "security",
            "sections": [
                {
                    "id": "password",
                    "options": [{"id": "admin_strength", "type": "select"}],
                },
                {
                    "id": "ssh",
                    "options": [
                        {"id": "ssh_port", "type": "number"},
                        {"id": "ssh_password_authentication", "type": "boolean"},
                        {"id": "ssh_compatibility", "type": "select"},
                    ],
                },
                {
                    "id": "nginx",
                    "options": [{"id": "nginx_redirect_to_https", "type": "boolean"}],
                },
            ],
        },
        {
            "id": "email",
            "sections": [
                {
                    "id": "smtp",
                    "options": [
                        {"id": "smtp_relay_enabled", "type": "boolean"},
                        {"id": "smtp_relay_host", "type": "string"},
                    ],
                },
            ],
        },
    ],
}

# Map full key path -> option_id (derived from FULL_CONFIG)
KEY_TO_OPTION = {
    "security.password.admin_strength": "admin_strength",
    "security.ssh.ssh_port": "ssh_port",
    "security.ssh.ssh_password_authentication": "ssh_password_authentication",
    "security.ssh.ssh_compatibility": "ssh_compatibility",
    "security.nginx.nginx_redirect_to_https": "nginx_redirect_to_https",
    "email.smtp.smtp_relay_enabled": "smtp_relay_enabled",
    "email.smtp.smtp_relay_host": "smtp_relay_host",
}


def _mock_settings_get(values=None, key=None, **kwargs):
    """Mock settings_get that handles per-key queries."""
    if values is None:
        values = SETTING_VALUES
    if key:
        option_id = KEY_TO_OPTION.get(key, key)
        return values.get(option_id)
    return {}


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules."""
    mock_pkg = MagicMock()
    mock_settings = MagicMock()
    mock_pkg.settings = mock_settings

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.settings": mock_settings,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_settings


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module."""
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_settings"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_settings as mod

    return mod


MOCK_KEY_PATH_MAP = {v: k for k, v in KEY_TO_OPTION.items()}


def _run_module(mock_settings, args, values=None):
    """Set up mocks and execute the module."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    mod._build_key_path_map = MagicMock(return_value=MOCK_KEY_PATH_MAP)
    if values is None:
        values = dict(SETTING_VALUES)
    mock_settings.settings_get.side_effect = lambda **kw: _mock_settings_get(
        values=values, **kw
    )
    mod.main()


# ---------------------------------------------------------------------------
# Apply settings
# ---------------------------------------------------------------------------


class TestApplySettings:
    def test_change_single_setting(self, mock_yunohost, ansible_module):
        """Change one setting that differs from current state."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_settings, {"settings": {"ssh_port": 2222}})

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["changed_settings"]["ssh_port"]["before"] == 22
        assert data["changed_settings"]["ssh_port"]["after"] == 2222
        mock_settings.settings_set.assert_called_once()
        assert "ssh_port=2222" in mock_settings.settings_set.call_args[1]["args"]

    def test_change_multiple_settings(self, mock_yunohost, ansible_module):
        """Change multiple settings at once."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"ssh_port": 2222, "smtp_relay_enabled": True},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "ssh_port" in data["changed_settings"]
        assert "smtp_relay_enabled" in data["changed_settings"]
        mock_settings.settings_set.assert_called_once()
        call_args = mock_settings.settings_set.call_args[1]["args"]
        assert "ssh_port=2222" in call_args
        assert "smtp_relay_enabled=1" in call_args


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_no_change_when_settings_match(self, mock_yunohost, ansible_module):
        """No change when desired settings already match current state."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"ssh_port": 22, "admin_strength": 1},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        assert data["changed_settings"] == {}
        mock_settings.settings_set.assert_not_called()

    def test_bool_normalization(self, mock_yunohost, ansible_module):
        """Boolean True/False are normalized to 1/0 for comparison."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"nginx_redirect_to_https": True},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_settings.settings_set.assert_not_called()

    def test_partial_change(self, mock_yunohost, ansible_module):
        """Only changed settings are applied, unchanged are skipped."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"ssh_port": 22, "ssh_compatibility": "intermediate"},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "ssh_port" not in data["changed_settings"]
        assert "ssh_compatibility" in data["changed_settings"]
        mock_settings.settings_set.assert_called_once()
        assert (
            "ssh_compatibility=intermediate"
            in mock_settings.settings_set.call_args[1]["args"]
        )


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_with_changes(self, mock_yunohost, ansible_module):
        """In check_mode, report what would change without applying."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"ssh_port": 2222},
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "ssh_port" in data["changed_settings"]
        mock_settings.settings_set.assert_not_called()

    def test_check_mode_no_changes(self, mock_yunohost, ansible_module):
        """In check_mode with no changes needed, report no change."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"ssh_port": 22},
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_settings.settings_set.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_unknown_setting_key(self, mock_yunohost, ansible_module):
        """fail_json when an unknown setting key is provided."""
        mock_settings = mock_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"nonexistent_option": "value"},
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Unknown setting" in data["msg"]
        assert "nonexistent_option" in data["msg"]

    def test_settings_set_failure(self, mock_yunohost, ansible_module):
        """fail_json when settings_set raises an exception."""
        mock_settings = mock_yunohost
        mock_settings.settings_set.side_effect = Exception("Invalid value")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_settings,
                {
                    "settings": {"ssh_port": -1},
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Invalid value" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"settings": {"ssh_port": 22}})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
