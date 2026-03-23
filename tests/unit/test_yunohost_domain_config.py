"""Unit tests for the plopoyop.yunohost.yunohost_domain_config module."""

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


# Export mode: flat option_id -> value
CURRENT_SETTINGS = {
    "mail_in": 1,
    "mail_out": 1,
    "default_app": "_none",
    "portal_title": "YunoHost",
    "portal_theme": "system",
    "portal_tile_theme": "simple",
    "enable_public_apps_page": 0,
    "show_other_domains_apps": 1,
}

# Full mode: structured panel config (used to build option_id -> full key path mapping)
FULL_CONFIG = {
    "panels": [
        {
            "id": "feature",
            "sections": [
                {
                    "id": "mail",
                    "options": [
                        {"id": "mail_in", "type": "boolean"},
                        {"id": "mail_out", "type": "boolean"},
                    ],
                },
                {
                    "id": "app",
                    "options": [
                        {"id": "default_app", "type": "app"},
                    ],
                },
                {
                    "id": "portal",
                    "options": [
                        {"id": "portal_title", "type": "string"},
                        {"id": "portal_theme", "type": "select"},
                        {"id": "portal_tile_theme", "type": "select"},
                        {"id": "enable_public_apps_page", "type": "boolean"},
                        {"id": "show_other_domains_apps", "type": "boolean"},
                    ],
                },
            ],
        },
    ],
}


# Subdomain full config: no portal section
FULL_CONFIG_SUBDOMAIN = {
    "panels": [
        {
            "id": "feature",
            "sections": [
                {
                    "id": "mail",
                    "options": [
                        {"id": "mail_in", "type": "boolean"},
                        {"id": "mail_out", "type": "boolean"},
                    ],
                },
                {
                    "id": "app",
                    "options": [
                        {"id": "default_app", "type": "app"},
                    ],
                },
            ],
        },
    ],
}

CURRENT_SETTINGS_SUBDOMAIN = {
    "mail_in": 1,
    "mail_out": 1,
    "default_app": "_none",
}


def _mock_config_get(domain, export=False, full=False, **kwargs):
    """Default mock for domain_config_get that handles export and full modes."""
    if export:
        return dict(CURRENT_SETTINGS)
    if full:
        return dict(FULL_CONFIG)
    return {}


def _mock_config_get_subdomain(domain, export=False, full=False, **kwargs):
    """Mock for a subdomain where portal settings are not available."""
    if export:
        return dict(CURRENT_SETTINGS_SUBDOMAIN)
    if full:
        return dict(FULL_CONFIG_SUBDOMAIN)
    return {}


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules."""
    mock_pkg = MagicMock()
    mock_domain = MagicMock()
    mock_pkg.domain = mock_domain

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.domain": mock_domain,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_domain


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module."""
    fqcn = (
        "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_domain_config"
    )
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_domain_config as mod

    return mod


