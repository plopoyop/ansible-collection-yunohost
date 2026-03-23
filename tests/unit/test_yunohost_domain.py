"""Unit tests for the plopoyop.yunohost.yunohost_domain module."""

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


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules and return the mocked domain module."""
    mock_domain = MagicMock()
    mock_yunohost_pkg = MagicMock()
    mock_yunohost_pkg.domain = mock_domain

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_yunohost_pkg,
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
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_domain"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_domain as mod

    return mod


def _run_module(mock_domain, args):
    """Set up mocks and execute the module with the given args."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    mod.main()


# ---------------------------------------------------------------------------
# state=present
# ---------------------------------------------------------------------------


class TestDomainPresent:
    def test_add_new_domain(self, mock_yunohost, ansible_module):
        """Add a domain that does not exist yet."""
        mock_domain = mock_yunohost

        # 1st call: domain_exists -> not found. 2nd call: final get_domain_info.
        mock_domain.domain_list.side_effect = [
            {"domains": ["existing.tld"], "main": "existing.tld"},  # domain_exists
            {
                "domains": ["existing.tld", "new.tld"],
                "main": "existing.tld",
            },  # get_domain_info
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_domain, {"name": "new.tld", "state": "present"})

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["domain"] == "new.tld"
        assert "new.tld" in data["domains"]
        mock_domain.domain_add.assert_called_once_with(
            domain="new.tld",
            install_letsencrypt_cert=False,
            ignore_dyndns=False,
        )

    def test_domain_already_exists(self, mock_yunohost, ansible_module):
        """No change if the domain already exists."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {
            "domains": ["example.com"],
            "main": "example.com",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_domain, {"name": "example.com", "state": "present"})

        data = result.value.args[0]
        assert data["changed"] is False
        mock_domain.domain_add.assert_not_called()

    def test_add_domain_with_letsencrypt(self, mock_yunohost, ansible_module):
        """Add a domain with a Let's Encrypt certificate."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.side_effect = [
            {"domains": [], "main": "main.tld"},
            {"domains": [], "main": "main.tld"},
            {"domains": ["sub.main.tld"], "main": "main.tld"},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "sub.main.tld",
                    "state": "present",
                    "install_letsencrypt_cert": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_domain.domain_add.assert_called_once_with(
            domain="sub.main.tld",
            install_letsencrypt_cert=True,
            ignore_dyndns=False,
        )

    def test_set_main_domain(self, mock_yunohost, ansible_module):
        """Set an existing domain as the main domain."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.side_effect = [
            {"domains": ["a.tld", "b.tld"], "main": "a.tld"},  # exists check
            {"domains": ["a.tld", "b.tld"], "main": "a.tld"},  # main check
            {"domains": ["a.tld", "b.tld"], "main": "b.tld"},  # final
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {"name": "b.tld", "state": "present", "main": True},
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["main"] == "b.tld"
        mock_domain.domain_add.assert_not_called()
        mock_domain.domain_main_domain.assert_called_once_with(new_main_domain="b.tld")

    def test_already_main_domain(self, mock_yunohost, ansible_module):
        """No change if the domain is already the main one."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {
            "domains": ["a.tld"],
            "main": "a.tld",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {"name": "a.tld", "state": "present", "main": True},
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_domain.domain_main_domain.assert_not_called()

    def test_add_and_set_main(self, mock_yunohost, ansible_module):
        """Add a domain AND set it as the main domain."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.side_effect = [
            {"domains": ["old.tld"], "main": "old.tld"},  # exists: not found
            {
                "domains": ["old.tld", "new.tld"],
                "main": "old.tld",
            },  # main check after add
            {"domains": ["old.tld", "new.tld"], "main": "new.tld"},  # final
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {"name": "new.tld", "state": "present", "main": True},
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_domain.domain_add.assert_called_once()
        mock_domain.domain_main_domain.assert_called_once_with(
            new_main_domain="new.tld"
        )


# ---------------------------------------------------------------------------
# state=absent
# ---------------------------------------------------------------------------


class TestDomainAbsent:
    def test_remove_existing_domain(self, mock_yunohost, ansible_module):
        """Remove an existing domain."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.side_effect = [
            {"domains": ["a.tld", "target.tld"], "main": "a.tld"},  # exists check
            {"domains": ["a.tld"], "main": "a.tld"},  # final
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_domain, {"name": "target.tld", "state": "absent"})

        data = result.value.args[0]
        assert data["changed"] is True
        assert "target.tld" not in data["domains"]
        mock_domain.domain_remove.assert_called_once_with(
            domain="target.tld",
            remove_apps=False,
            force=False,
            ignore_dyndns=False,
        )

    def test_remove_nonexistent_domain(self, mock_yunohost, ansible_module):
        """No change if the domain does not exist."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {
            "domains": ["other.tld"],
            "main": "other.tld",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_domain, {"name": "gone.tld", "state": "absent"})

        data = result.value.args[0]
        assert data["changed"] is False
        mock_domain.domain_remove.assert_not_called()

    def test_remove_with_apps(self, mock_yunohost, ansible_module):
        """Remove a domain along with its installed apps."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.side_effect = [
            {"domains": ["a.tld", "b.tld"], "main": "a.tld"},
            {"domains": ["a.tld"], "main": "a.tld"},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "b.tld",
                    "state": "absent",
                    "remove_apps": True,
                    "force": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_domain.domain_remove.assert_called_once_with(
            domain="b.tld",
            remove_apps=True,
            force=True,
            ignore_dyndns=False,
        )

    def test_remove_with_ignore_dyndns(self, mock_yunohost, ansible_module):
        """Remove a DynDNS domain without unsubscribing."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.side_effect = [
            {"domains": ["test.nohost.me"], "main": "other.tld"},
            {"domains": [], "main": "other.tld"},
        ]

        with pytest.raises(AnsibleExitJson):
            _run_module(
                mock_domain,
                {
                    "name": "test.nohost.me",
                    "state": "absent",
                    "ignore_dyndns": True,
                },
            )

        mock_domain.domain_remove.assert_called_once_with(
            domain="test.nohost.me",
            remove_apps=False,
            force=False,
            ignore_dyndns=True,
        )


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_add(self, mock_yunohost, ansible_module):
        """In check_mode, domain_add should not be called."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {"domains": [], "main": "main.tld"}

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {"name": "new.tld", "state": "present", "_ansible_check_mode": True},
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_domain.domain_add.assert_not_called()

    def test_check_mode_remove(self, mock_yunohost, ansible_module):
        """In check_mode, domain_remove should not be called."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {
            "domains": ["target.tld"],
            "main": "other.tld",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {"name": "target.tld", "state": "absent", "_ansible_check_mode": True},
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_domain.domain_remove.assert_not_called()

    def test_check_mode_set_main(self, mock_yunohost, ansible_module):
        """In check_mode, domain_main_domain should not be called."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {
            "domains": ["a.tld", "b.tld"],
            "main": "a.tld",
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_domain,
                {
                    "name": "b.tld",
                    "state": "present",
                    "main": True,
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_domain.domain_main_domain.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_domain_add_failure(self, mock_yunohost, ansible_module):
        """fail_json when domain_add raises an exception."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {"domains": [], "main": "main.tld"}
        mock_domain.domain_add.side_effect = Exception("LDAP error")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(mock_domain, {"name": "fail.tld", "state": "present"})

        data = result.value.args[0]
        assert data["failed"] is True
        assert "LDAP error" in data["msg"]

    def test_domain_remove_failure(self, mock_yunohost, ansible_module):
        """fail_json when domain_remove raises an exception."""
        mock_domain = mock_yunohost
        mock_domain.domain_list.return_value = {
            "domains": ["fail.tld"],
            "main": "other.tld",
        }
        mock_domain.domain_remove.side_effect = Exception("Cannot remove main domain")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(mock_domain, {"name": "fail.tld", "state": "absent"})

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Cannot remove main domain" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"name": "test.tld"})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
