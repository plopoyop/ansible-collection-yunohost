#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_app
short_description: Manage YunoHost applications
version_added: "1.0.0"
description:
  - Install, remove, or upgrade applications on a YunoHost server.
  - Idempotent — does not reinstall an already installed app.
options:
  name:
    description:
      - The application identifier (catalog name, git URL, or local path).
      - For installed apps, this is the app instance ID (e.g. C(nextcloud), C(wordpress__2)).
    required: true
    type: str
  state:
    description:
      - Desired state of the application.
      - C(present) ensures the app is installed.
      - C(absent) ensures the app is removed.
      - C(latest) upgrades the app if an update is available.
    choices: ['present', 'absent', 'latest']
    default: present
    type: str
  domain:
    description:
      - Domain on which to install the application.
      - Required for installation of web apps.
    type: str
  path:
    description:
      - URL path for the application (e.g. C(/), C(/app)).
      - Required for installation of web apps.
    type: str
  label:
    description:
      - Custom label for the application.
      - Only used during installation.
    type: str
  args:
    description:
      - Extra installation arguments as a dictionary or query string.
      - C(domain) and C(path) are automatically included from their dedicated parameters.
      - Use this for app-specific settings (e.g. C(admin), C(language), C(is_public)).
    type: raw
  force:
    description:
      - Force installation of experimental/low-quality apps without confirmation.
      - Force upgrade even when no update is available.
    type: bool
    default: false
  purge:
    description:
      - Remove all application data when uninstalling.
      - Only used when C(state=absent).
    type: bool
    default: false
  no_safety_backup:
    description:
      - Disable automatic safety backup before upgrading.
      - Only used when C(state=latest).
    type: bool
    default: false
  ignore_yunohost_version:
    description:
      - Ignore YunoHost version compatibility requirements.
    type: bool
    default: false
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Install an app
  plopoyop.yunohost.yunohost_app:
    name: nextcloud
    domain: cloud.example.com
    path: /
    args:
      admin: admin

- name: Install with a custom label
  plopoyop.yunohost.yunohost_app:
    name: wordpress
    domain: blog.example.com
    path: /
    label: My Blog
    args:
      admin: admin
      language: en

- name: Upgrade an app
  plopoyop.yunohost.yunohost_app:
    name: nextcloud
    state: latest

- name: Remove an app
  plopoyop.yunohost.yunohost_app:
    name: wordpress
    state: absent

- name: Remove an app and purge data
  plopoyop.yunohost.yunohost_app:
    name: wordpress
    state: absent
    purge: true
"""

RETURN = r"""
app:
  description: The application identifier.
  type: str
  returned: always
  sample: nextcloud
app_info:
  description: Application information after the operation (when state=present or latest).
  type: dict
  returned: when app is installed
  sample:
    id: nextcloud
    name: Nextcloud
    version: "1.0~ynh1"