def _run_module(mock_domain, args):
    """Set up mocks and execute the module with the given args."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    mod.main()


# ---------------------------------------------------------------------------
# Apply settings
# ---------------------------------------------------------------------------


class TestApplySettings:
    def test_change_single_setting(self, mock_yunohost, ansible_module):
        """Change one setting that differs from current state."""
        mock_domain = mock_yunohost
        call_count = [0]
        final_settings = {**CURRENT_SETTINGS, "mail_in": 0}

        def mock_get(domain, export=False, full=False, **kwargs):
            call_count[0] += 1
            if full:
                return dict(FULL_CONFIG)
            if export and call_count[0] <= 2:
                return dict(CURRENT_SETTINGS)
            if export:
                return final_settings
            return {}

        mock_domain.domain_config_get.side_effect = mock_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": False},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "mail_in" in data["changed_settings"]
        assert data["changed_settings"]["mail_in"]["before"] == 1
        assert data["changed_settings"]["mail_in"]["after"] == 0
        mock_domain.domain_config_set.assert_called_once_with(
            domain="example.com",
            key="feature.mail.mail_in",
            value=0,
        )

    def test_change_multiple_settings(self, mock_yunohost, ansible_module):
        """Change multiple settings at once."""
        mock_domain = mock_yunohost
        call_count = [0]

        def mock_get(domain, export=False, full=False, **kwargs):
            call_count[0] += 1
            if full:
                return dict(FULL_CONFIG)
            if export and call_count[0] <= 2:
                return dict(CURRENT_SETTINGS)
            if export:
                return {**CURRENT_SETTINGS, "mail_in": 0, "portal_theme": "dark"}
            return {}

        mock_domain.domain_config_get.side_effect = mock_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": False, "portal_theme": "dark"},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "mail_in" in data["changed_settings"]
        assert "portal_theme" in data["changed_settings"]
        assert mock_domain.domain_config_set.call_count == 2

    def test_change_string_setting(self, mock_yunohost, ansible_module):
        """Change a string setting."""
        mock_domain = mock_yunohost
        call_count = [0]

        def mock_get(domain, export=False, full=False, **kwargs):
            call_count[0] += 1
            if full:
                return dict(FULL_CONFIG)
            if export and call_count[0] <= 2:
                return dict(CURRENT_SETTINGS)
            if export:
                return {**CURRENT_SETTINGS, "portal_title": "My Server"}
            return {}

        mock_domain.domain_config_get.side_effect = mock_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"portal_title": "My Server"},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["changed_settings"]["portal_title"]["before"] == "YunoHost"
        assert data["changed_settings"]["portal_title"]["after"] == "My Server"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_no_change_when_settings_match(self, mock_yunohost, ansible_module):
        """No change when desired settings already match current state."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": True, "mail_out": True},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        assert data["changed_settings"] == {}
        mock_domain.domain_config_set.assert_not_called()

    def test_bool_normalization(self, mock_yunohost, ansible_module):
        """Boolean True/False are normalized to 1/0 for comparison."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"enable_public_apps_page": False},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_domain.domain_config_set.assert_not_called()

    def test_partial_change(self, mock_yunohost, ansible_module):
        """Only actually changed settings are applied, unchanged ones are skipped."""
        mock_domain = mock_yunohost
        call_count = [0]

        def mock_get(domain, export=False, full=False, **kwargs):
            call_count[0] += 1
            if full:
                return dict(FULL_CONFIG)
            if export and call_count[0] <= 2:
                return dict(CURRENT_SETTINGS)
            if export:
                return {**CURRENT_SETTINGS, "portal_theme": "dark"}
            return {}

        mock_domain.domain_config_get.side_effect = mock_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": True, "portal_theme": "dark"},
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "mail_in" not in data["changed_settings"]
        assert "portal_theme" in data["changed_settings"]
        mock_domain.domain_config_set.assert_called_once_with(
            domain="example.com",
            key="feature.portal.portal_theme",
            value="dark",
        )


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_with_changes(self, mock_yunohost, ansible_module):
        """In check_mode, report what would change without applying."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": False},
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "mail_in" in data["changed_settings"]
        mock_domain.domain_config_set.assert_not_called()

    def test_check_mode_no_changes(self, mock_yunohost, ansible_module):
        """In check_mode with no changes needed, report no change."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": True},
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_domain.domain_config_set.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_config_set_failure(self, mock_yunohost, ansible_module):
        """fail_json when domain_config_set raises an exception."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get
        mock_domain.domain_config_set.side_effect = Exception(
            "Invalid value for mail_in"
        )

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"mail_in": False},
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Invalid value" in data["msg"]

    def test_config_get_failure(self, mock_yunohost, ansible_module):
        """fail_json when domain_config_get raises an exception."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = Exception("domain_unknown")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "nonexistent.tld",
                    "settings": {"mail_in": False},
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "domain_unknown" in data["msg"]

    def test_unknown_setting_key(self, mock_yunohost, ansible_module):
        """fail_json when an unknown setting key is provided."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "example.com",
                    "settings": {"nonexistent_option": "value"},
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Unknown setting" in data["msg"]
        assert "nonexistent_option" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"name": "test.tld", "settings": {"mail_in": False}})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]


# ---------------------------------------------------------------------------
# ignore_unavailable
# ---------------------------------------------------------------------------


class TestIgnoreUnavailable:
    def test_skip_unavailable_settings(self, mock_yunohost, ansible_module):
        """With ignore_unavailable, skip settings not available on subdomains."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get_subdomain

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "sub.example.com",
                    "settings": {"mail_in": False, "portal_title": "My Server"},
                    "ignore_unavailable": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert "mail_in" in data["changed_settings"]
        assert "portal_title" not in data["changed_settings"]
        assert "portal_title" in data["skipped_settings"]

    def test_all_settings_unavailable(self, mock_yunohost, ansible_module):
        """No change when all requested settings are unavailable."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get_subdomain

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "sub.example.com",
                    "settings": {"portal_title": "My Server", "portal_theme": "dark"},
                    "ignore_unavailable": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        assert data["skipped_settings"] == ["portal_title", "portal_theme"]
        mock_domain.domain_config_set.assert_not_called()

    def test_fail_without_ignore_unavailable(self, mock_yunohost, ansible_module):
        """Without ignore_unavailable, fail on unavailable settings."""
        mock_domain = mock_yunohost
        mock_domain.domain_config_get.side_effect = _mock_config_get_subdomain

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "sub.example.com",
                    "settings": {"portal_title": "My Server"},
                },
            )

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Unknown setting" in data["msg"]
