# Plugins

## Modules

| Module | Description |
|---|---|
| `yunohost_postinstall` | Run YunoHost post-installation (main domain + first admin user) |
| `yunohost_domain` | Manage domains (add, remove, set main) |
| `yunohost_domain_config` | Configure domain settings (mail, portal, default app) |
| `yunohost_user` | Manage users (create, update, delete) |
| `yunohost_firewall` | Manage firewall ports (open, close, UPnP) |
| `yunohost_settings` | Manage global settings (security, email, network) |
| `yunohost_app` | Manage applications (install, remove, upgrade, change URL) |
| `yunohost_permission` | Manage app permissions (who can access what) |

All modules require `become: true` (root access) on the target YunoHost server.

## Module utilities

| File | Description |
|---|---|
| `module_utils/yunohost.py` | Shared YunoHost context initialization, Moulinette interface stub, lock management |
