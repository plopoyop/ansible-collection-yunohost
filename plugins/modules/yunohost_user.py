#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_user
short_description: Manage YunoHost users
version_added: "1.0.0"
description:
  - Create, update, or delete users on a YunoHost server.
  - Idempotent — existing users are only updated when attributes differ.
options:
  name:
    description:
      - The username to manage.
    required: true
    type: str
  state:
    description:
      - Whether the user should exist or not.
    choices: ['present', 'absent']
    default: present
    type: str
  password:
    description:
      - The user password.
      - Required when C(state=present) and the user does not exist yet.
      - When set on an existing user, behavior depends on C(update_password).
    type: str
    no_log: true
  update_password:
    description:
      - C(on_create) will only set the password for new users.
      - C(always) will update the password on every run (not idempotent).
    choices: ['on_create', 'always']
    default: on_create
    type: str
  fullname:
    description:
      - The full name of the user.
      - Required when C(state=present) and the user does not exist yet.
    type: str
  domain:
    description:
      - The domain for the user's primary email address.
      - Required when C(state=present) and the user does not exist yet.
    type: str
  mailbox_quota:
    description:
      - Mailbox quota in megabytes (e.g. C(500) or C(500M) for 500 MB, C(2G) for 2 GB).
      - A bare number is treated as megabytes (like the YunoHost web interface).
      - C(0) means unlimited. Defaults to unlimited when not specified.
    type: str
  mail_forwards:
    description:
      - List of mail forwarding addresses.
      - Replaces the current list of forwards entirely.
    type: list
    elements: str
  mail_aliases:
    description:
      - List of mail alias addresses.
      - Replaces the current list of aliases entirely.
    type: list
    elements: str
  login_shell:
    description:
      - Login shell for the user.
    type: str
  admin:
    description:
      - Whether the user should be an admin.
      - Only used during user creation.
    type: bool
    default: false
  purge:
    description:
      - Remove the user's home directory and mail spool when deleting.
      - Only used when C(state=absent).
    type: bool
    default: false
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Create a user
  plopoyop.yunohost.yunohost_user:
    name: john
    fullname: John Doe
    domain: example.com
    password: "{{ vault_user_password }}"

- name: Create an admin user
  plopoyop.yunohost.yunohost_user:
    name: admin_user
    fullname: Admin User
    domain: example.com
    password: "{{ vault_admin_password }}"
    admin: true

- name: Update user mail forwards
  plopoyop.yunohost.yunohost_user:
    name: john
    mail_forwards:
      - john@external.com
      - john.backup@other.com

- name: Change user password
  plopoyop.yunohost.yunohost_user:
    name: john
    password: "{{ vault_new_password }}"

- name: Delete a user and purge data
  plopoyop.yunohost.yunohost_user:
    name: john
    state: absent
    purge: true
"""

RETURN = r"""
user:
  description: The username that was managed.
  type: str
  returned: always
  sample: john
user_info:
  description: User information after the operation (when state=present).
  type: dict
  returned: when state=present
  sample:
    username: john
    fullname: John Doe
    mail: john@example.com
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    build_diff,
    check_yunohost,
    init_yunohost,
)


def _normalize_quota(value):
    """Normalize a mailbox quota value.

    The YunoHost web interface sends a bare number (e.g. "500") and the backend
    stores it with an "M" suffix (e.g. "500M"). We replicate this behavior so
    that ``mailbox_quota: 500`` is equivalent to ``mailbox_quota: 500M``.
    "0" means unlimited and is left as-is.
    """
    value = str(value).strip()
    if value == "0":
        return "0"
    # If it's a bare number, append "M" (megabytes) like the web UI does
    if value.isdigit():
        return value + "M"
    return value


