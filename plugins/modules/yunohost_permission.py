#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_permission
short_description: Manage YunoHost application permissions
version_added: "1.0.0"
description:
  - Set which users or groups are allowed to access a YunoHost application.
  - Idempotent — only applies changes when the allowed list differs.
  - Permissions are created by app installation. This module configures
    existing permissions, it does not create or delete them.
options:
  name:
    description:
      - The permission identifier.
      - "Format: C(app.permission) (e.g. C(nextcloud.main), C(wordpress.editors))."
      - "If no dot is present, C(.main) is appended automatically."
    required: true
    type: str
  allowed:
    description:
      - List of groups or users that should have access to this permission.
      - This is the desired final state — it replaces the current allowed list.
      - "Common values: C(all_users), C(visitors) (public), C(admins), or any custom group/user."
    required: true
    type: list
    elements: str
  label:
    description:
      - Custom display label for the permission.
      - Only applicable to app permissions, not system permissions.
    type: str
  show_tile:
    description:
      - Whether to show this permission as a tile in the SSO portal.
      - Only applicable to app permissions.
    type: bool
  protected:
    description:
      - Whether to prevent adding C(visitors) without C(force).
      - Only applicable to app permissions.
    type: bool
  force:
    description:
      - Override restrictions (e.g. allow visitors on protected permissions).
    type: bool
    default: false
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Allow all users to access nextcloud
  plopoyop.yunohost.yunohost_permission:
    name: nextcloud.main
    allowed:
      - all_users

- name: Make an app public
  plopoyop.yunohost.yunohost_permission:
    name: wordpress.main
    allowed:
      - visitors
      - all_users

- name: Restrict an app to admins only
  plopoyop.yunohost.yunohost_permission:
    name: phpmyadmin.main
    allowed:
      - admins

- name: Set a custom label and show tile
  plopoyop.yunohost.yunohost_permission:
    name: nextcloud.main
    allowed:
      - all_users
    label: My Cloud
    show_tile: true
"""

RETURN = r"""
permission:
  description: The permission identifier.
  type: str
  returned: always
  sample: nextcloud.main
allowed:
  description: The allowed groups/users after the operation.
  type: list
  elements: str
  returned: always
  sample: ["all_users"]
changed_details:
  description: What was changed (added/removed groups).
  type: dict
  returned: when changed
  sample: {"added": ["visitors"], "removed": ["admins"]}
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    build_diff,
    check_yunohost,
    init_yunohost,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            allowed=dict(type="list", elements="str", required=True),
            label=dict(type="str"),
            show_tile=dict(type="bool"),
            protected=dict(type="bool"),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    name = module.params["name"]
    # Append .main if no dot present (YunoHost convention)
    if "." not in name:
        name = name + ".main"

    desired_allowed = sorted(set(module.params["allowed"]))

    try:
        lock = init_yunohost()

        from yunohost.permission import (
            user_permission_info,
            user_permission_update,
        )

        try:
            # Read current state
            current = user_permission_info(name)
            current_allowed = sorted(current.get("allowed", []))

            # Compute diff for allowed
            to_add = sorted(set(desired_allowed) - set(current_allowed))
            to_remove = sorted(set(current_allowed) - set(desired_allowed))

            # Check other attributes
            attrs_changed = False
            if module.params["label"] is not None:
                if module.params["label"] != current.get("label"):
                    attrs_changed = True
            if module.params["show_tile"] is not None:
                if module.params["show_tile"] != current.get("show_tile"):
                    attrs_changed = True
            if module.params["protected"] is not None:
                if module.params["protected"] != current.get("protected"):
                    attrs_changed = True

            if not to_add and not to_remove and not attrs_changed:
                module.exit_json(
                    changed=False,
                    permission=name,
                    allowed=current_allowed,
                )

            if module.check_mode:
                module.exit_json(
                    changed=True,
                    permission=name,
                    allowed=desired_allowed,
                    changed_details={"added": to_add, "removed": to_remove},
                )

            # Build update kwargs
            update_kwargs = {"permission": name, "force": module.params["force"]}
            if to_add:
                update_kwargs["add"] = to_add
            if to_remove:
                update_kwargs["remove"] = to_remove
            if module.params["label"] is not None:
                update_kwargs["label"] = module.params["label"]
            if module.params["show_tile"] is not None:
                update_kwargs["show_tile"] = module.params["show_tile"]
            if module.params["protected"] is not None:
                update_kwargs["protected"] = module.params["protected"]

            result = user_permission_update(**update_kwargs)

            module.exit_json(
                changed=True,
                permission=name,
                allowed=sorted(result.get("allowed", [])),
                changed_details={"added": to_add, "removed": to_remove},
                diff=build_diff(
                    {"allowed": current_allowed},
                    {"allowed": sorted(result.get("allowed", []))},
                    header="yunohost permission: %s" % name,
                ),
            )

        finally:
            lock.release()

    except Exception as e:
        import traceback

        module.fail_json(
            msg="%s\n%s" % (e, traceback.format_exc()),
            permission=name,
        )


if __name__ == "__main__":
    main()
