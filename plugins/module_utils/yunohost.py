"""Shared utilities for YunoHost Ansible modules.

Provides the YunoHost context initialization required by all modules:
- Moulinette interface stub (skips interactive prompts)
- Lazy import pattern (init before importing YunoHost modules so
  YunohostLogger is registered before loggers are created)
- Lock acquisition and release
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from moulinette import Moulinette

    HAS_YUNOHOST = True
except ImportError:
    HAS_YUNOHOST = False
    Moulinette = None


class AnsibleInterface:
    """Minimal Moulinette interface stub.

    YunoHost checks ``Moulinette.interface.type`` to decide whether to show
    interactive CLI prompts. Setting ``type = "api"`` skips all of them.
    """

    type = "api"

    @staticmethod
    def prompt(*args, **kwargs):
        return ""

    @staticmethod
    def display(*args, **kwargs):
        pass


def init_yunohost():
    """Initialize the YunoHost / Moulinette context.

    This **must** be called before importing any ``yunohost.*`` module so that
    ``setLoggerClass(YunohostLogger)`` runs first and loggers created at import
    time get the ``.success()`` method.

    Returns:
        A ``MoulinetteLock`` instance that the caller must release in a
        ``finally`` block.
    """
    import os

    # Ensure the log directory exists before init_logging tries to open a
    # file handler — otherwise it fails with "Unable to configure handler 'file'".
    logdir = "/var/log/yunohost"
    if not os.path.isdir(logdir):
        os.makedirs(logdir, 0o750, exist_ok=True)

    from yunohost import init as _yunohost_init

    lock = _yunohost_init(interface="cli")
    Moulinette._interface = AnsibleInterface()
    return lock


def check_yunohost(module):
    """Fail the module early if the yunohost package is not installed."""
    if not HAS_YUNOHOST:
        module.fail_json(
            msg="This module must run on a YunoHost server "
            "with the yunohost package installed."
        )
