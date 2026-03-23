#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, plopoyop
# GNU General Public License v2.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: yunohost_firewall
short_description: Manage YunoHost firewall ports
version_added: "1.0.0"
description:
  - Open or close ports on a YunoHost server firewall.
  - Manage UPnP port forwarding.
  - Idempotent — only applies changes when the port state differs.
options:
  port:
    description:
      - Port number or range to manage (e.g. C(80), C(8000-8100)).
    required: true
    type: raw
  protocol:
    description:
      - Network protocol.
    choices: ['tcp', 'udp', 'both']
    default: tcp
    type: str
  state:
    description:
      - Whether the port should be open or closed.
    choices: ['open', 'closed']
    default: open
    type: str
  comment:
    description:
      - Human-readable reason for opening the port.
      - Only used when C(state=open).
    type: str
    default: ""
  upnp:
    description:
      - Enable UPnP port forwarding for this port.
      - Only used when C(state=open).
    type: bool
    default: false
  no_reload:
    description:
      - Do not reload the firewall after making changes.
      - Useful when batching multiple port changes.
    type: bool
    default: false
author:
  - plopoyop
"""

EXAMPLES = r"""
- name: Open HTTP port
  plopoyop.yunohost.yunohost_firewall:
    port: 80
    protocol: tcp
    comment: HTTP

- name: Open a port range on both TCP and UDP
  plopoyop.yunohost.yunohost_firewall:
    port: "8000-8100"
    protocol: both
    comment: App ports

- name: Open a port with UPnP forwarding
  plopoyop.yunohost.yunohost_firewall:
    port: 25565
    protocol: tcp
    comment: Minecraft
    upnp: true

- name: Close a port
  plopoyop.yunohost.yunohost_firewall:
    port: 8080
    protocol: tcp
    state: closed

- name: Open multiple ports without reloading (batch)
  plopoyop.yunohost.yunohost_firewall:
    port: "{{ item.port }}"
    protocol: "{{ item.protocol | default('tcp') }}"
    comment: "{{ item.comment }}"
    no_reload: true
  loop:
    - { port: 80, comment: HTTP }
    - { port: 443, comment: HTTPS }
  notify: Reload YunoHost firewall
"""

RETURN = r"""
port:
  description: The port or range that was managed.
  type: raw
  returned: always
  sample: 80
protocol:
  description: The protocol(s) affected.
  type: str
  returned: always
  sample: tcp
opened:
  description: List of currently open TCP and UDP ports after the operation.
  type: dict
  returned: always
  sample: {"tcp": [22, 80, 443], "udp": []}
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.plopoyop.yunohost.plugins.module_utils.yunohost import (
    check_yunohost,
    init_yunohost,
)


def _get_open_ports(firewall_list):
    """Return currently open ports as {tcp: [...], udp: [...]}."""
    tcp = firewall_list(raw=False, protocol="tcp", forwarded=False)
    udp = firewall_list(raw=False, protocol="udp", forwarded=False)
    return {
        "tcp": tcp.get("tcp", []),
        "udp": udp.get("udp", []),
    }


def _normalize_port(port):
    """Normalize port to int or string range."""
    port = str(port).strip().replace(":", "-")
    if "-" not in port:
        return int(port)
    return port


def _port_is_open(firewall_list, protocol, port):
    """Check if a port is open for a given protocol."""
    result = firewall_list(raw=False, protocol=protocol, forwarded=False)
    return port in result.get(protocol, [])


def main():
    module = AnsibleModule(
        argument_spec=dict(
            port=dict(type="raw", required=True),
            protocol=dict(type="str", default="tcp", choices=["tcp", "udp", "both"]),
            state=dict(type="str", default="open", choices=["open", "closed"]),
            comment=dict(type="str", default=""),
            upnp=dict(type="bool", default=False),
            no_reload=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_yunohost(module)

    port = _normalize_port(module.params["port"])
    protocol = module.params["protocol"]
    state = module.params["state"]
    comment = module.params["comment"]
    upnp = module.params["upnp"]
    no_reload = module.params["no_reload"]

    # Determine which protocols to manage
    protocols = ["tcp", "udp"] if protocol == "both" else [protocol]

    try:
        lock = init_yunohost()

        from yunohost.firewall import firewall_close, firewall_list, firewall_open

        try:
            changed = False

            for proto in protocols:
                is_open = _port_is_open(firewall_list, proto, port)

                if state == "open" and not is_open:
                    if not module.check_mode:
                        firewall_open(
                            port=port,
                            protocol=proto,
                            comment=comment,
                            upnp=upnp,
                            no_reload=True,
                        )
                    changed = True
                elif state == "closed" and is_open:
                    if not module.check_mode:
                        firewall_close(
                            port=port,
                            protocol=proto,
                            no_reload=True,
                        )
                    changed = True

            # Reload once after all changes (unless no_reload or check_mode)
            if changed and not no_reload and not module.check_mode:
                from yunohost.firewall import firewall_reload

                firewall_reload()

            opened = _get_open_ports(firewall_list) if not module.check_mode else {}

            module.exit_json(
                changed=changed,
                port=port,
                protocol=protocol,
                opened=opened,
            )

        finally:
            lock.release()

    except Exception as e:
        module.fail_json(msg=str(e), port=port, protocol=protocol)


if __name__ == "__main__":
    main()
