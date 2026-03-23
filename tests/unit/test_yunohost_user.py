"""Unit tests for the plopoyop.yunohost.yunohost_user module."""

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


USER_INFO_JOHN = {
    "username": "john",
    "fullname": "John Doe",
    "mail": "john@example.com",
    "loginShell": "/bin/bash",
    "mail-aliases": [],
    "mail-forward": [],
    "mailbox-quota": {"limit": "No quota", "use": "0"},
}


@pytest.fixture
def mock_yunohost(monkeypatch):
    """Inject yunohost mocks into sys.modules."""
    mock_pkg = MagicMock()
    mock_user = MagicMock()
    mock_pkg.user = mock_user

    modules = {
        "moulinette": MagicMock(),
        "yunohost": mock_pkg,
        "yunohost.user": mock_user,
    }
    for mod_name, mod_mock in modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_mock)

    return mock_user


@pytest.fixture
def ansible_module(monkeypatch):
    """Patch exit_json and fail_json on AnsibleModule."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def _get_mod():
    """Import or retrieve the cached module."""
    fqcn = "ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_user"
    if fqcn in sys.modules:
        return sys.modules[fqcn]
    import ansible_collections.plopoyop.yunohost.plugins.modules.yunohost_user as mod

    return mod


def _run_module(mock_user, args):
    """Set up mocks and execute the module."""
    set_module_args(args)
    mod = _get_mod()
    mod.check_yunohost = MagicMock()
    mod.init_yunohost = MagicMock(return_value=MagicMock())
    mod.main()


BASE_CREATE_ARGS = {
    "name": "john",
    "fullname": "John Doe",
    "domain": "example.com",
    "password": "S3cure!Pass",
}


# ---------------------------------------------------------------------------
# state=present — create
# ---------------------------------------------------------------------------


class TestUserCreate:
    def test_create_new_user(self, mock_yunohost, ansible_module):
        """Create a user that does not exist yet."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {}}
        mock_user.user_info.return_value = dict(USER_INFO_JOHN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_user, BASE_CREATE_ARGS)

        data = result.value.args[0]
        assert data["changed"] is True
        assert data["user"] == "john"
        mock_user.user_create.assert_called_once_with(
            username="john",
            domain="example.com",
            password="S3cure!Pass",
            fullname="John Doe",
            mailbox_quota="0",
            admin=False,
            loginShell=None,
        )

    def test_create_admin_user(self, mock_yunohost, ansible_module):
        """Create an admin user."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {}}
        mock_user.user_info.return_value = dict(USER_INFO_JOHN)

        with pytest.raises(AnsibleExitJson):
            _run_module(mock_user, {**BASE_CREATE_ARGS, "admin": True})

        mock_user.user_create.assert_called_once()
        call_kwargs = mock_user.user_create.call_args[1]
        assert call_kwargs["admin"] is True

    def test_create_with_aliases_and_forwards(self, mock_yunohost, ansible_module):
        """Create a user with mail aliases and forwards."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {}}
        mock_user.user_info.return_value = {
            **USER_INFO_JOHN,
            "mail-aliases": ["j@example.com"],
            "mail-forward": ["john@external.com"],
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    **BASE_CREATE_ARGS,
                    "mail_aliases": ["j@example.com"],
                    "mail_forwards": ["john@external.com"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_user.user_create.assert_called_once()
        mock_user.user_update.assert_called_once()
        update_kwargs = mock_user.user_update.call_args[1]
        assert "add_mailalias" in update_kwargs
        assert "add_mailforward" in update_kwargs


# ---------------------------------------------------------------------------
# state=present — update
# ---------------------------------------------------------------------------


class TestUserUpdate:
    def test_no_change_when_identical(self, mock_yunohost, ansible_module):
        """No change when user exists with matching attributes."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.return_value = dict(USER_INFO_JOHN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "fullname": "John Doe",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_user.user_update.assert_not_called()

    def test_update_fullname(self, mock_yunohost, ansible_module):
        """Update user's fullname."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.side_effect = [
            dict(USER_INFO_JOHN),
            {**USER_INFO_JOHN, "fullname": "Jonathan Doe"},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "fullname": "Jonathan Doe",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_user.user_update.assert_called_once()
        assert mock_user.user_update.call_args[1]["fullname"] == "Jonathan Doe"

    def test_update_password_always(self, mock_yunohost, ansible_module):
        """Password change triggers update when update_password=always."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.side_effect = [
            dict(USER_INFO_JOHN),
            dict(USER_INFO_JOHN),
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "password": "NewP4ss!",
                    "update_password": "always",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert mock_user.user_update.call_args[1]["change_password"] == "NewP4ss!"

    def test_update_password_on_create_skips_existing(
        self, mock_yunohost, ansible_module
    ):
        """Password is not changed on existing user with update_password=on_create."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.return_value = dict(USER_INFO_JOHN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "password": "NewP4ss!",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_user.user_update.assert_not_called()

    def test_mailbox_quota_bare_number_normalized(self, mock_yunohost, ansible_module):
        """A bare number like '500' is treated as '500M' and matches current state."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.return_value = {
            **USER_INFO_JOHN,
            "mailbox-quota": {"limit": "500M", "use": "10M"},
        }

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "mailbox_quota": "500",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is False
        mock_user.user_update.assert_not_called()

    def test_mailbox_quota_unlimited_idempotent(self, mock_yunohost, ansible_module):
        """No change when quota is 0 and current limit is a translated 'unlimited' string."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}

        for translated_unlimited in ["No quota", "Pas de quota", "Illimité"]:
            mock_user.user_info.return_value = {
                **USER_INFO_JOHN,
                "mailbox-quota": {"limit": translated_unlimited, "use": "0"},
            }

            with pytest.raises(AnsibleExitJson) as result:
                _run_module(
                    mock_user,
                    {
                        "name": "john",
                        "mailbox_quota": "0",
                    },
                )

            data = result.value.args[0]
            assert data["changed"] is False, (
                "Should be idempotent with limit=%r" % translated_unlimited
            )
            mock_user.user_update.assert_not_called()

    def test_update_mail_aliases(self, mock_yunohost, ansible_module):
        """Compute alias diff: add new, remove old."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.side_effect = [
            {**USER_INFO_JOHN, "mail-aliases": ["old@example.com"]},
            {**USER_INFO_JOHN, "mail-aliases": ["new@example.com"]},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "mail_aliases": ["new@example.com"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        kwargs = mock_user.user_update.call_args[1]
        assert "new@example.com" in kwargs["add_mailalias"]
        assert "old@example.com" in kwargs["remove_mailalias"]

    def test_update_mail_forwards(self, mock_yunohost, ansible_module):
        """Compute forward diff: add new, remove old."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.side_effect = [
            {**USER_INFO_JOHN, "mail-forward": ["old@ext.com"]},
            {**USER_INFO_JOHN, "mail-forward": ["new@ext.com"]},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "mail_forwards": ["new@ext.com"],
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        kwargs = mock_user.user_update.call_args[1]
        assert "new@ext.com" in kwargs["add_mailforward"]
        assert "old@ext.com" in kwargs["remove_mailforward"]

    def test_update_login_shell(self, mock_yunohost, ansible_module):
        """Update login shell."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.side_effect = [
            dict(USER_INFO_JOHN),
            {**USER_INFO_JOHN, "loginShell": "/bin/zsh"},
        ]

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "login_shell": "/bin/zsh",
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        assert mock_user.user_update.call_args[1]["loginShell"] == "/bin/zsh"


# ---------------------------------------------------------------------------
# state=absent
# ---------------------------------------------------------------------------


class TestUserDelete:
    def test_delete_existing_user(self, mock_yunohost, ansible_module):
        """Delete an existing user."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_user, {"name": "john", "state": "absent"})

        data = result.value.args[0]
        assert data["changed"] is True
        mock_user.user_delete.assert_called_once_with(
            username="john",
            purge=False,
        )

    def test_delete_nonexistent_user(self, mock_yunohost, ansible_module):
        """No change when user does not exist."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {}}

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(mock_user, {"name": "john", "state": "absent"})

        data = result.value.args[0]
        assert data["changed"] is False
        mock_user.user_delete.assert_not_called()

    def test_delete_with_purge(self, mock_yunohost, ansible_module):
        """Delete and purge home directory."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}

        with pytest.raises(AnsibleExitJson):
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "state": "absent",
                    "purge": True,
                },
            )

        mock_user.user_delete.assert_called_once_with(
            username="john",
            purge=True,
        )


