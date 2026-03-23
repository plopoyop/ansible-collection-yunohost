"""
Test fixtures for the YunoHost Ansible collection.

The YunoHost source code is available as a reference in tests/_vendor/yunohost/src
(git submodule) but cannot be imported directly in a dev environment due to its
many system dependencies (miniupnpc, ldap, dbus, etc.).

Testing strategy:
  - Unit tests      : mock the yunohost functions called by the modules
  - Integration tests: run on a real YunoHost machine (via molecule)
"""
