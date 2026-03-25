#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_domain
short_description: Manage YunoHost domains
version_added: "1.0.0"
description:
  - Add or remove domains on a YunoHost server.
  - Set a domain as the main domain.
options:
  name:
    description:
      - The domain name to manage.
    required: true
    type: str
  state:
    description:
      - Whether the domain should exist or not.
    choices: ['present', 'absent']
    default: present
    type: str
  main:
    description:
      - Whether to set this domain as the main domain.
      - Only used when C(state=present).
    type: bool
    default: false
  remove_apps:
    description:
      - Remove applications installed on the domain when removing it.
      - Only used when C(state=absent).
    type: bool
    default: false
  force:
    description:
      - Force domain removal without confirmation prompts.
      - Only used when C(state=absent) with C(remove_apps=true).
    type: bool
    default: false
  install_letsencrypt_cert:
    description:
      - Install a Let's Encrypt certificate after adding the domain.
      - Only used when C(state=present) and the domain is being created.
    type: bool
    default: false
  ignore_dyndns:
    description:
      - Do not subscribe/unsubscribe to DynDNS when adding/removing a DynDNS domain.
    type: bool
    default: false
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Add a domain
  plopoyop.yunohost.yunohost_domain:
    name: example.com

- name: Add a domain with Let's Encrypt
  plopoyop.yunohost.yunohost_domain:
    name: sub.example.com
    install_letsencrypt_cert: true

- name: Set a domain as main domain
  plopoyop.yunohost.yunohost_domain:
    name: example.com
    main: true

- name: Remove a domain
  plopoyop.yunohost.yunohost_domain:
    name: old.example.com
    state: absent

- name: Remove a domain and its apps
  plopoyop.yunohost.yunohost_domain:
    name: old.example.com
    state: absent
    remove_apps: true
    force: true
"""

RETURN = r"""
domain:
  description: The domain name that was managed.
  type: str
  returned: always
  sample: example.com
domains:
  description: The list of all domains after the operation.
  type: list
  elements: str
  returned: always
  sample: ["example.com", "sub.example.com"]
main:
  description: The current main domain after the operation.
  type: str
  returned: always
  sample: example.com
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    check_yunohost,
    init_yunohost,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            state=dict(type="str", default="present", choices=["present", "absent"]),
            main=dict(type="bool", default=False),
            remove_apps=dict(type="bool", default=False),
            force=dict(type="bool", default=False),
            install_letsencrypt_cert=dict(type="bool", default=False),
            ignore_dyndns=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    name = module.params["name"]
    state = module.params["state"]

    try:
        lock = init_yunohost()

        from yunohost.domain import (
            domain_add,
            domain_list,
            domain_main_domain,
            domain_remove,
        )

        try:
            current = domain_list()
            exists = name in current["domains"]

            if state == "present":
                changed = False

                if not exists:
                    if module.check_mode:
                        module.exit_json(
                            changed=True,
                            domain=name,
                            domains=current["domains"],
                            main=current["main"],
                        )
                    domain_add(
                        domain=name,
                        install_letsencrypt_cert=module.params[
                            "install_letsencrypt_cert"
                        ],
                        ignore_dyndns=module.params["ignore_dyndns"],
                    )
                    changed = True

                if module.params["main"]:
                    current = domain_list()
                    if current["main"] != name:
                        if module.check_mode:
                            module.exit_json(
                                changed=True,
                                domain=name,
                                domains=current["domains"],
                                main=current["main"],
                            )
                        domain_main_domain(new_main_domain=name)
                        changed = True

            else:  # state == absent
                if not exists:
                    changed = False
                elif module.check_mode:
                    module.exit_json(
                        changed=True,
                        domain=name,
                        domains=current["domains"],
                        main=current["main"],
                    )
                else:
                    domain_remove(
                        domain=name,
                        remove_apps=module.params["remove_apps"],
                        force=module.params["force"],
                        ignore_dyndns=module.params["ignore_dyndns"],
                    )
                    changed = True

            result = domain_list()
            module.exit_json(
                changed=changed,
                domain=name,
                domains=result["domains"],
                main=result["main"],
            )

        finally:
            lock.release()

    except Exception as e:
        import traceback

        module.fail_json(msg="%s\n%s" % (e, traceback.format_exc()), domain=name)


if __name__ == "__main__":
    main()