# ---------------------------------------------------------------------------
# check_mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_mode_create(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without creating."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {}}

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    **BASE_CREATE_ARGS,
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_user.user_create.assert_not_called()

    def test_check_mode_delete(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without deleting."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "state": "absent",
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_user.user_delete.assert_not_called()

    def test_check_mode_update(self, mock_yunohost, ansible_module):
        """In check_mode, report changed without updating."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_info.return_value = dict(USER_INFO_JOHN)

        with pytest.raises(AnsibleExitJson) as result:
            _run_module(
                mock_user,
                {
                    "name": "john",
                    "fullname": "New Name",
                    "_ansible_check_mode": True,
                },
            )

        data = result.value.args[0]
        assert data["changed"] is True
        mock_user.user_update.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_create_failure(self, mock_yunohost, ansible_module):
        """fail_json when user_create raises an exception."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {}}
        mock_user.user_create.side_effect = Exception("system_username_exists")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(mock_user, BASE_CREATE_ARGS)

        data = result.value.args[0]
        assert data["failed"] is True
        assert "system_username_exists" in data["msg"]

    def test_delete_failure(self, mock_yunohost, ansible_module):
        """fail_json when user_delete raises an exception."""
        mock_user = mock_yunohost
        mock_user.user_list.return_value = {"users": {"john": {}}}
        mock_user.user_delete.side_effect = Exception("Cannot delete last admin")

        with pytest.raises(AnsibleFailJson) as result:
            _run_module(mock_user, {"name": "john", "state": "absent"})

        data = result.value.args[0]
        assert data["failed"] is True
        assert "Cannot delete last admin" in data["msg"]

    def test_missing_yunohost_package(self, ansible_module, monkeypatch):
        """fail_json when yunohost is not installed."""
        set_module_args({"name": "john"})
        mod = _get_mod()

        import ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost as mu

        monkeypatch.setattr(mu, "HAS_YUNOHOST", False)
        mod.check_yunohost = mu.check_yunohost

        with pytest.raises(AnsibleFailJson) as result:
            mod.main()

        data = result.value.args[0]
        assert data["failed"] is True
        assert "YunoHost" in data["msg"]
