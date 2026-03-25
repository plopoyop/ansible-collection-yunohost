#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_domain_config
short_description: Manage YunoHost domain configuration
version_added: "1.0.0"
description:
  - Get or set configuration options for a YunoHost domain.
  - Supports mail settings, portal customization, default app, and more.
  - Only changed settings are applied (idempotent).
options:
  name:
    description:
      - The domain name to configure.
    required: true
    type: str
  settings:
    description:
      - Dictionary of settings to apply.
      - Only settings that differ from the current state will be changed.
      - "Common keys: C(mail_in), C(mail_out) (bool): enable/disable incoming/outgoing mail."
      - "C(default_app) (str): set the default web app for the domain."
      - "C(portal_title) (str): portal page title (top-level domains only)."
      - "C(portal_theme) (str): portal theme (system, light, dark, etc.)."
      - "C(portal_tile_theme) (str): tile layout (descriptive, simple, periodic)."
      - "C(enable_public_apps_page) (bool): show public apps page."
      - "C(show_other_domains_apps) (bool): show apps from other domains."
      - "C(custom_css) (str): custom CSS for the portal."
      - "C(search_engine) (str): search engine URL."
      - "C(portal_user_intro) (str): portal intro text for logged-in users."
      - "C(portal_public_intro) (str): portal intro text for public visitors."
    required: true
    type: dict
  ignore_unavailable:
    description:
      - Skip settings that are not available for this domain instead of failing.
      - Useful when applying the same settings dict to both top-level and subdomains,
        since portal settings are only available on top-level domains.
    type: bool
    default: false
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Disable incoming mail for a domain
  plopoyop.yunohost.yunohost_domain_config:
    name: example.com
    settings:
      mail_in: false

- name: Configure portal appearance
  plopoyop.yunohost.yunohost_domain_config:
    name: example.com
    settings:
      portal_title: "My Server"
      portal_theme: dark
      portal_tile_theme: simple
      enable_public_apps_page: true

- name: Set default app and disable outgoing mail
  plopoyop.yunohost.yunohost_domain_config:
    name: example.com
    settings:
      default_app: nextcloud
      mail_out: false
"""

RETURN = r"""
domain:
  description: The domain name that was configured.
  type: str
  returned: always
  sample: example.com
changed_settings:
  description: Dictionary of settings that were actually changed (old -> new).
  type: dict
  returned: always
  sample: {"mail_in": {"before": 1, "after": 0}}
current_settings:
  description: All current settings after the operation.
  type: dict
  returned: always
  sample: {"mail_in": 1, "mail_out": 1}
skipped_settings:
  description: Settings that were skipped because they are not available for this domain.
  type: list
  elements: str
  returned: when ignore_unavailable is true and settings were skipped
  sample: ["portal_title", "portal_theme"]
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    check_yunohost,
    init_yunohost,
)


def _build_key_path_map(domain_config_get, domain):
    """Build a mapping of option_id -> full key path (panel.section.option)."""
    full = domain_config_get(domain, full=True)
    key_map = {}
    for panel in full.get("panels", []):
        panel_id = panel.get("id", "")
        for section in panel.get("sections", []):
            section_id = section.get("id", "")
            for option in section.get("options", []):
                option_id = option.get("id", "")
                if option_id:
                    key_map[option_id] = "%s.%s.%s" % (panel_id, section_id, option_id)
    return key_map


def _normalize_value(value):
    """Normalize a value for comparison (bool -> int, etc.)."""
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            settings=dict(type="dict", required=True),
            ignore_unavailable=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    name = module.params["name"]
    desired = module.params["settings"]
    ignore_unavailable = module.params["ignore_unavailable"]

    try:
        lock = init_yunohost()

        from yunohost.domain import domain_config_get, domain_config_set

        try:
            current = domain_config_get(name, export=True)
            key_path_map = _build_key_path_map(domain_config_get, name)

            # Validate requested settings and filter unavailable ones
            skipped_settings = []
            valid_desired = {}
            for key, desired_value in desired.items():
                if key not in key_path_map:
                    if ignore_unavailable:
                        skipped_settings.append(key)
                        continue
                    module.fail_json(
                        msg="Unknown setting '%s'. Available: %s"
                        % (key, ", ".join(sorted(key_path_map.keys()))),
                        domain=name,
                    )
                valid_desired[key] = desired_value

            # Compute diff
            changed_settings = {}
            for key, desired_value in valid_desired.items():
                normalized = _normalize_value(desired_value)
                current_value = current.get(key)
                if current_value != normalized:
                    changed_settings[key] = {
                        "before": current_value,
                        "after": normalized,
                    }

            result_extra = {}
            if skipped_settings:
                result_extra["skipped_settings"] = skipped_settings

            if not changed_settings:
                module.exit_json(
                    changed=False,
                    domain=name,
                    changed_settings={},
                    current_settings=current,
                    **result_extra,
                )

            if module.check_mode:
                module.exit_json(
                    changed=True,
                    domain=name,
                    changed_settings=changed_settings,
                    current_settings=current,
                    **result_extra,
                )

            for key in changed_settings:
                domain_config_set(
                    domain=name,
                    key=key_path_map[key],
                    value=_normalize_value(valid_desired[key]),
                )

            final = domain_config_get(name, export=True)

            module.exit_json(
                changed=True,
                domain=name,
                changed_settings=changed_settings,
                current_settings=final,
                **result_extra,
            )

        finally:
            lock.release()

    except Exception as e:
        import traceback

        module.fail_json(msg="%s\n%s" % (e, traceback.format_exc()), domain=name)


if __name__ == "__main__":
    main()