def _compute_updates(current_info, params):
    """Compute what needs to be updated. Returns a dict of update kwargs."""
    updates = {}

    if params["fullname"] is not None and params["fullname"] != current_info.get(
        "fullname"
    ):
        updates["fullname"] = params["fullname"]

    if params["password"] is not None and params["update_password"] == "always":
        updates["change_password"] = params["password"]

    if params["mailbox_quota"] is not None:
        current_quota = current_info.get("mailbox-quota", {})
        current_limit = current_quota.get("limit", "?")
        desired = _normalize_quota(params["mailbox_quota"])
        # "0" means unlimited. The limit field is a translated string when
        # unlimited (e.g. "No quota", "Pas de quota"), so we check whether
        # the current limit looks like a size value (digits + optional unit).
        current_is_unlimited = not any(c.isdigit() for c in str(current_limit))
        if desired == "0":
            if not current_is_unlimited:
                updates["mailbox_quota"] = desired
        elif current_is_unlimited or current_limit != desired:
            updates["mailbox_quota"] = desired

    if params["login_shell"] is not None:
        if params["login_shell"] != current_info.get("loginShell"):
            updates["loginShell"] = params["login_shell"]

    if params["mail_aliases"] is not None:
        current_aliases = set(current_info.get("mail-aliases", []))
        desired_aliases = set(params["mail_aliases"])
        to_add = desired_aliases - current_aliases
        to_remove = current_aliases - desired_aliases
        if to_add:
            updates["add_mailalias"] = list(to_add)
        if to_remove:
            updates["remove_mailalias"] = list(to_remove)

    if params["mail_forwards"] is not None:
        current_forwards = set(current_info.get("mail-forward", []))
        desired_forwards = set(params["mail_forwards"])
        to_add = desired_forwards - current_forwards
        to_remove = current_forwards - desired_forwards
        if to_add:
            updates["add_mailforward"] = list(to_add)
        if to_remove:
            updates["remove_mailforward"] = list(to_remove)

    return updates


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            state=dict(type="str", default="present", choices=["present", "absent"]),
            password=dict(type="str", no_log=True),
            update_password=dict(
                type="str", default="on_create", choices=["on_create", "always"]
            ),
            fullname=dict(type="str"),
            domain=dict(type="str"),
            mailbox_quota=dict(type="str"),
            mail_forwards=dict(type="list", elements="str"),
            mail_aliases=dict(type="list", elements="str"),
            login_shell=dict(type="str"),
            admin=dict(type="bool", default=False),
            purge=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    username = module.params["name"]
    state = module.params["state"]

    try:
        lock = init_yunohost()

        from yunohost.user import (
            user_create,
            user_delete,
            user_info,
            user_list,
            user_update,
        )

        try:
            exists = username in user_list()["users"]

            if state == "absent":
                if not exists:
                    module.exit_json(changed=False, user=username)
                if module.check_mode:
                    module.exit_json(changed=True, user=username)
                user_delete(username=username, purge=module.params["purge"])
                module.exit_json(
                    changed=True,
                    user=username,
                    diff=build_diff(
                        {"user": username, "state": "present"},
                        {"user": username, "state": "absent"},
                        header="yunohost user: %s" % username,
                    ),
                )

            # state == present
            if not exists:
                missing = [
                    p
                    for p in ("fullname", "domain", "password")
                    if module.params[p] is None
                ]
                if missing:
                    module.fail_json(
                        msg="Missing required parameters for user creation: %s"
                        % ", ".join(missing),
                        user=username,
                    )
                if module.check_mode:
                    module.exit_json(changed=True, user=username)

                user_create(
                    username=username,
                    domain=module.params["domain"],
                    password=module.params["password"],
                    fullname=module.params["fullname"],
                    mailbox_quota=_normalize_quota(
                        module.params["mailbox_quota"] or "0"
                    ),
                    admin=module.params["admin"],
                    loginShell=module.params["login_shell"],
                )

                if module.params["mail_aliases"] or module.params["mail_forwards"]:
                    update_kwargs = {}
                    if module.params["mail_aliases"]:
                        update_kwargs["add_mailalias"] = module.params["mail_aliases"]
                    if module.params["mail_forwards"]:
                        update_kwargs["add_mailforward"] = module.params[
                            "mail_forwards"
                        ]
                    user_update(username=username, **update_kwargs)

                info = user_info(username)
                module.exit_json(
                    changed=True,
                    user=username,
                    user_info=info,
                    diff=build_diff(
                        {"state": "absent"},
                        info,
                        header="yunohost user: %s" % username,
                    ),
                )

            # User exists — compute updates
            current = user_info(username)
            updates = _compute_updates(current, module.params)

            if not updates:
                module.exit_json(changed=False, user=username, user_info=current)
            if module.check_mode:
                module.exit_json(changed=True, user=username, user_info=current)

            user_update(username=username, **updates)
            info = user_info(username)
            module.exit_json(
                changed=True,
                user=username,
                user_info=info,
                diff=build_diff(current, info, header="yunohost user: %s" % username),
            )

        finally:
            lock.release()

    except Exception as e:
        module.fail_json(msg=str(e), user=username)


if __name__ == "__main__":
    main()