"""

from urllib.parse import urlencode

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    build_diff,
    check_yunohost,
    init_yunohost,
)


def _build_install_args(module):
    """Build the installation args query string from module parameters."""
    params = {}

    if module.params["domain"]:
        params["domain"] = module.params["domain"]
    if module.params["path"] is not None:
        params["path"] = module.params["path"]

    # Merge extra args
    extra = module.params["args"]
    if extra is not None:
        if isinstance(extra, dict):
            params.update(extra)
        elif isinstance(extra, str):
            from urllib.parse import parse_qs

            for key, values in parse_qs(extra).items():
                params[key] = values[0] if len(values) == 1 else values

    if not params:
        return None
    return urlencode(params)


def _get_installed_apps(app_list):
    """Return a dict of installed app IDs -> app info."""
    result = app_list(full=True)
    return {app["id"]: app for app in result.get("apps", [])}


def _app_has_upgrade(app_info_fn, app_id):
    """Check if an app has an available upgrade."""
    try:
        info = app_info_fn(app_id, with_upgrade_infos=True)
        upgrade = info.get("upgrade", {})
        return upgrade.get("available", False)
    except Exception:
        return False


def _do_install(module, app_install):
    """Run app_install with the assembled arguments."""
    app_install(
        app=module.params["name"],
        label=module.params["label"],
        args=_build_install_args(module),
        force=module.params["force"],
        ignore_yunohost_version=module.params["ignore_yunohost_version"],
    )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            state=dict(
                type="str", default="present", choices=["present", "absent", "latest"]
            ),
            domain=dict(type="str"),
            path=dict(type="str"),
            label=dict(type="str"),
            args=dict(type="raw"),
            force=dict(type="bool", default=False),
            purge=dict(type="bool", default=False),
            no_safety_backup=dict(type="bool", default=False),
            ignore_yunohost_version=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    name = module.params["name"]
    state = module.params["state"]

    try:
        lock = init_yunohost()

        from yunohost.app import (
            app_change_url,
            app_info,
            app_install,
            app_list,
            app_remove,
            app_upgrade,
        )

        try:
            installed = _get_installed_apps(app_list)
            is_installed = name in installed

            # --- state=absent ---
            if state == "absent":
                if not is_installed:
                    module.exit_json(changed=False, app=name)
                if module.check_mode:
                    module.exit_json(changed=True, app=name)

                app_remove(app=name, purge=module.params["purge"])
                module.exit_json(
                    changed=True,
                    app=name,
                    diff=build_diff(
                        {"app": name, "state": "present"},
                        {"app": name, "state": "absent"},
                        header="yunohost app: %s" % name,
                    ),
                )

            # --- state=present ---
            if state == "present":
                if is_installed:
                    # Check if domain/path needs to change
                    changed = False
                    current = installed[name]
                    desired_domain = module.params["domain"]
                    desired_path = module.params["path"]

                    if desired_domain or desired_path is not None:
                        current_domain_path = current.get("domain_path", "")
                        if current_domain_path:
                            cur_domain, cur_path = (
                                current_domain_path.split("/", 1)
                                if "/" in current_domain_path
                                else (current_domain_path, "")
                            )
                            cur_path = "/" + cur_path
                        else:
                            cur_domain, cur_path = "", ""

                        new_domain = desired_domain or cur_domain
                        new_path = (
                            desired_path if desired_path is not None else cur_path
                        )

                        if new_domain != cur_domain or new_path != cur_path:
                            if module.check_mode:
                                module.exit_json(
                                    changed=True, app=name, app_info=current
                                )
                            app_change_url(app=name, domain=new_domain, path=new_path)
                            changed = True

                    if not changed:
                        module.exit_json(changed=False, app=name, app_info=current)

                    info = app_info(name, full=True)
                    module.exit_json(
                        changed=True,
                        app=name,
                        app_info=info,
                        diff=build_diff(
                            current, info, header="yunohost app: %s" % name
                        ),
                    )

                if module.check_mode:
                    module.exit_json(changed=True, app=name)

                _do_install(module, app_install)

                info = app_info(name, full=True)
                module.exit_json(
                    changed=True,
                    app=name,
                    app_info=info,
                    diff=build_diff(
                        {"state": "absent"},
                        {
                            "state": "present",
                            "id": name,
                            "version": info.get("version", ""),
                        },
                        header="yunohost app: %s" % name,
                    ),
                )

            # --- state=latest ---
            if state == "latest":
                if not is_installed:
                    if module.check_mode:
                        module.exit_json(changed=True, app=name)

                    _do_install(module, app_install)

                    info = app_info(name, full=True)
                    module.exit_json(changed=True, app=name, app_info=info)

                has_upgrade = _app_has_upgrade(app_info, name)

                if not has_upgrade and not module.params["force"]:
                    module.exit_json(
                        changed=False,
                        app=name,
                        app_info=installed[name],
                    )

                if module.check_mode:
                    module.exit_json(
                        changed=True,
                        app=name,
                        app_info=installed[name],
                    )

                app_upgrade(
                    app=name,
                    force=module.params["force"],
                    no_safety_backup=module.params["no_safety_backup"],
                    ignore_yunohost_version=module.params["ignore_yunohost_version"],
                )

                info = app_info(name, full=True)
                module.exit_json(changed=True, app=name, app_info=info)

        finally:
            lock.release()

    except Exception as e:
        module.fail_json(msg=str(e), app=name)


if __name__ == "__main__":
    main()
