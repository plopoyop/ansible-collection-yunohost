#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_postinstall
short_description: Run YunoHost post-installation
version_added: "1.0.0"
description:
  - Perform the YunoHost post-installation step.
  - This configures the main domain and creates the first admin user.
  - Idempotent — does nothing if YunoHost is already installed.
options:
  domain:
    description:
      - The main domain for the YunoHost instance.
    required: true
    type: str
  username:
    description:
      - The admin username to create.
    required: true
    type: str
  fullname:
    description:
      - The full name of the admin user.
    required: true
    type: str
  password:
    description:
      - The admin password.
    required: true
    type: str
    no_log: true
  ignore_dyndns:
    description:
      - Do not subscribe to DynDNS when using a DynDNS domain.
    type: bool
    default: false
  force_diskspace:
    description:
      - Bypass the 10 GB minimum disk space requirement.
    type: bool
    default: false
  overwrite_root_password:
    description:
      - Set the root password to match the admin password.
    type: bool
    default: true
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Run YunoHost post-installation
  plopoyop.yunohost.yunohost_postinstall:
    domain: example.com
    username: admin
    fullname: Admin User
    password: "{{ vault_yunohost_admin_password }}"

- name: Post-install with forced disk space check bypass
  plopoyop.yunohost.yunohost_postinstall:
    domain: example.com
    username: admin
    fullname: Admin User
    password: "{{ vault_yunohost_admin_password }}"
    force_diskspace: true

- name: Post-install ignoring DynDNS
  plopoyop.yunohost.yunohost_postinstall:
    domain: myserver.nohost.me
    username: admin
    fullname: Admin User
    password: "{{ vault_yunohost_admin_password }}"
    ignore_dyndns: true
"""

RETURN = r"""
installed:
  description: Whether YunoHost is installed after the operation.
  type: bool
  returned: always
  sample: true
domain:
  description: The main domain configured.
  type: str
  returned: always
  sample: example.com
username:
  description: The admin username configured.
  type: str
  returned: always
  sample: admin
"""

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    build_diff,
    check_yunohost,
    init_yunohost,
)

# Same check as yunohost.is_installed() but without importing yunohost,
# which would trigger the full moulinette/logging init chain too early.
YUNOHOST_INSTALLED_MARKER = "/etc/yunohost/installed"


def main():
    module = AnsibleModule(
        argument_spec=dict(
            domain=dict(type="str", required=True),
            username=dict(type="str", required=True),
            fullname=dict(type="str", required=True),
            password=dict(type="str", required=True, no_log=True),
            ignore_dyndns=dict(type="bool", default=False),
            force_diskspace=dict(type="bool", default=False),
            overwrite_root_password=dict(type="bool", default=True, no_log=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    domain = module.params["domain"]
    username = module.params["username"]

    try:
        # Check if already installed without importing yunohost
        if os.path.isfile(YUNOHOST_INSTALLED_MARKER):
            module.exit_json(
                changed=False,
                installed=True,
                domain=domain,
                username=username,
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                installed=False,
                domain=domain,
                username=username,
            )

        lock = init_yunohost()

        from yunohost.tools import tools_postinstall

        try:
            tools_postinstall(
                domain=domain,
                username=username,
                fullname=module.params["fullname"],
                password=module.params["password"],
                ignore_dyndns=module.params["ignore_dyndns"],
                force_diskspace=module.params["force_diskspace"],
                overwrite_root_password=module.params["overwrite_root_password"],
            )
        finally:
            lock.release()

        module.exit_json(
            changed=True,
            installed=True,
            domain=domain,
            username=username,
            diff=build_diff(
                {"installed": False},
                {"installed": True, "domain": domain, "username": username},
                header="yunohost postinstall",
            ),
        )

    except Exception as e:
        import traceback

        module.fail_json(
            msg="%s\n%s" % (e, traceback.format_exc()),
            domain=domain,
            username=username,
        )


if __name__ == "__main__":
    main()
