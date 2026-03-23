# Ansible Collection — plopoyop.yunohost

Ansible collection to install and configure [YunoHost](https://yunohost.org) servers.

## Requirements

- Ansible >= 2.15
- Target: Debian 12 (Bookworm) with YunoHost installed
- `become: true` required (all modules need root access)

## Roles

| Role | Description |
|---|---|
| `plopoyop.yunohost.install` | Install YunoHost on a fresh Debian 12 system |
| `plopoyop.yunohost.configure` | Configure a YunoHost server (postinstall, settings, domains, users, firewall, apps, permissions) |

## Modules

| Module | Description |
|---|---|
| `yunohost_postinstall` | Run YunoHost post-installation |
| `yunohost_settings` | Manage global settings (security, email, network) |
| `yunohost_domain` | Manage domains (add, remove, set main) |
| `yunohost_domain_config` | Configure domain settings (mail, portal, etc.) |
| `yunohost_user` | Manage users (create, update, delete) |
| `yunohost_firewall` | Manage firewall ports (open, close) |
| `yunohost_app` | Manage applications (install, remove, upgrade) |
| `yunohost_permission` | Manage app permissions (who can access what) |

## Quick start

```yaml
- hosts: yunohost_servers
  become: true
  roles:
    - role: plopoyop.yunohost.install

    - role: plopoyop.yunohost.configure
      vars:
        yunohost_main_domain: example.com
        yunohost_admin_username: admin
        yunohost_admin_fullname: Admin User
        yunohost_admin_password: "{{ vault_admin_password }}"

        yunohost_settings_security:
          ssh_port: 2222

        yunohost_domains:
          - name: example.com
            main: true
          - name: cloud.example.com

        yunohost_users:
          - name: john
            fullname: John Doe
            domain: example.com
            password: "{{ vault_john_password }}"

        yunohost_apps:
          - name: nextcloud
            domain: cloud.example.com
            path: /
            args:
              admin: admin

        yunohost_permissions:
          - name: nextcloud
            allowed: [all_users]
```

## License

GPL-2.0-or-later
