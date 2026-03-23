#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_settings
short_description: Manage YunoHost global settings
version_added: "1.0.0"
description:
  - Get or set global configuration settings for a YunoHost server.
  - Supports security, email, network, and miscellaneous settings.
  - Only changed settings are applied (idempotent).
options:
  settings:
    description:
      - Dictionary of settings to apply.
      - Only settings that differ from the current state will be changed.
      - "Security: C(admin_strength), C(user_strength) (select): password strength."
      - "SSH: C(ssh_port) (int), C(ssh_compatibility) (select), C(ssh_password_authentication) (bool)."
      - "NGINX: C(nginx_redirect_to_https) (bool), C(nginx_compatibility) (select)."
      - "Email: C(pop3_enabled) (bool), C(smtp_relay_enabled) (bool), C(smtp_relay_host) (str)."
      - "Network: C(dns_exposure) (select), C(dns_custom_resolvers_enabled) (bool)."
      - "Misc: C(backup_compress_tar_archives) (bool)."
    required: true
    type: dict
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Configure SSH settings
  plopoyop.yunohost.yunohost_settings:
    settings:
      ssh_port: 2222
      ssh_password_authentication: false

- name: Configure SMTP relay
  plopoyop.yunohost.yunohost_settings:
    settings:
      smtp_relay_enabled: true
      smtp_relay_host: smtp.relay.example.com
      smtp_relay_port: 587
      smtp_relay_user: relay_user
      smtp_relay_password: relay_password

- name: Harden password policy
  plopoyop.yunohost.yunohost_settings:
    settings:
      admin_strength: 3
      user_strength: 2

- name: Enable HTTPS redirect and modern TLS
  plopoyop.yunohost.yunohost_settings:
    settings:
      nginx_redirect_to_https: true
      nginx_compatibility: modern
"""

RETURN = r"""
changed_settings:
  description: Dictionary of settings that were actually changed (old -> new).
  type: dict
  returned: always
  sample: {"ssh_port": {"before": 22, "after": 2222}}
current_settings:
  description: Current values for the requested settings after the operation.
  type: dict
  returned: always
  sample: {"ssh_port": 2222}
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    check_yunohost,
    init_yunohost,
)


CONFIG_TOML_PATH = "/usr/share/yunohost/config_global.toml"


def _build_key_path_map():
    """Build a mapping of option_id -> full key path (panel.section.option).

    Parses the TOML config definition file directly to avoid triggering
    ConfigPanel form evaluation, which raises KeyError on conditional options
    (e.g. smtp_relay_host depends on smtp_relay_enabled).
    """
    import toml

    config = toml.load(CONFIG_TOML_PATH)
    key_map = {}
    for panel_id, panel in config.items():
        if not isinstance(panel, dict):
            continue
        for section_key, section in panel.items():
            if not isinstance(section, dict):
                continue
            # section_key is "panel.section", extract section_id
            parts = section_key.split(".")
            section_id = parts[-1] if parts else section_key
            for option_key, option in section.items():
                if not isinstance(option, dict) or "type" not in option:
                    continue
                # option_key is "panel.section.option", extract option_id
                option_parts = option_key.split(".")
                option_id = option_parts[-1] if option_parts else option_key
                key_map[option_id] = "%s.%s.%s" % (panel_id, section_id, option_id)
    return key_map


def _get_current_value(settings_get, full_key):
    """Read the current value of a single setting by its full key path."""
    try:
        return settings_get(key=full_key)
    except Exception:
        return None


def _normalize_value(value):
    """Normalize a value for comparison (bool -> int, etc.)."""
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def main():
    module = AnsibleModule(
        argument_spec=dict(
            settings=dict(type="dict", required=True),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    desired = module.params["settings"]

    try:
        lock = init_yunohost()

        from yunohost.settings import settings_get, settings_set

        try:
            # Build option_id -> full key path mapping from the TOML definition
            key_path_map = _build_key_path_map()

            # Validate requested settings
            for key in desired:
                if key not in key_path_map:
                    module.fail_json(
                        msg="Unknown setting '%s'. Available: %s"
                        % (key, ", ".join(sorted(key_path_map.keys()))),
                    )

            # Read current values — some may fail if they depend on a
            # conditional toggle that is currently off (e.g. smtp_relay_host
            # is unreadable when smtp_relay_enabled=false). We store None
            # for those, which will always diff against the desired value.
            current = {}
            for key in desired:
                current[key] = _get_current_value(settings_get, key_path_map[key])

            # Compute diff
            changed_settings = {}
            for key, desired_value in desired.items():
                normalized = _normalize_value(desired_value)
                current_value = current.get(key)
                if current_value != normalized:
                    changed_settings[key] = {
                        "before": current_value,
                        "after": normalized,
                    }

            if not changed_settings:
                module.exit_json(
                    changed=False,
                    changed_settings={},
                    current_settings=current,
                )

            if module.check_mode:
                module.exit_json(
                    changed=True,
                    changed_settings=changed_settings,
                    current_settings=current,
                )

            # Apply all changed settings at once using the `args` parameter.
            # This is required because settings_set evaluates visibility
            # conditions (e.g. smtp_relay_host has visible="smtp_relay_enabled")
            # and needs all related values in the context at the same time.
            from urllib.parse import urlencode

            args_dict = {
                key: _normalize_value(desired[key]) for key in changed_settings
            }
            settings_set(args=urlencode(args_dict))

            # Re-read changed settings
            final = {}
            for key in desired:
                final[key] = _get_current_value(settings_get, key_path_map[key])

            module.exit_json(
                changed=True,
                changed_settings=changed_settings,
                current_settings=final,
            )

        finally:
            lock.release()

    except Exception as e:
        import traceback

        module.fail_json(msg="%s\n%s" % (e, traceback.format_exc()))


if __name__ == "__main__":
    main()
